---
name: memory_hygiene
description: 每日记忆整理。梦境式的内部清理 + 合并 + 收敛,保持记忆系统「能用」而非「堆着」。
version: 1.0.0
platforms: []
---

# 记忆卫生

> 记忆的价值在「能用」不在「记得多」。一份待清理的意识流里 30 个 status tag,
> 没用,只在让真正想看的思绪被淹没。

这是**长期记忆卫生纪律**,每晚触发一次,把当天的累积整理回「下次醒来能用」的状态。

## 何时触发

- 每晚 **23:00** `routine/night_dream` —— 唯一强约束触发点
- 周日 23:00 同作息升级为「周度版」(深入跨 section / 周度回顾)
- 不在白天的任何 wake 跑(memory_hygiene 是「睡眠中的整理」,不是 nova 工作时段的事)

## 它不做什么

- **不响应外部消息** —— dream 是内部 wake,真人在飞书发消息你静默
- **不开项目代码协作** —— alpha 派任务来你不收
- **不做决策 / 不汇报真人** —— express_to_human 在 dream 模式下被禁用
- **不轻整理**:每次必把记忆体检面板的 ⚠ 项处理掉至少一半(不能写"今天状态还行, rest 了")
- **不为 action 计数收尾**:之前若 sleep 因 token 耗光系统中断, 本作息仍要拉回做完
- **一次性不该跨 200K token**: dream 是轻量的(理想 ≤50K),不烧钱

## 思考骨架

### 0. 入场(2 turn)

1. 调 `sense_vitals` 看能量。能量 < 30 时,跳到第 7 步只做最小整理(清 status / 清 SCRATCHPAD) + rest。
2. 调 `skill_view memory_hygiene` 加载本方法论(自身)。

### 1. 看体检面板(prompt 顶部已有的「## 记忆体检」段)

不重新跑 sense,直接看 prompt 上「## 记忆体检」段的 ⚠ 列表。这是今晚要处理的 backlog:
- 哪些文件超阈?
- 是不是至少 3 项 ⚠?是多就该集中处理

**判断标准**:
| ⚠ 类别 | 处理优先级 |
|---|---|
| 意识流 status 报告 ≥ 5 | P0 必清(机械可删) |
| SCRATCHPAD 并行任务 ≥ 3 | P0 必清(看你今天到底在干什么) |
| LESSONS 某 section > 25 | P1 合并(嗅觉真心思考) |
| INSIGHTS > 30 总数 | P1 升级/删(个别判断) |
| 某文件 7 天没动 | P2 标注(不强制删) |
| RULES > 40 节 | P2 看哪些项目死了 |

只跑一项 P0/P1 是不够的,至少把 P0 全处理完。

### 2. CONSCIOUSNESS 清 status 报告(机械:30 秒)

**做什么**: 删意识流主文件里所有 status 类 tag 段,这些是运行时心跳、不该污染主观意识流。

**工具**: 走 `terminal` 工具直接改文件(没有专用 delete_thought):
```bash
# 备份 → 用 sed/python 删 status 段
```

具体段标签(出现就删整段):
- `[status]`
- `[trading_wait]` / `[system_wait]` / `[final_status]`
- 任何 `[xxx_wait]` 模式

**注意**:
- 这些 tag 的内容**已 import 到 DAILY.md / archive**, 删主文件不丢信息
- 不删「主观思绪段」。判断标准:段是「我现在在想什么,有什么感觉」(主观) vs「我完成了 X,状态 Y」(运行时主观,该删)
- 边界模糊的段保留(不误删)

**完成定义**:
- status 类 tag 总数 = 0(或 ≤ 2,容错)
- 配分:**意识流主文件 + archive 都不应该再有 > 5 个 status**

**反模式**:
- ❌ 删了文件没留 audit trail(consciousness 里要留 [整理] tag 记录改了什么)
- ❌ 把 record_thought(status) 误删 — 那是当下 active 的运行时信息

