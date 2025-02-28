"""
Configuration module for the Atheon AI Orchestrator.

This module loads environment variables and provides configuration settings
for the application.
"""

import os
from typing import Dict, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    api_debug: bool = Field(default=False, env="API_DEBUG")

    # Database Configuration
    database_url: str = Field(..., env="DATABASE_URL")

    # Kafka Configuration
    kafka_bootstrap_servers: str = Field(..., env="KAFKA_BOOTSTRAP_SERVERS")
    kafka_topic_prefix: str = Field(default="atheon", env="KAFKA_TOPIC_PREFIX")

    # LLM API Keys
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    huggingface_api_key: Optional[str] = Field(default=None, env="HUGGINGFACE_API_KEY")

    # Authentication
    jwt_secret: str = Field(..., env="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expiration: int = Field(default=86400, env="JWT_EXPIRATION")  # 24 hours

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # LLM Model Configuration
    default_llm_provider: str = Field(default="anthropic", env="DEFAULT_LLM_PROVIDER")
    llm_providers: Dict[str, Dict[str, str]] = {
        "anthropic": {
            "model": "claude-3-7-sonnet-20240229",
            "description": "Code Generation & Reasoning",
        },
        "openai": {
            "model": "gpt-4",
            "description": "Summarization, General NLP tasks",
        },
        "whisper": {
            "model": "whisper-1",
            "description": "Speech-to-Text Transcription",
        },
        "huggingface": {
            "model": "meta-llama/Llama-2-70b-chat-hf",
            "description": "Cost-efficient open-source fallback",
        },
    }

    # HITL Configuration
    hitl_enabled: bool = Field(default=True, env="HITL_ENABLED")
    hitl_approval_timeout: int = Field(default=300, env="HITL_APPROVAL_TIMEOUT")  # 5 minutes

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


# Create a global settings instance
settings = Settings()