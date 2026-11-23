#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Report the nearest EDK II stable base, or the checkout revision."""
import argparse
import re
import subprocess
from pathlib import Path

UPSTREAM = 'https://github.com/tianocore/edk2.git'
TAG = re.compile(r'edk2-stable[0-9]{6}')
PATTERN = 'edk2-stable' + '[0-9]' * 6


def git(repo, *args):
    return subprocess.check_output(['git', '-C', repo, *args], text=True).strip()


def fetch_base_tag(repo):
    # The downstream fork need not publish TianoCore's tags. Match the
    # checked-out history against the upstream refs, including annotated tags.
    refs = git(repo, 'ls-remote', '--tags', UPSTREAM, 'refs/tags/edk2-stable*')
    tags = {}
    for line in refs.splitlines():
        oid, ref = line.split()
        tag = ref.removeprefix('refs/tags/').removesuffix('^{}')
        if TAG.fullmatch(tag):
            tags[oid] = tag
    if not tags:
        raise SystemExit('TianoCore did not return any EDK II stable tags')

    head = git(repo, 'rev-parse', 'HEAD')
    depth = 64
    previous = ''
    while True:
        history = git(repo, 'rev-list', '--first-parent', head)
        for oid in history.splitlines():
            if oid in tags:
                tag = 'refs/tags/' + tags[oid]
                git(repo, 'fetch', '--no-tags', '--no-recurse-submodules', UPSTREAM, tag + ':' + tag)
                return
        if history == previous or git(repo, 'rev-parse', '--is-shallow-repository') != 'true':
            return
        previous = history
        git(repo, 'fetch', '--deepen=' + str(depth), '--no-tags', '--no-recurse-submodules', 'origin', head)
        depth *= 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo', type=Path)
    parser.add_argument('--fetch', action='store_true', help='fetch stable tag metadata during source preparation')
    args = parser.parse_args()
    repo = args.repo.resolve()
    if Path(git(repo, 'rev-parse', '--show-toplevel')).resolve() != repo:
        raise SystemExit(f'{repo} is not an EDK II checkout')
    if args.fetch:
        fetch_base_tag(repo)
    version = git(repo, 'describe', '--tags', '--first-parent', '--match', PATTERN, '--abbrev=0', '--always', 'HEAD')
    if TAG.fullmatch(version):
        version = version.removeprefix('edk2-')
    else:
        version = git(repo, 'rev-parse', '--short=12', 'HEAD')
    print('EDK II ' + version)


if __name__ == '__main__':
    main()
