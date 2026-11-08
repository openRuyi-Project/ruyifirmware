#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tag Ruyi Firmware and its pinned project sources without pushing."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PROJECT_OWNER = 'openRuyi-Project'


def git(repo, *args, optional=False):
    result = subprocess.run(['git', '-C', str(repo), *args],
                            capture_output=True, text=True)
    if result.returncode:
        if optional and result.returncode == 1:
            return None
        raise ValueError(f'{repo.name}: {result.stderr.strip()}')
    return result.stdout.strip()


def repository_id(url):
    if url.startswith('git@github.com:'):
        path = url.split(':', 1)[1]
    else:
        parsed = urlsplit(url)
        if parsed.hostname != 'github.com':
            return None
        path = parsed.path.lstrip('/')
    return path.removesuffix('.git').rstrip('/')


def push_remote(repo, expected):
    names = git(repo, 'remote').splitlines()
    names.sort(key=lambda name: (name not in ('ruyi', 'origin'), name != 'ruyi', name))
    for name in names:
        urls = git(repo, 'remote', 'get-url', '--push', '--all', name).splitlines()
        if len(urls) == 1 and repository_id(urls[0]) == expected:
            return name
    raise ValueError(f'{repo.name}: no push remote for github.com/{expected}')


@dataclass
class Target:
    name: str
    repo: Path
    commit: str
    remote: str
    existing: bool
    branch: bool


def inspect_target(name, repo, commit, expected, tag):
    if not repo.is_dir() or Path(git(repo, 'rev-parse', '--show-toplevel')).resolve() != repo:
        raise ValueError(f'{name}: missing development repository at {repo}')
    git(repo, 'cat-file', '-e', f'{commit}^{{commit}}')
    remote = push_remote(repo, expected)
    ref = f'refs/tags/{tag}'
    existing = git(repo, 'rev-parse', '--verify', '--quiet', ref, optional=True)
    if existing is not None:
        tagged = git(repo, 'rev-parse', f'{ref}^{{commit}}')
        if tagged != commit:
            raise ValueError(f'{name}: tag {tag} points to {tagged}, expected {commit}')
    else:
        git(repo, 'var', 'GIT_COMMITTER_IDENT')
    branch = git(repo, 'rev-parse', '--verify', '--quiet', 'refs/heads/ruyi', optional=True)
    return Target(name, repo, commit, remote, existing is not None, branch == commit)


def release_targets(root, repos_dir, tag):
    git(root, 'check-ref-format', f'refs/tags/{tag}')
    revision = git(root, 'rev-parse', 'HEAD^{commit}')
    modules = f'{revision}:.gitmodules'
    paths = git(root, 'config', '--blob', modules, '--null', '--get-regexp',
                r'^submodule\..*\.path$')
    entries = git(root, 'ls-tree', '-r', '-z', revision)
    pins = {}
    for entry in entries.split('\0'):
        if entry:
            metadata, path = entry.split('\t', 1)
            mode, kind, commit = metadata.split()
            if mode == '160000' and kind == 'commit':
                pins[path] = commit

    targets, skipped = [], []
    for entry in paths.split('\0'):
        if not entry:
            continue
        key, path = entry.split('\n', 1)
        name = key[len('submodule.'):-len('.path')]
        if path not in pins:
            raise ValueError(f'{name}: {path} is not a submodule in {revision}')
        if name == 'linux':
            skipped.append((name, 'uses its existing kernel tag'))
            continue
        url = git(root, 'config', '--blob', modules, '--get', key[:-4] + 'url')
        expected = repository_id(url)
        if expected is None or not expected.startswith(PROJECT_OWNER + '/'):
            skipped.append((name, 'upstream repository'))
            continue
        repo = (repos_dir / name).resolve()
        if not repo.is_relative_to(repos_dir) or repo == repos_dir:
            raise ValueError(f'{name}: invalid development repository path')
        if repo.is_relative_to(root / 'src'):
            raise ValueError(f'{name}: use the development repository, not the src/ validation checkout')
        targets.append(inspect_target(name, repo, pins[path], expected, tag))

    targets.append(inspect_target('ruyifirmware', root, revision,
                                  PROJECT_OWNER + '/ruyifirmware', tag))
    return targets, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag', help='release tag, for example 20261108')
    parser.add_argument('--repos-dir', type=Path, default=ROOT.parent,
                        help='parent directory of component development repositories (default: sibling directories)')
    parser.add_argument('--dry-run', action='store_true',
                        help='check all targets and print the plan without creating tags')
    args = parser.parse_args()
    try:
        targets, skipped = release_targets(ROOT, args.repos_dir.resolve(), args.tag)
        for name, reason in skipped:
            print(f'# Skip {name}: {reason}')
        for target in targets:
            action = 'Keep' if target.existing else 'Create'
            print(f'# {action} {target.name}: {args.tag} at {target.commit}')

        if not args.dry_run:
            for target in targets:
                if not target.existing:
                    git(target.repo, 'tag', '-a', '-m', f'Ruyi Firmware {args.tag}',
                        '--', args.tag, target.commit)

        print('\n# Push commands. Run after creating the tags. The release repository is last.')
        print('set -e')
        for target in targets:
            command = ['git', '-C', str(target.repo), 'push', '--atomic',
                       '--no-follow-tags', '--recurse-submodules=no', target.remote]
            if target.branch:
                command.append(f'{target.commit}:refs/heads/ruyi')
            else:
                print(f'# {target.name}: ruyi does not match the pinned commit; push only the tag.')
            command.append(f'refs/tags/{args.tag}')
            print(shlex.join(command))
    except (OSError, ValueError) as error:
        parser.exit(1, f'error: {error}\n')


if __name__ == '__main__':
    main()
