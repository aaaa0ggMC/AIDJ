import re
import os
import sys
import json
import time
import subprocess
import requests
import openai
import random
import glob
import shutil
from tqdm import tqdm
from rapidfuzz import process, fuzz
from rich.markdown import Markdown
from concurrent.futures import ThreadPoolExecutor
import termios
import threading
import tty

# --- Custom Modules ---
from wait_games import run_waiting_game

# --- UI & Interaction Imports ---
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.live import Live
from rich import print as rprint
import questionary
from questionary import Style

# --- Configuration Constants ---
CONFIG_PATH = "./config.json"
METADATA_PATH = "./music_metadata.json"
PLAYLIST_DIR = "./playlists"
MUSIC_EXTS = ('.mp3', '.flac', '.wav', '.m4a')
NCM_BASE_URL = "http://localhost:3000"
CFG_KEY_MF = "music_folders"

SEPARATOR = "[---SONG_LIST---]"
LANGUAGE = "简体中文"

console = Console()

# --- Vibe Assets ---
EMOJIS_MUSIC = ["🎵", "🎹", "🎸", "🎷", "🎺", "🎻", "🪕", "🥁", "🎚️", "🎤", "🎧", "📻"]
EMOJIS_VIBE = ["✨", "🌊", "🔥", "💿", "📀", "😎", "🚀", "🪐", "🍹", "🌃", "💤", "🕹️"]

# --- Helpers ---
def get_random_icon():
    return random.choice(EMOJIS_MUSIC)

def ensure_playlist_dir():
    if not os.path.exists(PLAYLIST_DIR):
        os.makedirs(PLAYLIST_DIR)
        demo_path = os.path.join(PLAYLIST_DIR, "demo.txt")
        with open(demo_path, "w", encoding="utf-8") as f:
            f.write("# Demo Playlist\nForget\nMerry Christmas Mr. Lawrence")
    return True

def load_config():
    if not os.path.exists(CONFIG_PATH):
        config = {}
    else:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                console.print(f"[bold red]❌ ERROR[/] {CONFIG_PATH} is corrupted!")
                exit(-1)

    if "preferences" not in config:
        config["preferences"] = {}

    pref_defaults = {
        "model": None,
        "verbose": False,
        "saved_trigger": None,
        "dbus_target": None
    }
    for key, val in pref_defaults.items():
        if key not in config["preferences"]:
            config["preferences"][key] = val

    if "ai_settings" not in config:
        config["ai_settings"] = {}

    ai_defaults = {
        "base_url": "https://api.deepseek.com",
        "available_models": ["deepseek-chat", "deepseek-reasoner"],
        "metadata_model": "deepseek-chat",
        "chat_model": "deepseek-chat"
    }

    modified = False
    for key, val in ai_defaults.items():
        if key not in config["ai_settings"]:
            config["ai_settings"][key] = val
            modified = True

    if not config["preferences"]["model"]:
        config["preferences"]["model"] = config["ai_settings"]["chat_model"]
        modified = True

    if modified:
        save_config(config)

    return config

def save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        console.print(f"[red]❌ Failed to save config: {e}[/]")

def load_cached_metadata():
    if not os.path.exists(METADATA_PATH):
        return {}
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}

