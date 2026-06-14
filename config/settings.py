from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # 应用配置
    app_name: str = "Personal Knowledge Base"
    app_version: str = "0.1.4"
    debug: bool = False
    log_level: str = "INFO"
    # 日志文件路径（使用绝对路径，基于项目根目录）
    log_file: str = os.getenv("LOG_FILE") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "app.log")
    # LLM 专用日志文件（仅记录LLM返回内容）
    llm_log_file: str = os.getenv("LLM_LOG_FILE") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "llm.log")
    
    # Qdrant配置（从环境变量加载）
    qdrant_host: str
    qdrant_port: int
    qdrant_api_key: Optional[str] = None
    qdrant_collection_name: str
    qdrant_default_limit: int
    # 安全保护：是否允许在配置不匹配时自动重建集合（会清空数据）
    qdrant_allow_recreate_on_mismatch: bool = False
    
    # JWT配置
    secret_key: str = "your-secret-key-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30  # access token 过期时间（分钟）
    refresh_token_expire_days: int = 30    # refresh token 过期时间（天）
    
    # 向量化模型配置（兼容阿里DashScope OpenAI接口）
    embedding_model: str = os.getenv("EMBEDDING_MODEL") or "openai/text-embedding-v4"
    vector_size: int = int(os.getenv("VECTOR_SIZE") or 1024)
    # 优先使用 DASHSCOPE_API_KEY，其次 OPENAI_API_KEY
    dashscope_api_key: Optional[str] = os.getenv("DASHSCOPE_API_KEY")
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    # 嵌入API的Base URL（阿里百炼兼容模式）
    embedding_api_base: Optional[str] = os.getenv("EMBEDDING_API_BASE") or "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # 稀疏嵌入与BM42配置
    use_sparse_bm42: bool = True
    sparse_embedding_model: str = os.getenv("SPARSE_EMBEDDING_MODEL") or "Qdrant/bm42-all-minilm-l6-v2-attentions"
    sparse_vector_name: str = os.getenv("SPARSE_VECTOR_NAME") or "bm42"

    # 默认搜索分数阈值（密集/稀疏），可通过环境变量覆盖
    qdrant_dense_default_threshold: float = float(os.getenv("QDRANT_DENSE_DEFAULT_THRESHOLD") or 0.7)
    qdrant_sparse_default_threshold: float = float(os.getenv("QDRANT_SPARSE_DEFAULT_THRESHOLD") or 0.0)
    
    # Rerank配置（使用通义千问在线API）
    use_rerank: bool = os.getenv("USE_RERANK", "true").lower() == "true"
    rerank_model: str = os.getenv("RERANK_MODEL") or "qwen3-rerank"
    rerank_top_n: int = int(os.getenv("RERANK_TOP_N") or 5)  # Rerank后返回给LLM的结果数
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K") or 20)  # 初始检索返回的候选数
    
    # LLM配置（OpenAI兼容，例如DeepSeek）
    llm_api_base: Optional[str] = os.getenv("LLM_API_BASE") or "https://api.deepseek.com/v1"
    llm_api_key: Optional[str] = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL") or "deepseek-chat"
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE") or 0.3)
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS") or 8192)  # DeepSeek最大支持8192

    # HuggingFace 缓存与镜像（供 fastembed / huggingface_hub 使用）
    hf_endpoint: Optional[str] = os.getenv("HF_ENDPOINT")
    hf_home: Optional[str] = os.getenv("HF_HOME")
    fastembed_cache_path: Optional[str] = os.getenv("FASTEMBED_CACHE_PATH")

    # 网页抓取配置（使用内置 httpx + BeautifulSoup 实现，无外部服务依赖）

    # 文件上传配置（使用绝对路径，基于项目根目录）
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: list = [".txt", ".pdf", ".docx", ".md"]
    # 从环境变量读取上传目录，默认为项目根目录下的uploads
    upload_dir: str = os.getenv("UPLOAD_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
    
    # 文本分块配置（可通过环境变量覆盖）
    text_chunk_size: int = int(os.getenv("TEXT_CHUNK_SIZE") or 500)
    text_chunk_overlap: int = int(os.getenv("TEXT_CHUNK_OVERLAP") or 100)

    # 结构化解析配置（MinerU）
    use_mineru: bool = os.getenv("USE_MINERU", "false").lower() == "true"
    mineru_method: str = os.getenv("MINERU_METHOD") or "auto"  # auto, ocr, txt

    # 多模态处理配置
    vlm_api_base: Optional[str] = os.getenv("VLM_API_BASE")  # 视觉语言模型 API
    vlm_api_key: Optional[str] = os.getenv("VLM_API_KEY")
    vlm_model: str = os.getenv("VLM_MODEL") or "qwen-vl-max"  # 默认使用通义千问 VL
    vlm_enabled: bool = os.getenv("VLM_ENABLED", "false").lower() == "true"

    # 解析缓存配置
    parse_cache_enabled: bool = os.getenv("PARSE_CACHE_ENABLED", "true").lower() == "true"
    parse_cache_max_age_days: int = int(os.getenv("PARSE_CACHE_MAX_AGE_DAYS") or 30)

    # 语义分块配置
    chunk_strategy: str = os.getenv("CHUNK_STRATEGY") or "fixed"  # fixed 或 semantic
    semantic_threshold: float = float(os.getenv("SEMANTIC_THRESHOLD") or 0.5)
    min_chunk_size: int = int(os.getenv("MIN_CHUNK_SIZE") or 100)

    # 上下文感知配置（参照 RAG-Anything ContextConfig）
    # context_window: 上下文窗口大小（page 模式=页数，chunk 模式=块数）
    context_window: int = int(os.getenv("CONTEXT_WINDOW") or 1)
    # context_mode: "page"（按页边界提取） / "chunk"（按块序号提取）
    context_mode: str = os.getenv("CONTEXT_MODE") or "page"
    # max_context_tokens: 上下文最大字符数（无 tokenizer 时按字符截断）
    max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS") or 2000)
    # context_include_headers: 是否在上下文中包含 Markdown 标题
    context_include_headers: bool = os.getenv("CONTEXT_INCLUDE_HEADERS", "true").lower() == "true"
    # context_include_captions: 是否在上下文中包含图片/表格标题
    context_include_captions: bool = os.getenv("CONTEXT_INCLUDE_CAPTIONS", "true").lower() == "true"
    # context_filter_content_types: 纳入上下文的内容类型列表（逗号分隔）
    context_filter_content_types: str = os.getenv("CONTEXT_FILTER_CONTENT_TYPES", "text")

    # 知识图谱配置（Neo4j）
    neo4j_enabled: bool = os.getenv("NEO4J_ENABLED", "false").lower() == "true"
    neo4j_uri: str = os.getenv("NEO4J_URI") or "bolt://localhost:7687"
    neo4j_user: str = os.getenv("NEO4J_USER") or "neo4j"
    neo4j_password: str = os.getenv("NEO4J_PASSWORD") or "password"
    neo4j_database: str = os.getenv("NEO4J_DATABASE") or "neo4j"

    # 图谱查询模式：vector / local / global / hybrid / mix
    kg_query_mode: str = os.getenv("KG_QUERY_MODE") or "vector"

    # Redis缓存配置
    redis_enabled: bool = os.getenv("REDIS_ENABLED", "false").lower() == "true"
    redis_host: str = os.getenv("REDIS_HOST") or "localhost"
    redis_port: int = int(os.getenv("REDIS_PORT") or 6379)
    redis_db: int = int(os.getenv("REDIS_DB") or 0)
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD") or None
    redis_max_memory: str = os.getenv("REDIS_MAX_MEMORY") or "256mb"
    
    # 文档元数据缓存TTL（秒）
    document_metadata_cache_ttl: int = int(os.getenv("DOCUMENT_METADATA_CACHE_TTL") or 3600)

    # 查询缓存配置
    query_cache_enabled: bool = os.getenv("QUERY_CACHE_ENABLED", "true").lower() == "true"
    query_cache_ttl: int = int(os.getenv("QUERY_CACHE_TTL") or 3600)  # 缓存有效期（秒）

    # LLM 调用韧性配置
    llm_retry_max_attempts: int = int(os.getenv("LLM_RETRY_MAX_ATTEMPTS") or 3)
    llm_retry_base_delay: float = float(os.getenv("LLM_RETRY_BASE_DELAY") or 1.0)
    llm_circuit_breaker_threshold: int = int(os.getenv("LLM_CIRCUIT_BREAKER_THRESHOLD") or 5)
    llm_circuit_breaker_timeout: float = float(os.getenv("LLM_CIRCUIT_BREAKER_TIMEOUT") or 60.0)

    # 批量导入配置
    batch_max_concurrent: int = int(os.getenv("BATCH_MAX_CONCURRENT") or 3)  # 最大并发文件数

    # 多模态并发处理配置（参照 RAG-Anything _process_multimodal_content_batch_type_aware）
    # multimodal_max_parallel: 同时调用 VLM/LLM 的最大并发数（避免 API 限速）
    multimodal_max_parallel: int = int(os.getenv("MULTIMODAL_MAX_PARALLEL") or 2)
    # kg_entity_max_parallel: 知识图谱实体提取的最大并发 chunk 数
    kg_entity_max_parallel: int = int(os.getenv("KG_ENTITY_MAX_PARALLEL") or 3)
    
    # 分页配置
    default_page_size: int = 20
    max_page_size: int = 100

    # 数据库配置（MySQL）
    database_url: str = "mysql+pymysql://root:root@127.0.0.1:3306/personal_knowledgebase"
    database_echo: bool = False
    
    # 短信服务配置（阿里云）
    sms_access_key_id: Optional[str] = None
    sms_access_key_secret: Optional[str] = None
    sms_sign_name: Optional[str] = None
    sms_template_code: Optional[str] = None
    sms_region: str = "cn-hangzhou"
    
    # 邮件服务配置（企业微信邮箱）
    smtp_host: Optional[str] = "smtp.exmail.qq.com"  # 企业微信邮箱SMTP服务器
    smtp_port: int = 465  # SSL端口
    smtp_username: Optional[str] = ""
    smtp_password: Optional[str] = ""
    smtp_use_tls: bool = False  # 465端口使用SSL，不使用TLS
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

settings = Settings()