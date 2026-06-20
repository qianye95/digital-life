"""L4 lifecycle context: 当前进程正在执行哪个 affair。

运行时在加载事务时调用 set_current_affair(aid)，
lifecycle 工具通过 get_current_affair() 拿到 aid 并把 WaitIntent 绑定到它。

用 ContextVar 而非全局变量，使得同进程内多运行时实例不互串。
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_current: ContextVar[Optional[str]] = ContextVar("digital_life_affair_id", default=None)


def set_current_affair(affair_id: Optional[str]) -> None:
    _current.set(affair_id)


def get_current_affair() -> Optional[str]:
    return _current.get()


_wake_reason: ContextVar[str] = ContextVar("digital_life_wake_reason", default="")


def set_current_wake_reason(reason: str) -> None:
    _wake_reason.set(reason)


def get_current_wake_reason() -> str:
    return _wake_reason.get()


# 当前正在交互的 conversation_id（平台内唯一 ID，如飞书 oc_xxx）
# sense_conversation 用它做智能默认过滤
_conversation_id: ContextVar[str] = ContextVar("digital_life_conversation_id", default="")


def set_current_conversation_id(conv_id: str) -> None:
    _conversation_id.set(conv_id)


def get_current_conversation_id() -> str:
    return _conversation_id.get()


# 当前正在处理的事件来源 chat_id（消息事件携带，prompt hint + reply channel 默认值）
# set 由 scheduler wake 入口、mid-session inject 路径负责
# express_to_human 在模型未显式指定 chat_id 时用它做 fallback
# 与 conversation_id 的区别：conversation_id 更宽泛（含主动发起的会话），
# event_chat_id 严格表示"当前刺激来源 chat"
_event_chat_id: ContextVar[str] = ContextVar("digital_life_event_chat_id", default="")


def set_current_event_chat_id(chat_id: str) -> object:
    """设置当前事件来源 chat_id。返回 token 供 reset 使用。"""
    return _event_chat_id.set(chat_id or "")


def get_current_event_chat_id() -> str:
    return _event_chat_id.get()


def reset_current_event_chat_id(token) -> None:
    """与 set_current_event_chat_id 配对使用。"""
    try:
        _event_chat_id.reset(token)
    except Exception:
        pass


# ── 多通道上下文：当前事件来自哪个平台 + 通道相关的 platform token ──────────
# feishu → 平台前缀 "lark"，wechat → "wechat"
# express_to_human 用来决定发到哪个通道(action_tools.py channel 前缀)
_event_platform: ContextVar[str] = ContextVar("digital_life_event_platform", default="")


def set_current_event_platform(platform: str) -> object:
    """设置当前事件来源平台（feishu/wechat/...）。返回 token。"""
    _pf = "lark" if (platform or "").lower() in ("feishu", "lark") else (platform or "")
    return _event_platform.set(_pf)


def get_current_event_platform() -> str:
    """返回当前事件平台前缀（lark / wechat / ''=未设置）。"""
    return _event_platform.get()


def reset_current_event_platform(token) -> None:
    try:
        _event_platform.reset(token)
    except Exception:
        pass


# ClawBot context_token：微信 ClawBot 发回复必须传的对话令牌
# express_to_human → _send_wechat_clawbot 读取它
_context_token: ContextVar[str] = ContextVar("digital_life_context_token", default="")


def set_current_context_token(token: str) -> object:
    """设置当前会话的 ClawBot context_token。返回 token。"""
    return _context_token.set(token or "")


def get_current_context_token() -> str:
    """返回当前会话的 context_token（ClawBot 用，飞书为空）。"""
    return _context_token.get()


def reset_current_context_token(token) -> None:
    try:
        _context_token.reset(token)
    except Exception:
        pass
