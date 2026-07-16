import time
import random
import sys
import select
import os
import importlib
import pkgutil
from rich.live import Live
from rich.panel import Panel
from rich.align import Align
import tty

# --- 🎮 输入监听核心 (通用) ---
class InputHandler:
    @staticmethod
    def get_key():
        """
        检查是否有按键输入，非阻塞。
        返回: 'w', 'a', 's', 'd', ' ', 'p', or None
        """
        try:
            dr, dw, de = select.select([sys.stdin], [], [], 0)
            if dr:
                key = sys.stdin.read(1).lower()
                if key in ['\n', '\r']: return None
                return key
        except (OSError, ValueError):
            pass
        return None

def get_all_games():
    """获取所有可用游戏模块名的列表"""
    game_folder = os.path.join(os.path.dirname(__file__), "games")
    return [name for _, name, _ in pkgutil.iter_modules([game_folder])]

def load_game(game_name):
    """加载指定名称的游戏"""
    try:
        module = importlib.import_module(f"games.{game_name}")
        # 强制重新加载，确保每次切换都能重置状态 (如果是单例模式的话，虽然这里是实例化类)
        importlib.reload(module)
        return module.Game(), game_name
    except Exception as e:
        return None, str(e)

# --- 核心运行逻辑 ---
def run_waiting_game(stop_event, ai_status=None):
    # 阻止回显，确保退出时恢复终端设置
    import termios
    old_tty = termios.tcgetattr(sys.stdin.fileno())
    tty.setcbreak(sys.stdin.fileno())

    try:
        _run_waiting_game_inner(stop_event, ai_status)
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_tty)

def _run_waiting_game_inner(stop_event, ai_status=None):
    # 1. 获取游戏列表
    available_games = get_all_games()

    if not available_games:
        from rich.console import Console
        Console().print("[red]No games found in /games folder[/]")
        while not stop_event.is_set(): time.sleep(1)
        return

    # 2. 初始随机加载一个
    current_game_name = random.choice(available_games)
    game, name = load_game(current_game_name)

    if not game:
        from rich.console import Console
        Console().print(f"[red]Failed to load game: {name}[/]")
        return

    with Live(refresh_per_second=15, transient=True, auto_refresh=False) as live:
        step = 0
        while not stop_event.is_set():
            # 获取按键
            key = InputHandler.get_key()

            # --- [NEW] 切换游戏逻辑 ---
            if key == 'p':
                # 随机选一个（除了当前这个，防止切到同一个）
                others = [g for g in available_games if g != current_game_name]
                if others:
                    current_game_name = random.choice(others)
                elif available_games:
                    current_game_name = available_games[0] # 只有一个游戏时

                # 重新加载新游戏
                game, name = load_game(current_game_name)
                step = 0 # 重置步数
                key = None # 消耗掉按键，不传给新游戏

            # --- 正常游戏逻辑 ---
            if key and game:
                game.handle_input(key)

            if game:
                renderable = game.render(step)

                # 动态修改 Panel subtitle 显示 AI 进度
                if ai_status and isinstance(renderable, Panel):
                    count = ai_status.get('count', 0)
                    # 在原 subtitle 后增加切换提示
                    base_sub = renderable.subtitle or ""
                    # 避免重复叠加提示
                    if "[P] Switch" not in base_sub:
                        new_sub = f"{base_sub} | [dim]🧠 AI: [bold cyan]{count}[/] chars | [P] Switch Game[/]"
                    else:
                        # 如果是游戏自带的渲染逻辑，我们可能需要硬覆盖或者保留 AI 计数
                        new_sub = f"[dim]🧠 AI: [bold cyan]{count}[/] chars | [P] Switch Game[/]"

                    renderable.subtitle = new_sub

                live.update(renderable, refresh=True)

            time.sleep(0.05)
            step += 1

# --- 独立游戏模式 ---
def run_free_play():
    """独立运行游戏（不依赖 AI 等待事件），按 Q 退出。"""
    import termios
    old_tty = termios.tcgetattr(sys.stdin.fileno())
    tty.setcbreak(sys.stdin.fileno())

    try:
        _run_free_play_inner()
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_tty)

def _run_free_play_inner():
    from rich.console import Console
    c = Console()

    available_games = get_all_games()
    if not available_games:
        c.print("[red]No games found in /games folder[/]")
        return

    current_game_name = random.choice(available_games)
    game, name = load_game(current_game_name)

    if not game:
        c.print(f"[red]Failed to load game: {name}[/]")
        return

    with Live(refresh_per_second=15, transient=True, auto_refresh=False) as live:
        step = 0
        while True:
            key = InputHandler.get_key()

            if key == 'q':
                break

            if key == 'p':
                others = [g for g in available_games if g != current_game_name]
                if others:
                    current_game_name = random.choice(others)
                elif available_games:
                    current_game_name = available_games[0]
                game, name = load_game(current_game_name)
                step = 0
                key = None

            if key and game:
                game.handle_input(key)

            if game:
                renderable = game.render(step)
                if isinstance(renderable, Panel):
                    base_sub = renderable.subtitle or ""
                    if "[P] Switch" not in base_sub:
                        renderable.subtitle = f"{base_sub} | [dim][P] Switch | [Q] Quit[/]"
                live.update(renderable, refresh=True)

            time.sleep(0.05)
            step += 1
