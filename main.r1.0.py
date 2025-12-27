import re
import os
import json
import time
import subprocess
import requests
import openai
import random
import glob
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
            f.write("# 这是你的自定义歌单\n# 每行写一首歌名（支持模糊搜索）\nForget\nMerry Christmas Mr. Lawrence\nListening for the weather")
        return True
    return False

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
        "saved_trigger": None 
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

# --- Core Logic Functions ---
def scan_music_files(folders):
    music_files = {}
    for folder in folders:
        if not os.path.exists(folder):
            console.print(f"[yellow]⚠️ WARN[/] folder {folder} does not exist! Skipping...")
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
                {
                    "role": "system",
                    "content": "你是一个歌曲提取助手。提取歌曲信息，必须输出 JSON 格式。字段包含：language, emotion, genre, loudness, review。"
                },
                {
                    "role": "user",
                    "content": f"请分析以下内容并提取信息:\n {song_info}"
                }
            ],
            response_format={'type': 'json_object'},
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        # 如果是 Ctrl+C 会抛出 KeyboardInterrupt，这里不捕获它，让外层捕获
        if isinstance(e, KeyboardInterrupt):
            raise e
        console.print(f"[red]❌ API Error:[/]{e}")
        return None

def sync_metadata(client, targets, metadata):
    if not targets:
        return metadata
        
    console.print(f"[cyan]🚀 Syncing {len(targets)} new songs... (Press Ctrl+C to skip)[/]")
    pbar = tqdm(targets.items(), desc="Fetching Metadata", unit="song")
    
    try:
        for name, path in pbar:
            pbar.set_postfix_str(f"{name[:15]}...")
            try:
                search_url = f"{NCM_BASE_URL}/search?keywords=\"{name}\"&limit=1"
                res = requests.get(search_url).json()
                if res.get('code') != 200 or res['result']['songCount'] == 0:
                    continue

                song = res['result']['songs'][0]
                sid = song['id']
                
                l_res = requests.get(f"{NCM_BASE_URL}/lyric", params={"id": sid}).json()
                c_res = requests.get(f"{NCM_BASE_URL}/comment/music", params={"id": sid, "limit": 5}).json()
                
                raw_lyric = l_res.get('lrc', {}).get('lyric', "暂无歌词")
                clean_lyric = re.sub(r'\[.*?\]', '', raw_lyric).strip()
                hot_comments = [{"user": c['user']['nickname'], "content": c['content'], "liked": c['likedCount']} for c in c_res.get('hotComments', [])]

                info = {
                    "title": song['name'],
                    "artist": [ar['name'] for ar in song.get('ar', [])],
                    "album": song['album']['name'],
                    "lyrics": clean_lyric[:1000],
                    "hot_comments": hot_comments
                }

                response = get_song_info(client, info)
                if response:
                    song_data = json.loads(response)
                    metadata[name] = song_data
                    with open(METADATA_PATH, "w", encoding="utf-8") as f:
                        json.dump(metadata, f, ensure_ascii=False, indent=4)
            except KeyboardInterrupt:
                raise # 抛给外层处理
            except Exception as e:
                continue
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Sync skipped by user.[/]")
        pbar.close()
        return metadata

    return metadata

