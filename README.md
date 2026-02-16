# Crypt Clash CLI (MVP)

A playable full-screen terminal RPG prototype using Python + Textual.

## What is playable now

- Party-based adventure loop with exploration + encounters
- Turn-based action selection in a full-screen TUI with a dedicated battle screen panel
- Combat actions: `Attack`, `Skills`, `Defend`, `Path`, `Bag`, `Equip Gear`, `Rest`
- Explore actions: `Venture Deeper`, `Look Around`, `Path`, `Bag`, `Equip Gear`, `Rest`
- Explore actions also include contextual `Open Chest` after successful chest discovery.
- `Path` opens a dedicated mini-map overlay with route progress and legend
- Loot rewards, consumables, and simple per-character gear progression
- Encounter XP and level progression (`level`, `xp`, level-up stat gains)
- Autosave after actions, plus optional named save slots
- Ironman mode (one life, no manual save, hall-of-fame archive on victory)

## Quickstart

```bash
cd /Users/brianvassell/DND-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cryptclash
```

### One-command install (macOS/Linux)

If you're publishing this repo publicly, you can also let players run the installer script:

```bash
curl -fsSL https://raw.githubusercontent.com/VF-AdminOver/Crpyt-Clash/main/scripts/install.sh | bash -s -- --repo https://github.com/VF-AdminOver/Crpyt-Clash.git
cryptclash
```

### Homebrew tap (best UX for macOS users)

Once you publish a Homebrew tap, players can install with:

```bash
brew tap VF-AdminOver/games
brew install crypt-clash
cryptclash
```

Single command (no separate tap step):

```bash
brew install vf-adminover/games/crypt-clash && cryptclash
```

Primary command is `cryptclash` (alias: `crypt-clash`). Legacy aliases `DND` / `dnd` remain for compatibility.

## Start modes

```bash
cryptclash new --mode normal
cryptclash new --mode ironman
cryptclash new --hero <character_id>
```

`cryptclash new` opens a character creation flow before the run begins:
- Name (2-16 chars, letters/space/hyphen)
- Archetype (`Fighter`, `Rogue`, `Cleric`, `Mage`)
- Point-Buy 27 stat allocation (base 8-15)
- Live preview of derived combat stats while adjusting point-buy
- Review and confirm

Only `cryptclash new` opens creator. `continue` and `load` skip it and resume saves.

## Roster

```bash
cryptclash roster
```

Use roster IDs with `--hero` to begin with a saved hero.

## Continue a run

```bash
cryptclash continue
```

## Load a specific save

```bash
cryptclash load --file ~/.dnd-cli/saves/autosave.json
cryptclash load --slot boss-run
```

## Create a save slot

```bash
cryptclash save --slot boss-run
```

## List saves

```bash
cryptclash list-saves
```

`cryptclash list-saves` now shows both active saves and `hall-of-fame` ironman victories.

## Get a quick gameplay tip

```bash
cryptclash tip
```

## Online host/join (authoritative host)

Start a host session (this machine owns the game state and opens the full Textual battle UI):

```bash
cryptclash host --bind 0.0.0.0 --port 8765 --code CRYP --name Host
cryptclash host --bind 0.0.0.0 --port 8765 --code CRYP --name Host --hero <character_id>
cryptclash host --bind 0.0.0.0 --port 8765 --code CRYP --name Host --chat-mode reactions_only
cryptclash host --bind 0.0.0.0 --port 8765 --code CRYP --name Host --chat-mode text_18_plus
```

Join from another terminal (or another machine on LAN) with the same full UI:

```bash
cryptclash join --host 127.0.0.1 --port 8765 --code CRYP --name Iris
```

Notes:
- Host is authoritative; clients send action intents only.
- First joined players are assigned party members automatically; extra joiners spectate.
- Unassigned party members are auto-piloted so the run never stalls.
- Room comms default to reactions-only; host can opt into `text_18_plus` chat mode.
- Host and join clients both use the polished panel UI (party, battle/map, log, actions).

## Controls

- Number keys / numpad `1-9`: choose matching action instantly
- Arrow keys + Enter: move and confirm selected action
- Mouse click: click icon action rows to trigger
- `s`: save to autosave (disabled in ironman)
- `t`: add a gameplay tip to the log
- `r`: restart encounter
- `q`: quit

## Combat UX (V2)

- Turn flow: `Action -> Style/Skill -> Target` while keeping initiative order.
- `Attack` now opens styles: `Quick` (+hit, lower damage), `Balanced`, `Heavy` (-hit, higher damage).
- `Skills` opens class moves (2 per archetype) with mana cost shown as `(X MP)`.
- Manual target picker appears for enemy/ally targeting with `Target:` labels.
- Mana rules: spend on skills, +1 mana at start of your turn, and +2 mana when using `Rest` in combat.

## Chained Adventures

- Clearing all rooms now ends the current arc and unlocks `Begin Next Adventure`.
- Selecting it keeps your party progression (levels/gear), restores HP/MP, and starts a tougher new 3-room descent.
- Enemy stats and rewards scale by adventure number, so runs can continue as a long-form campaign.

## Treasure Chests

- Some rooms contain hidden treasure chests.
- `Look Around` performs a discovery roll: `d20 + INT mod vs DC 13` (max 2 attempts per room).
- `Open Chest` appears only after discovery and can be used once.
- Chests grant bonus gold and often a bonus consumable/item, and can only be opened once.

## Look Around Outcomes

- `Look Around` can trigger a one-time roaming encounter check per room.
- On trigger, combat starts immediately as a side encounter and does not advance room depth when won.

## Loot Economy (V2.2)

- Combat and chest rewards now use one unified item-drop pipeline.
- Rarity tiers use weighted odds (`Common 65%`, `Uncommon 28%`, `Rare 7%`), with chest rolls slightly favoring higher tiers.
- Rare pity protection guarantees the next drop is Rare after 5 non-rare drops.
- Smart bias softly boosts drops that fit alive party archetypes and under-equipped slots while still allowing surprises.
- Duplicate gear past useful copy limits is auto-salvaged into gold and logged.

## Store Crafting & Trade

- Store actions now show explicit recipe costs and payouts in-line.
- Craft recipes currently include `Healing Potion`, `Smoke Bomb`, and `Holy Water`.
- Trade actions are dynamic (`Sell ... x1` and `Sell ... xAll`) based on current inventory.

## Notes

- This is an MVP focused on immediate playability.
- Content is original and text-only in-terminal (ASCII-friendly).

## Roadmap

- Track current status and upcoming phases in `/Users/brianvassell/DND-cli/docs/roadmap.md`.
- Online systems spec draft is in `/Users/brianvassell/DND-cli/docs/online-roadmap.md`.

## Documentation

- Installation guide: `/Users/brianvassell/DND-cli/docs/installation.md`
- Homebrew distribution guide: `/Users/brianvassell/DND-cli/docs/homebrew.md`
- Full game guide: `/Users/brianvassell/DND-cli/docs/game-manual.md`
- Project roadmap: `/Users/brianvassell/DND-cli/docs/roadmap.md`
- Online systems roadmap: `/Users/brianvassell/DND-cli/docs/online-roadmap.md`
