# Pokopia Editor - extended resident and habitat controls
# Fork extension for cycalo/Pokopia-Editor (GPL-3.0).
# Experimental spawn records and event-item handling; see docs/FORK_FEATURES.md.
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import struct
import traceback
import zlib

import pokopia_save as ps
import pokopia_island as pi
import sys as _rsh_sys
import pokopia_extras as _rsh_extras


def _rsh_portable_lichii_roots():
    """Find common portable Lichii user directories without scanning whole drives.

    A portable installation typically has <emulator folder>/user/nand.
    Installation folders elsewhere can be selected with Open > Browse for a folder.
    """
    if _rsh_sys.platform != 'win32':
        return []
    from pathlib import Path
    candidates = []
    for name in ('LICHII_USER_DIR', 'LICHII_HOME'):
        value = os.environ.get(name)
        if value:
            candidates.append(Path(value).expanduser())
    places = [Path(_rsh_sys.executable).resolve().parent, Path.cwd(),
              Path.home() / 'Desktop', Path.home() / 'Downloads']
    for base in places:
        candidates.append(base)
        try:
            for child in base.iterdir():
                if child.is_dir() and 'lichii' in child.name.casefold():
                    candidates.append(child)
        except OSError:
            continue
    found = []
    seen = set()
    for folder in candidates:
        for candidate in (folder, folder / 'user'):
            try:
                if not (candidate / 'nand').is_dir():
                    continue
                norm = os.path.normcase(os.path.realpath(str(candidate)))
            except OSError:
                continue
            if norm not in seen:
                seen.add(norm)
                found.append(str(candidate))
    return found


def _rsh_enable_lichii_support():
    """Enable Lichii save discovery and running-emulator warnings in the upstream UI."""
    extras = _rsh_extras
    if getattr(extras, '_rsh_lichii_patched', False):
        return
    extras.YUZU_FAMILY = tuple(dict.fromkeys((*extras.YUZU_FAMILY, 'lichii')))
    extras.EMULATORS = tuple(dict.fromkeys((*extras.EMULATORS, 'lichii')))
    old_roots = extras._data_roots

    def roots(name):
        existing = list(old_roots(name))
        if name.casefold() == 'lichii':
            existing.extend(_rsh_portable_lichii_roots())
        return list(dict.fromkeys(existing))

    extras._data_roots = roots
    extras._rsh_lichii_patched = True


_rsh_enable_lichii_support()

from gui.app import main

_PATCH_ERROR = None


def dex_slots(resident):
    valid = {i for i, _ in ps.COLLECTION['dex']}
    return [slot for slot, ri in enumerate(ps.DEX_RESIDENT)
            if slot in valid and ri == resident]


def installed_home_template(c):
    """Return the layout of a real home from this exact save, preserving unknown fields."""
    for i in c.villagers():
        o = ps.HOME_OFS + i * ps.HOME_SIZE
        if c.data[o] == 1 and struct.unpack_from('<H', c.data, o + 1)[0] >= 101:
            return bytes(c.data[o:o + ps.HOME_SIZE])
    raise ValueError('No occupied habitat home exists to use as a safe save template.')


def edit_resident(c, idx, friendship, when, register=True, home=None, habitat_type=None):
    """Modify CommonSave in memory, so the editor's own undo/save and backups apply."""
    if not isinstance(idx, int) or not (0 < idx < ps.VIL_COUNT):
        raise ValueError('Invalid resident ID')
    if idx >= len(ps.VILLAGER_NAMES) or not ps.VILLAGER_NAMES[idx].strip():
        raise ValueError('This resident ID has no species name')
    if not 0 <= friendship <= ps.FRIENDSHIP_MAX:
        raise ValueError('Friendship out of range')
    if not isinstance(when, _dt.datetime) or not (2020 <= when.year < 2100):
        raise ValueError('Invalid first-meeting date')
    slots = dex_slots(idx)
    if register and not slots:
        raise ValueError('No supported Pokédex entry for this resident')
    o = idx * ps.VIL_SIZE
    new = not c.villager_present(idx)
    if new:
        sources = c.villagers()
        if not sources:
            raise ValueError('No resident template in save')
        # The game uses a repeated initialized resident header. Unknown state is intentionally
        # preserved from an existing record, mutable interaction fields reset.
        source = sources[0] * ps.VIL_SIZE
        record = bytearray(c.data[source:source + ps.VIL_SIZE])
        record[0x11:0x17] = b'\0' * 6
        record[0x1B:0x1F] = b'\0' * 4
        record[0xC4] = 0
        record[ps.VIL_MET_DATE:ps.VIL_MET_DATE + 12] = b'\0' * 12
        record[0x15] = 1
        c.data[o:o + ps.VIL_SIZE] = record
        h = ps.HOME_OFS + idx * ps.HOME_SIZE
        c.data[h:h + ps.HOME_SIZE] = bytes(ps.HOME_SIZE)
    struct.pack_into('<H', c.data, o + 0x11, friendship)
    sec = c.play_seconds
    if sec is not None:
        struct.pack_into('<f', c.data, o + ps.VIL_MET_PLAYTIME, float(sec))
    struct.pack_into('<6H', c.data, o + ps.VIL_MET_DATE,
                     when.year, when.month, when.day, when.hour, when.minute, when.second)
    if register:
        c.unlock_collection('dex', slots)
    if home is not None:
        area, uid, (x, y, z) = home
        if not (0 <= area < 256 and 101 <= uid < 1025 and all(-32768 <= int(v) < 32768 for v in (x,y,z))):
            raise ValueError('Invalid habitat/home coordinates')
        h = ps.HOME_OFS + idx * ps.HOME_SIZE
        row = bytearray(installed_home_template(c))
        row[0] = 1
        struct.pack_into('<H', row, 1, uid)
        row[3] = int(area)
        struct.pack_into('<3h', row, 6, int(x), int(y), int(z))
        c.data[h:h + ps.HOME_SIZE] = row
    if habitat_type is not None:
        # Complete habitat dex only for catalogued habitat types.
        if habitat_type in {i for i, _ in ps.COLLECTION['habitat']}:
            c.unlock_collection('habitat', [habitat_type])
    return 'added' if new else 'updated'


def remove_resident(c, idx):
    """Unregister one CommonSave resident; restore the game's observed empty slot.

    This does NOT claim to delete an independently persisted world object in STGDAT.
    Dex/history entries are intentionally preserved. The standard unoccupied
    record in examined G00/B00 CommonSave files has only byte +0x15 set to 1.
    """
    if not isinstance(idx, int) or not 0 < idx < ps.VIL_COUNT:
        raise ValueError('Invalid resident ID')
    if not c.villager_present(idx):
        raise ValueError('The resident is not present in this save.')
    # Never silently overwrite a custom structure: require the normal 374-byte
    # resident shape and the ordinary presence marker at +1..+16.
    o = idx * ps.VIL_SIZE
    h = ps.HOME_OFS + idx * ps.HOME_SIZE
    if len(c.data[o:o+ps.VIL_SIZE]) != ps.VIL_SIZE or len(c.data[h:h+ps.HOME_SIZE]) != ps.HOME_SIZE:
        raise ValueError('Unrecognized save structure; nothing was changed.')
    blank = bytearray(ps.VIL_SIZE)
    blank[0x15] = 1
    c.data[o:o+ps.VIL_SIZE] = blank
    c.data[h:h+ps.HOME_SIZE] = bytes(ps.HOME_SIZE)
    if c.villager_present(idx):
        raise ValueError('Resident removal failed; undo the change.')
    return True


