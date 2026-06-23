"""Project deliverables CRUD, operating on todos.db."""

from __future__ import annotations

import logging
import secrets
from typing import Optional

from infrastructure.persistence import sqlite

logger = logging.getLogger("digital_life.domain.project")

DELIVERABLE_UPDATE_COLUMNS = {
    "title",
    "description",
    "status",
    "priority",
    "assignee_instance",
    "assignee_position",
}

PROJECT_TODO_UPDATE_COLUMNS = {
    "parent_todo_id",
    "title",
    "description",
    "status",
    "priority",
    "assignee_instance",
    "assignee_kind",
    "type",
    "linked_deliverable_id",
    "sort_order",
}
# 向后兼容（外部老 caller 引用 PROJECT_TASK_UPDATE_COLUMNS 仍能 import）
PROJECT_TASK_UPDATE_COLUMNS = PROJECT_TODO_UPDATE_COLUMNS


def _new_id() -> str:
    return secrets.token_hex(4)


def _now_iso() -> str:
    try:
        from domain.lifecycle.clock import now_iso
        return now_iso()
    except Exception:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


def create_deliverable(
    db: sqlite.Connection,
    title: str,
    description: str = "",
    priority: str = "medium",
    assignee_instance: str = "",
    assignee_position: str = "",
    *,
    project_id: str = "",
    acceptance_criteria: str = "",
) -> str:
    """创建 deliverable —— 同时同步到 global todos.db.todos。

    设计 6.5(项目：独立模块，消费待办): 项目 deliverable 必须在 global todos
    表里有一条对应 todo。todo 通过 linked_deliverable_id 反查 deliverable,
    通过 project_id 反查项目。deliverable 是项目侧的「交付物」记录(分配岗位、
    责任归属),todo 是 agent 侧的「该做的事」记录(出现在 sense_todos 看板)。

    历史 BUG(2026-06-23): create_deliverable 只写 deliverables 表,
    不同步 global todos → zero 拆 16 个 P0-T9 deliverable 后 alpha
    sense_todos 一条都看不到 → alpha 完全不知道有这些活儿等着它做。
    导致 alpha 自己手调 todo create 复制了 Phase 1(9ca7ca4a), 跟 deliverable
    a197be94 完全脱节, 两套数据。
    """
    did = _new_id()
    now = _now_iso()
    db.execute(
        """INSERT INTO deliverables (id, title, description, status, priority,
           assignee_instance, assignee_position, created_at, updated_at)
           VALUES (?, ?, ?, 'planned', ?, ?, ?, ?, ?)""",
        (did, title, description, priority, assignee_instance, assignee_position, now, now),
    )
    db.commit()

    # ⭐ 关键:同步到 global todos.db.todos(设计 6.5:项目模块消费待办)
    if project_id:
        try:
            from domain.todos.crud import create_task
            result = create_task(
                title=title,
                description=description,
                priority=priority,
                status="planned",
                source="personal",  # 旧字段向后兼容;project_id 优先识别
                linked_deliverable_id=did,
                type="development" if assignee_position == "developer" else "",
                assignee_instance=assignee_instance or None,
                project_id=project_id,
                acceptance_criteria=acceptance_criteria,
                detail="",
            )
            logger.info(
                "create_deliverable synced global todo for %s (deliverable=%s assignee=%s ok=%s)",
                project_id, did[:8], (assignee_instance or "")[:8],
                bool(result.get("ok")) if isinstance(result, dict) else "?",
            )
        except Exception as exc:
            # 同步失败不应阻断 deliverable 创建本身(主操作已 commit)。
            # 但需明显 log 让人觉察到——否则就会出现"todo 没建但没人知道"。
            logger.warning(
                "create_deliverable FAILED to sync global todo for deliverable %s "
                "(project=%s): %s",
                did[:8], project_id, exc,
            )

    return did


