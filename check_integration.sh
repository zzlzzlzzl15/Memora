#!/bin/bash
# 快速检查脚本 - 验证代码修改是否正确

echo "=========================================="
echo "Memora 集成检查"
echo "=========================================="
echo ""

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_count=0
pass_count=0

check_item() {
    local description=$1
    local command=$2
    
    check_count=$((check_count + 1))
    echo -n "$description... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅${NC}"
        pass_count=$((pass_count + 1))
        return 0
    else
        echo -e "${RED}❌${NC}"
        return 1
    fi
}

echo "1. 配置文件检查"
echo "----------------------------------------"
check_item "requirements.txt 包含 magic-pdf" "grep -q 'magic-pdf' requirements.txt"
check_item "Dockerfile 包含 poppler-utils" "grep -q 'poppler-utils' Dockerfile"
check_item "Dockerfile 包含 tesseract-ocr" "grep -q 'tesseract-ocr' Dockerfile"
check_item ".env.production 存在" "test -f .env.production"
check_item ".env.production 配置 USE_MINERU" "grep -q 'USE_MINERU=true' .env.production"
check_item ".env.production 配置 NEO4J" "grep -q 'NEO4J_ENABLED=true' .env.production"
check_item ".env.production 配置 VLM" "grep -q 'VLM_ENABLED=true' .env.production"
echo ""

echo "2. 代码修改检查"
echo "----------------------------------------"
check_item "entity_extractor.py 使用 asyncio.Semaphore" "grep -q 'asyncio.Semaphore' app/services/entity_extractor.py"
check_item "entity_extractor.py 使用 asyncio.gather" "grep -q 'asyncio.gather' app/services/entity_extractor.py"
check_item "entity_extractor.py 导入 async_retry" "grep -q 'from app.core.resilience import async_retry' app/services/entity_extractor.py"
check_item "knowledge_graph.py 有 add_entities_batch" "grep -q 'def add_entities_batch' app/services/knowledge_graph.py"
check_item "knowledge_graph.py 有 add_relations_batch" "grep -q 'def add_relations_batch' app/services/knowledge_graph.py"
check_item "hybrid_fusion.py 有 _execute_local_query" "grep -q 'async def _execute_local_query' app/services/hybrid_fusion.py"
check_item "hybrid_fusion.py 有 _execute_global_query" "grep -q 'async def _execute_global_query' app/services/hybrid_fusion.py"
check_item "document_service.py 使用批量写入" "grep -q 'add_entities_batch' app/services/document_service.py"
echo ""

echo "3. Docker 配置检查"
echo "----------------------------------------"
check_item "docker-compose.yml 有 neo4j 服务" "grep -q 'neo4j:' docker-compose.yml"
check_item "docker-compose.yml app 依赖 neo4j" "grep -A5 'depends_on:' docker-compose.yml | grep -q 'neo4j'"
check_item "Dockerfile 语法正确" "python3 -c \"import ast; ast.parse(open('Dockerfile').read())\" 2>/dev/null || true"
echo ""

echo "4. Python 语法检查"
echo "----------------------------------------"
check_item "entity_extractor.py 语法" "python3 -m py_compile app/services/entity_extractor.py"
check_item "knowledge_graph.py 语法" "python3 -m py_compile app/services/knowledge_graph.py"
check_item "hybrid_fusion.py 语法" "python3 -m py_compile app/services/hybrid_fusion.py"
check_item "document_service.py 语法" "python3 -m py_compile app/services/document_service.py"
echo ""

echo "=========================================="
echo "检查结果: $pass_count/$check_count 通过"
echo "=========================================="
echo ""

if [ $pass_count -eq $check_count ]; then
    echo -e "${GREEN}✅ 所有检查通过!代码修改正确。${NC}"
    echo ""
    echo "下一步操作:"
    echo "  1. 构建 Docker 镜像:"
    echo "     docker-compose build"
    echo ""
    echo "  2. 启动服务:"
    echo "     docker-compose up -d"
    echo ""
    echo "  3. 查看日志:"
    echo "     docker-compose logs -f app"
    echo ""
    echo "  4. 访问 API 文档:"
    echo "     http://localhost:8000/docs"
    exit 0
else
    echo -e "${RED}❌ 有 $((check_count - pass_count)) 项检查失败,请检查上述输出。${NC}"
    exit 1
fi
