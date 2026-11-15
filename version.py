"""App version, read by the window (update check, What's New) and by PokopiaEditor.spec (exe file version).

Bump this before building a release; the GitHub release tag should be v<VERSION>.
Rewrite WHATS_NEW for each release: it is shown once, the first time that version is opened."""
VERSION = (1, 5, 0)
VERSION_STR = '.'.join(map(str, VERSION))

WHATS_NEW = [
    ('Collection page', 'Complete the Pokédex, the Habitat Dex, crafting recipes and cooking recipes: pick single '
                        'entries or finish a whole list with one click.'),
    ('Items, records and artifacts', 'Fill the item list, Human Records and Ancient Artifacts the same way.'),
    ('Photo frames and filters', 'Unlock every frame and filter for the camera on the Collection page.'),
    ('Play as Pokemon 1.2', 'New buttons: ZL + L3 (left stick click) turns you into the Pokémon and back, and '
                            'ZL + D-pad Left / Right pick the previous / next Pokémon while playing. Press Update '
                            'on the Mods page.'),
    ('Upgrades and Life Coins', 'Switch on bag and PP upgrades, Jump, painting and Poké Center PC features, and set '
                                'your Life Coins. Keep a backup: the upgrade switches are new and lightly tested.'),
]
