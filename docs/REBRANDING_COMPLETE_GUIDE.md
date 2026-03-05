# 🏛️ CatoCode 重命名完成指南

## 📋 已创建的文件

### 1. 核心文档
- ✅ `README_CATOCODE.md` - 全新的 CatoCode README
- ✅ `docs/BRAND_ASSETS.md` - 品牌资产和设计指南
- ✅ `docs/GIT_IDENTITY_UPDATE.md` - Git identity 配置指南
- ✅ `scripts/rebrand_to_catocode.sh` - 自动重命名脚本

### 2. 现有文档（已创建，待更新）
- `docs/SKILL_ARCHITECTURE.md` - 需要更新名称
- `docs/SKILL_IMPLEMENTATION_SUMMARY.md` - 需要更新名称
- `docs/REBRANDING_GUIDE.md` - 重命名策略文档

## 🚀 执行重命名的步骤

### 步骤 1：运行自动重命名脚本

```bash
# 给脚本执行权限
chmod +x scripts/rebrand_to_catocode.sh

# 运行脚本（会自动备份）
./scripts/rebrand_to_catocode.sh
```

脚本会自动完成：
- ✅ 创建备份
- ✅ 重命名目录 `src/catocode` → `src/catocode`
- ✅ 更新所有 Python 文件中的导入
- ✅ 更新文档中的名称
- ✅ 更新 `pyproject.toml`
- ✅ 更新 Dockerfile
- ✅ 更新环境变量引用
- ✅ 清理缓存
- ✅ 重新安装依赖
- ✅ 运行测试

### 步骤 2：手动更新 Git Identity

按照 `docs/GIT_IDENTITY_UPDATE.md` 的指南，手动修改：

1. **`src/catocode/container/manager.py`** (第 167 行)
   ```python
   def _configure_git_identity(self) -> None:
       """Set git identity as CatoCode inside the container."""
       self.exec('git config --global user.name "CatoCode"')
       self.exec('git config --global user.email "catocode@catocode.dev"')
       self.exec("git config --global --add safe.directory '*'")
       self.exec("git config --global credential.helper catocode")
       logger.debug("Git identity: CatoCode <catocode@catocode.dev>")
   ```

2. **`src/catocode/container/Dockerfile`** (第 38 行)
   ```dockerfile
   RUN printf '#!/bin/bash\necho "protocol=https"\necho "host=github.com"\necho "username=x-access-token"\necho "password=${GITHUB_TOKEN}"\n' \
         > /usr/local/bin/git-credential-catocode \
       && chmod +x /usr/local/bin/git-credential-catocode \
       && git config --global credential.helper catocode
   ```

3. **`src/catocode/config.py`** (添加新函数)
   ```python
   def get_user_name() -> str:
       """Get user name for Co-Authored-By (optional)."""
       return os.environ.get("CATOCODE_USER_NAME", "")

   def get_user_email() -> str:
       """Get user email for Co-Authored-By (optional)."""
       return os.environ.get("CATOCODE_USER_EMAIL", "")
   ```

### 步骤 3：更新 README

```bash
# 替换旧 README
mv README.md README_OLD.md
mv README_CATOCODE.md README.md
```

### 步骤 4：创建 CatoCode 头像

参考 `docs/BRAND_ASSETS.md`，创建头像：

**快速方案（临时）**：
- 使用 🏛️ emoji
- 或让 GitHub 自动生成 identicon

**专业方案**：
- 使用 AI 生成工具（DALL-E, Midjourney）
- Prompt: "A minimalist logo for CatoCode. Ancient Roman column in white on dark blue background, with golden code brackets. Professional, clean, 512x512 pixels."
- 上传到 Gravatar（邮箱：`catocode@catocode.dev`）

### 步骤 5：更新环境变量

```bash
# 旧环境变量（删除）
unset CATOCODE_MEM
unset CATOCODE_CPUS
unset CATOCODE_PATROL_MAX_ISSUES
unset GIT_USER_NAME
unset GIT_USER_EMAIL

# 新环境变量
export CATOCODE_MEM=8g
export CATOCODE_CPUS=4
export CATOCODE_PATROL_MAX_ISSUES=5

# 可选：用于 Co-Authored-By
export CATOCODE_USER_NAME="Your Name"
export CATOCODE_USER_EMAIL="your@email.com"
```

