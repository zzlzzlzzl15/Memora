#!/usr/bin/env python3
"""检查Neo4j数据库中的实体节点属性"""
from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
username = "neo4j"
password = "memora_neo4j_pass"

driver = GraphDatabase.driver(uri, auth=(username, password))

with driver.session() as session:
    # 查询所有Entity节点的属性
    print("=== Entity节点属性 ===")
    result = session.run("""
        MATCH (e:Entity)
        RETURN e LIMIT 5
    """)
    
    for i, record in enumerate(result, 1):
        entity = record['e']
        print(f"\n--- Entity {i} ---")
        print(f"Properties: {dict(entity)}")
        print(f"Keys: {list(dict(entity).keys())}")
        
        # 检查是否有entity_id
        if 'entity_id' in dict(entity):
            print(f"✓ Has entity_id: {entity['entity_id']}")
        else:
            print("✗ No entity_id field")
            
        # 检查是否有user_id
        if 'user_id' in dict(entity):
            print(f"✓ Has user_id: {entity['user_id']}")
        else:
            print("✗ No user_id field")

driver.close()
