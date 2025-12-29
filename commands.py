import os
import json
import random
import time
import glob
import dbus
import re
import requests 
from rich.live import Live
from rich.align import Align
from rich.panel import Panel
import questionary
from rapidfuzz import process, fuzz
from config import save_config, PLAYLIST_DIR, SEPARATOR, LANGUAGE, LYRICS_DIR, NCM_BASE_URL
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

@registry.register("ls", "players")
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

@registry.register("rm", "del", "remove")
def cmd_remove(ctx: Context, *args):
    """Remove song(s): rm <index> (e.g. 'rm 1')."""
    if not ctx.play_list:
        console.print("[yellow]⚠️ Playlist is empty.[/]")
        return

    if not args or not args[0].isdigit():
        console.print("[red]Usage: rm <index> (1-based)[/]")
        return

    idx = int(args[0]) - 1
    if 0 <= idx < len(ctx.play_list):
        removed = ctx.play_list.pop(idx)
        ui.print_action_feedback(f"Removed: [bold]{removed['name']}[/]")
        # 只有当删除了东西，才打印新的列表，或者你可以选择只打印 feedback
        ui.print_playlist(ctx.play_list, ctx.aidj.metadata, "Updated List")
    else:
        console.print(f"[red]❌ Index out of range (1-{len(ctx.play_list)}).[/]")

@registry.register("add", "insert")
def cmd_add(ctx: Context, *args):
    """Add song manually: add <song name>."""
    if not args:
        console.print("[red]Usage: add <song name search>[/]")
        return

    query = " ".join(args)
    all_keys = list(ctx.aidj.music_paths.keys())

    # 模糊搜索库
    result = process.extractOne(query, all_keys, scorer=fuzz.token_sort_ratio)

    if result and result[1] > 60:
        name = result[0]
        # 检查是否已存在
        if any(t['name'] == name for t in ctx.play_list):
            console.print(f"[yellow]⚠️ '{name}' is already in the playlist.[/]")
            return

        ctx.play_list.append({"name": name, "path": ctx.aidj.music_paths[name]})
        ui.print_action_feedback(f"Added: [bold]{name}[/]")
        # 自动滚动到最后一行显示
        ui.print_playlist(ctx.play_list[-3:], ctx.aidj.metadata, "Added (Showing last 3)")
    else:
        console.print(f"[red]❌ Song '{query}' not found in library.[/]")

@registry.register("mv", "move")
def cmd_move(ctx: Context, *args):
    """Move song: mv <from> <to> (e.g. 'mv 5 1' moves 5th song to top)."""
    if not ctx.play_list: return

    if len(args) < 2 or not (args[0].isdigit() and args[1].isdigit()):
        console.print("[red]Usage: mv <from_idx> <to_idx>[/]")
        return

    src = int(args[0]) - 1
    dst = int(args[1]) - 1
    max_len = len(ctx.play_list)

    if 0 <= src < max_len and 0 <= dst < max_len:
        item = ctx.play_list.pop(src)
        ctx.play_list.insert(dst, item)
        ui.print_action_feedback(f"Moved '{item['name']}' to #{dst+1}")
        ui.print_playlist(ctx.play_list, ctx.aidj.metadata, "Reordered")
    else:
        console.print("[red]❌ Index out of range.[/]")

@registry.register("swap", "sw")
def cmd_swap(ctx: Context, *args):
    """Swap two songs: swap <idx1> <idx2>."""
    if len(args) < 2 or not (args[0].isdigit() and args[1].isdigit()):
        console.print("[red]Usage: swap <idx1> <idx2>[/]")
        return

    i1, i2 = int(args[0]) - 1, int(args[1]) - 1
    L = ctx.play_list

    if 0 <= i1 < len(L) and 0 <= i2 < len(L):
        L[i1], L[i2] = L[i2], L[i1]
        ui.print_action_feedback(f"Swapped #{i1+1} and #{i2+1}")
        ui.print_playlist(ctx.play_list, ctx.aidj.metadata, "Swapped")
    else:
        console.print("[red]❌ Index out of range.[/]")

@registry.register("shuffle", "mix")
def cmd_shuffle(ctx: Context, *args):
    """Shuffle the current playlist."""
    if not ctx.play_list: return
    random.shuffle(ctx.play_list)
    ui.print_action_feedback("Playlist shuffled locally.")
    ui.print_playlist(ctx.play_list, ctx.aidj.metadata, "Shuffled")

@registry.register("reverse", "rev")
def cmd_reverse(ctx: Context, *args):
    """Reverse the playlist order."""
    if not ctx.play_list: return
    ctx.play_list.reverse()
    ui.print_action_feedback("Playlist reversed.")
    ui.print_playlist(ctx.play_list, ctx.aidj.metadata, "Reversed")

