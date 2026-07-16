# `dlyrics` / `lrc` — Synced Lyrics Display

> **Aliases**: lrc  |  **Category**: Player Control

---

## SYNOPSIS

```
dlyrics               # download + display synced lyrics for current track
dlyrics <song_name>   # lyrics for a specific song
dlyrics <index>       # lyrics for queue entry at index
```

## DESCRIPTION

Fetches synced (LRC-format) lyrics from QQ Music and displays them in real
time, synchronized to the playing track's position via DBus.

Features:

- **Synced scrolling**: Lyrics highlight at the correct timestamp as the
  song plays.
- **Rich Markdown rendering**: Lyrics use Rich's Markdown widget with
  centered alignment and color formatting.
- **Immersive mode hint**: Suggests running in fullscreen for best effect.
- **Fallback**: If synced lyrics aren't available for a song, falls back
  to static lyrics display.

## BEHAVIOR

1. Queries QQ Music API for LRC-format lyrics.
2. Parses `[mm:ss.xx]` timestamp tags from the LRC data.
3. Polls the current player's DBus position every ~200ms.
4. Renders a sliding window of lyrics around the current line.
5. Exits on Ctrl+C or when playback stops.

## SEE ALSO

- [show](cmd:show) — View static song metadata
- [init](cmd:init) — Set the DBus player target
