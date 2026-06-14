#!/bin/bash
# 快速测试:为单个文档重建知识图谱

echo "=========================================="
echo "测试:为单个文档重建知识图谱"
echo "=========================================="
echo ""

# 获取第一个completed状态的文档ID
DOC_INFO=$(curl -s http://localhost:8000/api/v1/documents/ | python3 -c "
import sys, json
data = json.load(sys.stdin)
for doc in data['documents']:
    if doc['status'] == 'completed':
        print(f\"{doc['document_id']}|{doc['title']}\")
        break
")

if [ -z "$DOC_INFO" ]; then
    echo "❌ 没有找到completed状态的文档"
    exit 1
fi

DOC_ID=$(echo "$DOC_INFO" | cut -d'|' -f1)
DOC_TITLE=$(echo "$DOC_INFO" | cut -d'|' -f2)

echo "📄 选择文档: $DOC_TITLE"
echo "🆔 文档ID: $DOC_ID"
echo ""

# 调用重新处理API
echo "🚀 开始重新处理..."
response=$(curl -s -X POST "http://localhost:8000/api/v1/documents/$DOC_ID/reprocess" \
    -H "Content-Type: application/json")

echo "📥 API响应:"
echo "$response" | python3 -m json.tool
echo ""

# 等待处理完成
echo "⏳ 等待处理完成(预计30-60秒)..."
sleep 30

# 检查Neo4j中是否有新数据
echo ""
echo "🔍 检查Neo4j图谱数据..."
neo4j_response=$(curl -s http://localhost:7474/db/neo4j/query/v2 \
    -u neo4j:memora_neo4j_pass \
    -H "Content-Type: application/json" \
    -d "{\"statement\": \"MATCH (e:Entity) RETURN e.entity_name, e.entity_type LIMIT 5\"}")

entity_count=$(echo "$neo4j_response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    count = len(data.get('data', {}).get('values', []))
    print(count)
except:
    print(0)
")

if [ "$entity_count" -gt 0 ]; then
    echo "✅ 成功! Neo4j中现在有 $entity_count 个实体"
    echo ""
    echo "📊 实体列表:"
    echo "$neo4j_response" | python3 -m json.tool | grep -A 2 "entity_name"
else
    echo "⚠️  Neo4j中仍未检测到实体"
    echo ""
    echo "💡 可能原因:"
    echo "   1. 文档仍在处理中,请稍后再次检查"
    echo "   2. LLM API调用失败,查看应用日志:"
    echo "      docker logs memora-app | tail -50"
fi

echo ""
echo "=========================================="
