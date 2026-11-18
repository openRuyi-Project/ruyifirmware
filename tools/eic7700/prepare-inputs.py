#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the EIC7700 SCPU stage and collect the DDR firmware notices."""
import argparse
from collections import deque
from pathlib import Path
import shutil
import subprocess

from ddr import build_image


def boot_cpu_rate(dtb):
    def get(node, prop, kind='u', default=None):
        options = [] if default is None else ['-d', default]
        return subprocess.check_output(
            ['fdtget', *options, '-t', kind, str(dtb), node, prop], text=True).split()

    def children(node):
        names = subprocess.check_output(['fdtget', '-l', str(dtb), node], text=True)
        return [node.rstrip('/') + '/' + name for name in names.split()]

    def enabled(node):
        return get(node, 'status', 's', default='okay') in (['okay'], ['ok'])

    handle, = get('/cpus/cpu@0', 'operating-points-v2')
    pending = deque(['/'])
    while pending:
        table = pending.popleft()
        if get(table, 'phandle', default='') == [handle]:
            break
        pending.extend(children(table))
    else:
        raise ValueError('boot CPU operating-points-v2 phandle not found')

    if not enabled(table) or 'operating-points-v2' not in get(table, 'compatible', 's'):
        raise ValueError('boot CPU operating point table is disabled or incompatible')

    rates = []
    for node in children(table):
        props = subprocess.check_output(['fdtget', '-p', str(dtb), node], text=True).split()
        if 'opp-hz' not in props or not enabled(node):
            continue
        if 'turbo-mode' in props or 'opp-supported-hw' in props:
            continue
        high, low = map(int, get(node, 'opp-hz'))
        rates.append((high << 32) | low)
    if not rates:
        raise ValueError('no enabled normal CPU operating point')
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
