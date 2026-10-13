#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Encode native K3 BootROM RAM images and 8 MiB SPI images."""
import argparse
import hashlib
from pathlib import Path
import struct
import zlib

LIMIT = 0x74000


def bootrom_payload(path):
    image = path.read_bytes()
    if len(image) != 0x800000 or image[8:12] != b'NORF':
        raise ValueError('Expected a packaged K3 SPI image')
    start = 0x20000
    header = image[start + 0xfe0:start + 0x1000]
    magic, version, secure, reserved, size, address, header_crc, body_crc = struct.unpack('<4sBBHQQII', header)
    total = 0x1000 + size + 0x100
    body = image[start + 0x1000:start + 0x1000 + size]
    if magic != b'AIHD' or version != 1 or secure or not size or size % 32 or total > LIMIT:
        raise ValueError('Invalid BootROM payload header')
    if zlib.crc32(header[:24]) != header_crc or zlib.crc32(body) != body_crc:
        raise ValueError('BootROM payload CRC mismatch')
    return image[start:start + total]


def wrap(payload):
    body = bytes(payload) + bytes((-len(payload)) % 32)
    if not body or 0x1000 + len(body) + 0x100 > LIMIT:
        raise ValueError('BootROM container exceeds the 0x74000-byte limit')
    header = struct.pack('<4sBBHQQ', b'AIHD', 1, 0, 0, len(body), 0)
    header += struct.pack('<II', zlib.crc32(header), zlib.crc32(body))
    # Non-secure images carry no public keys or certificates. Reserved
    # configuration and signature fields are zero-filled.
    result = bytearray(0x1000 + len(body) + 0x100)
    first = struct.pack('<4sBBHQQ', b'AIHD', 1, 0, 0, 0xfe0, 0xc0800000)
    first += struct.pack('<II', zlib.crc32(first), 0)
    result[0x100:0x120] = first
    result[0xfe0:0x1000] = header
    result[0x1000:0x1000 + len(body)] = body
    return result


def nor_header():
    header = bytearray(80)
    struct.pack_into('<II4s', header, 0, 0xb00714f0, 0x10001, b'NORF')
    struct.pack_into('<III', header, 16, 256, 0x10000, 0x800000)
    struct.pack_into('<III', header, 32, 0x20000, 0, LIMIT)
    struct.pack_into('<I', header, 64, zlib.crc32(header[:64]))
    return header


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    ram = commands.add_parser('ram', help='Extract the BootROM entry from the matching normal SPI image')
    ram.add_argument('--rom', type=Path, required=True)
    ram.add_argument('--output', type=Path, required=True)
    nor = commands.add_parser('nor', help='Wrap the CBFS-populated coreboot ROM for SPI boot')
    nor.add_argument('--rom', type=Path, required=True)
    nor.add_argument('--bootblock', type=Path, required=True)
    nor.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'ram':
        result = bootrom_payload(args.rom)
    else:
        result = bytearray(args.rom.read_bytes())
        if len(result) != 0x800000 or result[0x1b0000:0x1b0008] != b'__FMAP__':
            raise ValueError('Expected the K3 8 MiB coreboot NOR layout')
        # cbfstool updates the metadata hash anchor inside the ROM. Use those
        # bytes, not the unpatched intermediate bootblock file.
        payload = result[0x20000:0x20000 + args.bootblock.stat().st_size]
        container = wrap(payload)
        result[0x20000:0xa0000] = b'\xff' * 0x80000
        result[0x20000:0x20000 + len(container)] = container
        result[:80] = nor_header()
        result[0x10000:0x20000] = b'\xff' * 0x10000
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    print(f'{args.output}: {len(result)} bytes, SHA256 {hashlib.sha256(result).hexdigest()}')


if __name__ == '__main__':
    main()
