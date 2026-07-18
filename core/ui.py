import json
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from core.command_handler import console
from rich.console import Group
import re

def print_banner(config, musics, metadata):
    pref = config.get('preferences', {})
    ai_settings = config.get('ai_settings', {})
    model = pref.get('model') or "default"
    base_url = ai_settings.get('base_url', '—')
    conc = pref.get('metadata_concurrency', 1)
    volbal = pref.get('dynamic_balance_volume', False)
    freq = pref.get('record_freq', False)
    trigger = pref.get('saved_trigger')
    mf = config.get('music_folders', [])

    music_count = len(musics)
    meta_count = len(metadata)
    valid_count = len(set(metadata.keys()) & set(musics.keys()))
    coverage = f"{meta_count}/{music_count}" if music_count else "—"
    volbal_state = "[bold green]ON[/]" if volbal else "[dim]OFF[/]"
    freq_state = "[bold green]ON[/]" if freq else "[dim]OFF[/]"
    trigger_state = f"[bold cyan]{trigger}[/]" if trigger else "[dim]OFF[/]"
    folder_list = "\n".join(f"    [dim]•[/] {f}" for f in mf) if mf else "    [dim]• (current dir)[/]"

    body = (
        f"[bold cyan]🎧 AI DJ SYSTEM v4.0[/]\n"
        f"\n"
        f"[bold]📡 API[/]\n"
        f"  Endpoint  [dim]{base_url}[/]\n"
        f"  Chat      [yellow]{model}[/]\n"
        f"  Metadata  [yellow]{ai_settings.get('metadata_model', '—')}[/]  |  Sync  [bold]{conc}w[/]\n"
        f"\n"
        f"[bold]🎵 Music Library[/]\n"
        f"{folder_list}\n"
        f"  Tracks    [bold green]{music_count}[/]  |  Metadata  [bold cyan]{coverage}[/]  |  Valid  [bold yellow]{valid_count}[/]\n"
        f"\n"
        f"[bold]⚙️  Quick Status[/]\n"
        f"  VolBal     {volbal_state}    FreqRec  {freq_state}    AutoTrig  {trigger_state}"
    )

    console.print(Panel(body, title="✨ System Ready ✨", border_style="bold magenta"))

def print_dj_intro(intro_text):
    if not intro_text: return
    # 清洗 <think> 标签
    clean_intro = re.sub(r'<think>.*?</think>', '', intro_text, flags=re.DOTALL).strip()
    if clean_intro:
        md_content = Markdown(clean_intro)
        console.print(Panel(
            md_content,
            title="💬 DJ Says",
            border_style="bold magenta",
            padding=(1, 2)
        ))

def print_playlist(playlist, metadata, title_suffix="List"):
    t = Table(show_header=True, title=f"Playlist ({len(playlist)}) - {title_suffix}", show_lines=True)
    t.add_column("Track", style="bold green", no_wrap=True)
    t.add_column("Language", style="cyan")
    t.add_column("Genre", style="magenta")
    t.add_column("Emotion", style="yellow")
    t.add_column("Loudness", style="dim")

    def safe_fmt(val):
        if val is None: return "-"
        if isinstance(val, list): return ", ".join(str(x) for x in val)
        return str(val)

    for item in playlist:
        name = item['name']
        info = metadata.get(name, {})

        t.add_row(
            name, 
            safe_fmt(info.get('language')), 
            safe_fmt(info.get('genre')), 
            safe_fmt(info.get('emotion')), 
            safe_fmt(info.get('loudness'))
        )
    console.print(t)

