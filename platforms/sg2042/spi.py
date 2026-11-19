#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the SG2042 SCP flash partition table and its contents."""
import argparse
from pathlib import Path
import struct

TABLE_OFFSET = 0x600000
TABLE_SIZE = 0x1000
MAGIC = 0x55aa55aa
# struct part_info in the SCP. The last field is the DRAM load address.
PARTITION = struct.Struct('<I32sII4xQ')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('fip', 'rom', 'output'):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    entries = (
        ('fip.bin', 0x30000, 0, args.fip),
        ('ruyi-vars', 0x700000, 0, None),
        ('zsbl.bin', 0x800000, 0x40000000, args.rom),
    )
    size = entries[-1][1] + args.rom.stat().st_size
    image = bytearray(b'\xff') * size
    occupied = [(TABLE_OFFSET, TABLE_OFFSET + TABLE_SIZE)]
    for index, (name, start, address, source) in enumerate(entries):
        data = source.read_bytes() if source is not None else b'\xff' * 0x90000
        end = start + len(data)
        if not data or any(start < hi and lo < end for lo, hi in occupied):
            raise ValueError(f'invalid flash region for {name}')
        occupied.append((start, end))
        PARTITION.pack_into(image, TABLE_OFFSET + index * PARTITION.size,
                            MAGIC, name.encode('ascii'), start, len(data), address)
        image[start:end] = data
    args.output.write_bytes(image)


if __name__ == '__main__':
    main()
