# AI Generation — `p`, `pr`, `r`

> **Aliases**: `p` / `prompt` / `gen`  |  `pr`  |  `r`
> **Category**: AI Generation

---

## SYNOPSIS

```
p <prompt>
pr
r
```

## DESCRIPTION

The core AI generation commands. Build playlists from natural-language prompts
using the configured LLM backend.

### `p` / `prompt` / `gen` — Generate

Creates a new DJ playlist from your prompt. The AI receives your music library
inventory, genre/emotion metadata, and play history, then returns a curated
tracklist.

```
p relaxing acoustic evening
p high energy J-rock for workout
p 有点忧伤的中文民谣
```

### `r` — Regenerate

Discards the last AI response and re-prompts with the same input. Useful when
the first suggestion doesn't hit the mark.

### `pr` — Partial Regenerate

Keeps the first few tracks from the current suggestion and re-generates the
rest. Great for tweaking without starting over.

## BEHAVIOR

1. AI receives full library context + genre/emotion tags + play history
2. Response is parsed for track names, fuzzy-matched against your library
3. Matched tracks are pushed to the queue and (if `auto` is set) sent to player
4. DJ intro commentary is displayed if present

## SEE ALSO

- [pc](cmd:pc) — Continuous AI DJ mode
- [auto](cmd:auto) — Set persistent auto-trigger
- [model](cmd:model) — Switch AI model
- [verbose](cmd:verbose) — Debug AI prompts/responses
