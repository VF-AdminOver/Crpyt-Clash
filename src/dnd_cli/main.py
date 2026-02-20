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
    load_tutorial_state,
    save_game,
    save_slot,
    save_tutorial_state,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cryptclash", description="Crypt Clash terminal RPG")
    subparsers = parser.add_subparsers(dest="command")
    parser.set_defaults(command="menu", mode="normal", hero="")

    subparsers.add_parser("menu", help="Open launcher menu")

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

    parser_register = subparsers.add_parser("register", help="Register an online account")
    parser_register.add_argument("--server", default="", help="Optional server URL (defaults to last used/local)")
    parser_register.add_argument("--username", required=True)
    parser_register.add_argument("--password", default="", help="Optional password (if omitted, prompt securely)")

    parser_login = subparsers.add_parser("login", help="Login to online account")
    parser_login.add_argument("--server", default="", help="Optional server URL (defaults to last used/local)")
    parser_login.add_argument("--username", required=True)
    parser_login.add_argument("--password", default="", help="Optional password (if omitted, prompt securely)")

    subparsers.add_parser("logout", help="Logout from online account")
    subparsers.add_parser("characters", help="List online characters")

    parser_character = subparsers.add_parser("character", help="Character operations")
    character_subparsers = parser_character.add_subparsers(dest="character_command")
    parser_character_create = character_subparsers.add_parser("create", help="Create an online character")
    parser_character_create.add_argument("--name", default="")
    parser_character_create.add_argument("--archetype", default="")

    parser_online = subparsers.add_parser("online", help="Join online hub")
    parser_online.add_argument("--server", default="")

    parser_server = subparsers.add_parser("server", help="Run online server")
    parser_server.add_argument("--host", default="0.0.0.0")
    parser_server.add_argument("--port", type=int, default=8000)
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


def _run_tutorial(seed: int = 7) -> str:
    from dnd_cli.app import DndApp

    app = DndApp(
        game=Game(seed=seed, run_mode="normal", run_context="tutorial"),
        save_path=None,
        creation_enabled=False,
        run_mode="normal",
        seed=seed,
        tutorial_mode=True,
    )
    app.run()
    return str(getattr(app, "tutorial_result", "quit"))


def _run_online_ui(host: str, port: int, code: str, name: str) -> None:
    from dnd_cli.app import DndApp

    client = OnlineClient(host=host, port=port, code=code, name=name)
    client.start()
    app = DndApp(game=Game(seed=7, run_mode="normal"), online_client=client)
    app.run()


def _run_launcher() -> str | None:
    from dnd_cli.launcher import run_launcher

    return run_launcher()


def _run_launcher_form(command: str) -> dict | None:
    from dnd_cli.launcher import run_launcher_form

    return run_launcher_form(command)


def _run_launcher_message(title: str, body: str) -> None:
    from dnd_cli.launcher import run_launcher_message

    run_launcher_message(title, body)


