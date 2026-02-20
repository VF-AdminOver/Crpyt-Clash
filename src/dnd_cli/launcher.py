from __future__ import annotations

from dataclasses import dataclass
import os

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from dnd_cli.storage import load_auth


@dataclass(frozen=True)
class LauncherChoice:
    key: str
    title: str
    description: str


@dataclass(frozen=True)
class FormField:
    key: str
    label: str
    placeholder: str = ""
    default: str = ""
    password: bool = False
    optional: bool = False


def _default_server() -> str:
    env_server = os.getenv("CRYPTCLASH_DEFAULT_SERVER", "").strip()
    if env_server:
        return env_server
    auth_data = load_auth()
    saved = str(auth_data.get("server", "")).strip()
    if saved:
        return saved
    return "http://127.0.0.1:8000"


CHOICES: list[LauncherChoice] = [
    LauncherChoice("tutorial", "Tutorial", "Learn core mechanics in a guided one-room scenario."),
    LauncherChoice("new", "New Adventure", "Start a fresh run with character creation."),
    LauncherChoice("continue", "Continue", "Resume your latest active run."),
    LauncherChoice("start_local_server", "Start Local Server", "Run online server in background on this machine."),
    LauncherChoice("stop_local_server", "Stop Local Server", "Stop background local online server."),
    LauncherChoice("online", "Online Hub", "Enter MMO-lite hub with your online character."),
    LauncherChoice("characters", "Online Characters", "List your server-side characters."),
    LauncherChoice("register", "Register Account", "Create a new online account."),
    LauncherChoice("login", "Login Account", "Login to your online account."),
    LauncherChoice("character_create", "Create Online Character", "Create a server-side character slot."),
    LauncherChoice("roster", "Local Roster", "View local saved roster heroes."),
    LauncherChoice("host", "LAN Host", "Host a legacy LAN run (authoritative host)."),
    LauncherChoice("join", "LAN Join", "Join a legacy LAN host."),
    LauncherChoice("quit", "Quit", "Exit Crypt Clash."),
]

FORM_CHOICES: dict[str, list[FormField]] = {
    "register": [
        FormField("server", "Server URL (leave blank for local/default)", default=_default_server(), optional=True),
        FormField("username", "Username", "player1"),
        FormField("password", "Password (min 8 chars)", password=True),
    ],
    "login": [
        FormField("server", "Server URL (leave blank for local/default)", default=_default_server(), optional=True),
        FormField("username", "Username", "player1"),
        FormField("password", "Password (min 8 chars)", password=True),
    ],
    "character_create": [
        FormField("name", "Character Name", "Iris"),
        FormField("archetype", "Archetype", "Fighter/Rogue/Cleric/Mage", default="Mage"),
    ],
    "online": [
        FormField("server", "Server URL (leave blank for local/default)", default=_default_server(), optional=True),
    ],
    "host": [
        FormField("bind", "Bind", default="0.0.0.0"),
        FormField("port", "Port", default="8765"),
        FormField("code", "Join Code", placeholder="auto", optional=True),
        FormField("name", "Host Name", default="Host"),
        FormField("chat_mode", "Chat Mode", default="reactions_only"),
    ],
    "join": [
        FormField("host", "Host", "127.0.0.1"),
        FormField("port", "Port", default="8765"),
        FormField("code", "Join Code"),
        FormField("name", "Player Name", default="Player"),
    ],
}


