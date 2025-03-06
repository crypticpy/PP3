"""
Configuration settings for the AI Analysis module.
"""

import os
import logging
from pydantic import BaseModel, field_validator
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AIAnalysisConfig(BaseModel):
    """Configuration parameters for the AIAnalysis class."""
    openai_api_key: Optional[str] = None
    model_name: str = "gpt-4o-2024-08-06"
    max_context_tokens: int = 120_000
    safety_buffer: int = 20_000
    max_retries: int = 3
    retry_base_delay: float = 1.0
    cache_ttl_minutes: int = 30
    log_level: str = "INFO"

    @field_validator('max_context_tokens')
    @classmethod
    def validate_max_context_tokens(cls, v):
        if v < 1000:
            raise ValueError("max_context_tokens must be at least 1000")
        if v > 1_000_000:
            raise ValueError("max_context_tokens seems unreasonably high")
        return v

    @field_validator('safety_buffer')
    @classmethod
    def validate_safety_buffer(cls, v):
        if v < 0:
            raise ValueError("safety_buffer cannot be negative")
        return v

    @field_validator('max_retries')
    @classmethod
    def validate_max_retries(cls, v):
        if v < 0:
            raise ValueError("max_retries cannot be negative")
        if v > 10:
            raise ValueError("max_retries seems unreasonably high")
        return v

    @field_validator('retry_base_delay')
    @classmethod
    def validate_retry_base_delay(cls, v):
        if v <= 0:
            raise ValueError("retry_base_delay must be positive")
        if v > 10:
            raise ValueError("retry_base_delay seems unreasonably high")
        return v

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(
                f"log_level must be one of: {', '.join(valid_levels)}")
        return v

    @field_validator('openai_api_key')
    @classmethod
    def validate_api_key(cls, v, info):
        # This validator needs to check the environment variable if v is None
        if v is None and not os.environ.get("OPENAI_API_KEY"):
            raise ValueError(
                "OpenAI API key must be provided or set in OPENAI_API_KEY environment variable"
            )
        return v


# Set up logger level based on environment
def configure_logging(level_name="INFO"):
    """Configure logging level from string name."""
    level = getattr(logging, level_name)
    logger.setLevel(level)

    # Return logger for convenience
    return logger
