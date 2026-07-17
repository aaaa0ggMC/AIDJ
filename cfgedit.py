"""AIDJ Config Editor — Textual TUI for managing config.json"""
import json
import os
import sys

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, ListView, ListItem, Label, Input, Static, Button, DataTable
    from textual.containers import Container, Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.binding import Binding
    from textual import on
    from rich.text import Text
except ImportError:
    print("Please install textual: pip install textual")
    sys.exit(1)

CONFIG_PATH = "data/config.json"

DEFAULTS = {
    "ai_settings": {
        "base_url":       "https://api.deepseek.com",
        "metadata_model": "deepseek-chat",
    },
    "preferences": {
        "model":                    None,
        "verbose":                  False,
        "saved_trigger":            None,
        "dbus_target":              None,
        "record_freq":              False,
        "dynamic_balance_volume":   False,
        "sound_adjust_method":      "lufs",
        "volume_curve":             3.0,
        "metadata_concurrency":     1,
    },
}

SECRET_FIELDS = {"api_key", "deepseek", "openai", "gemini", "password", "token", "secret"}

FIELD_META = {
    "base_url":          ("str",  "API base endpoint URL", "https://api.deepseek.com"),
    "metadata_model":    ("str",  "Model used for metadata extraction", "deepseek-chat"),
    "model":             ("str",  "Active chat model", "qwen/qwen3.7-max"),
    "verbose":           ("bool", "Enable debug logging", "false"),
    "saved_trigger":     ("str",  "Persistent auto-trigger command", "send"),
    "dbus_target":       ("str",  "Preferred MPRIS player name", "vlc"),
    "record_freq":       ("bool", "Track per-song play counts", "false"),
    "dynamic_balance_volume": ("bool", "Loudness-based volume balancing", "false"),
    "sound_adjust_method":  ("str",  "Volume adjust method: lufs or linear", "lufs"),
    "volume_curve":      ("float","Volume curve multiplier", "3.0"),
    "metadata_concurrency":  ("int","Parallel workers for metadata sync (1-16)", "1"),
}

# sidebar sections: (label, section_key, mode)
# mode: "map" | "list"
SECTIONS = [
    ("  🔑 Secrets",       "secrets",          "map"),
    ("  🧠 AI Settings",    "ai_settings",      "map"),
    ("  📋 Models",         "available_models", "list"),
    ("  ⚙️  Preferences",   "preferences",      "map"),
    ("  🎵 Music Folders",  "music_folders",    "list"),
]


