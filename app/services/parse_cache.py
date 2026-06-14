"""
解析结果缓存服务

基于文件指纹（mtime + size + 配置哈希）的 JSON 文件缓存，
避免重复解析同一文档，减少 MinerU 等解析器的调用次数。

缓存存储位置：uploads/.parse_cache/
缓存键：md5(file_path + file_size + mtime + parser_config_hash)
"""
import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from loguru import logger

from config.settings import settings


class ParseCacheService:
    """解析结果缓存服务"""

    def __init__(self):
        self.cache_dir = Path(settings.upload_dir) / ".parse_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"解析缓存目录: {self.cache_dir}")

    def _generate_cache_key(self, file_path: str, parse_config: Dict[str, Any] = None) -> str:
        """
        生成缓存键：基于文件路径 + 大小 + mtime + 解析配置
        
        Args:
            file_path: 文件路径
            parse_config: 解析配置（如 chunk_size, chunk_overlap 等）
        
        Returns:
            缓存键字符串（md5 哈希）
        """
        try:
            stat = os.stat(file_path)
            # 组合唯一标识
            key_parts = [
                file_path,
                str(stat.st_size),
                str(stat.st_mtime),
            ]
            # 加入解析配置
            if parse_config:
                # 排序保证一致性
                config_str = json.dumps(parse_config, sort_keys=True)
                key_parts.append(config_str)
            
            key_str = "|".join(key_parts)
            cache_key = hashlib.md5(key_str.encode()).hexdigest()
            return cache_key
        except FileNotFoundError:
            logger.warning(f"文件不存在，无法生成缓存键: {file_path}")
            return None

    def _cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, file_path: str, parse_config: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        获取缓存的解析结果
        
        Args:
            file_path: 文件路径
            parse_config: 解析配置
        
        Returns:
            缓存结果字典，未命中返回 None
        """
        cache_key = self._generate_cache_key(file_path, parse_config)
        if not cache_key:
            return None

        cache_file = self._cache_path(cache_key)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 验证缓存的文件路径和 mtime 仍然匹配
            cached_path = data.get("file_path")
            cached_mtime = data.get("mtime")
            if cached_path != file_path:
                logger.debug(f"缓存路径不匹配: {cached_path} != {file_path}")
                return None

            # 验证文件未被修改
            current_mtime = os.stat(file_path).st_mtime
            if abs(current_mtime - cached_mtime) > 1.0:  # 允许1秒误差
                logger.debug(f"文件已被修改，缓存失效: {file_path}")
                self.invalidate(file_path, parse_config)
                return None

            logger.info(f"解析缓存命中: {file_path} (key={cache_key[:8]}...)")
            return data.get("result")

        except Exception as e:
            logger.warning(f"读取缓存失败: {e}")
            return None

    def set(
        self,
        file_path: str,
        result: Dict[str, Any],
        parse_config: Dict[str, Any] = None
    ) -> bool:
        """
        保存解析结果到缓存
        
        Args:
            file_path: 文件路径
            result: 解析结果（如 content_list, extracted_text 等）
            parse_config: 解析配置
        
        Returns:
            是否保存成功
        """
        cache_key = self._generate_cache_key(file_path, parse_config)
        if not cache_key:
            return False

        cache_file = self._cache_path(cache_key)
        try:
            stat = os.stat(file_path)
            data = {
                "file_path": file_path,
                "mtime": stat.st_mtime,
                "file_size": stat.st_size,
                "parse_config": parse_config or {},
                "result": result,
                "cached_at": os.path.getmtime(file_path),
            }

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"解析结果已缓存: {file_path} (key={cache_key[:8]}...)")
            return True

        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
            return False

    def invalidate(self, file_path: str, parse_config: Dict[str, Any] = None) -> bool:
        """
        使指定文件的缓存失效
        
        Args:
            file_path: 文件路径
            parse_config: 解析配置
        
        Returns:
            是否成功删除缓存
        """
        cache_key = self._generate_cache_key(file_path, parse_config)
        if not cache_key:
            return False

        cache_file = self._cache_path(cache_key)
        try:
            if cache_file.exists():
                os.remove(cache_file)
                logger.info(f"缓存已失效: {file_path} (key={cache_key[:8]}...)")
            return True
        except Exception as e:
            logger.warning(f"删除缓存失败: {e}")
            return False

    def clear_all(self) -> int:
        """
        清空所有缓存
        
        Returns:
            删除的缓存文件数量
        """
        count = 0
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    os.remove(cache_file)
                    count += 1
                except Exception:
                    pass
            logger.info(f"已清空 {count} 个缓存文件")
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
        return count

    def cleanup_stale(self, max_age_days: int = 30) -> int:
        """
        清理过期缓存（超过指定天数的缓存文件）
        
        Args:
            max_age_days: 最大缓存天数
        
        Returns:
            删除的缓存文件数量
        """
        import time
        count = 0
        cutoff = time.time() - (max_age_days * 86400)
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    if cache_file.stat().st_mtime < cutoff:
                        os.remove(cache_file)
                        count += 1
                except Exception:
                    pass
            if count > 0:
                logger.info(f"已清理 {count} 个过期缓存文件")
        except Exception as e:
            logger.error(f"清理过期缓存失败: {e}")
        return count


# 全局缓存服务实例
_parse_cache_service = None


def get_parse_cache_service() -> ParseCacheService:
    """获取解析缓存服务实例（单例模式）"""
    global _parse_cache_service
    if _parse_cache_service is None:
        _parse_cache_service = ParseCacheService()
    return _parse_cache_service
