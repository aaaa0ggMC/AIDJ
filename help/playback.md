# Playback Controls

> **Category**: Playback

---

## SYNOPSIS

```
play           Resume / start playback
pause          Pause playback
toggle         Toggle play ↔ pause
stop           Stop playback
next | n       Skip to next track
prev | b       Go back to previous track
send           Push queued playlist to active DBus player
mpv            Push playlist to mpv
vlc            Push playlist to VLC
auto <cmd>     Set persistent auto-trigger
```

## DESCRIPTION

Direct player control via MPRIS DBus interface.

### Transport Controls

- **`play`** — Resume paused playback or start playing from queue.
- **`pause`** — Pause the currently active player.
- **`toggle`** — Flip between play and pause state.
- **`stop`** — Stop playback entirely.
- **`next`** / **`n`** — Skip to the next track in the player's queue.
- **`prev`** / **`b`** — Return to the previous track.

### Sending

- **`send`** — Push the current queue to whatever DBus player is auto-detected.
- **`mpv`** — Push the current queue specifically to mpv (opens it if needed).
- **`vlc`** — Push the current queue specifically to VLC (opens it if needed).

### Auto-Trigger

- **`auto`** — Without arguments, shows the current auto-trigger.
- **`auto mpv`** — Sets `mpv` as the persistent auto-trigger. After every
  `p` or `pc` generation, the queue is automatically pushed to mpv.
- **`auto vlc`** / **`auto send`** — Same for VLC or auto-detected player.
- **`auto off`** — Disable auto-trigger.

## SEE ALSO

- [p](cmd:p) — AI playlist generation
- [pc](cmd:pc) — Continuous AI DJ mode
- [ls](cmd:ls) — List available DBus players
