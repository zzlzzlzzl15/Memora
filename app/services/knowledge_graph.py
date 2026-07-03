"""
Neo4j 知识图谱服务

提供与 Neo4j 图数据库的连接管理、实体/关系的 CRUD 操作、
以及基于 Cypher 的图谱查询功能。

参照方案 3.4：知识图谱增强 — 实体-关系提取与图谱查询
"""

import uuid
from typing import List, Optional, Dict, Any
from loguru import logger
from config.settings import settings


class KnowledgeGraphService:
    """Neo4j 知识图谱服务"""

    def __init__(self):
        self._driver = None
        self._available = False

    @property
    def available(self) -> bool:
        """知识图谱服务是否可用"""
        return self._available and self._driver is not None

    def connect(self) -> bool:
        """
        连接 Neo4j 数据库

        Returns:
            是否连接成功
        """
        if not settings.neo4j_enabled:
            logger.info("知识图谱未启用 (NEO4J_ENABLED=false)")
            return False

        try:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            # 验证连接
            self._driver.verify_connectivity()
            self._available = True
            logger.info(f"Neo4j 知识图谱连接成功: {settings.neo4j_uri}")

            # 初始化约束和索引
            self._init_constraints()
            return True
        except ImportError:
            logger.warning("neo4j 包未安装，请执行: pip install neo4j")
            self._available = False
            return False
        except Exception as e:
            logger.warning(f"Neo4j 连接失败: {e}")
            self._available = False
            return False

    def close(self):
        """关闭连接"""
        if self._driver:
            self._driver.close()
            self._driver = None
            self._available = False

    def _init_constraints(self):
        """初始化节点唯一性约束和索引"""
        if not self.available:
            return

        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE",
        ]

        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.entity_name)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.user_id)",
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.user_id)",
        ]

        with self._driver.session(database=settings.neo4j_database) as session:
            for cql in constraints + indexes:
                try:
                    session.run(cql)
                except Exception as e:
                    logger.warning(f"初始化约束/索引失败: {e}")

    # ─── 实体操作 ───────────────────────────────────────────────

    def add_entity(
        self,
        entity_name: str,
        entity_type: str,
        description: str,
        doc_id: str,
        user_id: str,
        source_chunk_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        添加实体节点

        如果同名同类型实体已存在，则合并描述并创建 APPEARS_IN 关系

        Returns:
            entity_id 或 None
        """
        if not self.available:
            return None

        entity_id = str(uuid.uuid4())

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                result = session.execute_write(
                    self._create_or_merge_entity,
                    entity_id, entity_name, entity_type, description,
                    doc_id, user_id, source_chunk_id,
                )
                return result
        except Exception as e:
            logger.error(f"添加实体失败: {e}")
            return None

    @staticmethod
    def _create_or_merge_entity(
        tx, entity_id, entity_name, entity_type, description,
        doc_id, user_id, source_chunk_id,
    ):
        # MERGE 同名同类型实体，避免重复
        result = tx.run(
            """
            MERGE (e:Entity {entity_name: $name, entity_type: $type, user_id: $user_id})
            ON CREATE SET e.entity_id = $entity_id,
                          e.description = $description,
                          e.created_at = datetime()
            ON MATCH SET  e.description = CASE
                              WHEN e.description IS NULL THEN $description
                              ELSE e.description + '; ' + $description
                          END,
                          e.updated_at = datetime()
            WITH e
            MATCH (d:Document {doc_id: $doc_id})
            MERGE (e)-[:APPEARS_IN]->(d)
            RETURN e.entity_id AS eid
            """,
            entity_id=entity_id,
            name=entity_name,
            type=entity_type,
            description=description,
            doc_id=doc_id,
            user_id=user_id,
        )
        record = result.single()
        return record["eid"] if record else None

    def add_document_node(self, doc_id: str, title: str, user_id: str):
        """添加文档节点"""
        if not self.available:
            return

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                session.run(
                    """
                    MERGE (d:Document {doc_id: $doc_id})
                    ON CREATE SET d.title = $title,
                                  d.user_id = $user_id,
                                  d.document_id = $doc_id,
                                  d.created_at = datetime()
                    ON MATCH SET  d.title = $title,
                                  d.updated_at = datetime()
                    """,
                    doc_id=doc_id,
                    title=title,
                    user_id=user_id,
                )
        except Exception as e:
            logger.error(f"添加文档节点失败: {e}")

    # ─── 关系操作 ───────────────────────────────────────────────

    def add_entities_batch(
        self,
        entities: List[Dict[str, Any]],
        doc_id: str,
        user_id: str,
    ):
        """
        批量添加实体 (使用 MERGE 避免重复)
        
        参照 RAG-Anything: 批量写入 Neo4j,提升性能
        
        Args:
            entities: [{name, type, description, source_chunk_id}, ...]
            doc_id: 文档 ID
            user_id: 用户 ID
        """
        if not self.available:
            return
        
        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                for entity in entities:
                    session.execute_write(
                        self._merge_entity,
                        entity_name=entity["name"],
                        entity_type=entity.get("type", "概念"),
                        description=entity.get("description", ""),
                        doc_id=doc_id,
                        user_id=user_id,
                        source_chunk_id=entity.get("source_chunk_id"),
                    )
            logger.info(f"批量添加 {len(entities)} 个实体完成")
        except Exception as e:
            logger.error(f"批量添加实体失败: {e}")

    @staticmethod
    def _merge_entity(
        tx,
        entity_name: str,
        entity_type: str,
        description: str,
        doc_id: str,
        user_id: str,
        source_chunk_id: Optional[str] = None,
    ):
        """MERGE 实体节点,避免重复"""
        tx.run(
            """
            MERGE (e:Entity {entity_name: $entity_name, user_id: $user_id})
            ON CREATE SET 
                e.entity_id = toString(randomUUID()),
                e.entity_type = $entity_type,
                e.description = $description,
                e.created_at = datetime()
            ON MATCH SET 
                e.description = CASE 
                    WHEN $description <> '' THEN $description 
                    ELSE e.description 
                END,
                e.updated_at = datetime()
            MERGE (d:Document {doc_id: $doc_id, user_id: $user_id})
            MERGE (e)-[:APPEARS_IN]->(d)
            RETURN e
            """,
            entity_name=entity_name,
            entity_type=entity_type,
            description=description,
            doc_id=doc_id,
            user_id=user_id,
        )

    def add_relations_batch(
        self,
        relations: List[Dict[str, Any]],
        doc_id: str,
        user_id: str,
    ):
        """
        批量添加关系
        
        Args:
            relations: [{source, target, type, description}, ...]
            doc_id: 文档 ID
            user_id: 用户 ID
        """
        if not self.available:
            return
        
        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                for rel in relations:
                    session.execute_write(
                        self._merge_relation,
                        source_name=rel["source"],
                        target_name=rel["target"],
                        relation_type=rel.get("type", "相关"),
                        description=rel.get("description", ""),
                        doc_id=doc_id,
                        user_id=user_id,
                    )
            logger.info(f"批量添加 {len(relations)} 个关系完成")
        except Exception as e:
            logger.error(f"批量添加关系失败: {e}")

    @staticmethod
    def _merge_relation(
        tx,
        source_name: str,
        target_name: str,
        relation_type: str,
        description: str,
        doc_id: str,
        user_id: str,
    ):
        """MERGE 关系,自动创建端点实体"""
        tx.run(
            """
            MERGE (e1:Entity {entity_name: $source_name, user_id: $user_id})
            ON CREATE SET e1.entity_id = randomUUID(),
                          e1.entity_type = '未知',
                          e1.created_at = datetime()
            MERGE (e2:Entity {entity_name: $target_name, user_id: $user_id})
            ON CREATE SET e2.entity_id = randomUUID(),
                          e2.entity_type = '未知',
                          e2.created_at = datetime()
            MERGE (e1)-[r:RELATED_TO {
                relation_type: $relation_type,
                source_doc_id: $doc_id
            }]->(e2)
            ON CREATE SET r.description = $description,
                          r.created_at = datetime()
            ON MATCH SET  r.updated_at = datetime()
            """,
            source_name=source_name,
            target_name=target_name,
            relation_type=relation_type,
            description=description,
            doc_id=doc_id,
            user_id=user_id,
        )

    def add_relation(
        self,
        source_name: str,
        target_name: str,
        relation_type: str,
        description: str,
        doc_id: str,
        user_id: str,
        source_chunk_id: Optional[str] = None,
    ):
        """
        添加实体间关系

        如果端点实体不存在，自动创建
        """
        if not self.available:
            return

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                session.execute_write(
                    self._create_relation,
                    source_name, target_name, relation_type, description,
                    doc_id, user_id, source_chunk_id,
                )
        except Exception as e:
            logger.error(f"添加关系失败: {e}")

    @staticmethod
    def _create_relation(
        tx, source_name, target_name, relation_type, description,
        doc_id, user_id, source_chunk_id,
    ):
        tx.run(
            """
            MERGE (e1:Entity {entity_name: $source_name, user_id: $user_id})
            ON CREATE SET e1.entity_id = randomUUID(),
                          e1.entity_type = '未知',
                          e1.created_at = datetime()
            MERGE (e2:Entity {entity_name: $target_name, user_id: $user_id})
            ON CREATE SET e2.entity_id = randomUUID(),
                          e2.entity_type = '未知',
                          e2.created_at = datetime()
            MERGE (e1)-[r:RELATED_TO {
                relation_type: $relation_type,
                source_doc_id: $doc_id
            }]->(e2)
            ON CREATE SET r.description = $description,
                          r.source_chunk_id = $chunk_id,
                          r.created_at = datetime()
            ON MATCH SET  r.updated_at = datetime()
            """,
            source_name=source_name,
            target_name=target_name,
            relation_type=relation_type,
            description=description,
            doc_id=doc_id,
            user_id=user_id,
            chunk_id=source_chunk_id,
        )

    # ─── 图谱查询 ───────────────────────────────────────────────

    def search_entities(
        self, keyword: str, user_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        按名称搜索实体

        Returns:
            [{entity_id, entity_name, entity_type, description}, ...]
        """
        if not self.available:
            return []

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                result = session.run(
                    """
                    MATCH (e:Entity)
                    WHERE e.user_id = $user_id AND e.entity_name CONTAINS $keyword
                    RETURN e.entity_id AS entity_id,
                           e.entity_name AS entity_name,
                           e.entity_type AS entity_type,
                           e.description AS description
                    LIMIT $limit
                    """,
                    keyword=keyword,
                    user_id=user_id,
                    limit=limit,
                )
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"搜索实体失败: {e}")
            return []

    def get_entity_with_relations(
        self, entity_name: str, user_id: str, depth: int = 2
    ) -> Dict[str, Any]:
        """
        获取实体及其 N 度关系

        Returns:
            {entities: [...], relations: [...], related_chunks: [...]}
        """
        if not self.available:
            return {"entities": [], "relations": [], "related_chunks": []}

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                result = session.run(
                    """
                    MATCH (e:Entity {entity_name: $name, user_id: $user_id})
                    CALL {
                        WITH e
                        MATCH path = (e)-[r*1..2]-(related:Entity)
                        RETURN path, r, related
                    }
                    RETURN e, r, related,
                           [n IN nodes(path) | n.entity_name] AS path_names,
                           [rel IN relationships(path) | rel.relation_type] AS path_rels
                    """,
                    name=entity_name,
                    user_id=user_id,
                )

                entities = []
                relations = []
                seen_entity_ids = set()
                seen_rel_keys = set()

                for record in result:
                    # 收集实体
                    for node_key in ["e", "related"]:
                        node = record[node_key]
                        if node and node.get("entity_id") not in seen_entity_ids:
                            seen_entity_ids.add(node.get("entity_id"))
                            entities.append({
                                "entity_id": node.get("entity_id"),
                                "entity_name": node.get("entity_name"),
                                "entity_type": node.get("entity_type"),
                                "description": node.get("description", ""),
                            })

                    # 收集关系
                    rels = record["r"]
                    if isinstance(rels, list):
                        for rel in rels:
                            rel_key = (
                                rel.get("relation_type", ""),
                                rel.start_node.get("entity_name", ""),
                                rel.end_node.get("entity_name", ""),
                            )
                            if rel_key not in seen_rel_keys:
                                seen_rel_keys.add(rel_key)
                                relations.append({
                                    "source": rel.start_node.get("entity_name", ""),
                                    "target": rel.end_node.get("entity_name", ""),
                                    "relation_type": rel.get("relation_type", ""),
                                    "description": rel.get("description", ""),
                                })

                return {"entities": entities, "relations": relations, "related_chunks": []}
        except Exception as e:
            logger.error(f"获取实体关系失败: {e}")
            return {"entities": [], "relations": [], "related_chunks": []}

    def get_local_context(
        self, entity_names: List[str], user_id: str
    ) -> Dict[str, Any]:
        """
        获取实体的局部上下文（实体描述 + 关联文档块）
        对应 LightRAG 的 local 模式

        Returns:
            {entities: [...], relations: [...], related_chunks: [...]}
        """
        if not self.available:
            return {"entities": [], "relations": [], "related_chunks": []}

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                # 查询实体及其直接关系
                result = session.run(
                    """
                    MATCH (e:Entity)-[r]-(related:Entity)
                    WHERE e.entity_name IN $names AND e.user_id = $user_id
                    RETURN e.entity_id AS entity_id,
                           e.entity_name AS entity_name,
                           e.entity_type AS entity_type,
                           e.description AS description,
                           related.entity_name AS rel_entity_name,
                           related.entity_type AS rel_entity_type,
                           related.description AS rel_description,
                           type(r) AS rel_type,
                           r.relation_type AS relation_type,
                           r.description AS rel_description_text
                    """,
                    names=entity_names,
                    user_id=user_id,
                )

                entities = []
                relations = []
                seen_entity_ids = set()

                for record in result:
                    eid = record["entity_id"]
                    if eid not in seen_entity_ids:
                        seen_entity_ids.add(eid)
                        entities.append({
                            "entity_id": eid,
                            "entity_name": record["entity_name"],
                            "entity_type": record["entity_type"],
                            "description": record["description"] or "",
                        })

                    # 关系实体
                    rel_name = record["rel_entity_name"]
                    if rel_name and rel_name not in [e["entity_name"] for e in entities]:
                        entities.append({
                            "entity_name": rel_name,
                            "entity_type": record["rel_entity_type"],
                            "description": record["rel_description"] or "",
                        })

                    relations.append({
                        "source": record["entity_name"],
                        "target": rel_name,
                        "relation_type": record.get("relation_type") or record.get("rel_type", ""),
                        "description": record.get("rel_description_text") or "",
                    })

                return {"entities": entities, "relations": relations, "related_chunks": []}
        except Exception as e:
            logger.error(f"获取局部上下文失败: {e}")
            return {"entities": [], "relations": [], "related_chunks": []}

    def get_global_context(
        self, entity_names: List[str], user_id: str
    ) -> Dict[str, Any]:
        """
        获取全局上下文（关系遍历 → 子图 → 全局推理）
        对应 LightRAG 的 global 模式

        Returns:
            {entities: [...], relations: [...], related_chunks: [...]}
        """
        if not self.available:
            return {"entities": [], "relations": [], "related_chunks": []}

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                result = session.run(
                    """
                    MATCH (e:Entity)-[r*1..3]-(related:Entity)
                    WHERE e.entity_name IN $names AND e.user_id = $user_id
                    DISTINCT
                    RETURN DISTINCT e.entity_name AS source,
                           related.entity_name AS target,
                           related.entity_type AS target_type,
                           related.description AS target_desc,
                           [rel IN r | {type: rel.relation_type, desc: rel.description}] AS rels
                    LIMIT 50
                    """,
                    names=entity_names,
                    user_id=user_id,
                )

                entities = []
                relations = []
                seen_names = set()

                for record in result:
                    target_name = record["target"]
                    if target_name not in seen_names:
                        seen_names.add(target_name)
                        entities.append({
                            "entity_name": target_name,
                            "entity_type": record["target_type"],
                            "description": record["target_desc"] or "",
                        })

                    for rel in record["rels"]:
                        relations.append({
                            "source": record["source"],
                            "target": target_name,
                            "relation_type": rel.get("type", ""),
                            "description": rel.get("desc", ""),
                        })

                return {"entities": entities, "relations": relations, "related_chunks": []}
        except Exception as e:
            logger.error(f"获取全局上下文失败: {e}")
            return {"entities": [], "relations": [], "related_chunks": []}

    def get_cross_document_relations(
        self, doc_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """
        跨文档关系查询：查找与指定文档共享实体的其他文档

        Returns:
            [{doc_id, title, shared_entities}, ...]
        """
        if not self.available:
            return []

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                result = session.run(
                    """
                    MATCH (d1:Document)<-[:APPEARS_IN]-(e:Entity)-[:APPEARS_IN]->(d2:Document)
                    WHERE d1.doc_id = $doc_id AND d1.user_id = $user_id AND d1 <> d2
                    RETURN DISTINCT d2.doc_id AS doc_id,
                           d2.title AS title,
                           collect(e.entity_name) AS shared_entities
                    """,
                    doc_id=doc_id,
                    user_id=user_id,
                )
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"跨文档关系查询失败: {e}")
            return []

    def get_related_documents(
        self, doc_id: str, user_id: str, limit: int = 10
    ) -> List[tuple]:
        """
        获取与指定文档相关的文档列表（基于共享实体）

        document_service.get_related_documents 调用此方法，
        期望返回 List[Tuple[doc_id, shared_entity_names]]

        Args:
            doc_id: 文档 ID
            user_id: 用户 ID
            limit: 最多返回的文档数量

        Returns:
            [(doc_id, [entity_name, ...]), ...]  按共享实体数量降序
        """
        if not self.available:
            return []

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                result = session.run(
                    """
                    MATCH (d1:Document)<-[:APPEARS_IN]-(e:Entity)-[:APPEARS_IN]->(d2:Document)
                    WHERE d1.doc_id = $doc_id AND d1.user_id = $user_id AND d1 <> d2
                    RETURN DISTINCT d2.doc_id AS doc_id,
                           collect(DISTINCT e.entity_name) AS shared_entities,
                           count(DISTINCT e) AS shared_count
                    ORDER BY shared_count DESC
                    LIMIT $limit
                    """,
                    doc_id=doc_id,
                    user_id=user_id,
                    limit=limit,
                )
                return [
                    (record["doc_id"], list(record["shared_entities"]))
                    for record in result
                ]
        except Exception as e:
            logger.error(f"获取相关文档失败: {e}")
            return []

    # ─── 文档级操作 ───────────────────────────────────────────────

    def delete_document_graph(self, doc_id: str, user_id: str):
        """删除文档关联的所有图谱数据"""
        if not self.available:
            logger.warning(f"Neo4j 不可用，跳过删除文档 {doc_id} 的图谱数据")
            return

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                # 先统计要删除的数据量
                stats_result = session.run(
                    """
                    MATCH (d:Document {doc_id: $doc_id, user_id: $user_id})
                    OPTIONAL MATCH (d)-[r]-(e)
                    RETURN count(DISTINCT d) AS doc_count, count(r) AS rel_count
                    """,
                    doc_id=doc_id,
                    user_id=user_id,
                )
                stats = stats_result.single()
                doc_count = stats["doc_count"]
                rel_count = stats["rel_count"]
                
                logger.info(f"准备删除文档 {doc_id}: {doc_count} 个文档节点, {rel_count} 条关系")
                
                # 删除文档节点及其关系
                session.run(
                    """
                    MATCH (d:Document {doc_id: $doc_id, user_id: $user_id})
                    DETACH DELETE d
                    """,
                    doc_id=doc_id,
                    user_id=user_id,
                )
                
                # 删除孤立实体（没有 APPEARS_IN 关系的）
                orphan_result = session.run(
                    """
                    MATCH (e:Entity {user_id: $user_id})
                    WHERE NOT (e)-[:APPEARS_IN]->(:Document)
                    WITH e LIMIT 1000
                    DETACH DELETE e
                    RETURN count(e) AS deleted_count
                    """,
                    user_id=user_id,
                )
                orphan_stats = orphan_result.single()
                orphan_count = orphan_stats["deleted_count"] if orphan_stats else 0
                
                logger.info(f"已删除文档 {doc_id} 的图谱数据，同时清理了 {orphan_count} 个孤立实体")
        except Exception as e:
            logger.error(f"删除文档图谱数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def get_stats(self, user_id: str) -> Dict[str, int]:
        """获取知识图谱统计信息"""
        if not self.available:
            return {"entity_count": 0, "relation_count": 0, "document_count": 0}

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                # user_id 在 Neo4j 中存储为字符串，直接使用
                neo4j_user_id = str(user_id)
                
                entity_result = session.run(
                    "MATCH (e:Entity {user_id: $user_id}) RETURN count(e) AS count",
                    user_id=neo4j_user_id,
                )
                entity_count = entity_result.single()["count"]

                rel_result = session.run(
                    """
                    MATCH (e1:Entity {user_id: $user_id})-[r:RELATED_TO]->(e2:Entity)
                    RETURN count(r) AS count
                    """,
                    user_id=neo4j_user_id,
                )
                relation_count = rel_result.single()["count"]

                doc_result = session.run(
                    "MATCH (d:Document {user_id: $user_id}) RETURN count(d) AS count",
                    user_id=user_id,
                )
                document_count = doc_result.single()["count"]

                return {
                    "entity_count": entity_count,
                    "relation_count": relation_count,
                    "document_count": document_count,
                }
        except Exception as e:
            logger.error(f"获取图谱统计失败: {e}")
            return {"entity_count": 0, "relation_count": 0, "document_count": 0}

    def get_full_graph(self, user_id: str, limit: int = 200) -> Dict[str, Any]:
        """获取用户的完整知识图谱数据(用于可视化)
        
        Args:
            user_id: 用户ID
            limit: 最大节点数量限制(避免返回过多数据)
            
        Returns:
            {
                "nodes": [{"id", "label", "type", "properties"}],
                "edges": [{"source", "target", "type", "properties"}],
                "document_count": 文档数量,
                "total_nodes": 实体总数,
                "total_edges": 关系总数
            }
        """
        if not self.available:
            return {"nodes": [], "edges": [], "document_count": 0, "total_nodes": 0, "total_edges": 0}

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                # user_id 在 Neo4j 中存储为字符串，直接使用
                neo4j_user_id = str(user_id)
                
                # 获取文档数量
                doc_result = session.run(
                    "MATCH (d:Document {user_id: $user_id}) RETURN count(d) AS count",
                    user_id=neo4j_user_id,
                )
                document_count = doc_result.single()["count"]
                
                # 获取所有实体节点(限制数量)
                entities_query = """
                MATCH (e:Entity {user_id: $user_id})
                WITH e ORDER BY e.created_at DESC LIMIT $limit
                RETURN coalesce(e.entity_id, e.entity_name) AS id, labels(e)[0] AS label, e.entity_type AS type, 
                       e.entity_name AS name, e.description AS description,
                       e.created_at AS created_at
                """
                entity_result = session.run(entities_query, user_id=neo4j_user_id, limit=limit)
                
                nodes = []
                entity_ids = set()
                for record in entity_result:
                    node = {
                        "id": record["id"],
                        "label": record["name"],
                        "type": record.get("type", "Entity"),
                        "description": record.get("description", "")
                    }
                    nodes.append(node)
                    entity_ids.add(record["id"])
                
                # 获取这些实体之间的关系
                relations_query = """
                MATCH (e1:Entity {user_id: $user_id})-[r:RELATED_TO]->(e2:Entity {user_id: $user_id})
                WHERE e1.entity_id IN $entity_ids AND e2.entity_id IN $entity_ids
                RETURN e1.entity_id AS source, e2.entity_id AS target, r.relation_type AS type,
                       r.weight AS weight, r.created_at AS created_at
                """
                relation_result = session.run(
                    relations_query, 
                    user_id=neo4j_user_id, 
                    entity_ids=list(entity_ids)
                )
                
                edges = []
                for record in relation_result:
                    edge = {
                        "source": record["source"],
                        "target": record["target"],
                        "type": record.get("type", "RELATED_TO"),
                        "weight": record.get("weight", 1.0)
                    }
                    edges.append(edge)
                
                return {
                    "nodes": nodes,
                    "edges": edges,
                    "document_count": document_count,
                    "total_nodes": len(nodes),
                    "total_edges": len(edges)
                }
        except Exception as e:
            logger.error(f"获取图谱数据失败: {e}")
            return {"nodes": [], "edges": [], "document_count": 0, "total_nodes": 0, "total_edges": 0, "error": str(e)}
    
    def get_document_graph(self, user_id: str, limit: int = 100) -> Dict[str, Any]:
        """获取文档图谱(文档节点和文档间关系)
        
        Args:
            user_id: 用户ID
            limit: 最大文档数量限制
            
        Returns:
            {
                "nodes": [{"id", "label", "type", "properties"}],
                "edges": [{"source", "target", "type", "properties"}],
                "total_nodes": 文档总数,
                "total_edges": 关系总数
            }
        """
        if not self.available:
            return {"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0}

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                # user_id 在 Neo4j 中存储为字符串，直接使用
                neo4j_user_id = str(user_id)
                
                # 获取所有文档节点
                docs_query = """
                MATCH (d:Document {user_id: $user_id})
                WITH d ORDER BY d.created_at DESC LIMIT $limit
                RETURN d.doc_id AS id, d.title AS label, 'Document' AS type,
                       d.created_at AS created_at
                """
                doc_result = session.run(docs_query, user_id=neo4j_user_id, limit=limit)
                
                nodes = []
                doc_ids = set()
                for record in doc_result:
                    # 处理可能的None值
                    doc_id = record.get("id")
                    if not doc_id:
                        logger.warning(f"跳过没有id的文档记录: {record}")
                        continue
                    
                    node = {
                        "id": doc_id,
                        "label": record.get("label") or f"文档{doc_id[:8]}",
                        "type": "Document",
                        "created_at": record.get("created_at")
                    }
                    nodes.append(node)
                    doc_ids.add(doc_id)
                
                logger.info(f"找到 {len(nodes)} 个文档节点, IDs: {list(doc_ids)[:5]}...")
                
                # 如果没有文档，直接返回
                if not doc_ids:
                    return {
                        "nodes": [],
                        "edges": [],
                        "total_nodes": 0,
                        "total_edges": 0
                    }
                
                # 获取文档之间的关系(通过共享实体)
                relations_query = """
                MATCH (d1:Document {user_id: $user_id})-[:APPEARS_IN]-(e:Entity)-[:APPEARS_IN]-(d2:Document {user_id: $user_id})
                WHERE d1.doc_id IN $doc_ids AND d2.doc_id IN $doc_ids AND d1.doc_id < d2.doc_id
                WITH d1, d2, count(e) AS weight
                RETURN d1.doc_id AS source, d2.doc_id AS target, 'SHARED_ENTITY' AS type, weight
                """
                relation_result = session.run(
                    relations_query, 
                    user_id=neo4j_user_id, 
                    doc_ids=list(doc_ids)
                )
                
                edges = []
                for record in relation_result:
                    edge = {
                        "source": record.get("source"),
                        "target": record.get("target"),
                        "type": record.get("type", "SHARED_ENTITY"),
                        "weight": record.get("weight", 1.0)
                    }
                    edges.append(edge)
                
                logger.info(f"找到 {len(edges)} 条文档关系")
                
                return {
                    "nodes": nodes,
                    "edges": edges,
                    "total_nodes": len(nodes),
                    "total_edges": len(edges)
                }
        except Exception as e:
            logger.error(f"获取文档图谱失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0, "error": str(e)}
    
    def get_entity_graph(self, user_id: str, limit: int = 200) -> Dict[str, Any]:
        """获取实体图谱(实体节点和实体间关系)
        
        Args:
            user_id: 用户ID
            limit: 最大实体数量限制
            
        Returns:
            {
                "nodes": [{"id", "label", "type", "properties"}],
                "edges": [{"source", "target", "type", "properties"}],
                "total_nodes": 实体总数,
                "total_edges": 关系总数
            }
        """
        if not self.available:
            return {"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0}

        try:
            with self._driver.session(database=settings.neo4j_database) as session:
                # user_id 在 Neo4j 中存储为字符串，直接使用
                neo4j_user_id = str(user_id)
                
                # 获取所有实体节点
                entities_query = """
                MATCH (e:Entity {user_id: $user_id})
                WITH e ORDER BY e.created_at DESC LIMIT $limit
                RETURN coalesce(e.entity_id, e.entity_name) AS id, e.entity_name AS label, e.entity_type AS type,
                       e.description AS description, e.created_at AS created_at
                """
                entity_result = session.run(entities_query, user_id=neo4j_user_id, limit=limit)
                
                nodes = []
                entity_ids = set()
                for record in entity_result:
                    # 处理可能的None值
                    entity_id = record.get("id")
                    if not entity_id:
                        logger.warning(f"跳过没有id的实体记录: {record}")
                        continue
                    
                    node = {
                        "id": entity_id,
                        "label": record.get("label") or f"实体{entity_id[:8]}",
                        "type": record.get("type") or "Entity",
                        "description": record.get("description", "")
                    }
                    nodes.append(node)
                    entity_ids.add(entity_id)
                
                logger.info(f"找到 {len(nodes)} 个实体节点, IDs: {list(entity_ids)[:5]}...")
                
                # 如果没有实体，直接返回
                if not entity_ids:
                    return {
                        "nodes": [],
                        "edges": [],
                        "total_nodes": 0,
                        "total_edges": 0
                    }
                
                # 获取实体之间的关系
                relations_query = """
                MATCH (e1:Entity {user_id: $user_id})-[r]->(e2:Entity {user_id: $user_id})
                WHERE coalesce(e1.entity_id, e1.entity_name) IN $entity_ids 
                  AND coalesce(e2.entity_id, e2.entity_name) IN $entity_ids
                  AND e1 <> e2
                RETURN coalesce(e1.entity_id, e1.entity_name) AS source, 
                       coalesce(e2.entity_id, e2.entity_name) AS target, 
                       coalesce(r.relation_type, type(r)) AS type,
                       r.weight AS weight, r.created_at AS created_at
                """
                relation_result = session.run(
                    relations_query, 
                    user_id=neo4j_user_id, 
                    entity_ids=list(entity_ids)
                )
                
                edges = []
                for record in relation_result:
                    edge = {
                        "source": record.get("source"),
                        "target": record.get("target"),
                        "type": record.get("type", "RELATED_TO"),
                        "weight": record.get("weight", 1.0)
                    }
                    edges.append(edge)
                
                logger.info(f"找到 {len(edges)} 条实体关系")
                
                return {
                    "nodes": nodes,
                    "edges": edges,
                    "total_nodes": len(nodes),
                    "total_edges": len(edges)
                }
        except Exception as e:
            logger.error(f"获取实体图谱失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0, "error": str(e)}


    def sync_with_mysql(self, user_id: str) -> Dict[str, int]:
        """
        同步 Neo4j 与 MySQL 的文档数据一致性
        
        以 MySQL 为单一事实来源（Single Source of Truth）：
        1. 查询 MySQL 中该用户所有未删除的文档 ID
        2. 删除 Neo4j 中存在但 MySQL 中不存在的 Document 节点
        3. 清理孤立 Entity 节点
        
        Returns:
            统计信息：{"orphan_docs_deleted": N, "orphan_entities_deleted": M}
        """
        if not self.available:
            logger.warning("Neo4j 不可用，跳过同步")
            return {"orphan_docs_deleted": 0, "orphan_entities_deleted": 0}
        
        try:
            # 1. 从 MySQL 获取权威文档列表
            from app.core.sql import get_db
            from app.models.db_models import DocumentORM
            
            db = next(get_db())
            mysql_doc_ids = set(
                doc.doc_id for doc in db.query(DocumentORM.doc_id).filter(
                    DocumentORM.user_id == user_id,
                    DocumentORM.is_deleted == False
                ).all()
            )
            db.close()
            
            logger.info(f"MySQL 中文档数量: {len(mysql_doc_ids)}")
            
            # 2. 找出 Neo4j 中的孤儿文档（MySQL 中不存在或未删除的）
            with self._driver.session(database=settings.neo4j_database) as session:
                # 先获取 Neo4j 中所有文档 ID
                neo4j_docs_result = session.run(
                    "MATCH (d:Document {user_id: $user_id}) RETURN d.doc_id AS doc_id",
                    user_id=user_id,
                )
                neo4j_doc_ids = {record["doc_id"] for record in neo4j_docs_result}
                
                orphan_doc_ids = neo4j_doc_ids - mysql_doc_ids
                
                if orphan_doc_ids:
                    logger.warning(f"发现 {len(orphan_doc_ids)} 个孤儿文档节点: {orphan_doc_ids}")
                    
                    # 批量删除孤儿文档及其关系
                    result = session.run(
                        """
                        MATCH (d:Document {user_id: $user_id})
                        WHERE d.doc_id IN $orphan_ids
                        DETACH DELETE d
                        RETURN count(d) AS deleted_count
                        """,
                        user_id=user_id,
                        orphan_ids=list(orphan_doc_ids),
                    )
                    deleted_docs = result.single()["deleted_count"]
                    logger.info(f"已删除 {deleted_docs} 个孤儿文档节点")
                else:
                    deleted_docs = 0
                    logger.info("Neo4j 与 MySQL 文档数据一致，无孤儿节点")
                
                # 3. 清理孤立实体节点（没有 APPEARS_IN 关系的）
                orphan_entities_result = session.run(
                    """
                    MATCH (e:Entity {user_id: $user_id})
                    WHERE NOT (e)-[:APPEARS_IN]->(:Document)
                    WITH e LIMIT 5000
                    DETACH DELETE e
                    RETURN count(e) AS deleted_count
                    """,
                    user_id=user_id,
                )
                deleted_entities = orphan_entities_result.single()["deleted_count"]
                
                if deleted_entities > 0:
                    logger.info(f"已清理 {deleted_entities} 个孤立实体节点")
                
                return {
                    "orphan_docs_deleted": deleted_docs,
                    "orphan_entities_deleted": deleted_entities,
                    "mysql_doc_count": len(mysql_doc_ids),
                    "neo4j_doc_count": len(neo4j_doc_ids) - len(orphan_doc_ids),
                }
                
        except Exception as e:
            logger.error(f"同步 Neo4j 与 MySQL 失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "orphan_docs_deleted": 0,
                "orphan_entities_deleted": 0,
                "error": str(e),
            }


# ─── 单例管理 ────────────────────────────────────────────────────

_kg_service: Optional[KnowledgeGraphService] = None


def get_knowledge_graph_service() -> KnowledgeGraphService:
    """获取知识图谱服务单例"""
    global _kg_service
    if _kg_service is None:
        _kg_service = KnowledgeGraphService()
        _kg_service.connect()
    return _kg_service
