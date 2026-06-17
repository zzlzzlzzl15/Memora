#!/usr/bin/env python3
"""为Neo4j数据库中的现有实体添加entity_id字段"""
from neo4j import GraphDatabase
import uuid

uri = "bolt://localhost:7687"
username = "neo4j"
password = "memora_neo4j_pass"

driver = GraphDatabase.driver(uri, auth=(username, password))

print("开始为现有实体添加entity_id...")

with driver.session() as session:
    # 查询所有没有entity_id的Entity节点
    result = session.run("""
        MATCH (e:Entity)
        WHERE e.entity_id IS NULL
        RETURN e.user_id AS user_id, e.entity_name AS entity_name
    """)
    
    count = 0
    for record in result:
        user_id = record['user_id']
        entity_name = record['entity_name']
        
        # 生成新的entity_id
        new_entity_id = str(uuid.uuid4())
        
        # 更新实体节点
        session.run("""
            MATCH (e:Entity {user_id: $user_id, entity_name: $entity_name})
            SET e.entity_id = $new_entity_id
        """, user_id=user_id, entity_name=entity_name, new_entity_id=new_entity_id)
        
        count += 1
        if count % 10 == 0:
            print(f"已处理 {count} 个实体...")

print(f"\n完成!共为 {count} 个实体添加了entity_id")

# 验证
print("\n验证结果:")
result = session.run("""
    MATCH (e:Entity)
    WITH count(CASE WHEN e.entity_id IS NOT NULL THEN 1 END) AS with_id,
         count(CASE WHEN e.entity_id IS NULL THEN 1 END) AS without_id
    RETURN with_id, without_id
""")

for record in result:
    print(f"有entity_id的实体: {record['with_id']}")
    print(f"无entity_id的实体: {record['without_id']}")

driver.close()
