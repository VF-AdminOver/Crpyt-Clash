# Crypt Clash Game Manual

This guide covers how to install, start, play, and troubleshoot the game.

## 1) Install & Launch

```bash
cd /path/to/project
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cryptclash
```

Primary command is `cryptclash` (alias `crypt-clash`). Legacy `DND` / `dnd` aliases still work.

If the command is not found, activate the venv and reinstall with `pip install -e .`.

## 2) Command Reference

### Start & Progress

- `cryptclash`  
  Starts a new normal run (same as `cryptclash new --mode normal`).
- `cryptclash new --mode normal`
- `cryptclash new --mode ironman`
- `cryptclash new --hero <character_id>`
- `cryptclash continue`
- `cryptclash load --file <path>`
- `cryptclash load --slot <name>`

### Saves & Utility

- `cryptclash save --slot <name>`
- `cryptclash list-saves`
- `cryptclash roster`
- `cryptclash tip`

### Online

- `cryptclash host --bind 0.0.0.0 --port 8765 --code CRYP --name Host`
- `cryptclash host --hero <character_id> --code CRYP --name Host`
- `cryptclash host --chat-mode reactions_only --code CRYP --name Host`
- `cryptclash host --chat-mode text_18_plus --code CRYP --name Host`
- `cryptclash join --host <ip> --port 8765 --code CRYP --name <player>`

## 3) Core Controls

- `1-9` (or numpad): choose action
- Arrow keys + `Enter`: navigate and confirm
- Mouse click: clickable action rows
- `s`: save (disabled in ironman)
- `t`: tip
- `r`: restart encounter
- `q` / `esc`: quit

## 4) Tutorial Mode

- On first local launcher run, tutorial starts automatically once.
- During tutorial, choose `Skip Tutorial` anytime from the actions panel.
- Tutorial can be replayed later from launcher via `Tutorial`.
- Tutorial is isolated onboarding and does not overwrite your normal autosave run.

## 5) Gameplay Loop

1. Create/select hero.
2. Explore room.
3. Trigger combat.
4. Resolve encounter and collect rewards.
5. Move deeper through all rooms.
6. Start next adventure with scaled difficulty.

## 6) Character Creation

On `cryptclash new`, creator flow is:

1. Name
2. Archetype (`Fighter`, `Rogue`, `Cleric`, `Mage`)
3. Point-buy stats (27-point budget, base range 8–15)
4. Review and confirm

Your main hero is saved to roster and can be reused with `--hero`.

## 7) Combat Flow (RPG-Style)

Turn flow:

1. `Attack` or `Skills` (or utility)
2. If attack: pick style (`Quick`, `Balanced`, `Heavy`)
3. Pick target (`Target:` / `Target Ally:`)
4. Resolve roll and apply outcome

### Attack styles

- `Quick`: higher hit chance, lower damage
- `Balanced`: baseline
- `Heavy`: lower hit chance, higher damage

### Skills & mana

- Skills show mana cost in the action label.
- Mana is spent when a skill resolves.
- Acting unit gains mana at turn start.
- `Rest` in combat grants extra mana to the acting unit.

### Dice motion feedback

- Dice checks now animate in phases: fast spin, visible slowdown, then settle.
- The battle panel shows rolling momentum text so outcomes are easier to read.

## 8) Exploration Systems

### Look Around

- Reveals room flavor and can trigger roaming encounters.
- Can discover hidden chests via search roll.

### Space exploration

- Rooms use a space-based exploration track.
- Space events can include loot, clues, hazards, and ambushes.

### Chests

- `Open Chest` is hidden until discovered.
- Discovery roll: `d20 + INT mod` vs room DC.
- Two discovery attempts per room.

### Utility actions

- `Path`: map/route overlay
- `Bag`: consumables
- `Equip Gear`: per-character equipment
- `Rest`: one short rest per room
- `Backtrack`: return to cleared rooms (when allowed)
- `Hunt`: trigger respawn encounters (limited uses)
- `Harvest`: collect crafting materials

## 9) Loot, Economy, and Progression

### Loot

- Unified drops for combat and chests.
- Rarity tiers: common / uncommon / rare.
- Rare pity: guaranteed rare after streak of non-rare drops.
- Smart bias favors party-relevant equipment without hard-locking outcomes.
- Excess duplicates can auto-salvage into gold.

### Store, crafting, trade

- Store availability follows milestone cadence.
- Crafting labels show full costs in action text.
- Trade labels show direct payout (including `xAll` where available).

### Progression

- XP and levels scale through longer runs.
- Every 10th adventure is a boss adventure.
- Boss rewards include unique ability-gear messaging.

## 10) Online Play Basics

- Host is authoritative.
- Clients send action intents.
- Party control is assigned to connected players when possible.
- Uncontrolled party members auto-play to avoid dead turns.
- Chat defaults to reactions-only.
- `text_18_plus` mode is explicit host opt-in.

## 11) Troubleshooting

### `command not found`

```bash
cd /path/to/project
source .venv/bin/activate
pip install -e .
```

### Save/roster issues

- Confirm you are using the same Python environment used to install the package.
- Run `cryptclash roster` to confirm hero IDs before using `--hero`.

### UI/input confusion

- Use number keys for fastest action selection.
- Use `t` for contextual tips.
- If needed, restart current encounter with `r`.

## 12) Related Docs

- Product roadmap: `/path/to/project/docs/roadmap.md`
- Online systems roadmap: `/path/to/project/docs/online-roadmap.md`
