import random
from rich.panel import Panel
from rich.align import Align

class Game:
    def __init__(self, width=40, height=15):
        self.width = width
        self.height = height
        # Drops: [y_position, speed, trail_length, char_type]
        self.drops = [self._create_drop(x) for x in range(width)]
        self.chars = "ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍ012345789Z:・.="

    def _create_drop(self, x):
        return {
            "x": x,
            "y": random.randint(-20, 0),
            "speed": random.uniform(0.5, 1.5),
            "len": random.randint(3, 10)
        }

    def handle_input(self, key):
        pass # Screensaver mode, no input

    def render(self, step):
        grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        
        for d in self.drops:
            d["y"] += d["speed"]
            if d["y"] - d["len"] > self.height:
                d["y"] = random.randint(-10, 0)
                d["speed"] = random.uniform(0.5, 1.5)

            head_y = int(d["y"])
            for i in range(d["len"]):
                y = head_y - i
                if 0 <= y < self.height:
                    char = self.chars[(head_y + i*3) % len(self.chars)]
                    if i == 0:
                        grid[y][d["x"]] = f"[bold white]{char}[/]" # Head
                    elif i < 3:
                        grid[y][d["x"]] = f"[bright_green]{char}[/]" # Body top
                    else:
                        grid[y][d["x"]] = f"[green]{char}[/]" # Trail

        board_str = "\n".join(["".join(row) for row in grid])
        return Panel(Align.center(board_str), title="📟 SYSTEM HACKING", subtitle="Decrypting Playlist...", border_style="green", padding=(0,1))
