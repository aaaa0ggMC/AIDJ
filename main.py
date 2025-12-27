import re
import os
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

# --- UI & Interaction Imports ---
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich import print as rprint
import questionary
from questionary import Style

# --- Configuration ---
CONFIG_PATH = "./config.json"
METADATA_PATH = "./music_metadata.json"
PLAYLIST_DIR = "./playlists"
MUSIC_EXTS = ('.mp3', '.flac', '.wav', '.m4a')
DS_BASE_URL = "https://api.deepseek.com"
NCM_BASE_URL = "http://localhost:3000"
CFG_KEY_MF = "music_folders"

SEPARATOR = "[---SONG_LIST---]"

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
        console.print(f"[bold red]❌ ERROR[/] cannot open file {CONFIG_PATH}!")
        exit(-1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    if "preferences" not in config:
        config["preferences"] = {}
    
    defaults = {
        "model": "deepseek-chat",
        "verbose": False,
        "saved_trigger": None, # 持久化 Trigger
        "dbus_target": None
    }
    
    for key, val in defaults.items():
        if key not in config["preferences"]:
            config["preferences"][key] = val
            
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

# --- DBus Manager (Shell Wrapper) ---
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

def get_song_info(client, song_info):
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "提取歌曲信息JSON: language, emotion, genre, loudness, review"},
                {"role": "user", "content": f"{song_info}"}
            ],
            response_format={'type': 'json_object'}, stream=False
        )
        return response.choices[0].message.content
    except KeyboardInterrupt: raise
    except: return None

