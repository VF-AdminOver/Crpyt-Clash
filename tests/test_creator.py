from __future__ import annotations

import unittest

from dnd_cli.creator import (
    ARCHETYPES,
    build_companions,
    build_main_character,
    point_buy_cost,
    preview_derived_stats,
    recommended_stats,
    validate_name,
    validate_point_buy,
)


class CreatorTests(unittest.TestCase):
    def test_point_buy_recommended_is_valid(self) -> None:
        stats = recommended_stats("Fighter")
        self.assertTrue(validate_point_buy(stats))
        self.assertEqual(point_buy_cost(stats), 27)

    def test_point_buy_rejects_out_of_range(self) -> None:
        bad = {"str": 16, "dex": 8, "con": 8, "int": 8, "wis": 8, "cha": 8}
        self.assertFalse(validate_point_buy(bad))

    def test_build_main_character_contains_metadata(self) -> None:
        stats = recommended_stats("Rogue")
        hero = build_main_character("Alden", "Rogue", stats)
        self.assertEqual(hero.owner_type, "local_player")
        self.assertEqual(hero.archetype, "Rogue")
        self.assertTrue(hero.character_id.startswith("pc-"))
        self.assertGreaterEqual(hero.max_hp, 14)
        self.assertEqual(hero.max_mana, 6)
        self.assertEqual(hero.mana, hero.max_mana)
        self.assertIn("rogue_precise_stab", hero.class_skills or [])

    def test_companions_are_two_distinct_archetypes(self) -> None:
        companions = build_companions("Fighter", seed=7)
        self.assertEqual(len(companions), 2)
        self.assertTrue(all(unit.owner_type == "npc_companion" for unit in companions))
        self.assertTrue(all(unit.archetype in ARCHETYPES for unit in companions))

    def test_name_validation(self) -> None:
        self.assertTrue(validate_name("Alden-Rook"))
        self.assertFalse(validate_name("A"))
        self.assertFalse(validate_name("WayTooLongForRulesName"))
        self.assertFalse(validate_name("Bad#Name"))

    def test_preview_changes_with_stats(self) -> None:
        stats = recommended_stats("Fighter")
        base_preview = preview_derived_stats("Fighter", stats)
        stats["str"] = 15
        stronger_preview = preview_derived_stats("Fighter", stats)
        self.assertGreaterEqual(stronger_preview["attack_bonus"], base_preview["attack_bonus"])


if __name__ == "__main__":
    unittest.main()
