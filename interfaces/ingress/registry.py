"""通道注册表 + 工厂函数 —— 从配置创建 adapter 的唯一入口。

架构原则：server.py / handler.py 不直接 import 具体Adapter，全部通过本模块
的 create_adapters_from_config 拿到 adapter 列表。

支持的通道类型（在 _ADAPTER_BUILDERS 里注册）：
  - "feishu" → FeishuAdapter（飞书 WebSocket 长连接）
  - "wechat_clawbot" → WeChatClawBotAdapter（微信 ClawBot 长轮询）

未来加新通道只需：
  1. 实现 IngressAdapter Protocol（新建一个 adapter 文件）
  2. 在 _ADAPTER_BUILDERS 加一个 factory 函数
  3. 其余层（handler/router/server）零改动
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("digital_life.ingress.registry")


def _build_feishu(cfg: dict[str, Any], secrets_env: dict[str, str]) -> Any:
    """从 channels.feishu 配置 + secrets 构建 FeishuAdapter。"""
    from interfaces.ingress.feishu import FeishuAdapter

    app_id = str(cfg.get("app_id") or "").strip()
    app_secret = (
        secrets_env.get("FEISHU_APP_SECRET")
        or os.getenv("FEISHU_APP_SECRET")
        or ""
    ).strip()
    domain = str(cfg.get("feishu_domain") or "").strip() or None
    if not app_id:
        raise ValueError("feishu channel requires app_id")
    return FeishuAdapter(app_id=app_id, app_secret=app_secret, domain=domain)


def _build_wechat_clawbot(cfg: dict[str, Any], secrets_env: dict[str, str]) -> Any:
    """从 channels.wechat 配置 + secrets 构建 WeChatClawBotAdapter。"""
    from interfaces.ingress.wechat_clawbot import WeChatClawBotAdapter

    bot_token = (
        secrets_env.get("WECHAT_BOT_TOKEN")
        or os.getenv("WECHAT_BOT_TOKEN")
        or ""
    ).strip()
    domain = str(cfg.get("domain") or "").strip() or None
    bot_id = str(cfg.get("bot_id") or "").strip()

    if not bot_token:
        raise ValueError(
            "wechat_clawbot channel requires WECHAT_BOT_TOKEN in secrets.env.\n"
            "扫码登录拿 token：python -c \"import asyncio; "
            "from interfaces.ingress.wechat_clawbot import login_clawbot_qrcode; "
            "asyncio.run(login_clawbot_qrcode())\""
        )
    return WeChatClawBotAdapter(bot_token=bot_token, domain=domain, bot_id=bot_id)


# 通道类型 → builder 映射
_ADAPTER_BUILDERS = {
    "feishu": _build_feishu,
    "wechat_clawbot": _build_wechat_clawbot,
    # 未来：
    # "dingtalk_stream": _build_dingtalk,
    # "telegram": _build_telegram,
    # "wecom": _build_wecom,
}


def parse_channels(app_yaml_cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """从实例的 app.yaml 解析 channels 配置。

    支持两种格式：
    1. 新格式（多通道）：
        channels:
          feishu:
            type: feishu
            app_id: cli_xxx
          wechat:
            type: wechat_clawbot

    2. 旧格式（单通道，向后兼容）：
        messenger:
          type: feishu
          app_id: cli_xxx

    旧格式自动包装成 { feishu: { type: feishu, app_id: cli_xxx } }。
    """
    if not app_yaml_cfg:
        return {}

    # 新格式优先
    channels = app_yaml_cfg.get("channels")
    if isinstance(channels, dict) and channels:
        return channels

    # 旧格式兼容：messenger → 单通道
    messenger = app_yaml_cfg.get("messenger")
    if isinstance(messenger, dict) and messenger:
        msgr_type = str(messenger.get("type") or "feishu")
        # 用 messenger 的 type 作为 channel name（通常是 feishu）
        return {msgr_type: messenger}

    return {}


def create_adapters_from_config(
    app_yaml_cfg: dict[str, Any],
    secrets_env: dict[str, str],
) -> list[Any]:
    """从配置创建所有通道的 adapter 列表。

    Args:
        app_yaml_cfg: apps/<id>/config/app.yaml 解析后的 dict
        secrets_env: apps/<id>/config/secrets.env 解析后的 {key: value}

    Returns:
        adapter 实例列表（已初始化但未 start）
    """
    channels = parse_channels(app_yaml_cfg)
    if not channels:
        logger.warning("No channels configured in app.yaml")
        return []

    adapters = []
    for ch_name, ch_cfg in channels.items():
        adapter_type = str(ch_cfg.get("type") or ch_name)
        builder = _ADAPTER_BUILDERS.get(adapter_type)
        if not builder:
            logger.warning(
                "Unknown channel type '%s' (name='%s'), skipping. "
                "Supported: %s",
                adapter_type, ch_name, list(_ADAPTER_BUILDERS.keys()),
            )
            continue
        try:
            adapter = builder(ch_cfg, secrets_env)
            adapters.append(adapter)
            logger.info(
                "Channel '%s' (type=%s) adapter created: platform=%s identity=%s",
                ch_name, adapter_type,
                getattr(adapter, "platform", "?"),
                getattr(adapter, "app_identity", "?"),
            )
        except Exception as exc:
            logger.error(
                "Failed to create adapter for channel '%s' (type=%s): %s",
                ch_name, adapter_type, exc,
            )

    return adapters


def get_supported_types() -> list[str]:
    """返回当前注册的所有通道类型名。"""
    return list(_ADAPTER_BUILDERS.keys())


__all__ = [
    "parse_channels",
    "create_adapters_from_config",
    "get_supported_types",
]
