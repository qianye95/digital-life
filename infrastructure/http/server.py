"""Gateway 服务器 — 协调所有核心服务。

两种运行模式：
  - run_master_gateway(): HTTP server + InstanceSupervisor，不连飞书、不跑 cron
  - run_instance_gateway(instance_id): 单个实例的 FeishuAdapter + Cron，不起 HTTP

旧函数 run_gateway() 仍保留作为兼容入口（= master 模式但不 spawn 子进程）。
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import threading
from typing import Optional

from aiohttp import web

logger = logging.getLogger("gateway")


def _instance_feishu_credentials(instance_id: str) -> tuple[str, str]:
    """从 apps/<id>/config/app.yaml + config/secrets.env 读 messenger 凭证。

    app_id 从 app.yaml 的 messenger.app_id 读（非敏感）。
    app_secret 从 config/secrets.env 读（敏感）——这里直接读文件，
    不依赖 load_runtime_dotenv（那个函数需要 ContextVar 已设置）。
    """
    import yaml
    from infrastructure.config import get_project_root
    root = get_project_root()
    cfg_path = root / "apps" / instance_id / "config" / "app.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    app_id = ((cfg.get("messenger") or {}).get("app_id") or "").strip()
    app_secret = ""
    secrets_path = root / "apps" / instance_id / "config" / "secrets.env"
    if secrets_path.exists():
        for line in secrets_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("FEISHU_APP_SECRET="):
                app_secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return app_id, app_secret


def _cleanup_stale_affair_on_startup(instance_id: str) -> None:
    """进程启动时清理 stale RUNNING affair。

    问题：mid-session到达的新消息事件会被 signal 到内存队列；如果进程在此之前 wake
    后 crash/重启，DB 里 affair.status=RUNNING，但内存队列丢失。stale rollback 要
    等 aff.updated_at > 300s 才触发，期间事件卡死最多 6 分钟。

    修法：process 重启时，DB RUNNING affair 必然 stale（session driver 已死）。
    立即回退 BLOCKED + 关闭 DB 中所有未关闭的 session。
    """
    from domain.lifecycle.affairs.runtime import (
        get_affair, update_affair, list_affairs, now_iso,
    )
    from domain.lifecycle.state_machine import AffairStatus
    from datetime import datetime, timezone
    try:
        from domain.orchestration.lifecycle_orchestration.bootstrap.runtime import _find_life_affair
    except Exception:
        return

    life_aid = _find_life_affair()
    if not life_aid:
        return
    aff = get_affair(life_aid)
    if not aff or aff.status != AffairStatus.RUNNING.value:
        return

    logger.warning(
        "Instance %s startup: found stale RUNNING affair %s (updated %s) — rolling back immediately",
        instance_id[:8], life_aid[:8], aff.updated_at,
    )
    update_affair(life_aid, status=AffairStatus.BLOCKED.value, updated_at=now_iso())

    # 关闭未关闭的 sessions，避免 session_events 表残留
    try:
        import sqlite3
        from infrastructure.config import get_runtime_state_db_path
        sdb_path = get_runtime_state_db_path()
        if sdb_path.exists():
            conn = sqlite3.connect(str(sdb_path))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if row:
                from infrastructure.ai.session_db import SessionDB
                sdb = SessionDB()
                sdb.end_session(row["id"], "startup_stale_rollback")
                logger.info("Startup stale rollback closed session %s", row["id"])
    except Exception as exc:
        logger.debug("Startup stale rollback session close failed: %s", exc)


# ──────────────────────────────── Instance 子进程模式 ────────────────────────────────


async def run_instance_gateway(instance_id: str) -> None:
    """跑单个实例：消息通道 adapter(s) + Cron loop。不起 HTTP。

    通过 registry 从 app.yaml 配置创建一个或多个通道 adapter（飞书/微信/钉钉...）。
    旧格式（只有 messenger 段）自动兼容为单飞书通道。
    """
    from application.ingress.handler import handle_message as ingress_handle_message
    from infrastructure.config import set_current_instance_id, get_project_root
    from domain.lifecycle.events import set_instance_context
    from interfaces.ingress.registry import create_adapters_from_config
    import yaml as _yaml

    # 读实例 app.yaml + secrets.env
    _root = get_project_root()
    cfg_path = _root / "apps" / instance_id / "config" / "app.yaml"
    secrets_path = _root / "apps" / instance_id / "config" / "secrets.env"
    app_yaml_cfg = {}
    if cfg_path.exists():
        try:
            app_yaml_cfg = _yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    secrets_env = {}
    if secrets_path.exists():
        for line in secrets_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                secrets_env[k.strip()] = v.strip().strip('"').strip("'")

    # 创建所有通道 adapter（凭证不全的通道自动跳过，不报错）
    adapters = [a for a in create_adapters_from_config(app_yaml_cfg, secrets_env) if a is not None]
    if not adapters:
        logger.info("Instance %s has no configured channels yet (all credentials empty), skipping adapter start", instance_id[:8])

    # 设置进程级 ContextVar —— 这个进程只服务于这一个实例
    os.environ["DIGITAL_LIFE_INSTANCE_ID"] = instance_id
    try:
        set_current_instance_id(instance_id)
    except Exception:
        pass
    try:
        set_instance_context(instance_id)
    except Exception:
        pass

    # 注入运行时适配器
    try:
        from application.runtime_provider import configure_runtime_provider
        configure_runtime_provider()
    except Exception as exc:
        logger.warning("configure_runtime_provider failed at instance startup: %s", exc)

    # Startup stale 清理
    try:
        _cleanup_stale_affair_on_startup(instance_id)
    except Exception as exc:
        logger.warning("Instance %s startup stale cleanup failed: %s", instance_id[:8], exc)

    # 集中初始化所有 SQLite 表
    try:
        from domain.lifecycle.schema import init_all_schemas
        init_all_schemas()
    except Exception as exc:
        logger.warning("Instance %s schema init failed: %s", instance_id[:8], exc)

    stop_event = asyncio.Event()

    def _signal_handler(sig):
        logger.info("Instance %s received signal %s", instance_id[:8], sig)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler, sig)
        except NotImplementedError:
            pass

    # 启动所有通道 adapter
    started_adapters: list[Any] = []
    for adapter in adapters:
        adapter.on_message(
            lambda msg, a=adapter: ingress_handle_message(adapter=a, msg=msg)
        )
        await adapter.start()
        started_adapters.append(adapter)
        logger.info(
            "Instance %s adapter started (platform=%s, identity=%s)",
            instance_id[:8],
            getattr(adapter, "platform", "?"),
            getattr(adapter, "app_identity", "?"),
        )

    # 热加载通道：每 30s 检查一次 secrets.env 是否有新凭证（用户在控制台改了
    # 飞书 secret / 微信扫码登录后不需要重启网关，自动发现新通道）
    import yaml as _yaml_reload
    from interfaces.ingress.registry import create_adapters_from_config as _caf

    async def _hot_reload_channels():
        from application.ingress.handler import handle_message as _hm
        reload_interval = 30
        while not stop_event.is_set():
            await asyncio.sleep(reload_interval)
            try:
                cfg_path_r = get_project_root() / "apps" / instance_id / "config" / "app.yaml"
                secrets_path_r = get_project_root() / "apps" / instance_id / "config" / "secrets.env"
                if not cfg_path_r.exists():
                    continue
                new_cfg = _yaml_reload.safe_load(cfg_path_r.read_text(encoding="utf-8")) or {}
                new_secrets: dict[str, str] = {}
                if secrets_path_r.exists():
                    for line in secrets_path_r.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            new_secrets[k.strip()] = v.strip().strip('"').strip("'")

                new_adapters = [a for a in _caf(new_cfg, new_secrets) if a is not None]
                # 找出新启动的（started_adapters 里没有的）
                existing_platforms = {getattr(a, "platform", "") for a in started_adapters}
                for new_ad in new_adapters:
                    if getattr(new_ad, "platform", "") not in existing_platforms:
                        new_ad.on_message(
                            lambda msg, a=new_ad: _hm(adapter=a, msg=msg)
                        )
                        await new_ad.start()
                        started_adapters.append(new_ad)
                        existing_platforms.add(getattr(new_ad, "platform", ""))
                        logger.info(
                            "Instance %s HOT-LOADED new adapter: platform=%s identity=%s",
                            instance_id[:8],
                            getattr(new_ad, "platform", "?"),
                            getattr(new_ad, "app_identity", "?"),
                        )
            except Exception as exc:
                logger.debug("hot reload check failed: %s", exc)

    hot_reload_task = asyncio.create_task(_hot_reload_channels())

    # 启动 Cron 循环（只 tick 当前实例）
    cron_stop = threading.Event()
    cron_thread = threading.Thread(
        target=_instance_cron_loop,
        args=(instance_id, cron_stop),
        name=f"cron-{instance_id[:8]}",
        daemon=True,
    )
    cron_thread.start()
    logger.info("Instance %s cron loop started", instance_id[:8])

    await stop_event.wait()
    logger.info("Instance %s shutting down...", instance_id[:8])

    for adapter in adapters:
        try:
            await adapter.stop()
        except Exception:
            pass
    cron_stop.set()
    cron_thread.join(timeout=5)
    logger.info("Instance %s stopped", instance_id[:8])


def _instance_cron_loop(instance_id: str, stop_event: threading.Event) -> None:
    """每个实例独立的 cron 循环。"""
    import time
    from infrastructure.config import set_current_instance_id, reset_current_instance_id
    from domain.lifecycle.events import set_instance_context, reset_instance_context
    from infrastructure.scheduler.cron_lifecycle import run_l4_tick

    interval = int(os.environ.get("L4_CRON_INTERVAL", "60"))
    logger.info("Instance %s cron loop tick interval=%ds", instance_id[:8], interval)

    while not stop_event.is_set():
        try:
            ctx1 = set_current_instance_id(instance_id)
            ctx2 = set_instance_context(instance_id)
            try:
                run_l4_tick(instance_id=instance_id)
            finally:
                reset_instance_context(ctx2)
                reset_current_instance_id(ctx1)
        except Exception as exc:
            logger.warning("Instance %s cron tick failed: %s", instance_id[:8], exc)
        # tick 间隔内分次 sleep，便于快速响应 stop
        slept = 0
        while slept < interval and not stop_event.is_set():
            time.sleep(min(5, interval - slept))
            slept += 5


# ──────────────────────────────── Master 主进程模式 ────────────────────────────────


def _ensure_default_instance() -> None:
    """首次启动自动 bootstrap 两个数字生命实例：zero（策略师）+ alpha（交易员）。

    体验：新人 clone 仓库后只需：
      1. cp config/secrets.example.env config/secrets.env
      2. 填 LLM_API_KEY + FEISHU_APP_ID/SECRET + API_SERVER_KEY
      3. digital-life start
    完全不用跑 scripts/init_instance.py —— 启动发现无实例时，自动创建两个
    示范实例（zero 和 alpha），把 secrets.env 里已填的飞书凭证写进 zero，
    alpha 留空（用户后续在控制台填飞书应用 2 的 token），跑通就在眼前。

    多次启动 / 已有实例的情况：discover_instances 返回非空就不做事（幂等）。
    """
    from infrastructure.config import discover_active_instances
    try:
        existing = discover_active_instances()
    except Exception:
        existing = []
    if existing:
        return

    logger.info("No instance registered — auto-bootstrapping default zero + alpha instances...")

    feishu_app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    feishu_app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    glm_api_key = (os.environ.get("LLM_API_KEY") or os.environ.get("GLM_API_KEY") or "").strip()

    default_instances = [
        {
            "display_name": "zero",
            "tagline": "策略师 / 架构师",
            "accent_color": "#00f0ff",
            "sort_order": 1,
            "feishu_app_id": feishu_app_id,  # 用 global secrets.env 配的第一个飞书应用
            "feishu_app_secret": feishu_app_secret,
        },
        {
            "display_name": "alpha",
            "tagline": "交易员 / 执行者",
            "accent_color": "#ff2d9c",
            "sort_order": 2,
            "feishu_app_id": "",  # alpha 用第二个飞书应用（用户后续配置）
            "feishu_app_secret": "",
        },
    ]

    bootstrapped_uuids: list[str] = []
    for cfg in default_instances:
        try:
            from infrastructure.bootstrap.instance import init_instance
            inst_dir = init_instance(
                cfg["display_name"],
                interactive=False,
                feishu_app_id=cfg["feishu_app_id"],
                feishu_app_secret=cfg["feishu_app_secret"],
                feishu_chat_ids=None,
            )
            instance_uuid = inst_dir.name
            bootstrapped_uuids.append(instance_uuid)

            # 应用 persona 元数据：tagline / accent_color / sort_order
            _patch_instance_metadata(
                instance_uuid,
                {
                    "tagline": cfg["tagline"],
                    "accent_color": cfg["accent_color"],
                    "sort_order": cfg["sort_order"],
                },
            )

            logger.info("✓ Default instance '%s' bootstrapped at %s", cfg["display_name"], inst_dir)
            if not cfg["feishu_app_id"]:
                logger.warning(
                    "  Note: no FEISHU_APP_ID for %s — bot won't connect until "
                    "you configure it in apps/%s/config/", cfg["display_name"], instance_uuid,
                )
        except Exception as exc:
            logger.warning("Auto-bootstrap of '%s' failed (continuing): %s", cfg["display_name"], exc)
            continue

    if not bootstrapped_uuids:
        return

    # 把 secrets.env 的 DIGITAL_LIFE_INSTANCE_ID 自动指向第一个实例（zero）
    cur_iid = os.environ.get("DIGITAL_LIFE_INSTANCE_ID", "").strip()
    if not cur_iid:
        first_uuid = bootstrapped_uuids[0]
        try:
            from infrastructure.config import get_global_secrets_path
            secrets_path = get_global_secrets_path()
            if secrets_path.exists():
                content = secrets_path.read_text(encoding="utf-8")
                import re as _re
                updated = _re.sub(
                    r"(?m)^DIGITAL_LIFE_INSTANCE_ID=.*\n",
                    f"DIGITAL_LIFE_INSTANCE_ID={first_uuid}\n",
                    content,
                )
                updated = _re.sub(
                    r"(?m)^DIGITAL_LIFE_DISPLAY_NAME=.*\n",
                    "DIGITAL_LIFE_DISPLAY_NAME=zero\n",
                    updated,
                )
                secrets_path.write_text(updated, encoding="utf-8")
                os.environ["DIGITAL_LIFE_INSTANCE_ID"] = first_uuid
                os.environ["DIGITAL_LIFE_DISPLAY_NAME"] = "zero"
                logger.info("Auto-filled DIGITAL_LIFE_INSTANCE_ID=%s in %s", first_uuid, secrets_path.name)
        except Exception as exc:
            logger.warning("Auto-fill secrets.env INSTANCE_ID failed: %s", exc)


def _patch_instance_metadata(instance_uuid: str, updates: dict) -> None:
    """Merge updates into apps/<uuid>/config/app.yaml (whole-file rewrite)."""
    import yaml
    from infrastructure.config import get_project_root
    path = get_project_root() / "apps" / instance_uuid / "config" / "app.yaml"
    if not path.exists():
        return
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            return
        for k, v in updates.items():
            raw[k] = v
        path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
    except Exception as exc:
        logger.warning("patch_instance_metadata(%s) failed: %s", instance_uuid, exc)


def _ensure_default_project() -> None:
    """首次启动防护：没有项目时自动 seed「龙虾模拟炒股」项目。

    新人 clone + 跑起来就有一个完整 demo 场景可看：
    zero + alpha 协作执行量化策略（trader/strategist/architect 岗位分工）。
    项目已存在同名 id 时不覆盖（用户自定义的修改保留）。
    """
    import yaml

    from infrastructure.config import get_project_root, _load_registry  # type: ignore[attr-defined]

    projects_dir = get_project_root() / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    # 项目已存在（同名 id）不 seed
    default_pid = "trading_simulation"
    project_yaml = projects_dir / default_pid / "project.yaml"
    if project_yaml.exists():
        return

    # 取当前已 bootstrap 的实例作为 trader / strategist
    registry = _load_registry() or {}
    iids = list(registry.keys())
    if len(iids) < 2:
        # 单实例时只填 trader，用户后续可指定 strategist
        zero_iid = iids[0] if iids else ""
        alpha_iid = ""
    else:
        # 第一个做 strategist/manager（zero 决策），第二个做 trader（执行）
        zero_iid = iids[0]
        alpha_iid = iids[1]

    project_dir = projects_dir / default_pid
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "data").mkdir(exist_ok=True)

    # 构造完整 project.yaml —— 来源：龙虾模拟炒股任务说明书（用户提供的 docx）
    project_data = {
        "project": {
            "id": default_pid,
            "name": "龙虾模拟炒股挑战",
            "description": (
                "获得 10 万元虚拟启动资金，在 A 股市场进行模拟投资。"
                "目标是通过自主决策、自律盯盘、自我复盘，将资金增值到 100 万元（+900%）。"
                "这是一场考验综合能力的长期挑战 —— 不只是赚钱，更是"
                "规划、执行、反思、迭代的全闭环。"
            ),
            "status": "active",
            "manager": zero_iid,
            "group_chat_id": "",
            "goal": (
                "初始资金 ¥100,000 → 目标资金 ¥1,000,000（+900%）。"
                "关键不是能不能赚够，而是：\n"
                "1. 能否自主规划并持续执行一个长期任务\n"
                "2. 遇到问题时如何分析、如何解决\n"
                "3. 能否诚实面对亏损并从中学习\n"
                "4. 决策逻辑是否清晰可追溯\n"
                "策略可随时调整，只需能解释原因。必要时承认"
                "「这个我做不到」也是一种诚实的反思。"
            ),
            "kpis": [
                "每日复盘完成率 ≥ 80%",
                "每笔交易有明确理由 + 操作记录",
                "账户状态文件随时可查",
                "亏损时有结构化归因（判断失误 / 时机 / 信息不足）",
            ],
            "thesis": (
                "投资者注意力策略 + 不对称盈亏比："
                "精力聚焦在首板涨停次日溢价（论断 4：T+1 收盘前必须了结）+"
                "止损 -3% / 止盈 +5~7% 的不对称结构能在 45% 胜率下实现正期望。"
                "核心是诚实迭代——每一笔交易（无论盈亏）都进入结构性反思，"
                "论断本身可以随时被修正甚至废弃（如论断 4 在 6/18 已废弃）。"
            ),
            "positions": [
                {
                    "id": "strategist",
                    "name": "策略师",
                    "assignees": [zero_iid] if zero_iid else [],
                },
                {
                    "id": "trader",
                    "name": "交易员",
                    "assignees": [alpha_iid] if alpha_iid else [],
                },
                {
                    "id": "manager",
                    "name": "项目经理（人类）",
                    "assignees": [],
                },
            ],
            "review_schedule": {
                "daily_review_time": "21:00",
                "weekly_planning_day": "Sunday",
                "monthly_review_day": "last_friday",
            },
            "rules": {
                "t_plus_1": "当天买入次日才能卖出",
                "limit_up_down": "主板 ±10%，创业板/科创板 ±20%，ST 股 ±5%",
                "trading_hours": "9:30-11:30 13:00-15:00 工作日",
                "fees": "印花税 0.1%（卖）、佣金 0.025%（买卖）、过户费 0.001%",
                "lot_size": "买入需 100 股整数倍，卖出不限",
            },
            "accounting": {
                "initial_capital": 100000,
                "remember": (
                    "账户状态由数字生命自主维护。建议维护 trading_log.json +"
                    "账户快照；每笔交易（含手续费）实时扣减现金。"
                ),
            },
            "working_memory": (
                "见 projects/trading_simulation/working_memory/ 下的"
                "thesis.md（论断列表）+ daily_log.md（每日策略执行记录）+"
                "review.md（复盘结论）。这些文件由数字生命自己写入 / 修正。"
            ),
        }
    }

    project_yaml.write_text(
        yaml.dump(project_data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    logger.info("Default project '%s' seeded", default_pid)


async def run_master_gateway() -> None:
    """主进程：HTTP server + InstanceSupervisor。

    InstanceSupervisor 读取 var/run/last_active.json，spawn 所有子进程，
    监视并在 crash 时有限次数内重启。
    """
    # 首次启动防护:一个实例都没有时,自动 bootstrap 默认 zero 实例。
    # 让新人 clone + 填好 secrets.env 后直接 `digital-life start` 就能跑通,
    # 无需手动 `python scripts/init_instance.py`。
    _ensure_default_instance()

    # 首次启动防护:没有项目时,自动 seed 默认「龙虾模拟炒股」项目。
    # 这是项目里默认的 demo 场景 (zero + alpha 多实例协作执行量化策略)。
    try:
        _ensure_default_project()
    except Exception as exc:
        logger.warning("seed default project failed (non-fatal): %s", exc)

    # 注入运行时适配器（保险：实际 wake 在 instance 子进程里跑，子进程会
    # 自行注入。这里补一刀覆盖可能的开发模式直接跑 master 的情况，
    # 让 session_evidence 的 fallback reader 不再是 NullSessionEvidenceReader）。
    try:
        from application.runtime_provider import configure_runtime_provider
        configure_runtime_provider()
    except Exception as exc:
        logger.warning("configure_runtime_provider failed at master startup: %s", exc)

    from gateway.instance_supervisor import InstanceSupervisor

    stop_event = asyncio.Event()

    def _signal_handler(sig):
        logger.info("Master received signal %s", sig)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler, sig)
        except NotImplementedError:
            pass

    # 启动 HTTP server
    app = web.Application()
    app["feishu_adapters"] = []  # master 不持有 adapter

    from application.api.employee_console_routes import register
    register(app, adapter=None)

    # 系统级路由（跨实例）：/api/system/* + /employee/{iid}/assets/*
    from application.api.system_routes import add_system_routes
    add_system_routes(app)

    # 广播 endpoint:接收 peer 实例的 HTTP 广播(去中心化消息总线 Phase 3)
    from application.api.broadcast_routes import add_broadcast_routes
    add_broadcast_routes(app)

    # 启动时同步各实例的 subscriptions.yaml(其他实例在哪群 → 各自写好 peers 列表)
    try:
        from domain.messages.broadcast import sync_subscriptions_from_registry
        sync_subscriptions_from_registry()
    except Exception as exc:
        logger.warning("sync_subscriptions failed (non-fatal): %s", exc)

    from infrastructure.http.openai_api import add_openai_routes
    add_openai_routes(app)

    port = int(os.getenv("API_SERVER_PORT") or 8642)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Master HTTP server started on port %d", port)

    # 启动 supervisor
    supervisor = InstanceSupervisor()
    app["supervisor"] = supervisor  # 暴露给 HTTP routes，用于 toggle active 时联动 spawn/stop
    await supervisor.start()

    # restart 物理触发：POST /api/system/gateway/restart 写 var/run/.restart_requested，
    # 本 watcher 检测到后 graceful shutdown + os._exit(2)（外部 wrapper / launchd 拉起）
    async def _watch_restart_trigger():
        from infrastructure.config import get_project_root

        trigger_path = get_project_root() / "var" / "run" / ".restart_requested"
        while not stop_event.is_set():
            try:
                if trigger_path.exists():
                    try:
                        payload = trigger_path.read_text(encoding="utf-8")
                    except Exception:
                        payload = ""
                    logger.warning(
                        "Master restart triggered. Payload:\n%s\n"
                        "外部 wrapper（launchd/systemd/`digital-life restart`）会拉起新进程。",
                        payload,
                    )
                    try:
                        trigger_path.unlink()
                    except OSError:
                        pass
                    stop_event.set()
                    # 给 graceful shutdown 2s 后强制退出（由 wrapper 拉起重启）
                    import asyncio as _aio
                    await _aio.sleep(2)
                    import os as _os
                    _os._exit(2)
            except Exception as exc:
                logger.warning("restart watcher tick failed: %s", exc)
            await asyncio.sleep(5)

    restart_watcher_task = asyncio.create_task(_watch_restart_trigger())

    await stop_event.wait()
    logger.info("Master shutting down...")

    await supervisor.stop()
    await runner.cleanup()
    logger.info("Master stopped")


# ──────────────────────────────── 兼容入口 ────────────────────────────────


def _discover_feishu_bots() -> list[dict]:
    """旧版兼容：单进程扫描所有实例的 feishu bot。

    主线不再使用，保留用于回退或调试。
    """
    import yaml
    from infrastructure.config import discover_active_instances, get_project_root

    bots: dict[str, dict] = {}
    for instance_id in discover_active_instances():
        config_file = get_project_root() / "apps" / instance_id / "config" / "app.yaml"
        if not config_file.exists():
            continue
        try:
            cfg = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
            messenger = cfg.get("messenger") or {}
            app_id = (messenger.get("app_id") or "").strip()
            app_secret = ""
            secrets_path = get_project_root() / "apps" / instance_id / "config" / "secrets.env"
            if secrets_path.exists():
                for line in secrets_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("FEISHU_APP_SECRET="):
                        app_secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
            if app_id and app_id not in bots:
                bots[app_id] = {
                    "app_id": app_id,
                    "app_secret": app_secret,
                    "label": instance_id,
                }
        except Exception:
            pass

    if not bots:
        app_id = os.environ.get("FEISHU_APP_ID", "")
        app_secret = os.environ.get("FEISHU_APP_SECRET", "")
        if app_id:
            bots[app_id] = {"app_id": app_id, "app_secret": app_secret, "label": "env"}

    return list(bots.values())


async def run_gateway() -> None:
    """Legacy 单进程入口：跑 HTTP + 所有 adapter + cron。

    用于调试或单实例场景。多实例推荐用 run_master_gateway / run_instance_gateway。
    """
    adapters: list = []
    stop_event = asyncio.Event()

    from interfaces.ingress.feishu import FeishuAdapter
    from application.ingress.handler import handle_message as ingress_handle_message

    for bot in _discover_feishu_bots():
        feishu = FeishuAdapter(app_id=bot["app_id"], app_secret=bot["app_secret"])
        feishu.on_message(lambda msg, f=feishu: ingress_handle_message(adapter=f, msg=msg))
        await feishu.start()
        adapters.append(feishu)
        logger.info("Feishu ingress adapter for %s started", bot["label"])

    app = web.Application()
    app["feishu_adapters"] = list(adapters)
    from application.api.employee_console_routes import register
    register(app, adapter=None)

    # 广播 endpoint:接收 peer 实例的 HTTP 广播(去中心化消息总线 Phase 3)
    from application.api.broadcast_routes import add_broadcast_routes
    add_broadcast_routes(app)

    # 启动时同步各实例的 subscriptions.yaml(其他实例在哪群 → 各自写好 peers 列表)
    try:
        from domain.messages.broadcast import sync_subscriptions_from_registry
        sync_subscriptions_from_registry()
    except Exception as exc:
        logger.warning("sync_subscriptions failed (non-fatal): %s", exc)
    from infrastructure.http.openai_api import add_openai_routes
    add_openai_routes(app)

    port = int(os.getenv("API_SERVER_PORT") or 8642)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("HTTP server started on port %d", port)

    cron_thread = None
    cron_stop = threading.Event()
    try:
        from infrastructure.scheduler.cron_runner import start_cron_daemon
        cron_thread = start_cron_daemon(stop_event=cron_stop)
        logger.info("Cron daemon started")
    except Exception as exc:
        logger.warning("Cron daemon failed to start: %s", exc)

    def _signal_handler(sig):
        logger.info("Received signal %s", sig)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler, sig)
        except NotImplementedError:
            pass

    await stop_event.wait()
    logger.info("Gateway shutting down...")

    for adapter in adapters:
        try:
            await adapter.stop()
        except Exception:
            pass
    await runner.cleanup()
    if cron_thread and cron_thread.is_alive():
        cron_stop.set()
        cron_thread.join(timeout=5)
    logger.info("Gateway stopped")
