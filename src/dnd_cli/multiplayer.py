from __future__ import annotations

import asyncio
import json
import queue
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime

from dnd_cli.game import Action, Game


def resolve_action_input(raw: str, actions: list[str]) -> str | None:
    value = raw.strip()
    if not value:
        return None
    if value.isdigit():
        index = int(value) - 1
        if 0 <= index < len(actions):
            return actions[index]
        return None
    lowered = value.casefold()
    for action in actions:
        if lowered == action.casefold():
            return action
    return None


def render_snapshot(snapshot: dict) -> str:
    chat_mode = str(snapshot.get("chat_mode", "reactions_only"))
    chat_label = "Text (18+)" if chat_mode == "text_18_plus" else "Reactions Only"
    lines: list[str] = [
        f"=== DND ONLINE | {snapshot.get('status', 'Unknown')} ===",
        f"Room: {snapshot.get('room', 'Unknown')} | {snapshot.get('depth', 'Depth: ?')}",
        f"Comms: {chat_label}",
        "",
        "Party:",
    ]
    for unit in snapshot.get("party", []):
        marker = "*" if unit.get("is_active") else "-"
        controller = unit.get("controller_name") or "AI/Open"
        lines.append(
            f"{marker} {unit.get('name', 'Unknown'):12} "
            f"{unit.get('hp', 0)}/{unit.get('max_hp', 0)} "
            f"[{controller}]"
        )
    lines.extend(["", "Adventure Log:"])
    for entry in snapshot.get("log", []):
        lines.append(f"• {entry}")
    actions = snapshot.get("actions", [])
    lines.extend(["", "Actions:"])
    for index, action in enumerate(actions, start=1):
        lines.append(f"{index}. {action}")
    lines.append("")
    lines.append(f"Last Roll: {snapshot.get('last_roll', 'No roll yet.')}")
    lines.append("Type action number/text, or `quit`.")
    return "\n".join(lines)


@dataclass
class _Client:
    client_id: str
    name: str
    writer: asyncio.StreamWriter
    assigned_character_id: str | None = None


