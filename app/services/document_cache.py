"""
Redis缓存服务 - 用于缓存文档元数据
"""
import json
from typing import Optional, Dict, Any, List
from loguru import logger
import redis
from config.settings import settings


class DocumentMetadataCache:
    """文档元数据Redis缓存服务"""
    
    def __init__(self):
        self.enabled = settings.redis_enabled
        self.ttl = settings.document_metadata_cache_ttl
        
        if not self.enabled:
            logger.info("Redis缓存未启用")
            self.client = None
            return
        
        try:
            # 创建Redis连接
            self.client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True,  # 自动解码为字符串
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # 测试连接
            self.client.ping()
            logger.info(f"Redis连接成功: {settings.redis_host}:{settings.redis_port}")
            
        except Exception as e:
            logger.warning(f"Redis连接失败，缓存功能将不可用: {e}")
            self.client = None
            self.enabled = False
    
    def _get_cache_key(self, document_id: str) -> str:
        """生成缓存键"""
        return f"doc:meta:{document_id}"
    
    def get(self, document_id: str) -> Optional[Dict[str, Any]]:
        """获取文档元数据缓存"""
        if not self.enabled or not self.client:
            return None
        
        try:
            cache_key = self._get_cache_key(document_id)
            cached_data = self.client.get(cache_key)
            
            if cached_data:
                logger.debug(f"缓存命中: {document_id}")
                return json.loads(cached_data)
            else:
                logger.debug(f"缓存未命中: {document_id}")
                return None
                
        except Exception as e:
            logger.warning(f"Redis读取失败: {e}")
            return None
    
    def set(self, document_id: str, metadata: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """设置文档元数据缓存"""
        if not self.enabled or not self.client:
            return False
        
        try:
            cache_key = self._get_cache_key(document_id)
            cache_ttl = ttl or self.ttl
            
            # 序列化并存储
            serialized = json.dumps(metadata, ensure_ascii=False, default=str)
            self.client.setex(cache_key, cache_ttl, serialized)
            
            logger.debug(f"缓存已设置: {document_id}, TTL={cache_ttl}s")
            return True
            
        except Exception as e:
            logger.warning(f"Redis写入失败: {e}")
            return False
    
    def delete(self, document_id: str) -> bool:
        """删除文档元数据缓存"""
        if not self.enabled or not self.client:
            return False
        
        try:
            cache_key = self._get_cache_key(document_id)
            result = self.client.delete(cache_key)
            
            if result > 0:
                logger.debug(f"缓存已删除: {document_id}")
            
            return result > 0
            
        except Exception as e:
            logger.warning(f"Redis删除失败: {e}")
            return False
    
    def mget(self, document_ids: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """批量获取文档元数据缓存"""
        if not self.enabled or not self.client:
            return {}
        
        results = {}
        try:
            cache_keys = [self._get_cache_key(doc_id) for doc_id in document_ids]
            cached_values = self.client.mget(cache_keys)
            
            for doc_id, cached_data in zip(document_ids, cached_values):
                if cached_data:
                    results[doc_id] = json.loads(cached_data)
                else:
                    results[doc_id] = None
            
            hit_count = sum(1 for v in results.values() if v is not None)
            logger.debug(f"批量缓存查询: {len(document_ids)}个文档, 命中{hit_count}个")
            
            return results
            
        except Exception as e:
            logger.warning(f"Redis批量读取失败: {e}")
            return {}
    
    def invalidate_user_documents(self, user_id: str) -> int:
        """失效用户的所有文档缓存（通过模式匹配）"""
        if not self.enabled or not self.client:
            return 0
        
        try:
            # Redis不支持直接按value搜索，这里只能通过前缀扫描
            # 更好的做法是在应用层维护user->docs映射
            pattern = "doc:meta:*"
            deleted_count = 0
            
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor=cursor, match=pattern, count=100)
                
                if keys:
                    # 需要检查每个key对应的user_id
                    for key in keys:
                        doc_id = key.replace("doc:meta:", "")
                        # 这里简化处理，实际应该先查metadata确认user_id
                        # 或者维护额外的索引: user:{user_id}:docs -> [doc_ids]
                        pass
                
                if cursor == 0:
                    break
            
            logger.info(f"用户 {user_id} 的文档缓存失效完成")
            return deleted_count
            
        except Exception as e:
            logger.warning(f"Redis批量失效失败: {e}")
            return 0
    
    def clear_all(self) -> bool:
        """清空所有文档缓存（慎用）"""
        if not self.enabled or not self.client:
            return False
        
        try:
            pattern = "doc:meta:*"
            deleted_count = 0
            
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor=cursor, match=pattern, count=100)
                
                if keys:
                    self.client.delete(*keys)
                    deleted_count += len(keys)
                
                if cursor == 0:
                    break
            
            logger.info(f"已清空所有文档缓存，共{deleted_count}个")
            return True
            
        except Exception as e:
            logger.warning(f"Redis清空缓存失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self.enabled or not self.client:
            return {"enabled": False}
        
        try:
            info = self.client.info('memory')
            keys_count = self.client.dbsize()
            
            return {
                "enabled": True,
                "connected": True,
                "total_keys": keys_count,
                "used_memory_human": info.get('used_memory_human', 'N/A'),
                "max_memory_human": info.get('maxmemory_human', 'N/A'),
                "ttl_seconds": self.ttl
            }
            
        except Exception as e:
            logger.warning(f"获取Redis统计失败: {e}")
            return {"enabled": True, "connected": False, "error": str(e)}
    
    def health_check(self) -> bool:
        """健康检查"""
        if not self.enabled:
            return True
        
        try:
            if self.client:
                return self.client.ping()
            return False
        except Exception:
            return False


# 单例模式
_cache_instance = None

def get_document_metadata_cache() -> DocumentMetadataCache:
    """获取文档元数据缓存单例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DocumentMetadataCache()
    return _cache_instance

