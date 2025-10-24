"""
Configuración del microservicio usando Pydantic Settings.
Lee variables de entorno o .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Settings del microservicio de scraping."""
    
    # API Configuration
    api_key: str = "development-key-change-in-production"
    environment: str = "development"  # development | production
    
    # Redis / RQ
    redis_url: str = "redis://localhost:6379"
    
    # SFTP API Configuration
    sftp_api_url: str = "https://sftp-api-production.up.railway.app"
    sftp_api_key: str = "xs0*Zff7V6BemA3>r<["
    sftp_base_path: str = "/scraping_data"
    
    # Scraping Configuration
    captcha_timeout_seconds: int = 300  # 5 minutos
    max_retries: int = 3
    job_timeout_minutes: int = 30
    
    # Paths
    data_dir: str = "data"
    
    # Docker Manager Configuration (Multi-Client Viewers)
    docker_manager_url: str = "http://localhost:8001"
    viewer_host: str = "localhost"  # Hostname/IP del servidor con viewers
    
    # Database
    database_path: str = "data/scraper.db"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Singleton
settings = Settings()

