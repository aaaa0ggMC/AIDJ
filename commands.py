import os
import json
import random
import glob
import questionary
from rapidfuzz import process, fuzz
from config import save_config, PLAYLIST_DIR, SEPARATOR, LANGUAGE
from player import execute_player_command
from command_handler import registry, console, Context
import ui

# --- Helper Logic ---
def _update_playlist_and_trigger(ctx: Context, new_playlist, intro, title_desc):
    """更新上下文中的播放列表，打印表格，并执行自动触发"""
    if intro:
        ui.print_dj_intro(intro)
    
    if not new_playlist:
        if not intro: console.print("[yellow]No matches found.[/]")
        return

    # Update Global State
    ctx.play_list = new_playlist
    
    # Print UI
    ui.print_playlist(new_playlist, ctx.aidj.metadata, title_desc)

    # Auto Trigger
    trigger = ctx.config['preferences'].get('saved_trigger')
    if trigger:
        console.print(f"[yellow]⚡ Auto-Executing: {trigger}[/]")
        execute_player_command(trigger, ctx.play_list, ctx.dbus)

def _player_helper(ctx, cmd):
    """Player command wrapper"""
    execute_player_command(cmd, ctx.play_list if cmd in ['mpv','vlc','send'] else None, ctx.dbus)

# --- System Commands ---

@registry.register("exit", "quit", "q")
def cmd_exit(ctx: Context, *args):
    """Exit the application."""
    console.print("[bold red]👋 See ya![/]")
    raise SystemExit

@registry.register("help", "?")
def cmd_help(ctx: Context, *args):
    """Show this help message."""
    registry.print_help()

@registry.register("status", "check", "conf")
def cmd_status(ctx: Context, *args):
    """Show system configuration and status."""
    ui.print_status(ctx.config, ctx.config.get('ai_settings', {}), len(ctx.play_list))

@registry.register("verbose")
def cmd_verbose(ctx: Context, *args):
    """Toggle verbose logging mode."""
    curr = ctx.config['preferences']['verbose']
    ctx.config['preferences']['verbose'] = not curr
    save_config(ctx.config)
    ctx.aidj.config = ctx.config # Update instance config
    console.print(f"[green]📝 Verbose Mode: {not curr}[/]")

@registry.register("refresh")
def cmd_refresh(ctx: Context, *args):
    """Refresh session history (keep songs)."""
    ctx.aidj.refresh(clear_history=False)

@registry.register("reset")
def cmd_reset(ctx: Context, *args):
    """Reset session history and played songs memory."""
    ctx.aidj.refresh(clear_history=True)

@registry.register("auto")
def cmd_auto(ctx: Context, *args):
    """Set persistent auto-trigger command (e.g. 'auto mpv')."""
    if not args:
        curr = ctx.config['preferences'].get('saved_trigger')
        console.print(f"[yellow]Current Trigger: {curr or 'None'}[/]")
        return
    
    val = args[0].lower()
    if val in ["off", "none", "stop"]:
        ctx.config['preferences']['saved_trigger'] = None
        console.print("[green]⚡ Auto Trigger Disabled[/]")
    else:
        ctx.config['preferences']['saved_trigger'] = val
        console.print(f"[green]⚡ Auto Trigger Set: {val}[/]")
    save_config(ctx.config)

@registry.register("model")
def cmd_model(ctx: Context, *args):
    """Switch AI Model."""
    avail = ctx.config['ai_settings'].get("available_models", ["deepseek-chat"])
    curr = ctx.config['preferences']['model']
    sel = questionary.select("Switch Model:", choices=avail, default=curr).ask()
    if sel:
        ctx.config['preferences']['model'] = sel
        save_config(ctx.config)
        ctx.aidj.config = ctx.config
        console.print(f"[green]🧠 Model Switched to: {sel}[/]")

@registry.register("show")
def cmd_show(ctx: Context, *args):
    """Inspect metadata: show <song_name>."""
    if not args:
        console.print("[red]Usage: show <song name>[/]")
        return
    query = " ".join(args)
    keys = list(ctx.aidj.metadata.keys())
    result = process.extractOne(query, keys, scorer=fuzz.token_sort_ratio)
    if not result or result[1] < 60:
        console.print(f"[red]❌ Song '{query}' not found.[/]")
        return
    ui.print_metadata(result[0], ctx.aidj.metadata[result[0]])

# --- Generator Commands ---

@registry.register("r")
def cmd_random(ctx: Context, *args):
    """Select N random songs: r <count>."""
    if not args or not args[0].isdigit():
        console.print("[red]Usage: r <number>[/]")
        return
    count = int(args[0])
    all_keys = list(ctx.aidj.music_paths.keys())
    
    if count <= 0:
        console.print("[yellow]Please select at least 1 song.[/]")
        return

    if count > 50:
        count = 50
        console.print(f"[dim]⚠️ Capped at 50 songs.[/]")
    
    if count > len(all_keys): count = len(all_keys)
    
    selected = random.sample(all_keys, count)
    pl = [{"name": k, "path": ctx.aidj.music_paths[k]} for k in selected]
    
    console.print(f"[green]🎲 Randomly selected {len(pl)} tracks.[/]")
    _update_playlist_and_trigger(ctx, pl, None, "Random Selection")

