# 🏛️ CatoCode

**The Incorruptible Code Guardian**

> Named after Cato the Elder, the Roman statesman renowned for his unwavering integrity and strict moral standards. Like its namesake, CatoCode never compromises—every bug fix comes with proof, every claim backed by evidence.

[![Tests](https://img.shields.io/badge/tests-61%20passed-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-required-blue)](https://www.docker.com/)

---

## 🎯 The Problem with AI Code Assistants

AI coding tools are confident but often wrong. They say "I fixed it" without proof. You spend hours verifying their work, running tests, checking edge cases. The promise of "AI saves time" falls apart.

**The trust problem is real:**
- ❌ AI generates code that looks right but fails in production
- ❌ No way to verify claims without manual testing
- ❌ Fixes break other parts of the codebase
- ❌ You become the QA for the AI

## ✨ The CatoCode Solution

CatoCode implements **Proof of Work**—a two-layer evidence protocol inspired by Cato's uncompromising standards:

```
Layer 1: Reproduction Evidence (Mandatory)
├─ Run the failing test → capture output
├─ Trigger the bug → save error logs
└─ Take "before" screenshot → prove it's broken

Layer 2: Verification Evidence (Mandatory)
├─ Apply the fix
├─ Run the same test → capture success
├─ Take "after" screenshot → prove it works
└─ Run full test suite → no regressions
```

**Every PR includes a Before/After Evidence Table. No trust required—just look at the proof.**

---

## 🏛️ Why "Cato"?

**Cato the Elder** (234-149 BC) was a Roman statesman famous for:
- **Integrity**: Never compromised his principles
- **Strict Standards**: Demanded evidence and accountability
- **Incorruptibility**: Could not be bribed or swayed

These values are the foundation of CatoCode:
- **No lies**: Every claim backed by evidence
- **No shortcuts**: Mandatory proof collection
- **No exceptions**: The protocol is enforced, always

---

## 🚀 Quick Start

### Prerequisites
- Docker
- Python 3.12+
- GitHub account
- Anthropic API key ([get one here](https://console.anthropic.com/))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/catocode.git
cd catocode

# Install dependencies
uv sync

# Set up environment
export ANTHROPIC_API_KEY="your-api-key"
export GITHUB_TOKEN="your-github-token"

# Start watching a repository
uv run catocode watch https://github.com/owner/repo

# Start the daemon (runs in background)
uv run catocode daemon
```

### Fix a Single Issue (No Daemon)

```bash
uv run catocode fix https://github.com/owner/repo/issues/123
```

---

## 📖 How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Host: CatoCode Daemon (Python)                             │
│  ├─ Scheduler (3 async loops)                               │
│  │  ├─ Poll GitHub events (60s)                             │
│  │  ├─ Patrol scan (12h interval)                           │
│  │  └─ Dispatch pending activities                          │
│  ├─ SQLite Store (repos, activities, logs)                  │
│  └─ Container Manager                                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  Container: catocode-worker (Docker)                        │
│  ├─ Claude Agent SDK (the AI brain)                         │
│  ├─ Development Tools                                        │
│  │  ├─ git, gh (GitHub CLI)                                 │
│  │  ├─ Python, Node.js, uv                                  │
│  │  └─ Playwright (for screenshots)                         │
│  └─ Multi-repo workspace                                     │
│     └─ /repos/{owner-repo}/                                 │
│        ├─ CLAUDE.md (repo knowledge)                        │
│        └─ .claude/memory/ (learning)                        │
└─────────────────────────────────────────────────────────────┘
```

### Git Identity

All commits are signed by CatoCode:

```
Author: CatoCode <catocode@catocode.dev>
Committer: CatoCode <catocode@catocode.dev>

Co-Authored-By: Your Name <your@email.com>
```

This makes it clear that CatoCode did the work, while crediting you as the project owner.

---

## 🎯 Features

### 🔧 Autonomous Bug Fixing
- Monitors GitHub issues 24/7
- **Reproduces bugs before fixing** (mandatory)
- Creates PRs with complete evidence chains
- Handles review feedback automatically

### 🔍 Proactive Code Patrol
- Scans your codebase for security vulnerabilities
- Finds bugs before users do
- Rate-limited (won't spam you with issues)
- **Only reports bugs it can actually reproduce**

### 🏷️ Intelligent Issue Triage
- Classifies new issues (bug/feature/question)
- Attempts quick reproduction
- Adds labels and helpful responses
- Detects duplicates

### 💬 Natural Interaction
- Mention `@catocode` in any issue/PR
- Ask it to add features, refactor code, investigate problems
- All interaction through GitHub—no separate UI

---

## 📊 The Proof of Work Protocol

### For Bug Fixes

Every PR includes an evidence table like this:

```markdown
## Evidence

### Before (reproduction)
<details>
<summary>Test output showing failure</summary>

\`\`\`
FAILED tests/test_login.py::test_null_email
AttributeError: 'NoneType' object has no attribute 'lower'
\`\`\`
</details>

### After (verification)
<details>
<summary>Test output showing fix</summary>

\`\`\`
PASSED tests/test_login.py::test_null_email
PASSED tests/test_login.py (42 tests in 2.3s)
\`\`\`
</details>

### Summary
| Check | Before | After |
|-------|--------|-------|
| Failing test | ❌ FAIL | ✅ PASS |
| Full test suite | 41 passed, 1 failed | 42 passed |
| Related functionality | Broken | Working |
```

### For Security Issues
- Exploit code that triggers the vulnerability
- Proof that the exploit no longer works
- Security test coverage

### For UI Bugs
- Before/after screenshots
- Browser console logs
- Network request traces

**30 seconds to verify. No manual testing required.**

---

## 🎮 Usage Examples

### Watch a Repository

```bash
# Start monitoring a repo
catocode watch https://github.com/myorg/myapp

# This will:
# 1. Clone the repo
# 2. Explore it and generate CLAUDE.md (repo knowledge)
# 3. Start watching for new issues/PRs
# 4. Run periodic security scans
```

### Fix an Issue

```bash
# Fix a specific issue (blocking, shows logs)
catocode fix https://github.com/myorg/myapp/issues/42

# CatoCode will:
# 1. Read the issue
# 2. Reproduce the bug (Layer 1 evidence)
# 3. Write a minimal fix
# 4. Verify it works (Layer 2 evidence)
# 5. Create a PR with evidence table
```

### Mention in Comments

```markdown
@catocode can you add caching to the user API endpoint?
```

CatoCode will:
- Read the PR/issue context
- Implement the feature
- Add tests
- Reply with what it did

### Check Status

```bash
# View all watched repos
catocode status

# View specific repo activities
catocode status myorg-myapp

# View activity logs
catocode logs activity_abc123 --follow
```

---

## 🛠️ Configuration

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...           # Your Anthropic API key
GITHUB_TOKEN=ghp_...                   # GitHub personal access token

# Optional
ANTHROPIC_BASE_URL=https://...         # Custom API endpoint
CATOCODE_MEM=8g                        # Container memory limit
CATOCODE_CPUS=4                        # Container CPU limit
CATOCODE_PATROL_MAX_ISSUES=5           # Max issues per patrol window
CATOCODE_PATROL_WINDOW_HOURS=12        # Patrol rate limit window
```

### Customizing Skills

CatoCode uses a skill-based architecture. You can customize any behavior:

```bash
# Override the fix_issue skill
cat > ~/.catocode/skills/fix_issue/SKILL.md << 'EOF'
---
name: fix_issue
description: My custom fix process
---

# Custom Fix Process
1. Always add extensive logging
2. Write integration tests, not just unit tests
3. Update documentation
...
EOF
```

---

## 📊 Activity Types

| Activity | Trigger | What CatoCode Does |
|----------|---------|-------------------|
| `init` | First time watching repo | Explores codebase, generates CLAUDE.md |
| `fix_issue` | New issue opened | Reproduces → fixes → verifies → PR |
| `triage` | New issue opened | Classifies, attempts reproduction, replies |
| `patrol` | Scheduled (e.g., every 12h) | Scans for bugs/security issues |
| `respond_review` | PR review comments | Addresses feedback, pushes updates |
| `task` | @mention in comment | Executes arbitrary request |

---

## 🧪 Testing

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

Current test coverage: **61 tests, all passing**

---

## 🏗️ Architecture Deep Dive

### Why Docker?

CatoCode runs in a container for:
- **Security**: Isolated from your host system
- **Reproducibility**: Same environment everywhere
- **Multi-repo**: One container serves multiple repos
- **Tool availability**: Pre-installed dev tools

### Why Claude Agent SDK?

We use the SDK (not just the CLI) because:
- **Type safety**: Structured output, not string parsing
- **Control**: Retry logic, timeouts, session resume
- **Hooks**: Intercept dangerous operations
- **Streaming**: Real-time log output

### Why Skills?

Skills are Markdown files that define agent behavior:
- **Maintainable**: Edit prompts without code changes
- **Customizable**: Users can override any skill
- **Versionable**: Track prompt changes in git
- **Hot-reload**: No redeployment needed

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Add tests**: `tests/test_your_feature.py`
5. **Run tests**: `uv run pytest`
6. **Commit**: `git commit -m "feat: add amazing feature"`
7. **Push**: `git push origin feature/amazing-feature`
8. **Open a PR**

### Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/catocode.git
cd catocode

# Install dev dependencies
uv sync --dev

# Run tests in watch mode
uv run pytest-watch

# Build the Docker image
cd src/catocode/container
docker build -t catocode-worker:dev .
```

---

## 📚 Documentation

- [Architecture Guide](docs/SKILL_ARCHITECTURE.md) - Deep dive into the skill system
- [Implementation Summary](docs/SKILL_IMPLEMENTATION_SUMMARY.md) - How we built it
- [Skills Reference](src/catocode/container/skills/) - All available skills

---

## 🗺️ Roadmap

### v1.0 (Current)
- ✅ Fix issues with proof of work
- ✅ Proactive patrol scanning
- ✅ Issue triage
- ✅ PR review response
- ✅ Skill-based architecture

### v1.1 (Next)
- ⏳ PR review (proactive code review)
- ⏳ Multi-language support (currently Python/JS focused)
- ⏳ Custom patrol rules
- ⏳ Slack/Discord notifications

### v2.0 (Future)
- 🔮 Learning from feedback (improve over time)
- 🔮 Team collaboration (multiple agents)
- 🔮 Cost optimization (cheaper models for simple tasks)
- 🔮 Web dashboard (visual activity monitoring)

---

## ⚠️ Limitations

**What CatoCode Can Do:**
- Fix bugs with clear reproduction steps
- Find security vulnerabilities
- Respond to specific requests
- Work with standard dev tools (git, npm, pytest, etc.)

**What It Can't Do (Yet):**
- Understand complex business logic without context
- Make architectural decisions
- Handle issues requiring human judgment
- Work with proprietary/closed-source tools

**Cost Considerations:**
- Uses Claude Opus/Sonnet (premium models)
- Typical cost: $0.50-$2 per issue fix
- Patrol scans: $1-$5 per scan (depending on codebase size)
- Budget accordingly for production use

---

## 🔒 Security

### Data Privacy
- All code stays in your Docker container
- No code sent to third parties (except Anthropic API)
- GitHub tokens stored locally only
- Logs stored in local SQLite

### Permissions
- Requires GitHub token with `repo` scope
- Runs in isolated Docker container
- No sudo/root access needed on host
- All git commits signed as CatoCode

### Best Practices
- Use a dedicated GitHub account for CatoCode
- Rotate API keys regularly
- Review PRs before merging (always)
- Set up branch protection rules

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

---

## 🙏 Acknowledgments

- Built with [Claude](https://www.anthropic.com/claude) by Anthropic
- Inspired by Cato the Elder's unwavering integrity
- Thanks to all contributors and early adopters

---

## 💬 Community

- **Issues**: [GitHub Issues](https://github.com/yourusername/catocode/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/catocode/discussions)
- **Twitter**: [@catocode_dev](https://twitter.com/catocode_dev)

---

## ⭐ Star History

If CatoCode helps you maintain code integrity, consider giving it a star!

[![Star History Chart](https://api.star-history.com/svg?repos=yourusername/catocode&type=Date)](https://star-history.com/#yourusername/catocode&Date)

---

<div align="center">

**"Integrity is doing the right thing, even when no one is watching."**
— Cato the Elder

Built with unwavering standards by developers who believe AI should prove its work.

[Get Started](#-quick-start) • [Documentation](docs/) • [Contributing](#-contributing)

</div>
