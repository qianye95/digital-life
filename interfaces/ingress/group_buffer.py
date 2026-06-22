"""群消息合并窗口 + 每实例静态 offset —— 收口到 adapter。

设计意图:
- 取代 domain/lifecycle/events.py 里 group_message 类的 30s debounce
  (事件层只调度,不合并,单一职责)
- 每实例独立 0~29s offset (app.yaml.group_chat.batch_offset_s)
  防止多个 bot 同步吐 batch → 同步 wake → 群消息交错两份方案同时到

⚠️ 2026-06-21 重大 bug 修法:
之前 _flush_loop 是 asyncio task,跑在调用 add 时所在的 event loop。但
FeishuAdapter 把 lark_oapi WSClient 跑在子线程,子线程的 loop 用
`loop.run_until_complete(_connect())` blocking — add 在该 blocking loop
里被调,即便 create_task 了 _flush_loop,loop 永远 stuck 在 socket read
不 yield 给该 task → flush 偶发跑不跑。

修法: 扔掉 asyncio task timing, 改 daemon thread + 异步 run coroutine。
daemon thread 每 30s tick, 每次用独立 asyncio.run(_flush_once) 跑 handler。
彻底脱离 lark WS 的 blocking loop。
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Awaitable, Callable, List, Optional

logger = logging.getLogger(__name__)


# 窗口长度(秒)
GROUP_BATCH_WINDOW_S = 30


class GroupMessageBuffer:
    """pipeline: 收 → buffer → 30s + offset 吐 batch (1 个 NormalizedMessage)。

    每 adapter 一个实例。flush 在 daemon thread 跑, 不依赖任何外部 loop。
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
        self._offset_s = offset_s
        # buffer 跨线程共享, threading.Lock 保护
        self._buffer: List[Any] = []
        self._buffer_lock = threading.Lock()
        # stop flag 让 daemon thread 跳出循环
        self._stop_flag = threading.Event()
        self._flush_thread: Optional[threading.Thread] = None
        self._started = False

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """兼容接口。flush 已不再依赖 loop timing, 这方法是 no-op。"""
        pass

    def add(self, msg: Any) -> None:
        """加一条群消息。同步、线程安全。首次 add 启动 daemon thread。"""
        with self._buffer_lock:
            self._buffer.append(msg)
        self._ensure_started()

    def _ensure_started(self) -> None:
        if self._started:
            return
        self._started = True
        self._flush_thread = threading.Thread(
            target=self._flush_run,
            daemon=True,
            name="group-buffer-flush",
        )
        self._flush_thread.start()

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

    def _flush_run(self) -> None:
        """daemon thread 主循环: 窗口 30s → random(0,10) 抖动 → flush。

        累积窗口 30s 不变(收集消息)。
        flush 延迟 random(0,10) 让多实例自然错峰(替代之前的静态 batch_offset_s)。
        每次 flush 用 asyncio.run 在临时 loop 跑,避免污染 lark_oapi blocking WS loop。
        """
        import random

        while not self._stop_flag.is_set():
            # 30s 累积窗口(stop 时立刻 break)
            if self._stop_flag.wait(self._window_s):
                break
            # random(0,10) 抖动 — 多实例自然错峰,期望响应延迟 0~10s
            jitter = random.uniform(0, 10)
            if self._stop_flag.wait(jitter):
                break
            try:
                asyncio.run(self._flush_once())
            except Exception as exc:
                logger.warning("GroupMessageBuffer flush run failed: %s", exc)

    async def _flush_once(self) -> None:
        """把 buffer 里所有消息聚成单个 NormalizedMessage 一次调 handler。"""
        with self._buffer_lock:
            if not self._buffer:
                return
            batch = list(self._buffer)
            self._buffer.clear()

        if not batch:
            return

        base = batch[0]
        if len(batch) == 1:
            await self._handler(base)
            return

        # 多条合并:把所有 sender/text 收集, base 字段换成最新一条
        merged_texts = []
        for m in batch:
            sender = getattr(m, "sender_name", "") or getattr(m, "sender_id", "") or "?"
            text = getattr(m, "content", "") or getattr(m, "text", "")
            if text:
                merged_texts.append({"sender": sender, "text": text[:500]})
        try:
            latest = batch[-1]
            for field in ("content", "sender_name", "sender_id", "message_id"):
                if hasattr(latest, field):
                    setattr(base, field, getattr(latest, field))
            base.merged_texts = merged_texts
        except Exception as exc:
            logger.warning("GroupMessageBuffer merge failed, fallback per-msg: %s", exc)
            for m in batch:
                await self._handler(m)
            return

        logger.info(
            "GroupMessageBuffer flushed batch: %d msgs, merged_texts=%d",
            len(batch), len(merged_texts),
        )
        await self._handler(base)

    def stop(self) -> None:
        """adapter stop 时停止 daemon thread + 吐最后一批。"""
        self._stop_flag.set()
        try:
            asyncio.run(self._flush_once())
        except Exception as exc:
            logger.warning("GroupMessageBuffer stop flush failed: %s", exc)
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=2.0)
