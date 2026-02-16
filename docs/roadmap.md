# DND CLI Roadmap

**Last Updated:** 2026-02-15  
Single source-of-truth for shipped features, active work, and upcoming phases.

## How to Read

- **Status Legend:** `Done`, `In Progress`, `Next`, `Planned`, `Deferred`
- **Priority Tags:** `P0` (critical), `P1` (important), `P2` (nice-to-have)

## Current Snapshot

### What shipped recently

- Loot rarity + pity + smart bias + salvage.
- Chest discovery gating via search roll.
- `Look Around` roaming encounters.
- 15-space room exploration and space events.
- HP/MP notation, XP gauge, roll animation, toast system.
- Action list text cleanup and MP visibility improvements.
- Backtrack / Hunt / Harvest / store shell / boss cadence base.
- PvE donation pool mechanics (base).

### Biggest blockers / open issues

- Economy balance still needs tuning for long-run progression.
- Tournament runtime is still specification-level and not yet playable.

### Discussed but not implemented yet

- **[Planned][P1] Playable 3v3 tournament runtime**  
  **Scope:** Move from schema/docs into a playable PvP flow with lobby, team lock, initiative, and match resolution.  
  **Acceptance Criteria:** Players can complete at least one full 3v3 tournament match end-to-end in-game.
  **Notes/Dependencies:** Uses the initiative rule already implemented in core game logic.

- **[Deferred][P2] Auction house / market**  
  **Scope:** Add player-facing listing, bidding, and settlement flow for items.  
  **Acceptance Criteria:** Players can list, discover, and complete item trades through a market UI.  
  **Notes/Dependencies:** Requires stronger online identity/session systems first.

- **[Deferred][P2] Full MMO runtime beyond host-authoritative sessions**  
  **Scope:** Persistent server-side world/session model with scalable multiplayer infra.  
  **Acceptance Criteria:** Sessions are persistent and not tied to a single player-host process.  
  **Notes/Dependencies:** Network, persistence, moderation, and operations foundation required.

- **[Deferred][P2] Full text chat moderation stack**  
  **Scope:** Extend current reactions + age-gated chat with moderation controls and abuse handling.  
  **Acceptance Criteria:** Includes mute/kick/filter/audit events with enforceable room policy.  
  **Notes/Dependencies:** Baseline chat-mode enforcement is done; safety/runtime expansion remains.

## Phase Buckets

## Phase 1 — Gameplay Core v1 (active)

- **[Done][P0] Gameplay Core integration + polish**  
  **Scope:** Finish cross-system flow for progression, exploration, and UX clarity.  
  **Acceptance Criteria:** End-to-end run loop is stable; no broken transitions in `new -> explore -> combat -> victory -> next adventure`.
  **Notes/Dependencies:** Added explicit end-to-end regression coverage for combat-to-next-adventure handoff.

- **[Done][P0] Result banner clarity + UX consistency**  
  **Scope:** Ensure victory/defeat outcomes are always obvious and consistent with toasts/log text.  
  **Acceptance Criteria:** Every victory/defeat state shows a clear banner, toast, and final log callout.
  **Notes/Dependencies:** Tied to battle panel rendering and state transitions.

- **[Done][P1] Hero roster persistence end-to-end**  
  **Scope:** Complete reusable hero flow across solo and host/public starts.  
  **Acceptance Criteria:** Player can list/select heroes from roster, start run with selected hero, and see updates persisted after play.
  **Notes/Dependencies:** Storage APIs exist; CLI and UI entrypoints still need full integration.

- **[Done][P0] Fix `Begin Next Adventure` dispatch bug**  
  **Scope:** Remove game-over early-return path that blocks menu action dispatch.  
  **Acceptance Criteria:** Selecting `Begin Next Adventure` from victory state reliably starts the next adventure.
  **Notes/Dependencies:** UI action handler (`action_confirm_action`) ordering.

- **[Done][P1] Complete roster + CLI integration**  
  **Scope:** Add `DND roster`, `--hero`, and host/new hero selection flow.  
  **Acceptance Criteria:** `DND new --hero <id>` and `DND host --hero <id>` work; `DND roster` lists available heroes.
  **Notes/Dependencies:** Uses `storage.py` roster APIs.

- **[Done][P1] Store milestone validation (`adv % 10 in {4,8}`)**  
  **Scope:** Validate and polish store availability cadence and UX prompts.  
  **Acceptance Criteria:** Store appears exactly on configured milestone adventures and is clearly actionable.
  **Notes/Dependencies:** Needs gameplay verification after cadence tweaks.

