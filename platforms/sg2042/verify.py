#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the SG2042 SPI and SD handoffs against the linked firmware."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import struct
import subprocess
import tempfile

from elftools.elf.elffile import ELFFile


def require(valid, message):
    if not valid:
        raise ValueError(message)


def check_self(data, segments, entry):
    header = struct.Struct('>4sIIQII')
    for index, (kind, addr, content, memsz) in enumerate(segments):
        tag, compression, start, load, size, memory = header.unpack_from(data, index * header.size)
        require((tag, load, memory) == (kind, addr, memsz), 'CBFS segment layout differs')
        require(start >= header.size * (len(segments) + 1) and start + size <= len(data),
                'CBFS segment outside payload')
        block = data[start:start + size]
        require(compression in (0, 1), 'unsupported CBFS compression')
        require((lzma.decompress(block) if compression else block) == content,
                'CBFS segment differs from its input')
    require(header.unpack_from(data, len(segments) * header.size) == (b'ENTR', 0, 0, entry, 0, 0),
            'incorrect entry point')


def check_cbfs(build, rom, fd, sbi):
    tool = build / 'coreboot-normal/cbfstool'
    boards = {'sg2042-evb-v1': 'sophgo,sg2042-evb-v1',
              'sg2042-milkv-pioneer': 'milkv,pioneer',
              'sg2042-evb-v2': 'sophgo,sg2042-evb-v2'}
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'entry'
        def extract(name):
            subprocess.run([tool, rom, 'extract', '-U', '-n', name, '-f', path], check=True)
            return path.read_bytes()
        for name, compatible in boards.items():
            name += '.dtb'
            require(extract(name) == (build / name).read_bytes(), f'{name} differs from Linux DTB')
            actual = subprocess.check_output(['fdtget', path, '/', 'compatible'], text=True).split()
            require(actual == [compatible, 'sophgo,sg2042'], f'{name} has wrong board compatible')
        check_self(extract('fallback/payload'), [(b'CODE', 0x02000000, fd, len(fd))], 0x02000000)
        with sbi.open('rb') as src:
            elf = ELFFile(src)
            require(elf.header.e_entry == 0x00200000, 'wrong OpenSBI link address')
            segments = [(b'CODE' if s['p_flags'] & 1 else b'DATA',
                         s['p_paddr'], s.data(), s['p_memsz'])
                        for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
            check_self(extract('fallback/opensbi'), segments, elf.header.e_entry)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    parser.add_argument('fip', type=Path)
    parser.add_argument('sbi', type=Path)
    args = parser.parse_args()
    build = args.build.resolve()
    boot = (build / 'coreboot-normal/cbfs/fallback/bootblock.raw.bin').read_bytes()
    rom = (build / 'zsbl.bin').read_bytes()
    fd = (build / 'SG2042.fd').read_bytes()
    require(len(rom) == 0x800000 and boot and rom.startswith(boot), 'wrong SCP reset image')
    require(len(fd) == 0x800000 and fd[40:44] == b'_FVH' and
            struct.unpack_from('<Q', fd, 32)[0] == len(fd), 'wrong Ruyi SG2042 code volume')
    check_cbfs(build, build / 'zsbl.bin', fd, args.sbi)

    spi = (build / 'normal-spi.bin').read_bytes()
    fip = args.fip.read_bytes()
    entries = [(b'fip.bin', 0x30000, 0, fip), (b'ruyi-vars', 0x700000, 0, b'\xff' * 0x90000),
               (b'zsbl.bin', 0x800000, 0x40000000, rom)]
    pos = 0x600000
    for name, offset, lma, content in entries:
        magic, rawname, start, size, address = struct.unpack_from('<I32sII4xQ', spi, pos)
        require((magic, rawname.rstrip(b'\0'), start, size, address) ==
                (0x55aa55aa, name, offset, len(content), lma), 'wrong SPI descriptor')
        require(spi[start:start + size] == content, 'wrong SPI partition contents')
        pos += 56
    require(spi[pos:pos + 4] == b'\xff' * 4, 'unexpected SPI partition')

    sd = build / 'recovery-sd.img'
    with sd.open('rb') as stream:
        mbr = stream.read(512)
        start, sectors = struct.unpack_from('<II', mbr, 454)
        require(mbr[450] == 0x0c and mbr[510:] == b'\x55\xaa' and start == 2048 and
                (start + sectors) * 512 == sd.stat().st_size, 'invalid SD partition')
        stream.seek(start * 512)
        boot_sector = stream.read(512)
    sector_bytes, cluster_sectors, reserved, fats = struct.unpack_from('<HBHB', boot_sector, 11)
    volume_sectors, fat_sectors = struct.unpack_from('<II', boot_sector, 32)
    data_sectors = sectors - reserved - fats * fat_sectors
    require(sector_bytes == 512 and volume_sectors == sectors and fat_sectors > 0 and
            cluster_sectors > 0 and data_sectors // cluster_sectors >= 65525,
            'SD partition does not meet the FAT32 cluster count requirement')
    for name, content in [('fip.bin', fip), ('zsbl.bin', rom)]:
        actual = subprocess.check_output(['mcopy', '-i', f'{sd}@@{512 * start}', '::/' + name, '-'])
        require(actual == content, f'SD {name} differs')
    images = {}
    for path in (build / 'normal-spi.bin', sd):
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        images[path.name] = {'size': path.stat().st_size, 'sha256': digest}
    checks = {'board': 'sg2042', 'images': images}
    (build / 'image-checks.json').write_text(json.dumps(checks, indent=2) + '\n')


if __name__ == '__main__':
    main()
