"""Publish immutable, versioned releases for the archived RSH preview builds.

Each release references the original commit and attaches the executable from
its corresponding successful GitHub Actions build. Existing releases are left
untouched. Requires GH_TOKEN (GitHub Actions GITHUB_TOKEN) with actions:read
and contents:write permissions.
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


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['gh', *args], check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def release_exists(tag: str) -> bool:
    p = gh('release', 'view', tag, '--repo', REPO, '--json', 'tagName', check=False)
    if p.returncode == 0:
        return True
    if 'not found' in p.stderr.lower() or '404' in p.stderr:
        return False
    # GitHub CLI error text can vary. Fail closed on authentication problems.
    raise RuntimeError(f'Cannot check release {tag}: {p.stderr.strip()}')


def main() -> int:
    if not os.environ.get('GH_TOKEN'):
        print('GH_TOKEN is required', file=sys.stderr)
        return 2
    for item in HISTORY:
        tag = item['tag']
        if release_exists(tag):
            print(f'{tag}: already exists, preserving release and asset')
            continue
        with tempfile.TemporaryDirectory(prefix=f'rsh-{tag}-') as temp:
            dest = pathlib.Path(temp)
            print(f'{tag}: downloading original artifact from run {item["run"]}', flush=True)
            gh('run', 'download', str(item['run']), '--repo', REPO,
               '--name', ARTIFACT, '--dir', str(dest))
            exe = dest / 'PokopiaEditor_RSH.exe'
            if not exe.is_file() or exe.stat().st_size < 1_000_000:
                raise RuntimeError(f'{tag}: historical build artifact is missing or incomplete')
            notes = dest / 'notes.md'
            notes.write_text(item['notes'] + '\n---\n\n'
                             + f'Build: [GitHub Actions run #{item["run"]}]'
                             + f'(https://github.com/{REPO}/actions/runs/{item["run"]})  \n'
                             + f'Source commit: [`{item["sha"][:10]}`]'
                             + f'(https://github.com/{REPO}/commit/{item["sha"]})\n\n'
                             + 'This is an archived development preview. Save backups are recommended.\n',
                             encoding='utf-8')
            print(f'{tag}: publishing original EXE ({exe.stat().st_size:,} bytes)', flush=True)
            gh('release', 'create', tag, str(exe), '--repo', REPO,
               '--target', item['sha'], '--title', f'Pokopia Editor RSH {tag} — {item["title"]}',
               '--notes-file', str(notes), '--prerelease')
            print(f'{tag}: published successfully', flush=True)
    print('Historical releases complete; original rsh-preview left unchanged.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