@registry.register("dedup", "unique")
def cmd_dedup(ctx: Context, *args):
    """Remove duplicate songs from playlist."""
    if not ctx.play_list: return

    seen = set()
    new_list = []
    for item in ctx.play_list:
        if item['name'] not in seen:
            new_list.append(item)
            seen.add(item['name'])

    removed_count = len(ctx.play_list) - len(new_list)
    ctx.play_list = new_list

    if removed_count > 0:
        ui.print_action_feedback(f"Removed {removed_count} duplicates.")
        ui.print_playlist(ctx.play_list, ctx.aidj.metadata, "Cleaned")
    else:
        console.print("[yellow]✨ No duplicates found.[/]")

@registry.register("clear", "cls")
def cmd_clear(ctx: Context, *args):
    """Clear the playlist."""
    if not ctx.play_list: return
    if questionary.confirm("Clear list?").ask():
        ctx.play_list = []
        ui.print_action_feedback("Playlist cleared.", "yellow")

@registry.register("top")
def cmd_top(ctx: Context, *args):
    """Move a specific song to the top: top <index>."""
    if not args or not args[0].isdigit(): return
    cmd_move(ctx, args[0], "1") # 复用 mv 命令逻辑

@registry.register("view", "list", "pl", "queue")
def cmd_view(ctx: Context, *args):
    """View current playlist: view / list / pl."""
    if not ctx.play_list:
        console.print("[yellow]⚠️ Playlist is empty.[/]")
        return
    # 复用 ui.py 里的打印函数
    ui.print_playlist(ctx.play_list, ctx.aidj.metadata, "Current Queue")

def _parse_lrc(lrc_text):
    """解析 LRC 文本为 [(seconds, text), ...]"""
    if not lrc_text: return []
    lines = []
    # 匹配 [mm:ss.xx] 或 [mm:ss.xxx]
    pattern = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)')
    for line in lrc_text.split('\n'):
        match = pattern.search(line)
        if match:
            m, s, ms_str = int(match.group(1)), int(match.group(2)), match.group(3)
            ms = int(ms_str) * (10 if len(ms_str) == 2 else 1)
            total = m * 60 + s + ms / 1000.0
            text = match.group(4).strip()
            if text: lines.append((total, text))
    lines.sort(key=lambda x: x[0])
    return lines

def _get_lyrics_data(title, artist):
    """获取歌词流程：文件缓存 -> API -> 文件保存"""
    if not os.path.exists(LYRICS_DIR): os.makedirs(LYRICS_DIR)

    safe_name = re.sub(r'[\\/*?:"<>|]', "", f"{title} - {artist}".strip(" -"))
    fpath = os.path.join(LYRICS_DIR, f"{safe_name}.lrc")

    # 1. 读缓存
    if os.path.exists(fpath):
        with open(fpath, 'r', encoding='utf-8') as f:
            return _parse_lrc(f.read())

    # 2. 调 API
    try:
        kw = f"{title} {artist}".strip()
        # 搜索
        s_res = requests.get(f"{NCM_BASE_URL}/search", params={"keywords": kw, "limit": 1}, timeout=2).json()

        raw = "[00:00.00] 暂无歌词"
        if s_res.get('code') == 200 and s_res['result']['songCount'] > 0:
            sid = s_res['result']['songs'][0]['id']
            # 获取
            l_res = requests.get(f"{NCM_BASE_URL}/lyric", params={"id": sid}, timeout=2).json()
            if l_res.get('code') == 200:
                raw = l_res.get('lrc', {}).get('lyric', "")
                if not raw: raw = "[00:00.00] 纯音乐或无歌词"

        # 3. 写缓存
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(raw)
        return _parse_lrc(raw)
    except Exception:
        return []

