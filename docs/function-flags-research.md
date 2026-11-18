# Function flags: code and data map (steps 1–2)

Game build: main 76A489F3 (update 655360 / Recompia 2.0.1, same main). Offsets are main-relative
(main = 0x7100000000 in Recompia). Sources: Ghidra headless (`re/dump.ps1`), `re/scripts/callargs.py`
on `re/build/main_text.bin`, and LINKDATA tables from the RomFS. Nothing here was tested in game yet.

**Summary:** all but eleven flags in 1–159 now have a known source: quests (105 flags), event chains
(shop purchases: bag, PP, handy bag, tripod, plus 11 and 114) or story scripts (opcode 3000).
**Flags 160–249 appear nowhere** (no quest, event, script, code or ROM bits): almost certainly unused.
Never set by anything in 1–159: 80, 81, 83, 85, 94, 110–113, 142, 154 (142 is checked in code but never set).

## Where the flags live

| What | Where |
|---|---|
| Save object `S` | `*(main+0x3483B60)` (same pointer also at `main+0x3561930`) |
| Function flags | `S+0x4A26A8`, 32 bytes, bit `id & 7` of byte `id >> 3`, **ids 1–249** (= save file `0x220F04`, `FLAG_COUNT 250`) |
| Per-flag ROM table | LINKDATA entry **949** (resource slot 0xA5; entry = slot + 784): 250 x 4 bytes, byte +2 = behaviour bits |
| Getter | `main+0x113F10  IsFunctionFlag(id, player)`; player 0xFF = you, 0–3 = a Link Play slot |

ROM table byte +2 (read by the getter):
- bit 0 = flag always counts as on (only flag **19**).
- bit 1 = always on while the current area is 17 (`main+0x77ECB0`: `area == 0x11`).
- bit 2 = in Link Play, read the given player's copy (from the player-info packet) instead of yours.
  76 flags have bits 1+2, 10 only bit 2, 8 only bit 1, 154 none. Flag 155 also has a u16 `0xB7` at +0.

The getter is the only reader. A second, unrelated 250-bit array sits at `S+0x4A2CCC` (ids 1–250,
map-region gating with ROM table 1211, set by event commands at `0x122CD4` / `0x12C8E0`); it is
**not** the editor's flag block.

## Who sets flags

| Function | Trigger |
|---|---|
| `0x11A800` | Quest completed (state 4): sets every flag the quest lists (map lookup `0xA58C00` on `*(main+0x3483AD8)`) |
| `0x121BB8` | Script command: set up to 4 flags (u16 ids at +2/+4/+6/+8) |
| `0x1227FC` | Script command: set/clear one flag (id +2, value +4) |
| `0x10C0D0` | Event-chain action type 2: set/clear one flag (record +4 id, +6 value), see step 2b |
| `0x12C35C` | Script opcode 3000: set/clear (id +4, mode +8: 1 on, 2 off), see step 2b |
| `0x10C33C` | Apply the next PP upgrade (see 102–105) |

Side effects on set: 149/150 refresh a menu (`[main+0x3561960]+0x16B4 = 1`, `0x1042FA8`);
129 calls `0xA8CC30(0, 0x77, 10, 1)`; 107 calls `0x5D1620(S+0x108, 0x75, 1)`.
`0x535240` copies all flags into your Link Play player-info record.

**Most flags are data driven**: their ids come from quest/script/ROM records, not from code. Only the
ones below appear as constants. The rest need step 2 (ROM tables, starting with the quest → flag list).

## Flags checked by constant id

Confidence: **sure** = the code makes the meaning plain; **likely** = fits the code and agrees with
another source; **use only** = we know where it is checked, not what it means yet.

