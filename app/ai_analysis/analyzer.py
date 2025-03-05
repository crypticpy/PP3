"""
Core AIAnalysis class that orchestrates the bill analysis workflow.
"""

import logging
import re
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Literal, Tuple
from contextlib import contextmanager, asynccontextmanager  # Added asynccontextmanager
from threading import Lock

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from ai_analysis.errors import (
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
        self.db_session = db_session
        if db_session is None:
            raise ValueError("Database session is required")

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

    def analyze_legislation(self, legislation_id: int) -> LegislationAnalysis:
        with self._cache_lock:
            if legislation_id in self._analysis_cache:
                cache_time, cached_analysis = self._analysis_cache[legislation_id]
                cache_age_minutes = (datetime.now(timezone.utc) - cache_time).total_seconds() / 60
                if cache_age_minutes < self.config.cache_ttl_minutes:
                    logger.info(f"Using cached analysis for legislation ID={legislation_id}")
                    return cached_analysis
                else:
                    del self._analysis_cache[legislation_id]

        try:
            leg_obj = self.db_session.query(Legislation).filter_by(id=legislation_id).first()
            if leg_obj is None:
                error_msg = f"Legislation with ID={legislation_id} not found in the DB."
                logger.error(error_msg)
                raise ValueError(error_msg)

            text_rec = leg_obj.latest_text
            full_text = ""
            if text_rec is not None and isinstance(text_rec.text_content, str):
                is_binary = False
                if hasattr(text_rec, 'is_binary'):
                    is_binary = bool(text_rec.is_binary)
                if is_binary:
                    logger.warning(f"Binary content detected in LegislationText ID={text_rec.id}, using description instead")
                    full_text = leg_obj.description if leg_obj.description is not None else ""
                else:
                    full_text = text_rec.text_content
            else:
                full_text = leg_obj.description if leg_obj.description is not None else ""

            # Convert to string explicitly
            if isinstance(full_text, bytes):
                full_text = full_text.decode("utf-8")

            # Ensure full_text is a string if it's a SQLAlchemy Column
            if hasattr(full_text, 'column'):
                full_text = str(full_text)

            # Now it's safe to compute token count
            token_count = self.token_counter.count_tokens(full_text)

            if token_count > self.config.max_context_tokens:
                raise TokenLimitError(f"Token count exceeds limit of {self.config.max_context_tokens}")


            safe_limit = self.config.max_context_tokens - self.config.safety_buffer
            logger.info(f"Legislation {legislation_id} has ~{token_count} tokens (limit: {safe_limit})")

            analysis_data = None
            if token_count > safe_limit:
                logger.warning(f"Legislation {legislation_id} exceeds token limit, using intelligent chunking")
                chunks, has_structure = self.text_chunker.chunk_text(full_text, safe_limit)
                if len(chunks) == 1:
                    text_for_analysis = chunks[0]
                    analysis_data = self._call_structured_analysis(text_for_analysis)
                else:
                    analysis_data = self._analyze_in_chunks(chunks, has_structure, leg_obj)
            else:
                analysis_data = self._call_structured_analysis(full_text)

            if analysis_data is None:
                error_msg = f"Failed to generate analysis for Legislation ID={legislation_id}"
                logger.error(error_msg)
                raise AIAnalysisError(error_msg)

            result_analysis = self._store_legislation_analysis(legislation_id, analysis_data)
            with self._cache_lock:
                self._analysis_cache[legislation_id] = (datetime.now(timezone.utc), result_analysis)

            if HAS_PRIORITY_MODEL:
                self._update_legislation_priority(legislation_id, analysis_data)

            return result_analysis

        except ValueError:
            raise
        except (AIAnalysisError, DatabaseError):
            raise
        except Exception as e:
            error_msg = f"Unexpected error analyzing legislation ID={legislation_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AIAnalysisError(error_msg) from e

    def _call_structured_analysis(self, text: str, is_chunk: bool = False) -> Dict[str, Any]:
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
        return analysis_data

    def _analyze_in_chunks(self, chunks: List[str], structured: bool, leg_obj: Legislation) -> Dict[str, Any]:
        description_text = leg_obj.description if leg_obj.description is not None else ""
        govt_type_value = "unknown"
        if leg_obj.govt_type is not None:
            govt_type_value = str(getattr(leg_obj.govt_type, 'value', 'unknown'))
        status_value = "unknown"
        if hasattr(leg_obj, 'bill_status') and leg_obj.bill_status is not None:
            status_value = str(getattr(leg_obj.bill_status, 'value', 'unknown'))
        context = {
            "bill_number": leg_obj.bill_number,
            "title": leg_obj.title,
            "description": description_text,
            "govt_type": govt_type_value,
            "govt_source": leg_obj.govt_source,
            "status": status_value
        }
        cumulative_analysis = {}
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} for legislation {leg_obj.id}")
            try:
                chunk_prompt = create_chunk_prompt(
                    chunk=chunk, 
                    chunk_index=i, 
                    total_chunks=len(chunks),
                    prev_summaries=chunk_summaries,
                    legislation_metadata=context,
                    is_structured=structured
                )
                chunk_result = self._call_structured_analysis(chunk_prompt, is_chunk=True)
                if chunk_result is None:
                    logger.warning(f"Failed to analyze chunk {i+1}, continuing with partial analysis")
                    continue
                if "summary" in chunk_result:
                    chunk_summaries.append(f"Chunk {i+1} Summary: {chunk_result['summary']}")
                if i == 0:
                    cumulative_analysis = chunk_result
                else:
                    cumulative_analysis = merge_analyses(cumulative_analysis, chunk_result)
            except APIError as e:
                logger.error(f"API error analyzing chunk {i+1}: {e}")
                if i == 0:
                    raise AIAnalysisError(f"Failed to analyze legislation {leg_obj.id} - first chunk analysis failed") from e
            except Exception as e:
                logger.error(f"Error analyzing chunk {i+1}: {e}", exc_info=True)
                if i == 0:
                    raise AIAnalysisError(f"Failed to analyze legislation {leg_obj.id} - first chunk analysis failed") from e
        if not cumulative_analysis or "summary" not in cumulative_analysis:
            raise AIAnalysisError(f"Failed to generate complete analysis for legislation {leg_obj.id} after processing all chunks")
        if "summary" in cumulative_analysis and len(chunks) > 1:
            cumulative_analysis["summary"] = self._post_process_summary(cumulative_analysis["summary"], len(chunks))
        return cumulative_analysis

    def _post_process_summary(self, summary: str, chunk_count: int) -> str:
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
        self, legislation_id: int, analysis_dict: Dict[str, Any]
    ) -> LegislationAnalysis:
        if not analysis_dict:
            raise ValidationError("Cannot store empty analysis data")
        try:
            with self._db_transaction():
                existing_analyses = self.db_session.query(LegislationAnalysis).filter_by(
                    legislation_id=legislation_id
                ).all()
                if existing_analyses:
                    prev = max(
                        existing_analyses,
                        key=lambda x: x.analysis_versiin on if isinstance(x.analysis_version, int) else -1,
                        default=None
                    )
                    new_version = (prev.analysis_version or 0) + 1
                    prev_id = prev.id
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
                        logger.warning(f"Invalid impact_category value: {impact_category_str}, error: {e}")
                if impact_level_str is not None:
                    try:
                        impact_level_enum = ImpactLevelEnum(impact_level_str)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid impact_level value: {impact_level_str}, error: {e}")
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
                if hasattr(analysis_obj, 'processing_metadata'):
                    analysis_obj.processing_metadata = {
                        "date_processed": datetime.now(timezone.utc).isoformat(),
                        "model_name": self.config.model_name,
                        "software_version": "2.0.0",
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
        if not HAS_PRIORITY_MODEL:
            logger.debug("LegislationPriority model not available - skipping priority update")
            return
        try:
            priority_data = calculate_priority_scores(analysis_dict, legislation_id)
            with self._db_transaction():
                priority = self.db_session.query(LegislationPriority).filter_by(
                    legislation_id=legislation_id
                ).first()
                if priority is not None:
                    if not bool(priority.manually_reviewed):
                        priority.public_health_relevance = priority_data["public_health_relevance"]
                        priority.local_govt_relevance = priority_data["local_govt_relevance"]
                        priority.overall_priority = priority_data["overall_priority"]
                        priority.auto_categorized = True
                        priority.auto_categories = priority_data["auto_categories"]
                else:
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
            logger.warning(error_msg)

    def get_cached_analysis(self, legislation_id: int) -> Optional[LegislationAnalysis]:
        with self._cache_lock:
            if legislation_id in self._analysis_cache:
                cache_time, cached_analysis = self._analysis_cache[legislation_id]
                cache_age_minutes = (datetime.now(timezone.utc) - cache_time).total_seconds() / 60
                if cache_age_minutes < self.config.cache_ttl_minutes:
                    logger.debug(f"Using cached analysis for legislation ID={legislation_id}")
                    return cached_analysis
                else:
                    del self._analysis_cache[legislation_id]
        return None

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._analysis_cache.clear()
        logger.info("Analysis cache cleared")

    def get_token_usage_estimate(self, legislation_id: int) -> Dict[str, Any]:
        try:
            leg_obj = self.db_session.query(Legislation).filter_by(id=legislation_id).first()
            if leg_obj is None:
                raise ValueError(f"Legislation with ID={legislation_id} not found")
            text_rec = leg_obj.latest_text
            full_text = ""
            if text_rec is not None and text_rec.text_content is not None:
                is_binary = False
                if hasattr(text_rec, 'is_binary'):
                    is_binary = bool(text_rec.is_binary)
                if is_binary:
                    full_text = leg_obj.description if leg_obj.description is not None else ""
                else:
                    full_text = text_rec.text_content
            else:
                full_text = leg_obj.description if leg_obj.description is not None else ""
            if isinstance(full_text, bytes):
                full_text = full_text.decode("utf-8")
            token_count = self.token_counter.count_tokens(str(full_text)) # Modification here
            completion_estimate = min(8000, token_count // 2)
            safe_limit = self.config.max_context_tokens - self.config.safety_buffer
            chunks_needed = (token_count + safe_limit - 1) // safe_limit if token_count > 0 else 1
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
                    raise AIAnalysisError(f"Batch analysis stopped due to error on legislation ID={leg_id}: {error_msg}")
        return results

    async def analyze_legislation_async(self, legislation_id: int) -> LegislationAnalysis:
        with self._cache_lock:
            if legislation_id in self._analysis_cache:
                cache_time, cached_analysis = self._analysis_cache[legislation_id]
                cache_age_minutes = (datetime.now(timezone.utc) - cache_time).total_seconds() / 60
                if cache_age_minutes < self.config.cache_ttl_minutes:
                    logger.info(f"Using cached analysis for legislation ID={legislation_id}")
                    return cached_analysis
                else:
                    del self._analysis_cache[legislation_id]
        try:
            leg_obj = self.db_session.query(Legislation).filter_by(id=legislation_id).first()
            if leg_obj is None:
                error_msg = f"Legislation with ID={legislation_id} not found in the DB."
                logger.error(error_msg)
                raise ValueError(error_msg)
            text_rec = leg_obj.latest_text
            full_text = ""
            if text_rec is not None and text_rec.text_content is not None:
                is_binary = False
                if hasattr(text_rec, 'is_binary'):
                    is_binary = bool(text_rec.is_binary)
                if is_binary:
                    logger.warning(f"Binary content detected in LegislationText ID={text_rec.id}, using description instead")
                    full_text = leg_obj.description if leg_obj.description is not None else ""
                else:
                    full_text = text_rec.text_content
            else:
                full_text = leg_obj.description if leg_obj.description is not None else ""
                if not full_text:
                    logger.warning(f"No text content found for Legislation ID={legislation_id}")
            if isinstance(full_text, bytes):
                full_text = full_text.decode("utf-8")
            token_count = self.token_counter.count_tokens(full_text)
            safe_limit = self.config.max_context_tokens - self.config.safety_buffer
            logger.info(f"Legislation {legislation_id} has ~{token_count} tokens (limit: {safe_limit})")
            analysis_data = None
            async with self._get_async_transaction() as transaction:
                self.openai_client.set_db_session(self.db_session)
                if token_count > safe_limit:
                    logger.warning(f"Legislation {legislation_id} exceeds token limit, using intelligent chunking")
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
                if analysis_data is None:
                    error_msg = f"Failed to generate analysis for Legislation ID={legislation_id}"
                    logger.error(error_msg)
                    raise AIAnalysisError(error_msg)
                result_analysis = self._store_legislation_analysis(legislation_id, analysis_data)
                with self._cache_lock:
                    self._analysis_cache[legislation_id] = (datetime.now(timezone.utc), result_analysis)
                if HAS_PRIORITY_MODEL:
                    self._update_legislation_priority(legislation_id, analysis_data)
                return result_analysis
        except ValueError:
            raise
        except (AIAnalysisError, DatabaseError):
            raise
        except Exception as e:
            error_msg = f"Unexpected error analyzing legislation ID={legislation_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AIAnalysisError(error_msg) from e

    @asynccontextmanager
    async def _get_async_transaction(self):
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

    async def _call_structured_analysis_async(
        self, 
        text: str, 
        is_chunk: bool = False,
        transaction_ctx: Any = None
    ) -> Dict[str, Any]:
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
        description_text = leg_obj.description if leg_obj.description is not None else ""
        govt_type_value = "unknown"
        if leg_obj.govt_type is not None:
            govt_type_value = str(getattr(leg_obj.govt_type, 'value', 'unknown'))
        status_value = "unknown"
        if hasattr(leg_obj, 'bill_status') and leg_obj.bill_status is not None:
            status_value = str(getattr(leg_obj.bill_status, 'value', 'unknown'))
        context = {
            "bill_number": leg_obj.bill_number,
            "title": leg_obj.title,
            "description": description_text,
            "govt_type": govt_type_value,
            "govt_source": leg_obj.govt_source,
            "status": status_value
        }
        cumulative_analysis = {}
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} for legislation {leg_obj.id}")
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
                    chunk_prompt, is_chunk=True, transaction_ctx=transaction_ctx
                )
                if chunk_result is None:
                    logger.warning(f"Failed to analyze chunk {i+1}, continuing with partial analysis")
                    continue
                if "summary" in chunk_result:
                    chunk_summaries.append(f"Chunk {i+1} Summary: {chunk_result['summary']}")
                if i == 0:
                    cumulative_analysis = chunk_result
                else:
                    cumulative_analysis = merge_analyses(cumulative_analysis, chunk_result)
            except APIError as e:
                logger.error(f"API error analyzing chunk {i+1}: {e}")
                if i == 0:
                    raise AIAnalysisError(f"Failed to analyze legislation {leg_obj.id} - first chunk analysis failed") from e
            except Exception as e:
                logger.error(f"Error analyzing chunk {i+1}: {e}", exc_info=True)
                if i == 0:
                    raise AIAnalysisError(f"Failed to analyze legislation {leg_obj.id} - first chunk analysis failed") from e
        if not cumulative_analysis or "summary" not in cumulative_analysis:
            raise AIAnalysisError(f"Failed to generate complete analysis for legislation {leg_obj.id} after processing all chunks")
        if "summary" in cumulative_analysis and len(chunks) > 1:
            cumulative_analysis["summary"] = self._post_process_summary(cumulative_analysis["summary"], len(chunks))
        return cumulative_analysis

    async def batch_analyze_async(self, legislation_ids: List[int], max_concurrent: int = 5) -> Dict[str, Any]:
        results = {
            "total": len(legislation_ids),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "analyses": {},"errors": {}
        }
        semaphore = asyncio.Semaphore(max_concurrent)
        async def process_legislation(leg_id):
            async with semaphore:
                try:
                    cached = self.get_cached_analysis(leg_id)
                    if cached is not None:
                        return {"leg_id": leg_id, "status": "cached", "analysis": cached}
                    analysis = await self.analyze_legislation_async(leg_id)
                    return {"leg_id": leg_id, "status": "success", "analysis": analysis}
                except Exception as e:
                    return {"leg_id": leg_id, "status": "error", "error": str(e)}
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

    def analyze_bill(self, bill_text: str, bill_title: Optional[str] = None, state: Optional[str] = None) -> Dict[str, Any]:
        try:
            token_count = self.token_counter.count_tokens(bill_text)
            safe_limit = self.config.max_context_tokens - self.config.safety_buffer
            context = {
                "bill_title": bill_title or "Unspecified Bill",
                "state": state or "Unspecified"
            }
            if token_count > safe_limit:
                logger.info(f"Bill exceeds token limit ({token_count} tokens), using intelligent chunking")
                chunks, has_structure = self.text_chunker.chunk_text(bill_text, safe_limit)
                if len(chunks) == 1:
                    text_for_analysis = chunks[0]
                    return self._call_structured_analysis(text_for_analysis)
                else:
                    # Create a mock legislation instance for context by instantiating the type
                    MockLegislation = type('MockLegislation', (), {
                        'id': 0,
                        'bill_number': "N/A",
                        'title': bill_title or "Unspecified",
                        'description': bill_text[:500] + "..." if len(bill_text) > 500 else bill_text,
                        'govt_type': type('MockEnum', (), {'value': state or "Unspecified"})(),
                        'govt_source': "External",
                        'bill_status': type('MockEnum', (), {'value': "External"})()
                    })
                    mock_leg = MockLegislation()
                    return self._analyze_in_chunks(chunks, has_structure, mock_leg)
            else:
                return self._call_structured_analysis(bill_text)
        except Exception as e:
            error_msg = f"Error analyzing bill text: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AIAnalysisError(error_msg) from e