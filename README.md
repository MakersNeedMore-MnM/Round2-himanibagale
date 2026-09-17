# CodeLith

An AI mentor that blends coding assistance with adaptive teaching. CodeLith
runs entirely on your machine: a local daemon orchestrates a graph of
specialised agents that write and debug your code, detect the programming
concepts you are using, quiz you on them, and save teaching material — all
visible live in a browser dashboard while you work from the terminal.

Your code never leaves your laptop except for the model calls themselves.
There is no server, no account, and no telemetry.

## Features

- **Terminal-first workflow** — the `codelith` command starts an interactive
  session against your own project files.
- **Local daemon** — a FastAPI server runs in the background on
  `127.0.0.1:8765`, auto-started on demand and shared by the CLI and the
  dashboard.
- **Multi-agent orchestration** — a LangGraph state machine routes work
  through a coding agent, a debug agent, a concept detector, an assessment
  agent, and a teacher agent.
- **Adaptive teaching** — every turn, the code you write is scanned for
  programming concepts; each concept gets an explanation and a Mermaid
  diagram on the dashboard.
- **Socratic assessment** — generated questions test whether you actually
  understand the concepts you just used, graded by the LLM with retry
  feedback.
- **Three session modes** — Learn, Pair Programming, and Autonomous change
  how much teaching, explanation, and autonomy you get. Switchable from
  either the CLI or the dashboard, synced live.
- **Live activity stream** — the dashboard shows which agent is running and
  which tools are executing, via server-sent events.
- **Durable progress** — concepts, assessments, and teachings persist per
  session in a local SQLite database.

## Quick start

Requires Python 3.10 or newer.

```bash
pip install codelith
codelith
```

