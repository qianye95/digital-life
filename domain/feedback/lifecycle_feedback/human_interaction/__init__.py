"""Human interaction feedback rules for the lifecycle system.

This package owns the pure business rules that interpret a human message as
relationship/vital feedback. Runtime side effects, such as writing Hermes DB
rows or scheduling threshold events, stay behind the Hermes adapter boundary.
"""

from __future__ import annotations

from typing import Dict, List, Tuple


NURTURE_KINDS: Dict[str, Dict[str, float]] = {
    "feed": {"satiety": 15.0, "mood": 2.0},
    "pet": {"mood": 10.0, "bond": 5.0},
    "groom": {"hygiene": 15.0, "mood": 2.0},
    "play": {"mood": 8.0, "bond": 4.0, "energy": -2.0},
    "praise": {"mood": 8.0, "bond": 4.0},
    "comfort": {"mood": 7.0, "bond": 5.0},
    "chat": {"bond": 2.0},
    "scold": {"mood": -8.0, "bond": -5.0},
    "ignore": {"bond": -2.0},
}

PATTERNS: List[Tuple[str, List[str]]] = [
    (
        "feed",
        [
            "投食",
            "喂你",
            "吃饭",
            "饿了",
            "来吃",
            "点了外卖",
            "吃的来了",
            "给你带了",
            "零食",
            "饿了吧",
        ],
    ),
    ("pet", ["摸摸", "拍拍头", "拍拍", "揉揉", "揉揉脑袋", "搭肩膀", "抱抱", "捏脸"]),
    ("groom", ["洗澡", "理发", "剪指甲", "换衣服", "干净点", "收拾一下"]),
    ("play", ["打游戏", "来玩", "一起玩", "玩一会", "打球", "打球去", "踢足球"]),
    ("praise", ["乖", "真乖", "棒", "好样的", "厉害", "聪明", "真行", "爱你", "喜欢你", "哥最爱你"]),
    ("comfort", ["别怕", "没事的", "我在", "有我呢", "别难过", "我陪你", "别担心"]),
    ("scold", ["坏", "笨", "不听话", "烦死了", "滚", "别闹", "烦人"]),
]


def parse_message(text: str) -> List[str]:
    """Return every nurture kind matched by a human message."""
    text = text or ""
    hits: List[str] = []
    for kind, keywords in PATTERNS:
        for keyword in keywords:
            if keyword in text:
                hits.append(kind)
                break
    return hits


def merge_deltas(kinds: List[str]) -> Dict[str, float]:
    """Merge nurture deltas, damping additional matches in one message."""
    merged: Dict[str, float] = {}
    for index, kind in enumerate(kinds):
        factor = 1.0 if index == 0 else 0.7
        for dimension, delta in NURTURE_KINDS.get(kind, {}).items():
            merged[dimension] = merged.get(dimension, 0.0) + delta * factor
    return {key: round(value, 2) for key, value in merged.items() if abs(value) > 0.01}


__all__ = ["NURTURE_KINDS", "PATTERNS", "parse_message", "merge_deltas"]
