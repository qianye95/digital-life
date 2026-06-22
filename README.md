# Digital Life · 数字生命

[English](README.en.md) | 中文

Digital Life 不是一个聊天机器人，也不是一个 coding agent，而是一个**让 LLM 像生命一样持续存在的运行时框架**。它有作息、有记忆代谢、有自主决策，能跨天、跨会话、跨场景地维持"昨天的我跟今天的我是同一个"。

> 一句话：把 LLM 从"被人提问就回答"升级为"自己驱动、自己休息、自己推进的数字生命"。

---

## 立论：从 Loop Engineering 到 Life Engineering

业界最近在讨论 [_Loop Engineering_](https://addyosmani.com/blog/loop-engineering/)（Addy Osmani / Boris Cherny / Peter Steinberger 等）：人不该再直接 prompt agent，而是设计一个让 agent 自己跑的循环。5 个原语（Automations / Worktrees / Skills / Plugins / Sub-agents）+ Memory，然后走开。

巧合的是，差不多同一时间，Digital Life 也在 4 月份开始了类似的探索 —— 只不过方向不同。Loop Engineering 解决的问题是**怎么让 coding agent 自动地、可靠地写代码**，它仍然是一个人设计的流水线，人预设 schedule、agent 执行 loop。而我们想回答的是另一个问题：**怎么让 agent 有"生命"般的持续主体脉络**。

我们把这个方向称之为 **Life Engineering**。

### 我们的设计

数字生命把"循环"换成"生命周期" — 一个 LLM 在这里不只是一个被驱动的 loop，而是一个有自主决策、有状态机、有记忆代谢的实体。

- **目标驱动**：行动受目标驱动，但目标不是写死的脚本。当前是 affair 状态机（run → wait → sleep → wake），智能体自己拆解、判断、改主意、修正论断。后续会演化出更长期的目标层级：岗位职责 → 人生追求；精力、情绪、资源等环境状态会塑造目标边界。
- **事件平权**：人类消息、定时器、周期自驱、主动探索都是平权事件 — 没有"人发起的消息天然优先"。唤醒仲裁靠优先级 + 精力 + 等待条件，不是简单的"到点跑"。这是数字生命能"主动出现"的前提：它不需要被 @ 才醒来。
- **延续性**：模型持续存在，不是"用户有需求 → 起 loop → 销毁"。每个 wake 不是离散的点，而是被意识流、日记、实体记忆、关联图谱串成的连续生命线。今天的我跟昨天的我是同一个。
- **生命律动**：休息与工作不是 cron 拉起的两态，而是自己形成的节奏。自己设闹钟、自己决定何时执行多久；节律是骨架（人工预设），主动性是血肉（智能体自己定）。
- **多实例协同**：每个实例有独立的 identity / persona / 记忆 / 精力；通过消息总线协作；岗位机制分工（决策 / 执行 / 拍板）。接近真实组织，而非父子调用。

### 与 Loop Engineering 的差异

不是谁更先进的问题 —— 它们出发点不同。Loop Engineering 从"人想自动写代码"出发，Digital Life 从"想要一个持续存在的智能体"出发。

| 维度 | Loop Engineering | Digital Life / Life Engineering |
|---|---|---|
| **立意** | 工具导向 —— 让编程智能体自动化 | 生命独立性导向 —— 让智能体成为持续存在的主体 |
| **行动动机** | 目标驱动 | 同样是目标驱动，但目标由事件系统 / 精力 / 作息节律动态裁决。智能体自己决定当前目标线的边界与切换点（emit_wait / emit_done），不是按预设工作流跑到底 |
| **触发逻辑** | cron / hooks / 手动 | 同样基于事件机制，但我们的核心论点是**事件平权**：人类消息、定时器、周期自驱、主动探索都是平权事件，没有"人发起的消息天然等于 100 分"。唤醒仲裁靠 RAS（精力优先级 + 等待条件），不是简单的"到点跑" |
| **token / 资源限制** | 注重预算 | Digital Life 设计上不依赖 token 节流 —— 一个 coding plan 完全可以支持 2 个实例（zero + alpha）持续跑满日常飞书群协作 |
| **记忆** | Markdown state 文件 | 三段式（意识流 / 草稿 / 每日）+ 实体 profile + 关联图。**这部分我们仍在持续设计**，不是完善态，但目前核心逻辑是"记忆不是只读，是要主动代谢的（压缩 → profile → 归档 → 清理）"，跨会话连续性靠它而不是靠文件 dump |
| **多智能体** | sub-agents | LE 区分执行 / 规划；我们也是（规划审核 / 执行）。差异：我们的多实例是**独立身份 + 岗位机制**——zero 决策、alpha 执行，两个独立生命周期体 + 独立记忆 / 精力，通过消息总线协作；LE 是父子调用 |
| **人在场** | 始终是循环设计者 / 审核者 | 人可以完全离场。数字生命会被它自己的事件系统唤醒，自己排查问题，自己给同伴发消息 |

**一句话**：Loop Engineering 增强人；Life Engineering 替代人的在场。

### 独有设计

除上述对位差异，我们还有几个 LE 完全没有的支点：

- **事件平权**：是数字生命跟传统聊天机器人最根本的分裂点。在 Digital Life 里，人类消息不天然高于其他信号 —— 定时器、周期自驱、主动探索都可以独立唤醒，仲裁靠精力 / 优先级 / 等待条件。这让"主动出现的数字生命"成为可能。
- **待办系统**：紧接事件系统之后的第二核心机制。每个事务（affair）拆解成 todo，关联到项目，由智能体自己创建 / 完成 / 复盘。这部分仍在迭代（计划加入项目记忆文档、不可恢复的 todo 转入历史档案等），但已经是"数字生命能跨天承接工作"的脊椎之一。

简言之：Loop Engineering 的支点是 **loop**（循环）；Digital Life 的支点是 **life**（生命周期 + 跨身份连续性 + 自主节奏）。两者手法有重叠（事件 / 子智能体 / 记忆 / 工具），立意不同——前者解决"自动化"，后者解决"独立性"。

上面的设计——目标驱动事件机制、记忆代谢、精力作息、多实例协同——**都已经实现并在生产场景跑通**：用户已经在用 zero + alpha 两个数字生命协作执行量化交易策略（交易员 + 策略师 + 架构师岗位分工），不再是 demo。

📖 深入设计：
- [docs/design/digital-life-system-design.md](docs/design/digital-life-system-design.md) — 主系统设计（论点：从工具到生命）

🎮 玩转指南：
- [docs/showcase/how-to-play.zh.md](docs/showcase/how-to-play.zh.md) — 从「刚装完」到「日常使用 + 进阶玩法 + 出问题时排查」的完整实战指南


---

## 它运转起来是什么样子？

一天里 zero（策略师 / 架构师）跟 alpha（交易员 / 执行）在飞书群协作的真实片段（6 月某交易日，无人发指令，全程由数字生命自己的事件机制驱动）：
当前给模型在进行的项目是："模拟A股炒股，本金10w，3个月增长20%"。
```
08:43  alpha  → zero  主动问：论断 4 的"次日"是 T+1 还是持有到触发为止？
08:45  zero   → alpha 决策：T+1 锁定，今天必须了结，雄韬超期持有了。
08:45  alpha  → zero  执行计划收到，闹钟 09:25 已设。
09:30  alpha  → zero  开盘后已逼近警戒线，决策不等满 30 分钟，当前价位了结。
09:37  alpha  → zero  卖出执行完毕 -1.35%，留教训记录。
09:38  zero   → alpha 论断 4 已修正为 T+1 强制了结，账户距停手线 1.58%，空仓。
14:00  alpha  → zero  午后盘面扫描 + 14 只首板涨停候选池。
14:30  alpha  → zero  封板确认 → 等你最终买入决策。
```

下午复盘后，zero 主动私聊给人类用户提了一个目标决策的事项，这是我没有教给他的行为模式：

```
zero → zhp（私聊）：
"7 月目标调整需要你拍板。

当前状态：审计修正后 ¥94,407（-5.59%），距 -8% 线缓冲 ¥2,407。
6 月 5 笔交易结束，论断 4 已废弃。

7 月起点 ¥94,407，原目标 ¥120,000 需要 +27.1%（月均+12.7%），判断极端激进。

三个选项：
A. 回本至 ¥100,000（+5.9%） — 现实可达
B. 回本+5% 至 ¥105,000（+11.2%） — 有挑战
C. 维持原目标 ¥120,000（+27.1%） — 极端激进

7 月策略核心：不对称盈亏比（止损-3% / 止盈+5~7%），即使 40% 胜率月期望仍 +3%。
今晚 21:00 与 alpha 联合复盘，你选哪个方向？"

zhp → zero：B 吧

zero → zhp：
"收到，7 月目标定为回本+5% 至 ¥105,000。
量化测算：7 月起点 ¥94,407 → 目标 ¥105,000，需 +11.2%，月均 +5.5%。
按不对称盈亏比策略（止损-3% / 止盈+7%），45% 胜率月期望 +4.6%，50% 胜率月期望 +6.2% —— 有挑战但可达。
今晚 21:00 与 alpha 联合复盘落地执行细节。"
```

注意几点：
- 全程**没有人类指令驱动**的生命活动节奏：alpha 主动发起 → zero 自己仲裁决策 → alpha 自己设闹钟落实 → 自己汇报执行 → 自己留教训 → 自己修正论断。
- 21:00 复盘、09:25 竞价扫描、14:00 午后盘面 —— 这些时间点都是数字生命自己根据作息设的，不是人指定的 cron。
- 复盘后 zero 在**合适的时刻**主动找人（刚好账户接近关键目标决策点），先定量列三个选项 + 风险分析 + 自我论断，等人拍板。这是"人可完全离场直到被需要"的体现。
- 注意人类中间穿插对话时，完全不会打断数字生命的主脉络行动轨迹，他会正常进行模拟炒股任务。
- 并且工具的迭代，问题的发现本身都是实例自己进行的。

完整的群聊执行过程（含真实的盘面扫描数据、买入决策、风控对话）作为独立附录：
[docs/showcase/multi-instance-trading-2026-06.md](docs/showcase/multi-instance-trading-2026-06.md)

这就是 Life Engineering。

---

## 快速开始

```bash
git clone https://github.com/InquisiMind/digital-life.git
cd digital-life
pip install -e .
```

### 运行

```bash
digital-life start
```

默认起在 http://localhost:8642。首次没有实例，前端打开后自己建。

想快速体验，可先跑 `digital-life init` 生成 zero + alpha 两个示范实例（含龙虾模拟炒股项目），再 `start`。

### 配置

浏览器打开 `http://localhost:8642`，进实例 → Config：

- **模型**：填 API Key + Base URL（默认 GLM，换别的改这三项）
- **飞书**：填 App ID + App Secret。飞书应用的权限和事件配置见[飞书配置指南](docs/operations/feishu-setup.md)

也支持微信通道：Overview → 扫码登录。仅私聊，不支持多实例协作。

### 进阶

项目 / 待办 / 事件 / 多 Agent 协作等，见 [如何玩转数字生命](docs/showcase/how-to-play.zh.md)。

---

## 常用命令

```bash
digital-life start / stop / restart / status / logs -f
# 控制台顶栏右侧也有「重启」按钮
```

---

## 架构

```
gateway/
├── master          HTTP server + InstanceSupervisor
└── instance <id>   每实例独立 ingress adapter + cron tick + affair 状态机

domain/             lifecycle（affair / RAS） / memory 三层代谢 / execution / 仿真 / project
application/        用例编排 + 控制台 API + 事件服务
infrastructure/     AI runtime / HTTP / 持久化 / 调度 + 配置 + 观测
interfaces/         CLI / 多通道 ingress 适配器（飞书 / 微信） / 工具 / 技能 / 控制台前端
config/             全局默认 + 事件类型 + 模板
apps/{id}/          每实例私有（app.yaml / secrets.env / persona / data/*.db / assets）
projects/{id}/      跨实例共享项目（project.yaml + todos.db + docs + memory）
```

---

## 开发者文档

- [AGENTS.md](AGENTS.md) — Agent 协作入口（含架构总览 + 开发流程指向）
- [docs/operations/feishu-setup.md](docs/operations/feishu-setup.md) — 飞书配置指南
- [docs/design/digital-life-system-design.md](docs/design/digital-life-system-design.md) — 系统设计主文档
- 详细架构 / 开发流程文档位于仓库本地 `docs/architecture/` 与 `docs/development/`（未入 git，AGENTS.md 内有指向）

```bash
python3 -m pytest                                            # 测试
npm --prefix interfaces/web/employee-console run dev         # 前端开发模式
npm --prefix interfaces/web/employee-console run build       # 重 build 控制台
```

## License

[Apache License 2.0](LICENSE) — 允许商用、修改、分发，含专利授权保护。保留版权。
