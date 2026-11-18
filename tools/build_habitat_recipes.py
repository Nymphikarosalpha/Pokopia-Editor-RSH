"""Build data/habitat_recipes.json: the minimum each habitat needs, resolved to placeable game items.

Usage: py tools\\build_habitat_recipes.py REQUIREMENTS.txt

REQUIREMENTS.txt has one habitat per line, "Name (#dex) | Item x count; Item x count", taken from a public
habitat guide (fan-collected requirement lists). Each requirement becomes one of:
  item    - a placeable object (one fixed item, or the first match for "(any)" groups)
  liquid  - ground blocks replaced by a liquid (water, ocean water, muddy water, hot-spring water, lava)
  note    - something the editor cannot place (waterfall, high-up location, kits), shown as a reminder
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pokopia_extras as px  # noqa: E402
import pokopia_save as ps  # noqa: E402

OUT = os.path.join(ROOT, 'data', 'habitat_recipes.json')
LIQUIDS = {'water': 383, 'ocean water': 389, 'muddy water': 388, 'hot-spring water': 384, 'lava': 386}
NOTES = {'waterfall': 'needs a waterfall', 'high-up location': 'needs to be up high (raise the ground first)'}
# "(any)" and loose groups: preferred item names first, then a keyword search over placeable item names
GROUPS = {
    'tall grass (any)': ['tall grass'],
    'large tree (any)': ['Leppa tree', 'large palm tree', 'pointy tree'],
    'berry tree (any)': ['Leppa tree', 'Oran tree', 'Pecha tree'],
    'hedge (any)': ['healthy hedge', 'stylish hedge', 'adorable hedge', 'damp hedge'],
    'seat (any)': ['straw stool', 'log chair', 'plain stool', 'wooden chair'],
    'seat (wide)': ['wooden bench', 'stone bench', 'plain sofa', 'chic sofa'],
    'table (any)': ['straw table', 'log table', 'wooden table', 'plain table'],
    'table (large)': ['wooden table', 'plain table', 'log table'],
    'lighting (any)': ['mushroom streetlight', 'town streetlight', 'torch', 'lantern'],
    'streetlight (any)': ['town streetlight', 'mushroom streetlight', 'harbor streetlight'],
    'bed (any)': ['straw bed', 'log bed', 'plain bed'],
    'doll (any)': ['Pikachu doll', 'Eevee doll'],
    'toy (any)': ['toy blocks', 'sand toys'],
    'waste bin (any)': ['garbage bin', 'waste bin'],
    'sign (any)': ['stone sign', 'arrow sign', 'sign'],
    'potted plant (any)': ['potted plant', 'tall potted plant'],
    'closet (any)': ['plain closet', 'closet'],
    'partition (any)': ['house partition (small)', 'partition'],
    'dresser (any)': ['plain dresser', 'dresser'],
    'stand (any)': ['iron stand', 'stand'],
    'post (any)': ['wooden posts', 'post'],
    'music mat (any)': ['music mat'],
    'tree stump (any)': ['tree stump', 'Leppa tree stump', 'palm tree stump'],
    'vegetable field (any)': ['fresh carrot stem', 'tomato plant', 'potato plant'],
    'plated food': ['sandwiches', 'pizza', 'fried potatoes'],
    'iron beam or column': ['iron column', 'iron beam'],
    'lost relic (large)': ['large lost relic'],
    'castform weather charm': ['Castform weather charm'],
    'sign': ['stone sign', 'arrow sign'],
    'mirror (large)': ['large mirror', 'mirror'],
    'treasure (outdoor item)': ['big treasure chest'],
}


def placeable():
    """{lower-case item name: (item id, variation)} for every item that can stand on an island."""
    px.map_part(0)
    out = {}
    for var, (base, item, w, h, d, _) in sorted(px._MAP_PARTS.items()):
        n = ps.item_name(item) if item else ''
        if item and n and not n.startswith('Item ') and n.lower() not in out:
            out[n.lower()] = (item, var)
    return out


def find(name, table):
    n = name.lower().strip()
    for cand in (n, n.rstrip('s'), n + 's', n.replace('poke ball', 'poké ball'), n.replace('pokemon', 'pokémon')):
        if cand in table:
            return table[cand]
    return None


def resolve(label, count, table):
    key = label.lower().strip()
    if key in LIQUIDS:
        return dict(kind='liquid', label=label, count=count, block=LIQUIDS[key])
    if key in NOTES:
        return dict(kind='note', label=label, count=count, note=NOTES[key])
    for cand in GROUPS.get(key, []) + [label]:
        hit = find(cand, table)
        if hit:
            return dict(kind='item', label=label, count=count, item=hit[0], var=hit[1])
    # keyword fallback for "(any)": the first placeable item containing the base word
    base = re.sub(r'\s*\(.*\)', '', key).strip()
    for n, hit in table.items():
        if base and base in n:
            return dict(kind='item', label=label, count=count, item=hit[0], var=hit[1])
    return dict(kind='note', label=label, count=count, note='the editor cannot place this one')


def main():
    if len(sys.argv) != 2:
        sys.exit('Usage: py tools\\build_habitat_recipes.py REQUIREMENTS.txt')
    table = placeable()
    norm = lambda t: t.strip().lower().replace('’', "'").replace('é', 'e')
    habitat_types = {norm(n): i for i, n in enumerate(ps.HABITAT_NAMES) if n and n.strip()}
    recipes, missing = [], []
    for line in open(sys.argv[1], encoding='utf-8'):
        if '|' not in line:
            continue
        head, reqs = line.split('|', 1)
        m = re.match(r'(.*?)\s*\(#([^)]+)\)', head.strip())
        name, dex = m.group(1), m.group(2)
        parts = []
        for r in reqs.split(';'):
            r = r.strip()
            mm = re.match(r'(.*?)\s*x\s*(\d+)$', r)
            if not mm:
                continue
            p = resolve(mm.group(1), int(mm.group(2)), table)
            parts.append(p)
            if p['kind'] == 'note' and 'cannot' in p['note']:
                missing.append(f'{name}: {p["label"]}')
        recipes.append(dict(name=name, dex=dex, type=habitat_types.get(norm(name)), parts=parts))
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(recipes, f, ensure_ascii=False, indent=0)
    full = sum(1 for r in recipes if all(p['kind'] != 'note' or 'cannot' not in p['note'] for p in r['parts']))
    print(f'{len(recipes)} habitats -> {OUT}; {full} fully placeable; {len(missing)} requirements not placeable:')
    for m in missing:
        print('  ', m)


if __name__ == '__main__':
    main()
