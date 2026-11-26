#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Package SYS, DDR, D2D and the Ruyi MCPU image for D560."""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import struct
import subprocess
import sys
import zlib
from tempfile import NamedTemporaryFile, TemporaryDirectory
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/eic7700'))
from firmware_image import ENTRY, FHT_MAGIC, HEADER, SIGNATURE_BYTES, SIGNATURE_MAGIC

RELEASE = 'https://github.com/eswincomputing/ebc7702-dev-board-ubuntu/releases/download/2025.12.30/'
DIGESTS = ('257407cc088204c722bc15412e235437bec98456e98d8948c74dd604153efed6',
           '8e2b18ea979f92d00c141f7a74f398f47cef9c10032b3ee2499945fb3d32f202')
D2D_166_SHA256 = ('b66a98491d23a87b1fd69fc622a4fabc4fa276fa2a64420d9c6eaac98398696d',
                  'c08f1246fb1f0a530abb11bbf8181d6994348d5c016708bdc74f6f1ba1e0b2c2')
# Complete 1.66 stage with the board-type handoff entry built from d2d-entry.S.
D2D_166_HANDOFF_SHA256 = ('1a9ddec60ac96c3fea0cf6cfc50c5ad2cef663fd824b161032f8d25b5cb2d53a',
                          'a60c9ad026ca1143bd14f26af78c5da4e272180deb4e2ee92e50697e59e5782e')
MCPU_LOAD = 0x80000000
ROM_SIZE = 4 * 1024 * 1024
# ESWIN D560 primary layout: boot info, DDR record, then the D2D PMIX sector.
STAGE_AREA = 0x50000
SPI_LIMITS = (0x600000, 0x680000)
ERASE_BYTES = 4096
UPDATE_BYTES = 16 * 1024 * 1024
UPDATE_HEADER = struct.Struct('<8sII32sI32s')
D2D_ENTRY_BYTES = 28  # Seven RV32I instructions in d2d-entry.S.
SIGN = struct.Struct('<IIQQQQQ')
SEGMENT = struct.Struct('>4sIIQII')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reference(directory, die, download):
    name = f'bootloader_EBC7702-D01_die{die}.bin'
    path = directory / name
    if not path.exists() and download:
        directory.mkdir(parents=True, exist_ok=True)
        with urlopen(RELEASE + name, timeout=60) as src:
            data = src.read(8 * 1024 * 1024 + 1)
        require(hashlib.sha256(data).hexdigest() == DIGESTS[die], f'{name}: download mismatch')
        replace(path, data)
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == DIGESTS[die], f'{name}: reference digest mismatch')
    return data


def replace(path, data):
    with NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        try:
            tmp.write(data)
            tmp.close()
            os.chmod(tmp.name, 0o644)
            os.replace(tmp.name, path)
        finally:
            Path(tmp.name).unlink(missing_ok=True)


def stages(data, die):
    types = (0x70, 0x10, 0x20) if die else (0x70, 0x10, 0x20, 0x30)
    require(HEADER.unpack_from(data) == (FHT_MAGIC, len(types)), 'wrong die or boot table')
    end = HEADER.size + len(types) * ENTRY.size
    parts = []
    for i, kind in enumerate(types):
        slot = HEADER.size + i * ENTRY.size
        version, pos, size, sig, key, typ, last, pad, _, _ = ENTRY.unpack_from(data, slot)
        require(version == 1 and typ == kind and sig == key == 0 and
                last == (i == len(types) - 1) and pad == bytes(4), 'unexpected ESWIN entry')
        require(pos >= end and pos % 32 == 0 and size > 0, 'invalid stage extent')
        end = pos + SIGNATURE_BYTES + size
        require(end <= len(data), 'truncated stage')
        magic, _, _, offset, count, load, entry = SIGN.unpack_from(data, pos)
        require(magic == SIGNATURE_MAGIC and (offset, count) == (pos, size) and
                data[pos + 64] == kind, 'invalid stage header')
        if entry != load:
            require(kind == 0x20 and size > D2D_ENTRY_BYTES and
                    entry == load + size - D2D_ENTRY_BYTES and
                    hashlib.sha256(data[pos + SIGNATURE_BYTES:end]).hexdigest() ==
                    D2D_166_HANDOFF_SHA256[die], 'unexpected stage entry point')
        if kind == 0x20:
            require(load == 0x59000000 + die * 0x20000000, 'incorrect D2D SRAM address')
        if kind == 0x30:
            require(load == MCPU_LOAD and data[pos + 65] == 1, 'invalid MCPU entry')
        parts.append((pos, size))
    require(end == len(data), 'unexpected trailing data')
    return parts


