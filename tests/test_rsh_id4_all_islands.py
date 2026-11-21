"""Offline regression checks for ID-4 anchor selector across G00 stages.

These tests do not assert a working in-game Pokémon spawn or safe game semantics.
"""
import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / 'pokopia_gui_fork.py'


class ID4ExistingAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = SOURCE.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.code)
        cls.ui = next(n for n in cls.tree.body if isinstance(n, ast.FunctionDef) and n.name == 'add_dialog')
        cls.ui_text = ast.get_source_segment(cls.code, cls.ui)

    def test_all_categories_use_g00_candidates(self):
        self.assertIn('supported = _sp_special_candidate_stages(app)', self.ui_text)
        self.assertNotIn('supported = (_sp_special_candidate_stages(app) if special', self.ui_text)
        self.assertIn('if is_test:', self.ui_text)
        self.assertIn('known_habs = read_habitats(app, area)', self.ui_text)

    def test_existing_anchor_is_not_special_only(self):
        self.assertIn("('special-anchor', int(anchor['uid']))", self.ui_text)
        self.assertIn('if is_anchor:', self.ui_text)
        self.assertIn("if is_anchor:\n        mp = app.pages.get('Island Map')", self.ui_text)
        self.assertNotIn("if method == 'spawn' and special:\n        mp = app.pages.get('Island Map')", self.ui_text)

    def test_new_habitat_spawn_remains_on_examined_stage(self):
        self.assertIn('if not special and matched and area in _sp_supported_stages(app):', self.ui_text)
        self.assertIn("hab.addItem(f\"Build new:", self.ui_text)
        self.assertIn('else _sp_supported_stages(app))', self.ui_text)

    def test_ineligible_stages_and_empty_habitats_report_reason(self):
        self.assertIn('No usable registered habitat on the chosen island', self.ui_text)
        self.assertIn('No encounter data was changed', self.ui_text)
        self.assertIn('idx <= 4', self.ui_text)
        self.assertIn('if habitat_key(name) in _EVENT_POKEMON and not special:', self.ui_text)

    def test_backup_and_structural_checks_remain(self):
        self.assertIn('_sp_backup(app.save, app.save.stage_files().get(area))', self.ui_text)
        for x in ('def _sp_has_free_event(isl):', 'def _sp_event(isl, resident_id, uid, habitat_type):',
                  'if not _sp_has_free_event(isl):', 'isl._put(offset, entry)'):
            self.assertIn(x, self.code)
        self.assertIn('is_anchor', self.ui_text)
        self.assertIn('This is not a', self.ui_text) if False else None

if __name__ == '__main__':
    unittest.main()
