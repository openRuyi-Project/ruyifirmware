#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect or set the initial driver-emulation setting in a K3 or Unmatched image."""

import argparse
from collections import namedtuple
import hashlib
import json
from pathlib import Path
import struct
import zlib

# On-flash ABI shared with the platform settings libraries.
UNMATCHED_OFFSET = 0x10000
SECTOR_SIZE = 0x1000
SLOT_COUNT = 2
MAGIC = int.from_bytes(b'UMCF', 'little')
COMMIT = int.from_bytes(b'DONE', 'little')
K3_OFFSET = 0x20e000
K3_NETWORK_OFFSET = 0x20d000
K3_MAGIC = int.from_bytes(b'K3EM', 'little')
RECORD_VERSION = 1
ENABLED = 1 << 0
DEFAULT_ENABLED = 1 << 1
GENERATION_MASK = (1 << 32) - 1
GENERATION_HALF_RANGE = 1 << 31
RECORD_BODY = struct.Struct('<IHHII')
RECORD_TRAILER = struct.Struct('<II')  # CRC32 and commit marker
RECORD = struct.Struct('<IHHIIII')
K3_BODY = struct.Struct('<IHHI')
K3_RECORD = struct.Struct('<IHHII')
CRC32 = struct.Struct('<I')

FMAP_HEADER = struct.Struct('<8sBBQI32sH')
FMAP_AREA = struct.Struct('<II32sH')
FMAP_PRESERVE = 1 << 3
FlashArea = namedtuple('FlashArea', 'offset size flags')

# Accepted layouts from the coreboot board FMDs. Check these before writing
# settings, whose addresses are part of the firmware ABI, not relocatable data.
LAYOUTS = {
    0x800000: ('k3', {
        'BOOTINFO': (0x0, 0x20000),
        'BOOTBLOCK': (0x20000, 0x80000),
        'FMAP': (0x1b0000, 0x1000),
        'EARLY_RESERVED': (0x1b1000, 0x5f000),
        'COREBOOT': (0x210000, 0x300000),
        'UEFI_VARIABLES': (0x700000, 0xc0000),
    }),
    0x2000000: ('unmatched', {
        'BOOTBLOCK': (0x0, 0x10000),
        'FMAP': (0x20000, 0x200),
        'PLATFORM_CONFIG': (UNMATCHED_OFFSET, 0x10000),
        'COREBOOT': (0x20200, 0x1edfe00),
        'NVRAM': (0x1f00000, 0x90000),
    }),
}


def region_bytes(image, area):
    return image[area.offset:area.offset + area.size]


def encode(enabled, generation=0, default_enabled=None):
    if default_enabled is None:
        default_enabled = enabled
    flags = (ENABLED if enabled else 0) | (DEFAULT_ENABLED if default_enabled else 0)
    header = RECORD_BODY.pack(MAGIC, RECORD_VERSION, RECORD.size,
                              generation & GENERATION_MASK, flags)
    return header + RECORD_TRAILER.pack(zlib.crc32(header), COMMIT)


def decode(data):
    if len(data) < RECORD.size:
        return None
    magic, version, size, generation, flags, crc, commit = RECORD.unpack_from(data)
    if ((magic, version, size, commit) != (MAGIC, RECORD_VERSION, RECORD.size, COMMIT)
            or flags & ~(ENABLED | DEFAULT_ENABLED)):
        return None
    if zlib.crc32(data[:RECORD_BODY.size]) != crc:
        return None
    return {'enabled': bool(flags & ENABLED),
            'default_enabled': bool(flags & DEFAULT_ENABLED), 'generation': generation}


