"""Build the Collection page's lookup tables from a RomFS dump.

Usage: py tools\\extract_catalog_tables.py ROMFS_DIR [--check]

Writes into data/ (or, with --check, only compares with what is there):
  catalog_dex.bin        u16 per Pokédex slot: row of the Pokédex table, 0xFFFF = unused slot
  catalog_residents.bin  u16 per Pokédex slot: resident index (villager.txt line) for the name and portrait
  catalog_recipes.bin    u16 per crafting recipe: item ID it makes
  catalog_cooking.bin    u16 per cooking row: dish item ID
  catalog_records.bin    u16 per Human Record number (0-181): item ID that carries its name, 0 = none
  catalog_artifacts.bin  u16 item ID + u8 section (1 Lost Relics L, 2 Lost Relics S, 3 Fossils, 8 Treasure Maps)
                         + u8 group (1 main, 3 Bubbly Basin) per row of the Ancient Artifacts table
  item_group.bin         u8 per item ID: the collection group the game files the item under
                         (0 not listed, 1 main, 2 event, 3 Bubbly Basin, 6 building parts)
  dex.txt, habitat.txt   English names by Pokédex slot / habitat number

Entries of LD_C0_R.BIN used (index in LI_C0_R.IDX), each a 0x40-byte header followed by fixed records:
  1066  Pokédex table, 1024 x 104: u16 +24 own row number, u16 +40 Pokédex slot
   469  Pokémon table, 1024 x 48 (row = resident index - 4): u16 +18 Pokédex table row
   493  crafting recipes, 1500 x 44: u16 +18 item ID
   490  cooking recipes, 101 x 20: u16 +0 dish item ID
   983  item table, 4600 x 68: u8 +57 collection group, u8 +58 category (13 = record), u32 +12 record number
  1095  Ancient Artifacts table, 300 x 8: u16 item ID, u8 section, u8 group
  4934 / 4538  English Pokédex / habitat names (text tables: u32 count, u32 2, then relative offsets)
The table numbers for 1066, 493, 490 and the two text tables were first published by PokoHex; the resident link
through table 469 and the item group byte are own findings. Nothing is downloaded.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_item_tags import read_entry  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
HEADER = 0x40


def u16(b, o):
    return struct.unpack_from('<H', b, o)[0]


def table(romfs, entry, count, stride):
    t = read_entry(romfs, entry)
    if struct.unpack_from('<I', t)[0] != count or len(t) < HEADER + count * stride:
        raise ValueError(f'table {entry} does not look like {count} x {stride} records; different game version?')
    return [t[HEADER + i * stride:HEADER + (i + 1) * stride] for i in range(count)]


def names(romfs, entry, count, stride):
    t = read_entry(romfs, entry)
    if struct.unpack_from('<II', t) != (count, 2):
        raise ValueError(f'text table {entry} does not hold {count} names; different game version?')
    out = []
    for i in range(count):
        field = HEADER + i * stride
        start = field + struct.unpack_from('<I', t, field)[0]
        text = t[start:t.index(b'\0', start)].decode('utf-8')
        out.append(re.sub(r'<([^<>:]+):[^<>]+>', r'\1', text))
    return out


def build(romfs):
    out = {}
    dex_rows = table(romfs, 1066, 1024, 104)
    dex = [0xFFFF] * 1024
    for i, r in enumerate(dex_rows):
        slot = u16(r, 40)
        if slot:
            if u16(r, 24) != i or slot >= 1024 or dex[slot] != 0xFFFF:
                raise ValueError('Pokédex slot invalid or used twice')
            dex[slot] = i
    out['catalog_dex.bin'] = struct.pack('<1024H', *dex)
    by_row = {}
    for i, r in enumerate(table(romfs, 469, 1024, 48)):
        if u16(r, 18):
            by_row.setdefault(u16(r, 18), i + 4)       # first Pokémon row that points at this Pokédex row
    out['catalog_residents.bin'] = struct.pack('<1024H', *[by_row.get(row, 0) if row != 0xFFFF else 0 for row in dex])
    out['catalog_recipes.bin'] = b''.join(r[18:20] for r in table(romfs, 493, 1500, 44))
    out['catalog_cooking.bin'] = b''.join(r[0:2] for r in table(romfs, 490, 101, 20))
    items = table(romfs, 983, 4600, 68)
    out['item_group.bin'] = bytes(r[57] for r in items)
    records = [0] * 182
    for i, r in enumerate(items):
        n = struct.unpack_from('<I', r, 12)[0]
        if r[58] == 13 and 0 < n < len(records) and not records[n]:
            records[n] = i
    out['catalog_records.bin'] = struct.pack(f'<{len(records)}H', *records)
    out['catalog_artifacts.bin'] = b''.join(r[0:4] for r in table(romfs, 1095, 300, 8))
    row_names = names(romfs, 4934, 1024, 8)
    out['dex.txt'] = '\n'.join('' if row == 0xFFFF else row_names[row] for row in dex).encode('utf-8') + b'\n'
    out['habitat.txt'] = '\n'.join(names(romfs, 4538, 501, 12)).encode('utf-8') + b'\n'
    return out


def main():
    args = [a for a in sys.argv[1:] if a != '--check']
    check = '--check' in sys.argv[1:]
    if len(args) != 1:
        sys.exit('Usage: py tools\\extract_catalog_tables.py ROMFS_DIR [--check]')
    romfs = args[0]
    if not os.path.isfile(os.path.join(romfs, 'LI_C0_R.IDX')):
        sys.exit(f'No LI_C0_R.IDX in {romfs}; point this at the dumped romfs folder.')
    for name, blob in build(romfs).items():
        path = os.path.join(DATA, name)
        try:
            with open(path, 'rb') as f:
                old = f.read()
        except OSError:
            old = None
        if name.endswith('.txt') and old is not None:
            old = old.replace(b'\r\n', b'\n')
        same = old == blob
        if not check and not same:
            with open(path, 'wb') as f:
                f.write(blob)
        print(f'{name:24} {len(blob):6} bytes  {"same as data/" if same else "DIFFERENT" if check else "written"}')


if __name__ == '__main__':
    main()
