"""Project manager: CRUD for project entities."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("digital_life.domain.project")

_PROJECTS_DIR = Path(__file__).resolve().parents[2] / "projects"


def create_project(project_id: str, name: str, description: str = "", manager: str = "") -> bool:
    """Create a new project: directory + project.yaml + todos.db."""
    proj_dir = _PROJECTS_DIR / project_id
    if proj_dir.exists():
        logger.warning("Project %s already exists", project_id)
        return False

    # Create directories
    (proj_dir / "data").mkdir(parents=True, exist_ok=True)
    (proj_dir / "deliverables").mkdir(parents=True, exist_ok=True)
    (proj_dir / "knowledge" / "documents").mkdir(parents=True, exist_ok=True)

    # Write project.yaml
    import yaml
    config = {
        "project": {
            "id": project_id,
            "name": name,
            "description": description,
            "status": "active",
            "manager": manager,
            "group_chat_id": "",
        },
        "positions": [],
    }
    with open(proj_dir / "project.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # Initialize todos.db（仍需要建 deliverables 表，给项目级交付成果存处）
    from ._infra import get_project_db
    db = get_project_db(project_id)
    db.close()

    # 初始化默认待办树（写到 global_todos.db，不是项目自己的 todos.db）
    # 设计原则（2026-06-14 用户确认）：待办是独立 entity，关联项目+实例。
    # 项目创建时自动 seed 根待办 + "项目分工" 给 manager。后续项目分工可
    # 拆出更多子待办+分配给其他实例。
    try:
        from domain.todos.crud import create_task
        root_id = create_task(
            title=name,
            description=description,
            status="planned",
            source=f"project:{project_id}",
            type="project_root",
            assignee_instance=manager,
            project_id=project_id,
        )
        if not root_id.get("ok"):
            logger.warning("init root todo for %s failed: %s", project_id, root_id.get("reason"))
        else:
            root_tid = root_id["task"]["id"]
            bootstrap_id = create_task(
                title="项目分工",
                description=f"分析项目「{name}」目标，定义岗位分工、创建执行待办",
                status="planned",
                source=f"project:{project_id}",
                type="project_bootstrap",
                assignee_instance=manager,
                project_id=project_id,
            )
            management_id = create_task(
                title="项目管理",
                description=f"管理项目「{name}」的节奏、进度、决议、review",
                status="planned",
                source=f"project:{project_id}",
                type="project_management",
                assignee_instance="",
                project_id=project_id,
            )
            logger.info(
                "Initialized todo tree for %s: root=%s bootstrap=%s mgmt=%s",
                project_id, root_tid,
                bootstrap_id.get("task", {}).get("id"),
                management_id.get("task", {}).get("id"),
            )
    except Exception as exc:
        logger.warning("init_project_todo_tree failed for %s: %s", project_id, exc)

    logger.info("Created project %s (%s)", project_id, name)
    return True


def set_project_positions(project_id: str, positions: list[dict]) -> bool:
    """Write positions block to project.yaml (overwrites existing positions)."""
    yaml_path = _PROJECTS_DIR / project_id / "project.yaml"
    if not yaml_path.exists():
        return False

    import yaml
    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    raw["positions"] = positions
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return True


def create_project_full(
    project_id: str,
    name: str,
    description: str,
    manager: str,
    positions: list[dict],
    group_chat_id: str = "",
) -> bool:
    """One-shot project creation with positions, used by project_bootstrap tool."""
    if not create_project(project_id, name, description, manager):
        return False
    if group_chat_id:
        update_project_info(project_id, group_chat_id=group_chat_id)
    if positions:
        set_project_positions(project_id, positions)
    return True


def archive_project(project_id: str) -> bool:
    """Set project status to archived."""
    yaml_path = _PROJECTS_DIR / project_id / "project.yaml"
    if not yaml_path.exists():
        return False

    import yaml
    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    raw["project"]["status"] = "archived"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    logger.info("Archived project %s", project_id)
    return True


def update_project_info(project_id: str, **kwargs) -> bool:
    """Update project top-level fields in project.yaml."""
    yaml_path = _PROJECTS_DIR / project_id / "project.yaml"
    if not yaml_path.exists():
        return False

    import yaml
    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    proj = raw.setdefault("project", {})
    for key, value in kwargs.items():
        proj[key] = value

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return True
