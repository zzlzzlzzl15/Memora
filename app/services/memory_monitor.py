"""
内存监控服务 - 实时监控系统内存使用情况
"""
import psutil
import os
from typing import Dict, Any
from loguru import logger
from datetime import datetime


class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self._last_check_time = None
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取详细的内存使用统计"""
        try:
            # 进程内存信息
            memory_info = self.process.memory_info()
            
            stats = {
                "timestamp": datetime.utcnow().isoformat(),
                "process": {
                    "rss_mb": round(memory_info.rss / 1024 / 1024, 2),  # 物理内存
                    "vms_mb": round(memory_info.vms / 1024 / 1024, 2),  # 虚拟内存
                    "percent": round(self.process.memory_percent(), 2),  # 系统内存占比
                },
                "system": {
                    "total_gb": round(psutil.virtual_memory().total / 1024 / 1024 / 1024, 2),
                    "available_gb": round(psutil.virtual_memory().available / 1024 / 1024 / 1024, 2),
                    "used_percent": psutil.virtual_memory().percent,
                }
            }
            
            # 尝试获取应用组件的内存使用情况
            try:
                from app.services.document_service import get_document_service
                doc_service = get_document_service()
                
                stats["components"] = {
                    "document_cache": {
                        "cached_documents": len(doc_service.store.documents),
                        "metadata_documents": len(doc_service.store.document_metadata),
                        "max_cache_size": doc_service.store.max_cached_documents,
                        "cache_usage_percent": round(
                            len(doc_service.store.documents) / doc_service.store.max_cached_documents * 100, 2
                        ) if doc_service.store.max_cached_documents > 0 else 0
                    }
                }
                
                # Redis缓存统计
                try:
                    redis_stats = doc_service.metadata_cache.get_stats()
                    stats["components"]["redis_cache"] = redis_stats
                except Exception as e:
                    logger.debug(f"获取Redis统计失败: {e}")
                
                # Embedding模型状态
                try:
                    from app.services.embedding import get_embedding_service
                    emb_service = get_embedding_service()
                    stats["components"]["embedding_model"] = {
                        "loaded": emb_service.model is not None,
                        "provider": emb_service.provider,
                        "sparse_enabled": emb_service.sparse_enabled,
                        "sparse_loaded": emb_service.sparse_model is not None if emb_service.sparse_enabled else False
                    }
                except Exception as e:
                    logger.debug(f"获取Embedding统计失败: {e}")
                
                # Rerank模型状态
                try:
                    from app.services.rerank import get_rerank_service
                    rerank_service = get_rerank_service()
                    stats["components"]["rerank_model"] = {
                        "enabled": rerank_service.enabled,
                        "loaded": rerank_service.model is not None if hasattr(rerank_service, 'model') else False
                    }
                except Exception as e:
                    logger.debug(f"获取Rerank统计失败: {e}")
                    
            except Exception as e:
                logger.warning(f"获取组件统计失败: {e}")
                stats["components"] = {"error": str(e)}
            
            self._last_check_time = datetime.utcnow()
            
            return stats
            
        except Exception as e:
            logger.error(f"获取内存统计失败: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_threshold(self, threshold_mb: int = 2048) -> Dict[str, Any]:
        """检查内存是否超过阈值"""
        stats = self.get_memory_stats()
        
        rss_mb = stats.get("process", {}).get("rss_mb", 0)
        
        result = {
            "threshold_mb": threshold_mb,
            "current_mb": rss_mb,
            "exceeded": rss_mb > threshold_mb,
            "usage_percent": round(rss_mb / threshold_mb * 100, 2) if threshold_mb > 0 else 0,
            "recommendation": None
        }
        
        # 根据使用情况给出建议
        if rss_mb > threshold_mb * 1.5:
            result["recommendation"] = "严重超标! 建议立即清理缓存或重启服务"
            logger.warning(f"⚠️ 内存严重超标: {rss_mb}MB / {threshold_mb}MB")
        elif rss_mb > threshold_mb:
            result["recommendation"] = "超过阈值,建议监控趋势并考虑优化"
            logger.warning(f"⚠️ 内存超过阈值: {rss_mb}MB / {threshold_mb}MB")
        elif rss_mb > threshold_mb * 0.8:
            result["recommendation"] = "接近阈值,建议关注内存增长趋势"
            logger.info(f"ℹ️ 内存接近阈值: {rss_mb}MB / {threshold_mb}MB")
        else:
            result["recommendation"] = "内存使用正常"
        
        return result
    
    def get_trend(self, samples: int = 10) -> Dict[str, Any]:
        """获取内存使用趋势(简化版,实际应存储历史数据)"""
        current = self.get_memory_stats()
        
        return {
            "current": current,
            "note": "趋势分析需要持久化历史数据,当前仅返回瞬时值",
            "suggestion": "建议使用Prometheus + Grafana进行长期监控"
        }
    
    def emergency_cleanup(self) -> Dict[str, Any]:
        """紧急清理 - 在内存过高时调用"""
        logger.warning("🚨 执行紧急内存清理...")
        
        cleanup_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "actions": []
        }
        
        try:
            # 1. 清空文档缓存
            from app.services.document_service import get_document_service
            doc_service = get_document_service()
            
            cached_count = len(doc_service.store.documents)
            doc_service.store.documents.clear()
            doc_service.store.access_order.clear()
            
            cleanup_result["actions"].append({
                "action": "clear_document_cache",
                "cleared_count": cached_count,
                "success": True
            })
            logger.info(f"已清空文档缓存: {cached_count}个文档")
            
            # 2. 清空Redis缓存
            try:
                cleared = doc_service.metadata_cache.clear_all()
                cleanup_result["actions"].append({
                    "action": "clear_redis_cache",
                    "cleared": cleared,
                    "success": True
                })
            except Exception as e:
                cleanup_result["actions"].append({
                    "action": "clear_redis_cache",
                    "error": str(e),
                    "success": False
                })
            
            # 3. 强制GC
            import gc
            collected = gc.collect()
            cleanup_result["actions"].append({
                "action": "force_garbage_collection",
                "collected_objects": collected,
                "success": True
            })
            
            # 4. 记录清理后内存
            after_stats = self.get_memory_stats()
            cleanup_result["after_cleanup"] = after_stats
            
            logger.info(f"✅ 紧急清理完成,当前内存: {after_stats['process']['rss_mb']}MB")
            
        except Exception as e:
            logger.error(f"紧急清理失败: {e}")
            cleanup_result["error"] = str(e)
        
        return cleanup_result


# 单例模式
_monitor_instance = None

def get_memory_monitor() -> MemoryMonitor:
    """获取内存监控器单例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = MemoryMonitor()
    return _monitor_instance
