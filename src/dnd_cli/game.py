from __future__ import annotations

import base64
import pickle
import random
from dataclasses import dataclass
from enum import Enum

from dnd_cli.items import CONSUMABLE_IDS, GEAR_IDS, ITEM_DEFS, is_gear, item_label, item_rarity, item_tags


class Action(Enum):
    NEXT_ADVENTURE = "Begin Next Adventure"
    OPEN_CHEST = "Open Chest"
    BACKTRACK = "Backtrack"
    HUNT = "Hunt"
    HARVEST = "Harvest"
    STORE = "Visit Store"
    ATTACK = "Attack"
    SKILLS = "Skills"
    DEFEND = "Defend"
    LOOK = "Look Around"
    EXPLORE_SPACE = "Explore Space"
    BAG = "Bag"
    PATH = "Path"
    EQUIP = "Equip Gear"
    VENTURE = "Venture Deeper"
    REST = "Rest"
    CLOSE_MAP = "Close Map"
    BACK = "Back"


@dataclass
class Unit:
    name: str
    hp: int
    max_hp: int
    attack_bonus: int
    damage_min: int
    damage_max: int
    defending: bool = False
    character_id: str = ""
    owner_type: str = "npc_companion"
    archetype: str = "Adventurer"
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    level: int = 1
    experience: int = 0
    next_level_xp: int = 100
    mana: int = 6
    max_mana: int = 6
    resource_name: str = "Mana"
    class_skills: list[str] | None = None

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def hp_text(self) -> str:
        return f"{self.hp}/{self.max_hp}"


