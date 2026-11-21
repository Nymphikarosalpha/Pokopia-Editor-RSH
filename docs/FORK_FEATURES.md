# Fork features and limitations

This fork extends [cycalo/Pokopia-Editor](https://github.com/cycalo/Pokopia-Editor), retaining its existing save editor and user interface.

## Added controls

- Resident creation and updates based on known save structures.
- Resident removal from the common save's resident registry and associated home assignment. Independent world NPC objects are **not** removed by this operation.
- Resident home linking and unlinking, with a selectable island and recorded habitat.
- Habitat placement and an **experimental** 32-byte encounter record for compatible island save layouts. The experimental ID offset is **not** a universal species selection guarantee.
- Event item preparation for certain known event habitats, including Milotic's event items, without asserting event-story completion.
- Offline habitat fallback mappings and manual habitat selection where appropriate.

## What is not established

- Spawning arbitrary legendary or special Pokémon as visible, persistent NPCs without their story encounter.
- Marking all limited-time event quests completed or reliably bypassing all event gates.
- Guaranteed species selection via the experimental encounter record.
- Removing all persisted NPC world objects when a resident registry entry is cleared.

## Emulator support, including Lichii

- Standard Lichii installations: look for user data in the usual Windows AppData roots, in addition to the upstream Yuzu-family emulators.
- Common portable Lichii installations: check nearby `user/nand` directories, including Lichii-named folders on the Desktop and in Downloads.
- Custom Lichii installations: use **Open → Browse for a folder** and select the game save directory (or an enclosing folder).
- While the app is open, a running `lichii.exe` is included in the emulator-process warning.

The Lichii detection paths have been added to the source; a full Windows/Lichii end-to-end test is still required before marking this integration stable.

## Safety and compatibility

- Close the emulator before editing saves; keep external backups of each save.
- Experimental stage editing has strict structural checks and is restricted to save layouts examined during development. It can reject unsupported saves.
- Do not assume a saved resident record is sufficient to create a visible world NPC.
- Emulator support and game-version compatibility should be tested before publishing a stable release.
- No game files, keys, save dumps or ROM assets are distributed in this repository.

## Current status

Development preview. Save-editing actions were exercised on sample saves, and selected in-game encounter behavior was reported during testing. A complete regression suite across supported emulators and game versions has **not** been completed.

This project is an independent community modification and is not affiliated with Nintendo, The Pokémon Company or Koei Tecmo.
