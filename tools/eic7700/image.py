#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build EIC7700 SPI firmware and UART DDR recovery images."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from firmware_image import (IMAGE_BYTES, FIRMWARE_BYTES, COREBOOT_BYTES,
                            SCPU_ADDRESS, MCPU_ADDRESS, FHT_MAGIC,
                            SIGNATURE_MAGIC, STAGE_TYPES, HEADER, ENTRY,
                            SIGNATURE_BYTES, entries)
FIRST_STAGE_OFFSET = 0x200
STAGE_GAP = 0x200
STAGE_ALIGNMENT = 32
HEX_RECORD_BYTES = 16
UART_TABLE_ADDRESS = 0x3000c000
UART_STAGE_ADDRESSES = (0x30008000, SCPU_ADDRESS, 0x80000000)
# Four harts wait at a compressed J 0 instruction until JTAG loads coreboot.
MCPU_WAIT = struct.pack('<H', 0xa001) * 8
DDR_HEADER = struct.Struct('<4s8s6I')


def ddr_payloads(data):
    """Validate the dispatcher layout and return its two vendor programs."""
    if len(data) < DDR_HEADER.size or len(data) >= 0x100000:
        raise ValueError('invalid DDR dispatcher size')
    jump, magic, version, normal, normal_size, ecc, ecc_size, entry = DDR_HEADER.unpack_from(data)
    instruction = int.from_bytes(jump, 'little')
    target = ((instruction >> 31) << 20 | ((instruction >> 12) & 255) << 12 |
              ((instruction >> 20) & 1) << 11 | ((instruction >> 21) & 1023) << 1)
    if (magic != b'RUYIDDR\0' or version != 1 or instruction & 0xfff != 0x6f
            or target != entry or normal < DDR_HEADER.size or normal % 0x1000
            or not normal_size or not ecc_size or ecc % 0x1000
            or ecc < normal + normal_size or entry < ecc + ecc_size
            or entry >= len(data) or entry < max(normal_size, ecc_size)):
        raise ValueError('invalid DDR dispatcher layout')
    return data[normal:normal + normal_size], data[ecc:ecc + ecc_size]


def hex_record(kind, address, data=b''):
    record = struct.pack('>BHB', len(data), address, kind) + data
    return ':' + (record + bytes((-sum(record) & 255,))).hex().upper() + '\n'


def uart_transfer(address, data):
    if not data or address < 0 or address + len(data) > 1 << 32:
        raise ValueError('invalid UART transfer range')
    records = []
    upper = None
    offset = 0
    while offset < len(data):
        current = address + offset
        if upper != current >> 16:
            upper = current >> 16
            records.append(hex_record(4, 0, upper.to_bytes(2, 'big')))
        size = min(HEX_RECORD_BYTES, len(data) - offset, 0x10000 - (current & 0xffff))
        records.append(hex_record(0, current & 0xffff, data[offset:offset + size]))
        offset += size
    return ''.join(records) + hex_record(1, 0)



def uart_images(image):
    """Decode the ordered HEX files consumed by the ROM UART protocol.

    Signatures and payloads deliberately use the same addresses. Each EOF
    terminates one transfer, so these must not be flattened into a memory map.
    """
    transfers = []
    data = bytearray()
    base = None
    upper = 0
    for line in image.decode('ascii').splitlines():
        if not line.startswith(':'):
            raise ValueError('invalid UART HEX record')
        record = bytes.fromhex(line[1:])
        if len(record) < 5 or len(record) != record[0] + 5 or sum(record) & 255:
            raise ValueError('invalid UART HEX length or checksum')
        size, address, kind = struct.unpack_from('>BHB', record)
        payload = record[4:-1]
        if kind == 4 and size == 2 and address == 0:
            upper = int.from_bytes(payload, 'big') << 16
        elif kind == 0 and size:
            address += upper
            if base is None:
                base = address
            if address != base + len(data):
                raise ValueError('non-contiguous UART transfer')
            data.extend(payload)
        elif kind == 1 and size == 0 and address == 0 and base is not None:
            transfers.append((base, bytes(data)))
            base, data, upper = None, bytearray(), 0
        else:
            raise ValueError('unsupported UART HEX record')
    if base is not None or len(transfers) != 7:
        raise ValueError('expected seven complete UART transfers')
    return transfers


def check_uart(image):
    transfers = uart_images(image)
    table_address, table = transfers[0]
    if (table_address != UART_TABLE_ADDRESS or len(table) != HEADER.size + 3 * ENTRY.size
            or HEADER.unpack_from(table) != (FHT_MAGIC, 3)):
        raise ValueError('invalid UART boot table')
    stages = []
    for index, address in enumerate(UART_STAGE_ADDRESSES):
        sig_address, signature = transfers[1 + 2 * index]
        payload_address, payload = transfers[2 + 2 * index]
        version, offset, size, sign, key, kind, last, padding, r1, r2 = ENTRY.unpack_from(
            table, HEADER.size + index * ENTRY.size)
        if (version != 1 or sign or key or kind != STAGE_TYPES[index]
                or last != (index == 2) or padding != bytes(4) or r1 or r2
                or offset % 32 or size != len(payload) or not size
                or sig_address != address or payload_address != address
                or len(signature) != SIGNATURE_BYTES):
            raise ValueError(f'invalid UART boot stage {index}')
        fields = struct.unpack_from('<IIQQQQQ', signature)
        if (fields != (SIGNATURE_MAGIC, 0, 0, offset, size, 0, address)
                or signature[48:51] != bytes(3)
                or signature[64:66] != bytes((kind, last))):
            raise ValueError(f'invalid UART signature {index}')
        stages.append(payload)
    if stages[2] != MCPU_WAIT:
        raise ValueError('UART recovery does not park the MCPU harts')
    return stages


