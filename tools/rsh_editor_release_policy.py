"""Guard against publishing documentation/CI commits as editor versions.

RSH release notes are curated editor-specific changes supplied at dispatch.
Prior true editor version: v0.1.4, which contains resident/habitat fixes.
Later editor versions must have new code/data compared with the previous
editor release. No new version is generated from CI run numbers.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

BASE_COMMIT = 'd179632cc95b2c2f5fa015c7dc13de9ae30f398d'
EDITOR_PATHS = (
    'pokopia_gui_fork.py', 'pokopia_gui.py', 'pokopia_save.py',
    'pokopia_island.py', 'pokopia_extras.py', 'gui/',
    'data/',
)


def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], text=True, encoding='utf-8').strip()


def validate_version(version: str) -> None:
    if not re.fullmatch(r'v\d+\.\d+\.\d+', version):
        raise ValueError('Version must be semantic, e.g. v0.2.0')
    numbers = tuple(map(int, version[1:].split('.')))
    if numbers < (0, 2, 0):
        raise ValueError('Use v0.2.0 or higher for future editor updates; old version numbers are reserved')


def latest_editor_base() -> str:
    # Existing historical version v0.1.4 represents the last true editor change.
    # After that, use the most recent v0.2.* or newer editor release tag.
    tags = git('tag', '--list', 'v*').splitlines()
    versions = []
    for tag in tags:
        if re.fullmatch(r'v\d+\.\d+\.\d+', tag):
            nums = tuple(map(int, tag[1:].split('.')))
            if nums >= (0, 2, 0):
                versions.append((nums, tag))
    return max(versions)[1] if versions else BASE_COMMIT


def editor_paths_changed(base: str) -> bool:
    result = subprocess.run(['git', 'diff', '--name-only', base, 'HEAD', '--'],
                            check=True, capture_output=True, text=True)
    changed = result.stdout.splitlines()
    return any(name == prefix or name.startswith(prefix)
               for name in changed for prefix in EDITOR_PATHS)


def write_notes(version: str, editor_changes: str) -> None:
    notes = editor_changes.replace('\r', '').strip()
    if len(notes) < 18 or not any(line.lstrip().startswith('- ') for line in notes.splitlines()):
        raise ValueError('Write concrete English editor changes as Markdown bullets starting with "- "')
    if any(x in notes.casefold() for x in ('github workflow', 'readme only', 'release automation')):
        raise ValueError('Only real editor functionality belongs in release notes, not repository maintenance')
    dest = Path('dist/rsh-editor-release-notes.md')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        f'# Pokopia Editor RSH {version}\n\n'
        '## Changes in this editor version\n\n'
        f'{notes}\n\n'
        '## Download\n\n'
        'Download **PokopiaEditor_RSH.exe** under Assets below.\n\n'
        '## Known limitations\n\n'
        '- Development preview: close your emulator and back up saves before editing.\n'
        '- Experimental habitat-linked encounters do not guarantee a visible spawn.\n'
        '- Building event habitats does not complete time-limited event quests.\n\n'
        'Based on [cycalo/Pokopia-Editor](https://github.com/cycalo/Pokopia-Editor); GPL-3.0.\n',
        encoding='utf-8')
    print(f'Validated new editor version {version}; notes saved to {dest}', flush=True)


def main() -> int:
    version = os.environ['RSH_VERSION'].strip()
    changes = os.environ['RSH_EDITOR_CHANGES']
    validate_version(version)
    base = latest_editor_base()
    if not editor_paths_changed(base):
        raise RuntimeError(f'No actual editor-source or data changes since {base}. '
                           'Do not publish a version for README, workflow or release-history changes.')
    write_notes(version, changes)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
