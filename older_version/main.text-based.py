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
        "auto_play": False,
        "saved_trigger": None,
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

# --- DBus Manager (Shell Wrapper Version) ---
class DBusManager:
    """
    不依赖 pydbus，直接调用系统 dbus-send 命令，
    解决 Python 环境隔离导致的找不到播放器问题。
    """
    def __init__(self, preferred_target=None):
        self.preferred_target = preferred_target
        # 检查 dbus-send 是否存在
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
        """解析 dbus-send 输出获取播放器列表"""
        if not self.available: return []
        
        # 列出所有 names
        cmd = [
            "dbus-send", "--session", "--dest=org.freedesktop.DBus", 
            "--type=method_call", "--print-reply", 
            "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"
        ]
        output = self._run_cmd(cmd)
        if not output: return []

        # 解析 ugly 的 dbus-send 输出
        players = []
        for line in output.split("\n"):
            if "org.mpris.MediaPlayer2." in line:
                # 提取引号中的内容
                match = re.search(r'"(org\.mpris\.MediaPlayer2\.[^"]+)"', line)
                if match:
                    players.append(match.group(1))
        return players

    def get_active_player(self):
        players = self.get_players()
        if not players: return None, "No Active Players"

        target = None
        # 1. 偏好匹配
        if self.preferred_target:
            target = next((p for p in players if self.preferred_target.lower() in p.lower()), None)
        
        # 2. MPV 默认
        if not target:
            target = next((p for p in players if "mpv" in p), None)
            
        # 3. 任意
        if not target:
            target = players[0]
            
        return target, target

    def send_files(self, file_paths):
        dest, name = self.get_active_player()
        if not dest: return False, name
        
        count = 0
        for path in file_paths:
            # 使用 OpenUri 方法
            uri = f"file://{path}"
            cmd = [
                "dbus-send", "--session", "--type=method_call", 
                f"--dest={dest}", "/org/mpris/MediaPlayer2", 
                "org.mpris.MediaPlayer2.Player.OpenUri", 
                f"string:{uri}"
            ]
            if self._run_cmd(cmd) is not None:
                count += 1
                time.sleep(0.05) # 防止过快
        
        return True, f"Sent {count} tracks to {name}"

    def control(self, command):
        dest, name = self.get_active_player()
        if not dest: return False, name
        
        method_map = {
            "next": "Next", "prev": "Previous", 
            "play": "Play", "pause": "Pause", 
            "toggle": "PlayPause", "stop": "Stop"
        }
        
        if command not in method_map:
            return False, "Unknown Command"
            
        method = method_map[command]
        cmd = [
            "dbus-send", "--session", "--type=method_call", 
            f"--dest={dest}", "/org/mpris/MediaPlayer2", 
            f"org.mpris.MediaPlayer2.Player.{method}"
        ]
        
        if self._run_cmd(cmd) is not None:
            return True, f"Executed {command} on {name}"
        return False, "Command Failed"

# --- Core Logic Functions ---
def scan_music_files(folders):
    music_files = {}
    for folder in folders:
        if not os.path.exists(folder):
            continue
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
                    with open(METADATA_PATH, "w") as f: json.dump(metadata, f, ensure_ascii=False)
            except KeyboardInterrupt: raise
            except: continue
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Sync skipped.[/]")
    return metadata

# --- DJ Session ---
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
        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
        for line in lines:
            if line.startswith("#"): continue
            
            # Fuzzy Search
            match = None
            clean = line.replace('"','').replace("'", "")
            if clean in self.music_paths: match = clean
            elif len(clean)>2:
                match = next((k for k in self.music_paths if clean.lower() in k.lower()), None)
            
            if match:
                playlist_names.append(match)
            elif source == "AI" and not playlist_names:
                intro_text += line + " "

        playlist_names = list(dict.fromkeys(playlist_names))
        playlist = []
        for name in playlist_names:
            if source == "AI": self.played_songs.add(name)
            playlist.append({"name": name, "path": self.music_paths[name]})
        return playlist, intro_text

    def next_step(self, user_request):
        self.turn_count += 1
        model = self.config['preferences']['model']
        
        base_prompt = """You are a DJ. Output: 
        1. Intro sentence with emojis. 
        2. Song list (one per line)."""
        
        if self.turn_count == 1 or self.turn_count % 5 == 0:
            content = f"{base_prompt}\nLibrary:\n{self._format_library()}"
            self.chat_history.append({"role": "system", "content": content})

        full_req = f"{user_request}\n(Forbidden: {','.join(list(self.played_songs))})"
        self.chat_history.append({"role": "user", "content": full_req})

        with console.status(f"[bold green]🎧 DJ ({model}) thinking... (Ctrl+C to stop)[/]"):
            try:
                resp = self.client.chat.completions.create(
                    model=model, messages=self.chat_history
                )
                raw = resp.choices[0].message.content
                self.chat_history.append({"role": "assistant", "content": raw})
                return self.parse_raw_playlist(raw, source="AI")
            except KeyboardInterrupt: raise
            except Exception as e:
                console.print(f"[red]Err: {e}[/]")
                return [], ""

