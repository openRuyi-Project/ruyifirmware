#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the EIC7700 SCPU stage and collect the DDR firmware notices."""
import argparse
from pathlib import Path
import shutil
import subprocess

from cpu import boot_cpu_rate, p550_gpio_rate
from ddr import build_image


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('sources', type=Path)
    parser.add_argument('build', type=Path)
    parser.add_argument('--cross-compile', required=True)
    parser.add_argument('--dtb', type=Path, required=True)
    args = parser.parse_args()
    sources, build = args.sources.resolve(), args.build.resolve()
    root = Path(__file__).resolve().parents[2]
    stage = root / 'platforms/eic7700'
    ddr = stage / 'ddr'
    build.mkdir(parents=True, exist_ok=True)

    rate = boot_cpu_rate(args.dtb)
    late_rate = p550_gpio_rate(args.dtb, rate)

    def build_stage(name, inputs, isa='rv32imac'):
        elf = build / (name + '.elf')
        flags = [
            '-march=' + isa, '-mabi=ilp32', '-Os', '-ffreestanding',
            '-fno-builtin', '-fpie', '-fno-stack-protector',
            '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
            '-fno-ident', '-msmall-data-limit=0', '-mno-relax',
            '-nostdlib', '-static', '-Wall', '-Wextra', '-Werror',
            f'-DEIC7700_BOOT_CPU_HZ={1400000000 if late_rate else rate}ULL',
            '-I' + str(sources / 'edk2-ruyi/EswinPlatformPkg/Include'),
            '-Wl,--no-relax,--build-id=none,-T,' + str(stage / (name + '.ld')),
        ]
        subprocess.run([args.cross_compile + 'gcc', *flags,
                        *map(str, inputs), '-o', str(elf)], check=True)
        subprocess.run([args.cross_compile + 'objcopy', '-O', 'binary',
                        str(elf), str(build / (name + '.bin'))], check=True)

    build_stage('sys-init', [stage / 'sys-init.c'])
    build_image(args.dtb, build / 'ddr.bin',
                sources / 'edk2-ruyi/EswinPlatformPkg/Include', args.cross_compile, late_rate)
    for name in ('LICENSE', 'COPYING'):
        notice = ddr / name
        shutil.copyfile(notice, build / ('ddr-' + name + '.txt'))


if __name__ == '__main__':
    main()
