"""Validate source-level Lichii integration without requiring an emulator."""
import ast
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
CODE = (ROOT / 'pokopia_gui_fork.py').read_text(encoding='utf-8')


def functions():
    tree = ast.parse(CODE)
    required = {'_rsh_portable_lichii_roots', '_rsh_enable_lichii_support'}
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in required]
    namespace = {'_rsh_sys': SimpleNamespace(platform='win32', executable=sys.executable),
                 'os': __import__('os'), '_rsh_extras': None}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(ROOT/'pokopia_gui_fork.py'), 'exec'), namespace)
    return namespace


class LichiiIntegrationTests(unittest.TestCase):
    def test_emulator_register_and_roots_are_idempotent(self):
        ns = functions()
        original_roots = lambda name: ['standard']
        fake = SimpleNamespace(YUZU_FAMILY=('yuzu',), EMULATORS=('yuzu',), _data_roots=original_roots)
        ns['_rsh_extras'] = fake
        with patch.dict(ns['_rsh_portable_lichii_roots'].__globals__, {'_rsh_sys': SimpleNamespace(platform='linux')}):
            ns['_rsh_enable_lichii_support']()
            ns['_rsh_enable_lichii_support']()
        self.assertEqual(fake.YUZU_FAMILY.count('lichii'), 1)
        self.assertEqual(fake.EMULATORS.count('lichii'), 1)
        self.assertEqual(fake._data_roots('lichii'), ['standard'])

    def test_portable_discovery(self):
        import tempfile
        ns = functions()
        with tempfile.TemporaryDirectory() as d:
            base = pathlib.Path(d)
            root = base / 'Lichii Portable'
            (root / 'user' / 'nand').mkdir(parents=True)
            with patch.object(pathlib.Path, 'home', return_value=base):
                with patch.dict(ns['_rsh_portable_lichii_roots'].__globals__,
                                {'_rsh_sys': SimpleNamespace(platform='win32', executable=str(base/'Editor.exe'))}):
                    (base/'Downloads').mkdir()
                    (base/'Desktop').mkdir()
                    moved = base/'Downloads'/'Lichii 341'
                    (moved/'user'/'nand').mkdir(parents=True)
                    found = ns['_rsh_portable_lichii_roots']()
            self.assertIn(str(moved/'user'), found)


if __name__ == '__main__':
    unittest.main()
