"""Regression checks for two Toxtricity forms and their habitat recipes."""
import ast
import json
import os
import pathlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'pokopia_gui_fork.py'


def _mapping_namespace():
    """Test isolated source functions without importing a GUI or contacting servers."""
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    names = {'display_species_name', 'species', 'habitat_key',
             'habitat_map', 'offline_resident_catalog', 'matching_recipes'}
    constants = {'_HABITAT_SOURCE', '_HABITAT_MAP', '_HABITAT_MAP_STATUS',
                 '_HABITAT_FALLBACK', '_FORM_HABITATS_BY_RESIDENT', '_RSH_RESIDENT_CATALOG'}
    selected = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets):
            selected.append(node)
    villager_names = [''] * 300
    villager_names[143] = 'Toxtricity'
    villager_names[266] = 'Toxtricity'
    villager_names[73] = 'Gengar'
    ps = SimpleNamespace(VILLAGER_NAMES=villager_names,VIL_COUNT=300,
        name_of=lambda names, idx, missing: names[idx] if names[idx] else missing)
    ns = {'ps':ps, 'json':json, 'os':os, 'pi':SimpleNamespace(DATA=str(ROOT/'data'))}
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(SOURCE),'exec'),ns)
    return ns


class ToxtricityHabitatTests(unittest.TestCase):
    def setUp(self):
        self.ns = _mapping_namespace()
        self.recipes = [
            {'name': 'Amped rock stage', 'dex': '189', 'type': 119},
            {'name': 'Low-key rock stage', 'dex': '190', 'type': 120},
            {'name': 'Surprise in store', 'dex': '073', 'type': 200},
        ]

    def test_form_names_are_distinguishable_in_selector(self):
        species = dict(self.ns['species']())
        self.assertEqual(species[143], 'Toxtricity (Amped Form)')
        self.assertEqual(species[266], 'Toxtricity (Low Key Form)')

    def test_correct_form_offline(self):
        with patch('urllib.request.urlopen', side_effect=OSError('no internet')):
            match = self.ns['matching_recipes']
            self.assertEqual([x['dex'] for x in match('Toxtricity', self.recipes, 143)], ['189'])
            self.assertEqual([x['dex'] for x in match('Toxtricity', self.recipes, 266)], ['190'])
            self.assertEqual([x['dex'] for x in match('Toxtricity', self.recipes)], ['189', '190'])
            self.assertEqual([x['name'] for x in match('Gengar', self.recipes, 73)], ['Surprise in store'])

    def test_online_form_names_stay_distinct(self):
        # The external reference uses fully qualified form names, whereas the
        # game's original villager table uses the same base name for both.
        import io
        rows = ['Name,Habitat 1,Habitat 2,Habitat 3',
                'Gengar,Surprise in store,,',
                'Mewtwo,,,',
                'Toxtricity Amped Form,Amped rock stage,,',
                'Toxtricity Low Key Form,Low-key rock stage,,']
        rows.extend(f'OtherName{i},,,' for i in range(300))
        payload = ('\n'.join(rows) + '\n').encode('utf-8')
        with patch('urllib.request.urlopen', return_value=io.BytesIO(payload)):
            match = self.ns['matching_recipes']
            self.assertEqual([r['dex'] for r in match('Toxtricity', self.recipes, 143)], ['189'])
            self.assertEqual([r['dex'] for r in match('Toxtricity', self.recipes, 266)], ['190'])
            self.assertEqual(self.ns['habitat_map']()[1], 'online (PokopiaPlanning / Serebii)')

    def test_unrecognized_form_does_not_enable_unrelated_habitats(self):
        with patch('urllib.request.urlopen',side_effect=OSError('offline')):
            self.assertIsNone(self.ns['matching_recipes']('Unknown Pokémon',self.recipes,999))

    def test_exact_bundled_habitat_ids(self):
        recipes_file = ROOT / 'data' / 'habitat_recipes.json'
        if not recipes_file.exists():
            self.skipTest('Run against a complete fork checkout for bundled recipe validation')
        recipes = json.loads(recipes_file.read_text(encoding='utf-8'))
        matches = {r['name'].casefold():r for r in recipes}
        self.assertEqual((matches['amped rock stage']['dex'], matches['amped rock stage']['type']), ('189',119))
        self.assertEqual((matches['low-key rock stage']['dex'], matches['low-key rock stage']['type']), ('190',120))

if __name__=='__main__':
    unittest.main()
