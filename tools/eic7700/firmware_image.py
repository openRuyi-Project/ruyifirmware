# SPDX-License-Identifier: MIT
"""EIC7700 BootROM container layout shared by packaging and settings tools."""
import struct

IMAGE_BYTES = 0x800000
FIRMWARE_BYTES = 0x600000
COREBOOT_BYTES = 0x400000
SCPU_ADDRESS = 0x59000000
MCPU_ADDRESS = 0x90000000
FHT_MAGIC = 0x42575345
SIGNATURE_MAGIC = 0xbb455357
STAGE_TYPES = (0x70, 0x10, 0x30)
HEADER = struct.Struct('<II')
ENTRY = struct.Struct('<IQQBBBB4sII')
SIGNATURE_BYTES = 256

def entries(image):
    if len(image) < HEADER.size:
        raise ValueError('truncated ROM header')
    magic, count = HEADER.unpack_from(image)
    if magic != FHT_MAGIC or count != 3:
        raise ValueError('expected three ROM boot stages')
    found = []
    end = HEADER.size + count * ENTRY.size
    for index in range(count):
        version, offset, size, sign, key, kind, last, padding, r1, r2 = ENTRY.unpack_from(
            image, HEADER.size + index * ENTRY.size)
        if (version != 1 or sign or key or kind != STAGE_TYPES[index]
                or last != (index == 2) or padding != bytes(4) or r1 or r2
                or offset < end or offset % 32 or not size
                or offset + SIGNATURE_BYTES + size > min(len(image), FIRMWARE_BYTES)):
            raise ValueError(f'invalid ROM entry {index}')
        magic, reserved, link, stored_offset, stored_size, load, entry = struct.unpack_from('<IIQQQQQ', image, offset)
        expected = MCPU_ADDRESS if index == 2 else SCPU_ADDRESS
        if (magic != SIGNATURE_MAGIC or reserved or link or stored_offset != offset
                or stored_size != size or load != expected or entry != expected
                or image[offset + 48:offset + 51] != bytes(3)
                or image[offset + 64] != kind or image[offset + 65] != (index == 2)):
            raise ValueError(f'invalid ROM signature header {index}')
        found.append((offset, size, kind, last))
        end = offset + SIGNATURE_BYTES + size
    return found
