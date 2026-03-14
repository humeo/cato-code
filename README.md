# 🏛️ CatoCode

**The Autonomous GitHub Code Maintenance Agent**

> Named after Cato the Elder, the Roman statesman renowned for his unwavering integrity. CatoCode never compromises—every bug fix comes with proof, every claim backed by evidence.

[![CI](https://github.com/humeo/cato-code/actions/workflows/ci.yml/badge.svg)](https://github.com/humeo/cato-code/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-required-blue)](https://www.docker.com/)

---

## 🎯 What Is CatoCode?

CatoCode is an **autonomous agent** that monitors your GitHub repositories and:

- **Fixes bugs** — reproduces them first, then patches, then verifies
- **Reviews PRs** — catches quality issues before merge
- **Triages issues** — classifies, labels, and responds automatically
- **Patrols code** — proactively scans for security issues and bugs

Every action includes **Proof of Work**: before/after evidence so you can verify results in 30 seconds without manual testing.

```markdown
| Check            | Before               | After       |
|------------------|----------------------|-------------|
| Failing test     | ❌ FAIL              | ✅ PASS     |
| Full test suite  | 41 passed, 1 failed  | 42 passed   |
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/humeo/cato-code.git
cd cato-code
cp .env.example .env          # 编辑 .env，填入 ANTHROPIC_API_KEY 和 GITHUB_TOKEN
docker compose up -d          # 启动服务
docker compose exec catocode catocode watch https://github.com/owner/repo
```

详细步骤见下方 [Docker Compose 部署](#-docker-compose-recommended)。

---

## 🔄 How It Works

1. **New issue opened** on GitHub → webhook fires to CatoCode
2. **Daemon receives** the event → `analyze_issue` activity created
3. **Docker worker container** spins up (built automatically on first run)
4. **Claude Agent** analyzes the issue, posts a comment with analysis + proposed solutions
5. **You reply** `/approve` on the GitHub issue
6. **CatoCode** creates a PR with the fix + Proof of Work evidence

---

## 📋 CLI Reference

```bash
# Watch a repo (registers in local DB)
catocode watch https://github.com/owner/repo

# Stop watching a repo
catocode unwatch https://github.com/owner/repo

# Start the daemon (webhook server + scheduler)
catocode daemon --webhook-port 8080

# Fix a specific issue immediately (no webhook needed)
catocode fix https://github.com/owner/repo/issues/42

# Show watched repos and recent activity
catocode status

# View logs for an activity (get activity ID from `catocode status`)
catocode logs <activity_id>
```

> **Tip**: 使用 Docker Compose 时，在命令前加 `docker compose exec catocode`，例如 `docker compose exec catocode catocode watch ...`。
> 本地开发时使用 `uv run catocode watch ...`。

---

## 🏗️ Architecture

```
┌─ Host Process ──────────────────────────────────────┐
│  CLI Daemon                                          │
│  ├── Scheduler (approval check, patrol, dispatch)   │
│  ├── Webhook Server (/webhook/github/{repo_id})      │
│  └── Store (SQLite at /data/catocode.db)       │
└──────────────────┬──────────────────────────────────┘
                   │ Docker API
┌─ Worker Container ──────────────────────────────────┐
│  catocode-worker                                    │
│  ├── Claude Agent SDK + Claude Code CLI             │
│  ├── Dev tools (git, gh, python, node, uv)          │
│  └── /repos/{owner-repo}/ (cloned repos)            │
└─────────────────────────────────────────────────────┘
```

The Docker image is built automatically on first run (~5–10 minutes). Subsequent starts reuse the cached image.

### Skills

CatoCode uses Markdown prompt templates called **skills**:

| Skill | Trigger | What It Does |
|-------|---------|--------------|
| `analyze_issue` | Issue opened | Analyzes issue, posts plan, waits for `/approve` |
| `fix_issue` | After `/approve` | Reproduces → patches → verifies → creates PR |
| `review_pr` | PR opened | Reviews code quality, security, tests |
| `respond_review` | PR review comments | Addresses feedback, pushes updates |
| `triage` | Issue opened | Classifies and labels issues |
| `patrol` | Scheduled | Proactive scan for bugs/security issues |

Skills live in `src/catocode/container/skills/` and can be customized without code changes.

---

## ⚙️ Configuration

All configuration through environment variables. Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

| 变量 | 必填 | 说明 |
|------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | Anthropic API 密钥 |
| `GITHUB_TOKEN` | ✅ | GitHub PAT（需要 `repo` 权限） |
| `PORT` | | 服务监听端口（默认 `8000`） |
| `GIT_USER_NAME` | | 容器内 Git 提交用户名（默认 `CatoCode`） |
| `GIT_USER_EMAIL` | | 容器内 Git 提交邮箱（默认 `catocode@bot.local`） |
| `MAX_CONCURRENT` | | 最大并发任务数（默认 `3`） |
| `CATOCODE_MEM` | | Worker 容器内存限制（默认 `8g`） |
| `CATOCODE_CPUS` | | Worker 容器 CPU 限制（默认 `4`） |
| `CATOCODE_PATROL_MAX_ISSUES` | | 每个巡检窗口最大 issue 数（默认 `5`） |
| `CATOCODE_PATROL_WINDOW_HOURS` | | 巡检滚动窗口（默认 `12` 小时） |

完整变量列表见 [`.env.example`](.env.example)。

---

## 🐳 Docker Compose (Recommended)

Docker Compose 是最简单的部署方式，不需要本地安装 Python/uv。

### 1. Clone & Configure

```bash
git clone https://github.com/humeo/cato-code.git
cd cato-code
cp .env.example .env
```

编辑 `.env`，填入你的配置值。CLI 模式下必填项：

| 变量 | 说明 | 示例 |
|------|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | `sk-ant-...` |
| `GITHUB_TOKEN` | GitHub Personal Access Token (需要 `repo` 权限) | `ghp_...` |

其他变量都有默认值，可按需调整（容器资源、巡检频率、Git 身份等），详见 `.env.example` 中的注释。

### 2. Start

```bash
docker compose up -d
```

CatoCode 服务启动在端口 `8000`（可通过 `.env` 中的 `PORT` 修改）。

首次启动会自动构建 Docker 镜像（约 5-10 分钟），后续启动复用缓存。

### 3. Watch a Repo

```bash
docker compose exec catocode catocode watch https://github.com/owner/repo
```

### 4. Check Status

```bash
# 查看监听的仓库和最近活动
docker compose exec catocode catocode status

# 查看日志
docker compose logs -f catocode
```

### 5. (Optional) Expose Webhook

没有 webhook，CatoCode 仍然可以工作（patrol 巡检 + `fix` 命令）。配置 webhook 后可以**实时**响应新 issue 和 PR。

```bash
# 安装 cloudflared (macOS)
brew install cloudflare/cloudflare/cloudflared

# 创建临时公网隧道
cloudflared tunnel --url http://localhost:8000
```

在 GitHub 仓库 Settings → Webhooks 中添加：
- **URL**: `https://<tunnel-id>.trycloudflare.com/webhook/github/{owner-repo}`
- **Content type**: `application/json`
- **Events**: Issues, Issue comments, Pull requests, Pull request reviews

> `{owner-repo}` 格式为 `owner-repo`，例如 `alice-myproject`

### 6. (Optional) Frontend Dashboard

前端 Dashboard 提供可视化的仓库状态和活动历史，CLI 模式下无需登录。

```bash
cd frontend
cp .env.example .env.local   # 默认值即可，无需修改
bun install
bun dev
# 打开 http://localhost:3000
```

> **Note**: Docker Compose 挂载了 Docker socket，使 CatoCode 能管理 worker 容器。数据通过 Docker volume（`catocode-data`）持久化。

---

## 🔐 GitHub App Mode (Advanced)

For teams and organizations, GitHub App mode offers:
- Automatic installation across all repos in an org
- OAuth dashboard with per-user activity tracking
- No need to manually configure webhooks per repo

See [docs/GITHUB_APP_SETUP.md](docs/GITHUB_APP_SETUP.md) for setup instructions.

---

## 🧪 Development

```bash
# Install dependencies (including dev tools)
uv sync --dev

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/catocode

# Run integration tests (requires Docker)
uv run pytest -m integration

# Lint
uv run ruff check src/
uv run ruff check src/ --fix

# Frontend
cd frontend && bun install && bun dev
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run tests: `uv run pytest`
5. Commit: `git commit -m "feat: add amazing feature"`
6. Open a PR

---

## 🔒 Security

- Your code never leaves your infrastructure (except the Anthropic API)
- GitHub token stored locally in `.env` — never committed
- CatoCode runs in an isolated Docker container with limited permissions
- All commits are attributed to the configured `GIT_USER_NAME` / `GIT_USER_EMAIL`

---

## 📄 License

Apache License 2.0 — see [LICENSE](LICENSE) for details.

---

<div align="center">

**"Integrity is doing the right thing, even when no one is watching."**
— Cato the Elder

[Quick Start](#-quick-start) • [Docker Deploy](#-docker-compose-recommended) • [CLI Reference](#-cli-reference) • [Contributing](#-contributing)

</div>
