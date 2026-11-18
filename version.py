"""App version, read by the window (update check, What's New) and by PokopiaEditor.spec (exe file version).

Bump this before building a release; the GitHub release tag should be v<VERSION>.
Rewrite WHATS_NEW for each release: it is shown once, the first time that version is opened."""
VERSION = (1, 8, 0)
VERSION_STR = '.'.join(map(str, VERSION))

WHATS_NEW = [
    ('Function flags', 'The Advanced page now lists every flag with what it does, grouped by topic, with a switch '
                       'and a tag for how sure the description is. Search and filters included.'),
    ('More flags described', '68 flags now have a description, up from 38: specialties, bag and PP upgrades, '
                             'purchases, area milestones and more.'),
]
