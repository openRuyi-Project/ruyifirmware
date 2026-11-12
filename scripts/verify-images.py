#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify firmware containers and embedded payloads for a board build."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from k3 import image as k3image
from eic7700 import image as eic7700image
import settings

# UEFI PI firmware-volume header, coreboot payload segments, and DTB header.
FV_HEADER = struct.Struct('<16s16sQ4sIHHHBB')
PAYLOAD_SEGMENT = struct.Struct('>4sIIQII')
DTB_HEADER = struct.Struct('>10I')
DTB_MAGIC = 0xd00dfeed
CBFS_COMPRESS_NONE = 0
CBFS_COMPRESS_LZMA = 1


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def jump_target(data):
    """Decode the signed displacement of a RISC-V JAL x0 instruction."""
    insn = struct.unpack_from('<I', data)[0]
    require(insn & 0xfff == 0x6f, 'missing RISC-V entry jump')
    relative = ((insn >> 31) << 20 | ((insn >> 12) & 0xff) << 12 |
                ((insn >> 20) & 1) << 11 | ((insn >> 21) & 0x3ff) << 1)
    if relative & (1 << 20):
        relative -= 1 << 21
    return relative


def check_fd(fd, size):
    require(len(fd) == size and size >= FV_HEADER.size, 'invalid firmware volume size')
    _, _, length, signature, _, header, _, _, _, _ = FV_HEADER.unpack_from(fd)
    require(signature == b'_FVH' and length == size, 'invalid firmware volume header')
    require(FV_HEADER.size <= header <= size and not header % 2, 'invalid FV header length')
    require(sum(word for (word,) in struct.iter_unpack('<H', fd[:header])) & 0xffff == 0,
            'invalid FV checksum')
    require(header <= jump_target(fd) < size, 'entry jump leaves the FV')


def check_payload(payload, fd, address):
    header_size = 2 * PAYLOAD_SEGMENT.size  # CODE followed by ENTR
    require(len(payload) >= header_size, 'truncated CBFS payload')
    kind, compression, offset, load, size, memory = PAYLOAD_SEGMENT.unpack_from(payload)
    entry_kind, entry_compression, entry_offset, entry, entry_size, entry_memory = PAYLOAD_SEGMENT.unpack_from(payload, PAYLOAD_SEGMENT.size)
    require(kind == b'CODE' and entry_kind == b'ENTR', 'unexpected payload segments')
    require(load == entry == address and memory == len(fd), 'payload address or memory size mismatch')
    require((entry_compression, entry_offset, entry_size, entry_memory) == (0, 0, 0, 0), 'invalid entry segment')
    require(offset == header_size and offset + size == len(payload), 'payload bounds mismatch')
    data = payload[offset:]
    if compression == CBFS_COMPRESS_LZMA:
        data = lzma.decompress(data)
    else:
        require(compression == CBFS_COMPRESS_NONE, 'unsupported payload compression')
    require(data == fd, 'embedded EDK2 differs from the build')


def check_k3(image, enabled):
    require(settings.inspect(image) == dict(emulation=enabled, pxe=False, http=False), 'platform defaults mismatch')


def check_unmatched(rom, enabled):
    _, areas = settings.read_layout(rom)
    cbfs, boot = areas['COREBOOT'], areas['BOOTBLOCK']
    require(areas['PLATFORM_CONFIG'].flags == settings.FMAP_PRESERVE, 'invalid platform settings flags')
    require(cbfs.offset + cbfs.size == len(rom), 'CBFS does not end at the image boundary')
    require(settings.inspect(rom) == dict(emulation=enabled, pxe=False, http=False), 'platform defaults mismatch')


LAYOUT_CHECKS = {'k3': check_k3, 'unmatched': check_unmatched}


