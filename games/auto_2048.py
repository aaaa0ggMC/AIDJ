import random
from rich.panel import Panel
from rich.align import Align
from rich.table import Table

class Game:
    def __init__(self):
        self.size = 4
        self._reset()

    def _reset(self):
        self.grid = [[0]*4 for _ in range(4)]
        self.score = 0
        self.game_over = False
        self._spawn()
        self._spawn()
        self.auto_timer = 0  # 自动操作计时器

    def _spawn(self):
        empty = [(r, c) for r in range(4) for c in range(4) if self.grid[r][c] == 0]
        if empty:
            r, c = random.choice(empty)
            self.grid[r][c] = 2 if random.random() < 0.9 else 4

    def _merge(self, row):
        new_row = [i for i in row if i != 0]
        for i in range(len(new_row)-1):
            if new_row[i] == new_row[i+1]:
                new_row[i] *= 2
                self.score += new_row[i]
                new_row[i+1] = 0
        new_row = [i for i in new_row if i != 0]
        return new_row + [0]*(4-len(new_row))

    def move(self, direction):
        if self.game_over: return False
        original = [r[:] for r in self.grid]
        
        if direction == 'w': # Up
            self.grid = [list(r) for r in zip(*self.grid)]
            self.grid = [self._merge(r) for r in self.grid]
            self.grid = [list(r) for r in zip(*self.grid)]
        elif direction == 's': # Down
            self.grid = [list(r) for r in zip(*self.grid)]
            self.grid = [self._merge(r[::-1])[::-1] for r in self.grid]
            self.grid = [list(r) for r in zip(*self.grid)]
        elif direction == 'a': # Left
            self.grid = [self._merge(r) for r in self.grid]
        elif direction == 'd': # Right
            self.grid = [self._merge(r[::-1])[::-1] for r in self.grid]

        if self.grid != original:
            self._spawn()
            return True
        return False

    def handle_input(self, key):
        if self.game_over: 
            if key: self._reset()
            return
        
        # 用户介入时，执行移动
        if key in ['w', 'a', 's', 'd']:
            self.move(key)

    def render(self, step):
        # --- 自动演示逻辑 (Auto Bot) ---
        if not self.game_over:
            # 每 3 帧 (约0.2秒) 自动动一次
            if step % 3 == 0:
                # 简单的 AI：随机尝试移动，或者稍微聪明点（优先向下/向右）
                moves = ['s', 'd', 'a', 'w'] 
                # 这里用纯随机，观赏性也不错，看它怎么把自己玩死
                random.shuffle(moves)
                for m in moves:
                    if self.move(m): break
        else:
            # 游戏结束后，自动重置逻辑
            self.auto_timer += 1
            if self.auto_timer > 30: # 约2秒后自动重开
                self._reset()
                return Panel(Align.center(f"[bold red]GAME OVER[/]\nScore: {self.score}\n[dim]Auto Restarting...[/]"), 
                             title="🔢 2048 Bot", border_style="red")

        # --- 绘图 ---
        t = Table.grid(padding=1)
        for row in self.grid:
            cells = []
            for val in row:
                if val == 0: 
                    style, text = "dim", "·"
                else:
                    color = {2:"white", 4:"cyan", 8:"blue", 16:"green", 32:"yellow", 64:"red", 128:"bold red", 256:"bold magenta"}.get(val, "bold magenta")
                    style, text = color, str(val)
                cells.append(f"[{style}]{text:^4}[/]")
            t.add_row(*cells)
            
        return Panel(Align.center(t), title=f"🔢 2048 [Score: {self.score}]", subtitle="[W/A/S/D] Takeover", border_style="bold white")
