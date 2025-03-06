"""
Custom exceptions for AI analysis error handling.
"""


class AIAnalysisError(Exception):
    """Base exception class for AI analysis errors."""
    pass


class TokenLimitError(AIAnalysisError):
    """Raised when content exceeds token limits."""
    pass


class APIError(AIAnalysisError):
    """Raised when OpenAI API returns an error."""
    pass


class RateLimitError(APIError):
    """Raised when OpenAI rate limits are hit."""
    pass


class ContentProcessingError(AIAnalysisError):
    """Raised when content processing (splitting, merging) fails."""
    pass


class DatabaseError(AIAnalysisError):
    """Raised when database operations fail."""
    pass
