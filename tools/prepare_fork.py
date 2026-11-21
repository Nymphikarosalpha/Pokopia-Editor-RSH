"""Prepare the fork README while keeping upstream contents and licensing."""
from pathlib import Path
import ast
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
MARKER = '<!-- Fork-specific features -->'
README_SECTION = """
---

## Resident, Spawn & Habitat (RSH) — development preview

This fork extends the original editor with resident management, selectable island habitat placement, experimental encounter records and selected event-item preparation.

- **Resident controls:** add or update residents, remove resident registry entries, and assign or unlink a home.
- **Island selection:** place or link habitats on supported stage layouts, including custom island names.
- **Encounter experiment:** optional habitat-linked encounter records; arbitrary Pokémon spawns are **not** guaranteed.
- **Event habitats:** prepare certain required event items. This does **not** mark event quests completed or bypass every story requirement.

See [fork features and limitations](docs/FORK_FEATURES.md), the [fork changelog](CHANGELOG_FORK.md), and the [Windows build guide](docs/BUILD_WINDOWS.md).

Launch from source with `python pokopia_gui_fork.py`, or build an executable using `python tools/build_fork.py`.

Original project: [cycalo/Pokopia-Editor](https://github.com/cycalo/Pokopia-Editor). The original GPL-3.0 license and all upstream author notices are retained.
"""

def check():
    required = ['pokopia_gui.py', 'pokopia_save.py', 'pokopia_island.py', 'PokopiaEditor.spec', 'LICENSE', 'README.md', 'gui/app.py']
    absent = [name for name in required if not (ROOT / name).exists()]
    if absent:
        raise SystemExit('Missing original upstream files: ' + ', '.join(absent) + '\nFirst fork and clone https://github.com/cycalo/Pokopia-Editor, then copy the overlay into that checkout.')
    addon = ROOT / 'pokopia_gui_fork.py'
    if not addon.is_file():
        raise SystemExit('Missing pokopia_gui_fork.py')
    ast.parse(addon.read_text(encoding='utf-8'), filename=str(addon))
    spec = (ROOT / 'PokopiaEditor.spec').read_text(encoding='utf-8')
    if "pokopia_gui.py" not in spec:
        raise SystemExit('Upstream build spec has changed: entry script pokopia_gui.py not found.')
    print('Base repository, license, entry point and extension syntax: OK')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    check()
    if args.check_only:
        return
    readme = ROOT / 'README.md'
    old = readme.read_text(encoding='utf-8')
    # Earlier previews appended a fork section at the very bottom. Replace it.
    old = old.split('<!-- Fork-specific features -->')[0].rstrip() + '\n' if '<!-- Fork-specific features -->' in old else old
    section = (ROOT / 'README_RSH_TOP_SECTION.md').read_text(encoding='utf-8').strip()
    if '<!-- RSH fork overview -->' not in old:
        # Put the fork identity before Getting started, not below the original README.
        marker = '## 🚀 Getting started'
        if marker not in old:
            raise SystemExit('Original README structure changed: Getting started heading was not found.')
        old = old.replace(marker, section + '\n\n' + marker, 1)
    old = old.replace('# Pokopia Editor\n', '# Pokopia Editor RSH\n', 1)
    old = old.replace('label=Download&style=for-the-badge', 'label=Upstream%20release&style=for-the-badge', 1)
    old = old.replace("1. **[Download `PokopiaEditor.exe`](https://github.com/cycalo/Pokopia-Editor/releases/latest)**. There's nothing to install.",
                      '1. **RSH preview:** Build or download the RSH artifact from this fork\'s Actions tab. For the unchanged upstream version, see [upstream releases](https://github.com/cycalo/Pokopia-Editor/releases/latest).', 1)
    readme.write_text(old, encoding='utf-8')
    print('README identity and RSH overview updated near top.')
    ignore = ROOT / '.gitignore'
    existing = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
    additions = ['# Fork local build files', 'PokopiaEditor.fork-build.spec', '.fork-build/', '__pycache__/', 'dist/', 'build/']
    if 'PokopiaEditor.fork-build.spec' not in existing:
        ignore.write_text(existing.rstrip()+'\n\n'+'\n'.join(additions)+'\n', encoding='utf-8')
    print('Fork preparation complete.')

if __name__ == '__main__':
    main()
