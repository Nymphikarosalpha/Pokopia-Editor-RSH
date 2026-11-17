"""App version, read by the window (update check, What's New) and by PokopiaEditor.spec (exe file version).

Bump this before building a release; the GitHub release tag should be v<VERSION>.
Rewrite WHATS_NEW for each release: it is shown once, the first time that version is opened."""
VERSION = (1, 7, 0)
VERSION_STR = '.'.join(map(str, VERSION))

WHATS_NEW = [
    ('Pokémon abilities', 'Press ZR (or ZL + D-pad Down) as a Pokémon to use Grow, Burn, Water or Generate. '
                          'Update Play as Pokemon on the Mods page.'),
    ('Recompia', 'Play as Pokemon 1.4.0 has the abilities too, and other Link Play players now see your Pokémon.'),
]
