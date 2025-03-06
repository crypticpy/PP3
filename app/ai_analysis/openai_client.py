""" OpenAI client interface for making API calls with appropriate error handling. """

import os
import json
import time
import logging
import re
import asyncio
from typing import Dict, List, Any, Optional
from contextlib import contextmanager

# Import OpenAI with version checking
try:
    import openai
    from openai import OpenAI, AsyncOpenAI
    HAS_NEW_OPENAI = hasattr(openai, 'OpenAI')
    HAS_ASYNC_OPENAI = hasattr(openai, 'AsyncOpenAI')
except ImportError:
    raise ImportError(
        "Failed to import OpenAI package. Please install with: pip install openai"
    )

try:
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import SQLAlchemyError
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

from app.ai_analysis.errors import APIError, RateLimitError, AIAnalysisError, DatabaseError

logger = logging.getLogger(__name__)


class OpenAIClient:
    """ Wrapper for OpenAI API client with retry logic and error handling. """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gpt-4o-2024-08-06",
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        db_session: Optional[Any] = None,
    ):
        """
        Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key
            model_name: Name of the model to use
            max_retries: Maximum number of retry attempts
            retry_base_delay: Base delay for exponential backoff
            db_session: Optional SQLAlchemy session for transaction support
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key must be provided or set as OPENAI_API_KEY environment variable"
            )

        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.db_session = db_session

        # Initialize client based on OpenAI SDK version
        if HAS_NEW_OPENAI:
            self.client = OpenAI(api_key=self.api_key)
            if HAS_ASYNC_OPENAI:
                self.async_client = AsyncOpenAI(api_key=self.api_key)
            else:
                self.async_client = None
        else:
            openai.api_key = self.api_key
            self.client = openai
            self.async_client = None

    def set_db_session(self, db_session: Any) -> None:
        """
        Set the database session for transaction support.

        Args:
            db_session: SQLAlchemy session
        """
        self.db_session = db_session

    @contextmanager
    def transaction(self):
        """
        Provides a transaction context if a database session is available.
        If no session is available, yields a null context.

        Usage:
            with client.transaction() as transaction:
                # operations inside a transaction

        Yields:
            SQLAlchemy transaction context or null context
        """
        if HAS_SQLALCHEMY and self.db_session:
            transaction = self.db_session.begin_nested()
            try:
                yield transaction
            except Exception as e:
                logger.error(f"Error in transaction: {e}")

                if transaction.is_active:  # Make sure transaction is active before rollback
                    transaction.rollback()

                raise
            finally:
                # Ensure transaction is closed properly if not committed
                if transaction.is_active:
                    transaction.commit()

        else:
            # Null context if no session available
            try:
                yield None
            except Exception as e:
                logger.error(f"Error in null transaction context: {e}")
                raise

    def call_structured_analysis(
            self,
            messages: List[Dict[str, str]],
            json_schema: Dict[str, Any],
            temperature: float = 0.2,
            reasoning_effort: Optional[str] = None,
            max_completion_tokens: Optional[int] = None,
            store: bool = True,
            transaction_ctx: Optional[Any] = None) -> Dict[str, Any]:
        """
        Call OpenAI API with retry logic and structured output validation.

        Args:
            messages: List of message objects for the API call
            json_schema: JSON schema for structured output
            temperature: Controls randomness (0-1)
            reasoning_effort: For o-series models, control reasoning depth ("low", "medium", "high") 
            max_completion_tokens: Cap on total tokens (reasoning + visible output)
            store: Whether to store completions (set false for sensitive data)
            transaction_ctx: Optional transaction context from self.transaction()

        Returns:
            Structured analysis as a dictionary

        Raises:
            APIError: On unrecoverable API errors
            RateLimitError: On API rate limit errors
        """
        for attempt in range(self.max_retries + 1):
            try:
                # Make the API call
                start_time = time.time()

                # Handle new vs old OpenAI API
                if HAS_NEW_OPENAI:
                    params = {
                        "model": self.model_name,
                        "messages": messages,
                        "temperature": temperature,
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": json_schema
                        },
                        "max_tokens":
                        8000,  # Legacy parameter but keeping for compatibility
                        "store": store
                    }

                    # Add optional parameters if provided
                    if reasoning_effort is not None:
                        params["reasoning_effort"] = reasoning_effort
                    if max_completion_tokens is not None:
                        params["max_completion_tokens"] = max_completion_tokens

                    response = self.client.chat.completions.create(**params)
                    response_message = response.choices[0].message
                    content = response_message.content or ""
                else:
                    # Legacy OpenAI API - deprecated but keeping for compatibility
                    response = self.client.ChatCompletion.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=temperature,
                        response_format={"type": "json_object"},
                        max_tokens=8000  # Limit output tokens for safety
                    )
                    response_message = response.choices[0]["message"]
                    content = response_message.get("content", "")

                # Calculate and log API call time
                elapsed_time = time.time() - start_time
                logger.debug(f"API call completed in {elapsed_time:.2f}s")

                # Check for empty response
                if not content:
                    logger.error("OpenAI returned empty content")
                    if attempt < self.max_retries:
                        continue
                    return {}

                # Parse the JSON response
                result = self._safe_json_load(content)

                # If we're using a transaction and inside a database operation, we could
                # record the API call here if needed
                if HAS_SQLALCHEMY and self.db_session and transaction_ctx:
                    try:
                        # Example: record API usage in a transactions
                        # api_log = APICallLog(model=self.model_name, tokens_used=response.usage.total_tokens)
                        # self.db_session.add(api_log)
                        pass
                    except Exception as e:
                        logger.error(
                            f"Failed to record API call in database: {e}")
                        # We don't raise here because the API call itself succeeded

                return result

            except Exception as e:
                # Handle retry logic based on error type
                should_retry = False
                error_msg = str(e)

                # Check for rate limit errors
                if "rate limit" in error_msg.lower(
                ) or "rate_limit" in error_msg.lower():
                    error_type = "Rate limit"
                    should_retry = True
                # Check for timeout errors
                elif "timeout" in error_msg.lower():
                    error_type = "Timeout"
                    should_retry = True
                # Check for server errors
                elif "server error" in error_msg.lower(
                ) or "5xx" in error_msg.lower():
                    error_type = "Server"
                    should_retry = True
                # Check for connection errors
                elif "connection" in error_msg.lower():
                    error_type = "Connection"
                    should_retry = True
                else:
                    error_type = "API"

                if should_retry and attempt < self.max_retries:
                    delay = self.retry_base_delay * (2**attempt
                                                     )  # Exponential backoff
                    logger.warning(
                        f"{error_type} error: {e}. Retrying in {delay:.2f}s (attempt {attempt+1}/{self.max_retries})"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"{error_type} error after {attempt} attempts: {e}")

                    if "rate limit" in error_msg.lower(
                    ) or "rate_limit" in error_msg.lower():
                        raise RateLimitError(
                            f"OpenAI rate limit exceeded after {attempt} attempts: {str(e)}"
                        ) from e
                    else:
                        raise APIError(
                            f"OpenAI API error after {attempt} attempts: {str(e)}"
                        ) from e

        # This should never be reached due to the raises in the loop
        raise AIAnalysisError(
            "Failed to get a valid response after all retries")

    async def call_structured_analysis_async(
            self,
            messages: List[Dict[str, str]],
            json_schema: Dict[str, Any],
            temperature: float = 0.2,
            reasoning_effort: Optional[str] = None,
            max_completion_tokens: Optional[int] = None,
            store: bool = True,
            transaction_ctx: Optional[Any] = None) -> Dict[str, Any]:
        """
        Async version of call_structured_analysis. Call OpenAI API with retry logic and structured output validation.

        Args:
            messages: List of message objects for the API call
            json_schema: JSON schema for structured output
            temperature: Controls randomness (0-1)
            reasoning_effort: For o-series models, control reasoning depth ("low", "medium", "high") 
            max_completion_tokens: Cap on total tokens (reasoning + visible output)
            store: Whether to store completions (set false for sensitive data)
            transaction_ctx: Optional transaction context from self.transaction()

        Returns:
            Structured analysis as a dictionary

        Raises:
            APIError: On unrecoverable API errors
            RateLimitError: On API rate limit errors
            ValueError: If async client is not available
        """
        if not HAS_ASYNC_OPENAI or not self.async_client:
            raise ValueError(
                "Async OpenAI client not available. Please update your openai package."
            )

        for attempt in range(self.max_retries + 1):
            try:
                # Make the API call
                start_time = time.time()

                params = {
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": json_schema
                    },
                    "max_tokens":
                    8000,  # Legacy parameter but keeping for compatibility
                    "store": store
                }

                # Add optional parameters if provided
                if reasoning_effort is not None:
                    params["reasoning_effort"] = reasoning_effort
                if max_completion_tokens is not None:
                    params["max_completion_tokens"] = max_completion_tokens

                response = await self.async_client.chat.completions.create(
                    **params)
                response_message = response.choices[0].message
                content = response_message.content or ""

                # Calculate and log API call time
                elapsed_time = time.time() - start_time
                logger.debug(
                    f"Async API call completed in {elapsed_time:.2f}s")

                # Check for empty response
                if not content:
                    logger.error("OpenAI returned empty content")
                    if attempt < self.max_retries:
                        continue
                    return {}

                # Parse the JSON response
                result = self._safe_json_load(content)

                # If we're using a transaction and inside a database operation, we could
                # record the API call here if needed
                if HAS_SQLALCHEMY and self.db_session and transaction_ctx:
                    try:
                        # Example: record API usage in a transaction
                        # api_log = APICallLog(model=self.model_name, tokens_used=response.usage.total_tokens)
                        # self.db_session.add(api_log)
                        pass
                    except Exception as e:
                        logger.error(
                            f"Failed to record API call in database: {e}")
                        # We don't raise here because the API call itself succeeded

                return result

            except Exception as e:
                # Handle retry logic based on error type
                should_retry = False
                error_msg = str(e)

                # Check for rate limit errors
                if "rate limit" in error_msg.lower(
                ) or "rate_limit" in error_msg.lower():
                    error_type = "Rate limit"
                    should_retry = True
                # Check for timeout errors
                elif "timeout" in error_msg.lower():
                    error_type = "Timeout"
                    should_retry = True
                # Check for server errors
                elif "server error" in error_msg.lower(
                ) or "5xx" in error_msg.lower():
                    error_type = "Server"
                    should_retry = True
                # Check for connection errors
                elif "connection" in error_msg.lower():
                    error_type = "Connection"
                    should_retry = True
                else:
                    error_type = "API"

                if should_retry and attempt < self.max_retries:
                    delay = self.retry_base_delay * (2**attempt
                                                     )  # Exponential backoff
                    logger.warning(
                        f"{error_type} error: {e}. Retrying in {delay:.2f}s (attempt {attempt+1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"{error_type} error after {attempt} attempts: {e}")

                    if "rate limit" in error_msg.lower(
                    ) or "rate_limit" in error_msg.lower():
                        raise RateLimitError(
                            f"OpenAI rate limit exceeded after {attempt} attempts: {str(e)}"
                        ) from e
                    else:
                        raise APIError(
                            f"OpenAI API error after {attempt} attempts: {str(e)}"
                        ) from e

        # This should never be reached due to the raises in the loop
        raise AIAnalysisError(
            "Failed to get a valid response after all retries")

    async def batch_structured_analysis_async(
            self,
            batch_messages: List[List[Dict[str, str]]],
            json_schema: Dict[str, Any],
            temperature: float = 0.2,
            reasoning_effort: Optional[str] = None,
            max_completion_tokens: Optional[int] = None,
            store: bool = True,
            max_concurrent: int = 5,
            use_transaction: bool = True) -> List[Dict[str, Any]]:
        """
        Process multiple structured analysis requests concurrently.
        If use_transaction is True and a database session is available, all operations
        are wrapped in a single transaction.

        Args:
            batch_messages: List of message lists for each API call
            json_schema: JSON schema for structured output
            temperature: Controls randomness (0-1)
            reasoning_effort: For o-series models, control reasoning depth
            max_completion_tokens: Cap on total tokens
            store: Whether to store completions
            max_concurrent: Maximum number of concurrent requests
            use_transaction: Whether to use a database transaction for all operations

        Returns:
            List of structured analysis dictionaries in the same order as input messages

        Raises:
            ValueError: If async client is not available
        """
        if not HAS_ASYNC_OPENAI or not self.async_client:
            raise ValueError(
                "Async OpenAI client not available. Please update your openai package."
            )

        # If using a transaction and we have a database session
        if use_transaction and HAS_SQLALCHEMY and self.db_session:
            with self.transaction() as transaction:
                results = await self._execute_batch_requests(
                    batch_messages, json_schema, temperature, reasoning_effort,
                    max_completion_tokens, store, max_concurrent, transaction)
                return results
        else:
            # Execute without transaction
            results = await self._execute_batch_requests(
                batch_messages, json_schema, temperature, reasoning_effort,
                max_completion_tokens, store, max_concurrent, None)
            return results

    async def _execute_batch_requests(
            self, batch_messages: List[List[Dict[str, str]]],
            json_schema: Dict[str, Any], temperature: float,
            reasoning_effort: Optional[str],
            max_completion_tokens: Optional[int], store: bool,
            max_concurrent: int,
            transaction: Optional[Any]) -> List[Dict[str, Any]]:
        """
        Execute a batch of requests with concurrency control.

        Args:
            batch_messages: List of message lists for each API call
            json_schema: JSON schema for structured output
            temperature: Controls randomness (0-1)
            reasoning_effort: For o-series models, control reasoning depth
            max_completion_tokens: Cap on total tokens
            store: Whether to store completions
            max_concurrent: Maximum number of concurrent requests
            transaction: Optional transaction context

        Returns:
            List of results in the same order as input messages
        """
        # Create a semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(messages):
            async with semaphore:
                return await self.call_structured_analysis_async(
                    messages=messages,
                    json_schema=json_schema,
                    temperature=temperature,
                    reasoning_effort=reasoning_effort,
                    max_completion_tokens=max_completion_tokens,
                    store=store,
                    transaction_ctx=transaction)

        # Create tasks for all message sets
        tasks = [
            process_with_semaphore(messages) for messages in batch_messages
        ]

        # Execute all tasks concurrently and gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, converting exceptions to empty dictionaries with error info
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error in batch request {i}: {str(result)}")
                processed_results.append({
                    "error": str(result),
                    "error_type": type(result).__name__
                })
            else:
                processed_results.append(result)

        return processed_results

    def _safe_json_load(self, content: str) -> Dict[str, Any]:
        """
        Safely loads JSON from a string, handling various formats.

        Args:
            content: String containing JSON data (possibly with markdown or other formatting)

        Returns:
            Parsed JSON as a dictionary, or empty dict on error
        """
        if not content or not isinstance(content, str):
            logger.warning(
                "Empty or non-string content provided to JSON parser")
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
