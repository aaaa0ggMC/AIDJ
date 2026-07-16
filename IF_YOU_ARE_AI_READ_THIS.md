# AI Agent Conventions — Read Before Coding

This file establishes mandatory conventions for any AI agent (Claude Code,
Copilot, etc.) contributing to this project.

---

## 1. When You Add a New Command

Whenever you register a new command via `@registry.register("cmdname")` in
`commands.py`, you **MUST** also:

### a) Update `help/index.md`

Add the new command to the appropriate category table. Follow the existing
four-column format:

```
| `cmdname` | `alias` | Short description |
```

Group it under the correct category (PLAYBACK, PLAYLIST, AI GENERATION, etc.).
If the command belongs to a new category, create a new category section.

### b) Create or update `help/<page>.md`

- If the command is complex enough to warrant its own page (PC mode, volume
  balance commands, lyrics), create `help/cmdname.md`.
- If it's a simple command, add it to an existing category page (e.g.,
  `help/playback.md` for transport controls, `help/playlist.md` for queue
  editing).
- Follow the established markdown format with these sections:
  ```
  # `cmdname` — Short Title
  > **Aliases**: ...  |  **Category**: ...
  ---
  ## SYNOPSIS
  ## DESCRIPTION
  ## USAGE / BEHAVIOR / OPTIONS (as appropriate)
  ## SEE ALSO
  ```

### c) SEE ALSO — Cross-Reference Format

Use this syntax for internal cross-references:

```markdown
[volbal](cmd:volbal) — Toggle volume balancing
```

This is automatically rendered by `dhelp` as **volbal** *(→ dhelp volbal)*.

### d) Check `dhelp` Links Work

Verify: `dhelp <newcommand>` renders the page. SEE ALSO links should show
the command name in bold with a dimmed hint path.

---

## 2. When You Add a New Config Preference

### a) Add to `config.py` `pref_defaults` dict

```python
pref_defaults = {
    ...
    "new_setting": default_value,
}
```

### b) Add to `ui.py` `print_status()` dashboard

New preferences must appear in the grouped status dashboard under the
appropriate section (PLAYBACK, VOLUME BALANCE, AI, DEBUG/LOGGING).

### c) If the preference is a toggle/strategy → add a command

Follow section 1 above for the new command. The command should:
- Accept no args → show current value
- Accept a value → set it and persist to config via `save_config()`
- Print a confirmation message

---

## 3. File Organization

| Path | Purpose |
|---|---|
| `commands.py` | All slash-command implementations |
| `command_handler.py` | Registry, Context, input loop |
| `config.py` | Configuration loading, saving, defaults |
| `player.py` | DBusManager, MPRIS integration |
| `dj_core.py` | AI DJ core (prompt building, parsing) |
| `loudness.py` | Audio analysis (soundfile + pyloudnorm) |
| `ui.py` | Rich UI components (status, playlist, metadata) |
| `help/` | dhelp markdown documentation |
| `help/index.md` | dhelp command index |
| `help/<name>.md` | Per-command or per-category docs |
| `IF_YOU_ARE_AI_READ_THIS.md` | This file |

---

## 4. Coding Style

- **No speculative abstractions**: Three similar lines → keep the repetition.
  Only abstract when a pattern stabilizes across 4+ uses.
- **User-facing strings**: English by default. Console output uses Rich markup
  (`[bold]`, `[cyan]`, `[dim]`, `[green]`).
- **Config persistence**: Always call `save_config(ctx.config)` after mutating.
- **Thread safety**: Any shared mutable state touched by background threads
  must use `threading.Lock()`.
- **Dependencies**: Add to `pyproject.toml` under `dependencies`. Run `uv sync`
  after adding. Do NOT edit `uv.lock` manually.

---

## 5. Testing / Verification

- `uv run python -c "from commands import cmd_xxx; print('OK')"` is the
  standard smoke test for import validity.
- For volume/loudness changes, verify with a real audio file:
  ```python
  from loudness import analyze_loudness, compute_volume, LoudnessCache
  ```

---

*Last updated: 2026-07-16*
