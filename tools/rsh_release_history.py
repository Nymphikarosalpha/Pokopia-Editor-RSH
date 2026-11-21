"""Produce immutable notes for individual historical RSH releases.

The GitHub Actions workflow downloads the original build artifacts and uses
softprops/action-gh-release to publish them. This script NEVER creates a release,
so each version retains its own source EXE, notes and commit reference.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile

REPO = 'Nymphikarosalpha/Pokopia-Editor-RSH'
ARTIFACT = 'Pokopia-Editor-RSH-Windows-Preview'

# These are real completed, successful build runs from the repository history.
# Never change an existing version's source commit or release notes.
HISTORY = [
    {
        'tag': 'v0.1.1',
        'run': 44848526136,
        'sha': 'd03597f1571e2ed66a5f3e4138d4d5786190c68d',
        'title': 'Initial RSH Development Preview',
        'notes': '''## Highlights
- Initial Resident, Spawn & Habitat extension of the upstream Pokopia Editor.
- Added resident registry editing, resident removal controls and home assignment tools.
- Added experimental habitat-linked encounter records and event material preparation.
- Included Lichii save discovery support and build/test infrastructure.

## Known limitations
- Experimental resident/encounter edits do not guarantee a visible world NPC.
- Event completion flags and unrestricted legendary spawns are not implemented.
- Back up save data and close the emulator before editing.
''',
    },
    {
        'tag': 'v0.1.2',
        'run': 44849321888,
        'sha': 'c236081aa09d5c5b399683105f61426276be8641',
        'title': 'Automated Windows Preview Release',
        'notes': '''## Changes
- Added GitHub Actions publication of a downloadable Windows preview executable.
- Updated download and build instructions for the RSH fork.
- Preserved all features and experimental limitations of v0.1.1.

## Notes
This build introduced the original rolling `rsh-preview` release workflow, which has since been replaced by versioned releases.
''',
    },
    {
        'tag': 'v0.1.3',
        'run': 44850060326,
        'sha': '25532a9f037a041baf2df05fd06bab139f518269',
        'title': 'Download Button and Repository Presentation',
        'notes': '''## Changes
- Added a prominent Pokémon-inspired Windows download button to the project README.
- Added the associated download-button SVG asset.

## Notes
This was a documentation and presentation update; it did not introduce new in-game functionality.
''',
    },
    {
        'tag': 'v0.1.4',
        'run': 44882150845,
        'sha': 'd179632cc95b2c2f5fa015c7dc13de9ae30f398d',
        'title': 'Resident Habitat Catalog and Event Workflow Fixes',
        'notes': '''## Fixed
- Audited 402 named resident records against 252 bundled habitat recipes.
- Added resident-ID-based habitat lookup and corrected form-specific mappings, including both Toxtricity forms.
- Improved manual habitat selection and event habitat selection validation.

## Changed
- Added separate **Build event habitat on the map** and **Prepare event materials in bag only** actions.
- Kept **Build habitat + register resident** as the default flow.
- Added catalog and event-workflow regression tests.

## Known limitations
Building event habitat objects does not automatically mark quests complete or guarantee an event Pokémon spawns.
''',
    },
    {
        'tag': 'v0.1.5',
        'run': 44883052213,
        'sha': '4c5b0b5ade5c0f516f2bbc55be04e457b1be325b',
        'title': 'Release Navigation and Changelog',
        'notes': '''## Changes
- Updated the graphical README download button to link to the general Releases page.
- Added a standard `CHANGELOG.md` to the source repository.
- Improved access to release history and documentation.

## Notes
This was a documentation update; it did not change the editor's game-save functionality.
''',
    },
]


def release_notes(tag: str) -> str:
    item = next((r for r in HISTORY if r['tag'] == tag), None)
    if item is None:
        raise ValueError(f'Unknown historical RSH release tag: {tag}')
    return (f'# Pokopia Editor RSH {tag} — {item["title"]}\n\n'
            + item['notes'].strip() + '\n\n'
            + '## Download\n'
            + 'Download **PokopiaEditor_RSH.exe** from the Assets section below.\n\n'
            + '## Provenance\n'
            + f'- Original successful [Windows build #{item["run"]}]'
              f'(https://github.com/{REPO}/actions/runs/{item["run"]})\n'
            + f'- Source commit: [`{item["sha"][:12]}`]'
              f'(https://github.com/{REPO}/commit/{item["sha"]})\n\n'
            + 'Historical development preview. Back up your save and close the emulator.\n'
            + 'GPL-3.0 fork of [cycalo/Pokopia-Editor]'
              '(https://github.com/cycalo/Pokopia-Editor).\n')


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notes-only', action='store_true', required=True)
    parser.add_argument('tag', choices=[r['tag'] for r in HISTORY])
    parser.add_argument('output', type=pathlib.Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(release_notes(args.tag), encoding='utf-8')
    print(f'Prepared release notes for {args.tag}: {args.output}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
