from __future__ import annotations

ITEM_DEFS: dict[str, dict[str, object]] = {
    "healing_potion": {
        "name": "Healing Potion",
        "kind": "consumable",
        "slot": "",
        "damage_bonus": 0,
        "ac_bonus": 0,
        "rarity": "common",
        "drop_weight": 16,
        "archetype_tags": [],
        "max_useful_copies": 8,
        "salvage_gold": 2,
    },
    "smoke_bomb": {
        "name": "Smoke Bomb",
        "kind": "consumable",
        "slot": "",
        "damage_bonus": 0,
        "ac_bonus": 0,
        "rarity": "uncommon",
        "drop_weight": 10,
        "archetype_tags": ["Rogue"],
        "max_useful_copies": 6,
        "salvage_gold": 4,
    },
    "holy_water": {
        "name": "Holy Water",
        "kind": "consumable",
        "slot": "",
        "damage_bonus": 0,
        "ac_bonus": 0,
        "rarity": "rare",
        "drop_weight": 7,
        "archetype_tags": ["Cleric", "Mage"],
        "max_useful_copies": 5,
        "salvage_gold": 6,
    },
    "rusty_sword": {
        "name": "Rusty Sword",
        "kind": "gear",
        "slot": "weapon",
        "damage_bonus": 1,
        "ac_bonus": 0,
        "rarity": "common",
        "drop_weight": 14,
        "archetype_tags": ["Fighter", "Rogue"],
        "max_useful_copies": 2,
        "salvage_gold": 8,
    },
    "leather_vest": {
        "name": "Leather Vest",
        "kind": "gear",
        "slot": "armor",
        "damage_bonus": 0,
        "ac_bonus": 1,
        "rarity": "uncommon",
        "drop_weight": 12,
        "archetype_tags": [],
        "max_useful_copies": 2,
        "salvage_gold": 10,
    },
    "crypt_herb": {
        "name": "Crypt Herb",
        "kind": "material",
        "slot": "",
        "damage_bonus": 0,
        "ac_bonus": 0,
        "rarity": "common",
        "drop_weight": 8,
        "archetype_tags": [],
        "max_useful_copies": 20,
        "salvage_gold": 1,
    },
    "boss_sigil_blade": {
        "name": "Boss Sigil Blade",
        "kind": "gear",
        "slot": "weapon",
        "damage_bonus": 2,
        "ac_bonus": 0,
        "rarity": "rare",
        "drop_weight": 2,
        "archetype_tags": ["Fighter", "Rogue"],
        "max_useful_copies": 1,
        "salvage_gold": 40,
        "on_hit_effect": "sigil_burn",
        "skill_bonus_tag": "boss_warden_strike",
    },
    "boss_warden_plate": {
        "name": "Boss Warden Plate",
        "kind": "gear",
        "slot": "armor",
        "damage_bonus": 0,
        "ac_bonus": 2,
        "rarity": "rare",
        "drop_weight": 2,
        "archetype_tags": ["Fighter", "Cleric"],
        "max_useful_copies": 1,
        "salvage_gold": 40,
        "on_hit_effect": "warding_shell",
        "skill_bonus_tag": "boss_warden_guard",
    },
}

CONSUMABLE_IDS = [item_id for item_id, item in ITEM_DEFS.items() if item["kind"] == "consumable"]
GEAR_IDS = [item_id for item_id, item in ITEM_DEFS.items() if item["kind"] == "gear"]


def item_label(item_id: str | None) -> str:
    if not item_id:
        return "None"
    item = ITEM_DEFS.get(item_id)
    return str(item["name"]) if item else item_id


def is_gear(item_id: str) -> bool:
    item = ITEM_DEFS.get(item_id, {})
    return str(item.get("kind", "")) == "gear"


def item_rarity(item_id: str) -> str:
    item = ITEM_DEFS.get(item_id, {})
    rarity = str(item.get("rarity", "common")).lower()
    return rarity if rarity in {"common", "uncommon", "rare"} else "common"


def item_tags(item_id: str) -> list[str]:
    item = ITEM_DEFS.get(item_id, {})
    tags = item.get("archetype_tags", [])
    if isinstance(tags, list):
        return [str(tag) for tag in tags]
    return []
