# Tools

辅助脚本，从 `tools/` 目录下运行。

## download_music

```bash
cd tools && ./download_music "<关键词>"
```

通过 Netease Cloud Music API (`pyncm`) 下载音乐到 `$HOME/CChaos/Musics`。

需要: `~/.ncm_info` 登录凭据文件（位于 `$HOME/Apps/ncm_info`）。

## lyrics_sync

```bash
uv run python tools/lyrics_sync.py
```

批量下载歌词（LRC 文件），从 Netease Cloud Music API 获取，存入 `data/lyrics/`。

需要: NCM API (`localhost:3000`) 正在运行。

## lyrics_sync_lyrica

```bash
uv run tools/lyrics_sync_lyrica.py
```

批量下载歌词（LRC 文件），通过 Lyrica API 获取，存入 `data/lyrics/`。

需要: Lyrica 服务在 `localhost:2778` 运行 (`$HOME/Apps/start_lyrica`)。

## simp_zhconv

```bash
uv run python tools/simp_zhconv.py
```

将 `data/lyrics/` 中的简体中文 LRC 歌词批量转换为繁体中文 (`zh-tw`)，输出到 `data/lyrics_tc/`。

## leak_check

```bash
uv run python tools/leak_check.py          # 全部 unmapped 中文词
uv run python tools/leak_check.py --top 20 # top 20
```

扫描 `data/music_metadata.jsonl`，找出 emotion / genre 中尚未被
`core/analyse.py` 映射的 CJK 词汇。输出结果可逐个添加到 `EMOTION_SYNONYMS`
或 `GENRE_MAP` 中，逐步提升 `analyse` 命令的归一化覆盖率。
