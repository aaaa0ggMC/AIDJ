"""Metadata analyser — normalise & compute distributions for language / emotion / genre."""
import json
import re
from collections import Counter
from core.log import log

JSONL_PATH = "./data/music_metadata.jsonl"

# ── Language normalisation ────────────────────────────────

LANG_MAP = {
    # Chinese variants
    "chinese": "Chinese", "中文": "Chinese", "zh": "Chinese", "zh-cn": "Chinese",
    "chinese (mandarin)": "Chinese", "mandarin chinese": "Chinese",
    "mandarin": "Chinese", "华语": "Chinese", "国语": "Chinese",
    "chinese (cantonese)": "Cantonese", "chinese (cantonese/mandarin)": "Chinese",
    # Japanese
    "japanese": "Japanese", "日语": "Japanese", "ja": "Japanese",
    # Korean
    "korean": "Korean", "韩语": "Korean", "ko": "Korean",
    # English
    "english": "English", "en": "English", "英语": "English",
    # Other languages
    "french": "French", "法语": "French", "fr": "French",
    "german": "German", "德语": "German", "de": "German",
    "russian": "Russian", "俄语": "Russian", "ru": "Russian",
    "spanish": "Spanish", "西班牙语": "Spanish", "es": "Spanish",
    "italian": "Italian", "意大利语": "Italian",
    "portuguese": "Portuguese", "葡萄牙语": "Portuguese",
    "vietnamese": "Vietnamese", "越南语": "Vietnamese",
    "swedish": "Swedish", "瑞典语": "Swedish",
    "cantonese": "Cantonese", "粤语": "Cantonese",
    "indonesian": "Indonesian", "印尼语": "Indonesian",
    "korean": "Korean", "ko": "Korean", "韩文": "Korean", "韩国语": "Korean",
    "朝鲜语": "Korean",
    "sanskrit": "Sanskrit", "梵语": "Sanskrit",
    "latin": "Latin",
    "arabic": "Arabic",
    "hindi": "Hindi",
    "thai": "Thai", "泰语": "Thai",
    "tibetan": "Tibetan", "藏语": "Tibetan",
    "tagalog": "Tagalog",
    # Instrumental / no lyrics
    "instrumental": "Instrumental", "纯音乐": "Instrumental",
    "纯音乐（无歌词）": "Instrumental", "纯音乐 (无歌词)": "Instrumental",
    "纯音乐/器乐": "Instrumental",
    "无歌词": "Instrumental", "无": "Instrumental",
    "no lyrics": "Instrumental", "music_only": "Instrumental",
    "music": "Instrumental",
    # Unknown
    "未知": "Unknown", "unknown": "Unknown", "n/a": "Unknown",
    "none": "Unknown", "null": "Unknown", "unspecified": "Unknown",
    "unknown (instrumental)": "Instrumental", "muted": "Unknown",
    # Mixed / multi-language — keep as-is after splitting
    "japanese and english": "Japanese+English",
    "english and japanese": "Japanese+English",
    "chinese and english": "Chinese+English",
    "英语和日语": "Japanese+English", "日语和英语": "Japanese+English",
    "英语和粤语": "Cantonese+English",
    "japanese and english and chinese": "Mixed",
    "multi": "Mixed",
    "yi (nuosu) and chinese": "Chinese",
    "yi (nuosu)": "Yi",
    "vietnamese, english": "Vietnamese+English",
    # More Chinese edge-case patterns
    "乌克兰语": "Ukrainian", "粤语和英语": "Cantonese+English",
    "英语和西班牙语": "English+Spanish", "俄语和中文": "Chinese+Russian",
    "中文（包含哈尼族元素）": "Chinese",
    "多种语言（包括克林贡语、意大利语、英语）": "Mixed",
    "多语种": "Mixed", "意大利语": "Italian",
    "英语（纯音乐无歌词）": "Instrumental",
    "纯音乐无歌词": "Instrumental", "纯音乐 (不存在歌词)": "Instrumental",
    "无歌词纯音乐": "Instrumental",
    "无语言内容": "Instrumental", "无语言/纯音乐": "Instrumental",
    "无语言": "Instrumental", "无法确定": "Unknown",
}

