"""工具注册中心 — OpenAI 兼容的工具注册与调度。

ToolRegistry 提供：
  - register(): 注册工具（name/toolset/schema/handler/check_fn/emoji）
  - dispatch(): 按名称调度工具执行
  - get_definitions(): 获取 OpenAI function-calling 格式的工具定义列表
  - is_toolset_available(): 检查工具集是否可用（通过 check_fn）
  - get_available_toolsets(): 获取所有可用工具集及其工具列表

ToolEntry 数据结构：
  name, toolset, schema（OpenAI function schema）, handler（执行函数）,
  check_fn（可用性检查，如环境变量是否配置）, requires_env, is_async, emoji

每个工具按 toolset 分组（如 actions/senses/tasks/terminal），
toolset 级别的 check_fn 控制整组工具的可用性。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolEntry:
    name: str
    toolset: str
    schema: dict[str, Any]
    handler: Callable[..., Any]
    check_fn: Callable[[], bool] | None = None
    requires_env: tuple[str, ...] = ()
    is_async: bool = False
    description: str = ""
    emoji: str = ""
    max_result_size_chars: int | float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """数字生命工具注册中心——OpenAI 兼容的函数调用格式。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}
        self._toolset_checks: dict[str, Callable[[], bool]] = {}

    def register(
        self,
        name: str,
        toolset: str,
        schema: dict[str, Any],
        handler: Callable[..., Any],
        check_fn: Callable[[], bool] | None = None,
        requires_env: list[str] | tuple[str, ...] | None = None,
        is_async: bool = False,
        description: str = "",
        emoji: str = "",
        max_result_size_chars: int | float | None = None,
        **metadata: Any,
    ) -> None:
        self._tools[name] = ToolEntry(
            name=name,
            toolset=toolset,
            schema={**(schema or {}), "name": name},
            handler=handler,
            check_fn=check_fn,
            requires_env=tuple(requires_env or ()),
            is_async=is_async,
            description=description or str((schema or {}).get("description", "")),
            emoji=emoji,
            max_result_size_chars=max_result_size_chars,
            metadata=dict(metadata),
        )
        if check_fn and toolset not in self._toolset_checks:
            self._toolset_checks[toolset] = check_fn

    def deregister(self, name: str) -> None:
        entry = self._tools.pop(name, None)
        if not entry:
            return
        if not any(tool.toolset == entry.toolset for tool in self._tools.values()):
            self._toolset_checks.pop(entry.toolset, None)

    def dispatch(self, name: str, args: dict[str, Any] | None = None, **kwargs: Any) -> str:
        entry = self._tools.get(name)
        if not entry:
            return tool_error(f"Unknown tool: {name}")
        try:
            payload = args or {}
            if entry.is_async:
                from interfaces.tools.async_utils import run_async

                return run_async(entry.handler(payload, **kwargs))
            result = entry.handler(payload, **kwargs)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as exc:
            logger.exception("Tool %s dispatch error: %s", name, exc)
            return tool_error(f"Tool execution failed: {type(exc).__name__}: {exc}")

    def get_definitions(self, tool_names: set[str], quiet: bool = False) -> list[dict[str, Any]]:
        definitions: list[dict[str, Any]] = []
        for name in sorted(tool_names):
            entry = self._tools.get(name)
            if not entry or not self._entry_available(entry, quiet=quiet):
                continue
            definitions.append({"type": "function", "function": dict(entry.schema)})
        return definitions

    def get_all_tool_names(self) -> list[str]:
        return sorted(self._tools)

    def get_schema(self, name: str) -> dict[str, Any] | None:
        entry = self._tools.get(name)
        return dict(entry.schema) if entry else None

    def get_toolset_for_tool(self, name: str) -> str | None:
        entry = self._tools.get(name)
        return entry.toolset if entry else None

    def get_emoji(self, name: str, default: str = "⚡") -> str:
        entry = self._tools.get(name)
        return entry.emoji or default if entry else default

    def get_tool_to_toolset_map(self) -> dict[str, str]:
        return {name: entry.toolset for name, entry in self._tools.items()}

    def is_toolset_available(self, toolset: str) -> bool:
        check = self._toolset_checks.get(toolset)
        if not check:
            return True
        try:
            return bool(check())
        except Exception:
            logger.debug("Toolset %s check failed", toolset, exc_info=True)
            return False

    def check_toolset_requirements(self) -> dict[str, bool]:
        return {toolset: self.is_toolset_available(toolset) for toolset in self._all_toolsets()}

    def check_tool_availability(self, quiet: bool = False):
        available: list[str] = []
        unavailable: list[dict[str, Any]] = []
        for toolset in self._all_toolsets():
            if self.is_toolset_available(toolset):
                available.append(toolset)
            else:
                unavailable.append({"name": toolset, "tools": self._tools_for_toolset(toolset)})
        return available, unavailable

    def get_available_toolsets(self) -> dict[str, dict[str, Any]]:
        return {
            toolset: {
                "available": self.is_toolset_available(toolset),
                "tools": self._tools_for_toolset(toolset),
                "requirements": sorted({env for entry in self._tools.values() if entry.toolset == toolset for env in entry.requires_env}),
            }
            for toolset in self._all_toolsets()
        }

    def get_toolset_requirements(self) -> dict[str, dict[str, Any]]:
        return {
            toolset: {
                "name": toolset,
                "env_vars": sorted({env for entry in self._tools.values() if entry.toolset == toolset for env in entry.requires_env}),
                "tools": self._tools_for_toolset(toolset),
                "check_fn": self._toolset_checks.get(toolset),
                "setup_url": None,
            }
            for toolset in self._all_toolsets()
        }

    def get_max_result_size(self, name: str, default: int | float | None = None) -> int | float | None:
        entry = self._tools.get(name)
        if entry and entry.max_result_size_chars is not None:
            return entry.max_result_size_chars
        return default

    def tool_error(self, message: Any, **extra: Any) -> str:
        return tool_error(message, **extra)

    def tool_result(self, data: Any = None, **kwargs: Any) -> str:
        return tool_result(data, **kwargs)

    def _entry_available(self, entry: ToolEntry, *, quiet: bool) -> bool:
        if not entry.check_fn:
            return True
        try:
            return bool(entry.check_fn())
        except Exception:
            if not quiet:
                logger.debug("Tool %s check failed", entry.name, exc_info=True)
            return False

    def _all_toolsets(self) -> list[str]:
        return sorted({entry.toolset for entry in self._tools.values()})

    def _tools_for_toolset(self, toolset: str) -> list[str]:
        return sorted(name for name, entry in self._tools.items() if entry.toolset == toolset)


def tool_error(message: Any, **extra: Any) -> str:
    payload = {"error": str(message)}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False, default=str)


def tool_result(data: Any = None, **kwargs: Any) -> str:
    payload = data if data is not None else kwargs
    return json.dumps(payload, ensure_ascii=False, default=str)


registry = ToolRegistry()

