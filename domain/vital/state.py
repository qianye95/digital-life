"""精力状态管理 — VitalSnapshot + 持久化 + 养育记录。

精力运作逻辑：
- 恢复：随时间自动恢复（+ENERGY_RECOVERY_PER_HOUR），无论 RUNNING 还是 BLOCKED
- 衰减：每次工具调用/模型访问消耗 ENERGY_COST_PER_CALL（由外部 consume_energy 触发）
- 补充：仅管理台"加鸡腿"

重要设计：recovery 持久化时不更新 vitals.updated_at，保留其作为"最后真实事件时间"。
这确保 initiative 检测能正确判断"离上次 session 结束多久了"。
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass as _dataclass
from datetime import timedelta as _td
from typing import Dict, List, Optional

from domain.lifecycle.clock import now_dt, now_iso, parse_iso

from domain.lifecycle.affairs.runtime import (
    _conn,
    init_db as _init_affairs_db,
)


# ---------------- schema ----------------
VITALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS vitals (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    energy           REAL NOT NULL DEFAULT 70.0,
    updated_at       TEXT NOT NULL,
    last_nurture     TEXT,
    meta_json        TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS nurture_log (
    log_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    at               TEXT NOT NULL,
    kind             TEXT NOT NULL,
    deltas_json      TEXT NOT NULL,
    raw_text         TEXT,
    source           TEXT
);

CREATE INDEX IF NOT EXISTS idx_nurture_at ON nurture_log(at DESC);
"""


def init_vitals_db() -> None:
    _init_affairs_db()
    with _conn() as c:
        c.executescript(VITALS_SCHEMA)
        row = c.execute("SELECT id FROM vitals WHERE id = 1").fetchone()
        if not row:
            c.execute(
                "INSERT INTO vitals (id, energy, updated_at) VALUES (1, 70.0, ?)",
                (now_iso(),),
            )


# ---------------- data class ----------------

@_dataclass
class VitalSnapshot:
    energy: float
    updated_at: str


# ---------------- core API ----------------

def _apply_recovery(base: VitalSnapshot) -> VitalSnapshot:
    """随时间恢复精力，无论 RUNNING 还是 BLOCKED。"""
    from domain.vital.simulation.engine import ENERGY_RECOVERY_PER_HOUR

    now = now_dt()
    last = parse_iso(base.updated_at)
    elapsed_h = max(0.0, (now - last).total_seconds() / 3600.0)
    new_energy = base.energy + ENERGY_RECOVERY_PER_HOUR * elapsed_h

    return VitalSnapshot(
        energy=max(0, min(100, new_energy)),
        updated_at=base.updated_at,  # 不更新 updated_at——保留"最后真实事件时间"
    )


def get_current_vitals() -> VitalSnapshot:
    init_vitals_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM vitals WHERE id = 1").fetchone()
    if not row:
        return VitalSnapshot(energy=70.0, updated_at=now_iso())

    base = VitalSnapshot(
        energy=row["energy"] if "energy" in row.keys() else 70.0,
        updated_at=row["updated_at"],
    )

    recovered = _apply_recovery(base)

    # 持久化恢复后的精力，但不更新 updated_at
    if abs(recovered.energy - base.energy) > 0.01:
        with _conn() as c:
            c.execute("UPDATE vitals SET energy=? WHERE id=1", (recovered.energy,))

    return recovered


def _persist_snapshot(snap: VitalSnapshot, last_nurture: Optional[str] = None) -> None:
    """写入精力快照并更新 updated_at（仅在真实事件时调用）。"""
    with _conn() as c:
        if last_nurture:
            c.execute(
                "UPDATE vitals SET energy=?, updated_at=?, last_nurture=? WHERE id=1",
                (snap.energy, now_iso(), last_nurture),
            )
        else:
            c.execute(
                "UPDATE vitals SET energy=?, updated_at=? WHERE id=1",
                (snap.energy, now_iso()),
            )


def apply_nurture(kind: str, deltas: Dict[str, float],
                  raw_text: str = "", source: str = "") -> VitalSnapshot:
    """外部养育操作（管理台加鸡腿等）。更新 updated_at。"""
    init_vitals_db()
    current = get_current_vitals()
    new = VitalSnapshot(
        energy=max(0, min(100, current.energy + deltas.get("energy", 0))),
        updated_at=now_iso(),
    )
    _persist_snapshot(new, last_nurture=kind)

    with _conn() as c:
        c.execute(
            "INSERT INTO nurture_log (at, kind, deltas_json, raw_text, source) VALUES (?, ?, ?, ?, ?)",
            (now_iso(), kind, _json.dumps(deltas, ensure_ascii=False), raw_text, source),
        )
    return new


def consume_energy(amount: float, reason: str = "activity") -> VitalSnapshot:
    """消耗精力（工具调用/模型访问）。更新 updated_at。"""
    return apply_nurture(kind=f"energy_cost:{reason}", deltas={"energy": -amount})


def recent_nurture_log(hours: int = 24) -> List[Dict]:
    init_vitals_db()
    since = (now_dt() - _td(hours=hours)).isoformat(timespec="seconds")
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM nurture_log WHERE at >= ? ORDER BY at DESC",
            (since,),
        ).fetchall()
    return [
        {
            "at": r["at"],
            "kind": r["kind"],
            "deltas": _json.loads(r["deltas_json"]),
            "raw_text": r["raw_text"] or "",
            "source": r["source"] or "",
        }
        for r in rows
    ]


# ---------------- formatting ----------------

def format_vitals_report(snap: Optional[VitalSnapshot] = None) -> str:
    from domain.vital.simulation.engine import ENERGY_SEGMENTS

    snap = snap or get_current_vitals()
    energy = snap.energy

    seg_name = "未知"
    seg_exp = ""
    for name, lo, hi, exp in ENERGY_SEGMENTS:
        if lo <= energy <= hi:
            seg_name = name
            seg_exp = exp
            break

    lines = [f"## 精力状态  {energy:.0f}/100（{seg_name}）"]
    if seg_exp:
        lines.append(f"> {seg_exp}")

    return "\n".join(lines)


__all__ = [
    "VitalSnapshot",
    "init_vitals_db",
    "get_current_vitals",
    "apply_nurture",
    "consume_energy",
    "recent_nurture_log",
    "format_vitals_report",
]
