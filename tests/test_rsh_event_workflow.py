"""Offline checks for the event builder vs. inventory-only preparation.

Does not claim time-limited quest completion or an in-game spawn.
"""
import ast
import json
import pathlib
import unittest
from types import SimpleNamespace

BASE = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (BASE / 'pokopia_gui_fork.py').read_text(encoding='utf8')


def isolated():
    tree = ast.parse(SOURCE)
    wanted = {'habitat_key', 'is_event_recipe', 'permitted_habitats_for_action',
              'offline_resident_catalog', 'matching_recipes', 'event_content_bypass'}
    globals_ = {'_FORM_HABITATS_BY_RESIDENT', '_RSH_RESIDENT_CATALOG',
                '_HABITAT_FALLBACK', '_EVENT_POKEMON'}
    selected=[]
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            selected.append(node)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id in globals_ for t in targets):
                selected.append(node)
    class SaveDummy:
        def __init__(self):
            self.slots=[(0,0)]*20
            self.collections=[]
        def get_slot(self, i): return self.slots[i]
        def add_item(self, item, n):
            for j,slot in enumerate(self.slots):
                if slot[0]==0:
                    self.slots[j]=(item,n)
                    return
            raise ValueError('no free inventory slot')
        def unlock_collection(self, kind, slots, partial=False):
            self.collections.append((kind,tuple(slots),partial))
    ps=SimpleNamespace(VILLAGER_NAMES=['']*1050, name_of=lambda ls,i,d:ls[i] or d,
                       ITEM_MASK=65535, INV_COUNT=20, INV_MAIN=20,
                       COLLECTION={'item':[(500,'item')], 'habitat':[(222,'event')]})
    ps.VILLAGER_NAMES[509]='Milotic'
    import os
    ns={'ps':ps,'pi':SimpleNamespace(DATA=str(BASE/'data')),'json':json,
        'os':os,'__name__':'rsh_event_isolated','recipes':lambda:[],
        'dex_slots':lambda i:[],'edit_resident':lambda *a,**k:None}
    exec(compile(ast.Module(body=selected,type_ignores=[]),'<rsh_event>','exec'),ns)
    return ns,SaveDummy


class EventWorkflowTests(unittest.TestCase):
    def test_event_actions_are_separate(self):
        self.assertIn("'Build event habitat on the map (no quest completion)'",SOURCE)
        self.assertIn("'Prepare event materials in bag only'",SOURCE)
        self.assertIn("manual_hab.setEnabled(method in ('existing', 'new', 'event', 'event_items'))",SOURCE)
        self.assertIn("allow_unverified=manually_selected",SOURCE)
        self.assertIn("if method in ('new', 'spawn', 'event'):",SOURCE)
        self.assertIn("event_mode=(method == 'event')",SOURCE)
        self.assertIn("'No quest flag or NPC encounter changed.",SOURCE)

    def test_event_manual_choices_limited_to_event_recipes(self):
        ns,_=isolated()
        all_= [{'dex':'001','name':'Normal grass','type':1},
               {'dex':'E-006','name':'Exciting beach','type':221},
               {'dex':'E-007','name':'Marine leisure activities','type':222}]
        matched= [all_[2]]
        p=ns['permitted_habitats_for_action']
        self.assertEqual(p(all_,matched,'event'), matched)
        self.assertEqual(p(all_,matched,'event_items'), matched)
        self.assertEqual(p(all_,None,'event',manual=True),all_[1:])
        self.assertEqual(p(all_,None,'event_items',manual=True),all_[1:])
        self.assertEqual(p(all_,None,'new',manual=True),all_)
        self.assertEqual(p(all_,None,'event',manual=False),[])

    def test_verified_event_materials_dont_touch_quest_flags(self):
        ns,Save=isolated()
        rec={'dex':'E-007','name':'Marine leisure activities','type':222,
             'parts':[{'kind':'item','item':500,'count':3}]}
        ns['recipes'] = lambda:[rec]
        c=Save()
        outcome=ns['event_content_bypass'](c,509,rec,None,0)
        self.assertEqual(outcome['added'],{500:3})
        self.assertEqual(c.slots[0],(500,3))
        self.assertIn(('habitat',(222,),True),c.collections)
        self.assertFalse(any(k=='quest' for k,_,__ in c.collections))

    def test_event_materials_manual_override_is_explicit(self):
        ns,Save=isolated()
        rec={'dex':'E-006','name':'Exciting beach','type':221,
             'parts':[{'kind':'item','item':500,'count':1}]}
        ns['recipes']=lambda:[{'dex':'E-007','name':'Marine leisure activities','type':222}]
        with self.assertRaisesRegex(ValueError,'Recipe does not match'):
            ns['event_content_bypass'](Save(),509,rec,None,0)
        c=Save()
        out=ns['event_content_bypass'](c,509,rec,None,0,allow_unverified=True)
        self.assertEqual(out['added'],{500:1})
        with self.assertRaisesRegex(ValueError,'not a supported event'):
            ns['event_content_bypass'](Save(),509,{'dex':'001','type':1},None,0,allow_unverified=True)

    def test_event_modes_cannot_validate_normal_recipe(self):
        ns,_=isolated()
        all_=[{'dex':'001','type':1},{'dex':'E-001','type':250}]
        for method in ('event','event_items'):
            self.assertEqual(ns['permitted_habitats_for_action'](all_, all_, method),[all_[1]])

if __name__=='__main__': unittest.main()
