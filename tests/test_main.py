from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest.mock import patch

import dnd_cli.main as main


class MainTests(unittest.TestCase):
    def test_default_launcher_select_new_runs_game(self) -> None:
        argv = ["DND"]
        captured: dict = {}

        def fake_run_game(game, creation_enabled=False, seed=7):
            captured["creation_enabled"] = creation_enabled
            captured["run_mode"] = game.run_mode

        with patch("sys.argv", argv):
            with patch("dnd_cli.main.load_tutorial_state", return_value={"seen": True}):
                with patch("dnd_cli.main._run_launcher", side_effect=["new", "quit"]):
                    with patch("dnd_cli.main._run_launcher_form", return_value={}):
                        with patch("dnd_cli.main.save_game", return_value=None):
                            with patch("dnd_cli.main.autosave_path", return_value=Path("/tmp/autosave.json")):
                                with patch("dnd_cli.main._run_game", side_effect=fake_run_game):
                                    main.run()
        self.assertTrue(captured.get("creation_enabled"))
        self.assertEqual(captured.get("run_mode"), "normal")

    def test_default_launcher_quit_exits_cleanly(self) -> None:
        argv = ["DND"]
        with patch("sys.argv", argv):
            with patch("dnd_cli.main.load_tutorial_state", return_value={"seen": True}):
                with patch("dnd_cli.main._run_launcher", return_value="quit"):
                    with patch("dnd_cli.main._run_launcher_form", return_value={}):
                        with patch("dnd_cli.main._run_game") as run_game:
                            main.run()
        run_game.assert_not_called()

    def test_new_subcommand_still_runs_without_hero(self) -> None:
        argv = ["DND", "new"]
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

    def test_launcher_character_create_routes_to_online_create(self) -> None:
        argv = ["DND"]
        try:
            import dnd_cli.online as online
        except ModuleNotFoundError:
            self.skipTest("online dependencies not installed")
            return

        with patch("sys.argv", argv):
            with patch("dnd_cli.main.load_tutorial_state", return_value={"seen": True}):
                with patch("dnd_cli.main._run_launcher", side_effect=["character_create", "quit"]):
                    with patch(
                        "dnd_cli.main._run_launcher_form",
                        return_value={"name": "Iris", "archetype": "Mage"},
                    ):
                        with patch.object(online, "create_character", return_value={"name": "Iris", "archetype": "Mage", "slot_index": 0}):
                            with patch("dnd_cli.main._run_launcher_message") as launcher_message:
                                main.run()
        launcher_message.assert_called()
        message_text = str(launcher_message.call_args.args[1])
        self.assertIn("Created character: Iris", message_text)

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
            with patch("dnd_cli.main.load_tutorial_state", return_value={"seen": True}):
                with patch("dnd_cli.main.load_roster", return_value=[{"character_id": "pc-1", "name": "Iris", "archetype": "Mage"}]):
                    with patch("dnd_cli.main.HostService", FakeHostService):
                        with patch("dnd_cli.main._run_online_ui", return_value=None):
                            with patch("sys.stdout", new_callable=io.StringIO):
                                main.run()
        self.assertEqual(len(captured.get("party", [])), 3)
        self.assertEqual(captured["party"][0].character_id, "pc-1")
        self.assertEqual(captured["chat_mode"], "text_18_plus")

    def test_first_launcher_run_auto_starts_tutorial_when_unseen(self) -> None:
        argv = ["DND"]
        with patch("sys.argv", argv):
            with patch("dnd_cli.main.load_tutorial_state", return_value={"seen": False}):
                with patch("dnd_cli.main._run_tutorial", return_value="completed") as run_tutorial:
                    with patch("dnd_cli.main.save_tutorial_state") as save_tutorial:
                        with patch("dnd_cli.main._run_launcher_message"):
                            with patch("dnd_cli.main._run_launcher", return_value="quit"):
                                main.run()
        run_tutorial.assert_called_once()
        save_tutorial.assert_called_once()

    def test_launcher_tutorial_choice_runs_tutorial(self) -> None:
        argv = ["DND"]
        with patch("sys.argv", argv):
            with patch("dnd_cli.main.load_tutorial_state", return_value={"seen": True, "completed": False, "skipped": False}):
                with patch("dnd_cli.main._run_tutorial", return_value="completed") as run_tutorial:
                    with patch("dnd_cli.main.save_tutorial_state") as save_tutorial:
                        with patch("dnd_cli.main._run_launcher", side_effect=["tutorial", "quit"]):
                            with patch("dnd_cli.main._run_launcher_form", return_value={}):
                                main.run()
        run_tutorial.assert_called_once()
        save_tutorial.assert_called_once()


if __name__ == "__main__":
    unittest.main()
