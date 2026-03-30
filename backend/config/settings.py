"""项目配置管理"""
from pydantic_settings import BaseSettings
from typing import Optional
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

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()