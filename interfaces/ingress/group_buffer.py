"""群消息合并窗口 + 每实例静态 offset —— 收口到 adapter。

设计意图：
- 取代 domain/lifecycle/events.py 里 group_message 类的 30s debounce
  —— 事件层只调度,不合并(单一职责)
- 每实例独立 0~29s offset（配置在 app.yaml.group_chat.batch_offset_s）
  —— 防止多个 bot 同步吐 batch → 同步 wake → 群消息交错两份方案同时到

核心机制：
1. 群消息进来 → 加进 buffer
2. 一个 30s tick 的 flush 协程
3. 每实例有自己的 offset（如 zero=0s、alpha=15s）—— tick 触发时间错开
4. flush 时把窗口里所有 NormalizedMessage 聚成 **单个** NormalizedMessage，
   第一条作为 base，其余以 [{sender, text}, ...] 形式塞 base.merged_texts
   字段（handler / payload 透传给事件层,模型 wake 时能看到 batch 历史）
5. handler 一次调用

各实例读 offset 的来源：
  - app.yaml.group_chat.batch_offset_s（推荐写这里,前端 ConfigTab 可见）
  - fallback 环境 FG_GROUP_BATCH_OFFSET
  - 最终默认 0(意思是该实例跟 tick 同步吐,适合单实例或主导实例)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, List, Optional

logger = logging.getLogger(__name__)


# 窗口长度（秒）。所有实例共用 —— 错开是靠 offset,不是靠窗口长度本身。
GROUP_BATCH_WINDOW_S = 30


class GroupMessageBuffer:
    """pipeline: 收→ buffer → 每 30s + offset 吐 batch。

    每个 adapter 持有自己一个实例(独立 process,无需锁 cross-instance)。
    线程模型: add 在飞书 WS 回调线程(我们把消息 normalize 后异步塞);
    flush 协程在 adapter 自己的 event loop。
    """

    def __init__(
        self,
        handler: Callable[[Any], Awaitable[Any]],
        *,
        window_s: int = GROUP_BATCH_WINDOW_S,
        offset_s: Optional[float] = None,
    ) -> None:
        self._handler = handler
        self._window_s = window_s
        self._offset_s = offset_s  # None 时按 _read_offset() 动态读
        self._buffer: List[Any] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """adapter 在 start() 时绑定 loop。如果 GroupMessageBuffer 在 loop
        之外被构造(比如 __init__),需要 adapter.start 显式 set 一次。"""
        self._loop = loop

    def add(self, msg: Any) -> None:
        """加一条群消息。如果 flush 协程没起,自动起。"""
        if self._loop is None:
            # 退化为同步立即派发(理论上不会发生,adapter start 时一定 set loop)
            logger.warning("GroupMessageBuffer.add called before set_loop; dispatching now")
            self._loop = asyncio.get_event_loop()
        # 把 msg 塞 buffer。lock 走协程,但 add 可能从非 async 上下文调,
        # 用 call_soon_threadsafe 跳回 loop 线程。
        def _do():
            self._buffer.append(msg)
            if self._flush_task is None or self._flush_task.done():
                self._flush_task = self._loop.create_task(self._flush_loop())
        self._loop.call_soon_threadsafe(_do)

    def get_offset(self) -> float:
        """offset 来源: 构造期显式 > env > app.yaml > 默认 0。"""
        if self._offset_s is not None:
            return float(self._offset_s)
        try:
            import os
            v = os.getenv("DIGITAL_LIFE_GROUP_BATCH_OFFSET")
            if v:
                return float(v)
        except Exception:
            pass
        try:
            from infrastructure.config import get_app_instance_id, get_project_root
            iid = get_app_instance_id() or ""
            if iid:
                import yaml as _yaml
                cfg_path = get_project_root() / "apps" / iid / "config" / "app.yaml"
                if cfg_path.exists():
                    cfg = _yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
                    gc = cfg.get("group_chat") or {}
                    v = gc.get("batch_offset_s")
                    if v is not None:
                        return float(v)
        except Exception:
            pass
        return 0.0

    async def _flush_loop(self) -> None:
        """每 _window_s 秒吐一次 batch,首次启动延迟 = offset。

        offset 的作用:让多个实例即使在同一时间窗收到消息,也不会同时吐。
        比如 zero offset=0 → T+0/30/60 吐; alpha offset=15 → T+15/45/75 吐。
        各自看到的 batch 内容不同（alpha 吐时已经能看到 zero 刚才发的消息）。
        """
        offset = self.get_offset()
        # 首次延迟 offset 让首个 tick 时间错开
        await asyncio.sleep(offset)
        while True:
            await asyncio.sleep(self._window_s)
            await self._flush_once()

    async def _flush_once(self) -> None:
        """把 buffer 里所有消息聚成单个 NormalizedMessage 一次调 handler。"""
        async with self._lock:
            if not self._buffer:
                return
            batch = list(self._buffer)
            self._buffer.clear()

        if not batch:
            return

        # 第一条作为 base（保留 chat_id / platform / is_group 等元信息）
        base = batch[0]
        # 单条直接 dispatch（无需包成 batch payload）
        if len(batch) == 1:
            await self._handler(base)
            return

        # 多条合并:把其余条目以 [{sender, text}, ...] 形式挂在 base.merged_texts
        # NormalizedMessage 是 dataclass,直接 setattr; handler 把它传给 payload 透传
        merged_texts = []
        for m in batch:
            sender = getattr(m, "sender_name", "") or getattr(m, "sender_id", "") or "?"
            text = getattr(m, "content", "") or getattr(m, "text", "")
            if text:
                merged_texts.append({"sender": sender, "text": text[:500]})
        try:
            # 构造合并 message 时把最新一条作为 base 内容（让 prompt 主行看到最新一条）
            latest = batch[-1]
            # 复制 base 但替换 content/sender 为最新一条 —— dataclass 不支持 replace by default
            # 简单 setattr（NormalizedMessage 是 mutable dataclass）
            for field in ("content", "sender_name", "sender_id", "message_id"):
                if hasattr(latest, field):
                    setattr(base, field, getattr(latest, field))
            base.merged_texts = merged_texts  # 见 base.py NormalizedMessage 字段
        except Exception as exc:
            logger.warning("GroupMessageBuffer merge failed, fallback to per-msg dispatch: %s", exc)
            for m in batch:
                await self._handler(m)
            return

        logger.info(
            "GroupMessageBuffer flushed batch: %d msgs, merged_texts=%d",
            len(batch), len(merged_texts),
        )
        await self._handler(base)

    async def stop(self) -> None:
        """adapter stop 时取消 flush。"""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        # 最后吐一次残留
        await self._flush_once()


# 默认实例:每个 adapter 持有自己的 buffer（独立 process,无需共享）
# 但简化使用,这里给个 _default_buffer lazy 单例,供上面 _GROUP_MSG_BUFFER 调用
_default_buffer: Optional[GroupMessageBuffer] = None


def get_default_buffer(handler: Optional[Callable] = None) -> GroupMessageBuffer:
    """获取默认 buffer 单例。第一次调用必须传 handler。"""
    global _default_buffer
    if _default_buffer is None:
        if handler is None:
            raise RuntimeError(
                "GroupMessageBuffer default not initialized; "
                "call get_default_buffer(handler=...) first"
            )
        _default_buffer = GroupMessageBuffer(handler)
    return _default_buffer


def set_default_buffer(buf: GroupMessageBuffer) -> None:
    """让 adapter start() 时显式注入带正确 loop 的 buffer。"""
    global _default_buffer
    _default_buffer = buf