class MultiplayerServer:
    def __init__(self, game: Game, join_code: str, chat_mode: str = "reactions_only") -> None:
        self.game = game
        self.join_code = join_code.strip()
        self.chat_mode = chat_mode if chat_mode in {"reactions_only", "text_18_plus"} else "reactions_only"
        self.clients: dict[str, _Client] = {}
        self.controllers: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def run(self, bind: str, port: int) -> None:
        server = await asyncio.start_server(self._handle_client, bind, port)
        async with server:
            await server.serve_forever()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        client: _Client | None = None
        try:
            join_message = await self._read_json(reader)
            if not join_message or join_message.get("type") != "join":
                await self._send_json(writer, {"type": "error", "message": "Expected join message."})
                return
            name = str(join_message.get("name", "")).strip() or "Player"
            code = str(join_message.get("code", "")).strip()
            if code != self.join_code:
                await self._send_json(writer, {"type": "error", "message": "Invalid join code."})
                return
            async with self._lock:
                client_id = f"c-{uuid.uuid4().hex[:8]}"
                assigned_character_id = self._assign_character_id(client_id)
                client = _Client(
                    client_id=client_id,
                    name=name,
                    writer=writer,
                    assigned_character_id=assigned_character_id,
                )
                self.clients[client_id] = client
                if assigned_character_id:
                    self.controllers[assigned_character_id] = client_id
                self.game.log.append(f"{name} joined the session.")
                self.game.log = self.game.log[-12:]
            await self._send_json(
                writer,
                {
                    "type": "join_ack",
                    "client_id": client.client_id,
                    "assigned_character_id": client.assigned_character_id,
                    "chat_mode": self.chat_mode,
                },
            )
            await self._broadcast_snapshot()
            while True:
                message = await self._read_json(reader)
                if message is None:
                    break
                msg_type = message.get("type")
                if msg_type == "reaction":
                    emote = str(message.get("emote", "👍")).strip() or "👍"
                    target = str(message.get("target", "party")).strip() or "party"
                    await self._handle_reaction(client.client_id, emote, target)
                    continue
                if msg_type == "chat":
                    text = str(message.get("message", "")).strip()
                    ok, error = await self._handle_chat(client.client_id, text)
                    if not ok:
                        await self._send_json(writer, {"type": "error", "message": error})
                    continue
                if msg_type != "action":
                    await self._send_json(writer, {"type": "error", "message": "Unknown message type."})
                    continue
                action_raw = str(message.get("action", ""))
                await self._handle_action(client.client_id, action_raw)
        finally:
            if client:
                async with self._lock:
                    self.clients.pop(client.client_id, None)
                    for character_id, owner_id in list(self.controllers.items()):
                        if owner_id == client.client_id:
                            del self.controllers[character_id]
                    self.game.log.append(f"{client.name} disconnected.")
                    self.game.log = self.game.log[-12:]
                await self._broadcast_snapshot()
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def _assign_character_id(self, client_id: str) -> str | None:
        for unit in self.game.party:
            character_id = unit.character_id or unit.name
            if character_id not in self.controllers:
                return character_id
        return None

    async def _handle_action(self, client_id: str, action_raw: str) -> None:
        async with self._lock:
            labels = self.game.action_labels()
            action = resolve_action_input(action_raw, labels)
            if not action:
                await self._send_to_client(client_id, {"type": "error", "message": "Invalid action."})
                return
            allowed, reason = self._can_client_act(client_id)
            if not allowed:
                await self._send_to_client(client_id, {"type": "error", "message": reason})
                return
            self.game.perform_player_action(action)
            if self.game.mode == "combat" and self.game.action_consumed_turn and not self.game.game_over():
                self.game.run_enemy_turns_until_player()
            self._auto_play_uncontrolled_turns()
        await self._broadcast_snapshot()

    async def _handle_reaction(self, client_id: str, emote: str, target: str) -> None:
        async with self._lock:
            client = self.clients.get(client_id)
            sender = client.name if client else "Player"
            stamp = datetime.now().strftime("%H:%M:%S")
            self.game.log.append(f"[{stamp}] {sender} reacts {emote} -> {target}")
            self.game.log = self.game.log[-12:]
        await self._broadcast_snapshot()

    async def _handle_chat(self, client_id: str, text: str) -> tuple[bool, str]:
        if self.chat_mode != "text_18_plus":
            return False, "Text chat is disabled in this room (reactions-only)."
        if not text:
            return False, "Chat message is empty."
        if len(text) > 240:
            return False, "Chat message is too long (max 240 chars)."
        async with self._lock:
            client = self.clients.get(client_id)
            sender = client.name if client else "Player"
            stamp = datetime.now().strftime("%H:%M:%S")
            self.game.log.append(f"[{stamp}] {sender}: {text}")
            self.game.log = self.game.log[-12:]
        await self._broadcast_snapshot()
        return True, ""

    def _can_client_act(self, client_id: str) -> tuple[bool, str]:
        if self.game.mode != "combat":
            return True, ""
        actor = self.game.active_unit()
        if actor is None:
            return False, "No active turn."
        if actor not in self.game.party:
            return False, "Wait for enemy turn resolution."
        character_id = actor.character_id or actor.name
        owner = self.controllers.get(character_id)
        if owner and owner != client_id:
            owner_name = self.clients.get(owner).name if owner in self.clients else "another player"
            return False, f"Wait: {owner_name} controls {actor.name}."
        return True, ""

    def _auto_play_uncontrolled_turns(self) -> None:
        while self.game.mode == "combat" and self.game.is_player_turn() and not self.game.game_over():
            actor = self.game.active_unit()
            if actor is None or actor not in self.game.party:
                return
            character_id = actor.character_id or actor.name
            owner = self.controllers.get(character_id)
            if owner and owner in self.clients:
                return
            labels = self.game.action_labels()
            if Action.ATTACK.value in labels:
                self.game.perform_player_action(Action.ATTACK.value)
            elif any(label.startswith("Style: Balanced") for label in labels):
                self.game.perform_player_action("Style: Balanced")
            elif any(label.startswith("Target: ") for label in labels):
                target = next(label for label in labels if label.startswith("Target: "))
                self.game.perform_player_action(target)
            elif labels:
                self.game.perform_player_action(labels[0])
            else:
                return
            if self.game.mode == "combat" and self.game.action_consumed_turn and not self.game.game_over():
                self.game.run_enemy_turns_until_player()

    async def _broadcast_snapshot(self) -> None:
        clients = list(self.clients.values())
        if not clients:
            return
        for client in clients:
            payload = self._snapshot_for_client(client.client_id)
            await self._send_json(client.writer, payload)

    def _snapshot_for_client(self, client_id: str) -> dict:
        actor = self.game.active_unit()
        active_character_id = ""
        if actor and actor in self.game.party:
            active_character_id = actor.character_id or actor.name
        active_name = actor.name if actor else ""
        party_rows: list[dict[str, object]] = []
        for unit in self.game.party:
            character_id = unit.character_id or unit.name
            owner_id = self.controllers.get(character_id)
            owner_name = self.clients.get(owner_id).name if owner_id in self.clients else None
            party_rows.append(
                {
                    "name": unit.name.split(" (", 1)[0],
                    "hp": unit.hp,
                    "max_hp": unit.max_hp,
                    "mana": unit.mana,
                    "max_mana": unit.max_mana,
                    "character_id": character_id,
                    "controller_name": owner_name,
                    "is_active": character_id == active_character_id,
                }
            )
        enemy_rows: list[dict[str, object]] = []
        for enemy in self.game.enemies:
            enemy_rows.append(
                {
                    "name": enemy.name.split(" (", 1)[0],
                    "hp": enemy.hp,
                    "max_hp": enemy.max_hp,
                    "alive": enemy.alive,
                }
            )
        pending_text = ""
        if self.game.pending_action_type == "attack" and self.game.pending_style:
            pending_text = f"Pending: {self.game.pending_style} Attack -> choose target"
        elif self.game.pending_action_type == "skill" and self.game.pending_skill_id:
            skill_name = self.game.SKILL_DEFS.get(self.game.pending_skill_id, {}).get("name", self.game.pending_skill_id)
            pending_text = f"Pending: {skill_name} -> choose target"
        return {
            "type": "snapshot",
            "status": self.game.status_summary(),
            "room": self.game.current_room_name(),
            "depth": self.game.depth_text(),
            "mode": self.game.mode,
            "menu": self.game.menu,
            "menu_context": self.game.menu_context_text(),
            "chat_mode": self.chat_mode,
            "loot_non_rare_streak": self.game.loot_non_rare_streak,
            "round": self.game.round_number,
            "mood": self.game.room_mood_text(),
            "active_name": active_name,
            "last_roll": self.game.last_roll_text,
            "pending_text": pending_text,
            "log": self.game.log[-8:],
            "actions": self.game.action_labels(),
            "party": party_rows,
            "enemies": enemy_rows,
            "map_text": self.game.map_overlay_text() if self.game.menu == "map" else "",
            "your_character_id": self.clients.get(client_id).assigned_character_id if client_id in self.clients else None,
            "active_character_id": active_character_id,
        }

    async def _send_to_client(self, client_id: str, payload: dict) -> None:
        client = self.clients.get(client_id)
        if client:
            await self._send_json(client.writer, payload)

    @staticmethod
    async def _send_json(writer: asyncio.StreamWriter, payload: dict) -> None:
        data = json.dumps(payload, separators=(",", ":")) + "\n"
        writer.write(data.encode("utf-8"))
        await writer.drain()

    @staticmethod
    async def _read_json(reader: asyncio.StreamReader) -> dict | None:
        line = await reader.readline()
        if not line:
            return None
        try:
            return json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            return None


