"""App version, read by the window (update check, What's New) and by PokopiaEditor.spec (exe file version).

Bump this before building a release; the GitHub release tag should be v<VERSION>.
Rewrite WHATS_NEW for each release: it is shown once, the first time that version is opened.
WHATS_NEW_PAGE is the page its button opens (None for no button)."""
VERSION = (1, 9, 1)
VERSION_STR = '.'.join(map(str, VERSION))

WHATS_NEW = [
    ('Play as Pokemon 1.6', 'Fixes the crash in co-op with three or four players.'),
    ('Reinstall the mod', 'The Mods page shows Play as Pokemon as outdated: install it again. Everyone in a Link Play session needs 1.6.'),
    ('Nothing else changed', 'This release only updates the Play as Pokemon mod.'),
]
WHATS_NEW_PAGE = 'Mods'
