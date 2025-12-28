import random
from rich.panel import Panel
from rich.align import Align

class Game:
    def __init__(self, width=30):
        self.width = width
        self.ground_chars = "._"
        self._reset()

    def _reset(self):
        self.dino_y = 0  # 0 = 地面, >0 = 空中
        self.obstacles = []
        self.score = 0
        self.jump_timer = 0
        self.game_over = False
        self.reset_timer = 0

    def handle_input(self, key):
        # 支持 空格, w, k 跳跃
        # 只有在地面(dino_y==0)且游戏未结束时才能跳
        if key in [' ', 'w', 'k'] and self.dino_y == 0 and not self.game_over:
            self.dino_y = 1  # 标记为跳起状态
            self.jump_timer = 8  # [修复] 增加滞空帧数 (8帧 * 0.05s ≈ 0.4s)

    def render(self, step):
        # --- 游戏结束逻辑 ---
        if self.game_over:
            self.reset_timer += 1
            if self.reset_timer > 20:
                self._reset()
            return Panel(Align.center(f"[bold red]CRASHED![/]\nScore: {self.score}\n[dim]Reviving...[/]"),
                         title="🦖 Dino Run", border_style="red")

        # --- 物理逻辑 (跳跃) ---
        if self.jump_timer > 0:
            self.jump_timer -= 1
            self.dino_y = 1 # 保持在空中
            if self.jump_timer == 0:
                self.dino_y = 0 # 落地

        # --- 障碍物生成与移动 ---
        if step % 3 == 0: # 控制游戏速度
            self.score += 1
            # 移动障碍物
            self.obstacles = [x - 1 for x in self.obstacles if x > 0]

            # 生成新障碍物 (随机概率 + 最小间距限制)
            if random.random() < 0.15 and (not self.obstacles or self.obstacles[-1] < self.width - 8):
                self.obstacles.append(self.width - 1)

        # --- 碰撞检测 ---
        dino_x_pos = 4
        # 只有当恐龙在地面 (dino_y == 0) 且位置与障碍物重叠时才算撞击
        if self.dino_y == 0 and dino_x_pos in self.obstacles:
            self.game_over = True

        # --- 绘图逻辑 ---
        # 初始化两行：天空和地面
        sky_line = [" " for _ in range(self.width)]
        ground_line = [random.choice(self.ground_chars) for _ in range(self.width)]

        # 绘制障碍物 (仙人掌都在地面上)
        for ox in self.obstacles:
            if 0 <= ox < self.width:
                ground_line[ox] = "[red]🌵[/]"

        # 绘制恐龙
        dino_char = "🦖"
        if self.dino_y > 0:
            # 跳起时画在天空行
            sky_line[dino_x_pos] = dino_char
            # 地面对应位置画个影子或留空，视觉效果更好
            ground_line[dino_x_pos] = "[dim]_[/]"
        else:
            # 在地面时画在地面行
            ground_line[dino_x_pos] = dino_char

        # 拼接画面
        scene = "".join(sky_line) + "\n" + "".join(ground_line)

        return Panel(
            Align.center(scene),
            title=f"🦖 Dino Run [Score: {self.score}]",
            subtitle="[SPACE/W] Jump", # 提示文字也更新一下
            border_style="yellow",
            padding=(2, 2)
        )
