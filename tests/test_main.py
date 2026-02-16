from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest.mock import patch

import dnd_cli.main as main


class MainTests(unittest.TestCase):
    def test_default_command_without_subcommand_does_not_require_hero(self) -> None:
        argv = ["DND"]
        captured: dict = {}

        def fake_run_game(game, creation_enabled=False, seed=7):
            captured["creation_enabled"] = creation_enabled
            captured["run_mode"] = game.run_mode

        with patch("sys.argv", argv):
            with patch("dnd_cli.main.save_game", return_value=None):
                with patch("dnd_cli.main.autosave_path", return_value=Path("/tmp/autosave.json")):
                    with patch("dnd_cli.main._run_game", side_effect=fake_run_game):
                        main.run()
        self.assertTrue(captured.get("creation_enabled"))
        self.assertEqual(captured.get("run_mode"), "normal")

    def test_roster_command_prints_heroes(self) -> None:
        argv = ["DND", "roster"]
        with patch("sys.argv", argv):
            with patch("dnd_cli.main.list_roster_heroes", return_value=[{"character_id": "pc-1", "name": "Iris", "archetype": "Mage", "level": 3}]):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                    main.run()
        output = mock_out.getvalue()
        self.assertIn("Roster Heroes:", output)
        self.assertIn("pc-1", output)

    def test_new_with_hero_uses_roster_party_and_skips_creator(self) -> None:
        argv = ["DND", "new", "--hero", "pc-1"]
        captured: dict = {}

        def fake_run_game(game, creation_enabled=False, seed=7):
            captured["creation_enabled"] = creation_enabled
            captured["party"] = game.party

        with patch("sys.argv", argv):
            with patch("dnd_cli.main.load_roster", return_value=[{"character_id": "pc-1", "name": "Iris", "archetype": "Mage"}]):
                with patch("dnd_cli.main.save_game", return_value=None):
                    with patch("dnd_cli.main.autosave_path", return_value=Path("/tmp/autosave.json")):
                        with patch("dnd_cli.main._run_game", side_effect=fake_run_game):
                            main.run()
        self.assertFalse(captured.get("creation_enabled", True))
        self.assertEqual(len(captured.get("party", [])), 3)
        self.assertEqual(captured["party"][0].character_id, "pc-1")

    def test_host_with_hero_passes_party_to_host_service(self) -> None:
        argv = ["DND", "host", "--hero", "pc-1", "--code", "ABCD", "--name", "Host", "--chat-mode", "text_18_plus"]
        captured: dict = {}

        class FakeHostService:
            def __init__(self, bind, port, code, mode, party=None, chat_mode="reactions_only"):
                captured["party"] = party
                captured["chat_mode"] = chat_mode
                self.error = None

            def start(self):
                return None

            def wait_until_ready(self, timeout):
                return True

        with patch("sys.argv", argv):
            with patch("dnd_cli.main.load_roster", return_value=[{"character_id": "pc-1", "name": "Iris", "archetype": "Mage"}]):
                with patch("dnd_cli.main.HostService", FakeHostService):
                    with patch("dnd_cli.main._run_online_ui", return_value=None):
                        with patch("sys.stdout", new_callable=io.StringIO):
                            main.run()
        self.assertEqual(len(captured.get("party", [])), 3)
        self.assertEqual(captured["party"][0].character_id, "pc-1")
        self.assertEqual(captured["chat_mode"], "text_18_plus")


if __name__ == "__main__":
    unittest.main()
