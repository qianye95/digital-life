"""TokenUsageTracker — 每实例 LLM token 用量累加器，持久化到 state.db。

设计依据：
  - 历史问题：`infrastructure/ai/agent.py:_chat()` 直接丢弃了 API response
    里的 usage 字段；sessions.input_tokens / messages.token_count /
    WakeContext.end(input_tokens, output_tokens) 三个 schema 就绪但没人
    填。token 用量在生产里完全不可见——精力 0.2/call 是"摆设"，超配额
    的 wake 一路推进没人拦。
  - 解：这里建一个**持久化累加器**。每次 LLM call 后从 `_chat()` 解出
    usage，调 `tracker.record(...)` 一行。预算闸门
    （`cron_lifecycle.py`）和精力-token 耦合（agent.py）从这里取数。

聚合窗口：
  - 本小时（按整点切）：usage_last_hour()
  - 今天（按 00:00 UTC 切）：usage_today()
  - 短期高峰（last N 分钟）：usage_last_n_minutes()

存储：state.db 的 `budget_log` 表：
    id, instance_id, occurred_at(unix ts), input_tokens, output_tokens,
    total_tokens, session_id, kind
一行 = 一笔 LLM call 的 token 用量。小时/日聚合走 `SELECT SUM(...) WHERE ts >= ?`。

并发：本意每实例一个进程，单写者。多线程（agent ReAct loop 内）安全靠 SQLite
连接每用每开。其他进程（如 console）只读查询，不写。
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS budget_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id     TEXT NOT NULL,
    occurred_at     REAL NOT NULL,           -- Unix ts (秒)，方便按时间区剪/排序
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    session_id      TEXT DEFAULT '',
    kind            TEXT DEFAULT 'llm_call'  -- llm_call / session_summary / ...
);
CREATE INDEX IF NOT EXISTS idx_budget_log_occurred
    ON budget_log(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_budget_log_instance_time
    ON budget_log(instance_id, occurred_at DESC);
"""


def _beijing_now() -> datetime:
    """北京时间当前时刻。Token 预算按北京时间"今天 00:00 → 明天 00:00"切。"""
    return datetime.now(timezone(timedelta(hours=8)))


def _hour_start_utc_ts() -> float:
    """当前北京小时的开端 ts（用于"本小时累计"窗口）。"""
    now_bj = _beijing_now()
    hour_start_bj = now_bj.replace(minute=0, second=0, microsecond=0)
    return hour_start_bj.timestamp()


def _day_start_utc_ts() -> float:
    """当前北京日的 00:00 ts。"""
    now_bj = _beijing_now()
    day_start_bj = now_bj.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start_bj.timestamp()


class TokenUsageTracker:
    """每实例 token 用量累加器。

    单例 + ContextVar-id 隔离：每个实例进程持有自己的实例 ID，
    `get_token_tracker()` 返回单例；写出时按当前 ContextVar 写 instance_id。
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """幂等建表。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as conn:
                conn.executescript(_SCHEMA_SQL)
                conn.commit()
        except Exception as exc:
            logger.warning("budget_log schema init failed: %s", exc)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        # WAL 减少锁竞争（cron 读、agent 写、console 读三个进程）
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        return conn

    def record(
        self,
        *,
        instance_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        session_id: str = "",
        kind: str = "llm_call",
        occurred_at: Optional[float] = None,
    ) -> None:
        """记一笔 token 用量。

        传入的 input_tokens/output_tokens 直接来自 LLM API 的 usage 字段。
        total_tokens 自动算 (input + output)；模型若返回 total_tokens 也直接
        用也行（本实现优先 input+output 之和，兼容 GLM/OpenAI）。
        """
        if input_tokens <= 0 and output_tokens <= 0:
            return  # 没数据，不记
        total = input_tokens + output_tokens
        ts = occurred_at if occurred_at is not None else time.time()
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO budget_log "
                    "(instance_id, occurred_at, input_tokens, output_tokens, "
                    "total_tokens, session_id, kind) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (instance_id, ts, int(input_tokens), int(output_tokens),
                     int(total), session_id, kind),
                )
                conn.commit()
        except Exception as exc:
            # 记录失败不能阻断 LLM call 流程，吞掉。
            logger.debug("budget_log record failed: %s", exc)

    # ── 查询 ──

    def _sum_since(self, since_ts: float, instance_id: str = "") -> int:
        try:
            with self._connect() as conn:
                if instance_id:
                    row = conn.execute(
                        "SELECT COALESCE(SUM(total_tokens), 0) as s FROM budget_log "
                        "WHERE occurred_at >= ? AND instance_id = ?",
                        (since_ts, instance_id),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT COALESCE(SUM(total_tokens), 0) as s FROM budget_log "
                        "WHERE occurred_at >= ?",
                        (since_ts,),
                    ).fetchone()
            return int(row["s"] if row else 0)
        except Exception as exc:
            logger.debug("budget_log sum failed: %s", exc)
            return 0

    def usage_last_hour(self, instance_id: str = "") -> int:
        """当前小时（北京时）累计 token。"""
        return self._sum_since(_hour_start_utc_ts(), instance_id)

    def usage_today(self, instance_id: str = "") -> int:
        """今天（北京时 00:00 → 现在）累计 token。"""
        return self._sum_since(_day_start_utc_ts(), instance_id)

    def usage_last_n_minutes(self, n: int, instance_id: str = "") -> int:
        """最近 N 分钟累计 token。"""
        since = time.time() - n * 60
        return self._sum_since(since, instance_id)

    def hour_resets_at(self) -> str:
        """下个小时开端（北京时），ISO 字符串。前端展示"重置于 ..."用。"""
        now_bj = _beijing_now()
        next_hour = (now_bj.replace(minute=0, second=0, microsecond=0)
                     + timedelta(hours=1))
        return next_hour.isoformat(timespec="minutes")

    def day_resets_at(self) -> str:
        """明天 00:00（北京时）。"""
        now_bj = _beijing_now()
        tomorrow = (now_bj.replace(hour=0, minute=0, second=0, microsecond=0)
                    + timedelta(days=1))
        return tomorrow.isoformat(timespec="minutes")


# ── 单例 ──

_tracker: Optional[TokenUsageTracker] = None


def get_token_tracker(db_path: Optional[Path | str] = None) -> TokenUsageTracker:
    """获取 / 创建 TokenUsageTracker 单例。

    db_path 不传时从 instance ContextVar 解析（同 events 模块的同款套路）；
    解析失败兜底用 `<runtime_home>/state.db`。
    """
    global _tracker
    if _tracker is not None and db_path is None:
        return _tracker
    if db_path is None:
        try:
            from infrastructure.config import get_runtime_state_db_path
            db_path = get_runtime_state_db_path()
        except Exception:
            # 兜底：让进程启动早期也能用（虽然没必要在这个阶段记录）
            db_path = Path("var/state.db")
    assert _tracker is None or db_path is not None
    _tracker = TokenUsageTracker(db_path)
    return _tracker


def reset_token_tracker_for_test() -> None:
    """测试专用：清掉单例。"""
    global _tracker
    _tracker = None


__all__ = [
    "TokenUsageTracker",
    "get_token_tracker",
    "reset_token_tracker_for_test",
]