class LauncherApp(App[str | None]):
    CSS = """
    Screen {
      align: center middle;
    }
    #root {
      width: 92;
      max-width: 92;
      height: auto;
      border: round #5ca8f5;
      padding: 1 2;
    }
    #title {
      text-style: bold;
      color: #5ca8f5;
      margin-bottom: 1;
    }
    #subtitle {
      color: #b6c6d9;
      margin-bottom: 1;
    }
    #help {
      color: #9aa8b8;
      margin-top: 1;
    }
    #help-keys {
      color: #9aa8b8;
      margin-top: 1;
    }
    ListView {
      height: 12;
      border: round #2f3f52;
    }
    """

    BINDINGS = [("enter", "confirm", "Select"), ("q", "quit", "Quit"), ("escape", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        with Vertical(id="root"):
            yield Header(show_clock=False)
            yield Label("CRYPT CLASH", id="title")
            yield Static("Terminal RPG + Online MMO-lite Launcher", id="subtitle")
            rows = ListView(*(ListItem(Static(f"{choice.title}  [dim]{choice.description}[/dim]")) for choice in CHOICES))
            rows.id = "choices"
            yield rows
            yield Static("Use arrows + Enter. You can still run direct commands anytime.", id="help")
            yield Footer()

    def on_mount(self) -> None:
        list_view = self.query_one(ListView)
        if list_view.index is None:
            list_view.index = 0
        list_view.focus()

    def action_confirm(self) -> None:
        self._exit_selected_choice()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "choices":
            self._exit_selected_choice()

    def _exit_selected_choice(self) -> None:
        list_view = self.query_one(ListView)
        index = list_view.index if list_view.index is not None else 0
        if index < 0 or index >= len(CHOICES):
            return
        self.exit(CHOICES[index].key)

    def action_quit(self) -> None:
        self.exit("quit")


def run_launcher() -> str | None:
    app = LauncherApp()
    return app.run()


class LauncherFormApp(App[dict | None]):
    CSS = """
    Screen {
      align: center middle;
    }
    #root {
      width: 88;
      max-width: 88;
      height: auto;
      border: round #5ca8f5;
      padding: 1 2;
    }
    #title {
      text-style: bold;
      color: #5ca8f5;
      margin-bottom: 1;
    }
    .field-label {
      color: #d7e4f2;
      margin-top: 1;
    }
    Input {
      border: round #2f3f52;
      margin-top: 0;
    }
    #help {
      color: #9aa8b8;
      margin-top: 1;
    }
    #error {
      color: #ff7b7b;
      margin-top: 1;
    }
    """

    BINDINGS = [
        ("enter", "next_field", "Next"),
        ("ctrl+s", "submit", "Submit"),
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
    ]

    def __init__(self, command: str, fields: list[FormField]) -> None:
        super().__init__()
        self.command = command
        self.fields = fields

    def compose(self) -> ComposeResult:
        with Vertical(id="root"):
            yield Header(show_clock=False)
            yield Label(f"{self.command.replace('_', ' ').title()} Setup", id="title")
            yield Static(
                "Tip: `http://127.0.0.1:8000` means the server running on this same machine.",
                id="help",
            )
            for field in self.fields:
                yield Static(field.label, classes="field-label")
                yield Input(
                    value=field.default,
                    placeholder=field.placeholder,
                    password=field.password,
                    id=f"field-{field.key}",
                )
            yield Static("Enter: next field | Ctrl+S: submit | Esc: cancel", id="help-keys")
            yield Static("", id="error")
            yield Footer()

    def on_mount(self) -> None:
        first = self.query_one(f"#field-{self.fields[0].key}", Input)
        first.focus()

    def action_next_field(self) -> None:
        focused = self.focused
        if not isinstance(focused, Input):
            self.action_submit()
            return
        ids = [f"field-{field.key}" for field in self.fields]
        current = focused.id or ""
        if current not in ids:
            self.action_submit()
            return
        index = ids.index(current)
        if index >= len(ids) - 1:
            self.action_submit()
            return
        self.query_one(f"#{ids[index + 1]}", Input).focus()

    def action_submit(self) -> None:
        payload: dict[str, str] = {}
        for field in self.fields:
            value = self.query_one(f"#field-{field.key}", Input).value.strip()
            if not value and not field.optional:
                self.query_one("#error", Static).update(f"{field.label} is required.")
                self.query_one(f"#field-{field.key}", Input).focus()
                return
            payload[field.key] = value
        if self.command in {"register", "login"}:
            username = payload.get("username", "")
            password = payload.get("password", "")
            if len(username) < 3:
                self.query_one("#error", Static).update("Username must be at least 3 characters.")
                self.query_one("#field-username", Input).focus()
                return
            if len(password) < 8:
                self.query_one("#error", Static).update("Password must be at least 8 characters.")
                self.query_one("#field-password", Input).focus()
                return
        self.exit(payload)

    def action_cancel(self) -> None:
        self.exit(None)


def run_launcher_form(command: str) -> dict | None:
    fields = FORM_CHOICES.get(command)
    if not fields:
        return {}
    app = LauncherFormApp(command=command, fields=fields)
    return app.run()


class LauncherMessageApp(App[None]):
    CSS = """
    Screen {
      align: center middle;
    }
    #root {
      width: 92;
      max-width: 92;
      height: auto;
      border: round #5ca8f5;
      padding: 1 2;
    }
    #title {
      text-style: bold;
      color: #5ca8f5;
      margin-bottom: 1;
    }
    #body {
      color: #d7e4f2;
      margin-top: 1;
      margin-bottom: 1;
    }
    """
    BINDINGS = [("enter", "close", "Continue"), ("escape", "close", "Continue"), ("q", "close", "Continue")]

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self.title = title
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="root"):
            yield Header(show_clock=False)
            yield Label(self.title, id="title")
            yield Static(self.body, id="body")
            yield Static("Press Enter to return to launcher.")
            yield Footer()

    def action_close(self) -> None:
        self.exit(None)


def run_launcher_message(title: str, body: str) -> None:
    LauncherMessageApp(title=title, body=body).run()