class EditModal(ModalScreen[str]):
    def __init__(self, field: str, current: str, meta: tuple, is_secret: bool = False):
        super().__init__()
        self.field = field
        self.current = current
        self.meta = meta
        self.is_secret = is_secret

    def compose(self) -> ComposeResult:
        ftype, desc, placeholder = self.meta
        display_val = "********" if self.is_secret else str(self.current)
        with Vertical(id="dialog"):
            yield Label(f"[bold cyan]{self.field}[/bold cyan]\n[dim]{desc}[/dim]")
            yield Input(value=display_val, id="val_input", password=self.is_secret,
                        placeholder=placeholder)
            if ftype in ("int", "float"):
                yield Static(f"[dim]Type: {ftype}[/dim]", id="type_hint")
            with Horizontal(id="buttons"):
                yield Button("✔ Save", variant="primary", id="save")
                yield Button("✘ Cancel", variant="error", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.dismiss(self.query_one("#val_input").value)
        else:
            self.dismiss(None)


class AddStringModal(ModalScreen[str]):
    def __init__(self, label: str, placeholder: str = ""):
        super().__init__()
        self.label = label
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"[bold cyan]{self.label}[/bold cyan]")
            yield Input(placeholder=self.placeholder, id="add_input")
            with Horizontal(id="buttons"):
                yield Button("✔ Add", variant="primary", id="add")
                yield Button("✘ Cancel", variant="error", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add":
            self.dismiss(self.query_one("#add_input").value)
        else:
            self.dismiss(None)


class ConfigApp(App):
    """AIDJ Config Editor"""

    CSS = """
    Screen { background: $surface; }
    #sidebar { width: 26; border-right: thick $primary-darken-2; background: $panel; }
    #sidebar ListView { height: 1fr; }
    #sidebar ListItem { padding: 0 1; }
    #sidebar ListItem.--highlight { background: $primary 30%; }
    #content { width: 1fr; }
    #section_title { padding: 1 2; background: $primary-darken-2; text-style: bold; color: $text; }
    DataTable { height: 1fr; border: solid $primary-darken-1; margin: 0 1; }
    #status_bar { padding: 0 2; height: 1; background: $panel; color: $text-disabled; }
    #dialog {
        padding: 1 2; background: $surface; border: thick $primary;
        width: 62; height: auto; align: center middle;
    }
    #dialog Label { padding-bottom: 1; }
    #buttons { margin-top: 1; align-horizontal: right; }
    #buttons Button { margin-left: 1; }
    #type_hint { padding-top: 1; color: $text-disabled; }
    """

    BINDINGS = [
        Binding("s", "save_all", "Save", show=True),
        Binding("r", "remove_item", "Remove", show=True),
        Binding("a", "add_item", "Add", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.cfg: dict = {}
        self.section: str = ""
        self.section_mode: str = "map"  # "map" | "list"
        self._load()

    def _load(self):
        path = CONFIG_PATH
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.cfg = json.load(f)
        else:
            self.cfg = {}

    def _save(self):
        path = CONFIG_PATH
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, ensure_ascii=False, indent=4)

    # ── Compose ────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label("  [bold]📁 SECTIONS[/]", id="section_title")
                items = [ListItem(Label(label)) for label, _, _ in SECTIONS]
                yield ListView(*items, id="nav")
            with Vertical(id="content"):
                yield Label("Select a section", id="section_title")
                yield DataTable(id="table")
                yield Static("[dim]s:save  r:remove  a:add  q:quit[/dim]", id="status_bar")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#table", DataTable)
        table.add_columns("Key", "Value", "Type / Description")
        table.cursor_type = "row"

    # ── Navigation ─────────────────────────────────────────

    @on(ListView.Selected)
    def on_nav_select(self, event: ListView.Selected):
        idx = self.query_one("#nav", ListView).index
        if idx is None:
            return
        _, self.section, self.section_mode = SECTIONS[idx]
        self._render_table()
        title = SECTIONS[idx][0].strip()
        self.query_one("#section_title", Label).update(f"  [bold]{title}[/]")

    # ── Table rendering ────────────────────────────────────

    def _get_data(self) -> dict:
        if self.section == "available_models":
            return self.cfg.get("ai_settings", {})
        return self.cfg.get(self.section, {})

    def _mask(self, key: str) -> bool:
        return self.section == "secrets" or any(s in key.lower() for s in SECRET_FIELDS)

    def _save_cursor(self):
        table = self.query_one("#table", DataTable)
        if table.row_count == 0:
            return None
        row_keys = list(table.rows.keys())
        return row_keys[table.cursor_row].value if table.cursor_row is not None else None

    def _restore_cursor(self, saved_key):
        if saved_key is None:
            return
        table = self.query_one("#table", DataTable)
        row_keys = list(table.rows.keys())
        try:
            idx = row_keys.index(saved_key)
            table.cursor_coordinate = (idx, 0)
        except (ValueError, IndexError):
            pass

    def _render_table(self):
        table = self.query_one("#table", DataTable)
        saved = self._save_cursor()
        table.clear()

        if self.section_mode == "list":
            items = self._get_list_items()
            for key, val in items:
                table.add_row(
                    Text(key, style="cyan"),
                    Text(val, style="green"),
                    Text("str", style="dim"),
                    key=val,
                )
        else:
            data = self._get_data()
            defaults = DEFAULTS.get(self.section, {})
            for key, default_val in defaults.items():
                if key not in data:
                    continue
                val = data[key]
                meta = FIELD_META.get(key, ("str", "", ""))
                is_secret = self._mask(key)
                display = self._fmt_val(val, is_secret)
                key_color = self._key_color(key, val, default_val)
                table.add_row(
                    Text(key, style=key_color),
                    display,
                    Text(f"{meta[0]}  —  {meta[1]}", style="dim"),
                    key=key,
                )
            for key, val in data.items():
                if key in defaults:
                    continue
                is_secret = self._mask(key)
                display = self._fmt_val(val, is_secret)
                table.add_row(
                    Text(key, style="bold cyan"),
                    display,
                    Text("custom", style="dim"),
                    key=key,
                )

        self._restore_cursor(saved)

    def _get_list_items(self) -> list:
        if self.section == "available_models":
            models = self.cfg.get("ai_settings", {}).get("available_models", [])
            return [("model", m) for m in models]
        elif self.section == "music_folders":
            return [("path", p) for p in self.cfg.get("music_folders", [])]
        return []

    def _fmt_val(self, val, is_secret: bool) -> Text:
        if is_secret:
            n = min(len(str(val)), 16) if val else 0
            return Text("*" * n if n else "(empty)", style="yellow")
        if isinstance(val, bool):
            return Text(str(val), style="bold green" if val else "red")
        if val is None:
            return Text("—", style="dim")
        s = str(val)
        if len(s) > 50:
            s = s[:47] + "..."
        return Text(s, style="green")

    def _key_color(self, key: str, val, default_val) -> str:
        return "bold green" if val != default_val else "dim"

    # ── Row actions ────────────────────────────────────────

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected):
        key = event.row_key.value
        if self.section_mode == "list":
            return  # remove only (via 'r')

        data = self._get_data()
        current_val = data.get(key, "")
        meta = FIELD_META.get(key, ("str", "", ""))

        if meta[0] == "bool":
            data[key] = not current_val if isinstance(current_val, bool) else True
            self._render_table()
            return

        is_secret = self._mask(key)

        def _cb(new_val: str | None):
            if new_val is None:
                return
            data[key] = self._coerce(new_val, meta[0])
            self._render_table()

        self.push_screen(EditModal(key, str(current_val), meta, is_secret), _cb)

    def _coerce(self, raw: str, ftype: str):
        raw = raw.strip()
        if ftype == "bool":
            return raw.lower() in ("true", "1", "yes", "on")
        if ftype == "int":
            return int(raw)
        if ftype == "float":
            return float(raw)
        if ftype == "list":
            return [v.strip() for v in raw.split(",") if v.strip()]
        return raw

    # ── Keybindings ────────────────────────────────────────

    def action_save_all(self):
        self._save()
        self.notify("💾 Config saved!", severity="information", timeout=2)

    def action_remove_item(self):
        table = self.query_one("#table", DataTable)
        if table.cursor_row is None:
            return
        row_keys = list(table.rows.keys())
        key = row_keys[table.cursor_row].value

        if self.section_mode == "list":
            target = self._get_target_list()
            if key in target:
                target.remove(key)
                self.notify(f"Removed: {key}", timeout=2)
        else:
            data = self._get_data()
            if key in data:
                if key in DEFAULTS.get(self.section, {}):
                    data[key] = DEFAULTS[self.section][key]
                    self.notify(f"Reset '{key}' to default", timeout=2)
                else:
                    del data[key]
                    self.notify(f"Removed '{key}'", timeout=2)
        self._render_table()

    def _get_target_list(self) -> list:
        if self.section == "available_models":
            return self.cfg.setdefault("ai_settings", {}).setdefault("available_models", [])
        if self.section == "music_folders":
            return self.cfg.setdefault("music_folders", [])
        return []

    def action_add_item(self):
        if self.section_mode == "list":
            if self.section == "available_models":
                hint = "Model ID (e.g. provider/name)"
                placeholder = "deepseek/deepseek-chat"
            else:
                hint = "Music folder path"
                placeholder = "/home/user/Music"

            def _cb(val: str | None):
                if val and val.strip():
                    self._get_target_list().append(val.strip())
                    self._render_table()

            self.push_screen(AddStringModal(f"Add to {self.section}", placeholder), _cb)
        else:
            self.notify("Add is supported in list-mode sections only", severity="warning", timeout=3)


if __name__ == "__main__":
    ConfigApp().run()
