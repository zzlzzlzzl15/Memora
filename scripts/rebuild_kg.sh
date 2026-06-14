#!/bin/bash
# 为已有文档重新构建知识图谱的简单脚本

echo "=========================================="
echo "为Memora已有文档重建知识图谱"
echo "=========================================="
echo ""

# 获取所有文档ID
echo "📋 正在获取文档列表..."
DOCS=$(curl -s http://localhost:8000/api/v1/documents/ | python3 -c "
import sys, json
data = json.load(sys.stdin)
for doc in data['documents']:
    if doc['status'] in ['completed', 'indexed']:
        print(f\"{doc['document_id']}|{doc['title']}\")
")

if [ -z "$DOCS" ]; then
    echo "❌ 没有找到需要处理的文档"
    exit 1
fi

echo "✅ 找到以下文档:"
echo "$DOCS" | while IFS='|' read -r doc_id title; do
    echo "  - ${title:0:40}"
done
echo ""

# 逐个触发重新处理
count=0
success=0
failed=0

echo "🚀 开始重建知识图谱..."
echo ""

echo "$DOCS" | while IFS='|' read -r doc_id title; do
    count=$((count + 1))
    echo "[$count] 处理: ${title:0:50}"
    
    # 调用重新处理API
    response=$(curl -s -X POST "http://localhost:8000/api/v1/documents/$doc_id/reprocess" \
        -H "Content-Type: application/json")
    
    # 检查响应
    if echo "$response" | grep -q '"status"'; then
        echo "  ✅ 成功提交"
        success=$((success + 1))
    else
        echo "  ❌ 失败: $response"
        failed=$((failed + 1))
    fi
    
    echo ""
    
    # 等待5秒,避免API限流
    sleep 5
done

echo "=========================================="
echo "处理完成!"
echo "  总计: $count"
echo "  成功: $success"  
echo "  失败: $failed"
echo "=========================================="
echo ""
echo "💡 提示: 可以通过以下命令查看Neo4j中的图谱数据:"
echo "   curl http://localhost:7474/db/neo4j/query/v2 \\"
echo "     -u neo4j:memora_neo4j_pass \\"
echo "     -d '{\"statement\": \"MATCH (e:Entity) RETURN e.entity_name LIMIT 10\"}'"
