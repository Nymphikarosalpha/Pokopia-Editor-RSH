# Unlimited Crafting Storage Range for Recompia

The [Unlimited Crafting Storage Range](../../mods/unlimited-crafting-storage-range/README.md) mod for
[Recompia](https://github.com/Dittobyte/Recompia), the PC port of Pokopia. Crafting stations use the items in **every**
storage box, chest and crate you have placed, at any distance, not only the boxes right next to them. Crafting takes the
materials out of whichever box holds them, and from your bag if the boxes run short.

No buttons and no settings: install it and craft as usual.

**Game version 2.0.1 only** (the version Recompia needs). Windows and Linux (x86-64; the Linux library needs glibc 2.17
or newer).

## Install

1. Copy `recompia_unlimited_crafting_storage_range-1.0.0.pkmod` into Recompia's `mods` folder (on Windows, next to
   `pkp.exe`).
2. Open `PokopiaLauncher.exe`, go to **Mods**, and allow the new mod's code when it asks.
3. The mod adds new hook points, so the launcher rebuilds the game once before the next start (a few minutes). Then
   press **Play**.

The game log (`pkp.log`) should show
`[unlimited_crafting_storage_range] ready: crafting stations use every storage box, at any distance`.

It works together with Play as Pokemon.

## Notes

- Counts storage boxes, chests, crates and big storage boxes. Other furniture with slots is left alone.
- While you use a crafting station, a box far away may show as in use.
- Not tested in Link Play. The mod changes gameplay, so every player in a session should have it.

## How it works

The emulator version is an IPS patch. Recompia runs the game as native code, so that does not work there. This version
is a Modtopia code mod (`mod.dll` / `mod.so`): each of the IPS's four code patches is a `take_over` hook point at the
same game instruction (`mod.toml` lists them with the instruction each one expects).

- `scan_local` / `scan_shared`: right after the game's scan of the blocks around the station, the station's box list
  is turned into "every box of this kind" entries, and one box of a kind is added when none stands next to the station.
- `range_count` / `range_take`: the two functions that turn a list entry into item slots give the slots of every
  placed box of the kind for those entries.

The source is `src/unlimited_crafting_storage_range.c`.

## Build

```bash
py recompia\unlimited-crafting-storage-range\build.py --zig "C:\path\to\recompia\tools\build\zig\zig.exe" --clang "C:\path\to\llvm-mingw\bin\clang.exe"
```

It writes `mod.toml`, compiles `mod.dll` with zig and `mod.so` for Linux (with zig if it has Linux headers, else with
clang + ld.lld), and packs `dist/recompia_unlimited_crafting_storage_range-<version>.pkmod` with a `.sha256` file and a
`.zip` (the package and this README) beside it. It reuses the build helpers of `../play-as-pokemon/build.py`.
