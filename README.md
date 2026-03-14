<div align="center">

<img src="frontend/public/logo.svg" width="80" height="80" alt="CatoCode" />

# CatoCode

### 修 bug 要手动复现、修复、验证——CatoCode 替你做完这三步

[![CI](https://github.com/humeo/cato-code/actions/workflows/ci.yml/badge.svg)](https://github.com/humeo/cato-code/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-required-blue)](https://www.docker.com/)

[快速开始](#-快速开始) · [工作原理](#-工作原理) · [CLI 参考](#-cli-参考) · [配置](#-配置) · [贡献](#-贡献)

</div>

---

> [!IMPORTANT]
> **CatoCode 会做什么：**
> - 在本地运行 Docker 容器（隔离执行环境）
> - 调用 Anthropic API（你的代码片段会发送给 Anthropic 用于分析）
> - 向 GitHub 发送 comment、创建 PR
>
> **CatoCode 不会做什么：**
> - 不会将代码发送给除 Anthropic 以外的第三方
> - 不会在没有你 `/approve` 的情况下自动提交代码（默认审批流）
>
> **如何停止：** `docker compose down` 立即停止所有活动。

---

## 问题

你打开 GitHub，看到 12 个 open issues。

每修一个 bug，流程都一样：读 issue → 本地复现 → 定位原因 → 写修复 → 跑测试 → 提 PR。重复、耗时、容易出错。

AI 代码补全工具（Copilot、Cursor）能帮你写代码，但它们不会主动监听你的 repo、不会自己复现 bug、也不会给你留下可验证的证据。Devin 这类全自动工具走向另一个极端——你不知道它改了什么，也不知道该不该信任结果。

CatoCode 的定位在中间：**自动执行，但每一步都留证据，你来决定是否合并。**

---

## 快速开始

```bash
git clone https://github.com/humeo/cato-code.git
cd cato-code
cp .env.example .env          # 填入 ANTHROPIC_API_KEY 和 GITHUB_TOKEN
docker compose up -d
docker compose exec catocode catocode watch https://github.com/owner/repo
```

详细步骤见 [Docker Compose 部署](#-docker-compose-部署)。

---

## 看它工作

Issue 开启 → CatoCode 分析并评论 → 你回复 `/approve` → PR 创建，附带测试证据。全程约 5 分钟，你只需要审一个 PR。

完整流程：

```
# 1. 监听你的 repo
$ docker compose exec catocode catocode watch https://github.com/alice/myproject
✓ GitHub App has access to alice/myproject
Watching https://github.com/alice/myproject

# 2. 有人开了一个 issue：
#   "Bug: calculate_average() crashes when list is empty"

# 3. CatoCode 自动分析，在 issue 下留评论：
#   "我复现了这个 bug。根本原因是 ZeroDivisionError。
#    建议修复：在 calculate_average() 开头加空列表检查。
#    回复 /approve 让我执行修复。"

# 4. 你回复 /approve

# 5. CatoCode 执行修复，创建 PR，附带 Proof of Work：
$ catocode status
done  88b7ce3b  fix_issue  issue:42  $0.68

# PR 描述里包含：
# | Check           | Before              | After      |
# |-----------------|---------------------|------------|
# | Failing test    | ❌ ZeroDivisionError | ✅ PASS    |
# | Full test suite | 11 passed, 1 failed | 12 passed  |
```

你在 30 秒内就能验证结果——不需要本地跑测试。

---

## Docker Compose 部署

Docker Compose 是推荐的部署方式，不需要本地安装 Python。

### 1. Clone & 配置

```bash
git clone https://github.com/humeo/cato-code.git
cd cato-code
cp .env.example .env
```

编辑 `.env`，填入必填项：

| 变量 | 必填 | 说明 |
|------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | Anthropic API 密钥 |
| `GITHUB_TOKEN` | ✅ | GitHub PAT（需要 `repo` 权限） |
| `PORT` | | 服务端口（默认 `8000`） |
| `GIT_USER_NAME` | | 容器内 Git 提交用户名（默认 `CatoCode`） |
| `GIT_USER_EMAIL` | | 容器内 Git 提交邮箱（默认 `catocode@bot.local`） |
| `MAX_CONCURRENT` | | 最大并发任务数（默认 `3`） |
| `CATOCODE_MEM` | | Worker 容器内存限制（默认 `8g`） |
| `CATOCODE_CPUS` | | Worker 容器 CPU 限制（默认 `4`） |
| `CATOCODE_PATROL_MAX_ISSUES` | | 每个巡检窗口最大 issue 数（默认 `5`） |
| `CATOCODE_PATROL_WINDOW_HOURS` | | 巡检滚动窗口（默认 `12` 小时） |

完整变量列表见 [`.env.example`](.env.example)。

### 2. 启动

```bash
docker compose up -d
```

首次启动会自动构建 Docker 镜像（约 5–10 分钟），后续复用缓存。

### 3. 监听 Repo

```bash
docker compose exec catocode catocode watch https://github.com/owner/repo
```

### 4. 查看状态

```bash
# 查看监听的 repo 和最近活动
docker compose exec catocode catocode status

# 查看容器日志
docker compose logs -f catocode
```

### 5. Dashboard（可选）

前端 Dashboard 提供可视化的 repo 状态和活动历史：

```bash
cd frontend
cp .env.example .env.local   # 默认值即可
bun install
bun dev
# 打开 http://localhost:3000
```

### 6. 配置 Webhook（可选）

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

---

## CLI 参考

```bash
# 监听一个 repo（注册到本地 DB）
catocode watch https://github.com/owner/repo

# 停止监听
catocode unwatch https://github.com/owner/repo

# 启动 daemon（webhook server + scheduler）
catocode daemon --webhook-port 8080

# 立即修复一个 issue（无需 webhook）
catocode fix https://github.com/owner/repo/issues/42

# 查看监听的 repo 和最近活动
catocode status

# 查看某个 activity 的日志（activity ID 从 status 获取）
catocode logs <activity_id>
```

> **Tip**: Docker Compose 部署时在命令前加 `docker compose exec catocode`。
> 本地开发时使用 `uv run catocode`。

---

## 工作原理

```
┌─ Host Process ──────────────────────────────────────┐
│  CLI Daemon                                          │
│  ├── Scheduler (approval check, patrol, dispatch)   │
│  ├── Webhook Server (/webhook/github/{repo_id})      │
│  └── Store (SQLite at /data/catocode.db)             │
└──────────────────┬──────────────────────────────────┘
                   │ Docker API
┌─ Worker Container ──────────────────────────────────┐
│  catocode-worker                                    │
│  ├── Claude Agent SDK + Claude Code CLI             │
│  ├── Dev tools (git, gh, python, node, uv)          │
│  └── /repos/{owner-repo}/ (cloned repos)            │
└─────────────────────────────────────────────────────┘
```

**事件流：**

1. GitHub issue 开启 → webhook 触发（或 patrol 定时扫描）
2. Decision engine 分类事件，选择 skill
3. Worker 容器执行 Claude Agent，分析 issue，发布评论
4. 你回复 `/approve`
5. Agent 复现 bug → 写修复 → 跑测试 → 创建 PR，附带 Proof of Work

<details>
<summary><b>Skills 详情</b> — 每种自动化任务的触发条件和行为</summary>

Skills 是 Markdown 提示模板，存放在 `src/catocode/container/skills/`，可以直接编辑定制，无需改代码。

| Skill | 触发条件 | 行为 |
|-------|---------|------|
| `analyze_issue` | Issue 开启 | 分析 issue，发布分析评论，等待 `/approve` |
| `fix_issue` | `/approve` 后 | 复现 → 修复 → 验证 → 创建 PR（含 Proof of Work） |
| `review_pr` | PR 开启 | 审查代码质量、安全性、测试覆盖 |
| `respond_review` | PR review 评论 | 处理 review 反馈，推送更新 |
| `triage` | Issue 开启 | 分类并打标签 |
| `patrol` | 定时触发 | 主动扫描代码库，发现潜在 bug 和安全问题 |

</details>

<details>
<summary><b>审批流</b> — 如何控制 CatoCode 的行为</summary>

默认情况下，CatoCode 在执行修复前需要你的明确授权：

1. Issue 开启 → `analyze_issue` 发布分析评论，末尾附 "回复 `/approve` 继续"
2. 你（或有 write 权限的协作者）回复 `/approve`
3. Scheduler 检测到 approve 评论 → 创建 `fix_issue` activity
4. 修复执行，PR 创建，包含完整 Proof of Work

如果你信任某个 repo，可以通过修改 `analyze_issue` skill 跳过审批步骤。

</details>

---

## GitHub App 模式（进阶）

适合团队和组织：
- 自动覆盖 org 下所有 repo，无需逐个配置 webhook
- 无需手动管理 PAT

见 [docs/GITHUB_APP_SETUP.md](docs/GITHUB_APP_SETUP.md)。

---

## 开发

```bash
# 安装依赖（含开发工具）
uv sync --dev

# 运行测试
uv run pytest

# 带覆盖率
uv run pytest --cov=src/catocode

# 集成测试（需要 Docker）
uv run pytest -m integration

# Lint
uv run ruff check src/
uv run ruff check src/ --fix

# 前端
cd frontend && bun install && bun dev
```

---

## 贡献

1. Fork 仓库
2. 创建 feature 分支：`git checkout -b feature/amazing-feature`
3. 修改并添加测试
4. 运行测试：`uv run pytest`
5. 提交：`git commit -m "feat: add amazing feature"`
6. 开 PR

---

## License

Apache License 2.0 — 详见 [LICENSE](LICENSE)。

---

<div align="center">

[快速开始](#-快速开始) · [Docker 部署](#-docker-compose-部署) · [CLI 参考](#-cli-参考) · [贡献](#-贡献)

</div>
