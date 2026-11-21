"""Create per-version release notes from the actual commits since the last release.

Explicit release notes can be supplied at docs/releases/<tag>.md for detailed
feature releases. Otherwise the current commit history is used; never duplicate
cumulative CHANGELOG.md as if it were a single-version change list.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys


def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], text=True, encoding='utf-8').strip()


def build_notes(tag: str) -> str:
    if not re.fullmatch(r'v0\.1\.\d+', tag):
        raise ValueError('Expected version tag v0.1.N')
    specified = pathlib.Path('docs/releases') / (tag + '.md')
    if specified.exists():
        changes = specified.read_text(encoding='utf-8').strip()
        if not changes.startswith('## '):
            raise ValueError(f'{specified} needs a Markdown section heading')
    else:
        current = int(tag.split('.')[-1])
        known = git('tag', '--list', 'v0.1.*').splitlines()
        candidates = [(int(v.split('.')[-1]), v) for v in known
                      if re.fullmatch(r'v0\.1\.\d+', v) and int(v.split('.')[-1]) < current]
        previous = max(candidates)[1] if candidates else None
        commit_range = f'{previous}..HEAD' if previous else 'HEAD'
        # Git commit subjects are the source of truth for the current release's
        # changes. Preserve all commits since the previous version, not just HEAD.
        subjects = git('log', '--reverse', '--pretty=format:%s', commit_range).splitlines()
        subjects = [x.strip() for x in subjects if x.strip()]
        if not subjects:
            subjects = [git('log', '-1', '--pretty=format:%s')]
        changes = '## What changed\n' + '\n'.join('- ' + s for s in subjects)
        if previous:
            changes += f'\n\nChanges since `{previous}`.'
    return (f'# Pokopia Editor RSH {tag}\n\n{changes}\n\n'
            '## Download\n'
            'Download **PokopiaEditor_RSH.exe** from the assets section below.\n\n'
            '## Development preview notes\n'
            '- Close the emulator and back up save files before editing.\n'
            '- Habitat-linked encounters and event workflows remain experimental.\n'
            '- Special and legendary Pokémon spawning is not guaranteed.\n'
            '- GPL-3.0 fork of [cycalo/Pokopia-Editor](https://github.com/cycalo/Pokopia-Editor).\n')


def main() -> None:
    tag = os.environ.get('RSH_RELEASE_TAG', '').strip()
    if not tag:
        raise ValueError('RSH_RELEASE_TAG is required')
    dst = pathlib.Path('dist') / 'rsh-release-notes.md'
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(build_notes(tag), encoding='utf-8')
    print('Created', dst, 'for', tag)


if __name__ == '__main__':
    main()
