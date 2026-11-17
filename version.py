"""App version, read by the window (update check, What's New) and by PokopiaEditor.spec (exe file version).

Bump this before building a release; the GitHub release tag should be v<VERSION>.
Rewrite WHATS_NEW for each release: it is shown once, the first time that version is opened."""
VERSION = (1, 6, 0)
VERSION_STR = '.'.join(map(str, VERSION))

WHATS_NEW = [
    ('Unlimited Crafting Storage Range', 'A new mod: crafting stations use the items in every storage box, chest and '
                                         'crate you have placed, at any distance. Install it on the Mods page.'),
    ('Recompia', 'The mod is also available for Recompia on Windows and Linux, as a .pkmod on the release page.'),
]
