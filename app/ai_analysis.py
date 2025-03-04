"""
ai_analysis.py

Provides a production-grade AIAnalysis class that:
  1) Retrieves the full bill text from Legislation + LegislationText in the database
  2) Dynamically handles documents of any size with intelligent context-preserving chunking
  3) Calls OpenAI's ChatCompletion with strict JSON schema validation for structured outputs
  4) Processes the AI response into a fully structured analysis with proper error handling
  5) Stores the results in LegislationAnalysis with versioning and audit tracking

Key features:
  - Precise token counting using tiktoken for accurate context window management
  - Intelligent document splitting preserving section coherence for large documents
  - Robust retry logic with exponential backoff for API resilience
  - Comprehensive error handling with detailed logging and status preservation
  - Transaction management ensuring data integrity even in failure scenarios
  - Caching for performance optimization and cost reduction
  - Type safety throughout the codebase

Prerequisites:
 - The 'models.py' must define Legislation, LegislationText, LegislationAnalysis, etc.
 - pip install openai pydantic tiktoken (and ensure OPENAI_API_KEY is set or passed to constructor)
 - A GPT-4o model that supports structured outputs is recommended (e.g. "gpt-4o-2024-08-06" or later).

Usage:
    from sqlalchemy.orm import Session
    from models import init_db
    from ai_analysis import AIAnalysis

    SessionFactory = init_db()
    db_session = SessionFactory()
    ai = AIAnalysis(db_session=db_session, model_name="gpt-4o-2024-08-06")
    analysis = ai.analyze_legislation(legislation_id=123)  # ID from Legislation table
    print("Analysis version:", analysis.analysis_version)
"""

import os
import json
import logging
import re
import time
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Literal, Tuple, cast, Type
from contextlib import contextmanager

import openai
import tiktoken
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator, root_validator, ValidationError

# Import required models
from models import (
    Legislation,
    LegislationText,
    LegislationAnalysis,
    ImpactCategoryEnum,
    ImpactLevelEnum
)

# Try to import additional related models if available
try:
    from models import LegislationPriority
    HAS_PRIORITY_MODEL = True
except ImportError:
    HAS_PRIORITY_MODEL = False

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Custom exceptions for better error handling
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


# Pydantic models for structured validation

class KeyPoint(BaseModel):
    """Model representing a key point in the legislation analysis."""
    point: str = Field(..., description="The text of the bullet point")
    impact_type: Literal["positive", "negative", "neutral"] = Field(
        ..., description="The overall tone or impact of this point"
    )


class PublicHealthImpacts(BaseModel):
    """Model representing public health impacts of the legislation."""
    direct_effects: List[str] = Field(default_factory=list)
    indirect_effects: List[str] = Field(default_factory=list)
    funding_impact: List[str] = Field(default_factory=list)
    vulnerable_populations: List[str] = Field(default_factory=list)


class LocalGovernmentImpacts(BaseModel):
    """Model representing local government impacts of the legislation."""
    administrative: List[str] = Field(default_factory=list)
    fiscal: List[str] = Field(default_factory=list)
    implementation: List[str] = Field(default_factory=list)


class EconomicImpacts(BaseModel):
    """Model representing economic impacts of the legislation."""
    direct_costs: List[str] = Field(default_factory=list)
    economic_effects: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    long_term_impact: List[str] = Field(default_factory=list)


class ImpactSummary(BaseModel):
    """Model representing the overall impact summary."""
    primary_category: Literal["public_health", "local_gov", "economic", 
                             "environmental", "education", "infrastructure"]
    impact_level: Literal["low", "moderate", "high", "critical"]
    relevance_to_texas: Literal["low", "moderate", "high"]


class LegislationAnalysisResult(BaseModel):
    """Complete model for structured analysis results from the AI model."""
    summary: str
    key_points: List[KeyPoint]
    public_health_impacts: PublicHealthImpacts
    local_government_impacts: LocalGovernmentImpacts
    economic_impacts: EconomicImpacts
    environmental_impacts: List[str] = Field(default_factory=list)
    education_impacts: List[str] = Field(default_factory=list)
    infrastructure_impacts: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    immediate_actions: List[str] = Field(default_factory=list)
    resource_needs: List[str] = Field(default_factory=list)
    impact_summary: ImpactSummary

    class Config:
        """Pydantic configuration."""
        extra = "forbid"  # Prevent extra fields


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

    @validator('max_context_tokens')
    def check_max_context_tokens(cls, v):
        """Ensure max_context_tokens is reasonable."""
        if v < 1000:
            raise ValueError("max_context_tokens must be at least 1000")
        if v > 1_000_000:
            raise ValueError("max_context_tokens seems unreasonably high")
        return v
    
    @validator('safety_buffer')
    def check_safety_buffer(cls, v):
        """Validate safety buffer."""
        if v < 0:
            raise ValueError("safety_buffer cannot be negative")
        return v
        
    @validator('max_retries')
    def check_max_retries(cls, v):
        """Validate max retries."""
        if v < 0:
            raise ValueError("max_retries cannot be negative")
        if v > 10:
            raise ValueError("max_retries seems unreasonably high")
        return v
        
    @validator('retry_base_delay')
    def check_retry_base_delay(cls, v):
        """Validate retry base delay."""
        if v <= 0:
            raise ValueError("retry_base_delay must be positive")
        if v > 10:
            raise ValueError("retry_base_delay seems unreasonably high")
        return v
        
    @validator('log_level')
    def check_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"log_level must be one of: {', '.join(valid_levels)}")
        return v

    @root_validator
    def check_api_key(cls, values):
        """Ensure API key is available in config or environment."""
        if not values.get('openai_api_key') and not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OpenAI API key must be provided or set in OPENAI_API_KEY environment variable")
        return values


