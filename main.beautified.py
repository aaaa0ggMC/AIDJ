import re
import os
import json
import time
import subprocess
import requests
import openai
import random
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
HISTORY_PATH = ".dj_history"
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

def load_config():
    if not os.path.exists(CONFIG_PATH):
        console.print(f"[bold red]❌ ERROR[/] cannot open file {CONFIG_PATH}!")
        exit(-1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    if "preferences" not in config:
        config["preferences"] = {
            "model": "deepseek-chat",
            "verbose": False,
            "auto_play": False
        }
    return config

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

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
        console.print(f"[red]❌ API Error:[/]{e}")
        return None

def sync_metadata(client, targets, metadata):
    if not targets:
        return metadata
        
    console.print(f"[cyan]🚀 Syncing {len(targets)} new songs...[/]")
    pbar = tqdm(targets.items(), desc="Fetching Metadata", unit="song")
    
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
        except Exception as e:
            continue

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

    def next_step(self, user_request):
        self.turn_count += 1
        model_name = self.config['preferences']['model']
        is_verbose = self.config['preferences']['verbose']

        if is_verbose:
            console.print(f"[dim]🤖 Using Model: {model_name}[/]")

        # --- AI Persona Injection 🤖 ---
        base_prompt = """You are a top-tier Radio DJ with a great vibe.
        【Task】: Select songs from the library based on the user's request.
        【Output Format】:
        1. (Optional) A single short sentence intro with emojis describing the vibe (e.g., "Here is some chill beats for you 🌊").
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

        with console.status(f"[bold green]🎧 DJ ({model_name}) is mixing the vibe...[/]", spinner="dots12"):
            try:
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=self.chat_history
                )
                raw_answer = response.choices[0].message.content
            except Exception as e:
                console.print(f"[bold red]❌ API Error:[/]{e}")
                return [], ""

        if is_verbose:
            console.print(Panel(raw_answer, title="🧠 AI Raw Response", border_style="dim"))

        playlist_names = []
        intro_text = ""
        
        lines = [line.strip() for line in raw_answer.split('\n') if line.strip()]
        for line in lines:
            if line in self.music_paths:
                playlist_names.append(line)
            elif len(playlist_names) == 0 and len(line) > 0:
                intro_text += line + " "

        playlist_names = list(dict.fromkeys(playlist_names))
        
        playlist_with_paths = []
        for name in playlist_names:
            self.played_songs.add(name)
            playlist_with_paths.append({
                "name": name,
                "path": self.music_paths[name]
            })

        self.chat_history.append({"role": "assistant", "content": raw_answer})
        return playlist_with_paths, intro_text

# --- Player Execution Logic ---
def execute_player_command(command, playlist):
    """统一处理播放逻辑，复用代码"""
    if not playlist:
        console.print("[red]❌ No playlist to play![/]")
        return

    paths = [item['path'] for item in playlist]
    
    # 确保命令带 / (虽然外部已经处理，但为了稳健)
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
    
    if need_to_sync:
        metadata = sync_metadata(ds_client, need_to_sync, metadata)
    
    aidj = DJSession(ds_client, metadata, musics, config)

    # Vibe Banner
    console.print(Panel.fit(
        "[bold cyan]🎚️  AI DJ SYSTEM v2.2 (Auto-Trigger Mode)[/]\n"
        f"[dim]🤖 Model: {config['preferences']['model']} | ▶ AutoPlay: {config['preferences']['auto_play']}[/]",
        title="✨ Welcome to the Club ✨",
        border_style="magenta"
    ))

    play_list = []
    
    # 【新增】单次触发器 Flag
    one_off_command = None 

    # Custom Questionary Style
    custom_style = Style([
        ('qmark', 'fg:#673ab7 bold'),
        ('question', 'bold'),
        ('answer', 'fg:#f44336 bold'),
        ('pointer', 'fg:#673ab7 bold'),
        ('highlighted', 'fg:#673ab7 bold'),
    ])

    while True:
        try:
            # 动态 Prompt: 如果有挂载命令，显示提示
            prompt_icon = random.choice(EMOJIS_VIBE)
            label = f"{prompt_icon} What's the vibe tonight?"
            if one_off_command:
                label += f" [⚡ Next: {one_off_command}]"

            user_input = questionary.text(
                label,
                qmark="🎤",
                style=custom_style
            ).ask()

            if user_input is None: break
            prompt = user_input.strip()
            if not prompt: continue

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
                    help_table.add_row("/model", "🤖 Switch AI Model")
                    help_table.add_row("/auto <cmd>", "⚡ Set one-time trigger (e.g. /auto mpv)")
                    help_table.add_row("/autoplay", "▶ Toggle Global Auto-Play")
                    help_table.add_row("/verbose", "📝 Toggle Logs")
                    help_table.add_row("/mpv", "🔊 Play current list in mpv")
                    help_table.add_row("/vlc", "🟠 Play current list in VLC")
                    help_table.add_row("/refresh", "🧹 Clear History")
                    help_table.add_row("/reset", "💥 Factory Reset")
                    console.print(help_table)
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
                        console.print(f"[green]✔ Model switched to: {choice}[/]")
                    continue

                # 【修改】/auto 逻辑
                elif action == "/auto":
                    if not args:
                        console.print("[red]❌ Usage: /auto <command> [optional prompt][/]")
                        continue
                    
                    # 自动补全 / (如果用户只输了 mpv)
                    target_cmd = args[0]
                    if not target_cmd.startswith("/"):
                        target_cmd = "/" + target_cmd
                    
                    # 设置单次触发器
                    one_off_command = target_cmd
                    
                    # 如果用户在 /auto mpv 后面还跟了 Prompt (e.g., /auto mpv 来点爵士)
                    # 则直接把剩下的部分当做 Prompt 继续执行
                    if len(args) > 1:
                        prompt = " ".join(args[1:])
                        # 这里不 continue，让程序往下走到 Selection Logic
                        console.print(f"[yellow]⚡ Auto-Trigger Set: {one_off_command} -> Processing Prompt...[/]")
                    else:
                        console.print(f"[yellow]⚡ Trigger Set! Next generated playlist will run: {one_off_command}[/]")
                        continue # 只有单纯设置命令时才跳过 AI 分析

                elif action == "/autoplay":
                    curr = config['preferences']['auto_play']
                    config['preferences']['auto_play'] = not curr
                    save_config(config)
                    aidj.config = config
                    console.print(f"[green]▶ Global Auto-Play: {not curr}[/]")
                    continue

                elif action == "/verbose":
                    curr = config['preferences']['verbose']
                    config['preferences']['verbose'] = not curr
                    save_config(config)
                    aidj.config = config
                    console.print(f"[green]📝 Verbose Mode: {not curr}[/]")
                    continue
                
                elif action == "/refresh":
                    aidj.refresh(clear_history=False)
                    continue
                elif action == "/reset":
                    aidj.refresh(clear_history=True)
                    continue

                # 统一使用 execute_player_command
                elif action == "/mpv":
                    execute_player_command("/mpv", play_list)
                    continue
                elif action == "/vlc":
                    execute_player_command("/vlc", play_list)
                    continue
                
                # 如果 prompt 是其他未知指令，不继续
                else:
                    if prompt.startswith("/"):
                        console.print(f"[red]❓ Unknown command: {action}[/]")
                        continue

            # --- AI Selection Logic ---
            play_list, intro = aidj.next_step(prompt)

            if not play_list:
                console.print("[yellow]🤷‍♂️ No matches found. Try again.[/]")
                continue

            # Output Intro
            if intro:
                console.print(f"\n[bold magenta]💬 DJ Says:[/]\n{intro}\n")

            # Rich Table Output
            table = Table(show_header=True, header_style="bold magenta", border_style="cyan", title=f"💿 Playlist ({len(play_list)} tracks)")
            table.add_column("#", style="dim", width=4, justify="right")
            table.add_column("Vibe", justify="center", width=4)
            table.add_column("Track Name", style="bold white")
            
            for i, item in enumerate(play_list, 1):
                icon = get_random_icon() 
                table.add_row(f"{i:02d}", icon, item['name'])
            console.print(table)

            # --- 🚀 触发器逻辑核心 (Trigger Logic) ---
            
            # 优先检查是否有单次触发器 (/auto xxx)
            if one_off_command:
                console.print(f"[bold yellow]⚡ Executing One-off Trigger: {one_off_command}[/]")
                execute_player_command(one_off_command, play_list)
                one_off_command = None # ❗执行完销毁，防止复读
            
            # 如果没有单次触发器，再看全局 AutoPlay
            elif config['preferences']['auto_play']:
                console.print("[green]🚀 Auto-Play ON...[/]")
                execute_player_command("/mpv", play_list) # 默认走 mpv

        except KeyboardInterrupt:
            console.print("\n[bold red]🛑 Session Ended.[/]")
            break
        except Exception as e:
            console.print(f"[bold red]💥 System Error:[/]{e}")

if __name__ == "__main__":
    main()
