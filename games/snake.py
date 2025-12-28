import random
from rich.panel import Panel
from rich.align import Align

class Game:
    def __init__(self, width=24, height=10):
        self.width = width
        self.height = height
        self._reset()

    def _reset(self):
        self.snake = [(5, 5), (5, 4), (5, 3)]
        self.food = self._spawn_food()
        self.direction = (0, 1)
        self.score = 0
        self.game_over = False
        self.reset_timer = 0

    def _spawn_food(self):
        while True:
            f = (random.randint(1, self.height-2), random.randint(1, self.width-2))
            if f not in self.snake: return f

    def handle_input(self, key):
        if self.game_over or not key: return
        dirs = {'w': (-1, 0), 's': (1, 0), 'a': (0, -1), 'd': (0, 1)}
        if key in dirs:
            new_dir = dirs[key]
            if (self.direction[0] + new_dir[0] != 0) or (self.direction[1] + new_dir[1] != 0):
                self.direction = new_dir

    def render(self, step):
        if self.game_over:
            self.reset_timer += 1
            if self.reset_timer > 20:
                self._reset()
            return Panel(Align.center(f"[bold red]GAME OVER[/]\nScore: {self.score}\n[dim]Restarting...[/]"), 
                         title="🐍 Snake", border_style="red")

        if step % 2 == 0:
            head = self.snake[0]
            move = self.direction
            new_head = ((head[0]+move[0])%self.height, (head[1]+move[1])%self.width)
            
            if new_head in self.snake:
                self.game_over = True
            else:
                self.snake.insert(0, new_head)
                if new_head == self.food:
                    self.score += 1
                    self.food = self._spawn_food()
                else:
                    self.snake.pop()

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
