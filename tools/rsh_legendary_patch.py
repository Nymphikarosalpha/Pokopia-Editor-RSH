#!/usr/bin/env python3
"""Exact-source patch for Pokopia Editor RSH v0.2.1: special encounter experiments.

The ID−4 association is a hypothesis, not a verified legendary spawn mechanism.
Use only on a disposable save. This module patches source, never a shipped EXE.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys
import subprocess

BASE_BLOB_SHA = '87f983da4a95764f047c8f5f983025c124689c68'
SOURCE_NAME = 'pokopia_gui_fork.py'


def github_blob_sha(content: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(content)).encode('ascii') + b'\x00' + content).hexdigest()


def replace_exact(source: str, before: str, after: str, label: str) -> str:
    found = source.count(before)
    if found != 1:
        raise ValueError(f'Patch nicht angewendet: {label} (erwartet 1 Treffer, gefunden {found}). '
                         'Dein Editor hat vermutlich einen anderen Quellcode-Stand.')
    return source.replace(before, after, 1)


def rewrite(source: str) -> str:
    # Make the existing special-classification work for the Jirachi event too;
    # never treat an E-series recipe as proof of its encounter gate.
    source = replace_exact(source,
        "    'articuno', 'zapdos', 'moltres', 'kyogre', 'volcanion'\n})",
        "    'articuno', 'zapdos', 'moltres', 'kyogre', 'volcanion', 'jirachi'\n})",
        'Spezial-Pokémon-Liste')

    # Add a transparent in-editor guide: recommendations are driven by the
    # existing resident-ID catalog and known event markers, not elemental types.
    source = replace_exact(source,
        "def add_dialog(page, selected_index=None):\n",
        'def species_mode_recommendation(idx, all_recipes, area, eligible_areas):\n    """Read-only guide. Never infer a species\' encounter from a habitat anchor."""\n    if idx is None:\n        return \'Select a Pokémon to see the recommended action.\'\n    name = display_species_name(idx)\n    key = habitat_key(name)\n    matched = matching_recipes(name, all_recipes, idx)\n    event_matches = [r for r in (matched or []) if is_event_recipe(r)]\n    if is_special_pokemon(name):\n        kind = (\'SPECIAL / EVENT (unique encounter)\' if key in _EVENT_POKEMON\n                else \'LEGENDARY / MYTHICAL (unique encounter)\')\n        test = (\'ID−4 is available for a disposable test save only if an existing \'\n                \'anchor is on this island.\' if area in eligible_areas else\n                \'ID−4 is disabled on this island layout; select an eligible STGDAT01 island.\')\n        event_note = (\' A known E-series habitat may be built in Event habitat mode, \'\n                      \'but that does not complete the event.\' if event_matches else\n                      \' No verified event habitat is assigned to this Pokémon.\')\n        return (f\'{kind} — {name}. Recommended for real encounter: original story/event \'\n                \'conditions, not a guessed habitat. For save editing: \'\n                \'Register resident without habitat = registry ONLY. \'\n                + test + \' No spawn or event completion is confirmed.\' + event_note)\n    if key in _EVENT_POKEMON:\n        if event_matches:\n            return (f\'EVENT POKÉMON — {name}. Recommended: Build event habitat on the map \'\n                    \'(E-series recipe). "Prepare event materials in bag only" adds materials, \'\n                    \'but does not build or unlock the event. The game may still require \'\n                    \'separate event conditions. ID−4 is not validated here.\')\n        return (f\'EVENT POKÉMON — {name}. No verified E-series habitat mapping is \'\n                \'available. Do not select a random event recipe for spawning. \'\n                \'Register without a habitat for registry-only testing, or use a manual \'\n                \'habitat override with no encounter guarantee.\')\n    if matched:\n        return (f\'NORMAL / HABITAT-BASED — {name}. Recommended: "Build habitat + \'\n                \'register resident" to place a mapped habitat, or "Assign an existing \'\n                \'habitat" if one already exists on the island. Neither guarantees an \'\n                \'immediate visible encounter. ID−4 is an unverified alternative test.\')\n    if matched == []:\n        return (f\'NO BUILDABLE HABITAT MAPPED — {name}. Recommended: Register resident \'\n                \'without a habitat for registry-only experiments. Do not assume any \'\n                \'manual habitat will create this species.\')\n    return (f\'UNKNOWN HABITAT MAPPING — {name}. Recommended: verify the resident ID \'\n            \'and habitat data first. Manual habitat selection is an unverified \'\n            \'housing/building experiment, not a proven spawn. Registration without \'\n            \'a habitat only updates the save registry.\')\n\n\ndef species_settings_reference():\n    """Full workflow legend shown by the dialog\'s Help button."""\n    return (\'NORMAL (mapped habitat): Build habitat + register resident; \'\n            \'or assign an existing compatible habitat. Not an instant spawn.\\n\\n\'\n            \'EVENT (E-series recipe): Build event habitat on the map. \'\n            \'Prepare event materials is inventory-only; neither completes quests.\\n\\n\'\n            \'LEGENDARY / MYTHICAL (Mew, Suicune, Mewtwo, etc.): \'\n            \'Do not invent an event habitat. Real encounters may require story \'\n            \'or unique conditions. Register without habitat is registry-only. \'\n            \'ID−4 is a separate unverified encounter experiment: existing habitat \'\n            \'is a position anchor, not a Pokémon-specific spawn recipe.\\n\\n\'\n            \'UNKNOWN / NO MAPPING: Avoid random habitat IDs. Manual choices are \'\n            \'explicitly unverified.\\n\\n\'\n            \'IMPORTANT: Fire/Water/Grass/etc. elemental types do NOT determine \'\n            \'the editor mode. The category is based on the encounter mechanism \'\n            \'and resident-ID-to-habitat mapping.\\n\\n\'\n            \'ID−4 limitations: supported STGDAT01 stage layout, free compatible \'\n            \'32-byte event slot, and a pre-existing anchor for specials. \'\n            \'No successful in-game special spawn has been verified. Use a \'\n            \'disposable save, close the emulator, and keep the ZIP backup.\')\n\n\n',
        'Automatische Modus-Empfehlungen nach Pokémon-Kategorie')

    source = replace_exact(source,
        "    hinfo = QLabel('')\n    hinfo.setWordWrap(True)\n",
        "    hinfo = QLabel('')\n    hinfo.setWordWrap(True)\n"
        "    recommend = QLabel('Select a Pokémon for recommendations.')\n"
        "    recommend.setWordWrap(True)\n"
        "    recommend.setStyleSheet('padding: 8px; border: 1px solid #777; border-radius: 5px;')\n"
        "    help_modes = QPushButton('Which settings for which Pokémon?')\n",
        'Sichtbares Empfehlungsfeld und Hilfebutton')

    source = replace_exact(source,
        "    form.addRow('Status:', info)\n    form.addRow('Habitat details:', hinfo)\n",
        "    form.addRow('Status:', info)\n"
        "    form.addRow('Recommended settings:', recommend)\n"
        "    form.addRow('', help_modes)\n"
        "    form.addRow('Habitat details:', hinfo)\n",
        'Empfehlungen direkt im Dialog anzeigen')

    source = replace_exact(source,
        "    dlg.resize(630, 480)",
        "    dlg.resize(730, 590)",
        'Mehr Platz für die Empfehlungen')

    source = replace_exact(source,
        "    def populate_habs(*_):\n        nonlocal all_recipes, known_habs, loading_error\n",
        "    def populate_habs(*_):\n"
        "        nonlocal all_recipes, known_habs, loading_error\n"
        "        try:\n"
        "            recommend.setText(species_mode_recommendation(\n"
        "                choose.currentData(), all_recipes if all_recipes is not None else recipes(),\n"
        "                area_box.currentData(), _sp_supported_stages(app)))\n"
        "        except Exception as ex:\n"
        "            recommend.setText('Recommendation unavailable: ' + str(ex))\n",
        'Empfehlung automatisch bei Pokémon- und Inselwechsel aktualisieren')

    source = replace_exact(source,
        "    event_resident.toggled.connect(populate_habs)\n    populate()",
        "    event_resident.toggled.connect(populate_habs)\n"
        "    help_modes.clicked.connect(lambda: QMessageBox.information(\n"
        "        dlg, 'Recommended editor settings by Pokémon category',\n"
        "        species_settings_reference()))\n"
        "    populate()",
        'Hilfefenster mit vollständiger Modus-Übersicht')

    source = replace_exact(source,
        "mode.addItem('Experimental encounter record (ID−4)', 'spawn')",
        "mode.addItem('Experimental encounter (ID−4; automatic special detection)', 'spawn')",
        'Testmodus-Beschriftung')

    source = replace_exact(source,
        "QSpinBox, QDateTimeEdit, QCheckBox, QLabel, QMessageBox, QVBoxLayout)",
        "QSpinBox, QDateTimeEdit, QCheckBox, QLabel, QMessageBox, QVBoxLayout, QPushButton)",
        'Hilfebutton importieren')

    source = replace_exact(source,
        "if habitat_key(name) in _EVENT_POKEMON:\n                    hab.setEnabled(False)",
        "if habitat_key(name) in _EVENT_POKEMON and not special:\n                    hab.setEnabled(False)",
        'Event-Sperre in UI')

    source = replace_exact(source,
        """                if special or matched == [] or idx <= 4:
                    hab.setEnabled(False)
                    hinfo.setText(name+': has no confirmed normal habitat spawn. '
                                  'Mew, Suicune and other special Pokémon will not appear through this mode. '
                                  'Use resident registration without a habitat, or assign a home to an existing resident.')
                    return
""",
        """                if special:
                    # Do NOT invent a Mew habitat. Use an existing habitat entry
                    # solely as a position/UID anchor for the unverified ID−4 row.
                    known_habs = read_habitats(app, area)
                    for anchor in known_habs:
                        if (101 <= int(anchor['uid']) <= 1024 and
                                0 < int(anchor['type']) < 4096 and
                                len(anchor['home']) == 3):
                            hab.addItem(
                                f\"Anchor: {anchor['name']}  ·  UID {anchor['uid']} (existing)\",
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
                    hinfo.setText(name+': no verified normal habitat and no supported ID−4 test. '
                                  'The editor will not guess a spawn recipe.')
                    return
""",
        'Spezial-Pokémon: Ankerliste statt grauer Auswahl')

    source = replace_exact(source,
        """        if method == 'existing' and key is not None:
""",
        """        if method == 'spawn' and isinstance(key, tuple) and key[0] == 'special-anchor':
            anchor = next((h for h in known_habs if h['uid'] == key[1]), None)
            if anchor:
                hinfo.setText(
                    f\"EXPERIMENT ONLY: {display_species_name(choose.currentData())} "
                    f\"will use {anchor['name']} (UID {anchor['uid']}, type {anchor['type']}) "
                    'as a position anchor. The ID−4 species reference is an unverified '
                    'hypothesis. The original habitat and resident registry stay unchanged. '
                    'This may produce no Pokémon, a different Pokémon, or be ignored.')
            return
        if method == 'existing' and key is not None:
""",
        'Detailinfo für ausgewählten Anker')

    source = replace_exact(source,
        """    if method in ('new', 'spawn', 'event', 'event_items'):
        chosen_recipe = next((r for r in all_recipes or [] if str(r['dex']) == str(choice)), None)
""",
        """    if method in ('new', 'spawn', 'event', 'event_items') and not (method == 'spawn' and special):
        chosen_recipe = next((r for r in all_recipes or [] if str(r['dex']) == str(choice)), None)
""",
        'Keine Rezeptpflicht für Spezial-ID−4')

    source = replace_exact(source,
        """        if habitat_key(name) in _EVENT_POKEMON:
            return QMessageBox.warning(page, 'Event Pokémon',
""",
        """        if habitat_key(name) in _EVENT_POKEMON and not special:
            return QMessageBox.warning(page, 'Event Pokémon',
""",
        'Event-ID−4 nicht generell sperren')

    source = replace_exact(source,
        """        if special:
            return QMessageBox.warning(page, 'Special encounter',
                                       'Mew, Suicune and other special Pokémon do not appear '
                                       'through a standard habitat experiment.')
""",
        """        if special:
            if not (isinstance(choice, tuple) and len(choice) == 2 and
                    choice[0] == 'special-anchor'):
                return QMessageBox.warning(page, 'Missing test anchor',
                                           'Select an existing habitat position anchor.')
            anchor = next((h for h in read_habitats(app, area)
                           if h['uid'] == choice[1]), None)
            if anchor is None:
                return QMessageBox.warning(page, 'Anchor missing',
                                           'Selected existing habitat no longer exists.')
""",
        'Spezial-ID−4 Bestätigung')

    source = replace_exact(source,
        """    elif method in ('new', 'spawn'):
        detail = ('New habitat and experimental ID−4 encounter record; NO resident registration.'
""",
        """    elif method == 'spawn' and special:
        detail = ('SPECIAL TEST / ID−4: Write one hypothetical encounter entry using '
                  f\"existing habitat UID {anchor['uid']} as position anchor. \"
                  'Do not build any habitat, create a world NPC, or modify quest flags. '
                  'Actual species appearance is NOT confirmed.')
    elif method in ('new', 'spawn'):
        detail = ('New habitat and experimental ID−4 encounter record; NO resident registration.'
""",
        'Bestätigung für Spezialversuch')

    source = replace_exact(source,
        """    if method in ('new', 'spawn', 'event'):
        mp = app.pages.get('Island Map')
""",
        """    if method == 'spawn' and special:
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
""",
        'Eigenständiger Test ohne Habitat-Neubau')

    source = replace_exact(source,
        """    def patch_show_island(self, view):
        old_show_island(self, view)
        if getattr(self, 'resident_pending', None) or getattr(self, 'spawn_pending', None):
""",
        """    def patch_show_island(self, view):
        old_show_island(self, view)
        if getattr(self, 'special_test_pending', None):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: _sp_run_special_pending(self))
        if getattr(self, 'resident_pending', None) or getattr(self, 'spawn_pending', None):
""",
        'Asynchron geladene Insel für Spezialtest')

    source = replace_exact(source,
        """def _sp_backup(save, stage_path):
""",
        """def _sp_run_special_pending(mp):
    \"\"\"Experimental ID−4 on an existing island habitat; zero recipe/home changes.

    Called when the selected map is available. Never write if the island or
    layout is unsupported; the hypothesis must not be extrapolated blindly.
    The normal MapPage.commit journal enables Undo and Ctrl+S.
    \"\"\"
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
        'Press Ctrl+S only on a disposable test save; you can Undo first. '
        'Original ZIP backup: ' + pending['backup'], 'info')


def _sp_backup(save, stage_path):
""",
        'Testschreiber in bestehende Undo-/Save-Verwaltung')

    return source

