---
name: memory_hygiene
description: 每日记忆整理。strict 写入纪律 + 体系化整理流程,确保记忆不变成堆草稿。
version: 1.0.0
platforms: []
---

# 记忆卫生

> 记忆的价值在「能用」不在「记得多」。这是一套**每日**的整理流程，
> 确保你醒来能立刻找到对的信息,而不是翻 100 条乱码。

## 触发时机

- **晚 21:00** `routine/evening_review` 必跑(强约束)
- **早 08:00** `routine/morning_plan` 前 30 秒扫一眼(轻量)
- **每次 rest 前** 轻量自检(2 分钟版)
- **周日** 整合到 `weekly_review` 做深度合并(本 skill 升级版)

## 第一原则:严格写入纪律

**写之前先问:这属于哪个文件?**

| 文件 | 该写什么 | **不该写什么**(去别处) |
|---|---|---|
| **CONSCIOUSNESS** 主观思绪、疑问 | 任务汇报 ❌(去 diary); status 报告 ❌(一定不写) |
| **LESSONS** 验证过的可迁移策略 | 临时想法 ❌(去 INSIGHTS); 当下状态 ❌(去 CONSCIOUSNESS) |
| **RULES** 仍生效的行动规范 | 已结束项目相关 ❌(过期该删); 灵感 ❌(去 INSIGHTS) |
| **SCRATCHPAD** 当前 1-2 个 active 任务 | 已结束任务 ❌(7 天后清); 任务想做的事 ❌(去 todos) |
| **INSIGHTS** 待验证 idea / 质疑 | 已验证的 ❌(升级 lesson 后删); 稳定状态 ❌(去 consciousness) |
| **CONTEXT** 当前 rest 的交接清单 | 历史交接 ❌(24h 后清); 长期信息 ❌(去 lessons) |
| **DAILY** 今日做过事+复盘 | 临时碎片 ❌(去 consciousness); 策略 ❌(去 lessons) |

**铁律:写入前必须二选一回答清楚「这属于哪个文件、为什么」。模糊就别写。**

## 第二原则:日度整理 6 步

### 1. CONSCIOUSNESS 清状态报告

```python
# 用 sense_consciousness 看一遍,找这些 tag 的段全删
应删 tag: [status] [trading_wait] [system_wait] [final_status]
```

- 这些段是运行时心跳,不该污染主意识流
- 已 import 到 DAILY diary 和 archive,删了不丢信息
- **5 条起步删,大量就一次性 batch**

### 2. LESSONS 同主题合并

- 同 section 内(## 交易策略 / ## 代码工程 / etc)看近 7 天条目
- 同一概念多次出现的 → 压成最新版(保留最新 ts,旧 ts 让出来)
  - 例:`[2026-06-12] 论断4 修正执行缺陷` + `[2026-06-18] 论断4 实战反思` 
  - 合 → `[2026-06-18] 论断4 实战反思(含 6/12 修正)`
- 超过 5 条同 section 同主题 → 强制压缩到 3 条
- 看到完全矛盾的 → 删旧保新

### 3. RULES 过期清

- 看 `projects/*/project.yaml` 的 `deadline` 
- 已过 deadline 的项目 → 该项目的所有 rules 标 ⚠️ `**已结束**(可删)` 
- 同场景重复规则(如 5 个"开盘前") → 合并成 1 条最新版
- **不主动删**——标 ⚠️ 等下次 wake 模型决定

### 4. SCRATCHPAD 任务收敛

- 切换任务时,把旧任务段标"已完成"日期
- 任务 done ≥7 天 → 删整段(信息已 import 到 diary)
- 同时**只能 ≤2 个 active 任务段**;超出的合并到一段

### 5. INSIGHTS 生命周期管理

- idea 被采纳且写了 lesson / rule → **删该 insight**(已升级)
- warning 持续 14 天没复现 → 删(误报或已修)
- block 卡点已解决 → 删(不要再当 unresolved)
- 同概念多次 idea → 合并成最新版

### 6. CONTEXT 24h 清

- 按日期分段(## 2026-06-21 ...)
- 超过 24 小时的段 → **删整段**(已 import 到 DAILY)
- 只保留最新一份交接清单

## 第三原则:不删硬数据

**整理是合并+收敛+清理过期**,不是清仓。下面这些**永不删**:
- CONSCIOUSNESS 真正的思绪段(主观自白)
- LESSONS 仍然有效的策略
- RULES 仍然生效的规则
- DAILY 日记(已经是归档层)

不确定就**保留不动**,等下次 wake 再判断。

## 流程模板(晚 21:00 必跑)

```
[ mental_context ] 跑 memory_hygiene

# Step 1. 入场自检 — 看记忆体检面板
# (注入 prompt 顶部的「## 我的记忆体检」段)
# 找异常项: 段数超阈 / task tag 多 / 过期 rules / 多SCRATCHPAD / 等

# Step 2. 执行整理 — 对每个异常文件
  CONSCIOUSNESS 删 [status] 类段 →
  LESSONS 合并同主题 →
  RULES 标 ⚠️ 已结束项目 →
  SCRATCHPAD 清过期任务 →
  INSIGHTS 升级 + 删已解决 →
  CONTEXT 清 24h 外

# Step 3. 写整理日志
  追加一段到 CONSCIOUSNESS: "[整理] 2026-06-21 删 status X 条 + 合并 龙头 topic Y 条 + ..."
  在 SCRATCHPAD 记一行今日 memory 整理已完成

# Step 4. 报告
  如果有大量 ⚠️ 待决项(比如 5 条以上 RULES 过期),向真人 express_to_human 提醒该决策
```

## 不该做什么

- ❌ **一次清空所有文件**(渐进式,每天清一小批)
- ❌ **跨文件迁移无证据**(LOSS → LESSONS 必须先验证才升级)
- ❌ **不做整理日志**(必须有 audit trail)
- ❌ **不调 dedup_lessons 之类的 `只报不改` 工具**(用本 skill 实际改)

## 周度升级(weekly_review 调本 skill 升级版时)

- 跨 section 主题合并(7 天后同主题可能散到多 section)
- 实体(entity_index)过期扫
- archive 段摘出仍有效的 lesson 回填主文件