def d2d_pair(directory, build):
    parts = []
    for die, name in enumerate(('d2d.bin', 'die1_d2d_init.bin')):
        path = directory / name
        require(path.is_file(), f'missing {path}: D560 requires the paired D2D 1.66 files')
        payload = path.read_bytes()
        require(hashlib.sha256(payload).hexdigest() == D2D_166_SHA256[die],
                f'{name}: expected the D2D 1.66 payload for die {die}')
        adapter = (build / f'd2d-entry{die}.bin').read_bytes()
        stage = payload + adapter
        require(len(adapter) == D2D_ENTRY_BYTES and hashlib.sha256(stage).hexdigest() ==
                D2D_166_HANDOFF_SHA256[die], 'unexpected D2D entry adapter')
        parts.append(stage)
    return parts


def assemble(ref, rom, die, d2d):
    parts = stages(ref, die)
    pos, size = parts[2]
    slot = HEADER.size + 2 * ENTRY.size
    entry = list(ENTRY.unpack_from(ref, slot))
    header = bytearray(ref[pos:pos + SIGNATURE_BYTES])
    original = ref[pos + SIGNATURE_BYTES:pos + SIGNATURE_BYTES + size]
    require(entry[-2:] == [0x20100, zlib.crc32(original, 0xffffffff)] and
            not any(header[80:]), 'unsupported D2D stage header')
    load = struct.unpack_from('<Q', header, 32)[0]
    struct.pack_into('<Q', header, 24, len(d2d))
    struct.pack_into('<Q', header, 40, load + len(d2d) - D2D_ENTRY_BYTES)
    entry[2] = len(d2d)
    entry[-1] = zlib.crc32(d2d, 0xffffffff)
    out = bytearray(ref[:pos])
    ENTRY.pack_into(out, slot, *entry)
    out.extend(header)
    out.extend(d2d)
    if die:
        return bytes(out)
    out.extend(bytes(-len(out) % 32))

    require(len(rom) == ROM_SIZE, 'wrong D560 coreboot ROM size')
    pos = len(out)
    old_pos = parts[-1][0]
    header = bytearray(ref[old_pos:old_pos + SIGNATURE_BYTES])
    require(not any(header[80:]), 'unsupported MCPU header')
    ENTRY.pack_into(out, HEADER.size + 3 * ENTRY.size,
                    1, pos, len(rom), 0, 0, 0x30, 1, bytes(4), 0, 0)
    struct.pack_into('<QQ', header, 16, pos, len(rom))
    out.extend(header)
    out.extend(rom)
    return bytes(out)


def spi_image(container, die):
    # Preserve the boot info and calibration sectors. Older es_burn versions
    # also hard-code a D2D slot too small for the current release.
    parts = stages(container, die)
    table_size = HEADER.size + len(parts) * ENTRY.size
    raw = bytearray(b'\xff' * STAGE_AREA)
    raw[:table_size] = container[:table_size]
    for i, (pos, size) in enumerate(parts):
        dest = len(raw)
        struct.pack_into('<Q', raw, HEADER.size + i * ENTRY.size + 4, dest)
        # ESWIN's installer relocates the FHT entry, keeping the original
        # per-stage header and payload together.
        raw.extend(container[pos:pos + SIGNATURE_BYTES + size])
        raw.extend(b'\xff' * (-len(raw) % 0x1000))
    require(len(raw) <= SPI_LIMITS[die], 'D560 stages exceed the primary boot area')
    return raw


def paired_update(die0, die1):
    # Firmware Update accepts a fixed file size. Only the two image extents
    # describe data to program. Keep the reserved SPI sectors on each board.
    header = UPDATE_HEADER.pack(b'D560SPI\0', 1, len(die0), hashlib.sha256(die0).digest(),
                                len(die1), hashlib.sha256(die1).digest())
    image = header.ljust(ERASE_BYTES, b'\xff') + die0 + die1
    require(len(image) <= UPDATE_BYTES, 'D560 update exceeds the envelope')
    return image.ljust(UPDATE_BYTES, b'\xff')