The `codelith` command starts the daemon in the background if it is not
already running, then opens an interactive session and the dashboard at
[http://localhost:8765](http://localhost:8765). Type a request in the
terminal; watch the agents, concepts, and questions appear in the dashboard.

```text
CodeLith — an AI mentor that blends coding assistance with adaptive teaching.
Workspace: C:\Users\you\my-project
Mode: learn

> What is a closure?
A closure is a function that remembers the variables from the scope where it
was defined, even after that scope has finished running...

> exit
```

Exit the session with `exit`, `quit`, `q`, or Ctrl+C. The daemon keeps
running in the background afterwards; stop it with
`python -m backend.daemon.launcher stop`.

## Connecting the LLM providers

Two API keys are used, each from a different provider:

- **`GROQ_API_KEY`** — teaching-side models: teacher explanations, assessment
  grading, concept detection, and dashboard questions. Defaults to Groq's
  `openai/gpt-oss-120b`. Get a key at [console.groq.com/keys](https://console.groq.com/keys).
- **`OPENROUTER_API_KEY`** — the coding and debug agents that read, write, and
  edit files. Defaults to `qwen/qwen3-coder-next`; change it with
  `CODELITH_AGENT_MODEL` (any OpenRouter slug, e.g.
  `anthropic/claude-sonnet-4.5` for the strongest agentic coder, or any
  `...:free` model). Get a key at [openrouter.ai/keys](https://openrouter.ai/keys).

Keys are resolved from, in order: environment variables, a `.env` file in the
project root, then a `.env` file in the daemon state directory (`~/.codelith/`).
The files are re-read on every request, so adding a key takes effect
immediately — no daemon restart needed.

```bash
# .env (project root, or ~/.codelith/.env for a machine-wide default)
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
# Optional: pick a different coding-agent model
# CODELITH_AGENT_MODEL=anthropic/claude-sonnet-4.5
```

## Using the product

### The `codelith` CLI

| Command | Effect |
| --- | --- |
| `codelith` | Start (or reuse) the daemon and open an interactive session |
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

- **Live activity** — which agent is running and which tools are executing.
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

### Session modes

| Mode | Teacher agent | Agent explains code | LLM concept detection | Assessment questions | Max tool rounds |
| --- | --- | --- | --- | --- | --- |
| `learn` | always runs | yes | yes | high (every new concept) | 8 |
| `pair-programming` | always runs | no | yes | low (about 1 in 3 concepts) | 12 |
| `autonomous` | skipped | minimal | no | none | 15 |

Learn mode is for studying: concepts are detected and you are quizzed on each
one. Pair Programming keeps the teaching in the background while you drive.
Autonomous disables questions and explanations and gives the coding agent the
most tool rounds — it just gets things done.

## Architecture

CodeLith is a local three-process system: a CLI, a browser dashboard, and a
background daemon that hosts the API and the agent graph. Both frontends talk
to the same daemon, which is the single source of truth for session state
(conversation history, mode, concepts, assessments, teachings).

```text
                            YOUR MACHINE (localhost)

  +----------------+                            +----------------------+
  |    Terminal    |                            |       Browser        |
  | codelith (CLI) |                            | Dashboard (React +   |
  |                |                            | Vite + Mermaid)      |
  +--------+-------+                            +----------+-----------+
           |                                               |
           |  HTTP 127.0.0.1:8765                          |  HTTP + SSE
           |  POST /chat                                   |  127.0.0.1:8765
           |                                               |
           +---------------------+-------------------------+
                                 |
                                 v
  +---------------------------------------------------------------------+
  |                 DAEMON  (FastAPI + uvicorn)                         |
  |                                                                     |
  |  POST /chat                 run the agent graph, return reply       |
  |  POST /chat/stream          same, plus live SSE activity events     |
  |  GET/POST /mode             session mode (CLI <-> dashboard sync)   |
  |  GET /concepts              detected concepts for a session         |
  |  GET /assessments           questions + answer counts               |
  |  POST /assessments/answer   LLM-graded answer submission            |
  |  GET /teachings             teaching entries + Mermaid diagrams     |
  |  POST /question             dashboard Q&A (no file operations)      |
  |  GET /progress              learning progress summary               |
  |  GET /health                liveness probe (used by the launcher)   |
  |  GET /                      the built dashboard (static files)      |
  +-----------------------------+---------------------------------------+
                                |
                                v  run_graph()
  +---------------------------------------------------------------------+
  |           ORCHESTRATOR  (LangGraph state machine)                   |
  |                                                                     |
  |            +--------------+                                         |
  |            | coding agent |-------------------+                     |
  |            +--------------+                   | last run_command    |
  |                   | commands pass             | failed              |
  |                   v                           v                     |
  |     +---------------------+            +-------------+               |
  |     | detect concepts     |<-----------| debug agent |               |
  |     | (registry + LLM)    |  repaired  +-------------+               |
  |     +----------+----------+                                        |
  |                |                                                   |
  |                | mode disables questions? --------> END            |
  |                v                                                   |
  |     +-------------------+   mode: teacher does  +-----+             |
  |     | assessment agent  |   not run? ------->  | END |             |
  |     +---------+---------+                      +-----+             |
  |               |                                                    |
  |               v                                                    |
  |     +---------------+                                              |
  |     | teacher agent | -------------------------------------->  END |
  |     +---------------+                                              |
  +------+-----------------+-----------------------------+-------------+
         |                 |                             |
  +------v-------+  +------v---------+  +----------------v---------+
  | coding +     |  | concept        |  | assessment +             |
  | debug agents |  | detector       |  | teacher agents           |
  | tools:       |  | pattern        |  | question templates,      |
  | read_file    |  | registry + LLM |  | LLM grading, teaching    |
  | write_file   |  | fallback,      |  | entries                  |
  | edit_file    |  | Mermaid        |  |                          |
  | run_command  |  | diagrams       |  |                          |
  +------+-------+  +----------------+  +------------+-------------+
         |                                           |
         v                                           v
  +---------------------------------------------------------------------+
  |              LLM PROVIDERS  (HTTPS, external)                       |
  |  OpenRouter (coding + debug agents)   Groq (teaching-side agents)   |
  |  qwen/qwen3-coder-next (default)      openai/gpt-oss-120b (default) |
  +---------------------------------------------------------------------+

  +---------------------------------------------------------------------+
  |                 PERSISTENCE   ~/.codelith/                          |
  |  codelith.db (SQLite, WAL): concepts / teachings / assessments      |
  |  daemon.pid  daemon.port  .env (optional key file)                  |
  +---------------------------------------------------------------------+
```

### How a turn flows

1. **Your message** arrives at the daemon: `POST /chat` from the CLI, or
   `POST /chat/stream` from the dashboard with live activity events.
2. **Coding agent** plans and acts with tools — `read_file`, `write_file`,
   `edit_file`, and `run_command` against your workspace — in multiple tool
   rounds capped by the session mode.
3. **Routing** inspects the structured tool-call log, never the agent's reply
   text: if the most recent `run_command` failed (non-zero exit code or
   stderr), the **debug agent** takes over — it runs tests, reads the error,
   fixes the code, and re-runs within a capped retry loop. A clean turn skips
   it. Provider-side LLM errors are never "fixed" by the debug agent.
4. **Concept detection** runs exactly once per turn. A curated registry of
   known patterns (React hooks, async/await, decorators, Python OOP, ...)
   matches the files the coding agent wrote; anything unrecognised goes to an
   LLM pass (skipped in Autonomous mode to save calls). Each concept carries a
   description and a Mermaid diagram, cached by content hash so unchanged
   code is never re-analysed.
5. **Assessment agent** (mode-gated) turns new concepts into Socratic
   questions for the dashboard.
6. **Teacher agent** (mode-gated) writes or refreshes teaching entries and
   explanations; if your message was a direct question, it answers in the
   terminal instead.

### Key design decisions

- **Structured routing over keyword matching.** The debug agent is triggered
  by execution results recorded in the tool-call log, so a reply that merely
  mentions the word "error" can never misroute the graph.
- **One detection pass, shared.** Concept detection used to run in both the
  assessment and teacher agents; it now runs once in a shared node and both
  consumers read the result, halving LLM calls per turn.
- **Identity-keyed storage.** Concepts are keyed by a stable slug derived
  from the concept name, not by which file they appeared in, with a content
  hash of the underlying code so explanations are reused until the code
  actually changes.
- **Concurrent-safe local storage.** SQLite in WAL mode lets the daemon
  write while the dashboard reads without `database is locked` errors.
- **Fail-closed test isolation.** Under any test runner, the database
  resolves into a per-process temp directory, so tests can never touch real
  `~/.codelith` data — a structural guarantee, not a fixture convention.

## Repository layout

```text
CodeLith/
├── backend/
│   ├── agents/           # coding, debug, assessment, teacher agents + concept detector
│   ├── cli/              # the `codelith` command-line interface
│   ├── daemon/           # FastAPI server, detached-process launcher, state files
│   ├── database/         # SQLite persistence: concepts, teachings, assessments
│   ├── llm/              # Groq + OpenRouter clients, key and model resolution
│   ├── orchestrator/     # LangGraph agent graph, session modes, event stream
│   └── main.py           # backend entrypoint
├── frontend/             # React dashboard (Vite + TypeScript + Mermaid)
├── tests/                # pytest suite
├── pyproject.toml        # packaging config + `codelith` entry point
└── README.md
```

## Development setup

### Backend

```bash
git clone https://github.com/your-username/CodeLith
cd CodeLith
python -m venv .venv
.venv\Scripts\activate            # Windows (bash: source .venv/Scripts/activate)
pip install -e .
```

Run from source without installing the package:

```bash
python -m backend.cli.main
```

### Frontend

```bash
cd frontend
npm install
npm run dev       # dev server with hot reload, proxies API calls to :8765
npm run build     # production build, copied into the package's static folder
```

### Tests

```bash
python -m pytest tests/ -v
```

The suite covers diagram routing, concept categories, Mermaid validation,
mode-based routing after coding, and a store-isolation tripwire that fails if
any test could touch the real `~/.codelith` database.

## Packaging and publishing

The PyPI package ships only the `backend*` packages plus the built dashboard
static files; `tests/`, `frontend/` sources, and dev caches never leave git.

```bash
# 1. Build the dashboard and copy it into the package's static folder
cd frontend && npm run build && cd ..
# copy frontend/dist into the package's static directory

# 2. Build the distributables
python -m build

# 3. Publish to TestPyPI first and verify a clean install
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ codelith
codelith    # run it from a different folder to verify the entry point

# 4. Publish to PyPI
twine upload dist/*
```

## License

MIT — see [LICENSE](LICENSE).

