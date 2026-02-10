from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Configuración de Base de Datos (MySQL XAMPP)
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # IA y APIs
    GEMINI_API_KEY : str

    # Configuración del Agente
    AGENT_POLLING_INTERVAL: int = 60
    MAX_TOKENS_PER_CHUNK: int = 3000  # Para controlar el tamaño de fragmentos de novela

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()