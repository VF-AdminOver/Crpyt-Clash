from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from dnd_cli.creator import (
    ARCHETYPES,
    STAT_KEYS,
    apply_archetype_bonus,
    build_companions,
    build_main_character,
    point_buy_cost,
    preview_derived_stats,
    random_name,
    recommended_stats,
    remaining_points,
    validate_name,
)
from dnd_cli.game import Game, Unit
from dnd_cli.items import ITEM_DEFS, item_rarity
from dnd_cli.storage import (
    archive_ironman_victory,
    delete_active_ironman_save,
    load_roster,
    save_game,
    upsert_roster_hero,
)


class DndApp(App[None]):
    TITLE = "DND CLI - Crypt Clash MVP"
    BINDINGS = [
        ("enter", "confirm_action", "Confirm"),
        ("escape", "quit", "Quit"),
        ("z", "cycle_zoom", "Zoom"),
        ("w", "toggle_wrap", "Wrap"),
        ("g", "toggle_render", "Render"),
        ("m", "toggle_sound", "Sound"),
        ("y", "react_cheer", "React"),
    ]
    CSS = """
    Screen {
        layout: vertical;
        background: #0a1018;
        color: #d6dfeb;
    }
    #content {
        height: 1fr;
    }
    .panel {
        border: round #4a617d;
        background: #111a28;
        padding: 1;
        width: 1fr;
        margin: 0 1 1 1;
    }
    .active_panel {
        border: round #d2aa64;
        background: #162337;
    }
    Label {
        color: #9dbced;
        text-style: bold;
    }
    #log_title {
        color: #f3d58b;
    }
    #party_panel {
        width: 1.35fr;
    }
    #actions_panel {
        width: 1.15fr;
    }
    #battle_panel {
        width: 2.05fr;
    }
    #log_panel {
        width: 2.2fr;
    }
    #status {
        height: 2;
        margin: 0 1;
        border: round #5b7391;
        background: #101726;
        padding: 0 1;
    }
    #actions_title {
        margin-bottom: 1;
    }
    #actions_list {
        border: none;
        padding: 0;
    }
    #actions_list > ListItem {
        height: auto;
        min-height: 1;
    }
    #actions_list > ListItem > Label {
        text-wrap: wrap;
    }
    ListView > ListItem.--highlight {
        background: #2d3f5a;
        color: #f7fbff;
        text-style: bold;
    }
    #help {
        color: #a8b4c6;
        height: 2;
    }
    #toast {
        color: #f0d27a;
        height: 1;
        margin: 0 1;
        background: #111a28;
        border: round #6d5a33;
        padding: 0 1;
    }
    """

    game: reactive[Game] = reactive(Game)
    STAT_INFO = {
        "str": "STR: melee damage and power.",
        "dex": "DEX: precision, speed, and initiative.",
        "con": "CON: toughness and max HP scaling.",
        "int": "INT: arcane aptitude and tactics.",
        "wis": "WIS: insight, focus, and support power.",
        "cha": "CHA: presence and social force.",
    }
    TUTORIAL_STEPS = [
        "Select Venture Deeper to start the lesson fight.",
        "Use Attack, pick a style, then pick an enemy target.",
        "Use Skills on a target, or Defend if needed.",
        "Open Bag or Equip Gear to learn utility controls.",
        "Open Path and then Close Map.",
        "Use Look Around, then Open Chest.",
        "Finish tutorial and begin your real adventure.",
    ]

    def __init__(
        self,
        game: Game | None = None,
        save_path: Path | None = None,
        creation_enabled: bool = False,
        run_mode: str = "normal",
        seed: int = 7,
        online_client: Any | None = None,
        tutorial_mode: bool = False,
    ) -> None:
        super().__init__()
        self.seed = seed
        self.game = game if game is not None else Game(seed=seed, run_mode=run_mode)
        self.save_path = save_path
        self.online_client = online_client
        self.online_mode = online_client is not None
        self.online_snapshot: dict = {}
        self.online_notes: list[str] = []
        self._display_action_map: dict[str, str] = {}
        self.roll_animating = False
        self.roll_frames: list[str] = []
        self.roll_frame_delays: list[float] = []
        self.roll_frame_index = 0
        self.pending_action_label: str | None = None
        self.roll_timer: Any | None = None
        self.sound_enabled = True
        self.text_wrap_enabled = True
        self.render_mode = "hybrid_ascii"
        self.zoom_level = 100
        self.toast_message = ""
        self.toast_timer: Any | None = None
        self.event_timer: Any | None = None
        self.event_flash_message = ""
        self._local_log_snapshot = [str(entry) for entry in self.game.log[-12:]]
        self._online_log_snapshot: list[str] = []
        self.tutorial_mode = tutorial_mode and not self.online_mode
        self.tutorial_step_index = 0
        self.tutorial_map_opened = False
        self.tutorial_result = "quit"
        self.roster_cache = load_roster() if creation_enabled and not self.online_mode else []
        self.creation_mode = creation_enabled and not self.online_mode and not self.tutorial_mode
        self.creator_stage = "roster" if self.creation_mode and self.roster_cache else "name"
        self.creator_name = random_name(seed)
        self.creator_archetype = "Fighter"
        self.creator_stats = recommended_stats(self.creator_archetype)
        self.creator_selected_stat = "str"
        self.creator_log: list[str] = [
            "GM> Welcome, traveler. I will guide your character creation.",
            "GM> Begin by choosing a name for your hero." if self.creator_stage == "name" else "GM> Choose a saved hero or create a new one.",
        ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="status")
        with Horizontal(id="content"):
            with Vertical(classes="panel", id="party_panel"):
                yield Label("Party Ledger", id="party_title")
                yield Static("", id="party_text")
            with Vertical(classes="panel", id="battle_panel"):
                yield Label("Battle Screen", id="battle_title")
                yield Static("", id="battle_text")
            with Vertical(classes="panel", id="log_panel"):
                yield Label("Adventure Chronicle", id="log_title")
                yield Static("", id="log_text")
            with Vertical(classes="panel", id="actions_panel"):
                yield Label("Actions", id="actions_title")
                yield ListView(id="actions_list")
                yield Static("", id="help")
        yield Static("", id="toast")
        yield Footer()

    def on_mount(self) -> None:
        self._apply_zoom_layout()
        if self.online_mode:
            self.set_interval(0.1, self._poll_online_events)
        self._refresh_all()

    def on_unmount(self) -> None:
        if self.toast_timer:
            self.toast_timer.stop()
        if self.event_timer:
            self.event_timer.stop()
        if self.online_client:
            self.online_client.close()

    def _show_toast(self, text: str, seconds: float = 1.8) -> None:
        self.toast_message = text
        self.query_one("#toast", Static).update(text)
        if self.toast_timer:
            self.toast_timer.stop()
        self.toast_timer = self.set_timer(seconds, self._clear_toast)

    def _clear_toast(self) -> None:
        self.toast_message = ""
        self.query_one("#toast", Static).update("")

    def _clear_event_flash(self) -> None:
        self.event_flash_message = ""

    def _apply_zoom_layout(self) -> None:
        party_panel = self.query_one("#party_panel", Vertical)
        battle_panel = self.query_one("#battle_panel", Vertical)
        log_panel = self.query_one("#log_panel", Vertical)
        actions_panel = self.query_one("#actions_panel", Vertical)
        if self.zoom_level == 80:
            party_panel.styles.width = "1.2fr"
            battle_panel.styles.width = "2.2fr"
            log_panel.styles.width = "2.3fr"
            actions_panel.styles.width = "1.1fr"
        elif self.zoom_level == 120:
            party_panel.styles.width = "1.5fr"
            battle_panel.styles.width = "1.9fr"
            log_panel.styles.width = "2.0fr"
            actions_panel.styles.width = "1.2fr"
        else:
            party_panel.styles.width = "1.35fr"
            battle_panel.styles.width = "2.05fr"
            log_panel.styles.width = "2.2fr"
            actions_panel.styles.width = "1.15fr"

    def _highlight_active_panel(self) -> None:
        party_panel = self.query_one("#party_panel", Vertical)
        battle_panel = self.query_one("#battle_panel", Vertical)
        log_panel = self.query_one("#log_panel", Vertical)
        actions_panel = self.query_one("#actions_panel", Vertical)
        for panel in [party_panel, battle_panel, log_panel, actions_panel]:
            panel.remove_class("active_panel")
        if self.creation_mode:
            battle_panel.add_class("active_panel")
            return
        if self.game.mode == "combat" or self.game.menu in {"map", "attack_style", "skill_list", "target_enemy", "target_ally"}:
            battle_panel.add_class("active_panel")
            actions_panel.add_class("active_panel")
        elif self.game.menu in {"store", "items", "equip-member", "equip-item"}:
            actions_panel.add_class("active_panel")
            party_panel.add_class("active_panel")
        else:
            log_panel.add_class("active_panel")

    def _apply_wrap_mode(self) -> None:
        wrap_value = "wrap" if self.text_wrap_enabled else "nowrap"
        self.query_one("#party_text", Static).styles.text_wrap = wrap_value
        self.query_one("#battle_text", Static).styles.text_wrap = wrap_value
        self.query_one("#log_text", Static).styles.text_wrap = wrap_value

    def action_restart(self) -> None:
        if self.online_mode:
            self._append_online_note("Restart is host-controlled in online mode.")
            self._refresh_all()
            return
        if self.creation_mode:
            self._reset_creator()
            self._refresh_all()
            return
        self.game = Game(seed=7, run_mode=self.game.run_mode)
        self._save_silent()
        self._refresh_all()

    def action_confirm_action(self) -> None:
        if self.roll_animating:
            return
        if self.online_mode:
            action_label = self._selected_action_label()
            if not action_label or action_label == "Waiting for host...":
                return
            sent = self.online_client.send_action(action_label) if self.online_client else False
            if not sent:
                self._append_online_note("Could not send action. Not connected.")
                self._refresh_all()
            return
        if self.creation_mode:
            self._confirm_creator_action()
            self._refresh_all()
            return
        action_label = self._selected_action_label()
        if not action_label:
            return
        if self.tutorial_mode:
            if action_label == "Skip Tutorial":
                self._finish_tutorial("skipped")
                return
            if action_label == "Finish Tutorial":
                if self.tutorial_step_index >= len(self.TUTORIAL_STEPS) - 1:
                    self._finish_tutorial("completed")
                else:
                    self._show_toast("Complete all tutorial steps first.")
                return
            if not self._tutorial_action_allowed(action_label):
                self.game.log.append(f"Tutorial hint: {self._tutorial_step_text()}")
                self.game.log = self.game.log[-12:]
                self._show_toast("Follow the tutorial step on screen.")
                self._refresh_all()
                return
        if action_label in {"Restart with R", "Quit with Q", "Waiting for enemy turn..."}:
            return
        if self._should_animate_roll(action_label):
            self._start_roll_animation(action_label)
            return
        self._execute_game_action(action_label)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.action_confirm_action()

    def action_save(self) -> None:
        if self.online_mode:
            self._append_online_note("Save is handled by the host.")
            self._refresh_all()
            return
        if self.creation_mode:
            self._append_creator_log("Save is unavailable during character creation.")
            self._refresh_all()
            return
        if self.game.run_mode == "ironman":
            self.game.log.append("Ironman: manual save is disabled.")
            self.game.log = self.game.log[-12:]
            self._refresh_all()
            return
        if not self.save_path:
            self.game.log.append("No save path configured.")
            self._refresh_all()
            return
        save_game(self.game, self.save_path)
        self.game.log.append(f"Saved to {self.save_path.name}.")
        self.game.log = self.game.log[-12:]
        self._refresh_all()

    def action_tip(self) -> None:
        if self.online_mode:
            self._append_online_note("Tip: coordinate actions with your party in chat/voice.")
            self._refresh_all()
            return
        if self.creation_mode:
            self._append_creator_log("Tip: Spend points on your archetype's primary stat first.")
            self._refresh_all()
            return
        self.game.log.append(self.game.next_tip())
        self.game.log = self.game.log[-12:]
        self._refresh_all()

    def action_cycle_zoom(self) -> None:
        order = [80, 100, 120]
        current_index = order.index(self.zoom_level) if self.zoom_level in order else 1
        self.zoom_level = order[(current_index + 1) % len(order)]
        self._apply_zoom_layout()
        self._show_toast(f"Zoom set to {self.zoom_level}%")
        self._refresh_all()

    def action_toggle_wrap(self) -> None:
        self.text_wrap_enabled = not self.text_wrap_enabled
        self._show_toast(f"Wrap {'ON' if self.text_wrap_enabled else 'OFF'}")
        self._refresh_all()

    def action_toggle_render(self) -> None:
        self.render_mode = "text_only" if self.render_mode == "hybrid_ascii" else "hybrid_ascii"
        self._show_toast(f"Render mode: {self.render_mode}")
        self._refresh_all()

    def action_toggle_sound(self) -> None:
        self.sound_enabled = not self.sound_enabled
        self._show_toast(f"Sound {'ON' if self.sound_enabled else 'OFF'}")
        self._refresh_all()

    def action_react_cheer(self) -> None:
        if not self.online_mode or not self.online_client:
            return
        if self.online_client.send_reaction("🔥", "party"):
            self._show_toast("Reaction sent: 🔥")
        else:
            self._show_toast("Reaction failed.")

    def on_key(self, event: Key) -> None:
        shortcut_number = self._shortcut_number_from_key(event.key)
        if shortcut_number is not None:
            self._activate_numbered_action(shortcut_number)
            return

        if self.creation_mode:
            if self.creator_stage == "name":
                if event.key == "backspace":
                    self.creator_name = self.creator_name[:-1]
                    self._refresh_all()
                    return
                if event.key == "space":
                    char = " "
                elif len(event.key) == 1:
                    char = event.key
                else:
                    return
                if len(self.creator_name) >= 16:
                    return
                if char.isalpha() or char in {" ", "-"}:
                    self.creator_name += char
                    self._refresh_all()
            return

        if self.online_mode:
            if event.key == "q":
                self.action_quit()
            return

        if self.roll_animating:
            return

        if event.key == "r":
            self.action_restart()
            return
        if event.key == "s":
            self.action_save()
            return
        if event.key == "t":
            self.action_tip()
            return
        if event.key == "q":
            self.action_quit()

    def _refresh_all(self) -> None:
        if self.online_mode:
            self._refresh_online_view()
            return
        if self.creation_mode:
            self._refresh_creator_view()
            return
        self._capture_local_log_updates()
        self._update_panel_visibility()
        self._highlight_active_panel()
        self._apply_wrap_mode()
        status = self.game.status_summary()
        if self.tutorial_mode:
            status = f"Tutorial Step {self.tutorial_step_index + 1}/{len(self.TUTORIAL_STEPS)} | {status}"
        self.query_one("#status", Static).update(status)
        self.query_one("#party_text", Static).update(self._render_party())
        battle_title = "Mini Map Overlay" if self.game.menu == "map" else "Battle Screen"
        self.query_one("#battle_title", Label).update(battle_title)
        self.query_one("#log_text", Static).update(self._render_log())
        self.query_one("#help", Static).update(self._help_text())
        self._render_actions()
        self._update_battle_panel_content()
        self.query_one("#toast", Static).update(self.toast_message)

    def _refresh_online_view(self) -> None:
        self._capture_online_log_updates()
        self._update_panel_visibility()
        self._highlight_active_panel()
        self._apply_wrap_mode()
        status = str(self.online_snapshot.get("status", "Connecting to host..."))
        self.query_one("#status", Static).update(status)
        self.query_one("#party_text", Static).update(self._render_online_party())
        battle_title = "Mini Map Overlay" if self.online_snapshot.get("menu") == "map" else "Battle Screen"
        self.query_one("#battle_title", Label).update(battle_title)
        self.query_one("#log_text", Static).update(self._render_online_log())
        self.query_one("#help", Static).update(self._help_text())
        self._render_actions()
        self._update_battle_panel_content()
        self.query_one("#toast", Static).update(self.toast_message)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if self.creation_mode or self.roll_animating:
            return
        self._update_battle_panel_content()

    def _refresh_creator_view(self) -> None:
        self._update_panel_visibility()
        self._highlight_active_panel()
        self._apply_wrap_mode()
        self.query_one("#status", Static).update("Character Creation | DND New Run")
        self.query_one("#battle_title", Label).update("Character Creator")
        self.query_one("#party_text", Static).update(self._render_creator_party())
        self.query_one("#battle_text", Static).update(self._render_creator_center())
        self.query_one("#log_text", Static).update("\n".join(f"• {entry}" for entry in self.creator_log[-12:]))
        self.query_one("#help", Static).update(self._help_text())
        self._render_actions()
        self.query_one("#toast", Static).update(self.toast_message)

    def _render_party(self) -> str:
        lines: list[str] = []
        if self.render_mode == "hybrid_ascii":
            lines.extend(
                [
                    "  /\\        ____",
                    " /  \\  _   / __ \\",
                    "/_/\\_\\(_) /_/  \\_\\",
                    "",
                ]
            )
        lines.append(f"Mode: {self.game.run_mode}")
        lines.append(f"Area: {self.game.current_room_name()}")
        lines.append(self.game.depth_text())
        lines.append(f"Mood: {self.game.room_mood_text()}")
        lines.append(f"Gold: {self.game.gold}")
        lines.append("")
        for unit in self.game.party:
            state = "DOWN" if not unit.alive else "OK"
            defend = " [DEF]" if unit.defending else ""
            hp_text = self._hp_notation(unit.hp, unit.max_hp)
            mp_text = self._mp_notation(unit.mana, unit.max_mana)
            lines.append(
                f"{self._health_icon(unit)} {self._short_name(unit.name):10} "
                f"{unit.archetype:7} L{unit.level} {hp_text} {mp_text} "
                f"{self._xp_gauge(unit)} {state}{defend}"
            )
        if self.game.mode == "combat":
            lines.append("")
            lines.append("Enemies:")
            for enemy in self.game.enemies:
                state = "[red][DED][/]" if not enemy.alive else "[green][ALV][/]"
                lines.append(
                    f"{self._health_icon(enemy)} {self._short_name(enemy.name):10} "
                    f"{self._hp_notation(enemy.hp, enemy.max_hp)} {state}"
                )
        return "\n".join(lines)

    def _render_log(self) -> str:
        if self.render_mode == "text_only":
            return "\n".join(str(entry) for entry in self.game.log[-12:])
        lines = ["[bold #8eb5ff]~ Adventure Feed ~[/]"]
        if self.tutorial_mode:
            lines.append(f"[bold #f6d07a]Tutorial:[/] {self._tutorial_step_text()}")
            lines.append("")
        if self.event_flash_message:
            lines.append(f"[bold #ffd27f]>> JUST NOW <<[/] {self._style_log_text(self.event_flash_message)}")
            lines.append("")
        for entry in self.game.log[-12:]:
            bullet = self._entry_bullet(str(entry))
            lines.append(f"{bullet} {self._style_log_text(str(entry))}")
        return "\n".join(lines)

    def _render_online_party(self) -> str:
        if not self.online_snapshot:
            return "Connecting..."
        lines = [
            *(
                [
                    "  /\\        ____",
                    " /  \\  _   / __ \\",
                    "/_/\\_\\(_) /_/  \\_\\",
                    "",
                ]
                if self.render_mode == "hybrid_ascii"
                else []
            ),
            f"Area: {self.online_snapshot.get('room', 'Unknown')}",
            str(self.online_snapshot.get("depth", "Depth: ?")),
            f"Mood: {self.online_snapshot.get('mood', 'Unknown')}",
            "",
        ]
        for unit in self.online_snapshot.get("party", []):
            hp = int(unit.get("hp", 0))
            max_hp = int(unit.get("max_hp", 1))
            mana = int(unit.get("mana", 0))
            max_mana = int(unit.get("max_mana", 0))
            health_icon = self._health_icon_from_values(hp, max_hp)
            active = " [TURN]" if unit.get("is_active") else ""
            controller = unit.get("controller_name") or "AI/Open"
            lines.append(
                f"{health_icon} {str(unit.get('name', 'Unknown')):10} "
                f"{self._hp_notation(hp, max_hp)} {self._mp_notation(mana, max_mana)} "
                f"[{controller}]{active}"
            )
        return "\n".join(lines)

    def _render_online_battle(self) -> str:
        if not self.online_snapshot:
            return "Connecting to host..."
        if self.online_snapshot.get("menu") == "map":
            return str(self.online_snapshot.get("map_text", "Map unavailable."))
        lines = [
            "BATTLE SCREEN",
            *(
                [
                    " .-^-.",
                    "/_o o_\\  < encounter feed >",
                    "  /_\\",
                    "",
                ]
                if self.render_mode == "hybrid_ascii"
                else []
            ),
            f"Room: {self.online_snapshot.get('room', 'Unknown')}",
            f"Round: {self.online_snapshot.get('round', 1)}",
            f"Active: {self.online_snapshot.get('active_name', 'Unknown')}",
            f"Last Roll: {self.online_snapshot.get('last_roll', 'No roll yet.')}",
            f"Menu: {self.online_snapshot.get('menu_context', 'Combat > Action')}",
            "",
            "Enemy Status:",
        ]
        pending_text = str(self.online_snapshot.get("pending_text", "")).strip()
        if pending_text:
            lines.insert(5, pending_text)
        enemies = self.online_snapshot.get("enemies", [])
        if not enemies:
            lines.append("No enemies in sight.")
        else:
            for enemy in enemies:
                hp = int(enemy.get("hp", 0))
                max_hp = int(enemy.get("max_hp", 1))
                status = "[green][ALV][/]" if enemy.get("alive") else "[red][DED][/]"
                lines.append(
                    f"{self._health_icon_from_values(hp, max_hp)} "
                    f"{str(enemy.get('name', 'Enemy')):12} {self._hp_notation(hp, max_hp)} {status}"
                )
        return "\n".join(lines)

    def _update_battle_panel_content(self) -> None:
        if self.roll_animating:
            return
        if self.creation_mode:
            return
        if self.online_mode:
            base = self._render_online_battle()
            tooltip = self._tooltip_for_online_selection()
        else:
            base = self.game.battle_screen_text()
            tooltip = self._tooltip_for_local_selection()
        if self.render_mode == "hybrid_ascii" and not self.online_mode:
            base = (
                " .-< BATTLE VIEW >-.\n"
                " |  steel and spell |\n"
                " '------------------'\n\n"
                f"{base}"
            )
        if self.render_mode == "text_only":
            filtered_prefixes = (".-< BATTLE VIEW >-.", "|  steel and spell |", "'------------------'", ".-^-.", "/_o o_\\")
            base_lines = [
                line
                for line in base.splitlines()
                if "< encounter feed >" not in line and not any(line.strip().startswith(prefix) for prefix in filtered_prefixes)
            ]
            base = "\n".join(base_lines)
        tutorial_line = f"Tutorial: {self._tutorial_step_text()}" if self.tutorial_mode else ""
        blocks = [base]
        if tooltip:
            blocks.append(f"Skill Tip: {tooltip}")
        if tutorial_line:
            blocks.append(tutorial_line)
        self.query_one("#battle_text", Static).update("\n\n".join(blocks))

    def _tooltip_for_local_selection(self) -> str:
        if self.game.mode != "combat":
            selected = self._selected_action_label() or ""
            if selected == "Look Around":
                return "Search for hidden chest (DC 13, INT-based)."
            return ""
        selected = self._selected_action_label() or ""
        if self.game.menu == "attack_style" and selected.startswith("Style: "):
            style = selected.replace("Style: ", "", 1)
            style_data = self.game.ATTACK_STYLES.get(style)
            if style_data:
                return (
                    f"{style} | Hit {style_data['hit_bonus']:+.0f} | "
                    f"Damage x{style_data['damage_mult']:.2f}"
                )
        if self.game.menu == "skill_list" and selected.startswith("Skill: "):
            skill_id = self.game._skill_id_from_action_label(selected)
            if skill_id:
                skill = self.game.SKILL_DEFS.get(skill_id, {})
                target = str(skill.get("target", "enemy")).title()
                cost = int(skill.get("cost", 0))
                if skill.get("heal_min"):
                    return f"{skill.get('name', skill_id)} | Cost {cost} MP | Target {target} | Heal {skill['heal_min']}-{skill['heal_max']}"
                if skill.get("aoe"):
                    return f"{skill.get('name', skill_id)} | Cost {cost} MP | Target All Enemies | Damage {skill['damage_min']}-{skill['damage_max']}"
                hit = int(skill.get("hit_bonus", 0))
                damage = int(skill.get("damage_bonus", 0))
                return f"{skill.get('name', skill_id)} | Cost {cost} MP | Target {target} | Hit {hit:+d} | Damage {damage:+d}"
        if self.game.menu in {"target_enemy", "target_ally"}:
            if self.game.pending_action_type == "attack" and self.game.pending_style:
                return f"Select target for {self.game.pending_style} Attack"
            if self.game.pending_action_type == "skill" and self.game.pending_skill_id:
                skill_name = self.game.SKILL_DEFS.get(self.game.pending_skill_id, {}).get("name", self.game.pending_skill_id)
                return f"Select target for {skill_name}"
        return ""

    def _tooltip_for_online_selection(self) -> str:
        selected = self._selected_action_label() or ""
        if selected == "Look Around":
            return "Search for hidden chest (DC 13, INT-based)."
        if selected.startswith("Style: "):
            style = selected.replace("Style: ", "", 1)
            style_data = self.game.ATTACK_STYLES.get(style)
            if style_data:
                return f"{style} | Hit {style_data['hit_bonus']:+.0f} | Damage x{style_data['damage_mult']:.2f}"
        if selected.startswith("Skill: "):
            skill_id = self.game._skill_id_from_action_label(selected)
            if skill_id:
                skill = self.game.SKILL_DEFS.get(skill_id, {})
                target = str(skill.get("target", "enemy")).title()
                cost = int(skill.get("cost", 0))
                return f"{skill.get('name', skill_id)} | Cost {cost} MP | Target {target}"
        if selected.startswith("Target"):
            pending = str(self.online_snapshot.get("pending_text", "")).strip()
            return pending or "Choose a target to resolve the action."
        return ""

    def _render_online_log(self) -> str:
        entries = [str(item) for item in self.online_snapshot.get("log", [])]
        entries.extend(self.online_notes[-4:])
        if not entries:
            entries = ["Connecting to host..."]
        if self.render_mode == "text_only":
            return "\n".join(entries[-12:])
        lines = ["[bold #8eb5ff]~ Party Channel ~[/]"]
        if self.event_flash_message:
            lines.append(f"[bold #ffd27f]>> JUST NOW <<[/] {self._style_log_text(self.event_flash_message)}")
            lines.append("")
        for entry in entries[-12:]:
            bullet = self._entry_bullet(entry)
            lines.append(f"{bullet} {self._style_log_text(entry)}")
        return "\n".join(lines)

    def _render_creator_party(self) -> str:
        if self.creator_stage == "roster":
            lines = ["Saved Heroes:"]
            if not self.roster_cache:
                lines.append("- No saved heroes yet.")
            else:
                for hero in self.roster_cache[:8]:
                    lines.append(
                        f"- {hero.get('name', 'Unknown')} "
                        f"({hero.get('archetype', 'Adventurer')}) "
                        f"Lv{hero.get('level', 1)} "
                        f"[{hero.get('character_id', 'no-id')}]"
                    )
            lines.append("")
            lines.append("Pick a saved hero or create a new one.")
            return "\n".join(lines)
        final_stats = apply_archetype_bonus(self.creator_stats, self.creator_archetype)
        preview = preview_derived_stats(self.creator_archetype, self.creator_stats)
        lines = [
            f"Name: {self.creator_name or '<type name>'}",
            f"Archetype: {self.creator_archetype}",
            f"Point Buy: {point_buy_cost(self.creator_stats)}/27",
            f"Remaining: {remaining_points(self.creator_stats)}",
            f"Preview: HP {preview['hp']} | ATK +{preview['attack_bonus']} | DMG {preview['damage_min']}-{preview['damage_max']}",
            f"Selected: {self.creator_selected_stat.upper()}",
            "",
            "Stats (base -> final):",
        ]
        for stat in STAT_KEYS:
            marker = ">" if stat == self.creator_selected_stat else " "
            current = self.creator_stats[stat]
            increase_cost = self._point_delta(stat, current, current + 1) if current < 15 else None
            decrease_refund = self._point_delta(stat, current, current - 1) if current > 8 else None
            up_text = f"+{increase_cost}" if increase_cost is not None else "MAX"
            down_text = f"-{decrease_refund}" if decrease_refund is not None else "MIN"
            lines.append(
                f"{marker} {stat.upper():3}: {current} -> {final_stats[stat]} "
                f"(inc:{up_text} dec:{down_text})"
            )
        lines.append("")
        lines.append("Companions preview:")
        for companion in build_companions(self.creator_archetype, seed=self.seed):
            lines.append(f"- {companion.name} ({companion.archetype})")
        return "\n".join(lines)

    def _render_creator_center(self) -> str:
        if self.creator_stage == "roster":
            return (
                "Step 0/4: Hero Roster\n"
                "Continue with a saved hero, or\n"
                "choose Create New Hero to open\n"
                "full character creation."
            )
        if self.creator_stage == "name":
            return (
                "Step 1/4: Name\n"
                "Type letters/space/hyphen.\n"
                "Length: 2-16 chars.\n"
                "Pick Continue when valid."
            )
        if self.creator_stage == "archetype":
            return (
                "Step 2/4: Archetype\n"
                "Choose your class identity.\n"
                "This affects stat bonuses,\n"
                "damage profile, and role."
            )
        if self.creator_stage == "stats":
            return (
                "Step 3/4: Stats (Point-Buy 27)\n"
                "Use actions: Pick Stat -> Increase/Decrease.\n"
                "Valid base range: 8 to 15 (before bonuses).\n"
                "Costs: 8:0 9:1 10:2 11:3 12:4 13:5 14:7 15:9.\n"
                f"{self.STAT_INFO[self.creator_selected_stat]}\n"
                f"Remaining points: {remaining_points(self.creator_stats)}"
            )
        return (
            "Step 4/4: Review\n"
            f"Name: {self.creator_name}\n"
            f"Archetype: {self.creator_archetype}\n"
            f"Point-Buy used: {point_buy_cost(self.creator_stats)}/27\n"
            "Confirm to begin the run."
        )

    def _render_actions(self) -> None:
        actions_list = self.query_one("#actions_list", ListView)
        actions_list.clear()
        if self.online_mode:
            raw_labels = [str(label) for label in self.online_snapshot.get("actions", [])]
        else:
            raw_labels = self._creator_action_labels() if self.creation_mode else self.game.action_labels()
        if self.tutorial_mode and not self.creation_mode:
            if self.tutorial_step_index >= len(self.TUTORIAL_STEPS) - 1:
                raw_labels = [*raw_labels, "Finish Tutorial", "Skip Tutorial"]
            else:
                raw_labels = [*raw_labels, "Skip Tutorial"]
        if not raw_labels:
            raw_labels = ["Waiting for host..." if self.online_mode else "Waiting for enemy turn..."]
        self._display_action_map = {}
        for index, raw_label in enumerate(raw_labels, start=1):
            display_label = self._format_action_label(raw_label)
            numbered = f"{index}. {display_label}" if index <= 9 else display_label
            self._display_action_map[numbered] = raw_label
            actions_list.append(ListItem(Label(numbered)))
        if actions_list.children:
            actions_list.index = 0

    def _format_action_label(self, raw_label: str) -> str:
        if raw_label == "Skills" and self.game.mode == "combat":
            actor = self.game.active_unit()
            if actor and actor in self.game.party:
                return f"Skills ({actor.mana}/{actor.max_mana} MP)"
        if raw_label.startswith("Skill: ") and "(" not in raw_label:
            skill_id = self.game._skill_id_from_action_label(raw_label)
            if skill_id:
                skill = self.game.SKILL_DEFS.get(skill_id, {})
                cost = int(skill.get("cost", 0))
                name = str(skill.get("name", raw_label.replace("Skill: ", "", 1)))
                return f"Skill: {name} ({cost} MP)"
        return raw_label

    def _update_panel_visibility(self) -> None:
        party_panel = self.query_one("#party_panel", Vertical)
        battle_panel = self.query_one("#battle_panel", Vertical)
        log_panel = self.query_one("#log_panel", Vertical)
        if self.creation_mode:
            party_panel.styles.display = "block"
            battle_panel.styles.display = "block"
            log_panel.styles.display = "none"
            return
        if self.online_mode:
            mode = str(self.online_snapshot.get("mode", "explore"))
            menu = str(self.online_snapshot.get("menu", "root"))
            party_panel.styles.display = "block"
            log_panel.styles.display = "block"
            battle_panel.styles.display = "block" if mode == "combat" or menu == "map" else "none"
            return
        if self.game.mode == "combat" or self.game.menu == "map":
            party_panel.styles.display = "block"
            battle_panel.styles.display = "block"
            log_panel.styles.display = "block"
        else:
            party_panel.styles.display = "block"
            battle_panel.styles.display = "none"
            log_panel.styles.display = "block"

    def _help_text(self) -> str:
        if self.roll_animating:
            return "[Rolling d20...]"
        if self.online_mode:
            context = str(self.online_snapshot.get("menu_context", "Online"))
            return f"{context} | [1-9] or click [Enter] confirm [Esc] quit | Mode:{self.render_mode}"
        if self.creation_mode:
            if self.creator_stage == "name":
                return "[Type name] [1-9] select [Enter] confirm [Esc] quit"
            return "[1-9] select [Enter] confirm [Esc] quit"
        if self.tutorial_mode:
            return "[Tutorial] [1-9] select [Enter] confirm | Skip Tutorial available"
        if self.game.mode == "victory":
            return "Victory reached. Choose [1] Begin Next Adventure, then press [Enter]."
        if self.game.mode == "defeat":
            return "Defeat screen: choose [1] Restart with R or [2] Quit with Q."
        return f"{self.game.menu_context_text()} | [1-9] or click [R/S/T/Q] [Enter] confirm | Mode:{self.render_mode}"

    def _creator_action_labels(self) -> list[str]:
        if self.creator_stage == "roster":
            labels = [f"Use Hero: {hero.get('name', 'Unknown')} [{hero.get('character_id', '')}]" for hero in self.roster_cache[:8]]
            return labels + ["Create New Hero"]
        if self.creator_stage == "name":
            return ["Continue", "Random Name", "Clear Name"]
        if self.creator_stage == "archetype":
            return list(ARCHETYPES.keys()) + ["Back"]
        if self.creator_stage == "stats":
            stat_selectors = [f"Pick {stat.upper()}" for stat in STAT_KEYS]
            return [
                *stat_selectors,
                "Increase Selected",
                "Decrease Selected",
                "Continue",
                "Back",
            ]
        return ["Confirm Character", "Back"]

    def _confirm_creator_action(self) -> None:
        action_label = self._selected_action_label()
        if not action_label:
            return
        if self.creator_stage == "roster":
            self._handle_roster_stage(action_label)
            return
        if self.creator_stage == "name":
            self._handle_name_stage(action_label)
            return
        if self.creator_stage == "archetype":
            self._handle_archetype_stage(action_label)
            return
        if self.creator_stage == "stats":
            self._handle_stats_stage(action_label)
            return
        self._handle_review_stage(action_label)

    def _handle_name_stage(self, action_label: str) -> None:
        if action_label == "Random Name":
            self.creator_name = random_name(self.seed + len(self.creator_name))
            self._append_creator_log(f"GM> Fate suggests the name '{self.creator_name}'.")
            return
        if action_label == "Clear Name":
            self.creator_name = ""
            self._append_creator_log("GM> Name cleared. Enter the one you want remembered.")
            return
        if not validate_name(self.creator_name):
            self._append_creator_log("Name must be 2-16 chars (letters, space, hyphen).")
            return
        self.creator_stage = "archetype"
        self._append_creator_log("GM> Good. Now choose your archetype.")

    def _handle_roster_stage(self, action_label: str) -> None:
        if action_label == "Create New Hero":
            self.creator_stage = "name"
            self._append_creator_log("GM> Let us forge a new hero.")
            return
        if not action_label.startswith("Use Hero: "):
            return
        hero_id = ""
        if "[" in action_label and action_label.endswith("]"):
            hero_id = action_label.rsplit("[", 1)[1][:-1]
        chosen = None
        for entry in self.roster_cache:
            if str(entry.get("character_id", "")) == hero_id:
                chosen = entry
                break
        if not chosen:
            self._append_creator_log("GM> Could not load that saved hero.")
            return
        main_character = self._unit_from_roster_entry(chosen)
        companions = build_companions(main_character.archetype, seed=self.seed)
        self.game = Game(seed=self.seed, run_mode=self.game.run_mode, party=[main_character] + companions)
        self.creation_mode = False
        self.game.log.append(f"Loaded hero: {main_character.name} ({main_character.archetype}).")
        self.game.log = self.game.log[-12:]
        self._save_silent()

    def _handle_archetype_stage(self, action_label: str) -> None:
        if action_label == "Back":
            self.creator_stage = "name"
            self._append_creator_log("GM> We can reconsider the name.")
            return
        if action_label not in ARCHETYPES:
            return
        self.creator_archetype = action_label
        self.creator_stats = recommended_stats(self.creator_archetype)
        self.creator_selected_stat = "str"
        self.creator_stage = "stats"
        self._append_creator_log(
            f"GM> {self.creator_archetype} chosen. Shape your stats with point-buy."
        )

    def _handle_stats_stage(self, action_label: str) -> None:
        if action_label == "Back":
            self.creator_stage = "archetype"
            self._append_creator_log("GM> Return to archetype selection.")
            return
        if action_label == "Continue":
            if remaining_points(self.creator_stats) < 0:
                self._append_creator_log("Point-buy exceeds 27.")
                return
            self.creator_stage = "review"
            self._append_creator_log("GM> Your build is ready. Review and confirm.")
            return
        if action_label.startswith("Pick "):
            self.creator_selected_stat = action_label.split(" ", 1)[1].lower()
            self._append_creator_log(
                f"GM> Focus shifted to {self.creator_selected_stat.upper()}."
            )
            return
        value = self.creator_stats[self.creator_selected_stat]
        if action_label == "Increase Selected" and value < 15:
            self.creator_stats[self.creator_selected_stat] = value + 1
            if remaining_points(self.creator_stats) < 0:
                self.creator_stats[self.creator_selected_stat] = value
                self._append_creator_log("Not enough points for that increase.")
            return
        if action_label == "Increase Selected" and value >= 15:
            self._append_creator_log("That stat is already at max base value (15).")
            return
        if action_label == "Decrease Selected" and value > 8:
            self.creator_stats[self.creator_selected_stat] = value - 1
            return
        if action_label == "Decrease Selected" and value <= 8:
            self._append_creator_log("That stat is already at minimum base value (8).")

    def _handle_review_stage(self, action_label: str) -> None:
        if action_label == "Back":
            self.creator_stage = "stats"
            self._append_creator_log("GM> One last chance to tune your stats.")
            return
        if action_label != "Confirm Character":
            return
        if not validate_name(self.creator_name):
            self._append_creator_log("Name is invalid.")
            return
        main_character = build_main_character(self.creator_name, self.creator_archetype, self.creator_stats)
        companions = build_companions(self.creator_archetype, seed=self.seed)
        upsert_roster_hero(main_character)
        self.roster_cache = load_roster()
        self.game = Game(seed=self.seed, run_mode=self.game.run_mode, party=[main_character] + companions)
        self.creation_mode = False
        self.game.log.append("GM> Your journey begins. Trust your choices.")
        self.game.log.append(f"Hero created: {main_character.name} the {main_character.archetype}.")
        self.game.log = self.game.log[-12:]
        self._save_silent()

    def _append_creator_log(self, text: str) -> None:
        self.creator_log.append(text)
        self.creator_log = self.creator_log[-12:]

    def _reset_creator(self) -> None:
        self.roster_cache = load_roster()
        self.creator_stage = "roster" if self.roster_cache else "name"
        self.creator_name = random_name(self.seed)
        self.creator_archetype = "Fighter"
        self.creator_stats = recommended_stats(self.creator_archetype)
        self.creator_selected_stat = "str"
        self.creator_log = ["Character Creator reset."]

    @staticmethod
    def _unit_from_roster_entry(row: dict) -> Unit:
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

    def _selected_action_label(self) -> str | None:
        actions_list = self.query_one("#actions_list", ListView)
        selected = actions_list.highlighted_child
        if not selected and actions_list.children:
            selected = actions_list.children[0]
        if not selected:
            return None
        display_label = str(selected.query_one(Label).renderable)
        mapped = self._display_action_map.get(display_label)
        if mapped:
            return mapped
        cleaned = re.sub(r"^\d+\.\s+", "", display_label)
        cleaned = re.sub(r"^\[[A-Z.]+\]\s+", "", cleaned)
        return cleaned.strip()

    def _activate_numbered_action(self, number: int) -> None:
        actions_list = self.query_one("#actions_list", ListView)
        if number < 1 or number > len(actions_list.children):
            return
        actions_list.index = number - 1
        self.action_confirm_action()

    @staticmethod
    def _shortcut_number_from_key(key: str) -> int | None:
        if key.isdigit():
            return int(key)
        key_map = {
            "kp_1": 1,
            "kp_2": 2,
            "kp_3": 3,
            "kp_4": 4,
            "kp_5": 5,
            "kp_6": 6,
            "kp_7": 7,
            "kp_8": 8,
            "kp_9": 9,
            "numpad1": 1,
            "numpad2": 2,
            "numpad3": 3,
            "numpad4": 4,
            "numpad5": 5,
            "numpad6": 6,
            "numpad7": 7,
            "numpad8": 8,
            "numpad9": 9,
        }
        return key_map.get(key)

    def _icon_for_action(self, raw_label: str) -> str:
        if raw_label.startswith("Attack"):
            return "[ATK]"
        if raw_label.startswith("Skills") or raw_label.startswith("Skill:"):
            return "[SKL]"
        if raw_label.startswith("Style:"):
            return "[STY]"
        if raw_label.startswith("Target"):
            return "[TGT]"
        if raw_label.startswith("Defend"):
            return "[DEF]"
        if raw_label.startswith("Venture"):
            return "[GO]"
        if raw_label.startswith("Begin Next Adventure"):
            return "[GO]"
        if raw_label.startswith("Look"):
            return "[LUK]"
        if raw_label.startswith("Explore Space"):
            return "[EXP]"
        if raw_label.startswith("Open Chest"):
            return "[CHT]"
        if raw_label.startswith("Path") or raw_label.startswith("Close Map"):
            return "[MAP]"
        if raw_label.startswith("Bag") or raw_label.startswith("Use "):
            return "[BAG]"
        if raw_label.startswith("Equip"):
            return "[EQP]"
        if raw_label.startswith("Rest"):
            return "[RST]"
        if raw_label.startswith("Continue") or raw_label.startswith("Confirm"):
            return "[OK]"
        if raw_label.startswith("Back"):
            return "[<-]"
        if raw_label.startswith("Random"):
            return "[RND]"
        if raw_label.startswith("Clear"):
            return "[CLR]"
        if raw_label.startswith("Select") or raw_label.startswith("Pick") or raw_label.startswith("Increase") or raw_label.startswith("Decrease"):
            return "[STA]"
        if raw_label.startswith("Restart"):
            return "[RST]"
        if raw_label.startswith("Quit"):
            return "[X]"
        if raw_label.startswith("Waiting"):
            return "[...]"
        return "[.]"

    def _poll_online_events(self) -> None:
        if not self.online_client:
            return
        changed = False
        for event in self.online_client.poll_events():
            event_type = event.get("type")
            if event_type == "snapshot":
                self.online_snapshot = event
                changed = True
            elif event_type == "join_ack":
                assigned = event.get("assigned_character_id")
                if assigned:
                    self._append_online_note(f"Connected. You control {assigned}.")
                else:
                    self._append_online_note("Connected as spectator.")
                changed = True
            elif event_type == "error":
                self._append_online_note(f"Server: {event.get('message', 'Error')}")
                changed = True
            elif event_type == "system":
                self._append_online_note(str(event.get("message", "System message")))
                changed = True
        if changed:
            self._refresh_all()

    def _should_animate_roll(self, action_label: str) -> bool:
        if self.creation_mode or self.online_mode or self.roll_animating:
            return False
        if action_label in {"Look Around", "Explore Space"}:
            return True
        return self.game.action_requires_roll(action_label)

    def _start_roll_animation(self, action_label: str) -> None:
        actor = self.game.active_unit()
        actor_name = self._short_name(actor.name) if actor else "Hero"
        self.roll_animating = True
        self.pending_action_label = action_label
        self.roll_frame_index = 0
        self.roll_frames = [
            f"{actor_name} rolls [ / ]  speed: fast",
            f"{actor_name} rolls [ - ]  speed: fast",
            f"{actor_name} rolls [ \\ ]  speed: fast",
            f"{actor_name} rolls [ | ]  speed: fast",
            f"{actor_name} rolls [ / ]  speed: fast",
            f"{actor_name} rolls [ - ]  speed: fast",
            f"{actor_name} rolls [ 16 ] speed: slowing",
            f"{actor_name} rolls [ 4 ]  speed: slowing",
            f"{actor_name} rolls [ 12 ] speed: slowing",
            f"{actor_name} rolls [ 9 ]  speed: slowing",
            "d20 lands [ ? ]  result pending",
            "d20 settled. Resolving action...",
        ]
        self.roll_frame_delays = [0.06, 0.06, 0.06, 0.06, 0.06, 0.06, 0.1, 0.11, 0.12, 0.13, 0.16, 0.16]
        self._show_toast("Rolling d20...")
        self._play_sfx("roll")
        self._render_roll_frame()
        if self.roll_timer:
            self.roll_timer.stop()
        self.roll_timer = self.set_timer(self.roll_frame_delays[0], self._on_roll_animation_tick)

    def _on_roll_animation_tick(self) -> None:
        if not self.roll_animating:
            if self.roll_timer:
                self.roll_timer.stop()
            return
        self.roll_frame_index += 1
        if self.roll_frame_index >= len(self.roll_frames):
            if self.roll_timer:
                self.roll_timer.stop()
                self.roll_timer = None
            pending = self.pending_action_label
            self.roll_animating = False
            self.pending_action_label = None
            self.roll_frames = []
            self.roll_frame_delays = []
            if pending:
                self._execute_game_action(pending)
            else:
                self._refresh_all()
            return
        self._render_roll_frame()
        if self.roll_timer:
            self.roll_timer.stop()
        delay = self.roll_frame_delays[min(self.roll_frame_index, len(self.roll_frame_delays) - 1)]
        self.roll_timer = self.set_timer(delay, self._on_roll_animation_tick)

    def _render_roll_frame(self) -> None:
        battle_title = "Mini Map Overlay" if self.game.menu == "map" else "Battle Screen"
        self.query_one("#battle_title", Label).update(battle_title)
        base = self.game.battle_screen_text()
        frame = self.roll_frames[self.roll_frame_index] if self.roll_frames else "Rolling..."
        self.query_one("#battle_text", Static).update(f"{base}\n\nDice Roll: {frame}")
        self.query_one("#help", Static).update(self._help_text())

    def _execute_game_action(self, action_label: str) -> None:
        before_menu = self.game.menu
        before_pending_action = self.game.pending_action_type
        before_log_len = len(self.game.log)
        before_mode = self.game.mode
        before_banner = self.game.result_banner
        before_drop = self.game.last_drop_debug
        before_levels = {unit.character_id or unit.name: unit.level for unit in self.game.party}
        self.game.perform_player_action(action_label)
        if self.game.mode == "combat" and self.game.action_consumed_turn and not self.game.game_over():
            self.game.run_enemy_turns_until_player()
        self._emit_action_toast(
            before_log_len=before_log_len,
            before_mode=before_mode,
            before_banner=before_banner,
            before_drop=before_drop,
            before_levels=before_levels,
        )
        if self.tutorial_mode:
            self._advance_tutorial_progress(
                action_label=action_label,
                before_menu=before_menu,
                before_pending_action=before_pending_action,
            )
        self._save_silent()
        self._refresh_all()

    def _emit_action_toast(
        self,
        *,
        before_log_len: int,
        before_mode: str,
        before_banner: str,
        before_drop: str,
        before_levels: dict[str, int],
    ) -> None:
        if self.game.result_banner and self.game.result_banner != before_banner:
            self._show_toast(f"Result: {self.game.result_banner}")
            self._play_sfx("result")
            return
        if self.game.mode != before_mode and self.game.mode in {"victory", "defeat"}:
            if self.game.mode == "victory":
                self._show_toast("Victory! Choose Begin Next Adventure to continue.")
            else:
                self._show_toast("Defeat... Choose Restart to try again.")
            self._play_sfx("result")
            return
        for unit in self.game.party:
            key = unit.character_id or unit.name
            if unit.level > before_levels.get(key, unit.level):
                self._show_toast(f"Level Up! {self._short_name(unit.name)} is now Lv {unit.level}")
                self._play_sfx("level")
                return
        if self.game.last_drop_debug and self.game.last_drop_debug != before_drop:
            self._show_toast(f"Loot: {self.game.last_drop_debug}")
            self._play_sfx("loot")
            return
        new_entries = self.game.log[before_log_len:]
        for entry in new_entries[::-1]:
            lowered = entry.lower()
            if "chest found" in lowered or "open the chest" in lowered:
                self._show_toast(entry)
                self._play_sfx("info")
                return
            if "boss reward" in lowered or "encounter won" in lowered:
                self._show_toast(entry)
                self._play_sfx("result")
                return

    def _play_sfx(self, event_type: str) -> None:
        if not self.sound_enabled:
            return
        bell_count = {
            "roll": 1,
            "loot": 1,
            "level": 2,
            "result": 3,
            "info": 1,
        }.get(event_type, 1)
        for _ in range(bell_count):
            try:
                self.bell()
            except Exception:
                print("\a", end="", file=sys.stderr, flush=True)

    def _append_online_note(self, text: str) -> None:
        self.online_notes.append(text)
        self.online_notes = self.online_notes[-12:]

    def _save_silent(self) -> None:
        if self.tutorial_mode:
            return
        if self.game.run_mode == "ironman" and self.game.mode == "defeat":
            delete_active_ironman_save()
            self.game.log.append("Ironman run ended. Save deleted.")
            self.game.log = self.game.log[-12:]
            return
        if self.game.run_mode == "ironman" and self.game.mode == "victory":
            archive_path = archive_ironman_victory(self.game)
            self.game.log.append(f"Ironman champion archived: {archive_path.name}")
            self.game.log = self.game.log[-12:]
            return
        if self.save_path:
            save_game(self.game, self.save_path)

    @staticmethod
    def _hp_notation(hp: int, max_hp: int) -> str:
        ratio = (hp / max_hp) if max_hp else 0
        if hp <= 0:
            color = "red"
        elif ratio > 0.66:
            color = "green"
        elif ratio > 0.33:
            color = "yellow"
        else:
            color = "orange3"
        return f"[{color}]HP:{hp}/{max_hp}[/]"

    @staticmethod
    def _mp_notation(mana: int, max_mana: int) -> str:
        return f"[cyan]MP:{mana}/{max_mana}[/]"

    @staticmethod
    def _xp_gauge(unit) -> str:
        total = max(1, int(unit.next_level_xp))
        current = max(0, min(total, int(unit.experience)))
        width = 10
        filled = int(round((current / total) * width))
        return f"XP:[{'#' * filled}{'.' * (width - filled)}] {current}/{total}"

    @staticmethod
    def _health_icon(unit) -> str:
        if not unit.alive:
            return "💀"
        hp_ratio = unit.hp / unit.max_hp if unit.max_hp else 0
        if hp_ratio > 0.66:
            return "💚"
        if hp_ratio > 0.33:
            return "💛"
        return "❤️"

    @staticmethod
    def _short_name(name: str) -> str:
        return name.split(" (", 1)[0]

    @staticmethod
    def _health_icon_from_values(hp: int, max_hp: int) -> str:
        if hp <= 0:
            return "💀"
        ratio = hp / max_hp if max_hp else 0
        if ratio > 0.66:
            return "💚"
        if ratio > 0.33:
            return "💛"
        return "❤️"

    def _capture_local_log_updates(self) -> None:
        current = [str(entry) for entry in self.game.log[-12:]]
        new_entries = self._extract_new_entries(self._local_log_snapshot, current)
        if new_entries:
            self._flash_event(new_entries[-1], play_sound=False)
        self._local_log_snapshot = current

    def _capture_online_log_updates(self) -> None:
        current = [str(item) for item in self.online_snapshot.get("log", [])]
        current.extend(self.online_notes[-4:])
        new_entries = self._extract_new_entries(self._online_log_snapshot, current)
        if new_entries:
            self._flash_event(new_entries[-1], play_sound=True)
        self._online_log_snapshot = current

    def _flash_event(self, text: str, play_sound: bool) -> None:
        self.event_flash_message = text
        if self.event_timer:
            self.event_timer.stop()
        self.event_timer = self.set_timer(2.8, self._clear_event_flash)
        if play_sound:
            self._play_sfx("info")

    @staticmethod
    def _extract_new_entries(previous: list[str], current: list[str]) -> list[str]:
        if not previous:
            return []
        if current == previous:
            return []
        if len(current) >= len(previous) and current[: len(previous)] == previous:
            return current[len(previous) :]
        max_overlap = min(len(previous), len(current))
        for overlap in range(max_overlap, 0, -1):
            if previous[-overlap:] == current[:overlap]:
                return current[overlap:]
        return current

    @staticmethod
    def _entry_bullet(entry: str) -> str:
        lowered = entry.lower()
        if "loot" in lowered or "reward" in lowered or "chest" in lowered or "gold" in lowered:
            return "[bold #ffd27f]◆[/]"
        if "ambush" in lowered or "trap" in lowered or "defeat" in lowered:
            return "[bold #ff9f9f]◆[/]"
        if "restorative" in lowered or "heals" in lowered or "recover" in lowered:
            return "[bold #9de5b2]◆[/]"
        return "[bold #8fb3d9]•[/]"

    def _style_log_text(self, entry: str) -> str:
        styled = entry
        rarity_palette = {"common": "#dfe8f2", "uncommon": "#88e2ff", "rare": "#f2a8ff"}
        for item_id, item_data in ITEM_DEFS.items():
            item_name = str(item_data.get("name", "")).strip()
            if not item_name:
                continue
            rarity = item_rarity(item_id)
            color = rarity_palette.get(rarity, "#dfe8f2")
            styled = re.sub(
                re.escape(item_name),
                lambda match: f"[{color}]{match.group(0)}[/]",
                styled,
                flags=re.IGNORECASE,
            )
        styled = re.sub(r"(\+?\d+\s*gold)", r"[#f5d279]\1[/]", styled, flags=re.IGNORECASE)
        styled = re.sub(r"(\+?\d+g)", r"[#f5d279]\1[/]", styled, flags=re.IGNORECASE)
        if "loot roll:" in entry.lower():
            return f"[#c7d2e3]{styled}[/]"
        return styled

    def _tutorial_step_text(self) -> str:
        index = min(self.tutorial_step_index, len(self.TUTORIAL_STEPS) - 1)
        return self.TUTORIAL_STEPS[index]

    def _tutorial_action_allowed(self, action_label: str) -> bool:
        if action_label in {"Skip Tutorial", "Finish Tutorial"}:
            return True
        step = self.tutorial_step_index
        if step == 0:
            return action_label == "Venture Deeper"
        if step >= 6:
            return action_label in {"Finish Tutorial", "Skip Tutorial"}
        return True

    def _advance_tutorial_progress(self, *, action_label: str, before_menu: str, before_pending_action: str | None) -> None:
        previous_step = self.tutorial_step_index
        if self.tutorial_step_index == 0 and action_label == "Venture Deeper":
            self.tutorial_step_index = 1
            self.game.log.append("Tutorial: Great. Now practice attack style selection and targeting.")
        elif (
            self.tutorial_step_index == 1
            and before_menu == "target_enemy"
            and before_pending_action == "attack"
            and action_label.startswith("Target: ")
        ):
            self.tutorial_step_index = 2
            self.game.log.append("Tutorial: Nice hit. Next, use a skill (or Defend if needed).")
        elif self.tutorial_step_index == 2 and action_label == "Defend":
            self.tutorial_step_index = 3
            self.game.log.append("Tutorial: Good defense. Open Bag or Equip Gear next.")
        elif (
            self.tutorial_step_index == 2
            and before_menu in {"target_enemy", "target_ally"}
            and before_pending_action == "skill"
            and action_label.startswith("Target")
        ):
            self.tutorial_step_index = 3
            self.game.log.append("Tutorial: Skill confirmed. Open Bag or Equip Gear next.")
        elif self.tutorial_step_index == 3 and action_label in {"Bag", "Equip Gear"}:
            self.tutorial_step_index = 4
            self.game.log.append("Tutorial: Utility learned. Open Path then close the map.")
        elif self.tutorial_step_index == 4 and action_label == "Path":
            self.tutorial_map_opened = True
        elif self.tutorial_step_index == 4 and self.tutorial_map_opened and action_label == "Close Map":
            self.tutorial_step_index = 5
            self.game.log.append("Tutorial: Great navigation. Look Around, then open the chest.")
        elif self.tutorial_step_index == 5 and action_label == "Open Chest":
            self.tutorial_step_index = 6
            self.game.log.append("Tutorial: Final step unlocked. Choose Finish Tutorial.")
        elif self.tutorial_step_index >= 1 and action_label != "Skip Tutorial" and self.tutorial_step_index == previous_step:
            self.game.log.append(f"Tutorial hint: {self._tutorial_step_text()}")
        self.game.log = self.game.log[-12:]

    def _finish_tutorial(self, result: str) -> None:
        self.tutorial_result = result
        if result == "completed":
            self.game.log.append("Tutorial complete. You are ready for a full run.")
            self._show_toast("Tutorial complete.")
        else:
            self.game.log.append("Tutorial skipped.")
            self._show_toast("Tutorial skipped.")
        self.game.log = self.game.log[-12:]
        self.exit()

    def _point_delta(self, stat: str, from_value: int, to_value: int) -> int:
        before = dict(self.creator_stats)
        before[stat] = from_value
        after = dict(self.creator_stats)
        after[stat] = to_value
        return abs(point_buy_cost(after) - point_buy_cost(before))
