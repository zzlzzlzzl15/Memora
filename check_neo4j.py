from neo4j import GraphDatabase

uri = 'bolt://localhost:7687'
auth = ('neo4j', 'memora_neo4j_pass')

driver = GraphDatabase.driver(uri, auth=auth)
session = driver.session()

# 查询所有 Entity 的 user_id
result = session.run('MATCH (e:Entity) RETURN e.user_id as user_id, count(*) as count')
print('Entity nodes by user_id:')
for r in result:
    print(f'  user_id={r["user_id"]}: {r["count"]} entities')

# 查询所有 Document 的 user_id
doc_result = session.run('MATCH (d:Document) RETURN d.user_id as user_id, d.doc_id as doc_id, count(*) as count')
print('\nDocument nodes:')
for r in doc_result:
    print(f'  user_id={r["user_id"]}, doc_id={r["doc_id"]}')

# 查询是否有 APPEARS_IN 关系
rel_result = session.run('MATCH ()-[r:APPEARS_IN]->() RETURN count(r) as count')
print(f'\nTotal APPEARS_IN relations: {rel_result.single()["count"]}')

session.close()
driver.close()