def remove_resident_ui(page, idx=None):
    from PySide6.QtWidgets import QMessageBox
    if not page.app.save:
        return page.app.toast('Open a save file first.', 'err')
    sel = page.selected()
    if idx is None:
        if len(sel) != 1:
            return page.app.toast('Select exactly one resident.', 'err')
        idx = sel[0]
    c = page.app.save.common
    if not c.villager_present(idx):
        return QMessageBox.information(page, 'Not present', 'This resident is not in the save.')
    name = ps.name_of(ps.VILLAGER_NAMES, idx, 'Resident')
    msg = (f'Remove {name} (resident ID {idx}) from the save registry?\n\n'
           'Removes the 374-byte resident record and its home assignment.\n'
           'The Pokédex entry and built habitat are retained.\n'
           'Separately stored world NPCs may still exist or reappear. '
           'Full deletion of visible NPCs has NOT been validated.\n\n'
           'A ZIP backup is created first. Press Ctrl+S to commit changes.')
    if QMessageBox.warning(page, 'Remove resident (experimental)', msg,
                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
        return
    try:
        backup = backup_common_save(page.app.save)
    except Exception as exc:
        return QMessageBox.critical(page, 'Backup failed',
                                    'No changes: ' + str(exc))
    if page.app.do(f'{name} (ID {idx}): remove resident registry entry',
                   lambda: remove_resident(c, idx)):
        page.fill()
        QMessageBox.information(page, 'Resident registry entry removed',
            'The entry has been removed from the list. Press Ctrl+S to save.\n\n'
            'Previous backup: ' + backup)


def backup_common_save(save):
    """Backup entire source save before any resident deletion or event experiment."""
    from pathlib import Path
    import zipfile
    root = Path(save.folder).resolve()
    common = root / 'G00' / 'CMNDAT.BIN'
    if not common.is_file():
        raise ValueError('G00/CMNDAT.BIN was not found.')
    files = [p for p in root.rglob('*') if p.is_file()]
    if not files or len(files)>80 or sum(p.stat().st_size for p in files)>500*1024*1024:
        raise ValueError('Unexpected save file count or size; create a manual backup first.')
    import datetime
    outdir = Path.home() / 'PokopiaEditor_Backups'
    outdir.mkdir(parents=True, exist_ok=True)
    output = outdir / ('Pokopia_before_resident_event_' +
                       datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.zip')
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for p in files:
            z.write(p, p.relative_to(root))
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:
            output.unlink(missing_ok=True)
            raise ValueError('Backup archive verification failed.')
    return str(output)


def event_content_bypass(c, idx, recipe, when, friendship, add_resident=False, register_dex=False, allow_unverified=False):
    """Unlock event habitat *materials* and catalog – not unknown quest/event flags.

    Stages and quest state are not modified. The user can build the event
    habitat without having participated in its limited-time event. A real
    story-event-completed flag is unknown and intentionally left untouched.
    """
    name = ps.name_of(ps.VILLAGER_NAMES, idx, 'Resident')
    if not is_event_recipe(recipe):
        raise ValueError('This is not a supported event habitat recipe.')
    valid = matching_recipes(name, recipes(), idx) or []
    verified = any(str(r['dex']) == str(recipe.get('dex')) and
                   int(r['type']) == int(recipe['type']) for r in valid)
    if not verified and not allow_unverified:
        raise ValueError('Recipe does not match this event Pokémon. ' 
                         'Use the explicit unverified-habitat option to override.')
    from collections import Counter
    need = Counter()
    for part in recipe.get('parts', []):
        if part.get('kind') != 'item':
            continue
        item_id = int(part.get('item') or 0)
        count = int(part.get('count') or 0)
        if not (0 < item_id <= ps.ITEM_MASK and 0 < count <= 255):
            raise ValueError('Invalid event items in the habitat recipe.')
        need[item_id] += count
    missing = {}
    for item_id, count in need.items():
        have = sum(c.get_slot(s)[1] for s in range(ps.INV_COUNT)
                   if c.get_slot(s)[0] == item_id)
        if count > have:
            missing[item_id] = count-have
    # Pre-flight: no halfway edit if the inventory is full.
    empty_slots = sum(c.get_slot(s)[0] == 0 for s in range(ps.INV_MAIN))
    needed_slots = sum((count+254)//255 for count in missing.values())
    if empty_slots < needed_slots:
        raise ValueError(f'Not enough free bag slots ({needed_slots} needed, {empty_slots} available).')
    for item_id, count in missing.items():
        while count:
            take = min(count, 255)
            c.add_item(item_id, take)
            count -= take
    item_catalog = {i for i, _ in ps.COLLECTION.get('item', [])}
    for item_id in need:
        if item_id in item_catalog:
            c.unlock_collection('item', [item_id])
    habitat_types = {i for i, _ in ps.COLLECTION['habitat']}
    typ = int(recipe['type'])
    if typ in habitat_types:
        # 'Discovered' only, NOT 'built': this is the accurate state until built.
        c.unlock_collection('habitat', [typ], partial=True)
    if add_resident:
        edit_resident(c, idx, friendship, when, register=register_dex)
    elif register_dex:
        slots = dex_slots(idx)
        if slots:
            c.unlock_collection('dex', slots)
    return {'items': dict(need), 'added': missing, 'habitat': typ,
            'resident': bool(add_resident)}


def unlink_home(c, idx):
    """Remove a resident's home link WITHOUT removing the resident or world structures.

    Existing unhomed residents in the user's reference saves have home_type=0.
    Preserve the ancillary bytes, whose purpose is not fully understood.
    """
    if not isinstance(idx, int) or not (0 < idx < ps.VIL_COUNT):
        raise ValueError('Invalid resident ID')
    if not c.villager_present(idx):
        raise ValueError('The resident is not present in this save.')
    start = ps.HOME_OFS + idx * ps.HOME_SIZE
    if c.data[start] == 0:
        return 'The resident already has no home assigned.'
    # Clear known type, UID, island and xyz and linked-home marker only.
    c.data[start:start+12] = bytes(12)
    c.data[start+20] = 0
    return 'Home assignment removed; the resident is retained.'


def species_spawn_notice(idx, recipe=None):
    """Distinguish housing/unlocking from meeting a special Pokémon."""
    name = display_species_name(idx)
    if habitat_key(name) in _EVENT_POKEMON:
        return (f'{name}: event Pokémon. Its event habitat can be built and '
                'assigned as a home. The first appearance may still require '
                'event unlocks. ID−4 is NOT verified for event Pokémon.')
    if is_special_pokemon(name):
        return (f'{name}: special Pokémon. Mew has a separate story encounter, '
                'while Suicune is encountered through special Dream Island content. '
                'A normal habitat does NOT trigger their first appearance. '
                'A home assignment or Pokédex entry does not spawn a world NPC.')
    if recipe and int(recipe.get('type', 0)) == 240 and idx != 510:
        return ('WARNING: "Surrounded by stars" is associated with Jirachi. '
                'A natural habitat encounter may select Jirachi.')
    return ('A habitat can trigger normal encounters, but it does not guarantee a species. '
            'Only the separate ID−4 experiment attempts to create an encounter record; '
            'species control is not confirmed.')


def direct_unlink(page):
    from PySide6.QtWidgets import QMessageBox
    if not page.app.save:
        return page.app.toast('Load a save first.', 'err')
    ids = page.selected()
    if len(ids) != 1:
        return page.app.toast('Select exactly one resident.', 'err')
    idx = ids[0]
    c = page.app.save.common
    v = c.get_villager(idx)
    if not v['home_type']:
        return page.app.toast('This resident currently has no home.', 'info')
    question = (f'Remove the home assignment for {v["name"]} (ID {idx})?\n\n'
                'The resident and its Pokédex entry are retained. '
                'Habitat objects on the map are NOT deleted.')
    if QMessageBox.question(page, 'Remove home assignment', question,
                            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
        return
    if page.app.do(f'{v["name"]}: unlink home', lambda: unlink_home(c, idx)):
        page.fill()


def read_habitats(app, area):
    """Read the actual stage habitat registry; consult in-memory staged edits first."""
    loaded = app.save.islands.get(area) if app.save else None
    if loaded is not None:
        return [dict(uid=h.uid, home=tuple(h.home), type=h.type, name=h.name)
                for h in loaded.habitats]
    path = app.save.stage_files()[area]
    with open(path, 'rb') as f:
        buf = f.read()
    if len(buf) < pi.HEADER or struct.unpack_from('<I', buf)[0] != ps.MAGIC:
        raise ValueError('Unrecognized island data')
    end = struct.unpack_from('<I', buf, 0x10)[0]
    if not pi.HEADER < end <= len(buf):
        raise ValueError('Invalid island data length')
    raw = zlib.decompress(buf[pi.HEADER:end])
    if len(raw) != pi.DATA_SIZE:
        raise ValueError('Island data has an unknown size')
    rows = []
    for j in range(pi.HABITAT_CAP):
        off = pi.HABITATS + j * pi.HABITAT_SIZE
        typ = struct.unpack_from('<I', raw, off+18)[0]
        if not typ:
            continue
        vals = struct.unpack_from('<9h', raw, off)
        if not (0 <= vals[0] <= vals[3] < 2048 and
                0 <= vals[1] <= vals[4] < 128 and
                0 <= vals[2] <= vals[5] < 2048 and typ < 4096):
            continue
        rows.append(dict(uid=101+j, home=tuple(vals[6:9]), type=typ,
                         name=ps.name_of(ps.HABITAT_NAMES, typ, 'Habitat')))
    return rows


def display_species_name(idx):
    """Show game-specific forms without altering the upstream resident name table.

    Resident slots 143 and 266 refer to the two distinct Toxtricity forms. Their
    original names are identical, so matching only the displayed name loses the form.
    """
    if idx in _FORM_HABITATS_BY_RESIDENT:
        return _FORM_HABITATS_BY_RESIDENT[idx][0]
    return ps.name_of(ps.VILLAGER_NAMES, idx, 'Resident')


def species():
    return [(i, display_species_name(i)) for i, n in enumerate(ps.VILLAGER_NAMES)
            if 0 < i < ps.VIL_COUNT and n.strip()]


def recipes():
    """The same bundled one-click recipes as the original Island Map, no extra download."""
    with open(os.path.join(pi.DATA, 'habitat_recipes.json'), encoding='utf-8') as f:
        raw = json.load(f)
    return sorted((r for r in raw if r.get('type') and r.get('dex')),
                  key=lambda r: r['name'].casefold())



# Habitat data maps Pokémon to confirmed, buildable spawn habitats.
# Recipes come from the original editor's built-in habitat catalog.
# Species-to-habitat data comes from a public reference table when available,
# because neither the recipe JSON nor the save provides species associations.
# A restricted offline fallback avoids known mismatches.
_HABITAT_SOURCE = 'https://raw.githubusercontent.com/JEschete/PokopiaPlanning/main/reference/Pokopia.csv'
_HABITAT_MAP = None
_HABITAT_MAP_STATUS = None
# Certain forms share a name in data/villager.txt but have DIFFERENT resident IDs.
# These IDs were cross-referenced with data/catalog_residents.bin (Dex slots 278/327)
# and the Pokopia habitat reference (#189/#190). Do not merge them into one resident.
_FORM_HABITATS_BY_RESIDENT = {
    143: ('Toxtricity (Amped Form)', ('Amped rock stage',)),
    266: ('Toxtricity (Low Key Form)', ('Low-key rock stage',)),
    229: ('Wooper (Paldean Form)', ('Marshy tall grass',)),
    256: ('Shellos (West Sea)', ('Road Sign',)),
    257: ('Shellos (East Sea)', ('Road Sign',)),
    258: ('Gastrodon (West Sea)', ('Ocean fishing spot',)),
    259: ('Gastrodon (East Sea)', ('Ocean fishing spot',)),
    267: ('Tatsugiri (Curly Form)', ('Beach Set',)),
    268: ('Tatsugiri (Droopy Form)', ('Beach Set',)),
    269: ('Tatsugiri (Stretchy Form)', ('Beach Set',)),
    584: ('Frillish (Male Form)', ('Playing sailor', 'Ocean treasures')),
    585: ('Frillish (Female Form)', ('Playing sailor', 'Ocean treasures')),
    586: ('Jellicent (Male Form)', ('Marine teatime',)),
    587: ('Jellicent (Female Form)', ('Marine teatime',)),
}

_HABITAT_FALLBACK = {
    # The generic name is intentionally inclusive; the resident-ID mapping above
    # narrows it to the correct form in resident-specific operations.
    'toxtricity': ('Amped rock stage', 'Low-key rock stage'),
    'suicune': (), 'raikou': (), 'entei': (), 'kyogre': (), 'volcanion': (),
    'gengar': ('Surprise in store',),
    'haunter': ('Surprise in store', 'Spooky study'),
    'gastly': ('Spooky study',),
    'jirachi': ('Surrounded by stars',),
    'mewtwo': (), 'mew': (), 'lugia': (), 'hooh': (),
    'articuno': (), 'zapdos': (), 'moltres': (),
    'bulbasaur': ('Tall grass', 'Bench with greenery'),
    'ivysaur': ('Field of Flowers', 'Bench with greenery'),
    'venusaur': ('Field of Flowers', 'Garden Terrace'),
    'charmander': ('Tall grass',),
    'charmeleon': ('Campsite',),
    'charizard': ('Tall grass', 'Berry-feast Campsite'),
    'squirtle': ('Tall grass', 'Hydrated tall grass'),
    'wartortle': ('Hydrated tall grass',),
    'blastoise': ('Hydrated tall grass', 'Floating in the shade'),
    'oddish': ('Tall grass',),
    'bellsprout': ('Tree-shaded tall grass',),
    # Proven event habitats: the original offline map omitted these despite
    # their recipes being bundled with the Editor. Missing network -> missing habitat.
    'feebas': ('Exciting beach',),
    'milotic': ('Marine leisure activities',),
    'hoppip': ('Yellow carpet',),
    'skiploom': ('Yellow carpet', 'Field-trip friends'),
    'jumpluff': ('Yellow carpet', 'Dandelion lunchtime'),
    'sableye': ('Treasure-hunting set',),
}


def habitat_key(name):
    """Compare human-readable names across the recipe list and Pokédex tables."""
    if not name:
        return ''
    return ''.join(c for c in str(name).casefold()
                   .replace('é', 'e').replace('♀', 'f').replace('♂', 'm')
                   if c.isalnum())


def habitat_map():
    """Once per editor process: fetch 300+ species mappings, or stay safely restricted.

    No standalone tool, installer or plugin is needed. Network outages cause a
    visible restricted state rather than reverting to showing all habitats.
    """
    global _HABITAT_MAP, _HABITAT_MAP_STATUS
    if _HABITAT_MAP is not None:
        return _HABITAT_MAP, _HABITAT_MAP_STATUS
    _HABITAT_MAP = {habitat_key(k): tuple(v) for k, v in _HABITAT_FALLBACK.items()}
    _HABITAT_MAP_STATUS = 'offline'
    try:
        import csv
        import io
        import urllib.request
        request = urllib.request.Request(_HABITAT_SOURCE,
                    headers={'User-Agent': 'Pokopia-Editor-ResidentHabitat/3.0'})
        with urllib.request.urlopen(request, timeout=4.0) as response:
            data = response.read(400000)
        rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
        # Reject partial, malformed or unrelated responses before using them.
        if len(rows) < 290 or not {'Name', 'Habitat 1', 'Habitat 2', 'Habitat 3'} <= set(rows[0]):
            raise ValueError('Unrecognized habitat reference data')
        mapped = {}
        for row in rows:
            name = habitat_key(row.get('Name'))
            if not name:
                continue
            names = []
            for n in (1, 2, 3):
                name_from_csv = (row.get('Habitat '+str(n)) or '').strip()
                if name_from_csv and habitat_key(name_from_csv) not in {habitat_key(x) for x in names}:
                    names.append(name_from_csv)
            mapped[name] = tuple(names)
        if len(mapped) < 290 or 'gengar' not in mapped or 'mewtwo' not in mapped:
            raise ValueError('Habitat reference data is incomplete')
        # The confirmed special residents must never get a mismatched habitat.
        mapped['gengar'] = ('Surprise in store',)
        mapped['jirachi'] = ('Surrounded by stars',)
        mapped['mewtwo'] = ()
        # Event species need specific event recipes, NOT a random habitat.
        mapped.update({
            'milotic': ('Marine leisure activities',),
            'feebas': ('Exciting beach',),
            'hoppip': ('Yellow carpet',),
            'skiploom': ('Yellow carpet', 'Field-trip friends'),
            'jumpluff': ('Yellow carpet', 'Dandelion lunchtime'),
            'sableye': ('Treasure-hunting set',),
        })
        _HABITAT_MAP.update(mapped)
        _HABITAT_MAP_STATUS = 'online (PokopiaPlanning / Serebii)'
    except Exception:
        _HABITAT_MAP_STATUS = 'offline (verified Pokémon only; network unavailable)'
    return _HABITAT_MAP, _HABITAT_MAP_STATUS


_EVENT_POKEMON = frozenset({'milotic', 'feebas', 'hoppip', 'skiploom',
                            'jumpluff', 'sableye', 'jirachi'})


def is_event_recipe(recipe):
    """Event-specific built-in recipe; this does not imply event/story completion."""
    return bool(recipe) and str(recipe.get('dex', '')).startswith('E-')


def permitted_habitats_for_action(all_recipes, matches, method, manual=False):
    """Resolve dialog choices and validation with identical rules.

    A manual event selection only exposes E-series recipes, never all normal
    habitat recipes, and never modifies event story flags.
    """
    if method in ('event', 'event_items'):
        event_recipes = [r for r in all_recipes if is_event_recipe(r)]
        if manual:
            return event_recipes
        return [r for r in (matches or []) if is_event_recipe(r)]
    if manual and method in ('existing', 'new'):
        return list(all_recipes)
    return list(matches or [])


_SPECIAL_POKEMON = frozenset({
    'mew', 'mewtwo', 'suicune', 'raikou', 'entei', 'lugia', 'hooh',
    'articuno', 'zapdos', 'moltres', 'kyogre', 'volcanion', 'jirachi'
})


def is_special_pokemon(name, matched=None):
    """Special-encounter Pokémon: a normal habitat does not unlock the species."""
    return habitat_key(name) in _SPECIAL_POKEMON


# Bundled, versioned resident-ID-to-habitat-Dex crosswalk. Unlike species-name
# matching this distinguishes forms and works even without Internet access.
_RSH_RESIDENT_CATALOG = None


def offline_resident_catalog():
    global _RSH_RESIDENT_CATALOG
    if _RSH_RESIDENT_CATALOG is not None:
        return _RSH_RESIDENT_CATALOG
    path = os.path.join(pi.DATA, 'rsh_resident_habitats.json')
    try:
        with open(path, encoding='utf-8') as f:
            doc = json.load(f)
        if doc.get('schema') != 1 or len(doc.get('recipe_ids_by_resident', {})) < 350:
            raise ValueError('Invalid or incomplete offline habitat catalog')
        _RSH_RESIDENT_CATALOG = doc['recipe_ids_by_resident']
    except (OSError, ValueError, TypeError) as exc:
        # An incomplete package must be reported as unsupported; never guess an
        # unrelated habitat just because two forms happen to share one name.
        _RSH_RESIDENT_CATALOG = {}
    return _RSH_RESIDENT_CATALOG


def matching_recipes(pokemon_name, all_recipes, resident_index=None):
    """Return buildable habitats by Resident ID and validated Habitat Dex ID.

    None: no verified relation. []: explicitly no buildable normal habitat.
    Unknown resident IDs must NOT fall back to same-named variants' recipes.
    """
    if resident_index is not None:
        catalog = offline_resident_catalog()
        keys = catalog.get(str(resident_index))
        if keys is not None:
            wanted = set(map(str, keys))
            return [r for r in all_recipes if str(r.get('dex')) in wanted]
        # Support older installations without the bundled catalog for the two
        # independently verified Toxtricity form mappings only.
        form = _FORM_HABITATS_BY_RESIDENT.get(resident_index)
        if form is not None:
            wanted = {habitat_key(x) for x in form[1]}
            return [r for r in all_recipes if habitat_key(r.get('name')) in wanted]
        return None
    # Name-only requests are retained for non-resident contexts, not for
    # resident creation where the index must be known.
    allowed, _ = habitat_map()
    names = allowed.get(habitat_key(pokemon_name))
    if names is None:
        return None
    wanted = {habitat_key(n) for n in names}
    return [r for r in all_recipes if habitat_key(r.get('name')) in wanted]


def species_mode_recommendation(idx, all_recipes, area, eligible_areas):
    """Read-only guide. Never infer a species' encounter from a habitat anchor."""
    if idx is None:
        return 'Select a Pokémon to see the recommended action.'
    name = display_species_name(idx)
    key = habitat_key(name)
    matched = matching_recipes(name, all_recipes, idx)
    event_matches = [r for r in (matched or []) if is_event_recipe(r)]
    if is_special_pokemon(name):
        kind = ('SPECIAL / EVENT (unique encounter)' if key in _EVENT_POKEMON
                else 'LEGENDARY / MYTHICAL (unique encounter)')
        test = ('ID−4 is available for a separate save copy only if an existing '
                'anchor is on this island.' if area in eligible_areas else
                'ID−4 is disabled on this island layout; select an eligible STGDAT01 island.')
        event_note = (' A known E-series habitat may be built in Event habitat mode, '
                      'but that does not complete the event.' if event_matches else
                      ' No verified event habitat is assigned to this Pokémon.')
        return (f'{kind} — {name}. Recommended for real encounter: original story/event '
                'conditions, not a guessed habitat. For save editing: '
                'Register resident without habitat = registry ONLY. '
                + test + ' No spawn or event completion is confirmed.' + event_note)
    if key in _EVENT_POKEMON:
        if event_matches:
            return (f'EVENT POKÉMON — {name}. Recommended: Build event habitat on the map '
                    '(E-series recipe). "Prepare event materials in bag only" adds materials, '
                    'but does not build or unlock the event. The game may still require '
                    'separate event conditions. ID−4 is not validated here.')
        return (f'EVENT POKÉMON — {name}. No verified E-series habitat mapping is '
                'available. Do not select a random event recipe for spawning. '
                'Register without a habitat for registry-only testing, or use a manual '
                'habitat override with no encounter guarantee.')
    if matched:
        return (f'NORMAL / HABITAT-BASED — {name}. Recommended: "Build habitat + '
                'register resident" to place a mapped habitat, or "Assign an existing '
                'habitat" if one already exists on the island. Neither guarantees an '
                'immediate visible encounter. ID−4 is an unverified experimental option.')
    if matched == []:
        return (f'NO BUILDABLE HABITAT MAPPED — {name}. Recommended: Register resident '
                'without a habitat for registry-only experiments. Do not assume any '
                'manual habitat will create this species.')
    return (f'UNKNOWN HABITAT MAPPING — {name}. Recommended: verify the resident ID '
            'and habitat data first. Manual habitat selection is an unverified '
            'housing/building experiment, not a proven spawn. Registration without '
            'a habitat only updates the save registry.')


def species_settings_reference():
    """Full workflow legend shown by the dialog's Help button."""
    return ('NORMAL (mapped habitat): Build habitat + register resident; '
            'or assign an existing compatible habitat. Not an instant spawn.\n\n'
            'EVENT (E-series recipe): Build event habitat on the map. '
            'Prepare event materials is inventory-only; neither completes quests.\n\n'
            'LEGENDARY / MYTHICAL (Mew, Suicune, Mewtwo, etc.): '
            'Do not invent an event habitat. Real encounters may require story '
            'or unique conditions. Register without habitat is registry-only. '
            'ID−4 is a separate unverified encounter experiment: existing habitat '
            'is a position anchor, not a Pokémon-specific spawn recipe.\n\n'
            'UNKNOWN / NO MAPPING: Avoid random habitat IDs. Manual choices are '
            'explicitly unverified.\n\n'
            'IMPORTANT: Fire/Water/Grass/etc. elemental types do NOT determine '
            'the editor mode. The category is based on the encounter mechanism '
            'and resident-ID-to-habitat mapping.\n\n'
            'ID−4 limitations: supported STGDAT01 stage layout, free compatible '
            '32-byte event slot, and a pre-existing anchor for specials. '
            'No successful in-game special spawn has been verified. Use a '
            'disposable save, close the emulator, and keep the ZIP backup.')


def add_dialog(page, selected_index=None):
    from PySide6.QtCore import Qt, QDateTime
    from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QComboBox,
                                  QSpinBox, QDateTimeEdit, QCheckBox, QLabel, QMessageBox, QVBoxLayout, QPushButton)
    app = page.app
    if not app.save:
        return app.toast('Open a save before editing residents.', 'err')
    c = app.save.common
    dlg = QDialog(page)
    dlg.setWindowTitle('Pokémon · Habitat · Spawn  |  Experimental')
    dlg.resize(730, 590)
    form = QFormLayout(dlg)
    query = QLineEdit()
    query.setPlaceholderText('Pokémon name or resident ID (e.g. Milotic)')
    choose = QComboBox()
    choose.setMinimumWidth(350)
    area_box = QComboBox()
    for area, path in app.save.stage_files().items():
        label = ps.name_of(ps.AREA_NAMES, area, 'Area')
        folder = os.path.basename(os.path.dirname(os.path.normpath(str(path))))
        area_box.addItem(f'{label}  [{folder}]', area)
    # When coming from a currently selected island map, open on that island.
    last_map = app.pages.get('Island Map')
    current_area = getattr(last_map, 'area', None)
    if current_area is not None:
        pos = area_box.findData(current_area)
        if pos >= 0:
            area_box.setCurrentIndex(pos)
    mode = QComboBox()
    mode.addItem('Assign an existing habitat', 'existing')
    mode.addItem('Build habitat + register resident (does not force spawn)', 'new')
    mode.addItem('Experimental encounter (ID−4; automatic special detection)', 'spawn')
    mode.addItem('Register resident without a habitat (no spawn)', 'none')
    mode.addItem('Remove an existing home assignment', 'unlink')
    mode.addItem('Remove resident from save registry (experimental)', 'remove')
    mode.addItem('Build event habitat on the map (no quest completion)', 'event')
    mode.addItem('Prepare event materials in bag only', 'event_items')
    # Building is the common RSH workflow. Existing-habitat mode requires a
    # habitat that is already registered on this island.
    mode.setCurrentIndex(1)
    hab = QComboBox()
    hab.setMinimumWidth(350)
    manual_hab = QCheckBox('Manually select an unverified habitat')
    manual_hab.setToolTip('Manual selection is only a habitat/home override, not a spawn. '
                          'In event modes, only built-in E-series event recipes are offered. '
                          'No quest or time-limited event is completed.')
    friend = QSpinBox()
    friend.setRange(0, ps.FRIENDSHIP_MAX)
    friend.setValue(20)
    met = QDateTimeEdit()
    met.setCalendarPopup(True)
    met.setDisplayFormat('yyyy-MM-dd HH:mm:ss')
    met.setDateTime(QDateTime.currentDateTime())
    dex = QCheckBox('Register Pokédex entry')
    dex.setChecked(True)
    event_resident = QCheckBox('Also register event resident (does not create a visible NPC)')
    event_resident.setChecked(False)
    info = QLabel('')
    info.setWordWrap(True)
    hinfo = QLabel('')
    hinfo.setWordWrap(True)
    recommend = QLabel('Select a Pokémon for recommendations.')
    recommend.setWordWrap(True)
    recommend.setStyleSheet('padding: 8px; border: 1px solid #777; border-radius: 5px;')
    help_modes = QPushButton('Which settings for which Pokémon?')
    caution = QLabel('Building and assigning a habitat does not force an encounter or finish event quests. '
                     'Mew, Suicune and other special Pokémon may require story or Dream Island encounters. '
                     'They may be registered as residents or assigned homes; '
                     'this is NOT a visible NPC spawn. Always back up saves before experimental changes.')
    caution.setWordWrap(True)
    caution.setStyleSheet('color: #eebc7a;')
    form.addRow('Search:', query)
    form.addRow('Pokémon:', choose)
    form.addRow('Island:', area_box)
    form.addRow('Resident / habitat action:', mode)
    form.addRow('Habitat:', hab)
    form.addRow('', manual_hab)
    form.addRow('Friendship:', friend)
    form.addRow('First met:', met)
    form.addRow('', dex)
    form.addRow('', event_resident)
    form.addRow('Status:', info)
    form.addRow('Recommended settings:', recommend)
    form.addRow('', help_modes)
    form.addRow('Habitat details:', hinfo)
    form.addRow(caution)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.button(QDialogButtonBox.Ok).setText('Apply / open map')
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    form.addRow(buttons)
    ok_button = buttons.button(QDialogButtonBox.Ok)
    available = species()
    all_recipes = None
    known_habs = []
    loading_error = ''

    def update_info():
        idx = choose.currentData()
        if idx is None:
            info.setText('No matching Pokémon')
            return
        v = c.get_villager(idx) if c.villager_present(idx) else None
        name = display_species_name(idx)
        state = ', '.join(f'{s}:{c.collection_state("dex", s)}' for s in dex_slots(idx)) or 'none'
        info.setText(f'{name} (Resident-ID {idx}) | ' +
                     ('already registered' if v else 'new') + f' | Pokédex-Slots {state}' +
                     (f' | Home UID {v["home_uid"]}' if v and v['home_type'] else ' | no home'))
        dex.setEnabled(bool(dex_slots(idx)) and mode.currentData() not in ('spawn', 'remove', 'unlink'))
        hinfo.setText(species_spawn_notice(idx))
        if v:
            friend.setValue(min(ps.FRIENDSHIP_MAX, v['friendship']))
            if v['met']:
                met.setDateTime(QDateTime.fromString(v['met'].strftime('%Y-%m-%d %H:%M:%S'), 'yyyy-MM-dd HH:mm:ss'))

    def populate(q=''):
        q = q.casefold().strip()
        current = choose.currentData()
        choose.blockSignals(True)
        choose.clear()
        for i, name in available:
            if not q or q in name.casefold() or str(i) == q:
                choose.addItem(f'{name}  ·  {i}' + ('  ✓' if c.villager_present(i) else ''), i)
        target = choose.findData(current)
        choose.setCurrentIndex(target if target >= 0 else 0)
        choose.blockSignals(False)
        update_info()
        populate_habs()

    def populate_habs(*_):
        nonlocal all_recipes, known_habs, loading_error
        try:
            recommend.setText(species_mode_recommendation(
                choose.currentData(), all_recipes if all_recipes is not None else recipes(),
                area_box.currentData(), _sp_supported_stages(app)))
        except Exception as ex:
            recommend.setText('Recommendation unavailable: ' + str(ex))
        hab.blockSignals(True)
        hab.clear()
        hab.blockSignals(False)
        hinfo.setText('')
        idx = choose.currentData()
        method, area = mode.currentData(), area_box.currentData()
        is_test = method == 'spawn'
        manual_hab.setEnabled(method in ('existing', 'new', 'event', 'event_items'))
        event_resident.setEnabled(method == 'event')
        friend.setEnabled(method not in ('spawn', 'remove', 'unlink', 'event_items') and
                           (method != 'event' or event_resident.isChecked()))
        met.setEnabled(method not in ('spawn', 'remove', 'unlink', 'event_items') and
                        (method != 'event' or event_resident.isChecked()))
        dex.setEnabled(method not in ('spawn', 'remove', 'unlink', 'event_items') and
                        (method != 'event' or event_resident.isChecked()) and
                        bool(dex_slots(idx)) if idx is not None else False)
        if method in ('none', 'unlink', 'remove'):
            hab.setEnabled(False)
            ok_button.setEnabled(idx is not None)
            hinfo.setText('Reset the resident record and home link, not world NPCs. '
                          'A ZIP backup is required. Pokédex entries are preserved.' if method == 'remove' else
                          'Unlink the home, but keep the resident.' if method == 'unlink' else
                          species_spawn_notice(idx) if idx is not None else 'Select a Pokémon.')
            if method in ('remove', 'unlink') and idx is not None:
                ok_button.setEnabled(c.villager_present(idx))
            return
        ok_button.setEnabled(False)
        if idx is None:
            hab.setEnabled(False)
            hinfo.setText('Select a Pokémon first.')
            return
        try:
            if all_recipes is None:
                all_recipes = recipes()
            name = display_species_name(idx)
            matched = matching_recipes(name, all_recipes, idx)
            special = is_special_pokemon(name, matched)
            if method in ('event', 'event_items') and not manual_hab.isChecked():
                # No arbitrary event-recipe crossover: either there is a confirmed
                # E-series recipe for this resident or the mode remains unavailable.
                if not any(is_event_recipe(r) for r in (matched or [])):
                    hab.setEnabled(False)
                    hinfo.setText('No verified E-series event habitat is mapped to this resident. '
                                  'For a habitat-only experiment, enable manual selection. '
                                  'This does not unlock a time-limited event or create an NPC.')
                    return
            if is_test:
                # The experimental event record is NOT a special-encounter generator.
                # Only the two save types inspected offline are eligible.
                supported = _sp_supported_stages(app)
                if area not in supported:
                    hab.setEnabled(False)
                    hinfo.setText('The ID−4 encounter experiment is only supported for G00 and B00. '
                                  'You can still build a normal habitat on this island.')
                    return
                if habitat_key(name) in _EVENT_POKEMON and not special:
                    hab.setEnabled(False)
                    hinfo.setText(name+': an event habitat can be built, but the ID−4 '
                                  'encounter experiment is not validated for event Pokémon. '
                                  'Use the habitat-building and resident-registration mode.')
                    return
                if special:
                    # Do NOT invent a Mew habitat. Use an existing habitat entry
                    # solely as a position/UID anchor for the unverified ID−4 row.
                    known_habs = read_habitats(app, area)
                    for anchor in known_habs:
                        if (101 <= int(anchor['uid']) <= 1024 and
                                0 < int(anchor['type']) < 4096 and
                                len(anchor['home']) == 3):
                            hab.addItem(
                                f"Anchor: {anchor['name']}  ·  UID {anchor['uid']} (existing)",
                                ('special-anchor', int(anchor['uid'])))
                    hab.setEnabled(bool(hab.count()))
                    ok_button.setEnabled(bool(hab.count()))
                    hinfo.setText(
                        name + ': special/event Pokémon automatically detected. '
                        'ID−4 uses an existing habitat as a POSITION ANCHOR only. '
                        'No habitat is built, assigned, or advertised as the species habitat. '
                        'A 32-byte encounter hypothesis is staged for this island, '
                        'NOT a verified NPC spawn. ' +
                        ('Select an existing anchor and continue.' if hab.count() else
                         'This island has no usable existing habitat anchor.'))
                    return
                if matched == [] or idx <= 4:
                    hab.setEnabled(False)
                    hinfo.setText(name+': no verified normal habitat and no supported ID−4 encounter option. '
                                  'The editor will not guess a spawn recipe.')
                    return
            if matched is None and not manual_hab.isChecked() and not special:
                hab.setEnabled(False)
                hinfo.setText('No verified resident-ID-to-habitat relation is available for '+name+'. '
                              'Enable manual selection to build or assign a habitat without '
                              'claiming it triggers a Pokémon encounter.')
                return
            if special and method in ('new', 'existing'):
                # Home assignment for a special Pokémon is allowed, not claimed to
                # trigger its unique first encounter.
                matched = all_recipes
            candidate_recipes = permitted_habitats_for_action(
                all_recipes, matched, method, manual_hab.isChecked() and not is_test)
            if not candidate_recipes:
                hab.setEnabled(False)
                hinfo.setText(name+': no compatible, buildable habitat recipe is available. '
                              'Try manual selection for a home-only experiment; no spawn is guaranteed.')
                return
            permitted_types = {int(r['type']) for r in candidate_recipes}
            if method == 'existing':
                known_habs = read_habitats(app, area)
                taken = {c.get_villager(i)['home_uid'] for i in c.villagers()
                         if c.get_villager(i)['home_type'] and c.get_villager(i)['home_area'] == area}
                for h in known_habs:
                    if h['type'] not in permitted_types:
                        continue
                    tag = '  [occupied]' if h['uid'] in taken else '  [available]'
                    hab.addItem(f'{h["name"]}  ·  UID {h["uid"]}' + tag, h['uid'])
            else:
                for recipe in candidate_recipes:
                    hab.addItem(f'{recipe["name"]}  ·  #{recipe["dex"]}', str(recipe['dex']))
            if not hab.count():
                hab.setEnabled(False)
                hinfo.setText('No matching '+ ('existing' if method == 'existing' else 'buildable') +
                              ' habitat for '+name+' found. '+
                              ('Switch to \"Build habitat + register resident\" to create this habitat.'
                               if method == 'existing' else 'Special recruitment may be required.'))
                return
            hab.setEnabled(True)
            ok_button.setEnabled(True)
        except Exception as ex:
            loading_error = str(ex)
            hab.setEnabled(False)
            hinfo.setText('Habitat data could not be read: ' + loading_error)
            return
        update_hinfo()

    def update_hinfo(*_):
        method = mode.currentData()
        key = hab.currentData()
        if method == 'spawn' and isinstance(key, tuple) and key[0] == 'special-anchor':
            anchor = next((h for h in known_habs if h['uid'] == key[1]), None)
            if anchor:
                hinfo.setText(
                    f"EXPERIMENT ONLY: {display_species_name(choose.currentData())} "
                    f"will use {anchor['name']} (UID {anchor['uid']}, type {anchor['type']}) "
                    'as a position anchor. The ID−4 species reference is an unverified '
                    'hypothesis. The original habitat and resident registry stay unchanged. '
                    'This may produce no Pokémon, a different Pokémon, or be ignored.')
            return
        if method == 'existing' and key is not None:
            h = next((h for h in known_habs if h['uid'] == key), None)
            if h:
                hinfo.setText(f'Type {h["type"]} | UID {h["uid"]} | X Y Z: {h["home"]}. '
                              'The existing habitat record will not be changed.\n'
                              + species_spawn_notice(choose.currentData()))
        elif method in ('new', 'spawn', 'event', 'event_items') and key is not None:
            r = next((r for r in all_recipes or [] if str(r['dex']) == key), None)
            if r:
                needs = ', '.join(f'{p["count"]}× {p["label"]}' for p in r['parts'] if p['kind'] != 'note')
                notes = '; '.join(p.get('note','') for p in r['parts'] if p['kind'] == 'note')
                if mode.currentData() == 'event':
                    tail = ('EVENT HABITAT: Click a valid location on the Island Map after this dialog. '
                            'No event flags, time-limited triggers or NPC spawning are modified.')
                elif mode.currentData() == 'event_items':
                    tail = ('EVENT MATERIALS: Missing items will be placed in the bag. '
                            'This does not build a habitat, complete quests or spawn NPCs.')
                elif mode.currentData() == 'spawn':
                    tail = ('EXPERIMENT ID−4: An encounter record is written for testing only. '
                            'Its effect is not validated on all supported island layouts. '
                            'This mode is disabled for special Pokémon.')
                else:
                    tail = species_spawn_notice(choose.currentData(), r)
                prefix = ('Prepare items: ' if method == 'event_items' else 'Automatically builds: ')
                how = ('. You may then build the event habitat normally.\n' if method == 'event_items'
                       else '. Then choose a position on Island Map; press R to rotate.\n')
                hinfo.setText(prefix + needs + ('. Conditions: ' + notes if notes else '') + how + tail)

    choose.currentIndexChanged.connect(lambda *_: (update_info(), populate_habs()))
    query.textChanged.connect(populate)
    mode.currentIndexChanged.connect(populate_habs)
    area_box.currentIndexChanged.connect(populate_habs)
    hab.currentIndexChanged.connect(update_hinfo)
    manual_hab.toggled.connect(populate_habs)
    event_resident.toggled.connect(populate_habs)
    help_modes.clicked.connect(lambda: QMessageBox.information(
        dlg, 'Recommended editor settings by Pokémon category',
        species_settings_reference()))
    populate()
    selected = page.selected()
    if selected_index is not None or len(selected) == 1:
        find = choose.findData(selected_index if selected_index is not None else selected[0])
        if find >= 0: choose.setCurrentIndex(find)
    populate_habs()
    if dlg.exec() != QDialog.Accepted:
        return
    idx, area = choose.currentData(), area_box.currentData()
    method, choice = mode.currentData(), hab.currentData()
    if idx is None or area is None:
        return QMessageBox.warning(page, 'Missing selection', 'Select a Pokémon and an island.')
    if method not in ('none', 'unlink', 'remove') and choice is None:
        return QMessageBox.warning(page, 'Missing habitat', 'Select a habitat.')
    if method == 'remove':
        return remove_resident_ui(page, idx)
    if method == 'unlink':
        if not c.villager_present(idx):
            return QMessageBox.warning(page, 'Resident not found', 'No existing resident to unlink.')
        if not c.get_villager(idx)['home_type']:
            return QMessageBox.information(page, 'No home assigned', 'This resident has no assigned home.')
        msg = (f'Remove the home assignment for {ps.name_of(ps.VILLAGER_NAMES, idx, "Resident")}?\n\n'
               'The resident and physical habitat remain in the save.')
        if QMessageBox.question(page, 'Remove home', msg,
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            if app.do('Remove home assignment', lambda: unlink_home(c, idx)):
                page.fill()
        return
    when = met.dateTime().toPython()
    score = friend.value()
    register = dex.isChecked() and bool(dex_slots(idx))
    name = display_species_name(idx)
    valid = matching_recipes(name, all_recipes or recipes(), idx)
    special = is_special_pokemon(name, valid)
    manually_selected = manual_hab.isChecked() and method in ('new','existing','event','event_items')
    available_for_action = permitted_habitats_for_action(
        all_recipes or recipes(),
        all_recipes if (special and method in ('new', 'existing')) else valid,
        method, manually_selected)
    valid_types = {int(r['type']) for r in available_for_action}
    if method in ('new', 'spawn', 'event', 'event_items') and not (method == 'spawn' and special):
        chosen_recipe = next((r for r in all_recipes or [] if str(r['dex']) == str(choice)), None)
        if not chosen_recipe or int(chosen_recipe['type']) not in valid_types or \
                (method in ('event', 'event_items') and not is_event_recipe(chosen_recipe)):
            return QMessageBox.warning(page, 'Habitat unavailable',
                                       'This habitat is not supported for the selected action. '
                                       'Event modes require an E-series recipe. No changes were made.')
    if method == 'spawn':
        if idx <= 4:
            return QMessageBox.warning(page, 'Invalid encounter ID',
                                       'The ID−4 hypothesis is not applicable to this resident ID.')
        if habitat_key(name) in _EVENT_POKEMON and not special:
            return QMessageBox.warning(page, 'Event Pokémon',
                                       'The ID−4 hypothesis has not been validated for event Pokémon. '
                                       'Use the normal habitat-building mode.')
        if special:
            if not (isinstance(choice, tuple) and len(choice) == 2 and
                    choice[0] == 'special-anchor'):
                return QMessageBox.warning(page, 'Missing position anchor',
                                           'Select an existing habitat position anchor.')
            anchor = next((h for h in read_habitats(app, area)
                           if h['uid'] == choice[1]), None)
            if anchor is None:
                return QMessageBox.warning(page, 'Anchor missing',
                                           'Selected existing habitat no longer exists.')
        if area not in _sp_supported_stages(app):
            return QMessageBox.warning(page, 'Stage layout not verified',
                                       'The ID−4 experiment is only available for G00/B00.')
    if method == 'existing':
        selected_h = next((h for h in known_habs if h['uid'] == choice), None)
        if not selected_h or int(selected_h['type']) not in valid_types:
            return QMessageBox.warning(page, 'Missing habitat',
                'No suitable existing habitat was found for this Pokémon.')
        detail = f'Link existing habitat {selected_h["uid"]} in {ps.name_of(ps.AREA_NAMES, area, "Area")} to this resident.'
        occupiers = [i for i in c.villagers() if i != idx and
                     c.get_villager(i)['home_type'] and
                     c.get_villager(i)['home_area'] == area and
                     c.get_villager(i)['home_uid'] == selected_h['uid']]
        if occupiers:
            detail += '\nWarning: this habitat is already occupied.'
    elif method == 'event':
        detail = ('Build the selected E-series event habitat directly on the map. '
                  'This does NOT enable event schedules, complete quests, or force Pokémon spawns.')
        if event_resident.isChecked():
            detail += ' Also write a resident entry, which does not guarantee a visible NPC.'
    elif method == 'event_items':
        detail = ('Add missing event habitat materials to the bag and mark their catalog entries. '
                  'No habitat is built; no quest flags are changed.')
    elif method == 'spawn' and special:
        detail = ('EXPERIMENTAL ENCOUNTER / ID−4: Write one hypothetical encounter entry using '
                  f"existing habitat UID {anchor['uid']} as position anchor. "
                  'Do not build any habitat, create a world NPC, or modify quest flags. '
                  'Actual species appearance is NOT confirmed.')
    elif method in ('new', 'spawn'):
        detail = ('New habitat and experimental ID−4 encounter record; NO resident registration.'
                  if method == 'spawn' else
                  'Build a habitat on the map and assign it as a home. This does not force a first encounter.')
    else:
        detail = 'Resident record only, NO spawn. Special recruitment may require additional game flags.'
    if manually_selected:
        proceed = QMessageBox.warning(page, 'Manually selected habitat',
                     'This habitat is not verified for the selected Pokémon. '
                     'A home assignment does NOT guarantee a Pokémon spawn. Continue?',
                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if proceed != QMessageBox.Yes:
            return
    resp = QMessageBox.warning(page, 'Confirm resident / habitat changes',
        f'{name} (ID {idx})?\n\n{detail}\n\n' +
        species_spawn_notice(idx) + '\n\n' +
        'This is an experimental operation; visible NPC creation is not verified. '
        'Create a backup and close the emulator before saving.',
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if resp != QMessageBox.Yes:
        return
    if method == 'event_items':
        try:
            backup = backup_common_save(app.save)
        except Exception as exc:
            return QMessageBox.critical(page, 'Backup failed', str(exc))
        result = {}
        if app.do(f'{name}: prepare event materials', lambda: result.update(
                event_content_bypass(c, idx, chosen_recipe, when, score,
                                     add_resident=False, register_dex=False,
                                     allow_unverified=manually_selected))):
            page.fill()
            QMessageBox.information(page, 'Event materials prepared',
                f'Missing materials for {chosen_recipe["name"]} have been placed in the bag.\n'
                'No event or quest completion flags were changed.\n'
                'Press Ctrl+S to save; use Build event habitat to place its items.\n\nBackup: ' + backup)
        return
    if method == 'spawn' and special:
        mp = app.pages.get('Island Map')
        if not mp:
            return app.toast('Island Map unavailable.', 'err')
        try:
            backup = _sp_backup(app.save, app.save.stage_files().get(area))
        except Exception as exc:
            return QMessageBox.critical(page, 'Backup failed', 'No changes: ' + str(exc))
        mp.special_test_pending = dict(
            area=area, index=idx, uid=int(anchor['uid']),
            habitat_type=int(anchor['type']), backup=backup)
        app.show_page('Island Map')
        mp.choose(area)
        _sp_run_special_pending(mp)  # Also supports an already cached island.
        return
    if method in ('new', 'spawn', 'event'):
        mp = app.pages.get('Island Map')
        if not mp:
            return app.toast('Island Map unavailable', 'err')
        stage = app.save.stage_files().get(area)
        try:
            backup = _sp_backup(app.save, stage)
        except Exception as exc:
            return QMessageBox.critical(page, 'Backup failed',
                                        'No changes were made: ' + str(exc))
        pending = dict(index=idx, area=area, recipe=str(choice),
                       when=when, friendship=score, dex=register, activated=False,
                       event_mode=(method == 'event'),
                       add_resident=(method != 'event' or event_resident.isChecked()))
        if method == 'spawn':
            mp.spawn_pending = pending
            mp.resident_pending = None
        else:
            mp.resident_pending = pending
            mp.spawn_pending = None
        app.show_page('Island Map')
        mp.choose(area)
        activate_pending_map(mp)
        app.toast(f'{name}: click a free location on the island map to build the habitat.', 'info')
        QMessageBox.information(page, 'Backup created',
            'A backup was created before editing:\n' + backup +
            '\n\nNow place the habitat and press Ctrl+S to save.')
        return
    home = None
    typ = None
    if method == 'existing':
        home = (area, selected_h['uid'], selected_h['home'])
        typ = selected_h['type']
    ok = app.do(f'{name}: add resident + home',
                lambda: edit_resident(c, idx, score, when, register, home, typ))
    if ok:
        page.fill()
        try: page.select_resident(idx)
        except Exception: pass


def activate_pending_map(mp):
    """When the stage loads asynchronously, select a recipe and arm the click-to-build tool."""
    pending = (getattr(mp, 'spawn_pending', None) or
               getattr(mp, 'resident_pending', None))
    if not pending or pending['activated'] or mp.area != pending['area'] or not mp.view_data:
        return
    mp.set_tool('habitat')
    mp.recipe_search.setText('')
    mp.fill_recipes()
    from PySide6.QtCore import Qt
    chosen = None
    for j in range(mp.recipe_list.count()):
        it = mp.recipe_list.item(j)
        if str(it.data(Qt.UserRole)) == pending['recipe']:
            chosen = it
            break
    if chosen is None:
        mp.app.toast('Selected habitat recipe is missing.', 'err')
        return
    mp.recipe_list.setCurrentItem(chosen)
    mp.recipe_chosen(chosen)
    pending['activated'] = True
    mp.app.toast('Habitat ready: click a valid spot on map (R=rotate).', 'info')


def record_habitat(isl, recipe, parts, liquids):
    """Experimental: register a newly stamped habitat in the stage table.

    Mirrors observed row layout (9 * int16 coordinates, u32 type, 4 ancillary bytes).
    Unknown ancillary bytes use zero, as for multiple natural habitats. The game may
    recompute/overwrite this registry on load.
    """
    typ = int(recipe['type'])
    if not 0 < typ < 4096:
        raise ValueError('Unknown habitat type')
    row = None
    for j in range(pi.HABITAT_CAP):
        off = pi.HABITATS + j * pi.HABITAT_SIZE
        if struct.unpack_from('<I', isl.d, off+18)[0] == 0:
            row = j
            break
    if row is None:
        raise ValueError('No free habitat slots')
    occupied = set()
    for var, x, y, z, direction in parts:
        for cx, cy, cz, *_ in isl._cells_of(var, x, y, z, direction):
            occupied.add((int(cx), int(cy), int(cz)))
    for x,z,bid in liquids:
        col = isl.column(x,z)
        y = col[2]+1 if col else 0
        occupied.add((int(x), int(y), int(z)))
    if not occupied:
        raise ValueError('The recipe has no buildable parts')
    xx, yy, zz = zip(*occupied)
    mn, mx = (min(xx), min(yy), min(zz)), (max(xx), max(yy), max(zz))
    # The first real-home coordinate in several saves lies inside the bbox and
    # is at ground level, often near the middle. Keep a plausible center cell.
    hx = (mn[0]+mx[0])//2
    hz = (mn[2]+mx[2])//2
    col = isl.column(hx,hz)
    hy = min(yy) if col is None else col[2]+1
    hy = min(max(hy, mn[1]), mx[1])
    home = (hx,hy,hz)
    if any(v < 0 or v >= 2048 for v in (mn[0],mx[0],mn[2],mx[2])) or not (0 <= mn[1] <= mx[1] < 128):
        raise ValueError('Habitat is out of stage bounds')
    packed = struct.pack('<9hI4s', *(mn+mx+home), typ, b'\0\0\0\0')
    isl._put(pi.HABITATS + row*pi.HABITAT_SIZE, packed)
    isl._read_habitats()
    return 101+row, home






# ============================================================
# SPECIES SPAWN – EXPERIMENTAL, OFFLINE SAVE PROTOTYPE
# The tuple of IDs is a testable hypothesis, NOT confirmed game semantics.
# No debugger, no RAM hooks, no forced Pokédex/resident creation.
# This intentionally operates only on the verified G00/STGDAT01 stage.
# ============================================================
_SP_EVENT_START = 0x15CCA6
_SP_EVENT_STRIDE = 32
_SP_EVENT_SLOTS = 20


def _sp_supported_stages(app):
    """Restrict binary 32-byte event experiment to G00 and B00 stage schema.

    This is still research: sharing decompressed size and blank event slots
    does NOT establish identical spawn logic on Palette Town (B00).
    """
    result = {}
    if not app.save:
        return result
    for area, name in app.save.stage_files().items():
        path = os.path.normpath(str(name)).replace('\\', '/').upper()
        if path.endswith('/G00/STGDAT01.BIN') or path.endswith('/B00/STGDAT01.BIN'):
            result[area] = name
    return result


def _sp_has_free_event(isl):
    d = isl.d
    if len(d) != pi.DATA_SIZE or len(d) < _SP_EVENT_START + _SP_EVENT_SLOTS * 32:
        return False
    # Validate that every occupied row looks like the observed event structure;
    # reject unknown binary layouts rather than blindly overwriting anything.
    free = False
    for i in range(_SP_EVENT_SLOTS):
        row = d[_SP_EVENT_START+i*32:_SP_EVENT_START+(i+1)*32]
        if row == bytes(32):
            free = True
            continue
        try:
            uid, typ, ref, wx, wy, wz = struct.unpack('<IHH8x3f4x', row)
            if not (101 <= uid <= 1024 and 0 < typ < 4096 and
                    0 <= ref < 4096 and all(-200000 <= v <= 200000 for v in (wx,wy,wz)) and
                    row[8:16] == bytes(8) and row[28:32] == bytes(4)):
                return False
        except Exception:
            return False
    return free


def _sp_event(isl, resident_id, uid, habitat_type):
    """Stage event: known 32-byte layout + unverified species reference ID−4.

    Every changed byte belongs to one previously observed empty event slot.
    New habitat registry must have been written with record_habitat() first.
    Mutation uses the editor's island journal: only committed on Ctrl+S.
    """
    if not isinstance(resident_id, int) or not (4 < resident_id < ps.VIL_COUNT):
        raise ValueError('Invalid resident ID for ID−4 experiment.')
    if not (0 < habitat_type <= 0xffff and 101 <= uid <= 1024):
        raise ValueError('Invalid habitat type or habitat index.')
    if len(isl.d) != pi.DATA_SIZE:
        raise ValueError('Unsupported stage data layout; experiment aborted.')
    idx = uid-101
    row = pi.HABITATS + idx*pi.HABITAT_SIZE
    vals = struct.unpack_from('<9hI', isl.d, row)
    if vals[9] != habitat_type:
        raise ValueError('Habitat record does not match the selected type.')
    if not (0 <= vals[0] <= vals[3] < 2048 and 0 <= vals[1] <= vals[4] < 128
            and 0 <= vals[2] <= vals[5] < 2048):
        raise ValueError('Invalid habitat coordinates; no encounter data was written.')
    # In the verified original Oddish record, world position matches bbox min.
    x, y, z = vals[:3]
    # observed world coordinate formula: (gridX - 1023.5)*100, gridY*100.
    wx, wy, wz = (x-1023.5)*100.0, y*100.0, (z-1023.5)*100.0
    # Unverified assumption: the u16 'reference' is the spawn index.
    guessed_ref = resident_id - 4
    entry = struct.pack('<IHH8x3f4x', uid, habitat_type, guessed_ref, wx, wy, wz)
    if len(entry) != 32:
        raise AssertionError('Unexpected encounter record size.')
    for slot in range(_SP_EVENT_SLOTS):
        offset = _SP_EVENT_START + slot * _SP_EVENT_STRIDE
        if isl.d[offset:offset+_SP_EVENT_STRIDE] == bytes(_SP_EVENT_STRIDE):
            isl._put(offset, entry)
            return slot, guessed_ref, (x,y,z)
    raise ValueError('All supported encounter slots are occupied. Nothing was overwritten.')


def _sp_run_special_pending(mp):
    """Experimental ID−4 on an existing island habitat; zero recipe/home changes.

    Called when the selected map is available. Never write if the island or
    layout is unsupported; the hypothesis must not be extrapolated blindly.
    The normal MapPage.commit journal enables Undo and Ctrl+S.
    """
    pending = getattr(mp, 'special_test_pending', None)
    if not pending or mp.area != pending['area']:
        return
    isl = mp.isl()
    if isl is None:
        return  # async map load will call this again
    mp.special_test_pending = None
    try:
        if pending['area'] not in _sp_supported_stages(mp.app):
            raise ValueError('Stage layout is not eligible for the ID−4 experiment.')
        if not _sp_has_free_event(isl):
            raise ValueError('No free compatible 32-byte encounter slot. Nothing was changed.')
        slot, ref, pos = _sp_event(
            isl, int(pending['index']), int(pending['uid']),
            int(pending['habitat_type']))
        mp.commit('EXPERIMENT ID−4 special: ' +
                  display_species_name(pending['index']))
    except Exception as exc:
        isl.rollback()
        mp.app.toast('Special encounter NOT applied: ' + str(exc), 'err')
        return
    mp.app.toast(
        f'Experimental entry staged: event slot {slot}, reference {ref}, '
        f'anchor UID {pending["uid"]}. Nothing is proven to spawn. '
        'Press Ctrl+S only on a separate save copy; you can Undo first. '
        'Original ZIP backup: ' + pending['backup'], 'info')


def _sp_backup(save, stage_path):
    """Back up the selected island and the entire opened save before editing.

    Ordinary habitat editing supports all G00/STGDAT##.BIN island files.
    The separate experimental encounter operation remains restricted by
    _sp_supported_stages(); backing up a file does not validate its event layout.
    """
    from pathlib import Path
    import zipfile
    if stage_path is None:
        raise ValueError('No stage data file was found for the selected island.')
    root = Path(save.folder).resolve()
    stage = Path(stage_path).resolve()
    if not re.fullmatch(r'STGDAT[0-9]{2}\.BIN', stage.name, re.IGNORECASE):
        raise ValueError('The selected island does not have a valid STGDAT##.BIN file.')
    if stage.parent.parent != root or stage.parent.name.upper() != 'G00':
        raise ValueError('The selected island stage is outside the opened save folder (G00).')
    if not (root / 'G00' / 'CMNDAT.BIN').is_file():
        raise ValueError('The opened save is missing G00/CMNDAT.BIN.')
    if not stage.is_file():
        raise ValueError('The selected island stage file does not exist.')
    # Only accept a stage that the save loader itself detected. This also blocks
    # stray paths and incorrectly selected folders without guessing island IDs.
    known = {Path(path).resolve() for path in save.stage_files().values()}
    if stage not in known:
        raise ValueError('The selected island stage is not listed in this save.')
    candidates = sorted(p for p in root.rglob('*') if p.is_file())
    if not candidates or len(candidates) > 80 or sum(p.stat().st_size for p in candidates) > 500 * 1024 * 1024:
        raise ValueError('Unexpected save size or file count; create a manual backup first.')
    if any(not p.resolve().is_relative_to(root) for p in candidates):
        raise ValueError('The save contains a file pointing outside its directory.')
    target = Path.home() / 'PokopiaEditor_Backups'
    target.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    out = target / ('Pokopia_before_island_edit_' + stamp + '.zip')
    try:
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
            for item in candidates:
                z.write(item, item.relative_to(root))
        with zipfile.ZipFile(out) as z:
            if z.testzip() is not None:
                raise ValueError('Backup archive verification failed.')
    except Exception:
        out.unlink(missing_ok=True)
        raise
    return str(out)


def _rsh_open_studio(page, selected_index=None):
    """Never swallow an exception when opening the Resident/Spawn dialog."""
    from PySide6.QtWidgets import QMessageBox
    try:
        return add_dialog(page, selected_index)
    except Exception:
        details = traceback.format_exc()
        try:
            logfile = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'),
                                   'Pokopia_ResidentHabitat_dialog_error.txt')
            with open(logfile, 'w', encoding='utf-8') as handle:
                handle.write(details)
            more = '\n\nError log: ' + logfile
        except OSError:
            more = ''
        QMessageBox.critical(page, 'Pokémon / Habitat / Spawn',
                             'The Resident Studio could not be opened. No save data was changed.\n\n'
                             + details.splitlines()[-1] + more)


def patch_all():
    # Process and save detection without renaming lichii.exe to yuzu.exe.
    import pokopia_extras as px
    px.EMULATORS = tuple(dict.fromkeys(tuple(px.EMULATORS) + ('lichii',)))
    px.YUZU_FAMILY = tuple(dict.fromkeys(tuple(px.YUZU_FAMILY) + ('lichii',)))
    from gui import widgets as W
    from gui import theme as T
    from gui.pages.residents import ResidentsPage
    from gui.pages.map import MapPage

    old_build = ResidentsPage.build
    def patch_build(self):
        old_build(self)
        left = self.layout().itemAt(0).widget()
        top = left.body.itemAt(0).layout()
        top.insertWidget(2, W.button('Pokémon · Habitat · Spawn', T.G['people'],
                                     lambda: _rsh_open_studio(self), accent=True))
        self.home_edit_button = W.button('Assign / change home', T.G['home'],
            lambda: _rsh_open_studio(self, self.selected()[0]) if len(self.selected()) == 1 else None)
        self.home_edit_button.setEnabled(False)
        self.detail.body.addWidget(self.home_edit_button)
        self.home_unlink_button = W.button('Remove home assignment', T.G['home'],
                                          lambda: direct_unlink(self))
        self.home_unlink_button.setEnabled(False)
        self.detail.body.addWidget(self.home_unlink_button)
        self.resident_remove_button = W.button('Remove resident from save', T.G['people'],
                                                lambda: remove_resident_ui(self))
        self.resident_remove_button.setEnabled(False)
        self.detail.body.addWidget(self.resident_remove_button)
    ResidentsPage.build = patch_build

    old_resident_show = ResidentsPage.show
    def patch_resident_show(self):
        old_resident_show(self)
        on = bool(self.app.save and len(self.selected()) == 1)
        if hasattr(self, 'home_edit_button'):
            self.home_edit_button.setEnabled(on)
        if hasattr(self, 'home_unlink_button'):
            self.home_unlink_button.setEnabled(on and
                bool(self.app.save.common.get_villager(self.selected()[0])['home_type']))
        if hasattr(self, 'resident_remove_button'):
            self.resident_remove_button.setEnabled(on and len(self.selected()) == 1)
    ResidentsPage.show = patch_resident_show

    old_show_island = MapPage.show_island
    def patch_show_island(self, view):
        old_show_island(self, view)
        if getattr(self, 'special_test_pending', None):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: _sp_run_special_pending(self))
        if getattr(self, 'resident_pending', None) or getattr(self, 'spawn_pending', None):
            # Defer tool changes until after the map has completed its normal setup.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: activate_pending_map(self))
    MapPage.show_island = patch_show_island

    old_stamp_here = MapPage.stamp_here
    def patch_stamp_here(self, wx, wz):
        sp = getattr(self, 'spawn_pending', None)
        pending = sp or getattr(self, 'resident_pending', None)
        if not pending or self.area != pending['area']:
            return old_stamp_here(self, wx, wz)
        ok, parts = self.stamp_parts(wx, wz)
        if not ok or (not parts and not self.stamp_liquids):
            return old_stamp_here(self, wx, wz)
        recipe = self.recipe
        if not recipe or str(recipe['dex']) != pending['recipe']:
            return self.app.toast('The selected habitat does not match the requested recipe. Re-select the habitat in the RSH dialog.', 'err')
        isl = self.isl()
        if not any(struct.unpack_from('<I', isl.d, pi.HABITATS+j*pi.HABITAT_SIZE+18)[0] == 0
                   for j in range(pi.HABITAT_CAP)):
            return self.app.toast('No free habitat slots.', 'err')
        if sp and not _sp_has_free_event(isl):
            return self.app.toast('No free verified encounter slot; nothing was changed.', 'err')
        snapshot = (recipe, list(parts), list(self.stamp_liquids), dict(pending))
        if sp:
            self._spawn_stamp = snapshot
        else:
            self._resident_stamp = snapshot
        try:
            return old_stamp_here(self, wx, wz)
        finally:
            self._spawn_stamp = None
            self._resident_stamp = None
    MapPage.stamp_here = patch_stamp_here

    old_commit = MapPage.commit
    def patch_commit(self, label):
        spawn_ready = getattr(self, '_spawn_stamp', None)
        ready = spawn_ready or getattr(self, '_resident_stamp', None)
        if not (ready and str(label).startswith('Built a habitat:')):
            return old_commit(self, label)
        recipe, parts, liquids, pending = ready
        isl = self.isl()
        try:
            uid, xyz = record_habitat(isl, recipe, parts, liquids)
            if spawn_ready:
                if self.area not in _sp_supported_stages(self.app):
                    raise ValueError('The encounter experiment is not supported on this island.')
                event_slot, guessed_id, pos = _sp_event(
                    isl, int(pending['index']), uid, int(recipe['type']))
        except Exception as ex:
            isl.rollback()
            self.app.toast('Habitat or encounter could not be placed: ' + str(ex), 'err')
            return
        result = old_commit(self, label)
        if spawn_ready:
            self.spawn_pending = None
            try: self.set_tool('select')
            except Exception: pass
            if self.habitats_item:
                self.habitats_item.update()
            self.app.toast(
                f'Spawn preview staged (not yet saved to disk): UID {uid}, '
                f'experimental species field {guessed_id}, event slot {event_slot}. '
                'Press Ctrl+S and reload the game. Species is not guaranteed.', 'ok')
            return result
        try:
            c = self.app.save.common
            res_name = display_species_name(pending['index'])
            if pending.get('event_mode') and not pending.get('add_resident'):
                self.resident_pending = None
                try: self.set_tool('select')
                except Exception: pass
                if self.habitats_item:
                    self.habitats_item.update()
                self.app.toast(f'{res_name}: event habitat built (UID {uid}). '
                               'No quest flag or NPC encounter changed. Save with Ctrl+S.', 'ok')
                return result
            success = self.app.do(f'{res_name}: register + habitat {uid}',
                lambda: edit_resident(c, pending['index'], pending['friendship'],
                                      pending['when'], pending['dex'],
                                      (pending['area'], uid, xyz), recipe['type']))
            if success:
                self.resident_pending = None
                self.app.toast(f'{res_name}: habitat UID {uid} placed and resident registered. Save with Ctrl+S.', 'ok')
                self.set_tool('select')
                if self.habitats_item:
                    self.habitats_item.update()
            else:
                self.app.toast('Map built, but resident registration failed. Undo the habitat if needed.', 'err')
        except Exception as ex:
            self.app.toast('Map built, but resident registration failed: '+str(ex), 'err')
        return result
    MapPage.commit = patch_commit


try:
    patch_all()
except Exception:
    _PATCH_ERROR = traceback.format_exc()
    try:
        # Keep the unmodified original app launchable even if this integration fails.
        loc = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'),
                           'Pokopia_ResidentHabitat_patch_error.txt')
        with open(loc, 'w', encoding='utf-8') as fh:
            fh.write(_PATCH_ERROR)
    except OSError:
        pass

if __name__ == '__main__':
    main()