def run() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    command = args.command or "menu"
    menu_mode = command == "menu"
    tutorial_checked = False

    while True:
        if menu_mode and command == "menu" and not tutorial_checked:
            tutorial_checked = True
            tutorial_state = load_tutorial_state()
            if not bool(tutorial_state.get("seen", False)):
                _run_launcher_message("Tutorial", "Starting first-run tutorial now. You can skip anytime.")
                outcome = _run_tutorial(seed=7)
                if outcome in {"completed", "skipped"}:
                    save_tutorial_state(
                        {
                            "seen": True,
                            "completed": outcome == "completed",
                            "skipped": outcome == "skipped",
                            "version": 1,
                        }
                    )
                command = "menu"
                continue
        if command == "menu":
            choice = _run_launcher()
            if not choice or choice == "quit":
                return
            if choice == "tutorial":
                outcome = _run_tutorial(seed=7)
                if outcome in {"completed", "skipped"}:
                    existing_state = load_tutorial_state()
                    save_tutorial_state(
                        {
                            "seen": True,
                            "completed": bool(existing_state.get("completed", False) or outcome == "completed"),
                            "skipped": bool(existing_state.get("skipped", False) or outcome == "skipped"),
                            "version": 1,
                        }
                    )
                continue
            if choice == "start_local_server":
                from dnd_cli.server.local_control import start_local_server

                ok, message = start_local_server(host="127.0.0.1", port=8000)
                detail = f"{message}\n\nTip: choose `Online Hub` next." if ok else message
                _run_launcher_message("Local Server", detail)
                continue
            if choice == "stop_local_server":
                from dnd_cli.server.local_control import stop_local_server

                _, message = stop_local_server()
                _run_launcher_message("Local Server", message)
                continue
            command = "character" if choice == "character_create" else choice
            values = _run_launcher_form(choice)
            if values is None:
                continue
            for key, value in values.items():
                setattr(args, key, value)
            if choice == "character_create":
                setattr(args, "character_command", "create")
            if hasattr(args, "port"):
                raw_port = str(getattr(args, "port", "")).strip()
                setattr(args, "port", int(raw_port) if raw_port.isdigit() else 8765)
            if command == "host":
                setattr(args, "mode", "normal")
                chat_mode = str(getattr(args, "chat_mode", "reactions_only")).strip()
                if chat_mode not in {"reactions_only", "text_18_plus"}:
                    setattr(args, "chat_mode", "reactions_only")

        if command in {"register", "login"} and not str(getattr(args, "username", "")).strip():
            if menu_mode:
                _run_launcher_message("Input Required", "Username is required.")
                command = "menu"
                continue
            parser.error("Username is required.")
        if command == "join":
            if not str(getattr(args, "host", "")).strip():
                if menu_mode:
                    _run_launcher_message("Input Required", "Host is required.")
                    command = "menu"
                    continue
                parser.error("Host is required.")
            if not str(getattr(args, "code", "")).strip():
                if menu_mode:
                    _run_launcher_message("Input Required", "Join code is required.")
                    command = "menu"
                    continue
                parser.error("Join code is required.")
        hero_id = str(getattr(args, "hero", "")).strip()

        if command == "list-saves":
            saves = list_saves()
            hall_entries = list_hall_of_fame()
            if not saves and not hall_entries:
                text = "No save files found."
            else:
                lines: list[str] = []
                if saves:
                    lines.append("Active Saves:")
                    lines.extend(str(path) for path in saves)
                if hall_entries:
                    lines.append("")
                    lines.append("Hall of Fame:")
                    lines.extend(str(path) for path in hall_entries)
                text = "\n".join(lines)
            if menu_mode:
                _run_launcher_message("Saves", text)
                command = "menu"
                continue
            print(text)
            return

        if command == "tip":
            tip = Game().next_tip()
            if menu_mode:
                _run_launcher_message("Gameplay Tip", tip)
                command = "menu"
                continue
            print(tip)
            return

        if command == "roster":
            heroes = list_roster_heroes()
            if not heroes:
                text = "No roster heroes saved yet."
            else:
                lines = ["Roster Heroes:"]
                for hero in heroes:
                    lines.append(
                        f"{hero.get('character_id', 'no-id')} | "
                        f"{hero.get('name', 'Unknown')} | "
                        f"{hero.get('archetype', 'Adventurer')} | "
                        f"Lv{hero.get('level', 1)}"
                    )
                text = "\n".join(lines)
            if menu_mode:
                _run_launcher_message("Local Roster", text)
                command = "menu"
                continue
            print(text)
            return

        if command == "register":
            from dnd_cli.online import OnlineError, register

            try:
                auth = register(
                    server=args.server,
                    username=args.username,
                    password=str(getattr(args, "password", "")).strip() or None,
                )
            except OnlineError as exc:
                if menu_mode:
                    _run_launcher_message("Register Failed", str(exc))
                    command = "menu"
                    continue
                parser.error(str(exc))
            text = f"Registered and logged in as {auth.username} ({auth.server})"
            if menu_mode:
                _run_launcher_message("Register Success", text)
                command = "menu"
                continue
            print(text)
            return

        if command == "login":
            from dnd_cli.online import OnlineError, login

            try:
                auth = login(
                    server=args.server,
                    username=args.username,
                    password=str(getattr(args, "password", "")).strip() or None,
                )
            except OnlineError as exc:
                if menu_mode:
                    _run_launcher_message("Login Failed", str(exc))
                    command = "menu"
                    continue
                parser.error(str(exc))
            text = f"Logged in as {auth.username} ({auth.server})"
            if menu_mode:
                _run_launcher_message("Login Success", text)
                command = "menu"
                continue
            print(text)
            return

        if command == "logout":
            from dnd_cli.online import logout

            logout()
            if menu_mode:
                _run_launcher_message("Logout", "Logged out.")
                command = "menu"
                continue
            print("Logged out.")
            return

        if command == "characters":
            from dnd_cli.online import OnlineError, list_characters

            try:
                rows = list_characters()
            except OnlineError as exc:
                if menu_mode:
                    _run_launcher_message("Characters", str(exc))
                    command = "menu"
                    continue
                parser.error(str(exc))
            if not rows:
                text = "No online characters yet."
            else:
                lines = ["Online Characters:"]
                for row in rows:
                    lines.append(
                        f"{row.get('id')} | {row.get('name')} | {row.get('archetype')} | "
                        f"Lv{row.get('level', 1)} | slot {row.get('slot_index', 0)}"
                    )
                text = "\n".join(lines)
            if menu_mode:
                _run_launcher_message("Characters", text)
                command = "menu"
                continue
            print(text)
            return

        if command == "character":
            subcommand = getattr(args, "character_command", "")
            if subcommand != "create":
                if menu_mode:
                    _run_launcher_message("Character", "Use `cryptclash character create`.")
                    command = "menu"
                    continue
                parser.error("Use `cryptclash character create`.")
            from dnd_cli.online import OnlineError, create_character

            name = str(args.name).strip() or input("Name: ").strip()
            archetype = str(args.archetype).strip() or input("Archetype (Fighter/Rogue/Cleric/Mage): ").strip()
            try:
                row = create_character(name=name, archetype=archetype)
            except OnlineError as exc:
                if menu_mode:
                    _run_launcher_message("Character Create Failed", str(exc))
                    command = "menu"
                    continue
                parser.error(str(exc))
            text = f"Created character: {row.get('name')} ({row.get('archetype')}) slot {row.get('slot_index')}"
            if menu_mode:
                _run_launcher_message("Character Created", text)
                command = "menu"
                continue
            print(text)
            return

        if command == "online":
            from dnd_cli.online import OnlineError, online_hub_loop
            import asyncio

            try:
                asyncio.run(online_hub_loop(server=args.server or None))
            except OnlineError as exc:
                if menu_mode:
                    _run_launcher_message("Online Hub", str(exc))
                    command = "menu"
                    continue
                parser.error(str(exc))
            if menu_mode:
                command = "menu"
                continue
            return

        if command == "server":
            from dnd_cli.server.app import create_app
            from dnd_cli.server.config import ServerConfig
            import uvicorn

            app = create_app(ServerConfig.from_env())
            uvicorn.run(app, host=args.host, port=args.port)
            return

        if command == "save":
            source = latest_normal_save()
            if not source:
                if menu_mode:
                    _run_launcher_message("Save", "No normal save found to copy into a slot.")
                    command = "menu"
                    continue
                parser.error("No normal save found to copy into a slot.")
            game = load_game(source)
            if game.run_mode == "ironman":
                if menu_mode:
                    _run_launcher_message("Save", "Cannot save an ironman run into slots.")
                    command = "menu"
                    continue
                parser.error("Cannot save an ironman run into slots.")
            path = save_slot(game, args.slot)
            if menu_mode:
                _run_launcher_message("Save", f"Saved slot: {path}")
                command = "menu"
                continue
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
                if menu_mode:
                    _run_launcher_message("LAN Host", f"Unable to start host: {service.error or 'unknown error'}")
                    command = "menu"
                    continue
                parser.error(f"Unable to start host: {service.error or 'unknown error'}")
            _run_online_ui(host="127.0.0.1", port=args.port, code=join_code, name=args.name)
            if menu_mode:
                command = "menu"
                continue
            return

        if command == "join":
            _run_online_ui(host=args.host, port=args.port, code=args.code, name=args.name)
            if menu_mode:
                command = "menu"
                continue
            return

        if command == "load":
            game = _resolve_load_target(args, parser)
            game.log.append("Loaded save.")
            game.log = game.log[-12:]
            _run_game(game)
            if menu_mode:
                command = "menu"
                continue
            return

        if command == "continue":
            ironman = active_ironman_save()
            if ironman:
                game = load_game(ironman)
                game.log.append(f"Loaded ironman run: {ironman.name}")
                game.log = game.log[-12:]
                _run_game(game)
                if menu_mode:
                    command = "menu"
                    continue
                return
            path = latest_normal_save()
            if path and path.exists():
                game = load_game(path)
                game.log.append(f"Loaded latest save: {path.name}")
                game.log = game.log[-12:]
                _run_game(game)
                if menu_mode:
                    command = "menu"
                    continue
                return
            if menu_mode:
                _run_launcher_message(
                    "Continue",
                    "No save found yet.\n\nStart a run with `New Adventure` first, then `Continue` will resume it.",
                )
                command = "menu"
                continue
            print("No save found. Start a run with `cryptclash new` first.")
            return

        if hero_id:
            game = Game(seed=7, run_mode=args.mode, party=_party_from_roster_hero(hero_id, parser))
            save_game(game, autosave_path(game.run_mode))
            _run_game(game, creation_enabled=False, seed=7)
            if menu_mode:
                command = "menu"
                continue
            return
        game = Game(seed=7, run_mode=args.mode)
        save_game(game, autosave_path(game.run_mode))
        _run_game(game, creation_enabled=True, seed=7)
        if menu_mode:
            command = "menu"
            continue
        return


if __name__ == "__main__":
    run()
