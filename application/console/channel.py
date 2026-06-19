"""Employee console channel configuration workflow.

Historical note: this workflow used to write FEISHU_* keys into the global
``secrets.env`` via its own dedicated endpoint ``/api/employee/channels``.
Multi-instance refactoring moved channel ownership to per-instance
``apps/{id}/config/app.yaml`` + ``secrets.env``. The shared global fallback
keys were retired (see action_tools.py: no longer reads
FEISHU_ALLOWED_USERS / FEISHU_HOME_CHANNEL to avoid cross-instance leakage).

This class is kept as a thin façade so existing callers and import tests keep
working. Both methods delegate to ``ConfigCenterWorkflow`` so all channel-ish
settings live behind the single /api/employee/config surface and never fall
out of sync again.
"""

from __future__ import annotations

from typing import Any

from application.contracts import UseCaseResult
from infrastructure.config import get_runtime_config_path, get_runtime_env_path


class ChannelConsoleWorkflow:
    """Façade over ConfigCenterWorkflow for backward compatibility."""

    @staticmethod
    def _feishu_defaults() -> dict[str, Any]:
        return {
            "enabled": False,
            "app_id": "",
            "has_app_secret": False,
            "connection_mode": "websocket",
            "allowed_users": "",
        }

    def _feishu_snapshot(self) -> dict[str, Any]:
        env = self._load_env()
        data = self._feishu_defaults()
        data.update({
            "enabled": bool((env.get("FEISHU_APP_ID") or "").strip()
                            and (env.get("FEISHU_APP_SECRET") or "").strip()),
            "app_id": (env.get("FEISHU_APP_ID") or "").strip(),
            "has_app_secret": bool((env.get("FEISHU_APP_SECRET") or "").strip()),
            "connection_mode": "websocket",
            "allowed_users": (env.get("FEISHU_ALLOWED_USERS") or "").strip(),
        })
        return data

    def channels(self) -> UseCaseResult:
        """Read-only snapshot. Real editing happens through ConfigCenter.

        The values here only reflect legacy global env, kept for diagnostics
        only — per-instance credentials live in apps/{id}/config/.
        """
        try:
            return UseCaseResult({
                "env_path": str(get_runtime_env_path()),
                "config_path": str(get_runtime_config_path()),
                "defaults": {"feishu": self._feishu_defaults()},
                "channels": {"feishu": self._feishu_snapshot()},
            })
        except Exception as exc:
            return UseCaseResult({"error": str(exc)}, 500)

    def update_channels(self, body: dict[str, Any]) -> UseCaseResult:
        """Deprecated write path.

        Editing FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_ALLOWED_USERS via the
        global env leaks across instances (each instance owns its own credentials
        now). Reject the mutation and point the caller at the config center, which
        writes to per-instance app.yaml / secrets.env.
        """
        return UseCaseResult(
            {
                "error": (
                    "channel 编辑已停用：钉书 app 凭证按实例管理。"
                    "用 PATCH /api/employee/config 改 messenger.app_id / 实例 secrets.env 的 FEISHU_APP_SECRET。"
                ),
                "channels": {"feishu": self._feishu_snapshot()},
            },
            409,
        )

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


__all__ = ["ChannelConsoleWorkflow"]