### 步骤 6：测试

```bash
# 测试 CLI
uv run catocode --help

# 测试容器构建
cd src/catocode/container
docker build -t catocode-worker:v1 .

# 测试 Git identity
docker run --rm catocode-worker:v1 git config --global user.name
# 应该输出: CatoCode

# 运行所有测试
uv run pytest -v
```

### 步骤 7：提交更改

```bash
# 查看更改
git status
git diff

# 添加所有更改
git add -A

# 提交
git commit -m "rebrand: CatoCode → CatoCode

- Rename all modules from catocode to catocode
- Update Git identity to use fixed CatoCode identity
- Add Co-Authored-By support for user attribution
- Update all documentation and README
- Create brand assets guide

BREAKING CHANGE: Environment variables renamed from CATOCODE_* to CATOCODE_*"

# 推送（可选）
# git push origin main
```

## 📦 迁移现有数据（如果需要）

如果你已经在使用 CatoCode，需要迁移数据：

```bash
# 迁移 SQLite 数据库
mkdir -p ~/.catocode
cp ~/.catocode/catocode.db ~/.catocode/catocode.db

# 迁移自定义 skills（如果有）
cp -r ~/.catocode/skills ~/.catocode/skills

# 清理旧容器和镜像
docker stop catocode-worker 2>/dev/null || true
docker rm catocode-worker 2>/dev/null || true
docker rmi catocode-worker:v1 2>/dev/null || true
```

## 🎯 验证清单

完成重命名后，验证以下内容：

- [ ] CLI 命令可用：`uv run catocode --help`
- [ ] 所有测试通过：`uv run pytest`
- [ ] Docker 镜像构建成功
- [ ] Git identity 正确：`CatoCode <catocode@catocode.dev>`
- [ ] 环境变量更新完成
- [ ] README 更新完成
- [ ] 文档中的名称全部更新
- [ ] 没有残留的 "catocode" 引用

## 🔍 检查残留引用

```bash
# 搜索可能遗漏的 catocode 引用
grep -r "catocode" src/ tests/ docs/ --exclude-dir=__pycache__ --exclude="*.pyc"

# 搜索可能遗漏的 CatoCode 引用
grep -r "CatoCode" src/ tests/ docs/ --exclude-dir=__pycache__ --exclude="*.pyc"

# 搜索可能遗漏的 CATOCODE 引用
grep -r "CATOCODE" src/ tests/ docs/ --exclude-dir=__pycache__ --exclude="*.pyc"
```

## 🚨 常见问题

### Q: 重命名后测试失败？
A: 运行 `uv sync` 重新安装依赖，清理缓存：
```bash
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
uv sync
```

### Q: Docker 镜像构建失败？
A: 检查 Dockerfile 中的路径是否都已更新：
```bash
grep -n "catocode" src/catocode/container/Dockerfile
```

### Q: Git identity 没有生效？
A: 检查 `manager.py` 中的 `_configure_git_identity()` 是否正确修改。

### Q: 环境变量不工作？
A: 确保使用新的变量名 `CATOCODE_*` 而不是 `CATOCODE_*`。

## 📚 下一步

重命名完成后，你可以：

1. **创建品牌资产**
   - 设计 logo
   - 创建头像
   - 设置 Gravatar

2. **准备发布**
   - 创建 GitHub repository
   - 设置 GitHub topics: `ai`, `code-maintenance`, `autonomous-agent`, `proof-of-work`
   - 准备 Product Hunt 发布

3. **营销推广**
   - 撰写技术博客
   - 录制 demo 视频
   - 准备 Hacker News 发布

4. **社区建设**
   - 创建 CONTRIBUTING.md
   - 设置 GitHub Discussions
   - 创建 Twitter 账号 @catocode_dev

## 🏛️ 欢迎来到 CatoCode！

> "Integrity is doing the right thing, even when no one is watching."
> — Cato the Elder

CatoCode 不只是一个名字的改变，它代表了一种理念：
- **Integrity** - 每个修复都有证据
- **Uncompromising** - 不妥协的质量标准
- **Trustworthy** - 可验证的 AI 助手

让我们一起构建一个值得信赖的 AI 代码维护工具！🚀
