"""
Core AIAnalysis class that orchestrates the bill analysis workflow.
"""

import logging
import re
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Literal, Tuple
from contextlib import contextmanager, asynccontextmanager
from threading import Lock

from sqlalchemy import Column
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.ai_analysis.errors import (
    AIAnalysisError, TokenLimitError, APIError, DatabaseError
)
from app.ai_analysis.models import LegislationAnalysisResult
from app.ai_analysis.config import AIAnalysisConfig
from app.ai_analysis.openai_client import OpenAIClient
from app.ai_analysis.chunking import TextChunker
from app.ai_analysis.utils import (
    TokenCounter, create_analysis_instructions, get_analysis_json_schema,
    create_user_prompt, merge_analyses, create_chunk_prompt,
    calculate_priority_scores
)

# Import required models
from app.models import (
    Legislation,
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

        logger.setLevel(getattr(logging, self.config.log_level))
        if not db_session:
            raise ValueError("Database session is required")
        self.db_session = db_session

        self.token_counter = TokenCounter(model_name=self.config.model_name)
        self.text_chunker = TextChunker(token_counter=self.token_counter)
        self.openai_client = OpenAIClient(
            api_key=self.config.openai_api_key,
            model_name=self.config.model_name,
            max_retries=self.config.max_retries,
            retry_base_delay=self.config.retry_base_delay
        )

        self._analysis_cache: Dict[int, Tuple[datetime, LegislationAnalysis]] = {}
        self._cache_lock = Lock()

        logger.info(f"AIAnalysis initialized with model {self.config.model_name}")

    @contextmanager
    def _db_transaction(self):
        transaction = None
        try:
            transaction = self.db_session.begin_nested()
            yield transaction
            transaction.commit()
        except SQLAlchemyError as e:
            if transaction is not None:
                transaction.rollback()
            logger.error(f"Database error in transaction: {e}", exc_info=True)
            raise DatabaseError(f"Database operation failed: {str(e)}") from e
        except Exception as e:
            if transaction is not None:
                transaction.rollback()
            logger.error(f"Unexpected error in transaction: {e}", exc_info=True)
            raise

    def _ensure_plain_string(self, possibly_column: Any) -> str:
        """
        Convert a Column[str], bytes, or any other object to a plain `str`.
        """
        # If it's actually a SQLAlchemy Column, convert to string
        if isinstance(possibly_column, Column):
            return str(possibly_column)

        # If it's bytes, decode it
        if isinstance(possibly_column, bytes):
            return possibly_column.decode("utf-8")

        # If it's already a string, return as is; otherwise str() it.
        if isinstance(possibly_column, str):
            return possibly_column
        return str(possibly_column)

    def analyze_legislation(self, legislation_id: int) -> LegislationAnalysis:
        """
        Analyze legislation by ID synchronously and return the resulting LegislationAnalysis.
        Uses caching to avoid re-analysis within the configured TTL.
        """
        with self._cache_lock:
            if legislation_id in self._analysis_cache:
                cache_time, cached_analysis = self._analysis_cache[legislation_id]
                cache_age_minutes = (
                    datetime.now(timezone.utc) - cache_time
                ).total_seconds() / 60
                if cache_age_minutes < self.config.cache_ttl_minutes:
                    logger.info(
                        f"Using cached analysis for legislation ID={legislation_id}"
                    )
                    return cached_analysis
                else:
                    del self._analysis_cache[legislation_id]

        leg_obj = self.db_session.query(Legislation).filter_by(id=legislation_id).first()
        if leg_obj is None:
            error_msg = f"Legislation with ID={legislation_id} not found in the DB."
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Attempt to get full text from the latest_text or fallback to description
        text_rec = leg_obj.latest_text
        if text_rec and text_rec.text_content:
            is_binary = getattr(text_rec, 'is_binary', False)
            if is_binary:
                logger.warning(
                    f"Binary content in LegislationText ID={text_rec.id}, using description"
                )
                full_text = self._ensure_plain_string(leg_obj.description)
            else:
                full_text = self._ensure_plain_string(text_rec.text_content)
        else:
            full_text = self._ensure_plain_string(leg_obj.description or "")

        token_count = self.token_counter.count_tokens(full_text)
        if token_count > self.config.max_context_tokens:
            raise TokenLimitError(
                f"Token count exceeds limit of {self.config.max_context_tokens}"
            )

        safe_limit = self.config.max_context_tokens - self.config.safety_buffer
        logger.info(
            f"Legislation {legislation_id} has ~{token_count} tokens (limit: {safe_limit})"
        )

        if token_count > safe_limit:
            logger.warning(
                f"Legislation {legislation_id} exceeds token limit, using chunking"
            )
            chunks, has_structure = self.text_chunker.chunk_text(full_text, safe_limit)
            if len(chunks) == 1:
                text_for_analysis = chunks[0]
                analysis_data = self._call_structured_analysis(text_for_analysis)
            else:
                analysis_data = self._analyze_in_chunks(chunks, has_structure, leg_obj)
        else:
            analysis_data = self._call_structured_analysis(full_text)

        if not analysis_data:
            error_msg = (
                f"Failed to generate analysis for Legislation ID={legislation_id}"
            )
            logger.error(error_msg)
            raise AIAnalysisError(error_msg)

        result_analysis = self._store_legislation_analysis(legislation_id, analysis_data)

        with self._cache_lock:
            self._analysis_cache[legislation_id] = (
                datetime.now(timezone.utc),
                result_analysis
            )

        if HAS_PRIORITY_MODEL:
            self.update_legislation_priority(legislation_id, analysis_data)

        return result_analysis

    def _call_structured_analysis(
        self, text: str, is_chunk: bool = False
    ) -> Dict[str, Any]:
        """
        Calls the OpenAI client to perform a structured analysis on the provided text.
        Returns the analysis data as a dictionary, if successful.
        """
        json_schema = get_analysis_json_schema()
        system_message = create_analysis_instructions(is_chunk=is_chunk)
        user_message = create_user_prompt(text, is_chunk=is_chunk)
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        analysis_data = self.openai_client.call_structured_analysis(
            messages=messages,
            json_schema=json_schema
        )
        if analysis_data is not None:
            try:
                validated_data = LegislationAnalysisResult(**analysis_data)
                return validated_data.model_dump()
            except ValidationError as e:
                logger.error(f"Response validation failed: {e}")
        return analysis_data or {}

    def _analyze_in_chunks(
        self, 
        chunks: List[str], 
        structured: bool, 
        leg_obj: Legislation
    ) -> Dict[str, Any]:
        """
        Breaks the text into chunks and analyzes them sequentially. Merges partial analyses.
        """
        description_text = self._ensure_plain_string(leg_obj.description or "")
        govt_type_value = str(getattr(leg_obj.govt_type, 'value', 'unknown'))
        status_value = str(getattr(leg_obj.bill_status, 'value', 'unknown'))

        context = {
            "bill_number": leg_obj.bill_number,
            "title": leg_obj.title,
            "description": description_text,
            "govt_type": govt_type_value,
            "govt_source": leg_obj.govt_source,
            "status": status_value
        }

        cumulative_analysis: Dict[str, Any] = {}
        chunk_summaries: List[str] = []

        for i, chunk in enumerate(chunks):
            logger.info(
                f"Processing chunk {i+1}/{len(chunks)} for legislation {leg_obj.id}"
            )
            try:
                chunk_prompt = create_chunk_prompt(
                    chunk=chunk,
                    chunk_index=i,
                    total_chunks=len(chunks),
                    prev_summaries=chunk_summaries,
                    legislation_metadata=context,
                    is_structured=structured
                )
                chunk_result = self._call_structured_analysis(
                    chunk_prompt, 
                    is_chunk=True
                )
                if not chunk_result:
                    logger.warning(
                        f"Failed to analyze chunk {i+1}, continuing partial analysis"
                    )
                    continue
                if "summary" in chunk_result:
                    chunk_summaries.append(
                        f"Chunk {i+1} Summary: {chunk_result['summary']}"
                    )
                if i == 0:
                    cumulative_analysis = chunk_result
                else:
                    cumulative_analysis = merge_analyses(
                        cumulative_analysis, chunk_result
                    )
            except APIError as e:
                logger.error(f"API error analyzing chunk {i+1}: {e}")
                if i == 0:
                    raise AIAnalysisError(
                        f"Failed to analyze legislation {leg_obj.id} - first chunk"
                    ) from e
            except Exception as e:
                logger.error(f"Error analyzing chunk {i+1}: {e}", exc_info=True)
                if i == 0:
                    raise AIAnalysisError(
                        f"Failed to analyze legislation {leg_obj.id} - first chunk"
                    ) from e

        if not cumulative_analysis or "summary" not in cumulative_analysis:
            raise AIAnalysisError(
                f"Failed to generate complete analysis for legislation {leg_obj.id} "
                "after processing all chunks"
            )

        if "summary" in cumulative_analysis and len(chunks) > 1:
            cumulative_analysis["summary"] = self._post_process_summary(
                cumulative_analysis["summary"],
                len(chunks)
            )
        return cumulative_analysis

    def _post_process_summary(self, summary: str, chunk_count: int) -> str:
        """
        Performs final cleanup on a merged summary, removing chunk-specific references.
        """
        if len(summary) > 2000:
            summary = summary[:1997] + "..."

        chunk_phrases = [
            "in this section", "this part of the bill", "this section of the legislation",
            "as mentioned earlier", "based on the previous sections",
            "in the previous sections", "in the earlier sections"
        ]
        for phrase in chunk_phrases:
            summary = summary.replace(phrase, "")
        summary = re.sub(r'\s+', ' ', summary).strip()
        return summary

    def _store_legislation_analysis(
        self, 
        legislation_id: int, 
        analysis_dict: Dict[str, Any]
    ) -> LegislationAnalysis:
        """
        Stores the analysis results in the database, creating a new LegislationAnalysis record
        and linking it to the previous version if it exists.
        """
        if not analysis_dict:
            raise ValidationError("Cannot store empty analysis data")

        with self._db_transaction():
            existing_analyses = self.db_session.query(LegislationAnalysis).filter_by(
                legislation_id=legislation_id
            ).all()

            if existing_analyses:
                prev = max(
                    existing_analyses,
                    key=lambda x: (
                        x.analysis_version if isinstance(x.analysis_version, int) else -1
                    ),
                    default=None
                )
                new_version = (
                    (prev.analysis_version or 0) + 1
                )
                prev_id = prev.id if prev else None
            else:
                new_version = 1
                prev_id = None

            impact_summary = analysis_dict.get("impact_summary", {})
            impact_category_str = impact_summary.get("primary_category")
            impact_level_str = impact_summary.get("impact_level")

            impact_category_enum = None
            impact_level_enum = None

            if impact_category_str is not None:
                try:
                    impact_category_enum = ImpactCategoryEnum(impact_category_str)
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Invalid impact_category value: {impact_category_str}: {e}"
                    )
            if impact_level_str is not None:
                try:
                    impact_level_enum = ImpactLevelEnum(impact_level_str)
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Invalid impact_level value: {impact_level_str}: {e}"
                    )

            analysis_obj = LegislationAnalysis(
                legislation_id=legislation_id,
                analysis_version=new_version,
                previous_version_id=prev_id,
                analysis_date=datetime.now(timezone.utc),
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
                raw_analysis=analysis_dict,
                model_version=self.config.model_name,
                impact_category=impact_category_enum,
                impact=impact_level_enum
            )

            # Optional: store some metadata
            if hasattr(analysis_obj, "processing_metadata"):
                analysis_obj.processing_metadata = {
                    "date_processed": datetime.now(timezone.utc).isoformat(),
                    "model_name": self.config.model_name,
                    "software_version": "2.0.0"
                }

            self.db_session.add(analysis_obj)
            logger.info(
                f"[AIAnalysis] Created new LegislationAnalysis "
                f"(version={new_version}) for Legislation {legislation_id}"
            )
            return analysis_obj

    def update_legislation_priority(
        self, 
        legislation_id: int, 
        analysis_dict: Dict[str, Any]
    ) -> None:
        """
        Updates or creates the LegislationPriority record based on newly generated analysis.
        """
        if not HAS_PRIORITY_MODEL:
            return

        with self._db_transaction():
            try:
                # Calculate priority data from the analysis
                # if your function expects two parameters, pass them
                priority_data = calculate_priority_scores(analysis_dict, legislation_id)

                priority = self.db_session.query(LegislationPriority).filter_by(
                    legislation_id=legislation_id
                ).first()

                if priority:
                    # Only update if it hasn't been manually reviewed
                    if not bool(priority.manually_reviewed):
                        priority.public_health_relevance = priority_data.get(
                            "public_health_relevance"
                        )
                        priority.local_govt_relevance = priority_data.get(
                            "local_govt_relevance"
                        )
                        priority.overall_priority = priority_data.get("overall_priority")
                        priority.auto_categorized = True
                        # Typically a dict
                        priority.auto_categories = priority_data.get(
                            "auto_categories",
                            {}
                        )
                else:
                    new_priority = LegislationPriority(
                        legislation_id=legislation_id,
                        public_health_relevance=priority_data.get("public_health_relevance"),
                        local_govt_relevance=priority_data.get("local_govt_relevance", 0),
                        overall_priority=priority_data.get("overall_priority", 0),
                        auto_categorized=priority_data.get("auto_categorized", False),
                        auto_categories=priority_data.get("auto_categories", {})
                    )
                    self.db_session.add(new_priority)

                logger.info(
                    f"Updated priority for legislation {legislation_id}: "
                    f"health={priority_data.get('public_health_relevance')}, "
                    f"local_govt={priority_data.get('local_govt_relevance')}, "
                    f"overall={priority_data.get('overall_priority')}"
                )

            except SQLAlchemyError as e:
                error_msg = (
                    f"Database error updating priority for legislation {legislation_id}: {e}"
                )
                logger.error(error_msg, exc_info=True)
                raise DatabaseError(error_msg) from e
            except Exception as e:
                error_msg = f"Error updating priority for legislation {legislation_id}: {e}"
                logger.error(error_msg, exc_info=True)
                logger.warning(error_msg)

    def get_cached_analysis(self, legislation_id: int) -> Optional[LegislationAnalysis]:
        """
        Retrieve a cached analysis if it is still valid; otherwise return None.
        """
        with self._cache_lock:
            if legislation_id in self._analysis_cache:
                cache_time, cached_analysis = self._analysis_cache[legislation_id]
                cache_age_minutes = (
                    datetime.now(timezone.utc) - cache_time
                ).total_seconds() / 60
                if cache_age_minutes < self.config.cache_ttl_minutes:
                    logger.debug(
                        f"Using cached analysis for legislation ID={legislation_id}"
                    )
                    return cached_analysis
                else:
                    del self._analysis_cache[legislation_id]
        return None

    def clear_cache(self) -> None:
        """
        Clears the in-memory analysis cache.
        """
        with self._cache_lock:
            self._analysis_cache.clear()
        logger.info("Analysis cache cleared")

    def get_token_usage_estimate(self, legislation_id: int) -> Dict[str, Any]:
        """
        Estimate the token usage for analyzing a given legislation.
        """
        leg_obj = self.db_session.query(Legislation).filter_by(id=legislation_id).first()
        if leg_obj is None:
            raise ValueError(f"Legislation with ID={legislation_id} not found")

        text_rec = leg_obj.latest_text
        if text_rec and text_rec.text_content is not None:
            is_binary = getattr(text_rec, 'is_binary', False)
            if is_binary:
                full_text = self._ensure_plain_string(leg_obj.description if leg_obj.description is not None else "")
            else:
                full_text = self._ensure_plain_string(text_rec.text_content)
        else:
            full_text = self._ensure_plain_string(leg_obj.description if leg_obj.description is not None else "")

        token_count = self.token_counter.count_tokens(full_text)
        completion_estimate = min(8000, token_count // 2)
        safe_limit = self.config.max_context_tokens - self.config.safety_buffer
        chunks_needed = (
            (token_count + safe_limit - 1) // safe_limit
            if token_count > 0
            else 1
        )
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

    def batch_analyze(
        self, 
        legislation_ids: List[int], 
        max_parallel: int = 1,
        error_handling: Literal["stop", "continue"] = "continue"
    ) -> Dict[str, Any]:
        """
        Batch analysis of multiple legislation IDs. Processes them sequentially by default.
        If max_parallel > 1 is set, parallel processing could be implemented in the future.
        """
        if max_parallel > 1:
            logger.warning(
                "Parallel processing not yet implemented, using sequential processing"
            )
            max_parallel = 1

        results: Dict[str, Any] = {
            "total": len(legislation_ids),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "analyses": {},
            "errors": {}
        }

        for leg_id in legislation_ids:
            try:
                cached = self.get_cached_analysis(leg_id)
                if cached is not None:
                    results["analyses"][leg_id] = {
                        "analysis_id": cached.id,
                        "version": cached.analysis_version,
                        "status": "cached"
                    }
                    results["skipped"] += 1
                    continue

                logger.info(f"Analyzing legislation ID={leg_id}")
                analysis = self.analyze_legislation(leg_id)
                results["analyses"][leg_id] = {
                    "analysis_id": analysis.id,
                    "version": analysis.analysis_version,
                    "status": "success"
                }
                results["successful"] += 1

            except Exception as e:
                error_msg = str(e)
                results["errors"][leg_id] = error_msg
                results["failed"] += 1
                logger.error(f"Error analyzing legislation ID={leg_id}: {error_msg}")
                if error_handling == "stop":
                    raise AIAnalysisError(
                        f"Batch analysis stopped; error on ID={leg_id}: {error_msg}"
                    )

        return results

    @asynccontextmanager
    async def _get_async_transaction(self):
        """
        Provides an async context manager for database transactions.
        """
        transaction = None
        try:
            transaction = self.db_session.begin_nested()
            yield transaction
            transaction.commit()
        except SQLAlchemyError as e:
            if transaction:
                transaction.rollback()
            logger.error(f"Database error in async transaction: {e}", exc_info=True)
            raise DatabaseError(f"Database operation failed: {str(e)}") from e
        except Exception as e:
            if transaction:
                transaction.rollback()
            logger.error(f"Unexpected error in async transaction: {e}", exc_info=True)
            raise

    async def analyze_legislation_async(self, legislation_id: int) -> LegislationAnalysis:
        """
        Asynchronously analyze a given legislation by ID. Uses the same logic as the
        synchronous method but wrapped in an async context and calls the async OpenAI client.
        """
        with self._cache_lock:
            if legislation_id in self._analysis_cache:
                cache_time, cached_analysis = self._analysis_cache[legislation_id]
                cache_age_minutes = (
                    datetime.now(timezone.utc) - cache_time
                ).total_seconds() / 60
                if cache_age_minutes < self.config.cache_ttl_minutes:
                    logger.info(
                        f"Using cached analysis for legislation ID={legislation_id}"
                    )
                    return cached_analysis
                else:
                    del self._analysis_cache[legislation_id]

        leg_obj = self.db_session.query(Legislation).filter_by(id=legislation_id).first()
        if leg_obj is None:
            error_msg = f"Legislation with ID={legislation_id} not found in DB."
            logger.error(error_msg)
            raise ValueError(error_msg)

        text_rec = leg_obj.latest_text
        if text_rec and text_rec.text_content is not None:
            is_binary = getattr(text_rec, 'is_binary', False)
            if is_binary:
                logger.warning(
                    f"Binary content in LegislationText ID={text_rec.id}, using description"
                )
                full_text = self._ensure_plain_string(leg_obj.description if leg_obj.description is not None else "")
            else:
                full_text = self._ensure_plain_string(text_rec.text_content)
        else:
            full_text = self._ensure_plain_string(leg_obj.description if leg_obj.description is not None else "")

        token_count = self.token_counter.count_tokens(full_text)
        safe_limit = self.config.max_context_tokens - self.config.safety_buffer
        logger.info(
            f"Legislation {legislation_id} has ~{token_count} tokens (limit: {safe_limit})"
        )

        async with self._get_async_transaction() as transaction:
            self.openai_client.set_db_session(self.db_session)
            if token_count > safe_limit:
                logger.warning(
                    f"Legislation {legislation_id} exceeds token limit, using chunking"
                )
                chunks, has_structure = self.text_chunker.chunk_text(full_text, safe_limit)
                if len(chunks) == 1:
                    text_for_analysis = chunks[0]
                    analysis_data = await self._call_structured_analysis_async(
                        text_for_analysis, transaction_ctx=transaction
                    )
                else:
                    analysis_data = await self._analyze_in_chunks_async(
                        chunks, has_structure, leg_obj, transaction_ctx=transaction
                    )
            else:
                analysis_data = await self._call_structured_analysis_async(
                    full_text, transaction_ctx=transaction
                )

            if not analysis_data:
                error_msg = (
                    f"Failed to generate analysis for Legislation ID={legislation_id}"
                )
                logger.error(error_msg)
                raise AIAnalysisError(error_msg)

            result_analysis = self._store_legislation_analysis(
                legislation_id,
                analysis_data
            )
            with self._cache_lock:
                self._analysis_cache[legislation_id] = (
                    datetime.now(timezone.utc),
                    result_analysis
                )

            if HAS_PRIORITY_MODEL:
                self.update_legislation_priority(legislation_id, analysis_data)

            return result_analysis

    async def _call_structured_analysis_async(
        self, 
        text: str, 
        is_chunk: bool = False,
        transaction_ctx: Any = None
    ) -> Dict[str, Any]:
        """
        Asynchronous version of _call_structured_analysis. 
        Uses the async OpenAI client to analyze the text.
        """
        json_schema = get_analysis_json_schema()
        system_message = create_analysis_instructions(is_chunk=is_chunk)
        user_message = create_user_prompt(text, is_chunk=is_chunk)
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        try:
            analysis_data = await self.openai_client.call_structured_analysis_async(
                messages=messages,
                json_schema=json_schema,
                transaction_ctx=transaction_ctx
            )
            if analysis_data is not None:
                try:
                    validated_data = LegislationAnalysisResult(**analysis_data)
                    return validated_data.model_dump()
                except ValidationError as e:
                    logger.error(f"Response validation failed: {e}")
            return analysis_data or {}
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
        Asynchronous version of the _analyze_in_chunks method, chunking the text
        and merging partial results.
        """
        description_text = self._ensure_plain_string(leg_obj.description if leg_obj.description is not None else "")
        govt_type_value = str(getattr(leg_obj.govt_type, 'value', 'unknown'))
        status_value = str(getattr(leg_obj.bill_status, 'value', 'unknown'))

        context = {
            "bill_number": leg_obj.bill_number,
            "title": leg_obj.title,
            "description": description_text,
            "govt_type": govt_type_value,
            "govt_source": leg_obj.govt_source,
            "status": status_value
        }

        cumulative_analysis: Dict[str, Any] = {}
        chunk_summaries: List[str] = []

        for i, chunk in enumerate(chunks):
            logger.info(
                f"Processing chunk {i+1}/{len(chunks)} for legislation {leg_obj.id}"
            )
            try:
                chunk_prompt = create_chunk_prompt(
                    chunk=chunk,
                    chunk_index=i,
                    total_chunks=len(chunks),
                    prev_summaries=chunk_summaries,
                    legislation_metadata=context,
                    is_structured=structured
                )
                chunk_result = await self._call_structured_analysis_async(
                    chunk_prompt,
                    is_chunk=True,
                    transaction_ctx=transaction_ctx
                )
                if not chunk_result:
                    logger.warning(
                        f"Failed to analyze chunk {i+1}, continuing partial analysis"
                    )
                    continue
                if "summary" in chunk_result:
                    chunk_summaries.append(
                        f"Chunk {i+1} Summary: {chunk_result['summary']}"
                    )
                if i == 0:
                    cumulative_analysis = chunk_result
                else:
                    cumulative_analysis = merge_analyses(
                        cumulative_analysis, chunk_result
                    )

            except APIError as e:
                logger.error(f"API error analyzing chunk {i+1}: {e}")
                if i == 0:
                    raise AIAnalysisError(
                        f"Failed to analyze legislation {leg_obj.id} - first chunk"
                    ) from e
            except Exception as e:
                logger.error(f"Error analyzing chunk {i+1}: {e}", exc_info=True)
                if i == 0:
                    raise AIAnalysisError(
                        f"Failed to analyze legislation {leg_obj.id} - first chunk"
                    ) from e

        if not cumulative_analysis or "summary" not in cumulative_analysis:
            raise AIAnalysisError(
                f"Failed to generate complete analysis for legislation {leg_obj.id} "
                "after processing all chunks"
            )

        if "summary" in cumulative_analysis and len(chunks) > 1:
            cumulative_analysis["summary"] = self._post_process_summary(
                cumulative_analysis["summary"],
                len(chunks)
            )
        return cumulative_analysis

    async def batch_analyze_async(
        self, 
        legislation_ids: List[int], 
        max_concurrent: int = 5
    ) -> Dict[str, Any]:
        """
        Asynchronously batch analyze a list of legislation IDs with concurrency control.
        """
        results: Dict[str, Any] = {
            "total": len(legislation_ids),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "analyses": {},
            "errors": {}
        }
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_legislation(leg_id: int) -> Dict[str, Any]:
            async with semaphore:
                try:
                    cached = self.get_cached_analysis(leg_id)
                    if cached is not None:
                        return {
                            "leg_id": leg_id, 
                            "status": "cached", 
                            "analysis": cached
                        }
                    analysis = await self.analyze_legislation_async(leg_id)
                    return {
                        "leg_id": leg_id, 
                        "status": "success", 
                        "analysis": analysis
                    }
                except Exception as exc:
                    return {
                        "leg_id": leg_id, 
                        "status": "error", 
                        "error": str(exc)
                    }

        tasks = [process_legislation(leg_id) for leg_id in legislation_ids]
        task_results = await asyncio.gather(*tasks)

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
            else:
                results["failed"] += 1
                results["errors"][leg_id] = result["error"]

        return results

    def analyze_bill(
        self, 
        bill_text: str, 
        bill_title: Optional[str] = None, 
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a raw bill text without storing it in the database. Returns the analysis
        as a dictionary.
        """
        safe_bill_text = self._ensure_plain_string(bill_text)
        token_count = self.token_counter.count_tokens(safe_bill_text)
        safe_limit = self.config.max_context_tokens - self.config.safety_buffer

        if token_count > safe_limit:
            logger.info(
                f"Bill exceeds token limit ({token_count} tokens), using chunking"
            )
            chunks, has_structure = self.text_chunker.chunk_text(safe_bill_text, safe_limit)
            if len(chunks) == 1:
                text_for_analysis = chunks[0]
                return self._call_structured_analysis(text_for_analysis)
            else:
                # Create a mock legislation instance for context
                MockGovtEnum = type('MockEnum', (), {'value': state or "Unspecified"})()
                MockStatusEnum = type('MockEnum', (), {'value': "External"})()
                MockLegislation = type('MockLegislation', (), {
                    'id': 0,
                    'bill_number': "N/A",
                    'title': bill_title or "Unspecified",
                    'description': (
                        safe_bill_text[:500] + "..."
                        if len(safe_bill_text) > 500
                        else safe_bill_text
                    ),
                    'govt_type': MockGovtEnum,
                    'govt_source': "External",
                    'bill_status': MockStatusEnum
                })
                mock_leg = MockLegislation()
                return self._analyze_in_chunks(chunks, has_structure, mock_leg)
        else:
            return self._call_structured_analysis(safe_bill_text)

    async def analyze_bill_async(
        self, 
        bill_text: str, 
        bill_title: Optional[str] = None, 
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Asynchronously analyze a raw bill text (not stored in the DB). 
        Returns the analysis as a dictionary.
        """
        safe_bill_text = self._ensure_plain_string(bill_text)
        token_count = self.token_counter.count_tokens(safe_bill_text)
        safe_limit = self.config.max_context_tokens - self.config.safety_buffer

        if token_count > safe_limit:
            logger.info(
                f"Bill exceeds token limit ({token_count} tokens), chunking"
            )
            chunks, has_structure = self.text_chunker.chunk_text(
                safe_bill_text,
                safe_limit
            )
            if len(chunks) == 1:
                text_for_analysis = chunks[0]
                return await self._call_structured_analysis_async(text_for_analysis)
            else:
                # Create a mock legislation instance
                MockGovtEnum = type('MockEnum', (), {'value': state or "Unspecified"})()
                MockStatusEnum = type('MockEnum', (), {'value': "External"})()
                MockLegislation = type('MockLegislation', (), {
                    'id': 0,
                    'bill_number': "N/A",
                    'title': bill_title or "Unspecified",
                    'description': (
                        safe_bill_text[:500] + "..."
                        if len(safe_bill_text) > 500 
                        else safe_bill_text
                    ),
                    'govt_type': MockGovtEnum,
                    'govt_source': "External",
                    'bill_status': MockStatusEnum
                })
                mock_leg = MockLegislation()
                return await self._analyze_in_chunks_async(
                    chunks,
                    has_structure,
                    mock_leg
                )
        else:
            return await self._call_structured_analysis_async(safe_bill_text)
