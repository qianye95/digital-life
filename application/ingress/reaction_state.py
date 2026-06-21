"""Reaction 表情收条状态机 —— 跨三个调用点传递 msg_id ↔ reaction_id。

三态收条(Hermes 风格):
  入站收到消息  → add_reaction 👀 (EYES)  → 存 reaction_id
  wake 触发开始 → remove 👀 + add ⚙️ (SETTINGS) → 更新 reaction_id
  express_to_human 发送成功 → remove ⚙️

msg_id 是唯一 key(单条消息同一时刻只有一个收条状态)。
三个调用点(handler 入站 / scheduler wake / action_tools send)互不传递 context,
所以用 module-level dict 共享。

为了不让 dict 无限增长,过期 entry 在 _try_set / register_* 时惰性清理(> 1h)。
"""
from __future__ import annotations

import time
import logging

logger = logging.getLogger(__name__)

# msg_id → {reaction_id, emoji, ts}
# emoji = "EYES" | "SETTINGS" | None（None 表示已最终撤回,无活跃表情）
_REACTIONS: dict[str, dict] = {}
_EXPIRY_S = 3600  # 1 小时无更新就忘掉

# 进程级 adapter 引用 (handler 入站时持有,后续 clear_on_reply 不需要重新拿)
# 每个 instance 独立进程,所以这里是单 adapter,无需区分。
_ADAPTER = None


def register_adapter(adapter) -> None:
    """让本进程的 adapter 在 module 里有引用。由 server 启动 adapter 时调一次。"""
    global _ADAPTER
    _ADAPTER = adapter


def _gc() -> None:
    """惰性 GC: 清掉超过 _EXPIRY_S 没动的 entry。"""
    now = time.time()
    expired = [k for k, v in _REACTIONS.items() if now - v.get("ts", 0) > _EXPIRY_S]
    for k in expired:
        _REACTIONS.pop(k, None)


async def register_received(msg_id: str, adapter) -> None:
    """入站收到消息 → 在飞书加 👀 表情,并把 reaction_id 存起来。

    幂等:同一 msg_id 重复调用不会重复加(已存在则跳过)。
    adapter 是 IngressAdapter(必须有 add_reaction 方法)。
    """
    if not msg_id or adapter is None:
        return
    if not hasattr(adapter, "add_reaction"):
        return  # adapter 不支持 reaction(如 ClawBot 当前的私聊 bot)
    _gc()
    if msg_id in _REACTIONS:
        return  # 已注册过(可能 30s batch 内同一原消息触发多次入站)
    try:
        rid = await adapter.add_reaction(msg_id, "EYES")
        if rid:
            _REACTIONS[msg_id] = {"reaction_id": rid, "emoji": "EYES", "ts": time.time()}
            logger.debug("reaction 👀 set on %s (rid=%s)", msg_id[:16], rid[:8])
    except Exception as exc:
        logger.debug("register_received failed: %s", exc)


async def mark_processing(msg_id: str, adapter) -> None:
    """wake 触发开始处理 → 撤掉 👀 加 ⚙️。

    必须给定 msg_id;若该 msg_id 没注册过(EYES 没成功),仍尝试加 ⚙️。
    """
    if not msg_id or adapter is None or not hasattr(adapter, "add_reaction"):
        return
    _gc()
    existing = _REACTIONS.get(msg_id)
    # 撤掉旧的(如果有)
    if existing and existing.get("reaction_id") and existing.get("emoji") == "EYES":
        try:
            await adapter.remove_reaction(msg_id, existing["reaction_id"])
        except Exception:
            pass
        existing["reaction_id"] = ""
        existing["emoji"] = ""
    # 加 ⚙️
    try:
        rid = await adapter.add_reaction(msg_id, "SETTINGS")
        if rid:
            _REACTIONS[msg_id] = {"reaction_id": rid, "emoji": "SETTINGS", "ts": time.time()}
            logger.debug("reaction ⚙️ set on %s (rid=%s)", msg_id[:16], rid[:8])
    except Exception as exc:
        logger.debug("mark_processing failed: %s", exc)


async def clear_on_reply(msg_id: str, adapter) -> None:
    """express_to_human 发送成功 → 撤掉 ⚙️(消息本身已是回应)。

    清理 _REACTIONS 中该 msg_id 的 entry(不再保留状态)。
    """
    if not msg_id or adapter is None or not hasattr(adapter, "remove_reaction"):
        return
    existing = _REACTIONS.pop(msg_id, None)
    if not existing or not existing.get("reaction_id"):
        return
    try:
        await adapter.remove_reaction(msg_id, existing["reaction_id"])
        logger.debug("reaction cleared on %s (was %s)",
                     msg_id[:16], existing.get("emoji"))
    except Exception as exc:
        logger.debug("clear_on_reply failed: %s", exc)


async def clear_current_reply() -> None:
    """express_to_human 调用便捷函数:从 runtime_context 拿当前 reply_msg_id
    + 本进程 adapter,撤掉 ⚙️。三态收条-态 3。

    失败静默(收条是反馈层,不影响主流程)。
    """
    if _ADAPTER is None:
        return
    try:
        from domain.lifecycle.runtime_context import get_current_reply_msg_id
        msg_id = get_current_reply_msg_id() or ""
    except Exception:
        return
    if not msg_id:
        return
    await clear_on_reply(msg_id, _ADAPTER)


# ── sync fire-and-forget wrappers ──────────────────────────────────────────
# 调用方(handler 入站 / _emit_l4_human_event / express_to_human)有时是 sync 函数,
# 不能直接 await。这些 wrappers 用一个 daemon 线程跑永不阻塞主流程。
def mark_processing_sync(msg_id: str) -> None:
    """sync 版 mark_processing —— 用于 _emit_l4_human_event 等 sync 调用点。

    用 daemon thread 起一个 asyncio.run。失败静默。
    """
    if not msg_id or _ADAPTER is None:
        return

    def _run():
        try:
            import asyncio
            asyncio.run(_mark_processing_runner(msg_id))
        except Exception as exc:
            logger.debug("mark_processing_sync failed: %s", exc)

    import threading
    threading.Thread(target=_run, daemon=True, name="reaction-mark").start()


async def _mark_processing_runner(msg_id: str) -> None:
    await mark_processing(msg_id, _ADAPTER)


def clear_current_reply_sync() -> None:
    """sync 版 clear_current_reply —— 用于 express_to_human 发送成功后撤 ⚙️。"""

    def _run():
        try:
            import asyncio
            asyncio.run(clear_current_reply())
        except Exception as exc:
            logger.debug("clear_current_reply_sync failed: %s", exc)

    import threading
    threading.Thread(target=_run, daemon=True, name="reaction-clear").start()