def filename(value):
    if not value or Path(value).name != value or value in ('.', '..'):
        raise argparse.ArgumentTypeError('expected a filename without a directory')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('build', type=Path)
    for name in ('fd', 'dtb'):
        parser.add_argument('--' + name, type=filename, required=True)
    for name in ('dtb-entry', 'compatible'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--images', nargs='+', type=filename, required=True)
    parser.add_argument('--rom', nargs=2, action='append', metavar=('IMAGE', 'VARIANT'), required=True)
    recovery = parser.add_mutually_exclusive_group(required=True)
    recovery.add_argument('--bootrom', type=filename)
    recovery.add_argument('--bootblock', type=filename)
    recovery.add_argument('--uart', type=filename)
    parser.add_argument('--cbfstool', type=Path, required=True)
    parser.add_argument('--address', type=lambda s: int(s, 0), required=True)
    parser.add_argument('--fd-size', type=lambda s: int(s, 0), required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    options = dict(line.split('=', 1) for line in (build / 'build-options.txt').read_text().splitlines())
    board = options['BOARD']
    require(board in set(LAYOUT_CHECKS) | {'p550'}, 'unsupported firmware layout')
    require(options['EMULATION_ENABLE'] in ('TRUE', 'FALSE'), 'invalid emulation setting')
    names = set(args.images)
    require(len(names) == len(args.images), 'duplicate image filename')
    roms = dict(args.rom)
    require(len(roms) == len(args.rom), 'duplicate ROM filename')
    for name in roms:
        filename(name)
    variants = set(roms.values())
    require(len(variants) == len(roms) and variants <= {'normal', 'recovery'} and
            'normal' in variants, 'invalid or duplicate ROM variant')
    if args.bootrom:
        require(board == 'k3' and variants == {'normal'}, 'unexpected BootROM recovery inputs')
    if args.bootblock:
        require(board == 'unmatched' and variants == {'normal', 'recovery'}, 'unexpected JTAG recovery inputs')
    if args.uart:
        require(board == 'p550' and variants == {'normal', 'recovery'}, 'unexpected UART recovery inputs')
    recovery_file = args.bootrom or args.bootblock or args.uart
    require(args.fd != args.dtb and recovery_file not in roms and
            not ({args.fd, args.dtb} & (set(roms) | {recovery_file})), 'conflicting image roles')
    require(set(roms) | {recovery_file} <= names, 'missing ROM or recovery image')
    require(names <= set(roms) | {recovery_file, args.fd, args.dtb}, 'image has no validation rule')
    checksums = {}
    for line in (build / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split()
        require(name in names and name not in checksums, 'unexpected checksum entry')
        checksums[name] = digest
    require(set(checksums) == names, 'missing checksum entry')
    images = {name: (build / name).read_bytes() for name in names}
    for name, data in images.items():
        require(hashlib.sha256(data).hexdigest() == checksums[name], name + ': checksum mismatch')
    fd, dtb = (build / args.fd).read_bytes(), (build / args.dtb).read_bytes()
    check_fd(fd, args.fd_size)
    require(len(dtb) >= DTB_HEADER.size, 'truncated DTB header')
    magic, size, *_ = DTB_HEADER.unpack_from(dtb)
    require(magic == DTB_MAGIC and size == len(dtb), 'invalid DTB header')
    compatible = subprocess.check_output(['fdtget', '-t', 's', str(build / args.dtb), '/', 'compatible'], text=True).split()
    require(args.compatible in compatible, 'device tree board mismatch')
    enabled = options['EMULATION_ENABLE'] == 'TRUE'
    p550_roms = {}
    uart_stages = eic7700image.check_uart(images[args.uart], settings.STAGE_LAYOUTS['p550']) if args.uart else None
    for name, variant in roms.items():
        rom = images[name]
        if board == 'p550':
            if variant == 'normal':
                require(len(rom) == settings.STAGE_LAYOUTS['p550'].image_bytes, 'invalid P550 SPI size')
                layout = settings.STAGE_LAYOUTS['p550']
                stages = eic7700image.entries(rom, firmware_bytes=layout.firmware_bytes,
                    stage_addresses=(layout.scpu_address, layout.scpu_address, layout.mcpu_address))
                require(settings.inspect(rom) == dict(emulation=enabled, pxe=False, http=False), 'platform defaults mismatch')
                tail = bytearray(rom[settings.STAGE_LAYOUTS['p550'].firmware_bytes:])
                defaults, stride = settings.DEFAULT_LAYOUTS['p550']
                for slot in range(settings.SLOT_COUNT):
                    start = defaults + slot * stride - settings.STAGE_LAYOUTS['p550'].firmware_bytes
                    tail[start:start + stride] = b'\xff' * stride
                require(tail == b'\xff' * len(tail), 'packaged P550 persistent stores must be erased')
                for index in range(2):
                    offset, size, *_ = stages[index]
                    start = offset + eic7700image.SIGNATURE_BYTES
                    payload = rom[start:start + size]
                    if index == 0:
                        require(payload == uart_stages[index] == (build / 'sys-init.bin').read_bytes(),
                                'SPI and UART system initialization differ')
                    else:
                        normal_ddr, ecc_ddr = eic7700image.ddr_payloads(payload)
                        require(normal_ddr == uart_stages[index] == (build / 'ddr-normal.bin').read_bytes(),
                                'normal DDR payload differs from UART recovery or source')
                        require(ecc_ddr == (build / 'ddr-ecc.bin').read_bytes(),
                                'ECC DDR payload differs from source')
                offset, size, *_ = stages[2]
                start = offset + eic7700image.SIGNATURE_BYTES
                rom = rom[start:start + size]
            require(len(rom) == settings.STAGE_LAYOUTS['p550'].coreboot_bytes, 'invalid P550 RAM firmware size')
            p550_roms[variant] = rom
        else:
            detected_board, areas = settings.read_layout(rom)
            require(detected_board == board, 'ROM layout differs from the build board')
            LAYOUT_CHECKS[board](rom, enabled)
        if args.bootrom:
            require(k3image.bootrom_payload(build / name) == images[args.bootrom],
                    'BootROM recovery entry differs from the SPI image')
        if args.bootblock and variant == 'recovery':
            bootblock = images[args.bootblock]
            start = jump_target(rom)
            require(0 < len(bootblock) <= areas['BOOTBLOCK'].size - start,
                    'recovery bootblock exceeds its reservation')
            require(rom[start:start + len(bootblock)] == bootblock, 'recovery bootblock differs')
        tool = str(args.cbfstool.resolve())
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            (temp / 'rom').write_bytes(rom)
            subprocess.run([tool, str(temp / 'rom'), 'extract', '-n', args.dtb_entry, '-f', str(temp / 'dtb')], check=True)
            subprocess.run([tool, str(temp / 'rom'), 'extract', '-n', 'fallback/payload', '-U', '-f', str(temp / 'payload')], check=True)
            require((temp / 'dtb').read_bytes() == dtb, 'embedded device tree differs')
            check_payload((temp / 'payload').read_bytes(), fd, args.address)
    if p550_roms:
        require(p550_roms['normal'] == p550_roms['recovery'], 'SPI and JTAG firmware differ')
    result = {'board': board, 'compatible': args.compatible,
              'images': {name: {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                         for name, data in sorted(images.items())}}
    (build / 'image-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(board + ': containers, payloads and checksums verified')


if __name__ == '__main__':
    main()
