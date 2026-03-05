#!/bin/bash
# CatoCode 重命名脚本
# 将 RepoCraft 重命名为 CatoCode

set -e  # 遇到错误立即退出

echo "🏛️  CatoCode Rebranding Script"
echo "================================"
echo ""
echo "This script will rename RepoCraft to CatoCode"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

# 备份
echo "📦 Creating backup..."
BACKUP_DIR="backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r src tests docs pyproject.toml "$BACKUP_DIR/"
echo "✅ Backup created: $BACKUP_DIR"
echo ""

# 1. 重命名目录
echo "📁 Renaming directories..."
if [ -d "src/repocraft" ]; then
    mv src/repocraft src/catocode
    echo "✅ src/repocraft → src/catocode"
fi
echo ""

# 2. 更新 Python 文件中的导入和引用
echo "🐍 Updating Python files..."
find src tests -type f -name "*.py" -exec sed -i '' 's/repocraft/catocode/g' {} +
find src tests -type f -name "*.py" -exec sed -i '' 's/RepoCraft/CatoCode/g' {} +
find src tests -type f -name "*.py" -exec sed -i '' 's/REPOCRAFT/CATOCODE/g' {} +
echo "✅ Python files updated"
echo ""

# 3. 更新 Markdown 文档
echo "📝 Updating documentation..."
find docs -type f -name "*.md" -exec sed -i '' 's/RepoCraft/CatoCode/g' {} +
find docs -type f -name "*.md" -exec sed -i '' 's/repocraft/catocode/g' {} +
find docs -type f -name "*.md" -exec sed -i '' 's/REPOCRAFT/CATOCODE/g' {} +
echo "✅ Documentation updated"
echo ""

# 4. 更新 pyproject.toml
echo "📦 Updating pyproject.toml..."
sed -i '' 's/name = "repocraft"/name = "catocode"/g' pyproject.toml
sed -i '' 's/repocraft/catocode/g' pyproject.toml
sed -i '' 's/RepoCraft/CatoCode/g' pyproject.toml
echo "✅ pyproject.toml updated"
echo ""

# 5. 更新 Dockerfile
echo "🐳 Updating Dockerfile..."
if [ -f "src/catocode/container/Dockerfile" ]; then
    sed -i '' 's/repocraft-worker/catocode-worker/g' src/catocode/container/Dockerfile
    sed -i '' 's/repocraft/catocode/g' src/catocode/container/Dockerfile
    echo "✅ Dockerfile updated"
fi
echo ""

# 6. 更新容器脚本
echo "🔧 Updating container scripts..."
if [ -f "src/catocode/container/scripts/run_activity.py" ]; then
    sed -i '' 's/repocraft/catocode/g' src/catocode/container/scripts/run_activity.py
    echo "✅ Container scripts updated"
fi
echo ""

# 7. 更新环境变量引用
echo "🌍 Updating environment variable references..."
find src -type f -name "*.py" -exec sed -i '' 's/REPOCRAFT_/CATOCODE_/g' {} +
echo "✅ Environment variables updated"
echo ""

# 8. 更新 Git 配置相关代码
echo "🔐 Updating Git identity..."
find src -type f -name "*.py" -exec sed -i '' 's/GIT_USER_NAME/CATOCODE_GIT_USER_NAME/g' {} +
find src -type f -name "*.py" -exec sed -i '' 's/GIT_USER_EMAIL/CATOCODE_GIT_USER_EMAIL/g' {} +

# 在 manager.py 中设置固定的 CatoCode identity
if [ -f "src/catocode/container/manager.py" ]; then
    # 这个需要手动修改，因为涉及到逻辑变更
    echo "⚠️  Please manually update src/catocode/container/manager.py to set:"
    echo "    git config --global user.name 'CatoCode'"
    echo "    git config --global user.email 'catocode@catocode.dev'"
fi
echo ""

# 9. 更新数据库路径
echo "💾 Updating database paths..."
find src -type f -name "*.py" -exec sed -i '' 's/\.repocraft/\.catocode/g' {} +
echo "✅ Database paths updated"
echo ""

# 10. 更新 README
echo "📖 Updating README..."
if [ -f "README_CATOCODE.md" ]; then
    mv README.md README_OLD.md 2>/dev/null || true
    mv README_CATOCODE.md README.md
    echo "✅ README updated"
fi
echo ""

# 11. 清理 Python 缓存
echo "🧹 Cleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "✅ Cache cleaned"
echo ""

# 12. 重新安装依赖
echo "📦 Reinstalling dependencies..."
if command -v uv &> /dev/null; then
    uv sync
    echo "✅ Dependencies reinstalled"
else
    echo "⚠️  uv not found, please run 'uv sync' manually"
fi
echo ""

# 13. 运行测试
echo "🧪 Running tests..."
if command -v uv &> /dev/null; then
    uv run pytest -v
    echo "✅ Tests passed"
else
    echo "⚠️  Please run 'uv run pytest' manually to verify"
fi
echo ""

# 完成
echo "================================"
echo "✅ Rebranding complete!"
echo ""
echo "📋 Next steps:"
echo "1. Review changes: git diff"
echo "2. Update your environment variables:"
echo "   - REPOCRAFT_* → CATOCODE_*"
echo "3. Manually update Git identity in manager.py"
echo "4. Create CatoCode avatar (see docs/BRAND_ASSETS.md)"
echo "5. Test the renamed application:"
echo "   uv run catocode --help"
echo "6. Commit changes:"
echo "   git add -A"
echo "   git commit -m 'rebrand: RepoCraft → CatoCode'"
echo ""
echo "🏛️  Welcome to CatoCode - The Incorruptible Code Guardian!"
