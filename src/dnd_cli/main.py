from __future__ import annotations

import argparse
from pathlib import Path

from dnd_cli.creator import build_companions
from dnd_cli.game import Game
from dnd_cli.multiplayer import HostService, OnlineClient, default_join_code
from dnd_cli.storage import (
    active_ironman_save,
    autosave_path,
    list_hall_of_fame,
    latest_normal_save,
    list_saves,
    load_game,
    load_roster,
    load_slot,
    list_roster_heroes,
    save_game,
    save_slot,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cryptclash", description="Crypt Clash terminal RPG")
    subparsers = parser.add_subparsers(dest="command")
    parser.set_defaults(command="new", mode="normal", hero="")

    parser_new = subparsers.add_parser("new", help="Start a new game")
    parser_new.add_argument("--mode", choices=["normal", "ironman"], default="normal")
    parser_new.add_argument("--hero", default="", help="Start with a saved hero character_id from roster")

    subparsers.add_parser("continue", help="Continue the most recent run")

    parser_load = subparsers.add_parser("load", help="Load a save by file or slot")
    parser_load.add_argument("--file", type=Path)
    parser_load.add_argument("--slot")
    parser_load.add_argument("--force", action="store_true", help="Allow loading arbitrary files for ironman saves.")

    parser_save = subparsers.add_parser("save", help="Copy latest normal run to a slot")
    parser_save.add_argument("--slot", required=True)

    subparsers.add_parser("list-saves", help="List all save files")
    subparsers.add_parser("tip", help="Show a gameplay tip")

    parser_host = subparsers.add_parser("host", help="Host an online run")
    parser_host.add_argument("--bind", default="0.0.0.0")
    parser_host.add_argument("--port", type=int, default=8765)
    parser_host.add_argument("--code", default="")
    parser_host.add_argument("--mode", choices=["normal", "ironman"], default="normal")
    parser_host.add_argument("--name", default="Host")
    parser_host.add_argument("--hero", default="", help="Host with a saved hero character_id from roster")
    parser_host.add_argument("--chat-mode", choices=["reactions_only", "text_18_plus"], default="reactions_only")

    parser_join = subparsers.add_parser("join", help="Join an online host")
    parser_join.add_argument("--host", required=True)
    parser_join.add_argument("--port", type=int, default=8765)
    parser_join.add_argument("--code", required=True)
    parser_join.add_argument("--name", required=True)

    subparsers.add_parser("roster", help="List saved roster heroes")
    return parser


def _unit_from_roster_row(row: dict):
    from dnd_cli.game import Unit

    stats = dict(row.get("stats", {}))
    max_hp = int(row.get("max_hp", 22))
    max_mana = int(row.get("max_mana", 6))
    return Unit(
        name=str(row.get("name", "Hero")),
        hp=max_hp,
        max_hp=max_hp,
        attack_bonus=int(row.get("attack_bonus", 2)),
        damage_min=int(row.get("damage_min", 3)),
        damage_max=int(row.get("damage_max", 7)),
        character_id=str(row.get("character_id", "")),
        owner_type=str(row.get("owner_type", "local_player")),
        archetype=str(row.get("archetype", "Adventurer")),
        strength=int(stats.get("str", 10)),
        dexterity=int(stats.get("dex", 10)),
        constitution=int(stats.get("con", 10)),
        intelligence=int(stats.get("int", 10)),
        wisdom=int(stats.get("wis", 10)),
        charisma=int(stats.get("cha", 10)),
        level=int(row.get("level", 1)),
        mana=max_mana,
        max_mana=max_mana,
        resource_name="Mana",
        class_skills=None,
    )


def _party_from_roster_hero(hero_id: str, parser: argparse.ArgumentParser):
    roster = load_roster()
    match = None
    for hero in roster:
        if str(hero.get("character_id", "")) == hero_id:
            match = hero
            break
    if not match:
        parser.error(f"Roster hero not found: {hero_id}")
    main_character = _unit_from_roster_row(match)
    companions = build_companions(main_character.archetype, seed=7)
    return [main_character] + companions


def _resolve_load_target(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Game:
    if bool(args.file) == bool(args.slot):
        parser.error("Use exactly one of --file or --slot.")
    if args.slot:
        return load_slot(args.slot)
    assert args.file is not None
    if not args.file.exists():
        parser.error(f"Save file not found: {args.file}")
    game = load_game(args.file)
    if game.run_mode == "ironman" and not args.force:
        parser.error("Ironman file load requires --force.")
    return game


def _run_game(game: Game, creation_enabled: bool = False, seed: int = 7) -> None:
    from dnd_cli.app import DndApp

    app = DndApp(
        game=game,
        save_path=autosave_path(game.run_mode),
        creation_enabled=creation_enabled,
        run_mode=game.run_mode,
        seed=seed,
    )
    app.run()


def _run_online_ui(host: str, port: int, code: str, name: str) -> None:
    from dnd_cli.app import DndApp

    client = OnlineClient(host=host, port=port, code=code, name=name)
    client.start()
    app = DndApp(game=Game(seed=7, run_mode="normal"), online_client=client)
    app.run()


def run() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    command = args.command or "new"
    hero_id = str(getattr(args, "hero", "")).strip()

    if command == "list-saves":
        saves = list_saves()
        hall_entries = list_hall_of_fame()
        if not saves and not hall_entries:
            print("No save files found.")
            return
        if saves:
            print("Active Saves:")
            for path in saves:
                print(path)
        if hall_entries:
            print("Hall of Fame:")
            for path in hall_entries:
                print(path)
        return

    if command == "tip":
        print(Game().next_tip())
        return

    if command == "roster":
        heroes = list_roster_heroes()
        if not heroes:
            print("No roster heroes saved yet.")
            return
        print("Roster Heroes:")
        for hero in heroes:
            print(
                f"{hero.get('character_id', 'no-id')} | "
                f"{hero.get('name', 'Unknown')} | "
                f"{hero.get('archetype', 'Adventurer')} | "
                f"Lv{hero.get('level', 1)}"
            )
        return

    if command == "save":
        source = latest_normal_save()
        if not source:
            parser.error("No normal save found to copy into a slot.")
        game = load_game(source)
        if game.run_mode == "ironman":
            parser.error("Cannot save an ironman run into slots.")
        path = save_slot(game, args.slot)
        print(f"Saved slot: {path}")
        return

    if command == "host":
        party = _party_from_roster_hero(hero_id, parser) if hero_id else None
        join_code = args.code.strip() or default_join_code()
        service = HostService(
            bind=args.bind,
            port=args.port,
            code=join_code,
            mode=args.mode,
            party=party,
            chat_mode=args.chat_mode,
        )
        service.start()
        if not service.wait_until_ready(timeout=3):
            parser.error(f"Unable to start host: {service.error or 'unknown error'}")
        print(f"Host online: {args.bind}:{args.port} code={join_code}")
        _run_online_ui(host="127.0.0.1", port=args.port, code=join_code, name=args.name)
        return

    if command == "join":
        _run_online_ui(host=args.host, port=args.port, code=args.code, name=args.name)
        return

    if command == "load":
        game = _resolve_load_target(args, parser)
        game.log.append("Loaded save.")
        game.log = game.log[-12:]
        _run_game(game)
        return

    if command == "continue":
        ironman = active_ironman_save()
        if ironman:
            game = load_game(ironman)
            game.log.append(f"Loaded ironman run: {ironman.name}")
            game.log = game.log[-12:]
            _run_game(game)
            return
        path = latest_normal_save()
        if path and path.exists():
            game = load_game(path)
            game.log.append(f"Loaded latest save: {path.name}")
            game.log = game.log[-12:]
            _run_game(game)
            return
        _run_game(Game(seed=7, run_mode="normal"))
        return

    if hero_id:
        game = Game(seed=7, run_mode=args.mode, party=_party_from_roster_hero(hero_id, parser))
        save_game(game, autosave_path(game.run_mode))
        _run_game(game, creation_enabled=False, seed=7)
        return
    game = Game(seed=7, run_mode=args.mode)
    save_game(game, autosave_path(game.run_mode))
    _run_game(game, creation_enabled=True, seed=7)


if __name__ == "__main__":
    run()
