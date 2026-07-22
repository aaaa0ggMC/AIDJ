"""fuzz_lrc_match: 模糊匹配 mp3 → lrc，将匹配到的歌词拷贝到新目录。

用法:
  uv run tools/fuzz_lrc_match <music_dir> <lyrics_dir> <output_dir>

匹配逻辑:
  1. 从 music_dir 扫描所有 .mp3/.flac 等音频文件
  2. 从 lyrics_dir 扫描所有 .lrc 文件
  3. 对每个音频文件，用 difflib 在 lrc 列表中做模糊匹配
  4. 将最佳匹配拷贝到 output_dir，以音频文件名为准命名

示例:
  uv run tools/fuzz_lrc_match /Music/Netease-Translated /data/lyrics /data/lyrics_new
"""

import os
import re
import sys
import shutil
import difflib
from pathlib import Path

AUDIO_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".opus"}


def clean(name: str) -> str:
    """清洗文件名：去括号内容 / feat. / 多余空格，返回小写"""
    name = re.sub(r"[（(][^)）]*[)）]", "", name)
    name = re.sub(r"(?i)feat\..*", "", name)
    name = re.sub(r"[_\-]", " ", name)
    name = re.sub(r"\s+", " ", name)
    name = name.replace("／", " ")
    name = name.replace("．", ".")
    name = name.replace(".mp3", "").replace(".lrc", "")
    return name.strip().lower()


def stem(name: str) -> str:
    """去掉扩展名"""
    return os.path.splitext(name)[0]


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    music_dir = Path(sys.argv[1])
    lyrics_dir = Path(sys.argv[2])
    output_dir = Path(sys.argv[3])

    if not music_dir.is_dir():
        print(f"❌ music_dir 不存在: {music_dir}")
        sys.exit(1)
    if not lyrics_dir.is_dir():
        print(f"❌ lyrics_dir 不存在: {lyrics_dir}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 收集音频文件
    audio_files = []
    for f in music_dir.iterdir():
        if f.suffix.lower() in AUDIO_EXTS:
            audio_files.append(f)
    audio_files.sort()

    # 收集 lrc 文件
    lrc_files = []
    for f in lyrics_dir.iterdir():
        if f.suffix.lower() == ".lrc":
            lrc_files.append(f)

    # 构建 lrc 候选： (path, cleaned_name)
    lrc_candidates = [(p, clean(p.stem)) for p in lrc_files]
    lrc_texts = [c[1] for c in lrc_candidates]

    matched = 0
    skipped = 0
    not_found = 0

    for af in audio_files:
        af_clean = clean(af.stem)
        out_path = output_dir / f"{stem(af.name)}.lrc"

        if out_path.exists():
            skipped += 1
            continue

        # 精确匹配优先
        found = None
        for lrc_path, lrc_clean in lrc_candidates:
            if af_clean == lrc_clean:
                found = lrc_path
                break

        # 模糊匹配
        if found is None:
            matches = difflib.get_close_matches(af_clean, lrc_texts, n=1, cutoff=0.4)
            if matches:
                idx = lrc_texts.index(matches[0])
                found = lrc_candidates[idx][0]

        if found is not None:
            shutil.copy2(found, out_path)
            matched += 1
            print(f"  ✅ {af.name}  ←  {found.name}")
        else:
            not_found += 1
            print(f"  ❌ {af.name}  →  无匹配")

    print()
    print(f"🎯 完成!  匹配拷贝: {matched}  已存在跳过: {skipped}  无匹配: {not_found}")
    print(f"   输出目录: {output_dir}")


if __name__ == "__main__":
    main()
