from rich.panel import Panel
from rich.align import Align

class Game:
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
        return Panel(
            Align.center(board_str), 
            title=f"🏓 Pong [Score: {self.score}]", 
            subtitle="[W/S] Move", 
            border_style="cyan"
        )
