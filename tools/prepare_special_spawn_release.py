"""Prepare the v0.2.1 source release in a full GitHub checkout, not an EXE folder.

This command patches *only* the exact audited main version of pokopia_gui_fork.py.
It is intended for the Windows GitHub Actions release job and will abort on
mismatched source instead of applying offsets to an unknown editor version.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rsh_legendary_patch import BASE_BLOB_SHA, github_blob_sha, rewrite

RELEASE_MARKER = '## v0.2.1 — Special encounter experiment and settings guidance (2026-11-21)'
CHANGELOG = f'''{RELEASE_MARKER}

### Changed in the editor
- Recognizes Mew, Mewtwo, Suicune, Raikou, Entei and other known special Pokémon, with a dedicated experimental ID−4 path.
- The experimental path lists existing island habitat records as **position anchors**. No fabricated Mew/Mewtwo habitat, no new habitat construction, and no resident/home or story flag modifications are performed by this path.
- Fixes the disabled habitat/action controls for special Pokémon when the stage is supported and has a usable anchor. If no anchor exists or the stage layout is unsupported, the editor explicitly explains why the action is disabled.
- Adds Pokémon-category-specific recommended settings and a complete in-dialog mode guide.
- Creates a ZIP backup of the opened save before the experimental change, validates the stage layout and free encounter slot, and uses the normal Undo/Ctrl+S journal.

### Experimental limitations
- **No in-game Mew or Mewtwo spawn has been verified.** ID−4 is only a hypothesis about an encounter reference field; the game may ignore it, choose another Pokémon, or require story/event flags.
- Only previously examined stage-file layouts are eligible for ID−4. Other islands remain available to ordinary habitat editing; do not assume that equal file sizes prove the same event record semantics.
- The single-file Windows EXE is created by the repository's existing Windows PyInstaller build on GitHub Actions. No runtime source-file or Python dependency is required for the end user.
'''

DOC_MARKER = '## Special Pokémon experimental encounter (v0.2.1)'
DOC = f'''{DOC_MARKER}

The editor automatically identifies known special/legendary Pokémon (for example **Mew and Mewtwo**) from its resident IDs and species names. The action selector offers **Experimental encounter (ID−4; automatic special detection)**. For these species it lists an **existing** habitat as a technical UID/position anchor instead of inventing a species habitat. A matched anchor does **not** mean that the game accepts that habitat as Mew's or Mewtwo's real habitat.

Recommended settings are visible in the Resident + Habitat Studio for normal Pokémon, E-series event Pokémon, legendary/mythical encounters, and Pokémon with no reliable recipe mapping. The **Which settings for which Pokémon?** help button describes the options.

The editor refuses to write when there is no usable anchor, no free compatible encounter row, or an unsupported stage layout. It creates and verifies a ZIP backup first and stages the write in the undoable island journal. Only press Ctrl+S on a disposable testing save. **There is no verified direct spawn/unlock for Mew, Mewtwo or any other legendary Pokémon.**
'''


README_MARKER = '## Which spawn settings should I use? (RSH v0.2.1)'
README_SPAWN_GUIDE = """## Which spawn settings should I use? (RSH v0.2.1)

Choose by **encounter mechanism**, not by elemental type (Fire, Water, Psychic,
etc.). A Pokémon's elemental typing does not establish its spawn logic.
The editor displays **Recommended settings** when you select a resident.

| Pokémon category and examples | Recommended editor action | What this actually does |
| --- | --- | --- |
| **Normal Pokémon with a verified habitat mapping** (e.g., Oddish or Bulbasaur) | **Build habitat + register resident**, or **Assign an existing habitat** when a matching one is already built | Builds/assigns the known habitat and edits the resident registry; an immediate visible encounter is not guaranteed. |
| **Limited-time/E-series event Pokémon** (e.g., Feebas, Milotic, Hoppip, Sableye) | **Build event habitat on the map** when a verified `E-*` recipe exists. **Prepare event materials in bag only** is optional. | Places event objects, or supplies missing materials. It does **not** complete event quests, open event windows or force an NPC spawn. |
| **Legendary/mythical or story-dependent Pokémon** (e.g., **Mew, Mewtwo, Suicune, Raikou, Entei, Lugia, Ho-Oh, Articuno, Zapdos, Moltres, Kyogre, Volcanion**) | For a real first encounter, use the game's **story/event encounter**. For save research only, **Experimental encounter (ID−4)** on a supported stage with a pre-existing habitat **position anchor**. | Attempts one hypothetical 32-byte encounter record. **Not a verified spawn.** The anchor belongs to a different habitat and does not become an authentic Mew/Mewtwo habitat. |
| **Special Pokémon with a known event habitat**, e.g. Jirachi | **Build event habitat** for the documented event recipe; use **ID−4** only for controlled, disposable-save research if the stage is supported | A real story/event gate may still be required. Recipe creation is not the same as spawning or completing an event. |
| **No buildable habitat or unknown recipe mapping** | **Register resident without a habitat** (registry only); or investigate the species/ID before attempting a manual housing experiment | Does not create a visible world Pokémon. Do not assign a random habitat as a supposed species spawn. |

