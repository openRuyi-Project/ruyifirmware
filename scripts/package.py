#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Package verified firmware images and the selected board's documentation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('extra', nargs='*', type=Path)
    args = parser.parse_args()
    build, output = args.build.resolve(), args.output.resolve()
    checks = json.loads((build / 'image-checks.json').read_text())
    board = checks['board']
    if Path(board).name != board or not (ROOT / 'docs' / board).is_dir():
        raise ValueError('unknown board documentation')
    files = {}
    for name, expected in checks['images'].items():
        if Path(name).name != name:
            raise ValueError('invalid image filename')
        source = build / name
        data = source.read_bytes()
        if len(data) != expected['size'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError(f'{name} changed after verification')
        files[name] = source
    for name in ('image-checks.json', 'source-revisions.txt', 'build-options.txt',
                 'submodules.txt', 'toolchain.txt', 'amd-gop.json'):
        files[name] = build / name
    for source in sorted((ROOT / 'docs' / board).iterdir()):
        if source.is_file() and source.suffix in ('.md', '.txt'):
            files[source.name] = source
    for source in (ROOT / 'docs/linux-issues.md', ROOT / 'docs/settings.md',
                   ROOT / 'docs/display-testing.md', *args.extra):
        if source.name in files:
            raise ValueError('duplicate package filename: ' + source.name)
        files[source.name] = source
    output.mkdir(parents=True, exist_ok=True)
    previous = output / 'image-checks.json'
    if previous.exists():
        old = json.loads(previous.read_text())
        for name in set(old['images']) - set(checks['images']):
            if Path(name).name != name:
                raise ValueError('invalid previous image filename')
            (output / name).unlink(missing_ok=True)
    for name, source in files.items():
        shutil.copy2(source, output / name)
    readme = output / 'README.md'
    readme.write_text(readme.read_text().replace('../linux-issues.md', 'linux-issues.md')
                     .replace('../settings.md', 'settings.md')
                     .replace('../display-testing.md', 'display-testing.md'))
    defaults = output / 'settings.md'
    text = defaults.read_text()
    for other in ('k3', 'unmatched', 'p550'):
        target = 'INSTALL.txt' if other == board else (
            'https://github.com/openRuyi-Project/ruyifirmware/blob/ruyi/docs/'
            + other + '/INSTALL.txt')
        text = text.replace('](' + other + '/INSTALL.txt)', '](' + target + ')')
    defaults.write_text(text)
    (output / 'build-revision.txt').write_text(subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True))
    names = set(files) | {'build-revision.txt'}
    unexpected = {p.name for p in output.iterdir()} - names - {'SHA256SUMS'}
    if unexpected:
        raise ValueError('unexpected package files: ' + ', '.join(sorted(unexpected)))
    (output / 'SHA256SUMS').write_text(''.join(
        hashlib.sha256((output / name).read_bytes()).hexdigest() + '  ' + name + '\n'
        for name in sorted(names)))
    print(output)


if __name__ == '__main__':
    main()