class Game:
    LOOT_TIER_WEIGHTS: dict[str, int] = {"common": 65, "uncommon": 28, "rare": 7}
    CHEST_TIER_WEIGHTS: dict[str, int] = {"common": 58, "uncommon": 32, "rare": 10}
    RARE_PITY_THRESHOLD = 5
    DONATION_RATIO = 0.5
    BOSS_INTERVAL = 10
    RESPawn_XP_FACTORS = [0.7, 0.4]
    BASE_ROOMS = [
        {
            "name": "Antechamber",
            "description": "Cold air spills from shattered urns.",
            "enemies": [("Goblin Cutter", 18, 2, 3, 6)],
            "loot": ["healing_potion", "rusty_sword"],
        },
        {
            "name": "Hall of Chains",
            "description": "Iron hooks sway above cracked tiles.",
            "enemies": [("Bone Hound", 22, 3, 4, 7), ("Goblin Sneak", 16, 3, 3, 5)],
            "loot": ["smoke_bomb", "healing_potion", "leather_vest"],
        },
        {
            "name": "Crypt Sanctum",
            "description": "A sigil glows under dust and bones.",
            "enemies": [("Crypt Warden", 34, 4, 6, 10), ("Bone Hound", 22, 3, 4, 7)],
            "loot": ["holy_water", "healing_potion", "smoke_bomb"],
        },
    ]
    ATTACK_STYLES: dict[str, dict[str, float]] = {
        "Quick": {"hit_bonus": 2, "damage_mult": 0.8},
        "Balanced": {"hit_bonus": 0, "damage_mult": 1.0},
        "Heavy": {"hit_bonus": -2, "damage_mult": 1.35},
    }
    ARCHETYPE_SKILLS: dict[str, list[str]] = {
        "Fighter": ["fighter_power_strike", "fighter_guard_shove"],
        "Rogue": ["rogue_precise_stab", "rogue_kidney_shot"],
        "Cleric": ["cleric_smite", "cleric_mend"],
        "Mage": ["mage_arcane_bolt", "mage_force_burst"],
    }
    SKILL_DEFS: dict[str, dict[str, object]] = {
        "fighter_power_strike": {"name": "Power Strike", "cost": 3, "target": "enemy", "hit_bonus": 0, "damage_bonus": 3, "damage_mult": 1.0},
        "fighter_guard_shove": {"name": "Guard Shove", "cost": 2, "target": "enemy", "hit_bonus": 0, "damage_bonus": 0, "damage_mult": 1.0, "grant_defend": True, "strip_defend": True},
        "rogue_precise_stab": {"name": "Precise Stab", "cost": 3, "target": "enemy", "hit_bonus": 2, "damage_bonus": -1, "damage_mult": 1.0},
        "rogue_kidney_shot": {"name": "Kidney Shot", "cost": 4, "target": "enemy", "hit_bonus": -1, "damage_bonus": 4, "damage_mult": 1.0},
        "cleric_smite": {"name": "Smite", "cost": 3, "target": "enemy", "hit_bonus": 0, "damage_bonus": 2, "damage_mult": 1.0, "spell": True},
        "cleric_mend": {"name": "Mend", "cost": 3, "target": "ally", "heal_min": 8, "heal_max": 12},
        "mage_arcane_bolt": {"name": "Arcane Bolt", "cost": 3, "target": "enemy", "hit_bonus": 1, "damage_bonus": 2, "damage_mult": 1.0, "spell": True},
        "mage_force_burst": {"name": "Force Burst", "cost": 5, "target": "enemy", "aoe": True, "damage_min": 4, "damage_max": 7, "hit_bonus": 0, "spell": True},
    }
    TIPS = [
        "Use Defend when a hero is low to halve incoming damage.",
        "Save smoke bombs for multi-enemy rooms to skip pressure turns.",
        "Equip gear before venturing deeper for immediate stat value.",
        "Short rest once per room can stabilize before the next encounter.",
        "Focus one enemy at a time to reduce enemy actions quickly.",
        "Holy water is strongest when used early in hard encounters.",
    ]
    CRAFT_RECIPES: dict[str, dict[str, object]] = {
        "healing_potion": {"herbs": 1, "gold": 2},
        "smoke_bomb": {"herbs": 2, "gold": 6},
        "holy_water": {"herbs": 3, "gold": 12},
    }

    def __init__(
        self,
        seed: int = 7,
        run_mode: str = "normal",
        party: list[Unit] | None = None,
        run_context: str = "normal",
    ) -> None:
        self.seed = seed
        self.run_mode = run_mode if run_mode in {"normal", "ironman"} else "normal"
        self.run_context = run_context if run_context in {"normal", "tutorial"} else "normal"
        self.is_tutorial = self.run_context == "tutorial"
        self.rng = random.Random(self.seed)
        self.mode = "explore"
        self.combat_kind = "main"
        self.menu = "root"
        self.adventure_number = 1
        self.pending_action_type: str | None = None
        self.pending_style: str | None = None
        self.pending_skill_id: str | None = None
        self.action_consumed_turn = False
        self.selected_member_name: str | None = None
        self.room_index = 0
        self.previous_room_index = 0
        self.rest_used_in_room = False
        self.skip_enemy_phase = False
        self.travel_percent = 0
        self.can_backtrack = False
        self.room_respawns_used: dict[int, int] = {}
        self.room_respawns_max = 2
        self.store_available_now = False
        self.store_triggered_this_adventure = False
        self.store_inventory: list[str] = []
        self.is_pvp_mode = False
        self.result_banner = ""
        self.pve_donation_pool: dict[str, int] = {}
        self.boss_reward_pending = False
        self.gold = 0
        self.inventory: dict[str, int] = {"healing_potion": 2}
        self.rooms = self._generate_tutorial_rooms() if self.is_tutorial else self._generate_rooms_for_adventure(self.adventure_number)
        self.party = party if party is not None else self._default_party()
        self.equipment = {
            self._equipment_key(unit): {"weapon": None, "armor": None}
            for unit in self.party
        }
        self.enemies: list[Unit] = []
        self.turn_index = 0
        self.round_number = 1
        self.tip_index = 0
        self.last_roll_text = "No roll yet."
        self.loot_non_rare_streak = 0
        self.loot_total_drops = 0
        self.last_drop_debug = ""
        self.log: list[str] = [
            f"Run mode: {self.run_mode}.",
            "Tutorial mode: guided one-room onboarding." if self.is_tutorial else "Your party descends into the crypt.",
            "Choose Venture Deeper to begin tutorial combat." if self.is_tutorial else "Choose Venture Deeper to begin the first encounter.",
        ]
        self._turn_order: list[Unit] = []
        self._update_travel_percent()
        self._append_log(f"Current room: {self.current_room_name()}")

    def rebuild_turn_order(self) -> None:
        self._turn_order = [unit for unit in self.party + self.enemies if unit.alive]
        if not self._turn_order:
            self.turn_index = 0
            return
        self.turn_index = self.turn_index % len(self._turn_order)

    def active_unit(self) -> Unit | None:
        if self.mode != "combat":
            return None
        if not self._turn_order:
            return None
        return self._turn_order[self.turn_index]

    def is_player_turn(self) -> bool:
        unit = self.active_unit()
        return unit in self.party if unit else False

    def game_over(self) -> bool:
        return self.mode in {"victory", "defeat"}

    def party_defeated(self) -> bool:
        return not any(unit.alive for unit in self.party)

    def enemies_defeated(self) -> bool:
        return self.mode == "combat" and not any(unit.alive for unit in self.enemies)

    def status_summary(self) -> str:
        if self.mode == "victory":
            return f"Victory! Adventure {self.adventure_number} cleared."
        if self.mode == "defeat" or self.party_defeated():
            return "Defeat... your party has fallen."
        if self.mode == "explore":
            return (
                f"Explore | Adventure {self.adventure_number} "
                f"| Room {self.room_index + 1}/{len(self.rooms)}: {self.current_room_name()} "
                f"| Travel {self.travel_percent}%"
            )
        actor = self.active_unit()
        if not actor:
            return "No active turn."
        return f"Adventure {self.adventure_number} | Round {self.round_number} | Current turn: {actor.name}"

    def menu_context_text(self) -> str:
        if self.mode != "combat":
            return "Explore"
        if self.menu == "map":
            return "Combat > Map"
        if self.menu == "attack_style":
            return "Combat > Attack > Style"
        if self.menu == "skill_list":
            return "Combat > Skills"
        if self.menu == "target_enemy":
            return "Combat > Target Enemy"
        if self.menu == "target_ally":
            return "Combat > Target Ally"
        return "Combat > Action"

    def action_requires_roll(self, action_label: str) -> bool:
        if self.mode != "combat":
            return False
        if self.menu == "target_enemy":
            if self.pending_action_type == "attack":
                return action_label.startswith("Target: ")
            if self.pending_action_type == "skill" and self.pending_skill_id:
                skill = self.SKILL_DEFS.get(self.pending_skill_id, {})
                return bool(skill) and not bool(skill.get("heal_min"))
        return False

    def action_labels(self) -> list[str]:
        if self.mode in {"victory", "defeat"}:
            if self.mode == "victory":
                return [Action.NEXT_ADVENTURE.value, "Restart with R", "Quit with Q"]
            return ["Restart with R", "Quit with Q"]
        if self.menu == "map":
            return [Action.CLOSE_MAP.value]
        if self.menu == "items":
            labels = [self._item_action_label(item_id) for item_id in self._consumables_available()]
            return labels + [Action.BACK.value]
        if self.menu == "store":
            labels: list[str] = []
            if self.store_inventory:
                labels.extend([f"Buy {item_label(item_id)} ({self._store_price(item_id)}g)" for item_id in self.store_inventory])
            labels.extend(self._store_craft_action_labels())
            labels.extend(self._store_trade_action_labels())
            labels.append(Action.BACK.value)
            return labels
        if self.menu == "equip-member":
            labels = [f"Equip: {unit.name}" for unit in self.party if unit.alive]
            return labels + [Action.BACK.value]
        if self.menu == "equip-item":
            labels = [self._gear_action_label(item_id) for item_id in self._gear_available_for_selected_member()]
            return labels + [Action.BACK.value]
        if self.menu == "attack_style":
            return [f"Style: {style}" for style in self.ATTACK_STYLES] + [Action.BACK.value]
        if self.menu == "skill_list":
            actor = self.active_unit()
            if not actor:
                return [Action.BACK.value]
            return self._skill_labels_for_unit(actor) + [Action.BACK.value]
        if self.menu == "target_enemy":
            return self._enemy_target_labels() + [Action.BACK.value]
        if self.menu == "target_ally":
            return self._ally_target_labels() + [Action.BACK.value]
        if self.mode == "explore":
            room = self.rooms[self.room_index] if self.room_index < len(self.rooms) else {}
            labels = [
                Action.VENTURE.value,
                Action.LOOK.value,
                *([Action.EXPLORE_SPACE.value] if self._can_explore_space(room) else []),
                *( [Action.OPEN_CHEST.value] if self._is_chest_openable_current_room() else [] ),
                *( [Action.BACKTRACK.value] if self.can_backtrack else [] ),
                *( [Action.HUNT.value] if self._can_hunt_current_room() else [] ),
                *( [Action.HARVEST.value] if self._can_harvest_current_room() else [] ),
                *( [Action.STORE.value] if self.store_available_now else [] ),
                Action.PATH.value,
                Action.BAG.value,
                Action.EQUIP.value,
                Action.REST.value,
            ]
            return labels
        actor = self.active_unit()
        if not actor or actor not in self.party:
            return []
        labels = [
            Action.ATTACK.value,
            Action.SKILLS.value,
            Action.DEFEND.value,
            Action.PATH.value,
            Action.BAG.value,
            Action.EQUIP.value,
            Action.REST.value,
        ]
        return labels

    def perform_player_action(self, action_label: str) -> None:
        self.action_consumed_turn = False
        if self.mode == "victory":
            if action_label == Action.NEXT_ADVENTURE.value:
                self._start_next_adventure()
            return
        if self.menu == "map":
            if action_label in {Action.CLOSE_MAP.value, Action.BACK.value}:
                self.menu = "combat_root" if self.mode == "combat" else "root"
            return
        if self.menu == "store":
            if action_label == Action.BACK.value:
                self.menu = "root"
                self.store_available_now = False
                return
            if action_label.startswith("Buy "):
                self._buy_store_item(action_label)
                return
            if action_label.startswith("Craft "):
                self._craft_item(self._recipe_id_from_store_label(action_label))
                return
            if action_label.startswith("Sell "):
                parsed = self._sale_from_store_label(action_label)
                if parsed:
                    item_id, qty = parsed
                    self._trade_item("merchant", item_id, qty)
                else:
                    self._append_log("Unknown trade option.")
                return
            return
        if self.menu == "attack_style":
            if action_label == Action.BACK.value:
                self._clear_pending_combat_selection()
                self.menu = "combat_root"
                return
            style = self._style_from_action_label(action_label)
            if style:
                self.pending_action_type = "attack"
                self.pending_style = style
                self.menu = "target_enemy"
            return
        if self.menu == "skill_list":
            if action_label == Action.BACK.value:
                self._clear_pending_combat_selection()
                self.menu = "combat_root"
                return
            skill_id = self._skill_id_from_action_label(action_label)
            actor = self.active_unit()
            if not skill_id or not actor or not actor.alive:
                return
            if skill_id not in self._skills_for_unit(actor):
                self._append_log("That skill is unavailable for this class.")
                return
            self.pending_action_type = "skill"
            self.pending_skill_id = skill_id
            target_type = str(self.SKILL_DEFS[skill_id].get("target", "enemy"))
            self.menu = "target_ally" if target_type == "ally" else "target_enemy"
            return
        if self.menu == "target_enemy":
            if action_label == Action.BACK.value:
                if self.pending_action_type == "attack":
                    self.menu = "attack_style"
                elif self.pending_action_type == "skill":
                    self.menu = "skill_list"
                else:
                    self.menu = "combat_root"
                return
            target = self._enemy_from_target_label(action_label)
            if not target:
                self._append_log("Choose a valid enemy target.")
                return
            consumed_turn = False
            if self.pending_action_type == "attack":
                style = self.pending_style or "Balanced"
                self._append_log(f"{self._short_name(self.active_unit().name if self.active_unit() else 'Hero')} chooses {style} Attack on {self._short_name(target.name)}.")
                consumed_turn = self._resolve_attack_on_target(target, style)
            elif self.pending_action_type == "skill" and self.pending_skill_id:
                consumed_turn = self._resolve_skill_on_target(self.pending_skill_id, target)
            self._clear_pending_combat_selection()
            self.menu = "combat_root"
            if consumed_turn:
                self._advance_turn()
                self.action_consumed_turn = True
            self._check_combat_resolution()
            return
        if self.menu == "target_ally":
            if action_label == Action.BACK.value:
                self.menu = "skill_list" if self.pending_action_type == "skill" else "combat_root"
                return
            target = self._ally_from_target_label(action_label)
            if not target:
                self._append_log("Choose a valid ally target.")
                return
            consumed_turn = False
            if self.pending_action_type == "skill" and self.pending_skill_id:
                consumed_turn = self._resolve_skill_on_target(self.pending_skill_id, target)
            self._clear_pending_combat_selection()
            self.menu = "combat_root"
            if consumed_turn:
                self._advance_turn()
                self.action_consumed_turn = True
            self._check_combat_resolution()
            return
        if action_label == Action.BACK.value:
            if self.menu == "equip-item":
                self.menu = "equip-member"
            else:
                self.menu = "combat_root" if self.mode == "combat" else "root"
            return
        if self.menu == "items":
            self._use_item_by_action_label(action_label)
            self.menu = "combat_root" if self.mode == "combat" else "root"
            return
        if self.menu == "equip-member":
            self._select_member(action_label)
            return
        if self.menu == "equip-item":
            self._equip_by_action_label(action_label)
            self.menu = "combat_root" if self.mode == "combat" else "root"
            self.selected_member_name = None
            return
        if action_label == Action.BAG.value:
            self.menu = "items"
            return
        if action_label == Action.PATH.value:
            self.menu = "map"
            return
        if action_label == Action.EQUIP.value:
            self.menu = "equip-member"
            return
        if self.mode == "explore":
            if action_label == Action.VENTURE.value:
                self._start_room_encounter()
            elif action_label == Action.LOOK.value:
                self._look_around()
            elif action_label == Action.EXPLORE_SPACE.value:
                self._explore_room_space()
            elif action_label == Action.OPEN_CHEST.value:
                self._open_room_chest()
            elif action_label == Action.BACKTRACK.value:
                self._backtrack()
            elif action_label == Action.HUNT.value:
                self._hunt_respawn()
            elif action_label == Action.HARVEST.value:
                self._harvest_room_node()
            elif action_label == Action.STORE.value:
                self._open_store()
            elif action_label == Action.REST.value:
                self._short_rest()
            return
        actor = self.active_unit()
        if not actor or actor not in self.party or not actor.alive:
            return
        if action_label == Action.ATTACK.value:
            self.pending_action_type = "attack"
            self.pending_style = None
            self.menu = "attack_style"
            return
        elif action_label == Action.SKILLS.value:
            self.pending_action_type = "skill"
            self.pending_skill_id = None
            self.menu = "skill_list"
            return
        elif action_label == Action.DEFEND.value:
            actor.defending = True
            self._append_log(f"{actor.name} braces for impact.")
            self._advance_turn()
            self.action_consumed_turn = True
        elif action_label == Action.REST.value:
            did_rest = self._short_rest()
            if did_rest:
                mana_gain = self._gain_mana(actor, 2)
                if mana_gain > 0:
                    self._append_log(f"{self._short_name(actor.name)} recovers {mana_gain} Mana.")
                self._advance_turn()
                self.action_consumed_turn = True
        self._check_combat_resolution()

    def run_enemy_turns_until_player(self) -> None:
        if self.skip_enemy_phase and self.mode == "combat":
            self.skip_enemy_phase = False
            self._append_log("Smoke bomb confuses the enemy line. Their phase is skipped.")
            while self.mode == "combat" and not self.game_over() and not self.is_player_turn():
                self._advance_turn()
                self._check_combat_resolution()
            return
        while self.mode == "combat" and not self.game_over() and not self.is_player_turn():
            actor = self.active_unit()
            if not actor or actor not in self.enemies:
                break
            target = self._choose_enemy_target(actor)
            if target:
                self._attack(actor, target)
            self._advance_turn()
            self._check_combat_resolution()

    def _append_log(self, text: str) -> None:
        self.log.append(text)
        self.log = self.log[-12:]

    def _advance_turn(self) -> None:
        if self.mode != "combat":
            return
        self.rebuild_turn_order()
        if self.mode != "combat" or not self._turn_order:
            return
        self.turn_index += 1
        if self.turn_index >= len(self._turn_order):
            self.turn_index = 0
            self.round_number += 1
        actor = self.active_unit()
        if actor and actor in self.party and actor.alive:
            gained = self._gain_mana(actor, 1)
            if gained > 0:
                self._append_log(f"{self._short_name(actor.name)} channels +{gained} Mana.")
        for unit in self._turn_order:
            if unit is not self.active_unit():
                unit.defending = False

    def _attack(
        self,
        attacker: Unit,
        target: Unit,
        *,
        hit_bonus: int = 0,
        damage_bonus: int = 0,
        damage_mult: float = 1.0,
        fixed_damage: tuple[int, int] | None = None,
        include_weapon_bonus: bool = True,
    ) -> bool:
        roll = self.rng.randint(1, 20)
        total = roll + attacker.attack_bonus + hit_bonus
        armor_class = self._armor_class(target)
        roll_parts = [f"d20 {roll}", f"+ {attacker.attack_bonus}"]
        if hit_bonus:
            roll_parts.append(f"{'+ ' if hit_bonus > 0 else '- '}{abs(hit_bonus)}")
        self.last_roll_text = f"{' '.join(roll_parts)} = {total} vs AC {armor_class}"
        if total < armor_class:
            self._append_log(f"{attacker.name} attacks {target.name} but misses ({total} vs AC {armor_class}).")
            return False
        if fixed_damage is not None:
            damage = self.rng.randint(fixed_damage[0], fixed_damage[1])
        else:
            weapon_bonus = self._weapon_bonus(attacker) if include_weapon_bonus else 0
            max_damage = attacker.damage_max + weapon_bonus
            damage = self.rng.randint(attacker.damage_min, max_damage)
        damage = max(1, int(round((damage + damage_bonus) * damage_mult)))
        if target.defending:
            damage = max(1, damage // 2)
        target.hp = max(0, target.hp - damage)
        self._append_log(f"{attacker.name} hits {target.name} for {damage} damage.")
        if target.hp <= 0:
            self._append_log(f"{target.name} is defeated.")
        return True

    def _armor_class(self, unit: Unit) -> int:
        bonus = 0
        if unit in self.party:
            armor_id = self.equipment.get(self._equipment_key(unit), {}).get("armor")
            if armor_id:
                bonus = int(ITEM_DEFS[armor_id]["ac_bonus"])
        return 11 + bonus

    def _weapon_bonus(self, attacker: Unit) -> int:
        if attacker in self.party:
            weapon_id = self.equipment.get(self._equipment_key(attacker), {}).get("weapon")
            if weapon_id:
                return int(ITEM_DEFS[weapon_id]["damage_bonus"])
        return 0

    @staticmethod
    def _first_alive(units: list[Unit]) -> Unit | None:
        for unit in units:
            if unit.alive:
                return unit
        return None

    @staticmethod
    def _lowest_hp_alive(units: list[Unit]) -> Unit | None:
        alive = [unit for unit in units if unit.alive]
        if not alive:
            return None
        return min(alive, key=lambda unit: unit.hp / unit.max_hp)

    def _choose_enemy_target(self, attacker: Unit) -> Unit | None:
        del attacker  # Reserved for future behavior that depends on enemy archetype.
        candidates = [unit for unit in self.party if unit.alive]
        if not candidates:
            return None
        weights: list[float] = []
        for unit in candidates:
            max_hp = max(1, unit.max_hp)
            ratio = unit.hp / max_hp
            weight = 1.0
            if ratio <= 0.33:
                weight *= 1.75
            elif ratio <= 0.66:
                weight *= 1.25
            weights.append(weight)
        total_weight = sum(weights)
        if total_weight <= 0:
            return candidates[0]
        roll = self.rng.random() * total_weight
        current = 0.0
        for unit, weight in zip(candidates, weights):
            current += weight
            if roll <= current:
                return unit
        return candidates[-1]

    def current_room_name(self) -> str:
        if self.room_index >= len(self.rooms):
            return "Cleared Depths"
        return self.rooms[self.room_index]["name"]

    def _generate_rooms_for_adventure(self, adventure_number: int) -> list[dict]:
        if self._is_boss_adventure(adventure_number):
            return [self._generate_boss_room_for_adventure(adventure_number)]
        scale = max(0, adventure_number - 1)
        rooms: list[dict] = []
        for index, base_room in enumerate(self.BASE_ROOMS):
            scaled_enemies: list[tuple[str, int, int, int, int]] = []
            for name, hp, attack_bonus, damage_min, damage_max in base_room["enemies"]:
                scaled_enemies.append(
                    (
                        name,
                        hp + (4 * scale),
                        attack_bonus + min(3, scale),
                        damage_min + min(2, scale // 2),
                        damage_max + min(3, scale),
                    )
                )
            rooms.append(
                {
                    "name": base_room["name"] if adventure_number == 1 else f"{base_room['name']} (A{adventure_number})",
                    "description": base_room["description"],
                    "enemies": scaled_enemies,
                    "loot": list(base_room["loot"]),
                    "look_encounter_checked": False,
                    "looked": False,
                    "spaces_total": 15,
                    "spaces_explored": 0,
                    "harvested": False,
                    "respawns_used": 0,
                    "chest": {
                        "present": True if index % 2 == 0 else adventure_number > 1,
                        "opened": False,
                        "discovered": False,
                        "search_attempts": 0,
                        "search_attempts_max": 2,
                        "search_dc": 13,
                        "tier": "rare" if index == len(self.BASE_ROOMS) - 1 else "common",
                    },
                }
            )
        return rooms

    def _generate_tutorial_rooms(self) -> list[dict]:
        return [
            {
                "name": "Training Annex",
                "description": "Lanterns reveal etched instructions across the stone floor.",
                "enemies": [("Training Wraith", 18, 2, 3, 6)],
                "loot": ["healing_potion", "rusty_sword"],
                "look_encounter_checked": True,
                "looked": False,
                "spaces_total": 6,
                "spaces_explored": 0,
                "harvested": False,
                "respawns_used": 0,
                "chest": {
                    "present": True,
                    "opened": False,
                    "discovered": False,
                    "search_attempts": 0,
                    "search_attempts_max": 2,
                    "search_dc": 10,
                    "tier": "common",
                },
            }
        ]

    def _is_boss_adventure(self, adventure_number: int | None = None) -> bool:
        value = self.adventure_number if adventure_number is None else adventure_number
        return value > 0 and value % self.BOSS_INTERVAL == 0

    def _generate_boss_room_for_adventure(self, adventure_number: int) -> dict:
        scale = max(0, adventure_number - 1)
        boss_hp = 60 + (8 * scale)
        boss_enemy = ("Sigil Tyrant", boss_hp, 5 + min(4, scale // 2), 8 + min(3, scale // 2), 14 + min(6, scale))
        enemies = [boss_enemy]
        if adventure_number >= 20:
            enemies.append(("Warden Echo", 28 + (4 * scale), 4 + min(3, scale // 3), 5 + min(2, scale // 3), 10 + min(4, scale // 2)))
        return {
            "name": f"Boss Reliquary (A{adventure_number})",
            "description": "An ancient tyrant rises from a ring of blazing sigils.",
            "enemies": enemies,
            "loot": ["holy_water", "boss_sigil_blade", "boss_warden_plate"],
            "look_encounter_checked": True,
            "looked": True,
            "spaces_total": 15,
            "spaces_explored": 15,
            "harvested": False,
            "respawns_used": 0,
            "chest": {
                "present": True,
                "opened": False,
                "discovered": True,
                "search_attempts": 0,
                "search_attempts_max": 0,
                "search_dc": 13,
                "tier": "rare",
            },
        }

    def depth_text(self) -> str:
        current_depth = min(self.room_index + 1, len(self.rooms))
        room = self.rooms[self.room_index] if self.room_index < len(self.rooms) else {}
        spaces_done = int(room.get("spaces_explored", 0))
        spaces_total = int(room.get("spaces_total", 15))
        return f"Depth: {current_depth}/{len(self.rooms)} | Travel: {self.travel_percent}% | Spaces: {spaces_done}/{spaces_total}"

    def room_mood_text(self) -> str:
        moods = [
            "Air is stale. Torches flicker.",
            "Chains rattle in distant echoes.",
            "Ancient runes pulse in the dark.",
        ]
        index = min(self.room_index, len(moods) - 1)
        if self.mode == "victory":
            return "Silence settles over the crypt."
        if self.mode == "defeat":
            return "Cold stone and silence remain."
        return moods[index]

    def next_tip(self) -> str:
        tip = self.TIPS[self.tip_index % len(self.TIPS)]
        self.tip_index += 1
        return f"Tip: {tip}"

    def dungeon_scale_text(self) -> str:
        parts: list[str] = []
        for index, room in enumerate(self.rooms):
            if index < self.room_index:
                marker = "x"
            elif index == self.room_index and self.mode != "victory":
                marker = ">"
            else:
                marker = "-"
            parts.append(f"[{marker}] {room['name']}")
        if self.mode == "victory":
            return "Path: " + " -> ".join(f"[x] {room['name']}" for room in self.rooms)
        return "Path: " + " -> ".join(parts)

    def battle_screen_text(self) -> str:
        if self.menu == "map":
            return self.map_overlay_text()
        if self.mode == "combat":
            lines = [
                "BATTLE SCREEN",
                f"Room: {self.current_room_name()}",
                f"Round: {self.round_number}",
                f"Mood: {self.room_mood_text()}",
                f"Menu: {self.menu_context_text()}",
            ]
            actor = self.active_unit()
            lines.append(f"Active: {actor.name if actor else 'Unknown'}")
            if actor and actor in self.party:
                lines.append(f"HP: {actor.hp}/{actor.max_hp}")
                lines.append(f"Mana: {actor.mana}/{actor.max_mana}")
            lines.append(f"Last Roll: {self.last_roll_text}")
            if self.pending_action_type == "attack" and self.pending_style:
                lines.append(f"Pending: {self.pending_style} Attack -> choose target")
            elif self.pending_action_type == "skill" and self.pending_skill_id:
                skill_name = self.SKILL_DEFS.get(self.pending_skill_id, {}).get("name", self.pending_skill_id)
                lines.append(f"Pending: {skill_name} -> choose target")
            lines.append("")
            lines.append("Turn Order:")
            if self._turn_order:
                for index, unit in enumerate(self._turn_order):
                    marker = ">" if index == self.turn_index else "-"
                    lines.append(f"{marker} {self._short_name(unit.name)}")
            else:
                lines.append("No turn order available.")
            lines.append("")
            lines.append("Enemy Status:")
            for enemy in self.enemies:
                intent = self._enemy_intent(enemy)
                alive_text = "[ALV]" if enemy.alive else "[DED]"
                lines.append(
                    f"{self._short_name(enemy.name):10} {self._hp_bar(enemy.hp, enemy.max_hp)} "
                    f"HP:{enemy.hp}/{enemy.max_hp} {alive_text} [{intent}]"
                )
            return "\n".join(lines)
        if self.mode == "explore":
            return f"BATTLE SCREEN\nNo active combat.\nMood: {self.room_mood_text()}\nChoose Venture Deeper to engage enemies."
        if self.mode == "victory":
            return (
                "====================\n"
                "      VICTORY\n"
                "====================\n"
                f"Final chamber cleared.\nMood: {self.room_mood_text()}\n"
                "Your party stands victorious.\nChoose Begin Next Adventure to continue."
            )
        return (
            "====================\n"
            "       DEFEAT\n"
            "====================\n"
            f"Your party was defeated.\nMood: {self.room_mood_text()}\nRestart to begin a new run."
        )

    def map_overlay_text(self) -> str:
        lines = [
            "MINI MAP OVERLAY",
            f"Depth: {min(self.room_index + 1, len(self.rooms))}/{len(self.rooms)}",
            "",
        ]
        for index, room in enumerate(self.rooms):
            if index < self.room_index:
                marker = "[x]"
            elif index == self.room_index and self.mode != "victory":
                marker = "[>]"
            else:
                marker = "[ ]"
            connector = "  |" if index < len(self.rooms) - 1 else "   "
            lines.append(f"{marker} {room['name']}")
            if index < len(self.rooms) - 1:
                lines.append(connector)
        lines.extend(
            [
                "",
                "Legend: [>] current, [x] cleared, [ ] upcoming",
                "Use 'Close Map' to return.",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _hp_bar(current_hp: int, max_hp: int, width: int = 12) -> str:
        if max_hp <= 0:
            return "|" + ("." * width) + "|"
        ratio = max(0.0, min(1.0, current_hp / max_hp))
        filled = int(round(ratio * width))
        return "|" + ("#" * filled) + ("." * (width - filled)) + "|"

    @staticmethod
    def _short_name(name: str) -> str:
        return name.split(" (", 1)[0]

    @staticmethod
    def _enemy_intent(enemy: Unit) -> str:
        if not enemy.alive:
            return "Down"
        ratio = enemy.hp / enemy.max_hp if enemy.max_hp else 0
        if ratio < 0.35:
            return "Frenzy"
        if enemy.defending:
            return "Guard"
        return "Strike"

    def inventory_text(self) -> str:
        if not any(quantity > 0 for quantity in self.inventory.values()):
            return "Empty"
        labels: list[str] = []
        for item_id in sorted(self.inventory):
            quantity = self.inventory[item_id]
            if quantity > 0:
                labels.append(f"{item_label(item_id)} x{quantity}")
        return ", ".join(labels[:3])

    def equipment_text(self) -> str:
        summaries: list[str] = []
        for unit in self.party:
            member_equipment = self.equipment.get(self._equipment_key(unit), {})
            weapon = item_label(member_equipment.get("weapon"))
            armor = item_label(member_equipment.get("armor"))
            summaries.append(f"{unit.name.split(' ')[0]}[W:{weapon},A:{armor}]")
        return " | ".join(summaries)

    def equipment_lines(self) -> list[str]:
        lines: list[str] = []
        for unit in self.party:
            member_equipment = self.equipment.get(self._equipment_key(unit), {})
            weapon = item_label(member_equipment.get("weapon"))
            armor = item_label(member_equipment.get("armor"))
            lines.append(
                f"{self._short_name(unit.name):10} {unit.archetype:7} "
                f"L{unit.level} XP:{unit.experience}/{unit.next_level_xp} "
                f"W:{weapon} A:{armor}"
            )
        return lines

    def _start_room_encounter(self) -> None:
        if self.room_index >= len(self.rooms):
            self.mode = "victory"
            return
        room = self.rooms[self.room_index]
        self.previous_room_index = self.room_index
        self.enemies = [
            Unit(name, hp=hp, max_hp=hp, attack_bonus=attack_bonus, damage_min=damage_min, damage_max=damage_max)
            for name, hp, attack_bonus, damage_min, damage_max in room["enemies"]
        ]
        self.mode = "combat"
        self.result_banner = ""
        self.combat_kind = "main"
        self.menu = "combat_root"
        self._clear_pending_combat_selection()
        self.round_number = 1
        self.turn_index = 0
        self.rebuild_turn_order()
        self._append_log(f"You enter {room['name']}: {room['description']}")

    def _look_around(self) -> None:
        if self.room_index >= len(self.rooms):
            self._append_log("You scan the crypt. Only silence remains.")
            return
        room = self.rooms[self.room_index]
        room["looked"] = True
        self._append_log(f"You survey {room['name']}: {room['description']}")
        enemy_count = len(room.get("enemies", []))
        if enemy_count <= 0:
            self._append_log("No immediate threats reveal themselves.")
        elif enemy_count == 1:
            self._append_log("You sense one hostile presence nearby.")
        else:
            self._append_log(f"You sense {enemy_count} hostile figures ahead.")
        if room.get("loot"):
            self._append_log("Clues suggest useful salvage deeper inside.")
        if self.is_tutorial:
            chest = room.get("chest", {})
            if isinstance(chest, dict) and bool(chest.get("present")) and not bool(chest.get("discovered")):
                chest["discovered"] = True
                chest["search_attempts"] = max(1, int(chest.get("search_attempts", 0)))
                self._append_log("Tutorial: You notice a chest tucked behind the practice pillars.")
        self._attempt_chest_discovery()
        self._attempt_look_encounter()

    @staticmethod
    def _can_explore_space(room: dict) -> bool:
        looked = bool(room.get("looked", False))
        spaces_total = int(room.get("spaces_total", 15))
        spaces_explored = int(room.get("spaces_explored", 0))
        return looked and spaces_explored < spaces_total

    def _explore_room_space(self) -> None:
        if self.room_index >= len(self.rooms):
            self._append_log("There are no more rooms to explore.")
            return
        room = self.rooms[self.room_index]
        if not self._can_explore_space(room):
            if not bool(room.get("looked", False)):
                self._append_log("Look Around first to scout this room.")
            else:
                self._append_log("You have explored every corner of this room.")
            return
        room["spaces_explored"] = int(room.get("spaces_explored", 0)) + 1
        current = int(room["spaces_explored"])
        total = int(room.get("spaces_total", 15))
        self._append_log(f"Room exploration: {current}/{total} spaces mapped.")
        self._trigger_space_event(room)
        if current in {5, 10, total}:
            if current == total:
                self._append_log("You fully mapped the room. You can push forward with confidence.")
            else:
                self._append_log("You discover new clues in the stonework as you explore deeper.")

    def _trigger_space_event(self, room: dict) -> None:
        roll = self.rng.random()
        if roll < 0.12:
            self._append_log("Space event: Ambush! A hidden foe rushes from the dark.")
            self._start_search_encounter()
            return
        if roll < 0.25:
            herbs = self.rng.randint(1, 2)
            self.inventory["crypt_herb"] = self.inventory.get("crypt_herb", 0) + herbs
            self._append_log(f"Space event: Resource cache found (+{herbs} Crypt Herb).")
            return
        if roll < 0.38:
            chest = room.get("chest", {})
            if isinstance(chest, dict) and bool(chest.get("present")) and not bool(chest.get("discovered")):
                dc = int(chest.get("search_dc", 13))
                new_dc = max(8, dc - 1)
                chest["search_dc"] = new_dc
                room["chest"] = chest
                self._append_log(f"Space event: Clues found. Chest search DC drops to {new_dc}.")
            else:
                self._append_log("Space event: You map useful routes through the room.")
            return
        if roll < 0.48:
            target = self._first_alive(self.party)
            if not target:
                return
            damage = self.rng.randint(1, 4)
            target.hp = max(0, target.hp - damage)
            self._append_log(f"Space event: Trap sprung! {self._short_name(target.name)} takes {damage} damage.")
            self._check_party_defeat_out_of_combat()
            return
        if roll < 0.58:
            gold_found = self.rng.randint(4, 12) + max(0, self.adventure_number - 1)
            self.gold += gold_found
            self._append_log(f"Space event: Hidden coin cache (+{gold_found}g).")
            return
        if roll < 0.68:
            target = self._lowest_hp_alive(self.party)
            if target:
                heal = self.rng.randint(3, 8)
                target.hp = min(target.max_hp, target.hp + heal)
                self._append_log(f"Space event: Restorative shrine heals {self._short_name(target.name)} for {heal}.")
            return
        if roll < 0.78:
            target = self._first_alive(self.party)
            if target:
                mana_gain = self._gain_mana(target, self.rng.randint(1, 3))
                if mana_gain > 0:
                    self._append_log(f"Space event: Arcane current restores {mana_gain} Mana to {self._short_name(target.name)}.")
                else:
                    self._append_log("Space event: Arcane current crackles, but your mana is already full.")
            return
        if roll < 0.88:
            loot_item = self._roll_item_drop(source="combat", room_loot=list(room.get("loot", [])))
            if loot_item:
                self._append_log(f"Space event: Hidden cache reveals {item_label(loot_item)}.")
            else:
                self._append_log("Space event: Hidden cache collapses into scrap.")
            return
        self._append_log("Space event: Quiet passage. No immediate danger.")

    def _check_party_defeat_out_of_combat(self) -> None:
        if self.mode != "explore":
            return
        if self.party_defeated():
            if not self.is_pvp_mode:
                self._donate_inventory_on_pve_death()
            self.mode = "defeat"
            self.result_banner = "DEFEAT"
            self.menu = "root"
            self._append_log("Your party succumbs while exploring the crypt.")

    def _attempt_look_encounter(self) -> None:
        if self.mode != "explore" or self.room_index >= len(self.rooms):
            return
        room = self.rooms[self.room_index]
        if bool(room.get("look_encounter_checked", False)):
            return
        room["look_encounter_checked"] = True
        if self.rng.random() > 0.33:
            self._append_log("No movement in the shadows... for now.")
            return
        self._append_log("Your search stirs lurking monsters from the dark!")
        self._start_search_encounter()

    def _start_search_encounter(self) -> None:
        scale = max(0, self.adventure_number - 1)
        enemy_count = 1 if self.rng.random() < 0.65 else 2
        enemy_pool = [
            ("Skittering Ghoul", 14 + (3 * scale), 2 + min(2, scale), 2 + min(1, scale), 5 + min(2, scale)),
            ("Crypt Spider", 12 + (2 * scale), 3 + min(2, scale), 2 + min(1, scale), 4 + min(2, scale)),
            ("Lost Sentry", 16 + (3 * scale), 2 + min(2, scale), 3 + min(1, scale), 6 + min(2, scale)),
        ]
        self.enemies = []
        for _ in range(enemy_count):
            name, hp, attack_bonus, damage_min, damage_max = self.rng.choice(enemy_pool)
            self.enemies.append(
                Unit(name, hp=hp, max_hp=hp, attack_bonus=attack_bonus, damage_min=damage_min, damage_max=damage_max)
            )
        self.mode = "combat"
        self.combat_kind = "search"
        self.menu = "combat_root"
        self._clear_pending_combat_selection()
        self.round_number = 1
        self.turn_index = 0
        self.rebuild_turn_order()
        self._append_log(f"Ambush! A roaming encounter begins in {self.current_room_name()}.")

    def _room_chest_state(self) -> dict | None:
        if self.room_index >= len(self.rooms):
            return None
        room = self.rooms[self.room_index]
        chest = room.get("chest")
        if not isinstance(chest, dict):
            return None
        chest.setdefault("present", False)
        chest.setdefault("opened", False)
        chest.setdefault("discovered", False)
        chest.setdefault("search_attempts", 0)
        chest.setdefault("search_attempts_max", 2)
        chest.setdefault("search_dc", 13)
        chest.setdefault("tier", "common")
        room["chest"] = chest
        return chest

    def _can_search_chest_current_room(self) -> bool:
        chest = self._room_chest_state()
        if not chest:
            return False
        if not bool(chest.get("present")) or bool(chest.get("opened")):
            return False
        if bool(chest.get("discovered")):
            return False
        return int(chest.get("search_attempts", 0)) < int(chest.get("search_attempts_max", 2))

    def _is_chest_openable_current_room(self) -> bool:
        chest = self._room_chest_state()
        if not chest:
            return False
        return bool(chest.get("present")) and bool(chest.get("discovered")) and not bool(chest.get("opened"))

    def _int_modifier_for_searcher(self) -> int:
        searcher = self._first_alive(self.party)
        if not searcher:
            return 0
        return self._stat_modifier(searcher.intelligence)

    def _attempt_chest_discovery(self) -> None:
        chest = self._room_chest_state()
        if not chest or not bool(chest.get("present")):
            return
        if bool(chest.get("opened")):
            return
        if bool(chest.get("discovered")):
            self._append_log("You already spotted the chest here.")
            return
        attempts = int(chest.get("search_attempts", 0))
        attempts_max = int(chest.get("search_attempts_max", 2))
        if attempts >= attempts_max:
            self._append_log("You find no more hidden stashes in this room.")
            return
        roll = self.rng.randint(1, 20)
        int_mod = self._int_modifier_for_searcher()
        total = roll + int_mod
        dc = int(chest.get("search_dc", 13))
        chest["search_attempts"] = attempts + 1
        if total >= dc:
            chest["discovered"] = True
            self._append_log(f"Search roll: d20 {roll} + INT {int_mod:+d} = {total} vs DC {dc}. Chest found!")
            self._append_log("You spot a treasure chest tucked behind rubble.")
            return
        attempts_left = max(0, attempts_max - int(chest["search_attempts"]))
        self._append_log(f"Search roll: d20 {roll} + INT {int_mod:+d} = {total} vs DC {dc}. Missed. Attempts left: {attempts_left}.")
        if attempts_left == 0:
            self._append_log("You find no more hidden stashes in this room.")

    def _open_room_chest(self) -> None:
        chest = self._room_chest_state()
        if not chest or not bool(chest.get("present")) or bool(chest.get("opened")):
            self._append_log("No unopened chest is here.")
            return
        if not bool(chest.get("discovered")):
            self._append_log("You need to find the chest first.")
            return
        room = self.rooms[self.room_index]
        chest["opened"] = True
        room["chest"] = chest
        scale = max(0, self.adventure_number - 1)
        tier = str(chest.get("tier", "common"))
        if tier == "rare":
            gold_found = self.rng.randint(18, 32) + (4 * scale)
            bonus_item_pool = ["holy_water", "smoke_bomb", "healing_potion"]
        else:
            gold_found = self.rng.randint(8, 18) + (2 * scale)
            bonus_item_pool = ["healing_potion", "smoke_bomb"]
        self.gold += gold_found
        self._append_log(f"You open the chest and claim {gold_found} gold.")
        if self.rng.random() < 0.9:
            room_loot = list(room.get("loot", [])) + bonus_item_pool
            item_id = self._roll_item_drop(source="chest", room_loot=room_loot)
            if item_id:
                self._append_log(f"Chest reward: {item_label(item_id)}.")

    def _can_backtrack(self) -> bool:
        return self.mode == "explore" and self.room_index > 0

    def _backtrack(self) -> None:
        if not self._can_backtrack():
            self._append_log("No previous room to backtrack to.")
            return
        self.room_index = max(0, self.room_index - 1)
        self.can_backtrack = self.room_index > 0
        self._update_travel_percent()
        self._append_log(f"You backtrack to {self.current_room_name()}.")

    def _can_hunt_current_room(self) -> bool:
        if self.mode != "explore" or self.room_index >= len(self.rooms):
            return False
        room = self.rooms[self.room_index]
        used = int(room.get("respawns_used", 0))
        return used < self.room_respawns_max

    def _hunt_respawn(self) -> None:
        if not self._can_hunt_current_room():
            self._append_log("No more monsters answer your hunt here.")
            return
        room = self.rooms[self.room_index]
        room["respawns_used"] = int(room.get("respawns_used", 0)) + 1
        self.combat_kind = "hunt"
        self._start_respawn_encounter(room)
        self._append_log("You stir the crypt and draw out another threat.")

    def _start_respawn_encounter(self, room: dict) -> None:
        enemies_def = list(room.get("enemies", []))
        if not enemies_def:
            self._append_log("Nothing emerges from the silence.")
            return
        pick_count = 1 if len(enemies_def) == 1 else self.rng.randint(1, min(2, len(enemies_def)))
        picked = [self.rng.choice(enemies_def) for _ in range(pick_count)]
        self.enemies = []
        for name, hp, attack_bonus, damage_min, damage_max in picked:
            scaled_hp = max(10, int(hp * 0.85))
            self.enemies.append(Unit(name, hp=scaled_hp, max_hp=scaled_hp, attack_bonus=attack_bonus, damage_min=damage_min, damage_max=damage_max))
        self.mode = "combat"
        self.menu = "combat_root"
        self._clear_pending_combat_selection()
        self.round_number = 1
        self.turn_index = 0
        self.rebuild_turn_order()

    def _can_harvest_current_room(self) -> bool:
        if self.mode != "explore" or self.room_index >= len(self.rooms):
            return False
        return not bool(self.rooms[self.room_index].get("harvested", False))

    def _harvest_room_node(self) -> None:
        if not self._can_harvest_current_room():
            self._append_log("No harvestable reagents remain here.")
            return
        room = self.rooms[self.room_index]
        room["harvested"] = True
        herbs = self.rng.randint(1, 3)
        self.inventory["crypt_herb"] = self.inventory.get("crypt_herb", 0) + herbs
        self._append_log(f"Harvested {herbs} Crypt Herb.")

    def _store_price(self, item_id: str) -> int:
        base = {
            "healing_potion": 12,
            "smoke_bomb": 18,
            "holy_water": 25,
            "rusty_sword": 28,
            "leather_vest": 24,
        }.get(item_id, 20)
        return base + max(0, (self.adventure_number - 1))

    def _open_store(self) -> None:
        if not self.store_available_now:
            self._append_log("No store caravan is currently available.")
            return
        pool = ["healing_potion", "smoke_bomb", "rusty_sword", "leather_vest"]
        if self.adventure_number >= 8:
            pool.append("holy_water")
        self.store_inventory = pool
        self.menu = "store"
        self._append_log("A wandering merchant opens shop.")

    def _buy_store_item(self, action_label: str) -> None:
        item_name = action_label.replace("Buy ", "", 1).rsplit(" (", 1)[0]
        item_id = None
        for candidate_id, item_data in ITEM_DEFS.items():
            if item_data.get("name") == item_name:
                item_id = candidate_id
                break
        if not item_id:
            self._append_log("Unknown store item.")
            return
        price = self._store_price(item_id)
        if self.gold < price:
            self._append_log(f"Not enough gold for {item_label(item_id)} ({price}g).")
            return
        self.gold -= price
        self.inventory[item_id] = self.inventory.get(item_id, 0) + 1
        self._append_log(f"Bought {item_label(item_id)} for {price}g.")

    def _craft_item(self, recipe_id: str) -> None:
        recipe = self.CRAFT_RECIPES.get(recipe_id)
        if not recipe:
            self._append_log("Unknown recipe.")
            return
        herb_cost = int(recipe.get("herbs", 0))
        gold_cost = int(recipe.get("gold", 0))
        current_herbs = self.inventory.get("crypt_herb", 0)
        if current_herbs < herb_cost or self.gold < gold_cost:
            self._append_log(
                f"Need {herb_cost} Crypt Herb and {gold_cost} gold to craft {item_label(recipe_id)}."
            )
            return
        self.inventory["crypt_herb"] = current_herbs - herb_cost
        self.gold -= gold_cost
        self.inventory[recipe_id] = self.inventory.get(recipe_id, 0) + 1
        self._append_log(
            f"Crafted {item_label(recipe_id)}. (-{herb_cost} Herb, -{gold_cost}g)"
        )

    def _trade_item(self, target_character_id: str, item_id: str, qty: int) -> None:
        if qty <= 0:
            self._append_log("Invalid trade quantity.")
            return
        if self.inventory.get(item_id, 0) < qty:
            self._append_log(f"Not enough {item_label(item_id)} to trade.")
            return
        sell_price = max(1, self._store_price(item_id) // 2)
        self.inventory[item_id] -= qty
        self.gold += sell_price * qty
        self._append_log(f"Traded {qty} {item_label(item_id)} for {sell_price * qty}g.")

    def _store_craft_action_labels(self) -> list[str]:
        labels: list[str] = []
        for recipe_id, recipe in self.CRAFT_RECIPES.items():
            herb_cost = int(recipe.get("herbs", 0))
            gold_cost = int(recipe.get("gold", 0))
            labels.append(f"Craft {item_label(recipe_id)} ({herb_cost} Herb + {gold_cost}g)")
        return labels

    def _store_trade_action_labels(self) -> list[str]:
        labels: list[str] = []
        for item_id in [*CONSUMABLE_IDS, *GEAR_IDS]:
            qty = self.inventory.get(item_id, 0)
            if qty <= 0:
                continue
            sell_price = max(1, self._store_price(item_id) // 2)
            labels.append(f"Sell {item_label(item_id)} x1 (+{sell_price}g)")
            if qty > 1:
                labels.append(f"Sell {item_label(item_id)} xAll (+{sell_price * qty}g)")
        return labels

    def _recipe_id_from_store_label(self, action_label: str) -> str:
        name = action_label.replace("Craft ", "", 1).split(" (", 1)[0]
        for item_id, item_data in ITEM_DEFS.items():
            if item_data.get("name") == name:
                return item_id
        return ""

    def _sale_from_store_label(self, action_label: str) -> tuple[str, int] | None:
        if not action_label.startswith("Sell "):
            return None
        sale_text = action_label.replace("Sell ", "", 1)
        item_name, _, qty_text = sale_text.partition(" x")
        item_name = item_name.strip()
        item_id = ""
        for candidate_id, item_data in ITEM_DEFS.items():
            if item_data.get("name") == item_name:
                item_id = candidate_id
                break
        if not item_id:
            return None
        inventory_qty = self.inventory.get(item_id, 0)
        if qty_text.startswith("All"):
            return item_id, inventory_qty
        raw_qty = qty_text.split(" ", 1)[0].strip()
        if not raw_qty.isdigit():
            return None
        qty = int(raw_qty)
        return item_id, qty

    def _start_next_adventure(self) -> None:
        self.adventure_number += 1
        self.mode = "explore"
        self.result_banner = ""
        self.combat_kind = "main"
        self.menu = "root"
        self.room_index = 0
        self.previous_room_index = 0
        self.rest_used_in_room = False
        self.skip_enemy_phase = False
        self.can_backtrack = False
        self.room_respawns_used = {}
        self.store_available_now = False
        self.store_triggered_this_adventure = False
        self.store_inventory = []
        self.boss_reward_pending = False
        self.round_number = 1
        self.turn_index = 0
        self.enemies = []
        self._turn_order = []
        self._clear_pending_combat_selection()
        self.rooms = self._generate_rooms_for_adventure(self.adventure_number)
        self._update_travel_percent()
        for unit in self.party:
            if unit.alive:
                unit.hp = unit.max_hp
                unit.mana = unit.max_mana
                unit.defending = False
        self._append_log(f"GM> A new threat rises. Adventure {self.adventure_number} begins.")

    def _clear_pending_combat_selection(self) -> None:
        self.pending_action_type = None
        self.pending_style = None
        self.pending_skill_id = None

    def _skills_for_unit(self, unit: Unit) -> list[str]:
        if unit.class_skills is not None:
            return [skill_id for skill_id in unit.class_skills if skill_id in self.SKILL_DEFS]
        return list(self.ARCHETYPE_SKILLS.get(unit.archetype, []))

    def _skill_labels_for_unit(self, unit: Unit) -> list[str]:
        labels: list[str] = []
        for skill_id in self._skills_for_unit(unit):
            skill = self.SKILL_DEFS[skill_id]
            labels.append(f"Skill: {skill['name']} ({skill['cost']} MP)")
        return labels

    def _style_from_action_label(self, action_label: str) -> str | None:
        if not action_label.startswith("Style: "):
            return None
        style = action_label.replace("Style: ", "", 1)
        return style if style in self.ATTACK_STYLES else None

    def _skill_id_from_action_label(self, action_label: str) -> str | None:
        if not action_label.startswith("Skill: "):
            return None
        if " (" in action_label:
            name = action_label.replace("Skill: ", "", 1).split(" (", 1)[0]
        else:
            name = action_label.replace("Skill: ", "", 1)
        for skill_id, skill in self.SKILL_DEFS.items():
            if skill["name"] == name:
                return skill_id
        return None

    def _enemy_target_labels(self) -> list[str]:
        labels: list[str] = []
        for enemy in self.enemies:
            if enemy.alive:
                labels.append(f"Target: {self._short_name(enemy.name)} {enemy.hp}/{enemy.max_hp}")
        return labels

    def _ally_target_labels(self) -> list[str]:
        labels: list[str] = []
        for ally in self.party:
            if ally.alive:
                labels.append(f"Target Ally: {self._short_name(ally.name)} {ally.hp}/{ally.max_hp}")
        return labels

    def _enemy_from_target_label(self, action_label: str) -> Unit | None:
        if not action_label.startswith("Target: "):
            return None
        rest = action_label.replace("Target: ", "", 1)
        short_name = rest.rsplit(" ", 1)[0] if " " in rest else rest
        for enemy in self.enemies:
            if enemy.alive and self._short_name(enemy.name) == short_name:
                return enemy
        return None

    def _ally_from_target_label(self, action_label: str) -> Unit | None:
        if not action_label.startswith("Target Ally: "):
            return None
        rest = action_label.replace("Target Ally: ", "", 1)
        short_name = rest.rsplit(" ", 1)[0] if " " in rest else rest
        for ally in self.party:
            if ally.alive and self._short_name(ally.name) == short_name:
                return ally
        return None

    def _gain_mana(self, unit: Unit, amount: int) -> int:
        if amount <= 0:
            return 0
        before = unit.mana
        unit.mana = min(unit.max_mana, unit.mana + amount)
        return unit.mana - before

    def _spend_mana(self, unit: Unit, amount: int) -> bool:
        if amount <= 0:
            return True
        if unit.mana < amount:
            self._append_log(f"Not enough Mana (need {amount}, have {unit.mana}).")
            return False
        unit.mana -= amount
        return True

    def _resolve_attack_on_target(self, target: Unit, style: str) -> bool:
        actor = self.active_unit()
        if not actor:
            return False
        style_data = self.ATTACK_STYLES.get(style, self.ATTACK_STYLES["Balanced"])
        self._attack(
            actor,
            target,
            hit_bonus=int(style_data["hit_bonus"]),
            damage_mult=float(style_data["damage_mult"]),
        )
        return True

    def _resolve_skill_on_target(self, skill_id: str, target: Unit) -> bool:
        actor = self.active_unit()
        if not actor:
            return False
        skill = self.SKILL_DEFS.get(skill_id)
        if not skill:
            self._append_log("Unknown skill.")
            return False
        cost = int(skill["cost"])
        if not self._spend_mana(actor, cost):
            return False
        skill_name = str(skill["name"])
        if skill.get("heal_min"):
            heal = self.rng.randint(int(skill["heal_min"]), int(skill["heal_max"]))
            target.hp = min(target.max_hp, target.hp + heal)
            self._append_log(f"{self._short_name(actor.name)} casts {skill_name} on {self._short_name(target.name)} (+{heal} HP).")
            return True
        if skill.get("aoe"):
            self._append_log(f"{self._short_name(actor.name)} unleashes {skill_name} across the enemy line.")
            for enemy in [unit for unit in self.enemies if unit.alive]:
                self._attack(
                    actor,
                    enemy,
                    hit_bonus=int(skill.get("hit_bonus", 0)),
                    fixed_damage=(int(skill["damage_min"]), int(skill["damage_max"])),
                    include_weapon_bonus=False,
                )
            return True
        self._append_log(f"{self._short_name(actor.name)} casts {skill_name} on {self._short_name(target.name)}.")
        hit = self._attack(
            actor,
            target,
            hit_bonus=int(skill.get("hit_bonus", 0)),
            damage_bonus=int(skill.get("damage_bonus", 0)),
            damage_mult=float(skill.get("damage_mult", 1.0)),
            include_weapon_bonus=not bool(skill.get("spell", False)),
        )
        if hit:
            if skill.get("strip_defend"):
                target.defending = False
            if skill.get("grant_defend"):
                actor.defending = True
        return True

    def _short_rest(self) -> bool:
        if self.rest_used_in_room:
            self._append_log("You have already rested in this room.")
            return False
        self.rest_used_in_room = True
        for unit in self.party:
            if unit.alive:
                heal = self.rng.randint(3, 7)
                unit.hp = min(unit.max_hp, unit.hp + heal)
        self._append_log("The party camps briefly and recovers some strength.")
        return True

    def _consumables_available(self) -> list[str]:
        return [item_id for item_id in CONSUMABLE_IDS if self.inventory.get(item_id, 0) > 0]

    def _gear_available_for_selected_member(self) -> list[str]:
        if not self.selected_member_name:
            return []
        available: list[str] = []
        member = self._find_party_member_by_name(self.selected_member_name)
        member_equipment = self.equipment.get(self._equipment_key(member), {}) if member else {}
        for item_id in GEAR_IDS:
            inventory_count = self.inventory.get(item_id, 0)
            equipped_elsewhere = self._equipped_count(item_id)
            already_equipped = member_equipment.get(str(ITEM_DEFS[item_id]["slot"])) == item_id
            if inventory_count > equipped_elsewhere or already_equipped:
                available.append(item_id)
        return available

    def _equipped_count(self, item_id: str) -> int:
        count = 0
        for member_equipment in self.equipment.values():
            if member_equipment.get("weapon") == item_id:
                count += 1
            if member_equipment.get("armor") == item_id:
                count += 1
        return count

    def _item_action_label(self, item_id: str) -> str:
        return f"Use {item_label(item_id)} ({self.inventory.get(item_id, 0)})"

    def _gear_action_label(self, item_id: str) -> str:
        if not self.selected_member_name:
            return f"Equip {item_label(item_id)}"
        slot = str(ITEM_DEFS[item_id]["slot"])
        member = self._find_party_member_by_name(self.selected_member_name)
        member_equipment = self.equipment.get(self._equipment_key(member), {}) if member else {}
        marker = " (equipped)" if member_equipment.get(slot) == item_id else ""
        ability_suffix = " *Boss Ability*" if ITEM_DEFS[item_id].get("skill_bonus_tag") else ""
        return f"Equip {item_label(item_id)} ({self.inventory.get(item_id, 0)}){marker}{ability_suffix}"

    def _select_member(self, action_label: str) -> None:
        if not action_label.startswith("Equip: "):
            self._append_log("Choose a party member to equip.")
            return
        member_name = action_label.replace("Equip: ", "", 1)
        member = self._find_party_member_by_name(member_name)
        if member is None:
            self._append_log("Invalid party member.")
            return
        self.selected_member_name = member.name
        self.menu = "equip-item"

    def _use_item_by_action_label(self, action_label: str) -> None:
        item_id = self._item_id_from_action_label(action_label, prefix="Use ")
        if not item_id:
            self._append_log("No usable item selected.")
            return
        if self.inventory.get(item_id, 0) <= 0:
            self._append_log(f"{item_label(item_id)} is not available.")
            return
        self.inventory[item_id] -= 1
        if item_id == "healing_potion":
            target = self.active_unit() if self.mode == "combat" and self.is_player_turn() else self._lowest_hp_alive(self.party)
            if target is None:
                self._append_log("No valid target for healing.")
                return
            amount = self.rng.randint(8, 14)
            target.hp = min(target.max_hp, target.hp + amount)
            self._append_log(f"{target.name} drinks a healing potion and restores {amount} HP.")
        elif item_id == "smoke_bomb":
            if self.mode != "combat":
                self._append_log("Smoke bomb can only be used in combat.")
                self.inventory[item_id] += 1
                return
            self.skip_enemy_phase = True
            self._append_log("A smoke bomb erupts and blinds the enemy line.")
            self._advance_turn()
            self.action_consumed_turn = True
        elif item_id == "holy_water":
            if self.mode != "combat":
                self._append_log("Holy water can only be used in combat.")
                self.inventory[item_id] += 1
                return
            target = self._first_alive(self.enemies)
            if target is None:
                self._append_log("No enemy target.")
                return
            amount = self.rng.randint(10, 16)
            target.hp = max(0, target.hp - amount)
            self._append_log(f"Holy water scorches {target.name} for {amount} damage.")
            if target.hp == 0:
                self._append_log(f"{target.name} is defeated.")
            self._advance_turn()
            self.action_consumed_turn = True
        self._check_combat_resolution()

    def _equip_by_action_label(self, action_label: str) -> None:
        item_id = self._item_id_from_action_label(action_label, prefix="Equip ")
        if not item_id or not self.selected_member_name:
            self._append_log("No gear selected.")
            return
        if self.inventory.get(item_id, 0) <= 0:
            self._append_log(f"{item_label(item_id)} is not available.")
            return
        member = self._find_party_member_by_name(self.selected_member_name)
        if member is None:
            self._append_log("Selected party member is missing.")
            return
        equipment_key = self._equipment_key(member)
        member_equipment = self.equipment.get(equipment_key, {})
        slot = str(ITEM_DEFS[item_id]["slot"])
        current = member_equipment.get(slot)
        if current == item_id:
            self._append_log(f"{item_label(item_id)} is already equipped by {self.selected_member_name}.")
            return
        if self._equipped_count(item_id) >= self.inventory.get(item_id, 0):
            self._append_log(f"All copies of {item_label(item_id)} are already equipped.")
            return
        member_equipment[slot] = item_id
        self.equipment[equipment_key] = member_equipment
        self._append_log(f"{member.name} equipped {item_label(item_id)}.")
        ability_text = self._boss_ability_text(item_id)
        if ability_text:
            self._append_log(f"Boss trait active: {ability_text}")

    @staticmethod
    def _item_id_from_action_label(action_label: str, prefix: str) -> str | None:
        if not action_label.startswith(prefix):
            return None
        rest = action_label[len(prefix) :]
        if " (" in rest:
            rest = rest.split(" (", 1)[0]
        for item_id, item_data in ITEM_DEFS.items():
            if item_data["name"] == rest:
                return item_id
        return None

    def _check_combat_resolution(self) -> None:
        if self.party_defeated():
            if not self.is_pvp_mode:
                self._donate_inventory_on_pve_death()
            self.mode = "defeat"
            self.result_banner = "DEFEAT"
            self.menu = "root"
            self._clear_pending_combat_selection()
            self.selected_member_name = None
            self._append_log("Your party falls in the crypt.")
            return
        if self.enemies_defeated():
            if self.combat_kind == "search":
                self._append_log("Roaming encounter won.")
                self.mode = "explore"
                self.result_banner = "VICTORY"
                self.menu = "root"
                self.enemies = []
                self._turn_order = []
                self.turn_index = 0
                self._clear_pending_combat_selection()
                self.selected_member_name = None
                self.combat_kind = "main"
                self._append_log("The area calms, but the main path still lies ahead.")
                return
            if self.combat_kind == "hunt":
                self._append_log("Hunt encounter won.")
                self.mode = "explore"
                self.result_banner = "VICTORY"
                self.menu = "root"
                self.enemies = []
                self._turn_order = []
                self.turn_index = 0
                self._clear_pending_combat_selection()
                self.selected_member_name = None
                self.combat_kind = "main"
                current_room = self.rooms[self.room_index]
                respawns_used = int(current_room.get("respawns_used", 1))
                factor = self.RESPawn_XP_FACTORS[min(respawns_used - 1, len(self.RESPawn_XP_FACTORS) - 1)]
                xp_amount = max(1, int((25 + (3 * self.adventure_number)) * factor))
                self._award_experience(xp_amount)
                self._append_log(f"Hunt reward: {xp_amount} XP ({int(factor * 100)}%).")
                if self.rng.random() < 0.55:
                    self._roll_item_drop(source="combat", room_loot=current_room.get("loot", []))
                return
            cleared_room = self.rooms[self.room_index]
            self._append_log("Encounter won.")
            self._grant_loot(cleared_room["loot"])
            self.room_index += 1
            self.can_backtrack = self.room_index > 0
            self._update_travel_percent()
            self.rest_used_in_room = False
            self.enemies = []
            self._turn_order = []
            self.turn_index = 0
            self.menu = "root"
            self._clear_pending_combat_selection()
            self.selected_member_name = None
            self.combat_kind = "main"
            self._maybe_enable_store(only_main_room_clear=True)
            if self.room_index >= len(self.rooms):
                self.mode = "victory"
                self.result_banner = "VICTORY"
                if self._is_boss_adventure():
                    self.boss_reward_pending = True
                    self._roll_boss_reward()
                self._append_log(f"Adventure {self.adventure_number} complete. You may begin the next descent.")
            else:
                self.mode = "explore"
                self._append_log(f"Path opens to the next room: {self.current_room_name()}.")

    def _grant_loot(self, loot_pool: list[str]) -> None:
        if not loot_pool:
            return
        scale = max(0, self.adventure_number - 1)
        gold_found = self.rng.randint(7, 18) + (3 * scale)
        self.gold += gold_found
        self._append_log(f"Found {gold_found} gold.")
        xp_found = self.rng.randint(20, 35) + (5 * scale)
        self._award_experience(xp_found)
        item_id = self._roll_item_drop(source="combat", room_loot=loot_pool)
        if item_id:
            self._append_log(f"Loot gained: {item_label(item_id)}.")

    def _update_travel_percent(self) -> None:
        room_total = max(1, len(self.rooms))
        completed = min(self.room_index, room_total)
        self.travel_percent = max(0, min(100, int((completed / room_total) * 100)))

    def _maybe_enable_store(self, *, only_main_room_clear: bool = False) -> None:
        if only_main_room_clear and self.combat_kind != "main":
            return
        if self.store_triggered_this_adventure:
            return
        if self.adventure_number % 10 not in {4, 8}:
            return
        self.store_available_now = True
        self.store_triggered_this_adventure = True
        self._append_log("A merchant caravan is nearby. Visit Store is available.")

    def _roll_boss_reward(self) -> None:
        boss_rewards = ["boss_sigil_blade", "boss_warden_plate", "holy_water"]
        reward = self.rng.choice(boss_rewards)
        self.inventory[reward] = self.inventory.get(reward, 0) + 1
        self.boss_reward_pending = False
        ability_text = self._boss_ability_text(reward)
        if ability_text:
            self._append_log(f"Boss reward: {item_label(reward)}. Ability: {ability_text}")
        else:
            self._append_log(f"Boss reward: {item_label(reward)} infused with relic power.")

    @staticmethod
    def _boss_ability_text(item_id: str) -> str:
        item_data = ITEM_DEFS.get(item_id, {})
        skill_tag = str(item_data.get("skill_bonus_tag", ""))
        if skill_tag == "boss_warden_strike":
            return "Sigil Burn — weapon attacks gain +2 bonus damage."
        if skill_tag == "boss_warden_guard":
            return "Warding Shell — gain +1 Mana each turn while defending."
        return ""

    def _donate_inventory_on_pve_death(self) -> None:
        donated_any = False
        for item_id, quantity in list(self.inventory.items()):
            if quantity <= 0:
                continue
            donated = max(0, int(quantity * self.DONATION_RATIO))
            if donated <= 0:
                continue
            self.inventory[item_id] -= donated
            self.pve_donation_pool[item_id] = self.pve_donation_pool.get(item_id, 0) + donated
            donated_any = True
        if donated_any:
            self._append_log("Your fallen party leaves supplies behind for future adventurers.")

    def _roll_item_drop(self, source: str, room_loot: list[str] | None = None) -> str | None:
        pity_active = self.loot_non_rare_streak >= self.RARE_PITY_THRESHOLD
        if pity_active:
            self._append_log("Pity active: guaranteed Rare")
        tier = self._roll_rarity_tier(source=source)
        candidates = self._eligible_items_for_tier(tier)
        if not candidates:
            candidates = self._eligible_items_for_tier("common")
            tier = "common"
        if not candidates:
            return None
        weighted_candidates = self._apply_smart_bias(candidates)
        weighted_candidates = self._inject_donation_pool_into_chest_rolls(source, weighted_candidates)
        if room_loot:
            room_set = set(room_loot)
            boosted: list[tuple[str, float]] = []
            for item_id, weight in weighted_candidates:
                boost = 1.2 if item_id in room_set else 1.0
                boosted.append((item_id, weight * boost))
            weighted_candidates = boosted
        item_id = self._weighted_item_choice(weighted_candidates)
        if item_id is None:
            return None
        final_item_id, salvage_gold = self._apply_duplicate_policy(item_id)
        self.loot_total_drops += 1
        if tier == "rare":
            self.loot_non_rare_streak = 0
        else:
            self.loot_non_rare_streak += 1
        tier_label = tier.capitalize()
        if final_item_id:
            self.last_drop_debug = f"{tier_label} -> {item_label(final_item_id)}"
            self._append_log(f"Loot roll: {self.last_drop_debug}")
            self.inventory[final_item_id] = self.inventory.get(final_item_id, 0) + 1
            if source == "chest" and self.pve_donation_pool.get(final_item_id, 0) > 0:
                self.pve_donation_pool[final_item_id] -= 1
                if self.pve_donation_pool[final_item_id] <= 0:
                    del self.pve_donation_pool[final_item_id]
                self._append_log("Recovered a donated relic from a past fallen run.")
            return final_item_id
        self.last_drop_debug = f"{tier_label} -> {item_label(item_id)} (salvaged)"
        self._append_log(f"Loot roll: {self.last_drop_debug}")
        if salvage_gold > 0:
            self.gold += salvage_gold
            self._append_log(f"Duplicate salvaged for {salvage_gold} gold.")
        return None

    def _inject_donation_pool_into_chest_rolls(
        self, source: str, weighted_candidates: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        if source != "chest" or not self.pve_donation_pool:
            return weighted_candidates
        boosted = list(weighted_candidates)
        for item_id, quantity in self.pve_donation_pool.items():
            if quantity <= 0:
                continue
            found = False
            for idx, (candidate, weight) in enumerate(boosted):
                if candidate == item_id:
                    boosted[idx] = (candidate, weight + min(4.0, quantity * 0.6))
                    found = True
                    break
            if not found and item_id in ITEM_DEFS:
                boosted.append((item_id, min(4.0, quantity * 0.6)))
        return boosted

    def _roll_rarity_tier(self, source: str = "combat") -> str:
        if self.loot_non_rare_streak >= self.RARE_PITY_THRESHOLD:
            return "rare"
        weights = self.CHEST_TIER_WEIGHTS if source == "chest" else self.LOOT_TIER_WEIGHTS
        roll = self.rng.randint(1, 100)
        threshold_common = int(weights["common"])
        threshold_uncommon = threshold_common + int(weights["uncommon"])
        if roll <= threshold_common:
            return "common"
        if roll <= threshold_uncommon:
            return "uncommon"
        return "rare"

    @staticmethod
    def _eligible_items_for_tier(tier: str) -> list[str]:
        normalized_tier = tier.lower()
        return [item_id for item_id in ITEM_DEFS if item_rarity(item_id) == normalized_tier]

    def _apply_smart_bias(self, candidates: list[str]) -> list[tuple[str, float]]:
        alive_archetypes = {unit.archetype for unit in self.party if unit.alive}
        weighted: list[tuple[str, float]] = []
        for item_id in candidates:
            item_data = ITEM_DEFS.get(item_id, {})
            weight = float(item_data.get("drop_weight", 1) or 1)
            tags = set(item_tags(item_id))
            if tags and tags.intersection(alive_archetypes):
                weight *= 1.35
            if is_gear(item_id):
                slot = str(item_data.get("slot", ""))
                if slot and self._party_has_missing_slot(slot):
                    weight *= 1.3
            max_useful = int(item_data.get("max_useful_copies", 99))
            current_copies = int(self.inventory.get(item_id, 0))
            if current_copies < max_useful:
                weight *= 1.2
            else:
                weight *= 0.75
            weighted.append((item_id, max(weight, 0.1)))
        return weighted

    def _apply_duplicate_policy(self, item_id: str) -> tuple[str | None, int]:
        if not is_gear(item_id):
            return item_id, 0
        item_data = ITEM_DEFS.get(item_id, {})
        max_useful = int(item_data.get("max_useful_copies", 99))
        next_count = int(self.inventory.get(item_id, 0)) + 1
        if next_count <= max_useful:
            return item_id, 0
        salvage_gold = int(item_data.get("salvage_gold", 0))
        return None, max(0, salvage_gold)

    def _weighted_item_choice(self, weighted_candidates: list[tuple[str, float]]) -> str | None:
        if not weighted_candidates:
            return None
        total_weight = sum(max(0.0, weight) for _, weight in weighted_candidates)
        if total_weight <= 0:
            return weighted_candidates[0][0]
        needle = self.rng.random() * total_weight
        current = 0.0
        for item_id, weight in weighted_candidates:
            current += max(0.0, weight)
            if needle <= current:
                return item_id
        return weighted_candidates[-1][0]

    def _party_has_missing_slot(self, slot: str) -> bool:
        for unit in self.party:
            if not unit.alive:
                continue
            equipment = self.equipment.get(self._equipment_key(unit), {})
            if not equipment.get(slot):
                return True
        return False

    def _award_experience(self, amount: int) -> None:
        if amount <= 0:
            return
        for unit in self.party:
            if not unit.alive:
                continue
            unit.experience += amount
            self._append_log(f"{self._short_name(unit.name)} gains {amount} XP.")
            while unit.experience >= unit.next_level_xp:
                unit.experience -= unit.next_level_xp
                unit.level += 1
                unit.next_level_xp += 50
                hp_gain = max(2, 4 + self._stat_modifier(unit.constitution))
                unit.max_hp += hp_gain
                unit.hp = min(unit.max_hp, unit.hp + hp_gain)
                if unit.level % 2 == 0:
                    unit.attack_bonus += 1
                    unit.damage_max += 1
                self._append_log(
                    f"{self._short_name(unit.name)} reached level {unit.level}! "
                    f"+{hp_gain} HP"
                )

    @staticmethod
    def _stat_modifier(value: int) -> int:
        return (value - 10) // 2

    @staticmethod
    def pvp_initiative_order(entries: list[tuple[str, int, int]]) -> list[str]:
        ordered = sorted(entries, key=lambda item: (int(item[1]), -int(item[2]), str(item[0]).casefold()))
        return [str(name) for name, _, _ in ordered]

    def to_dict(self) -> dict:
        return {
            "seed": self.seed,
            "run_mode": self.run_mode,
            "run_context": self.run_context,
            "adventure_number": self.adventure_number,
            "mode": self.mode,
            "combat_kind": self.combat_kind,
            "menu": self.menu,
            "pending_action_type": self.pending_action_type,
            "pending_style": self.pending_style,
            "pending_skill_id": self.pending_skill_id,
            "selected_member_name": self.selected_member_name,
            "room_index": self.room_index,
            "previous_room_index": self.previous_room_index,
            "rest_used_in_room": self.rest_used_in_room,
            "skip_enemy_phase": self.skip_enemy_phase,
            "travel_percent": self.travel_percent,
            "can_backtrack": self.can_backtrack,
            "room_respawns_used": self.room_respawns_used,
            "room_respawns_max": self.room_respawns_max,
            "store_available_now": self.store_available_now,
            "store_triggered_this_adventure": self.store_triggered_this_adventure,
            "store_inventory": self.store_inventory,
            "is_pvp_mode": self.is_pvp_mode,
            "result_banner": self.result_banner,
            "pve_donation_pool": self.pve_donation_pool,
            "boss_reward_pending": self.boss_reward_pending,
            "turn_index": self.turn_index,
            "round_number": self.round_number,
            "tip_index": self.tip_index,
            "last_roll_text": self.last_roll_text,
            "loot_non_rare_streak": self.loot_non_rare_streak,
            "loot_total_drops": self.loot_total_drops,
            "last_drop_debug": self.last_drop_debug,
            "gold": self.gold,
            "rooms": self.rooms,
            "inventory": self.inventory,
            "equipment": self.equipment,
            "party": [self._unit_to_dict(unit) for unit in self.party],
            "enemies": [self._unit_to_dict(unit) for unit in self.enemies],
            "log": self.log,
            "rng_state": base64.b64encode(pickle.dumps(self.rng.getstate())).decode("ascii"),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Game:
        game = cls.__new__(cls)
        game.seed = int(data.get("seed", 7))
        game.run_mode = str(data.get("run_mode", "normal"))
        game.run_context = str(data.get("run_context", "normal"))
        game.is_tutorial = game.run_context == "tutorial"
        game.adventure_number = int(data.get("adventure_number", 1))
        game.rng = random.Random(game.seed)
        rng_state = data.get("rng_state")
        if isinstance(rng_state, str):
            game.rng.setstate(pickle.loads(base64.b64decode(rng_state.encode("ascii"))))
        game.mode = str(data.get("mode", "explore"))
        game.combat_kind = str(data.get("combat_kind", "main"))
        game.menu = str(data.get("menu", "root"))
        game.pending_action_type = data.get("pending_action_type")
        game.pending_style = data.get("pending_style")
        game.pending_skill_id = data.get("pending_skill_id")
        game.action_consumed_turn = False
        game.selected_member_name = data.get("selected_member_name")
        game.room_index = int(data.get("room_index", 0))
        game.previous_room_index = int(data.get("previous_room_index", game.room_index))
        game.rest_used_in_room = bool(data.get("rest_used_in_room", False))
        game.skip_enemy_phase = bool(data.get("skip_enemy_phase", False))
        game.travel_percent = int(data.get("travel_percent", 0))
        game.can_backtrack = bool(data.get("can_backtrack", game.room_index > 0))
        game.room_respawns_used = {
            int(key): int(value) for key, value in dict(data.get("room_respawns_used", {})).items()
        }
        game.room_respawns_max = int(data.get("room_respawns_max", 2))
        game.store_available_now = bool(data.get("store_available_now", False))
        game.store_triggered_this_adventure = bool(data.get("store_triggered_this_adventure", False))
        game.store_inventory = [str(item) for item in list(data.get("store_inventory", []))]
        game.is_pvp_mode = bool(data.get("is_pvp_mode", False))
        game.result_banner = str(data.get("result_banner", ""))
        game.pve_donation_pool = {str(item): int(qty) for item, qty in dict(data.get("pve_donation_pool", {})).items()}
        game.boss_reward_pending = bool(data.get("boss_reward_pending", False))
        game.turn_index = int(data.get("turn_index", 0))
        game.round_number = int(data.get("round_number", 1))
        game.tip_index = int(data.get("tip_index", 0))
        game.last_roll_text = str(data.get("last_roll_text", "No roll yet."))
        game.loot_non_rare_streak = int(data.get("loot_non_rare_streak", 0))
        game.loot_total_drops = int(data.get("loot_total_drops", 0))
        game.last_drop_debug = str(data.get("last_drop_debug", ""))
        game.gold = int(data.get("gold", 0))
        loaded_rooms = list(data.get("rooms", []))
        game.rooms = loaded_rooms if loaded_rooms else (
            game._generate_tutorial_rooms() if game.is_tutorial else game._generate_rooms_for_adventure(game.adventure_number)
        )
        for index, room in enumerate(game.rooms):
            room.setdefault("look_encounter_checked", False)
            room.setdefault("looked", False)
            room.setdefault("spaces_total", 15)
            room.setdefault("spaces_explored", 0)
            room.setdefault("harvested", False)
            room.setdefault("respawns_used", 0)
            chest = room.get("chest")
            if not isinstance(chest, dict):
                # Backward compatibility: infer chest presence from old room pattern.
                room["chest"] = {
                    "present": True if index % 2 == 0 else game.adventure_number > 1,
                    "opened": False,
                    "discovered": False,
                    "search_attempts": 0,
                    "search_attempts_max": 2,
                    "search_dc": 13,
                    "tier": "rare" if index == len(game.rooms) - 1 else "common",
                }
            else:
                chest.setdefault("present", False)
                chest.setdefault("opened", False)
                chest.setdefault("discovered", False)
                chest.setdefault("search_attempts", 0)
                chest.setdefault("search_attempts_max", 2)
                chest.setdefault("search_dc", 13)
                chest.setdefault("tier", "common")
        game.inventory = dict(data.get("inventory", {}))
        game.party = [cls._unit_from_dict(item) for item in data.get("party", [])]
        equipment_data = data.get("equipment", {})
        if "weapon" in equipment_data or "armor" in equipment_data:
            # Legacy save compatibility: convert old shared equipment to party mapping.
            game.equipment = {game._equipment_key(unit): {"weapon": None, "armor": None} for unit in game.party}
            if game.party:
                key = game._equipment_key(game.party[0])
                game.equipment[key]["weapon"] = equipment_data.get("weapon")
                game.equipment[key]["armor"] = equipment_data.get("armor")
        else:
            game.equipment = {game._equipment_key(unit): {"weapon": None, "armor": None} for unit in game.party}
            for unit in game.party:
                legacy_member_data = equipment_data.get(unit.name, {})
                keyed_member_data = equipment_data.get(game._equipment_key(unit), {})
                member_data = keyed_member_data if keyed_member_data else legacy_member_data
                key = game._equipment_key(unit)
                game.equipment[key]["weapon"] = member_data.get("weapon")
                game.equipment[key]["armor"] = member_data.get("armor")
        game.enemies = [cls._unit_from_dict(item) for item in data.get("enemies", [])]
        game.log = list(data.get("log", []))[-12:] or ["Save loaded."]
        if game.travel_percent <= 0:
            game._update_travel_percent()
        game._turn_order = []
        if game.mode == "combat":
            game.rebuild_turn_order()
        return game

    @staticmethod
    def _unit_to_dict(unit: Unit) -> dict:
        return {
            "name": unit.name,
            "hp": unit.hp,
            "max_hp": unit.max_hp,
            "attack_bonus": unit.attack_bonus,
            "damage_min": unit.damage_min,
            "damage_max": unit.damage_max,
            "defending": unit.defending,
            "character_id": unit.character_id,
            "owner_type": unit.owner_type,
            "archetype": unit.archetype,
            "stats": {
                "str": unit.strength,
                "dex": unit.dexterity,
                "con": unit.constitution,
                "int": unit.intelligence,
                "wis": unit.wisdom,
                "cha": unit.charisma,
            },
            "progression": {
                "level": unit.level,
                "experience": unit.experience,
                "next_level_xp": unit.next_level_xp,
            },
            "mana": {
                "current": unit.mana,
                "max": unit.max_mana,
                "name": unit.resource_name,
            },
            "class_skills": list(unit.class_skills) if unit.class_skills else [],
        }

    @staticmethod
    def _unit_from_dict(data: dict) -> Unit:
        stats = data.get("stats", {})
        default_by_archetype = {
            "Fighter": {"str": 14, "dex": 10, "con": 13, "int": 10, "wis": 10, "cha": 10},
            "Rogue": {"str": 10, "dex": 14, "con": 12, "int": 12, "wis": 10, "cha": 10},
            "Cleric": {"str": 10, "dex": 10, "con": 13, "int": 10, "wis": 14, "cha": 10},
            "Mage": {"str": 8, "dex": 12, "con": 12, "int": 15, "wis": 12, "cha": 10},
        }
        archetype = str(data.get("archetype", "Adventurer"))
        defaults = default_by_archetype.get(archetype, {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        progression = data.get("progression", {})
        mana = data.get("mana", {})
        class_skills = data.get("class_skills")
        default_skills = list(Game.ARCHETYPE_SKILLS.get(archetype, []))
        return Unit(
            name=str(data.get("name", "Unknown")),
            hp=int(data.get("hp", 1)),
            max_hp=int(data.get("max_hp", 1)),
            attack_bonus=int(data.get("attack_bonus", 0)),
            damage_min=int(data.get("damage_min", 1)),
            damage_max=int(data.get("damage_max", 1)),
            defending=bool(data.get("defending", False)),
            character_id=str(data.get("character_id", "")),
            owner_type=str(data.get("owner_type", "npc_companion")),
            archetype=archetype,
            strength=int(stats.get("str", defaults["str"])),
            dexterity=int(stats.get("dex", defaults["dex"])),
            constitution=int(stats.get("con", defaults["con"])),
            intelligence=int(stats.get("int", defaults["int"])),
            wisdom=int(stats.get("wis", defaults["wis"])),
            charisma=int(stats.get("cha", defaults["cha"])),
            level=int(progression.get("level", 1)),
            experience=int(progression.get("experience", 0)),
            next_level_xp=int(progression.get("next_level_xp", 100)),
            mana=int(mana.get("current", mana.get("max", 6))),
            max_mana=int(mana.get("max", 6)),
            resource_name=str(mana.get("name", "Mana")),
            class_skills=list(class_skills) if isinstance(class_skills, list) and class_skills else default_skills,
        )

    @staticmethod
    def _equipment_key(unit: Unit) -> str:
        return unit.character_id or unit.name

    def _find_party_member_by_name(self, name: str | None) -> Unit | None:
        if not name:
            return None
        for unit in self.party:
            if unit.name == name:
                return unit
        return None

    @staticmethod
    def _default_party() -> list[Unit]:
        return [
            Unit(
                "Aria (Rogue)",
                hp=24,
                max_hp=24,
                attack_bonus=4,
                damage_min=4,
                damage_max=8,
                character_id="npc-aria",
                owner_type="npc_companion",
                archetype="Rogue",
                strength=10,
                dexterity=14,
                constitution=12,
                intelligence=12,
                wisdom=10,
                charisma=11,
                mana=6,
                max_mana=6,
                resource_name="Mana",
                class_skills=["rogue_precise_stab", "rogue_kidney_shot"],
            ),
            Unit(
                "Borin (Fighter)",
                hp=32,
                max_hp=32,
                attack_bonus=3,
                damage_min=5,
                damage_max=10,
                character_id="npc-borin",
                owner_type="npc_companion",
                archetype="Fighter",
                strength=14,
                dexterity=10,
                constitution=13,
                intelligence=10,
                wisdom=10,
                charisma=10,
                mana=5,
                max_mana=5,
                resource_name="Mana",
                class_skills=["fighter_power_strike", "fighter_guard_shove"],
            ),
            Unit(
                "Lyra (Cleric)",
                hp=28,
                max_hp=28,
                attack_bonus=2,
                damage_min=3,
                damage_max=6,
                character_id="npc-lyra",
                owner_type="npc_companion",
                archetype="Cleric",
                strength=10,
                dexterity=10,
                constitution=13,
                intelligence=10,
                wisdom=14,
                charisma=10,
                mana=8,
                max_mana=8,
                resource_name="Mana",
                class_skills=["cleric_smite", "cleric_mend"],
            ),
        ]