- **[Done][P1] Boss ability-gear balancing/messaging**  
  **Scope:** Tune boss reward stats and ensure explicit ability messaging in UI/logs.  
  **Acceptance Criteria:** Boss rewards feel meaningful, are clearly explained, and do not break balance.
  **Notes/Dependencies:** Boss room progression and loot systems.

- **[Done][P1] Apply render mode behavior fully**  
  **Scope:** Make `hybrid_ascii` and `text_only` visibly distinct across all panels.  
  **Acceptance Criteria:** Toggling render mode immediately changes content style in battle/party/log areas.
  **Notes/Dependencies:** UI render functions and layout state.

## Phase 2 — Economy Depth

- **[Done][P1] Crafting expansion**  
  **Scope:** Add more recipes, material sinks, and clearer craft outcomes.  
  **Acceptance Criteria:** Multiple useful recipes with balanced costs and clear success feedback.
  **Notes/Dependencies:** Store now shows recipe costs and uses unified craft recipe metadata.

- **[Done][P1] Better trade UX**  
  **Scope:** Improve trade from basic sell actions to clearer exchange flows.  
  **Acceptance Criteria:** Trading is intuitive, predictable, and reflected in inventory/gold immediately.
  **Notes/Dependencies:** Store now exposes dynamic sell options with x1/xAll and explicit payout.

- **[Planned][P2] Donation-pool economy tuning**  
  **Scope:** Balance donation injection rates and chest recovery messaging.  
  **Acceptance Criteria:** Donation recovery feels rewarding without overwhelming standard loot tables.
  **Notes/Dependencies:** Loot weighting/pity systems.

## Phase 3 — Online/MMO Foundations

- **[Done][P1] Reactions protocol**  
  **Scope:** Add lightweight reactions events for online sessions.  
  **Acceptance Criteria:** Players can send/receive reaction events with stable sync behavior.
  **Notes/Dependencies:** Multiplayer snapshot/event contracts.

- **[Done][P0] Age-gated chat contract**  
  **Scope:** Define and implement policy-safe chat mode gating.  
  **Acceptance Criteria:** Default is reactions-only; text chat requires explicit age-gated room mode.
  **Notes/Dependencies:** Snapshot/join metadata now includes chat mode; oversized messages are rejected.

- **[Done][P2] Online roadmap documentation**  
  **Scope:** Publish technical design for MMO-adjacent features and constraints.  
  **Acceptance Criteria:** `docs/online-roadmap.md` exists with protocol drafts and phased implementation order.
  **Notes/Dependencies:** Cross-team alignment.

## Phase 4 — PvP/Tournament Systems

- **[Planned][P1] 3v3 tournament schema**  
  **Scope:** Define lobby, bracket, and match lifecycle models.  
  **Acceptance Criteria:** Tournament flow documented and implemented with deterministic progression states.
  **Notes/Dependencies:** Online room/session contracts.

- **[Done][P1] PvP initiative rules**  
  **Scope:** Initiative by d20 where rolls closer to 20 act later; ties by speed stat.  
  **Acceptance Criteria:** Initiative ordering is deterministic and validated by tests.
  **Notes/Dependencies:** PvP combat mode separation.

## Backlog / Parking Lot

- **[Deferred][P2] Full auction house**
- **[Deferred][P2] Full chat runtime beyond gated/reactions baseline**
- **[Deferred][P2] Full MMO infra beyond host-authoritative sessions**

## Roadmap Hygiene

- At the end of each implementation batch, move completed items to `Done` and date-stamp the change log.
- Keep `Next` to a maximum of 5 items (`P0/P1` only) so focus stays clear.
- If scope changes, add a short note under the item’s `Notes/Dependencies`.
- Do not delete deferred items; keep them visible in `Backlog / Parking Lot`.
- When a blocker is resolved, remove it from “Biggest blockers / open issues” in the same update.

## Change Log

- **2026-02-15:** Added roadmap v1 with phased breakdown from playtest feedback and current implementation state.
- **2026-02-15:** Completed next P0/P1 sweep for gameplay core (victory dispatch, roster CLI/host flow, store cadence, render-mode behavior, boss reward messaging), added reactions runtime and age-gated chat contract scaffold, and expanded tests.
- **2026-02-15:** Closed remaining P0/P1 items in this batch: gameplay loop e2e regression, chat-mode metadata hardening, dynamic crafting/trade store actions, and roadmap status refresh.
- **2026-02-15:** Added explicit “Discussed but not implemented yet” section to track tournament runtime, auction house, MMO infra, and full text-chat moderation work.
