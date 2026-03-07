# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest

# Run a single test
uv run pytest tests/test_basic.py::test_config_parses_owner_repo

# Run tests with coverage
uv run pytest --cov=src/catocode

# Run integration tests (requires Docker)
uv run pytest -m integration

# Run the CLI
uv run catocode --help

# CLI mode: watch a repo + run daemon
uv run catocode watch https://github.com/owner/repo
uv run catocode daemon --webhook-port 8080

# SaaS mode: unified server (OAuth + API + webhooks + scheduler)
uv run catocode server --port 8000

# Frontend (Next.js)
cd frontend && bun install && bun dev
```

## Architecture Overview

CatoCode is an **autonomous GitHub code maintenance agent** with two operating modes:

1. **CLI mode** — Single-user, personal access token, `watch` + `daemon` commands
2. **SaaS mode** — Multi-tenant, GitHub App + OAuth, unified `server` command with Next.js frontend

```
┌─ Host Process ──────────────────────────────────────┐
│  CLI / FastAPI Server                                │
│  ├── Scheduler (3 async loops)                       │
│  ├── Webhook Server (per-repo + app-level)           │
│  ├── OAuth + REST API (SaaS mode)                    │
│  ├── Decision Engine                                 │
│  └── Store (SQLite or PostgreSQL)                    │
└──────────────────┬──────────────────────────────────┘
                   │ Docker API
