"""Offline tests for v0.2.1 legendary/mythical encounter experiment.

These tests prove source transformations and guards, not game behavior.
"""
from __future__ import annotations
import ast
from pathlib import Path
import hashlib
import sys
import tempfile
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch as mockpatch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import rsh_legendary_patch as sp
import prepare_special_spawn_release as release


def generated_fragment(label):
    """Extract a literal patch fragment without importing PySide6 or a game save."""
    tree = ast.parse((ROOT / 'tools' / 'rsh_legendary_patch.py').read_text(encoding='utf-8'))
    rewrite = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'rewrite')
    for n in ast.walk(rewrite):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'replace_exact':
            if ast.literal_eval(n.args[3]) == label:
                return ast.literal_eval(n.args[2])
    raise AssertionError(f'No injection found: {label}')


class ReleasePatchTests(TestCase):
    def test_exact_source_replacement_and_no_guessing(self):
        tree = ast.parse((ROOT / 'tools' / 'rsh_legendary_patch.py').read_text(encoding='utf-8'))
        rewrite = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'rewrite')
        before = [ast.literal_eval(n.args[1]) for n in ast.walk(rewrite)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == 'replace_exact']
        self.assertEqual(len(before), 19)
        assembled = '\n'.join(before)
        for s in before:
            self.assertEqual(assembled.count(s), 1)
        modified = sp.rewrite(assembled)
        self.assertIn('def species_mode_recommendation(', modified)
        self.assertIn('def _sp_run_special_pending(mp):', modified)
        self.assertIn("('special-anchor', int(anchor['uid']))", modified)
        self.assertIn('QVBoxLayout, QPushButton)', modified)
        self.assertIn('Recommended settings:', modified)
        self.assertIn('Which settings for which Pokémon?', modified)
        self.assertNotIn('if special or matched == [] or idx <= 4:', modified)
        with self.assertRaises(ValueError):
            sp.rewrite('not our original source')

    def test_special_mode_guidance_for_mew_and_mewtwo(self):
        injected = generated_fragment('Automatische Modus-Empfehlungen nach Pokémon-Kategorie')
        tree = ast.parse(injected)
        name = {85:'Mew',84:'Mewtwo',189:'Suicune',40:'Oddish',510:'Jirachi',100:'Unknown'}
        mapping = {85:[],84:[],189:[],40:[{'dex':'002'}],510:[{'dex':'E-003'}],100:None}
        namespace = {
            'display_species_name': lambda i:name[i],
            'habitat_key': lambda x:x.lower().replace(' ',''),
            'is_special_pokemon': lambda x:x in ('Mew','Mewtwo','Suicune','Jirachi'),
            'matching_recipes': lambda n,r,i:mapping[i],
            '_EVENT_POKEMON':frozenset({'jirachi'}),
            'is_event_recipe':lambda x:str(x.get('dex','')).startswith('E-')
        }
        exec(compile(tree,'<guidance>','exec'),namespace)
        guide = namespace['species_mode_recommendation']
        for i in (85,84,189):
            msg = guide(i,[],1,{1:'a-stage'})
            self.assertIn('LEGENDARY / MYTHICAL',msg)
            self.assertIn('No spawn or event completion is confirmed',msg)
            self.assertIn('existing anchor',msg)
        self.assertIn('disabled on this island',guide(84,[],2,{1:'stage'}))
        self.assertIn('NORMAL / HABITAT-BASED',guide(40,[],1,{}))
        self.assertIn('SPECIAL / EVENT',guide(510,[],1,{}))
        self.assertIn('UNKNOWN HABITAT MAPPING',guide(100,[],1,{}))
        self.assertIn('position anchor',namespace['species_settings_reference']())

    def test_experimental_runner_only_journals_after_guards(self):
        block = generated_fragment('Testschreiber in bestehende Undo-/Save-Verwaltung')
        script = block.split('\ndef _sp_backup(save, stage_path):',1)[0]
        events=[]
        ns = {
            '_sp_supported_stages':lambda app: {1:'stage'},
            '_sp_has_free_event':lambda isl: True,
            '_sp_event':lambda isl,i,uid,typ:(events.append(('event',i,uid,typ)) or (5,i-4,(3,2,1))),
            'display_species_name':lambda i:'Mew' if i==85 else 'Mewtwo'
        }
        exec(compile(script,'<runner>','exec'),ns)
        mp=SimpleNamespace(
            area=1, special_test_pending={'area':1,'index':85,'uid':105,
                 'habitat_type':3,'backup':'backup.zip'},
            isl=lambda:SimpleNamespace(rollback=lambda:events.append(('rollback',))),
            commit=lambda label:events.append(('commit',label)),
            app=SimpleNamespace(toast=lambda *args:events.append(('toast',args)))
        )
        ns['_sp_run_special_pending'](mp)
        self.assertEqual(events[0],('event',85,105,3))
        self.assertEqual(events[1][0],'commit')
        self.assertIsNone(mp.special_test_pending)

    def test_unsupported_stage_aborts_without_encounter_write(self):
        block = generated_fragment('Testschreiber in bestehende Undo-/Save-Verwaltung')
        script = block.split('\ndef _sp_backup(save, stage_path):',1)[0]
        events=[]
        ns={'_sp_supported_stages':lambda app:{},
            '_sp_has_free_event':lambda isl:True,
            '_sp_event':lambda *a:events.append('BAD_WRITE'),
            'display_species_name':lambda i:'Mewtwo'}
        exec(compile(script,'<runner>','exec'),ns)
        mp=SimpleNamespace(area=1,special_test_pending={'area':1,'index':84,'uid':105,
                       'habitat_type':3,'backup':'backup.zip'},
             isl=lambda:SimpleNamespace(rollback=lambda:events.append('rollback')),
             commit=lambda label:events.append('commit'),
             app=SimpleNamespace(toast=lambda *a:None))
        ns['_sp_run_special_pending'](mp)
        self.assertEqual(events,['rollback'])

    def test_release_helper_rejects_exe_folder_and_source_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'PokopiaEditor_RSH.exe').write_bytes(b'MZ')
            with self.assertRaisesRegex(ValueError,'full GitHub source'):
                release.prepare(root)
            (root/'PokopiaEditor.spec').write_text('stub',encoding='utf-8')
            (root/'pokopia_gui_fork.py').write_text('wrong source',encoding='utf-8')
            (root/'CHANGELOG_FORK.md').write_text('old',encoding='utf-8')
            (root/'docs').mkdir()
            (root/'docs'/'FORK_FEATURES.md').write_text('old',encoding='utf-8')
            (root/'README.md').write_text('# Old README\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'differs'):
                release.prepare(root)
            self.assertEqual((root/'pokopia_gui_fork.py').read_text(encoding='utf-8'),'wrong source')
            self.assertEqual((root/'CHANGELOG_FORK.md').read_text(encoding='utf-8'),'old')

    def test_release_helper_source_patch_and_idempotence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'PokopiaEditor.spec').write_text('stub',encoding='utf-8')
            (root/'pokopia_gui_fork.py').write_text('placeholder\n',encoding='utf-8')
            (root/'CHANGELOG_FORK.md').write_text('# Old history\n',encoding='utf-8')
            (root/'docs').mkdir()
            (root/'docs'/'FORK_FEATURES.md').write_text('# Features\n',encoding='utf-8')
            (root/'README.md').write_text('# Original README\n',encoding='utf-8')
            with mockpatch.object(release,'github_blob_sha',return_value=release.BASE_BLOB_SHA), \
                 mockpatch.object(release,'rewrite',return_value='def _sp_run_special_pending(mp):\n    pass\n\ndef species_mode_recommendation(a,b,c,d):\n    pass\n'):
                self.assertEqual(len(release.prepare(root,dry_run=True)),4)
                modified=release.prepare(root)
                self.assertEqual(set(modified),{'pokopia_gui_fork.py','CHANGELOG_FORK.md','docs/FORK_FEATURES.md','README.md'})
                self.assertEqual(release.prepare(root),[])
            self.assertIn('No in-game Mew or Mewtwo', (root/'CHANGELOG_FORK.md').read_text(encoding='utf-8'))
            self.assertIn('Which spawn settings should I use?', (root/'README.md').read_text(encoding='utf-8'))
            self.assertIn('Mew, Mewtwo', (root/'README.md').read_text(encoding='utf-8'))
            self.assertFalse((root/'pokopia_gui_fork.py.rsh021.tmp').exists())

    def test_release_uses_one_exe_not_an_installer_patch(self):
        workflow=(ROOT/'.github'/'workflows'/'publish-special-spawn-v021.yml').read_text(encoding='utf-8')
        self.assertIn('dist/PokopiaEditor_RSH.exe',workflow)
        self.assertIn('python tools/build_fork.py',workflow)
        self.assertIn('python tools/prepare_special_spawn_release.py',workflow)
        self.assertIn('README.md', workflow)
        self.assertIn('v0.2.1',workflow)
        self.assertNotIn('pyinstaller --onefile',workflow.lower())
        # Existing PyInstaller spec is reused by the official Windows builder.


if __name__=='__main__':
    import unittest
    unittest.main()
