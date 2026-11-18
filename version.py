"""App version, read by the window (update check, What's New) and by PokopiaEditor.spec (exe file version).

Bump this before building a release; the GitHub release tag should be v<VERSION>.
Rewrite WHATS_NEW for each release: it is shown once, the first time that version is opened.
WHATS_NEW_PAGE is the page its button opens (None for no button)."""
VERSION = (1, 9, 0)
VERSION_STR = '.'.join(map(str, VERSION))

WHATS_NEW = [
    ('Island Map editor', 'Move, place and delete objects, paint paths, and shape the ground.'),
    ('One-click habitats', 'Build any of 252 habitats with the fewest items they need.'),
    ('Better map', 'Real block textures, labelled areas, a mini map and look inside.'),
    ('Recompia saves', 'Found automatically; choose which save opens at start.'),
    ('Function flags', 'The Advanced page lists every flag with a description, grouped by topic.'),
]
WHATS_NEW_PAGE = 'Island Map'
