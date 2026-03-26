# GitHub App SaaS Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current global PAT/global-installation auth path with a multi-user SaaS GitHub App model that uses encrypted user tokens in the control plane and per-installation short-lived tokens at runtime.

**Architecture:** Keep one platform-managed GitHub App. Split GitHub auth into two runtime classes: user tokens for control-plane access and installation tokens for repo execution. Resolve runtime GitHub credentials per repo/activity instead of from one global env variable. Preserve the existing session/worktree/runtime envelope architecture.

**Tech Stack:** Python 3.12, FastAPI, SQLite/PostgreSQL via `Store`, GitHub App OAuth + installation tokens, Docker worker containers, pytest, `uv`, Next.js dashboard

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/catocode/config.py` | Modify | Replace PAT-first config with GitHub App SaaS config getters |
| `src/catocode/auth/base.py` | Modify | Separate user-token and installation-token auth interfaces |
| `src/catocode/auth/github_app.py` | Modify | Support app-JWT, per-installation token minting, and user-token exchange helpers |
| `src/catocode/auth/__init__.py` | Modify | Remove global installation/PAT product path from SaaS runtime selection |
| `src/catocode/store.py` | Modify | Persist repo-to-installation bindings explicitly |
| `src/catocode/api/oauth.py` | Modify | Use GitHub App OAuth flow and installation linking consistently |
| `src/catocode/api/routes.py` | Modify | Filter dashboard repos by installation presence plus write permission |
| `src/catocode/webhook/server.py` | Modify | Bind repos to installations and keep installation state in sync |
| `src/catocode/scheduler.py` | Modify | Resolve installation token per repo before dispatch |
| `src/catocode/dispatcher.py` | Modify | Accept per-activity installation token instead of global GitHub token |
| `src/catocode/container/manager.py` | Modify | Continue injecting only the resolved installation token into workers |
| `src/catocode/github/permissions.py` | Modify | Make control-plane permission checks user-token aware |
| `tests/test_auth.py` | Modify | Cover SaaS auth config and token minting boundaries |
| `tests/test_github_app.py` | Modify | Cover GitHub App token flows and repo-installation resolution |
| `tests/test_webhook.py` | Modify | Cover installation/repo binding updates |
| `tests/test_dashboard.py` | Modify | Cover installed-and-writeable repo filtering |
| `tests/test_webhook_session_routing.py` | Modify | Ensure runtime dispatch still routes correctly with per-repo tokens |

### Task 1: Make Repo Installations First-Class

**Files:**
- Modify: `src/catocode/store.py`
- Modify: `tests/test_github_app.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- recording a repo's installation binding
- looking up a repo's installation id
- clearing or updating the binding when installation membership changes

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_github_app.py -v`
Expected: FAIL because repo installation helpers do not exist yet.

- [ ] **Step 3: Implement repo-installation persistence**

Add explicit repo-to-installation storage and query helpers.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_github_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/catocode/store.py tests/test_github_app.py
git commit -m "feat: persist repo installation bindings"
```

### Task 2: Replace Global Auth with GitHub App SaaS Primitives

**Files:**
- Modify: `src/catocode/config.py`
- Modify: `src/catocode/auth/base.py`
- Modify: `src/catocode/auth/github_app.py`
- Modify: `src/catocode/auth/__init__.py`
- Modify: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- required GitHub App SaaS config getters
- no PAT-first product path in SaaS mode
- app service can mint an installation token for an arbitrary installation id

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL because auth is still global-token/global-installation based.

- [ ] **Step 3: Implement GitHub App SaaS auth primitives**

Split:
- app-level credentials
- user-token storage/use
- per-installation token minting

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/catocode/config.py src/catocode/auth/base.py src/catocode/auth/github_app.py src/catocode/auth/__init__.py tests/test_auth.py
git commit -m "feat: add github app saas auth primitives"
```

### Task 3: Fix OAuth and Installation Linking Around the Single GitHub App

**Files:**
- Modify: `src/catocode/api/oauth.py`
- Modify: `src/catocode/webhook/server.py`
- Modify: `tests/test_webhook.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- login callback stores encrypted user token
- installation callback links installation to the logged-in user
- installation and installation_repositories events bind repos to installations

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_webhook.py -v`
Expected: FAIL because repo-installation linking and SaaS auth assumptions are incomplete.

- [ ] **Step 3: Implement OAuth/install binding updates**

Keep one GitHub App for login and install, and persist installation ownership plus repo membership.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_webhook.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/catocode/api/oauth.py src/catocode/webhook/server.py tests/test_webhook.py
git commit -m "feat: link github app installs to saas users"
```

### Task 4: Filter Dashboard Repos by Installation and Write Permission

**Files:**
- Modify: `src/catocode/api/routes.py`
- Modify: `src/catocode/github/permissions.py`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- dashboard repo list only includes repos installed for the platform App
- current user must have write permission to see/manage the repo

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: FAIL because current repo listing is ownership-based, not installation+permission based.

- [ ] **Step 3: Implement dashboard filtering**

Use the logged-in user's token for control-plane repo visibility and management checks.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/catocode/api/routes.py src/catocode/github/permissions.py tests/test_dashboard.py
git commit -m "feat: filter dashboard repos by installation access"
```

### Task 5: Resolve Installation Tokens Per Activity

**Files:**
- Modify: `src/catocode/scheduler.py`
- Modify: `src/catocode/dispatcher.py`
- Modify: `src/catocode/container/manager.py`
- Modify: `tests/test_webhook_session_routing.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- dispatch resolves the repo's installation id first
- runtime execution uses a repo-specific installation token
- worker injection remains token-scoped to the activity

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_webhook_session_routing.py -v`
Expected: FAIL because runtime still depends on one global auth token.

- [ ] **Step 3: Implement per-activity installation token resolution**

Thread the resolved installation token through scheduler -> dispatcher -> container manager.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_webhook_session_routing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/catocode/scheduler.py src/catocode/dispatcher.py src/catocode/container/manager.py tests/test_webhook_session_routing.py
git commit -m "feat: resolve installation tokens per activity"
```

### Task 6: Close the Auth Migration with Regression Verification

**Files:**
- Modify as needed based on prior tasks

- [ ] **Step 1: Run focused backend suite**

Run: `uv run pytest tests/test_auth.py tests/test_github_app.py tests/test_webhook.py tests/test_webhook_session_routing.py tests/test_dashboard.py -v`
Expected: PASS

- [ ] **Step 2: Run full backend suite**

Run: `uv run pytest`
Expected: PASS

- [ ] **Step 3: Run targeted lint**

Run: `uv run ruff check src/catocode/config.py src/catocode/auth/base.py src/catocode/auth/github_app.py src/catocode/auth/__init__.py src/catocode/store.py src/catocode/api/oauth.py src/catocode/api/routes.py src/catocode/webhook/server.py src/catocode/scheduler.py src/catocode/dispatcher.py src/catocode/container/manager.py src/catocode/github/permissions.py tests/test_auth.py tests/test_github_app.py tests/test_webhook.py tests/test_webhook_session_routing.py tests/test_dashboard.py`
Expected: PASS

- [ ] **Step 4: Run frontend build**

Run: `cd frontend && bun run build`
Expected: PASS

- [ ] **Step 5: Commit final cleanups**

```bash
git add <any remaining files>
git commit -m "test: close github app saas auth migration"
```
