"""飞书流式适配器。

继承 FeishuAdapter，通过 enable_streaming 属性切换流式/非流式输出。
不影响原有 FeishuAdapter 的任何方法。
"""

from __future__ import annotations

import logging

from interfaces.ingress.feishu import FeishuAdapter

logger = logging.getLogger(__name__)


class FeishuStreamingAdapter(FeishuAdapter):
    """支持流式输出的飞书适配器。

    通过 enable_streaming 属性控制 send() 是否走流式。
    False（默认）时行为与原 FeishuAdapter 完全一致。
    """

    def __init__(self, *args, enable_streaming: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_streaming: bool = enable_streaming
        self._active_stream = None  # 当前活跃的 FeishuStreamSender
        logger.info(
            "FeishuStreamingAdapter created (enable_streaming=%s)",
            enable_streaming,
        )

    async def send_streaming(
        self,
        chat_id: str,
        content: str,
        reply_to: str = "",
        *,
        initial_text: str = "正在输入...",
        update_interval: float = 0.3,
    ) -> bool:
        """一次性文本的流式发送（内部模拟流式效果）。

        把完整文本拆成字符逐步 feed，模拟打字机效果。
        """
        if not self.enable_streaming:
            return await self.send(chat_id, content, reply_to)

        from interfaces.ingress.feishu_stream import FeishuStreamSender

        sender = FeishuStreamSender(
            domain=self._domain,
            app_id=self._app_id,
            app_secret=self._app_secret,
            update_interval=update_interval,
        )

        if not await sender.start(chat_id, reply_to, initial_text):
            # 降级：直接发送完整内容
            return await self.send(chat_id, content, reply_to)

        self._active_stream = sender
        try:
            # 按字符逐字 feed，模拟打字机
            for char in content:
                await sender.feed(char)
        finally:
            self._active_stream = None

        return await sender.finish()

    async def send_chunks(
        self,
        chat_id: str,
        chunks: list[str],
        reply_to: str = "",
        *,
        initial_text: str = "正在输入...",
        update_interval: float = 0.3,
    ) -> bool:
        """按 chunk 列表流式发送（外部已有分段内容时使用）。

        每 feed 一个 chunk 等待 update_interval，让定时任务有时间 flush。
        """
        if not self.enable_streaming:
            full = "".join(chunks)
            return await self.send(chat_id, full, reply_to)

        import asyncio
        from interfaces.ingress.feishu_stream import FeishuStreamSender

        sender = FeishuStreamSender(
            domain=self._domain,
            app_id=self._app_id,
            app_secret=self._app_secret,
            update_interval=update_interval,
        )

        if not await sender.start(chat_id, reply_to, initial_text):
            full = "".join(chunks)
            return await self.send(chat_id, full, reply_to)

        self._active_stream = sender
        try:
            for chunk in chunks:
                await sender.feed(chunk)
                await asyncio.sleep(update_interval)
        finally:
            self._active_stream = None

        return await sender.finish()

    async def send_generator(
        self,
        chat_id: str,
        generator,
        reply_to: str = "",
        *,
        initial_text: str = "正在输入...",
        update_interval: float = 0.3,
    ) -> bool:
        """接收 async generator 的流式发送（LLM 流式输出场景）。

        generator 应 yield 文本片段（str）。
        """
        if not self.enable_streaming:
            parts = []
            async for chunk in generator:
                parts.append(chunk)
            full = "".join(parts)
            return await self.send(chat_id, full, reply_to)

        from interfaces.ingress.feishu_stream import FeishuStreamSender

        sender = FeishuStreamSender(
            domain=self._domain,
            app_id=self._app_id,
            app_secret=self._app_secret,
            update_interval=update_interval,
        )

        if not await sender.start(chat_id, reply_to, initial_text):
            parts = []
            async for chunk in generator:
                parts.append(chunk)
            full = "".join(parts)
            return await self.send(chat_id, full, reply_to)

        self._active_stream = sender
        try:
            async for chunk in generator:
                await sender.feed(chunk)
        finally:
            self._active_stream = None

        return await sender.finish()
