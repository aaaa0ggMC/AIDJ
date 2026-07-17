# Analyse Command

> **Category**: Analytics

---

## COMMANDS

| Command | Alias | Description |
|---|---|---|
| `analyse` | `stats` | Metadata distribution analysis |
| `freqtop` | `ftop` | Top N most-played songs |
| `discover` | `disc`, `fresh` | Discover underplayed songs |

---

## USAGE

### `analyse` / `stats`

Compute distribution of metadata tags across your library.

```
analyse              # language distribution (default)
analyse language     # same: lang
analyse emotion      # emotion tags: emo
analyse genre        # genre tags: gen
```

The command reads `data/music_metadata.jsonl` and normalises AI-generated
metadata — merging synonyms (e.g. "Chinese" / "中文" / "zh" → "Chinese"),
splitting compound values (e.g. "English, Chinese" or arrays), and producing
a ranked distribution with bar charts.

Output example:
```
📊 Metadata Distribution: Language (52 unique, 2590 total)

  Chinese                   ██████████████████████████████   890 (34.4%)
  English                   ████████████████████████████     734 (28.3%)
  Japanese                  ████████████████████             457 (17.6%)
  Instrumental              ████████                         244 ( 9.4%)
  ...
```

### `freqtop` / `ftop`

Show your top N most-played songs. Produces a playlist so auto-trigger can
immediately play them.

```
freqtop         # top 20 (default)
freqtop 10      # top 10
```

### `discover` / `disc` / `fresh`

Surface underplayed tracks from your library. Two-tier strategy:

1. **Unheard** — pick from tracks with zero play-count (random sample)
2. **Fallback** — if everything has been played, pick the least-played tracks

```
discover        # sample up to 20 tracks
discover 50     # sample 50
```

Always sets the playlist so `auto send` will play results immediately.
