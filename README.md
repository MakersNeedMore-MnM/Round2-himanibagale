# CodeLith

An AI mentor that blends coding assistance with adaptive teaching. CodeLith runs
entirely on your machine: a local daemon orchestrates a graph of specialised
agents that write and debug your code, detect the programming concepts you are
using, quiz you on them, and save teaching material — all visible live in a
browser dashboard while you work from the terminal.

Your code never leaves your laptop except for the model calls themselves. There
is no server, no account, and no telemetry.

## Features

- **Terminal-first workflow** — the `mentor` command starts an interactive
  session against your own project files.
- **Local daemon** — a FastAPI server that runs in the background on
  `127.0.0.1:8765`, auto-started on demand and shared by the CLI and the
  dashboard.
- **Multi-agent orchestration** — a LangGraph state machine routes work through
  a coding agent, a debug agent, a concept detector, an assessment agent, and a
  teacher agent.
- **Adaptive teaching** — every turn, the code you write is scanned for
  programming concepts; each concept gets an explanation and a Mermaid diagram
  on the dashboard.
- **Socratic assessment** — generated questions test whether you actually
  understand the concepts you just used, graded by the LLM with retry feedback.
- **Three session modes** — Learn, Pair Programming, and Autonomous change how
  much teaching, explanation, and autonomy you get. Switchable from either the
  CLI or the dashboard, synced live.
- **Live activity stream** — the dashboard shows which agent is running and
  which tools (read, write, edit, run command) are executing, via
  server-sent events.
- **Durable progress** — concepts, assessments, and teachings persist per
  session in a local SQLite database.

## Quick start

Requires Python 3.10 or newer.

```bash
pip install codelith
mentor
```