| Flag | Code evidence | Meaning | Confidence |
|---|---|---|---|
| 11 | gates an update step in `0x1C0D00` | ? | use only |
| 14 | two periodic timers in `0x1B8B20` / `0xBA8C0` (fire `0x1C9440`, `0x1C9AE0`) when the area allows it | some timed area event | use only |
| 15 | override in the region test `0x111680` | ? | use only |
| 16 | `0x1C3EE8`, not in area 5 | ? | use only |
| 18 | 6 sites around a timer/clock system (`0x1F79B8` every 10 s, `0x1FACD4` adds to `S+0xA42FC2`, `0x231C5C`) | a day/time feature is running | use only |
| 19 | ROM bit 0 | always on | sure |
| 22, 96, 37, 97 | `0x409FC` maps kind 1–4 to these four; `0x40870` checks them from record bits 1–4 | four unlockable "kinds" of something | use only |
| 23–25 | `0x116ED4(i)` = flag 23+i, i 0–2 | three-step unlock | use only |
| 38 | `0x40C20`, with area bit 0x8D.2 | ? | use only |
| 40 | `0x473A0`, with area bit 0x8D.4 | ? | use only |
| 61 | `0x1F8840` / `0x1F8C00`: in area 12 it raises a value from 2 to 3 | ? | use only |
| 63, 64, 65, 66 | bag size table `main+0x280BBE8` = 20 / 30 / 60 / 90 / 120; highest flag wins | **bag upgrade to 30 / 60 / 90 / 120 slots** | sure |
| 74, 125 | `0x4278EC` (per player): 125 → 0x20, else 74 → 0x16, else 4 | two tiers of the same effect (PokoHex: Rock Smash food boost / extra effect) | likely |
| 79, 99, 116, 84, 109, 118 | `0x11421C`: action type 21→79, 22→99, 24→116, 26→84, 27→109, 29→118 | specialty gates: paint, illuminate, engineer, Gather Honey, yawn, DJ (step 2c) | sure |
| 43, 48, 121/122, 120, 95, 116, 132, 158 | `0x48620`: type 2→43, 3→48, 4→121 or 122, 9→120, 20→95, 21→116, 23→132, 26→158 (Bubbly Basin only) | unlock per action type (second table) | use only |
| 86, 87, 88, 89, 151 | `0x114524` / `0x114574`: one flag per area 1–5 (Withered Wasteland, Bleak Beach, Rocky Ridges, Sparkling Skylands, Bubbly Basin) | per-area unlock/state | likely |
| 92 | `0x1145AC`: on and `S+0x972BA8` bit 2 clear | ? | use only |
| 102, 103, 104, 105 | `0x10C33C` sets the next of these (table `main+0x280805C`) and adds the PP difference | **PP upgrade 1 / 2 / 3 / 4** | sure |
| 107 | read next to the bag size in item/storage code (`0x5BC960`, `0x5BCE04`, `0x5727C0`) | inventory extra (PokoHex: secondary bar) | likely |
| 123, 124 | `0x1143A8`: type 22→123, 23→124 | ? | use only |
| 129 | setting it calls `0xA8CC30(0,0x77,10,1)` | triggers something (notice 0x77?) | use only |
| 139 | `0x116EF4` | ? | use only |
| 142 | gate at the top of `0x89360` | ? | use only |
| 148 | 55 sites; picks object record mask 0x1000 (on) or 0x800 (off), also on in area 17 | major unlock affecting objects (PokoHex: Dive) | use only |
| 149, 150 | checked when a type is 4 / 5 (8 sites); setting refreshes a menu | Sparkling Skylands / Bubbly Basin unlock? | use only |
| 159 | always paired after 148 (`0x78C330`, `0x858BC4`, `0x85A0F0`, `0x208960`) | follow-up to 148 | use only |

"Area" = byte `[main+0x3561710]+0x18` (1–5 = the five areas in `data/area.txt`, 0x11 = area 17).
"Action type" (1–63) is the first argument of `0x11421C` / `0x48620` / `0x1143A8`; for `0x11421C` and
`0x1143A8` it is the specialty id (step 2c).

## Step 2: flags set by quests (ROM data)

