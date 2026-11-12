#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect or change platform defaults in a Ruyi Firmware SPI image.

This changes image records. It does not change settings on a running board.
Use this tool with the firmware files from the same release package.
"""
import argparse
from collections import namedtuple
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

# Keep inspection from creating extra files in an extracted package.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / 'eic7700'))
from firmware_image import entries, SIGNATURE_BYTES
from image_layout import DEFAULT_LAYOUTS, STAGE_LAYOUTS

# Current defaults ABI. No legacy records are read or converted.
DEFAULT_MAGIC = int.from_bytes(b'RYCF', 'little')
DEFAULT_COMMIT = int.from_bytes(b'DONE', 'little')
DEFAULT_BODY = struct.Struct('<IHHII')
DEFAULT_RECORD = struct.Struct('<IHHIIII')
DEFAULT_VERSION = 1
DEFAULT_MASK = 7
SLOT_COUNT = 2

FMAP_HEADER = struct.Struct('<8sBBQI32sH')
FMAP_AREA = struct.Struct('<II32sH')
FMAP_PRESERVE = 1 << 3
FlashArea = namedtuple('FlashArea', 'offset size flags')

# Accepted layouts from the coreboot board FMDs. Check these before writing
# settings, whose addresses are part of the firmware ABI, not relocatable data.
LAYOUTS = {
    'k3': (0x800000, {
        'BOOTINFO': (0x0, 0x20000),
        'BOOTBLOCK': (0x20000, 0x80000),
        'FMAP': (0x1b0000, 0x1000),
        'EARLY_RESERVED': (0x1b1000, 0x5f000),
        'COREBOOT': (0x210000, 0x300000),
        'UEFI_VARIABLES': (0x700000, 0xc0000),
    }),
    'unmatched': (0x800000, {
        'BOOTBLOCK': (0x0, 0x10000),
        'FMAP': (0x20000, 0x200),
        'PLATFORM_CONFIG': (0x10000, 0x10000),
        'COREBOOT': (0x20200, 0x7dfe00),
    }),
}


def read_layout(image):
    candidates = [(board, required) for board, (size, required) in LAYOUTS.items()
                  if len(image) == size and
                  image[required['FMAP'][0]:required['FMAP'][0] + 8] == b'__FMAP__']
    if len(candidates) != 1:
        raise ValueError('unsupported firmware image layout')
    board, required = candidates[0]
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
    if image[:4] != b'ESWB':
        return read_layout(image)[0]
    layout = STAGE_LAYOUTS['p550']
    if len(image) != layout.image_bytes:
        raise ValueError('P550 SPI image must be 8 MiB')
    records = entries(image, firmware_bytes=layout.firmware_bytes,
                      stage_addresses=(layout.scpu_address, layout.scpu_address, layout.mcpu_address))
    offset, size, _, _ = records[2]
    if size != layout.coreboot_bytes:
        raise ValueError('invalid P550 coreboot size')
    rom = image[offset + SIGNATURE_BYTES:offset + SIGNATURE_BYTES + size]
    fmap = 0x20000
    fields = FMAP_HEADER.unpack_from(rom, fmap)
    if fields != (b'__FMAP__', 1, 1, 0, layout.coreboot_bytes, b'FLASH' + bytes(27), 3):
        raise ValueError('invalid P550 flash map')
    required = [(0, 0x20000, b'BOOTBLOCK', 0), (fmap, 0x1000, b'FMAP', 0),
                (0x21000, 0x3df000, b'COREBOOT', 0)]
    for index, expected in enumerate(required):
        start, length, name, flags = FMAP_AREA.unpack_from(rom, fmap + FMAP_HEADER.size + index * FMAP_AREA.size)
        if (start, length, name.rstrip(b'\0'), flags) != expected:
            raise ValueError('unsupported P550 settings layout')
    return 'p550'


def encode(values, generation=0):
    body = DEFAULT_BODY.pack(DEFAULT_MAGIC, DEFAULT_VERSION, DEFAULT_RECORD.size, generation, values)
    return body + struct.pack('<II', zlib.crc32(body), DEFAULT_COMMIT)


def decode(data):
    magic, version, size, generation, values, crc, commit = DEFAULT_RECORD.unpack_from(data)
    if (magic, version, size, commit) != (DEFAULT_MAGIC, DEFAULT_VERSION, DEFAULT_RECORD.size, DEFAULT_COMMIT):
        return None
    if values & ~DEFAULT_MASK or zlib.crc32(data[:DEFAULT_BODY.size]) != crc:
        return None
    return generation, values


def read_defaults(image, allow_empty=False):
    offset, stride = DEFAULT_LAYOUTS[check_layout(image)]
    selected = None
    empty = True
    for slot in range(SLOT_COUNT):
        start = offset + slot * stride
        data = image[start:start + DEFAULT_RECORD.size]
        empty = empty and data == b'\xff' * DEFAULT_RECORD.size
        record = decode(data)
        if record is None:
            continue
        if selected is None or 0 < (record[0] - selected[0]) & 0xffffffff < 0x80000000:
            selected = record
    if selected is None:
        if allow_empty and empty:
            return 0
        raise ValueError('no valid current-format defaults record; reflash a complete current package')
    return selected[1]


def inspect(image):
    values = read_defaults(image)
    return dict(emulation=bool(values & 1), pxe=bool(values & 2), http=bool(values & 4))


def configure(image, enabled=None, pxe=None, http=None):
    values = read_defaults(image, allow_empty=True)
    for bit, value in [(1, enabled), (2, pxe), (4, http)]:
        if value is not None:
            values = (values & ~bit) | (bit if value else 0)
    result = bytearray(image)
    offset, stride = DEFAULT_LAYOUTS[check_layout(image)]
    for slot in range(SLOT_COUNT):
        start = offset + slot * stride
        result[start:start + stride] = b'\xff' * stride
        result[start:start + DEFAULT_RECORD.size] = encode(values)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('image', type=Path)
    parser.add_argument('--default-emulation', choices=('enabled', 'disabled'),
                        help='set the emulation default in the output image')
    parser.add_argument('--default-pxe', choices=('enabled', 'disabled'))
    parser.add_argument('--default-http', choices=('enabled', 'disabled'))
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
    if any(value is not None for value in (args.default_emulation, args.default_pxe, args.default_http)):
        if args.output is None and args.output_dir is None:
            parser.error('--output or --output-dir is required when changing the default')
        values = [None if value is None else value == 'enabled' for value in (args.default_emulation, args.default_pxe, args.default_http)]
        image = configure(image, *values)
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
        parser.error('output options require a default-setting option')
    print(json.dumps({'board': check_layout(image), 'defaults': inspect(image),
                      'sha256': hashlib.sha256(image).hexdigest()}, indent=2))


if __name__ == '__main__':
    main()
