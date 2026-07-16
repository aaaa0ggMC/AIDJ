# `volcurve` / `curve` — MPRIS Volume Curve Compensation

> **Aliases**: curve  |  **Category**: Volume Balance

---

## SYNOPSIS

```
volcurve              # view current curve exponent
volcurve <number>     # set exponent (0.5 – 5.0)
```

## DESCRIPTION

Most media players (mpv, VLC) apply a **non-linear curve** to the MPRIS
Volume property. While the MPRIS spec says Volume should be linear
(0.5 = half amplitude = −6dB), these players internally map it through
a cubic or power-law curve inherited from their UI volume slider.

This command sets the **inverse compensation exponent**. The system
computes the linear target volume, then raises it to `1/curve` before
sending it over D-Bus. The player's own curve then squashes it back to
the correct level.

## RECOMMENDED VALUES

| Exponent | Player |
|---|---|
| `1.0` | Strict MPRIS spec players (deadbeef, some bare ALSA sinks) |
| `2.0` | Light curve — if 3.0 over-compensates |
| `3.0` | **mpv / VLC** default cubic curve (recommended) |
| `4.0` | Aggressive — if 3.0 still under-compensates |

## MATH

```
desired_gain  = 10^((anchor − song_loudness) / 20)
linear_target = base_volume × desired_gain
mpris_target  = linear_target ^ (1 / curve)
```

Player then applies: `actual_gain = mpris_target ^ curve = linear_target` ✓

## EXAMPLES

```
volcurve        # prints: "Current curve: 3.0"
volcurve 1.0    # linear — for spec-compliant players
volcurve 2.5    # custom — fine-tune between 2.0 and 3.0
```

## SEE ALSO

- [volbal](cmd:volbal) — Toggle volume balancing
- [adjmethod](cmd:adjmethod) — Choose linear or LUFS loudness strategy
- [pc](cmd:pc) — Continuous AI DJ mode