# --- DJ Class ---
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
            console.print("[yellow]🧹 Cleared: History & Played Songs[/]")
        else:
            console.print("[yellow]🧹 Cleared: Played Songs only[/]")

    def _format_library(self):
        lines = []
        available_songs = set(self.metadata.keys()) & set(self.music_paths.keys())
        for name in available_songs:
            info = self.metadata[name]
            if isinstance(info, dict) and "genre" in info:
                lines.append(f"- {name}: {info.get('genre')}, {info.get('emotion')}, {info.get('review')}")
        return "\n".join(lines)

    def parse_raw_playlist(self, raw_text, source="AI"):
        """统一解析引擎"""
        playlist_names = []
        intro_text = ""
        is_verbose = self.config['preferences']['verbose']
        
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        
        for line in lines:
            if line.startswith("#"): continue

            if line in self.music_paths:
                playlist_names.append(line)
                continue

            clean_line = line.replace('"', '').replace("'", "")
            if clean_line in self.music_paths:
                playlist_names.append(clean_line)
                continue

            if len(clean_line) > 2:
                match = next((k for k in self.music_paths.keys() if clean_line.lower() in k.lower()), None)
                if match:
                    playlist_names.append(match)
                    if is_verbose: console.print(f"[dim]🔍 Fuzzy Match: '{clean_line}' -> '{match}'[/]")
                    continue

            if source == "AI" and len(playlist_names) == 0:
                intro_text += line + " "

        playlist_names = list(dict.fromkeys(playlist_names))
        
        playlist_with_paths = []
        for name in playlist_names:
            if source == "AI": 
                self.played_songs.add(name)
            playlist_with_paths.append({
                "name": name,
                "path": self.music_paths[name]
            })

        return playlist_with_paths, intro_text

    def next_step(self, user_request):
        self.turn_count += 1
        model_name = self.config['preferences']['model']
        is_verbose = self.config['preferences']['verbose']

        if is_verbose:
            console.print(f"[dim]🤖 Using Model: {model_name}[/]")

        base_prompt = """You are a top-tier Radio DJ with a great vibe.
        【Task】: Select songs from the library based on the user's request.
        【Output Format】:
        1. (Optional) A single short sentence intro with emojis describing the vibe.
        2. The list of Song Names (JSON Keys), strictly one per line.
        3. Do NOT add numbers, bullets, or extra text to the song lines.
        4. Do NOT recommend songs already played.
        """

        if self.turn_count == 1 or self.turn_count % 5 == 0:
            library_data = self._format_library()
            content = f"{base_prompt}\n\nLibrary Summary:\n{library_data}"
            self.chat_history.append({"role": "system", "content": content})
            if is_verbose: console.print("[dim]🔄 Context Refreshed[/]")

        forbidden = "，".join(list(self.played_songs))
        full_request = f"{user_request}\n(Forbidden/Played: {forbidden})" if forbidden else user_request
        self.chat_history.append({"role": "user", "content": full_request})

        with console.status(f"[bold green]🎧 DJ ({model_name}) is mixing the vibe... (Ctrl+C to stop)[/]", spinner="dots12"):
            try:
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=self.chat_history
                )
                raw_answer = response.choices[0].message.content
            except KeyboardInterrupt:
                raise # 传递给上层处理
            except Exception as e:
                console.print(f"[bold red]❌ API Error:[/]{e}")
                return [], ""

        if is_verbose:
            console.print(Panel(raw_answer, title="🧠 AI Raw Response", border_style="dim"))

        return self.parse_raw_playlist(raw_answer, source="AI")

# --- Player Execution Logic ---
def execute_player_command(command, playlist):
    if not playlist:
        console.print("[red]❌ No playlist to play![/]")
        return

    paths = [item['path'] for item in playlist]
    
    if not command.startswith("/"):
        command = "/" + command

    if command == "/mpv":
        console.print(f"[green]🔊 Launching mpv ({len(playlist)} tracks)...[/]")
        subprocess.Popen(['mpv', '--force-window', '--geometry=600x600'] + paths)
    elif command == "/vlc":
        console.print(f"[green]🟠 Launching VLC ({len(playlist)} tracks)...[/]")
        subprocess.Popen(['vlc', '--one-instance', '--playlist-enqueue'] + paths)
    else:
        console.print(f"[red]❓ Unknown player command: {command}[/]")

