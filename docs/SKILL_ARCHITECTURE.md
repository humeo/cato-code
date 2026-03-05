# Skill+SDK 混合架构实现总结

## 概述

CatoCode v3 现在使用 **Skill+SDK 混合架构**，结合了两者的优势：
- **Skills**：可维护的 Markdown 格式 prompt 模板
- **SDK**：可靠的执行引擎，支持会话恢复、重试、流式日志

## 架构对比

### 之前（硬编码 Prompt）

```python
# templates/prompts.py
def fix_issue_prompt(issue_number, issue_title, issue_body, ...):
    return f"""
    You are fixing issue #{issue_number}...
    [500 lines of hardcoded instructions]
    """

# dispatcher.py
prompt = fix_issue_prompt(issue.number, issue.title, ...)
await exec_sdk_runner(prompt, ...)
```

**问题**：
- Prompt 硬编码在 Python 中，修改需要重新部署
- 无法利用 Claude Code 的原生功能（CLAUDE.md、skills）
- 用户无法自定义

### 现在（Skill+SDK）

```python
# skill_renderer.py
def build_fix_issue_prompt(issue_number, repo_id, issue_data):
    skill_template = read_skill("fix_issue")  # 读取 SKILL.md
    return render_skill_prompt(skill_template, {
        "issue_number": issue_number,
        "repo_id": repo_id,
    }) + f"\n\n## Current Task\n{issue_data}"

# dispatcher.py
prompt = build_fix_issue_prompt(issue_number, repo_id, issue_data)
await exec_sdk_runner(prompt, ...)
```

**优势**：
- Prompt 在 Markdown 文件中，易于维护
- 用户可以覆盖 skill 文件自定义
- 保持 SDK 的可靠性（重试、会话恢复、流式日志）

## 文件结构

```
src/catocode/
├── skill_renderer.py              ← 新增：Skill 渲染引擎
├── dispatcher.py                  ← 修改：使用 skill_renderer
└── container/
    ├── Dockerfile                 ← 修改：复制 skills 到容器
    └── skills/                    ← 新增：Skill 定义
        ├── fix_issue/
        │   ├── SKILL.md           ← Prompt 模板
        │   ├── README.md          ← 使用说明
        │   └── evals/
        │       └── evals.json     ← 测试用例
        ├── patrol/
        │   └── SKILL.md
        ├── triage/
        │   └── SKILL.md
        └── respond_review/
            └── SKILL.md
```

## 容器内布局

```
Container: catocode-worker
  /home/catocode/.claude/
    ├── CLAUDE.md                  ← 用户级规则（Proof of Work 协议）
    └── skills/                    ← CatoCode skills
        ├── fix_issue/SKILL.md
        ├── patrol/SKILL.md
        ├── triage/SKILL.md
        └── respond_review/SKILL.md

  /repos/{owner-repo}/
    ├── CLAUDE.md                  ← 仓库特定知识（init 生成）
    └── .claude/memory/            ← auto-memory
```

## 执行流程

### 1. 用户触发

```bash
catocode fix https://github.com/owner/repo/issues/123
```

### 2. Dispatcher 构建 Prompt

```python
# dispatcher.py
async def _build_prompt(activity, repo, github_token):
    if activity["kind"] == "fix_issue":
        issue_number = parse_trigger(activity["trigger"])  # "issue:123" -> "123"
        issue = await fetch_issue(owner, repo_name, issue_number, github_token)

        # 使用 skill_renderer
        return build_fix_issue_prompt(
            issue_number=issue_number,
            repo_id=repo["id"],
            issue_data=format_issue(issue),
        )
```

### 3. Skill Renderer 读取模板

```python
# skill_renderer.py
def build_fix_issue_prompt(issue_number, repo_id, issue_data):
    # 1. 读取 skill 文件
    skill_template = read_skill("fix_issue")
    # /home/catocode/.claude/skills/fix_issue/SKILL.md

    # 2. 变量替换
    skill_content = render_skill_prompt(skill_template, {
        "issue_number": issue_number,
        "repo_id": repo_id,
    })

    # 3. 附加当前任务上下文
    prompt = f"""{skill_content}

---

## Current Task

You are fixing issue #{issue_number} in repository {repo_id}.

### Issue Details

{issue_data}

Begin now.
"""
    return prompt
```

### 4. SDK 执行

```python
# dispatcher.py
await exec_sdk_runner(
    prompt=prompt,
    workdir=f"/repos/{repo_id}",
    max_turns=200,
    session_id=resume_session_id,  # 用于 respond_review
    ...
)
```

### 5. 流式日志

```python
# container/manager.py
async for line in exec_stream(cmd):
    store.append_log(activity_id, line)
    if verbose:
        print(line)
```

## Skill 文件格式

### YAML Frontmatter

```yaml
---
name: fix_issue
description: Fix a GitHub issue with rigorous Proof of Work evidence collection. Use this skill whenever...
---
```

### Markdown Body

