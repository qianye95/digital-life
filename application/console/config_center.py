"""Structured configuration workflow for the employee console."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from application.contracts import UseCaseResult
from infrastructure.config import (
    get_app_persona_path,
    get_app_skills_dir,
    get_project_root,
    get_runtime_config_path,
    get_runtime_env_path,
    get_runtime_home,
    get_runtime_memories_dir,
    get_runtime_state_db_path,
)


@dataclass(frozen=True)
class ConfigField:
    key: str
    label: str
    section: str
    source: str
    value_type: str = "string"
    path: str | None = None
    default: Any = ""
    secret: bool = False
    restart_required: bool = True
    readonly: bool = False
    options: tuple[str, ...] = ()
    description: str = ""


SECTION_META: dict[str, dict[str, str]] = {
    "employee": {"label": "员工实例", "description": "数字员工身份名（display_name）。实例 ID 由 init_instance.py 生成，不可改。"},
    "messenger": {"label": "消息通道", "description": "飞书凭证（App ID / App Secret）+ 群消息路由。改动后需重启网关生效。"},
    "model": {"label": "模型配置", "description": "主推理模型 + Provider + API Key（写入实例 app.yaml.model + secrets.env）。"},
    "runtime": {"label": "运行节律 / 精力策略", "description": "心跳间隔、token 上限、精力折算系数 —— 多实例共享的全局参数。"},
    "tasks": {"label": "任务执行策略", "description": "最大执行轮数、推理强度。"},
}


FIELDS: tuple[ConfigField, ...] = (
    # ════════════ 实例身份（不可改 ID 类）════════════
    ConfigField("display_name", "显示名称", "employee", "yaml", path="display_name", description="实例身份名（chat_stream「我自己」/ 前端实例标签 / 日志前缀）。"),
    # 注：DIGITAL_LIFE_INSTANCE_ID / DIGITAL_LIFE_DISPLAY_NAME 是进程屏蔽层用，
    #     不暴露给前端配置 —— 实例 UUID 由 init_instance.py 生成，
    #     display_name 通过 app.yaml.display_name 编辑

    # ════════════ 飞书凭证（实例私有，per-instance secrets）════════════
    ConfigField(
        "messenger.app_id",
        "飞书 App ID",
        "messenger",
        "yaml",
        path="messenger.app_id",
        description="该实例绑定的飞书自建应用 App ID（cli_xxx）。改动后必须重启网关。",
    ),
    ConfigField(
        "FEISHU_APP_SECRET",
        "飞书 App Secret",
        "messenger",
        "env",
        secret=True,
        description="对应自建应用的 App Secret（敏感，存实例 config/secrets.env）。",
    ),
    ConfigField(
        "messenger.feishu_domain",
        "飞书 API 域名",
        "messenger",
        "yaml",
        path="messenger.feishu_domain",
        default="https://open.feishu.cn",
        description="国内版填 https://open.feishu.cn，国际版填 https://open.larksuite.com。",
    ),
    ConfigField(
        "group_chat.attention_keywords",
        "群聊关键词（立即响应）",
        "messenger",
        "yaml",
        "array",
        path="group_chat.attention_keywords",
        description="含这些词的群消息立即响应。其余群消息走 30s 累积窗口。",
    ),
    ConfigField(
        "group_chat.owner_names",
        "群聊 Owner（立即响应）",
        "messenger",
        "yaml",
        "array",
        path="group_chat.owner_names",
        description="这些人发言立即响应。",
    ),

    # ════════════ 模型配置（实例私有，per-instance yaml + secrets）════════════
    # 事实源是 apps/<id>/config/app.yaml 段的 model.name/provider/base_url
    # + apps/<id>/config/secrets.env 的 GLM_API_KEY
    # 之前 6 个 DIGITAL_LIFE_MODEL/PROVIDER/SUMMARY/CHEAP/SMART_ROUTING env 字段
    # 都已经被代码忽略（model.cfg 优先级更高），从配置中心移除避免误导。
    ConfigField(
        "model.name",
        "主模型",
        "model",
        "yaml",
        path="model.name",
        default="glm-5.2",
        description="该实例主推理模型（如 glm-5.2 / glm-4.7-flash）。",
    ),
    ConfigField(
        "model.provider",
        "模型 Provider",
        "model",
        "yaml",
        path="model.provider",
        default="glm",
        description="provider identifier，决定 base_url + api_key 怎么拼。",
    ),
    ConfigField(
        "model.base_url",
        "Provider Base URL",
        "model",
        "yaml",
        path="model.base_url",
        default="https://open.bigmodel.cn/api/paas/v4",
        description="LLM API endpoint。",
    ),
    ConfigField(
        "GLM_API_KEY",
        "API Key",
        "model",
        "env",
        secret=True,
        description="模型 API Key（敏感，存实例 config/secrets.env）。留空保存 = 保留当前值。",
    ),

    # ════════════ 运行时（跨实例共享，全局通用配置）════════════
    ConfigField("L4_TICK_INTERVAL", "心跳检查间隔（秒）", "runtime", "env", "number", default=60),
    ConfigField(
        "DIGITAL_LIFE_TOKEN_HOURLY_LIMIT",
        "Token 小时上限",
        "runtime",
        "env",
        "number",
        default=50000000,
        description="每实例每小时 LLM token 上限。开发期默认 = 日上限（实际不拦）。"
                    "生产部署可调小。",
    ),
    ConfigField(
        "DIGITAL_LIFE_TOKEN_DAILY_LIMIT",
        "Token 日上限",
        "runtime",
        "env",
        "number",
        default=50000000,
        description="每实例每天 LLM token 上限。日累计超过就拒绝新 wake 直到次日 00:00。"
                    "默认 5000 万，给开发期留空间；生产部署可调小。",
    ),
    ConfigField(
        "DIGITAL_LIFE_ENERGY_PER_KTOKEN_INPUT",
        "输入 token 精力系数",
        "runtime",
        "env",
        "number",
        default=0.005,
        description="每 1k input token 折算多少精力消耗。1k input = 0.005 精力。",
    ),
    ConfigField(
        "DIGITAL_LIFE_ENERGY_PER_KTOKEN_OUTPUT",
        "输出 token 精力系数",
        "runtime",
        "env",
        "number",
        default=0.05,
        description="每 1k output token 折算多少精力消耗。output 比 input 贵 10×。"
                    "整体设计：一天满跑 2000 万 token 刚好耗尽 100 精力。",
    ),

    # ════════════ 任务执行策略（实例私有 yaml）════════════
    ConfigField("agent.max_turns", "最大执行轮数", "tasks", "yaml", "number", path="agent.max_turns", default=90),
    ConfigField(
        "agent.reasoning_effort",
        "推理强度",
        "tasks",
        "yaml",
        "select",
        path="agent.reasoning_effort",
        default="medium",
        options=("minimal", "low", "medium", "high", "xhigh"),
    ),
)


class ConfigCenterWorkflow:
    """Expose a product-level configuration registry instead of raw env files."""

    def config(self, employee_id: str | None = None) -> UseCaseResult:
        try:
            env = self._load_env()
            yaml_config = self._load_yaml()
            sections = self._sections(env, yaml_config, employee_id)
            return UseCaseResult({
                "sections": sections,
                "schema": [self._field_schema(field) for field in FIELDS],
                "paths": self._paths(employee_id),
                "config": self._legacy_runtime_policy(env, yaml_config),
            })
        except Exception as exc:
            return UseCaseResult({"error": str(exc)}, 500)

    def update_config(self, body: dict[str, Any], employee_id: str | None = None) -> UseCaseResult:
        try:
            if not isinstance(body, dict):
                return UseCaseResult({"error": "Invalid JSON body"}, 400)
            values = body.get("values") if isinstance(body.get("values"), dict) else body
            fields_by_key = {field.key: field for field in FIELDS}
            env_updates: dict[str, str | None] = {}
            yaml_updates: dict[str, Any] = {}

            for key, raw_value in values.items():
                field = fields_by_key.get(key)
                if not field or field.readonly:
                    continue
                if field.secret and (raw_value is None or str(raw_value).strip() == ""):
                    continue
                value = self._coerce_value(raw_value, field)
                if field.source == "env":
                    env_updates[field.key] = self._env_text(value, field)
                elif field.source == "yaml" and field.path:
                    yaml_updates[field.path] = value

            if env_updates:
                self._write_env_updates(env_updates)
            if yaml_updates:
                self._write_yaml_updates(yaml_updates)
            return self.config(employee_id)
        except ValueError as exc:
            return UseCaseResult({"error": str(exc)}, 400)
        except Exception as exc:
            return UseCaseResult({"error": str(exc)}, 500)

    def _sections(self, env: dict[str, str], yaml_config: dict[str, Any], employee_id: str | None) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in SECTION_META}
        for field in FIELDS:
            grouped[field.section].append(self._field_payload(field, env, yaml_config))
        # 注：之前 employee / events / diagnostics 还 extend 了一堆 _readonly 路径
        # 显示字段，用户反馈"没用"——全部移除。需要看路径就去对应的具体页面
        # （状态 / 实例概览 / db 路径等地方都有）。
        return [
            {
                "key": key,
                "label": meta["label"],
                "description": meta["description"],
                "fields": grouped.get(key, []),
            }
            for key, meta in SECTION_META.items()
        ]

    def _field_payload(self, field: ConfigField, env: dict[str, str], yaml_config: dict[str, Any]) -> dict[str, Any]:
        value, origin = self._field_value(field, env, yaml_config)
        configured = self._is_configured(value)
        if field.secret:
            value = ""
        return {
            **self._field_schema(field),
            "value": value,
            "configured": configured,
            "origin": origin,
        }

    @staticmethod
    def _field_schema(field: ConfigField) -> dict[str, Any]:
        return {
            "key": field.key,
            "label": field.label,
            "section": field.section,
            "source": field.source,
            "type": field.value_type,
            "secret": field.secret,
            "restart_required": field.restart_required,
            "readonly": field.readonly,
            "options": list(field.options),
            "description": field.description,
        }

    def _field_value(self, field: ConfigField, env: dict[str, str], yaml_config: dict[str, Any]) -> tuple[Any, str]:
        if field.source == "env":
            if field.key in env:
                return self._coerce_value(env[field.key], field), "secrets.env"
            if field.key in os.environ:
                return self._coerce_value(os.environ[field.key], field), "process.env"
            return self._coerce_value(field.default, field), "default"
        if field.source == "yaml" and field.path:
            value = self._get_nested(yaml_config, field.path)
            if value is not None:
                return self._coerce_value(value, field), "local.yaml"
        return self._coerce_value(field.default, field), "default"

    @staticmethod
    def _is_configured(value: Any) -> bool:
        if isinstance(value, bool):
            return True
        if isinstance(value, list):
            return len(value) > 0
        return value is not None and str(value).strip() != ""

    @staticmethod
    @staticmethod
    def _legacy_runtime_policy(env: dict[str, str], yaml_config: dict[str, Any]) -> dict[str, Any]:
        """Snapshot summary used by the status page. Mirrors fields that are
        actually consumed by the runtime (token gate, energy simulation,
        tick interval) so the displayed numbers reflect real behavior.
        历史快照里曾包含 VITALS_/DEBUG_ENERGY_RECOVERY_AMOUNT/L4_HEARTBEAT_HOURS
        等环境变量，但代码并不读它们——已于精简中一并删除（避免让用户以为改了会生效）。
        """
        def number(key: str, default: float) -> float:
            try:
                return float(env.get(key, default))
            except (TypeError, ValueError):
                return default

        return {
            "runtime": {
                "tick_interval": number("L4_TICK_INTERVAL", 60),
                "token_hourly_limit": number("DIGITAL_LIFE_TOKEN_HOURLY_LIMIT", 50_000_000),
                "token_daily_limit": number("DIGITAL_LIFE_TOKEN_DAILY_LIMIT", 50_000_000),
            },
            "energy": {
                "per_ktoken_input": number("DIGITAL_LIFE_ENERGY_PER_KTOKEN_INPUT", 0.005),
                "per_ktoken_output": number("DIGITAL_LIFE_ENERGY_PER_KTOKEN_OUTPUT", 0.05),
            },
            "agent": {
                "runtime_provider": env.get("DIGITAL_LIFE_RUNTIME_PROVIDER", "l4"),
                "max_turns": ConfigCenterWorkflow._get_nested(yaml_config, "agent.max_turns") or 90,
                "reasoning_effort": ConfigCenterWorkflow._get_nested(yaml_config, "agent.reasoning_effort") or "medium",
            },
        }

    @staticmethod
    def _load_env() -> dict[str, str]:
        path = get_runtime_env_path()
        if not path.exists():
            return {}
        values: dict[str, str] = {}
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    @staticmethod
    def _write_env_updates(updates: dict[str, str | None]) -> None:
        path = get_runtime_env_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        pending = dict(updates)
        written: list[str] = []
        for raw in lines:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                written.append(raw)
                continue
            key = stripped.split("=", 1)[0].strip()
            if key not in pending:
                written.append(raw)
                continue
            value = pending.pop(key)
            if value not in (None, ""):
                written.append(f"{key}={value}")
        for key, value in pending.items():
            if value not in (None, ""):
                written.append(f"{key}={value}")
        path.write_text("\n".join(written).rstrip() + "\n", encoding="utf-8")

    @staticmethod
    def _load_yaml() -> dict[str, Any]:
        path = get_runtime_config_path()
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    @staticmethod
    def _write_yaml_updates(updates: dict[str, Any]) -> None:
        path = get_runtime_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = ConfigCenterWorkflow._load_yaml()
        for dotted, value in updates.items():
            ConfigCenterWorkflow._set_nested(raw, dotted, value)
        path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")

    @staticmethod
    def _get_nested(data: dict[str, Any], dotted: str) -> Any:
        current: Any = data
        for part in dotted.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    @staticmethod
    def _set_nested(data: dict[str, Any], dotted: str, value: Any) -> None:
        current = data
        parts = dotted.split(".")
        for part in parts[:-1]:
            next_value = current.get(part)
            if not isinstance(next_value, dict):
                next_value = {}
                current[part] = next_value
            current = next_value
        current[parts[-1]] = value

    @staticmethod
    def _coerce_value(value: Any, field: ConfigField) -> Any:
        if field.value_type == "array":
            if value is None or value == "":
                return []
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            text = str(value)
            try:
                parsed = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                raise ValueError(f"{field.label} must be a YAML array: {exc}") from exc
            if parsed is None:
                return []
            if not isinstance(parsed, list):
                raise ValueError(f"{field.label} must be a list")
            return [str(v).strip() for v in parsed if str(v).strip()]
        if field.value_type == "boolean":
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in {"1", "true", "yes", "on"}:
                return True
            if text in {"0", "false", "no", "off"}:
                return False
            raise ValueError(f"{field.label} must be boolean")
        if field.value_type == "number":
            if value in (None, ""):
                return field.default
            number = float(value)
            return int(number) if number.is_integer() else number
        return "" if value is None else str(value).strip()

    @staticmethod
    def _env_text(value: Any, field: ConfigField) -> str:
        if field.value_type == "boolean":
            return "true" if bool(value) else "false"
        return str(value).strip()

    @staticmethod
    def _is_configured(value: Any) -> bool:
        if isinstance(value, bool):
            return True
        if isinstance(value, list):
            return len(value) > 0
        return value is not None and str(value).strip() != ""

    @staticmethod
    def _paths(employee_id: str | None) -> dict[str, str]:
        return {
            "project_root": str(get_project_root()),
            "runtime_home": str(get_runtime_home()),
            "config_path": str(get_runtime_config_path()),
            "env_path": str(get_runtime_env_path()),
            "state_db": str(get_runtime_state_db_path()),
            "memories_dir": str(get_runtime_memories_dir()),
            "persona_path": str(get_app_persona_path(employee_id)),
            "skills_dir": str(get_app_skills_dir(employee_id)),
        }


__all__ = ["ConfigCenterWorkflow"]
