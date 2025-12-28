import time
import random
import sys
import select
from rich.panel import Panel
from rich.align import Align
from rich.live import Live
from rich.layout import Layout
from rich.text import Text

# --- 🎮 输入监听核心 (非阻塞) ---
class InputHandler:
    @staticmethod
    def get_key():
        """
        检查是否有按键输入，非阻塞。
        返回: 'w', 'a', 's', 'd', ' ', or None
        """
        try:
            # select 检查 stdin 是否有数据可读，超时时间为 0 (立即返回)
            dr, dw, de = select.select([sys.stdin], [], [], 0)
            if dr:
                # 读取一个字符
                key = sys.stdin.read(1).lower()
                # 简单的清理，防止读取到换行符
                if key in ['\n', '\r']: return None
                return key
        except:
            pass
        return None

# --- 🕹️ 游戏 1: 贪吃蛇 (自动重启版) ---
class SnakeGame:
    def __init__(self, width=24, height=10):
        self.width = width
        self.height = height
        self._reset()

    def _reset(self):
        self.snake = [(5, 5), (5, 4), (5, 3)]
        self.food = self._spawn_food()
        self.direction = (0, 1) # (y, x) 初始向右
        self.score = 0
        self.game_over = False
        self.reset_timer = 0 # 失败后的倒计时

    def _spawn_food(self):
        while True:
            f = (random.randint(1, self.height-2), random.randint(1, self.width-2))
            if f not in self.snake: return f

    def handle_input(self, key):
        if self.game_over or not key: return
        dirs = {'w': (-1, 0), 's': (1, 0), 'a': (0, -1), 'd': (0, 1)}
        if key in dirs:
            new_dir = dirs[key]
            # 防止 180 度掉头
            if (self.direction[0] + new_dir[0] != 0) or (self.direction[1] + new_dir[1] != 0):
                self.direction = new_dir

    def render(self, step):
        if self.game_over:
            self.reset_timer += 1
            if self.reset_timer > 20: # 约 1.5 秒后重启
                self._reset()
            
            return Panel(Align.center(f"[bold red]GAME OVER[/]\nScore: {self.score}\n[dim]Restarting...[/]"), 
                         title="🐍 Snake", border_style="red")

        # 移动逻辑 (每2帧动一次，方便控制)
        if step % 2 == 0:
            head = self.snake[0]
            move = self.direction
            new_head = ((head[0]+move[0])%self.height, (head[1]+move[1])%self.width)
            
            # 撞到自己判定
            if new_head in self.snake:
                self.game_over = True
            else:
                self.snake.insert(0, new_head)
                if new_head == self.food:
                    self.score += 1
                    self.food = self._spawn_food()
                else:
                    self.snake.pop()

        # 绘图
        grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        for i, (y, x) in enumerate(self.snake):
            color = "green" if i == 0 else "bright_green"
            char = "●" if i == 0 else "o"
            if 0 <= y < self.height and 0 <= x < self.width: 
                grid[y][x] = f"[{color}]{char}[/]"
        
        fy, fx = self.food
        grid[fy][fx] = "[red]★[/]"

        board_str = "\n".join(["".join(row) for row in grid])
        return Panel(
            Align.center(board_str), 
            title=f"🐍 Snake [Score: {self.score}]", 
            subtitle="[W/A/S/D] Move",
            border_style="green",
            padding=(0,1)
        )

# --- 🕹️ 游戏 2: 恐龙快跑 (自动重启版) ---
class DinoGame:
    def __init__(self, width=30):
        self.width = width
        self.ground_chars = "._"
        self._reset()

    def _reset(self):
        self.dino_y = 0 # 0 = 地面, 1 = 跳起
        self.obstacles = [] 
        self.score = 0
        self.jump_timer = 0
        self.game_over = False
        self.reset_timer = 0

    def handle_input(self, key):
        # 空格跳跃
        if key == ' ' and self.dino_y == 0 and not self.game_over:
            self.dino_y = 2 
            self.jump_timer = 3 

    def render(self, step):
        if self.game_over:
            self.reset_timer += 1
            if self.reset_timer > 20: 
                self._reset()
            return Panel(Align.center(f"[bold red]CRASHED![/]\nScore: {self.score}\n[dim]Reviving...[/]"),
                         title="🦖 Dino Run", border_style="red")

        # 物理逻辑
        if self.jump_timer > 0:
            self.jump_timer -= 1
            if self.jump_timer == 0:
                self.dino_y = 0 

        # 障碍物生成与移动
        if step % 3 == 0: 
            self.score += 1
            self.obstacles = [x - 1 for x in self.obstacles if x > 0]
            if random.random() < 0.15 and (not self.obstacles or self.obstacles[-1] < self.width - 8):
                self.obstacles.append(self.width - 1)

        # 碰撞检测
        dino_x_pos = 4
        if self.dino_y == 0 and dino_x_pos in self.obstacles:
            self.game_over = True

        # 绘图
        sky_line = [" " for _ in range(self.width)]
        ground_line = [random.choice(self.ground_chars) for _ in range(self.width)]

        for ox in self.obstacles:
            if 0 <= ox < self.width:
                ground_line[ox] = "[red]🌵[/]"

        dino_char = "🦖"
        if self.dino_y > 0:
            sky_line[dino_x_pos] = dino_char
        else:
            ground_line[dino_x_pos] = dino_char

        scene = "".join(sky_line) + "\n" + "".join(ground_line)
        
        return Panel(
            Align.center(scene),
            title=f"🦖 Dino Run [Score: {self.score}]",
            subtitle="[SPACE] Jump",
            border_style="yellow",
            padding=(2, 2)
        )