**How quests set flags.** Quest ids 1–1000 have one 184-byte record in one of six LINKDATA tables, picked
by `main+0x11E520`:

| Quest ids | Table | Area (checked through flags 86–89/151) |
|---|---|---|
| 1–160 | 1206 | Withered Wasteland |
| 161–320 | 1204 | Bleak Beach |
| 321–480 | 1205 | Rocky Ridges |
| 481–640 | 1210 | Sparkling Skylands |
| 641–800 | 1207 | ? (painting quests live here) |
| 801–1000 | 1203 | Bubbly Basin |

Each record holds 4 commands run when the quest **completes** (type bytes +0xA9..+0xAC, params at
+0x0E + 16·slot) and 4 run when it **starts** (types +0xB1..+0xB4, params +0x68 + 16·slot; table 1203
uses +0xB3..+0xB6). A command is a type byte and 8 u16 params, run by `main+0x11B214`. Type **1** sets up
to 4 flags (params 0–3), type **0x19** sets/clears one flag (param 0 = id, param 1 = value).
Other useful types: 2 = learn a move (id = `data/skill.txt` line), 3 = unlock a crafting recipe
(row of `data/catalog_recipes.bin`), 0x27 = set a map-region bit in the other array.
Table 949's u16 at +0 adds one more link: flag **155** is set when quest **183** completes
(map `*(main+0x3483AD8)+0x6EB0`, read by `0x11A800`).

Quests have no reliable titles (many are hidden story steps), so the context below is what else the same
quest step does. Flags listed together are set by the same command list.

| Flag | Set by (quest, area, when) and what comes with it |
|---|---|
| 3 | q114 Wasteland done + recipes campfire, log table, log chair |
| 7 | q19 Wasteland done + flag 27 |
| 10 | q7 Wasteland start + flags 55, 101 |
| 14 | q20 Wasteland done + flags 86, 91 |
| 15 | q31 Wasteland done + learn **Rock Smash** |
| 16 | q17 Wasteland done + flags 18, 121, 138; q38 Wasteland done + flags 28, 34, 35 |
| 17 | q123 Wasteland done + flag 76 |
| 18 | q17 Wasteland done + flags 16, 121, 138 |
| 22, 26, 133, 140 | q22 Wasteland done |
| 23, 24, 25, 37, 38, 96, 127, 128 | q24 Wasteland done (one quest sets all eight) |
| 27 | q19 Wasteland done + flag 7 |
| 28, 34, 35 | q38 Wasteland done + flag 16 |
| 29 | q643 (641–800) done |
| 30 | q21 Wasteland done |
| 40, 60, 122 | q14 Wasteland done |
| 41 | q330 Ridges done |
| 43 | q58 Wasteland done |
| 48 | q175 Beach done |
| 54 | q199 Beach done |
| 55, 101 | q7 Wasteland start + flag 10 |
| 56 | q203 Beach done + learn **Surf** |
| 57 | q493 Skylands done + learn **Glide** |
| 58 | q539 Skylands done |
| 59 | q325 Ridges done |
| 61, 109 | q62 Wasteland done |
| 62, 144 | q97 Wasteland done |
| 67, 69, 71, 73 | q372 Ridges done + recipe **cutting board** |
| 68, 72 | q338 Ridges done + recipe **bread oven** |
| 70, 74, 125 | q386 Ridges done + recipe **frying pan** |
| 75, 141 | q13 Wasteland done |
| 76 | q123 Wasteland done + flag 17 |
| 77 | q694 (641–800) done |
| 78 | q700 (641–800) start |
| 79, 132 | q650 (641–800) start |
| 82 | q86 Wasteland done |
| 84 | q83 Wasteland done |
| 86 / 87 / 88 / 89 / 151 | q20 Wasteland / q166 Beach / q323 Ridges / q489 Skylands / q833 Basin, each done |
| 90 | q88 Wasteland done |
| 91 | q20 Wasteland done + flags 14, 86 |
| 92 | q654 (641–800) done |
| 93 | q326 Ridges done |
| 95 | q59 Wasteland done |
| 99 | q258 Beach done (on, + flag 123); q664 done clears it; q680 done sets it again |
| 106 | q9 Wasteland done |
| 108 | q102 Wasteland done |
| 115, 124 | q346 Ridges done |
| 116 | q502 Skylands done |
| 117 | q687 (641–800) done |
| 118 | q385 Ridges done + recipes **cannon**, **firework (white)** |
| 120 | q183 Beach done |
| 121, 138 | q17 Wasteland done + flags 16, 18 |
| 126 | q222 Beach done |
| 130 | q44 Wasteland done |
| 131 | q23 Wasteland done + recipe **straw bed** |
| 134 | q350 Ridges done |
| 135 | q12 Wasteland done |
| 136, 146 | q87 Wasteland done |
| 137 | q686 (641–800) done |
| 139 | q103 Wasteland done |
| 143 | q129 Wasteland done |
| 145 | q131 Wasteland start |
| 147 | q110 Wasteland done |
| 148 | q805 Basin done |
| 149, 150 | q801 Basin **start** (first Basin quest) |
| 152, 153 | q813 Basin done; q826 Basin done |
| 155 | q183 Beach done (through table 949) |
| 156 | q807 Basin start |
| 157 | q834 Basin done |
| 158 | q843 Basin done |
| 159 | q810 Basin start |

