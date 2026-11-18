"""Build data/blocks.bin from a RomFS dump: which item each terrain block id is, so the map can name and colour it.

Usage: py tools\\extract_block_table.py ROMFS_DIR

Own finding (2026-11-18): in the item table (entry 983 of LD_C0_R.BIN, 68-byte records indexed by item ID) the u16 at
+12 is the block id the item places when its sort code (u16 at +16) is 3000-3999 (terrain, floors, liquids), or when its
collection byte (+58) is 1 (walls and floors). Island cells (STGDAT) store that block id in their low 11 bits.

Output: 2048 records of 4 bytes, indexed by block id: u16 item ID (0 = none), u8 kind, u8 0.
Kinds: 1 natural terrain, 2 building block (floor / wall / road), 3 liquid.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_item_tags import read_entry  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'blocks.bin')
ITEM_TABLE, HEADER, RECORD = 983, 0x40, 68
NONE, TERRAIN, BUILD, LIQUID = 0, 1, 2, 3
SEA_SURFACE, SEAWATER = 349, 389   # 349 is the top layer of the sea; it shares seawater's texture


def main():
    if len(sys.argv) != 2:
        sys.exit('Usage: py tools\\extract_block_table.py ROMFS_DIR')
    romfs = sys.argv[1]
    if not os.path.isfile(os.path.join(romfs, 'LI_C0_R.IDX')):
        sys.exit(f'No LI_C0_R.IDX in {romfs}; point this at the dumped romfs folder.')
    table = read_entry(romfs, ITEM_TABLE)
    count = (len(table) - HEADER) // RECORD
    best = {}
    for item in range(count):
        rec = table[HEADER + item * RECORD:HEADER + (item + 1) * RECORD]
        r = struct.unpack_from('<34H', rec)
        kind_code, block, sort, group = r[4], r[6], r[8], rec[58]
        if not block or block >= 2048:
            continue
        if 3900 <= sort < 4000 and kind_code == 1:
            kind = LIQUID
        elif 3000 <= sort < 3900:
            kind = TERRAIN if kind_code == 10 else BUILD
        elif group == 1 and kind_code in (10, 20, 25, 30, 50, 500):
            kind = BUILD
        else:
            continue
        # several items can share a block (recipes, variants): keep the lowest sort code, then the lowest item ID
        key = (sort if sort >= 1000 else 9999, item)
        if block not in best or key < best[block][0]:
            best[block] = (key, item, kind)
    out = bytearray(2048 * 4)
    for block, (_, item, kind) in best.items():
        struct.pack_into('<HBB', out, block * 4, item, kind, 0)
    if SEAWATER in best and SEA_SURFACE not in best:
        struct.pack_into('<HBB', out, SEA_SURFACE * 4, best[SEAWATER][1], LIQUID, 0)
    with open(OUT, 'wb') as f:
        f.write(out)
    kinds = [best[b][2] for b in best]
    print(f'{len(best)} blocks -> {OUT}: {kinds.count(TERRAIN)} terrain, {kinds.count(BUILD)} building, '
          f'{kinds.count(LIQUID)} liquid')


if __name__ == '__main__':
    main()
