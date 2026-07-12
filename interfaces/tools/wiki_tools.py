"""Wiki工具集 — 数字生命与个人知识库集成。

工具列表：
  - wiki_index: 查看知识库概览
  - wiki_list: 列出知识库中的文件
  - wiki_read: 读取知识库中的文档
  - wiki_search: 搜索知识库内容
  - wiki_write_session: 写入会话记录
  - wiki_update_entity: 更新或创建实体
  - wiki_update_index: 更新索引

知识库路径从环境变量 WIKI_PATH 读取，默认：
  /Users/mac/Documents/qianye/hermes/个人助手/wiki
"""

from __future__ import annotations

import json
import os
from typing import Any

from interfaces.tools.registry import registry, tool_result, tool_error


WIKI_PATH = os.getenv("WIKI_PATH", "/Users/mac/Documents/qianye/hermes/个人助手/wiki")


def _get_wiki():
    """获取Wiki工具实例，失败返回None。"""
    try:
        from domain.tools.wiki_tool import WikiTool
        return WikiTool(WIKI_PATH)
    except Exception as e:
        return None


def _burn(amount: float = 0.3):
    """每个wiki调用消耗少量精力。"""
    try:
        from domain.vital import consume_energy
        consume_energy(amount, reason="wiki")
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════
# 工具定义
# ════════════════════════════════════════════════════════════════


def _handle_wiki_index(args: dict[str, Any], **context) -> str:
    """查看知识库概览。"""
    _burn(0.3)
    wiki = _get_wiki()
    if not wiki:
        return tool_error(f"Wiki路径不可用: {WIKI_PATH}")
    
    result = wiki.read_index()
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


def _handle_wiki_list(args: dict[str, Any], **context) -> str:
    """列出知识库中的文件。"""
    _burn(0.3)
    wiki = _get_wiki()
    if not wiki:
        return tool_error(f"Wiki路径不可用: {WIKI_PATH}")
    
    category = args.get("category")
    files = wiki.list_files(category)
    
    return tool_result({
        "category": category or "all",
        "count": len(files),
        "files": files
    })


def _handle_wiki_read(args: dict[str, Any], **context) -> str:
    """读取知识库中的文档。"""
    _burn(0.5)
    wiki = _get_wiki()
    if not wiki:
        return tool_error(f"Wiki路径不可用: {WIKI_PATH}")
    
    file_path = args.get("file_path", "")
    if not file_path:
        return tool_error("file_path is required")
    
    result = wiki.read_document(file_path)
    if "error" in result:
        return tool_error(result["error"])
    
    # 截断过长的内容
    content = result["content"]
    if len(content) > 50000:
        content = content[:50000] + "\n\n... [TRUNCATED] ..."
    
    return tool_result({
        "path": result["path"],
        "metadata": result["metadata"],
        "content": content
    })


def _handle_wiki_search(args: dict[str, Any], **context) -> str:
    """搜索知识库内容。"""
    _burn(0.5)
    wiki = _get_wiki()
    if not wiki:
        return tool_error(f"Wiki路径不可用: {WIKI_PATH}")
    
    query = args.get("query", "")
    if not query:
        return tool_error("query is required")
    
    results = wiki.search(query)
    
    return tool_result({
        "query": query,
        "count": len(results),
        "results": results
    })


def _handle_wiki_write_session(args: dict[str, Any], **context) -> str:
    """写入会话记录到知识库。"""
    _burn(1.0)
    wiki = _get_wiki()
    if not wiki:
        return tool_error(f"Wiki路径不可用: {WIKI_PATH}")
    
    title = args.get("title", "")
    content = args.get("content", "")
    
    if not title:
        return tool_error("title is required")
    if not content:
        return tool_error("content is required")
    
    result = wiki.create_session(title, content)
    
    # 自动更新索引
    wiki.update_index()
    
    return tool_result(result)


def _handle_wiki_update_entity(args: dict[str, Any], **context) -> str:
    """更新或创建实体。"""
    _burn(1.0)
    wiki = _get_wiki()
    if not wiki:
        return tool_error(f"Wiki路径不可用: {WIKI_PATH}")
    
    entity_name = args.get("entity_name", "")
    content = args.get("content")
    
    if not entity_name:
        return tool_error("entity_name is required")
    
    result = wiki.update_entity(entity_name, content)
    
    # 自动更新索引
    wiki.update_index()
    
    return tool_result(result)


def _handle_wiki_update_index(args: dict[str, Any], **context) -> str:
    """更新知识库索引。"""
    _burn(0.5)
    wiki = _get_wiki()
    if not wiki:
        return tool_error(f"Wiki路径不可用: {WIKI_PATH}")
    
    result = wiki.update_index()
    return tool_result(result)


# ════════════════════════════════════════════════════════════════
# 注册工具
# ════════════════════════════════════════════════════════════════


def register_wiki_tools() -> None:
    """注册wiki工具集。"""
    
    # wiki_index
    registry.register(
        name="wiki_index",
        toolset="wiki",
        schema={
            "description": "查看个人知识库概览，包含会话数、实体数、概念数等统计信息。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        handler=_handle_wiki_index,
        description="查看知识库概览",
        emoji="📚"
    )
    
    # wiki_list
    registry.register(
        name="wiki_list",
        toolset="wiki",
        schema={
            "description": "列出知识库中的文件，可按分类过滤（sessions/entities/concepts/projects/decisions/outputs）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "分类名，不填返回全部",
                        "enum": ["sessions", "entities", "concepts", "projects", "decisions", "outputs"]
                    }
                },
                "required": []
            }
        },
        handler=_handle_wiki_list,
        description="列出知识库文件",
        emoji="📋"
    )
    
    # wiki_read
    registry.register(
        name="wiki_read",
        toolset="wiki",
        schema={
            "description": "读取知识库中的文档内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径，如 'sessions/2024-01-01-xxx' 或 'entities/陈德志'"
                    }
                },
                "required": ["file_path"]
            }
        },
        handler=_handle_wiki_read,
        description="读取文档",
        emoji="📖"
    )
    
    # wiki_search
    registry.register(
        name="wiki_search",
        toolset="wiki",
        schema={
            "description": "在知识库中搜索关键词。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    }
                },
                "required": ["query"]
            }
        },
        handler=_handle_wiki_search,
        description="搜索知识库",
        emoji="🔍"
    )
    
    # wiki_write_session
    registry.register(
        name="wiki_write_session",
        toolset="wiki",
        schema={
            "description": "写入会话记录到知识库。每次重要的对话或决策后调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "会话标题"
                    },
                    "content": {
                        "type": "string",
                        "description": "会话内容摘要"
                    }
                },
                "required": ["title", "content"]
            }
        },
        handler=_handle_wiki_write_session,
        description="写入会话记录",
        emoji="✍️"
    )
    
    # wiki_update_entity
    registry.register(
        name="wiki_update_entity",
        toolset="wiki",
        schema={
            "description": "更新或创建实体（人物、工具、概念等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "实体名称"
                    },
                    "content": {
                        "type": "string",
                        "description": "新增内容（可选）"
                    }
                },
                "required": ["entity_name"]
            }
        },
        handler=_handle_wiki_update_entity,
        description="更新实体",
        emoji="🏷️"
    )
    
    # wiki_update_index
    registry.register(
        name="wiki_update_index",
        toolset="wiki",
        schema={
            "description": "更新知识库索引。通常在写入新文档后自动调用。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        handler=_handle_wiki_update_index,
        description="更新索引",
        emoji="🔄"
    )


# 模块加载时自动注册
register_wiki_tools()
