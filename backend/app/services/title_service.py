from __future__ import annotations

import hashlib
import random
import re

TONE_ENDINGS = {"gong": "归宁", "shang": "清怀", "jue": "新枝", "zhi": "微明", "yu": "静水"}
KNOWN_IMAGES = [
    "松风", "秋水", "远山", "云影", "微雨", "月色", "归鸟", "空山", "清泉",
    "暮云", "疏林", "寒潭", "春水", "落梅", "孤舟", "归舟", "竹影", "烟岚",
]
QUIET_WORDS = ("静", "安", "缓", "疏", "清", "幽", "月", "夜", "独", "心")
FLOW_WORDS = ("水", "风", "云", "雨", "泉", "流", "舟", "波")
SAD_WORDS = ("悲", "哀", "怨", "失落", "离", "伤")
OPEN_WORDS = ("舒展", "开阔", "澄明", "释然", "通达", "力量", "生机", "微明")


def clean_title(value: str | None) -> str:
    text = re.sub(r"[《》“”\"'、，。！？；：,.!?;:\r\n\t]+", "", value or "").strip()
    return re.sub(r"\s+", "", text)[:40]


def _rng(seed: object | None, card) -> random.Random:
    basis = str(seed or getattr(card, "prompt", "") or repr(card))
    digest = hashlib.sha256(basis.encode("utf8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _card_text(card) -> str:
    values = [
        getattr(card, "prompt", ""), getattr(card, "current", ""),
        getattr(card, "target", ""), "".join(getattr(card, "sound", []) or []),
    ]
    return "".join(str(value) for value in values)


def _images(card) -> list[str]:
    text = _card_text(card)
    found: list[str] = []
    for value in list(getattr(card, "imagery", []) or []) + KNOWN_IMAGES:
        token = re.sub(r"[^\u4e00-\u9fff]", "", str(value))
        candidates = [item for item in KNOWN_IMAGES if item in token or item in text]
        if len(token) == 2:
            candidates.insert(0, token)
        for item in candidates:
            if item not in found:
                found.append(item)
    return found or ["松风", "云影"]


def _allowed_suffixes(card, *, lyrics: bool, lyric_lines: int | None) -> list[str]:
    text = _card_text(card)
    mode = getattr(card, "mode", "xieyi")
    suffixes = ["引", "操"]
    if any(word in text for word in QUIET_WORDS) or mode == "tiaoxin":
        suffixes.append("吟")
    if any(word in text for word in FLOW_WORDS):
        suffixes.append("弄")
    # 调心曲取全曲抵达方向，不因用户当下悲伤就直接题作“怨”。
    if mode == "xieyi" and any(word in text for word in SAD_WORDS):
        suffixes.append("怨")
    if lyrics:
        suffixes.append("歌")
    if lyrics and lyric_lines and 3 <= lyric_lines <= 18:
        suffixes.append("拍")
    tone_path = getattr(card, "five_tone_path", []) or []
    if any(word in text for word in OPEN_WORDS) or (tone_path and tone_path[-1] in {"jue", "zhi"}):
        suffixes.append("畅")
    return list(dict.fromkeys(suffixes))


def _bare_candidates(images: list[str], ending: str) -> dict[int, list[str]]:
    first = images[0]
    second = images[1] if len(images) > 1 else ending
    return {
        2: [first, second, ending, "微明", "归宁", "听雨", "忘忧"],
        3: [f"听{first}", f"望{second}", f"{first[0]}间月", "月归心", "云归处", "山入梦"],
        4: [f"{first}{second}", f"{first}{ending}", "松下观涛", "云外归舟", "静水流深", "月照空山"],
        5: ["微雨过空山", "远山入暮云", "秋水照归舟", "云外一声鹤", "清风渡寒潭", "松间月初上"],
    }


def _genre_candidates(images: list[str], suffixes: list[str], *, lyric_lines: int | None) -> dict[int, list[str]]:
    first = images[0]
    second = images[1] if len(images) > 1 else "归心"
    pools = {2: [], 3: [], 4: [], 5: []}
    two_char_forms = {
        "引": ["云引", "月引"], "吟": ["松吟", "月吟"],
        "弄": ["水弄", "风弄"], "怨": ["秋怨", "离怨"],
        "歌": ["渔歌", "云歌"], "畅": ["清畅", "神畅"],
    }
    three_char_stems = [f"听{first}", f"望{second}", f"{first[0]}间月", "云归处"]
    four_char_stems = [f"{first}入夜", f"{first}过岭", f"{second}初霁", "静水归心"]
    for suffix in suffixes:
        pools[3].append(first + suffix)
        pools[2].extend(two_char_forms.get(suffix, []))
        pools[4].extend(stem + suffix for stem in three_char_stems)
        pools[5].extend(stem + suffix for stem in four_char_stems)
    if "拍" in suffixes and lyric_lines:
        numerals = {3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十", 11: "十一", 12: "十二", 13: "十三", 14: "十四", 15: "十五", 16: "十六", 17: "十七", 18: "十八"}
        numbered = first + numerals[lyric_lines] + "拍"
        if 2 <= len(numbered) <= 5:
            pools[len(numbered)].append(numbered)
    return pools


def compose_title(card, *, seed: object | None = None, lyrics: bool = False, lyric_lines: int | None = None) -> str:
    rng = _rng(seed, card)
    images = _images(card)
    tone_path = getattr(card, "five_tone_path", []) or ["gong"]
    ending = TONE_ENDINGS.get(tone_path[-1], "余韵")
    suffixes = _allowed_suffixes(card, lyrics=lyrics, lyric_lines=lyric_lines)
    target_length = rng.choice([2, 3, 4, 5])
    bare = _bare_candidates(images, ending)
    genre = _genre_candidates(images, suffixes, lyric_lines=lyric_lines)
    prefer_genre = rng.random() < 0.45
    primary = genre[target_length] if prefer_genre else bare[target_length]
    fallback = bare[target_length] if prefer_genre else genre[target_length]
    candidates = [clean_title(item) for item in primary + fallback]
    candidates = [item for item in dict.fromkeys(candidates) if len(item) == target_length]
    if not candidates:
        candidates = [clean_title(item) for item in bare[target_length] if len(clean_title(item)) == target_length]
    return rng.choice(candidates) if candidates else clean_title(images[0])


def compose_legacy_title(plan: dict) -> str:
    caption = str(plan.get("caption") or "")
    match = re.search(r"The imagery is (.*?)\. The emotional journey", caption)
    if not match:
        return ""
    parts = []
    for value in match.group(1).split(","):
        token = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", value)[:4]
        if token and token not in parts:
            parts.append(token)
    return clean_title("".join(parts[:2]))