# --- Main Interface ---
def main():
    config = load_config()
    secrets = config.get("secrets", {})
    if not secrets.get("deepseek"):
        console.print("[bold red]❌ ERROR: DeepSeek key missing![/]")
        return

    ds_client = openai.OpenAI(api_key=secrets["deepseek"], base_url=DS_BASE_URL)

    console.rule("[bold blue]💿 Library Initialization[/]")
    musics = scan_music_files(config.get(CFG_KEY_MF, []))
    console.print(f"[green]✔ Found {len(musics)} local tracks.[/]")
    
    metadata = load_cached_metadata()
    need_to_sync = {k: v for k, v in musics.items() if k not in metadata}
    
    # 【Init Phase】这里的 Ctrl+C 会跳过同步进入系统
    if need_to_sync:
        metadata = sync_metadata(ds_client, need_to_sync, metadata)
    
    ensure_playlist_dir()
    
    aidj = DJSession(ds_client, metadata, musics, config)

    console.print(Panel.fit(
        "[bold cyan]🎚️  AI DJ SYSTEM v2.5 (Final Release)[/]\n"
        f"[dim]🤖 Model: {config['preferences']['model']} | ▶ AutoPlay: {config['preferences']['auto_play']}[/]",
        title="✨ Welcome to the Club ✨",
        border_style="magenta"
    ))

    play_list = []
    one_off_command = config['preferences'].get('saved_trigger') 

    custom_style = Style([
        ('qmark', 'fg:#673ab7 bold'),
        ('question', 'bold'),
        ('answer', 'fg:#f44336 bold'),
    ])

    while True:
        # --- 1. Prompt Phase (Ctrl+C = Exit) ---
        try:
            prompt_icon = random.choice(EMOJIS_VIBE)
            label = f"{prompt_icon} What's the vibe tonight?"
            if one_off_command:
                label += f" [⚡ Next: {one_off_command}]"

            user_input = questionary.text(
                label,
                qmark="🎤",
                style=custom_style
            ).ask()

            if user_input is None: 
                # 这里捕获输入框的 Ctrl+C -> 退出程序
                console.print("[bold red]👋 See ya![/]")
                break
            
            prompt = user_input.strip()
            if not prompt: continue

            # --- 2. Processing Phase (Ctrl+C = Cancel Current Task) ---
            try:
                # --- Command Handling ---
                if prompt.startswith("/"):
                    cmd_parts = prompt.split()
                    action = cmd_parts[0].lower()
                    args = cmd_parts[1:] if len(cmd_parts) > 1 else []

                    if action == "/exit":
                        console.print("[bold red]👋 See ya![/]")
                        break
                    
                    elif action == "/help":
                        help_table = Table(title="📜 Command List")
                        help_table.add_column("Command", style="cyan")
                        help_table.add_column("Description", style="white")
                        help_table.add_row("/model", "🤖 Switch AI Model (Saved)")
                        help_table.add_row("/load", "📂 Load User Playlist (.txt)")
                        help_table.add_row("/auto <cmd>", "⚡ Set one-time trigger (Saved)")
                        help_table.add_row("/autoplay", "▶ Toggle Global Auto-Play (Saved)")
                        help_table.add_row("/verbose", "📝 Toggle Logs (Saved)")
                        help_table.add_row("/mpv", "🔊 Play current list in mpv")
                        help_table.add_row("/vlc", "🟠 Play current list in VLC")
                        help_table.add_row("/refresh", "🧹 Clear History")
                        help_table.add_row("/reset", "💥 Factory Reset")
                        console.print(help_table)
                        continue

                    elif action == "/load":
                        txt_files = glob.glob(os.path.join(PLAYLIST_DIR, "*.txt"))
                        if not txt_files:
                            console.print(f"[red]❌ No .txt files found in {PLAYLIST_DIR}[/]")
                            continue
                        choices = [os.path.basename(f) for f in txt_files]
                        selected_file = questionary.select(
                            "📂 Choose a playlist:",
                            choices=choices,
                            style=custom_style
                        ).ask()
                        if selected_file:
                            file_path = os.path.join(PLAYLIST_DIR, selected_file)
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()
                            console.print(f"[cyan]📖 Parsing {selected_file}...[/]")
                            play_list, _ = aidj.parse_raw_playlist(content, source="User")
                            if play_list:
                                table = Table(show_header=True, header_style="bold magenta", border_style="cyan", title=f"📂 Loaded: {selected_file}")
                                table.add_column("#", style="dim", width=4, justify="right")
                                table.add_column("Track", style="bold white")
                                for i, item in enumerate(play_list, 1):
                                    table.add_row(f"{i:02d}", item['name'])
                                console.print(table)
                                console.print(f"[green]✔ {len(play_list)} tracks loaded. Type /mpv to play.[/]")
                            else:
                                console.print("[yellow]⚠ No valid songs found in file.[/]")
                        continue

                    elif action == "/model":
                        choice = questionary.select(
                            "🤖 Select Brain:",
                            choices=["deepseek-reasoner", "deepseek-chat"],
                            default=config['preferences']['model'],
                            style=custom_style
                        ).ask()
                        if choice:
                            config['preferences']['model'] = choice
                            save_config(config)
                            aidj.config = config
                            console.print(f"[green]✔ Model switched to: {choice} (Saved)[/]")
                        continue

                    elif action == "/auto":
                        if not args:
                            console.print("[red]❌ Usage: /auto <command> [optional prompt][/]")
                            continue
                        target_cmd = args[0]
                        if not target_cmd.startswith("/"):
                            target_cmd = "/" + target_cmd
                        
                        one_off_command = target_cmd
                        config['preferences']['saved_trigger'] = one_off_command
                        save_config(config)
                        aidj.config = config
                        
                        if len(args) > 1:
                            prompt = " ".join(args[1:])
                            console.print(f"[yellow]⚡ Auto-Trigger Set (Saved): {one_off_command} -> Processing Prompt...[/]")
                        else:
                            console.print(f"[yellow]⚡ Trigger Set (Saved)! Next generated playlist will run: {one_off_command}[/]")
                            continue

                    elif action == "/autoplay":
                        curr = config['preferences']['auto_play']
                        config['preferences']['auto_play'] = not curr
                        save_config(config)
                        aidj.config = config
                        console.print(f"[green]▶ Global Auto-Play: {not curr} (Saved)[/]")
                        continue

                    elif action == "/verbose":
                        curr = config['preferences']['verbose']
                        config['preferences']['verbose'] = not curr
                        save_config(config)
                        aidj.config = config
                        console.print(f"[green]📝 Verbose Mode: {not curr} (Saved)[/]")
                        continue
                    
                    elif action == "/refresh":
                        aidj.refresh(clear_history=False)
                        continue
                    elif action == "/reset":
                        aidj.refresh(clear_history=True)
                        continue
                    elif action == "/mpv":
                        execute_player_command("/mpv", play_list)
                        continue
                    elif action == "/vlc":
                        execute_player_command("/vlc", play_list)
                        continue
                    else:
                        if prompt.startswith("/"):
                            console.print(f"[red]❓ Unknown command: {action}[/]")
                            continue

                # --- AI Selection Logic ---
                play_list, intro = aidj.next_step(prompt)

                if not play_list:
                    console.print("[yellow]🤷‍♂️ No matches found (Even with fuzzy match). Try again.[/]")
                    continue

                if intro:
                    console.print(f"\n[bold magenta]💬 DJ Says:[/]\n{intro}\n")

                table = Table(show_header=True, header_style="bold magenta", border_style="cyan", title=f"💿 Playlist ({len(play_list)} tracks)")
                table.add_column("#", style="dim", width=4, justify="right")
                table.add_column("Vibe", justify="center", width=4)
                table.add_column("Track Name", style="bold white")
                
                for i, item in enumerate(play_list, 1):
                    icon = get_random_icon() 
                    table.add_row(f"{i:02d}", icon, item['name'])
                console.print(table)

                # --- Trigger Logic ---
                if one_off_command:
                    console.print(f"[bold yellow]⚡ Executing One-off Trigger: {one_off_command}[/]")
                    execute_player_command(one_off_command, play_list)
                    
                    one_off_command = None
                    config['preferences']['saved_trigger'] = None
                    save_config(config) 

                elif config['preferences']['auto_play']:
                    console.print("[green]🚀 Auto-Play ON...[/]")
                    execute_player_command("/mpv", play_list)

            # --- 2b. Catch Ctrl+C during Processing ---
            except KeyboardInterrupt:
                console.print("\n[yellow]⛔ Action cancelled by user. Returning to deck...[/]")
                continue
            except Exception as e:
                console.print(f"[bold red]💥 System Error:[/]{e}")

        # --- 1b. Catch Ctrl+C from input phase (Backup) ---
        except KeyboardInterrupt:
             console.print("\n[bold red]👋 See ya![/]")
             break

if __name__ == "__main__":
    main()
