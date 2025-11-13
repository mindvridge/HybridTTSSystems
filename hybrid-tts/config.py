"""
Configuration settings for Hybrid TTS Cost Optimizer
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Application
    APP_NAME: str = "Hybrid TTS Cost Optimizer"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # API Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Redis Cache
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_TTL_DAYS: int = 365

    # Cache Settings
    MAX_CACHE_CLIPS: int = 1000
    MEMORY_LIMIT_MB: int = 500
    CACHE_STORAGE_PATH: str = "./hybrid-tts/cache/storage"

    # Audio Settings
    AUDIO_FORMAT: str = "opus"  # opus, mp3, wav
    AUDIO_SAMPLE_RATE: int = 24000
    AUDIO_BITRATE: str = "64k"
    CROSSFADE_DURATION_MS: int = 30  # 10-50ms recommended

    # OpenAI LLM
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-2024-08-06"
    OPENAI_TEMPERATURE: float = 0.1

    # TTS Provider (google or polly)
    TTS_PROVIDER: str = "google"

    # Google Cloud TTS
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    GOOGLE_TTS_VOICE: str = "ko-KR-Neural2-A"
    GOOGLE_TTS_LANGUAGE: str = "ko-KR"

    # Amazon Polly
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "ap-northeast-2"
    POLLY_VOICE_ID: str = "Seoyeon"
    POLLY_ENGINE: str = "neural"

    # Matching Configuration
    EXACT_MATCH_TIMEOUT_MS: int = 5
    FUZZY_MATCH_TIMEOUT_MS: int = 50
    FUZZY_MATCH_THRESHOLD: int = 75  # 70-80% recommended
    SEMANTIC_MATCH_TIMEOUT_MS: int = 100
    SEMANTIC_MATCH_THRESHOLD: float = 0.85
    TTS_FALLBACK_TIMEOUT_MS: int = 500

    # Matching Weights
    WEIGHT_EXACT: float = 0.5
    WEIGHT_FUZZY: float = 0.3
    WEIGHT_SEMANTIC: float = 0.2

    # Semantic Search
    SENTENCE_TRANSFORMER_MODEL: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    VECTOR_DIM: int = 768

    # Templates
    TEMPLATE_FILE: str = "./hybrid-tts/templates/data/templates.yaml"

    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_LOG_PATH: str = "./hybrid-tts/logs/metrics.json"

    # Target Metrics
    TARGET_CACHE_HIT_RATE: float = 0.80  # 80%
    TARGET_COST_REDUCTION: float = 0.70  # 70%

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
