"""配置管理模块 - 负责安全地读取环境变量"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


class Config:
    """应用配置类"""

    # API Keys
    TAVILY_API_KEY: str
    ZHIPUAI_API_KEY: str

    # Streamlit 配置
    STREAMLIT_PORT: int = 8501
    STREAMLIT_SERVER_HEADLESS: bool = True
    STREAMLIT_SERVER_ADDRESS: str = "localhost"

    # API 配置
    API_TIMEOUT: int = 30
    MAX_RETRIES: int = 3

    # 搜索配置
    SEARCH_MAX_RESULTS: int = 10
    SEARCH_DAYS_LOOKBACK: int = 90  # 增加到 90 天，以获取更多历史消息

    # SOC 投资分析配置
    SEARCH_KEYWORDS: list = ["SOC", "PHMSA", "pipeline", "restart", "approval"]

    def __init__(self, env_file: Optional[Path] = None):
        """初始化配置

        Args:
            env_file: .env 文件路径，默认为项目根目录下的 .env
        """
        self._load_env(env_file or ENV_FILE)
        self._validate()

    def _load_env(self, env_file: Path) -> None:
        """加载环境变量

        Args:
            env_file: .env 文件路径
        """
        if env_file.exists():
            load_dotenv(env_file)
        # 云环境（如 Streamlit Cloud）直接从系统环境变量读取
        # 不强制要求 .env 文件存在

    def _validate(self) -> None:
        """验证必需的环境变量是否存在"""
        self.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
        self.ZHIPUAI_API_KEY = os.getenv("ZHIPUAI_API_KEY", "")

        if not self.TAVILY_API_KEY or self.TAVILY_API_KEY == "your_tavily_api_key_here":
            raise ValueError("TAVILY_API_KEY is not configured in .env file")

        if not self.ZHIPUAI_API_KEY or self.ZHIPUAI_API_KEY == "your_zhipuai_api_key_here":
            raise ValueError("ZHIPUAI_API_KEY is not configured in .env file")

        # 加载可选配置
        self.STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", self.STREAMLIT_PORT))
        self.STREAMLIT_SERVER_HEADLESS = os.getenv("STREAMLIT_SERVER_HEADLESS", "true").lower() == "true"
        self.STREAMLIT_SERVER_ADDRESS = os.getenv("STREAMLIT_SERVER_ADDRESS", self.STREAMLIT_SERVER_ADDRESS)
        self.API_TIMEOUT = int(os.getenv("API_TIMEOUT", self.API_TIMEOUT))
        self.MAX_RETRIES = int(os.getenv("MAX_RETRIES", self.MAX_RETRIES))
        self.SEARCH_MAX_RESULTS = int(os.getenv("SEARCH_MAX_RESULTS", self.SEARCH_MAX_RESULTS))
        self.SEARCH_DAYS_LOOKBACK = int(os.getenv("SEARCH_DAYS_LOOKBACK", self.SEARCH_DAYS_LOOKBACK))


# 全局配置实例
_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例

    Returns:
        Config: 配置实例
    """
    global _config
    if _config is None:
        _config = Config()
    return _config
