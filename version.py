"""App version, read by the window (update check, What's New) and by PokopiaEditor.spec (exe file version).

Bump this before building a release; the GitHub release tag should be v<VERSION>.
Rewrite WHATS_NEW for each release: it is shown once, the first time that version is opened."""
VERSION = (1, 7, 0)
VERSION_STR = '.'.join(map(str, VERSION))

WHATS_NEW = [
    ('Pokémon abilities', 'Play as Pokemon 1.3: as a Pokémon with the Grow, Burn, Water or Generate specialty, press ZR (or ZL + '
                          'D-pad Down) to use it on what is in front of you: crops grow, campfires light, soil gets watered, '
                          'sludge gets Bubbled and washed, lights and machines get powered. Update the mod on the Mods page.'),
    ('Recompia', 'The abilities are in the Recompia version too (1.3.0, a .pkmod on the release page).'),
]
