#!/bin/bash
# Memora Docker 部署验证脚本

set -e  # 遇到错误立即退出

echo "=========================================="
echo "Memora Docker 部署验证"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查函数
check_service() {
    local service_name=$1
    local health_url=$2
    local description=$3
    
    echo -n "检查 $description... "
    
    if curl -s -f "$health_url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 正常${NC}"
        return 0
    else
        echo -e "${RED}❌ 失败${NC}"
        return 1
    fi
}

# Step 1: 检查 Docker 和 Docker Compose
echo "Step 1: 检查 Docker 环境"
echo "----------------------------------------"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker 未安装${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose 未安装${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker 版本: $(docker --version)${NC}"
echo -e "${GREEN}✅ Docker Compose 版本: $(docker-compose --version)${NC}"
echo ""

# Step 2: 检查配置文件
echo "Step 2: 检查配置文件"
echo "----------------------------------------"

if [ -f ".env.production" ]; then
    echo -e "${GREEN}✅ .env.production 存在${NC}"
else
    echo -e "${RED}❌ .env.production 不存在${NC}"
    exit 1
fi

if [ -f "docker-compose.yml" ]; then
    echo -e "${GREEN}✅ docker-compose.yml 存在${NC}"
else
    echo -e "${RED}❌ docker-compose.yml 不存在${NC}"
    exit 1
fi

if [ -f "Dockerfile" ]; then
    echo -e "${GREEN}✅ Dockerfile 存在${NC}"
else
    echo -e "${RED}❌ Dockerfile 不存在${NC}"
    exit 1
fi
echo ""

# Step 3: 检查关键配置项
echo "Step 3: 检查关键配置项"
echo "----------------------------------------"

check_config() {
    local key=$1
    local expected=$2
    
    value=$(grep "^${key}=" .env.production | cut -d'=' -f2 | tr -d '"' | tr -d "'")
    
    if [ -z "$value" ]; then
        echo -e "${RED}❌ $key 未配置${NC}"
        return 1
    elif [ "$expected" != "" ] && [ "$value" != "$expected" ]; then
        echo -e "${YELLOW}⚠️  $key = $value (期望: $expected)${NC}"
        return 0
    else
        echo -e "${GREEN}✅ $key = $value${NC}"
        return 0
    fi
}

check_config "USE_MINERU" "true"
check_config "NEO4J_ENABLED" "true"
check_config "VLM_ENABLED" "true"
check_config "KG_QUERY_MODE" "mix"
echo ""

# Step 4: 构建 Docker 镜像
echo "Step 4: 构建 Docker 镜像"
echo "----------------------------------------"
read -p "是否重新构建 Docker 镜像? (y/n): " rebuild

if [ "$rebuild" = "y" ] || [ "$rebuild" = "Y" ]; then
    echo "开始构建..."
    docker-compose build --no-cache
    echo -e "${GREEN}✅ 镜像构建完成${NC}"
else
    echo "跳过构建,使用现有镜像"
fi
echo ""

# Step 5: 启动服务
echo "Step 5: 启动 Docker 服务"
echo "----------------------------------------"
read -p "是否启动服务? (y/n): " start_services

if [ "$start_services" = "y" ] || [ "$start_services" = "Y" ]; then
    echo "启动服务..."
    docker-compose up -d
    
    echo "等待服务启动 (30秒)..."
    sleep 30
    
    echo -e "${GREEN}✅ 服务启动完成${NC}"
else
    echo "跳过启动"
fi
echo ""

# Step 6: 健康检查
echo "Step 6: 服务健康检查"
echo "----------------------------------------"

failed=0

check_service "MySQL" "http://localhost:3306" "MySQL" || ((failed++))
check_service "Qdrant" "http://localhost:6333" "Qdrant" || ((failed++))
check_service "Neo4j Browser" "http://localhost:7474" "Neo4j Browser" || ((failed++))
check_service "App Health" "http://localhost:8000/health" "应用服务" || ((failed++))

echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "所有服务运行正常! 🎉"
    echo "==========================================${NC}"
    echo ""
    echo "访问地址:"
    echo "  - 应用 API: http://localhost:8000"
    echo "  - Neo4j Browser: http://localhost:7474 (neo4j/memora_neo4j_pass)"
    echo "  - Qdrant Dashboard: http://localhost:6333/dashboard"
    echo ""
else
    echo -e "${RED}=========================================="
    echo "有 $failed 个服务检查失败,请查看日志"
    echo "==========================================${NC}"
    echo ""
    echo "查看日志命令:"
    echo "  docker-compose logs -f app"
    echo "  docker-compose logs -f neo4j"
    echo ""
    exit 1
fi
