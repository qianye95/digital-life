"""Project infrastructure: todos.db connection and schema.

命名对齐（用户要求 2026-06-14）：项目内所有 task 残留命名改为 todo。
表 project_tasks → project_todos；字段 parent_task_id → parent_todo_id。
脚本 ALTER old → new 做迁移，旧库自动改名继续用。
"""

from __future__ import annotations

import logging
from pathlib import Path

from infrastructure.persistence import sqlite

logger = logging.getLogger("digital_life.domain.project")


def _project_dir(project_id: str) -> Path:
    return Path(__file__).resolve().parents[2] / "projects" / project_id


def _db_path(project_id: str) -> Path:
    return _project_dir(project_id) / "data" / "todos.db"


def get_project_db(project_id: str) -> sqlite.Connection:
    """Return a connection to the project's todos.db. Auto-creates DB + tables.

    含两张表：
      deliverables — 项目级交付成果（已有，不动）
      project_todos — 项目级待办树（v5 重命名：原 project_tasks，对齐
        全局 task→todo 合并的命名约定）
    """
    db_path = _db_path(project_id)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite.connect(str(db_path))
    db.row_factory = sqlite.Row
    db.execute("PRAGMA journal_mode=WAL")
    # 先迁移老家伙（如果 project_tasks 还在，改成 project_todos + 字段重命名）
    # 必须在 CREATE TABLE IF NOT EXISTS project_todos 之前，否则_rename 会撞名
    _migrate_legacy_project_tasks(db)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS deliverables (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'planned',
            priority TEXT DEFAULT 'medium',
            assignee_instance TEXT DEFAULT '',
            assignee_position TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_deliverables_status ON deliverables(status);
        CREATE INDEX IF NOT EXISTS idx_deliverables_assignee ON deliverables(assignee_instance);

        CREATE TABLE IF NOT EXISTS project_todos (
            id TEXT PRIMARY KEY,
            parent_todo_id TEXT DEFAULT '',
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'planned',
            priority TEXT DEFAULT 'medium',
            assignee_instance TEXT DEFAULT '',
            assignee_kind TEXT DEFAULT '',
            type TEXT DEFAULT '',
            linked_deliverable_id TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_project_todos_parent ON project_todos(parent_todo_id);
        CREATE INDEX IF NOT EXISTS idx_project_todos_status ON project_todos(status);
        CREATE INDEX IF NOT EXISTS idx_project_todos_assignee ON project_todos(assignee_instance);
    """)
    return db


def _migrate_legacy_project_tasks(db: sqlite.Connection) -> None:
    """老库还叫 project_tasks / parent_task_id —— 检测到就迁移到新表名。

    必须在 CREATE TABLE IF NOT EXISTS project_todos 之前调用，否则 RENAME 会撞名。
    """
    try:
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='project_tasks'"
        ).fetchall()
        if not rows:
            return
        # 同时清理老 index（RENAME 自动重建，但旧名还在；CREATE INDEX IF NOT EXISTS
        # 在新表上会顺利建新的）
        db.executescript("""
            DROP INDEX IF EXISTS idx_project_tasks_parent;
            DROP INDEX IF EXISTS idx_project_tasks_status;
            DROP INDEX IF EXISTS idx_project_tasks_assignee;
            ALTER TABLE project_tasks RENAME TO project_todos;
            ALTER TABLE project_todos RENAME COLUMN parent_task_id TO parent_todo_id;
        """)
        logger.info("Migrated project_tasks → project_todos (column parent_task_id → parent_todo_id)")
    except Exception as exc:
        # 不致命——表可能已经在另一个 process 改过（multi-instance）
        logger.debug("project_tasks migration skipped: %s", exc)


def project_dir(project_id: str) -> Path:
    return _project_dir(project_id)


def deliverables_dir(project_id: str) -> Path:
    p = _project_dir(project_id) / "deliverables"
    p.mkdir(parents=True, exist_ok=True)
    return p
