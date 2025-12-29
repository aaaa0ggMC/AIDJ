import shlex
from rich.console import Console
from rich.table import Table

# 全局 Console 对象，保证输出统一
console = Console()

class Context:
    """
    上下文对象：持有所有系统组件的状态。
    被传递给每一个命令函数。
    """
    def __init__(self, aidj, dbus, config, play_list=None):
        self.aidj = aidj
        self.dbus = dbus
        self.config = config
        self.play_list = play_list or [] # 全局播放列表
        self.console = console

class CommandRegistry:
    """命令注册与分发器"""
    def __init__(self):
        self.commands = {}
        self.descriptions = {}

    def register(self, *names):
        """装饰器：注册命令"""
        def decorator(func):
            for name in names:
                self.commands[name.lower()] = func
            desc = (func.__doc__ or "No description").strip().split('\n')[0]
            self.descriptions[names[0]] = desc
            return func
        return decorator

    def dispatch(self, raw_input, ctx: Context):
        """解析并执行命令"""
        if not raw_input.strip():
            return

        try:
            parts = shlex.split(raw_input)
        except ValueError:
            console.print("[red]❌ Error: Unmatched quotes in command.[/]")
            return

        cmd_name = parts[0].lower()
        args = parts[1:]

        if cmd_name in self.commands:
            try:
                self.commands[cmd_name](ctx, *args)
            except Exception as e:
                console.print(f"[red]❌ Execution Error: {e}[/]")
                # import traceback; traceback.print_exc() # Debug
        else:
            console.print(f"[red]❓ Unknown command: '{cmd_name}'. Type 'help' for list.[/]")

    def get_command_list(self):
        return list(self.commands.keys())

    def print_help(self):
        # 定义 4 列的表格 (Cmd | Desc || Cmd | Desc)
        t = Table(title="📜 Command Reference", show_lines=True, expand=True)
        
        # 第一组列
        t.add_column("Command", style="cyan", no_wrap=True)
        t.add_column("Description", style="white")
        
        # 第二组列 (中间加个空列或者直接并排，这里直接并排)
        t.add_column("Command", style="cyan", no_wrap=True)
        t.add_column("Description", style="white")

        # 获取所有排序后的 (命令, 描述) 元组
        items = sorted(self.descriptions.items())

        # 每次取 2 个进行循环 (步长为 2)
        for i in range(0, len(items), 2):
            # 左边的命令
            cmd1, desc1 = items[i]
            
            # 右边的命令 (检查是否存在，因为总数可能是奇数)
            if i + 1 < len(items):
                cmd2, desc2 = items[i+1]
            else:
                # 如果是奇数个，最后一行右边留空
                cmd2, desc2 = "", ""

            t.add_row(cmd1, desc1, cmd2, desc2)

        console.print(t) 

# 全局单例注册表
registry = CommandRegistry()