┌─ Per-User Container ────────────────────────────────┐
│  catocode-worker[-{user_id}]                        │
│  ├── Claude Agent SDK (run_activity.py)              │
│  ├── Dev tools (git, gh, python, node, uv)           │
│  ├── /repos/{owner-repo}/ (cloned repos)             │
│  └── ~/.claude/ (skills, CLAUDE.md, memory)          │
└─────────────────────────────────────────────────────┘
```

## Core Execution Flow

1. **Event arrives** → GitHub webhook or CLI command
2. **Decision engine** (`decision/engine.py`) → classify event, pick skill (analyze_issue, review_pr, etc.)
3. **Activity created** → stored in DB with `pending` status
4. **Scheduler** (`scheduler.py`) → picks pending activities, respects per-repo serial lock + global semaphore
5. **Dispatcher** (`dispatcher.py`) → ensures container running, builds prompt via `skill_renderer.py`, executes SDK runner
6. **SDK runner** (`container/scripts/run_activity.py`) → runs inside Docker container with Claude Agent SDK
7. **Result** → comment/PR posted to GitHub, activity marked `done`

## Key Modules

### Orchestration
- `cli.py` — Entry point. Subcommands: `server`, `watch`, `unwatch`, `daemon`, `fix`, `status`, `logs`
- `scheduler.py` — Three async loops: approval check (30s), patrol scan (per-repo interval), dispatch (5s). Per-repo serial locks, global concurrency semaphore (default 3)
- `dispatcher.py` — Activity execution: container setup → repo clone → prompt build → SDK run (up to 3 retries) → log streaming → status update
- `skill_renderer.py` — Reads `SKILL.md` templates, strips YAML frontmatter, substitutes variables, builds complete prompts

### Data Layer
- `db.py` — Dual-backend abstraction: SQLite (`?` placeholders, WAL mode, thread lock) and PostgreSQL (`%s` placeholders, psycopg2). `connect(url)` factory returns normalized `Connection`
- `store.py` — All data operations: users, sessions, repos, activities, logs, webhooks, installations, patrol budget. Schema migrations via `_MIGRATIONS` list

### Authentication (`auth/`)
- Factory pattern in `__init__.py`: prefers GitHub App (`GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY` + `GITHUB_APP_INSTALLATION_ID`), falls back to `GITHUB_TOKEN`
- `github_app.py` — Signs JWT with RSA private key, exchanges for 1-hour installation tokens, auto-refreshes before expiry
- `token.py` — Simple PAT wrapper

### API Layer (`api/`) — SaaS Mode
- `app.py` — FastAPI factory: mounts OAuth router, protected API router, webhook server, and dashboard
- `oauth.py` — GitHub OAuth 2.0: `/auth/github` (login), `/auth/github/callback` (token exchange), `/auth/github/install-callback` (app installation linking). 30-day session cookies
- `routes.py` — Protected endpoints: `/api/me`, `/api/stats`, `/api/repos`, `/api/activities`, `/api/install-url`
- `deps.py` — Session cookie validation, user extraction dependency
- `crypto.py` — Fernet encryption for stored GitHub access tokens

### Webhook System (`webhook/`)
- `server.py` — FastAPI receiver with two endpoint patterns: per-repo (`/webhook/github/{repo_id}`) and app-level (`/webhook/app`). Handles `installation` events (auto-watch repos), signature verification (optional if no secret configured), deduplication via delivery ID
- `parser.py` — Normalizes GitHub events into `WebhookEvent` objects with trigger format (`issue:123`, `pr:456`)
- `verifier.py` — HMAC-SHA256 signature verification

### Decision Engine (`decision/`)
- `engine.py` — Maps events to actions: issue opened → `analyze_issue`, PR opened → `review_pr`, approval comment → `fix_issue`, @mention → `task`. Skips CatoCode's own PRs
- `parser.py` — Event classification helpers, admin checks

### Container Management (`container/`)
- `manager.py` — Docker lifecycle: build image, create/start container, exec commands, update tokens (writes to `/etc/profile.d/` for `bash -lc` sessions), reset repos. Per-user naming in SaaS mode (`catocode-worker-{user_id[:8]}`)
- `registry.py` — `ContainerRegistry`: lazy dict of `user_id → ContainerManager` for multi-tenancy
- `scripts/run_activity.py` — Executed inside container; runs Claude Agent SDK with prompt file

### GitHub Integration (`github/`)
- `commenter.py` — Posts issue/PR comments, failure notifications
- `issue_fetcher.py` — Fetches issue details via GitHub API
- `permissions.py` — Checks repo write access (handles both PAT `/user` endpoint and App `/installation/repositories` endpoint)
- `poller.py` — Legacy polling (mostly replaced by webhooks)

## Skills

Markdown prompt templates in `src/catocode/container/skills/`:

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `analyze_issue` | `issue:N` | Analyze issue, suggest solutions, post comment, wait for `/approve` |
| `fix_issue` | `issue:N` | Execute approved fix with Proof of Work evidence |
| `review_pr` | `pr:N` | Review PR code quality, security, tests |
| `respond_review` | `pr:N` | Address PR review feedback (session resume) |
| `triage` | `issue:N` | Classify and label issues |
| `patrol` | `budget:N` | Proactive codebase scan for bugs/security |

Each skill has `SKILL.md` (template with `{variable}` placeholders) and `README.md`.

## Approval Flow

1. New issue → `analyze_issue` posts analysis comment with "Reply `/approve` to proceed"
2. Admin replies `/approve` (or "go ahead", etc.)
3. Scheduler's approval loop detects comment → creates `fix_issue` activity
4. Fix executes with full Proof of Work (before/after evidence)

## Frontend

Next.js 15 + React 19 + TypeScript + Tailwind CSS in `frontend/`. Uses `bun` for package management.

Key pages: landing (`/`), GitHub App install (`/install`), dashboard (`/dashboard`).
API client in `frontend/src/lib/api.ts` talks to backend at `CATOCODE_BASE_URL`.

## Environment Variables

```bash
# Required (one auth method)
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...                    # CLI mode (PAT)
# OR
GITHUB_APP_ID=...                       # SaaS mode (GitHub App)
GITHUB_APP_PRIVATE_KEY=...              # RSA private key (newlines as \n)
GITHUB_APP_INSTALLATION_ID=...

# SaaS mode additional
GITHUB_OAUTH_CLIENT_ID=...
GITHUB_OAUTH_CLIENT_SECRET=...
SESSION_SECRET_KEY=...                  # 32+ byte hex for Fernet
CATOCODE_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
GITHUB_APP_NAME=catocode-bot

# Optional
ANTHROPIC_BASE_URL=...                  # Custom API endpoint
CATOCODE_MEM=8g                         # Container memory limit
CATOCODE_CPUS=4                         # Container CPU limit
CATOCODE_PATROL_MAX_ISSUES=5
CATOCODE_PATROL_WINDOW_HOURS=12
DATABASE_URL=postgresql://...           # Default: SQLite at data/catocode.db
```

## SaaS vs CLI Mode

The daemon auto-detects mode based on environment:
- **SaaS mode**: `GITHUB_OAUTH_CLIENT_ID` + `SESSION_SECRET_KEY` set → unified FastAPI app with OAuth, API, webhooks
- **CLI mode**: Otherwise → webhook-only server

In SaaS mode, repos and activities are scoped to `user_id`. Container registry creates per-user Docker containers.