# --- Execution ---
def execute_player_command(command, playlist, dbus_manager):
    if not playlist and command in ["/mpv", "/vlc", "/dbsend"]:
        console.print("[red]❌ No playlist![/]")
        return

    paths = [item['path'] for item in playlist] if playlist else []
    
    # DBus Commands
    if command == "/dbsend":
        if not dbus_manager.available:
            console.print("[red]❌ 'dbus-send' command not found![/]")
            return
        ok, msg = dbus_manager.send_files(paths)
        color = "green" if ok else "red"
        console.print(f"[{color}]📡 DBus: {msg}[/]")
        return

    if command.startswith("/dbus"):
        parts = command.split()
        subcmd = parts[1] if len(parts) > 1 else "help"
        if subcmd == "help":
            console.print("[cyan]DBus Cmds: next, prev, play, pause, toggle, stop[/]")
        else:
            ok, msg = dbus_manager.control(subcmd)
            color = "green" if ok else "red"
            console.print(f"[{color}]📡 DBus: {msg}[/]")
        return

    # Native Commands
    if command == "/mpv":
        console.print(f"[green]🔊 MPV ({len(playlist)} trks)[/]")
        subprocess.Popen(['mpv', '--force-window', '--geometry=600x600'] + paths)
    elif command == "/vlc":
        console.print(f"[green]🟠 VLC ({len(playlist)} trks)[/]")
        subprocess.Popen(['vlc', '--one-instance', '--playlist-enqueue'] + paths)