**ID−4 research limits:** only stages whose path ends in `G00/STGDAT01.BIN`
or `B00/STGDAT01.BIN` are candidates, and only when the record-layout
validation finds a free compatible event slot. For special Pokémon the island
must already contain a valid habitat record to act as an unchanged UID/position
anchor. Other islands may still support normal habitat building. The editor
creates a full ZIP backup, uses its Undo journal and requires **Ctrl+S** for
writing. Close the emulator before save editing, and test **only on a copy**.

**Why are the controls grey?** Either the selected action has no valid habitat
mapping, the island layout is unsupported for ID−4, the island lacks a usable
existing anchor, or an experimental record cannot be safely written. Switch
to an appropriate mode; do not force a write or invent an event-habitat ID.

**Important:** The ID−4-to-species relationship is a **hypothesis**. No successful
Mew or Mewtwo spawn is confirmed. Pokémon-Dex registration and home assignment
are separate from a visible NPC and from story/event unlocks.
"""


def inject_section(file: Path, marker: str, section: str) -> bool:
    if not file.is_file():
        raise ValueError(f'Missing repository file: {file}')
    content = file.read_text(encoding='utf-8')
    if marker in content:
        return False
    if not content.endswith('\n'):
        content += '\n'
    if content.startswith('# '):
        first, rest = content.split('\n', 1)
        changed = first + '\n\n' + section + '\n' + rest
    else:
        changed = section + '\n' + content
    file.write_text(changed, encoding='utf-8')
    return True


def prepare(root: Path, dry_run: bool = False) -> list[str]:
    root = root.resolve()
    target = root / 'pokopia_gui_fork.py'
    if not target.is_file() or not (root / 'PokopiaEditor.spec').is_file():
        raise ValueError('The full GitHub source checkout is required; an EXE folder is not valid.')
    raw = target.read_bytes().replace(b'\r\n', b'\n')
    contents = raw.decode('utf-8')
    if 'def _sp_run_special_pending(mp):' in contents and \
            'def species_mode_recommendation(' in contents:
        changed_code = False
        patched = contents
    elif github_blob_sha(raw) == BASE_BLOB_SHA:
        patched = rewrite(contents)
        compile(patched, str(target), 'exec')
        changed_code = True
    else:
        raise ValueError('GitHub editor source differs from the audited v0.2.0 build. '
                         'The patch was NOT applied. Check current main before proceeding.')
    result = []
    if changed_code:
        result.append('pokopia_gui_fork.py')
    changelog_path = root / 'CHANGELOG_FORK.md'
    docs_path = root / 'docs' / 'FORK_FEATURES.md'
    readme_path = root / 'README.md'
    if not changelog_path.is_file() or not docs_path.is_file() or not readme_path.is_file():
        raise ValueError('Required README, changelog or feature documentation is missing.')
    # Validate before the first write. Source is written atomically.
    if dry_run:
        planned = result[:]
        for target, marker in ((changelog_path, RELEASE_MARKER),
                               (docs_path, DOC_MARKER),
                               (readme_path, README_MARKER)):
            if marker not in target.read_text(encoding='utf-8'):
                planned.append(str(target.relative_to(root)))
        return planned
    if changed_code:
        tmp = target.with_suffix('.py.rsh021.tmp')
        try:
            tmp.write_text(patched, encoding='utf-8', newline='')
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
    if inject_section(changelog_path, RELEASE_MARKER, CHANGELOG):
        result.append('CHANGELOG_FORK.md')
    if inject_section(docs_path, DOC_MARKER, DOC):
        result.append('docs/FORK_FEATURES.md')
    if inject_section(readme_path, README_MARKER, README_SPAWN_GUIDE):
        result.append('README.md')
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', default=str(ROOT), help='Git checkout with pokopia_gui_fork.py')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    try:
        modified = prepare(Path(args.repo), dry_run=args.dry_run)
    except Exception as exc:
        print('RELEASE PATCH REFUSED:', exc, file=sys.stderr)
        return 1
    print('Patch verified; files:', modified if modified else '(already patched)')
    print('This does not prove a successful in-game Mew or Mewtwo encounter.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
