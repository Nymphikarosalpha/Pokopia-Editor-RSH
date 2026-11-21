"""Regression tests: habitat backups must work on every selected G00 island.

No real save data is opened or modified. The test extracts only the backup
function so a PySide6 install is not required for these checks.
"""
from __future__ import annotations
import ast
import datetime as dt
import pathlib
import re
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1] / 'pokopia_gui_fork.py'


def backup_function():
    module = ast.parse(SOURCE.read_text(encoding='utf-8'))
    nodes = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == '_sp_backup']
    assert len(nodes) == 1
    scope = {'re': re, '_dt': dt}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), scope)
    return scope['_sp_backup']


class AllIslandStageBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = pathlib.Path(self.tmp.name)
        self.root = self.work / 'game-save'
        (self.root / 'G00').mkdir(parents=True)
        (self.root / 'B00').mkdir(parents=True)
        (self.root / 'G00' / 'CMNDAT.BIN').write_bytes(b'common-save-placeholder')
        (self.root / 'B00' / 'CMNDAT.BIN').write_bytes(b'previous-save-placeholder')
        self.home = self.work / 'home'
        self.home.mkdir()
        self.fn = backup_function()

    def call(self, stage, registered=True):
        save = SimpleNamespace(
            folder=str(self.root),
            stage_files=lambda: {0: str(stage)} if registered else {},
        )
        with patch.object(pathlib.Path, 'home', return_value=self.home):
            return self.fn(save, str(stage) if stage is not None else None)

    def test_different_island_stages_create_valid_backups(self):
        for number in (0, 1, 2, 3, 9, 10, 99):
            with self.subTest(island=number):
                stage = self.root / 'G00' / f'STGDAT{number:02d}.BIN'
                data = bytes([number]) * 16
                stage.write_bytes(data)
                result = self.call(stage)
                with zipfile.ZipFile(result) as backup:
                    self.assertIsNone(backup.testzip())
                    self.assertEqual(backup.read(f'G00/STGDAT{number:02d}.BIN'), data)
                    self.assertIn('G00/CMNDAT.BIN', backup.namelist())
                    self.assertIn('B00/CMNDAT.BIN', backup.namelist())
                self.assertEqual(stage.read_bytes(), data)

    def test_rejects_stage_outside_selected_save(self):
        outside = self.work / 'other-save' / 'G00' / 'STGDAT02.BIN'
        outside.parent.mkdir(parents=True)
        outside.write_bytes(b'outside')
        with self.assertRaisesRegex(ValueError, 'outside the opened save'):
            self.call(outside)

    def test_rejects_unlisted_stage(self):
        stage = self.root / 'G00' / 'STGDAT03.BIN'
        stage.write_bytes(b'test')
        with self.assertRaisesRegex(ValueError, 'not listed'):
            self.call(stage, registered=False)

    def test_rejects_wrong_stage_filename_and_missing_file(self):
        wrong = self.root / 'G00' / 'DIFFERENT.BIN'
        wrong.write_bytes(b'test')
        with self.assertRaisesRegex(ValueError, 'valid STGDAT'):
            self.call(wrong)
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            self.call(self.root / 'G00' / 'STGDAT04.BIN')
        with self.assertRaisesRegex(ValueError, 'No stage data'):
            self.call(None)

    def test_rejects_previous_save_as_selected_stage(self):
        stage = self.root / 'B00' / 'STGDAT01.BIN'
        stage.write_bytes(b'old stage')
        with self.assertRaisesRegex(ValueError, 'outside the opened save'):
            self.call(stage)

    def test_spawn_experiment_still_restricted(self):
        text = SOURCE.read_text(encoding='utf-8')
        self.assertIn("path.endswith('/G00/STGDAT01.BIN')", text)
        self.assertIn("if self.area not in _sp_supported_stages(self.app):", text)
        self.assertIn('The encounter experiment is not supported on this island.', text)


if __name__ == '__main__':
    unittest.main()
