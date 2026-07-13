import os
import json
import csv
from log import *

CONFIG_PATH = "./config.json"
METADATA_PATH = "./music_metadata.json"
METADATA_JSONL_PATH = "./music_metadata.jsonl"
FREQ_CSV_PATH = "./frequency.csv"
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
        "dbus_target": None,
        "record_freq": False
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
    # 1. JSONL 存在 → 只读 JSONL
    if os.path.exists(METADATA_JSONL_PATH):
        metadata = {}
        try:
            with open(METADATA_JSONL_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if "name" in record and "metadata" in record:
                            metadata[record["name"]] = record["metadata"]
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            log(f"[yellow]⚠️ Failed to read {METADATA_JSONL_PATH}: {e}[/]")
        return metadata

    # 2. JSONL 不存在，但旧 JSON 存在 → 读取并迁移到 JSONL
    if os.path.exists(METADATA_PATH):
        metadata = {}
        try:
            with open(METADATA_PATH, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except (json.JSONDecodeError, ValueError):
            log(f"[yellow]⚠️ {METADATA_PATH} corrupted, starting fresh.[/]")
            return {}

        # 迁移：把 JSON 内容逐条写入 JSONL
        log(f"[cyan]📦 Migrating {len(metadata)} entries to JSONL...[/]")
        try:
            with open(METADATA_JSONL_PATH, "w", encoding="utf-8") as f:
                for name, meta in metadata.items():
                    record = {"name": name, "metadata": meta}
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            log(f"[green]✅ Migration complete. JSONL is now the source of truth.[/]")
        except Exception as e:
            log(f"[yellow]⚠️ Migration failed: {e}[/]")

        return metadata

    return {}

def append_metadata_jsonl(song_name, metadata_dict):
    """追加单条元数据到 JSONL 文件"""
    try:
        record = {"name": song_name, "metadata": metadata_dict}
        with open(METADATA_JSONL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        log(f"[red]❌ Failed to append metadata: {e}[/]")
        return False

# --- Frequency Tracking ---

def load_frequency():
    """从 CSV 加载播放频率到 dict"""
    freq = {}
    if not os.path.exists(FREQ_CSV_PATH):
        return freq
    try:
        with open(FREQ_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) == 2 and row[1].isdigit():
                    freq[row[0]] = int(row[1])
    except Exception as e:
        log(f"[yellow]⚠️ Failed to read {FREQ_CSV_PATH}: {e}[/]")
    return freq

def save_frequency(freq):
    """按降序写入 frequency.csv"""
    if not freq:
        return
    try:
        sorted_items = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        with open(FREQ_CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "times"])
            for name, times in sorted_items:
                writer.writerow([name, times])
    except Exception as e:
        log(f"[red]❌ Failed to save frequency: {e}[/]")

def bump_frequency(freq, song_names):
    """内存中对指定歌曲的播放次数 +1，返回是否发生了变更"""
    changed = False
    for name in song_names:
        freq[name] = freq.get(name, 0) + 1
        changed = True
    return changed

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
