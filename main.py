import sys
import openai
import termios
import questionary
# [新增] 引入 Completer 接口
from prompt_toolkit.completion import WordCompleter, Completer 
from prompt_toolkit.history import FileHistory
from questionary import Style

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
        metadata = sync_metadata(client, missing, metadata, model)
    
    ensure_playlist_dir()
    
    # 4. 创建 Session
    aidj = DJSession(client, metadata, musics, config, inject_pre, run_waiting_game, inject_aft)
    
    # 5. 构建 Context
    ctx = Context(aidj, dbus_manager, config)
    
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
                
            registry.dispatch(user_input, ctx)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/]")
        except SystemExit:
            break
        except Exception as e:
            console.print(f"[red]CRITICAL ERROR: {e}[/]")
            # import traceback; traceback.print_exc()

if __name__ == "__main__":
    main()
