# CatoCode Git Identity 配置指南

## 🔐 Git Identity 变更

CatoCode 使用固定的 Git identity，所有 commit 都以 CatoCode 的名义提交。

### 变更前（CatoCode）
```python
# 使用用户的 Git identity
name = get_git_user_name()  # 从环境变量 GIT_USER_NAME
email = get_git_user_email()  # 从环境变量 GIT_USER_EMAIL
```

### 变更后（CatoCode）
```python
# 使用固定的 CatoCode identity
name = "CatoCode"
email = "catocode@catocode.dev"

# 用户信息通过 Co-Authored-By 添加
co_author = f"{user_name} <{user_email}>"  # 从环境变量获取
```

## 📝 需要修改的文件

### 1. `src/catocode/container/manager.py`

找到 `_configure_git_identity` 方法（约第 167 行），修改为：

```python
def _configure_git_identity(self) -> None:
    """Set git identity as CatoCode inside the container."""
    # Fixed CatoCode identity
    self.exec('git config --global user.name "CatoCode"')
    self.exec('git config --global user.email "catocode@catocode.dev"')
    self.exec("git config --global --add safe.directory '*'")
    self.exec("git config --global credential.helper catocode")
    logger.debug("Git identity: CatoCode <catocode@catocode.dev>")
```

### 2. `src/catocode/config.py`

添加获取用户信息的函数（用于 Co-Authored-By）：

```python
def get_user_name() -> str:
    """Get user name for Co-Authored-By (optional)."""
    return os.environ.get("CATOCODE_USER_NAME", "")

def get_user_email() -> str:
    """Get user email for Co-Authored-By (optional)."""
    return os.environ.get("CATOCODE_USER_EMAIL", "")
```

### 3. Commit 消息模板

在创建 commit 时，添加 Co-Authored-By：

```python
def create_commit_message(summary: str, issue_number: str | None = None) -> str:
    """Create commit message with Co-Authored-By."""
    message = f"{summary}\n\n"

    if issue_number:
        message += f"Fixes #{issue_number}\n\n"

    # Add Co-Authored-By if user info is available
    user_name = get_user_name()
    user_email = get_user_email()
    if user_name and user_email:
        message += f"Co-Authored-By: {user_name} <{user_email}>\n"

    return message
```

## 🎨 Git Credential Helper

更新 credential helper 名称：

### Dockerfile 中（约第 38 行）

```dockerfile
# 变更前
RUN printf '#!/bin/bash\necho "protocol=https"\necho "host=github.com"\necho "username=x-access-token"\necho "password=${GITHUB_TOKEN}"\n' \
      > /usr/local/bin/git-credential-catocode \
    && chmod +x /usr/local/bin/git-credential-catocode \
    && git config --global credential.helper catocode

# 变更后
RUN printf '#!/bin/bash\necho "protocol=https"\necho "host=github.com"\necho "username=x-access-token"\necho "password=${GITHUB_TOKEN}"\n' \
      > /usr/local/bin/git-credential-catocode \
    && chmod +x /usr/local/bin/git-credential-catocode \
    && git config --global credential.helper catocode
```

## 🔄 环境变量变更

### 旧环境变量（删除）
```bash
GIT_USER_NAME="Your Name"
GIT_USER_EMAIL="your@email.com"
```

### 新环境变量（可选）
```bash
# 用于 Co-Authored-By（可选）
CATOCODE_USER_NAME="Your Name"
CATOCODE_USER_EMAIL="your@email.com"
```

## 📋 完整的修改清单

- [ ] 修改 `src/catocode/container/manager.py` 中的 `_configure_git_identity()`
- [ ] 修改 `src/catocode/container/Dockerfile` 中的 credential helper
- [ ] 添加 `get_user_name()` 和 `get_user_email()` 到 `config.py`
- [ ] 更新 commit 消息生成逻辑（添加 Co-Authored-By）
- [ ] 更新文档中的环境变量说明
- [ ] 测试 Git commit 是否正确显示 CatoCode 作为 author

## 🧪 测试

重命名后，测试 Git identity：

```bash
# 启动容器
uv run catocode watch https://github.com/test/repo

# 进入容器检查
docker exec -it catocode-worker bash

# 验证 Git 配置
git config --global user.name    # 应该显示: CatoCode
git config --global user.email   # 应该显示: catocode@catocode.dev

# 测试 commit
cd /repos/test-repo
echo "test" > test.txt
git add test.txt
git commit -m "test: verify git identity"
git log -1 --pretty=full
# 应该显示:
# Author: CatoCode <catocode@catocode.dev>
# Commit: CatoCode <catocode@catocode.dev>
```

## 📧 Gravatar 设置

为了让 GitHub 显示 CatoCode 的头像：

1. **注册邮箱**：`catocode@catocode.dev`（或使用 GitHub noreply）
2. **上传头像到 Gravatar**：https://gravatar.com/
3. **GitHub 自动识别**：GitHub 会根据邮箱显示 Gravatar 头像

### 临时方案（使用 GitHub noreply）

如果不想注册独立邮箱，可以使用：
```
catocode@users.noreply.github.com
```

GitHub 会为这个邮箱生成一个默认的 identicon。

## 🎯 最终效果

### Commit 显示
```
commit abc123def456...
Author: CatoCode <catocode@catocode.dev>
Date:   Wed Mar 5 19:00:00 2026 +0800

    fix: add null check for email field

    Fixes #123

    Co-Authored-By: Your Name <your@email.com>
```

### GitHub PR 显示
```
CatoCode committed 2 hours ago
✓ fix: add null check for email field (#124)

Co-authored-by: Your Name <your@email.com>
```

### GitHub Insights 显示
- **Contributor**: CatoCode（主要贡献者）
- **Co-Author**: Your Name（协作者）

这样既明确了是 AI 做的工作，又给予了项目所有者应有的认可。
