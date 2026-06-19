"""Project portfolio snapshot — gives the model a complete view of
"who I am across all my projects", at wake time.

Aggregates per-instance data:
  - All active projects the instance is assigned to
  - Per project: position + responsibilities + goal/KPI/thesis/deadline
  - Per project: assignee's todos (personal tasks) + deliverables (project-level)
  - Per project: siblings (other instances) and their roles
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from domain.lifecycle.clock import parse_iso


def build_my_portfolio(instance_id: str | None = None) -> List[Dict[str, Any]]:
    """Return a list of project dicts the instance is part of, with full context.

    Each dict has shape:
      {
        "project_id": ...,
        "name": ...,
        "status": ...,
        "is_manager": bool,
        "my_position": "策略师" | ...,
        "responsibilities": [...],
        "goal": {...},
        "thesis": [...],
        "kpis": [...],
        "deadline": ...,
        "deadline_remaining_days": int | None,
        "personal_todos": [...],     # from instance's tasks.db WHERE source=project_id
        "project_deliverables": [...],# from projects/<pid>/data/...db WHERE assignee_instance=instance_id 鈥 OR 全部
        "siblings": [...]            # other instances in this project
      }
    """
    from domain.project.loader import load_all_projects
    from infrastructure.config import get_app_instance_id

    iid = instance_id or get_app_instance_id() or ""
    if not iid:
        return []

    out: list[dict] = []
    projects = load_all_projects() or {}
    for pid, cfg in projects.items():
        if cfg.status != "active":
            continue
        pos = cfg.get_position_for_instance(iid)
        if not pos:
            # 不在这个项目里——略过（portfolio 只含我参与的项目）
            continue

        # 拉个人 todos（tasks 表里 source=project_id 的）
        personal_todos = _load_personal_todos(iid, pid)

        # 拉项目级 deliverables assignee 是我 或 unassigned
        project_deliverables = _load_project_deliverables(pid, iid)

        # siblings：同项目其他实例
        siblings: list[dict] = []
        for ap in cfg.positions:
            for a in ap.assignees:
                if a != iid and a and not a.startswith("human:"):
                    siblings.append({
                        "instance_id": a,
                        "position": ap.name,
                        "responsibilities": list(ap.responsibilities or []),
                    })

        # deadline remaining
        deadline_remaining = None
        if cfg.goal.get("deadline"):
            try:
                dl = parse_iso(cfg.goal["deadline"])
                deadline_remaining = (dl - datetime.now(timezone.utc)).days
            except Exception:
                pass

        out.append({
            "project_id": pid,
            "name": cfg.name,
            "description": cfg.description,
            "status": cfg.status,
            "is_manager": cfg.manager == iid,
            "my_position": pos.name,
            "responsibilities": list(pos.responsibilities or []),
            "goal": dict(cfg.goal or {}),
            "thesis": list(cfg.thesis or []),
            "review_schedule": dict(cfg.review_schedule or {}),
            "kpis": list(cfg.kpis or []),
            "deadline": cfg.goal.get("deadline", ""),
            "deadline_remaining_days": deadline_remaining,
            "personal_todos": personal_todos,
            "project_deliverables": project_deliverables,
            "siblings": siblings,
        })

    return out


def _load_personal_todos(instance_id: str, project_id: str) -> list[dict]:
    """读 instance 的 tasks.db tasks 表，WHERE source=project_id"""
    try:
        from infrastructure.config import get_runtime_home
        runtime_home = get_runtime_home()
        tasks_db_path = runtime_home / "tasks" / "tasks.db"
        if not tasks_db_path.exists():
            return []
        conn = sqlite3.connect(str(tasks_db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, title, status, priority, deadline, description, updated_at "
                "FROM tasks WHERE source = ? ORDER BY status, updated_at DESC LIMIT 20",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error:
            return []
        finally:
            conn.close()
    except Exception:
        return []


def _load_project_deliverables(project_id: str, instance_id: str | None = None) -> list[dict]:
    """读项目 deliverables 表，标出我的 / 别人的 / 无主的"""
    try:
        from domain.project._infra import get_project_db
        db = get_project_db(project_id)
        try:
            # 给我相关的（assigned to me），或全部
            if instance_id:
                rows = db.execute(
                    "SELECT id, title, status, priority, assignee_instance, assignee_position, "
                    "description, updated_at FROM deliverables "
                    "WHERE assignee_instance = ? OR assignee_instance = '' OR assignee_instance IS NULL "
                    "ORDER BY "
                    "CASE status WHEN 'in_progress' THEN 0 WHEN 'planned' THEN 1 ELSE 2 END, updated_at DESC "
                    "LIMIT 25",
                    (instance_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT id, title, status, priority, assignee_instance, assignee_position, "
                    "description, updated_at FROM deliverables "
                    "ORDER BY "
                    "CASE status WHEN 'in_progress' THEN 0 WHEN 'planned' THEN 1 ELSE 2 END, updated_at DESC "
                    "LIMIT 25",
                ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["mine"] = bool((d.get("assignee_instance") or "") == instance_id)
                out.append(d)
            return out
        finally:
            db.close()
    except Exception:
        return []
