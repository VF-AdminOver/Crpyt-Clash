from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from dnd_cli.game import Game
from dnd_cli.multiplayer import MultiplayerServer, render_snapshot, resolve_action_input


class MultiplayerTests(unittest.TestCase):
    def test_resolve_action_input_by_index(self) -> None:
        actions = ["Attack", "Defend", "Bag"]
        self.assertEqual(resolve_action_input("2", actions), "Defend")
        self.assertIsNone(resolve_action_input("9", actions))

    def test_resolve_action_input_by_label(self) -> None:
        actions = ["Venture Deeper", "Path", "Rest"]
        self.assertEqual(resolve_action_input("path", actions), "Path")
        self.assertIsNone(resolve_action_input("unknown", actions))

    def test_render_snapshot_shows_chat_mode_label(self) -> None:
        text = render_snapshot({"status": "Explore", "chat_mode": "text_18_plus", "actions": []})
        self.assertIn("Comms: Text (18+)", text)

    def test_server_assigns_distinct_party_members(self) -> None:
        game = Game(seed=3)
        server = MultiplayerServer(game=game, join_code="ABCD")
        first = server._assign_character_id("c-a")
        if first:
            server.controllers[first] = "c-a"
        second = server._assign_character_id("c-b")
        self.assertNotEqual(first, second)
        self.assertIn(first, [unit.character_id or unit.name for unit in game.party])
        self.assertIn(second, [unit.character_id or unit.name for unit in game.party])

    def test_uncontrolled_party_turn_can_auto_play(self) -> None:
        game = Game(seed=7)
        game.perform_player_action("Venture Deeper")
        server = MultiplayerServer(game=game, join_code="ABCD")
        while game.mode == "combat" and game.is_player_turn():
            actor = game.active_unit()
            if actor:
                server.controllers[actor.character_id or actor.name] = "client-x"
            game._advance_turn()
        game.turn_index = 0
        game.rebuild_turn_order()
        server.controllers.clear()
        server._auto_play_uncontrolled_turns()
        self.assertIn(game.mode, {"combat", "explore", "victory", "defeat"})

    def test_snapshot_contains_battle_metadata(self) -> None:
        game = Game(seed=7)
        game.perform_player_action("Venture Deeper")
        server = MultiplayerServer(game=game, join_code="ABCD", chat_mode="text_18_plus")
        snapshot = server._snapshot_for_client("none")
        self.assertIn("round", snapshot)
        self.assertIn("enemies", snapshot)
        self.assertIn("mood", snapshot)
        self.assertIn("menu_context", snapshot)
        self.assertIn("loot_non_rare_streak", snapshot)
        self.assertEqual(snapshot["chat_mode"], "text_18_plus")

    def test_snapshot_includes_submenu_actions(self) -> None:
        game = Game(seed=7)
        game.perform_player_action("Venture Deeper")
        game.perform_player_action("Attack")
        server = MultiplayerServer(game=game, join_code="ABCD")
        snapshot = server._snapshot_for_client("none")
        self.assertTrue(any(action.startswith("Style:") for action in snapshot["actions"]))
        self.assertIn("menu_context", snapshot)

    def test_online_action_path_style_to_target_consumes_turn(self) -> None:
        game = Game(seed=7)
        game.perform_player_action("Venture Deeper")
        server = MultiplayerServer(game=game, join_code="ABCD")
        game.perform_player_action("Attack")
        game.perform_player_action("Style: Balanced")
        target = next(label for label in game.action_labels() if label.startswith("Target: "))
        game.perform_player_action(target)
        self.assertTrue(game.action_consumed_turn)

    def test_snapshot_chest_action_hidden_until_discovery(self) -> None:
        game = Game(seed=7)
        server = MultiplayerServer(game=game, join_code="ABCD")
        snapshot = server._snapshot_for_client("none")
        self.assertNotIn("Open Chest", snapshot["actions"])
        with patch.object(game.rng, "randint", return_value=20):
            with patch.object(game.rng, "random", return_value=0.99):
                game.perform_player_action("Look Around")
        snapshot_after = server._snapshot_for_client("none")
        self.assertIn("Open Chest", snapshot_after["actions"])

    def test_reaction_event_appends_to_shared_log(self) -> None:
        game = Game(seed=7)
        server = MultiplayerServer(game=game, join_code="ABCD")
        asyncio.run(server._handle_reaction("no-client", "🔥", "party"))
        self.assertTrue(any("reacts 🔥" in entry for entry in game.log))

    def test_chat_blocked_when_reactions_only(self) -> None:
        game = Game(seed=7)
        server = MultiplayerServer(game=game, join_code="ABCD", chat_mode="reactions_only")
        ok, error = asyncio.run(server._handle_chat("no-client", "hello"))
        self.assertFalse(ok)
        self.assertIn("reactions-only", error.lower())

    def test_chat_allowed_in_text_18_plus_mode(self) -> None:
        game = Game(seed=7)
        server = MultiplayerServer(game=game, join_code="ABCD", chat_mode="text_18_plus")
        ok, error = asyncio.run(server._handle_chat("no-client", "hello"))
        self.assertTrue(ok)
        self.assertEqual(error, "")
        self.assertTrue(any("hello" in entry for entry in game.log))

    def test_chat_rejects_oversized_payload(self) -> None:
        game = Game(seed=7)
        server = MultiplayerServer(game=game, join_code="ABCD", chat_mode="text_18_plus")
        ok, error = asyncio.run(server._handle_chat("no-client", "x" * 241))
        self.assertFalse(ok)
        self.assertIn("max 240", error)


if __name__ == "__main__":
    unittest.main()
