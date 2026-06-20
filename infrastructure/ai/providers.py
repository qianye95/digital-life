"""LLM provider adapter — 模型知识的唯一家园，agent.py 不识别具体模型。

每个模型家族出站 reasoning 的字段名不同、入站把 reasoning 拼回去的方式也不同：
  GLM-4.5/4.6/5/5.2  出站 message.reasoning_content
                     入站：GLM-5.2 实测会读取 reasoning_content 字段并投入
                     reasoning context（2026-06 "789 数字"实验：含 reasoning_content
                     的历史 assistant message 入站后，模型能正确回忆）。
                     GLM-5 时代（旧）静默忽略 → 用 markdown 引证块 hack；
                     5.2 已解除限制，用原生 reasoning_content 字段。

  DeepSeek-R1     出站 message.reasoning_content；入站用 <think></think> 是行业标准
  OpenAI o1/o3    出站 message.reasoning.summary；reasoning 不应入站
  Claude thinking 出站 thinking block；可作为 thinking block 传回

抽象三端口：
  extract_reasoning(message_dict) -> str         出站：从响应 message 拿 reasoning 文本
  inject_into_messages(messages, reasonings)     入站：把上 N 轮 reasoning 注入到
                                                  对应 assistant message
  customize_payload(payload, reasoning_config)   请求：按家族选填 / 跳过 /
                                                  重映射 GLM 特有的 reasoning_effort
                                                  等字段。
"""
from __future__ import annotations

from typing import Any, Mapping, Protocol


