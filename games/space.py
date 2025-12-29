import random
from rich.panel import Panel
from rich.align import Align

class Game:
    def __init__(self, width=28, height=12):
        self.width = width
        self.height = height
        self._reset()

    def _reset(self):
        self.ship_x = self.width // 2
        self.bullets = [] # (y, x)
        self.enemies = [] # (y, x)
        self.score = 0
        self.game_over = False
        self.reset_timer = 0

    def handle_input(self, key):
        if self.game_over: return
        if key == 'a' and self.ship_x > 0: self.ship_x -= 1
        if key == 'd' and self.ship_x < self.width - 1: self.ship_x += 1
        if key == ' ': self.bullets.append((self.height - 2, self.ship_x))

    def render(self, step):
        if self.game_over:
            self.reset_timer += 1
            if self.reset_timer > 20: self._reset()
            return Panel(Align.center(f"[bold red]DESTROYED![/]\nScore: {self.score}\n[dim]Rebuilding...[/]"), 
                         title="🚀 Space Shooter", border_style="red")

        # Logic
        # Move Bullets
        self.bullets = [(y-1, x) for y, x in self.bullets if y > 0]
        
        # Spawn Enemies
        if step % 10 == 0:
            ex = random.randint(0, self.width - 1)
            self.enemies.append((0, ex))
        
        # Move Enemies (slower)
        if step % 16 == 0:
            self.enemies = [(y+1, x) for y, x in self.enemies]

        # Collision
        new_bullets = []
        for b in self.bullets:
            hit = False
            for e in self.enemies:
                if b == e:
                    self.enemies.remove(e)
                    self.score += 10
                    hit = True
                    break
            if not hit: new_bullets.append(b)
        self.bullets = new_bullets

        # Game Over Check
        for ey, ex in self.enemies:
            if ey >= self.height - 1 or (ey == self.height-1 and ex == self.ship_x):
                self.game_over = True

        # Render
        grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        
        for ey, ex in self.enemies: grid[ey][ex] = "[red]👾[/]"
        for by, bx in self.bullets: grid[by][bx] = "[cyan]│[/]"
        grid[self.height-1][self.ship_x] = "[bold blue]▲[/]"

        board_str = "\n".join(["".join(row) for row in grid])
        return Panel(Align.center(board_str), title=f"🚀 Shooter [Score: {self.score}]", subtitle="[A/D] Move [SPACE] Shoot", border_style="blue")