# --- Lyrics Command ---
@registry.register("dlyrics", "lrc")
def cmd_dlyrics(ctx: Context, *args):
    """
    Sync lyrics from DBus player with Rich Markdown rendering.
    Usage: dlyrics [player_name] [immersive]
    Example: 'dlyrics immersive', 'dlyrics spotify immersive'
    """
    import bisect
    from rich.markdown import Markdown
    from rich.align import Align # 确保引入 Align

    # --- 0. 参数解析 (处理 immersive) ---
    args_list = [str(a).lower() for a in args]
    is_immersive = "immersive" in args_list

    # 移除 'immersive' 关键字，剩下的作为播放器名称筛选
    clean_args = [a for a in args if str(a).lower() != "immersive"]

    # --- 配置区域 ---
    SYNC_OFFSET = 0

    # --- 1. 连接 DBus ---
    try:
        bus = dbus.SessionBus()
    except Exception as e:
        console.print(f"[red]❌ DBus error: {e}[/]")
        return

    # 确定目标播放器
    target = None
    if clean_args:
        target = clean_args[0]
    else:
        current_pref = ctx.config['preferences'].get('dbus_target')
        active_services = [n for n in bus.list_names() if n.startswith("org.mpris.MediaPlayer2")]
        if current_pref and any(current_pref in s for s in active_services):
            target = next(s for s in active_services if current_pref in s)
        elif active_services:
            target = active_services[0]

    if not target:
        console.print("[red]❌ No active MPRIS player found.[/]")
        return

    try:
        player = bus.get_object(target, "/org/mpris/MediaPlayer2")
        props = dbus.Interface(player, "org.freedesktop.DBus.Properties")
        props.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus")
    except Exception as e:
        console.print(f"[red]❌ Failed to connect to {target}: {e}[/]")
        return

    # 如果不是沉浸模式，打印提示；沉浸模式下直接进界面
    if not is_immersive:
        console.print(f"[green]🔗 Linked to: {target} (Ctrl+C to quit)[/]")

    # --- 2. 主循环 ---
    last_key = None
    timeline = []
    time_keys = []

    # screen=is_immersive: True 时开启全屏独占模式（自动清空控制台）
    # transient=True: 退出时清除 Live 输出（保持终端干净）
    with Live(console=console, refresh_per_second=10, screen=is_immersive, transient=True) as live:
        try:
            while True:
                try:
                    # 获取状态
                    try:
                        meta = props.Get("org.mpris.MediaPlayer2.Player", "Metadata")
                        status = str(props.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus"))
                    except dbus.exceptions.DBusException:
                        err_panel = Panel("[red]Player disconnected.[/]", title="Connection Lost")
                        # 沉浸模式下居中显示错误
                        if is_immersive: err_panel = Align(err_panel, align="center", vertical="middle")
                        live.update(err_panel)
                        time.sleep(2)
                        break

                    # 提取信息
                    title = str(meta.get("xesam:title", "Unknown Title"))
                    artist_list = meta.get("xesam:artist", ["Unknown Artist"])
                    artist = str(artist_list[0]) if (isinstance(artist_list, (list, dbus.Array)) and len(artist_list) > 0) else str(artist_list)
                    curr_key = f"{title}-{artist}"

                    # 切歌逻辑
                    if curr_key != last_key:
                        loading_panel = Panel(f"Fetching: {title}...", title="Loading")
                        if is_immersive: loading_panel = Align(loading_panel, align="center", vertical="middle")
                        live.update(loading_panel)

                        last_key = curr_key
                        try:
                            timeline = _get_lyrics_data(title, artist)
                            time_keys = [x[0] for x in timeline]
                        except Exception:
                            timeline = []
                            time_keys = []

                    # 暂停状态
                    if status != "Playing":
                        pause_panel = Panel(
                            Align.center(f"[yellow]⏸ Paused[/]\n\n[bold]{title}[/]\n{artist}"),
                            title="Status", border_style="yellow", padding=(1, 4)
                        )
                        if is_immersive: pause_panel = Align(pause_panel, align="center", vertical="middle")
                        live.update(pause_panel)
                        time.sleep(0.2)
                        continue

                    # 同步逻辑
                    pos = props.Get("org.mpris.MediaPlayer2.Player", "Position") / 1_000_000
                    idx = bisect.bisect_right(time_keys, pos + SYNC_OFFSET) - 1

                    # 渲染内容
                    if not timeline:
                        md_content = f"\n\n[dim]No lyrics found for:[/]\n[bold]{title}[/]\n[dim]{artist}[/]"
                        render_obj = Align.center(md_content)
                    else:
                        current_idx = max(0, min(idx, len(timeline) - 1))
                        # 沉浸模式显示行数稍微多一点点，普通模式紧凑一点
                        window_pre = 3 if is_immersive else 2
                        window_post = 5 if is_immersive else 5

                        start_idx = max(0, current_idx - window_pre)
                        end_idx = min(len(timeline), current_idx + window_post)

                        md_str = ""
                        for i in range(start_idx, end_idx):
                            t_sec, text = timeline[i]
                            if not text.strip(): continue

                            if i == current_idx:
                                md_str += f"\n# 🎵 **{text}** 🎵\n"
                            else:
                                md_str += f"{text}\n"

                        render_obj = Align.center(Markdown(md_str, justify="center"))

                    # 构建面板
                    main_panel = Panel(
                        render_obj,
                        title=f"Playing: {title} ({pos:.1f}s)",
                        border_style="green",
                        padding=(1, 2) if not is_immersive else (2, 4), # 沉浸模式留白多一点
                        subtitle="[dim]Press Ctrl+C to exit[/]" if is_immersive else None
                    )

                    # 如果是沉浸模式，将 Panel 垂直居中
                    if is_immersive:
                        final_view = Align(main_panel, align="center", vertical="middle")
                    else:
                        final_view = main_panel

                    live.update(final_view)
                    time.sleep(0.05)

                except KeyboardInterrupt:
                    raise
                except Exception:
                    pass

        except KeyboardInterrupt:
            pass

    # 退出 Live 后，如果是 immersive，屏幕会自动切回来，无需手动 clean
    if not is_immersive:
        console.print("[yellow]👋 Lyrics mode exited.[/]")
