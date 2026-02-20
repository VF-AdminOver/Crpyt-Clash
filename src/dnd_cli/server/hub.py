from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field


@dataclass
class HubConnection:
    account_id: str
    connection_id: str
    character_id: str | None = None
    character_name: str | None = None
    archetype: str | None = None
    level: int = 1
    status_flags: list[str] = field(default_factory=list)


@dataclass
class PartyState:
    party_id: str
    leader_character_id: str
    members: dict[str, bool]
    state: str = "forming"
    chat_mode: str = "reactions_only"


class ReactionLimiter:
    def __init__(self, max_count: int, window_seconds: int) -> None:
        self.max_count = max_count
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.time()
        async with self._lock:
            queue = self._events.setdefault(key, deque())
            while queue and now - queue[0] > self.window_seconds:
                queue.popleft()
            if len(queue) >= self.max_count:
                return False
            queue.append(now)
            return True


class HubState:
    def __init__(self, presence_limit: int) -> None:
        self.presence_limit = presence_limit
        self.connections: dict[str, HubConnection] = {}
        self.parties: dict[str, PartyState] = {}
        self.queues: dict[str, list[str]] = {}
        self.party_by_character: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def join(self, account_id: str) -> HubConnection:
        async with self._lock:
            connection = HubConnection(account_id=account_id, connection_id=f"h-{uuid.uuid4().hex[:10]}")
            self.connections[connection.connection_id] = connection
            return connection

    async def leave(self, connection_id: str) -> None:
        async with self._lock:
            connection = self.connections.pop(connection_id, None)
            if not connection or not connection.character_id:
                return
            party_id = self.party_by_character.get(connection.character_id)
            if party_id:
                party = self.parties.get(party_id)
                if party and connection.character_id in party.members:
                    del party.members[connection.character_id]
                    self.party_by_character.pop(connection.character_id, None)
                    if not party.members:
                        self.parties.pop(party.party_id, None)
                    elif party.leader_character_id == connection.character_id:
                        party.leader_character_id = next(iter(party.members))

    async def set_presence(
        self,
        connection_id: str,
        character_id: str,
        character_name: str,
        archetype: str,
        level: int,
        status_flags: list[str],
    ) -> HubConnection | None:
        async with self._lock:
            connection = self.connections.get(connection_id)
            if not connection:
                return None
            connection.character_id = character_id
            connection.character_name = character_name
            connection.archetype = archetype
            connection.level = level
            connection.status_flags = status_flags[:5]
            return connection

    async def snapshot(self) -> list[dict]:
        async with self._lock:
            players = [connection for connection in self.connections.values() if connection.character_id]
            players = players[: self.presence_limit]
            return [
                {
                    "connection_id": row.connection_id,
                    "character_id": row.character_id,
                    "name": row.character_name,
                    "archetype": row.archetype,
                    "level": row.level,
                    "status_flags": row.status_flags,
                }
                for row in players
            ]

    async def create_party(self, leader_character_id: str) -> PartyState:
        async with self._lock:
            existing_id = self.party_by_character.get(leader_character_id)
            if existing_id and existing_id in self.parties:
                return self.parties[existing_id]
            party_id = str(uuid.uuid4())
            party = PartyState(party_id=party_id, leader_character_id=leader_character_id, members={leader_character_id: True})
            self.parties[party_id] = party
            self.party_by_character[leader_character_id] = party_id
            return party

    async def invite_member(self, party_id: str, target_character_id: str) -> PartyState | None:
        async with self._lock:
            party = self.parties.get(party_id)
            if not party:
                return None
            party.members.setdefault(target_character_id, False)
            self.party_by_character[target_character_id] = party_id
            return party

    async def set_ready(self, character_id: str, ready: bool) -> PartyState | None:
        async with self._lock:
            party_id = self.party_by_character.get(character_id)
            if not party_id:
                return None
            party = self.parties.get(party_id)
            if not party or character_id not in party.members:
                return None
            party.members[character_id] = ready
            return party

    async def join_queue(self, party_id: str, dungeon_type: str) -> int:
        async with self._lock:
            queue = self.queues.setdefault(dungeon_type, [])
            if party_id not in queue:
                queue.append(party_id)
            return queue.index(party_id) + 1

    async def leave_queue(self, party_id: str, dungeon_type: str) -> None:
        async with self._lock:
            queue = self.queues.get(dungeon_type, [])
            if party_id in queue:
                queue.remove(party_id)

    async def pop_match_party(self, dungeon_type: str) -> str | None:
        async with self._lock:
            queue = self.queues.get(dungeon_type, [])
            if not queue:
                return None
            return queue.pop(0)

    def to_party_payload(self, party: PartyState) -> dict:
        return {
            "party_id": party.party_id,
            "leader_character_id": party.leader_character_id,
            "members": [{"character_id": character_id, "ready": ready} for character_id, ready in party.members.items()],
            "state": party.state,
            "chat_mode": party.chat_mode,
        }
