#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Encode native K3 BootROM RAM images and 8 MiB SPI images."""
import argparse
import hashlib
from pathlib import Path
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from settings import read_layout

# K3 BootROM container ABI. Payload alignment also applies to non-secure
# boot. The first header describes the configuration block.
DOWNLOAD_LIMIT = 0x74000
CONFIG_SIZE = 0x1000
CONFIG_HEADER_OFFSET = 0x100
SIGNATURE_SIZE = 0x100
PAYLOAD_ALIGNMENT = 32
SRAM_BASE = 0xc0800000
IMAGE_HEADER_BODY = struct.Struct('<4sBBHQQ')
IMAGE_HEADER = struct.Struct('<4sBBHQQII')
CRC_PAIR = struct.Struct('<II')
PAYLOAD_HEADER_OFFSET = CONFIG_SIZE - IMAGE_HEADER.size

# NOR geometry and BootROM boot-information descriptor.
NOR_PAGE_SIZE = 256
NOR_BLOCK_SIZE = 0x10000
NOR_MAGIC = 0xb00714f0
NOR_VERSION = 0x10001
NOR_HEADER_BODY = struct.Struct('<II4s4xIII4xIII20x')
NOR_HEADER_CRC = struct.Struct('<I12x')
NOR_HEADER_SIZE = NOR_HEADER_BODY.size + NOR_HEADER_CRC.size


def layout(image):
    board, areas = read_layout(image)
    if board != 'k3':
        raise ValueError('Expected a K3 coreboot NOR layout')
    return areas


def image_header(size, address, body_crc=0):
    header = IMAGE_HEADER_BODY.pack(b'AIHD', 1, 0, 0, size, address)
    return header + CRC_PAIR.pack(zlib.crc32(header), body_crc)


def bootrom_payload(path):
    image = path.read_bytes()
    start = layout(image)['BOOTBLOCK'].offset
    if image[:NOR_HEADER_SIZE] != nor_header(len(image), start):
        raise ValueError('Invalid NOR boot-information header')
    config_header = image_header(PAYLOAD_HEADER_OFFSET, SRAM_BASE)
    if image[start + CONFIG_HEADER_OFFSET:start + CONFIG_HEADER_OFFSET + IMAGE_HEADER.size] != config_header:
        raise ValueError('Invalid BootROM configuration header')
    header = image[start + PAYLOAD_HEADER_OFFSET:start + CONFIG_SIZE]
    magic, version, secure, reserved, size, address, header_crc, body_crc = IMAGE_HEADER.unpack(header)
    total = CONFIG_SIZE + size + SIGNATURE_SIZE
    body = image[start + CONFIG_SIZE:start + CONFIG_SIZE + size]
    if (magic != b'AIHD' or version != 1 or secure or reserved or address
            or not size or size % PAYLOAD_ALIGNMENT or total > DOWNLOAD_LIMIT):
        raise ValueError('Invalid BootROM payload header')
    if zlib.crc32(header[:IMAGE_HEADER_BODY.size]) != header_crc or zlib.crc32(body) != body_crc:
        raise ValueError('BootROM payload CRC mismatch')
    return image[start:start + total]


def wrap(payload):
    body = bytes(payload) + bytes((-len(payload)) % PAYLOAD_ALIGNMENT)
    if not body or CONFIG_SIZE + len(body) + SIGNATURE_SIZE > DOWNLOAD_LIMIT:
        raise ValueError(f'BootROM container exceeds the {DOWNLOAD_LIMIT:#x}-byte limit')
    header = image_header(len(body), 0, zlib.crc32(body))
    # Non-secure images carry no public keys or certificates. Reserved
    # configuration and signature fields are zero-filled.
    result = bytearray(CONFIG_SIZE + len(body) + SIGNATURE_SIZE)
    result[CONFIG_HEADER_OFFSET:CONFIG_HEADER_OFFSET + IMAGE_HEADER.size] = image_header(PAYLOAD_HEADER_OFFSET, SRAM_BASE)
    result[PAYLOAD_HEADER_OFFSET:CONFIG_SIZE] = header
    result[CONFIG_SIZE:CONFIG_SIZE + len(body)] = body
    return result


def nor_header(flash_size, bootblock_offset):
    header = NOR_HEADER_BODY.pack(NOR_MAGIC, NOR_VERSION, b'NORF',
                                  NOR_PAGE_SIZE, NOR_BLOCK_SIZE, flash_size,
                                  bootblock_offset, 0, DOWNLOAD_LIMIT)
    return header + NOR_HEADER_CRC.pack(zlib.crc32(header))


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
        areas = layout(result)
        bootblock = areas['BOOTBLOCK']
        # cbfstool updates the metadata hash anchor inside the ROM. Use those
        # bytes, not the unpatched intermediate bootblock file.
        payload = result[bootblock.offset:bootblock.offset + args.bootblock.stat().st_size]
        container = wrap(payload)
        result[bootblock.offset:bootblock.offset + bootblock.size] = b'\xff' * bootblock.size
        result[bootblock.offset:bootblock.offset + len(container)] = container
        result[:NOR_HEADER_SIZE] = nor_header(len(result), bootblock.offset)
        # BootROM's second boot-information erase block is unused.
        result[NOR_BLOCK_SIZE:areas['BOOTINFO'].size] = b'\xff' * (areas['BOOTINFO'].size - NOR_BLOCK_SIZE)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    print(f'{args.output}: {len(result)} bytes, SHA256 {hashlib.sha256(result).hexdigest()}')


if __name__ == '__main__':
    main()