class LLMProvider(Protocol):
    """模型家族适配接口。每个家族一个常量实现，agent.py 只调接口。"""

    name: str

    def extract_reasoning(self, message: Mapping[str, Any]) -> str:
        """从 LLM 响应的 message dict 里提取 reasoning 文本，没有返回 ''。"""
        ...

    def inject_into_messages(
        self,
        messages: list[dict[str, Any]],
        reasonings: list[str],
        *,
        max_rounds: int = 10,
    ) -> list[dict[str, Any]]:
        """把最近 N 轮 reasoning 就地拼回到对应 assistant message。"""
        ...

    def customize_payload(
        self,
        payload: dict[str, Any],
        *,
        reasoning_config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """按本家族规范修改 chat/completions 请求的 payload。

        例子：
          GLMProvider：把 reasoning_config["effort"] 写入 payload["reasoning_effort"]
          GenericOpenAIProvider（gpt-4o 等）：丢弃 reasoning_config（不透传无效字段）
          OpenAIReasoningProvider：把 GLM 的 minimal/xhigh 重映射到 low/high
          ClaudeProvider（未来）：需要改 tools 格式 + thinking budget

        返回新 payload 副本，不修改入参。
        """
        ...


class GLMProvider:
    """智谱 GLM（GLM-4.5/4.6/5）家族。

    出站：message.reasoning_content
    入站：GLM-5.2 实测确认 reasoning_content 字段会被读取并投入 reasoning context
          （"我心里想的数字是 789"实验：模型正确回忆 789）。GLM-5 时代静默忽略
          已被 5.2 修复。
    改成原生 reasoning_content 字段拼接，不再用"上一轮思考" markdown hack——
    避免长 context 中模型 reasoning 卡在早期 phase、循环重复旧 thinking。

    历史：GLM-5 时代 content 注入引用块 "上一轮思考"  是因为入站 reasoning_content
    被静默忽略——那时只能塞 content。GLM-5.2 时代这个限制已解除。
    """

    name = "glm"

    def extract_reasoning(self, message: Mapping[str, Any]) -> str:
        """出站：从 LLM 响应的 message dict 拿 reasoning_content。"""
        rc = message.get("reasoning_content")
        if isinstance(rc, str) and rc.strip():
            return rc.strip()
        rc2 = message.get("reasoning")
        if isinstance(rc2, str) and rc2.strip():
            return rc2.strip()
        return ""

    def inject_into_messages(
        self,
        messages: list[dict[str, Any]],
        reasonings: list[str],
        *,
        max_rounds: int = 10,
    ) -> list[dict[str, Any]]:
        """把最近 N 轮 reasoning 注入到对应 assistant message 的 `reasoning_content` 字段。

        GLM-5.2（2026-06 实测）：
          - 出站 assistant message 带 reasoning_content 字段（模型自己生成的思考）
          - 入站（多轮传回）reasoning_content 字段会被模型读取并投入下一轮的
            reasoning context —— GLM-5 时代静默忽略已解除。

        实验证据：含 reasoning_content 字段的 assistant 历史消息入站后，
        模型能在多轮里精确回忆 "789"（之前提示要求记住的数字）。

        实现要点：
          1. 只 patch 真实历史 assistant（跳过 `_is_fake=True` 注入占位）
          2. 保留 assistant 原始 content 不动
          3. 把推理文本写到 `reasoning_content` 字段
          4. trimmed 长度限制：单轮保留 600 chars（300 头 + 300 尾），
             避免无限堆叠
        """
        if not reasonings:
            return messages
        recent = reasonings[-max_rounds:]
        # 守卫同上：只 patch 真实历史 assistant，跳过注入占位（fake-assistant）
        assistant_idx = [
            i for i, m in enumerate(messages)
            if m.get("role") == "assistant"
            and not m.get("_is_fake")
        ]
        if not assistant_idx:
            return messages
        pair_count = min(len(recent), len(assistant_idx))
        to_patch_assistants = assistant_idx[-pair_count:]
        to_patch_thinks = recent[-pair_count:]
        new_messages = list(messages)
        for assistant_index, think in zip(to_patch_assistants, to_patch_thinks):
            m = dict(new_messages[assistant_index])
            # 修剪长 reasoning：保留头尾以保证可读性
            if len(think) <= 600:
                trimmed_think = think
            else:
                trimmed_think = think[:300] + "…（中段省略）…" + think[-300:]
            # 原生 reasoning_content 字段：GLM-5.2 出站时也用这个字段，
            # 入站时会被模型读取进 reasoning context。content 保留不动。
            m["reasoning_content"] = trimmed_think
            new_messages[assistant_index] = m
        return new_messages

    def customize_payload(
        self,
        payload: dict[str, Any],
        *,
        reasoning_config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """GLM：reasoning_effort 字段原生支持（minimal/low/medium/high/xhigh）。"""
        out = dict(payload)
        if reasoning_config and reasoning_config.get("effort"):
            out["reasoning_effort"] = reasoning_config["effort"]
        return out


class GenericOpenAIProvider:
    """通用 OpenAI 兼容家族（gpt-4o / deepseek-chat / qwen / kimi / 本地）

    不认 reasoning_effort 字段——某些严格模式（OpenAI o1）会 400。
    安全做法：丢弃 reasoning_config，让模型按自己默认行为思考。
    DeepSeek-R1 / Qwen-QwQ 内部自带 reasoning（不靠 external effort 控制）。
    """

    name = "generic_openai"

    def extract_reasoning(self, message: Mapping[str, Any]) -> str:
        """大部分 OpenAI 兼容 API 不在 response 里显式带 reasoning；
        DeepSeek-R1 走 reasoning_content 兼容（跟 GLM 一致），尝试取一次。"""
        rc = message.get("reasoning_content")
        if isinstance(rc, str) and rc.strip():
            return rc.strip()
        rc2 = message.get("reasoning")
        if isinstance(rc2, str) and rc2.strip():
            return rc2.strip()
        return ""

    def inject_into_messages(
        self,
        messages: list[dict[str, Any]],
        reasonings: list[str],
        *,
        max_rounds: int = 10,
    ) -> list[dict[str, Any]]:
        """DeepSeek-R1 用 <think></think> 入站（行业标准）。
        其余 gpt-4o 等：reasoning 直接丢（不影响主路径，仅跨轮系延续性差一些）。"""
        if not reasonings:
            return messages
        recent = reasonings[-max_rounds:]
        assistant_idx = [
            i for i, m in enumerate(messages)
            if m.get("role") == "assistant"
            and not m.get("_is_fake")
        ]
        if not assistant_idx:
            return messages
        pair_count = min(len(recent), len(assistant_idx))
        to_patch_assistants = assistant_idx[-pair_count:]
        to_patch_thinks = recent[-pair_count:]
        new_messages = list(messages)
        for ai, think in zip(to_patch_assistants, to_patch_thinks):
            m = dict(new_messages[ai])
            if len(think) <= 600:
                trimmed = think
            else:
                trimmed = think[:300] + "…（中段省略）…" + think[-300:]
            # DeepSeek 兼容 reasoning_content（主流中国模型采用同一字段）
            m["reasoning_content"] = trimmed
            new_messages[ai] = m
        return new_messages

    def customize_payload(
        self,
        payload: dict[str, Any],
        *,
        reasoning_config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """gpt-4o / deepseek / qwen / kimi 等不认 reasoning_effort：丢弃。"""
        return dict(payload)


class OpenAIReasoningProvider(GenericOpenAIProvider):
    """OpenAI o1 / o3 / o4 推理模型家族。

    特点：
      - 支持 reasoning_effort，但值域窄：low / medium / high（不支持 minimal/xhigh）
      - reasoning 出站字段：message.reasoning.summary（不是 reasoning_content）
      - 入站不应拼历史 reasoning（OpenAI 官方建议）
    """

    name = "openai_reasoning"

    def extract_reasoning(self, message: Mapping[str, Any]) -> str:
        """OpenAI o1: 拿 message.reasoning.summary（字符串）。"""
        rs = message.get("reasoning")
        if isinstance(rs, dict):
            summary = rs.get("summary")
        elif isinstance(rs, str):
            summary = rs
        else:
            summary = ""
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
        # fallback 走父类
        return super().extract_reasoning(message)

    def inject_into_messages(self, messages, reasonings, *, max_rounds=10):
        """OpenAI o1: 不要把 reasoning 注入历史 —— 官方建议省略。"""
        return messages

    def customize_payload(
        self,
        payload: dict[str, Any],
        *,
        reasoning_config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """OpenAI o1: reasoning_effort 重映射 GLM 值域 → OpenAI 值域。"""
        out = dict(payload)
        if reasoning_config and reasoning_config.get("effort"):
            effort = reasoning_config["effort"]
            mapping = {
                "minimal": "low",
                "low": "low",
                "medium": "medium",
                "high": "high",
                "xhigh": "high",
            }
            out["reasoning_effort"] = mapping.get(effort, "medium")
        return out


# 简易工厂：按 model name 推断家族。未来接 deepseek/claude 在此加分支。
def resolve_provider(model: str) -> LLMProvider:
    """按 model 名选 provider。未识别时回落 GLM（当前唯一接的家族）。"""
    m = (model or "").lower()
    if "o1" in m or "o3" in m or "o4" in m:
        return OpenAIReasoningProvider()
    if "deepseek" in m or "qwen" in m or "kimi" in m or "moonshot" in m:
        return GenericOpenAIProvider()
    if "claude" in m or "anthropic" in m:
        # TODO: Claude 需要单独 provider（tools 格式 + thinking block + 不同 API endpoint）
        return GenericOpenAIProvider()
    if "gpt-" in m or "openai" in m:
        return GenericOpenAIProvider()
    # glm-* / glm5 / 默认走 GLM
    return GLMProvider()


__all__ = [
    "LLMProvider",
    "GLMProvider",
    "GenericOpenAIProvider",
    "OpenAIReasoningProvider",
    "resolve_provider",
]

