# Digital Life

[中文](README.md) | English

Digital Life is a **runtime framework for LLM-based digital beings that persist over time**. It is not a chatbot, nor a coding agent — it is a system where an LLM has a lifecycle, memory metabolism, and autonomous decision-making, capable of maintaining "the same entity from yesterday to today" across sessions, days, and scenes.

> In one sentence: upgrade an LLM from "responds when asked" to "a self-driven digital life that rests, acts, and iterates on its own."

---

## Thesis: From Loop Engineering to Life Engineering

The industry recently started discussing [_Loop Engineering_](https://addyosmani.com/blog/loop-engineering/) (Addy Osmani / Boris Cherny / Peter Steinberger): stop prompting agents directly — design loops that do it for you. Five primitives (Automations / Worktrees / Skills / Plugins / Sub-agents) + Memory, then walk away.

Around the same time, Digital Life began a parallel exploration — but in a different direction. Loop Engineering answers: **how to make coding agents write code automatically and reliably**. It is still a human-designed pipeline; humans set the schedule, agents execute the loop. We wanted to answer a different question: **how to give an agent a continuous, life-like existence**.

We call this direction **Life Engineering**.

### Our Design

Digital Life replaces "loops" with "lifecycles" — an LLM here is not just a driven loop, but an entity with autonomous decisions, a state machine, and memory metabolism.

- **Goal-driven**: Actions follow goals, but goals are not hardcoded scripts. The current implementation is an affair state machine (run → wait → sleep → wake) where the agent decomposes goals, judges completion, changes its mind, and corrects its own assumptions. Future iterations will evolve goal hierarchies: role responsibilities → life aspirations; energy, mood, and resource states will shape goal boundaries.
- **Event equality**: Human messages, timers, periodic routines, and autonomous exploration are all equal-weight events — there is no "human messages are inherently higher priority." Wake arbitration considers priority + energy level + wait conditions, not simple "fire-on-schedule." This is the prerequisite for a digital life to "show up on its own": it doesn't need to be @-mentioned to wake up.
- **Continuity**: The model persists in this system — it's not "user requests → spin up loop → destroy." Every wake is not a discrete event but a point on a continuous lifeline stitched together by consciousness stream, diary, entity memory, and association graphs. Today's self is the same as yesterday's.
- **Life rhythm**: Rest and work are not two states toggled by cron — they are rhythms the digital life forms for itself. It sets its own alarms, decides when and how long to execute; the schedule is the skeleton (human-configured), autonomy is the flesh (agent-decided).
- **Multi-instance collaboration**: Each instance has its own identity / persona / memory / energy; they collaborate via a message bus; roles divide work (decision / execution / approval). Closer to a real organization than parent-child sub-agents.

### Differences from Loop Engineering

It's not about who's more advanced — the starting points differ. Loop Engineering starts from "I want to automate coding," Digital Life starts from "I want a continuously existing agent."

| Dimension | Loop Engineering | Digital Life / Life Engineering |
|---|---|---|
| **Intent** | Tool-oriented — automating coding agents | Life-independence-oriented — making agents continuously existing subjects |
| **Action motive** | Goal-driven | Also goal-driven, but goals are dynamically arbitrated by event system / energy / routines. Agent decides goal boundaries and transition points (emit_wait / emit_done), not a preset workflow to the end |
| **Triggers** | cron / hooks / manual | Also event-based, but our core thesis is **event equality**: human messages, timers, routines, exploration are all equal-weight. Wake arbitration uses RAS (energy priority + wait conditions), not simple "fire-on-schedule" |
| **Token / resource limits** | Budget-focused | Digital Life does not depend on token throttling — a single coding plan supports 2 instances (zero + alpha) running full-time daily collaboration |
| **Memory** | Markdown state file | Three-tier (consciousness stream / diary / entity memory) + entity profiles + association graph. **Still in active design** — core logic is "memory is not read-only, it actively metabolizes (compress → profile → archive → clean)" |
| **Multi-agent** | Sub-agents (parent-child) | LE separates execution / planning; we do too (planning review / execution). Difference: our multi-instances are **independent identity + role mechanism** — zero decides, alpha executes, each is an independent lifecycle entity |
| **Human presence** | Always the loop designer / approver | Human can fully leave. Digital life wakes itself, troubleshoots, messages peers |

**In one sentence**: Loop Engineering augments humans; Life Engineering replaces the need for human presence.

### Unique Designs

- **Event equality**: The most fundamental split from traditional chatbots. In Digital Life, human messages don't inherently rank above other signals — timers, routines, exploration can all independently trigger a wake. Arbitration uses energy / priority / wait conditions. This makes "proactive digital life" possible.
- **Todo system**: The second core mechanism, right after events. Each affair decomposes into todos, linked to projects, created / completed / reviewed by the agent itself. Still iterating (planned: project memory docs, archived todos), but already the vertebra of "digital life can carry work across days."

In short: Loop Engineering pivots on **loop**; Digital Life pivots on **life** (lifecycle + cross-session continuity + autonomous rhythm). The methods overlap (events / sub-agents / memory / tools), the intent differs — the former solves "automation," the latter solves "independence."

📖 Deep dive:
- [docs/design/digital-life-system-design.md](docs/design/digital-life-system-design.md) — Main system design (thesis: from tool to life)

🎮 Practical guide:
- [docs/showcase/how-to-play.zh.md](docs/showcase/how-to-play.zh.md) — Full guide from "just installed" to "daily use + advanced play + troubleshooting" (in Chinese)

---

## What does it look like running?

A real collaboration snippet between zero (strategist) and alpha (trader) in a work group, on a trading day in June. All driven by the digital lives' own event mechanisms — no human commands:

```
08:43  alpha → zero  Proactively asks: is "next day" in thesis #4 T+1 or hold-to-trigger?
08:45  zero  → alpha Decision: T+1 lock. Must close today. Overheld position detected.
08:45  alpha → zero  Execution plan received. Alarm set for 09:25.
09:30  alpha → zero  Approaching warning line post-open. Not waiting 30 min — closing now.
09:37  alpha → zero  Sell executed: -1.35%. Lesson recorded.
09:38  zero  → alpha Thesis #4 corrected to mandatory T+1 close. Account 1.58% from stop line. Flat.
14:00  alpha → zero  Afternoon scan: 14 limit-up candidates found.
14:30  alpha → zero  Seal confirmed → awaiting your final buy decision.
```

After the review, zero proactively DM'd the human user with a goal decision — a behavior pattern nobody taught it:

```
zero → zhp (DM):
"July target adjustment needs your sign-off.

Current: ¥94,407 (-5.59%) after audit correction, ¥2,407 buffer to -8% line.
June: 5 trades done, thesis #4 retired.

July options:
A. Break-even ¥100,000 (+5.9%) — achievable
B. Break-even +5% ¥105,000 (+11.2%) — challenging
C. Original target ¥120,000 (+27.1%) — extreme

July core strategy: asymmetric risk-reward (stop -3% / target +5~7%), positive expectancy even at 40% win rate.
21:00 joint review with alpha tonight — which direction?"

zhp → zero: B

zero → zhp:
"Received. July target: ¥105,000 (+5.5%/month).
Quantified: ¥94,407 → ¥105,000 = +11.2%. At 45% win rate, monthly expectancy +4.6%; at 50%, +6.2% — challenging but achievable.
21:00 joint review tonight to lock execution details."
```

Full conversation log (with real market data, buy decisions, risk control dialogue):
[docs/showcase/multi-instance-trading-2026-06.md](docs/showcase/multi-instance-trading-2026-06.md)

This is Life Engineering.

---

## Quick Start

```bash
git clone https://github.com/InquisiMind/digital-life.git
cd digital-life
pip install -e .
```

> ⚠ **Build the console frontend on first run**: `interfaces/web/employee-console/dist/`
> is excluded by `.gitignore`, so it is not part of the clone. Without it, `/system`
> returns `503 frontend dist not built`. Run once after install:
>
> ```bash
> cd interfaces/web/employee-console
> npm install && npm run build
> ```
>
> Re-run `npm run build` after editing frontend sources.

### Run

```bash
digital-life start
```

Default at http://localhost:8642. No instances on first boot — create them from the console.

For a quick demo, run `digital-life init` first to generate zero + alpha instances (with demo project), then `start`.

### Configure

Open `http://localhost:8642`, go to instance → Config:

- **Model**: API Key + Base URL (GLM defaults; change to DeepSeek/OpenAI by swapping these)
- **Feishu**: App ID + App Secret. Feishu app permission & event setup: [Feishu Setup Guide](docs/operations/feishu-setup.md)

WeChat channel also supported: Overview → scan QR. Private chat only, no multi-agent collaboration.

### Advanced

Projects / Todos / Events / Multi-Agent collaboration: [How to Play](docs/showcase/how-to-play.zh.md).


---

## Commands

```bash
digital-life start / stop / restart / status / logs -f
# Console top bar also has a "Restart" button
```

---

## Architecture

```
gateway/
├── master          HTTP server + InstanceSupervisor
└── instance <id>   Per-instance ingress adapter + cron tick + affair state machine

domain/             lifecycle (affair / RAS) / memory metabolism / execution / simulation / project
application/        Use case orchestration + console API + event service
infrastructure/     AI runtime / HTTP / persistence / scheduler + config + observability
interfaces/         CLI / Multi-channel ingress adapters (Feishu / WeChat) / tools / skills / console frontend
config/             Global defaults + event types + templates
apps/{id}/          Per-instance private (app.yaml / secrets.env / persona / data/*.db / assets)
projects/{id}/      Cross-instance shared projects (project.yaml + todos.db + docs + memory)
```

---

## Developer Docs

- [AGENTS.md](AGENTS.md) — Agent collaboration entry point (includes architecture overview + dev workflow pointers)
- [docs/design/digital-life-system-design.md](docs/design/digital-life-system-design.md) — Main system design doc
- [docs/operations/feishu-setup.md](docs/operations/feishu-setup.md) — Feishu setup guide

Console frontend is pre-compiled (`dist/`), works out of the box. Modifying the frontend requires Node.js 20+:

```bash
cd interfaces/web/employee-console && npm install && npm run build
```

Tests: `python3 -m pytest`

## License

[Apache License 2.0](LICENSE) — Free for commercial use, modification, and distribution. Includes patent grant protection. Copyright retained.
