"""Regression checks for every resident-to-habitat relation in the bundled catalog.

Only confirmed recipe IDs are offered; unknown events and internal NPC slots
are explicitly unsupported, rather than silently assigned random habitats.
"""
import ast
import json
import pathlib
import unittest
from types import SimpleNamespace

BASE = pathlib.Path(__file__).resolve().parents[1]
CATALOG = json.loads((BASE / 'data/rsh_resident_habitats.json').read_text(encoding='utf-8'))['recipe_ids_by_resident']
SOURCE = (BASE/'pokopia_gui_fork.py').read_text(encoding='utf-8')


def funcs():
    src = ast.parse(SOURCE)
    wanted = {'habitat_key', 'matching_recipes', 'offline_resident_catalog', 'display_species_name'}
    cn = {'_HABITAT_FALLBACK','_FORM_HABITATS_BY_RESIDENT','_RSH_RESIDENT_CATALOG'}
    selected = []
    for node in src.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            selected.append(node)
        if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id in cn for t in node.targets):
            selected.append(node)
    import os
    ps=SimpleNamespace(VILLAGER_NAMES=['']*1050, name_of=lambda v,i,d: v[i] or d)
    ns={'ps':ps,'pi':SimpleNamespace(DATA=str(BASE/'data')),'json':json,'os':os}
    exec(compile(ast.Module(body=selected,type_ignores=[]),'<catalog>','exec'), ns)
    return ns


class CatalogAuditTests(unittest.TestCase):
    def test_catalog_shape_and_completeness(self):
        self.assertEqual(len(CATALOG),367)
        self.assertEqual(sum(bool(x) for x in CATALOG.values()),350)
        self.assertEqual(sum(not x for x in CATALOG.values()),17)
        self.assertEqual(CATALOG['143'],['189'])
        self.assertEqual(CATALOG['266'],['190'])
        self.assertEqual(CATALOG['508'],['E-006'])
        self.assertEqual(CATALOG['509'],['E-007'])
        self.assertEqual(CATALOG['510'],['E-005'])

    def test_all_catalog_entries_use_known_recipe_codes(self):
        recipefile = BASE/'data/habitat_recipes.json'
        if not recipefile.exists():
            self.skipTest('Repository recipe catalog unavailable')
        recipes = json.loads(recipefile.read_text(encoding='utf-8'))
        if len(recipes)<200:
            self.skipTest('Local reduced fixture; complete recipe validation runs in GitHub Actions')
        valid={str(r['dex']) for r in recipes}
        unsupported={}
        for i, refs in CATALOG.items():
            missing=sorted(set(refs)-valid)
            if missing:unsupported[i]=missing
        self.assertEqual(unsupported,{})
        self.assertEqual(len(valid),len(recipes))

    def test_no_unknown_form_leakage(self):
        n=funcs()
        recipe=[{'dex':'189','name':'Amped rock stage'}, {'dex':'190','name':'Low-key rock stage'},
                {'dex':'E-007','name':'Marine leisure activities'},
                {'dex':'001','name':'Tall grass'}]
        resolve=n['matching_recipes']
        self.assertEqual([r['dex'] for r in resolve('Toxtricity',recipe,143)],['189'])
        self.assertEqual([r['dex'] for r in resolve('Toxtricity',recipe,266)],['190'])
        self.assertEqual([r['dex'] for r in resolve('Milotic',recipe,509)],['E-007'])
        self.assertIsNone(resolve('Pumpkaboo',recipe,513))
        self.assertIsNone(resolve('Toxtricity',recipe,999))
        self.assertEqual(resolve('Mew',recipe,85),[])

    def test_all_resident_relations_resolve_only_their_own_recipes(self):
        n=funcs()
        recipekeys=sorted({r for rows in CATALOG.values() for r in rows})
        sample=[{'dex':r,'name':r} for r in recipekeys]
        resolve=n['matching_recipes']
        for i, expected in CATALOG.items():
            with self.subTest(resident=i):
                actual=[r['dex'] for r in resolve('Not the right Pokémon',sample,int(i))]
                self.assertEqual(actual, sorted(expected),msg='Resident ID to recipe code mismatch')

    def test_variant_labels_distinguishable(self):
        n=funcs()
        names={i:n['display_species_name'](i) for i in (143,266,256,257,267,268,269,584,585,586,587)}
        self.assertEqual(len(set(names.values())),len(names))
        self.assertTrue(names[143].startswith('Toxtricity (Amped'))
        self.assertIn('Low Key',names[266])

    def test_event_mode_has_separate_map_and_bag_actions(self):
        self.assertIn("'Build event habitat on the map (no quest completion)'",SOURCE)
        self.assertIn("'Prepare event materials in bag only'",SOURCE)
        self.assertIn("if method in ('new', 'spawn', 'event'):",SOURCE)
        self.assertIn("event_mode=(method == 'event')",SOURCE)
        self.assertIn("if pending.get('event_mode') and not pending.get('add_resident')",SOURCE)
        self.assertIn("'No event or quest completion flags were changed.",SOURCE)

if __name__=='__main__': unittest.main()
