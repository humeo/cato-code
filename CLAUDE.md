# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Install dependencies (uses uv)
uv sync

# Run all tests
uv run pytest

# Run a single test
uv run pytest tests/test_basic.py::test_config_parses_owner_repo

# Run tests with verbose output
uv run pytest -v

# Run the CLI
uv run catocode --help
uv run catocode fix https://github.com/owner/repo/issues/123
```

## Architecture Overview

CatoCode is an **autonomous long-running codebase maintenance agent** that uses a **Skill+SDK hybrid architecture**:

```
Host: catocode (Python CLI + scheduler + SQLite)
  └── Docker Container "catocode-worker" (long-running)
      ├── Claude Agent SDK (the AI brain)
      ├── Development Tools (git, gh, python, node, uv, playwright)
      ├── ~/.claude/
      │   ├── CLAUDE.md         ← user-level rules (Proof of Work protocol)
      │   └── skills/           ← CatoCode skills (fix_issue, patrol, triage, etc.)
      └── /repos/{owner-repo}/
          ├── CLAUDE.md         ← repo-specific knowledge (init-generated)
          └── .claude/memory/   ← auto-memory
```

### Key Design Principles

1. **Autonomous Decision-Making**: CatoCode monitors ALL GitHub events (issues, PRs, comments) and autonomously decides when to engage
2. **Human-in-the-Loop**: For issue fixes, CatoCode first analyzes and proposes solutions, then waits for admin approval before executing
3. **Proactive PR Review**: Automatically reviews all new PRs with detailed feedback
4. **Event-Driven**: Uses GitHub webhooks (not polling) for real-time response
5. **Skills as Markdown**: Prompt templates live in `src/catocode/container/skills/*/SKILL.md`, not hardcoded in Python
6. **SDK Execution**: Uses Claude Agent SDK for reliability (retry, session resume, streaming logs)
7. **Proof of Work**: Every bug fix requires Before/After evidence (mandatory protocol)
8. **Multi-repo**: One container serves multiple repositories

## Core Modules

- `cli.py` - CLI with subcommands: fix, watch, daemon, status, logs
- `store.py` - SQLite database (repos, activities, logs)
- `scheduler.py` - Main loop + worker pool + webhook server
- `dispatcher.py` - SDK execution + log streaming
- `skill_renderer.py` - Renders skill templates with variable substitution
- `container/manager.py` - Docker container lifecycle management
- `github/issue_fetcher.py` - GitHub API interactions
- `github/webhook_handler.py` - Real-time GitHub webhook processing
- `github/commenter.py` - PR/issue commenting
- `decision_engine.py` - Autonomous decision-making (when to engage, what action to take)

## Skills

Skills are Markdown files that define agent behavior. Located in `src/catocode/container/skills/`:

| Skill | Purpose | Trigger Format |
|-------|---------|----------------|
| `analyze_issue` | Analyze issue, suggest solutions, wait for approval | `issue:123` |
| `fix_issue` | Execute approved fix with Proof of Work evidence | `issue:123` (after approval) |
| `review_pr` | Proactively review PR code, suggest improvements | `pr:123` |
| `respond_review` | Address PR review comments | `pr:123` |
| `respond_comment` | Respond to mentions/questions in comments | `comment:456` |
| `patrol` | Proactive codebase scan, create analysis reports | `budget:5` |

Each skill has:
- `SKILL.md` - Prompt template with YAML frontmatter
- `README.md` - Usage documentation
- `evals/evals.json` - Test cases (optional)

### Skill Execution Flow

1. **Webhook received** → `decision_engine.py` analyzes event
2. **Decision made** → Select appropriate skill (analyze_issue, review_pr, etc.)
3. **Skill rendered** → `skill_renderer.py` fills template with context
4. **SDK executes** → `dispatcher.py` runs Claude Agent SDK
5. **Result posted** → Comment/PR created on GitHub
6. **Wait for human** → If approval needed, activity pauses until admin responds

## Proof of Work Protocol

CatoCode enforces a two-layer evidence protocol for all bug fixes:

**Layer 1: Reproduction Evidence (MANDATORY)**
- Run failing test → capture output
- Trigger the bug → save error logs
- Take "before" screenshot (for UI bugs)

**Layer 2: Verification Evidence (MANDATORY)**
- Apply the fix
- Run same test → capture success
- Take "after" screenshot
- Run full test suite → no regressions

Every PR includes a Before/After evidence table. This is non-negotiable.

## Activity Types

| Activity | Trigger | What CatoCode Does |
|----------|---------|-------------------|
| `init` | First time watching repo | Explores codebase, generates CLAUDE.md |
| `review_pr` | New PR opened | **Proactively reviews code**, suggests improvements, finds bugs |
| `analyze_issue` | New issue opened | **Analyzes root cause**, suggests solution, waits for admin approval |
| `fix_issue` | Admin approves fix | Reproduces → fixes → verifies → PR (with Proof of Work) |
| `respond_review` | PR review comments | Addresses feedback, pushes updates |
| `respond_comment` | @mention or reply | Autonomously decides if response needed, executes request |
| `patrol` | Scheduled (e.g., every 12h) | Scans for bugs/security issues, creates analysis (not auto-fix) |

### Autonomous Workflow

**For New Issues:**
1. CatoCode receives webhook → analyzes issue
2. Posts comment with:
   - Root cause analysis
   - Potential solutions (ranked by risk/effort)
   - Reproduction steps (if applicable)
3. Waits for admin to reply with approval (e.g., "go ahead with solution 2")
4. Only then executes the fix with full Proof of Work

**For New PRs:**
1. CatoCode receives webhook → reviews all changes
2. Posts review with:
   - Code quality feedback
   - Potential bugs or security issues
   - Suggestions for improvement
   - Test coverage analysis
3. No auto-merge, human makes final decision

**For Comments/Mentions:**
1. CatoCode receives webhook → analyzes context
2. Autonomously decides if response is needed:
   - Direct @mention → always respond
   - Question about code → respond if relevant
   - Casual discussion → skip
3. If responding, executes request and reports back

## Git Identity

All commits are signed as:
```
Author: CatoCode <catocode@catocode.dev>
Committer: CatoCode <catocode@catocode.dev>
```

Optional Co-Authored-By can be added via `CATOCODE_USER_NAME` and `CATOCODE_USER_EMAIL` environment variables.

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...

# Optional
CATOCODE_MEM=8g                        # Container memory limit
CATOCODE_CPUS=4                        # Container CPU limit
CATOCODE_PATROL_MAX_ISSUES=5           # Max issues per patrol window
CATOCODE_PATROL_WINDOW_HOURS=12        # Patrol rate limit window
CATOCODE_USER_NAME="Your Name"         # For Co-Authored-By
CATOCODE_USER_EMAIL="your@email.com"   # For Co-Authored-By
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/catocode

# Run integration tests (requires Docker)
uv run pytest -m integration

# Run end-to-end tests (requires API keys)
uv run pytest -m e2e
```

Current status: 61 tests passing, 9 skipped

## Documentation

- `docs/SKILL_ARCHITECTURE.md` - Deep dive into Skill+SDK architecture
- `docs/SKILL_IMPLEMENTATION_SUMMARY.md` - Implementation details
- `docs/REBRANDING_COMPLETE_GUIDE.md` - Rebranding from RepoCraft to CatoCode
- `src/catocode/container/skills/` - All skill definitions
