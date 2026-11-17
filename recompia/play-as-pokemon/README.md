# Play as Pokemon for Recompia

The [Play as Pokemon](../../mods/play-as-pokemon/README.md) mod for [Recompia](https://github.com/Dittobyte/Recompia), the PC port of Pokopia. Turn into Ditto or any other Pokémon and walk around as it, even one that doesn't live in your town. Flying Pokémon can fly, and Pokémon with the Grow, Burn, Water or Generate specialty can use it.

**Game version 2.0.1 only** (the version Recompia needs). Windows and Linux (x86-64; the Linux library needs glibc 2.17 or newer). The Linux build is untested in game so far.

## Controls

| Press | Does |
|---|---|
| **ZL + L3** (left stick click) | Turn into the chosen Pokémon; press again to turn back |
| **F3** or **ZL + R3** | Open the list of all Pokémon and forms: Up / Down move, Left / Right move by 10, L / R jump to the next letter, A or Enter chooses, B or Esc closes |
| **ZL + D-pad Left / Right** | Pick the previous / next Pokémon (A to Z). While transformed you change as soon as you stop flicking through |
| **ZR** as a flying Pokémon | Take off, hold to rise |
| **ZL** while flying | Descend; keep holding it on the ground to land |
| **ZL + ZR** held while flying | Drop out of the air (press ZR again to take off) |
| **ZR** (Pokémon that can't fly) or **ZL + D-pad Down** (any) | Use the Pokémon's ability on what is in front of you |

Keyboard players can also set a key for "turn into", "turn back" and the ability, and change the F3 key, in the mod's settings.

## Install

1. Copy `recompia_play_as_pokemon-1.3.0.pkmod` into Recompia's `mods` folder (on Windows, next to `pkp.exe`), and remove an older version of it.
2. Open `PokopiaLauncher.exe`, go to **Mods**, and allow the new mod's code when it asks.
3. The first time these hook points are installed, the launcher rebuilds the game once before the next start (a few minutes). Updating from 1.1.x or 1.2.0-1.2.1 rebuilds once more, because 1.2.2 changes the hook points (1.3.0 keeps 1.2.2's). Then press **Play**.

The game log (`pkp.log`) should show `play_as_pokemon 1.3.0 started` and `[play_as_pokemon] ready: ZL + L3 turns into Ditto and back, ...`.

## Choosing the Pokémon

In the launcher's **Mods** page, or in game with **F1 → Mods**:

- **Which list below picks the Pokémon**: `A to L`, `M to Z` or `Experimental forms`. The in-game menu shows at most 256 names in one list, so the Pokémon are split in two.
- **Pokémon, A to L** / **Pokémon, M to Z**: the Pokémon. Default: Ditto.
- **Experimental form**: story objects and the shapes Ditto takes for its moves. The two towers are far larger than the camera expects.

A change made in F1 while you are transformed turns you into the new Pokémon at once. The list and ZL + D-pad Left / Right pick one for this session only: the settings stay as they are.

The other settings switch flying, the Left / Right picking and the name message off.

## Abilities

A transformed Pokémon can use its town specialty: press **ZR**, or **ZL + D-pad Down** (flying Pokémon keep ZR for flying). It plays the Pokémon's own specialty animation and then acts on what is in front of you:

| Ability | Pokémon | Does |
|---|---|---|
| **Grow** | Bulbasaur, Oddish, Snivy, Rowlet, ... (26) | The crops and plants in front of you grow a stage, each once, as when a resident uses Grow |
| **Burn** | Charmander, Vulpix, Torchic, Litwick, ... (34) | The object in front of you is burnt: a campfire lights |
| **Water** | Squirtle, Piplup, Marill, Lapras, ... (37) | Sludge that is not bubbled yet (Bleak Beach) gets Bubbled, with the Bubble animation. Otherwise the Water Gun: it waters soil and plants and washes bubbled sludge away |
| **Generate** | Pikachu, Pawmi, Mareep, Magnemite, ... (27) | The light or machine in front of you is powered |

The setting **Ability** is `Auto` by default: each Pokémon uses its own specialty. Pick Grow, Burn, Water or Generate there to use that one with any Pokémon. A Pokémon without one of these says so when you press the button. Flying Pokémon with one of these (Charizard: Burn and Fly) fly with ZR and use the other with ZL + D-pad Down.

Burn, Generate and Bubble act as one of the Pokémon living in the area (the game only lets a town Pokémon light a campfire), so a Pokémon must live where you are. The other specialties (Chop, Crush, Recycle, Search, ...) are not in yet: the game does those inside each Pokémon's job routine, not as an effect the mod can call. Which Pokémon has which specialty comes from the lists on pokopialab.com.

Press the button once you have finished transforming: a press during the transformation is ignored (`busy` in `pkp.log`).

`pkp.log` notes each use: `ability Grow: animation started, cell in front (x, y, z) ...` and `worked at` or `nothing at`.

## Talking to Pokémon

Talking to most Pokémon makes the game turn you back into your usual character: the conversation needs it (the Pokémon that comment on your transformation don't). Since 1.2.2 the mod lets that happen and turns you back into your Pokémon when the conversation is over and you walk off.

Crafting, sitting and opening doors don't show their button prompts while you're transformed. Turn back with ZL + L3 for those: a Pokémon has no animations for them anyway.

If the game changes your form any other way, the mod turns you into your Pokémon again half a second later. If that keeps happening (more than 3 times in 20 seconds), the mod leaves it and you count as turned back: ZL + L3 transforms you again.

`pkp.log` notes each of these (`an interaction turns the player human`, `the interaction is over`, `the game turned the player into form ...`, `the game asked to turn the player into form ...`), plus `trace` lines of every form change while transformed. Please include those lines when you report a problem.

## Link Play

The mod changes gameplay, so every player in a Link Play session needs it.

Your Pokémon is only shown on your own screen: the other players still see your usual character, standing still. Since 1.2.2 the mod only touches your own character. Before, a transformed player's game could also act on the other players' characters, for example by stopping them from turning back.

While a Link Play session is open, `pkp.log` also gets `remote trace` and `remote model` lines for the other players' characters. When one player transforms, the other players' logs show whether the change reached their game. Please send both players' logs.

## How it works

The emulator version is an IPS patch plus a cheat file. Recompia runs the game as native code, so neither works there. This version is a Modtopia code mod (`mod.dll`):

- six of the IPS's eight code patches are `take_over` hook points at the same game instructions (`mod.toml` lists them with the instruction each one expects; the two small-space ground writers are not needed here since 1.2.2), plus one more (`to_human`, the game's "turn the player human for an interaction");
- the cheat's button combos and memory writes run in the player's per-frame hook, with the player's controller read through Modtopia (`pad_read`);
- the animation loading (so non-resident Pokémon are not invisible) calls the game's own package and motion-set functions (`call_guest`), as the patch did;
- abilities: the residents' specialty actions (Burn 700, Water 703, Bubble 705, Grow 706, Generate 709) only animate when the player asks for them, because the game applies their effect for residents only. So the mod plays the action for the animation and calls the effect itself on the cell in front of the player (found as the game finds the target of the player's own moves): Grow `main+0x1F1200`, Burn and Generate `main+0x77CEA0` (the object at the cell, as a town Pokémon), Bubble the handler of action 705, the Water Gun's hit `main+0x3694C0`.

A test slot in unused game memory (`main+0x3D14D00`, used by nothing in normal play) lets a script on the PC run single ability steps; it does nothing unless a script writes its marker.

The source is `src/play_as_pokemon.c`. `include/modtopia/modtopia.h` is the Modtopia SDK header (MIT, see the LICENSE beside it).

## Build

```bash
py recompia\play-as-pokemon\build.py --zig "C:\path\to\recompia\tools\build\zig\zig.exe"
```

It writes `src/forms.h` and `mod.toml` from `mods/play-as-pokemon/pokemon.json` and `experimental.json`, compiles `mod.dll` with zig (Recompia ships one under `tools/build/zig`) and `mod.so` for Linux (with zig if it has Linux headers, else with clang + ld.lld: `--clang PATH`, e.g. llvm-mingw's), and packs `dist/recompia_play_as_pokemon-<version>.pkmod` with a `.sha256` file beside it.
