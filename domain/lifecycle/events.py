"""L4 事件总线桥接层 — 面向业务的事件发布/查询/消费 API。

底层存储：LegacyEventBus（SQLite events 表），实现在 domain.lifecycle.event_bus 中。

对外 API：
  emit_event(kind, payload)     — 发布事件（含防抖合并 + 实例隔离）
  pop_due_events(limit)         — 获取到期未消费事件（只读，不消费）
  consume_event(event_id, session_id) — 标记事件已消费
  list_recent_events(hours)     — 列出近期事件（含已消费）
  consume_events_by_kind(kind)  — 按类型批量消费
  pop_events_by_kind(kind)      — 按类型取出并消费

多实例隔离机制：
  通过 contextvars.ContextVar(_instance_channel_var) 实现线程级实例隔离。
  cron 守护线程在每个 tick 开始时调用 set_instance_context(instance_id)，
  后续所有事件操作自动使用正确的 channel 前缀（instance:{uuid}）。
  channel 在 emit 时写入 events 表的 channel 列，查询时通过 LIKE 'instance:{uuid}%' 过滤。

防抖机制 (_apply_debounce)：
  根据 event_registry 配置的 debounce_window_s + merge_policy：
  - latest: 窗口内同类型 → 用新 payload 覆盖最新一条
  - accumulate: 累加 _merged_texts（最多 5 条）+ _merged_count
  - count: 只增计数不合并文本
  定时事件（有 fire_at）不防抖。
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import random
import sys
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set


from .clock import now_dt, now_iso

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# 每线程/协程的实例上下文 — cron 守护线程在每个 tick 开始时设置
# channel 格式：instance:{uuid}，所有事件操作自动限域到当前实例
_instance_channel_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "instance_channel", default="instance:zero"
)


def set_instance_context(instance_id: str | None = None) -> contextvars.Token:
    """设置当前实例上下文（每个 cron tick 开始时调用）。

    返回的 Token 用于在 tick 结束时 reset_instance_context() 恢复。
    """
    if instance_id is None:
        instance_id = os.environ.get("DIGITAL_LIFE_INSTANCE_ID", "zero")
    return _instance_channel_var.set(f"instance:{instance_id}")


def reset_instance_context(token: contextvars.Token) -> None:
    """恢复到上一个实例上下文。"""
    _instance_channel_var.reset(token)


def _get_instance_channel() -> str:
    """返回当前实例的 channel 前缀，用于事件隔离。"""
    return _instance_channel_var.get()

from domain.lifecycle.event_bus import LegacyEventBus  # noqa: E402
from domain.lifecycle.affairs.runtime import _conn, init_db  # noqa: E402

logger = logging.getLogger(__name__)


_event_bus = LegacyEventBus(
    connection_factory=_conn,
    init_database=init_db,
    now_iso=now_iso,
    now_dt=now_dt,
)


def _ensure_columns() -> None:
    """幂等扩展 events 表列（fire_at、kind、consumed_by_session_id）。"""
    _event_bus.ensure_columns()


def _apply_debounce(kind: str, payload: Dict, fire_at: Optional[str]) -> Optional[int]:
    """防抖合并 — 窗口期内同类型事件合并为一条，避免事件风暴。

    返回值：
      None → 未命中防抖，正常 insert 新事件
      event_id → 命中防抖，已更新已有事件的 payload，无需再 insert

    合并策略（从 event_registry 读取）：
      - latest: 用新 payload 覆盖旧 payload，只增 _merged_count（如 human_message）
      - accumulate: 累加 _merged_texts 列表（最多 5 条），保留最新 sender_name/text
      - count: 只增 _merged_count，不合并文本内容

    定时事件（有 fire_at）不防抖——每次闹钟到期都是独立事件，必须逐一触发。
    channel 过滤确保多实例之间防抖互不干扰。
    """
    if fire_at:
        return None  # 定时事件不防抖
    try:
        from .event_registry import resolve_event_config
        cfg = resolve_event_config(kind)
    except Exception:
        return None

    window_range = cfg.get("debounce_window_s", (0, 0))
    # 兼容老调用（int 直接当作 (n, n)）
    if isinstance(window_range, int):
        lo = hi = window_range
    elif isinstance(window_range, (list, tuple)) and len(window_range) >= 2:
        lo, hi = int(window_range[0]), int(window_range[1])
        if lo > hi:
            lo, hi = hi, lo
    else:
        lo = hi = 0
    if lo <= 0 and hi <= 0:
        return None
    # 单点窗口（lo == hi）直接用，范围窗口随机取一个值
    window = lo if lo == hi else random.randint(lo, hi)
    policy = cfg.get("merge_policy", "latest")

    cutoff = (now_dt() - timedelta(seconds=window)).isoformat(timespec="seconds")
    instance_channel = _get_instance_channel()
    try:
        with _conn() as conn:
            # channel 用 LIKE 前缀匹配——handler 写入的 channel 实际是
            # "instance:{uuid}/gateway:lark:group"(因为 emit_event 第 213 行拼接了
            # 显式 channel),而 _get_instance_channel 返回的是 "instance:{uuid}"(不含
            # 子通道)。严格 = 匹配永远不命中,debounce 失效。
            # LIKE 让 instance 前缀的所有子通道都能被防抖合并。
            row = conn.execute(
                "SELECT event_id, payload FROM events "
                "WHERE kind = ? AND consumed_at IS NULL AND created_at >= ? "
                "AND (channel LIKE ? OR channel IS NULL) "
                "ORDER BY event_id DESC LIMIT 1",
                (kind, cutoff, instance_channel + "%"),
            ).fetchone()
            if not row:
                return None

            existing_id = row["event_id"]
            try:
                existing_payload = json.loads(row["payload"]) if row["payload"] else {}
            except Exception:
                existing_payload = {}

            if policy == "latest":
                merged = dict(payload)
                merged["_merged_count"] = existing_payload.get("_merged_count", 1) + 1
            elif policy == "count":
                merged = dict(existing_payload)
                merged["_merged_count"] = merged.get("_merged_count", 1) + 1
            else:  # accumulate (default for groups)
                merged = dict(existing_payload)
                merged["_merged_count"] = merged.get("_merged_count", 1) + 1
                # 存 sender+text 对的 list,让 batch 触发时模型能看到"谁说了哪条"
                # (不只文本页 senders,历史 BUG:只存 text 模型不知道发话者语境)
                texts = merged.get("_merged_texts", [])
                if not isinstance(texts, list):
                    texts = []
                new_sender = payload.get("sender_name") or payload.get("sender_id") or "?"
                new_text = payload.get("text") or payload.get("last_sent_text") or ""
                if new_text:
                    texts.append({"sender": new_sender, "text": new_text[:200]})
                # 不设条数上限——按你的设计"按时间区间累积,不看消息数量"
                merged["_merged_texts"] = texts
                # 保留最新发送者信息(main text/sender 字段仍指最新的一条,
                # wake_prompt 主行用最新那条,真正 batch 历史走 _merged_texts)
                if "sender_name" in payload:
                    merged["sender_name"] = payload["sender_name"]
                if "text" in payload:
                    merged["text"] = payload["text"]

            conn.execute(
                "UPDATE events SET payload = ?, created_at = ? "
                "WHERE event_id = ? AND (channel LIKE ? OR channel IS NULL)",
                (json.dumps(merged, ensure_ascii=False), now_iso(),
                 existing_id, instance_channel + "%"),
            )
            logger.debug(
                "event %s debounced (policy=%s, count=%d, window=%ds)",
                kind, policy, merged.get("_merged_count", 1), window,
            )
            return existing_id
    except Exception as exc:
        logger.warning("debounce check failed for %s: %s", kind, exc)
        return None


def emit_event(
    kind: str,
    payload: Optional[Dict] = None,
    fire_at: Optional[str] = None,
    channel: Optional[str] = None,
) -> int:
    """发布或调度一个事件——事件生命周期的起点。

    流程：
      1. 解析当前实例的 channel 前缀（instance:{uuid}），实现多实例隔离
      2. 校验 kind 是否在 event_registry 中注册（未注册只 warning 不拦截）
      3. vital_threshold 事件额外校验维度是否在 SEGMENTS 中（已移除维度自动丢弃）
      4. 走防抖合并（_apply_debounce），命中则返回已有 event_id
      5. 未命中防抖 → INSERT 到 events 表，返回新 event_id

    channel 参数：外部显式传入的 channel（如 gateway:lark:user）会被拼接为
    instance:{uuid}/gateway:lark:user，确保跨实例隔离的同时保留子通道信息。

    fire_at 已废弃：定时事件应使用 alarm 系统（alarms.set_alarm），此参数仅为
    向后兼容保留，无活跃调用方。
    """
    # Resolve instance-scoped channel for isolation
    instance_channel = _get_instance_channel()

    try:
        from .event_registry import validate_event_type

        validate_event_type(kind, raise_on_unknown=False)
    except Exception:
        pass

    payload = payload or {}

    merged_id = _apply_debounce(kind, payload, fire_at)
    if merged_id is not None:
        return merged_id

    # Resolve final channel: explicit channel is prefixed with instance to isolate it
    if channel is not None:
        effective_channel = f"{instance_channel}/{channel}"
    else:
        effective_channel = instance_channel

    return _event_bus.emit_event(kind=kind, payload=payload, fire_at=fire_at, channel=effective_channel)


def pop_due_events(limit: int = 50) -> List[Dict]:
    """取出当前实例到期未消费的事件（只读不消费，用于 cron tick 和 sense 工具）。

    查询条件：consumed_at IS NULL AND (fire_at IS NULL OR fire_at <= now)
             AND channel LIKE 'instance:{uuid}%'
    按 event_id ASC 排序，确保先入先出。
    """
    channel_prefix = _get_instance_channel()
    return _event_bus.pop_due_events(limit=limit, channel_prefix=channel_prefix)


def list_recent_events(
    hours: float = 6.0,
    kinds: Optional[Set[str]] = None,
    include_consumed: bool = True,
    limit: int = 100,
) -> List[Dict]:
    """列出近期事件（含已消费），用于生命周期上下文和 sense 工具查询。

    按 created_at 时间窗口 + channel 前缀过滤，结果按 event_id DESC 排序。
    支持按 kinds 集合二次过滤（在 Python 侧进行）。
    """
    channel_prefix = _get_instance_channel()
    return _event_bus.list_recent_events(
        hours=hours,
        kinds=kinds,
        include_consumed=include_consumed,
        limit=limit,
        channel_prefix=channel_prefix,
    )


def consume_event(event_id: int, target_affair_id: Optional[str] = None, session_id: Optional[str] = None) -> None:
    """标记事件已消费——事件生命周期的终点。

    写入 consumed_at（当前时间）和 consumed_by_session_id（消费会话）。
    consumed_by_session_id 被 calendar() 用于按会话聚合展示过往活动记录。

    唯一的生产消费入口是 sense_event_detail 工具。session_id 优先使用显式传入值，
    否则从 ContextVar 读取（scheduler 在 session 创建时设置）。
    """
    from infrastructure.config import get_current_session_id

    sid = session_id or get_current_session_id() or None
    _event_bus.consume_event(event_id=event_id, target_affair_id=target_affair_id, session_id=sid)


def unconsume_events(event_ids: list[int]) -> int:
    """回退事件消费——将已消费事件恢复为未消费状态。

    用于 LLM 调用失败等异常场景：auto-consume 后 agent 报错，需要让事件
    在下一轮 tick 重新被 pop 出来。返回实际回退的数量。
    """
    channel_prefix = _get_instance_channel()
    return _event_bus.unconsume_events(event_ids=event_ids, channel_prefix=channel_prefix)


def backoff_minutes_for(event: dict, *, base: float = 2.0, cap: float = 60.0) -> float:
    """根据单个事件已有的失败次数算下次退避分钟数。

    事件自己记得被「复活」过几次（resurrect_count）。退避 = base * 2^n，
    n = resurrect_count（当前已有失败次数）。封顶 cap。

      首次失败（n=0）→ 2 min
      第二次（n=1）→ 4 min
      第三次（n=2）→ 8 min
      ...
      第八次及以后 → 60 min（封顶）

    纯函数，不碰数据库；调用方拿到值后再传给 delay_pending_events。
    """
    try:
        n = int(event.get("resurrect_count", 0) or 0)
    except Exception:
        n = 0
    return min(cap, base * (2 ** n))


def delay_pending_events(events: list[dict], *, base: float = 2.0, cap: float = 60.0) -> int:
    """事件消费失败后的「自我指数退避」——把这次 wake 抓出来的整批事件
    推迟到同一个未来时间点，再集体重试。

    设计依据（设计文档 5.5 / 22.1）：闹钟只管「到没到时间」，事件只管
    「有没有待处理」。failure recovery 不归属闹钟——闹钟只为真实的未来
    时间点服务（作息、回复等待、deadline、agent 主动 rest）。事件被消费
    失败时，自己学会推迟下次露面时间：
      - consumed_at 重置为 NULL（再次未消费）
      - fire_at 设为 now + backoff（推到未来）
      - resurrect_count 自增

    pop_due_events 的 SQL 守卫 `fire_at <= now` 会自动让这些事件在退避
    窗口内对 cron 不可见，从结构上杜绝「每分钟重复触发」。

    三层解耦（与用户对齐的最终语义）：
      - **触发层**：每个事件记自己的 resurrect_count（事件个体属性）
      - **呈现层**：数字生命睁眼时只关心「看到一件还是多件」，走
        单事件或多事件清单路径（设计文档 5.3），不感知退避状态
      - **失败处置层（本函数）**：同一批被这次 wake 抓出来的事件，
        如果失败 → 一起退避到本批里**最大的**那个下次唤醒时间
        （取这批里 resurrect_count 最大的事件应得的退避分钟数）

    同频而不是各自独立退避的原因：一次 wake 是一个"挤压队列"的处理尝试。
    失败了，整个队列一起退避到同一下次尝试点，下次它们仍然形成队列
    一起被单次会话消费；而不是被拆散、各自飘到不同的未来点。后者会
    退化成"一次只能做一件事"——违背"挤压队列一次性消费"的设计意图。

    Args:
        events: pending_events 列表（带 event_id 字段的 dict）
        base: 退避基数（分钟）。默认 2 → 2/4/8/16/32/60。
        cap: 单次退避上限（分钟）。默认 60。

    Returns:
        实际被推迟的事件数。
    """
    if not events:
        return 0
    # 同频到本批最大值：避免「同一次 wake 的事件下一次被拆到不同时间点」
    max_minutes = 0.0
    eids: list[int] = []
    for ev in events:
        eid = ev.get("event_id")
        if not eid:
            continue
        eids.append(int(eid))
        # 每个事件按自己的 resurrect_count 算应得分钟（保留独立计数语义），
        # 但实际施加的是这批的最大值，确保下次同步回来。
        minutes = backoff_minutes_for(ev, base=base, cap=cap)
        if minutes > max_minutes:
            max_minutes = minutes
    if not eids:
        return 0
    channel_prefix = _get_instance_channel()
    total = _event_bus.delay_pending_events(
        event_ids=eids, minutes=max_minutes, channel_prefix=channel_prefix,
    )
    if total:
        logger.info(
            "delay_pending_events: %d event(s) backed off together to +%d min "
            "(同步退避 = 整批下次一起回来形成队列)",
            total, int(max_minutes),
        )
    return total


def consume_events_by_kind(kind: str, session_id: Optional[str] = None) -> int:
    """按类型批量消费到期事件——一次性把同类型未消费事件全部标记已消费。

    常用于 session 结束时由 system 批量消费 system 类事件
    （routine/timer/vital_threshold/initiative 等）。
    返回实际消费的事件数量。
    """
    from infrastructure.config import get_current_session_id

    sid = session_id or get_current_session_id() or None
    channel_prefix = _get_instance_channel()
    return _event_bus.consume_events_by_kind(kind=kind, channel_prefix=channel_prefix, session_id=sid)


def pop_events_by_kind(kind: str, limit: int = 10, session_id: Optional[str] = None) -> List[Dict]:
    """按类型取出并消费到期事件——先 SELECT 再 UPDATE consumed_at。

    与 consume_events_by_kind 的区别：pop 会返回事件内容（payload），
    consume 只批量标记不返回内容。用于需要拿到事件数据后再消费的场景。
    """
    from infrastructure.config import get_current_session_id

    sid = session_id or get_current_session_id() or None
    channel_prefix = _get_instance_channel()
    return _event_bus.pop_events_by_kind(kind=kind, limit=limit, channel_prefix=channel_prefix, session_id=sid)


def count_pending_by_kind_and_payload(kind: str, payload_key: str, payload_value: str) -> int:
    """统计队列里未消费的同源事件数。

    产品语义（设计文档 6.4 + 你确认的「一次提醒就够」原则）：
    - 「待办太久没动」是一种状态性提醒——同一待办只要队列里已经有一个
      未消费的提醒，就不该再发第二个。
    - 第一次发出后，要么模型推进了（更新 updated_at）→ 状态自然消除，
      要么模型没推进（系统挂 / 失败 / 忙别的）→ 那 1 个未消费的事件
      就是充足的通知，再多也是噪音 + 浪费 token。

    用法：emit_task_reminder 前先 check_count_pending_by_payload('task_reminder',
    'task_id', 'xxx')——如果 >0 就静默跳过。

    Args:
        kind: 事件类型，如 "task_reminder"
        payload_key: payload 中的去重 key，如 "task_id"
        payload_value: 该 key 的目标值

    Returns:
        队列里未消费的同源事件数（0 表示没有，可以发新的）。
    """
    channel_prefix = _get_instance_channel()
    return _event_bus.count_pending_by_payload_key(
        kind=kind,
        payload_key=payload_key,
        payload_value=payload_value,
        channel_prefix=channel_prefix,
    )


def _row_to_dict(row):
    """向后兼容的 SQLite Row → dict 转换，委托 LegacyEventBus.row_to_dict。"""
    return _event_bus.row_to_dict(row)


__all__ = [
    "set_instance_context",
    "reset_instance_context",
    "emit_event",
    "pop_due_events",
    "list_recent_events",
    "consume_event",
    "consume_events_by_kind",
    "pop_events_by_kind",
]
