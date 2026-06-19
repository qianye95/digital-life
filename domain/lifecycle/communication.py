"""发送前上下文检查 — express_to_human 发送消息前拦截。

check_before_send() 是 express_to_human 和实际发送之间的拦截层。
只问一个问题：会话中有没有被模型忽略的人类/群聊消息？

如果有 → 拦截发送，加载最近几轮对话流水（含新到消息）让模型重新组织
         回复，跟「主动调用了查看历史对话工具」一样的效果。
如果没有 → 放行，直接发送。

事件消费：
  拦截时发现的未消费事件会被立即 consume（写入 consumed_at + consumed_by_session_id），
  下次调用不会再拦截同一事件。

数据来源（两路合并去重）：
  1. DB 事件队列（pop_due_events）— 持久化事件
  2. 内存信号事件（peek_signalled_events）— RUNNING 期间 cron 注入的事件
  3. chats.db 聚合表（如可拿 chat_id）— 群里近几轮完整对话
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def check_before_send(
    text: str,
    *,
    session_id: str = "",
) -> dict[str, Any] | None:
    """发送前拦截核心——检查是否有未消费的人类消息需先展示给模型。

    核心问题：是否有模型还没看到的人类/群消息？

    有未读消息 → 拦截，加载最近几轮对话历史让模型自己重新组织回复
    无未读消息 → 放行（return None），允许直接发送

    consume_event() 是唯一的消费入口，被拦截事件写入 consumed_at + consumed_by_session_id。
    """
    unread: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    # DB-backed event queue (unconsumed events only)
    try:
        from domain.lifecycle.events import pop_due_events
        from domain.lifecycle.event_registry import get_event_type

        for ev in pop_due_events(limit=20):
            eid = ev.get("event_id")
            if not eid or eid in seen_ids:
                continue
            kind = ev.get("kind", "")
            if kind in ("message", "group_message"):
                type_def = get_event_type(kind)
                payload = ev.get("payload", {}) if isinstance(ev.get("payload"), dict) else {}
                raw_text = (payload.get("text") or "").strip()
                sender = payload.get("sender_name", "")
                seen_ids.add(eid)
                unread.append({
                    "event_id": eid,
                    "kind": kind,
                    "display_name": type_def.display_name if type_def else kind,
                    "text": raw_text,
                    "sender": sender,
                })
    except Exception:
        pass

    # In-memory signalled events (from cron tick during RUNNING session)
    try:
        from domain.lifecycle.session_events import peek_signalled_events

        for ev in peek_signalled_events():
            eid = ev.get("event_id")
            if not eid or eid in seen_ids:
                continue
            kind = ev.get("kind", "")
            if kind in ("message", "group_message"):
                payload = ev.get("payload", {}) if isinstance(ev.get("payload"), dict) else {}
                raw_text = (payload.get("text") or "").strip()
                seen_ids.add(eid)
                unread.append({
                    "event_id": eid,
                    "kind": kind,
                    "display_name": ev.get("display_name") or "新消息",
                    "text": raw_text,
                    "sender": payload.get("sender_name", ""),
                })
    except Exception:
        pass

    if not unread:
        return None

    # Consume discovered events — single consumption entry point.
    # After this, consumed_at + consumed_by_session_id are set in DB.
    # 同步清空内存 signalled_events 池里的同一批 event_id——避免
    # 下一次 express 又被 signalled_events 拦截 (peek_signalled_events
    # 只读不清，必须显式 consume_signalled_events_by_ids)。否则同一
    # 条消息进 signalled 池一次就让后续所有 express 都被拦截，循环死锁。
    if session_id:
        try:
            from domain.lifecycle.events import consume_event as _consume
            for eid in seen_ids:
                _consume(eid, session_id=session_id)
        except Exception:
            pass
        try:
            from domain.lifecycle.session_events import consume_signalled_events_by_ids
            consume_signalled_events_by_ids(seen_ids)
        except Exception as pass_err:
            logger.debug("consume_signalled_events_by_ids failed: %s", pass_err)

    # 拉当前 chat 的近 10 轮完整对话流水——不只新消息，也不是快照，
    # 而是跟"主动调查看历史对话"一样的体验：模型读一遍就能完整重建画面。
    recent_chat_log = _build_recent_chat_log()

    # 设计原则：模型读完后必须立刻重新组织回复。
    # 不保留草稿（让模型自己根据完整历史判断要怎么改）；用平铺直叙的语义。
    response: dict[str, Any] = {
        "sent": False,
        "result_summary": (
            f"你的消息发送失败了，因为有 {len(unread)} 条新消息未读。"
            "为了避免你的回复过时，先看一遍下面这份完整对话历史，"
            "然后重新组织你的回复再发一次。"
        ),
        # 完整对话流水：当前 wake 所属 chat 的近 10 条（含本实例 + 其他 bot + 真人）
        "recent_chat_log": recent_chat_log or "（无可用 chat_id，无法加载历史）",
    }

    return response


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _build_recent_chat_log() -> str | None:
    """构建当前 chat 的最近 10 条对话流水，仿 sense_conversation。"""
    try:
        from domain.lifecycle.runtime_context import get_current_event_chat_id
        chat_id = get_current_event_chat_id() or ""
    except Exception:
        chat_id = ""
    if not chat_id:
        return None
    try:
        from domain.conversations import list_chat_messages
        msgs = list_chat_messages(chat_id, limit=10)
        if not msgs:
            return None
        lines: list[str] = []
        for m in msgs:
            sender = (m.get("sender_name") or "").strip()
            if not sender:
                sender = m.get("sender_id") or "未知"
                if len(sender) > 16:
                    sender = sender[:12] + "…"
            text = (m.get("text") or "").strip()
            if not text:
                continue
            lines.append(f"{sender}：{text[:300]}")
        return "\n\n".join(lines)
    except Exception:
        return None