async def run_host(bind: str, port: int, code: str, mode: str) -> None:
    game = Game(seed=7, run_mode=mode)
    server = MultiplayerServer(game=game, join_code=code)
    print(f"[DND host] listening on {bind}:{port}")
    print(f"[DND host] join code: {code}")
    print(f"[DND host] players join with: DND join --host <HOST_IP> --port {port} --code {code} --name <name>")
    await server.run(bind, port)


async def run_join(host: str, port: int, code: str, name: str) -> None:
    reader, writer = await asyncio.open_connection(host, port)
    await MultiplayerServer._send_json(writer, {"type": "join", "name": name, "code": code})
    ack = await MultiplayerServer._read_json(reader)
    if not ack:
        print("Disconnected before join handshake.")
        return
    if ack.get("type") == "error":
        print(f"Join failed: {ack.get('message', 'Unknown error')}")
        return
    if ack.get("type") != "join_ack":
        print("Unexpected server response.")
        return
    assigned = ack.get("assigned_character_id")
    if assigned:
        print(f"Connected as {name}. You control {assigned}.")
    else:
        print(f"Connected as {name}. You are spectating.")
    latest_snapshot: dict = {}
    connected = True

    async def receiver() -> None:
        nonlocal latest_snapshot, connected
        while connected:
            message = await MultiplayerServer._read_json(reader)
            if message is None:
                connected = False
                print("Disconnected from host.")
                return
            if message.get("type") == "snapshot":
                latest_snapshot = message
                print("\033[2J\033[H", end="")
                print(render_snapshot(message))
            elif message.get("type") == "error":
                print(f"[server] {message.get('message', 'Error')}")

    receive_task = asyncio.create_task(receiver())
    try:
        while connected:
            await asyncio.sleep(0.05)
            if not latest_snapshot:
                continue
            raw = await asyncio.to_thread(input, "> ")
            if raw.strip().lower() in {"quit", "exit"}:
                connected = False
                break
            action = resolve_action_input(raw, latest_snapshot.get("actions", []))
            if not action:
                print("Invalid action input.")
                continue
            await MultiplayerServer._send_json(writer, {"type": "action", "action": action})
    finally:
        connected = False
        receive_task.cancel()
        writer.close()
        await writer.wait_closed()