```markdown
# Fix Issue with Proof of Work

You are fixing a GitHub issue using CatoCode's Self-Proving methodology.

## Context Setup

1. Read `~/.claude/CLAUDE.md` for universal rules
2. Read `/repos/{repo_id}/CLAUDE.md` for repo-specific conventions
3. Fetch issue: `gh issue view {issue_number}`

## The Two-Layer Evidence Protocol

### Layer 1: Reproduction Evidence (MANDATORY)
...

### Layer 2: Verification Evidence (MANDATORY)
...

## Step-by-Step Workflow
...
```

### 变量替换

Skill 中可以使用 `{variable}` 占位符：
- `{issue_number}` → 实际的 issue 编号
- `{repo_id}` → 仓库 ID
- `{budget_remaining}` → 剩余预算（patrol）

## 已实现的 Skills

### 1. fix_issue

**用途**：修复 GitHub issue，强制要求 Before/After 证据

**触发格式**：`issue:123`

**关键特性**：
- Layer 1: 复现 bug，捕获失败输出
- Layer 2: 验证修复，捕获成功输出
- 创建 PR，包含证据表格
- 分支命名：`catocode/fix/{issue_number}-{slug}`

### 2. patrol

**用途**：主动扫描代码库，发现 bug 和安全漏洞

**触发格式**：`budget:5`

**关键特性**：
- 优先级：安全 > 崩溃 > 逻辑错误 > 代码质量
- 强制要求复现证据（不允许推测性 issue）
- 预算限制（防止 issue 泛滥）
- 使用 `gh issue create` 创建 issue

### 3. triage

**用途**：分类新 issue，尝试快速复现，提供有用回复

**触发格式**：`issue:123`

**关键特性**：
- 分类：bug / feature / question / duplicate
- 快速复现尝试（5-10 分钟）
- 添加标签
- 发布实质性回复

### 4. respond_review

**用途**：响应 PR review 评论，修复问题，推送更新

**触发格式**：`pr:123`

**关键特性**：
- 会话恢复（PR 分支已存在）
- 逐条处理 review 评论
- 不使用 force-push
- 包含修复证据

## 用户自定义

用户可以通过覆盖 skill 文件来自定义行为：

### 方法 1：容器内覆盖

```bash
# 在容器内
cat > /home/catocode/.claude/skills/fix_issue/SKILL.md << 'EOF'
---
name: fix_issue
description: My custom fix_issue skill
---

# My Custom Fix Process
...
EOF
```

### 方法 2：主机挂载

```python
# container/manager.py
docker.containers.run(
    volumes={
        "/path/to/custom/skills": {
            "bind": "/home/catocode/.claude/skills",
            "mode": "ro"
        }
    }
)
```

## 测试

每个 skill 都有测试用例：

```json
{
  "skill_name": "fix_issue",
  "evals": [
    {
      "id": 1,
      "prompt": "Fix GitHub issue #42...",
      "expected_output": "Should reproduce, fix, verify, create PR...",
      "files": []
    }
  ]
}
```

运行测试（未来实现）：
```bash
python -m scripts.test_skill fix_issue
```

## 迁移路径

### 短期（当前）

✅ 使用 Skill+SDK 混合方案
- Prompt 在 Markdown 文件中（易维护）
- SDK 执行（可靠、可控）
- 用户可自定义 skill

### 长期（观察）

如果 Claude Code CLI 未来支持：
- Skill 参数传递：`claude -p /repo /fix_issue issue:123`
- JSONL 流式输出
- 会话恢复

则可以完全迁移到 CLI：
```python
# 从 SDK 迁移到 CLI
await exec_claude_cli(f"claude -p /repos/{repo_id} /fix_issue issue:{issue_num}")
```

但当前 SDK 方案已经足够好。

## 优势总结

| 特性 | 硬编码 Prompt | Skill+SDK | 纯 CLI |
|------|--------------|-----------|--------|
| Prompt 可维护性 | ❌ | ✅ | ✅ |
| 用户自定义 | ❌ | ✅ | ✅ |
| 执行可靠性 | ✅ | ✅ | ❓ |
| 会话恢复 | ✅ | ✅ | ❓ |
| 重试机制 | ✅ | ✅ | ❌ |
| 流式日志 | ✅ | ✅ | ❓ |
| 热更新 | ❌ | ✅ | ✅ |

**结论**：Skill+SDK 是当前最优方案。

## 下一步

1. ✅ 创建 fix_issue skill
2. ✅ 创建 patrol skill
3. ✅ 创建 triage skill
4. ✅ 创建 respond_review skill
5. ✅ 更新 dispatcher 使用 skill_renderer
6. ✅ 更新 Dockerfile 复制 skills
7. ⏳ 创建 review_pr skill
8. ⏳ 创建 task skill（通用任务执行）
9. ⏳ 添加 skill 测试框架
10. ⏳ 编写用户文档

## 相关文件

- `src/catocode/skill_renderer.py` - Skill 渲染引擎
- `src/catocode/dispatcher.py` - 使用 skill_renderer
- `src/catocode/container/Dockerfile` - 复制 skills 到容器
- `src/catocode/container/skills/*/SKILL.md` - Skill 定义
- `src/catocode/templates/user_claude_md.py` - 用户级 CLAUDE.md（Proof of Work 协议）