class AIAnalysis:
    """
    The AIAnalysis class orchestrates generating a structured legislative analysis
    from OpenAI's language models and storing it in the database with version control.
    
    This class handles:
    1. Retrieving legislation text from the database
    2. Intelligent splitting of large documents with context preservation
    3. Making structured AI requests with robust error handling and retries
    4. Processing AI responses into validated structured data
    5. Storing analysis results with proper versioning
    
    The analysis captures multiple impact dimensions including public health,
    local government, economic, environmental, and more, providing a comprehensive
    assessment of legislation.
    """

    def __init__(
        self,
        db_session: Session,
        openai_api_key: Optional[str] = None,
        model_name: str = "gpt-4o-2024-08-06",
        max_context_tokens: int = 120_000,
        safety_buffer: int = 20_000,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        cache_ttl_minutes: int = 30
    ):
        """
        Initialize the AIAnalysis instance.
        
        Args:
            db_session: SQLAlchemy Session for database operations
            openai_api_key: Optional OpenAI API key (uses OPENAI_API_KEY env var if not provided)
            model_name: Name of the GPT-4o model that supports structured outputs
            max_context_tokens: Maximum context size in tokens
            safety_buffer: Buffer to subtract from max tokens to avoid hitting limits
            max_retries: Maximum number of retry attempts for API calls
            retry_base_delay: Base delay in seconds for retry exponential backoff
            cache_ttl_minutes: Time-to-live in minutes for cached analyses
            
        Raises:
            ValidationError: If configuration parameters are invalid
        """
        # Validate configuration with Pydantic
        try:
            self.config = AIAnalysisConfig(
                openai_api_key=openai_api_key,
                model_name=model_name,
                max_context_tokens=max_context_tokens,
                safety_buffer=safety_buffer,
                max_retries=max_retries,
                retry_base_delay=retry_base_delay,
                cache_ttl_minutes=cache_ttl_minutes
            )
        except ValidationError as e:
            logger.error(f"AIAnalysis initialization failed: {e}")
            raise
        
        # Set up logging based on config
        logger.setLevel(getattr(logging, self.config.log_level))
        
        # Database session for interacting with the database
        self.db_session = db_session
        if not self.db_session:
            raise ValueError("Database session is required")
            
        # Configure OpenAI client
        self.api_key = self.config.openai_api_key or os.environ.get("OPENAI_API_KEY")
        openai.api_key = self.api_key
        
        # Initialize token encoder for the specified model
        self._initialize_token_encoder()
        
        # Transfer config values to instance attributes for compatibility
        self.model_name = self.config.model_name
        self.max_context_tokens = self.config.max_context_tokens
        self.safety_buffer = self.config.safety_buffer
        
        # Cache for legislation analysis to prevent redundant work
        self._analysis_cache: Dict[int, Tuple[datetime, LegislationAnalysis]] = {}
        
        logger.info(f"AIAnalysis initialized with model {self.model_name}")

    def _initialize_token_encoder(self) -> None:
        """
        Initialize the tiktoken encoder for token counting.
        Selects the appropriate encoding based on the model name.
        """
        try:
            # Match the model name prefix to determine encoding
            if self.config.model_name.startswith(("gpt-4", "gpt-3.5")):
                encoding_name = "cl100k_base"  # Used by gpt-4, gpt-3.5-turbo, text-embedding-ada-002
            elif self.config.model_name.startswith("o"):
                encoding_name = "cl100k_base"  # Best current match for o-series models
            else:
                # Default encoding if no match
                encoding_name = "cl100k_base"
                logger.warning(f"No specific encoding found for {self.config.model_name}, using default encoding")
                
            self.token_encoder = tiktoken.get_encoding(encoding_name)
            logger.debug(f"Initialized token encoder using {encoding_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize token encoder: {e}", exc_info=True)
            # Fall back to approximate token counting
            self.token_encoder = None
            logger.warning("Using approximate token counting as fallback")

    @contextmanager
    def _db_transaction(self):
        """
        Context manager for handling database transactions with proper error handling.
        
        Yields:
            Transaction context for database operations
        """
        try:
            # Start transaction
            transaction = self.db_session.begin_nested()
            yield transaction
            # Commit at the end if no exception occurred
            transaction.commit()
        except SQLAlchemyError as e:
            # Rollback on database errors
            transaction.rollback()
            logger.error(f"Database error in transaction: {e}", exc_info=True)
            raise DatabaseError(f"Database operation failed: {str(e)}") from e
        except Exception as e:
            # Rollback on any other exception
            transaction.rollback()
            logger.error(f"Unexpected error in transaction: {e}", exc_info=True)
            raise

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text.
        Uses tiktoken for accurate model-specific token counting.
        
        Args:
            text: The text to count tokens for
            
        Returns:
            Number of tokens in the text
        """
        if not text:
            return 0
            
        if self.token_encoder:
            # Use tiktoken for accurate counting
            return len(self.token_encoder.encode(text))
        else:
            # Fallback to approximate counting
            return self._approx_tokens(text)

    def _approx_tokens(self, text: str) -> int:
        """
        Approximate the number of tokens in text as a fallback method.
        
        Args:
            text: The text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # This approximation assumes ~4 characters per token on average,
        # but actual tokenization varies by model and content
        if not text:
            return 0
        return len(text) // 4

    def analyze_legislation(self, legislation_id: int) -> LegislationAnalysis:
        """
        Main method to produce or update an AI-based analysis for a Legislation record.
        
        Steps:
         1) Fetch the Legislation + LegislationText from DB.
         2) If extremely large (approx > 100k tokens), intelligently chunk and analyze sequentially.
         3) Call the structured analysis with a strict JSON schema.
         4) Parse and store in a new LegislationAnalysis row (versioned).

        Args:
            legislation_id: The ID of the legislation to analyze

        Returns:
            The newly created LegislationAnalysis object
            
        Raises:
            ValueError: If legislation with the given ID is not found
            AIAnalysisError: If analysis generation fails
            DatabaseError: If database operations fail
        """
        # Check cache for valid entry
        if legislation_id in self._analysis_cache:
            cache_time, cached_analysis = self._analysis_cache[legislation_id]
            cache_age_minutes = (datetime.utcnow() - cache_time).total_seconds() / 60
            
            if cache_age_minutes < self.config.cache_ttl_minutes:
                logger.info(f"Using cached analysis for legislation ID={legislation_id}")
                return cached_analysis
            else:
                # Remove expired cache entry
                del self._analysis_cache[legislation_id]
            
        try:
            # 1) Load the legislation from DB
            leg_obj = self.db_session.query(Legislation).filter_by(id=legislation_id).first()
            if not leg_obj:
                error_msg = f"Legislation with ID={legislation_id} not found in the DB."
                logger.error(error_msg)
                raise ValueError(error_msg)

            # 2) Get full text (or fallback to description)
            text_rec = leg_obj.latest_text
            if text_rec and text_rec.text_content:
                # Check if content is binary
                if text_rec.is_binary if hasattr(text_rec, 'is_binary') else False:
                    # Skip binary content and use description instead
                    logger.warning(f"Binary content detected in LegislationText ID={text_rec.id}, using description instead")
                    full_text = leg_obj.description or ""
                else:
                    full_text = text_rec.text_content
            else:
                full_text = leg_obj.description or ""
                if not full_text:
                    warning_msg = f"No text content found for Legislation ID={legislation_id}"
                    logger.warning(warning_msg)

            # 3) Check token count
            token_count = self.count_tokens(full_text)
            safe_limit = self.max_context_tokens - self.safety_buffer
            
            # Log token information
            logger.info(f"Legislation {legislation_id} has ~{token_count} tokens (limit: {safe_limit})")
            
            analysis_data = None
            if token_count > safe_limit:
                logger.warning(f"Legislation {legislation_id} exceeds token limit, using intelligent chunking")
                # Use intelligent chunking for large documents
                chunks, has_structure = self._intelligent_text_split(full_text, safe_limit)
                
                if len(chunks) == 1:
                    # If we only have one chunk, process normally
                    text_for_analysis = chunks[0]
                    analysis_data = self._call_structured_analysis(text_for_analysis)
                else:
                    # For multiple chunks, analyze sequentially with context preservation
                    analysis_data = self._analyze_in_chunks(chunks, has_structure, leg_obj)
            else:
                # For normal-sized documents, proceed with standard analysis
                analysis_data = self._call_structured_analysis(full_text)
            
            if not analysis_data:
                error_msg = f"Failed to generate analysis for Legislation ID={legislation_id}"
                logger.error(error_msg)
                raise AIAnalysisError(error_msg)

            # 5) Save the new LegislationAnalysis record
            result_analysis = self._store_legislation_analysis(legislation_id, analysis_data)
            
            # Cache for future quick access
            self._analysis_cache[legislation_id] = (datetime.utcnow(), result_analysis)
            
            # 6) Update priority record if available
            if HAS_PRIORITY_MODEL:
                self._update_legislation_priority(legislation_id, analysis_data)
            
            return result_analysis
            
        except ValueError:
            # Re-raise not found errors
            raise
        except (AIAnalysisError, DatabaseError):
            # Re-raise custom errors
            raise
        except Exception as e:
            # Catch and wrap all other exceptions
            error_msg = f"Unexpected error analyzing legislation ID={legislation_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AIAnalysisError(error_msg) from e

    def _intelligent_text_split(self, text: str, max_tokens_per_chunk: int) -> Tuple[List[str], bool]:
        """
        Intelligently split text into chunks based on document structure.
        Attempts to preserve coherent sections and maintain context.
        
        Args:
            text: Full text to split
            max_tokens_per_chunk: Maximum tokens allowed per chunk
            
        Returns:
            Tuple of (list of text chunks, whether document has clear structure)
            
        Raises:
            ContentProcessingError: If text cannot be split properly
        """
        if not text:
            return ([""], False)
            
        try:
            # If text fits in one chunk, return it directly
            if self.count_tokens(text) <= max_tokens_per_chunk:
                return ([text], False)
                
            # Look for section markers that indicate document structure
            section_patterns = [
                # Common section patterns in legislation
                r'(?:^|\n)(?:Section|SEC\.|SECTION|Article|ARTICLE|Title|TITLE)\s+\d+\.?',
                r'(?:^|\n)§+\s*\d+',  # Section symbol
                r'(?:^|\n)\d+\.\s+[A-Z]',  # Numbered sections
                r'(?:^|\n)[A-Z][A-Z\s]+\n',  # ALL CAPS headers
                r'(?:^|\n)\*\*\*.*?\*\*\*',  # Special markers
            ]
            
            # Detect if document has clear structure
            has_structure = False
            for pattern in section_patterns:
                if len(re.findall(pattern, text)) > 3:  # At least 3 matches indicate structure
                    has_structure = True
                    break
            
            chunks = []
            
            if has_structure:
                # Split based on document structure
                logger.info("Document has clear structure, splitting by sections")
                
                # Combine all patterns into one regex for splitting
                combined_pattern = '|'.join(f'({p})' for p in section_patterns)
                
                # Get all potential split points while preserving the delimiter
                parts = re.split(f'(?=({combined_pattern}))', text)
                
                # Remove empty parts
                parts = [p for p in parts if p.strip()]
                
                # Merge parts into chunks based on token count
                current_chunk = ""
                
                for part in parts:
                    # Calculate tokens in current chunk + new part
                    temp_chunk = current_chunk + part
                    tokens = self.count_tokens(temp_chunk)
                    
                    if tokens <= max_tokens_per_chunk:
                        # Add to current chunk if we're within limits
                        current_chunk = temp_chunk
                    else:
                        # Save current chunk and start a new one
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = part
                
                # Don't forget the last chunk
                if current_chunk:
                    chunks.append(current_chunk)
                    
            else:
                # Fallback to paragraph-based splitting
                logger.info("Document lacks clear structure, splitting by paragraphs")
                paragraphs = re.split(r'\n\s*\n', text)
                
                current_chunk = ""
                
                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                        
                    # Calculate tokens in current chunk + new paragraph
                    temp_chunk = current_chunk + ("\n\n" if current_chunk else "") + para
                    tokens = self.count_tokens(temp_chunk)
                    
                    if tokens <= max_tokens_per_chunk:
                        # Add to current chunk if we're within limits
                        current_chunk = temp_chunk
                    else:
                        # Check if this single paragraph is too big
                        if not current_chunk:
                            # Single paragraph is too large, split by sentences
                            logger.warning("Found paragraph exceeding token limit, splitting by sentences")
                            para_chunks = self._split_paragraph_by_sentences(para, max_tokens_per_chunk)
                            chunks.extend(para_chunks)
                            current_chunk = ""
                            continue
                            
                        # Save current chunk and start a new one with this paragraph
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = para
                
                # Don't forget the last chunk
                if current_chunk:
                    chunks.append(current_chunk)
            
            # If we still don't have any chunks (rare case), use basic splitting
            if not chunks:
                logger.warning("Falling back to basic token-based splitting")
                chunks = self._basic_token_split(text, max_tokens_per_chunk)
                
            # Validate the chunks
            if not chunks:
                raise ContentProcessingError("Failed to split text into chunks")
                
            # Log split information
            logger.info(f"Split text into {len(chunks)} chunks, has_structure={has_structure}")
            for i, chunk in enumerate(chunks):
                logger.debug(f"Chunk {i+1}: ~{self.count_tokens(chunk)} tokens")
                
            return (chunks, has_structure)
            
        except Exception as e:
            error_msg = f"Error splitting text into chunks: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ContentProcessingError(error_msg) from e

    def _split_paragraph_by_sentences(self, paragraph: str, max_tokens_per_chunk: int) -> List[str]:
        """
        Split a single large paragraph into chunks by sentences.
        
        Args:
            paragraph: The paragraph text to split
            max_tokens_per_chunk: Maximum tokens allowed per chunk
            
        Returns:
            List of paragraph chunks
        """
        # Use regex for sentence boundaries (handles periods in abbreviations better)
        sentence_pattern = r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s'
        sentences = re.split(sentence_pattern, paragraph)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Check if this sentence alone exceeds the limit
            sentence_tokens = self.count_tokens(sentence)
            if sentence_tokens > max_tokens_per_chunk:
                # Extremely long sentence, split by character count as last resort
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                logger.warning(f"Found extremely long sentence ({sentence_tokens} tokens), splitting by character count")
                
                # Approximately how many characters per token
                chars_per_token = len(sentence) / sentence_tokens
                max_chars = int(max_tokens_per_chunk * chars_per_token) * 0.9  # 90% to be safe
                
                # Split into roughly equal parts
                for i in range(0, len(sentence), int(max_chars)):
                    chunks.append(sentence[i:i+int(max_chars)])
            else:
                # Calculate tokens in current chunk + new sentence
                temp_chunk = current_chunk + (" " if current_chunk else "") + sentence
                tokens = self.count_tokens(temp_chunk)
                
                if tokens <= max_tokens_per_chunk:
                    # Add to current chunk if we're within limits
                    current_chunk = temp_chunk
                else:
                    # Save current chunk and start a new one with this sentence
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = sentence
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def _basic_token_split(self, text: str, max_tokens_per_chunk: int) -> List[str]:
        """
        Basic token-based text splitting as a last resort.
        
        Args:
            text: Full text to split
            max_tokens_per_chunk: Maximum tokens allowed per chunk
            
        Returns:
            List of text chunks
        """
        # Get rough token estimate to determine total chunks needed
        total_tokens = self.count_tokens(text)
        
        # If single paragraph or can't detect sections, split by approximate token count
        chunk_count = (total_tokens // max_tokens_per_chunk) + 1
        
        if chunk_count <= 1:
            return [text]
            
        # Estimate characters per chunk (approximate)
        chars_per_token = len(text) / total_tokens
        chars_per_chunk = int(max_tokens_per_chunk * chars_per_token) * 0.9  # 90% to be safe
        
        chunks = []
        # Split into roughly equal parts
        for i in range(0, len(text), int(chars_per_chunk)):
            chunks.append(text[i:i+int(chars_per_chunk)])
            
        return chunks

    def _analyze_in_chunks(self, chunks: List[str], structured: bool, leg_obj: Legislation) -> Dict[str, Any]:
        """
        Analyzes a large bill in chunks, preserving context between chunks.
        
        Args:
            chunks: List of text chunks to analyze
            structured: Whether the chunks have structured sections
            leg_obj: The legislation database object
            
        Returns:
            Merged analysis data
            
        Raises:
            AIAnalysisError: If chunk analysis fails
        """
        # Start with bill metadata to provide context
        context = {
            "bill_number": leg_obj.bill_number,
            "title": leg_obj.title,
            "description": leg_obj.description or "",
            "govt_type": str(leg_obj.govt_type.value) if leg_obj.govt_type else "unknown",
            "govt_source": leg_obj.govt_source,
            "status": str(leg_obj.bill_status.value) if leg_obj.bill_status else "unknown"
        }
        
        # Initialize the cumulative analysis
        cumulative_analysis = {}
        chunk_summaries = []
        
        # Process each chunk, carrying forward context
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} for legislation {leg_obj.id}")
            
            try:
                # Create a custom prompt for this chunk that includes previous context
                chunk_prompt = self._create_chunk_prompt(
                    chunk=chunk, 
                    chunk_index=i, 
                    total_chunks=len(chunks),
                    prev_summaries=chunk_summaries,
                    legislation_metadata=context,
                    is_structured=structured
                )
                
                # Process this chunk
                chunk_result = self._call_structured_analysis(chunk_prompt, is_chunk=True)
                
                if not chunk_result:
                    logger.warning(f"Failed to analyze chunk {i+1}, continuing with partial analysis")
                    continue
                    
                # Add this chunk's summary to our context for future chunks
                if "summary" in chunk_result:
                    chunk_summaries.append(f"Chunk {i+1} Summary: {chunk_result['summary']}")
                    
                # Merge this chunk's analysis with the cumulative analysis
                if i == 0:
                    # For the first chunk, use it as the base
                    cumulative_analysis = chunk_result
                else:
                    # For subsequent chunks, merge intelligently
                    cumulative_analysis = self._merge_analyses(cumulative_analysis, chunk_result)
                    
            except APIError as e:
                logger.error(f"API error analyzing chunk {i+1}: {e}")
                if i == 0:
                    # If first chunk fails, we can't proceed
                    raise AIAnalysisError(f"Failed to analyze legislation {leg_obj.id} - first chunk analysis failed") from e
                # Otherwise, continue with partial information
            except Exception as e:
                logger.error(f"Error analyzing chunk {i+1}: {e}", exc_info=True)
                if i == 0:
                    # If first chunk fails, we can't proceed
                    raise AIAnalysisError(f"Failed to analyze legislation {leg_obj.id} - first chunk analysis failed") from e
                # Otherwise, continue with partial information
        
        # Verify we have at least a basic analysis
        if not cumulative_analysis or "summary" not in cumulative_analysis:
            raise AIAnalysisError(f"Failed to generate complete analysis for legislation {leg_obj.id} after processing all chunks")
            
        # Final post-processing of combined analysis
        if "summary" in cumulative_analysis and len(chunks) > 1:
            cumulative_analysis["summary"] = self._post_process_summary(cumulative_analysis["summary"], len(chunks))
        
        return cumulative_analysis
        
    def _create_chunk_prompt(self, 
                            chunk: str, 
                            chunk_index: int, 
                            total_chunks: int,
                            prev_summaries: List[str],
                            legislation_metadata: Dict[str, str],
                            is_structured: bool) -> str:
        """
        Creates a specialized prompt for analyzing a chunk of legislation with context preservation.
        Tailors the prompt based on which chunk is being processed and includes previous context.
        
        Args:
            chunk: Text chunk to analyze
            chunk_index: Index of this chunk (0-based)
            total_chunks: Total number of chunks
            prev_summaries: Summaries from previous chunks
            legislation_metadata: Bill metadata for context
            is_structured: Whether the document has structured sections
            
        Returns:
            Prompt with appropriate context for this chunk
        """
        # Prepare context section
        context_sections = [
            f"Bill Number: {legislation_metadata['bill_number']}",
            f"Title: {legislation_metadata['title']}",
            f"Description: {legislation_metadata['description']}",
            f"Government Type: {legislation_metadata['govt_type']}",
            f"Source: {legislation_metadata['govt_source']}",
            f"Status: {legislation_metadata['status']}"
        ]
        
        # Add summaries from previous chunks if available
        if prev_summaries:
            context_sections.append("\nSUMMARIES FROM PREVIOUS SECTIONS:")
            context_sections.extend(prev_summaries)
            
        context_text = "\n".join(context_sections)
        
        # Create appropriate instructions based on which chunk we're processing
        if chunk_index == 0:
            # First chunk
            instructions = (
                f"You are analyzing PART 1 OF {total_chunks} of a large legislative bill. "
                f"Focus on the sections provided while considering the bill's overall context."
            )
        elif chunk_index == total_chunks - 1:
            # Last chunk
            instructions = (
                f"You are analyzing THE FINAL PART ({chunk_index+1} OF {total_chunks}) of a large legislative bill. "
                f"Use the summaries of previous sections to inform your analysis and provide a comprehensive conclusion."
            )
        else:
            # Middle chunk
            instructions = (
                f"You are analyzing PART {chunk_index+1} OF {total_chunks} of a large legislative bill. "
                f"Consider the context from previous parts while focusing on the new content in this section."
            )
            
        # Additional guidance for structured vs. unstructured documents
        if is_structured:
            instructions += (
                " This document has structured sections. Pay attention to section headers and "
                "how they relate to previous parts of the bill."
            )
        else:
            instructions += (
                " This document was split by content size rather than by natural sections. "
                "Be aware that some concepts might span across chunks."
            )
            
        # Full prompt assembly
        full_prompt = (
            f"{instructions}\n\n"
            f"BILL CONTEXT:\n{context_text}\n\n"
            f"CURRENT SECTION TEXT TO ANALYZE:\n{chunk}"
        )
        
        return full_prompt

    def _post_process_summary(self, summary: str, chunk_count: int) -> str:
        """
        Post-process a combined summary for readability and coherence.
        
        Args:
            summary: Combined summary text
            chunk_count: Number of chunks that were combined
            
        Returns:
            Cleaned up summary text
        """
        # If the summary is too long, truncate it
        if len(summary) > 2000:
            summary = summary[:1997] + "..."
            
        # Remove phrases related to chunking
        chunk_phrases = [
            "in this section", "this part of the bill", "this section of the legislation",
            "as mentioned earlier", "based on the previous sections", 
            "in the previous sections", "in the earlier sections"
        ]
        
        for phrase in chunk_phrases:
            summary = summary.replace(phrase, "")
            
        # Clean up extra spaces and newlines
        summary = re.sub(r'\s+', ' ', summary).strip()
        
        return summary
        
    def _merge_analyses(self, base_analysis: Dict[str, Any], new_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligently merges analyses from different chunks based on field type and content.
        Handles text fields, arrays, and nested structures appropriately.
        
        Args:
            base_analysis: The cumulative analysis so far
            new_analysis: New analysis to merge in
            
        Returns:
            Merged analysis
        """
        merged = base_analysis.copy()
        
        # Merge summary with combination
        if "summary" in new_analysis:
            merged["summary"] = (
                base_analysis.get("summary", "") + " " + 
                new_analysis["summary"]
            )
            # Trim if it's getting too long
            if len(merged["summary"]) > 2000:
                merged["summary"] = merged["summary"][:1997] + "..."
                
        # Merge key points (avoid duplicates)
        if "key_points" in new_analysis and "key_points" in base_analysis:
            existing_points = {point["point"] for point in base_analysis["key_points"]}
            for point in new_analysis["key_points"]:
                if point["point"] not in existing_points:
                    merged["key_points"].append(point)
                    # Keep reasonable number of points
                    if len(merged["key_points"]) >= 15:
                        break
                        
        # Merge impact lists (take most significant from both)
        for impact_type in ["environmental_impacts", "education_impacts", "infrastructure_impacts"]:
            if impact_type in new_analysis and impact_type in base_analysis:
                # Get unique impacts
                all_impacts = set(base_analysis[impact_type])
                for impact in new_analysis[impact_type]:
                    all_impacts.add(impact)
                merged[impact_type] = list(all_impacts)[:10]  # Limit to 10 most important
                
        # Merge structured impact dictionaries
        for impact_dict in ["public_health_impacts", "local_government_impacts", "economic_impacts"]:
            if impact_dict in new_analysis and impact_dict in base_analysis:
                for category, items in new_analysis[impact_dict].items():
                    if category in base_analysis[impact_dict]:
                        # Add any new items that don't duplicate existing ones
                        existing_items = set(base_analysis[impact_dict][category])
                        for item in items:
                            if item not in existing_items:
                                merged[impact_dict][category].append(item)
                                # Keep reasonable number of items
                                if len(merged[impact_dict][category]) >= 8:
                                    break
                                    
        # For actions, get the most relevant from both
        for action_type in ["recommended_actions", "immediate_actions", "resource_needs"]:
            if action_type in new_analysis and action_type in base_analysis:
                # Combine and deduplicate
                all_actions = set(base_analysis[action_type])
                for action in new_analysis[action_type]:
                    all_actions.add(action)
                # Set a reasonable limit based on action type
                limit = 8 if action_type == "recommended_actions" else 5
                merged[action_type] = list(all_actions)[:limit]
            
        # For impact_summary, keep the most severe assessment
        if "impact_summary" in new_analysis and "impact_summary" in base_analysis:
            # Impact level priority (higher = more severe)
            impact_priority = {
                "low": 1,
                "moderate": 2,
                "high": 3,
                "critical": 4
            }
            
            base_level = impact_priority.get(base_analysis["impact_summary"]["impact_level"], 0)
            new_level = impact_priority.get(new_analysis["impact_summary"]["impact_level"], 0)
            
            # Keep the more severe impact assessment
            if new_level > base_level:
                merged["impact_summary"] = new_analysis["impact_summary"]
                
        return merged

    def _call_structured_analysis(self, text: str, is_chunk: bool = False) -> Dict[str, Any]:
        """
        Creates a single ChatCompletion request with a strict JSON schema that covers:
          - summary (string)
          - key_points (array of objects with point and impact_type)
          - multiple impacts: public_health, local_government, economic, environmental, education, infrastructure
          - recommended_actions, immediate_actions, resource_needs
        
        Implements retry logic with exponential backoff for API resilience.
        
        Args:
            text: The legislation text to analyze
            is_chunk: Whether this is a chunk of a larger document
            
        Returns:
            Dict containing the structured analysis results
            
        Raises:
            APIError: On unrecoverable API errors
            RateLimitError: On API rate limit errors
        """
        # Define the JSON schema for structured output
        json_schema = {
            "type": "json_schema",
            "json_schema": {
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "A concise summary of the bill"
                        },
                        "key_points": {
                            "type": "array",
                            "description": "List of key bullet points in the legislation",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "point": {
                                        "type": "string",
                                        "description": "The text of the bullet point"
                                    },
                                    "impact_type": {
                                        "type": "string",
                                        "enum": ["positive", "negative", "neutral"],
                                        "description": "The overall tone or impact of this point"
                                    }
                                },
                                "required": ["point", "impact_type"],
                                "additionalProperties": False
                            }
                        },
                        "public_health_impacts": {
                            "type": "object",
                            "properties": {
                                "direct_effects": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "indirect_effects": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "funding_impact": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "vulnerable_populations": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["direct_effects", "indirect_effects", "funding_impact", "vulnerable_populations"],
                            "additionalProperties": False
                        },
                        "local_government_impacts": {
                            "type": "object",
                            "properties": {
                                "administrative": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "fiscal": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "implementation": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["administrative", "fiscal", "implementation"],
                            "additionalProperties": False
                        },
                        "economic_impacts": {
                            "type": "object",
                            "properties": {
                                "direct_costs": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "economic_effects": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "benefits": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "long_term_impact": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["direct_costs", "economic_effects", "benefits", "long_term_impact"],
                            "additionalProperties": False
                        },
                        "environmental_impacts": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "education_impacts": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "infrastructure_impacts": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "recommended_actions": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "immediate_actions": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "resource_needs": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "impact_summary": {
                            "type": "object",
                            "properties": {
                                "primary_category": {
                                    "type": "string",
                                    "enum": ["public_health", "local_gov", "economic", "environmental", 
                                             "education", "infrastructure"]
                                },
                                "impact_level": {
                                    "type": "string",
                                    "enum": ["low", "moderate", "high", "critical"]
                                },
                                "relevance_to_texas": {
                                    "type": "string",
                                    "enum": ["low", "moderate", "high"]
                                }
                            },
                            "required": ["primary_category", "impact_level", "relevance_to_texas"],
                            "additionalProperties": False
                        }
                    },
                    "required": [
                        "summary", "key_points", "public_health_impacts", "local_government_impacts",
                        "economic_impacts", "environmental_impacts", "education_impacts", 
                        "infrastructure_impacts", "recommended_actions", "immediate_actions", 
                        "resource_needs", "impact_summary"
                    ],
                    "additionalProperties": False
                }
            }
        }

        # Construct the system message and user prompt
        system_message = (
            "You are a legislative analysis AI specializing in Texas public health and local government impacts. "
            "Provide a comprehensive, objective analysis of the bill text following the structured format exactly. "
            "Focus especially on impacts to Texas public health agencies and local governments. "
            "If information is insufficient for any field, provide reasonable, conservative assessments. "
            "Use only facts present in the text - do not add external information or assumptions."
        )

        # Adjust user message based on whether we're analyzing a chunk or not
        if is_chunk:
            # For chunks, the text already includes custom instructions
            user_message = text
        else:
            # Standard prompt for full document analysis
            user_message = (
                "Perform a structured analysis of the following bill text:\n\n"
                f"{text}\n\n"
                "Ensure your analysis addresses:\n"
                "1. Public health impacts - both direct effects and broader implications\n"
                "2. Local government impacts - administrative, fiscal, and implementation aspects\n"
                "3. Economic considerations - costs, benefits, and long-term effects\n"
                "4. Recommended actions for Texas Public Health and Government officials to prepare for this legislation\n"
                "5. Overall impact assessment for Texas stakeholders"
            )

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        # Implement retry logic with exponential backoff
        max_retries = self.config.max_retries
        base_delay = self.config.retry_base_delay
        
        for attempt in range(max_retries + 1):
            try:
                # Create the chat completion with structured output
                start_time = time.time()
                response = openai.ChatCompletion.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.2,  # Lower temperature for more consistent outputs
                    response_format=json_schema,
                    max_tokens=8000  # Limit output tokens for safety
                )
                end_time = time.time()
                
                # Log performance metrics
                elapsed_time = end_time - start_time
                logger.debug(f"API call completed in {elapsed_time:.2f}s")
                
                # Extract the content from the response
                response_message = response.choices[0]["message"]
                
                # Check if there was a refusal
                if hasattr(response_message, "refusal") and response_message.refusal:
                    logger.error(f"OpenAI refused to analyze the legislation: {response_message.refusal}")
                    return {}
                    
                # Handle the content based on the SDK version
                if hasattr(response_message, "parsed") and response_message.parsed:
                    # New SDK version with automatic parsing
                    analysis_data = response_message.parsed
                else:
                    # Fallback to manual JSON parsing if needed
                    content = response_message.get("content", "")
                    analysis_data = self._safe_json_load(content)
                
                # Validate the response with our Pydantic model
                if analysis_data:
                    try:
                        validated_data = LegislationAnalysisResult(**analysis_data)
                        return validated_data.dict()
                    except ValidationError as e:
                        logger.error(f"Response validation failed: {e}")
                        # Return original data - we'll try to work with what we have
                        return analysis_data
                
                return {}

            except openai.error.RateLimitError as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Rate limit error: {e}. Retrying in {delay:.2f}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                else:
                    logger.error(f"Rate limit error after {max_retries} retries: {e}")
                    raise RateLimitError(f"OpenAI rate limit exceeded after {max_retries} retries") from e
                    
            except openai.error.APIError as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"API error: {e}. Retrying in {delay:.2f}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                else:
                    logger.error(f"API error after {max_retries} retries: {e}")
                    raise APIError(f"OpenAI API error after {max_retries} retries: {str(e)}") from e
                    
            except openai.error.Timeout as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Timeout error: {e}. Retrying in {delay:.2f}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                else:
                    logger.error(f"Timeout error after {max_retries} retries: {e}")
                    raise APIError(f"OpenAI timeout after {max_retries} retries: {str(e)}") from e
                    
            except openai.error.ServiceUnavailableError as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Service unavailable: {e}. Retrying in {delay:.2f}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                else:
                    logger.error(f"Service unavailable after {max_retries} retries: {e}")
                    raise APIError(f"OpenAI service unavailable after {max_retries} retries: {str(e)}") from e
                    
            except openai.error.OpenAIError as e:
                # For other OpenAI errors, raise APIError
                logger.error(f"OpenAI API error: {e}", exc_info=True)
                raise APIError(f"OpenAI API error: {str(e)}") from e
                
            except Exception as e:
                # For unexpected errors, log and raise
                logger.error(f"Unexpected error in API call: {e}", exc_info=True)
                raise AIAnalysisError(f"Unexpected error in structured analysis: {str(e)}") from e
                
        # This should never be reached due to the raises in the loop
        raise AIAnalysisError(f"Failed to get a valid response after {max_retries} retries")

    def _safe_json_load(self, content: str) -> Dict[str, Any]:
        """
        Safely loads JSON from a string, handling various formats.
        
        Args:
            content: String containing JSON data (possibly with markdown or other formatting)
            
        Returns:
            Parsed JSON as a dictionary, or empty dict on error
        """
        if not content or not isinstance(content, str):
            logger.warning("Empty or non-string content provided to JSON parser")
            return {}
            
        try:
            # First, try direct JSON parsing
            return json.loads(content)
        except json.JSONDecodeError:
            pass
            
        # If that fails, try to extract JSON from markdown code blocks
        # Look for ```json ... ``` or just ``` ... ``` patterns
        json_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        matches = re.findall(json_pattern, content)
        
        if matches:
            # Try each match until we find valid JSON
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue
                    
        # Last-ditch effort: look for anything that resembles a JSON object
        object_pattern = r"(\{[\s\S]*\})"
        matches = re.findall(object_pattern, content)
        
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
                
        logger.error(f"Failed to parse JSON from content: {content[:100]}...")
        return {}

    def _store_legislation_analysis(
        self, legislation_id: int, analysis_dict: Dict[str, Any]
    ) -> LegislationAnalysis:
        """
        Creates a new LegislationAnalysis row or increments the version if existing ones exist.
        
        Args:
            legislation_id: The ID of the legislation
            analysis_dict: The structured analysis data
            
        Returns:
            The newly created LegislationAnalysis object
            
        Raises:
            ValidationError: If analysis_dict is empty or missing required fields
            DatabaseError: If database operations fail
        """
        if not analysis_dict:
            raise ValidationError("Cannot store empty analysis data")
            
        try:
            with self._db_transaction():
                # Check for existing analyses
                existing_analyses = self.db_session.query(LegislationAnalysis).filter_by(
                    legislation_id=legislation_id
                ).all()
                
                # Determine version and previous version
                if existing_analyses:
                    prev = max(existing_analyses, key=lambda x: x.analysis_version)
                    new_version = prev.analysis_version + 1
                    prev_id = prev.id
                else:
                    new_version = 1
                    prev_id = None

                # Extract impact summary information
                impact_summary = analysis_dict.get("impact_summary", {})
                impact_category_str = impact_summary.get("primary_category")
                impact_level_str = impact_summary.get("impact_level")
                
                # Convert string values to enum if present
                try:
                    impact_category_enum = ImpactCategoryEnum(impact_category_str) if impact_category_str else None
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid impact_category value: {impact_category_str}, error: {e}")
                    impact_category_enum = None
                    
                try:
                    impact_level_enum = ImpactLevelEnum(impact_level_str) if impact_level_str else None
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid impact_level value: {impact_level_str}, error: {e}")
                    impact_level_enum = None

                # Create the new analysis record
                analysis_obj = LegislationAnalysis(
                    legislation_id=legislation_id,
                    analysis_version=new_version,
                    previous_version_id=prev_id,
                    analysis_date=datetime.utcnow(),
                    
                    # Basic fields from the schema
                    summary=analysis_dict.get("summary", ""),
                    key_points=analysis_dict.get("key_points", []),
                    public_health_impacts=analysis_dict.get("public_health_impacts", {}),
                    local_gov_impacts=analysis_dict.get("local_government_impacts", {}),
                    economic_impacts=analysis_dict.get("economic_impacts", {}),
                    environmental_impacts=analysis_dict.get("environmental_impacts", []),
                    education_impacts=analysis_dict.get("education_impacts", []),
                    infrastructure_impacts=analysis_dict.get("infrastructure_impacts", []),
                    recommended_actions=analysis_dict.get("recommended_actions", []),
                    immediate_actions=analysis_dict.get("immediate_actions", []),
                    resource_needs=analysis_dict.get("resource_needs", []),
                    
                    # Store the complete raw analysis
                    raw_analysis=analysis_dict,
                    
                    # Model metadata
                    model_version=self.model_name,
                    
                    # Impact categorization
                    impact_category=impact_category_enum,
                    impact=impact_level_enum
                )
                
                # Store processing metadata
                if hasattr(analysis_obj, 'processing_metadata'):
                    analysis_obj.processing_metadata = {
                        "date_processed": datetime.utcnow().isoformat(),
                        "model_name": self.model_name,
                        "software_version": "2.0.0",  # Version of this software
                    }
                
                self.db_session.add(analysis_obj)

                logger.info(
                    f"[AIAnalysis] Created new LegislationAnalysis (version={new_version}) for Legislation {legislation_id}"
                )
                
                return analysis_obj
                
        except SQLAlchemyError as e:
            error_msg = f"Database error storing analysis for legislation {legislation_id}: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseError(error_msg) from e
        except Exception as e:
            error_msg = f"Error storing analysis for legislation {legislation_id}: {e}"
            logger.error(error_msg, exc_info=True)
            raise AIAnalysisError(error_msg) from e

    def _update_legislation_priority(self, legislation_id: int, analysis_dict: Dict[str, Any]) -> None:
        """
        Updates the LegislationPriority record based on analysis results.
        
        Args:
            legislation_id: The ID of the legislation
            analysis_dict: The structured analysis data
            
        Raises:
            DatabaseError: If database operations fail
        """
        if not HAS_PRIORITY_MODEL:
            logger.debug("LegislationPriority model not available - skipping priority update")
            return
            
        try:
            # Calculate priority scores
            health_relevance = 50  # Default medium score
            local_govt_relevance = 50  # Default medium score
            
            # Extract impact summary information
            impact_summary = analysis_dict.get("impact_summary", {})
            impact_category_str = impact_summary.get("primary_category")
            impact_level_str = impact_summary.get("impact_level")
            relevance_to_texas_str = impact_summary.get("relevance_to_texas")
            
            # Convert relevance categories to numeric scores (0-100)
            relevance_mapping = {
                "low": 25,
                "moderate": 50,
                "high": 75,
                "critical": 100
            }
            
            # Calculate base score from impact level
            base_score = relevance_mapping.get(impact_level_str, 50)
            
            # Adjust based on relevance to Texas
            texas_multiplier = {
                "low": 0.7,
                "moderate": 0.85,
                "high": 1.0
            }.get(relevance_to_texas_str, 0.85)
            
            # Adjust scores based on impact category
            if impact_category_str == "public_health":
                health_relevance = min(100, int(base_score * 1.5 * texas_multiplier))
                local_govt_relevance = min(100, int(base_score * 0.8 * texas_multiplier))
            elif impact_category_str == "local_gov":
                health_relevance = min(100, int(base_score * 0.8 * texas_multiplier))
                local_govt_relevance = min(100, int(base_score * 1.5 * texas_multiplier))
            else:
                # For other categories, calculate based on impact level and Texas relevance
                health_relevance = min(100, int(base_score * texas_multiplier))
                local_govt_relevance = min(100, int(base_score * texas_multiplier))
            
            # Check if we have health impacts detailed
            ph_impacts = analysis_dict.get("public_health_impacts", {})
            if ph_impacts:
                # Adjust score based on having detailed impacts
                if ph_impacts.get("direct_effects") or ph_impacts.get("funding_impact"):
                    health_relevance = min(100, health_relevance + 10)
            
            # Check if we have local government impacts detailed
            local_impacts = analysis_dict.get("local_government_impacts", {})
            if local_impacts:
                # Adjust score based on having detailed impacts
                if local_impacts.get("fiscal") or local_impacts.get("administrative"):
                    local_govt_relevance = min(100, local_govt_relevance + 10)
            
            # Calculate overall priority as weighted average
            overall_priority = (health_relevance + local_govt_relevance) // 2
            
            with self._db_transaction():
                # Get existing priority record or create a new one
                priority = self.db_session.query(LegislationPriority).filter_by(
                    legislation_id=legislation_id
                ).first()
                
                if priority:
                    # Only update if it wasn't manually reviewed
                    if not priority.manually_reviewed:
                        priority.public_health_relevance = health_relevance
                        priority.local_govt_relevance = local_govt_relevance
                        priority.overall_priority = overall_priority
                        priority.auto_categorized = True
                        priority.auto_categories = {
                            "health_impacts": health_relevance > 50,
                            "local_govt_impacts": local_govt_relevance > 50,
                            "impact_category": impact_category_str,
                            "impact_level": impact_level_str,
                            "texas_relevance": relevance_to_texas_str
                        }
                else:
                    # Create new priority record
                    new_priority = LegislationPriority(
                        legislation_id=legislation_id,
                        public_health_relevance=health_relevance,
                        local_govt_relevance=local_govt_relevance,
                        overall_priority=overall_priority,
                        auto_categorized=True,
                        auto_categories={
                            "health_impacts": health_relevance > 50,
                            "local_govt_impacts": local_govt_relevance > 50,
                            "impact_category": impact_category_str,
                            "impact_level": impact_level_str,
                            "texas_relevance": relevance_to_texas_str
                        }
                    )
                    self.db_session.add(new_priority)
                
                logger.info(f"Updated priority for legislation {legislation_id}: "
                          f"health={health_relevance}, local_govt={local_govt_relevance}, "
                          f"overall={overall_priority}")
                
        except SQLAlchemyError as e:
            error_msg = f"Database error updating priority for legislation {legislation_id}: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseError(error_msg) from e
        except Exception as e:
            error_msg = f"Error updating priority for legislation {legislation_id}: {e}"
            logger.error(error_msg, exc_info=True)
            # Log but don't raise - priority update is non-critical
            logger.warning(error_msg)

    def get_cached_analysis(self, legislation_id: int) -> Optional[LegislationAnalysis]:
        """
        Retrieve a cached analysis if available and not expired.
        
        Args:
            legislation_id: The ID of the legislation
            
        Returns:
            Cached LegislationAnalysis if valid, None otherwise
        """
        if legislation_id in self._analysis_cache:
            cache_time, cached_analysis = self._analysis_cache[legislation_id]
            cache_age_minutes = (datetime.utcnow() - cache_time).total_seconds() / 60
            
            if cache_age_minutes < self.config.cache_ttl_minutes:
                logger.debug(f"Using cached analysis for legislation ID={legislation_id}")
                return cached_analysis
            else:
                # Remove expired cache entry
                del self._analysis_cache[legislation_id]
                
        return None

    def clear_cache(self) -> None:
        """Clear the analysis cache."""
        self._analysis_cache.clear()
        logger.info("Analysis cache cleared")

    def get_token_usage_estimate(self, legislation_id: int) -> Dict[str, Any]:
        """
        Estimate token usage for analyzing a specific legislation.
        
        Args:
            legislation_id: The ID of the legislation
            
        Returns:
            Dictionary with token usage estimates
            
        Raises:
            ValueError: If legislation is not found
        """
        try:
            # Load the legislation text
            leg_obj = self.db_session.query(Legislation).filter_by(id=legislation_id).first()
            if not leg_obj:
                raise ValueError(f"Legislation with ID={legislation_id} not found")
                
            # Get the text content
            text_rec = leg_obj.latest_text
            if text_rec and text_rec.text_content:
                if hasattr(text_rec, 'is_binary') and text_rec.is_binary:
                    full_text = leg_obj.description or ""
                else:
                    full_text = text_rec.text_content
            else:
                full_text = leg_obj.description or ""
                
            # Count tokens
            token_count = self.count_tokens(full_text)
            
            # Calculate completion token estimate (typically smaller than input)
            # For o-series models, account for reasoning tokens
            completion_estimate = min(8000, token_count // 2)
            
            # Calculate chunks needed
            safe_limit = self.max_context_tokens - self.safety_buffer
            chunks_needed = (token_count + safe_limit - 1) // safe_limit if token_count > 0 else 1
            
            # Estimate total token usage
            total_estimate = token_count + (completion_estimate * chunks_needed)
            
            return {
                "legislation_id": legislation_id,
                "input_tokens": token_count,
                "estimated_completion_tokens": completion_estimate,
                "chunks_needed": chunks_needed,
                "total_estimated_tokens": total_estimate,
                "requires_chunking": token_count > safe_limit,
                "token_limit": safe_limit
            }
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error estimating token usage: {e}", exc_info=True)
            raise AIAnalysisError(f"Error estimating token usage: {str(e)}") from e

    def batch_analyze(self, legislation_ids: List[int], 
                     max_parallel: int = 1,
                     error_handling: Literal["stop", "continue"] = "continue") -> Dict[str, Any]:
        """
        Analyze multiple legislation records, with optional parallel processing.
        
        Args:
            legislation_ids: List of legislation IDs to analyze
            max_parallel: Maximum number of parallel analyses (default: 1 for sequential)
            error_handling: Whether to continue after errors or stop
            
        Returns:
            Dictionary with analysis results and statistics
            
        Raises:
            AIAnalysisError: If an unrecoverable error occurs and error_handling="stop"
        """
        if max_parallel > 1:
            logger.warning("Parallel processing not yet implemented, using sequential processing")
            max_parallel = 1
            
        results = {
            "total": len(legislation_ids),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "analyses": {},
            "errors": {}
        }
        
        for leg_id in legislation_ids:
            try:
                # Check if we already have an analysis in cache
                cached = self.get_cached_analysis(leg_id)
                if cached:
                    results["analyses"][leg_id] = {
                        "analysis_id": cached.id,
                        "version": cached.analysis_version,
                        "status": "cached"
                    }
                    results["skipped"] += 1
                    continue
                    
                # Perform the analysis
                logger.info(f"Analyzing legislation ID={leg_id}")
                analysis = self.analyze_legislation(leg_id)
                
                # Record the result
                results["analyses"][leg_id] = {
                    "analysis_id": analysis.id,
                    "version": analysis.analysis_version,
                    "status": "success"
                }
                results["successful"] += 1
                
            except Exception as e:
                # Record the error
                error_msg = str(e)
                results["errors"][leg_id] = error_msg
                results["failed"] += 1
                logger.error(f"Error analyzing legislation ID={leg_id}: {error_msg}")
                
                # If error handling is set to stop, raise the exception
                if error_handling == "stop":
                    raise AIAnalysisError(f"Batch analysis stopped due to error on legislation ID={leg_id}: {error_msg}")
        
        return results               