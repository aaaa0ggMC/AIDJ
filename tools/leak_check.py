"""Scan raw `music_metadata.jsonl` for CJK values not covered by the normaliser.

Runs each raw emotion / genre value through the normaliser and checks if the
*input* contains CJK characters that are NOT already in EMOTION_SYNONYMS or
GENRE_MAP.  Values already mapped (including those hitting the "Other"
fallback) are skipped — this tool shows only truly unmapped raw CJK strings.

Usage:
    uv run python tools/leak_check.py          # show all unmapped
    uv run python tools/leak_check.py --top 20 # top 20 by frequency
"""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.analyse import load_metadata, EMOTION_SYNONYMS, GENRE_MAP

CJK = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def _normalise_string(raw) -> str:
    if isinstance(raw, list):
        return ", ".join(str(v) for v in raw)
    return str(raw).strip().strip('"').strip("'")


def _smart_split(raw: str) -> list[str]:
    parts = re.split(r'[、/,，]|\band\b|\+', raw)
    return [p.strip() for p in parts if p.strip()]


def check_map(raw_value: str, mapping: dict) -> list[str]:
    """Return CJK sub-parts of raw_value NOT found in mapping."""
    s = _normalise_string(raw_value)
    if not s:
        return []
    leaks = []
    for part in _smart_split(s):
        key = part.strip().lower()
        if CJK.search(part) and key not in mapping:
            leaks.append(part.strip())
    return leaks


def main():
    top_n = None
    if "--top" in sys.argv:
        try:
            idx = sys.argv.index("--top")
            top_n = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            top_n = 20

    entries = load_metadata()
    print(f"Loaded {len(entries)} entries\n")

    for field, mapping in [("emotion", EMOTION_SYNONYMS), ("genre", GENRE_MAP)]:
        counter: Counter = Counter()
        for e in entries:
            raw = e.get("metadata", {}).get(field)
            if raw is None:
                continue
            for leak in check_map(raw, mapping):
                counter[leak] += 1

        if not counter:
            print(f"{field}: fully mapped — no unmapped CJK values")
        else:
            leaks = counter.most_common(top_n)
            print(f"{field}: {len(counter)} unmapped CJK terms (showing {len(leaks)}):")
            for val, count in leaks:
                print(f"  {count:>4}x  {val}")
        print()


if __name__ == "__main__":
    main()