# --- DBus Manager ---
class DBusManager:
    def __init__(self, preferred_target=None):
        self.preferred_target = preferred_target
        self.available = shutil.which("dbus-send") is not None

    def set_preference(self, target_name):
        self.preferred_target = target_name

    def _run_cmd(self, args):
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def get_players(self):
        if not self.available: return []
        cmd = ["dbus-send", "--session", "--dest=org.freedesktop.DBus", "--type=method_call", "--print-reply", "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"]
        output = self._run_cmd(cmd)
        if not output: return []
        players = []
        for line in output.split("\n"):
            match = re.search(r'"(org\.mpris\.MediaPlayer2\.[^"]+)"', line)
            if match: players.append(match.group(1))
        return players

    def get_active_player(self):
        players = self.get_players()
        if not players: return None, "No Active Players"
        target = None
        if self.preferred_target:
            target = next((p for p in players if self.preferred_target.lower() in p.lower()), None)
        if not target:
            target = next((p for p in players if "mpv" in p), None)
        if not target:
            target = players[0]
        return target, target

    def send_files(self, file_paths):
        dest, name = self.get_active_player()
        if not dest: return False, name
        count = 0
        for path in file_paths:
            uri = f"file://{path}"
            cmd = ["dbus-send", "--session", "--type=method_call", f"--dest={dest}", "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player.OpenUri", f"string:{uri}"]
            if self._run_cmd(cmd) is not None:
                count += 1
                time.sleep(0.05)
        return True, f"Sent {count} tracks to {name}"

    def control(self, command):
        dest, name = self.get_active_player()
        if not dest: return False, name
        method_map = {"next": "Next", "prev": "Previous", "play": "Play", "pause": "Pause", "toggle": "PlayPause", "stop": "Stop"}
        if command not in method_map: return False, "Unknown Command"
        cmd = ["dbus-send", "--session", "--type=method_call", f"--dest={dest}", "/org/mpris/MediaPlayer2", f"org.mpris.MediaPlayer2.Player.{method_map[command]}"]
        if self._run_cmd(cmd) is not None:
            return True, f"Executed {command} on {name}"
        return False, "Command Failed"

# --- Core Logic Functions ---
def scan_music_files(folders):
    music_files = {}
    for folder in folders:
        if not os.path.exists(folder): continue
        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(MUSIC_EXTS):
                    file_key = os.path.splitext(file)[0]
                    music_files[file_key] = os.path.join(root, file)
    return music_files

def get_song_info(client, song_info, model_name):
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "提取歌曲信息JSON: language, emotion, genre, loudness, review (20字以内)"},
                {"role": "user", "content": f"{song_info}"}
            ],
            response_format={'type': 'json_object'},
            stream=False,
            timeout=30.0
        )
        return response.choices[0].message.content
    except KeyboardInterrupt: raise
    except Exception as e:
        return None

def sync_metadata(client, targets, metadata, model_name):
    if not targets: return metadata
    console.print(f"[cyan]🚀 Syncing {len(targets)} new songs using {model_name}... (Ctrl+C to skip)[/]")
    pbar = tqdm(targets.items(), unit="song")
    try:
        for name, path in pbar:
            pbar.set_postfix_str(f"{name[:10]}...")
            try:
                res = requests.get(f"{NCM_BASE_URL}/search?keywords=\"{name}\"&limit=1", timeout=5).json()
                if res.get('code')!=200 or res['result']['songCount']==0: continue
                sid = res['result']['songs'][0]['id']
                l_res = requests.get(f"{NCM_BASE_URL}/lyric", params={"id": sid}, timeout=5).json()
                raw_lyric = l_res.get('lrc', {}).get('lyric', "暂无歌词")

                info = {"title": name, "lyrics": raw_lyric[:500]}
                resp = get_song_info(client, info, model_name)

                if resp:
                    metadata[name] = json.loads(resp)
                    with open(METADATA_PATH, "w") as f: json.dump(metadata, f, ensure_ascii=False, indent=4)
            except KeyboardInterrupt: raise
            except: continue
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Sync skipped.[/]")
    return metadata

