from __future__ import annotations

import unittest
from unittest.mock import patch

from dnd_cli.game import Game


class GameTests(unittest.TestCase):
    def test_new_app_enters_creator_mode(self) -> None:
        try:
            from dnd_cli.app import DndApp
        except ModuleNotFoundError as exc:
            if "textual" in str(exc):
                self.skipTest("textual not installed in test environment")
            raise
        app = DndApp(creation_enabled=True, run_mode="normal", seed=7)
        self.assertTrue(app.creation_mode)
        self.assertIn(app.creator_stage, {"name", "roster"})

    def test_begin_next_adventure_dispatches_from_game_over_ui_flow(self) -> None:
        try:
            from dnd_cli.app import DndApp
        except ModuleNotFoundError as exc:
            if "textual" in str(exc):
                self.skipTest("textual not installed in test environment")
            raise
        app = DndApp(game=Game(seed=7))
        app.game.mode = "victory"
        app._selected_action_label = lambda: "Begin Next Adventure"  # type: ignore[method-assign]
        app._save_silent = lambda: None  # type: ignore[method-assign]
        app._refresh_all = lambda: None  # type: ignore[method-assign]
        app.action_confirm_action()
        self.assertEqual(app.game.mode, "explore")

    def test_render_mode_text_only_removes_ascii_party_header(self) -> None:
        try:
            from dnd_cli.app import DndApp
        except ModuleNotFoundError as exc:
            if "textual" in str(exc):
                self.skipTest("textual not installed in test environment")
            raise
        app = DndApp(game=Game(seed=7))
        app.render_mode = "text_only"
        party_text = app._render_party()
        self.assertNotIn("/\\", party_text)

    def test_render_mode_changes_log_presentation(self) -> None:
        try:
            from dnd_cli.app import DndApp
        except ModuleNotFoundError as exc:
            if "textual" in str(exc):
                self.skipTest("textual not installed in test environment")
            raise
        app = DndApp(game=Game(seed=7))
        app.render_mode = "hybrid_ascii"
        hybrid_log = app._render_log()
        app.render_mode = "text_only"
        text_log = app._render_log()
        self.assertIn("Adventure Feed", hybrid_log)
        self.assertNotIn("Adventure Feed", text_log)

    def test_actions_include_path_bag_rest(self) -> None:
        game = Game(seed=11, run_mode="normal")
        labels = game.action_labels()
        self.assertIn("Look Around", labels)
        self.assertIn("Path", labels)
        self.assertIn("Bag", labels)
        self.assertIn("Rest", labels)

    def test_look_around_adds_room_context_to_log(self) -> None:
        game = Game(seed=11, run_mode="normal")
        baseline = list(game.log)
        game.perform_player_action("Look Around")
        self.assertGreater(len(game.log), len(baseline))
        self.assertTrue(any("survey" in entry.lower() for entry in game.log))

    def test_look_around_unlocks_explore_space_action(self) -> None:
        game = Game(seed=11, run_mode="normal")
        self.assertNotIn("Explore Space", game.action_labels())
        with patch.object(game.rng, "random", return_value=0.99):
            game.perform_player_action("Look Around")
        self.assertIn("Explore Space", game.action_labels())

    def test_explore_space_tracks_room_progress(self) -> None:
        game = Game(seed=11, run_mode="normal")
        with patch.object(game.rng, "random", return_value=0.99):
            game.perform_player_action("Look Around")
            for _ in range(15):
                game.perform_player_action("Explore Space")
        room = game.rooms[game.room_index]
        self.assertEqual(room["spaces_explored"], 15)
        self.assertNotIn("Explore Space", game.action_labels())

    def test_explore_space_resource_event_adds_materials(self) -> None:
        game = Game(seed=11, run_mode="normal")
        with patch.object(game.rng, "random", side_effect=[0.99, 0.2]):
            with patch.object(game.rng, "randint", return_value=2):
                game.perform_player_action("Look Around")
                game.perform_player_action("Explore Space")
        self.assertGreaterEqual(game.inventory.get("crypt_herb", 0), 2)
        self.assertTrue(any("resource cache" in entry.lower() for entry in game.log))

    def test_explore_space_clue_event_reduces_chest_dc(self) -> None:
        game = Game(seed=11, run_mode="normal")
        chest_before = game.rooms[game.room_index]["chest"]["search_dc"]
        with patch.object(game.rng, "random", side_effect=[0.99, 0.3]):
            with patch.object(game.rng, "randint", return_value=1):
                game.perform_player_action("Look Around")
                game.perform_player_action("Explore Space")
        chest_after = game.rooms[game.room_index]["chest"]["search_dc"]
        self.assertLess(chest_after, chest_before)

    def test_explore_space_ambush_event_starts_combat(self) -> None:
        game = Game(seed=11, run_mode="normal")
        with patch.object(game.rng, "random", side_effect=[0.99, 0.05, 0.2]):
            game.perform_player_action("Look Around")
            game.perform_player_action("Explore Space")
        self.assertEqual(game.mode, "combat")
        self.assertEqual(game.combat_kind, "search")
        self.assertTrue(any("ambush" in entry.lower() for entry in game.log))

    def test_explore_space_loot_event_can_grant_random_loot(self) -> None:
        game = Game(seed=11, run_mode="normal")
        loot_before = game.inventory.get("healing_potion", 0)
        with patch.object(game.rng, "random", side_effect=[0.99, 0.82]):
            with patch.object(game, "_roll_rarity_tier", return_value="common"):
                with patch.object(game, "_weighted_item_choice", return_value="healing_potion"):
                    game.perform_player_action("Look Around")
                    game.perform_player_action("Explore Space")
        self.assertGreater(game.inventory.get("healing_potion", 0), loot_before)
        self.assertTrue(any("hidden cache reveals" in entry.lower() for entry in game.log))

    def test_open_chest_hidden_until_search_success(self) -> None:
        game = Game(seed=11, run_mode="normal")
        self.assertNotIn("Open Chest", game.action_labels())
        with patch.object(game.rng, "randint", return_value=20):
            game.perform_player_action("Look Around")
        self.assertIn("Open Chest", game.action_labels())

    def test_search_roll_uses_int_modifier(self) -> None:
        game = Game(seed=11, run_mode="normal")
        game.party[0].intelligence = 8  # mod -1
        with patch.object(game.rng, "randint", return_value=13):
            game.perform_player_action("Look Around")
        self.assertNotIn("Open Chest", game.action_labels())
        self.assertTrue(any("INT -1" in entry for entry in game.log))

    def test_search_attempts_capped_at_two(self) -> None:
        game = Game(seed=11, run_mode="normal")
        with patch.object(game.rng, "randint", return_value=1):
            game.perform_player_action("Look Around")
            game.perform_player_action("Look Around")
            game.perform_player_action("Look Around")
        self.assertTrue(any("no more hidden stashes" in entry.lower() for entry in game.log))
        self.assertNotIn("Open Chest", game.action_labels())

    def test_search_success_reveals_open_chest_action(self) -> None:
        game = Game(seed=11, run_mode="normal")
        with patch.object(game.rng, "randint", return_value=20):
            game.perform_player_action("Look Around")
        self.assertIn("Open Chest", game.action_labels())

    def test_search_failure_then_success_path(self) -> None:
        game = Game(seed=11, run_mode="normal")
        with patch.object(game.rng, "randint", side_effect=[1, 20]):
            game.perform_player_action("Look Around")
            self.assertNotIn("Open Chest", game.action_labels())
            game.perform_player_action("Look Around")
        self.assertIn("Open Chest", game.action_labels())
        self.assertTrue(any("missed" in entry.lower() for entry in game.log))
        self.assertTrue(any("chest found" in entry.lower() for entry in game.log))

    def test_open_chest_requires_discovered_state(self) -> None:
        game = Game(seed=11, run_mode="normal")
        gold_before = game.gold
        game.perform_player_action("Open Chest")
        self.assertEqual(game.gold, gold_before)
        self.assertTrue(any("find the chest first" in entry.lower() for entry in game.log))

    def test_open_chest_rewards_once_after_discovery(self) -> None:
        game = Game(seed=11, run_mode="normal")
        with patch.object(game.rng, "randint", return_value=20):
            game.perform_player_action("Look Around")
        gold_before = game.gold
        game.perform_player_action("Open Chest")
        self.assertGreater(game.gold, gold_before)
        self.assertTrue(any("open the chest" in entry.lower() for entry in game.log))
        self.assertNotIn("Open Chest", game.action_labels())

    def test_combat_and_chest_use_unified_drop_pipeline(self) -> None:
        game = Game(seed=11, run_mode="normal")
        with patch.object(game, "_roll_item_drop", return_value="healing_potion") as drop_mock:
            game._grant_loot(["healing_potion"])
            game.rooms[game.room_index]["chest"]["discovered"] = True
            with patch.object(game.rng, "random", return_value=0.0):
                game._open_room_chest()
        self.assertGreaterEqual(drop_mock.call_count, 2)

    def test_rare_pity_triggers_after_five_non_rare_drops(self) -> None:
        game = Game(seed=11, run_mode="normal")
        game.loot_non_rare_streak = 5
        with patch.object(game, "_weighted_item_choice", return_value="holy_water"):
            dropped = game._roll_item_drop(source="combat", room_loot=["holy_water"])
        self.assertEqual(dropped, "holy_water")
        self.assertEqual(game.loot_non_rare_streak, 0)
        self.assertTrue(any("pity active" in entry.lower() for entry in game.log))

    def test_rare_drop_resets_non_rare_streak(self) -> None:
        game = Game(seed=11, run_mode="normal")
        game.loot_non_rare_streak = 3
        with patch.object(game, "_roll_rarity_tier", return_value="rare"):
            with patch.object(game, "_weighted_item_choice", return_value="holy_water"):
                game._roll_item_drop(source="combat", room_loot=["holy_water"])
        self.assertEqual(game.loot_non_rare_streak, 0)

    def test_smart_bias_prefers_party_relevant_items_without_exclusion(self) -> None:
        game = Game(seed=11, run_mode="normal")
        game.party[0].archetype = "Fighter"
        weighted = dict(game._apply_smart_bias(["rusty_sword", "holy_water"]))
        self.assertIn("rusty_sword", weighted)
        self.assertIn("holy_water", weighted)
        self.assertGreater(weighted["rusty_sword"], weighted["holy_water"])

    def test_duplicate_over_threshold_auto_salvages_to_gold(self) -> None:
        game = Game(seed=11, run_mode="normal")
        game.inventory["rusty_sword"] = 2
        gold_before = game.gold
        with patch.object(game, "_roll_rarity_tier", return_value="common"):
            with patch.object(game, "_weighted_item_choice", return_value="rusty_sword"):
                dropped = game._roll_item_drop(source="combat", room_loot=["rusty_sword"])
        self.assertIsNone(dropped)
        self.assertGreater(game.gold, gold_before)
        self.assertTrue(any("duplicate salvaged" in entry.lower() for entry in game.log))

    def test_drop_counters_roundtrip_in_save_load(self) -> None:
        game = Game(seed=11, run_mode="normal")
        game.loot_non_rare_streak = 4
        game.loot_total_drops = 9
        loaded = Game.from_dict(game.to_dict())
        self.assertEqual(loaded.loot_non_rare_streak, 4)
        self.assertEqual(loaded.loot_total_drops, 9)

    def test_legacy_save_loads_with_default_loot_counters(self) -> None:
        game = Game(seed=11, run_mode="normal")
        data = game.to_dict()
        data.pop("loot_non_rare_streak", None)
        data.pop("loot_total_drops", None)
        loaded = Game.from_dict(data)
        self.assertEqual(loaded.loot_non_rare_streak, 0)
        self.assertEqual(loaded.loot_total_drops, 0)

    def test_path_opens_map_overlay_and_can_close(self) -> None:
        game = Game(seed=11, run_mode="normal")
        game.perform_player_action("Path")
        self.assertEqual(game.menu, "map")
        screen = game.battle_screen_text()
        self.assertIn("MINI MAP OVERLAY", screen)
        self.assertIn("Legend:", screen)
        self.assertEqual(game.action_labels(), ["Close Map"])
        game.perform_player_action("Close Map")
        self.assertEqual(game.menu, "root")

    def test_tip_rotates_and_persists(self) -> None:
        game = Game(seed=11, run_mode="normal")
        first = game.next_tip()
        second = game.next_tip()
        self.assertNotEqual(first, second)
        loaded = Game.from_dict(game.to_dict())
        self.assertEqual(loaded.tip_index, game.tip_index)

    def test_round_trip_preserves_mode_inventory_equipment(self) -> None:
        game = Game(seed=11, run_mode="ironman")
        game.inventory["smoke_bomb"] = 2
        game.inventory["rusty_sword"] = 1
        game.selected_member_name = game.party[0].name
        game._equip_by_action_label("Equip Rusty Sword (1)")
        game.gold = 27

        loaded = Game.from_dict(game.to_dict())

        self.assertEqual(loaded.run_mode, "ironman")
        self.assertEqual(loaded.inventory["smoke_bomb"], 2)
        equipment_key = loaded.party[0].character_id or loaded.party[0].name
        self.assertEqual(loaded.equipment[equipment_key]["weapon"], "rusty_sword")
        self.assertEqual(loaded.gold, 27)
        self.assertIn("character_id", loaded.to_dict()["party"][0])

    def test_weapon_bonus_applies_per_character(self) -> None:
        game = Game(seed=5)
        game.inventory["rusty_sword"] = 1
        game.selected_member_name = game.party[0].name
        game._equip_by_action_label("Equip Rusty Sword (1)")

        self.assertEqual(game._weapon_bonus(game.party[0]), 1)
        self.assertEqual(game._weapon_bonus(game.party[1]), 0)

    def test_combat_win_grants_loot(self) -> None:
        game = Game(seed=3)
        game.perform_player_action("Venture Deeper")
        game.enemies.clear()
        game._check_combat_resolution()

        self.assertGreater(game.gold, 0)
        self.assertTrue(any(quantity > 0 for quantity in game.inventory.values()))

    def test_award_experience_levels_up_party(self) -> None:
        game = Game(seed=3)
        hero = game.party[0]
        start_level = hero.level
        start_hp = hero.max_hp
        game._award_experience(250)
        self.assertGreater(hero.level, start_level)
        self.assertGreater(hero.max_hp, start_hp)
        self.assertLess(hero.experience, hero.next_level_xp)

    def test_battle_screen_shows_combat_details(self) -> None:
        game = Game(seed=7)
        game.perform_player_action("Venture Deeper")
        game.perform_player_action("Attack")
        game.perform_player_action("Style: Balanced")
        enemy_target = next(label for label in game.action_labels() if label.startswith("Target: "))
        game.perform_player_action(enemy_target)
        screen = game.battle_screen_text()
        self.assertIn("BATTLE SCREEN", screen)
        self.assertIn("Turn Order:", screen)
        self.assertIn("Enemy Status:", screen)
        self.assertIn("Last Roll:", screen)

    def test_battle_screen_victory_and_defeat_banners(self) -> None:
        game = Game(seed=7)
        game.mode = "victory"
        self.assertIn("VICTORY", game.battle_screen_text())
        game.mode = "defeat"
        self.assertIn("DEFEAT", game.battle_screen_text())

    def test_combat_action_tree_includes_skills_and_styles(self) -> None:
        game = Game(seed=11)
        game.perform_player_action("Venture Deeper")
        self.assertIn("Skills", game.action_labels())
        game.perform_player_action("Attack")
        self.assertIn("Style: Quick", game.action_labels())
        self.assertIn("Style: Balanced", game.action_labels())
        self.assertIn("Style: Heavy", game.action_labels())

    def test_attack_requires_target_selection(self) -> None:
        game = Game(seed=11)
        game.perform_player_action("Venture Deeper")
        game.perform_player_action("Attack")
        game.perform_player_action("Style: Balanced")
        self.assertEqual(game.menu, "target_enemy")
        self.assertTrue(any(label.startswith("Target: ") for label in game.action_labels()))

    def test_manual_target_changes_damage_recipient(self) -> None:
        game = Game(seed=11)
        game.perform_player_action("Venture Deeper")
        game.enemies.append(game.enemies[0].__class__("Extra Ghoul", 15, 15, 2, 2, 4))
        before = {enemy.name: enemy.hp for enemy in game.enemies}
        game.perform_player_action("Attack")
        game.perform_player_action("Style: Balanced")
        target_label = next(label for label in game.action_labels() if "Extra Ghoul" in label)
        game.perform_player_action(target_label)
        after = {enemy.name: enemy.hp for enemy in game.enemies}
        self.assertLess(after["Extra Ghoul"], before["Extra Ghoul"])

    def test_style_modifies_hit_or_damage(self) -> None:
        balanced = Game(seed=5)
        heavy = Game(seed=5)
        balanced.perform_player_action("Venture Deeper")
        heavy.perform_player_action("Venture Deeper")
        balanced.perform_player_action("Attack")
        balanced.perform_player_action("Style: Balanced")
        target_balanced = next(label for label in balanced.action_labels() if label.startswith("Target: "))
        balanced.perform_player_action(target_balanced)
        heavy.perform_player_action("Attack")
        heavy.perform_player_action("Style: Heavy")
        target_heavy = next(label for label in heavy.action_labels() if label.startswith("Target: "))
        heavy.perform_player_action(target_heavy)
        self.assertNotEqual(balanced.last_roll_text, heavy.last_roll_text)

    def test_skill_cost_blocks_when_insufficient_mana(self) -> None:
        game = Game(seed=11)
        game.perform_player_action("Venture Deeper")
        actor = game.active_unit()
        self.assertIsNotNone(actor)
        actor.mana = 0
        game.perform_player_action("Skills")
        game.perform_player_action("Skill: Precise Stab (3 MP)")
        target_label = next(label for label in game.action_labels() if label.startswith("Target: "))
        game.perform_player_action(target_label)
        self.assertTrue(any("Not enough Mana" in entry for entry in game.log))

    def test_mend_targets_allies_only(self) -> None:
        game = Game(seed=11)
        game.perform_player_action("Venture Deeper")
        game.party[0].archetype = "Cleric"
        game.party[0].class_skills = ["cleric_smite", "cleric_mend"]
        game.party[1].hp = max(1, game.party[1].hp - 8)
        game.perform_player_action("Skills")
        game.perform_player_action("Skill: Mend (3 MP)")
        labels = game.action_labels()
        self.assertTrue(all(label.startswith("Target Ally:") or label == "Back" for label in labels))
        ally_before = game.party[1].hp
        target_ally = next(label for label in labels if game.party[1].name.split(" (", 1)[0] in label)
        game.perform_player_action(target_ally)
        self.assertGreaterEqual(game.party[1].hp, ally_before)

    def test_mana_regens_on_turn_start(self) -> None:
        game = Game(seed=11)
        game.perform_player_action("Venture Deeper")
        actor = game.active_unit()
        self.assertIsNotNone(actor)
        actor.mana = 0
        game.perform_player_action("Defend")
        game.run_enemy_turns_until_player()
        if game.mode == "combat" and game.is_player_turn():
            self.assertGreaterEqual(game.active_unit().mana, 1)

    def test_legacy_save_loads_with_default_mana_and_skills(self) -> None:
        game = Game(seed=11)
        data = game.to_dict()
        first_party = data["party"][0]
        first_party.pop("mana", None)
        first_party.pop("class_skills", None)
        loaded = Game.from_dict(data)
        self.assertEqual(loaded.party[0].max_mana, 6)
        self.assertEqual(loaded.party[0].mana, 6)
        self.assertGreaterEqual(len(loaded.party[0].class_skills or []), 1)

    def test_chest_discovery_fields_roundtrip_in_save_load(self) -> None:
        game = Game(seed=11)
        with patch.object(game.rng, "randint", return_value=20):
            game.perform_player_action("Look Around")
        loaded = Game.from_dict(game.to_dict())
        chest = loaded.rooms[loaded.room_index]["chest"]
        self.assertTrue(chest["discovered"])
        self.assertGreaterEqual(chest["search_attempts"], 1)
        self.assertEqual(chest["search_attempts_max"], 2)
        self.assertEqual(chest["search_dc"], 13)

    def test_legacy_room_chest_defaults_injected(self) -> None:
        game = Game(seed=11)
        data = game.to_dict()
        data["rooms"][0]["chest"] = {"present": True, "opened": False}
        data["rooms"][0].pop("look_encounter_checked", None)
        loaded = Game.from_dict(data)
        chest = loaded.rooms[0]["chest"]
        self.assertIn("discovered", chest)
        self.assertIn("search_attempts", chest)
        self.assertIn("search_attempts_max", chest)
        self.assertIn("search_dc", chest)
        self.assertIn("look_encounter_checked", loaded.rooms[0])

    def test_look_around_can_trigger_roaming_encounter(self) -> None:
        game = Game(seed=11)
        with patch.object(game.rng, "randint", return_value=20):
            with patch.object(game.rng, "random", side_effect=[0.1, 0.1]):
                game.perform_player_action("Look Around")
        self.assertEqual(game.mode, "combat")
        self.assertEqual(game.combat_kind, "search")
        self.assertTrue(any("roaming encounter begins" in entry.lower() for entry in game.log))

    def test_search_encounter_win_does_not_advance_room(self) -> None:
        game = Game(seed=11)
        with patch.object(game.rng, "randint", return_value=20):
            with patch.object(game.rng, "random", side_effect=[0.1, 0.1]):
                game.perform_player_action("Look Around")
        start_room = game.room_index
        game.enemies.clear()
        game._check_combat_resolution()
        self.assertEqual(game.mode, "explore")
        self.assertEqual(game.room_index, start_room)
        self.assertEqual(game.combat_kind, "main")
        self.assertTrue(any("main path still lies ahead" in entry.lower() for entry in game.log))

    def test_look_encounter_checked_once_per_room(self) -> None:
        game = Game(seed=11)
        game.rooms[game.room_index]["chest"]["present"] = False
        with patch.object(game.rng, "random", side_effect=[0.8]) as random_mock:
            game.perform_player_action("Look Around")
            game.perform_player_action("Look Around")
        self.assertEqual(random_mock.call_count, 1)
        self.assertEqual(game.mode, "explore")

    def test_victory_offers_next_adventure_action(self) -> None:
        game = Game(seed=11)
        game.mode = "victory"
        labels = game.action_labels()
        self.assertIn("Begin Next Adventure", labels)

    def test_begin_next_adventure_increments_and_resets_state(self) -> None:
        game = Game(seed=11)
        game.mode = "victory"
        game.room_index = len(game.rooms)
        game.party[0].hp = max(1, game.party[0].hp - 5)
        game.party[0].mana = 0
        current_adventure = game.adventure_number
        game.perform_player_action("Begin Next Adventure")
        self.assertEqual(game.mode, "explore")
        self.assertEqual(game.adventure_number, current_adventure + 1)
        self.assertEqual(game.room_index, 0)
        self.assertEqual(game.party[0].hp, game.party[0].max_hp)
        self.assertEqual(game.party[0].mana, game.party[0].max_mana)

    def test_end_to_end_run_loop_combat_to_next_adventure(self) -> None:
        game = Game(seed=11)
        self.assertEqual(game.mode, "explore")
        game.perform_player_action("Venture Deeper")
        self.assertEqual(game.mode, "combat")
        game.enemies.clear()
        game._check_combat_resolution()
        self.assertEqual(game.mode, "explore")
        self.assertGreaterEqual(game.room_index, 1)
        game.room_index = len(game.rooms)
        game.mode = "victory"
        adventure_before = game.adventure_number
        game.perform_player_action("Begin Next Adventure")
        self.assertEqual(game.mode, "explore")
        self.assertEqual(game.adventure_number, adventure_before + 1)
        self.assertEqual(game.room_index, 0)

    def test_adventure_number_persists_through_save_roundtrip(self) -> None:
        game = Game(seed=11)
        game.mode = "victory"
        game.perform_player_action("Begin Next Adventure")
        loaded = Game.from_dict(game.to_dict())
        self.assertEqual(loaded.adventure_number, game.adventure_number)

    def test_store_available_on_adventure_4_and_8_pattern(self) -> None:
        game = Game(seed=11)
        game.adventure_number = 4
        game.mode = "combat"
        game.combat_kind = "main"
        game.enemies = []
        game._check_combat_resolution()
        self.assertTrue(game.store_available_now)

    def test_store_not_triggered_by_hunt_or_search_resolution(self) -> None:
        for combat_kind in ("hunt", "search"):
            game = Game(seed=11)
            game.adventure_number = 4
            game.mode = "combat"
            game.combat_kind = combat_kind
            game.enemies = []
            game._check_combat_resolution()
            self.assertFalse(game.store_available_now)

    def test_store_triggered_once_per_adventure(self) -> None:
        game = Game(seed=11)
        game.adventure_number = 4
        game.mode = "combat"
        game.combat_kind = "main"
        game.enemies = []
        game._check_combat_resolution()
        self.assertTrue(game.store_available_now)
        game.store_available_now = False
        game.mode = "combat"
        game.combat_kind = "main"
        game.enemies = []
        game._check_combat_resolution()
        self.assertFalse(game.store_available_now)

    def test_boss_reward_logs_ability_text(self) -> None:
        game = Game(seed=11)
        with patch.object(game.rng, "choice", return_value="boss_sigil_blade"):
            game._roll_boss_reward()
        self.assertTrue(any("ability:" in entry.lower() for entry in game.log))

    def test_pvp_initiative_order_closer_to_20_goes_later_and_speed_breaks_ties(self) -> None:
        entries = [
            ("A", 18, 10),
            ("B", 10, 12),
            ("C", 10, 14),
            ("D", 3, 8),
        ]
        order = Game.pvp_initiative_order(entries)
        self.assertEqual(order, ["D", "C", "B", "A"])

    def test_store_craft_holy_water_recipe(self) -> None:
        game = Game(seed=11)
        game.inventory["crypt_herb"] = 3
        game.gold = 20
        game._craft_item("holy_water")
        self.assertEqual(game.inventory.get("holy_water", 0), 1)
        self.assertEqual(game.inventory.get("crypt_herb", 0), 0)
        self.assertEqual(game.gold, 8)

    def test_store_trade_quantity_sale(self) -> None:
        game = Game(seed=11)
        game.inventory["healing_potion"] = 4
        gold_before = game.gold
        game._trade_item("merchant", "healing_potion", 3)
        self.assertEqual(game.inventory.get("healing_potion", 0), 1)
        self.assertGreater(game.gold, gold_before)

    def test_store_labels_include_recipe_costs_and_dynamic_sell_options(self) -> None:
        game = Game(seed=11)
        game.store_available_now = True
        game.inventory["healing_potion"] = 2
        game._open_store()
        labels = game.action_labels()
        self.assertIn("Craft Healing Potion (1 Herb + 2g)", labels)
        self.assertIn("Sell Healing Potion xAll (+12g)", labels)

    def test_store_sell_all_uses_full_inventory_count(self) -> None:
        game = Game(seed=11)
        game.store_available_now = True
        game._open_store()
        game.inventory["smoke_bomb"] = 3
        game.gold = 0
        game.perform_player_action("Sell Smoke Bomb xAll (+27g)")
        self.assertEqual(game.inventory.get("smoke_bomb", 0), 0)
        self.assertEqual(game.gold, 27)


if __name__ == "__main__":
    unittest.main()
