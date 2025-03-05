"""
Core AIAnalysis class that orchestrates the bill analysis workflow.
"""

import os
import json
import logging
import re
import time
import traceback
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Union, Literal, Tuple, cast, Type
from contextlib import contextmanager

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from ai_analysis.errors import (
    AIAnalysisError, TokenLimitError, APIError, RateLimitError, 
    ContentProcessingError, DatabaseError
)
from ai_analysis.models import LegislationAnalysisResult
from ai_analysis.config import AIAnalysisConfig
from ai_analysis.openai_client import OpenAIClient
from ai_analysis.chunking import TextChunker
from ai_analysis.utils import (
    TokenCounter, create_analysis_instructions, get_analysis_json_schema,
    create_user_prompt, merge_analyses, create_chunk_prompt,
    calculate_priority_scores
)

# Import required models
from app.models import (
    Legislation,
    LegislationText,
    LegislationAnalysis,
    ImpactCategoryEnum,
    ImpactLevelEnum
)

# Try to import additional related models if available
try:
    from app.models import LegislationPriority
    HAS_PRIORITY_MODEL = True
except ImportError:
    HAS_PRIORITY_MODEL = False

logger = logging.getLogger(__name__)

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

        # Initialize supporting components
        self.token_counter = TokenCounter(model_name=self.config.model_name)
        self.text_chunker = TextChunker(token_counter=self.token_counter)
        self.openai_client = OpenAIClient(
            api_key=self.config.openai_api_key,
            model_name=self.config.model_name,
            max_retries=self.config.max_retries,
            retry_base_delay=self.config.retry_base_delay
        )

        # Transfer config values to instance attributes for compatibility
        self.model_name = self.config.model_name
        self.max_context_tokens = self.config.max_context_tokens
        self.safety_buffer = self.config.safety_buffer

        # Cache for legislation analysis to prevent redundant work
        self._analysis_cache: Dict[int, Tuple[datetime, LegislationAnalysis]] = {}

        logger.info(f"AIAnalysis initialized with model {self.model_name}")

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
            cache_age_minutes = (datetime.now(timezone.utc) - cache_time).total_seconds() / 60

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
                is_binary = False
                if hasattr(text_rec, 'is_binary'):
                    is_binary = bool(text_rec.is_binary)

                if is_binary:
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
            token_count = self.token_counter.count_tokens(full_text)
            safe_limit = self.max_context_tokens - self.safety_buffer

            # Log token information
            logger.info(f"Legislation {legislation_id} has ~{token_count} tokens (limit: {safe_limit})")

            analysis_data = None
            if token_count > safe_limit:
                logger.warning(f"Legislation {legislation_id} exceeds token limit, using intelligent chunking")
                # Use intelligent chunking for large documents
                chunks, has_structure = self.text_chunker.chunk_text(full_text, safe_limit)

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
            self._analysis_cache[legislation_id] = (datetime.now(timezone.utc), result_analysis)

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

    def _call_structured_analysis(self, text: str, is_chunk: bool = False) -> Dict[str, Any]:
        """
        Create structured analysis request to OpenAI.

        Args:
            text: Text to analyze
            is_chunk: Whether this is a chunk of a larger document

        Returns:
            Dictionary containing the structured analysis
        """
        # Get the JSON schema for structured output
        json_schema = get_analysis_json_schema()

        # Construct messages
        system_message = create_analysis_instructions(is_chunk=is_chunk)
        user_message = create_user_prompt(text, is_chunk=is_chunk)

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        # Call the OpenAI API with structured response
        analysis_data = self.openai_client.call_structured_analysis(
            messages=messages,
            json_schema=json_schema
        )

        # Validate with Pydantic if we have data
        if analysis_data:
            try:
                validated_data = LegislationAnalysisResult(**analysis_data)
                return validated_data.model_dump()
            except ValidationError as e:
                logger.error(f"Response validation failed: {e}")
                # Return original data if validation fails - we'll work with what we have

        return analysis_data

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
            "govt_type": str(getattr(leg_obj.govt_type, 'value', 'unknown')) if leg_obj.govt_type else "unknown",
            "govt_source": leg_obj.govt_source,
            "status": str(getattr(leg_obj.bill_status, 'value', 'unknown')) if hasattr(leg_obj, 'bill_status') and leg_obj.bill_status else "unknown"
        }

        # Initialize the cumulative analysis
        cumulative_analysis = {}
        chunk_summaries = []

        # Process each chunk, carrying forward context
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} for legislation {leg_obj.id}")

            try:
                # Create a custom prompt for this chunk that includes previous context
                chunk_prompt = create_chunk_prompt(
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
                    cumulative_analysis = merge_analyses(cumulative_analysis, chunk_result)

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
                impact_category_enum = None
                impact_level_enum = None

                if impact_category_str:
                    try:
                        impact_category_enum = ImpactCategoryEnum(impact_category_str)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid impact_category value: {impact_category_str}, error: {e}")

                if impact_level_str:
                    try:
                        impact_level_enum = ImpactLevelEnum(impact_level_str)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid impact_level value: {impact_level_str}, error: {e}")

                # Create the new analysis record
                analysis_obj = LegislationAnalysis(
                    legislation_id=legislation_id,
                    analysis_version=new_version,
                    previous_version_id=prev_id,
                    analysis_date=datetime.now(timezone.utc),

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
                        "date_processed": datetime.now(timezone.utc).isoformat(),
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
            priority_data = calculate_priority_scores(analysis_dict, legislation_id)

            with self._db_transaction():
                # Get existing priority record or create a new one
                priority = self.db_session.query(LegislationPriority).filter_by(
                    legislation_id=legislation_id
                ).first()

                if priority:
                    # Only update if it wasn't manually reviewed
                    if not bool(priority.manually_reviewed):
                        priority.public_health_relevance = priority_data["public_health_relevance"]
                        priority.local_govt_relevance = priority_data["local_govt_relevance"]
                        priority.overall_priority = priority_data["overall_priority"]
                        priority.auto_categorized = True
                        priority.auto_categories = priority_data["auto_categories"]
                else:
                    # Create new priority record
                    new_priority = LegislationPriority(
                        legislation_id=priority_data["legislation_id"],
                        public_health_relevance=priority_data["public_health_relevance"],
                        local_govt_relevance=priority_data["local_govt_relevance"],
                        overall_priority=priority_data["overall_priority"],
                        auto_categorized=priority_data["auto_categorized"],
                        auto_categories=priority_data["auto_categories"]
                    )
                    self.db_session.add(new_priority)

                logger.info(
                    f"Updated priority for legislation {legislation_id}: "
                    f"health={priority_data['public_health_relevance']}, "
                    f"local_govt={priority_data['local_govt_relevance']}, "
                    f"overall={priority_data['overall_priority']}"
                )

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
            cache_age_minutes = (datetime.now(timezone.utc) - cache_time).total_seconds() / 60

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
                is_binary = False
                if hasattr(text_rec, 'is_binary'):
                    is_binary = bool(text_rec.is_binary)

                if is_binary:
                    full_text = leg_obj.description or ""
                else:
                    full_text = text_rec.text_content
            else:
                full_text = leg_obj.description or ""

            # Count tokens
            token_count = self.token_counter.count_tokens(full_text)

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
            logger.error(f"Error estimating token usage: {e}")
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

    async def analyze_legislation_async(self, legislation_id: int) -> LegislationAnalysis:
        """
        Asynchronous version of analyze_legislation.

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
            cache_age_minutes = (datetime.now(timezone.utc) - cache_time).total_seconds() / 60

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
                is_binary = False
                if hasattr(text_rec, 'is_binary'):
                    is_binary = bool(text_rec.is_binary)

                if is_binary:
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
            token_count = self.token_counter.count_tokens(full_text)
            safe_limit = self.max_context_tokens - self.safety_buffer

            # Log token information
            logger.info(f"Legislation {legislation_id} has ~{token_count} tokens (limit: {safe_limit})")

            analysis_data = None

            # Start a transaction for the analysis
            with self._db_transaction() as transaction:
                # Make sure OpenAI client has our session
                self.openai_client.set_db_session(self.db_session)

                if token_count > safe_limit:
                    logger.warning(f"Legislation {legislation_id} exceeds token limit, using intelligent chunking")
                    # Use intelligent chunking for large documents
                    chunks, has_structure = self.text_chunker.chunk_text(full_text, safe_limit)

                    if len(chunks) == 1:
                        # If we only have one chunk, process normally
                        text_for_analysis = chunks[0]
                        analysis_data = await self._call_structured_analysis_async(
                            text_for_analysis, transaction_ctx=transaction
                        )
                    else:
                        # For multiple chunks, analyze sequentially with context preservation
                        analysis_data = await self._analyze_in_chunks_async(
                            chunks, has_structure, leg_obj, transaction_ctx=transaction
                        )
                else:
                    # For normal-sized documents, proceed with standard analysis
                    analysis_data = await self._call_structured_analysis_async(
                        full_text, transaction_ctx=transaction
                    )

                if not analysis_data:
                    error_msg = f"Failed to generate analysis for Legislation ID={legislation_id}"
                    logger.error(error_msg)
                    raise AIAnalysisError(error_msg)

                # 5) Save the new LegislationAnalysis record
                result_analysis = self._store_legislation_analysis(legislation_id, analysis_data)

                # Cache for future quick access
                self._analysis_cache[legislation_id] = (datetime.now(timezone.utc), result_analysis)

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

    async def _call_structured_analysis_async(
        self, 
        text: str, 
        is_chunk: bool = False,
        transaction_ctx: Any = None
    ) -> Dict[str, Any]:
        """
        Create structured analysis request to OpenAI asynchronously.

        Args:
            text: Text to analyze
            is_chunk: Whether this is a chunk of a larger document
            transaction_ctx: Transaction context for database operations

        Returns:
            Dictionary containing the structured analysis
        """
        # Get the JSON schema for structured output
        json_schema = get_analysis_json_schema()

        # Construct messages
        system_message = create_analysis_instructions(is_chunk=is_chunk)
        user_message = create_user_prompt(text, is_chunk=is_chunk)

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        # Call the OpenAI API with structured response
        try:
            analysis_data = await self.openai_client.call_structured_analysis_async(
                messages=messages,
                json_schema=json_schema,
                transaction_ctx=transaction_ctx
            )

            # Validate with Pydantic if we have data
            if analysis_data:
                try:
                    validated_data = LegislationAnalysisResult(**analysis_data)
                    return validated_data.model_dump()
                except ValidationError as e:
                    logger.error(f"Response validation failed: {e}")
                    # Return original data if validation fails - we'll work with what we have

            return analysis_data
        except Exception as e:
            logger.error(f"Error in async structured analysis: {e}")
            raise

    async def _analyze_in_chunks_async(
        self, 
        chunks: List[str], 
        structured: bool, 
        leg_obj: Legislation,
        transaction_ctx: Any = None
    ) -> Dict[str, Any]:
        """
        Analyzes a large bill in chunks asynchronously, preserving context between chunks.

        Args:
            chunks: List of text chunks to analyze
            structured: Whether the chunks have structured sections
            leg_obj: The legislation database object
            transaction_ctx: Transaction context for database operations

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
            "govt_type": str(getattr(leg_obj.govt_type, 'value', 'unknown')) if leg_obj.govt_type else "unknown",
            "govt_source": leg_obj.govt_source,
            "status": str(getattr(leg_obj.bill_status, 'value', 'unknown')) if hasattr(leg_obj, 'bill_status') and leg_obj.bill_status else "unknown"
        }

        # Initialize the cumulative analysis
        cumulative_analysis = {}
        chunk_summaries = []

        # Process each chunk, carrying forward context, but sequentially
        # We don't parallelize this because each chunk builds on previous context
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} for legislation {leg_obj.id}")

            try:
                # Create a custom prompt for this chunk that includes previous context
                chunk_prompt = create_chunk_prompt(
                    chunk=chunk, 
                    chunk_index=i, 
                    total_chunks=len(chunks),
                    prev_summaries=chunk_summaries,
                    legislation_metadata=context,
                    is_structured=structured
                )

                # Process this chunk
                chunk_result = await self._call_structured_analysis_async(
                    chunk_prompt, is_chunk=True, transaction_ctx=transaction_ctx
                )

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
                    cumulative_analysis = merge_analyses(cumulative_analysis, chunk_result)

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

    async def batch_analyze_async(self, legislation_ids: List[int], max_concurrent: int = 5) -> Dict[str, Any]:
        """
        Asynchronously analyze multiple legislation records in parallel.

        Args:
            legislation_ids: List of legislation IDs to analyze
            max_concurrent: Maximum number of concurrent analyses

        Returns:
            Dictionary with analysis results and statistics
        """
        results = {
            "total": len(legislation_ids),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "analyses": {},
            "errors": {}
        }

        # Create tasks for each legislation ID, respecting the max_concurrent limit
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_legislation(leg_id):
            async with semaphore:
                try:
                    # Check cache first
                    cached = self.get_cached_analysis(leg_id)
                    if cached:
                        return {"leg_id": leg_id, "status": "cached", "analysis": cached}

                    # Analyze the legislation
                    analysis = await self.analyze_legislation_async(leg_id)
                    return {"leg_id": leg_id, "status": "success", "analysis": analysis}
                except Exception as e:
                    return {"leg_id": leg_id, "status": "error", "error": str(e)}

        # Create tasks for all legislation IDs
        tasks = [process_legislation(leg_id) for leg_id in legislation_ids]

        # Execute all tasks concurrently
        task_results = await asyncio.gather(*tasks)

        # Process results
        for result in task_results:
            leg_id = result["leg_id"]

            if result["status"] == "cached":
                results["skipped"] += 1
                results["analyses"][leg_id] = {
                    "analysis_id": result["analysis"].id,
                    "version": result["analysis"].analysis_version,
                    "status": "cached"
                }
            elif result["status"] == "success":
                results["successful"] += 1
                results["analyses"][leg_id] = {
                    "analysis_id": result["analysis"].id,
                    "version": result["analysis"].analysis_version,
                    "status": "success"
                }
            else:  # error
                results["failed"] += 1
                results["errors"][leg_id] = result["error"]

        return results
        
    def analyze_bill(self, bill_text: str, bill_title: Optional[str] = None, state: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze bill text directly without storing in the database.

        Args:
            bill_text: The full text of the bill
            bill_title: Optional title of the bill
            state: Optional state where the bill originated

        Returns:
            Dict containing the structured analysis results

        Raises:
            AIAnalysisError: If analysis generation fails
        """
        try:
            # Count tokens to determine if we need chunking
            token_count = self.token_counter.count_tokens(bill_text)
            safe_limit = self.max_context_tokens - self.safety_buffer

            # Create context about the bill
            context = {
                "bill_title": bill_title or "Unspecified Bill",
                "state": state or "Unspecified"
            }

            # Analyze based on size
            if token_count > safe_limit:
                logger.info(f"Bill exceeds token limit ({token_count} tokens), using intelligent chunking")
                # Use intelligent chunking for large documents
                chunks, has_structure = self.text_chunker.chunk_text(bill_text, safe_limit)

                if len(chunks) == 1:
                    # If we only have one chunk, process normally
                    text_for_analysis = chunks[0]
                    return self._call_structured_analysis(text_for_analysis)
                else:
                    # For multiple chunks, create a mock legislation object for context
                    mock_leg = type('MockLegislation', (), {
                        'id': 0,
                        'bill_number': "N/A",
                        'title': bill_title or "Unspecified",
                        'description': bill_text[:500] + "..." if len(bill_text) > 500 else bill_text,
                        'govt_type': type('MockEnum', (), {'value': state or "Unspecified"}),
                        'govt_source': "External",
                        'bill_status': type('MockEnum', (), {'value': "External"})
                    })

                    # Analyze in chunks
                    return self._analyze_in_chunks(chunks, has_structure, mock_leg)
            else:
                # For normal-sized documents, proceed with standard analysis
                return self._call_structured_analysis(bill_text)

        except Exception as e:
            error_msg = f"Error analyzing bill text: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AIAnalysisError(error_msg) from e
