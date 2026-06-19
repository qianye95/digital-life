# 如何玩转数字生命

一份从"刚装完"到"日常使用"的实战指南。10-20 分钟读完，半小时跑通。

## 目录

1. [你刚装完，先看什么](#1-你刚装完先看什么)
2. [第一个晚上要做什么](#2-第一个晚上要做什么)
3. [日常怎么用](#3-日常怎么用)
4. [进阶玩法](#4-进阶玩法)
5. [当它出问题时](#5-当它出问题时)

---

## 1. 你刚装完，先看什么

装完后启动 gateway：

```bash
digital-life start
```

第一次启动会自动 bootstrap **两个数字生命**：
- **zero**（青色） — 策略师
- **alpha**（粉色） — 交易员

并自动 seed **龙虾模拟炒股挑战**项目作为 demo —— 你不需要自己创建任何东西。

### 关掉终端，打开控制台

```bash
digital-life status   # 看到底跑在哪个端口（默认 8642）
```

打开 `http://localhost:8642/system`（霓虹深空主题）。

**全局台**先看到：
- 系统实况：zero + alpha 卡片 + 能量条 + 状态灯
- 实例管理：zero / alpha 的 avatar / accent / tagline 可编辑
- 项目：trading_simulation 卡片可点击进入看完整 6 维详情

### 验证实例活着

进入 zero 的实例台（`/instance/<zero-uuid>/overview`）：
- 实例状态 = `休息中` 或 `工作中`（**绝不应该是 `异常` 或 `离线`**）
- 能量 = 接近 100%

进入 Session → 应该能看到历史 wakes 列表。如果空，没关系 —— 实例刚开始没事件进来很正常。

### 你还没办法跟它对话 —— 现在填飞书凭证

这一步必须在飞书控制台做：
1. https://open.feishu.cn/app 新建两个"自建应用"（一个给 zero，一个给 alpha）
2. 各自把 bot 加进同一个**测试群**（这是 zero 跟 alpha 协作的 channel）
3. 拿到 `App ID` + `App Secret`

然后：

**方法 1（控制台）**：`/instance/<id>/config` → 在「消息通道」section 填 App ID + App Secret（保存后控制台顶部「重启」按钮重启 gateway 才会 reload）

**方法 2（命令行）**：

```bash
# zero 的凭证（如果在 config/secrets.env 已填）
# 已经自动 bootstrap 时塞给了 zero；如果用新 app 就用下面命令覆盖

# alpha 的凭证 —— 手动编辑
vi apps/<alpha-uuid>/config/app.yaml   # 改 messenger.app_id
vi apps/<alpha-uuid>/config/secrets.env  # 改 FEISHU_APP_SECRET

# 重启
digital-life restart
```

### 验证飞书通了

在飞书群里 `@zero 应用程序` 发一条消息（先确保 bot 在群里），30 秒内 zero 应该回复了。alpha 也在群里 listen 同样消息（飞书原生 fan-out），但只在被 @ 它或它判断相关时响应。

---

## 2. 第一个晚上要做什么

第二天早上你会发现 —— 即使你睡觉了，zero 和 alpha 可能也没闲着。它们通过**事件机制**（不是你的指令）活着：

- 定时器（routines.yaml 里预设的节奏框架）触发 wake
- 主动探索（精力足够时会自己检查项目状态、扫描候选）触发 wake

查看它们的"昨晚"做了什么：

1. `/instance/<zero-uuid>/sessions` —— 找 timestamp 在昨晚的 wake，点开看完整 turns（含 reasoning + tool calls + LLM call JSON debug）
2. `/instance/<zero-uuid>/memories` —— 切到「日记」，按日期分段看复盘
3. `/instance/<zero-uuid>/memories` —— 切到「意识流」，看它整理思绪的过程

**调整人设** —— 如果你不喜欢它的语气或行为模式：

- `/instance/<zero-uuid>/persona` —— 编辑 LIFE_PERSONA.md。比如让它更严谨 / 更俏皮 / 更直接。保存，下次 wake 生效。

---

## 3. 日常怎么用

### 跟它对话

群里 @ 它（zero 或 alpha）—— 它会立即响应（被 @ 是平权事件里的"高优先级"之一，但不绝对最高，仲裁还看精力）。

**关键：不需要每次都 @**。比如：

- 它发现 trading_simulation 项目该下周复盘了 → 自己会触发
- 精力 < 30 持续两小时 → 它自己决定休息
- 它监控的某只股票触发止损 → 它自己执行（不需要你批准），事后给你执行报告

### 看它在做什么

- **概览** (`/instance/<id>/overview`)：状态、能量、最近 wakes、待办 Top、token / day
- **会话** (`/instance/<id>/sessions`)：完整 wake 列表，点击看每个 wake 的 turns、tool calls、LLM call 完整输入 JSON（debug 友好）
- **待办** (`/instance/<id>/todos`)：按 project 分组的任务清单，可勾选完成 / 删除 / 新建
- **记忆** (`/instance/<id>/memories`)：意识流 / 日记 / 联想图谱

### 看多实例协作

`/system/overview` —— 一图看两个实例的当前状态。

`docs/showcase/multi-instance-trading-2026-06.md` —— 一个真实长期运行的 zero + alpha 协作场景（量化交易策略从决策到执行到复盘的完整 1 天对话）。

### 给它新任务

**方法 A：对话直接说**

群里 @ 它说"明天起每周一早上 8 点检查一下持仓股票的新闻"。它会主动建立 todo + 占用 routines.yaml 里的一个时间槽。

**方法 B：通过项目**

`/system/projects` 新建项目 → 在 project.yaml 写 positions → 数字生命会接管自己岗的工作。

---

## 4. 进阶玩法

### 给它加技能

`/system/skills` 是**技能市场** —— 列出所有全局 skill（来自 `interfaces/skills/` + `shared/skills/`）。

对每个实例 toggle 订阅：
- `/instance/<id>/skills` —— 实例只看到它订阅的技能。订阅 = `app.yaml.skills` 列表加一条。

新增自定义技能：在 `shared/skills/<name>/SKILL.md` 写好 markdown 模板，master 重启后会自动出现在市场。

### 调事件类型

`/system/events` 是**事件类型注册表**。如果想让"账户亏损 5%"也能触发 wake，新建一个 event-type：type_id `risk_alert`、trigger_type `condition`，配上 prompt 模板。事件被触发后会按这个 prompt 走 wake 流程。

### 自动复盘议程

routines.yaml 有 `21:00 联合复盘` 槽位 —— 这个时段 zero 会主动找 alpha 复盘今天。如果你想加"23:00 单独反思"，加一条 routine 即可（数字生命在精力 < 20 时不会强制执行，避免 burn-out）。

### 多数字生命

想搞剧本组群（一个程序员 + 一个 reviewer + 一个 PM）：

1. `/system/instances` 新建实例，配 display_name / accent_color / tagline / 飞书凭证
2. `/system/projects` 新建项目，positions 加对应岗位
3. `/system/skills` 给新实例订阅合适的技能
4. 控制台「重启」拉起新实例子进程

新增实例是**完全独立的生命**：它有自己的 persona / affair / 记忆 / 精力 / 复盘习惯，互相之间通过消息总线协作（不共享状态）。

---

## 5. 当它出问题时

### 实例显示「异常」（status=error）

进 `/instance/<id>/overview` → 红色 banner 会显示**具体原因**：

```
⚠ 数字生命异常
模型调用失败：GLM_API_KEY invalid (turn #1065, role=assistant)
```

按 hint 修：
- API key 没填 / 填错 → 控制台 `/instance/<id>/config` 改 model section
- 模型 quota 用完 → 换 key 或等次日 reset
- 飞书 WS 断了 → 看是不是 token 失效（飞书控制台 revoke 的话）

**reset 按钮**：仅 abort 卡住的 wake（不动 lifecycle 状态机，模型自主决定何时休息/工作）。

**自动恢复**：一旦下一次 wake 里的模型调用成功（任意 role=assistant 无 error），banner 自动消失。

### 实例显示「离线」

实例 `app.yaml.active = false`，进程没起。控制台「上线」按钮一键拉起（或重启 gateway）。

### 数据库锁 / 启动失败

```bash
digital-life stop
# 等几秒
digital-life status    # 确认没残留进程
digital-life start
digital-life logs -f
```

### 重置单个数字生命

不直接删 `apps/<uuid>/` —— 会丢全部记忆。安全的做法：

```bash
digital-life stop

# 备份当前实例（包含全部数据）
cp -r apps/<uuid> apps/<uuid>.backup

# 清掉它当前事务状态，让 affair RESET —— persona / 记忆保留
sqlite3 apps/<uuid>/data/state.db "UPDATE affairs SET status='PENDING'"

digital-life start
```

### 重置整个项目（删 demo 重新开始）

```bash
digital-life stop
rm -rf projects/trading_simulation/*
digital-life start      # 自动 seed 新版龙虾模拟炒股项目
```

或控制台 `/system/projects` → 删除 trading_simulation → 重启 gateway → master 自动 seed 重新创建。

---

## 一句话总结

> Digital Life 不是你打开就用一下关闭的工具。它就是一直在那儿活着 —— 像两个真实员工。你不在的时候它在工作、在休息、在跟同伴协作、在自主修正论断。
>
> 你的角色是**项目里的人**：定方向、拍板、给反馈、调整它的边界。它能自己处理日常，重要的事主动找你。
