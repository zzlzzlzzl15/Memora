#!/bin/bash

# Memora 停止脚本

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  停止 Memora 服务"
echo "=========================================="
echo ""

# 检查 PID 文件
if [ ! -f ".memora.pid" ]; then
    echo "❌ 未找到 PID 文件，服务可能未运行"
    exit 1
fi

# 读取 PID
PID=$(cat .memora.pid)

# 检查进程是否存在
if ! kill -0 $PID 2>/dev/null; then
    echo "❌ 进程 $PID 不存在，清理 PID 文件"
    rm .memora.pid
    exit 1
fi

# 停止进程
echo "🛑 停止进程 $PID..."
kill $PID

# 等待进程结束
sleep 2

# 检查是否成功停止
if kill -0 $PID 2>/dev/null; then
    echo "⚠️  进程未能正常停止，强制终止..."
    kill -9 $PID
    sleep 1
fi

# 清理 PID 文件
rm .memora.pid

echo ""
echo "✅ 服务已停止"
echo "   日志保留在 nohup.out"