# --- 🕹️ 游戏 3: 赛博接球 (自动重启版) ---
class PongGame:
    def __init__(self, width=26, height=10):
        self.width = width
        self.height = height
        self._reset()

    def _reset(self):
        self.paddle_y = self.height // 2
        self.ball = [self.height // 2, self.width // 2]
        self.vel = [1, 1] 
        self.score = 0
        self.game_over = False
        self.reset_timer = 0

    def handle_input(self, key):
        if self.game_over: return
        if key == 'w' and self.paddle_y > 1: self.paddle_y -= 1
        if key == 's' and self.paddle_y < self.height - 2: self.paddle_y += 1

    def render(self, step):
        if self.game_over:
            self.reset_timer += 1
            if self.reset_timer > 20: 
                self._reset()
            return Panel(Align.center(f"[bold red]MISSED![/]\nScore: {self.score}\n[dim]Next ball...[/]"), 
                         title="🏓 Pong", border_style="red")

        if step % 2 == 0:
            ny, nx = self.ball[0] + self.vel[0], self.ball[1] + self.vel[1]
            if ny <= 0 or ny >= self.height - 1: self.vel[0] *= -1
            if nx >= self.width - 1: self.vel[1] *= -1

            if nx == 1:
                if self.paddle_y - 1 <= ny <= self.paddle_y + 1:
                    self.vel[1] *= -1 
                    self.score += 1
                else:
                    self.game_over = True 
            
            self.ball = [self.ball[0] + self.vel[0], self.ball[1] + self.vel[1]]

        # 绘图
        grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        grid[self.paddle_y][1] = "║"
        if self.paddle_y > 0: grid[self.paddle_y-1][1] = "║"
        if self.paddle_y < self.height-1: grid[self.paddle_y+1][1] = "║"

        by, bx = int(self.ball[0]), int(self.ball[1])
        if 0 <= by < self.height and 0 <= bx < self.width:
            grid[by][bx] = "●"

        for i in range(self.height): grid[i][self.width-1] = "│"

        board_str = "\n".join(["".join(row) for row in grid])
        return Panel(Align.center(board_str), title=f"🏓 Pong [Score: {self.score}]", subtitle="[W/S] Move", border_style="cyan")

# --- 🎰 游戏 4: 赛博老虎机 (观赏模式) ---
class CyberSlots:
    def __init__(self):
        self.emojis = ["🎵", "🎹", "🎸", "🎷", "💿", "🔥", "🌊", "🚀"]
        self.genres = ["Jazz", "LoFi", "R&B", "Soul", "Funk", "Rock", "Trap"]
        self.actions = ["Decrypting...", "Analyzing...", "Matching...", "Scanning..."]
        self.hex_chars = "0123456789ABCDEF"

    def handle_input(self, key):
        pass 

    def render(self, step):
        e1 = self.emojis[step % len(self.emojis)]
        e2 = self.emojis[(step + 3) % len(self.emojis)]
        e3 = self.emojis[(step + 7) % len(self.emojis)]
        g1 = self.genres[step % len(self.genres)]
        hex_line = "".join(random.choice(self.hex_chars) for _ in range(20))
        
        content = f"""
[bold cyan]╔═══╗ ╔═══╗ ╔═══╗[/]
[bold cyan]║[/] {e1} [bold cyan]║ ║[/] {e2} [bold cyan]║ ║[/] {e3} [bold cyan]║[/]
[bold cyan]╚═══╝ ╚═══╝ ╚═══╝[/]

[bold magenta]>> {random.choice(self.actions)}[/]
[yellow]Genre: [bold white]{g1}[/][/]
[dim green]{hex_line}[/]
"""
        return Panel(content, title="🎰 Decryptor", border_style="magenta", padding=(1,2))

# --- 核心运行逻辑 ---
def run_waiting_game(stop_event):
    games = [SnakeGame(), DinoGame(), PongGame(), CyberSlots()]
    # 你可以这里指定，或者保留随机
    game = random.choice(games)
    
    with Live(refresh_per_second=15, transient=True, auto_refresh=False) as live:
        step = 0
        while not stop_event.is_set():
            key = InputHandler.get_key()
            if key:
                game.handle_input(key)
            
            live.update(game.render(step), refresh=True)
            time.sleep(0.05)
            step += 1
