from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dnd_cli.game import Game
from dnd_cli.storage import (
    active_ironman_save,
    archive_ironman_victory,
    autosave_path,
    delete_active_ironman_save,
    delete_roster_hero,
    list_roster_heroes,
    list_hall_of_fame,
    load_roster,
    load_game,
    save_roster,
    save_game,
    save_slot,
    slot_path,
    upsert_roster_hero,
)


class StorageTests(unittest.TestCase):
    def test_ironman_defeat_save_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("dnd_cli.storage.save_root", return_value=root):
                game = Game(seed=9, run_mode="ironman")
                path = autosave_path(run_mode="ironman")
                save_game(game, path)
                self.assertTrue(active_ironman_save() and active_ironman_save().exists())
                delete_active_ironman_save()
                self.assertIsNone(active_ironman_save())

    def test_ironman_victory_archives_to_hall_of_fame(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("dnd_cli.storage.save_root", return_value=root):
                game = Game(seed=4, run_mode="ironman")
                save_game(game, autosave_path(run_mode="ironman"))
                archive_path = archive_ironman_victory(game)
                self.assertTrue(archive_path.exists())
                self.assertIsNone(active_ironman_save())
                self.assertEqual(len(list_hall_of_fame()), 1)

    def test_slot_save_rejects_ironman(self) -> None:
        game = Game(seed=7, run_mode="ironman")
        with self.assertRaises(ValueError):
            save_slot(game, "iron-path")

    def test_slot_path_slugifies_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("dnd_cli.storage.save_root", return_value=root):
                path = slot_path(" Boss Run!! ")
                self.assertEqual(path.name, "slot-boss-run.json")

    def test_save_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "save.json"
            game = Game(seed=2, run_mode="normal")
            game.gold = 10
            save_game(game, path)
            loaded = load_game(path)
            self.assertEqual(loaded.gold, 10)
            self.assertEqual(loaded.run_mode, "normal")

    def test_roster_save_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("dnd_cli.storage.profile_root", return_value=root):
                roster = [{"character_id": "pc-1234", "name": "Iris", "archetype": "Mage", "level": 2}]
                save_roster(roster)
                loaded = load_roster()
                self.assertEqual(len(loaded), 1)
                self.assertEqual(loaded[0]["character_id"], "pc-1234")

    def test_upsert_roster_hero_replaces_by_character_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("dnd_cli.storage.profile_root", return_value=root):
                hero = Game(seed=7).party[0]
                hero.character_id = "pc-test"
                hero.name = "Alden"
                upsert_roster_hero(hero)
                hero.level = 3
                upsert_roster_hero(hero)
                rows = list_roster_heroes()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["level"], 3)

    def test_delete_roster_hero_removes_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("dnd_cli.storage.profile_root", return_value=root):
                hero = Game(seed=7).party[0]
                hero.character_id = "pc-delete"
                upsert_roster_hero(hero)
                delete_roster_hero("pc-delete")
                rows = list_roster_heroes()
                self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
