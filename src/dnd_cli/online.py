from __future__ import annotations

import asyncio
import getpass
import json
import os
import ssl
import uuid
from dataclasses import dataclass
from urllib import error, parse, request

import websockets

from dnd_cli.storage import clear_auth, load_auth, save_auth

DEFAULT_SERVER_URL = "http://127.0.0.1:8000"


class OnlineError(RuntimeError):
    pass


@dataclass
class OnlineAuth:
    server: str
    username: str
    access_token: str
    refresh_token: str
    access_expires_at: str
    refresh_expires_at: str

    def to_dict(self) -> dict:
        return {
            "server": self.server,
            "username": self.username,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "access_expires_at": self.access_expires_at,
            "refresh_expires_at": self.refresh_expires_at,
        }


def _normalize_server(server: str) -> str:
    value = server.strip().rstrip("/")
    if not value:
        value = preferred_server()
    if not value.startswith(("http://", "https://")):
        value = f"http://{value}"
    return value


def preferred_server() -> str:
    env_server = os.getenv("CRYPTCLASH_DEFAULT_SERVER", "").strip()
    if env_server:
        return _normalize_server(env_server)
    auth_data = load_auth()
    saved_server = str(auth_data.get("server", "")).strip()
    if saved_server:
        return _normalize_server(saved_server)
    return DEFAULT_SERVER_URL


def _http_json(method: str, url: str, payload: dict | None = None, token: str | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, method=method, data=data, headers=headers)
    try:
        with request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        detail = body
        try:
            parsed = json.loads(body)
            payload_detail = parsed.get("detail") or parsed.get("message") or body
            if isinstance(payload_detail, list):
                messages: list[str] = []
                for item in payload_detail:
                    if not isinstance(item, dict):
                        continue
                    loc = item.get("loc", [])
                    field = loc[-1] if isinstance(loc, list) and loc else "field"
                    msg = str(item.get("msg", "Invalid value"))
                    if field == "password" and "at least 8" in msg.lower():
                        messages.append("Password must be at least 8 characters.")
                    elif field == "username" and "at least 3" in msg.lower():
                        messages.append("Username must be at least 3 characters.")
                    else:
                        messages.append(f"{field}: {msg}")
                detail = "; ".join(messages) if messages else str(payload_detail)
            else:
                detail = str(payload_detail)
        except json.JSONDecodeError:
            pass
        raise OnlineError(f"{exc.code}: {detail}") from exc
    except error.URLError as exc:
        local_hint = ""
        if "127.0.0.1" in url or "localhost" in url:
            local_hint = " Start local server with `./scripts/run-online-local.sh`."
        raise OnlineError(f"Unable to reach server: {exc.reason}.{local_hint}") from exc


def register(server: str = "", username: str = "", password: str | None = None) -> OnlineAuth:
    server_url = _normalize_server(server)
    if password is None:
        password = getpass.getpass("Password: ")
    payload = _http_json(
        "POST",
        f"{server_url}/api/auth/register",
        {"username": username, "password": password},
    )
    auth = OnlineAuth(
        server=server_url,
        username=username,
        access_token=str(payload["access_token"]),
        refresh_token=str(payload["refresh_token"]),
        access_expires_at=str(payload["access_expires_at"]),
        refresh_expires_at=str(payload["refresh_expires_at"]),
    )
    save_auth(auth.to_dict())
    return auth


def login(server: str = "", username: str = "", password: str | None = None) -> OnlineAuth:
    server_url = _normalize_server(server)
    if password is None:
        password = getpass.getpass("Password: ")
    payload = _http_json(
        "POST",
        f"{server_url}/api/auth/login",
        {"username": username, "password": password},
    )
    auth = OnlineAuth(
        server=server_url,
        username=username,
        access_token=str(payload["access_token"]),
        refresh_token=str(payload["refresh_token"]),
        access_expires_at=str(payload["access_expires_at"]),
        refresh_expires_at=str(payload["refresh_expires_at"]),
    )
    save_auth(auth.to_dict())
    return auth


def logout() -> None:
    auth_data = load_auth()
    server = str(auth_data.get("server", "")).rstrip("/")
    refresh_token = str(auth_data.get("refresh_token", ""))
    if server and refresh_token:
        try:
            _http_json("POST", f"{server}/api/auth/logout", {"refresh_token": refresh_token})
        except OnlineError:
            pass
    clear_auth()


def list_characters() -> list[dict]:
    auth_data = load_auth()
    if not auth_data:
        raise OnlineError("Not logged in. Run `cryptclash login` first.")
    payload = _http_json(
        "GET",
        f"{str(auth_data['server']).rstrip('/')}/api/characters",
        token=str(auth_data["access_token"]),
    )
    return payload if isinstance(payload, list) else []


