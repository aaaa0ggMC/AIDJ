import sys
import openai
import termios
import json
import os
import questionary
# [新增] 引入 Completer 接口
from prompt_toolkit.completion import WordCompleter, Completer 
from prompt_toolkit.history import FileHistory
from questionary import Style
from datetime import datetime

# 引入模块
from log import set_log_fn
from config import load_config, CFG_KEY_MF, ensure_playlist_dir
from dj_core import DJSession, scan_music_files, load_cached_metadata, sync_metadata
from wait_games import run_waiting_game
from player import DBusManager
import ui

from command_handler import Context, registry, console
import commands 

# --- Terminal Injection Helpers ---
fd = sys.stdin.fileno()
old_settings = None

def log_command_to_history(user_input, file_path="history.jsonl"):
    """
    将用户命令以 JSONL 格式追加到本地文件中。
    每行是一个独立的 JSON 对象，包含时间戳和命令内容。
    """
    # 过滤掉空输入或仅空格的输入
    if not user_input or not user_input.strip():
        return

    # 构建单行记录对象
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cmd": user_input.strip()
    }

    try:
        # 使用 'a' (append) 模式打开，如果文件不存在会自动创建
        with open(file_path, 'a', encoding='utf-8') as f:
            # ensure_ascii=False 保证中文命令不被转码为 \uXXXX
            line = json.dumps(entry, ensure_ascii=False)
            f.write(line + "\n")
    except Exception as e:
        # 记录日志报错，但不中断主程序运行
        print(f"[Log Error] Failed to save history: {e}")

def inject_pre():
    global old_settings
    old_settings = termios.tcgetattr(fd)

def inject_aft():
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    try: termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except: pass

# --- [新增] 自定义补全器逻辑 ---
class CommandOnlyCompleter(Completer):
    """
    智能补全器：只有在输入第一个单词（命令）时才触发补全。
    一旦输入了空格（进入参数部分），就停止补全。
    """
    def __init__(self, base_completer):
        self.base_completer = base_completer

    def get_completions(self, document, complete_event):
        # 获取光标前的文本，并去掉开头的空格
        text = document.text_before_cursor.lstrip()
        
        # 如果去掉开头空格后，文本里依然包含空格，说明用户已经打完了命令，正在打参数
        # 此时直接返回，不提供补全
        if " " in text:
            return

        # 否则，调用基础的 WordCompleter 进行补全
        yield from self.base_completer.get_completions(document, complete_event)

# --- Main ---

def main():
    set_log_fn(console.print)
    
    # 1. 初始化配置
    config = load_config()
    secrets = config.get("secrets", {})
    ai_settings = config.get("ai_settings", {})
    
    api_key = secrets.get("api_key") or secrets.get("deepseek", "")
    base_url = ai_settings.get("base_url", "https://api.deepseek.com")
    
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    dbus_manager = DBusManager(preferred_target=config['preferences'].get('dbus_target'))
    
    # 2. 准备数据
    musics = scan_music_files(config.get(CFG_KEY_MF, []))
    metadata = load_cached_metadata()
    
    # 3. 元数据同步
    missing = {k:v for k,v in musics.items() if k not in metadata}
    if missing:
        model = ai_settings.get("metadata_model", "deepseek-chat")
        metadata = sync_metadata(client, missing, metadata, model,
                                  concurrency=config['preferences'].get('metadata_concurrency', 1))
    
    ensure_playlist_dir()
    
    # 4. 创建 Session
    aidj = DJSession(client, metadata, musics, config, inject_pre, run_waiting_game, inject_aft)
    
    # 5. 构建 Context
    ctx = Context(aidj, dbus_manager, config)

    # 5.1 如果 record_freq 已启用，加载频率数据
    if config['preferences'].get('record_freq', False):
        from config import load_frequency
        ctx._freq = load_frequency()
        console.print(f"[green]📊 Frequency tracking loaded ({len(ctx._freq)} songs)[/]")
    else:
        ctx._freq = None
    
    # 6. UI Banner
    ui.print_banner(base_url, config['preferences']['model'])
    
    # 7. 准备 Prompt 工具
    history = FileHistory(".dj_history")
    
    # [修改] 先创建基础的 WordCompleter，再用我们的 CommandOnlyCompleter 包裹它
    base_completer = WordCompleter(registry.get_command_list(), ignore_case=True)
    smart_completer = CommandOnlyCompleter(base_completer)
    
    style = Style([
        ('qmark', 'fg:#673ab7 bold'),
        ('question', 'bold'),
        ('answer', 'fg:#f44336 bold'),
    ])

    # 8. 主循环
    while True:
        try:
            curr_trig = config['preferences'].get('saved_trigger')
            prefix = f"[⚡ {curr_trig}] " if curr_trig else ""
            
            user_input = questionary.text(
                f"{prefix}AIDJ >",
                qmark="🎤",
                style=style,
                history=history,
                completer=smart_completer # [修改] 使用智能补全器
            ).ask()
            
            if user_input is None: 
                console.print("[bold red]👋 Bye![/]")
                break
            
            log_command_to_history(user_input)
            
            registry.dispatch(user_input, ctx)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/]")
        except SystemExit:
            break
        except Exception as e:
            import traceback
            console.print(f"[red]CRITICAL ERROR: {e}[/]")
            traceback.print_exc()

if __name__ == "__main__":
    main()