def pack(stages, uart=False):
    """Encode the ROM's three-stage plaintext format, without signing keys."""
    if len(stages) != len(STAGE_TYPES):
        raise ValueError('expected system initialization, DDR and MCPU stages')
    table = bytearray(HEADER.pack(FHT_MAGIC, len(stages)))
    offset = FIRST_STAGE_OFFSET
    sections = []
    for index, (data, name, address) in enumerate(stages):
        if not data or offset + SIGNATURE_BYTES + len(data) > FIRMWARE_BYTES:
            raise ValueError(f'{name}: empty stage or firmware area exceeded')
        last = int(index == len(stages) - 1)
        kind = STAGE_TYPES[index]
        table.extend(ENTRY.pack(1, offset, len(data), 0, 0, kind, last, bytes(4), 0, 0))
        # Plaintext headers have no digest or cryptographic signature. Keep
        # reserved fields and the unused signature area zero, as in nsign.
        header = bytearray(SIGNATURE_BYTES)
        struct.pack_into('<IIQQQQQ', header, 0, SIGNATURE_MAGIC, 0, 0, offset,
                         len(data), 0 if uart else address, address)
        header[53:56] = b'eng'
        header[64:66] = bytes((kind, last))  # Only the final stage uses MCPU.
        sections.append((offset, address, header, data))
        # Match the vendor layout, including its extra alignment unit when
        # the end of the stage and its gap are already aligned.
        offset = ((offset + SIGNATURE_BYTES + len(data) + STAGE_GAP)
                  // STAGE_ALIGNMENT + 1) * STAGE_ALIGNMENT
    if uart:
        output = uart_transfer(UART_TABLE_ADDRESS, table)
        for _, address, header, data in sections:
            output += uart_transfer(address, header) + uart_transfer(address, data)
        return output.encode('ascii')
    image = bytearray(b'\xff' * IMAGE_BYTES)
    image[:len(table)] = table
    for offset, _, header, data in sections:
        image[offset:offset + SIGNATURE_BYTES + len(data)] = header + data
    return image


def spi_image(args):
    rom = args.rom.read_bytes()
    if len(rom) != COREBOOT_BYTES:
        raise ValueError('coreboot must be a 4 MiB RAM image')
    stages = [
        (args.sys_init.read_bytes(), 'sys-init.bin', SCPU_ADDRESS),
        (args.ddr.read_bytes(), 'ddr.bin', SCPU_ADDRESS),
        (rom, 'coreboot.rom', MCPU_ADDRESS),
    ]
    image = pack(stages)
    records = entries(image)
    manifest = []
    for (offset, size, kind, last), stage in zip(records, stages):
        data = stage[0]
        if size != len(data) or image[offset + SIGNATURE_BYTES:offset + SIGNATURE_BYTES + size] != data:
            raise ValueError('packed payload differs from input')
        manifest.append({'file': stage[1], 'offset': offset, 'size': size,
                         'load': stage[2], 'kind': kind, 'last': last,
                         'sha256': hashlib.sha256(data).hexdigest()})
    return image, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest='format', required=True)
    for name in ('nor', 'uart'):
        command = commands.add_parser(name, allow_abbrev=False)
        for option in ('sys-init', 'ddr', 'output'):
            command.add_argument('--' + option, type=Path, required=True)
        if name == 'nor':
            command.add_argument('--rom', type=Path, required=True)
    args = parser.parse_args()
    if args.format == 'nor':
        image, manifest = spi_image(args)
    else:
        stages = [
            (args.sys_init.read_bytes(), 'sys-init.bin', UART_STAGE_ADDRESSES[0]),
            (args.ddr.read_bytes(), 'ddr.bin', UART_STAGE_ADDRESSES[1]),
            (MCPU_WAIT, 'wait.bin', UART_STAGE_ADDRESSES[2]),
        ]
        image = pack(stages, uart=True)
        if check_uart(image) != [stage[0] for stage in stages]:
            raise ValueError('UART recovery payload differs from input')
        manifest = [{'file': stage[1], 'load': stage[2], 'size': len(stage[0]),
                     'sha256': hashlib.sha256(stage[0]).hexdigest()} for stage in stages]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    print(json.dumps({'image': str(args.output), 'bytes': len(image),
                     'sha256': hashlib.sha256(image).hexdigest(), 'stages': manifest}, indent=2))


if __name__ == '__main__':
    main()
