"""L4 生命周期钩子 — 每个 cron tick 对单个实例执行的唤醒检查。

核心流程 (_run_l4_tick_inner):
  1. 确保 DB 表存在（懒初始化可能遗漏新表）
  2. 检查是否有 wake 正在进行中 → 跳过
  3. 状态守卫：RUNNING 超 5 分钟 → 回退到 BLOCKED
  4. RUNNING 状态 → 注入新事件到运行中会话
  5. BLOCKED 状态 → 各子系统自行检查（闹钟、精力、例行任务、任务惯性）
  6. 拉取事件队列 → 按优先级确定唤醒原因 → 后台线程启动 wake_digital_life()

多实例隔离：
  - 通过 contextvars 设置实例事件上下文
  - _bg_wake 线程同时设置两个 ContextVar 系统（infrastructure + events 层）
"""

from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)


class _SkipL4(Exception):
    """跳过本次 tick 的 L4 检查信号。"""


def run_l4_tick(*, instance_id: str = "", logger: logging.Logger | None = None, adapters=None, loop=None) -> None:
    """对单个实例执行 L4 事件驱动唤醒检查。

    通过 contextvars 设置实例事件上下文，确保事件查询、session 信号、
    DB 路径都解析到正确的实例。调用方必须预先设置 os.environ["DIGITAL_LIFE_INSTANCE_ID"]。

    Args:
        instance_id: 要 tick 的数字生命实例 ID（如 "zero", "alpha"）。
    """
    log = logger or globals()["logger"]
    log.debug("L4 tick: instance=%s", instance_id)

    # Set per-instance event context (thread-safe via contextvars)
    from domain.lifecycle.events import set_instance_context, reset_instance_context
    token = set_instance_context(instance_id or os.environ.get("DIGITAL_LIFE_INSTANCE_ID", "zero"))

    try:
        _run_l4_tick_inner(instance_id, log)
    finally:
        reset_instance_context(token)


