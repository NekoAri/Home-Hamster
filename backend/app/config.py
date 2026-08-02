"""
HomeHamster 应用配置模块
使用 pydantic-settings 管理环境变量与配置项

注意：LLM 相关配置已迁移到数据库存储，通过前端设置界面管理。
此配置文件仅管理数据库连接和应用级配置。
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量或 .env 文件读取"""

    # ---- 数据库配置 ----
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "homehamster"
    DB_PASSWORD: str = "homehamster"
    DB_NAME: str = "homehamster"

    # ---- 应用配置 ----
    APP_NAME: str = "HomeHamster"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True

    # ---- CORS 配置 ----
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def database_dsn(self) -> str:
        """构建 asyncpg 直连 DSN"""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 全局配置单例
settings = Settings()
