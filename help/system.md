# System Commands

> **Category**: System

---

## COMMANDS

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

---

## USAGE

### `model`

Switch the AI model used for chat and playlist generation.

```
model                    # list available models
model deepseek-chat      # switch to a specific model
model 2                  # select by index from the list
```

Available models are read from the `ai_settings.available_models` config key.
The selected model persists across sessions.

### `verbose`

Toggle detailed debug logging. When enabled:

- AI prompts and responses are logged with full details
- Volume balance adjustments show per-track dB deltas and target volumes
- Pre-analysis activity is reported in real time

### `record_freq`

Toggle play-count frequency tracking. When enabled, each **send** (manual
or via auto-trigger) increments the play count for each track in the queue.
Data persists across sessions in `data/frequency.csv`.

Note: simply previewing a playlist (`p`, `pr`, `r`) does **not** count as a
listen — only `send` / auto-triggered sends do.

### `concurrency` / `conc`

Set or view metadata sync concurrency. Controls how many songs are processed
in parallel when building metadata for new music files.

```
concurrency          # show current value
concurrency 4        # use 4 parallel workers
concurrency 1        # back to sequential (default)
```

Higher values (2-8) speed up initial metadata sync significantly, but
increase API request load. Capped at 16 to avoid rate limits.

### `token` / `tokens`

Display the total token usage for the current session, broken down by
prompt tokens and completion (generated) tokens. Values are read directly
from the API response's `usage` field — no local tokenizer required.

```
token    # show session totals
```

Output example:

```
📊 Tokens this session: 12.3k prompt + 4.5k completion = 16.8k total
```

Counters accumulate across all chat turns in the session. The `reset`
command resets counters along with chat history.

### `injects` / `inj`

Toggle which metadata fields are injected into AI prompts alongside song
names. Song names are always included; all other fields are optional.

```
injects                 # show all toggle states
injects review on       # enable review injection
injects loudness off    # disable loudness injection
```

Fields: `genre`, `emotion`, `language`, `loudness`, `review`.

Enabled fields appear as extra columns in the library table sent to the AI,
improving recommendation quality at the cost of higher token usage per
turn.

### `refresh`

Reload the session without clearing play history. Useful after changing
configuration or adding new music to the library.

### `reset`

Full reset — clears AI conversation history, played-song memory, and
re-initializes the session state. Use when the AI gets stuck in a loop.

### `status` / `check` / `conf`

Display the system configuration dashboard: Playback settings, Volume
Balance state, AI endpoint/model, and Debug toggles — grouped in panels.

### `help` / `?`

Quick command listing — shows all registered commands with their docstrings.

### `dhelp` / `??`

Detailed help browser. Renders external Markdown documentation.

```
dhelp           # command index with categorized tables
dhelp pc        # detailed PC mode documentation
dhelp volbal    # volume balance documentation
```

### `exit` / `quit` / `q`

Exit the AI DJ application. Frequency data is flushed to disk if recording
was enabled.

## SEE ALSO

- [generate](cmd:generate) — AI playlist generation commands
- [pc](cmd:pc) — Continuous AI DJ mode
- [volbal](cmd:volbal) — Volume balance controls
