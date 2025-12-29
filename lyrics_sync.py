import os
import json
import time
import re
import random
import requests
import glob
from pathlib import Path

# 尝试引入 Rich，如果环境没装则报错提示
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
    from rich.panel import Panel
except ImportError:
    print("请先安装 rich: pip install rich")
    exit(1)

# 引入项目配置
try:
    from config import LYRICS_DIR, NCM_BASE_URL, CONFIG_FILE
except ImportError:
    #以此作为 fallback，防止单独运行找不到 config.py
    LYRICS_DIR = "./lyrics"
    NCM_BASE_URL = "http://localhost:3000" # 假设你的 NCM API 地址
    CONFIG_FILE = "./config.json"

console = Console()

# 支持的音频格式
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus'}

def load_library_paths():
    """从 config.json 读取音乐库路径，如果没配置则默认为当前目录"""
    paths = ["."]
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                # 假设配置里有个 library_paths 或者 music_dirs，如果没有就扫描当前文件夹
                # 你可以根据你实际 config.json 的结构修改这里
                if 'music_folders' in conf:
                    paths = conf['music_folders']
                elif 'music_dirs' in conf:
                    paths = conf['music_dirs']
        except Exception as e:
            console.print(f"[yellow]⚠️ 读取配置文件失败，将扫描当前目录: {e}[/]")
    return paths

def scan_music_files(paths):
    """扫描所有路径下的音频文件"""
    music_files = []
    for p in paths:
        if not os.path.exists(p):
            continue
        # 递归扫描
        for root, dirs, files in os.walk(p):
            for file in files:
                if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS:
                    full_path = os.path.join(root, file)
                    music_files.append(full_path)
    return music_files

def clean_filename(filename):
    """清洗文件名以便搜索 (移除扩展名、括号内容等)"""
    # 移除扩展名
    name = os.path.splitext(filename)[0]
    # 移除 (Live), [HQ] 等括号内容
    name = re.sub(r'[\(\[].*?[\)\]]', '', name)
    # 移除 feat. xxx
    name = re.sub(r'(?i)feat\..*', '', name)
    # 将下划线和连字符换成空格
    name = name.replace('_', ' ').replace('-', ' ')
    # 移除多余空格
    return " ".join(name.split())

def fetch_lyric_ncm(keyword):
    """调用 NCM API 下载歌词"""
    try:
        # 1. 搜索歌曲 ID
        search_url = f"{NCM_BASE_URL}/search"
        params = {"keywords": keyword, "limit": 1}
        resp = requests.get(search_url, params=params, timeout=5)
        data = resp.json()
        
        if data.get('code') != 200 or data['result']['songCount'] == 0:
            return None
        
        song_id = data['result']['songs'][0]['id']
        
        # 2. 获取歌词
        lrc_url = f"{NCM_BASE_URL}/lyric"
        resp = requests.get(lrc_url, params={"id": song_id}, timeout=5)
        lrc_data = resp.json()
        
        if lrc_data.get('code') == 200:
            lyric = lrc_data.get('lrc', {}).get('lyric')
            return lyric
    except Exception:
        return None
    return None

def main():
    console.clear()
    console.print(Panel.fit("[bold cyan]🎵 Lyric Sync Utility[/]", border_style="cyan"))

    # 1. 准备目录
    if not os.path.exists(LYRICS_DIR):
        os.makedirs(LYRICS_DIR)
        console.print(f"[green]📂 Created lyrics directory: {LYRICS_DIR}[/]")

    # 2. 扫描文件
    paths = load_library_paths()
    with console.status(f"[bold green]Scanning music files in: {paths}...[/]"):
        files = scan_music_files(paths)
    
    if not files:
        console.print("[red]❌ No music files found![/]")
        return

    console.print(f"[green]✅ Found {len(files)} audio files.[/]")
    
    # 3. 开始同步
    skipped = 0
    success = 0
    failed = 0
    
    # 使用 Rich 进度条
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        
        task = progress.add_task("[cyan]Syncing lyrics...", total=len(files))
        
        for file_path in files:
            file_name = os.path.basename(file_path)
            # 生成安全的歌词文件名 (与播放器逻辑一致)
            # 这里的逻辑必须和你播放器里 _get_lyrics_data 的 safe_name 逻辑尽量一致
            # 如果播放器是用 "Title - Artist" 搜的，这里最好也是。
            # 但这里我们只有文件名，通常文件名就是 "Title - Artist.mp3"
            
            clean_name_for_save = os.path.splitext(file_name)[0]
            # 简单清洗文件名用于保存 (去除系统非法字符)
            clean_name_for_save = re.sub(r'[\\/*?:"<>|]', "", clean_name_for_save)
            lrc_path = os.path.join(LYRICS_DIR, f"{clean_name_for_save}.lrc")
            
            progress.update(task, description=f"[cyan]Processing: {file_name}")

            # 检查是否已存在
            if os.path.exists(lrc_path):
                # console.print(f"[dim]⏭️  Skipped (Exists): {file_name}[/dim]")
                skipped += 1
                progress.advance(task)
                continue
            
            # 构造搜索关键词
            search_kw = clean_filename(file_name)
            
            # 下载
            lyric_content = fetch_lyric_ncm(search_kw)
            
            if lyric_content:
                try:
                    with open(lrc_path, 'w', encoding='utf-8') as f:
                        f.write(lyric_content)
                    # console.print(f"[green]⬇️  Downloaded: {file_name}[/]")
                    success += 1
                except Exception as e:
                    console.print(f"[red]❌ Write Error {file_name}: {e}[/]")
                    failed += 1
            else:
                # console.print(f"[yellow]⚠️  Not Found: {file_name}[/]")
                failed += 1
            
            progress.advance(task)
            
            # 随机延迟防止封禁 (0.1s - 0.5s)
            # time.sleep(random.uniform(0.1, 0.5))

    # 4. 总结
    console.print("\n[bold]🎉 Sync Completed![/]")
    console.print(f"[dim]Total Files: {len(files)}[/]")
    console.print(f"[green]Existing/Skipped: {skipped}[/]")
    console.print(f"[blue]Downloaded New: {success}[/]")
    console.print(f"[red]Failed/Not Found: {failed}[/]")

if __name__ == "__main__":
    main()
