"""LLM provider adapter — 模型知识的唯一家园，agent.py 不识别具体模型。

每个模型家族出站 reasoning 的字段名不同、入站把 reasoning 拼回去的方式也不同：
  GLM-4.5/4.6/5/5.2  出站 message.reasoning_content
                     入站：GLM-5.2 实测会读取 reasoning_content 字段并投入
                     reasoning context（2026-06 "789 数字"实验：含 reasoning_content
                     的历史 assistant message 入站后，模型能正确回忆）。
                     GLM-5 时代（旧）静默忽略 → 用 markdown 引用块 hack；
                     5.2 已解除限制，用原生 reasoning_content 字段。

  DeepSeek-R1     出站 message.reasoning_content；入站用 <think></think> 是行业标准
  OpenAI o1/o3    出站 message.reasoning.summary；reasoning 不应入站
  Claude thinking 出站 thinking block；可作为 thinking block 传回

抽象两端口：
  extract_reasoning(message_dict) -> str         出站：从响应 message 拿 reasoning 文本
  inject_into_messages(messages, reasonings)     入站：把上 N 轮 reasoning 注入到
                                                  对应 assistant message 的 reasoning_content 字段
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
        """把最近 N 轮 reasoning 就地拼回到对应 assistant message 的 content。

        每个 provider 管自己的入站语义（GLM/DeepSeek 用 <think></think> 拼到 content；
        Claude 用独立 thinking block；OpenAI-R1 不拼）。
        返回的是 messages 的副本（不修改入参），可安全替换。
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


# 简易工厂：按 model name 推断家族。未来接 deepseek/claude 在此加分支。
def resolve_provider(model: str) -> LLMProvider:
    """按 model 名选 provider。未识别时回落 GLM（当前唯一接的家族）。"""
    m = (model or "").lower()
    if "deepseek" in m:
        # 同 R1 系：<think></think> 入站行业约定，行为与 GLM 等同
        return GLMProvider()
    if "claude" in m or "anthropic" in m:
        # TODO: Claude thinking block 形态不同，单独实现。
        return GLMProvider()
    if "o1" in m or "o3" in m or "o4" in m:
        # TODO: OpenAI reasoning 模型，summary 字段提取 + 入站不拼。
        return GLMProvider()
    # glm-* / glm5 / 默认走 GLM
    return GLMProvider()


__all__ = ["LLMProvider", "GLMProvider", "resolve_provider"]

