# `adjmethod` / `loudnorm` — Loudness Measurement Strategy

> **Aliases**: loudnorm  |  **Category**: Volume Balance

---

## SYNOPSIS

```
adjmethod              # view current strategy
adjmethod <linear|lufs>
```

## DESCRIPTION

Select which loudness metric to use when comparing songs for volume
balancing. The choice affects how accurately the system can match
perceived loudness across tracks.

## STRATEGIES

**`linear`** — RMS amplitude comparison.
- Computes root-mean-square power from audio samples.
- Fastest. Purely mathematical.
- Does NOT account for human ear frequency sensitivity.
- Two songs with identical RMS may sound different loudness levels
  if one is bass-heavy and the other is treble-heavy.

**`lufs`** — ITU-R BS.1770-4 integrated loudness (default).
- Uses the `pyloudnorm` library with K-weighting filters.
- Models human ear frequency perception.
- Industry standard for loudness normalization (streaming platforms).
- Slightly more CPU-intensive, but pre-analysis runs in background.

## EXAMPLES

```
adjmethod           # prints: "Current: lufs"
adjmethod linear    # switch to RMS
adjmethod lufs      # switch to perceptual LUFS
```

## SEE ALSO

- [volbal](cmd:volbal) — Toggle volume balancing on/off
- [volcurve](cmd:volcurve) — Compensate for player volume curve
- [pc](cmd:pc) — Continuous AI DJ mode
