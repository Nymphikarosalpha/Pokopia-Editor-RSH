"""App version, read by the window (update check, What's New) and by PokopiaEditor.spec (exe file version).

Bump this before building a release; the GitHub release tag should be v<VERSION>.
Rewrite WHATS_NEW for each release: it is shown once, the first time that version is opened."""
VERSION = (1, 7, 0)
VERSION_STR = '.'.join(map(str, VERSION))

WHATS_NEW = [
    ('Play as Pokemon 1.5', 'Abilities (ZR or ZL + D-pad Down: Grow, Burn, Water, Generate), talking while transformed, '
                            'Link Play (others see your Pokémon), smoother flying. Update it on the Mods page.'),
    ('Recompia', 'Play as Pokemon 1.5.0 has the same, and fixes ending a Link Play session while transformed.'),
]