LANG_KEYS = sorted(LANG_MAP.keys(), key=len, reverse=True)  # longest match first

def _normalise_string(raw) -> str:
    """Handle JSON arrays, strip quotes/whitespace, lowercase for matching."""
    if isinstance(raw, list):
        return ", ".join(str(v) for v in raw)
    s = str(raw).strip().strip('"').strip("'")
    return s

def _smart_split(raw: str) -> list[str]:
    """Split on common delimiters: Chinese comma, slash, English comma, or English 'and'."""
    # Split arrays
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parts = json.loads(raw)
            return [p.strip() for p in parts if p.strip()]
        except:
            pass
    # Split on 、 / , and "and"
    parts = re.split(r'[、/,，]|\band\b|\+', raw)
    return [p.strip() for p in parts if p.strip()]

def normalise_language(raw) -> str:
    """Normalise a single language string to a canonical label."""
    s = _normalise_string(raw).lower()
    if not s:
        return "Unknown"

    # Try direct match first
    if s in LANG_MAP:
        return LANG_MAP[s]

    # Try splitting multi-part values
    parts = _smart_split(s)
    if len(parts) > 1:
        normed = []
        for p in parts:
            n = normalise_language(p)
            if n not in ("Unknown",) and n not in normed:
                normed.append(n)
        if len(normed) == 1:
            return normed[0]
        if len(normed) > 1:
            return "+".join(normed)  # e.g. "Chinese+English"

    return _capitalise(raw)  # fallback: preserve as-is


def _capitalise(s: str) -> str:
    s = s.strip().strip('"').strip("'")
    if not s:
        return "Unknown"
    return s[0].upper() + s[1:] if len(s) > 1 else s.upper()


# ── Emotion normalisation ──────────────────────────────────

EMOTION_SYNONYMS = {
    "melancholy": "Melancholy", "melancholic": "Melancholy",
    "sadness": "Sadness", "sad": "Sadness", "悲伤": "Sadness", "忧郁": "Melancholy",
    "悲伤/忧郁": "Sadness",
    "happy": "Happy", "happiness": "Happy", "joy": "Happy", "joyful": "Happy",
    "欢快": "Happy", "快乐": "Happy", "喜悦": "Happy",
    "calm": "Calm", "peaceful": "Calm", "serene": "Calm",
    "平静": "Calm", "宁静": "Calm", "安静": "Calm",
    "neutral": "Neutral", "中性": "Neutral",
    "energetic": "Energetic", "兴奋": "Energetic", "激昂": "Energetic",
    "hopeful": "Hopeful", "希望": "Hopeful", "积极": "Hopeful",
    "激励": "Hopeful", "励志": "Hopeful",
    "romantic": "Romantic", "浪漫": "Romantic",
    "contemplative": "Contemplative", "reflective": "Contemplative",
    "反思": "Contemplative", "沉思": "Contemplative",
    "nostalgic": "Nostalgic", "怀旧": "Nostalgic", "nostalgia": "Nostalgic",
    "bittersweet": "Bittersweet",
    "playful": "Playful", "幽默": "Playful", "诙谐": "Playful",
    "angry": "Angry", "愤怒": "Angry", "aggressive": "Angry",
    "confident": "Confident", "自信": "Confident",
    "mysterious": "Mysterious", "神秘": "Mysterious",
    "dark": "Dark", "tense": "Dark", "紧张": "Dark", "悬疑": "Dark",
    "lonely": "Lonely", "孤独": "Lonely", "introspective": "Lonely",
    "yearning": "Yearning", "longing": "Yearning", "渴望": "Yearning",
    "未知": "Unknown", "unknown": "Unknown", "null": "Unknown",
    "elegant": "Elegant", "优雅": "Elegant",
    "epic": "Epic", "宏大": "Epic",
    "uplifting": "Hopeful", "inspirational": "Hopeful",
    "relaxing": "Calm", "chill": "Calm", "laid-back": "Calm",
    "dreamy": "Dreamy", "梦幻": "Dreamy",
    "gentle": "Gentle", "温柔": "Gentle",
    "passionate": "Passionate", "热情": "Passionate", "深情": "Passionate",
    "rebellious": "Angry", "挑衅": "Angry",
    "独立": "Confident",
    "自豪": "Confident",
    "异域感": "Mysterious",
    "活泼": "Energetic",
    "讽刺": "Playful",
    "喜悦、自豪": "Happy",
    "幽默或轻松": "Playful",
    "积极、希望": "Hopeful",
    "希望、反思": "Hopeful",
    "爱情": "Romantic",
}


