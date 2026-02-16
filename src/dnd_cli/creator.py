from __future__ import annotations

import random
import uuid

from dnd_cli.game import Unit

STAT_KEYS = ("str", "dex", "con", "int", "wis", "cha")
POINT_BUY_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
POINT_BUY_BUDGET = 27

ARCHETYPES = {
    "Fighter": {
        "bonus": {"str": 2, "con": 1},
        "primary": "str",
        "hp_base": 26,
        "dmg_base": (5, 9),
        "companion_names": ["Borin", "Kara", "Vex"],
    },
    "Rogue": {
        "bonus": {"dex": 2, "int": 1},
        "primary": "dex",
        "hp_base": 22,
        "dmg_base": (4, 8),
        "companion_names": ["Aria", "Shade", "Nyx"],
    },
    "Cleric": {
        "bonus": {"wis": 2, "con": 1},
        "primary": "wis",
        "hp_base": 24,
        "dmg_base": (4, 7),
        "companion_names": ["Lyra", "Mara", "Talon"],
    },
    "Mage": {
        "bonus": {"int": 2, "dex": 1},
        "primary": "int",
        "hp_base": 20,
        "dmg_base": (3, 9),
        "companion_names": ["Orin", "Selene", "Quill"],
    },
}
ARCHETYPE_MANA = {"Fighter": 5, "Rogue": 6, "Cleric": 8, "Mage": 10}
ARCHETYPE_SKILLS = {
    "Fighter": ["fighter_power_strike", "fighter_guard_shove"],
    "Rogue": ["rogue_precise_stab", "rogue_kidney_shot"],
    "Cleric": ["cleric_smite", "cleric_mend"],
    "Mage": ["mage_arcane_bolt", "mage_force_burst"],
}


def default_stats() -> dict[str, int]:
    return {"str": 8, "dex": 8, "con": 8, "int": 8, "wis": 8, "cha": 8}


def validate_name(name: str) -> bool:
    trimmed = name.strip()
    if len(trimmed) < 2 or len(trimmed) > 16:
        return False
    for char in trimmed:
        if not (char.isalpha() or char in {" ", "-"}):
            return False
    return True


def point_buy_cost(stats: dict[str, int]) -> int:
    total = 0
    for key in STAT_KEYS:
        value = int(stats.get(key, 8))
        if value not in POINT_BUY_COST:
            raise ValueError(f"Invalid stat value for {key}: {value}")
        total += POINT_BUY_COST[value]
    return total


def remaining_points(stats: dict[str, int]) -> int:
    return POINT_BUY_BUDGET - point_buy_cost(stats)


def validate_point_buy(stats: dict[str, int]) -> bool:
    for key in STAT_KEYS:
        value = int(stats.get(key, 8))
        if value < 8 or value > 15:
            return False
    return point_buy_cost(stats) <= POINT_BUY_BUDGET


def recommended_stats(archetype: str) -> dict[str, int]:
    arrays = {
        "Fighter": {"str": 15, "dex": 12, "con": 14, "int": 8, "wis": 10, "cha": 13},
        "Rogue": {"str": 8, "dex": 15, "con": 12, "int": 14, "wis": 10, "cha": 13},
        "Cleric": {"str": 10, "dex": 8, "con": 14, "int": 12, "wis": 15, "cha": 13},
        "Mage": {"str": 8, "dex": 13, "con": 12, "int": 15, "wis": 14, "cha": 10},
    }
    return dict(arrays.get(archetype, default_stats()))


def random_name(seed: int) -> str:
    names = ["Alden", "Sable", "Rook", "Mira", "Dax", "Iris", "Thorne", "Kael"]
    rng = random.Random(seed)
    return rng.choice(names)


def build_main_character(name: str, archetype: str, allocated_stats: dict[str, int]) -> Unit:
    if archetype not in ARCHETYPES:
        raise ValueError(f"Unknown archetype: {archetype}")
    if not validate_name(name):
        raise ValueError("Invalid character name.")
    if not validate_point_buy(allocated_stats):
        raise ValueError("Invalid stat allocation.")
    final_stats = apply_archetype_bonus(allocated_stats, archetype)
    return _build_unit(
        name=name.strip(),
        archetype=archetype,
        stats=final_stats,
        owner_type="local_player",
        character_id=f"pc-{uuid.uuid4().hex[:8]}",
    )


def build_companions(main_archetype: str, seed: int = 7) -> list[Unit]:
    available = [archetype for archetype in ARCHETYPES if archetype != main_archetype]
    rng = random.Random(seed)
    rng.shuffle(available)
    picked = available[:2]
    companions: list[Unit] = []
    for index, archetype in enumerate(picked):
        names = ARCHETYPES[archetype]["companion_names"]
        name = str(names[index % len(names)])
        stats = apply_archetype_bonus(recommended_stats(archetype), archetype)
        companions.append(
            _build_unit(
                name=name,
                archetype=archetype,
                stats=stats,
                owner_type="npc_companion",
                character_id=f"npc-{archetype.lower()}-{index+1}",
            )
        )
    return companions


def preview_derived_stats(archetype: str, allocated_stats: dict[str, int]) -> dict[str, int]:
    if archetype not in ARCHETYPES:
        raise ValueError(f"Unknown archetype: {archetype}")
    if not validate_point_buy(allocated_stats):
        raise ValueError("Invalid stat allocation.")
    preview = _build_unit(
        name="Preview",
        archetype=archetype,
        stats=apply_archetype_bonus(allocated_stats, archetype),
        owner_type="local_player",
        character_id="preview",
    )
    return {
        "hp": preview.max_hp,
        "attack_bonus": preview.attack_bonus,
        "damage_min": preview.damage_min,
        "damage_max": preview.damage_max,
    }


def apply_archetype_bonus(stats: dict[str, int], archetype: str) -> dict[str, int]:
    output = {key: int(stats.get(key, 8)) for key in STAT_KEYS}
    bonus = ARCHETYPES[archetype]["bonus"]
    for key, value in bonus.items():
        output[key] += int(value)
    return output


def _modifier(value: int) -> int:
    return (value - 10) // 2


def _build_unit(name: str, archetype: str, stats: dict[str, int], owner_type: str, character_id: str) -> Unit:
    archetype_data = ARCHETYPES[archetype]
    con_mod = _modifier(stats["con"])
    primary_mod = _modifier(stats[str(archetype_data["primary"])])
    hp = max(14, int(archetype_data["hp_base"]) + (con_mod * 2))
    damage_min, damage_max = archetype_data["dmg_base"]
    damage_min = max(2, int(damage_min) + max(0, primary_mod // 2))
    damage_max = max(damage_min + 2, int(damage_max) + max(0, primary_mod))
    attack_bonus = 2 + primary_mod
    max_mana = int(ARCHETYPE_MANA.get(archetype, 6))
    return Unit(
        name=name,
        hp=hp,
        max_hp=hp,
        attack_bonus=attack_bonus,
        damage_min=damage_min,
        damage_max=damage_max,
        archetype=archetype,
        character_id=character_id,
        owner_type=owner_type,
        strength=stats["str"],
        dexterity=stats["dex"],
        constitution=stats["con"],
        intelligence=stats["int"],
        wisdom=stats["wis"],
        charisma=stats["cha"],
        mana=max_mana,
        max_mana=max_mana,
        resource_name="Mana",
        class_skills=list(ARCHETYPE_SKILLS.get(archetype, [])),
    )
