#!/bin/bash

# Memora 单用户模式启动脚本
# 用于 OpenClaw Skills 后台运行

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  Memora 知识库 - 单用户模式"
echo "=========================================="
echo ""

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "❌ 未找到 .env 配置文件"
    echo "   请复制 .env.skills.example 为 .env 并配置"
    exit 1
fi

# 检查虚拟环境
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
    echo "❌ 未找到项目虚拟环境: $VENV_PYTHON"
    echo "   请先创建并初始化 venv:"
    echo "     python3 -m venv venv"
    echo "     ./venv/bin/pip install -r requirements.txt"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
"$VENV_PYTHON" -m pip list 2>/dev/null | grep -q -i "^fastapi " || {
    echo "⚠️  未安装依赖，正在安装到 venv..."
    "$VENV_PYTHON" -m pip install -r requirements.txt
}

# 检查端口是否已被占用
if lsof -i :8080 -sTCP:LISTEN -P -n >/dev/null 2>&1; then
    EXISTING_PID=$(lsof -ti :8080 -sTCP:LISTEN)
    echo "⚠️  端口 8080 已被占用 (PID: $EXISTING_PID)，服务可能已在运行"
    echo "   如需重启，请先执行: ./stop.sh"
    exit 1
fi

# 启动应用
echo ""
echo "🚀 启动 Memora 服务..."
echo "   端口: 8080"
echo "   日志: nohup.out"
echo ""

# 后台运行（使用 venv 的 Python 解释器）
nohup "$VENV_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8080 > nohup.out 2>&1 &

# 获取进程 ID
PID=$!
echo $PID > .memora.pid

echo "✅ 服务已启动！"
echo "   PID: $PID"
echo "   健康检查: http://localhost:8080/health"
echo ""
echo "查看日志: tail -f nohup.out"
echo "停止服务: kill \$(cat .memora.pid)"
