<!-- RSH fork overview -->
## About Pokopia Editor RSH

**Pokopia Editor RSH (Resident · Spawn · Habitat)** is a community fork of
[cycalo/Pokopia-Editor](https://github.com/cycalo/Pokopia-Editor).
It retains the original save editor and adds resident, habitat and experimental
encounter tools. The upstream Git history, original author notices and
[GNU GPL-3.0 license](LICENSE) are preserved.

### RSH additions

| Feature | Description | Status |
| --- | --- | --- |
| Resident management | Add or update resident registry entries, friendship values and meeting dates | Preview |
| Resident removal | Remove a resident's save registry entry and home assignment while retaining the Pokédex entry | Experimental |
| Home assignment | Link residents to existing habitats or remove a home assignment | Preview |
| Habitat placement | Build available habitat recipes and associate them with residents on supported islands | Preview |
| Multiple islands | Choose among supported islands found in the loaded save; island names are read from the save | Preview |
| Habitat matching | Additional offline species-to-habitat mappings and optional manual selection | Preview |
| Encounter records | Optional experimental habitat-linked encounter records using an unverified ID mapping | Experimental |
| Event habitat items | Prepare supported event items and catalog entries without playing the original distribution event | Preview |
| Lichii integration | Recognize Lichii processes and search standard and nearby portable Lichii save locations | Preview |

> [!IMPORTANT]
> **This is a development preview, not a stable release.** A resident record or
> habitat assignment does not guarantee that a Pokémon appears as a visible NPC.
> Resident removal may leave separately stored world NPCs. Event item preparation
> does **not** mark story quests or limited-time events completed. Direct spawning
> of legendary and special Pokémon is not yet implemented or verified.
> Always close the emulator and back up your save before using experimental tools.

**Compatibility:** The editor can browse manually selected saves and looks for
Lichii saves in standard Windows user-data directories, as well as common nearby
portable `user/nand` layouts. Portable installations in other locations can be
opened using **Open → Browse for a folder**. The full RSH feature set has not
been validated on every emulator and game version.

**Windows download:** The latest RSH preview executable is available on the
[Pokopia Editor RSH preview release](https://github.com/Nymphikarosalpha/Pokopia-Editor-RSH/releases/tag/rsh-preview)
when the release build has completed. GitHub Actions also retains a ZIP artifact
for each successful workflow run. The original project's releases are upstream
builds and do **not** include RSH additions.

**Details:** [Feature guide and limitations](docs/FORK_FEATURES.md) ·
[Changes](CHANGELOG_FORK.md) · [Build guide](docs/BUILD_WINDOWS.md).

---
