"""Schema 集中入口 — 一次性建实例需要的所有 SQLite 表。

设计目的：
  各 domain 模块原本懒加载 `CREATE TABLE IF NOT EXISTS`，散落多处，
  新实例启动时不可靠（部分表只在被调用时才建）。
  此处统一调用所有模块的 schema 初始化函数，幂等可重复调用。

调用方：
  - scripts/init_instance.py 实例初始化时
  - infrastructure/http/server.py:run_instance_gateway 进程启动时（兜底）

涉及的 DB：
  - state.db（主实例库，most tables）
  - 同一进程上下文中的 sessions.db / tasks.db（subsystems 各自管理）
  - 注意：本函数只保证 state.db 表齐全；其他 DB 由各 domain 自建
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def init_all_schemas() -> None:
    """初始化当前实例上下文（ContextVar）对应 state.db 的全量表。

    必须在 set_current_instance_id / set_instance_context 设置好之后调用。
    若 state.db 不存在，各模块会自动创建（含父目录）。
    """
    failed: list[str] = []

    # 1) affairs / wait_intents / events / heartbeats / vitals / wallet / nurture_log / timers
    try:
        from domain.lifecycle.affairs.runtime import init_db as _affairs_init
        _affairs_init()
    except Exception as exc:
        failed.append(f"affairs: {exc}")
        logger.warning("schema init affairs failed: %s", exc)

    # 2) sessions / messages（SessionDB）
    try:
        from infrastructure.ai.session_db import SessionDB
        SessionDB()  # 内部按 ContextVar 解析 path
    except Exception as exc:
        failed.append(f"sessions: {exc}")
        logger.warning("schema init sessions failed: %s", exc)

    # 3) contacts / contact_ids（含 v1→v2 自动迁移）
    try:
        from domain.contacts import ensure_schema as _contacts_schema
        _contacts_schema()
    except Exception as exc:
        failed.append(f"contacts: {exc}")
        logger.warning("schema init contacts failed: %s", exc)

    # 4) conversation_log（sense_conversation 用）
    try:
        from domain.lifecycle.conversation_log import _ensure_table
        conn = _ensure_table()
        conn.close()
    except Exception as exc:
        failed.append(f"conversation_log: {exc}")
        logger.warning("schema init conversation_log failed: %s", exc)

    # 5) flow_event_logs / flow_event_log_events
    try:
        from infrastructure.config import get_instance_state_db_path
        from infrastructure.persistence.repositories.flow_event_log import (
            SQLiteFlowEventLogRepository,
        )
        SQLiteFlowEventLogRepository(db_path=get_instance_state_db_path())
    except Exception as exc:
        failed.append(f"flow_event_log: {exc}")
        logger.warning("schema init flow_event_log failed: %s", exc)

    # 6) alert_history（员工控制台告警）
    try:
        from application.console.alerts import AlertManager
        AlertManager()
    except Exception as exc:
        failed.append(f"alerts: {exc}")
        logger.warning("schema init alerts failed: %s", exc)

    # 7) tasks.py 子系统有自己的 tasks.db（lazy 在 get_db() 中建表）
    try:
        from domain.todos._infra import get_db as _tasks_get_db
        conn = _tasks_get_db()
        conn.close()
    except Exception as exc:
        failed.append(f"tasks: {exc}")
        logger.warning("schema init tasks failed: %s", exc)

    # 8) 新版分库：runtime_log / memory / vitals / workflow
    #    （每实例 4 个 .db，Schema 在 InstanceDB.__init__ 时自动建）
    try:
        from infrastructure.persistence.instance import get_instance_bundle
        bundle = get_instance_bundle()
        # Force schema creation by touching each connection. The InstanceDB
        # base class executes SCHEMA_SQL on init, so simply resolving the
        # bundle is enough. Bundle is memoized; later callers get the same.
        _ = (bundle.audit, bundle.memory, bundle.vitals, bundle.workflow)
    except Exception as exc:
        failed.append(f"instance_db: {exc}")
        logger.warning("schema init instance_db failed: %s", exc)

    # 9) budget_log（token 用量累加，预算闸门依赖）
    #    state.db 同库附加。LLM call 完成后 record 一笔，预算闸门读小时/日累计。
    try:
        from infrastructure.budget import get_token_tracker
        get_token_tracker()  # 构造时自动幂等建表
    except Exception as exc:
        failed.append(f"budget: {exc}")
        logger.warning("schema init budget failed: %s", exc)

    if failed:
        logger.warning("init_all_schemas: %d failures: %s", len(failed), "; ".join(failed))
    else:
        logger.info("init_all_schemas: all subsystems initialized")
