"""SimulationEngine — 数字生命的环境模拟核心。

精力系统：五段式 亢奋(85-100) → 清醒(60-85) → 平淡(40-60) → 疲惫(20-40) → 精疲力竭(0-20)

运作逻辑：
- 衰减：每次工具调用/模型访问消耗 ENERGY_COST_PER_CALL（所有调用平权）
- 恢复：随时间自动恢复，无论 RUNNING 还是 BLOCKED 状态
- 补充：仅管理台"加鸡腿"事件手动补充

三种事件：
  1. vital_threshold — RUNNING 状态下精力跌破阈值（进入疲惫/精疲力竭），提醒休息
  2. initiative — BLOCKED 状态下精力充足+空闲超时，触发主动探索
  3. nurture_energy — 前端手动加鸡腿（由 monitor 直接调 apply_deltas + emit_event）
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── 精力段位 ──

ENERGY_SEGMENTS = [
    ("亢奋", 85, 100, "精力充沛"),
    ("清醒", 60, 85, "状态很好"),
    ("平淡", 40, 60, "还行"),
    ("疲惫", 20, 40, "有点累，想休息"),
    ("精疲力竭", 0, 20, "撑不住了"),
]

# ── 精力常量 ──

ENERGY_MAX = 100
# 每小时恢复（RUNNING 和 BLOCKED 统一）。默认 100 / 24 ≈ 4.17 —— 一整天完全
# 不动可从 0 恢复到 100。这条和消耗系数共同保证「一天满跑 2000 万 token
# 刚好耗光满血」「休息一天满血复活」两条产品语义。可通过 env
# DIGITAL_LIFE_ENERGY_RECOVERY_PER_HOUR 覆盖默认值（_resolve_energy_token_constants）。
ENERGY_RECOVERY_PER_HOUR = 100.0 / 24   # ≈ 4.17
ENERGY_COST_PER_CALL = 0.2          # 每次工具调用/模型访问的"动作成本"（不与 token 挂钩）

# 精力-token 耦合（设计文档 15.4）：LLM call 走真实 token usage 消耗精力，
# 不再用上面的 ENERGY_COST_PER_CALL。
#
# 设计目标（与用户对齐 2026-06-14）：
#   - 一天满跑 ≤ 2000 万 token → 把满力 100 刚好耗光
#   - 一小时满跑 ≤ 200 万 token → 大约 1 小时扣 10 精力
#
# 推导：20M token / 100 精力 = 200K token/精力 = 0.005 精力/1K token
# output 实际计价比 input 贵，按 10× 比例分配：
#   - INPUT  = 0.005/k token （便宜，主要承担 prompt context）
#   - OUTPUT = 0.05/k token  （贵 10×，承担生成）
#
# 实际场景验算：
#   - 一次普通 LLM call: 50k input + 100 output ≈ 0.25 + 0.005 = 0.255 精力
#   - 一个 wake 平均 5-10 次 call → 1-3 精力
#   - 一小时满跑 1-2M token → 5-10 精力
#   - 一天满跑 20M token → 100 精力（正好满血耗光）
#   - 休息一天（无消耗）→ 恢复 4.17×24 = 100（正好满血复活）
#
# 工具调用（sense/terminal/todo 等）仍保持固定"动作成本"0.05-0.3，
# 不变；和 token usage 是两套独立的成本。
ENERGY_PER_KTOKEN_INPUT = 0.005
ENERGY_PER_KTOKEN_OUTPUT = 0.05


def _resolve_energy_token_constants() -> None:
    """从环境变量读 ENERGY_PER_KTOKEN_INPUT / OUTPUT / RECOVERY_PER_HOUR（config_center 注入），覆盖默认值。

    模块顶部硬编码默认值，config center 启动时如果有对应 env 就覆盖。
    """
    global ENERGY_PER_KTOKEN_INPUT, ENERGY_PER_KTOKEN_OUTPUT, ENERGY_RECOVERY_PER_HOUR
    try:
        v_in = os.environ.get("DIGITAL_LIFE_ENERGY_PER_KTOKEN_INPUT")
        if v_in:
            ENERGY_PER_KTOKEN_INPUT = float(v_in)
        v_out = os.environ.get("DIGITAL_LIFE_ENERGY_PER_KTOKEN_OUTPUT")
        if v_out:
            ENERGY_PER_KTOKEN_OUTPUT = float(v_out)
        v_rec = os.environ.get("DIGITAL_LIFE_ENERGY_RECOVERY_PER_HOUR")
        if v_rec:
            ENERGY_RECOVERY_PER_HOUR = float(v_rec)
    except (ValueError, TypeError):
        pass


# 模块导入时自动解析一次（后续 config_center 也可以再调本函数强制刷新）
_resolve_energy_token_constants()


# 主动探索
INITIATIVE_ENERGY_THRESHOLD = 50.0  # 精力 > 50 才可以主动探索
INITIATIVE_IDLE_HOURS = 1.0         # 空闲 > 1 小时触发


def _find_segment(energy: float):
    for name, lo, hi, exp in ENERGY_SEGMENTS:
        if lo <= energy <= hi:
            return name, exp
    return "未知", ""


def _now():
    from domain.lifecycle.clock import now_dt
    return now_dt()


def _now_iso():
    from domain.lifecycle.clock import now_iso
    return now_iso()


class SimulationEngine:
    """数字生命环境模拟核心 — 仅精力状态管理。"""

    def __init__(self):
        self._vitals: Optional[Dict[str, float]] = None
        self._current_segment: Optional[str] = None
        self._last_activity_at: Optional[Any] = None
        try:
            import os, sqlite3
            from domain.lifecycle.clock import parse_iso
            from pathlib import Path
            override = os.environ.get("DIGITAL_LIFE_STATE_DB")
            if override:
                db_path = Path(override)
            else:
                from infrastructure.config import get_runtime_state_db_path
                db_path = get_runtime_state_db_path()
            db = sqlite3.connect(str(db_path))
            r = db.execute("SELECT updated_at FROM vitals WHERE id=1").fetchone()
            db.close()
            if r:
                self._last_activity_at = parse_iso(r[0])
        except Exception:
            pass

    # ── 内部状态读写 ──

    def _load(self) -> None:
        from domain.lifecycle.affairs.runtime import get_vitals
        self._vitals = get_vitals()

    def _save(self) -> None:
        from domain.lifecycle.affairs.runtime import save_vitals
        if self._vitals:
            save_vitals(self._vitals)

    def _v(self) -> Dict[str, float]:
        self._load()
        return self._vitals

    # ── 状态查询 ──

    def get_state(self) -> Dict[str, Any]:
        v = self._v()
        energy = v["energy"]
        return {
            "energy": round(energy, 1),
            "segment": _find_segment(energy)[0],
            "now": _now_iso(),
        }

    def get_energy_state(self) -> Dict[str, Any]:
        v = self._v()
        energy = v["energy"]
        seg_name, seg_exp = _find_segment(energy)
        return {
            "energy": round(energy, 1),
            "segment": seg_name,
            "experience": seg_exp,
            "now": _now_iso(),
        }

    # ── 精力操作 ──

    def apply_deltas(self, deltas: Dict[str, float]) -> None:
        v = self._v()
        for dim, delta in deltas.items():
            if dim in v:
                v[dim] = max(0, min(ENERGY_MAX, v[dim] + delta))
        self._vitals = v
        self._last_activity_at = _now()
        self._save()

    def consume_energy(self, amount: float) -> float:
        v = self._v()
        v["energy"] = max(0, v["energy"] - abs(amount))
        self._vitals = v
        self._last_activity_at = _now()
        self._save()
        return v["energy"]

    def sync_last_activity_at(self) -> None:
        """从 DB 重读 vitals.updated_at 到内存。

        scheduler.py 每次 wake 都 UPDATE vitals.updated_at（重置 initiative idle
        timer，注释见 scheduler.py:_touch_vitals_on_wake），但本类是 module-level
        单例的内存状态——DB 改了，内存的 _last_activity_at 不会自动同步。
        没有消耗精力的唤醒（纯 timer / routine）走不动 consume_energy，于是
        initiative 计时器从昨晚一直累计到今天早上，导致早起和晨间 routine 挤压、
        第一件事、initiative 重复触发。

        解决：scheduler 触发 wake 那段 UPDATE 之后调一次本方法，强制内存与 DB
        一致；下一轮 check_energy_events 的 elapsed_h 才会从 wake 时刻算起。
        """
        try:
            import sqlite3
            from domain.lifecycle.clock import parse_iso
            from infrastructure.config import get_runtime_state_db_path
            import os
            from pathlib import Path
            override = os.environ.get("DIGITAL_LIFE_STATE_DB")
            db_path = Path(override) if override else get_runtime_state_db_path()
            db = sqlite3.connect(str(db_path))
            try:
                r = db.execute("SELECT updated_at FROM vitals WHERE id=1").fetchone()
                if r and r[0]:
                    self._last_activity_at = parse_iso(r[0])
            finally:
                db.close()
        except Exception as exc:
            logger.warning("sync_last_activity_at failed: %s", exc)

    # ── 时间推进 ──

    def tick(self) -> Dict[str, Any]:
        from .energy_events import check_energy_events
        check_energy_events(self)
        return {"vitals": self._v()}


# ── 全局单例 ──

_engine: Optional[SimulationEngine] = None


def get_engine() -> SimulationEngine:
    global _engine
    if _engine is None:
        _engine = SimulationEngine()
    return _engine


def reset_engine() -> None:
    global _engine
    _engine = None


__all__ = [
    "SimulationEngine",
    "get_engine",
    "reset_engine",
    "ENERGY_SEGMENTS",
    "ENERGY_MAX",
    "ENERGY_RECOVERY_PER_HOUR",
    "ENERGY_COST_PER_CALL",
    "INITIATIVE_ENERGY_THRESHOLD",
    "INITIATIVE_IDLE_HOURS",
]
