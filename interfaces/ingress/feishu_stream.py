"""飞书流式消息发送器。

实现打字机效果：先发一条消息，然后通过 PATCH API 不断更新内容。

飞书 SDK (lark_oapi) 没有封装 message update API，
所以用 httpx 直接调 REST 接口 PATCH /im/v1/messages/{message_id}。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FeishuStreamSender:
    """飞书流式消息发送器。

    工作流：
    1. send_initial() 发一条占位消息，拿到 message_id
    2. feed() 累积文本片段
    3. 后台定时任务调 PATCH API 更新消息内容
    4. finish() 取消定时任务 + 最后一次 update
    """

    def __init__(
        self,
        domain: str,
        app_id: str,
        app_secret: str,
        update_interval: float = 0.3,
    ):
        self._domain = domain
        self._app_id = app_id
        self._app_secret = app_secret
        self._update_interval = update_interval

        self._message_id: Optional[str] = None
        self._chat_id: Optional[str] = None
        self._buffer: str = ""
        self._last_update_time: float = 0
        self._update_task: Optional[asyncio.Task] = None
        self._is_streaming: bool = False

    # ── 公开 API ──

    async def start(
        self,
        chat_id: str,
        reply_to: str = "",
        initial_text: str = "正在输入...",
    ) -> bool:
        """发送初始占位消息，开始流式输出。"""
        self._chat_id = chat_id
        self._buffer = initial_text

        msg_id = await self._send_message(initial_text, reply_to)
        if not msg_id:
            logger.error("StreamSender: failed to send initial message")
            return False

        self._message_id = msg_id
        self._is_streaming = True
        self._last_update_time = asyncio.get_event_loop().time()
        self._update_task = asyncio.create_task(self._periodic_update_loop())
        return True

    async def feed(self, text: str) -> None:
        """喂入文本片段。"""
        if not self._is_streaming:
            return
        self._buffer += text

    async def finish(self) -> bool:
        """结束流式输出，做最后一次更新。"""
        if not self._is_streaming:
            return False
        self._is_streaming = False

        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        return await self._update_message(self._buffer)

    # ── 内部 ──

    async def _periodic_update_loop(self) -> None:
        try:
            while self._is_streaming:
                await asyncio.sleep(self._update_interval)
                if not self._is_streaming:
                    break
                now = asyncio.get_event_loop().time()
                if now - self._last_update_time >= self._update_interval:
                    await self._update_message(self._buffer)
                    self._last_update_time = now
        except asyncio.CancelledError:
            pass

    async def _send_message(self, content: str, reply_to: str = "") -> Optional[str]:
        """发送消息，返回 message_id（失败返回 None）。用 httpx 直调 REST。"""
        import httpx

        token = await self._get_token()
        if not token:
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {
            "receive_id": self._chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": content}, ensure_ascii=False),
        }

        def _do():
            try:
                with httpx.Client(timeout=5.0) as c:
                    if reply_to:
                        # 回复消息：POST /im/v1/messages/{reply_message_id}/reply
                        r = c.post(
                            f"{self._domain}/open-apis/im/v1/messages/{reply_to}/reply",
                            headers=headers,
                            json=body,
                        )
                    else:
                        r = c.post(
                            f"{self._domain}/open-apis/im/v1/messages?receive_id_type=chat_id",
                            headers=headers,
                            json=body,
                        )
                    data = r.json() or {}
                    if data.get("code") == 0:
                        return (data.get("data") or {}).get("message_id", "")
                    logger.error(f"StreamSender send failed: {data}")
                    return None
            except Exception as exc:
                logger.error(f"StreamSender send error: {exc}")
                return None

        return await asyncio.to_thread(_do)

    async def _update_message(self, content: str) -> bool:
        """PATCH 更新消息内容。"""
        if not self._message_id:
            return False

        import httpx

        token = await self._get_token()
        if not token:
            return False

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {
            "msg_type": "text",
            "content": json.dumps({"text": content}, ensure_ascii=False),
        }

        def _do():
            try:
                with httpx.Client(timeout=5.0) as c:
                    r = c.patch(
                        f"{self._domain}/open-apis/im/v1/messages/{self._message_id}",
                        headers=headers,
                        json=body,
                    )
                    data = r.json() or {}
                    if data.get("code") != 0:
                        logger.warning(f"StreamSender update failed: {data}")
                        return False
                    return True
            except Exception as exc:
                logger.warning(f"StreamSender update error: {exc}")
                return False

        return await asyncio.to_thread(_do)

    async def _get_token(self) -> str:
        """获取 tenant_access_token。"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.post(
                    f"{self._domain}/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": self._app_id, "app_secret": self._app_secret},
                )
                return r.json().get("tenant_access_token", "")
        except Exception:
            return ""
