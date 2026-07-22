#!/usr/bin/env python3
"""lyrics_sync_lyrica — 通过 Lyrica API 批量下载 LRC 歌词

用法:
    uv run tools/lyrics_sync_lyrica.py

前置: Lyrica 服务必须在 localhost:2778 运行。
       (cd $HOME/Apps && ./start_lyrica)

歌词会写入 data/lyrics/ 目录，文件名与音频文件同名（扩展名 .lrc）。
已存在的歌词文件会自动跳过。
"""

import os
import re
import time
import random
import json
import requests
from pathlib import Path

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
    from rich.panel import Panel
except ImportError:
    print("请先安装 rich: uv sync")
    exit(1)

LYRICA_BASE_URL = "http://localhost:2778"
LYRICS_DIR = "./data/lyrics"
CONFIG_FILE = "./data/config.json"
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus'}

console = Console()


def load_library_paths():
    paths = ["."]
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                if 'music_folders' in conf:
                    paths = conf['music_folders']
        except Exception as e:
            console.print(f"[yellow]⚠️ 读取配置文件失败，将扫描当前目录: {e}[/]")
    return paths


def scan_music_files(paths):
    music_files = []
    for p in paths:
        if not os.path.exists(p):
            continue
        for root, dirs, files in os.walk(p):
            for file in files:
                if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS:
                    music_files.append(os.path.join(root, file))
    return music_files


def parse_artist_song(filename):
    """从 'Artist - Title.ext' 解析出 (artist, title)"""
    name = os.path.splitext(filename)[0]
    # 移除括号内容
    name = re.sub(r'[\(\[].*?[\)\]]', '', name)
    # 移除 feat. xxx
    name = re.sub(r'(?i)feat\..*', '', name)
    name = name.strip()

    # 尝试按 ' - ' 分割
    if ' - ' in name:
        parts = name.split(' - ', 1)
        return parts[0].strip(), parts[1].strip()

    # fallback: 整个作为 song，artist 留空
    return "", name


def fetch_lyric_lyrica(artist, song):
    """调用 Lyrica API 获取歌词 (带时间戳)"""
    try:
        resp = requests.get(
            f"{LYRICA_BASE_URL}/lyrics/",
            params={"artist": artist, "song": song, "timestamps": "true"},
            timeout=30,
        )
        data = resp.json()

        if data.get("status") == "success":
            lyric_data = data.get("data", {})
            # 优先取 synced_lyrics / lyrics 字段
            lrc = lyric_data.get("synced_lyrics") or lyric_data.get("lyrics")
            if lrc:
                return lrc
    except Exception:
        return None
    return None


def main():
    console.clear()
    console.print(Panel.fit("[bold cyan]🎵 Lyric Sync (Lyrica)[/]", border_style="cyan"))

    # 检查 Lyrica 是否可达
    try:
        r = requests.get(f"{LYRICA_BASE_URL}/", timeout=3)
        if r.status_code != 200:
            console.print("[red]❌ Lyrica 未正常响应[/]")
            return
    except requests.ConnectionError:
        console.print(f"[red]❌ 无法连接 Lyrica ({LYRICA_BASE_URL})，请先启动 Lyrica[/]")
        return

    console.print(f"[green]✅ Lyrica 已就绪 ({LYRICA_BASE_URL})[/]")

    # 准备歌词目录
    os.makedirs(LYRICS_DIR, exist_ok=True)

    # 扫描文件
    paths = load_library_paths()
    with console.status(f"[bold green]扫描音乐文件: {paths}...[/]"):
        files = scan_music_files(paths)

    if not files:
        console.print("[red]❌ 未找到任何音频文件[/]")
        return

    console.print(f"[green]✅ 找到 {len(files)} 个音频文件[/]")

    # 同步
    skipped = 0
    success = 0
    failed = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Syncing lyrics via Lyrica...", total=len(files))

        for file_path in files:
            file_name = os.path.basename(file_path)
            clean_name = os.path.splitext(file_name)[0]
            clean_name = re.sub(r'[\\/*?:"<>|]', "", clean_name)
            lrc_path = os.path.join(LYRICS_DIR, f"{clean_name}.lrc")

            progress.update(task, description=f"[cyan]{file_name}")

            # 跳过已有的
            if os.path.exists(lrc_path):
                skipped += 1
                progress.advance(task)
                continue

            artist, song = parse_artist_song(file_name)

            # 无 artist 时尝试把整个 clean_name 作为搜索词
            if not artist:
                lyric = fetch_lyric_lyrica(song, song)
            else:
                lyric = fetch_lyric_lyrica(artist, song)

            if lyric:
                try:
                    with open(lrc_path, 'w', encoding='utf-8') as f:
                        f.write(lyric)
                    success += 1
                except Exception as e:
                    console.print(f"[red]❌ 写入失败 {file_name}: {e}[/]")
                    failed += 1
            else:
                failed += 1

            progress.advance(task)

            # 随机延迟 0.1-0.5s，避免给 Lyrica 造成压力
            time.sleep(random.uniform(0.1, 0.5))

    # 总结
    console.print("\n[bold]🎉 Sync Completed![/]")
    console.print(f"[dim]Total: {len(files)}[/]")
    console.print(f"[green]Existing/Skipped: {skipped}[/]")
    console.print(f"[blue]Downloaded: {success}[/]")
    console.print(f"[red]Failed/Not Found: {failed}[/]")


if __name__ == "__main__":
    main()
