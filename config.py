import os
import json
from log import *

CONFIG_PATH = "./config.json"
METADATA_PATH = "./music_metadata.json"
PLAYLIST_DIR = "./playlists"
LYRICS_DIR = "./lyrics"
MUSIC_EXTS = ('.mp3', '.flac', '.wav', '.m4a')
NCM_BASE_URL = "http://localhost:3000"
CFG_KEY_MF = "music_folders"

SEPARATOR = "[---SONG_LIST---]"
LANGUAGE = "简体中文"

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
                log(f"[bold red]❌ ERROR[/] {CONFIG_PATH} is corrupted!")
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
        log(f"[red]❌ Failed to save config: {e}[/]")

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
        if not os.path.exists(folder): continue
        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(MUSIC_EXTS):
                    file_key = os.path.splitext(file)[0]
                    music_files[file_key] = os.path.join(root, file)
    return music_files
