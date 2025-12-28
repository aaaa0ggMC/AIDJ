import random
from rich.panel import Panel

class Game:
    def __init__(self):
        self.emojis = ["🎵", "🎹", "🎸", "🎷", "💿", "🔥", "🌊", "🚀"]
        self.genres = ["Jazz", "LoFi", "R&B", "Soul", "Funk", "Rock", "Trap"]
        self.actions = ["Decrypting...", "Analyzing...", "Matching...", "Scanning..."]
        self.hex_chars = "0123456789ABCDEF"

    def handle_input(self, key):
        pass # 老虎机模式主要作为视觉屏保，不需要交互

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