@registry.register("pr")
def cmd_prompt_random(ctx: Context, *args):
    """AI curated random selection: pr <count>."""
    if not args or not args[0].isdigit():
        console.print("[red]Usage: pr <number>[/]")
        return
    count = int(args[0])
    count = min(count, 50) 
    all_keys = list(ctx.aidj.music_paths.keys())
    
    if count <= 0: return

    if count > len(all_keys): count = len(all_keys)
    
    random_keys = random.sample(all_keys, count)
    min_keep = max(1, count // 2)
    candidates_str = json.dumps(random_keys, ensure_ascii=False)
    
    system_req = (
        f"System Request: I have randomly picked {count} candidate songs from the library: {candidates_str}.\n"
        f"Task: Curate a coherent playlist from THIS SPECIFIC LIST.\n"
        f"Rules: 1. Sort for flow. 2. Filter clashes. 3. Keep at least {min_keep} songs. 4. No hallucinations.\n"
        f"5. Write in {LANGUAGE}. 6. Intro BEFORE separator, keys AFTER."
    )
    
    pl, intro = ctx.aidj.next_step(system_req)
    if not pl: 
         console.print("[yellow]AI curation failed, falling back to raw selection.[/]")
         pl = [{"name": k, "path": ctx.aidj.music_paths[k]} for k in random_keys]
    
    _update_playlist_and_trigger(ctx, pl, intro, "AI Curated Random")

@registry.register("p", "prompt", "gen")
def cmd_gen(ctx: Context, *args):
    """Generate playlist from text: p <request>."""
    if not args:
        console.print("[red]Usage: p <text>[/]")
        return
    request = " ".join(args)
    pl, intro = ctx.aidj.next_step(request)
    _update_playlist_and_trigger(ctx, pl, intro, "AI Generated")

# --- Player & DBus Commands ---
# 为了明确功能，这里分别注册，但统一调用辅助函数

@registry.register("next", "n")
def _c_next(ctx: Context, *args):
    """Play next track."""
    _player_helper(ctx, "next")

@registry.register("prev", "b")
def _c_prev(ctx: Context, *args):
    """Play previous track."""
    _player_helper(ctx, "prev")

@registry.register("play")
def _c_play(ctx: Context, *args):
    """Resume playback."""
    _player_helper(ctx, "play")

@registry.register("pause")
def _c_pause(ctx: Context, *args):
    """Pause playback."""
    _player_helper(ctx, "pause")

@registry.register("toggle")
def _c_toggle(ctx: Context, *args):
    """Toggle play/pause."""
    _player_helper(ctx, "toggle")

@registry.register("stop")
def _c_stop(ctx: Context, *args):
    """Stop playback."""
    _player_helper(ctx, "stop")

@registry.register("mpv")
def _c_mpv(ctx: Context, *args):
    """Play current list with MPV."""
    _player_helper(ctx, "mpv")

@registry.register("vlc")
def _c_vlc(ctx: Context, *args):
    """Play current list with VLC."""
    _player_helper(ctx, "vlc")

@registry.register("send")
def _c_send(ctx: Context, *args):
    """Send list to active DBus player."""
    _player_helper(ctx, "send")

@registry.register("ls", "list")
def cmd_list_players(ctx: Context, *args):
    """List active DBus media players."""
    players = ctx.dbus.get_players()
    ui.print_active_players(players, ctx.dbus.preferred_target)

@registry.register("init")
def cmd_init_player(ctx: Context, *args):
    """Set DBus target player: init <name>."""
    if not args:
        console.print("[red]Usage: init <name>[/]")
        return
    name = args[0]
    ctx.dbus.set_preference(name)
    ctx.config['preferences']['dbus_target'] = name
    save_config(ctx.config)
    console.print(f"[green]✔ Target set: {name}[/]")

# --- Playlist IO ---

@registry.register("save")
def cmd_save(ctx: Context, *args):
    """Save playlist: save <filename>."""
    if not ctx.play_list:
        console.print("[yellow]⚠️ Playlist empty.[/]")
        return
    if not args:
        console.print("[red]Usage: save <name>[/]")
        return
    
    fname = args[0].strip()
    if not fname.endswith(".txt"): fname += ".txt"
    fpath = os.path.join(PLAYLIST_DIR, fname)
    
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(f"# Saved Playlist: {fname}\n{SEPARATOR}\n")
            for t in ctx.play_list: f.write(f"{t['name']}\n")
        console.print(f"[green]✅ Saved to: {fname}[/]")
    except Exception as e:
        console.print(f"[red]❌ Save failed: {e}[/]")

@registry.register("load")
def cmd_load(ctx: Context, *args):
    """Load playlist from file."""
    target_file = None
    if args:
        # Load Direct
        raw = args[0].strip().strip('"')
        if not raw.endswith(".txt"): raw += ".txt"
        if os.path.exists(raw): target_file = raw
        elif os.path.exists(os.path.join(PLAYLIST_DIR, raw)): target_file = os.path.join(PLAYLIST_DIR, raw)
        else:
            console.print(f"[red]❌ File not found: {raw}[/]")
            return
    else:
        # Load Menu
        txts = glob.glob(os.path.join(PLAYLIST_DIR, "*.txt"))
        if not txts:
            console.print("[red]No playlists found.[/]")
            return
        sel = questionary.select("Select Playlist:", choices=[os.path.basename(f) for f in txts]).ask()
        if not sel: return
        target_file = os.path.join(PLAYLIST_DIR, sel)
    
    # Process
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
            if SEPARATOR not in content: content = f"{SEPARATOR}\n{content}"
            pl, _ = ctx.aidj.parse_raw_playlist(content, source="User")
            if pl:
                _update_playlist_and_trigger(ctx, pl, None, f"File: {os.path.basename(target_file)}")
            else:
                console.print("[yellow]⚠️ No valid tracks found.[/]")
    except Exception as e:
        console.print(f"[red]❌ Load failed: {e}[/]")
