import json
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from command_handler import console
import re

def print_banner(base_url, model):
    console.print(Panel.fit(
        f"[bold cyan]          AI DJ SYSTEM v4.0 (Refactored)        [/]\n"
        f"[dim]Endpoint: {base_url}[/]\n"
        f"[dim]Model: {model}[/]",
        title="✨ System Ready ✨", border_style="magenta"
    ))

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

    for item in playlist:
        name = item['name']
        info = metadata.get(name, {})
        
        def safe_fmt(val):
            if val is None: return "-"
            if isinstance(val, list): return ", ".join(str(x) for x in val)
            return str(val)
            
        t.add_row(
            name, 
            safe_fmt(info.get('language')), 
            safe_fmt(info.get('genre')), 
            safe_fmt(info.get('emotion')), 
            safe_fmt(info.get('loudness'))
        )
    console.print(t)

def print_status(config, ai_settings, playlist_len):
    t = Table(title="⚙️ System Status")
    t.add_column("Setting", style="cyan")
    t.add_column("Value", style="yellow")
    t.add_row("API Endpoint", ai_settings.get("base_url"))
    t.add_row("Current Model", config['preferences']['model'])
    t.add_row("Metadata Model", ai_settings.get("metadata_model", "N/A"))
    t.add_row("Verbose Mode", str(config['preferences']['verbose']))
    t.add_row("Auto Trigger", str(config['preferences']['saved_trigger'] or "OFF"))
    t.add_row("DBus Target", str(config['preferences']['dbus_target'] or "Auto"))
    t.add_row("Playlist Cache", f"{playlist_len} tracks")
    console.print(t)

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
