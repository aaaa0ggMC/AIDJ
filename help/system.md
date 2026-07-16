# System Commands

> **Category**: System

---

## COMMANDS

| Command | Alias | Description |
|---|---|---|
| `model` | — | Select AI model |
| `verbose` | — | Toggle debug logging |
| `record_freq` | — | Toggle play-count tracking |
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

Toggle play-count frequency tracking. When enabled, each time a track plays
(via PC mode), its count is incremented. Data is flushed to disk in batches
of 10 tracks. The AI uses frequency data to avoid over-playing tracks.

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
