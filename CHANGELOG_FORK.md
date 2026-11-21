# RSH fork changelog

This changelog covers changes to [Pokopia Editor RSH](https://github.com/Nymphikarosalpha/Pokopia-Editor-RSH), a GPL-3.0 fork of [cycalo/Pokopia-Editor](https://github.com/cycalo/Pokopia-Editor). The upstream history and license remain intact.

## Unreleased — Multi-island habitat backup fix (2026-11-21)

### Fixed
- Fixed **Build habitat + register resident** failing at the backup step on islands using `STGDAT00.BIN`, `STGDAT02.BIN`, or other valid stage filenames. Previously the RSH pre-edit backup incorrectly required `STGDAT01.BIN` for every island.
- Validates the selected stage against the opened save's `G00/STGDAT##.BIN` list, preserving protection against wrong-save paths and missing files.
- Validates each whole-save ZIP backup before allowing island editing to continue, and removes incomplete archives on failure.
- Adds offline regression checks for multiple islands, including negative path-validation tests.

### Limits
- This fixes a failed pre-edit backup check. It does **not** establish that every habitat or Pokémon encounter will behave identically on every island.
- The experimental **ID−4 encounter record** remains restricted to its previously examined stage layout. Other islands can use normal habitat building and resident home assignment, not that unverified encounter method.


## Unreleased – Resident habitat catalog and event workflow fixes (preview)

### Fixed

- Audited **402 named resident records** against the available habitat reference and the original editor's **252 built-in recipes**. A bundled, versioned resident-ID-to-Habitat-Dex table replaces ambiguous name-only lookups in resident-specific actions.
- **350 resident records** have a mapped, buildable recipe. **17 records** have an explicit empty/no-buildable-habitat mapping; **35 records** cannot be mapped reliably from the available reference and are deliberately left unmapped. These are record counts, not distinct Pokémon species.
- Distinguishes Toxtricity Amped and Low Key, Paldean Wooper, East/West Shellos and Gastrodon, Tatsugiri forms, and gendered Frillish and Jellicent where the resident data share generic names.
- Makes manual habitat selection available in both event modes, not only normal resident/habitat modes. In event modes it is restricted to **E-series event recipes** and requires an explicit unverified-choice confirmation.
- Resolves validation and selection against the same candidate recipes, avoiding a habitat being offered in the UI and then rejected solely because it is an event override.
- Keeps the normal **Build habitat + register resident** flow selected by default. This builds and assigns a home but does not force the Pokémon to appear in the world.

### Changed

- Renamed the former misleading event-bypass option into two accurate operations:
  - **Build event habitat on the map (no quest completion)**: choose a supported E-series recipe and place its objects on a supported island; optionally write a resident registry entry.
  - **Prepare event materials in bag only**: add missing recipe items to inventory and update discovered catalog entries without building or changing world state.
- Events with no verified recipe mapping are not silently assigned an unrelated habitat. A user may explicitly select an unverified event recipe; doing so does **not** unlock or complete event quests.
- Updated English-only, neutral interface messages explaining selection limitations and save-backup requirements.

### Validation

- Source compilation and **21 offline tests** pass, with two recipe-catalog integration checks reserved for the full upstream checkout/Windows CI environment.
- These are **source-level checks**. A successful test does not establish in-game event activation, NPC appearance, or working event-quest bypass.

### Known limitations

- The game’s limited-time event completion flags and direct visible-NPC spawn mechanism are not established. **This update does not bypass those game checks.**
- Resident registry editing and habitat placement do not guarantee an encounter or a persistent world NPC.
- Some internal NPC components and expansion/event forms have no reliable normal-habitat mapping; unavailable recipes remain unavailable.
- The upstream recipe list currently lacks the cited **Marine teatime** habitat for Jellicent, so the editor will not fabricate a buildable entry.
- Close the emulator before editing and keep a save backup.

## 2026-11-21 – Form-specific habitat mapping (preview)

- Toxtricity Amped Form (resident ID 143): Amped rock stage (Habitat Dex #189).
- Toxtricity Low Key Form (resident ID 266): Low-key rock stage (Habitat Dex #190).
- Separate form labels and offline regression checks.

## Initial RSH development preview

- Resident registration and save-registry removal tools.
- Resident home linking and multi-island habitat placement.
- Experimental encounter record editing on restricted stage layouts.
- Event material preparation, offline/manual habitat selection, and Lichii save discovery.
- English-language fork documentation and Windows release workflow.

The project is distributed under GNU GPL-3.0; upstream attribution and copyright notices are preserved.