def read_layout(image):
    if len(image) not in LAYOUTS:
        raise ValueError('expected an 8 MiB K3 or 32 MiB Unmatched image')
    board, required = LAYOUTS[len(image)]
    fmap, fmap_size = required['FMAP']
    signature, major, minor, base, size, name, count = FMAP_HEADER.unpack_from(image, fmap)
    if (signature, major, minor, base, size, name.rstrip(b'\0')) != (b'__FMAP__', 1, 1, 0, len(image), b'FLASH'):
        raise ValueError('invalid FMAP header')
    if not count or count > (fmap_size - FMAP_HEADER.size) // FMAP_AREA.size:
        raise ValueError('invalid FMAP area count')
    areas = {}
    for index in range(count):
        offset, size, name, flags = FMAP_AREA.unpack_from(
            image, fmap + FMAP_HEADER.size + index * FMAP_AREA.size)
        name = name.rstrip(b'\0').decode('ascii')
        if not name or name in areas or offset + size > len(image):
            raise ValueError('invalid FMAP area')
        areas[name] = FlashArea(offset, size, flags)
    if any(name not in areas or areas[name][:2] != region
           for name, region in required.items()):
        raise ValueError('unsupported settings layout')
    return board, areas


def check_layout(image):
    return read_layout(image)[0]


def encode_k3(enabled):
    header = K3_BODY.pack(K3_MAGIC, RECORD_VERSION, K3_RECORD.size, int(bool(enabled)))
    return header + CRC32.pack(zlib.crc32(header))


def decode_k3(data):
    if len(data) < K3_RECORD.size:
        return None
    magic, version, size, value, crc = K3_RECORD.unpack_from(data)
    if (magic, version, size) != (K3_MAGIC, RECORD_VERSION, K3_RECORD.size) or value > 1:
        return None
    if zlib.crc32(data[:K3_BODY.size]) != crc:
        return None
    return {'enabled': bool(value)}


def inspect(image):
    if check_layout(image) == 'k3':
        return decode_k3(image[K3_OFFSET:K3_OFFSET + K3_RECORD.size])
    selected = None
    for slot in range(SLOT_COUNT):
        start = UNMATCHED_OFFSET + slot * SECTOR_SIZE
        value = decode(image[start:start + RECORD.size])
        if value is None:
            continue
        delta = 0 if selected is None else (value['generation'] - selected['generation']) & GENERATION_MASK
        if selected is None or 0 < delta < GENERATION_HALF_RANGE:
            selected = dict(value, slot=slot)
    return selected


def configure(image, enabled):
    board = check_layout(image)
    result = bytearray(image)
    record = encode_k3(enabled) if board == 'k3' else encode(enabled)
    offsets = ([K3_OFFSET] if board == 'k3' else
               [UNMATCHED_OFFSET + slot * SECTOR_SIZE for slot in range(SLOT_COUNT)])
    for start in offsets:
        result[start:start + SECTOR_SIZE] = b'\xff' * SECTOR_SIZE
        result[start:start + len(record)] = record
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--default-emulation', choices=('enabled', 'disabled'),
                        help='set the initial SPI value. K3 Setup defaults remain disabled')
    output = parser.add_mutually_exclusive_group()
    output.add_argument('--output', type=Path)
    output.add_argument('--output-dir', type=Path,
                        help='create a new directory with the image and SHA256SUMS')
    args = parser.parse_args()
    try:
        process(args, parser)
    except (OSError, ValueError) as error:
        parser.error(str(error))


def process(args, parser):
    image = args.image.read_bytes()
    if args.default_emulation is not None:
        if args.output is None and args.output_dir is None:
            parser.error('--output or --output-dir is required when changing the initial setting')
        image = configure(image, args.default_emulation == 'enabled')
        if args.output_dir is not None:
            if args.image.name == 'SHA256SUMS' or any(char in args.image.name for char in '\n\r\\'):
                parser.error('unsupported image filename')
            args.output_dir.mkdir(parents=True, exist_ok=False)
            args.output = args.output_dir / args.image.name
        args.output.write_bytes(image)
        if args.output_dir is not None:
            (args.output_dir / 'SHA256SUMS').write_text(
                hashlib.sha256(image).hexdigest() + '  ' + args.output.name + '\n')
    elif args.output is not None or args.output_dir is not None:
        parser.error('output options require --default-emulation')
    print(json.dumps({'board': check_layout(image), 'settings': inspect(image),
                      'sha256': hashlib.sha256(image).hexdigest()}, indent=2))


if __name__ == '__main__':
    main()