def sync_metadata(client, targets, metadata):
    if not targets: return metadata
    console.print(f"[cyan]🚀 Syncing {len(targets)} new songs... (Ctrl+C to skip)[/]")
    pbar = tqdm(targets.items(), unit="song")
    try:
        for name, path in pbar:
            pbar.set_postfix_str(f"{name[:10]}...")
            try:
                res = requests.get(f"{NCM_BASE_URL}/search?keywords=\"{name}\"&limit=1").json()
                if res.get('code')!=200 or res['result']['songCount']==0: continue
                sid = res['result']['songs'][0]['id']
                l_res = requests.get(f"{NCM_BASE_URL}/lyric", params={"id": sid}).json()
                raw_lyric = l_res.get('lrc', {}).get('lyric', "暂无歌词")
                info = {"title": name, "lyrics": raw_lyric[:500]} 
                resp = get_song_info(client, info)
                if resp:
                    metadata[name] = json.loads(resp)
                    with open(METADATA_PATH, "w") as f: json.dump(metadata, f, ensure_ascii=False,indent = 4)
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

        # --- 核心切分逻辑 ---
        if SEPARATOR in raw_text:
            parts = raw_text.split(SEPARATOR)
            # parts[0] 是简介，parts[1] 是剩下的所有内容（歌单）
            intro_text = parts[0].replace('\n', ' ').strip()
            raw_list_block = parts[1]
            if is_verbose: console.print(f"[dim]✅ Separator found. Parsing list...[/]")
        else:
            # 兜底：AI 忘记输出分隔符
            if is_verbose and source == "AI":
                console.print(f"[yellow]⚠️ Separator '{SEPARATOR}' not found! Scanning entire text.[/]")
            # 这种情况下，我们假设没有简介，或者全部拿去尝试匹配
            intro_text = ""
            raw_list_block = raw_text

        # --- 解析歌单部分 (结合 RapidFuzz) ---
        lines = [l.strip() for l in raw_list_block.split('\n') if l.strip()]
        library_keys = list(self.music_paths.keys())

        for line in lines:
            if line.startswith("#"): continue

            # 清理
            clean = line.replace('"', '').replace("'", "").strip()
            if len(clean) < 2: continue # 跳过极短的行

            match = None

            # 使用 RapidFuzz 容错 (防止 AI 写错标点或顺序)
            result = process.extractOne(
                clean,
                library_keys,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=80 # 80分以上才算匹配，避免把废话当歌名
            )

            if result:
                match_name = result[0]
                if is_verbose:
                     console.print(f"[dim]🔍 Match: {clean} -> [green]{match_name}[/][/]")
                match = match_name

            if match:
                playlist_names.append(match)
            else:
                # 只有在找到了分隔符的情况下，我们才敢确信剩下的未匹配行是“垃圾数据”
                # 如果没找到分隔符，这些未匹配行可能是简介的一部分，但这里为了代码简单，我们选择忽略
                if is_verbose and SEPARATOR in raw_text:
                     console.print(f"[dim]❌ Ignored line in list block: {clean}[/]")

        # --- 结果构建 ---
        playlist_names = list(dict.fromkeys(playlist_names))

        playlist = []
        for name in playlist_names:
            if source == "AI":
                self.played_songs.add(name)
            playlist.append({"name": name, "path": self.music_paths[name]})

        return playlist, intro_text

    def next_step(self, user_request):
        user_request = f"[USER]：{user_request}\n\n[SYSTEM]：请牢记***输出格式***以及***只能输出现有歌单中的歌曲***。You MUST use the separator {SEPARATOR} between the intro and the playlist."

        self.turn_count += 1
        model = self.config['preferences']['model']
        is_verbose = self.config['preferences']['verbose']

        if is_verbose: console.print(f"[dim]🤖 Thinking with {model}...[/]")

        base_prompt = f"""You are a wonderful DJ. Output format is STRICTLY as follows:

            1. Introduction:
            - Respond to the user's request with a rich, engaging explanation.
            - Use emojis!
            - You can write as much as you want here.

            2. SEPARATOR:
            - Output exactly "{SEPARATOR}" on a separate line.
            - Do not use markdown code blocks around it.

            3. Song list:
            - Output ONLY the exact original keys from the library below the separator.
            - One key per line.
            - Do not number the list.
            """

        if self.turn_count == 1 or self.turn_count % 5 == 0:
            content = f"{base_prompt}\nLibrary:\n{self._format_library()}"
            self.chat_history.append({"role": "system", "content": content})
            if is_verbose: console.print("[dim]🔄 Context refreshed.[/]")
            
        full_req = f"{user_request}\n(Forbidden: {','.join(list(self.played_songs))})"
        self.chat_history.append({"role": "user", "content": full_req})
        
        with console.status(f"[bold green]🎧 DJ ({model}) thinking... (Ctrl+C to stop)[/]"):
            try:
                resp = self.client.chat.completions.create(model=model, messages=self.chat_history)
                raw = resp.choices[0].message.content
                if is_verbose: console.print(Panel(raw, title="Raw AI Output", border_style="dim"))
                self.chat_history.append({"role": "assistant", "content": raw})
                return self.parse_raw_playlist(raw, source="AI")
            except KeyboardInterrupt: raise
            except Exception as e:
                console.print(f"[red]Err: {e}[/]")
                return [], ""

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
    secrets = config.get("secrets",{})
    
    saved_dbus_target = config['preferences'].get('dbus_target')
    dbus_manager = DBusManager(preferred_target=saved_dbus_target)
    
    ds_client = openai.OpenAI(api_key=secrets.get("deepseek",""), base_url=DS_BASE_URL)
    musics = scan_music_files(config.get(CFG_KEY_MF, []))
    metadata = load_cached_metadata()
    if {k:v for k,v in musics.items() if k not in metadata}:
        metadata = sync_metadata(ds_client, {k:v for k,v in musics.items() if k not in metadata}, metadata)
    
    ensure_playlist_dir()
    aidj = DJSession(ds_client, metadata, musics, config)

    # UI Banner
    current_trigger = config['preferences'].get('saved_trigger')
    
    console.print(Panel.fit(
        f"[bold cyan]🎚️ AI DJ SYSTEM v3.1 (Persistent Shell)[/]\n"
        f"[dim]Type 'status' to check config | Type 'help' for commands[/]",
        title="✨ System Ready ✨", border_style="magenta"
    ))

    play_list = []
    style = Style([('qmark', 'fg:#673ab7 bold'),('question', 'bold'),('answer', 'fg:#f44336 bold')])

    while True:
        try:
            # 动态 Prompt
            # 实时从 config 读取 trigger (确保状态同步)
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

            # --- System & Config Commands ---
            if cmd in ["exit", "quit", "q"]:
                console.print("[bold red]👋 See ya![/]")
                break
            
            elif cmd in ["status", "check", "conf"]:
                t = Table(title="⚙️ System Status")
                t.add_column("Setting", style="cyan")
                t.add_column("Value", style="yellow")
                t.add_row("AI Model", config['preferences']['model'])
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
                t.add_row("p <text>", "Generate playlist (AI)")
                t.add_row("send", "Send list to DBus player")
                t.add_row("auto <cmd>", "Set persistent trigger (e.g. 'auto send')")
                t.add_row("auto off", "Disable auto trigger")
                t.add_row("status", "Check current config")
                t.add_row("verbose", "Toggle verbose logging")
                t.add_row("init <name>", "Set DBus target (e.g. 'init vlc')")
                t.add_row("ls", "List active players")
                t.add_row("mpv / vlc", "Play locally")
                t.add_row("next / prev", "Control playback")
                t.add_row("refresh", "Clear session history")
                t.add_row("reset", "Factory reset (clear played)")
                t.add_row("load", "Load playlist file")
                t.add_row("model", "Switch AI Model")
                console.print(t)
                continue

            elif cmd == "verbose":
                curr = config['preferences']['verbose']
                config['preferences']['verbose'] = not curr
                save_config(config)
                aidj.config = config # Update instance
                console.print(f"[green]📝 Verbose Mode: {not curr}[/]")
                continue

            elif cmd == "refresh":
                aidj.refresh(clear_history=False)
                continue
            
            elif cmd == "reset":
                aidj.refresh(clear_history=True)
                continue

            # --- Trigger Configuration ---
            elif cmd == "auto":
                if not args: 
                    console.print(f"[yellow]Current Trigger: {config['preferences'].get('saved_trigger') or 'None'}[/]")
                    console.print("[dim]Usage: 'auto send' or 'auto off'[/]")
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

            # --- AI Generation ---
            elif cmd in ["p", "prompt", "gen"]:
                if not args:
                    console.print("[red]Usage: p <your request>[/]")
                    continue
                
                pl, intro = aidj.next_step(args)
                if not pl:
                    console.print("[yellow]No matches.[/]")
                    continue
                
                play_list = pl
                if intro: console.print(f"\n[bold magenta]{intro}[/]\n")
                
                t = Table(show_header=True, title=f"Playlist ({len(pl)})",show_lines=True)
                t.add_column("Track", style="bold green", no_wrap=True)
                t.add_column("Language", style="cyan")
                t.add_column("Genre", style="magenta")
                t.add_column("Emotion", style="yellow")
                t.add_column("Loudness", style="dim") # 如果不需要响度可注释掉

                for item in pl:
                    name = item['name']
                    # 从 metadata 中安全获取信息，如果没有则返回空字典
                    info = aidj.metadata.get(name, {})

                    # 辅助函数：处理 数组 vs 字符串，并处理 None
                    def safe_fmt(val):
                        if val is None: return "-"
                        if isinstance(val, list):
                            return ", ".join(str(x) for x in val)
                        return str(val)

                    # 提取特定字段 (不包含 review)
                    lang = safe_fmt(info.get('language'))
                    genre = safe_fmt(info.get('genre'))
                    emotion = safe_fmt(info.get('emotion'))
                    loudness = safe_fmt(info.get('loudness'))

                    t.add_row(name, lang, genre, emotion, loudness)

                console.print(t)

                # ⚡ Persistent Trigger Execution
                # 这一次，我们只执行，不清除！
                current_trigger = config['preferences'].get('saved_trigger')
                if current_trigger:
                    console.print(f"[yellow]⚡ Auto-Executing: {current_trigger}[/]")
                    execute_player_command(current_trigger, play_list, dbus_manager)
                continue

            # --- Playback & Utils ---
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
                sel = questionary.select("Model:", choices=["deepseek-reasoner", "deepseek-chat"], default=config['preferences']['model']).ask()
                if sel:
                    config['preferences']['model'] = sel
                    save_config(config)
                    aidj.config = config
                    console.print(f"[green]Model: {sel}[/]")
                continue
            
            elif cmd == "load":
                txts = glob.glob(os.path.join(PLAYLIST_DIR, "*.txt"))
                if not txts: console.print("[red]No files.[/]")
                else:
                    sel = questionary.select("File:", choices=[os.path.basename(f) for f in txts]).ask()
                    if sel:
                        with open(os.path.join(PLAYLIST_DIR, sel), "r") as f:
                            pl, _ = aidj.parse_raw_playlist(f.read(), source="User")
                            if pl: 
                                play_list = pl
                                console.print(f"[green]Loaded {len(pl)} tracks.[/]")
                continue

            else:
                console.print(f"[red]Unknown: '{cmd}'[/]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/]")

if __name__ == "__main__":
    main()
