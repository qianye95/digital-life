"""Reaction 表情收条状态机 — 跨三个调用点传递 msg_id ↔ reaction_id。

三态收条:
  入站收到 → 加 ✅ (DONE)
  wake 启动 LLM → 撤全部 ✅ + 加 🤔 (THINKING) ← 延迟到 wake 真跑时(不是 emit 后立即)
  express_to_human 发送后 → 撤全部 🤔

batch 多条消息:register/mark/clear 全部对 batch 内所有 msg_id 操作。
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time

logger = logging.getLogger(__name__)

# msg_id → {reaction_id, emoji, ts}
_REACTIONS: dict[str, dict] = {}
_EXPIRY_S = 3600
_ADAPTER = None


def register_adapter(adapter) -> None:
    global _ADAPTER
    _ADAPTER = adapter


def _gc() -> None:
    now = time.time()
    expired = [k for k, v in _REACTIONS.items() if now - v.get("ts", 0) > _EXPIRY_S]
    for k in expired:
        _REACTIONS.pop(k, None)


async def register_received(msg_id: str, adapter) -> None:
    """入站收到消息 → 飞书消息上加 ✅。幂等。"""
    if not msg_id or adapter is None or not hasattr(adapter, "add_reaction"):
        return
    _gc()
    if msg_id in _REACTIONS:
        return
    try:
        rid = await adapter.add_reaction(msg_id, "DONE")
        if rid:
            _REACTIONS[msg_id] = {"reaction_id": rid, "emoji": "DONE", "ts": time.time()}
            logger.debug("✅ set on %s", msg_id[:16])
    except Exception as exc:
        logger.debug("register_received failed: %s", exc)


async def mark_all_processing(adapter=None) -> None:
    """撤掉所有 ✅ → 加 🤔。在 wake 真正启动 LLM 时调,不在 emit 后立即调。

    把所有当前 emoji=DONE 的 msg_id 切到 THINKING。
    """
    ad = adapter or _ADAPTER
    if ad is None or not hasattr(ad, "add_reaction"):
        return
    _gc()
    for msg_id, info in list(_REACTIONS.items()):
        if info.get("emoji") != "DONE":
            continue
        # 撤 ✅
        rid = info.get("reaction_id", "")
        if rid:
            try:
                await ad.remove_reaction(msg_id, rid)
            except Exception:
                pass
        # 加 🤔
        try:
            new_rid = await ad.add_reaction(msg_id, "THINKING")
            if new_rid:
                _REACTIONS[msg_id] = {"reaction_id": new_rid, "emoji": "THINKING", "ts": time.time()}
                logger.debug("🤔 set on %s", msg_id[:16])
        except Exception as exc:
            logger.debug("mark_processing on %s failed: %s", msg_id[:16], exc)


async def clear_all_reactions(adapter=None) -> None:
    """撤掉所有活跃表情(✅ 或 🤔)。express_to_human 发送成功后调。"""
    ad = adapter or _ADAPTER
    if ad is None or not hasattr(ad, "remove_reaction"):
        return
    for msg_id in list(_REACTIONS.keys()):
        info = _REACTIONS.pop(msg_id, None)
        if info and info.get("reaction_id"):
            try:
                await ad.remove_reaction(msg_id, info["reaction_id"])
                logger.debug("cleared %s on %s", info.get("emoji"), msg_id[:16])
            except Exception as exc:
                logger.debug("clear on %s failed: %s", msg_id[:16], exc)


# ── sync wrappers ──

def mark_all_processing_sync() -> None:
    if _ADAPTER is None:
        return
    def _run():
        try:
            asyncio.run(mark_all_processing())
        except Exception as exc:
            logger.debug("mark_all_processing_sync failed: %s", exc)
    threading.Thread(target=_run, daemon=True, name="reaction-mark").start()


def clear_all_reactions_sync() -> None:
    def _run():
        try:
            asyncio.run(clear_all_reactions())
        except Exception as exc:
            logger.debug("clear_all_reactions_sync failed: %s", exc)
    threading.Thread(target=_run, daemon=True, name="reaction-clear").start()
