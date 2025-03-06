"""
AI Analysis module for generating structured legislative analysis.

This module provides tools to analyze legislation text using OpenAI's language models,
with a focus on public health and local government impacts in Texas.
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, List

# Import key components for external use - use absolute imports
from .analyzer import AIAnalysis
from .errors import AIAnalysisError, DatabaseError, APIError, RateLimitError
from .config import AIAnalysisConfig
from .utils import TokenCounter
from .models import LegislationAnalysisResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import database session if available
try:
    from app.models import init_db
    from sqlalchemy.orm import Session
except ImportError:
    logger.warning(
        "Could not import database components. Some features may be limited.")


"""
AI Analysis module initialization
"""

# Singleton instance - will be lazy-loaded
_ai_analysis_instance = None

def get_ai_analysis(db_session=None):
    """
    Get or create the AIAnalysis singleton instance.

    Args:
        db_session: Optional database session to use

    Returns:
        AIAnalysis instance
    """
    global _ai_analysis_instance

    if _ai_analysis_instance is None and db_session is not None:
        # Lazy import to avoid circular imports
        from .analyzer import AIAnalysis

        try:
            _ai_analysis_instance = AIAnalysis(
                db_session=db_session,
                openai_api_key=os.environ.get("OPENAI_API_KEY"),
                model_name=os.environ.get("OPENAI_MODEL", "gpt-4o-2024-08-06")
            )
            logger.info("Created AIAnalysis singleton")
        except Exception as e:
            logger.error(f"Failed to create AIAnalysis instance: {e}")
            raise

    return _ai_analysis_instance

def reset_ai_analysis():
    """Reset the AIAnalysis singleton instance."""
    global _ai_analysis_instance
    _ai_analysis_instance = None

# Convenience functions that use the singleton
def analyze_legislation(legislation_id: int):
    """
    Convenience function to analyze a legislation.

    Args:
        legislation_id: The ID of the legislation to analyze

    Returns:
        The analyzed LegislationAnalysis object
    """
    try:
        analyzer = get_ai_analysis()
        if not analyzer:
            raise AIAnalysisError(
                "AIAnalysis singleton not initialized. Create an instance first.")
        return analyzer.analyze_legislation(legislation_id)
    except Exception as e:
        logger.error(f"Error analyzing legislation: {e}")
        raise

def analyze_bill(bill_text: str,
                 bill_title: Optional[str] = None,
                 state: Optional[str] = None,
                 db_session=None) -> Dict[str, Any]:
    """
    Convenience function to analyze a bill.

    Args:
        bill_text (str): The text content of the bill
        bill_title (str, optional): The title of the bill
        state (str, optional): The state where the bill was introduced
        db_session (Session, optional): Database session to use

    Returns:
        dict: Analysis results
    """
    try:
        analyzer = get_ai_analysis(db_session)
        if not analyzer:
             raise AIAnalysisError("AIAnalysis singleton not initialized.  Provide a database session.")
        return analyzer.analyze_bill(bill_text, bill_title, state)

    except Exception as e:
        logger.error(f"Error analyzing bill: {e}")
        raise


# New async convenience functions
async def analyze_legislation_async(legislation_id: int):
    """
    Async convenience function to analyze a legislation.

    Args:
        legislation_id: The ID of the legislation to analyze

    Returns:
        The analyzed LegislationAnalysis object
    """
    try:
        analyzer = get_ai_analysis()
        if not analyzer:
            raise AIAnalysisError(
                "AIAnalysis singleton not initialized. Create an instance first.")
        return await analyzer.analyze_legislation_async(legislation_id)
    except Exception as e:
        logger.error(f"Error analyzing legislation asynchronously: {e}")
        raise


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
    try:
        analyzer = get_ai_analysis()
        if not analyzer:
            raise AIAnalysisError(
                "AIAnalysis singleton not initialized. Create an instance first.")
        return await analyzer.batch_analyze_async(legislation_ids, max_concurrent)
    except Exception as e:
        logger.error(f"Error batch analyzing asynchronously: {e}")
        raise


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
    try:
        analyzer = get_ai_analysis()
        if not analyzer:
            raise AIAnalysisError(
                "AIAnalysis singleton not initialized. Create an instance first.")
        return await analyzer.analyze_bill_async(bill_text, bill_title, state)
    except Exception as e:
        logger.error(f"Error analyzing bill asynchronously: {e}")
        raise


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
    'get_ai_analysis',
    'reset_ai_analysis'
]