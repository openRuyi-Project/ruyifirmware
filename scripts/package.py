#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Collect the selected profile's verified build and installation notes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
build, output = (Path(p).resolve() for p in sys.argv[1:])
checks = json.loads((build / 'image-checks.json').read_text())
output.mkdir(parents=True, exist_ok=True)
for name in ('normal-spi.bin', 'recovery-bootrom.bin'):
    if hashlib.sha256((build / name).read_bytes()).hexdigest() != checks['images'][name]['sha256']:
        raise ValueError(f'{name} changed after verification')
for name in ('normal-spi.bin', 'recovery-bootrom.bin', 'source-revisions.txt',
             'submodules.txt', 'toolchain.txt', 'build-options.txt', 'image-checks.json'):
    shutil.copy2(build / name, output / name)
for name in ('INSTALL.txt', 'EC.txt'):
    shutil.copy2(ROOT / 'docs' / 'k3' / name, output / name)
(output / 'build-revision.txt').write_text(
    subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True))
files = sorted(p for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS')
(output / 'SHA256SUMS').write_text(''.join(
    hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in files))
print(output)