## Step 2b: event chains and scripts

**Event chains.** `main+0x10AFC0` runs the actions of "event" chains (ids 1–254, stage = s16, progress
saved at `S+0x4A4410 + id*16`). The records come from LINKDATA **5589–5622** (34 files, read by
`main+0x113DA0`): 0x40 header, u32 index list, then 28-byte records: +0 u16 event id, +2 s16 stage,
+4.. 9 s16 params, +0x16 action type, +0x17.. one "kind" byte per param (3 = quest id, 4 = shop row).
Action type 2 = set/clear flag (param 0 = id, param 1 = value), 8 = next PP upgrade. Handlers are the
16-entry table at `main+0x322D658`. Shop rows resolve through LINKDATA **70** (2048 x 36, u16 +8 = item):

| Event | Sets | Trigger |
|---|---|---|
| 61 | flags 63 → 64 → 65 → 66, one per stage | shop row 513 = **Packing Tips: Rookie** (bag upgrades) |
| 67 | next PP upgrade (102–105), 3 stages | shop row 527 = **PP Up** |
| 60 | flag 107 | shop row 514 = **handy bag** |
| 68 | flag 129 | shop row 1226 = **tripod** |
| 71 | flag 114 | after quest 46 completes |
| 69 | flag 11 | at stage 50 of event 2 (Withered Wasteland story chain) |

Events 2, 3, 4, 5 and 150 are the story chains of the five areas (stages list their quests).

