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
    """渲染给 LLM 看的社交关系文本。空时返回空字符串。"""
    lines: list[str] = ["## ── 我的社交关系 ──"]

    # ─── 联系人（contacts） ───
    try:
        from domain.contacts import list_contacts
        cs = list_contacts() or []
        humans = [c for c in cs if c.get("kind") == "human" and (c.get("name") or "").strip()]
        bots = [c for c in cs if c.get("kind") == "bot" and (c.get("name") or "").strip()]
        unnamed = [c for c in cs if not (c.get("name") or "").strip()]

        def _short_pid(c: dict) -> str:
            """提取联系人的飞书短码：ou_xxxx...（截断 12 位），私聊发消息时填入。
            缺失返回空串。"""
            for p in (c.get("platform_ids") or []):
                if p.get("platform") == "feishu":
                    pid = (p.get("platform_id") or "").strip()
                    # ou_ 是 open_id，私聊用；oc_ 是单聊 chat_id，也能用
                    if pid.startswith(("ou_", "oc_")):
                        return pid[:12] + "…" if len(pid) > 12 else pid
            return ""

        if humans:
            lines.append("\n联系人（人类），私聊请把 ou_xxx 填入 chat_id：")
            for c in humans[:20]:  # 仅前 20，避免过长
                short = _short_pid(c)
                id_part = f"（{short}）" if short else ""
                note = (c.get("notes") or "").strip()
                lines.append(f"  · {c['name']}{id_part}" + (f" / 备注: {note[:60]}" if note else ""))
        if bots:
            lines.append("\n联系人（机器人，可用 @<name> 召唤）：")
            for c in bots:
                short = _short_pid(c)
                id_part = f"（{short}）" if short else ""
                note = (c.get("notes") or "").strip()
                lines.append(
                    f"  · {c['name']}{id_part}（与另一个实例对话请用 @{c['name']}）"
                    + (f" / 备注: {note[:60]}" if note else "")
                )
        if unnamed:
            lines.append(f"\n（还有 {len(unnamed)} 个未命名的 stub 联系人）")
    except Exception as exc:
        logger.debug("social_context contacts failed: %s", exc)

    # ─── 群组（chat_ids） ───
    try:
        chats = _collect_known_chats(instance_id)
        if chats:
            lines.append("\n参与的群：")
            for cid, name in chats.items():
                short = cid[:12] + "…" if len(cid) > 12 else cid
                name_display = name or "(未命名群)"
                lines.append(f"  · {name_display}（{short}）")
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
    # 1. app.yaml messenger.chat_ids
    try:
        import yaml
        from infrastructure.config import get_project_root
        app_yaml = get_project_root() / "apps" / instance_id / "config" / "app.yaml"
        if app_yaml.exists():
            cfg = yaml.safe_load(app_yaml.read_text(encoding="utf-8")) or {}
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
                    "WHERE conversation_id LIKE 'oc_%' "
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
