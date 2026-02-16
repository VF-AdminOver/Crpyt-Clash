# DND CLI Online Roadmap (Spec Draft)

## Scope

This document defines protocol-level and gameplay-level design for upcoming online features:

- Reactions-first communication
- Age-gated chat mode (opt-in)
- 3v3 tournaments and PvP lifecycle
- Moderation hooks and anti-abuse safeguards

Runtime implementation can land in phased slices; this file is the contract baseline.

## 1) Reactions-Only Default Protocol

### Event

```json
{
  "type": "reaction",
  "emote": "🔥",
  "target": "character_id|enemy_id|room",
  "sender": "client_id",
  "timestamp": "iso-8601"
}
```

### Rules

- Enabled by default in all online rooms.
- Low-rate spam protection: max 4 reactions per 10 seconds per client.
- Reactions appear in Adventure Log and optional overlay lane.

## 2) Age-Gated Text Chat Mode (Disabled by Default)

### Room setting

```json
{
  "chat_mode": "reactions_only|text_18_plus"
}
```

### Text message event

```json
{
  "type": "chat",
  "sender": "client_id",
  "message": "string",
  "timestamp": "iso-8601"
}
```

### Safety rules

- `reactions_only` is default.
- `text_18_plus` requires explicit host enablement at room start.
- Profanity filter + mute + host kick must be available before broad rollout.

## 3) 3v3 Tournament Schema

## Lobby contract

```json
{
  "type": "tourney_lobby",
  "mode": "3v3",
  "state": "open|locked|in_match|complete",
  "teams": {
    "A": ["character_id"],
    "B": ["character_id"]
  },
  "seed": 7
}
```

## Initiative rules

- Every participant rolls `d20`.
- **Closer to 20 acts later** (descending urgency model).
- Tie-breaker: highest speed/dex stat acts earlier among tied results.
- Final tie: deterministic host RNG order.

## Match lifecycle

1. `open` → team assembly
2. `locked` → roster freeze + initiative roll
3. `in_match` → combat turns
4. `complete` → reward/reporting payload

## Result payload

```json
{
  "type": "tourney_result",
  "winner_team": "A|B",
  "mvp": "character_id",
  "rounds": 7,
  "timestamp": "iso-8601"
}
```

## 4) Moderation and Anti-Abuse Hooks

- `mute_user`
- `kick_user`
- reaction rate-limit violations
- chat filter violations
- host audit log entry for all moderation actions

## 5) Phased Delivery

1. Reactions protocol + UI display
2. Age-gated chat room flag + enforcement
3. PvP lobby schema + dry-run simulation
4. 3v3 runtime integration
5. Tournament rewards + ranking persistence
