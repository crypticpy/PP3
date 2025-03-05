"""
Configuration settings for the AI Analysis module.
"""

import os
import logging
from pydantic import BaseModel, model_validator
from typing import Optional


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

    @model_validator(mode='after')
    def validate_configuration(self) -> 'AIAnalysisConfig':
        """Validate all configuration settings."""
        # Validate max_context_tokens
        if self.max_context_tokens < 1000:
            raise ValueError("max_context_tokens must be at least 1000")
        if self.max_context_tokens > 1_000_000:
            raise ValueError("max_context_tokens seems unreasonably high")

        # Validate safety_buffer
        if self.safety_buffer < 0:
            raise ValueError("safety_buffer cannot be negative")

        # Validate max_retries
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.max_retries > 10:
            raise ValueError("max_retries seems unreasonably high")

        # Validate retry_base_delay
        if self.retry_base_delay <= 0:
            raise ValueError("retry_base_delay must be positive")
        if self.retry_base_delay > 10:
            raise ValueError("retry_base_delay seems unreasonably high")

        # Validate log_level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_levels:
            raise ValueError(f"log_level must be one of: {', '.join(valid_levels)}")

        # Check API key
        if not self.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OpenAI API key must be provided or set in OPENAI_API_KEY environment variable")

        return self

# Set up logger level based on environment
def configure_logging(level_name="INFO"):
    """Configure logging level from string name."""
    level = getattr(logging, level_name)
    logger.setLevel(level)

    # Return logger for convenience
    return logger