# `volbal` / `balance` — Dynamic Volume Balancing

> **Aliases**: balance  |  **Category**: Volume Balance

---

## SYNOPSIS

```
volbal
```

## DESCRIPTION

Toggle dynamic volume balancing for PC mode. When enabled, the system
analyzes every track's loudness and automatically adjusts the MPRIS player
volume so all songs sound equally loud during continuous playback.

This is a toggle — calling it flips the state and persists to config.

## HOW IT WORKS

- **Anchor**: The first track played after enabling volbal sets a fixed
  loudness reference (the "anchor"). Player volume is pinned to 50%.
- **Drift-free**: Every subsequent track computes its target volume as an
  *absolute* value relative to the anchor:
  `target = 0.5 × 10^((anchor − song) / 20)`
  No chained adjustments — zero floating-point drift accumulation.
- **Pre-analysis**: The next track in queue is analyzed in a background
  thread while the current track plays, so switching is instant.
- **Full-song analysis**: The entire audio file is decoded and analyzed
  (peak + RMS + integrated LUFS).

## INITIAL SETUP

On first activation in PC mode, the system sets the MPRIS player volume
to **50%** and prints a reminder to use **system volume** for overall
level adjustments — not the player's own volume control.

## SEE ALSO

- [adjmethod](cmd:adjmethod) — Choose linear or LUFS loudness strategy
- [volcurve](cmd:volcurve) — Compensate for player volume curve
- [pc](cmd:pc) — Continuous AI DJ mode (where volbal applies)
- [verbose](cmd:verbose) — See per-track volume adjustment logs