**Scripts.** The script VM `main+0x12F690` (run by `0x131200`) has opcode **3000** = set/clear flag:
12-byte instruction `u32 3000, u32 id, u32 mode` (1 = on, 2 = off), handler `0x12C35C`. LINKDATA
**7099** (308 scripts), **7100** (187), **7108** (102) hold real game scripts (u32 count + offset list);
7119–7122 are one-shot "progress preset" scripts that set 40–55 flags at once. 7124–7126 also use id 0,
so opcode 3000 may mean something else there. Flags set only by small scripts (meaning still needs the
script decoded): 1, 4, 5, 6, 20, 21, 31, 32, 33, 36, 39, 42, 44, 45, 47, 49, 52, 53
(e.g. 39 = 7099 #149, 42 = 7108 #35). Only in presets: 2, 9, 12, 97, 98, 100, 119.
7099 #1 clears ~35 flags and sets 1, 4, 5, 6, 19, 29, 53: likely the new-game reset.

## Step 2c: decoding the scripts

Disassembler: `re/scripts/scriptdis.py` (opcode lengths in `re/vm_ops.json` / `re/cond_ops.json`, pulled from
the two switch statements). A script bank is picked by script id in `main+0x132758` (id 1–229 → LINKDATA
7098 + id, so id 1 = 7099, 2 = 7100, 10 = 7108; quest record +0x58 is that quest's own script id).

- **Script**: w0 id, w1 kind, w7/w8 = condition tree offset/count, w9/w10 = command list offset/count.
- **Conditions** (`main+0x12483C`): 99999 = AND, 99998 = OR (w2 children, w3 child words); 1 = "script N
  already ran"; 1010 = talking to a character; 1020 = an item trigger; 2500 = save byte
  `S+0x6FABD9 + 4·X` equals n.
- **Commands** (`main+0x12F690`): 3000 = set/clear flag, 2000 = give item (item id), 2101 = show a tip
  (title = text 5177, body = 5168), 2105 = unlock a tip, 3565/3600 = act on a character.

Flag-setting scripts, with what they do alongside (from banks 7099, 7100, 7108):

| Flag | Script | Shown / given with it |
|---|---|---|
| 4, 7 | 7099 #205 | tip "Healing at a Pokémon Center", item diploma (7 also on/off in 7100 #20/#24) |
| 11 | 7099 #230 | tip "Pokémon Traces" (habitat clues in the Habitat Dex) |
| 20, 53 | 7099 #107, #108 | tip "Stockpile / Spit Out" |
| 22, 16, 28 | 7099 #176 | tip "Environment Level", item Chili Sauce |
| 23 | 7099 #260 | tips "Preferred Environment" + "Home Brightness" |
| 24 | 7099 #265 | tip "Home Temperature" |
| 25 | 7099 #266 | tip "Home Humidity Level" |
| 26 | 7099 #262 | tip "Things Pokémon Like" |
| 37 | 7099 #258 | tip "Comfort Level: Food" |
| 38 | 7099 #267 | tip "Things Pokémon Dislike" |
| 32, 33 | 7099 #268 | tip on the **storage** specialty |
| 47 | 7108 #40 | tip on the **grow** specialty |
| 3 | 7099 #119 | after talking to a character (PokoHex: Workbench) |
| 30 | 7099 #159, 7100 #22 | item Soda Pop (PokoHex: PC shop) |
| 36 | 7099 #161 | item Moomoo Milk coffee |
| 45 | 7099 #196, #203 | items Star Piece / palm seeds, Fresh Water |
| 31 | 7099 #290 | item nonburnable garbage |
| 10, 14, 15, 18, 39, 40, 42, 43, 44 | various | no tip or item to go on yet |

**Specialty unlocks.** Step 1's "action type" 1–63 is the **specialty id** (names in text 5078:
1 build, 4 litter, 5 grow, 6 storage, 8 water, 9 generate, 10 burn, … 21 paint, 22 illuminate, 23 party,
24 engineer, 26 Gather Honey, 27 yawn, 29 DJ). `main+0x11421C` gates specialties by flag:
21 paint → **79**, 22 illuminate → **99**, 24 engineer → **116**, 26 Gather Honey → **84**,
27 yawn → **109**, 29 DJ → **118**. `0x1143A8`: 22 → 123, 23 party → 124. A second table (`0x48620`)
uses ids 1–31 that may be a different list (2 → 43, 3 → 48, 4 → 121/122, 9 → 120, 20 → 95, 21 → 116,
23 → 132, 26 → 158).

## Best labels so far (steps 1 + 2)

PokoHex labels were used only as hints; "agrees" means our own evidence points the same way.

| Flag | Label | Evidence | Confidence |
|---|---|---|---|
| 3 | First crafting unlocked (Workbench; PokoHex agrees) | set with the first furniture recipes | likely |
| 7, 27 | Poké Center PC + PC challenges (PokoHex agrees) | set together by one quest | likely |
| 15 | Rock Smash unlock (rock-blocked regions) | set when Rock Smash is learned; overrides the region test | likely |
| 19 | Always on | ROM bit 0 | sure |
| 56 | Surf unlocked | set when Surf is learned | sure |
| 57 | Glide unlocked | set when Glide is learned | sure |
| 63–66 | Bag upgrade 30 / 60 / 90 / 120 slots | game's bag size table; set in order by the Packing Tips shop event | sure |
| 107 | Handy bag bought (PokoHex: secondary bar) | set by the handy bag shop event; read next to the bag size | sure |
| 114 | Set after quest 46 (PokoHex: PC appraisal) | event 71 | likely |
| 129 | Tripod bought | set by the tripod shop event | sure |
| 142 | Cut / unused feature | checked in code, never set by anything | likely |
| 67–74, 125 | Cooking unlocks tied to the cutting board (67, 69, 71, 73), bread oven (68, 72) and frying pan (70, 74, 125) | set with those recipes; 74/125 are two tiers in code | likely |
| 79 | **Paint** specialty usable (PokoHex: Painting) | specialty 21 gate in code | sure |
| 77, 78, 132 | Painting extras (PokoHex: patterns, paint areas) | set by the same 641–800 quest group as 79 | likely |
| 84 | **Gather Honey** specialty usable | specialty 26 gate | sure |
| 99 | **Illuminate** specialty usable (toggled by quests) | specialty 22 gate | sure |
| 109 | **Yawn** specialty usable | specialty 27 gate; set with flag 61 by the "Yawn up a storm!" story quest | sure |
| 116 | **Engineer** specialty usable | specialty 24 gate | sure |
| 118 | **DJ** specialty usable | specialty 29 gate; set with the cannon/firework recipes | sure |
| 4, 7 | Pokémon Center unlocks (7 = PC per PokoHex) | set with tip "Healing at a Pokémon Center" | likely |
| 11 | Pokémon traces / habitat clues | set with tip "Pokémon Traces" | likely |
| 20, 53 | Stockpile / Spit Out | set with that tip | likely |
| 22 | Environment level shown | set with tip "Environment Level" | likely |
| 23, 24, 25 | Home brightness / temperature / humidity shown | tips; code reads them as 23 + i, i 0–2 | likely |
| 26, 37, 38 | Likes / food comfort / dislikes shown | tips | likely |
| 32, 33 | Storage specialty | tip | likely |
| 47 | Grow specialty | tip | likely |
| 86, 87, 88, 89, 151 | One milestone per area (Wasteland, Beach, Ridges, Skylands, Basin) | code reads the current area's flag; each is set by a quest of that area | sure (meaning of the milestone unknown) |
| 99 | Temporary state | set, cleared and set again by quests | sure |
| 102–105 | PP upgrade 1–4 | code; applied one at a time by the PP Up shop event | sure |
| 118 | Cannon / fireworks feature | set with those recipes | likely |
| 148 | Bubbly Basin unlock affecting objects (PokoHex: Dive) | set by Basin quest 805; switches object masks | likely |
| 149, 150 | Bubbly Basin access | set when the first Basin quest starts | likely |
| 160–249 | Unused | referenced nowhere | likely |

## Still unexplained

- Source known, meaning not: the script-only and preset-only flags listed in step 2b, and most
  quest-set flags without a co-unlock.
- Never set by anything: 80, 81, 83, 85, 94, 110–113, 142, 154 (80, 81 have ROM bits 0x06) and 160–249.
- In the test saves (mid-game, read only) the only script/preset-only flags that are on are 39, 98, 100.

## Next steps

1. Step 3: save diffs in Recompia for the "likely" rows (one action per save, diff against the save before).
2. Name the characters in talk triggers / 3565 (character id → resident) and what `S+0x6FABD9` holds,
   to place the remaining script flags (10, 14, 15, 18, 39, 40, 42–44).
3. Find what area 17 is.
