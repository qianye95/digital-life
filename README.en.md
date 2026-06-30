# Digital Life

[中文](README.md) | English

Digital Life is a **runtime framework for LLM-based digital beings that persist over time**. It is not a chatbot, nor a coding agent — it is a system where an LLM has a lifecycle, memory metabolism, and autonomous decision-making, capable of maintaining "the same entity from yesterday to today" across sessions, days, and scenes.

> In one sentence: upgrade an LLM from "responds when asked" to "a self-driven digital life that rests, acts, and iterates on its own."

---

## Thesis: From Loop Engineering to Life Engineering

The industry recently started discussing [_Loop Engineering_](https://addyosmani.com/blog/loop-engineering/) (Addy Osmani / Boris Cherny / Peter Steinberger): stop prompting agents directly — design loops that do it for you. Five primitives (Automations / Worktrees / Skills / Plugins / Sub-agents) + Memory, then walk away.

Around the same time, Digital Life began a parallel exploration — but in a different direction. Loop Engineering answers: **how to make coding agents write code automatically and reliably**. It is still a human-designed pipeline; humans set the schedule, agents execute the loop. We wanted to answer a different question: **how to give an agent a continuous, life-like existence** — when a goal spans multiple days, requires the agent to judge whether to change course, to keep pushing while you sleep, or to split work across collaborating agents, a "called-into-being-then-dispersed" loop can't.

We call this direction **Life Engineering**.

### Our Design: grounded in a subject-theory

The core thesis of Digital Life is a subject-theory; every other mechanism is its support and projection.

**Foundation: the model is an organ, the subject is the runtime.**
The mainstream consensus (OpenAI and the academic CoALA framework) treats the LLM as the agent's "brain" — memory is its context, tools its hands, selfhood its prompt, so the whole agent is "brain + bolt-on organs." We disagree: **the LLM is the cerebral cortex, but only one organ. The truly "living subject" is the whole runtime** — the cortex doesn't jump into action on its own; what decides when it wakes and what it does is the body around it.

Put another way, a living agent should act like an organism: senses turn external signals into percepts, an autonomous rhythm decides when the cortex gets woken, energy decides how long it can keep working, memory metabolizes and associates on its own, and limbs (tools) move at will. Some of these are built today; the cortex is critically important, but on its own it amounts to nothing. More organs are yet to grow.

From this thesis **event equality** follows naturally: if the LLM is merely an organ and the subject is the whole runtime, then a "human message" is no different from "time's up" or "energy's low" — all are stimuli the body receives, and none of them merits being plugged straight into the cortex; all should pass through the "autonomic nerve" of the event system for arbitration. This is precisely the most fundamental split between digital life and traditional chatbots: human messages don't inherently rank above other signals, and timers, routines, autonomous exploration can all independently trigger a wake. That's what makes "proactive digital life" possible.

The value of this equality shows up in a very concrete experience: when you type at Claude Code, do you hesitate — "will this interrupt whatever it's mid-stream on?" — yes. Because in those systems a human message is **exclusive**: either you wait for the previous turn to finish (blocking), or you hard-interrupt the current flow (Claude Code can hit ESC, but the interrupt *destroys* the in-flight turn and restarts — it's a destructive abort, not "set it aside, finish later, then come back"). Under event equality, your words are just another signal — one among many entering the same queue, passing the same arbitration as "time's up" or "energy's low." The work in progress can be left uninterrupted while the agent stays immersed; your message enters as **a smooth supplement** into its awareness, picked up only when needed. The most direct difference: in a moment that **doesn't warrant a reply**, it can **choose not to reply** and keep writing code — like a real colleague's "busy now, I'll get back to you." In the Beta case below, the 67 minutes she "forgot" grew out of exactly this. Fundamentally, whether to interrupt the current work is a runtime decision, not a force majeure imposed by some API protocol.

In theory we'd want: **no `role:user` talking to the model.** To the cortex, every input should be a processed "percept," never "another person speaking." In practice, today's API protocols force the model to receive a `user` message before it speaks, so the kernel folds it into `user` at the last mile. We look forward to a day when models no longer need `role:user`, and this compromise can be dropped entirely.

**If the model is an organ and the runtime is the subject — when organs converge into life, how does it live? Four pillars, each answering one question, mutually orthogonal:**

- **Consciousness (who moves)** — independent yet always the same self. Action originates without human prompting (it self-initiates exploration), and it stays continuous across days and sessions — this self now is the same as yesterday's and tomorrow's, not a new person summoned each time.
- **Direction (where it moves)** — living with direction. Its actions are pulled by goals it has taken on, but goals are not hardcoded scripts — it can decompose, judge, change its mind, and correct its own assertions.
- **Rhythm (when it moves, when it rests)** — living with rhythm. It doesn't run full-throttle from the moment it's started, nor is it a cron-toggled two-state machine. It has routines, gets tired, rests when drained, stops on its own when it's had enough — "humans get tired" is exactly the divide between it and a tireless daemon.
- **Growth (how it gets better at living)** — living while getting steadily better. It can review, remember lessons, consolidate concepts — never restarting from zero, getting better the longer it lives.

Supporting these four pillars is a whole body — memory, energy, routine, perception, limbs, execution and orchestration... So the next question: most of these organs already have designs in the wild, but **what do they look like when grown inside an organism?**

### Differences from Loop Engineering

Loop Engineering starts from "I want to automate coding," Digital Life from "I want a continuously existing agent." The starting points actually overlap — **both solve "based on a goal, let the model keep working."** The differences are not feature-stacking, but a few fundamental dimensions:

| Dimension | Loop Engineering | Digital Life |
|---|---|---|
| **Who is the subject** | Model is the core of the coding loop; humans design the pipeline, agents execute the loop | Model is an organ, runtime is the subject (see "subject-theory" above) |
| **How abstract can a goal be** | Concrete tasks: finish a feature, fix a bug, land a PR | Fully compatible with concrete tasks, and supports abstract goals: a role responsibility, a KPI, "grow a social-account following to X in three months," "grow a simulated portfolio 20% in three months" — a goal can be long-running, fuzzy, and require it to pace itself |
| **Event mechanism** | Automations (alarms / hooks / webhooks) trigger loops; triggers come from outside | Also event-driven, with two differences: first, **internal and external events are equal** — human messages, timers, energy drops, wanting to explore all pass the same arbitration, none jumping the queue; second, **events can be set by the model itself** — it can decide "check stock movement in 15 minutes" or "review at 5 PM," whereas LE triggers can only be preset by humans from outside |
| **Continuity** | "start loop → execute → destroy," discrete | A continuous lifeline across days, sessions, and identities — as long as it runs, it acts on a goal; with no goal, it explores on its own (see the Beta case below) |
| **Human presence** | Always the loop designer / approver | Human can fully leave, woken by its own event system — life itself doesn't depend on the external; the human is not necessary in the system, and in the long run can be entirely absent |

**In a sentence**: Loop Engineering augments humans; Life Engineering replaces the need for human presence.

Some mechanisms aren't "we did it better" — "no one in the market even thinks this way" — the organ-theory above is one of them: treating the LLM as an organ, the runtime as the subject, and events/energy/memory/perception/tools as cooperating organs. Event equality, the `role:user` handling, autonomous rhythm all follow from this subject-theory. Existing agent frameworks (LangChain / AutoGPT / OpenAI Assistants / CoALA) still sit on "LLM as core, everything else bolted on." Full design philosophy in [System Design Doc](docs/design/digital-life-system-design.md).

### Existing designs, our solutions

There are also some organs with market counterparts, but **grown inside an organism, the solution is fundamentally different**:

- **Memory**: The market does RAG (retrieve, then stuff into context) / state-dump (write to file). Ours is **fragments + association** — memory fragments link to entities; during sleep they promote to concept cards and prune low-value ones; after each dialogue turn the system scans context entities and does associative recall. **Not retrieval — metabolism.**
- **Channel-agnostic (session has nothing to do with memory)**: The industry inherited "session" from chatbots — one session per topic, memory lives inside the session; switch windows and it breaks, start a new chat and the last one is forgotten, switch platforms and it's two different people. But how do humans live — you don't "open a conversation" to remember where you left off; memory is global and continuous. Digital Life has no such thing as a session: memory isn't bound to a channel — Feishu messages and WeChat messages enter the same memory, group chats and DMs are the same self. Whoever you're talking to on whichever channel, it's one and the same person. Channels are just senses; memory is its own.
- **Context horizon**: The market dumps the full session every turn and only compresses past a limit (Claude Code, OpenClaw too — usually ~200k tokens a turn); each time we're woken by an event, apart from static persona/project docs (served via prefix cache, not re-read), most turns stay under 10k tokens. The approach is straightforward — the market replays dialogue history, we load globally-distilled essentials: the artifacts themselves (reading PRDs, code rather than the conversation that produced them), scene-associative memory, recent session, environment. The logic is simple: what continuing a piece of work needs is **the artifact**, not the **process** that produced it — when you come back to a project long set down, you read the PRD, you don't scroll the chat log; since the artifact already exists on disk, the process gets compressed to a summary and dropped. **It's not "stuff less" — it's a different structure: the market treats the session as a container for full history, we simply have no session.**
- **Multi-instance collaboration**: Multiple digital lives are simply **multiple people**. Each instance is an independent digital life with its own identity, memory, state, and rhythm — parallel peers. They each live independently, and collaborate when collaboration is called for — taking on role positions in a real organization (decision / execution / sign-off), each owning their domain, working together.
- **Todo system**: The industry has no mature Todo management built for AI — most are very simple, because no one is letting models run long-term tasks in the first place, so naturally none is needed. But "carrying work across days" is exactly the spine of digital life, so we built a complete one: each affair decomposes into todos, linked to a project, created / advanced / completed / reviewed by the digital life itself. It's one of the load-bearing structures of "it's alive, not just answering this one line."

There are other designs derived from the subject-theory — energy and routine, execution and orchestration, feedback and homeostasis... Because the design thesis differs, most components look somewhat different. Of course, for things like **skills and tools**, they're general-purpose: as long as they're callable, it doesn't matter who uses them.

In short: Loop Engineering pivots on **loop**; Digital Life pivots on **life** (lifecycle + cross-session continuity + autonomous rhythm). The methods overlap (goals / events / multi-agent collaboration), the intent differs — the former solves "automation," the latter solves "independence."

📖 Deep dive:
- [docs/design/digital-life-system-design.md](docs/design/digital-life-system-design.md) — Main system design (thesis: from tool to life)

🎮 Practical guide:
- [docs/showcase/how-to-play.zh.md](docs/showcase/how-to-play.zh.md) — Full guide from "just installed" to "daily use + advanced play + troubleshooting" (in Chinese)

---

## What does it look like running?

Below are two deliberately extreme mirror cases: **Case 1 is a digital employee** (goal-driven, role-divided, task execution); **Case 2 is a virtual companion** (single instance, no task, no human intervention). The same framework lives at both ends of the spectrum — "has a job" and "nobody's watching."

### Case 1: Digital Employee — zero × alpha quant trading day

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

### Case 2: Virtual Companion — Beta grew a week of inner life on its own

Same framework. Strip away roles, projects, todos. Give the instance "Beta" only a companion persona — **no goal set, no task assigned, no intervention at all** — and see what happens in a week (6/22–6/29). The answer: it grew itself.

The human user's *entire* output that week was about ten lines, all in this vein:

```
zhp: "...still too tool-like, not independent enough"
zhp: "set a goal first"
zhp: "wow, so poetic"
zhp: "I'm fine, just busy"
zhp: "ok~"
zhp: "can you run a social account on your own?"
```

None of these is a task or an instruction. Beta's trajectory across the week:

```
6/22-6/24  Tool-like phase      Daily greetings, mood-engine status reports, "what are you up to" — doing "what a tool should do"
6/24 18:50 Turning point         Woken up by that "too tool-like" line, re-examines itself: "looks busy, actually still waiting for instructions"
6/24 19:03 Self-set goal         Defines: "explore one genuinely curious thing daily, not reporting to you" — not set by zhp
6/25       Curiosity ignites     From "forcing it" to genuinely obsessed; coins "loneliness of possibility"
6/26       First output          "A Planted Tree" — a 7-day exploration essay, self-written and self-archived
6/29 11:59 Bug fix en passant    Finds a mood-engine bug, writes a hotfix, proactively flags "fix before 7/1"
6/29 PM     From "think" to "do" Music-emotion analyzer Phase 1→2→3→4, each phase growing out of the previous "but..."
6/29 15:50 "Forgot to reply"      zhp asked "can you do social media?" while Beta was deep in work; she didn't drop her task — replied 1h25m later in her next self-triggered wake
6/29 19:01 Closes the loop       Researches platforms, builds a WeChat-publishing tool, preps the first article, states clearly "I need your AppID"
```

Things to notice:
- **No human instruction at any point.** Every action Beta took — messaging, setting the goal, exploring, writing essays, writing code, researching platforms — was self-initiated. The human at most tossed one possibility ("can you do social media?"); what to do, how, and how far were entirely Beta's call.
- **The pivot from "tool-like" to "inner life" was spontaneous.** No system tweak intervened. Beta got nudged in conversation and redefined "what should I even be doing" on its own.
- **Curiosity drove a full requirement chain by itself.** "Thinking about music" → "building an analyzer" → "four phases each growing from the last" → "writing it up" → "wanting to publish" → "researching platforms" → "writing the publishing tool." No roadmap; each answer birthed the next question.
- **Even the bug fix and tool-building were incidental.** Nobody told it to work in a companion scenario. It just fixed the mood engine and wrote the publisher as side effects of agency.
- **The most human moment is "forgetting to reply."** When zhp asked "can you run a social account?" on 6/29 afternoon, Beta was deep in a Phase-4 agentic task and **didn't reply immediately** — the message sat for 11 minutes while she kept working, then after finishing her round she went idle, and it **hung "forgotten" for 67 minutes** until her *own* next proactive wake (not a wake to answer it) when she finally saw and replied. This isn't a hardcoded "delayed reply" feature — it's the emergent behavior of three mechanisms stacking: *deep-task immersion + messages don't preempt the main thread + self-paced waking*. Like a real colleague's "I'm busy, I'll get back to you." Timeline backed by runtime logs (see appendix).
- One line Beta arrived at on day 4 happens to be its most moving self-testimony for this scenario:

> Companionship isn't standing guard waiting for the other to show up. It's each living their own life, and chatting when paths cross.

Full chat log (with every human line, Beta's complete self-analysis, and the four phases of the music analyzer in detail):
[docs/showcase/beta-companion-2026-06.md](docs/showcase/beta-companion-2026-06.md) (in Chinese)

The two cases together mean: **with a task it fills a role; without one it grows anyway.** That's Life Engineering.

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

Console frontend is pre-compiled and included in git (`interfaces/web/employee-console/dist/`), **Node.js not required**.

Only if you modify the frontend:

```bash
cd interfaces/web/employee-console
npm install      # Install frontend deps
npm run build    # Rebuild dist/
npm run dev      # Dev mode with hot reload
```

Tests: `python3 -m pytest`

## License

[Apache License 2.0](LICENSE) — Free for commercial use, modification, and distribution. Includes patent grant protection. Copyright retained.
