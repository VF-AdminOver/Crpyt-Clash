from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from dnd_cli.game import Game, Unit


def save_root() -> Path:
    root = Path.home() / ".dnd-cli" / "saves"
    root.mkdir(parents=True, exist_ok=True)
    return root


def profile_root() -> Path:
    root = Path.home() / ".dnd-cli" / "profile"
    root.mkdir(parents=True, exist_ok=True)
    return root


def roster_path() -> Path:
    return profile_root() / "roster.json"


def auth_path() -> Path:
    return profile_root() / "auth.json"


def tutorial_state_path() -> Path:
    return profile_root() / "tutorial.json"


def load_auth() -> dict:
    path = auth_path()
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def save_auth(payload: dict) -> None:
    path = auth_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)


def load_tutorial_state() -> dict:
    default = {"seen": False, "completed": False, "skipped": False, "version": 1}
    path = tutorial_state_path()
    if not path.exists():
        return dict(default)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return dict(default)
    return {
        "seen": bool(payload.get("seen", False)),
        "completed": bool(payload.get("completed", False)),
        "skipped": bool(payload.get("skipped", False)),
        "version": int(payload.get("version", 1) or 1),
        "updated_at": str(payload.get("updated_at", "")),
    }


def save_tutorial_state(payload: dict) -> None:
    path = tutorial_state_path()
    state = {
        "seen": bool(payload.get("seen", False)),
        "completed": bool(payload.get("completed", False)),
        "skipped": bool(payload.get("skipped", False)),
        "version": int(payload.get("version", 1) or 1),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp_path.replace(path)


def clear_auth() -> None:
    path = auth_path()
    if path.exists():
        path.unlink()


def hall_of_fame_root() -> Path:
    root = save_root() / "hall-of-fame"
    root.mkdir(parents=True, exist_ok=True)
    return root


def autosave_path(run_mode: str = "normal") -> Path:
    root = save_root()
    if run_mode == "ironman":
        return root / "ironman.json"
    return root / "autosave.json"


def slot_path(name: str) -> Path:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        raise ValueError("Slot name must include letters or numbers.")
    if len(slug) > 40:
        raise ValueError("Slot name is too long.")
    return save_root() / f"slot-{slug}.json"


def save_game(game: Game, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = game.to_dict()
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)


def load_roster() -> list[dict]:
    path = roster_path()
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    rows: list[dict] = []
    for entry in payload:
        if isinstance(entry, dict):
            rows.append(entry)
    return rows


def save_roster(roster: list[dict]) -> None:
    path = roster_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(roster, indent=2), encoding="utf-8")
    temp_path.replace(path)


def upsert_roster_hero(unit: Unit) -> None:
    hero = {
        "character_id": unit.character_id or unit.name,
        "name": unit.name,
        "archetype": unit.archetype,
        "level": unit.level,
        "owner_type": unit.owner_type,
        "attack_bonus": unit.attack_bonus,
        "damage_min": unit.damage_min,
        "damage_max": unit.damage_max,
        "max_hp": unit.max_hp,
        "max_mana": unit.max_mana,
        "stats": {
            "str": unit.strength,
            "dex": unit.dexterity,
            "con": unit.constitution,
            "int": unit.intelligence,
            "wis": unit.wisdom,
            "cha": unit.charisma,
        },
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    roster = load_roster()
    hero_id = str(hero["character_id"])
    replaced = False
    for index, existing in enumerate(roster):
        if str(existing.get("character_id", "")) == hero_id:
            roster[index] = hero
            replaced = True
            break
    if not replaced:
        roster.append(hero)
    save_roster(roster)


def list_roster_heroes() -> list[dict]:
    roster = load_roster()
    return sorted(roster, key=lambda row: str(row.get("updated_at", "")), reverse=True)


def delete_roster_hero(character_id: str) -> None:
    target = character_id.strip()
    if not target:
        return
    roster = [row for row in load_roster() if str(row.get("character_id", "")) != target]
    save_roster(roster)


def load_game(path: Path) -> Game:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Game.from_dict(payload)


def save_slot(game: Game, slot_name: str) -> Path:
    if game.run_mode == "ironman":
        raise ValueError("Ironman runs cannot create manual slots.")
    path = slot_path(slot_name)
    save_game(game, path)
    return path


def load_slot(slot_name: str) -> Game:
    path = slot_path(slot_name)
    if not path.exists():
        raise FileNotFoundError(path)
    return load_game(path)


def list_saves() -> list[Path]:
    root = save_root()
    return sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)


def list_hall_of_fame() -> list[Path]:
    root = hall_of_fame_root()
    return sorted(root.glob("ironman-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)


def list_normal_saves() -> list[Path]:
    return [path for path in list_saves() if path.name != "ironman.json"]


def latest_normal_save() -> Path | None:
    saves = list_normal_saves()
    return saves[0] if saves else None


def active_ironman_save() -> Path | None:
    path = autosave_path(run_mode="ironman")
    return path if path.exists() else None


def delete_active_ironman_save() -> None:
    path = autosave_path(run_mode="ironman")
    if path.exists():
        path.unlink()


def archive_ironman_victory(game: Game) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = hall_of_fame_root() / f"ironman-{stamp}.json"
    save_game(game, path)
    delete_active_ironman_save()
    return path
