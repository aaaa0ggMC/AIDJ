# `pc` — Continuous AI DJ Mode

> **Aliases**: none  |  **Category**: AI Generation

---

## SYNOPSIS

```
pc <prompt>
```

## DESCRIPTION

PC Mode is the system's flagship continuous playback mode. It combines a
rolling 100-song memory with dynamic context pruning and autonomous batch
fetching to deliver an uninterrupted AI-curated listening experience.

Key characteristics:

- **Rolling Memory**: Maintains a `deque` of the last 100 played songs,
  preventing repeats while allowing the AI to understand session context.
- **Dynamic Prompting**: The first batch is generated from your initial prompt.
  Subsequent batches use a "sequence flow" prompt that references the rolling
  history for continuity.
- **Batch Fetching**: Songs are fetched in batches of 8+ and buffered in a
  secondary queue, so playback never stalls waiting for AI.
- **Auto-Suspension**: Game injectors are automatically paused during PC mode.

## OPTIONS

None. The entire argument string after `pc` is treated as the prompt.

## BEHAVIOR

1. **Initial batch** — AI generates songs matching the prompt, applies
   library-constraint filtering, deduplication, and push to the player.
2. **Consumer loop** — monitors player status. When the current track
   finishes, the next track is popped from the queue and sent.
3. **Pre-fetch** — when the buffer drops below 2 batches, a background
   thread spawns to request the next batch. The AI context is pruned to
   the last 10 messages to keep prompts efficient.
4. **Frequency recording** — if enabled (`record_freq`), each track switch
   bumps the play count, with batch flushes every 10 tracks.

## VOLUME BALANCE INTEGRATION

When Dynamic Volume Balance is enabled ([volbal](cmd:volbal)):

- **First track**: sets the MPRIS player volume to 50% and establishes a
  loudness anchor from that track's RMS (or LUFS) value.
- **Subsequent tracks**: computes the target volume for each new track
  relative to the anchor, applying the configured
  [adjmethod](cmd:adjmethod) and [volcurve](cmd:volcurve) compensation.
- **Pre-analysis**: the next track in queue is analyzed in a background
  thread while the current track plays, so switching is instant.

## SEE ALSO

- [volbal](cmd:volbal) — Toggle volume balancing
- [adjmethod](cmd:adjmethod) — Choose linear or LUFS loudness strategy
- [volcurve](cmd:volcurve) — Set MPRIS volume curve compensation
- [p](cmd:p) — Single-batch AI generation
- [record_freq](cmd:record_freq) — Track play counts
- [verbose](cmd:verbose) — Enable detailed VolBal debug logs

## EXAMPLES

```
pc relaxing acoustic evening
pc high energy J-rock workout
pc lo-fi beats with female vocals
```