The `mentor` command starts the daemon in the background if it is not already
running, then opens an interactive session and the dashboard at
[http://localhost:8765](http://localhost:8765). Type a request in the terminal;
watch the agents, concepts, and questions appear in the dashboard.

```
CodeLith AI — autonomous coding agent
Workspace: C:\Users\you\my-project
Mode: learn

> What is a closure?
A closure is a function that remembers the variables from the scope where it
was defined, even after that scope has finished running...

> exit
```

Exit the session with `exit`, `quit`, `q`, or Ctrl+C. The daemon keeps running
in the background afterwards, so the dashboard stays available; stop it with
`python -m backend.daemon.launcher stop`.

## Connecting the LLM providers

Two API keys are used, each from a different provider:

- **`GROQ_API_KEY`** — mentor-side models: teacher explanations, assessment
  grading, concept detection, and dashboard questions. Defaults to Groq's
  `openai/gpt-oss-120b`. Get a key at [console.groq.com/keys](https://console.groq.com/keys).
- **`OPENROUTER_API_KEY`** — the coding and debug agents that read, write, and
  edit files. Defaults to `qwen/qwen3-coder-next`; change it with
  `CODELITH_AGENT_MODEL` (any OpenRouter slug, e.g.
  `anthropic/claude-sonnet-4.5` for the strongest agentic coder, or any
  `...:free` model). Get a key at [openrouter.ai/keys](https://openrouter.ai/keys).

Keys are resolved from, in order: environment variables, a `.env` file in the
project root, then a `.env` file in the daemon state directory (`~/.mentor/`).
The files are re-read on every request, so adding a key takes effect
immediately — no daemon restart needed.

```bash
# .env (project root, or ~/.mentor/.env for a machine-wide default)
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
# Optional: pick a different coding-agent model
# CODELITH_AGENT_MODEL=anthropic/claude-sonnet-4.5
```

## Using the product

### The `mentor` CLI

| Command | Effect |
| --- | --- |
| `mentor` | Start (or reuse) the daemon and open an interactive session |
| `mode` | Show the current session mode |
| `mode learn` / `mode pair-programming` / `mode autonomous` | Switch mode for the whole session |
| `reset` | Clear the conversation history for this session |
| `exit` | Leave the CLI; the daemon keeps running |

The daemon is the source of truth for the session mode: switching it in the
dashboard updates the CLI within a couple of seconds, and vice versa.

### The dashboard

Open [http://localhost:8765](http://localhost:8765) (the daemon serves the
built dashboard itself, so no separate dev server is needed). The dashboard
shows, for the current session:

- **Live activity** — which agent is running and each tool call as it happens
  (streamed over SSE from `POST /chat/stream`).
- **Concepts** — every concept detected in your code with its category,
  explanation, and Mermaid diagram.
- **Assessments** — Socratic questions for detected concepts. Answers are
  graded by the LLM; incorrect answers stay open with feedback so you can
  retry.
- **Teachings** — per-concept teaching entries saved by the teacher agent.
- **Progress** — a summary of concepts covered and assessment performance.
- **Mode switcher** — change the session mode without touching the terminal.

### Controlling the daemon

```bash
python -m backend.daemon.launcher start    # start detached if not running
python -m backend.daemon.launcher status   # is it running, on which port
python -m backend.daemon.launcher stop     # stop it
```

The daemon keeps its PID and port files in `~/.mentor/`; `start` never spawns
a second instance while one is already running. If the preferred port 8765 is
taken, the launcher falls back to a free port and records it.

### Session modes

| Mode | Teacher agent | Agent explains code | LLM concept detection | Assessment questions | Max tool rounds |
| --- | --- | --- | --- | --- | --- |
| `learn` | always runs | yes | yes | high (every new concept) | 8 |
| `pair-programming` | always runs | no | yes | low (about 1 in 3 concepts) | 12 |
| `autonomous` | skipped | minimal | no | none | 15 |

Learn mode is for studying: concepts are surfaced prominently and you are
quizzed on each one. Pair Programming keeps the teaching in the background
while you drive. Autonomous disables questions and explanations and gives the
coding agent the most tool rounds — it just gets things done.

## Architecture

CodeLith is a local three-process system: a CLI, a browser dashboard, and a
background daemon that hosts the API and the agent graph. Both frontends talk
to the same daemon, which is the single source of truth for session state
(conversation history, mode, concepts, assessments, teachings).

```text
                              YOUR MACHINE
+--------------------------------------------------------------------------+
|                                                                          |
|   +---------------+                        +----------------------+      |
|   |   Terminal    |                        |       Browser        |      |
|   |  mentor (CLI) |                        | Dashboard (React +   |      |
|   |               |                        | Vite + Mermaid)      |      |
|   +-------+-------+                        +----------+-----------+      |
|           |                                           |                  |
|           |  HTTP 127.0.0.1:8765                      |  HTTP + SSE      |
|           |  POST /chat                               |  127.0.0.1:8765  |
|           |                                           |                  |
|           +---------------------+---------------------+                  |
|                                 |                                        |
|                                 v                                        |
|  +-------------------------------------------------------------------+   |
|  |                  DAEMON  (FastAPI + uvicorn)                       |   |
|  |                                                                   |   |
|  |   POST /chat                  run the agent graph, return reply   |   |
|  |   POST /chat/stream           same, plus live SSE activity events |   |
|  |   GET/POST /mode              session mode (CLI <-> dashboard)    |   |
|  |   GET  /concepts              detected concepts for a session     |   |
|  |   GET  /assessments           questions + counts                  |   |
|  |   POST /assessments/answer    LLM-graded answer submission        |   |
|  |   GET  /teachings             teaching entries + diagrams         |   |
|  |   POST /question              dashboard Q&A (no file operations)  |   |
|  |   GET  /progress              learning progress summary           |   |
|  |   GET  /health                liveness probe (used by launcher)   |   |
|  |   GET  /                      the built dashboard (static files)  |   |
|  +-----------------------------+-------------------------------------+   |
|                                |                                         |
|                                v  run_graph()                            |
|  +-------------------------------------------------------------------+   |
|  |            ORCHESTRATOR  (LangGraph state machine)                 |   |
|  |                                                                   |   |
|  |              +--------------+                                     |   |
|  |              | coding agent |------------------+                  |   |
|  |              +--------------+                  | last command     |   |
|  |                     | commands/tests pass      | failed           |   |
|  |                     |                          v                  |   |
|  |                     |                  +-------------+             |   |
|  |                     |                  | debug agent |             |   |
|  |                     |                  +------+------+             |   |
|  |                     v                         |                    |   |
|  |          +-----------------+<-----------------+                    |   |
|  |          | detect concepts |  registry scan + mode-gated        |   |
|  |          +--------+--------+  LLM detection, once per turn         |   |
|  |                   |                                                |   |
|  |                   | mode disables questions? -----> END            |   |
|  |                   v                                                |   |
|  |          +------------------+  mode: teacher     +-----------+      |   |
|  |          | assessment agent |  does not run? -->|   END     |      |   |
|  |          +--------+---------+                   +-----------+      |   |
|  |                   |                                                |   |
|  |                   v                                                |   |
|  |          +----------------+                                        |   |
|  |          | teacher agent  | ------------------------------------> END   |
|  |          +----------------+                                        |   |
|  +----+-----------------+------------------------+---------------------+   |
|       |                 |                        |                         |
|       v                 v                        v                         |
|  +-------------+  +-----------------+  +--------------------------+       |
|  | coding +    |  | concept         |  | assessment +             |       |
|  | debug agent |  | detector        |  | teacher agents           |       |
|  | tools:      |  | pattern registry|  | question templates,      |       |
|  | read_file   |  | + LLM fallback, |  | LLM grading, teaching    |       |
|  | write_file  |  | Mermaid diagrams|  | entries                  |       |
|  | edit_file   |  +-----------------+  +-------------+------------+       |
|  | run_command |                              |                          |
|  +------+------+                              |                          |
|         |                                     |                          |
|         v                                     v                          |
|  +-------------------------------------------------------------------+   |
|  |                    LLM PROVIDERS  (HTTPS, external)                |   |
|  |   OpenRouter (coding + debug agents)    Groq (mentor-side agents)  |   |
|  |   OPENROUTER_API_KEY                    GROQ_API_KEY               |   |
|  |   qwen/qwen3-coder-next (default)       openai/gpt-oss-120b        |   |
|  +-------------------------------------------------------------------+   |
|                                                                          |
|  +-------------------------------------------------------------------+   |
|  |                     PERSISTENCE   ~/.mentor/                       |   |
|  |   mentor.db (SQLite, WAL): concepts / teachings / assessments      |   |
|  |   daemon.pid  daemon.port  .env (optional key file)                |   |
|  +-------------------------------------------------------------------+   |
|                                                                          |
+--------------------------------------------------------------------------+
```

### How a turn flows

1. **Your message** arrives at the daemon (`POST /chat` from the CLI, or
   `POST /chat/stream` from the dashboard with live events).
2. **Coding agent** plans and acts with tools: `read_file`, `write_file`,
   `edit_file`, and `run_command` against your workspace. Multiple tool rounds
   per turn, capped by the session mode.
3. **Routing** inspects the structured tool-call log, never the agent's reply
   text: if the most recent `run_command` failed (non-zero exit code or
   stderr), the **debug agent** takes over — it runs tests, reads the error,
   fixes the code, and re-runs, with a capped retry loop. A clean turn skips
   it. Provider-side LLM errors are never "fixed" by the debug agent.
4. **Concept detection** runs exactly once per turn. A curated registry of
   known patterns (React hooks, async/await, decorators, Python OOP, ...)
   matches the files the coding agent wrote; anything unrecognised goes to an
   LLM pass (skipped in Autonomous mode to save calls). Each concept carries a
   description and a Mermaid diagram, cached by content hash so unchanged code
   is never re-analysed.
5. **Assessment agent** (mode-gated) turns new concepts into Socratic
   questions for the dashboard.
6. **Teacher agent** (mode-gated) saves teaching entries with diagrams to the
   dashboard; if your message was a direct question, it answers in the
   terminal instead.

### Key design decisions

- **Structured routing over keyword matching.** The debug agent is triggered
  by execution results recorded in the tool-call log, so a reply that merely
  mentions the word "error" can never misroute the graph.
- **One detection pass, shared.** Concept detection used to run in both the
  assessment and teacher agents; it now runs once in a shared node and both
  consumers read the result, halving LLM calls per turn.
- **Identity-keyed storage.** Concepts are keyed by a stable slug derived from
  the concept name, not by which file they appeared in, with a content hash of
  the underlying code so explanations are reused until the code actually
  changes.
- **Concurrent-safe local storage.** SQLite in WAL mode lets the daemon write
  while the dashboard reads without `database is locked` errors.
- **Fail-closed test isolation.** Under any test runner, the database resolves
  into a per-process temp directory, so tests can never touch real
  `~/.mentor` data — a structural guarantee, not a fixture convention.

## Repository layout

```text
CodeLith/
├── backend/
│   ├── agents/           # coding, debug, assessment, teacher agents + concept detector
│   ├── cli/              # the `mentor` command-line interface
│   ├── daemon/           # FastAPI server, detached-process launcher, state files
│   ├── database/         # SQLite persistence: concepts, teachings, assessments
│   ├── llm/              # Groq + OpenRouter clients, key and model resolution
│   ├── orchestrator/     # LangGraph agent graph, session modes, event stream
│   └── main.py           # backend entrypoint
├── frontend/             # React dashboard (Vite + TypeScript + Mermaid)
├── tests/                # pytest suite
├── pyproject.toml        # packaging config + `mentor` entry point
└── README.md
```

## Development setup

### Backend

```bash
git clone https://github.com/your-username/codelith.git
cd codelith

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
pip install -e .                # exposes the `mentor` command
```

### Frontend

```bash
cd frontend
npm install
npm run dev       # dev server with hot reload; calls the daemon on port 8765
npm run build     # production build, served by the daemon at /
```

For dashboard development, run the daemon (start it with `mentor` or the
launcher) and the Vite dev server side by side; CORS is open to localhost.

### Tests

```bash
pytest
```

The suite covers agent routing behaviour, concept categories, Mermaid diagram
validation, and a store-isolation tripwire that guarantees tests never touch
real user data.

## License

[MIT](LICENSE)
# Round2-himanibagale
Repository for team himanibagale for Round 2
