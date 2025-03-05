"""
ai_analysis package

This package provides AI-based analysis of legislation using LLMs.
"""

import logging
import os
import sys

# Configure logging (combining with original's logging config)
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')  #Combined format for better readability.
logger = logging.getLogger(__name__)

# Export the main classes
try:
    from app.ai_analysis.analyzer import AIAnalysis
    from app.ai_analysis.errors import AIAnalysisError, APIError, RateLimitError, DatabaseError

    # Define what's available when importing from the package
    __all__ = ['AIAnalysis', 'AIAnalysisError', 'APIError', 'RateLimitError', 'DatabaseError']

except ImportError as e:
    logger.error(f"Error initializing ai_analysis package: {e}")
    raise