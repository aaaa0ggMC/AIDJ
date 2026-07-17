# AI DJ — Command Reference

---

## PLAYBACK

| Command | Alias | Description |
|---|---|---|
| `play` | — | Resume / start playback |
| `pause` | — | Pause playback |
| `toggle` | — | Toggle play ↔ pause |
| `stop` | — | Stop playback |
| `next` | `n` | Skip to next track |
| `prev` | `b` | Go back to previous track |
| `send` | — | Push queued playlist to player |
| `mpv` | — | Push playlist to mpv |
| `vlc` | — | Push playlist to VLC |
| `auto` | — | Set persistent auto-trigger |

→ `dhelp playback` for details.

## PLAYLIST — Edit

| Command | Alias | Description |
|---|---|---|
| `add` | `insert` | Add songs to queue |
| `rm` | `del`, `remove` | Remove songs from queue |
| `mv` | `move` | Move a song within queue |
| `swap` | `sw` | Swap two queue positions |
| `shuffle` | `mix` | Randomize queue order |
| `reverse` | `rev` | Reverse queue order |
| `dedup` | `unique` | Remove duplicate entries |
| `clear` | `cls` | Clear entire queue |
| `top` | — | Move a track to queue head |

→ `dhelp playlist` for details.

## PLAYLIST — View / Manage

| Command | Alias | Description |
|---|---|---|
| `view` | `list`, `pl`, `queue` | Display current queue |
| `search` | `find`, `s` | Fuzzy search music library |
| `show` | — | Show song metadata |
| `save` | — | Save queue to named playlist |
| `load` | — | Load named playlist |
| `init` | — | Set / scan MPRIS target player |

→ `dhelp playlist-io` for details.

## AI GENERATION

| Command | Alias | Description |
|---|---|---|
| `p` | `prompt`, `gen` | Generate playlist from prompt |
| `r` | — | Regenerate last response |
| `pr` | — | Partial regenerate |
| `pc` | — | Continuous AI DJ mode |

→ `dhelp generate` and `dhelp pc` for details.

## ANALYTICS

| Command | Alias | Description |
|---|---|---|
| `analyse` | `stats` | Metadata distribution analysis |
| `freqtop` | `ftop` | Top N most-played songs |
| `discover` | `disc`, `fresh` | Discover underplayed songs |

→ `dhelp analyse` for details.

## PLAYER CONTROL

| Command | Alias | Description |
|---|---|---|
| `ls` | `players` | List available MPRIS players |
| `dlyrics` | `lrc` | Download + display synced lyrics |
| `games` | — | Built-in mini-games |

→ `dhelp lyrics` and `dhelp games` for details.

## VOLUME BALANCE

| Command | Alias | Description |
|---|---|---|
| `volbal` | `balance` | Toggle dynamic volume balancing |
| `adjmethod` | `loudnorm` | Set loudness method (linear / lufs) |
| `volcurve` | `curve` | Set volume curve compensation |

→ `dhelp volbal`, `dhelp adjmethod`, `dhelp volcurve` for details.

## SYSTEM

| Command | Alias | Description |
|---|---|---|
| `model` | — | Select AI model |
| `verbose` | — | Toggle debug logging |
| `record_freq` | — | Toggle play-count tracking |
| `concurrency` | `conc` | Set metadata sync concurrency |
| `token` | `tokens` | Show session token usage |
| `injects` | `inj` | Toggle library metadata injects |
| `refresh` | — | Refresh session (keep history) |
| `reset` | — | Full session reset |
| `status` | `check`, `conf` | Configuration dashboard |
| `help` | `?` | Quick command list |
| `dhelp` | `??` | Detailed help browser |
| `exit` | `quit`, `q` | Exit the application |

→ `dhelp system` for details.

---

Type `dhelp <command>` for detailed documentation.
