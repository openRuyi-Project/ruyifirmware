#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the EIC7700 SCPU stage and collect the DDR firmware notices."""
import argparse
from pathlib import Path
import shutil
import subprocess

from ddr import build_image


def boot_cpu_rate(dtb):
    def get(node, prop, kind='u'):
        return subprocess.check_output(
            ['fdtget', '-t', kind, str(dtb), node, prop], text=True).split()

    if 'milkv,megrez' not in get('/', 'compatible', 's'):
        return 1400000000

    # Use the enabled operating points of the boot CPU. The standard
    # Megrez supplies 900 mV at reset and supports up to 1.6 GHz.
    phandle = get('/cpus/cpu@0', 'operating-points-v2')
    table = '/opp-table-cpu'
    if phandle != get(table, 'phandle'):
        raise ValueError('unexpected Megrez CPU operating point table')
    nodes = subprocess.check_output(['fdtget', '-l', str(dtb), table], text=True)
    rates = []
    for name in nodes.split():
        node = table + '/' + name
        status = subprocess.check_output(
            ['fdtget', '-d', 'okay', '-t', 's', str(dtb), node, 'status'], text=True).strip()
        if status not in ('ok', 'okay'):
            continue
        high, low = map(int, get(node, 'opp-hz'))
        if int(get(node, 'opp-microvolt')[0]) <= 900000:
            rates.append((high << 32) | low)
    if not rates or max(rates) != 1600000000:
        raise ValueError('Megrez requires a 1.6 GHz operating point at its boot voltage')
    return max(rates)


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

    def build_stage(name, inputs, isa='rv32imac'):
        elf = build / (name + '.elf')
        flags = [
            '-march=' + isa, '-mabi=ilp32', '-Os', '-ffreestanding',
            '-fno-builtin', '-fpie', '-fno-stack-protector',
            '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
            '-fno-ident', '-msmall-data-limit=0', '-mno-relax',
            '-nostdlib', '-static', '-Wall', '-Wextra', '-Werror',
            f'-DEIC7700_BOOT_CPU_HZ={boot_cpu_rate(args.dtb)}ULL',
            '-I' + str(sources / 'edk2-ruyi/EswinPlatformPkg/Include'),
            '-Wl,--no-relax,--build-id=none,-T,' + str(stage / (name + '.ld')),
        ]
        subprocess.run([args.cross_compile + 'gcc', *flags,
                        *map(str, inputs), '-o', str(elf)], check=True)
        subprocess.run([args.cross_compile + 'objcopy', '-O', 'binary',
                        str(elf), str(build / (name + '.bin'))], check=True)

    build_stage('sys-init', [stage / 'sys-init.c'])
    build_image(args.dtb, build / 'ddr.bin',
                sources / 'edk2-ruyi/EswinPlatformPkg/Include', args.cross_compile)
    for name in ('LICENSE', 'COPYING'):
        notice = ddr / name
        shutil.copyfile(notice, build / ('ddr-' + name + '.txt'))


if __name__ == '__main__':
    main()
