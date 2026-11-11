#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the EIC7700 SCPU stage and collect the DDR firmware notices."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('sources', type=Path)
    parser.add_argument('build', type=Path)
    parser.add_argument('--cross-compile', required=True)
    args = parser.parse_args()
    sources, build = args.sources.resolve(), args.build.resolve()
    root = Path(__file__).resolve().parents[2]
    stage = root / 'platforms/eic7700'
    ddr = stage / 'ddr'
    build.mkdir(parents=True, exist_ok=True)
    def build_stage(name, inputs, isa='rv32imac'):
        elf = build / (name + '.elf')
        flags = [
            '-march=' + isa, '-mabi=ilp32', '-Os', '-ffreestanding',
            '-fno-builtin', '-fpie', '-fno-stack-protector',
            '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
            '-fno-ident', '-msmall-data-limit=0', '-mno-relax',
            '-nostdlib', '-static', '-Wall', '-Wextra', '-Werror',
            '-I' + str(sources / 'edk2-ruyi/EswinPlatformPkg/Include'),
            '-Wl,--no-relax,--build-id=none,-T,' + str(stage / (name + '.ld')),
        ]
        subprocess.run([args.cross_compile + 'gcc', *flags,
                        *map(str, inputs), '-o', str(elf)], check=True)
        subprocess.run([args.cross_compile + 'objcopy', '-O', 'binary',
                        str(elf), str(build / (name + '.bin'))], check=True)

    build_stage('sys-init', [stage / 'sys-init.c'])
    # Keep both vendor programs at their original execution address. The
    # dispatcher copies the selected program there before entering it.
    assembly = build / 'ddr-payloads.S'
    assembly.write_text(''.join(
        f'.section .ddr.{kind}, "a"\n.incbin {json.dumps(str(path))}\n'
        for kind, path in (
            ('normal', ddr / 'ddr_fw.bin'),
            ('ecc', ddr / 'ddr_fw_ecc.bin'))))
    build_stage('ddr-dispatch', [stage / 'ddr-entry.S', stage / 'ddr-dispatch.c', assembly],
                isa='rv32imac_zifencei')
    for source, name in (('ddr_fw.bin', 'ddr-normal.bin'), ('ddr_fw_ecc.bin', 'ddr-ecc.bin')):
        shutil.copyfile(ddr / source, build / name)
    for name in ('LICENSE', 'COPYING'):
        notice = ddr / name
        shutil.copyfile(notice, build / ('ddr-' + name + '.txt'))


if __name__ == '__main__':
    main()