class DJSession:
    def __init__(self, client, metadata, music_paths, config):
        self.client = client
        self.metadata = metadata
        self.music_paths = music_paths
        self.config = config
        self.chat_history = []
        self.turn_count = 0
        self.played_songs = set()

    def refresh(self, clear_history=False):
        self.played_songs.clear()
        if clear_history:
            self.chat_history = []
            self.turn_count = 0
            console.print("[yellow]🧹 Cleared History[/]")
        else:
            console.print("[yellow]🧹 Cleared Played Songs[/]")

    def _format_library(self):
        lines = []
        available = set(self.metadata.keys()) & set(self.music_paths.keys())
        for name in list(available):
            info = self.metadata[name]
            if isinstance(info, dict):
                lines.append(f"- {name}: {info.get('genre','Pop')}, {info.get('emotion','Neutral')}")
        return "\n".join(lines)

    def parse_raw_playlist(self, raw_text, source="AI"):
        playlist_names = []
        intro_text = ""
        is_verbose = self.config['preferences']['verbose']

        if SEPARATOR in raw_text:
            parts = raw_text.split(SEPARATOR)
            intro_text = parts[0].strip()
            raw_list_block = parts[1]
            if is_verbose: console.print(f"[dim]✅ Separator found. Parsing list...[/]")
        else:
            if is_verbose and source == "AI":
                console.print(f"[dim]ℹ️ No separator found. Treating as pure conversation.[/]")
            intro_text = raw_text.strip()
            raw_list_block = ""

        lines = [l.strip() for l in raw_list_block.split('\n') if l.strip()]
        valid_keys = list(set(self.metadata.keys()) & set(self.music_paths.keys()))

        for line in lines:
            if line.startswith("#"): continue
            clean = line.replace('"', '').replace("'", "").strip()
            if len(clean) < 2: continue

            match = None
            result = process.extractOne(
                clean, valid_keys, scorer=fuzz.token_sort_ratio, score_cutoff=80
            )

            if result:
                match_name = result[0]
                if is_verbose: console.print(f"[dim]🔍 Match: {clean} -> [green]{match_name}[/][/]")
                match = match_name

            if match:
                playlist_names.append(match)
            else:
                if is_verbose and SEPARATOR in raw_text:
                     console.print(f"[dim]❌ Ignored line: {clean}[/]")

        playlist_names = list(dict.fromkeys(playlist_names))
        playlist = []
        for name in playlist_names:
            if source == "AI": self.played_songs.add(name)
            playlist.append({"name": name, "path": self.music_paths[name]})

        return playlist, intro_text

    def next_step(self, user_request):
        # --- 1. 配置与状态更新 ---
        self.turn_count += 1
        model = self.config['preferences']['model']
        is_verbose = self.config['preferences']['verbose']

        if is_verbose: console.print(f"[dim]🤖 Thinking with {model}...[/]")

        # --- 2. 构建系统指令 (System Prompt - Optimized) ---
        # 使用“协议模式”告诉AI，它正在通过一个严格的管道传输数据
        base_prompt = base_prompt = f"""
### ROLE DEFINITION
You are a **charismatic, knowledgeable, and expressive AI Radio Host**.
Your goal is not just to list songs, but to **curate an experience**.
-   **Personality:** Passionate, poetic, slightly "hyped" or "deep" (depending on the mood), and vibe-focused.
-   **Rule:** BE EXPRESSIVE. Do NOT give short, robotic responses like "Here is your list."
-   **Method:** Weave a narrative. Talk about the *texture* of the sound, the *emotion* of the artists, and *why* these songs fit the moment. Create a "scene" for the listener.

### DATA SOURCE (CRITICAL)
You are provided with a **Music Library**.
-   **RESTRICTION:** You can ONLY select songs that exist EXACTLY in the provided Library.
-   **PROHIBITION:** Do NOT hallucinate songs. Do NOT translate song titles. Do NOT fix typos in the library keys. Use the keys exactly as they appear.
-   If no songs in the library fit the mood, just chat (expressively!) and DO NOT output the separator.

### OUTPUT PROTOCOL
Your output is parsed by a Python script. You must strictly follow this structure:

[Part 1: The Intro]
(Content: A rich, paragraph-length DJ commentary. Use Markdown bolding for emphasis and emojis to set the mood. Talk about the genre, the instruments, or the feeling.)

{SEPARATOR}

[Part 2: The Payload]
(Content: Exact song keys from the Library. Hidden from the user, executed by system.)
(Format: One key per line. NO numbering. NO markdown bullets. NO extra text.)

### EXAMPLE INTERACTION
**Library:** ['Bohemian Rhapsody', 'Imagine', 'Billie Jean']
**User:** "Play something sad."
**Your Output:**
Oh, I feel that heavy energy in the air tonight. 🌧️ Sometimes we just need to let the tears flow to heal, right? I've pulled a track that is the definition of raw soul—it's just a piano and a voice, stripping away all the pretense to touch the core of humanity. Let's slow down the world for a moment and just *listen*. 🎹💔
{SEPARATOR}
Imagine
"""

        # --- 3. 注入上下文 (Context Injection) ---
        # 适时注入 Library，防止上下文过长，但保证 AI 随时能看到清单
        if self.turn_count == 1 or self.turn_count % 5 == 0:
            # 强化 Library 的边界感
            library_str = self._format_library()
            system_content = f"{base_prompt}\n\n### CURRENT MUSIC LIBRARY (Exact Keys Only):\n{library_str}"

            self.chat_history.append({"role": "system", "content": system_content})
            if is_verbose: console.print("[dim]🔄 Context refreshed with strict library constraints.[/]")

        # --- 4. 构建用户请求 (User Message) ---
        # 在这里再次强调“封闭集合”概念
        forbidden_list = ', '.join(list(self.played_songs)) if self.played_songs else "None"

        full_req = (
            f"User Request: \"{user_request}\"\n"
            f"Constraint: Don't repeat these songs: [{forbidden_list}]\n"
            f"Language Rule: Detect the language used in the 'User Request'. The [Intro] section MUST be written in that EXACT SAME language. (e.g. If user asks in Chinese, reply in Chinese).\n"
            f"Instruction: Check the Library provided in System context. "
            f"If matches found, output Intro + {SEPARATOR} + SongKeys. "
            f"If no matches, just Intro."
        )
        self.chat_history.append({"role": "user", "content": full_req})

        # --- 5. 🎮 交互式等待模式 (Streaming + Game) ---

        stop_event = threading.Event()
        ai_status = {'count': 0}  # 共享状态：字数统计

        def ask_ai_streaming():
            full_content = ""
            try:
                # 开启流式 stream=True
                stream = self.client.chat.completions.create(
                    model=model,
                    messages=self.chat_history,
                    timeout=180.0,
                    stream=True
                )

                for chunk in stream:
                    # [修复点 1] 必须先检查 choices 列表是否非空
                    # 防止部分心跳包或结束包为空导致 IndexError
                    if not chunk.choices:
                        continue

                    # [修复点 2] 获取 delta
                    delta = chunk.choices[0].delta

                    # [修复点 3] 确保 content 存在且不为 None
                    if getattr(delta, 'content', None):
                        content = delta.content
                        full_content += content

                        # 更新共享计数器，游戏线程会读取这个值
                        ai_status['count'] = len(full_content)

                return full_content

            except Exception as e:
                return e
            finally:
                # 无论成功失败，通知游戏停止
                stop_event.set()

        # 准备终端环境
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        result = None

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(ask_ai_streaming)
            try:
                # 开启游戏模式 (无回显 cbreak 模式)
                tty.setcbreak(fd)

                # 启动游戏，传入 stop_event 和 ai_status
                run_waiting_game(stop_event, ai_status)

            except KeyboardInterrupt:
                console.print("\n[dim]⚠️ Interrupted.[/]")
                stop_event.set()
                return [], ""
            finally:
                # 恢复终端设置，防止退出后终端乱码
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                try: termios.tcflush(sys.stdin, termios.TCIFLUSH)
                except: pass

            result = future.result()

        # --- 6. 结果处理 ---
        if isinstance(result, Exception):
            err_msg = str(result)
            if "timeout" in err_msg.lower():
                console.print(f"[red]⏳ AI Request Timed Out (180s)[/]")
            else:
                console.print(f"[red]❌ API Error:[/]{err_msg}")
            return [], ""

        # 流式返回的已经是完整字符串了
        raw = result

        # 清洗 <think> 标签 (针对 DeepSeek R1 等推理模型)
        clean_content = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        if not clean_content: clean_content = raw

        if is_verbose:
            console.print(Panel(raw, title="Raw AI Output (With Thoughts)", border_style="dim"))

        # 存入历史
        self.chat_history.append({"role": "assistant", "content": clean_content})

        # 解析并返回
        return self.parse_raw_playlist(clean_content, source="AI")

