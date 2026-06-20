"""WeChat ClawBot adapter —— 微信个人号机器人（腾讯 OpenClaw / iLink 协议）。

ClawBot 是腾讯 2026 年通过 OpenClaw 平台开放的微信个人号官方 Bot API。
底层走 iLink 协议（HTTP 长轮询，类似 Telegram Bot API 的 getUpdates）。

平台知识收口在这里：
  - 认证：扫码 → bot_token（Bearer auth）
  - 收消息：POST /ilink/bot/getupdates（hold 35s），用 get_updates_buf 游标推进
  - 发消息：POST /ilink/bot/sendmessage（必须带 context_token 关联对话窗口）
  - ID 格式：from_user_id = "xxx@im.wechat"，to_user_id = "xxx@im.bot"

限制（ChannelCapabilities 已声明）：
  - 仅支持私聊，不支持群聊
  - 不能主动推送，必须用户先发消息触发（有 context_token 才能回复）
  - 不支持媒体（图片/语音/文件，当前 SDK 限制）
  - 不支持 @（私聊场景不需要）

参考实现：github.com/SiverKing/weixin-ClawBot-API（bot.py + weixin-bot-api.md）
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import random
import time
from typing import Any

import httpx

from interfaces.ingress.base import (
    ChannelCapabilities,
    MessageHandler,
    NormalizedMessage,
)

logger = logging.getLogger("digital_life.ingress.wechat_clawbot")


# ClawBot 能力：私聊 only，不能群聊，不能主动推送
CLAWBOT_CAPABILITIES = ChannelCapabilities(
    supports_group=False,
    supports_dm=True,
    supports_proactive=False,   # 必须有 context_token 才能回
    supports_media=False,
    supports_mention=False,
    max_text_length=2000,
)

_DEFAULT_DOMAIN = "https://ilinkai.weixin.qq.com"
_POLL_TIMEOUT = 40  # 长轮询 hold 时间（ClawBot 服务端最多 hold 35s，we 给 40s）


class WeChatClawBotAdapter:
    """微信 ClawBot 个人号机器人 adapter。"""

    platform = "wechat"
    capabilities = CLAWBOT_CAPABILITIES

    def __init__(
        self,
        bot_token: str,
        *,
        domain: str | None = None,
        bot_id: str = "",
    ):
        """初始化 ClawBot adapter。

        Args:
            bot_token: 扫码登录后获得的 Bearer token
            domain: ClawBot API 域名（默认 https://ilinkai.weixin.qq.com）
            bot_id: 机器人自身 ID（xxx@im.bot），getupdates 返回时从消息里推断
        """
        self._bot_token = bot_token.strip()
        self._domain = (domain or _DEFAULT_DOMAIN).rstrip("/")
        self._bot_id = bot_id
        self._poll_buf = ""  # getupdates 游标
        self._handlers: list[MessageHandler] = []
        self._poll_task: asyncio.Task | None = None
        self._running = False

    @property
    def app_identity(self) -> str:
        """机器人稳定身份标识。"""
        return self._bot_id or "wechat_clawbot"

    def on_message(self, handler: MessageHandler) -> None:
        """注册消息回调。"""
        self._handlers.append(handler)

    async def start(self) -> None:
        """启动长轮询循环。"""
        if not self._bot_token:
            logger.error("WeChatClawBotAdapter: no bot_token configured, skipping start")
            return
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("WeChatClawBotAdapter started (%s)", self._bot_id or "bot_id pending")

    async def stop(self) -> None:
        """停止长轮询。"""
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await asyncio.wait_for(self._poll_task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        logger.info("WeChatClawBotAdapter stopped")

    # ── 长轮询循环 ────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        """持续长轮询 ClawBot getupdates。"""
        while self._running:
            try:
                messages = await self._get_updates()
                for raw_msg in messages:
                    normalized = self._normalize(raw_msg)
                    if normalized:
                        # 更新 bot_id（从第一条消息推断）
                        if not self._bot_id and raw_msg.get("to_user_id"):
                            self._bot_id = raw_msg["to_user_id"]
                        for handler in self._handlers:
                            asyncio.ensure_future(handler(normalized))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("ClawBot poll error: %s, retrying in 5s", exc)
                await asyncio.sleep(5)

    async def _get_updates(self) -> list[dict[str, Any]]:
        """POST /ilink/bot/getupdates 长轮询。"""
        url = f"{self._domain}/ilink/bot/getupdates"
        headers = self._build_headers()
        payload: dict[str, Any] = {}
        if self._poll_buf:
            payload["get_updates_buf"] = self._poll_buf

        async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # 推进游标
        if data.get("get_updates_buf"):
            self._poll_buf = data["get_updates_buf"]

        # 消息列表
        item_list = data.get("item_list") or data.get("updates") or []
        return item_list if isinstance(item_list, list) else []

    # ── 发送 ──────────────────────────────────────────────────────────

    async def send(self, chat_id: str, content: str, *, context_token: str = "", reply_to: str = "") -> bool:
        """POST /ilink/bot/sendmessage。

        ClawBot 要求必须带 context_token（从收到的消息里取）关联对话窗口。
        如果没有 context_token，返回 False（capabilities.supports_proactive=False 的原因）。

        Args:
            chat_id: 对方 user_id（xxx@im.wechat），兼容旧签名
            content: 文本内容
            context_token: 从收到的消息里取的对话上下文 token（ClawBot 必须要有）
            reply_to: 不用（ClawBot 没有 reply 语义）
        """
        if not context_token:
            logger.warning("ClawBot send: missing context_token — ClawBot requires it to associate the reply")
            return False

        url = f"{self._domain}/ilink/bot/sendmessage"
        headers = self._build_headers()
        payload = {
            "context_token": context_token,
            "to_user_id": chat_id,
            "item_list": [{"type": 1, "content": content[: self.capabilities.max_text_length]}],
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                result = resp.json()
                if result.get("ret") == 0 or result.get("errcode") == 0:
                    return True
                logger.warning("ClawBot send response: %s", result)
                return False
        except Exception as exc:
            logger.error("ClawBot send failed: %s", exc)
            return False

    # ── 消息标准化 ────────────────────────────────────────────────────

    def _normalize(self, raw: dict[str, Any]) -> NormalizedMessage | None:
        """把 ClawBot 的 JSON 消息转成 NormalizedMessage。

        ClawBot 消息结构：
          {
            "from_user_id": "xxx@im.wechat",
            "to_user_id": "yyy@im.bot",
            "message_id": "...",
            "context_token": "...",
            "item_list": [{"type": 1, "content": "你好"}],
            ...
          }

        type=1 是文本；其他 type（图片/语音/文件）当前不解析。
        """
        if not raw:
            return None
        # 提取文本内容（取 item_list 里第一个 type=1 的 item）
        content = ""
        items = raw.get("item_list") or []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("type") == 1:
                    content = str(item.get("content") or "").strip()
                    break
        if not content:
            # 非文本消息（图片/语音等），跳过
            return None

        from_user = str(raw.get("from_user_id") or "")
        to_user = str(raw.get("to_user_id") or "")
        # 推断 bot_id
        if to_user and not self._bot_id:
            self._bot_id = to_user

        return NormalizedMessage(
            platform="wechat",
            chat_id=from_user,           # 私聊：chat_id = 对方 user_id
            message_id=str(raw.get("message_id") or ""),
            sender_id=from_user,
            content=content,
            sender_name=str(raw.get("from_nickname") or ""),
            chat_name="",                # 私聊没有群名
            is_group=False,              # ClawBot 仅私聊
            mentions_bot=False,          # 私聊不需要 @
            sender_is_bot=False,         # ClawBot 不接收 bot → bot 消息
            context_token=str(raw.get("context_token") or ""),  # send 时回传
            raw=raw,
        )

    # ── 认证 header ───────────────────────────────────────────────────

    def _build_headers(self) -> dict[str, str]:
        """每次请求构建的认证 header。

        ClawBot 要求：
        - Authorization: Bearer {bot_token}
        - X-WECHAT-UIN: 随机 uint32 → base64（防重放）
        """
        headers = {
            "Authorization": f"Bearer {self._bot_token}",
            "Content-Type": "application/json",
        }
        # 防 replay：随机 UIN
        random_uin = random.randint(0, 0xFFFFFFFF)
        headers["X-WECHAT-UIN"] = base64.b64encode(str(random_uin).encode()).decode()
        return headers


# ── 扫码登录（一次性 bootstrap）─────────────────────────────────────────

async def login_clawbot_qrcode(
    domain: str | None = None,
    *,
    timeout: int = 120,
) -> tuple[str, str]:
    """引导用户扫码登录，返回 (bot_token, bot_id)。

    流程：
    1. POST /ilink/bot/get_bot_qrcode → 拿二维码 URL
    2. 循环 POST /ilink/bot/get_qrcode_status 直到 status=confirmed
    3. 拿到 bot_token + bot_id 返回

    这是一个 CLI / 控制台工具函数，不在 adapter runtime 中执行。
    """
    _domain = (domain or _DEFAULT_DOMAIN).rstrip("/")
    async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as client:
        # 1. 拿二维码
        resp = await client.post(f"{_domain}/ilink/bot/get_bot_qrcode")
        resp.raise_for_status()
        qr_data = resp.json()
        qr_url = qr_data.get("qrcode_url") or qr_data.get("url") or ""
        session_key = qr_data.get("session_key") or qr_data.get("ticket") or ""

        if qr_url:
            logger.info("请扫码登录微信 ClawBot: %s", qr_url)

        # 2. 等扫码确认
        deadline = time.time() + timeout
        while time.time() < deadline:
            await asyncio.sleep(3)
            resp = await client.post(
                f"{_domain}/ilink/bot/get_qrcode_status",
                json={"session_key": session_key},
            )
            status_data = resp.json()
            status = status_data.get("status") or status_data.get("ret")
            if status in ("confirmed", "ok", 0, "0"):
                bot_token = status_data.get("bot_token") or ""
                bot_id = status_data.get("bot_id") or ""
                if bot_token:
                    logger.info("ClawBot 登录成功！bot_id=%s", bot_id)
                    return bot_token, bot_id
        raise TimeoutError("ClawBot 扫码登录超时")


__all__ = [
    "WeChatClawBotAdapter",
    "CLAWBOT_CAPABILITIES",
    "login_clawbot_qrcode",
]