def default_join_code() -> str:
    return secrets.token_hex(2).upper()


class HostService:
    def __init__(
        self,
        bind: str,
        port: int,
        code: str,
        mode: str,
        party: list | None = None,
        chat_mode: str = "reactions_only",
    ) -> None:
        self.bind = bind
        self.port = port
        self.code = code
        self.mode = mode
        self.party = party
        self.chat_mode = chat_mode if chat_mode in {"reactions_only", "text_18_plus"} else "reactions_only"
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_thread, daemon=True)
        self._thread.start()

    def wait_until_ready(self, timeout: float) -> bool:
        self._ready.wait(timeout)
        return self.error is None and self._ready.is_set()

    def _run_thread(self) -> None:
        try:
            asyncio.run(self._run_server())
        except Exception as exc:
            self.error = str(exc)
            self._ready.set()

    async def _run_server(self) -> None:
        game = Game(seed=7, run_mode=self.mode, party=self.party)
        server = MultiplayerServer(game=game, join_code=self.code, chat_mode=self.chat_mode)
        listener = await asyncio.start_server(server._handle_client, self.bind, self.port)
        self._ready.set()
        async with listener:
            await listener.serve_forever()


class OnlineClient:
    def __init__(self, host: str, port: int, code: str, name: str) -> None:
        self.host = host
        self.port = port
        self.code = code
        self.name = name
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._events: queue.Queue[dict] = queue.Queue()
        self.connected = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_thread, daemon=True)
        self._thread.start()

    def poll_events(self, max_events: int = 50) -> list[dict]:
        events: list[dict] = []
        for _ in range(max_events):
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                break
        return events

    def send_action(self, action: str) -> bool:
        if not self.connected or not self._loop or not self._writer:
            return False

        async def _send() -> None:
            if self._writer:
                await MultiplayerServer._send_json(self._writer, {"type": "action", "action": action})

        self._loop.call_soon_threadsafe(lambda: asyncio.create_task(_send()))
        return True

    def send_reaction(self, emote: str, target: str = "party") -> bool:
        if not self.connected or not self._loop or not self._writer:
            return False

        async def _send() -> None:
            if self._writer:
                await MultiplayerServer._send_json(
                    self._writer,
                    {"type": "reaction", "emote": emote, "target": target},
                )

        self._loop.call_soon_threadsafe(lambda: asyncio.create_task(_send()))
        return True

    def close(self) -> None:
        self.connected = False
        if self._loop and self._writer:
            self._loop.call_soon_threadsafe(self._writer.close)

    def _run_thread(self) -> None:
        try:
            asyncio.run(self._run_async())
        except Exception as exc:
            self._events.put({"type": "system", "message": f"Connection error: {exc}"})

    async def _run_async(self) -> None:
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
        except Exception as exc:
            self._events.put({"type": "system", "message": f"Unable to connect: {exc}"})
            return
        self._loop = asyncio.get_running_loop()
        self._writer = writer
        await MultiplayerServer._send_json(writer, {"type": "join", "name": self.name, "code": self.code})
        ack = await MultiplayerServer._read_json(reader)
        if not ack:
            self._events.put({"type": "system", "message": "Disconnected during join."})
            writer.close()
            await writer.wait_closed()
            return
        if ack.get("type") == "error":
            self._events.put({"type": "system", "message": f"Join failed: {ack.get('message', 'Unknown error')}"})
            writer.close()
            await writer.wait_closed()
            return
        if ack.get("type") != "join_ack":
            self._events.put({"type": "system", "message": "Unexpected join response from host."})
            writer.close()
            await writer.wait_closed()
            return
        self.connected = True
        self._events.put(ack)
        while self.connected:
            message = await MultiplayerServer._read_json(reader)
            if message is None:
                break
            self._events.put(message)
        self.connected = False
        self._events.put({"type": "system", "message": "Disconnected from host."})
        writer.close()
        await writer.wait_closed()