def check_cbfs(build, rom):
    from elftools.elf.elffile import ELFFile
    with TemporaryDirectory() as tmp:
        out = Path(tmp) / 'entry'
        def extract(name):
            subprocess.run([build / 'coreboot-normal/cbfstool', rom, 'extract', '-U',
                            '-n', name, '-f', out], check=True)
            return out.read_bytes()
        dtb = build / 'eic7702-eswin-d560.dtb'
        require(extract('fallback/DTB') == dtb.read_bytes(), 'DTB mismatch')
        compatible = subprocess.check_output(['fdtget', dtb, '/', 'compatible'], text=True).split()
        require(compatible == ['eswin,eic7702-d560', 'eswin,eic7702'], 'unexpected board')
        def check(name, expected, entry):
            raw = extract(name)
            for i, (addr, memsz, contents) in enumerate(expected):
                tag, comp, offset, load, size, memory = SEGMENT.unpack_from(raw, i * SEGMENT.size)
                require(tag in (b'CODE', b'DATA', b'BSS\0') and load == addr and memory == memsz and
                        offset + size <= len(raw) and comp in (0, 1), f'{name}: segment mismatch')
                data = raw[offset:offset + size]
                require((lzma.decompress(data) if comp == 1 else data) == contents, f'{name}: contents mismatch')
            require(SEGMENT.unpack_from(raw, len(expected) * SEGMENT.size) ==
                    (b'ENTR', 0, 0, entry, 0, 0), f'{name}: wrong entry')
        fd = (build / 'EIC7700.fd').read_bytes()
        check('fallback/payload', [(0x82200000, len(fd), fd)], 0x82200000)
        with (build / 'opensbi/platform/generic/firmware/fw_dynamic.elf').open('rb') as f:
            elf = ELFFile(f)
            require(elf.header.e_entry == 0x80800000, 'wrong OpenSBI entry')
            check('fallback/opensbi', [(p.header.p_paddr, p.header.p_memsz, p.data())
                  for p in elf.iter_segments() if p.header.p_type == 'PT_LOAD' and p.header.p_memsz],
                  elf.header.e_entry)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('build', 'verify'))
    parser.add_argument('references', type=Path)
    parser.add_argument('build', type=Path)
    parser.add_argument('--d2d-dir', type=Path,
                        default=ROOT / 'platforms/eic7702', help='directory containing the two D2D 1.66 payloads')
    args = parser.parse_args()
    build = args.build.resolve()
    rom = build / 'd560.rom'
    payload = rom.read_bytes()
    d2d = d2d_pair(args.d2d_dir, build)
    outputs = {}
    digests = []
    for die in range(2):
        ref = reference(args.references, die, args.operation == 'build')
        expected = assemble(ref, payload, die, d2d[die])
        pos, size = stages(expected, die)[2]
        start = pos + SIGNATURE_BYTES
        digests.append(hashlib.sha256(expected[start:start + size]).hexdigest())
        outputs[build / f'bootchain-die{die}.bin'] = expected
        outputs[build / f'normal-spi-die{die}.bin'] = spi_image(expected, die)

    outputs[build / 'firmware.bin'] = paired_update(outputs[build / 'normal-spi-die0.bin'],
                                                  outputs[build / 'normal-spi-die1.bin'])
    if args.operation == 'build':
        for path, contents in outputs.items():
            replace(path, contents)
        return

    images = {}
    for path, contents in outputs.items():
        data = path.read_bytes()
        require(data == contents, f'{path.name}: package contents mismatch')
        images[path.name] = dict(size=len(data), sha256=hashlib.sha256(data).hexdigest())
    check_cbfs(build, rom)
    checks = dict(board='d560', d2d=dict(version='1.66',
                                         die0_sha256=digests[0], die1_sha256=digests[1]),
                  images=images)
    replace(build / 'image-checks.json', (json.dumps(checks, indent=2) + '\n').encode())


if __name__ == '__main__':
    main()