def create_character(name: str, archetype: str) -> dict:
    auth_data = load_auth()
    if not auth_data:
        raise OnlineError("Not logged in. Run `cryptclash login` first.")
    payload = _http_json(
        "POST",
        f"{str(auth_data['server']).rstrip('/')}/api/characters",
        {"name": name, "archetype": archetype},
        token=str(auth_data["access_token"]),
    )
    return payload if isinstance(payload, dict) else {}


async def online_hub_loop(server: str | None = None) -> None:
    auth_data = load_auth()
    if not auth_data:
        raise OnlineError("Not logged in. Run `cryptclash login` first.")
    server_url = _normalize_server(server or str(auth_data.get("server", "")) or preferred_server())
    token = str(auth_data.get("access_token", ""))
    characters = list_characters()
    if not characters:
        raise OnlineError("No online characters found. Create one with `cryptclash character create`.")
    print("Choose character:")
    for idx, character in enumerate(characters, start=1):
        print(
            f"{idx}. {character['name']} | {character['archetype']} | "
            f"Lv{character['level']} | slot {character['slot_index']}"
        )
    raw = input("> ").strip()
    choice = int(raw) if raw.isdigit() else 1
    choice = min(max(choice, 1), len(characters))
    selected = characters[choice - 1]

    ws_url = parse.urlparse(server_url)
    ws_scheme = "wss" if ws_url.scheme == "https" else "ws"
    hub_url = f"{ws_scheme}://{ws_url.netloc}/ws/hub"
    ssl_ctx = ssl.create_default_context() if ws_scheme == "wss" else None
    print(f"Connecting to hub at {hub_url} as {selected['name']}...")
    async with websockets.connect(hub_url, ssl=ssl_ctx, ping_interval=20, ping_timeout=20) as ws:
        hello = json.loads(await ws.recv())
        print(f"[hub] {hello.get('motd', 'Connected')}")
        auth_req = {"v": 1, "type": "auth", "request_id": str(uuid.uuid4()), "token": token}
        await ws.send(json.dumps(auth_req))
        auth_ack = json.loads(await ws.recv())
        if auth_ack.get("type") != "auth_ack":
            raise OnlineError("Hub authentication failed.")
        await ws.send(
            json.dumps(
                {
                    "v": 1,
                    "type": "presence_set",
                    "request_id": str(uuid.uuid4()),
                    "character_id": selected["id"],
                    "status_flags": ["looking_for_party"],
                }
            )
        )
        print("Hub connected. Commands: `party`, `ready`, `queue`, `react <emoji>`, `quit`.")

        latest_party_id = ""
        running = True

        async def receiver() -> None:
            nonlocal latest_party_id, running
            while running:
                msg = json.loads(await ws.recv())
                msg_type = msg.get("type")
                if msg_type == "presence_snapshot":
                    players = msg.get("players", [])
                    print(f"[hub] online players: {len(players)}")
                elif msg_type == "party_state":
                    latest_party_id = str(msg.get("party_id", latest_party_id))
                    print(f"[party] id={latest_party_id} state={msg.get('state')}")
                elif msg_type == "instance_assigned":
                    print(f"[queue] instance assigned: {msg.get('instance_id')}")
                elif msg_type == "error":
                    print(f"[error] {msg.get('message')}")

        receiver_task = asyncio.create_task(receiver())
        try:
            while running:
                raw_cmd = await asyncio.to_thread(input, "> ")
                command = raw_cmd.strip()
                if command in {"quit", "exit"}:
                    running = False
                    break
                if command == "party":
                    await ws.send(json.dumps({"v": 1, "type": "party_create", "request_id": str(uuid.uuid4())}))
                    continue
                if command == "ready":
                    await ws.send(
                        json.dumps({"v": 1, "type": "party_ready", "request_id": str(uuid.uuid4()), "ready": True})
                    )
                    continue
                if command == "queue":
                    await ws.send(
                        json.dumps(
                            {
                                "v": 1,
                                "type": "queue_join",
                                "request_id": str(uuid.uuid4()),
                                "dungeon_type": "standard",
                            }
                        )
                    )
                    continue
                if command.startswith("react "):
                    emote = command.split(" ", 1)[1].strip()
                    await ws.send(
                        json.dumps(
                            {
                                "v": 1,
                                "type": "reaction",
                                "request_id": str(uuid.uuid4()),
                                "emote": emote or "👍",
                                "target": "hub",
                            }
                        )
                    )
                    continue
                print("Unknown command.")
        finally:
            running = False
            receiver_task.cancel()
