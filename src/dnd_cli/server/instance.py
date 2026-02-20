from __future__ import annotations

import asyncio
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


@dataclass
class InstanceConnection:
    account_id: str
    character_id: str
    instance_id: str
    connected_at: datetime


class InstanceRuntime:
    def __init__(self, instance_id: str, character_ids: list[str], seed: int = 7) -> None:
        self.instance_id = instance_id
        self.character_ids = character_ids
        self.game = Game(seed=seed, run_mode="normal")
        self.controllers: dict[str, str] = {}
        self.connections: dict[str, InstanceConnection] = {}
        self.disconnected_at: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def connect(self, account_id: str, character_id: str) -> InstanceConnection:
        async with self._lock:
            connection = InstanceConnection(
                account_id=account_id,
                character_id=character_id,
                instance_id=self.instance_id,
                connected_at=datetime.utcnow(),
            )
            self.connections[account_id] = connection
            self.controllers[character_id] = account_id
            self.disconnected_at.pop(character_id, None)
            return connection

    async def disconnect(self, account_id: str) -> None:
        async with self._lock:
            connection = self.connections.pop(account_id, None)
            if connection:
                self.disconnected_at[connection.character_id] = datetime.utcnow()

    async def handle_action_intent(self, account_id: str, action_raw: str) -> tuple[bool, str]:
        async with self._lock:
            labels = self.game.action_labels()
            action = resolve_action_input(action_raw, labels)
            if not action:
                return False, "Invalid action."
            allowed, reason = self._can_account_act(account_id)
            if not allowed:
                return False, reason
            self.game.perform_player_action(action)
            if self.game.mode == "combat" and self.game.action_consumed_turn and not self.game.game_over():
                self.game.run_enemy_turns_until_player()
            self._auto_play_uncontrolled_turns()
            return True, ""

    def snapshot(self, your_character_id: str | None) -> dict:
        actor = self.game.active_unit()
        active_character_id = ""
        if actor and actor in self.game.party:
            active_character_id = actor.character_id or actor.name
        party_rows: list[dict[str, object]] = []
        for unit in self.game.party:
            character_id = unit.character_id or unit.name
            owner_id = self.controllers.get(character_id)
            party_rows.append(
                {
                    "name": unit.name.split(" (", 1)[0],
                    "hp": unit.hp,
                    "max_hp": unit.max_hp,
                    "mana": unit.mana,
                    "max_mana": unit.max_mana,
                    "character_id": character_id,
                    "controller_id": owner_id,
                    "is_active": character_id == active_character_id,
                }
            )
        return {
            "instance_id": self.instance_id,
            "status": self.game.status_summary(),
            "room": self.game.current_room_name(),
            "depth": self.game.depth_text(),
            "mode": self.game.mode,
            "menu": self.game.menu,
            "menu_context": self.game.menu_context_text(),
            "last_roll": self.game.last_roll_text,
            "log": self.game.log[-8:],
            "actions": self.game.action_labels(),
            "party": party_rows,
            "active_character_id": active_character_id,
            "your_character_id": your_character_id,
            "is_complete": self.game.game_over(),
        }

    def reward_payload(self) -> dict:
        rewards: dict[str, dict] = {}
        base_gold = max(8, self.game.adventure_number * 5)
        for character_id in self.character_ids:
            rewards[character_id] = {
                "gold": base_gold,
                "xp": 15,
                "items": {"healing_potion": 1},
            }
        return rewards

    def _can_account_act(self, account_id: str) -> tuple[bool, str]:
        if self.game.mode != "combat":
            return True, ""
        actor = self.game.active_unit()
        if actor is None:
            return False, "No active turn."
        if actor not in self.game.party:
            return False, "Wait for enemy turn resolution."
        character_id = actor.character_id or actor.name
        owner = self.controllers.get(character_id)
        if owner and owner != account_id:
            return False, "Wait for controlling player."
        return True, ""

    def _auto_play_uncontrolled_turns(self) -> None:
        while self.game.mode == "combat" and self.game.is_player_turn() and not self.game.game_over():
            actor = self.game.active_unit()
            if actor is None or actor not in self.game.party:
                return
            character_id = actor.character_id or actor.name
            owner = self.controllers.get(character_id)
            if owner and owner in self.connections:
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


class InstanceManager:
    def __init__(self) -> None:
        self.instances: dict[str, InstanceRuntime] = {}
        self._lock = asyncio.Lock()

    async def create_instance(self, character_ids: list[str], seed: int = 7) -> InstanceRuntime:
        async with self._lock:
            instance_id = str(uuid.uuid4())
            runtime = InstanceRuntime(instance_id=instance_id, character_ids=character_ids, seed=seed)
            self.instances[instance_id] = runtime
            return runtime

    async def get(self, instance_id: str) -> InstanceRuntime | None:
        async with self._lock:
            return self.instances.get(instance_id)

    async def remove(self, instance_id: str) -> None:
        async with self._lock:
            self.instances.pop(instance_id, None)
