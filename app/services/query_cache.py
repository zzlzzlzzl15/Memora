"""
查询结果缓存服务

参照 RAG-Anything 的多模态查询缓存设计，采用本地文件存储（无需 Redis 额外依赖）：
- 缓存键：md5(query_text + user_id + query_mode + limit + score_threshold)
- 缓存内容：search_results + answer（可选）+ 元信息
- TTL：默认 3600 秒（可配置）
- 失效策略：文档增删改时主动清理该用户的全部缓存

存储路径：{upload_dir}/.query_cache/{user_id}/{cache_key}.json
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, List

from loguru import logger
from config.settings import settings


class QueryCache:
    """本地文件查询缓存

    设计原则：
    - 零依赖（无 Redis）：使用本地 JSON 文件存储
    - 按用户隔离：每个用户独立目录，清除时只影响该用户
    - 线程安全写入：先写临时文件再原子替换
    - 自动过期：读取时检查 TTL，写入时记录 cached_at
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        ttl_seconds: int = 3600,
        enabled: bool = True,
    ):
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        # 默认缓存目录：{upload_dir}/.query_cache
        if cache_dir is None:
            cache_dir = os.path.join(settings.upload_dir, ".query_cache")
        self.cache_dir = Path(cache_dir)
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────────────

    def make_key(
        self,
        query: str,
        user_id: str,
        query_mode: str = "vector",
        limit: int = 10,
        score_threshold: float = 0.7,
    ) -> str:
        """生成缓存键（md5 哈希）

        参照 RAG-Anything 的 _generate_multimodal_cache_key 方法。
        """
        raw = json.dumps(
            {
                "query": query.strip(),
                "user_id": user_id,
                "mode": query_mode,
                "limit": limit,
                "threshold": score_threshold,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str, user_id: str) -> Optional[Dict[str, Any]]:
        """读取缓存条目，过期或不存在返回 None"""
        if not self.enabled:
            return None
        path = self._cache_path(user_id, key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # 检查 TTL
            cached_at = data.get("cached_at", 0)
            if time.time() - cached_at > self.ttl_seconds:
                logger.debug("查询缓存已过期: %s", key[:8])
                path.unlink(missing_ok=True)
                return None
            logger.info("查询缓存命中: %s (user=%s)", key[:8], user_id)
            return data
        except Exception as e:
            logger.debug("查询缓存读取失败 %s: %s", key[:8], e)
            return None

    def set(
        self,
        key: str,
        user_id: str,
        search_results: List[Any],
        answer: Optional[str] = None,
        query: str = "",
        query_mode: str = "vector",
    ) -> bool:
        """写入缓存条目（先写临时文件，再原子替换）"""
        if not self.enabled:
            return False
        try:
            user_dir = self._user_cache_dir(user_id)
            user_dir.mkdir(parents=True, exist_ok=True)

            # 序列化 search_results（Pydantic 模型 → dict）
            results_data = []
            for r in search_results:
                if hasattr(r, "model_dump"):
                    results_data.append(r.model_dump(mode="json"))
                elif hasattr(r, "dict"):
                    results_data.append(r.dict())
                else:
                    results_data.append(r)

            entry = {
                "query": query,
                "query_mode": query_mode,
                "cached_at": time.time(),
                "ttl": self.ttl_seconds,
                "search_results": results_data,
                "answer": answer,
            }
            path = self._cache_path(user_id, key)
            tmp_path = path.with_suffix(".tmp")
            tmp_path.write_text(
                json.dumps(entry, ensure_ascii=False, indent=None),
                encoding="utf-8",
            )
            tmp_path.replace(path)
            logger.debug("查询缓存已写入: %s (user=%s)", key[:8], user_id)
            return True
        except Exception as e:
            logger.warning("查询缓存写入失败 %s: %s", key[:8], e)
            return False

    def invalidate_user(self, user_id: str) -> int:
        """清除指定用户的全部查询缓存（文档增删改时调用）

        Returns:
            int: 删除的缓存条目数量
        """
        if not self.enabled:
            return 0
        user_dir = self._user_cache_dir(user_id)
        if not user_dir.exists():
            return 0
        count = 0
        try:
            for f in user_dir.glob("*.json"):
                f.unlink(missing_ok=True)
                count += 1
            logger.info("已清除用户 %s 的 %d 条查询缓存", user_id, count)
        except Exception as e:
            logger.warning("清除用户 %s 查询缓存失败: %s", user_id, e)
        return count

    def cleanup_expired(self) -> int:
        """清理所有已过期的缓存条目（可在定时任务中调用）

        Returns:
            int: 删除的过期条目数
        """
        if not self.enabled or not self.cache_dir.exists():
            return 0
        count = 0
        now = time.time()
        for json_file in self.cache_dir.rglob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                cached_at = data.get("cached_at", 0)
                if now - cached_at > self.ttl_seconds:
                    json_file.unlink(missing_ok=True)
                    count += 1
            except Exception:
                # 损坏的缓存文件直接删除
                try:
                    json_file.unlink(missing_ok=True)
                    count += 1
                except Exception:
                    pass
        if count:
            logger.info("已清理 %d 条过期查询缓存", count)
        return count

    def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self.enabled or not self.cache_dir.exists():
            return {"enabled": False, "total": 0}
        total = sum(1 for _ in self.cache_dir.rglob("*.json"))
        return {
            "enabled": True,
            "total": total,
            "cache_dir": str(self.cache_dir),
            "ttl_seconds": self.ttl_seconds,
        }

    # ──────────────────────────────────────────────────────
    # 私有方法
    # ──────────────────────────────────────────────────────

    def _user_cache_dir(self, user_id: str) -> Path:
        return self.cache_dir / str(user_id)

    def _cache_path(self, user_id: str, key: str) -> Path:
        return self._user_cache_dir(user_id) / f"{key}.json"


# ──────────────────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────────────────
_query_cache: Optional[QueryCache] = None


def get_query_cache() -> QueryCache:
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(
            ttl_seconds=getattr(settings, "query_cache_ttl", 3600),
            enabled=getattr(settings, "query_cache_enabled", True),
        )
    return _query_cache