def print_status(config, ai_settings, playlist_len):
    pref = config.get('preferences', {})

    # --- Helpers ---
    def on_off(val, on_label="ON", off_label="OFF"):
        return f"[bold green]{on_label}[/]" if val else f"[dim]{off_label}[/]"

    def fmt_row(key, val):
        return f"  [cyan]{key}[/]  [yellow]{val}[/]"

    def make_section(title, rows, border="blue"):
        return Panel("\n".join(rows), title=title, border_style=border, padding=(0, 1))

    # --- PLAYBACK ---
    dbus_tgt = pref.get('dbus_target') or "Auto"
    trigger = pref.get('saved_trigger') or "OFF"
    mf = config.get('music_folders', [])
    mf_label = f"{len(mf)} folders" if mf else "None"

    playback_rows = [
        fmt_row("DBus Target", dbus_tgt),
        fmt_row("Saved Trigger", trigger),
        fmt_row("Music Folders", mf_label),
        fmt_row("Playlist Cache", f"{playlist_len} tracks"),
    ]
    sections = [make_section("🔊 PLAYBACK", playback_rows)]

    # --- VOLUME BALANCE ---
    volbal = pref.get('dynamic_balance_volume', False)
    method = pref.get('sound_adjust_method', 'lufs')
    method_labels = {"linear": "RMS (linear)", "lufs": "ITU-R BS.1770 LUFS (perceptual)"}
    method_label = method_labels.get(method, method)

    curve = pref.get('volume_curve', 3.0)
    curve_label = f"{curve:.1f}x" if curve != 1.0 else "linear (1.0x)"

    vol_rows = [
        fmt_row("Dynamic Balance", on_off(volbal, "ACTIVE", "inactive")),
        fmt_row("Method", method_label),
        fmt_row("Volume Curve", curve_label),
    ]
    sections.append(make_section("🔈 VOLUME BALANCE", vol_rows))

    # --- AI ---
    model = pref.get('model') or "default"
    conc = pref.get('metadata_concurrency', 1)
    ai_rows = [
        fmt_row("API Endpoint", ai_settings.get('base_url', '—')),
        fmt_row("Chat Model", model),
        fmt_row("Metadata Model", ai_settings.get('metadata_model', '—')),
        fmt_row("Sync Concurrency", str(conc)),
    ]
    sections.append(make_section("🧠 AI", ai_rows, border="magenta"))

    # --- LIBRARY INJECTS ---
    injects = pref.get('library_injects', {})
    inj_rows = []
    for field in ("genre", "emotion", "language", "loudness", "review"):
        inj_rows.append(fmt_row(field, on_off(injects.get(field, False))))
    sections.append(make_section("📦 LIBRARY INJECTS", inj_rows, border="green"))

    # --- DEBUG ---
    verbose = pref.get('verbose', False)
    freq = pref.get('record_freq', False)

    debug_rows = [
        fmt_row("Verbose", on_off(verbose)),
        fmt_row("Freq Recording", on_off(freq, "RECORDING", "idle")),
    ]
    sections.append(make_section("🐛 DEBUG / LOGGING", debug_rows, border="dim"))

    console.print(Panel(Group(*sections), title="⚙️  System Status", border_style="bold blue"))

def print_metadata(name, data):
    t = Table(title=f"ℹ️ Metadata: [bold green]{name}[/]", border_style="blue")
    t.add_column("Field", style="bold cyan", justify="right")
    t.add_column("Value", style="white", overflow="fold")
    if isinstance(data, dict):
        for k in sorted(data.keys()):
            v = data[k]
            if k == "lyrics":
                val_str = str(v)[:100].replace("\n", " ") + "... (truncated)"
            elif isinstance(v, (list, dict)):
                val_str = json.dumps(v, ensure_ascii=False)
            else:
                val_str = str(v)
            t.add_row(k, val_str)
    else:
        t.add_row("Raw Data", str(data))
    console.print(t)

def print_active_players(players, preferred_target):
    t = Table(title="📡 Active Players")
    t.add_column("Name")
    for p in players:
        marker = " [green](Target)[/]" if preferred_target and preferred_target in p else ""
        t.add_row(f"{p}{marker}")
    console.print(t)

def print_action_feedback(message, style="green"):
    """轻量级操作反馈"""
    console.print(f"[{style}]✔ {message}[/]")