def _has_cjk(s: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', s))

def normalise_emotion(raw) -> list[str]:
    """Split + normalise an emotion string into canonical tags."""
    s = _normalise_string(raw)
    if not s or s.lower() in ("null", "none", "n/a", "unknown", "未知"):
        return ["Unknown"]

    parts = _smart_split(s)
    result = []
    for p in parts:
        key = p.strip().lower()
        if not key:
            continue
        norm = EMOTION_SYNONYMS.get(key)
        if norm:
            result.append(norm)
        else:
            cap = _capitalise(p)
            if _has_cjk(cap):
                result.append("Other")
            else:
                result.append(cap)
    return list(dict.fromkeys(result)) or ["Other"]  # dedupe, preserve order


# ── Genre normalisation ────────────────────────────────────

GENRE_MAP = {
    "流行": "Pop", "流行音乐": "Pop", "pop": "Pop", "流行芭乐": "Pop",
    "pop ballad": "Pop", "pop, r&b": "Pop+R&B", "r&b, 流行": "Pop+R&B",
    "流行、r&b": "Pop+R&B", "流行/r&b": "Pop+R&B",
    "r&b": "R&B",
    "摇滚": "Rock", "rock": "Rock", "流行摇滚": "Rock",
    "说唱": "Rap", "嘻哈": "Rap", "嘻哈/说唱": "Rap",
    "电子音乐": "Electronic", "electronic": "Electronic",
    "电子舞曲": "Electronic", "synthwave": "Electronic", "电子": "Electronic",
    "electronic, pop": "Electronic+Pop",
    "流行/电子": "Electronic+Pop", "流行、电子": "Electronic+Pop",
    "folk": "Folk", "民歌": "Folk", "民谣": "Folk",
    "folk, ballad": "Folk", "folk, acoustic": "Folk",
    "folk, acoustic, ballad": "Folk",
    "folk, acoustic, singer-songwriter": "Folk",
    "folk, indie": "Folk+Indie", "folk, indie pop": "Folk+Indie",
    "folk, indie folk": "Folk",
    "folk, singer-songwriter": "Folk",
    "jazz": "Jazz",
    "classical": "Classical", "classic": "Classical",
    "blues": "Blues",
    "country": "Country",
    "soul": "Soul",
    "funk": "Funk",
    "punk": "Punk",
    "metal": "Metal",
    "reggae": "Reggae",
    "latin": "Latin",
    "gospel": "Gospel",
    "soundtrack": "Soundtrack", "ost": "Soundtrack",
    "游戏原声": "Soundtrack", "游戏音乐": "Soundtrack",
    "electronic, game ost": "Soundtrack+Electronic",
    "ambient": "Ambient",
    "纯音乐": "Instrumental", "instrumental": "Instrumental",
    "纯音乐/器乐": "Instrumental",
    "phonk": "Phonk",
    "vocaloid": "Vocaloid", "vocaloid, j-pop, electronic": "Vocaloid+J-Pop",
    "j-pop": "J-Pop", "j-pop, ballad": "J-Pop",
    "j-pop, electronic": "J-Pop+Electronic",
    "j-pop, electronic pop": "J-Pop+Electronic",
    "j-pop, alternative pop": "J-Pop",
    "k-pop": "K-Pop",
    "mandopop": "Mandopop",
    "mandopop ballad": "Mandopop",
    "mandopop, r&b": "Mandopop+R&B",
    "mandopop, ballad": "Mandopop",
    "mandopop, indie pop": "Mandopop+Indie",
    "cantopop": "Cantopop",
    "cantopop ballad": "Cantopop",
    "cantopop, ballad": "Cantopop",
    "indie": "Indie",
    "post-rock": "Post-Rock",
    "math rock": "Math Rock",
    "中国风": "Chinese Traditional", "古风": "Chinese Traditional",
    "黄梅戏": "Chinese Opera", "花鼓戏": "Chinese Opera", "戏曲": "Chinese Opera",
    "花鼓戏/民歌": "Chinese Opera+Folk",
    "hip-hop": "Rap", "hip hop": "Rap",
    "disco": "Disco",
    "house": "Electronic", "techno": "Electronic", "trance": "Electronic",
    "dubstep": "Electronic", "drum and bass": "Electronic", "dnb": "Electronic",
    "lo-fi": "Lo-Fi", "lofi": "Lo-Fi",
    "acoustic": "Acoustic",
    "new age": "New Age",
    "world": "World",
    "experimental": "Experimental", "实验": "Experimental",
    "alternative": "Alternative",
    "avant-garde": "Experimental",
    "trap": "Trap",
    "edm": "Electronic",
    "bossa nova": "Bossa Nova",
    "samba": "Latin",
    "tango": "Latin",
    "flamenco": "Latin",
    "歌剧": "Opera", "opera": "Opera",
    "音乐剧": "Musical",
    "流行、戏曲融合": "Pop+Traditional",
    "流行、民谣": "Pop+Folk",
    "电子音乐、游戏原声": "Electronic+Soundtrack",
    "电子音乐、实验音乐": "Electronic+Experimental",
    "electronic, pop, dance": "Electronic+Pop",
    "电子流行、游戏音乐、remix": "Electronic+J-Pop",
    "流行、民谣、雷鬼": "Pop+Folk",
}


def normalise_genre(raw) -> list[str]:
    """Split + normalise a genre string into canonical tags."""
    s = _normalise_string(raw)
    if not s or s.lower() in ("null", "none", "n/a", "unknown", "未知"):
        return ["Unknown"]

    parts = _smart_split(s)
    result = []
    for p in parts:
        key = p.strip().lower()
        if not key:
            continue
        norm = GENRE_MAP.get(key)
        if norm:
            for tag in norm.split("+"):
                result.append(tag)
        else:
            cap = _capitalise(p)
            if _has_cjk(cap):
                result.append("Other")
            else:
                result.append(cap)
    return list(dict.fromkeys(result)) or ["Other"]


# ── Dataset loader ─────────────────────────────────────────

def load_metadata(path: str | None = None) -> list[dict]:
    """Load metadata entries from JSONL."""
    path = path or JSONL_PATH
    entries = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        log(f"[red]Metadata file not found: {path}[/]")
    return entries


def compute_distribution(entries: list[dict], field: str):
    """Compute normalised distribution for a metadata field.

    Returns (sorted_items, total_entries) where sorted_items is
    [(label, count, pct), ...] sorted by count descending.
    """
    normaliser = {
        "language": normalise_language,
        "emotion": normalise_emotion,
        "genre": normalise_genre,
    }.get(field)

    if not normaliser:
        raise ValueError(f"Unknown field: {field}")

    counter: Counter = Counter()
    for entry in entries:
        meta = entry.get("metadata", {})
        raw = meta.get(field)
        if raw is None:
            continue

        norm = normaliser(raw)
        if isinstance(norm, list):
            # emotion & genre are multi-tag
            for tag in norm:
                counter[tag] += 1
        else:
            # language is single
            counter[norm] += 1

    total = sum(counter.values())
    items = [(label, count, round(count / total * 100, 1)) for label, count in counter.most_common()]
    return items, total
