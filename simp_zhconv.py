import os
import zhconv
from rich.console import Console
from rich.progress import track

# --- 配置区域 ---
INPUT_DIR = "./lyrics"           # 输入目录 (简体源文件)
OUTPUT_DIR = "./lyrics_tc"       # 输出目录 (繁体结果保存位置)
TARGET_LOCALE = 'zh-tw'          # 目标语言: 'zh-tw'(台湾正体), 'zh-hk'(香港繁体)

console = Console()

def convert_and_export():
    # 1. 检查输入目录
    if not os.path.exists(INPUT_DIR):
        console.print(f"[red]❌ 输入目录不存在: {INPUT_DIR}[/]")
        return

    # 2. 创建输出目录 (如果不存在)
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        console.print(f"[green]📂 创建输出目录: {OUTPUT_DIR}[/]")
    else:
        console.print(f"[yellow]📂 输出目录已存在: {OUTPUT_DIR} (将覆盖同名文件)[/]")

    # 3. 获取所有 .lrc 文件名 (只获取文件名，不带路径)
    # 使用 os.listdir 可以直接拿到文件名，方便我们保持文件名不变
    all_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".lrc")]

    if not all_files:
        console.print("[red]❌ 目录中没有找到 LRC 文件！[/]")
        return

    console.print(f"[bold green]🚀 开始处理 {len(all_files)} 个文件...[/]")
    console.print(f"[dim]模式: 内容转繁体 ({TARGET_LOCALE}) | 文件名保持不变[/]")

    success_count = 0
    error_count = 0

    # 4. 遍历处理
    for filename in track(all_files, description="Processing..."):
        src_path = os.path.join(INPUT_DIR, filename)
        dst_path = os.path.join(OUTPUT_DIR, filename) # 核心：输出路径使用原始文件名

        try:
            # 读取
            with open(src_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 转换内容
            converted_content = zhconv.convert(content, TARGET_LOCALE)

            # 写入到新目录
            with open(dst_path, 'w', encoding='utf-8') as f:
                f.write(converted_content)
            
            success_count += 1

        except Exception as e:
            console.print(f"[red]Error processing {filename}: {e}[/]")
            error_count += 1

    # 5. 总结
    console.print(f"\n[bold cyan]✨ 任务完成！[/]")
    console.print(f"[green]成功导出: {success_count}[/]")
    if error_count > 0:
        console.print(f"[red]失败: {error_count}[/]")
    console.print(f"[bold]📁 文件已保存至: {os.path.abspath(OUTPUT_DIR)}[/]")

if __name__ == "__main__":
    convert_and_export()
