# Craft from Storage

Crafting stations (the workbench and the other crafting stations) normally only use storage boxes that stand right
next to them. With this mod they use the items in **every** storage box, chest and crate you have placed, at any
distance. Crafting takes the materials out of whichever box holds them, and from your bag if the boxes run short.

No buttons: install it and craft as usual.

## Install

- **Emulator (Eden, Yuzu and forks):** copy the `0400A3A01EE4C000` folder into the emulator's `load` folder
  (right-click the game → Open Mod Data Location), then tick **Craft from Storage** in the game's
  Properties → Add-Ons.
- **Switch with Atmosphère:** copy the `atmosphere` folder to the root of the SD card.

It works together with Play as Pokemon.

## Notes

- Made for Pokopia 2.0.0 (update 655360, build 76A489F3BD3642FA). On other versions it is not applied.
- Counts storage boxes, chests, crates and big storage boxes. Other furniture with slots is left alone.
- While you use a crafting station, a box far away may show as in use.
- Not tested in multiplayer.

## How it works

The game keeps a short list of the boxes a station may use, filled by a scan of the blocks right around the
station (main+0x7514E0, at most 4 boxes). After that scan the patch turns the list into "every box of this kind"
entries, and wraps the two functions that turn a list entry into item slots (main+0x5B1C84 for counting,
main+0x2EE4BC for checking and taking) so they cover all placed boxes. The code lives in unused padding after the
game's code (main+0x2749C00), clear of Play as Pokemon's patch.
