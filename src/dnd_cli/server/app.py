from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dnd_cli.server.config import ServerConfig
from dnd_cli.server.db import Database
from dnd_cli.server.hub import HubState, ReactionLimiter
from dnd_cli.server.instance import InstanceManager
from dnd_cli.server.models import Account, Character, Instance, Party, PartyMember
from dnd_cli.server.schemas import (
    CharacterCreateRequest,
    CharacterResponse,
    ErrorPayload,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from dnd_cli.server.security import SecurityManager
from dnd_cli.server.services import (
    ServiceError,
    authenticate_account,
    create_character,
    list_characters,
    register_account,
    revoke_refresh_token,
    rotate_refresh_token,
)


@dataclass
class HubClient:
    websocket: WebSocket
    account_id: str
    connection_id: str
    character_id: str | None = None


def _serialize_character(character: Character) -> CharacterResponse:
    return CharacterResponse(
        id=str(character.id),
        slot_index=character.slot_index,
        name=character.name,
        archetype=character.archetype,
        level=character.level,
        xp=character.xp,
        gold=character.gold,
        stats_jsonb=dict(character.stats_jsonb or {}),
        inventory_jsonb=dict(character.inventory_jsonb or {}),
        equipment_jsonb=dict(character.equipment_jsonb or {}),
        updated_at=character.updated_at.replace(tzinfo=timezone.utc) if character.updated_at.tzinfo is None else character.updated_at,
    )


def create_app(config: ServerConfig | None = None) -> FastAPI:
    cfg = config or ServerConfig.from_env()
    db = Database(cfg.database_url)
    security = SecurityManager(cfg.jwt_secret, cfg.access_token_minutes, cfg.refresh_token_days)
    hub_state = HubState(presence_limit=cfg.presence_limit)
    reaction_limiter = ReactionLimiter(cfg.reaction_limit_count, cfg.reaction_limit_window_seconds)
    instance_manager = InstanceManager()
    hub_clients: dict[str, HubClient] = {}
    hub_clients_lock = asyncio.Lock()
    instance_clients: dict[str, dict[str, tuple[WebSocket, str]]] = {}
    instance_clients_lock = asyncio.Lock()

    app = FastAPI(title="Crypt Clash Online Server", version="0.1.0")

    async def get_session():
        async with db.session() as session:
            yield session

    async def get_account_from_header(
        authorization: str = Header(default=""), session: AsyncSession = Depends(get_session)
    ) -> Account:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
        token = authorization.split(" ", 1)[1]
        try:
            payload = security.decode_access_token(token)
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.") from None
        account_id = payload.get("sub")
        if not account_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.")
        account = await session.get(Account, uuid.UUID(str(account_id)))
        if not account:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found.")
        return account

    async def hub_send(connection_id: str, payload: dict) -> None:
        async with hub_clients_lock:
            client = hub_clients.get(connection_id)
        if not client:
            return
        await client.websocket.send_json(payload)

    async def hub_broadcast(payload: dict) -> None:
        async with hub_clients_lock:
            clients = list(hub_clients.values())
        for client in clients:
            try:
                await client.websocket.send_json(payload)
            except Exception:
                continue

    async def broadcast_presence() -> None:
        players = await hub_state.snapshot()
        await hub_broadcast({"v": 1, "type": "presence_snapshot", "players": players})

    async def emit_party_state(party_id: str) -> None:
        party = hub_state.parties.get(party_id)
        if not party:
            return
        payload = {"v": 1, "type": "party_state", **hub_state.to_party_payload(party)}
        for member in party.members:
            connection_id = next((key for key, row in hub_clients.items() if row.character_id == member), None)
            if connection_id:
                await hub_send(connection_id, payload)

    async def ensure_party_row(session: AsyncSession, party_id: str, leader_character_id: str, chat_mode: str) -> None:
        party_uuid = uuid.UUID(party_id)
        existing = await session.get(Party, party_uuid)
        if not existing:
            session.add(
                Party(
                    id=party_uuid,
                    leader_character_id=uuid.UUID(leader_character_id),
                    state="forming",
                    chat_mode=chat_mode,
                )
            )
        await session.commit()

    async def ensure_party_member_rows(session: AsyncSession, party_id: str, member_map: dict[str, bool]) -> None:
        party_uuid = uuid.UUID(party_id)
        existing_rows = await session.scalars(select(PartyMember).where(PartyMember.party_id == party_uuid))
        by_character = {str(row.character_id): row for row in list(existing_rows)}
        for character_id, ready in member_map.items():
            row = by_character.get(character_id)
            if row:
                row.ready = ready
            else:
                session.add(
                    PartyMember(
                        party_id=party_uuid,
                        character_id=uuid.UUID(character_id),
                        ready=ready,
                    )
                )
        await session.commit()

    async def assign_instance_to_party(session: AsyncSession, party_id: str, dungeon_type: str) -> tuple[str, list[str]]:
        party = hub_state.parties.get(party_id)
        if not party:
            raise ServiceError("Party not found.")
        character_ids = list(party.members.keys())
        runtime = await instance_manager.create_instance(character_ids=character_ids, seed=7)
        session.add(
            Instance(
                id=uuid.UUID(runtime.instance_id),
                party_id=uuid.UUID(party_id),
                seed=7,
                dungeon_type=dungeon_type,
                state="active",
                started_at=datetime.utcnow(),
            )
        )
        await session.commit()
        return runtime.instance_id, character_ids

    async def persist_instance_rewards(session: AsyncSession, instance_id: str, rewards: dict) -> None:
        for character_id, row in rewards.items():
            character = await session.get(Character, uuid.UUID(character_id))
            if not character:
                continue
            character.gold = int(character.gold) + int(row.get("gold", 0))
            character.xp = int(character.xp) + int(row.get("xp", 0))
            character.inventory_jsonb = dict(character.inventory_jsonb or {})
            for item_id, qty in dict(row.get("items", {})).items():
                character.inventory_jsonb[item_id] = int(character.inventory_jsonb.get(item_id, 0)) + int(qty)
            while character.xp >= character.level * 100:
                character.xp -= character.level * 100
                character.level += 1
            character.updated_at = datetime.utcnow()
        instance_row = await session.get(Instance, uuid.UUID(instance_id))
        if instance_row:
            instance_row.state = "complete"
            instance_row.ended_at = datetime.utcnow()
        await session.commit()

    async def _parse_ws_message(ws: WebSocket) -> dict:
        raw = await ws.receive_text()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON payload.") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object.")
        if payload.get("v") != 1:
            raise ValueError("Unsupported protocol version.")
        return payload

    async def _ws_authenticate(websocket: WebSocket, session: AsyncSession) -> tuple[str, str]:
        await websocket.send_json({"v": 1, "type": "hello", "server_version": "0.1.0", "motd": cfg.motd})
        msg = await _parse_ws_message(websocket)
        if msg.get("type") != "auth":
            raise ValueError("Expected auth message.")
        token = str(msg.get("token", ""))
        request_id = str(msg.get("request_id", "")) or None
        try:
            payload = security.decode_access_token(token)
        except jwt.InvalidTokenError as exc:
            raise ValueError("Invalid access token.") from exc
        account_id = str(payload.get("sub", ""))
        if not account_id:
            raise ValueError("Invalid access token.")
        account = await session.get(Account, uuid.UUID(account_id))
        if not account:
            raise ValueError("Account not found.")
        return account_id, request_id or ""

    @app.on_event("startup")
    async def startup() -> None:
        await db.create_all()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await db.close()

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "service": "cryptclash-server", "version": "0.1.0"}

    @app.post("/api/auth/register", response_model=TokenResponse)
    async def register(request: RegisterRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
        try:
            account = await register_account(session, security, request.username, request.password)
            _, tokens = await authenticate_account(session, security, account.username, request.password)
        except ServiceError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            access_expires_at=tokens.access_expires_at,
            refresh_expires_at=tokens.refresh_expires_at,
        )

    @app.post("/api/auth/login", response_model=TokenResponse)
    async def login(request: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
        try:
            _, tokens = await authenticate_account(session, security, request.username, request.password)
        except ServiceError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            access_expires_at=tokens.access_expires_at,
            refresh_expires_at=tokens.refresh_expires_at,
        )

    @app.post("/api/auth/refresh", response_model=TokenResponse)
    async def refresh(request: RefreshRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
        try:
            _, tokens = await rotate_refresh_token(session, security, request.refresh_token)
        except ServiceError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            access_expires_at=tokens.access_expires_at,
            refresh_expires_at=tokens.refresh_expires_at,
        )

    @app.post("/api/auth/logout")
    async def logout(request: RefreshRequest, session: AsyncSession = Depends(get_session)) -> dict:
        await revoke_refresh_token(session, security, request.refresh_token)
        return {"ok": True}

    @app.get("/api/characters", response_model=list[CharacterResponse])
    async def characters(
        account: Account = Depends(get_account_from_header), session: AsyncSession = Depends(get_session)
    ) -> list[CharacterResponse]:
        rows = await list_characters(session, account.id)
        return [_serialize_character(row) for row in rows]

    @app.post("/api/characters", response_model=CharacterResponse)
    async def character_create(
        request: CharacterCreateRequest,
        account: Account = Depends(get_account_from_header),
        session: AsyncSession = Depends(get_session),
    ) -> CharacterResponse:
        try:
            character = await create_character(session, account.id, request.name, request.archetype)
        except ServiceError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return _serialize_character(character)

    @app.websocket("/ws/hub")
    async def ws_hub(websocket: WebSocket) -> None:
        await websocket.accept()
        async with db.session() as session:
            account_id = ""
            connection_id = ""
            try:
                account_id, request_id = await _ws_authenticate(websocket, session)
                connection = await hub_state.join(account_id)
                connection_id = connection.connection_id
                async with hub_clients_lock:
                    hub_clients[connection_id] = HubClient(websocket=websocket, account_id=account_id, connection_id=connection_id)
                await websocket.send_json({"v": 1, "type": "auth_ack", "request_id": request_id, "ok": True})
                await broadcast_presence()

                while True:
                    msg = await _parse_ws_message(websocket)
                    request_id = str(msg.get("request_id", "")) or None
                    msg_type = msg.get("type")

                    if msg_type == "presence_set":
                        character_id = str(msg.get("character_id", ""))
                        character = await session.get(Character, uuid.UUID(character_id))
                        if not character or str(character.account_id) != account_id:
                            await websocket.send_json(
                                ErrorPayload(
                                    request_id=request_id, code="character_not_found", message="Character not found."
                                ).model_dump()
                            )
                            continue
                        flags = list(msg.get("status_flags", []))
                        await hub_state.set_presence(
                            connection_id=connection_id,
                            character_id=str(character.id),
                            character_name=character.name,
                            archetype=character.archetype,
                            level=character.level,
                            status_flags=[str(flag) for flag in flags],
                        )
                        async with hub_clients_lock:
                            if connection_id in hub_clients:
                                hub_clients[connection_id].character_id = str(character.id)
                        await websocket.send_json({"v": 1, "type": "presence_set_ack", "request_id": request_id, "ok": True})
                        await broadcast_presence()
                        continue

                    if msg_type == "reaction":
                        allowed = await reaction_limiter.allow(f"{account_id}:hub")
                        if not allowed:
                            await websocket.send_json(
                                ErrorPayload(
                                    request_id=request_id,
                                    code="reaction_rate_limited",
                                    message="Too many reactions. Try again shortly.",
                                ).model_dump()
                            )
                            continue
                        await hub_broadcast(
                            {
                                "v": 1,
                                "type": "reaction_event",
                                "request_id": request_id,
                                "sender_character_id": hub_clients.get(connection_id).character_id if connection_id in hub_clients else None,
                                "emote": str(msg.get("emote", "👍")),
                                "target": str(msg.get("target", "hub")),
                            }
                        )
                        continue

                    if msg_type == "party_create":
                        client = hub_clients.get(connection_id)
                        if not client or not client.character_id:
                            await websocket.send_json(
                                ErrorPayload(request_id=request_id, code="presence_required", message="Set presence first.").model_dump()
                            )
                            continue
                        party = await hub_state.create_party(client.character_id)
                        await ensure_party_row(session, party.party_id, party.leader_character_id, party.chat_mode)
                        await ensure_party_member_rows(session, party.party_id, party.members)
                        await websocket.send_json({"v": 1, "type": "party_create_ack", "request_id": request_id, "ok": True})
                        await emit_party_state(party.party_id)
                        continue

                    if msg_type == "party_invite":
                        client = hub_clients.get(connection_id)
                        target_character_id = str(msg.get("target_character_id", ""))
                        if not client or not client.character_id:
                            await websocket.send_json(
                                ErrorPayload(request_id=request_id, code="presence_required", message="Set presence first.").model_dump()
                            )
                            continue
                        party_id = hub_state.party_by_character.get(client.character_id)
                        if not party_id:
                            await websocket.send_json(
                                ErrorPayload(request_id=request_id, code="party_required", message="Create a party first.").model_dump()
                            )
                            continue
                        party = await hub_state.invite_member(party_id, target_character_id)
                        if not party:
                            await websocket.send_json(
                                ErrorPayload(request_id=request_id, code="party_not_found", message="Party not found.").model_dump()
                            )
                            continue
                        await ensure_party_member_rows(session, party.party_id, party.members)
                        await websocket.send_json({"v": 1, "type": "party_invite_ack", "request_id": request_id, "ok": True})
                        await emit_party_state(party.party_id)
                        continue

                    if msg_type == "party_ready":
                        client = hub_clients.get(connection_id)
                        if not client or not client.character_id:
                            await websocket.send_json(
                                ErrorPayload(request_id=request_id, code="presence_required", message="Set presence first.").model_dump()
                            )
                            continue
                        party = await hub_state.set_ready(client.character_id, bool(msg.get("ready", False)))
                        if not party:
                            await websocket.send_json(
                                ErrorPayload(request_id=request_id, code="party_not_found", message="Party not found.").model_dump()
                            )
                            continue
                        await ensure_party_member_rows(session, party.party_id, party.members)
                        await websocket.send_json({"v": 1, "type": "party_ready_ack", "request_id": request_id, "ok": True})
                        await emit_party_state(party.party_id)
                        continue

                    if msg_type == "queue_join":
                        client = hub_clients.get(connection_id)
                        if not client or not client.character_id:
                            await websocket.send_json(
                                ErrorPayload(request_id=request_id, code="presence_required", message="Set presence first.").model_dump()
                            )
                            continue
                        party_id = hub_state.party_by_character.get(client.character_id)
                        if not party_id:
                            await websocket.send_json(
                                ErrorPayload(request_id=request_id, code="party_required", message="Create a party first.").model_dump()
                            )
                            continue
                        dungeon_type = str(msg.get("dungeon_type", "standard")) or "standard"
                        position = await hub_state.join_queue(party_id, dungeon_type)
                        await websocket.send_json(
                            {
                                "v": 1,
                                "type": "queue_state",
                                "request_id": request_id,
                                "position": position,
                                "eta_estimate": max(5, position * 8),
                                "dungeon_type": dungeon_type,
                            }
                        )
                        matched_party = await hub_state.pop_match_party(dungeon_type)
                        if matched_party:
                            instance_id, character_ids = await assign_instance_to_party(session, matched_party, dungeon_type)
                            for character_id in character_ids:
                                target_conn = next(
                                    (conn_id for conn_id, client_row in hub_clients.items() if client_row.character_id == character_id),
                                    None,
                                )
                                if target_conn:
                                    await hub_send(
                                        target_conn,
                                        {"v": 1, "type": "instance_assigned", "instance_id": instance_id, "dungeon_type": dungeon_type},
                                    )
                        continue

                    if msg_type == "queue_leave":
                        client = hub_clients.get(connection_id)
                        if not client or not client.character_id:
                            await websocket.send_json(
                                ErrorPayload(request_id=request_id, code="presence_required", message="Set presence first.").model_dump()
                            )
                            continue
                        party_id = hub_state.party_by_character.get(client.character_id)
                        dungeon_type = str(msg.get("dungeon_type", "standard")) or "standard"
                        if party_id:
                            await hub_state.leave_queue(party_id, dungeon_type)
                        await websocket.send_json({"v": 1, "type": "queue_leave_ack", "request_id": request_id, "ok": True})
                        continue

                    await websocket.send_json(
                        ErrorPayload(request_id=request_id, code="unknown_type", message="Unknown message type.").model_dump()
                    )
            except (WebSocketDisconnect, ValueError) as exc:
                if isinstance(exc, ValueError):
                    await websocket.send_json(
                        ErrorPayload(code="bad_request", message=str(exc)).model_dump()
                    )
            finally:
                if connection_id:
                    await hub_state.leave(connection_id)
                    async with hub_clients_lock:
                        hub_clients.pop(connection_id, None)
                    await broadcast_presence()

    @app.websocket("/ws/instance/{instance_id}")
    async def ws_instance(instance_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with db.session() as session:
            account_id = ""
            request_id = ""
            instance_client_character_id = ""
            try:
                account_id, request_id = await _ws_authenticate(websocket, session)
                instance_runtime = await instance_manager.get(instance_id)
                if not instance_runtime:
                    await websocket.send_json(
                        ErrorPayload(request_id=request_id, code="instance_not_found", message="Instance not found.").model_dump()
                    )
                    return
                character_rows = await session.scalars(select(Character).where(Character.account_id == uuid.UUID(account_id)))
                character_ids = [str(row.id) for row in list(character_rows)]
                instance_client_character_id = next((cid for cid in character_ids if cid in instance_runtime.character_ids), "")
                if not instance_client_character_id:
                    await websocket.send_json(
                        ErrorPayload(request_id=request_id, code="character_not_in_instance", message="No eligible character for this instance.").model_dump()
                    )
                    return
                await instance_runtime.connect(account_id=account_id, character_id=instance_client_character_id)
                async with instance_clients_lock:
                    instance_clients.setdefault(instance_id, {})[account_id] = (websocket, instance_client_character_id)
                await websocket.send_json({"v": 1, "type": "auth_ack", "request_id": request_id, "ok": True})
                await websocket.send_json({"v": 1, "type": "snapshot", **instance_runtime.snapshot(instance_client_character_id)})

                while True:
                    msg = await _parse_ws_message(websocket)
                    request_id = str(msg.get("request_id", "")) or None
                    msg_type = msg.get("type")
                    if msg_type == "action_intent":
                        ok, reason = await instance_runtime.handle_action_intent(account_id=account_id, action_raw=str(msg.get("action", "")))
                        if not ok:
                            await websocket.send_json(
                                ErrorPayload(request_id=request_id, code="invalid_action", message=reason).model_dump()
                            )
                            continue
                        async with instance_clients_lock:
                            targets = list(instance_clients.get(instance_id, {}).values())
                        for ws, your_character_id in targets:
                            try:
                                await ws.send_json({"v": 1, "type": "snapshot", **instance_runtime.snapshot(your_character_id)})
                            except Exception:
                                continue
                        if instance_runtime.game.game_over():
                            rewards = instance_runtime.reward_payload()
                            await persist_instance_rewards(session, instance_id, rewards)
                            async with instance_clients_lock:
                                targets = list(instance_clients.get(instance_id, {}).values())
                            for ws, your_character_id in targets:
                                reward = rewards.get(your_character_id, {"gold": 0, "xp": 0, "items": {}})
                                try:
                                    await ws.send_json({"v": 1, "type": "result", "win": True, "rewards": reward, "instance_id": instance_id})
                                except Exception:
                                    continue
                            await instance_manager.remove(instance_id)
                            break
                        continue
                    if msg_type == "reaction":
                        allowed = await reaction_limiter.allow(f"{account_id}:{instance_id}")
                        if not allowed:
                            await websocket.send_json(
                                ErrorPayload(
                                    request_id=request_id,
                                    code="reaction_rate_limited",
                                    message="Too many reactions. Try again shortly.",
                                ).model_dump()
                            )
                            continue
                        async with instance_clients_lock:
                            targets = list(instance_clients.get(instance_id, {}).values())
                        for ws, _ in targets:
                            try:
                                await ws.send_json(
                                    {
                                        "v": 1,
                                        "type": "reaction_event",
                                        "sender_character_id": instance_client_character_id,
                                        "emote": str(msg.get("emote", "👍")),
                                        "target": str(msg.get("target", "party")),
                                    }
                                )
                            except Exception:
                                continue
                        continue
                    await websocket.send_json(
                        ErrorPayload(request_id=request_id, code="unknown_type", message="Unknown message type.").model_dump()
                    )
            except (WebSocketDisconnect, ValueError):
                pass
            finally:
                if account_id:
                    runtime = await instance_manager.get(instance_id)
                    if runtime:
                        await runtime.disconnect(account_id)
                async with instance_clients_lock:
                    by_account = instance_clients.get(instance_id, {})
                    by_account.pop(account_id, None)
                    if not by_account:
                        instance_clients.pop(instance_id, None)

    return app
