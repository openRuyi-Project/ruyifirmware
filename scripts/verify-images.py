#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the paired K3 containers before uploading build artifacts."""
import hashlib
import json
from pathlib import Path
import runpy
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]


def verify(build):
    encoder = runpy.run_path(str(ROOT / 'tools/k3image.py'))
    normal = build / 'normal-spi.bin'
    recovery = build / 'recovery-bootrom.bin'
    image = normal.read_bytes()
    if image[:80] != encoder['nor_header']():
        raise ValueError('NOR boot information does not match the supported layout')
    if encoder['bootrom_payload'](normal) != recovery.read_bytes():
        raise ValueError('Recovery entry does not match the normal image')
    config = image[0x20100:0x20120]
    if zlib.crc32(config[:24]) != struct.unpack_from('<I', config, 24)[0]:
        raise ValueError('BootROM configuration header CRC mismatch')
    seen = set()
    for line in (build / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split()
        if name not in ('normal-spi.bin', 'recovery-bootrom.bin') or name in seen:
            raise ValueError('Unexpected image in SHA256SUMS')
        seen.add(name)
        if hashlib.sha256((build / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'{name}: SHA256 mismatch')
    if seen != {'normal-spi.bin', 'recovery-bootrom.bin'}:
        raise ValueError('SHA256SUMS must include both images')
    subprocess.run([str(build / 'coreboot-normal/cbfstool'), str(normal), 'print', '-kv'], check=True)
    result = {
        'container_and_pair_checks': 'passed',
        'hardware_tested': False,
        'images': {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in (normal, recovery)},
    }
    (build / 'image-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print('K3 image layout, CRCs, matching recovery entry and SHA256 sums passed')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