### 3. LESSONS 同主题合并(嗅觉:300 秒)

**做什么**: 在 LESSONS.md 内某一 section, 把多次写的同一理念压成最新版本。

**怎么判断"同一理念"**:
- 关键词重叠(论断4 → 涨停次日 → 实战 反思 → 修正执行)
- 主题一致:不是「时间相近」或「section 相同」
- 老 ts 没新信息(新版本已包含了老版本所有结论)

**工具**:
1. 调 `dedup_lessons` 看系统自动报告相似度 > 0.7 的对(只报不并)
2. 自己读那些建议对,**核对语义**(机械相似度会误判)
3. 真要合并的话用 `terminal` 写回主文件:
   ```
   [YYYY-MM-DD HH:MM] 【新表】包含了旧版 X 条结论:...
   ```
4. 删原条目

**完成定义**:
- 同 section 同主题最多 3 条(超就收)
- 长 section(trading 72 条)收 ≤ 30 条(机械 + 语义混合)

**反模式**:
- ❌ 跨 section 合并 — trading 教训绝不能合到 system section
- ❌ 因为 sim > 0.72 系统说相似就合 — 看 ts 6/12 vs ts 6/18 内容含义,可能恰好相反
- ❌ 删整个 section 「交易策略」只留 3 条 — 收 ≠ 抹

### 4. RULES 过期标注(看项目死活)

**做什么**: 找出"已结束项目"对应的 rules,标 ⚠️ 不删,等下次 wake 模型决定。

**判断标准**: 看 `projects/<pid>/project.yaml` 的 `goal.deadline`:
- deadline < 今天 且项目 status != active → 项目结束
- 该 projects/<pid>/positions 里所有 position 的 rules 都标过期

**工具**: `terminal` 直接 read projects/<pid>/project.yaml + project rules 段; 然后回 RULES.md 用 `update_rules` 改场景名加 ⚠️ 前缀。

**完成定义**:
- 已结束 rules 加 `**已结束**(可删)` 前缀;
- 同场景重复 rules 5 条 → 合 1 条(`update_rules` 用 replace mode 自动按场景去重)

**反模式**:
- ❌ 主动删 rules(没用户拍板,有风险)
- ❌ 把 ⚠️ 加到仍生效 rules

### 5. SCRATCHPAD 收敛(纪律:60 秒)

**做什么**: 草稿本oría 「我正在做什么 1-2 个事」。 把已 done 任务 7 天后删,只留 active。

**工具**:
- `update_scratchpad(mode=replace)` 一次性覆写整盘,只保留 active 段
- 历史 SCRATCHPAD 内容已 import 到 DAILY.md,删了不丢

**完成定义**:
- ≤ 2 个 ## 段(并行任务)
- 每段 < 500 字
- 已 done ≥ 7 天的任务段全删

### 6. INSIGHTS 升级与清理(判断:120 秒)

INSIGHTS 没有专用 update/delete 工具, 走 `terminal` 改文件。

**规则**:
- idea 已被采纳且写了对应 `add_lesson` → **删**该 insight(升级完不再原位存)
- warning 持续 14 天没复现 → **删**(误报或已修复)
- block **已解决** (下个 wake 已经能解决卡点) → **删** 别再当 unresolved
- 同概念多个 idea → 合并最新版

**工具**: `terminal` 直接 read INSIGHTS.md + 删除目标段 + write 回去。

**完成定义**:
- 总 entry 数 ≤ 30
- 没有 kind=block 的 ages > 7 天 entry (解决了或转化为 sense_*-based 任务)
- 加 `[整理]` 注释一行说明今天删了哪些

**反模式**:
- ❌ 把「有用 idea」误删 — INSIGHTS 是长期资产,删前必看
- ❌ 把 idea 转 lesson 没验证就迁 — 一定要先 self_review 验证

