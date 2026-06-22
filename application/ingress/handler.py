"""消息入口处理 — 将飞书消息路由到正确的数字生命实例。

核心流程 (handle_message):
  1. resolve_instance() 解析消息应发往哪个实例
  2. 编排前置检查（orchestration preflight）
  3. 设置实例上下文（ContextVar + 环境变量）
  4. _route_to_life() → 发出 message/group_message 事件
  5. 如果 affair 为 BLOCKED/PENDING → 直接后台唤醒
  6. 如果 affair 为 RUNNING → 立即注入事件到运行中会话（不等 cron tick）

直接唤醒 vs 等待 tick：
  - BLOCKED 状态直接唤醒：用户发消息时应立即响应，不等 60s cron 周期
  - RUNNING 状态注入事件：避免 cron tick 等待导致连续消息被遗漏
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time

from interfaces.ingress.base import IngressAdapter, NormalizedMessage

logger = logging.getLogger(__name__)


def _sender_is_sibling_bot(sender_id: str, platform: str) -> str:
    """Return the sibling app_id if ``sender_id`` belongs to another
    digital-life instance on this platform. Empty string otherwise.

    Each instance configures its own Feishu app at ``apps/<id>/config/app.yaml``;
    the app_id is what Feishu reports as ``sender_id`` when a bot emits a
    message. Two bot instances in the same group will see each other's
    replies — without suppression, that creates an echo loop.

    We never suppress the *self* instance's own messages because Feishu's
    WS delivery already filters the sender's own posts.
    """
    if not sender_id or not platform:
        return ""
    try:
        from infrastructure.config import discover_instances, get_app_instance_id
    except Exception:
        return ""
    me = ""
    try:
        me = get_app_instance_id() or ""
    except Exception:
        pass
    try:
        import yaml as _yaml
        from pathlib import Path
        from infrastructure.config import get_project_root
        for iid in discover_instances():
            if iid == me:
                continue
            cfg_path = get_project_root() / "apps" / iid / "config" / "app.yaml"
            if not cfg_path.is_file():
                continue
            try:
                data = _yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            # 旧/新格式都支持：messenger.app_id 或 channels.feishu.app_id
            identities = []
            messenger = data.get("messenger") or {}
            if isinstance(messenger, dict):
                aid = (messenger.get("app_id") or "").strip()
                if aid:
                    identities.append(aid)
            channels = data.get("channels")
            if isinstance(channels, dict):
                for ch_cfg in channels.values():
                    if isinstance(ch_cfg, dict):
                        aid = (ch_cfg.get("app_id") or "").strip()
                        if aid:
                            identities.append(aid)
                        bid = (ch_cfg.get("bot_id") or "").strip()
                        if bid:
                            identities.append(bid)
            for ident in identities:
                if ident and ident == sender_id:
                    return ident
    except Exception:
        return ""
    return ""


async def handle_message(*, adapter: IngressAdapter, msg: NormalizedMessage) -> bool:
    """处理一条入站消息：解析实例 → 发出事件 → 按需唤醒。

    完整流程：
      1. resolve_instance() 确定消息归属的数字生命实例
      2. 编排前置检查（orchestration preflight），命中则直接回复跳过
      3. 设置实例上下文（set_instance_context + 环境变量）
      4. _route_to_life() → 发出 message/group_message 事件
      5. BLOCKED/PENDING → 后台线程直接唤醒（不等 cron tick）
      6. RUNNING → 立即注入到运行中会话内存队列（不等 cron tick）
    """
    from application.ingress.router import resolve_instance

    instance_id = resolve_instance(msg)
    logger.info("Ingress message: platform=%s chat=%s -> instance=%s", msg.platform, msg.chat_id[:20], instance_id)

    # 黑名单拦截：sender_id 在黑名单中 → 直接丢弃，不 emit 事件、不唤醒
    if msg.sender_id:
        try:
            from domain.contacts import is_blocked, get_or_create_stub
            # platform 直接用 msg.platform（wechat/feishu/...）
            platform = msg.platform
            # 先查黑名单（若已 blocked 直接 drop，不消耗资源创建 stub）
            if is_blocked(platform, msg.sender_id):
                logger.info(
                    "Ingress drop: sender %s on %s is in blocklist",
                    msg.sender_id[:16], platform,
                )
                return False
            # 未知 sender 自动注册 stub 联系人（name 空，notes=auto-registered stub）
            # 前端可将其与现有联系人合并（编辑时把 platform_id 加到 named contact 上，
            # update_contact 会自动删除该 stub）。
            # 飞书 sender_type=='app' → 这是机器人（兄弟实例或第三方 bot），
            # 标记 kind='bot'，发送侧据此判断"@ 到了机器人→飞书会送达→本侧不再广播"。
            get_or_create_stub(platform, msg.sender_id, kind="bot" if msg.sender_is_bot else "human")
        except Exception:
            pass

    text = msg.content

    # ── Ignore Feishu's WS echo of sibling-bot messages ──
    # Two digital-life instances in the same Feishu group have POSIX
    # visibility into each other through two channels:
    #   1) Feishu's own WS fan-out (Feishu server delivers every bot's posts
    #      to every other bot in the chat) — purely reactive, no semantic
    #      context.
    #   2) The cross-instance aggregate DB at ``var/conversations/chats.db``
    #      + fan-out ``emit_event`` into the sibling's events table — the
    #      canonical channel by which one sibling perceives the other.
    # Channel (1) creates echo loops once the bots start replying. Channel
    # (2) is the right path; the message already lands in the sibling's
    # events queue via ``_fan_out_to_other_instances`` and triggers a wake
    # through the scheduler naturally.
    #
    # So when this handler sees a sibling sender on the WS-ingress side, we
    # ignore it completely (no chat aggregate write, no event emission, no
    # wake). The router-side wake will happen on the next cron tick or via
    # the BLOCKED→wake direct dispatch path.
    sibling_app_id = _sender_is_sibling_bot(msg.sender_id, msg.platform)
    if sibling_app_id:
        logger.info(
            "Ingress ignore (sibling WS echo): app_id=%s — handled via shared chats.db",
            sibling_app_id[:16],
        )
        return True

    # 三态收条-态 1: 入站已收到 → 加 ✅ 表情。
    # batch 合并时:merged_texts 里每条消息都加 ✅。
    # 后续 mark_processing 切 🤔,express_to_human 发送后全部撤。
    if not getattr(msg, "sender_is_bot", False):
        try:
            from application.ingress.reaction_state import register_received
            # 最新一条
            if msg.message_id:
                await register_received(msg.message_id, adapter)
            # batch 内其他条(marged_texts 带 msg_id)
            for item in (getattr(msg, "merged_texts", None) or []):
                mid = item.get("msg_id") if isinstance(item, dict) else ""
                if mid and mid != msg.message_id:
                    await register_received(mid, adapter)
        except Exception as _re:
            logger.debug("register_received failed: %s", _re)

    # Orchestration preflight
    orchestration_reply = _build_orchestration_reply(text)
    if orchestration_reply:
        await adapter.send(msg.chat_id, orchestration_reply, reply_to=msg.message_id)
        return True

    if text:
        prev_id = os.environ.get("DIGITAL_LIFE_INSTANCE_ID")
        os.environ["DIGITAL_LIFE_INSTANCE_ID"] = instance_id
        # Set instance context so events are written to the correct channel
        # (instance:{uuid}) — without this, events land in instance:zero.
        from domain.lifecycle.events import set_instance_context, reset_instance_context
        from infrastructure.config import set_current_instance_id, reset_current_instance_id
        ctx_token = set_instance_context(instance_id)
        config_token = set_current_instance_id(instance_id)
        try:
            await asyncio.to_thread(
                _route_to_life,
                text,
                instance_id=instance_id,
                is_group=msg.is_group,
                sender_name=msg.sender_name,
                sender_id=msg.sender_id,
                chat_name=msg.chat_name,
                chat_id=msg.chat_id,
                mentions_bot=msg.mentions_bot,
                mention_names=getattr(msg, "mention_names", []) or [],
                mention_map=getattr(msg, "mention_map", []) or [],
                msg_id=getattr(msg, "message_id", "") or "",
                # app_identity：从 adapter 自己拿（"平台知识唯一家园" = Adapter）。
                # 接第二个平台时只需该平台 adapter 实现 app_identity，这里零改动。
                app_id=getattr(adapter, "app_identity", "") or "",
                # 多通道：把 platform + ClawBot context_token 穿透到 express_to_human
                platform=msg.platform,
                ctx_token=getattr(msg, "context_token", "") or "",
                merged_texts=getattr(msg, "merged_texts", None) or None,
                adapter=adapter,
            )
        finally:
            reset_current_instance_id(config_token)
            reset_instance_context(ctx_token)
            if prev_id:
                os.environ["DIGITAL_LIFE_INSTANCE_ID"] = prev_id
    return True


def _build_orchestration_reply(text: str) -> str | None:
    """编排前置检查：如果消息匹配编排规则，直接返回预置回复，跳过事件注入。"""
    try:
        from domain.orchestration import plan_gateway_reply

        reply = plan_gateway_reply(text)
        return reply.text if reply else None
    except Exception as exc:
        logger.debug("Orchestration preflight skipped: %s", exc)
        return None


def _route_to_life(
    text: str,
    *,
    instance_id: str = "",
    is_group: bool = False,
    sender_name: str = "",
    sender_id: str = "",
    chat_name: str = "",
    chat_id: str = "",
    mentions_bot: bool = False,
    mention_names: list = None,
    mention_map: list = None,
    msg_id: str = "",
    app_id: str = "",
    platform: str = "feishu",
    ctx_token: str = "",
    merged_texts: list = None,
    adapter=None,
) -> None:
    """消息路由核心——发出事件并根据 affair 状态决定唤醒策略。

    三路分发：
      1. 发出 message/group_message 事件（_emit_l4_human_event）
      2. BLOCKED/PENDING → 立即后台线程唤醒（用户消息应立刻响应）
      3. RUNNING → 注入内存队列（_inject_msg_to_running_session，不等 cron tick）

    入站任何真人/群消息都意味着该实例上一轮发送已被看见——但仅限**同通道**。
    跨通道不要误取消（之前的 BUG：群 A 在等回复，群 B 来了无关消息 → 全局取消 →
    群 A 的 awaiting_reply 也被清掉，等不到 5min 自动 wake 的提醒）。

    修法（2026-06-16）：合成入站 channel 字符串（lark:<group|dm>:<chat_id>），
    调 cancel_alarms_by_filter 精确按通道取消。
    """
    try:
        from domain.lifecycle.alarms import cancel_alarms_by_filter

        # 1) 合成入站 channel 字符串（前缀按平台）
        inbound_channel = None
        if chat_id:
            kind = "group" if is_group else "dm"
            _prefix = "lark" if platform == "feishu" else platform  # wechat → wechat, feishu → lark
            inbound_channel = f"{_prefix}:{kind}:{chat_id}"

        # 2) 按通道精确取消
        #    无 chat_id 时 fallback 全局取消（兜底，理论上不该发生）
        if inbound_channel:
            n = cancel_alarms_by_filter(
                "awaiting_reply",
                payload_filter={"channel": inbound_channel},
            )
        else:
            n = cancel_alarms_by_filter("awaiting_reply")
        if n > 0:
            logger.info("Inbound cancelled %d awaiting_reply alarm(s) on channel=%s",
                        n, inbound_channel or "(all)")
    except Exception:
        logger.exception("Failed to cancel awaiting_reply on inbound")

    event_id = _emit_l4_human_event(
        text,
        is_group=is_group,
        sender_name=sender_name,
        sender_id=sender_id,
        chat_name=chat_name,
        chat_id=chat_id,
        mentions_bot=mentions_bot,
        mention_names=mention_names,
        mention_map=mention_map,
        msg_id=msg_id,
        app_id=app_id,
        platform=platform,
        merged_texts=merged_texts,
        adapter=adapter,
    )

    try:
        from interfaces.tools.action_tools import (
            set_dm_reply_context,
            set_group_reply_context,
        )

        # 不论是否 mid-session injection，每条消息都要更新 reply context：
        if chat_id:
            if is_group:
                set_group_reply_context(chat_id)
                set_dm_reply_context("")
                import interfaces.tools.action_tools as _at
                _at._DM_REPLY_CHAT_ID = None
            else:
                set_dm_reply_context(chat_id)
                set_group_reply_context("")
                import interfaces.tools.action_tools as _at
                _at._GROUP_REPLY_CHAT_ID = None

            # 多通道：存 platform + context_token 到 runtime_context（全链路可见）
            # 这是 ClawBot 发回复的必要条件
            try:
                from domain.lifecycle.runtime_context import (
                    set_current_event_platform,
                    set_current_context_token,
                    set_current_reply_msg_id,
                )
                set_current_event_platform(platform)
                set_current_context_token(ctx_token or "")
                # 三态收条:记录当前 wake 的入站原消息 id,供 express_to_human 发送后撤 ⚙️
                set_current_reply_msg_id(msg_id or "")
            except Exception:
                pass

            # 同时存 _REPLY_CONTEXT（为 express_to_human fallback 用）
            try:
                import interfaces.tools.action_tools as _at2
                # 用固定的 instance_id 作为 key + 设全局 mirror
                _at2._set_current_instance_id_mirror(instance_id)
                _iid = instance_id
                if _iid:
                    _ctx = _at2._REPLY_CONTEXT.get(_iid) or {}
                    _ctx["platform"] = platform
                    _ctx["chat_id"] = chat_id
                    _ctx["is_group"] = is_group
                    _ctx["wechat_context_token"] = ctx_token or ""
                    _at2._REPLY_CONTEXT[_iid] = _ctx
            except Exception:
                pass
        # scheduler 的 reply-context 设置只在 BLOCKED→wake 路径触发，
        # mid-session injection 时 scheduler 不再调用，会留下上轮 wake 的 stale context。
        # 这里根据当前消息类型把 group/dm 互相清干净 + 同步 wake_reason。
        if chat_id:
            if is_group:
                set_group_reply_context(chat_id)
                set_dm_reply_context("")  # 清 DM 污染
                import interfaces.tools.action_tools as _at
                _at._DM_REPLY_CHAT_ID = None
            else:
                set_dm_reply_context(chat_id)
                set_group_reply_context("")  # 清 group 污染
                import interfaces.tools.action_tools as _at
                _at._GROUP_REPLY_CHAT_ID = None

        # 同步 wake_reason：让 express_to_human 的 is_group_wake 判断看到最新消息类型，
        # 而不是 session 启动时的 wake 类型（避免 DM 在群聊 session 中响应到群）
        try:
            from domain.lifecycle.runtime_context import set_current_wake_reason
            set_current_wake_reason("group_message" if is_group else "message")
        except Exception:
            pass
    except Exception:
        pass

    try:
        from domain.lifecycle.affairs.runtime import get_affair
        from domain.orchestration.lifecycle_orchestration.bootstrap.runtime import _find_life_affair, ensure_life_affair
        from domain.lifecycle.scheduler import wake_digital_life

        affair_id = _find_life_affair()
        if not affair_id:
            affair_id = ensure_life_affair()
            logger.info("Auto-created life affair: %s", affair_id)

        affair = get_affair(affair_id)
        if affair and affair.status in ("BLOCKED", "PENDING"):
            # 群消息 urgency 分流:soft 消息不立即触发 wake,让其进 30s 累积窗口
            # (由 emit_event 内的 _apply_debounce 合并),下个 cron tick 自然触发。
            # immediate 消息(@我 / 含 attention_keywords / owner 发言)走现有立即 wake。
            # 私聊(message)永远 immediate,不分流。
            if is_group:
                urgency = _classify_group_urgency(text, mentions_bot, sender_name)
                if urgency == "soft":
                    logger.info("L4 group soft: deferred to 30s batch (sender=%s chat=%s)", sender_name, chat_id[:16] if chat_id else "?")
                    return  # 不立即 wake,事件已入 events 表,debounce 会合并,cron 到期触发
            # Pass the freshly emitted event directly so build_wake_prompt uses
            # it instead of re-querying (which would catch stale unconsumed events).
            if event_id > 0:
                kind = "group_message" if is_group else "message"
                from domain.lifecycle.event_registry import get_event_type
                ev_type = get_event_type(kind)
                # group_message mention 信息要传给 pending_ev，否则 wake prompt 的
                # {mention_names} {mention_map} 模板渲染为空（即使 DB payload 完整）
                _mention_names_str = "、".join(mention_names) if mention_names else ""
                _mention_map_str = "、".join(mention_map) if mention_map else ""
                pending_ev = {
                    "event_id": event_id,
                    "kind": kind,
                    "display_name": ev_type.display_name if ev_type else kind,
                    "description": ev_type.description if ev_type else "",
                    "payload": {
                        "text": text,
                        "sender_name": sender_name,
                        "sender_id": sender_id,
                        "chat_name": chat_name,
                        "chat_id": chat_id,
                        "mentions_bot": mentions_bot,
                        "mention_names": _mention_names_str,
                        "mention_map": _mention_map_str,
                    },
                }
                wake_args = (affair_id, kind, "", [pending_ev])
            else:
                wake_args = (affair_id, "message")
            thread = threading.Thread(
                target=wake_digital_life,
                args=wake_args,
                daemon=True,
            )
            thread.start()
            logger.info("L4 direct wake triggered for affair %s", affair_id)
        elif affair and affair.status == "RUNNING":
            # Immediately inject the new event into the running session
            # so the model sees it without waiting for the next cron tick.
            # 同样:群消息 soft 不打断当前 wake(不然 alpha 广播每条都打断 zero 思路)
            if is_group:
                urgency = _classify_group_urgency(text, mentions_bot, sender_name)
                if urgency == "soft":
                    logger.info("L4 group soft on RUNNING: deferred (sender=%s chat=%s)", sender_name, chat_id[:16] if chat_id else "?")
                    return
            _inject_msg_to_running_session(
                event_id=event_id,
                text=text,
                instance_id=instance_id,
                is_group=is_group,
                sender_name=sender_name,
                chat_name=chat_name,
                mentions_bot=mentions_bot,
            )
    except Exception as exc:
        logger.warning("L4 direct wake failed: %s", exc)


def _inject_msg_to_running_session(
    *,
    event_id: int,
    text: str,
    instance_id: str = "",
    is_group: bool = False,
    sender_name: str = "",
    chat_name: str = "",
    mentions_bot: bool = False,
) -> None:
    """立即将新消息事件注入到运行中会话的内存队列。

    避免等待下一次 cron tick（最多 60s），否则短时间内的连续消息会被遗漏。
    通过 session_events.signal_new_events() 写入内存队列，
    check_before_send 拦截器会在模型下次调 express_to_human 时检测到。

    同时持久化到当前 session 的 messages 表（role=user），让前端 sessions 列表
    能看到这条 mid-session 注入的事件，避免对话历史缺失。
    """
    try:
        from domain.lifecycle.session_events import signal_new_events
        from domain.lifecycle.event_registry import get_event_type

        kind = "group_message" if is_group else "message"
        ev_type = get_event_type(kind)

        # 组装完整 wake-prompt 文本（按当前 event_types.yaml 模板格式，模型 cross-wake 看到一致）
        # 简化：直接拼核心字段
        wf = (
            f"## ── ↓ 当下事件 ↓ ──\n\n"
            f"### 唤醒原因\n\n"
            f"💬 {'群聊有新消息' if is_group else '新消息'}。\n"
            + (f"{sender_name}：{text}\n" if is_group else f"{sender_name}：{text}\n")
            + f"\n如需回应，必须用 `express_to_human` 工具发送。\n"
            + f"── /当下事件 ──"
        )

        # 持久化为 user message（manager 线程不知道 session_id，需自己查最新的 running session）
        try:
            from infrastructure.ai.session_db import SessionDB
            from infrastructure.config import get_current_session_id
            cur_sid = get_current_session_id() or ""
            if not cur_sid:
                # ContextVar 未传过来（handler 线程场景），查最近未结束的 session
                import sqlite3
                from infrastructure.config import get_runtime_state_db_path
                sdb_path = get_runtime_state_db_path()
                if sdb_path.exists():
                    conn = sqlite3.connect(str(sdb_path))
                    try:
                        row = conn.execute(
                            "SELECT id FROM sessions WHERE ended_at IS NULL "
                            "ORDER BY started_at DESC LIMIT 1"
                        ).fetchone()
                        if row:
                            cur_sid = row[0]
                    finally:
                        conn.close()
            if cur_sid:
                sdb = SessionDB()
                sdb.append_message(
                    cur_sid, "user", wf,
                    chat_id=chat_id if is_group else "",
                )

            # 同步镜像到 runtime_log.turn 表(前端 Transcript 视图的数据源)。
            # 历史 BUG: 旁路注入只写 messages 表,Transcript 渲染 turn 表
            # 看不到,但"完整详情"展开看的 messages/injections 能看到——
            # 用户感觉"消息丢了一半"。
            # 归属: 挂到当前在跑的 wake 的 turn 序列末尾(不另立占位 wake)。
            # 没有在跑的 wake 时只 log,不写孤 turn(避免幽灵 turn BUG)。
            try:
                if cur_sid:
                    _mirror_inject_to_audit_turn(
                        instance_id=instance_id,
                        text=wf,
                        chat_id=chat_id if is_group else "",
                    )
            except Exception as exc:
                logger.debug("mid-session inject audit mirror failed: %s", exc)
        except Exception as exc:
            logger.debug("mid-session inject DB persistence failed: %s", exc)

        summary = {
            "event_id": event_id,
            "kind": kind,
            "display_name": ev_type.display_name if ev_type else kind,
            "description": ev_type.description if ev_type else "",
            "payload": {
                "text": text,
                "sender_name": sender_name,
                "chat_name": chat_name,
                "mentions_bot": mentions_bot,
            },
        }
        signal_new_events([summary], instance_id=instance_id)
        logger.info(
            "L4 direct: injected %s event %d to running session", kind, event_id
        )
        # 如果 session 正在 rest/sleep（emit_wait 后变 BLOCKED），
        # mid-session 注入可能赶不上最后一轮。确保事件不会被丢：
        # session 结束后 BLOCKED 时，cron 下次 tick 会消费 unconsumed events。
        # 但为了即时性，这里也触发一次 wake_if_pending（不等 60s cron tick）。
        try:
            import threading as _th
            def _delayed_wake_check():
                import time as _time
                _time.sleep(3)  # 等 session 把 rest 处理完
                try:
                    from domain.lifecycle.affairs.runtime import get_affair
                    aff = get_affair(affair_id)
                    if aff and aff.status.value in ("BLOCKED", "PENDING"):
                        logger.info("mid-session inject: affair %s now BLOCKED, triggering wake for event %d",
                                    affair_id[:8], event_id)
                        from domain.lifecycle.scheduler import wake_digital_life
                        wake_digital_life(
                            instance_id=instance_id,
                            trigger_reason=f"{kind}:delayed_after_inject",
                            affair_id=affair_id,
                        )
                except Exception as exc:
                    logger.debug("delayed wake check failed: %s", exc)
            _th.Thread(target=_delayed_wake_check, daemon=True).start()
        except Exception:
            pass
    except Exception as exc:
        logger.debug("L4 direct: inject to running session failed: %s", exc)

def _mirror_inject_to_audit_turn(*, instance_id: str, text: str, chat_id: str = "") -> None:
    """把 mid-session 旁路注入消息镜像到 runtime_log.turn 表对应当前在跑的 wake。

    Transcript 前端组件按 wake_id 拉取 turn 列表渲染。旁路注入只写 state.db.messages
    时,Transcript 看不到——但 chat_stream injection 拉到了 messages.db,所以
    "完整详情"看得到。两套数据源不一致导致用户感觉"消息丢了一半"。

    本函数补一份 turn 表写入,让 Transcript 在当前在跑 wake 的序列末尾看到这条消息。

    边界处理:
      - 没有在跑的 wake(affair 刚好转 BLOCKED 的几毫秒空隙)→ 只 log,不写孤 turn
      - 多实例隔离:按 instance_id 查 wake 表,确保不会写错别人实例的 wake
      - llm_call_seq / position_in_call 取该 wake 已有 turn 的最大值 +1:
        语义上"在上一个 LLM call 之间插入了一条 user 输入"
        (而非开启新的 LLM call,所以 llm_call_seq 不递增)
    """
    if not instance_id:
        return
    try:
        from infrastructure.persistence.instance import get_audit
        audit = get_audit(instance_id)
    except Exception:
        return

    try:
        # 找当前实例最近的未结束 wake 且仍在时间窗内(避免僵尸 wake 污染:
        # 进程被 SIGTERM 杀掉后,某些 wake.end_at 没写,长期 NULL 留在表里)
        row = audit.fetchone(
            "SELECT id, wake_seq FROM wake "
            "WHERE instance_id = ? AND ended_at IS NULL "
            "AND started_at >= ? "
            "ORDER BY started_at DESC LIMIT 1",
            (instance_id, time.time() - 3600),
        )
        if not row:
            # 当前没有在跑的 wake —— 不写孤 turn 避免幽灵数据
            logger.debug(
                "mid-session inject: no active wake for %s, skip turn mirror",
                instance_id[:8],
            )
            return

        wake_id = row.get("id") or row["wake_seq"]
        wake_seq = row["wake_seq"]

        # 找该 wake 现有 turn 的最后一行,继承 llm_call_seq
        last = audit.fetchone(
            "SELECT llm_call_seq AS c, position_in_call AS p "
            "FROM turn WHERE wake_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (wake_id,),
        )
        last_call = (last or {}).get("c") or 0
        last_pos = (last or {}).get("p") or 0
        # position_in_call +1 表示插入到当前 call 的最新 tool 之后。
        # 不递增 llm_call_seq(不属于新 LLM call,只是 mid-call 的 user 输入)
        audit.append_turn(
            wake_id=wake_id,
            wake_seq=wake_seq,
            llm_call_seq=last_call,
            position_in_call=last_pos + 1,
            role="user",
            content=text,
            chat_id=chat_id or None,
        )
        logger.debug(
            "mid-session inject mirrored to turn (wake=%s/%s call=%s pos=%s)",
            wake_id, wake_seq, last_call, last_pos + 1,
        )
    except Exception as exc:
        logger.debug("mid-session inject audit mirror failed: %s", exc)



_GROUP_CHAT_CONFIG_CACHE: dict[str, dict] = {}
_GROUP_CHAT_CONFIG_MTIME: dict[str, float] = {}


def _load_group_chat_config() -> dict:
    """从当前实例的 app.yaml 读 group_chat 配置(attention_keywords / owner_names)。
    缓存按文件 mtime 失效,避免每次入站消息都打开 yaml。
    """
    try:
        from infrastructure.config import get_instance_app_config_path, get_app_instance_id
        instance_id = get_app_instance_id() or ""
        cfg_path = get_instance_app_config_path(instance_id)
        if not cfg_path.exists():
            return {}
        mtime = cfg_path.stat().st_mtime
        if instance_id in _GROUP_CHAT_CONFIG_CACHE and _GROUP_CHAT_CONFIG_MTIME.get(instance_id) == mtime:
            return _GROUP_CHAT_CONFIG_CACHE[instance_id]
        import yaml
        with open(cfg_path) as f:
            full = yaml.safe_load(f) or {}
        gc = full.get("group_chat") or {}
        _GROUP_CHAT_CONFIG_CACHE[instance_id] = gc
        _GROUP_CHAT_CONFIG_MTIME[instance_id] = mtime
        return gc
    except Exception as exc:
        # 历史 BUG: 之前吞错静默 return {}，导致 _classify_group_urgency
        # 永远拿不到 owner_names / attention_keywords，所有非 @ 群消息
        # 全部被判 soft 不立即 wake。改成 warning 暴露根因。
        logger.warning("_load_group_chat_config failed (instance=%s): %s",
                       get_app_instance_id() if 'get_app_instance_id' in dir() else "?", exc,
                       exc_info=True)
        return {}


def _classify_group_urgency(text: str, mentions_bot: bool, sender_name: str) -> str:
    """群消息紧急度分级:immediate(立即响应) vs soft(30s 累积)。

    immediate 条件(任一命中):
      - @ 本实例(飞书 mention)
      - 正文含实例的 attention_keywords(如 zero 的 "zero/Zero/小零")
      - 发送者是 owner_names(如 zhp)
    其余(alpha 广播、其他群成员发言)→ soft,进 30s 累积窗口。
    """
    if mentions_bot:
        return "immediate"
    cfg = _load_group_chat_config()
    keywords = cfg.get("attention_keywords") or []
    if keywords and isinstance(text, str):
        for kw in keywords:
            if kw and kw in text:
                return "immediate"
    owner_names = cfg.get("owner_names") or []
    if owner_names and sender_name in owner_names:
        return "immediate"
    return "soft"


def _sender_notes(sender_id: str, sender_name: str = "") -> str:
    """查发送者备注。仅看 per-instance contacts(按 feishu open_id)。
    返回 '[发送者备注] XXX'，空则空串。

    Phase 4:删除 unified_contacts 后备路径 — 决策 3 表明 per-instance notes
    就够模型识别真人了,不再维护跨 app 同步的备注表。
    """
    if not sender_id:
        return ""
    try:
        from domain.contacts.store import _lookup_contact
        c = _lookup_contact("feishu", sender_id)
        if c:
            notes = (c.get("notes") or "").strip()
            if notes:
                return f"[发送者备注] {notes}"
    except Exception:
        pass
    return ""


def _emit_l4_human_event(
    text: str,
    *,
    is_group: bool = False,
    sender_name: str = "",
    sender_id: str = "",
    chat_name: str = "",
    chat_id: str = "",
    mentions_bot: bool = False,
    mention_names: list = None,
    mention_map: list = None,
    msg_id: str = "",
    app_id: str = "",
    platform: str = "feishu",
    merged_texts: list = None,
    adapter=None,
) -> int:
    """发出人类消息事件——消息入口的最后一步。
    流程：
      1. 解析消息内容（parse_message），提取 nurture kind（如 chat/technical）
      2. 应用精力滋养（apply_nurture），更新 vitals 表
      3. 群聊 → emit_event("group_message", channel="gateway:lark:group")
      4. 私聊 → emit_event("message", channel="gateway:lark:user")

    返回 event_id（-1 表示失败）。
    """
    # 平台前缀（source/channel 用）：feishu → lark, 其它 → platform 本身
    pf = "lark" if platform == "feishu" else platform

    # 身份统一层：sender_id 从 per-app open_id 转为跨实例稳定的 unified_id。
    # Phase 4:删除 resolve_unified_id 调用——平台视角的 open_id 自洽,永不跨实例
    # 输出(决策 3)。下游 всех消费者(events / messages.db / wake_prompt)看到的
    # sender_id 就是平台 open_id;per-instance contacts.notes 让模型识别真人是谁。
    # 旧 unified_contacts 体系是无中生有的复杂度。
    try:
        from domain.lifecycle.events import emit_event
        from domain.feedback.lifecycle_feedback.human_interaction import merge_deltas as _merge_deltas, parse_message
        from domain.vital import apply_nurture
        from domain.lifecycle.clock import now_iso

        kinds = parse_message(text) or ["chat"]
        primary_kind = kinds[0]
        deltas = _merge_deltas(kinds)

        apply_nurture(
            kind=primary_kind,
            deltas=deltas,
            raw_text=text[:500],
            source=f"gateway:{pf}",
        )

        if is_group:
            # 标注发送者岗位（如果在某个项目中）
            sender_position = ""
            try:
                from domain.project.loader import resolve_assignee_position
                pos_info = resolve_assignee_position(sender_id) if sender_id else None
                if pos_info:
                    sender_position = f"（{pos_info[0]} / {pos_info[1]}）"
            except Exception:
                pass
            # batch 历史渲染（如果 adapter 群消息 buffer 合并了多条群消息，
            # 见 interfaces/ingress/group_buffer.py，merged_texts 是 [{sender, text}]）
            _mt = merged_texts or []
            _mt_block = ""
            if _mt:
                lines = ["[近 30 秒合并群消息]"]
                for item in _mt:
                    s = (item.get("sender") if isinstance(item, dict) else "") or "?"
                    t = (item.get("text") if isinstance(item, dict) else "") or ""
                    lines.append(f"  {s}：{t}")
                _mt_block = "\n".join(lines)
            event_id = emit_event(
                kind="group_message",
                payload={
                    "text": text,
                    "sender_name": sender_name,
                    "sender_id": sender_id,
                    "sender_position": sender_position,
                    "sender_notes_block": _sender_notes(sender_id, sender_name),
                    "chat_name": chat_name,
                    "chat_id": chat_id,
                    "mentions_bot": mentions_bot,
                    "mention_names": "、".join(mention_names or []),
                    "source": f"gateway:{pf}",
                    "nurture_kinds": kinds,
                    "deltas": deltas,
                    "at": now_iso(),
                    "gateway_handled": True,
                    # batch 历史（adapter 30s + offset buffer 合并出来的,可能空）
                    "_merged_texts": _mt,
                    "_merged_texts_block": _mt_block,
                },
                channel=f"gateway:{pf}:group",
            )
            logger.info("L4 group event emitted: chat_id=%s sender=%s @=%s", chat_id, sender_name, mentions_bot)
            # 记录入站消息到 conversation_log（之前在这里 return 漏写了，导致只有 out 没有 in）
            try:
                from domain.lifecycle.conversation_log import log_conversation
                log_conversation(
                    platform=pf,
                    conversation_id=chat_id,
                    chat_type="group",
                    direction="in",
                    text=text,
                    sender_name=sender_name,
                )
            except Exception:
                pass
            # 记录到聚合库（让所有实例看到这条 in）
            # sender_id 已在函数顶部统一为 unified_id；msg_id 透传做 UNIQUE 去重。
            try:
                from domain.conversations import record_inbound_message
                record_inbound_message(
                    chat_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    text=text,
                    msg_id=msg_id,
                    sender_kind="human",
                )
            except Exception as exc:
                # 之前是 except: pass + 引用了未定义的 msg 变量，导致聚合库 5 天 0 条 human 消息。
                # 改为 warning 暴露根因，便于定位。
                logger.warning("record_inbound_message failed (chat=%s sender=%s): %s",
                               chat_id[:16], sender_name, exc, exc_info=True)
            return event_id

        event_id = emit_event(
            kind="message",
            payload={
                "text": text,
                "sender_name": sender_name,
                "sender_id": sender_id,
                "sender_notes_block": _sender_notes(sender_id, sender_name),
                "chat_id": chat_id,
                "source": f"gateway:{pf}",
                "nurture_kinds": kinds,
                "deltas": deltas,
                "at": now_iso(),
                "gateway_handled": True,
            },
            channel=f"gateway:{pf}:user",
        )
        logger.info("L4 human event emitted: nurture=%s", kinds)
        # 记录到对话日志 + 设置当前对话上下文
        try:
            from domain.lifecycle.runtime_context import set_current_conversation_id
            set_current_conversation_id(chat_id)
        except Exception:
            pass
        try:
            from domain.lifecycle.conversation_log import log_conversation
            log_conversation(
                platform=pf,
                conversation_id=chat_id,
                chat_type="group" if is_group else "dm",
                direction="in",
                text=text,
                sender_name=sender_name,
            )
        except Exception:
            pass
        return event_id
    except Exception as exc:
        logger.warning("Failed to emit l4 human event: %s", exc)
        return -1
