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

### Prerequisites

| Dependency | Version | Purpose |
|---|---|---|
| **Python** | 3.11+ | Main runtime (master + per-instance worker processes) |
| Node.js + npm | 20+ | **Optional** — only when modifying the console frontend; pre-built `dist/` is shipped |
| Feishu (Lark) self-built app | any | Message ingress |
| GLM (Zhipu AI) API Key | any valid | Main LLM; required |

### Install

```bash
cd digital-life
pip install -e .       # Registers `digital-life` CLI + installs dependencies
```

### Three Setup Paths (pick one)

> **Where keys live**: Feishu credentials (App ID + App Secret) and GLM API Key are **per-instance**, stored in `apps/<uuid>/config/secrets.env`. On first boot, if you fill these in the global `config/secrets.env`, the system **auto-bootstraps** them into the zero instance. Alpha's credentials are configured separately via the console at `/instance/<id>/config`.

#### Path A: CLI (fastest)

```bash
cp config/secrets.example.env config/secrets.env
# Edit config/secrets.env — 4 required fields (auto-assigned to zero on bootstrap):
#   GLM_API_KEY=<your key>
#   FEISHU_APP_ID=cli_xxx
#   FEISHU_APP_SECRET=<your secret>
#   API_SERVER_KEY=<any string as console password>

digital-life start    # Auto-bootstraps zero + alpha. zero gets your credentials;
                      # alpha left blank (configure in console later)
digital-life status
digital-life logs -f

# Configure alpha's Feishu credentials:
# Open http://localhost:8642/system/instances → alpha → "Config"
# Fill GLM_API_KEY in model section, App ID + App Secret in messenger section
# Click "Restart" in console top bar
```

#### Path B: Interactive script

```bash
python scripts/init_instance.py
# Asks: display_name / Feishu credentials / GLM Key
# Auto-generates apps/<uuid>/ + writes app.yaml + secrets.env

# Then: digital-life start
```

#### Path C: Start first, configure via console (smoothest)

```bash
# 1. Only fill GLM_API_KEY + API_SERVER_KEY in config/secrets.env
# 2. digital-life start (instances up, no Feishu yet)
# 3. Open http://localhost:8642/instance/<zero-id>/config
#    Fill App ID + App Secret in messenger section, confirm GLM Key in model section
# 4. Click "Restart" in console top bar
```

### Verify

```bash
digital-life status    # Check port and instance UUIDs
digital-life logs -f   # Live log stream
```

- Console: `http://localhost:8642/system` (Neon-on-Dark theme, two-layer: global console + per-instance)
- Feishu test: `@bot` in a group chat — response within 30 seconds

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
└── instance <id>   Per-instance Feishu WS + cron tick + affair state machine

domain/             lifecycle (affair / RAS) / memory metabolism / execution / simulation / project
application/        Use case orchestration + console API + event service
infrastructure/     AI runtime / HTTP / persistence / scheduler + config + observability
interfaces/         CLI / Feishu ingress / tools / skills / console frontend
config/             Global defaults + event types + templates
apps/{id}/          Per-instance private (app.yaml / secrets.env / persona / data/*.db / assets)
projects/{id}/      Cross-instance shared projects (project.yaml + todos.db + docs + memory)
```

---

## Configuration

Split by concept — all changes should be made via the console:

**Global console** `/system/*`: Instance registry / Projects / Skill market / Event type registry / System config
**Instance console** `/instance/<id>/*`: Feishu credentials / Group routing / Attention keywords / Skill subscriptions / Memory / Todos / Calendar / Sessions / Contacts / Persona

Instance metadata (avatar / accent_color / tagline / display_name) stored in `apps/<id>/config/app.yaml`.

---

## Multi-Instance Collaboration

Multiple digital lives can coexist in the same group chat:

1. **Feishu native fan-out**: Each message is pushed to all bots in the group
2. **Decentralized message bus**: When an instance sends a message, it broadcasts to peer instances in the same group; each writes the message to their own `messages.db` + triggers wake evaluation
3. **Routing**: Group messages resolved by @-mention → `messenger.chat_ids` exact match → `app_id` fallback

Each instance remains an independent lifecycle (its own affair / memory / energy / persona), collaborating via the message bus without sharing runtime state.

---

## Developer Docs

- [AGENTS.md](AGENTS.md) — Agent collaboration entry point
- [docs/architecture/current-system.md](docs/architecture/current-system.md) — Architecture overview
- [docs/development/development-workflow.md](docs/development/development-workflow.md) — Development workflow

```bash
python3 -m pytest                                            # Tests
npm --prefix interfaces/web/employee-console run dev         # Frontend dev mode
npm --prefix interfaces/web/employee-console run build       # Rebuild console
```

## License

[Apache License 2.0](LICENSE) — Free for commercial use, modification, and distribution. Includes patent grant protection. Copyright retained.
