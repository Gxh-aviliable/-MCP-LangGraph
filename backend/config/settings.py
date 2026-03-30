"""项目配置管理"""
from pydantic_settings import BaseSettings
from typing import Optional, List
from pathlib import Path

# 获取项目根目录的 .env 文件路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """应用配置"""

    # API Keys
    deepseek_api_key: Optional[str] = None
    amap_maps_api_key: Optional[str] = None

    # 应用配置
    app_name: str = "Travel Planning Agent"
    debug: bool = False

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000

    # 会话配置
    session_expire_seconds: int = 3600  # 会话过期时间（秒）

    # CORS 配置（生产环境应通过环境变量设置）
    allowed_origins: Optional[List[str]] = None

    # 确认关键词（统一配置）
    confirm_keywords: List[str] = ['确认', '满意', '好的', '可以', '没问题', 'confirm']

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()