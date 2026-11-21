"""Offline regression checks for the streamlined RSH encounter dialog.

No emulator, game save, GUI toolkit or game binaries are used.
"""
import ast
import os
import re
import pathlib
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
EDITOR = ROOT / 'pokopia_gui_fork.py'


def candidate_function():
    source = ast.parse(EDITOR.read_text(encoding='utf8'))
    named = [n for n in source.body if isinstance(n, ast.FunctionDef)
             and n.name == '_sp_special_candidate_stages']
    assert len(named) == 1, 'Special candidate function is missing or duplicated'
    scope = {'os': os, 're': re}
    exec(compile(ast.Module(body=named, type_ignores=[]), str(EDITOR), 'exec'), scope)
    return scope['_sp_special_candidate_stages']


class SpecialEncounterUIStageTests(unittest.TestCase):
    def test_special_stage_includes_palette_town_and_other_g00(self):
        pick = candidate_function()
        app = SimpleNamespace(save=SimpleNamespace(stage_files=lambda: {
            0: r'C:\Switch\Game\G00\STGDAT00.BIN',
            1: r'C:\Switch\Game\G00\STGDAT01.BIN',
            2: r'C:\Switch\Game\G00\STGDAT02.BIN',
            99: r'C:\Switch\Game\B00\STGDAT99.BIN',
            3: r'C:\Switch\Game\G00\DIFFERENT.BIN',
        }))
        result = pick(app)
        self.assertEqual(set(result), {0, 1, 2})

    def test_no_save_and_b00_not_accepted(self):
        pick = candidate_function()
        self.assertEqual(pick(SimpleNamespace(save=None)), {})
        app = SimpleNamespace(save=SimpleNamespace(stage_files=lambda: {
            0: '/tmp/B00/STGDAT00.BIN',
            1: '/tmp/G00/OTHER.BIN',
            2: '/tmp/G00/STGDAT0A.BIN',
        }))
        self.assertEqual(pick(app), {})

    def test_duplicate_remove_actions_removed_from_combo(self):
        source = EDITOR.read_text(encoding='utf8')
        dlg = source.split('def add_dialog(page, selected_index=None):', 1)[1]
        dlg = dlg.split('\ndef activate_pending_map(', 1)[0]
        self.assertNotIn("mode.addItem('Remove an existing home assignment'", dlg)
        self.assertNotIn("mode.addItem('Remove resident from save registry'", dlg)
        self.assertIn('def remove_resident_ui(', source)
        self.assertIn('def direct_unlink(', source)
        self.assertIn("self.resident_remove_button = W.button", source)
        self.assertIn("self.home_unlink_button = W.button", source)

    def test_special_stages_still_check_event_and_habitat_before_write(self):
        source = EDITOR.read_text(encoding='utf8')
        self.assertIn("_sp_has_free_event(isl)", source)
        self.assertIn("_sp_special_candidate_stages(mp.app)", source)
        self.assertIn("_sp_event(", source)
        self.assertIn("anchor = next((h for h in read_habitats(app, area)", source)
        self.assertIn("_sp_backup(app.save, app.save.stage_files().get(area))", source)
        self.assertIn('STGDAT00', source)

    def test_exact_mew_search_and_unused_controls_hidden(self):
        source = EDITOR.read_text(encoding='utf8')
        self.assertIn("name.casefold() == q", source)
        self.assertIn("form.setRowVisible(friend, method not in ('spawn', 'event_items'))", source)
        self.assertIn("form.setRowVisible(manual_hab, method in ('new', 'existing', 'event', 'event_items'))", source)


if __name__ == '__main__':
    unittest.main()