def main():
    config = load_config()
    secrets = config.get("secrets",{})
    
    # Init DBus Shell Wrapper
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
    dbus_status = "✔" if dbus_manager.available else "❌"
    current_dbus_pref = saved_dbus_target if saved_dbus_target else "Auto"
    
    console.print(Panel.fit(
        f"[bold cyan]🎚️ AI DJ SYSTEM v2.7 (Shell DBus)[/]\n"
        f"[dim]🤖 Model: {config['preferences']['model']} | 📡 DBus: {current_dbus_pref} | ▶ Auto: {config['preferences']['auto_play']}[/]",
        title="✨ Welcome to the Club ✨", border_style="magenta"
    ))

    play_list = []
    one_off_command = config['preferences'].get('saved_trigger')
    
    style = Style([('qmark', 'fg:#673ab7 bold'),('answer', 'fg:#f44336 bold')])

    while True:
        try:
            # 1. Prompt Phase
            label = f"{get_random_icon()} Vibe?"
            if one_off_command: label += f" [⚡ {one_off_command}]"
            
            ipt = questionary.text(label, qmark="🎤", style=style).ask()
            if ipt is None: 
                console.print("[red]👋 Bye![/]")
                break
            prompt = ipt.strip()
            if not prompt: continue

            # 2. Processing Phase
            try:
                if prompt.startswith("/"):
                    parts = prompt.split()
                    action = parts[0].lower()
                    args = parts[1:]
                    
                    if action == "/exit": break
                    elif action == "/help":
                        console.print("[cyan]Cmds: /model, /load, /auto, /dbsend, /dblist, /dbinit <name>, /mpv, /dbus <cmd>[/]")
                        continue
                    
                    # --- DBus Commands ---
                    elif action == "/dblist":
                        players = dbus_manager.get_players()
                        if not players:
                            console.print("[yellow]No active MPRIS players.[/]")
                        else:
                            t = Table(title="📡 Active Players")
                            t.add_column("DBus Name")
                            for p in players:
                                marker = ""
                                if dbus_manager.preferred_target and dbus_manager.preferred_target in p:
                                    marker = " [green](Target)[/]"
                                t.add_row(f"{p}{marker}")
                            console.print(t)
                        continue

                    elif action == "/dbinit":
                        if not args:
                            console.print("[red]Usage: /dbinit <name>[/]")
                            continue
                        target = args[0]
                        dbus_manager.set_preference(target)
                        config['preferences']['dbus_target'] = target
                        save_config(config)
                        console.print(f"[green]✔ DBus target set to: {target}[/]")
                        continue

                    elif action == "/dbsend":
                        execute_player_command("/dbsend", play_list, dbus_manager)
                        continue
                    elif action.startswith("/dbus"):
                        execute_player_command(prompt, None, dbus_manager)
                        continue

                    # --- Logic Commands ---
                    elif action == "/auto":
                        target = args[0] if args else "/dbsend"
                        if not target.startswith("/"): target = "/" + target
                        one_off_command = target
                        config['preferences']['saved_trigger'] = target
                        save_config(config)
                        aidj.config = config
                        if len(args) > 1: prompt = " ".join(args[1:])
                        else: 
                            console.print(f"[yellow]⚡ Trigger: {target}[/]")
                            continue
                    
                    # ... Copy previous commands (autoplay, model, load, mpv, vlc) logic here ...
                    # (为了代码简洁，请保留之前的 action 逻辑，这里只展示新改动)
                    elif action == "/autoplay":
                        curr = config['preferences']['auto_play']
                        config['preferences']['auto_play'] = not curr
                        save_config(config)
                        aidj.config = config
                        console.print(f"[green]▶ AutoPlay: {not curr}[/]")
                        continue
                    elif action == "/load":
                        txts = glob.glob(os.path.join(PLAYLIST_DIR, "*.txt"))
                        if not txts: 
                            console.print("[red]No playlists.[/]")
                            continue
                        sel = questionary.select("Load:", choices=[os.path.basename(f) for f in txts], style=style).ask()
                        if sel:
                            with open(os.path.join(PLAYLIST_DIR, sel), "r") as f:
                                pl, _ = aidj.parse_raw_playlist(f.read(), source="User")
                                if pl: 
                                    play_list = pl
                                    console.print(f"[green]Loaded {len(pl)} tracks.[/]")
                        continue
                    elif action == "/model":
                        sel = questionary.select("Model:", choices=["deepseek-reasoner", "deepseek-chat"], default=config['preferences']['model'], style=style).ask()
                        if sel:
                            config['preferences']['model'] = sel
                            save_config(config)
                            aidj.config = config
                            console.print(f"[green]Model: {sel}[/]")
                        continue
                    elif action == "/mpv":
                        execute_player_command("/mpv", play_list, dbus_manager)
                        continue

                # AI Logic
                if not prompt.startswith("/"):
                    pl, intro = aidj.next_step(prompt)
                    if not pl: 
                        console.print("[yellow]No matches.[/]")
                        continue
                    play_list = pl
                    if intro: console.print(f"\n[bold magenta]{intro}[/]\n")
                    
                    t = Table(show_header=True, title=f"Playlist ({len(pl)})")
                    t.add_column("Track")
                    for i,item in enumerate(pl,1): 
                        t.add_row(f"{get_random_icon()} {item['name']}")
                    console.print(t)

                    # Trigger
                    if one_off_command:
                        console.print(f"[yellow]⚡ Auto: {one_off_command}[/]")
                        execute_player_command(one_off_command, play_list, dbus_manager)
                        one_off_command = None
                        config['preferences']['saved_trigger'] = None
                        save_config(config)
                    elif config['preferences']['auto_play']:
                        cmd = "/dbsend" if dbus_manager.available else "/mpv"
                        execute_player_command(cmd, play_list, dbus_manager)

            except KeyboardInterrupt:
                console.print("\n[yellow]Cancelled.[/]")

        except KeyboardInterrupt:
            console.print("\n[red]Bye![/]")
            break

if __name__ == "__main__":
    main()
