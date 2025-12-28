import random
from rich.panel import Panel
from rich.align import Align

class Game:
    def __init__(self, width=30, height=15):
        self.width = width
        self.height = height
        self._reset()

    def _reset(self):
        self.bird_y = float(self.height // 2)
        self.bird_vel = 0.0
        self.gravity = 0.25
        self.jump_strength = -1.2
        self.pipes = [] # list of [x_pos, gap_y_start]
        self.score = 0
        self.game_over = False
        self.reset_timer = 0
        self.gap_size = 4

    def handle_input(self, key):
        if self.game_over: return
        if key in [' ', 'w', 'k']: # Jump
            self.bird_vel = self.jump_strength

    def render(self, step):
        if self.game_over:
            self.reset_timer += 1
            if self.reset_timer > 20: self._reset()
            return Panel(Align.center(f"[bold red]CRASHED![/]\nScore: {self.score}\n[dim]Respawning...[/]"), 
                         title="🐦 Flappy Bird", border_style="red")

        # Physics
        self.bird_vel += self.gravity
        self.bird_y += self.bird_vel
        
        # Pipe Logic
        if step % 8 == 0:
            gap_y = random.randint(1, self.height - self.gap_size - 1)
            self.pipes.append([self.width, gap_y])

        # Move pipes
        for p in self.pipes: p[0] -= 1
        self.pipes = [p for p in self.pipes if p[0] > -2]

        # Collision & Scoring
        bird_int_y = int(self.bird_y)
        if bird_int_y < 0 or bird_int_y >= self.height:
            self.game_over = True

        bird_x = 5 # Bird is fixed at x=5
        for p in self.pipes:
            px, gap_y = p
            if px == bird_x:
                self.score += 1
                if not (gap_y <= bird_int_y < gap_y + self.gap_size):
                    self.game_over = True

        # Render
        grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        
        # Draw Pipes
        for px, gap_y in self.pipes:
            if 0 <= px < self.width:
                for y in range(self.height):
                    if not (gap_y <= y < gap_y + self.gap_size):
                        grid[y][px] = "[green]║[/]"

        # Draw Bird
        if 0 <= bird_int_y < self.height:
            grid[bird_int_y][bird_x] = "[yellow]>[/]"

        board_str = "\n".join(["".join(row) for row in grid])
        return Panel(Align.center(board_str), title=f"🐦 Flappy [Score: {self.score}]", subtitle="[SPACE] Flap", border_style="yellow")