### 7. CONTEXT 24h 清(机械:30 秒)

CONTEXT.md 仅作为「下一个 rest 的交接清单」存在。每晚必清。

**做什么**: 删掉所有「日期段 ## YYYY-MM-DD」中**超过 24 小时**的段。

**工具**:
- `update_context` 工具用 mode=replace 写回最新版
- 或 `terminal` 直接改

**完成定义**:
- 只保留最近 24 小时的清单
- 文件总长 < 2000 字

### 8. 写 [整理] audit trail(必做)

整理全做完,在 CONSCIOUSNESS.md 顶部 record_thought 一行(用 `record_thought(kind=status)`):

```
[整理] 2026-06-21 23:30
  - 清意识流 28 条 status → 0
  - 合论断 4 段 11 条 → 3 条
  - 删 INSIGHTS 5 个 block + 升级 2 个 idea 为 lesson
  - SCRATCHPAD 4 段 → 2 段
  - CONTEXT 清 6/18 / 6/19 段
下次醒来应在「## 记忆体检」段看到 ✓ 记忆状态健康。
```

这是 audit trail,模型内部记忆的「今天 dream 干了什么」。

### 9. 收口

- 调 `sense_vitals` 看剩余能量
- 不调 express_to_human(内部 wake 禁用)
- rest 到明早 morning_plan 时间

## 周度(weekly_review 同一天 23:00)额外做

周日 night_dream 在 1-9 步基础上加:
- **跨 section 合并**:同主题可能散在多 section(比如「论断4」可能在 trading + workflow 同时出现)
- **entity_index 过期扫**: 30 天没出现在 wake context 的实体 = dead, **手动 prune**(用 `prune_fragments_for_entity` 工具)
- **archive 回填**: CONSCIOUSNESS.archive.md 里仍 active 的 lesson 可回填到 LESSONS.md 主文件,重新生效

## Template(可选直接抄)

```
[turn 1] skill_view memory_hygiene + sense_vitals
[turn 2] 读 prompt「## 记忆体检」段, 列出今晚 backlog
[turn 3] 处理 P0 (status / SCRATCHPAD) — 用 terminal / update_scratchpad
[turn 4] 处理 P1 (LESSONS 合并 / INSIGHTS 升级) — terminal
[turn 5] 处理 P2 (RULES 标 ⚠️ / 文件 mtime 警告) — update_rules
[turn 6] record_thought(kind=status) 写 [整理] audit trail
[turn 7-8] 收口, sense_vitals, rest 明早 morning_plan
```

理想 8-10 个 turn, 30K-50K token 上下,**不超过 200K**(否则超 dream 预算)。

## 反模式

1. **「今天没大问题就 rest 了」**: 即使体检 ✓ 健康,也至少跑一遍机械步骤(CONSCIOUSNESS status / SCRATCHPAD),因为总有几条今天新加的
2. **「修了一半说够了」**: backlog 必清一半以上, 不能写「23:30 累了 rest」不动
3. **「删了文件没 audit」**: 必写 [整理] tag 记录
4. **「调 dedup_lessons 完就 sleep 了」**: 它只报不改, 必须自己 terminal 写回去
5. **「在 21:00 evening_review 也跑」**: 复盘和整理不是一回事, 不要在白天跑本 skill
6. **「INSIGHTS → LESSONS 不验证就迁」**: 升级必须先有 add_lesson 真写了, 才能删 INSIGHTS
7. **「RULES 主动删过期」**: 只标 ⚠️, 删要让人 / 下次手动 wake 确认

## 失败兜底

如果 terminal 改文件失败 / token 超预算 / 突然异常:
- **不要写「上次 status 不清就算了」** — 必 record_thought 留错误信息
- 调 `rest` 时把 mental_context 写明「memory_hygiene 未完成, P0 段已清, P1 未清」
- 下次 morning_plan 看到记忆体检仍 ⚠️ 时优先把未清的做完
