"""
AI Analysis module for generating structured legislative analysis.

This module provides tools to analyze legislation text using OpenAI's language models,
with a focus on public health and local government impacts in Texas.
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import key components for external use - use absolute imports
from .analyzer import AIAnalysis
from app.ai_analysis.errors import AIAnalysisError, DatabaseError, APIError, RateLimitError
from app.ai_analysis.config import AIAnalysisConfig
from app.ai_analysis.utils import TokenCounter
from app.ai_analysis.models import LegislationAnalysisResult

# Import database session if available
try:
    from app.models import init_db
    from sqlalchemy.orm import Session
except ImportError:
    logger.warning(
        "Could not import database components. Some features may be limited.")

# Initialize a global singleton instance if possible
try:
    from app.models import init_db
    SessionFactory = init_db()
    _session = SessionFactory()
    analyzer = AIAnalysis(db_session=_session, model_name="gpt-4o-2024-08-06")
    logger.info("Created AIAnalysis singleton")
except Exception as e:
    logger.warning(
        f"Failed to create AIAnalysis singleton: {e}. You'll need to create an instance manually."
    )
    analyzer = None  # Set to None if initialization fails


# Convenience functions that use the singleton
def analyze_legislation(legislation_id: int):
    """
    Convenience function to analyze a legislation.

    Args:
        legislation_id: The ID of the legislation to analyze

    Returns:
        The analyzed LegislationAnalysis object
    """
    if not analyzer:
        raise AIAnalysisError(
            "AIAnalysis singleton not initialized. Create an instance first.")
    return analyzer.analyze_legislation(legislation_id)


def analyze_bill(bill_text: str,
                 bill_title: Optional[str] = None,
                 state: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to analyze a bill.

    Args:
        bill_text (str): The text content of the bill
        bill_title (str, optional): The title of the bill
        state (str, optional): The state where the bill was introduced

    Returns:
        dict: Analysis results
    """
    if not analyzer:
        raise AIAnalysisError(
            "AIAnalysis singleton not initialized. Create an instance first.")
    return analyzer.analyze_bill(bill_text, bill_title, state)


# New async convenience functions
async def analyze_legislation_async(legislation_id: int):
    """
    Async convenience function to analyze a legislation.

    Args:
        legislation_id: The ID of the legislation to analyze

    Returns:
        The analyzed LegislationAnalysis object
    """
    if not analyzer:
        raise AIAnalysisError(
            "AIAnalysis singleton not initialized. Create an instance first.")
    return await analyzer.analyze_legislation_async(legislation_id)


async def batch_analyze_async(legislation_ids: List[int],
                              max_concurrent: int = 5) -> Dict[str, Any]:
    """
    Async convenience function to analyze multiple legislation records in parallel.

    Args:
        legislation_ids: List of legislation IDs to analyze
        max_concurrent: Maximum number of concurrent analyses

    Returns:
        Dictionary with analysis results and statistics
    """
    if not analyzer:
        raise AIAnalysisError(
            "AIAnalysis singleton not initialized. Create an instance first.")
    return await analyzer.batch_analyze_async(legislation_ids, max_concurrent)


async def analyze_bill_async(bill_text: str,
                             bill_title: Optional[str] = None,
                             state: Optional[str] = None) -> Dict[str, Any]:
    """
    Async convenience function to analyze a bill.

    Args:
        bill_text (str): The text content of the bill
        bill_title (str, optional): The title of the bill
        state (str, optional): The state where the bill was introduced

    Returns:
        dict: Analysis results
    """
    if not analyzer:
        raise AIAnalysisError(
            "AIAnalysis singleton not initialized. Create an instance first.")
    return await analyzer.analyze_bill_async(bill_text, bill_title, state)


__all__ = [
    'AIAnalysis',
    'AIAnalysisError',
    'DatabaseError',
    'APIError',
    'RateLimitError',
    'AIAnalysisConfig',
    'LegislationAnalysisResult',
    'TokenCounter',
    'analyze_legislation',
    'analyze_bill',
    'analyze_legislation_async',
    'batch_analyze_async',
    'analyze_bill_async',
]
