"""Social context — 给模型的社交关系总览。

包含：
- 我认识的 contacts（人 / bot / system）— 来自 domain.contacts
- 我参与的群 — 来自 app.yaml.messenger.chat_ids + project.yaml.group_chat_id + chat_stream 历史里见过的 chat_id

每次 wake 注入到 prompt 里（_sys_tool=social_context），让模型决定
「这条话应该发给谁，发哪个 chat」。

注：项目岗位不再渲染——_role_positioning 段（scheduler.py）已经把
   "我担任什么项目的什么岗位 + 协作者是谁" 完整内容插到 system prompt
   里，这里再渲染会重复。
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def render_social_context(instance_id: str) -> str:
    """渲染给 LLM 看的社交关系文本。空时返回空字符串。

    多通道设计：每个联系人显示**所有平台**的可达 ID + 发送提示。
    模型据此决定「用什么 channel 发给谁」。
    """
    lines: list[str] = ["## ── 我的社交关系 ──"]

    # ─── 联系人（contacts） ───
    try:
        from domain.contacts import list_contacts
        cs = list_contacts() or []
        humans = [c for c in cs if c.get("kind") == "human"]
        bots = [c for c in cs if c.get("kind") == "bot"]

        def _channel_ids(c: dict) -> list[str]:
            """提取联系人**所有平台**的可达 ID（带通道前缀）。

            返回例：["lark:ou_eb5083eb...", "wechat:zhp@im.wechat..."]
            ⚠️ 完整 ID 必须保留——模型会原样填回 express_to_human(channel=...)。
               任何截断都会让模型拿到无法发送的废字符串。
            """
            out = []
            for p in (c.get("platform_ids") or []):
                pf = (p.get("platform") or "").strip()
                pid = (p.get("platform_id") or "").strip()
                if not pid:
                    continue
                if pf == "feishu":
                    out.append(f"lark:{pid}")
                elif pf == "wechat":
                    out.append(f"wechat:{pid}")
                else:
                    out.append(f"{pf}:{pid}")
            return out

        if humans:
            lines.append("\n联系人（人类），回复时按平台填 channel：")
            lines.append("  格式：lark:dm:<ou_xxx>（飞书私聊）/ lark:group:<oc_xxx>（飞书群）/ wechat:dm:<xxx@im.wechat>（微信）")
            for c in humans:
                ids = _channel_ids(c)
                name = (c.get("name") or "").strip()
                label = name if name else "(未命名)"
                id_part = f" [{', '.join(ids)}]" if ids else ""
                note = (c.get("notes") or "").strip()
                lines.append(f"  · {label}{id_part}" + (f" / 备注: {note[:80]}" if note else ""))
        if bots:
            lines.append("\n联系人（机器人，群内可用 @<name> 召唤）：")
            for c in bots:
                ids = _channel_ids(c)
                name = (c.get("name") or "").strip()
                label = name if name else "(未命名 bot)"
                id_part = f" [{', '.join(ids)}]" if ids else ""
                note = (c.get("notes") or "").strip()
                lines.append(f"  · {label}{id_part}" + (f" / 备注: {note[:80]}" if note else ""))
    except Exception as exc:
        logger.debug("social_context contacts failed: %s", exc)

    # ─── 群组（chat_ids） ───
    try:
        chats = _collect_known_chats(instance_id)
        if chats:
            lines.append("\n参与的群，回复时按平台填 channel：")
            lines.append("  格式：lark:group:<oc_xxx>（飞书群）/ wechat:group:<group_id>（微信群，ClawBot 暂不支持群）")
            for cid, name in chats.items():
                name_display = name or "(未命名群)"
                # 标注平台（飞书 oc_ / 微信 @im）— 完整 cid 保留
                if cid.startswith("oc_"):
                    lines.append(f"  · {name_display}（lark:{cid}）")
                elif "@im" in cid:
                    lines.append(f"  · {name_display}（wechat:{cid}）")
                else:
                    lines.append(f"  · {name_display}（{cid}）")
    except Exception as exc:
        logger.debug("social_context chats failed: %s", exc)

    # 项目岗位不再渲染——与 system prompt 的 _role_positioning 段完全重复。

    if len(lines) <= 1:
        return ""

    lines.append("\n## ── /社交关系 ──")
    return "\n".join(lines)


def _collect_known_chats(instance_id: str) -> dict[str, str]:
    """收集我参与的群（chat_id → name）。

    来源优先级：
    1. apps/<id>/config/app.yaml: feishu.chat_ids 列表（含名称如果配置）
    2. servers 上跑过的 project.yaml: group_chat_id（解析 chat_id 拿名称）
    3. conversation_log 里历史出现过的 chat_id（统计 in 事件，最常用的）
    """
    out: dict[str, str] = {}
    # 1. app.yaml: messenger.chat_ids + channels.*.chat_ids
    try:
        import yaml
        from infrastructure.config import get_project_root
        app_yaml = get_project_root() / "apps" / instance_id / "config" / "app.yaml"
        if app_yaml.exists():
            cfg = yaml.safe_load(app_yaml.read_text(encoding="utf-8")) or {}
            # 旧格式
            messenger = cfg.get("messenger") or {}
            for c in (messenger.get("chat_ids") or []):
                if isinstance(c, dict):
                    cid = str(c.get("chat_id") or c.get("id") or "").strip()
                    name = str(c.get("name") or c.get("display_name") or "").strip()
                    if cid and cid not in out:
                        out[cid] = name
                elif isinstance(c, str):
                    cid = c.strip()
                    if cid and cid not in out:
                        out[cid] = ""
            # 新格式 channels
            channels = cfg.get("channels") or {}
            if isinstance(channels, dict):
                for ch_cfg in channels.values():
                    if isinstance(ch_cfg, dict):
                        for c in (ch_cfg.get("chat_ids") or []):
                            if isinstance(c, str) and c.strip() and c.strip() not in out:
                                out[c.strip()] = ""
                            elif isinstance(c, dict):
                                cid = str(c.get("chat_id") or c.get("id") or "").strip()
                                name = str(c.get("name") or "").strip()
                                if cid and cid not in out:
                                    out[cid] = name
    except Exception as exc:
        logger.debug("_collect_known_chats app.yaml failed: %s", exc)

    # 2. project.yaml group_chat_id
    try:
        from domain.project.loader import load_all_projects
        for pid, cfg in (load_all_projects() or {}).items():
            gc = getattr(cfg, "group_chat_id", "") or ""
            if gc and gc not in out:
                out[gc] = getattr(cfg, "name", "") or ""
    except Exception as exc:
        logger.debug("_collect_known_chats project.yaml failed: %s", exc)

    # 3. conversation_log 历史里见过的 chat_id（最近 N 个 + 直方图，取前 5 个用量大）
    try:
        import sqlite3
        from infrastructure.config import get_runtime_state_db_path
        db = get_runtime_state_db_path()
        if db.exists():
            conn = sqlite3.connect(str(db))
            try:
                rows = conn.execute(
                    "SELECT conversation_id, COUNT(*) c "
                    "FROM conversation_log "
                    "WHERE conversation_id IS NOT NULL AND conversation_id != '' "
                    "GROUP BY conversation_id "
                    "ORDER BY c DESC LIMIT 5"
                ).fetchall()
                for cid, _ in rows:
                    cid = str(cid or "").strip()
                    if cid and cid not in out:
                        out[cid] = ""
            finally:
                conn.close()
    except Exception as exc:
        logger.debug("_collect_known_chats conversation_log failed: %s", exc)

    # 拉群名（chat_name）：现有 contacts 没记录群名。这里仅填充能查到的。
    # 后续可加 chat_groups 表显式登记群名（暂不做）。
    return out