def _run_l4_tick_inner(instance_id: str, log) -> None:
    """单实例 L4 tick 核心逻辑。

    状态机流转：
      RUNNING 超时（>5min）→ 回退 BLOCKED + 定时重试
      RUNNING 正常 → 注入新事件到会话 + 返回
      BLOCKED → 各子系统检查（闹钟/精力/例行/惯性）→ 拉取事件 → 后台唤醒

    唤醒原因按事件优先级（priority）确定，取最高优先级事件的 kind。
    wake_digital_life() 在独立线程中执行，避免阻塞 cron 循环。
    """
    try:
        from domain.lifecycle.affairs.runtime import init_db
        init_db()
    except Exception:
        pass

    try:
        from domain.orchestration.lifecycle_orchestration.bootstrap.runtime import _find_life_affair
        from domain.lifecycle.affairs.runtime import (
            init_db,
            get_affair,
            update_affair,
        )
        from domain.lifecycle.state_machine import AffairStatus, WaitType
        from domain.lifecycle.clock import now_dt, parse_iso

        life_aid = _find_life_affair()
        if not life_aid:
            return

        try:
            from domain.lifecycle.scheduler import _is_wake_in_progress

            if _is_wake_in_progress(instance_id):
                log.debug("L4: wake in progress for %s - skipping tick", instance_id)
                raise _SkipL4()
        except ImportError:
            pass
        except _SkipL4:
            raise

        # ── State guard ────────────────────────────────────────────────────────

        aff = get_affair(life_aid)
        if aff and aff.status == AffairStatus.RUNNING.value:
            try:
                updated = parse_iso(aff.updated_at)
                stale_seconds = (now_dt() - updated).total_seconds()
                if stale_seconds > 300:
                    log.warning("L4: affair RUNNING for >%.0fmin - rolling back", stale_seconds / 60)
                    from datetime import timedelta

                    from domain.lifecycle.affairs.runtime import WaitIntent, set_wait_intent

                    update_affair(life_aid, status=AffairStatus.BLOCKED)
                    retry_at = (now_dt() + timedelta(minutes=2)).isoformat(timespec="seconds")
                    set_wait_intent(
                        life_aid,
                        WaitIntent(
                            wait_type=WaitType.UNTIL,
                            resume_when=retry_at,
                            reason="stale_running_rollback",
                            resume_action="",
                            meta={},
                        ),
                    )
                    # 不再 set_alarm('stale_running_rollback')。
                    # 设计文档 5.5 / 22.1：闹钟只管「到没到点」，事件队列只管
                    # 「有没有待处理」。affair 已回 BLOCKED，下一轮 cron tick（60s）
                    # 会自然重扫事件队列；若上一轮 wake 真的崩了，它的失败分支自己
                    # 会用 delay_pending_events 把 pending events 带退避推到未来，
                    # 不需要这里额外再喊一次闹钟。

                    # 收尾 session：写 ended_at + 内存 _last_session_end
                    # 让下一次 wake 在 15min 内能命中 continuation
                    try:
                        from domain.lifecycle.scheduler import _last_session_end
                        from domain.lifecycle.clock import now_dt as _now_dt
                        # session_id 可能在 affair.meta_json 里 or scheduler 内部
                        # 安全做法：从 SessionDB 查最近未结束的 session
                        from infrastructure.ai.session_db import SessionDB
                        sdb = SessionDB()
                        row = sdb._conn.execute(
                            "SELECT id FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
                        ).fetchone()
                        if row:
                            sdb.end_session(row["id"], "stale_running_rollback")
                            _last_session_end[instance_id or ""] = {
                                "session_id": row["id"],
                                "at": _now_dt(),
                            }
                            log.info("L4: stale rollback closed session %s", row["id"])
                    except Exception as exc:
                        log.debug("stale rollback session close failed: %s", exc)
            except Exception as exc:
                log.debug("RUNNING timeout check failed: %s", exc)

        if aff and aff.status == AffairStatus.RUNNING.value:
            # mid-session 注入已经在 emit_event 内 inline 完成（_signal_event_to_running_session），
            # 不再在这里单独 _inject_events——所有事件来源（人/bot/alarm）经过 emit 都会
            # 立即让 RUNNING 实例的信号队列看到。这里的职责只剩下"stale 检测"，已在上文完成。
            return

        if not aff or aff.status != AffairStatus.BLOCKED.value:
            return

        # ── BLOCKED: 各子系统自行检查 → 推事件到队列 ──────────────────────────

        try:
            from domain.lifecycle.alarms import fire_due_alarms
            fired = fire_due_alarms()
            if fired:
                log.debug("L4: %d alarms fired", len(fired))
        except Exception as exc:
            log.debug("L4: alarm fire failed: %s", exc)

        try:
            from domain.vital.simulation import get_engine, reset_engine
            reset_engine()
            get_engine().tick()
        except Exception:
            pass

        try:
            from domain.lifecycle.routine_scheduler import ensure_routine_events
            ensure_routine_events()
        except Exception:
            pass

        # 任务惯性：任务系统自己判断是否推 task_momentum 事件
        try:
            from domain.todos import check_task_momentum
            momentum = check_task_momentum()
            if momentum:
                from domain.lifecycle.events import emit_event
                emit_event(kind="task_momentum", payload=momentum)
                log.info("L4: task_momentum event emitted")
        except Exception as exc:
            log.debug("L4: task_momentum check failed: %s", exc)

        # ── 拉取事件队列 ─────────────────────────────────────────────────────

        from domain.lifecycle.events import pop_due_events
        from domain.lifecycle.event_registry import get_event_type

        events = pop_due_events(limit=50)
        if not events:
            log.debug("L4: no due events — sleeping")
            return

        # All events are equal — no special filtering. Let the trigger chain
        # and wake prompt decide how to present them.

        # ── 确定唤醒原因 ───────────────────────────────────────────────────────
        # 同优先级 ties 的 tie-break：内容类事件优先（routine > message/group_message >
        # awaiting_reply > timer > initiative > 其它）。否则会出现下面这种 BUG：
        # 08:00 北京 morning_plan(routine) + timer 同时到期，pop_due_events 按 event_id
        # ASC 返回 → events=[routine, timer]，严格 > 让 timer 赢 → wake reason = timer，
        # build_wake_prompt 走 timer 模板而非 routine 的 prompt_template → morning_plan
        # 的 "skill_view daily_planner" 等深度思考 skill 永远不注入。
        # tie-break 表里的顺序就是"同优先级时哪种应该赢"。
        _REASON_TIEBREAK = {
            "routine": 0,
            "group_message": 1,
            "message": 2,
            "awaiting_reply": 3,
            "timer": 4,
            "initiative": 5,
        }

        reason = "unknown"
        top_priority = -1
        top_tiebreak = 10 ** 9
        for ev in events:
            kind = ev.get("kind", "")
            try:
                td = get_event_type(kind)
                pri = td.priority if td else 5
            except Exception:
                pri = 5
            tb = _REASON_TIEBREAK.get(kind, 100)
            if pri > top_priority or (pri == top_priority and tb < top_tiebreak):
                top_priority = pri
                top_tiebreak = tb
                reason = kind

        log.info("L4: waking — reason=%s pri=%d events=%d", reason, top_priority, len(events))

        # ── Token 预算闸门（基础设施级硬保护）─────────────────────────────
        # 不管事件优先级高低、精力是否充分，"这个小时/今日还能烧 token 么"
        # 由 budget_gate 决定。超阈值时拒绝 wake，把当前事件推到下个窗口
        # （delay_pending_events 复用现有退避路径，不发 retry alarm）。
        # **真人消息（message/group_message）+ 出生事件穿透闸门**，确保用户
        # 主动 @ 时永远能叫醒。
        # 设计依据（详见 docs/design 二十三章）：06-14 一夜 ~130MB 日志 +
        # GLM 配额爆掉死循环，根因是缺乏"还能不能烧"的基础设施级闸门。
        try:
            from infrastructure.budget import should_allow_wake
            from domain.lifecycle.events import delay_pending_events
            allowed, _gate_reason, _state = should_allow_wake(reason, instance_id or "")
            if not allowed:
                log.warning(
                    "L4: budget gate refusing wake for %s — events pushed to next window; "
                    "high-priority (message/group_message/birth) bypasses",
                    instance_id or "<?>",
                )
                # 复用事件自退避：把整批 events 推到 +5 分钟（保守 short backoff，
                # 比方说下个 cron tick 又看到的概率小）。token 窗口重置时自然恢复。
                try:
                    delay_pending_events(events, base=5.0, cap=5.0)
                except Exception as exc:
                    log.debug("budget-gate delay failed: %s", exc)
                return
        except Exception as exc:
            log.debug("budget gate check failed (let through): %s", exc)

        # ── Dispatch ──────────────────────────────────────────────────────────

        try:
            from domain.lifecycle.scheduler import wake_digital_life

            _captured_instance_id = instance_id

            def _bg_wake() -> None:
                if _captured_instance_id:
                    os.environ["DIGITAL_LIFE_INSTANCE_ID"] = _captured_instance_id
                    try:
                        from infrastructure.config import set_current_instance_id
                        set_current_instance_id(_captured_instance_id)
                    except Exception:
                        pass
                    try:
                        from domain.lifecycle.events import set_instance_context
                        set_instance_context(_captured_instance_id)
                    except Exception:
                        pass
                try:
                    wake_digital_life(life_aid, reason, extra="", pending_events=events)
                except Exception as exc:
                    log.warning("L4 background wake_digital_life error: %s", exc)

            thread = threading.Thread(target=_bg_wake, daemon=True)
            thread.start()
            log.info("L4: wake_digital_life dispatched (instance=%s, reason=%s)", instance_id, reason)
        except Exception as exc:
            log.warning("L4 wake_digital_life dispatch failed: %s", exc)

    except _SkipL4:
        return
    except Exception as exc:
        log.warning("L4 event check failed: %s", exc)
