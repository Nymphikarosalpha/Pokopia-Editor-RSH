"""Source-level checks for the neutral English RSH preview."""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "pokopia_gui_fork.py"


class LocalizationTests(unittest.TestCase):
    def test_source_parses(self):
        ast.parse(SOURCE.read_text(encoding="utf-8"))

    def test_no_personal_island_names(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("Nymphtopia", text)
        self.assertNotIn("Nymphikarosalpha", text)

    def test_rsh_interface_is_english(self):
        source = SOURCE.read_text(encoding="utf-8")
        german_words = (
            "Bewohner", "Sicherung", "Spielstand", "auswählen", "hinzugefügt",
            "aktualisiert", "Hinweis: Das", "Entfernen", "Wohnort", "Habitatdaten", "vorhanden",
            "Nicht genügend", "Event-Slot", "Event-Pokémon", "Strg+S", "Event-Umgehung", "Übernehmen",
        )
        for word in german_words:
            with self.subTest(word=word):
                self.assertNotIn(word.casefold(), source.casefold())
        for label in ("Remove resident from save", "Register resident without a habitat",
                      "Build habitat + register resident", "event quests", "Ctrl+S"):
            with self.subTest(label=label):
                self.assertIn(label, source)


if __name__ == "__main__":
    unittest.main()
