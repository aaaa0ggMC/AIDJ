import re
import requests
import threading
from log import *
from tqdm import tqdm
from rich.panel import Panel
from rapidfuzz import process, fuzz
from concurrent.futures import ThreadPoolExecutor

from config import *

def get_song_info(client, song_info, model_name):
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "提取歌曲信息JSON: language, emotion, genre, loudness, review"},
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
    log(f"[cyan]🚀 Syncing {len(targets)} new songs using {model_name}... (Ctrl+C to skip)[/]")
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
        log("\n[yellow]⚠️ Sync skipped.[/]")
    return metadata

class DJSession:
    def __init__(self, client, metadata, music_paths, config , wait_inject_prepare , wait_inject_main , wait_inject_after):
        self.client = client
        self.metadata = metadata
        self.music_paths = music_paths
        self.config = config
        self.chat_history = []
        self.turn_count = 0
        self.played_songs = set()
        self.wait_injects = [wait_inject_prepare,wait_inject_main,wait_inject_after]

    def refresh(self, clear_history=False):
        self.played_songs.clear()
        if clear_history:
            self.chat_history = []
            self.turn_count = 0
            log("[yellow]🧹 Cleared History[/]")
        else:
            log("[yellow]🧹 Cleared Played Songs[/]")

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
            if is_verbose: log(f"[dim]✅ Separator found. Parsing list...[/]")
        else:
            if is_verbose and source == "AI":
                log(f"[dim]ℹ️ No separator found. Treating as pure conversation.[/]")
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
                if is_verbose: log(f"[dim]🔍 Match: {clean} -> [green]{match_name}[/][/]")
                match = match_name

            if match:
                playlist_names.append(match)
            else:
                if is_verbose and SEPARATOR in raw_text:
                     log(f"[dim]❌ Ignored line: {clean}[/]")

        playlist_names = list(dict.fromkeys(playlist_names))
        playlist = []
        for name in playlist_names:
            if source == "AI": self.played_songs.add(name)
            playlist.append({"name": name, "path": self.music_paths[name]})

        return playlist, intro_text

    def next_step(self, user_request,external_status = None):
        # --- 1. 配置与状态更新 ---
        self.turn_count += 1
        model = self.config['preferences']['model']
        is_verbose = self.config['preferences']['verbose']

        if is_verbose: log(f"[dim]🤖 Thinking with {model}...[/]")

        # --- 2. 构建系统指令 (System Prompt - Optimized) ---
        # 使用“协议模式”告诉AI，它正在通过一个严格的管道传输数据
        base_prompt = f"""
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
            if is_verbose: log("[dim]🔄 Context refreshed with strict library constraints.[/]")

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
        ai_status = external_status if external_status is not None else {'count': 0}  # 共享状态：字数统计

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
        if self.wait_injects[0] is not None:
            self.wait_injects[0]()
        result = None

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(ask_ai_streaming)
            try:
                # 传入 stop_event 和 ai_status
                if self.wait_injects[1] is not None:
                    self.wait_injects[1](stop_event, ai_status)

            except KeyboardInterrupt:
                log("\n[dim]⚠️ Interrupted.[/]")
                stop_event.set()
                return [], ""
            finally:
                if self.wait_injects[2] is not None:
                    self.wait_injects[2]()

            result = future.result()

        # --- 6. 结果处理 ---
        if isinstance(result, Exception):
            err_msg = str(result)
            if "timeout" in err_msg.lower():
                log(f"[red]⏳ AI Request Timed Out (180s)[/]")
            else:
                log(f"[red]❌ API Error:[/]{err_msg}")
            return [], ""

        # 流式返回的已经是完整字符串了
        raw = result

        # 清洗 <think> 标签 (针对 DeepSeek R1 等推理模型)
        clean_content = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        if not clean_content: clean_content = raw

        if is_verbose:
            log(Panel(raw, title="Raw AI Output (With Thoughts)", border_style="dim"))

        # 存入历史
        self.chat_history.append({"role": "assistant", "content": clean_content})

        # 解析并返回
        return self.parse_raw_playlist(clean_content, source="AI")
