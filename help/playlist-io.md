# Playlist — View, Save, Load, Init

> **Category**: Playlist — View / Manage

---

## COMMANDS

| Command | Alias | Description |
|---|---|---|
| `view` | `list`, `pl`, `queue` | Display current queue |
| `show` | — | Inspect song metadata |
| `save` | — | Save queue to file |
| `load` | — | Load from file |
| `init` | — | Set / scan MPRIS player |

---

## USAGE

### `view` / `list` / `pl` / `queue`

Display the current queue as a Rich table with columns: Track, Language,
Genre, Emotion, Loudness. A visual overview of what's queued up.

```
view
list
```

### `show`

Inspect metadata for a specific song or the currently playing track.

```
show               # show current track from DBus
show 晴天          # show metadata for a song by name
show 3             # show metadata for the 3rd queue entry
```

Displays: genre, language, emotion, decade, tempo, loudness, instruments,
and full tags in a formatted panel.

### `save`

Persist the current queue to a named playlist file under `playlists/`.

```
save evening_chill
save workout_mix
```

Saved playlists can be loaded later with `load`. If the filename already
exists, you'll be prompted to confirm overwrite.

### `load`

Restore a previously saved playlist into the current queue.

```
load evening_chill
load              # lists available saved playlists
```

Without arguments, displays a list of all saved playlist files with track
counts. With a filename, loads that playlist into the queue.

### `init`

Set or scan the target MPRIS player for DBus control.

```
init              # auto-detect and list available players
init mpv          # set mpv as target player
init vlc          # set VLC as target player
```

The detected player is stored in config and used by `send`, `auto`, and
all transport commands. See [ls](cmd:ls) to just list players without setting.

## SEE ALSO

- [playlist](cmd:playlist) — Edit operations (add, rm, mv, swap, etc.)
- [ls](cmd:ls) — List active DBus players
- [auto](cmd:auto) — Set persistent auto-trigger
- [p](cmd:p) — AI playlist generation
