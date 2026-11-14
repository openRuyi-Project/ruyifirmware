#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compile shared SCPU training code into a BootROM-loadable DDR program."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from image import DDR_HEADER, check_ddr

SOURCE = Path(__file__).resolve().parents[2] / 'platforms/eic7700/ddr'
BASE = 0x59000000
SOURCE_OFFSET = 0x48000
PAYLOAD_LIMIT = 0x100000
SOURCES = ('common.c', 'lanes.c', 'controller.c', 'controller-state.c',
           'phy.c', 'training.c', 'ecc.c', 'entry.c', 'policy.c')
REFERENCE_SHA256 = 'c6fd5777c98e90cead9ed4c4b27775635cc007b320b7443f4656f7e116cd66c5'


def board_config(dtb):
    model = subprocess.run(
        ['fdtget', '-t', 's', str(dtb), '/', 'model'], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ).stdout.strip()
    compatibles = subprocess.check_output(
        ['fdtget', '-t', 's', str(dtb), '/', 'compatible'], text=True).split()
    if 'eswin,eic7700' not in compatibles:
        raise ValueError('DDR build requires an EIC7700 device tree')
    profiles = {
        'sifive,hifive-premier-p550': False,
        'milkv,megrez': False,
        'milkv,megrez-nx': True,
    }
    matched = next((name for name in compatibles if name in profiles), None)
    if matched is None:
        raise ValueError(
            'no DDR profile for device tree compatible: ' + ', '.join(compatibles))
    nx = profiles[matched]
    return {
        'model': model,
        'compatible': compatibles,
        'profile': matched,
        'nx': nx,
        'dtb_sha256': hashlib.sha256(dtb.read_bytes()).hexdigest(),
    }


def jump(source, destination):
    delta = destination - source
    if delta & 0x01 or not -(1 << 20) <= delta < (1 << 20):
        raise ValueError('DDR entry jump is out of range or misaligned')
    bits = delta & 0x1fffff
    return (0x6f | ((bits >> 20) << 31) | (((bits >> 1) & 0x3ff) << 21)
            | (((bits >> 11) & 0x01) << 20) | (((bits >> 12) & 0xff) << 12))


def build_image(dtb, output, include, cross_compile):
    board = board_config(dtb)
    original = (SOURCE / 'ddr_fw.bin').read_bytes()
    if (len(original) != 272552 or
            hashlib.sha256(original).hexdigest() != REFERENCE_SHA256):
        raise ValueError('ddr_fw.bin: reference size or SHA256 mismatch')
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output in (SOURCE / 'ddr_fw.bin', SOURCE / 'ddr_fw_ecc.bin'):
        raise ValueError('output must not overwrite a reference input')
    elf = output.with_suffix('.elf')
    native = output.with_suffix('.native.bin')
    flags = [
        '-march=rv32im', '-mabi=ilp32', '-Os', '-ffreestanding',
        '-fno-builtin', '-fno-pie', '-fno-stack-protector',
        '-fno-unwind-tables', '-fno-asynchronous-unwind-tables', '-fno-ident',
        '-msmall-data-limit=0', '-mno-relax', '-nostdlib', '-static', '-no-pie',
        '-Wall', '-Wextra', '-Werror',
        '-Wl,--no-relax,--build-id=none,-T,' + str(SOURCE / 'ddr.ld'),
        '-I' + str(include), '-DDDR_BOARD_NX=' + str(int(board['nx'])),
    ]
    subprocess.run([cross_compile + 'gcc', *flags,
                    *(str(SOURCE / name) for name in SOURCES), '-o', str(elf)], check=True)
    subprocess.run([cross_compile + 'objcopy', '-O', 'binary',
                    str(elf), str(native)], check=True)
    symbols = {}
    for line in subprocess.check_output(
            [cross_compile + 'nm', '--defined-only', str(elf)], text=True).splitlines():
        address, _, name = line.split()
        symbols[name] = int(address, 16)
    code = native.read_bytes()
    start, end = symbols['_ddr_source_start'], symbols['_ddr_source_end']
    if (start != BASE + SOURCE_OFFSET or end - start != len(code) or
            not code or end > BASE + PAYLOAD_LIMIT or len(original) > SOURCE_OFFSET):
        raise ValueError('DDR source layout does not match its reservation')
    image = bytearray(original)
    image.extend(bytes(SOURCE_OFFSET - len(image)))
    image.extend(code)
    spi_entry = symbols['ddr_entry'] - BASE
    uart_entry = symbols['ddr_recovery_entry'] - BASE
    if not all(SOURCE_OFFSET <= entry < len(image) for entry in (spi_entry, uart_entry)):
        raise ValueError('DDR entry is outside its image')
    DDR_HEADER.pack_into(image, 0, jump(0, spi_entry), b'RUYIDDR\0', 2,
                         int(board['nx']), spi_entry, uart_entry, len(image))
    check_ddr(image)
    output.write_bytes(image)
    recovery = bytearray(image)
    struct.pack_into('<I', recovery, 0, jump(0, uart_entry))
    check_ddr(recovery, recovery=True)
    output.with_name(output.stem + '-recovery.bin').write_bytes(recovery)
    result = {
        **board, 'reference': 'ddr_fw.bin', 'reference_sha256': REFERENCE_SHA256,
        'image_sha256': hashlib.sha256(image).hexdigest(),
        'recovery_sha256': hashlib.sha256(recovery).hexdigest(), 'size': len(image),
        'source_start': hex(start), 'source_end': hex(end),
        'spi_entry': hex(BASE + spi_entry), 'uart_entry': hex(BASE + uart_entry),
    }
    manifest = output.with_name(output.stem + '-build.json')
    manifest.write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument(
        '--include', type=Path,
        default=SOURCE.parents[2] / 'src/edk2-ruyi/EswinPlatformPkg/Include')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cross-compile', default='riscv64-linux-gnu-')
    args = parser.parse_args()
    build_image(args.dtb, args.output, args.include, args.cross_compile)


if __name__ == '__main__':
    main()
