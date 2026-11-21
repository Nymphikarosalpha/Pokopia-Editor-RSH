# RSH features and current limitations

## Special Pokémon experimental encounter (v0.2.1)

The editor automatically identifies known special/legendary Pokémon (for example **Mew and Mewtwo**) from its resident IDs and species names. The action selector offers **Experimental encounter (ID−4; automatic special detection)**. For these species it lists an **existing** habitat as a technical UID/position anchor instead of inventing a species habitat. A matched anchor does **not** mean that the game accepts that habitat as Mew's or Mewtwo's real habitat.

Recommended settings are visible in the Resident + Habitat Studio for normal Pokémon, E-series event Pokémon, legendary/mythical encounters, and Pokémon with no reliable recipe mapping. The **Which settings for which Pokémon?** help button describes the options.

The editor refuses to write when there is no usable anchor, no free compatible encounter row, or an unsupported stage layout. It creates and verifies a ZIP backup first and stages the write in the undoable island journal. Only press Ctrl+S on a disposable testing save. **There is no verified direct spawn/unlock for Mew, Mewtwo or any other legendary Pokémon.**


Pokopia Editor RSH builds on [cycalo/Pokopia-Editor](https://github.com/cycalo/Pokopia-Editor). Original features and licensing are retained.

## Resident and habitat tools

- Add/update resident registry entries, friendship and home assignments.
- Remove a resident registry entry (experimental; independent world NPC objects may remain).
- Assign existing habitats or place a new habitat using the Island Map.
- Select available islands from the loaded save; names are read from the save.
- Use a bundled resident-ID-to-habitat catalog, including form-specific mappings, without requiring an online lookup.
- Explicitly use a manual habitat override when no verified mapping exists. This does not establish a spawn.

## Verified mapping coverage (catalog audit)

The current editor data has 402 named resident records. Of these, 350 map to buildable Habitat Dex recipes, 17 have an explicit empty mapping, and 35 cannot be mapped reliably with the available source. The original editor includes 252 habitat recipes. Numbers describe resident records, not unique Pokémon.

Some cases cannot be mapped automatically: the original editor lacks a recipe for the referenced Jellicent Marine teatime habitat; special or internal NPC entries are deliberately not guessed.

## Event habitat workflow

- **Build event habitat on the map (no quest completion)**: choose an E-series habitat, optionally enable the unverified manual E-series override, confirm, click a valid location on the Island Map, and save.
- **Prepare event materials in bag only**: add missing materials for a supported E-series habitat, without building, spawning or changing event progression.
- Optional resident registration creates/updates save data but is not the same as spawning a visible NPC.
- An explicit unverified event-recipe choice means only "build this habitat". It is not a claim that the chosen species can be obtained from it.

**Not supported:** reliably marking limited-time events completed, bypassing game encounter gates, or forcibly spawning legendary/story/event NPCs. These mechanisms have not been established and are not advertised as working.

### Normal and special Pokémon on non-STGDAT01 islands

Starting with v0.2.4, the existing-habitat position-anchor ID−4 workflow is offered to ordinary Pokémon as well as special Pokémon on recognized G00/STGDAT## stage files. The original new-habitat+ID−4 workflow stays restricted to STGDAT01. An empty anchor list means no **registered and valid** habitat was found; it cannot be replaced by an arbitrary fabricated UID. Unknown encounter semantics are not automatically established by a matching binary layout. Close the emulator and test on a save copy only.

## Experimental encounter tool

The separate ID-minus-four experiment writes an unverified stage encounter field on checked layouts. Its mapping is a hypothesis, not proof that a particular Pokémon will appear. Avoid using it on valuable saves.

## Lichii and other emulators

Lichii is included in running-process detection and in standard/nearby portable save discovery. Use **Open → Browse for a folder** for custom locations. End-to-end testing under every Lichii build is not complete.

## Safety

Close the emulator, make a backup, and review the affected island before saving. Habitat placement is experimental. No game keys, ROMs, save dumps or copyrighted game assets are distributed by this fork beyond materials already present in the upstream open-source project.

### Palette Town / STGDAT00 (experimental candidate)

Earlier versions restricted ID−4 to STGDAT01 by filename. The special-Pokémon path now lists existing anchors for G00/STGDAT00..99 stage files, including Palette Town, but an eligible file name **does not prove that the 32-byte bytes represent a spawn event**. The island must pass existing header/version/decompressed-data checks; the event area must have an unused compatible record; the selected habitat entry must match the recorded UID/type and bounds. No unknown occupied rows are overwritten. Use a disposable save only.

The dropdown no longer repeats **Remove resident** or **Remove home assignment**, which remain available in the Residents panel.