def list_deliverables(
    db: sqlite.Connection,
    status: Optional[str] = None,
    assignee_instance: Optional[str] = None,
) -> list[dict]:
    conditions = []
    params = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if assignee_instance:
        conditions.append("assignee_instance = ?")
        params.append(assignee_instance)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    rows = db.execute(
        f"SELECT * FROM deliverables {where} ORDER BY priority DESC, updated_at DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_deliverable(db: sqlite.Connection, deliverable_id: str) -> dict | None:
    row = db.execute(
        "SELECT * FROM deliverables WHERE id = ?", (deliverable_id,)
    ).fetchone()
    return dict(row) if row else None


def update_deliverable(db: sqlite.Connection, deliverable_id: str, **kwargs) -> bool:
    """更新 deliverable 字段。

    P0：原仅更新 DB，缺反向联动到 task。
    现在：如果 caller 传了 project_id（建议传），状态变更时反向同步对应 task 状态。
    """
    project_id = kwargs.pop("project_id", None)
    kwargs = {
        key: value
        for key, value in kwargs.items()
        if key in DELIVERABLE_UPDATE_COLUMNS and value is not None
    }
    new_status = kwargs.get("status")

    if not kwargs and not project_id:
        return False
    if kwargs:
        kwargs["updated_at"] = _now_iso()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [deliverable_id]
        sql = "UPDATE deliverables SET " + sets + " WHERE id = ?"
        db.execute(sql, vals)
        db.commit()

    # 反向联动 deliverable → task（双向对称）：
    # 仅当 caller 提供 project_id + 状态变更时触发。
    # 注意：跨实例 task 反向写需要进程能访问对应实例的 tasks.db。
    # 由于 deliverable 改变通常发生在承担者进程内（task done → deliverable done 是同进程），
    # 这里主要覆盖"规划者直接改 deliverable 状态" 的场景（任务方应当被通知取消/标完成）。
    if project_id and new_status in ("done", "in_progress", "planned"):
        try:
            _reverse_sync_task_for_deliverable(
                project_id, deliverable_id, new_status
            )
        except Exception:
            # 反向联动失败不应阻断主操作
            pass

    return True


def _reverse_sync_task_for_deliverable(
    project_id: str, deliverable_id: str, new_status: str
) -> int:
    """把 deliverable 的状态变更反向写到对应 task 表。

    Returns:
        同步成功的 task 条数（同一个 deliverable 可能被多个实例认领，因此可能多 task）。

    设计：
    - 当前调用进程应该已经设了 instance context（set_current_instance_id）。
      所以 get_db()（domain.todos._infra）会打开**当前实例**的 tasks.db。
    - 跨实例任务（即其他实例认领的 task）本进程写不了对方的 tasks.db；
      那部分任务由**对方实例 wake 之后看到 deliverable_changed 事件**触发同步，
      这是事件机制的分内事，本函数只处理本实例的 task。
    """
    source_tag = f"project:{project_id}"
    target_task_status = {
        "done": "done",
        "in_progress": "in_progress",
        "planned": "planned",
    }.get(new_status)
    if not target_task_status:
        return 0

    # 本进程的 tasks.db
    try:
        from domain.todos._infra import get_db as _get_task_db
        tdb = _get_task_db()
        try:
            rows = tdb.execute(
                "SELECT id FROM tasks WHERE source = ? AND linked_deliverable_id = ?",
                (source_tag, deliverable_id),
            ).fetchall()
            count = 0
            for row in rows:
                tid = row["id"]
                tdb.execute(
                    "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
                    (target_task_status, _now_iso(), tid),
                )
                count += 1
            if count:
                tdb.commit()
            return count
        finally:
            tdb.close()
    except Exception:
        return 0


# ──────────────────────────────── project_todos（项目级待办树） ────────────────────────────────


def create_project_todo(
    db: sqlite.Connection,
    *,
    title: str,
    description: str = "",
    parent_todo_id: str = "",
    assignee_instance: str = "",
    assignee_kind: str = "",
    type: str = "",
    linked_deliverable_id: str = "",
    priority: str = "medium",
    sort_order: int = 0,
) -> str:
    """在项目 DB 里创建一个项目级待办。返回 todo id。"""
    tid = _new_id()
    now = _now_iso()
    db.execute(
        "INSERT INTO project_todos (id, parent_todo_id, title, description, status, "
        "priority, assignee_instance, assignee_kind, type, linked_deliverable_id, "
        "sort_order, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'planned', ?, ?, ?, ?, ?, ?, ?, ?)",
        (tid, parent_todo_id, title, description, priority,
         assignee_instance, assignee_kind, type, linked_deliverable_id,
         sort_order, now, now),
    )
    db.commit()
    return tid


# 向后兼容别名（老 caller 引用 create_project_task 仍能 work）
create_project_task = create_project_todo


def list_project_todos(
    db: sqlite.Connection,
    *,
    parent_todo_id: str | None = None,
    status: str | None = None,
    assignee_instance: str | None = None,
) -> list[dict]:
    """列项目级待办，可按 parent / status / assignee 过滤。"""
    where_parts: list[str] = []
    params: list = []
    if parent_todo_id is not None:
        where_parts.append("parent_todo_id=?")
        params.append(parent_todo_id)
    if status:
        where_parts.append("status=?")
        params.append(status)
    if assignee_instance:
        where_parts.append("assignee_instance=?")
        params.append(assignee_instance)
    sql = "SELECT * FROM project_todos"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += " ORDER BY sort_order, created_at"
    rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# 向后兼容
list_project_tasks = list_project_todos


def get_project_todo(db: sqlite.Connection, todo_id: str) -> dict | None:
    row = db.execute("SELECT * FROM project_todos WHERE id=?", (todo_id,)).fetchone()
    return dict(row) if row else None


get_project_task = get_project_todo


def update_project_todo(db: sqlite.Connection, todo_id: str, **kwargs) -> bool:
    """更新项目级待办。接受 parent_todo_id / assignee_instance / status 等字段。"""
    updates = {k: v for k, v in kwargs.items() if k in PROJECT_TODO_UPDATE_COLUMNS and v is not None}
    # 也允许旧 caller 传 parent_task_id（映射到 parent_todo_id）
    legacy_parent = kwargs.get("parent_task_id")
    if legacy_parent is not None:
        updates["parent_todo_id"] = legacy_parent
    if not updates:
        return False
    updates["updated_at"] = _now_iso()
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [todo_id]
    sql = "UPDATE project_todos SET " + sets + " WHERE id = ?"
    db.execute(sql, vals)
    db.commit()
    return True


update_project_task = update_project_todo


def delete_project_todo(db: sqlite.Connection, todo_id: str) -> bool:
    """删除项目级待办（连带递归删子待办）。"""
    children = list_project_todos(db, parent_todo_id=todo_id)
    for ch in children:
        delete_project_todo(db, ch["id"])
    cur = db.execute("DELETE FROM project_todos WHERE id=?", (todo_id,))
    db.commit()
    return cur.rowcount > 0


delete_project_task = delete_project_todo


def init_project_todo_tree(db: sqlite.Connection, project_id: str, project_name: str,
                            project_description: str, manager: str) -> dict:
    """初始化项目待办树。

    创建预设结构：
      根待办：<project_name>（项目概述+目标）
        ├─ 子待办：项目分工（承担=manager, type=project_bootstrap）
        └─ 子待办：项目管理（承担= ''待分配, type=project_management）

    返回 {"root_todo_id": ..., "bootstrap_todo_id": ..., "management_todo_id": ...}
    """
    # 根待办
    root_id = create_project_todo(
        db, title=project_name,
        description=project_description,
        parent_todo_id="",
        assignee_instance=manager,
        assignee_kind="instance",
        type="project_root",
    )

    # 子待办 1: 项目分工
    bootstrap_id = create_project_todo(
        db, title="项目分工",
        description=f"分析项目「{project_name}」目标，定义岗位分工、创建执行待办",
        parent_todo_id=root_id,
        assignee_instance=manager,
        assignee_kind="instance",
        type="project_bootstrap",
        sort_order=1,
    )

    # 子待办 2: 项目管理
    management_id = create_project_todo(
        db, title="项目管理",
        description=f"管理项目「{project_name}」的节奏、进度、决议、review",
        parent_todo_id=root_id,
        assignee_instance="",
        assignee_kind="",
        type="project_management",
        sort_order=2,
    )

    return {
        "root_todo_id": root_id,
        "bootstrap_todo_id": bootstrap_id,
        "management_todo_id": management_id,
        # 向后兼容 key（老 caller 仍可读 root_task_id 等）
        "root_task_id": root_id,
        "bootstrap_task_id": bootstrap_id,
        "management_task_id": management_id,
    }


# 向后兼容
init_project_task_tree = init_project_todo_tree