def execute_player_command(command, playlist, dbus_manager):
    if command in ["next", "prev", "play", "pause", "toggle", "stop"]:
        ok, msg = dbus_manager.control(command)
        color = "green" if ok else "red"
        console.print(f"[{color}]📡 DBus: {msg}[/]")
        return

    if not playlist and command in ["mpv", "vlc", "send"]:
        console.print("[red]❌ No playlist cached! Use 'p <text>' first.[/]")
        return

    paths = [item['path'] for item in playlist] if playlist else []

    if command == "send":
        if not dbus_manager.available:
            console.print("[red]❌ 'dbus-send' missing[/]")
            return
        ok, msg = dbus_manager.send_files(paths)
        color = "green" if ok else "red"
        console.print(f"[{color}]📡 DBus: {msg}[/]")
    elif command == "mpv":
        console.print(f"[green]🔊 MPV ({len(playlist)} trks)[/]")
        subprocess.Popen(['mpv', '--force-window', '--geometry=600x600'] + paths,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True)
    elif command == "vlc":
        console.print(f"[green]🟠 VLC ({len(playlist)} trks)[/]")
        subprocess.Popen(['vlc', '--one-instance', '--playlist-enqueue'] + paths,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True)

def main():
    config = load_config()
    secrets = config.get("secrets", {})
    ai_settings = config.get("ai_settings", {})

    # 配置读取
    api_key = secrets.get("api_key") or secrets.get("deepseek", "")
    base_url = ai_settings.get("base_url", "https://api.deepseek.com")

    ds_client = openai.OpenAI(api_key=api_key, base_url=base_url)

    saved_dbus_target = config['preferences'].get('dbus_target')
    dbus_manager = DBusManager(preferred_target=saved_dbus_target)

    musics = scan_music_files(config.get(CFG_KEY_MF, []))
    metadata = load_cached_metadata()

    missing_metadata = {k:v for k,v in musics.items() if k not in metadata}
    if missing_metadata:
        meta_model = ai_settings.get("metadata_model", "deepseek-chat")
        metadata = sync_metadata(ds_client, missing_metadata, metadata, meta_model)

    ensure_playlist_dir()
    aidj = DJSession(ds_client, metadata, musics, config)

    console.print(Panel.fit(
        f"[bold cyan]          AI DJ SYSTEM v3.5       [/]\n"
        f"[dim]Endpoint: {base_url}[/]\n"
        f"[dim]Model: {config['preferences']['model']}[/]",
        title="✨ System Ready ✨", border_style="magenta"
    ))

    play_list = []
    style = Style([('qmark', 'fg:#673ab7 bold'),('question', 'bold'),('answer', 'fg:#f44336 bold')])

    while True:
        try:
            current_trigger = config['preferences'].get('saved_trigger')
            prefix = f"[⚡ {current_trigger}] " if current_trigger else ""
            label = f"{prefix}AIDJ >"

            user_input = questionary.text(label, qmark="🎤", style=style).ask()
            if user_input is None:
                console.print("[red]👋 Bye![/]")
                break

            raw_input = user_input.strip()
            if not raw_input: continue

            parts = raw_input.split(" ", 1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            if cmd in ["exit", "quit", "q"]:
                console.print("[bold red]👋 See ya![/]")
                break

            elif cmd in ["status", "check", "conf"]:
                t = Table(title="⚙️ System Status")
                t.add_column("Setting", style="cyan")
                t.add_column("Value", style="yellow")
                t.add_row("API Endpoint", base_url)
                t.add_row("Current Model", config['preferences']['model'])
                t.add_row("Metadata Model", ai_settings.get("metadata_model", "N/A"))
                t.add_row("Verbose Mode", str(config['preferences']['verbose']))
                t.add_row("Auto Trigger", str(config['preferences']['saved_trigger'] or "OFF"))
                t.add_row("DBus Target", str(config['preferences']['dbus_target'] or "Auto"))
                t.add_row("Playlist Cache", f"{len(play_list)} tracks")
                console.print(t)
                continue

            elif cmd in ["help", "?"]:
                t = Table(title="📜 Command Reference")
                t.add_column("Cmd", style="cyan")
                t.add_column("Desc", style="white")

                # --- Core ---
                t.add_row("p <text>", "Generate playlist (AI)")
                t.add_row("r <num>", "Random <num> songs (Direct)")
                t.add_row("pr <num>", "Random <num> songs (AI Curated)")
                t.add_row("show <song>", "Inspect metadata")
                t.add_row("model", "Switch AI Model")

                # --- DBus / Player Control (Expanded) ---
                t.add_row("play / pause", "Resume / Pause")
                t.add_row("toggle", "Play/Pause Toggle")
                t.add_row("stop", "Stop playback")
                t.add_row("next / n", "Next track")
                t.add_row("prev / b", "Previous track")
                t.add_row("send", "Send list to DBus player")
                t.add_row("init", "init DBus player")
                t.add_row("mpv / vlc", "Play locally (Spawn process)")

                # --- Playlist Files ---
                t.add_row("save <name>", "Save current playlist")
                t.add_row("load [name]", "Load playlist (Menu or Direct)")

                # --- System ---
                t.add_row("auto <cmd>", "Set persistent trigger")
                t.add_row("status", "Show system status")
                t.add_row("quit", "Exit")

                console.print(t)
                continue

            elif cmd == "verbose":
                curr = config['preferences']['verbose']
                config['preferences']['verbose'] = not curr
                save_config(config)
                aidj.config = config
                console.print(f"[green]📝 Verbose Mode: {not curr}[/]")
                continue

            elif cmd == "refresh":
                aidj.refresh(clear_history=False)
                continue

            elif cmd == "reset":
                aidj.refresh(clear_history=True)
                continue

            elif cmd == "auto":
                if not args:
                    console.print(f"[yellow]Current Trigger: {config['preferences'].get('saved_trigger') or 'None'}[/]")
                elif args.lower() in ["off", "none", "stop"]:
                    config['preferences']['saved_trigger'] = None
                    save_config(config)
                    console.print("[green]⚡ Auto Trigger Disabled[/]")
                else:
                    target = args
                    config['preferences']['saved_trigger'] = target
                    save_config(config)
                    console.print(f"[green]⚡ Auto Trigger Set (Persistent): {target}[/]")
                continue

            elif cmd == "show":
                if not args:
                    console.print("[red]Usage: show <song name>[/]")
                    continue
                query = args
                keys = list(aidj.metadata.keys())
                result = process.extractOne(query, keys, scorer=fuzz.token_sort_ratio)
                if not result or result[1] < 60:
                    console.print(f"[red]❌ Song '{query}' not found in metadata cache.[/]")
                    continue
                match_name = result[0]
                data = aidj.metadata[match_name]
                t = Table(title=f"ℹ️ Metadata: [bold green]{match_name}[/]", border_style="blue")
                t.add_column("Field", style="bold cyan", justify="right")
                t.add_column("Value", style="white", overflow="fold")
                if isinstance(data, dict):
                    for k in sorted(data.keys()):
                        v = data[k]
                        if k == "lyrics":
                            val_str = str(v)[:100].replace("\n", " ") + "... (truncated)"
                        elif isinstance(v, list):
                            val_str = ", ".join(str(x) for x in v)
                        elif isinstance(v, dict):
                            val_str = json.dumps(v, ensure_ascii=False)
                        else:
                            val_str = str(v)
                        t.add_row(k, val_str)
                else:
                    t.add_row("Raw Data", str(data))
                console.print(t)
                continue

            # --- Unified Generator Logic (r, pr, p) ---
            elif cmd in ["r", "pr", "p", "prompt", "gen"]:
                # 1. 初始化变量
                pl = None
                intro = None
                target_cmd = cmd # 用于后续区分 Table 标题

                # --- 分支 A: 随机类 (r, pr) ---
                if cmd in ["r", "pr"]:
                    if not args or not args.isdigit():
                        console.print("[red]Usage: r/pr <number> (e.g., pr 20)[/]")
                        continue

                    count = int(args)
                    all_keys = list(aidj.music_paths.keys())

                    if count <= 0:
                        console.print("[yellow]Please select at least 1 song.[/]")
                        continue

                    # 限制最大数量，防止 Token 爆炸
                    if count > 50:
                        count = 50
                        console.print(f"[dim]⚠️ Capped at 50 songs.[/]")
                    if count > len(all_keys):
                        count = len(all_keys)

                    # 核心：真正随机抽取
                    random_keys = random.sample(all_keys, count)

                    if cmd == "r":
                        # 纯随机：直接构建 playlist，没有 intro
                        pl = [{"name": k, "path": aidj.music_paths[k]} for k in random_keys]
                        intro = None
                        console.print(f"[green]🎲 Randomly selected {len(pl)} tracks.[/]")

                    elif cmd == "pr":
                        # AI 策展随机：构建 Prompt 并复用 next_step
                        min_keep = max(1, count // 2)
                        candidates_str = json.dumps(random_keys, ensure_ascii=False)

                        system_req = (
                            f"System Request: I have randomly picked {count} candidate songs from the library: {candidates_str}.\n"
                            f"Task: Curate a coherent playlist from THIS SPECIFIC LIST.\n"
                            f"Rules:\n"
                            f"1. Sort them to create a good flow (vibe/tempo/genre).\n"
                            f"2. You act as a filter: Remove songs that completely clash with the majority vibe.\n"
                            f"3. [IMPORTANT] You MUST keep at least {min_keep} songs (Current candidates: {count}).\n"
                            f"4. Do NOT include any song not in the candidate list.\n"
                            f"5. [LANGUAGE] You MUST write the response in {LANGUAGE}.\n"
                            f"6. [FORMAT] Explain your selection logic (why you chose these songs, what's the vibe) entirely in the [Intro] section BEFORE the separator. The section after the separator must contain ONLY the song keys."
                        )
                        # 复用核心 AI 逻辑
                        pl, intro = aidj.next_step(system_req)

                # --- 分支 B: 普通 AI 生成 (p) ---
                else: # p, prompt, gen
                    if not args:
                        console.print("[red]Usage: p <your request>[/]")
                        continue
                    # 复用核心 AI 逻辑
                    pl, intro = aidj.next_step(args)


                # --- 统一展示逻辑 (复用你提供的代码) ---

                # 1. 打印 DJ Intro (如果有)
                if intro:
                    # 使用正则做最后一道保险，防止残留
                    clean_intro = re.sub(r'<think>.*?</think>', '', intro, flags=re.DOTALL).strip()
                    if clean_intro:
                        md_content = Markdown(clean_intro)
                        console.print(Panel(
                            md_content,
                            title="💬 DJ Says",
                            border_style="bold magenta",
                            padding=(1, 2)
                        ))

                # 2. 检查列表是否为空
                if not pl:
                    # 如果 AI 没返回列表，但对于 'r' 命令这不可能发生，主要是防 'p/pr'
                    if not intro and cmd != 'r':
                        console.print("[yellow]No matches.[/]")
                    elif cmd == 'pr':
                         # pr 失败时的回退机制（可选）
                         console.print("[yellow]AI curation failed, falling back to raw selection.[/]")
                         pl = [{"name": k, "path": aidj.music_paths[k]} for k in random_keys]
                    else:
                        continue

                # 3. 更新全局播放列表
                play_list = pl

                # 4. 打印表格
                title_map = {"r": "Random Selection", "pr": "AI Curated Random", "p": "AI Generated"}
                table_title = f"Playlist ({len(pl)}) - {title_map.get(target_cmd, 'List')}"

                t = Table(show_header=True, title=table_title, show_lines=True)
                t.add_column("Track", style="bold green", no_wrap=True)
                t.add_column("Language", style="cyan")
                t.add_column("Genre", style="magenta")
                t.add_column("Emotion", style="yellow")
                t.add_column("Loudness", style="dim")

                for item in pl:
                    name = item['name']
                    info = aidj.metadata.get(name, {})
                    def safe_fmt(val):
                        if val is None: return "-"
                        if isinstance(val, list): return ", ".join(str(x) for x in val)
                        return str(val)
                    t.add_row(name, safe_fmt(info.get('language')), safe_fmt(info.get('genre')), safe_fmt(info.get('emotion')), safe_fmt(info.get('loudness')))

                console.print(t)

                # 5. 自动执行 Trigger
                current_trigger = config['preferences'].get('saved_trigger')
                if current_trigger:
                    console.print(f"[yellow]⚡ Auto-Executing: {current_trigger}[/]")
                    execute_player_command(current_trigger, play_list, dbus_manager)

                continue

            elif cmd in ["mpv", "vlc", "send"]:
                execute_player_command(cmd, play_list, dbus_manager)
                continue

            elif cmd in ["next", "n", "prev", "stop", "pause", "play", "toggle"]:
                execute_player_command(cmd, None, dbus_manager)
                continue

            elif cmd in ["ls", "list"]:
                players = dbus_manager.get_players()
                t = Table(title="📡 Active Players")
                t.add_column("Name")
                for p in players:
                    marker = " [green](Target)[/]" if dbus_manager.preferred_target and dbus_manager.preferred_target in p else ""
                    t.add_row(f"{p}{marker}")
                console.print(t)
                continue

            elif cmd == "init":
                if not args: console.print("[red]Usage: init <name>[/]")
                else:
                    dbus_manager.set_preference(args)
                    config['preferences']['dbus_target'] = args
                    save_config(config)
                    console.print(f"[green]✔ Target set: {args}[/]")
                continue

            elif cmd == "model":
                available_models = ai_settings.get("available_models", ["deepseek-chat"])
                current_model = config['preferences']['model']
                sel = questionary.select("Switch Model:", choices=available_models, default=current_model).ask()
                if sel:
                    config['preferences']['model'] = sel
                    save_config(config)
                    aidj.config = config
                    console.print(f"[green]🧠 Model Switched to: {sel}[/]")
                continue

            # --- Playlist File Management ---
            elif cmd == "save":
                if not play_list:
                    console.print("[yellow]⚠️ Current playlist is empty. Nothing to save.[/]")
                    continue
                if not args:
                    console.print("[red]Usage: save <filename>[/]")
                    continue

                filename = args.strip()
                if not filename.endswith(".txt"): filename += ".txt"
                filepath = os.path.join(PLAYLIST_DIR, filename)

                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        # 写入 header 和分隔符，模拟 AI 输出格式以便 parse 复用
                        f.write(f"# Saved Playlist: {filename}\n{SEPARATOR}\n")
                        for track in play_list:
                            f.write(f"{track['name']}\n")
                    console.print(f"[green]✅ Playlist saved to: {filename}[/]")
                except Exception as e:
                    console.print(f"[red]❌ Save failed: {e}[/]")
                continue

            elif cmd == "load":
                target_file = None

                # Case A: Load with parameter
                if args:
                    raw_name = args.strip().strip('"').strip("'")
                    if not raw_name.endswith(".txt"): raw_name += ".txt"

                    if os.path.exists(raw_name):
                        target_file = raw_name
                    elif os.path.exists(os.path.join(PLAYLIST_DIR, raw_name)):
                        target_file = os.path.join(PLAYLIST_DIR, raw_name)
                    else:
                        console.print(f"[red]❌ File not found: {raw_name}[/]")
                        continue

                # Case B: Interactive Menu
                else:
                    txts = glob.glob(os.path.join(PLAYLIST_DIR, "*.txt"))
                    if not txts:
                        console.print("[red]No saved playlists found.[/]")
                        continue
                    sel = questionary.select("Select Playlist:", choices=[os.path.basename(f) for f in txts]).ask()
                    if not sel: continue
                    target_file = os.path.join(PLAYLIST_DIR, sel)

                # Process File
                if target_file:
                    try:
                        with open(target_file, "r", encoding="utf-8") as f:
                            content = f.read()
                            if SEPARATOR not in content:
                                content = f"{SEPARATOR}\n{content}"

                            pl, _ = aidj.parse_raw_playlist(content, source="User")

                            if pl:
                                play_list = pl
                                # --- 这里开始是新增的：显示表格 ---
                                t = Table(show_header=True, title=f"Playlist ({len(pl)}) - {os.path.basename(target_file)}", show_lines=True)
                                t.add_column("Track", style="bold green", no_wrap=True)
                                t.add_column("Language", style="cyan")
                                t.add_column("Genre", style="magenta")
                                t.add_column("Emotion", style="yellow")
                                t.add_column("Loudness", style="dim")

                                for item in pl:
                                    name = item['name']
                                    info = aidj.metadata.get(name, {})
                                    def safe_fmt(val):
                                        if val is None: return "-"
                                        if isinstance(val, list): return ", ".join(str(x) for x in val)
                                        return str(val)
                                    t.add_row(name, safe_fmt(info.get('language')), safe_fmt(info.get('genre')), safe_fmt(info.get('emotion')), safe_fmt(info.get('loudness')))

                                console.print(t)
                                # --- 表格显示结束 ---
                            else:
                                console.print("[yellow]⚠️ No valid tracks found in file.[/]")
                    except Exception as e:
                        console.print(f"[red]❌ Error loading file: {e}[/]")
                continue

            else:
                console.print(f"[red]Unknown: '{cmd}'[/]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/]")

if __name__ == "__main__":
    main()
