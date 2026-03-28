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

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
pip3 list | grep -q fastapi || {
    echo "⚠️  未安装依赖，正在安装..."
    pip3 install -r requirements.txt
}

# 启动应用
echo ""
echo "🚀 启动 Memora 服务..."
echo "   端口: 8080"
echo "   日志: nohup.out"
echo ""

# 后台运行
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 > nohup.out 2>&1 &

# 获取进程 ID
PID=$!
echo $PID > .memora.pid

echo "✅ 服务已启动！"
echo "   PID: $PID"
echo "   健康检查: http://localhost:8080/health"
echo ""
echo "查看日志: tail -f nohup.out"
echo "停止服务: kill \$(cat .memora.pid)"
