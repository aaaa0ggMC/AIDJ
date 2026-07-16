# Playlist Editing

> **Category**: Playlist — Edit

---

## COMMANDS

| Command | Alias | Description |
|---|---|---|
| `add` | `insert` | Add songs to queue by name |
| `rm` | `del`, `remove` | Remove songs by index |
| `mv` | `move` | Move a song within the queue |
| `swap` | `sw` | Swap two queue positions |
| `shuffle` | `mix` | Randomize queue order |
| `reverse` | `rev` | Reverse queue order |
| `dedup` | `unique` | Remove duplicate entries |
| `clear` | `cls` | Clear entire queue |
| `top` | — | Move a track to position 1 |

---

## USAGE

### `add` / `insert`

Add tracks to the playlist by fuzzy-matching song names from your library.

```
add 晴天
add Blinding Lights Perfect
insert 夜曲
```

Multiple names can be added in one call.

### `rm` / `del` / `remove`

Remove tracks by their 1-indexed position in the queue. Use [view](cmd:view)
to see current positions.

```
rm 3           # remove 3rd song
rm 1 5 8       # remove songs at positions 1, 5, 8
```

### `mv` / `move`

Reposition a track. Indexes are 1-based.

```
mv 5 1          # move 5th song to top
mv 3 8          # move 3rd song to position 8
```

### `swap` / `sw`

Exchange two tracks' positions.

```
swap 2 4        # swap 2nd and 4th tracks
```

### `shuffle` / `mix`

Randomize the playlist order. No arguments.

### `reverse` / `rev`

Flip the playlist order (last becomes first). No arguments.

### `dedup` / `unique`

Remove duplicate tracks, keeping the first occurrence. Duplicates are detected
by song name (case-insensitive, with simplified-Chinese normalization).

### `clear` / `cls`

Remove all tracks from the queue. Irreversible — use with caution.

### `top`

Move a specific track to the head of the queue.

```
top 7           # move 7th song to position 1
```

## SEE ALSO

- [view](cmd:view) — Display current queue
- [save](cmd:save) — Save queue to named playlist
- [load](cmd:load) — Load saved playlist
- [show](cmd:show) — Inspect song metadata
