"""
legiscan_api.py

Contains the LegiScanAPI class which fetches data from the LegiScan API
and stores/updates it in the local database, with a focus on US Congress and 
Texas legislation relevant to public health and local government.

This module:
1. Provides methods to interact with the LegiScan API with proper rate limiting and error handling
2. Converts API responses into database records (Legislation, LegislationText, LegislationSponsor)
3. Calculates relevance scores for Texas public health and local government impacts
4. Manages sync operations to keep the database up-to-date with LegiScan
"""

import os
import time
import logging
import requests
import base64
import sys
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple, Set, Union, cast
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, update
from sqlalchemy.exc import SQLAlchemyError

from app.models import (
    Legislation,
    LegislationText,
    LegislationSponsor,
    DataSourceEnum,
    GovtTypeEnum,
    BillStatusEnum,
    SyncMetadata,
    SyncStatusEnum,
    SyncError
)

# Check if optional models are available
try:
    from app.models import LegislationPriority
    HAS_PRIORITY_MODEL = True
except ImportError:
    HAS_PRIORITY_MODEL = False

try:
    from app.models import Amendment, AmendmentStatusEnum
    HAS_AMENDMENT_MODEL = True
except ImportError:
    HAS_AMENDMENT_MODEL = False


logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Custom exception for LegiScan API errors."""
    pass


class RateLimitError(ApiError):
    """Custom exception for rate limiting errors."""
    pass


@dataclass
class LegiScanConfig:
    """Configuration settings for LegiScan API."""
    api_key: str
    base_url: str = "https://api.legiscan.com/"
    rate_limit_delay: float = 1.0
    max_retries: int = 3
    timeout: int = 30


class LegiScanAPI:
    """
    Client for interacting with the LegiScan API and storing/updating 
    legislation data in the local database.

    Focuses on US Congress and Texas legislation with special attention to
    bills relevant to public health and local government.
    """

    def __init__(self, db_session: Session, api_key: Optional[str] = None):
        """
        Initialize the LegiScan API client.

        Args:
            db_session: SQLAlchemy session for database operations
            api_key: Optional API key (uses LEGISCAN_API_KEY env var if not provided)

        Raises:
            ValueError: If no API key is available
        """
        self.api_key = api_key or os.environ.get("LEGISCAN_API_KEY")
        if not self.api_key:
            raise ValueError("LEGISCAN_API_KEY not set. Please set the LEGISCAN_API_KEY environment variable.")

        self.config = LegiScanConfig(
            api_key=self.api_key,
            base_url="https://api.legiscan.com/",
            rate_limit_delay=1.0,
            max_retries=3,
            timeout=30
        )

        self.db_session = db_session

        # Rate limiting controls
        self.last_request = datetime.now(timezone.utc)

        # Texas & US focus
        self.monitored_jurisdictions = ["US", "TX"]

        # Public health relevance keywords for prioritization
        self.health_keywords = [
            "health", "healthcare", "public health", "medicaid", "medicare", "hospital", 
            "physician", "vaccine", "immunization", "disease", "epidemic", "public health emergency",
            "mental health", "substance abuse", "addiction", "opioid", "healthcare workforce" 
        ]

        # Local government relevance keywords for prioritization
        self.local_govt_keywords = [
            "municipal", "county", "local government", "city council", "zoning", 
            "property tax", "infrastructure", "public works", "community development", 
            "ordinance", "school district", "special district", "county commissioner"
        ]

    def _throttle_request(self) -> None:
        """
        Implements rate limiting to avoid overwhelming the LegiScan API.
        Ensures requests are spaced by at least rate_limit_delay seconds.
        """
        elapsed = (datetime.now(timezone.utc) - self.last_request).total_seconds()
        if elapsed < self.config.rate_limit_delay:
            time.sleep(self.config.rate_limit_delay - elapsed)

    def _make_request(self, operation: str, params: Optional[Dict[str, Any]] = None, retries: Optional[int] = None) -> Dict[str, Any]:
        """
        Makes a request to the LegiScan API with rate limiting and retry logic.

        Args:
            operation: LegiScan API operation to perform
            params: Optional parameters for the API call
            retries: Number of retry attempts on failure (defaults to config value)

        Returns:
            JSON response data

        Raises:
            ApiError: If the API request fails after retries or returns an error
            RateLimitError: If rate limiting is encountered
        """
        self._throttle_request()

        if params is None:
            params = {}
        params["key"] = self.api_key
        params["op"] = operation

        max_retries = self.config.max_retries if retries is None else retries

        # Implement retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                resp = requests.get(
                    self.config.base_url, 
                    params=params, 
                    timeout=self.config.timeout
                )
                self.last_request = datetime.now(timezone.utc)
                resp.raise_for_status()

                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON response from LegiScan API: {resp.text[:100]}...")
                    raise ApiError("Invalid JSON response from LegiScan API")

                if data.get("status") != "OK":
                    err_msg = data.get("alert", {}).get("message", "Unknown error from LegiScan")
                    logger.warning(f"LegiScan API returned error: {err_msg}")

                    # Check if we should retry based on error message
                    if "rate limit" in err_msg.lower():
                        wait_time = 5 * (2 ** attempt)  # Exponential backoff
                        logger.info(f"Rate limited. Waiting {wait_time}s before retry {attempt+1}/{max_retries}")
                        time.sleep(wait_time)
                        if attempt == max_retries - 1:
                            raise RateLimitError(f"LegiScan API rate limit exceeded after {max_retries} retries")
                        continue

                    raise ApiError(f"LegiScan API error: {err_msg}")

                return data

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"API request failed (attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API request failed after {max_retries} attempts: {e}")
                    raise ApiError(f"API request failed: {e}")

        # This should never be reached due to the raise in the loop
        raise ApiError("API request failed: Maximum retries exceeded")

    # ------------------------------------------------------------------------
    # Common calls to LegiScan
    # ------------------------------------------------------------------------
    def get_session_list(self, state: str) -> List[Dict[str, Any]]:
        """
        Retrieves available legislative sessions for a state.

        Args:
            state: Two-letter state code

        Returns:
            List of session information dictionaries
        """
        try:
            data = self._make_request("getSessionList", {"state": state})
            return data.get("sessions", [])
        except ApiError as e:
            logger.error(f"get_session_list({state}) failed: {e}")
            return []

    def get_master_list(self, session_id: int) -> Dict[str, Any]:
        """
        Retrieves the full master bill list for a session.

        Args:
            session_id: LegiScan session ID

        Returns:
            Dictionary of bill information
        """
        try:
            data = self._make_request("getMasterList", {"id": session_id})
            return data.get("masterlist", {})
        except ApiError as e:
            logger.error(f"get_master_list({session_id}) failed: {e}")
            return {}

    def get_master_list_raw(self, session_id: int) -> Dict[str, Any]:
        """
        Retrieves the optimized master bill list for change detection.
        The raw version includes change_hash values for efficient updates.

        Args:
            session_id: LegiScan session ID

        Returns:
            Dictionary of bill information with change_hash values
        """
        try:
            data = self._make_request("getMasterListRaw", {"id": session_id})
            return data.get("masterlist", {})
        except ApiError as e:
            logger.error(f"get_master_list_raw({session_id}) failed: {e}")
            return {}

    def get_bill(self, bill_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves detailed information for a specific bill.

        Args:
            bill_id: LegiScan bill ID

        Returns:
            Dictionary with bill details or None if not found
        """
        try:
            data = self._make_request("getBill", {"id": bill_id})
            bill_data = data.get("bill")

            # Validate essential bill data
            if bill_data and self._validate_bill_data(bill_data):
                return bill_data
            else:
                logger.warning(f"Invalid or incomplete bill data received for bill_id={bill_id}")
                return None
        except ApiError as e:
            logger.error(f"get_bill({bill_id}) failed: {e}")
            return None

    def _validate_bill_data(self, bill_data: Dict[str, Any]) -> bool:
        """
        Validates that essential fields are present in the bill data.

        Args:
            bill_data: Bill data from LegiScan API

        Returns:
            True if all required fields are present, False otherwise
        """
        required_fields = ["bill_id", "state", "bill_number", "title"]
        return all(field in bill_data for field in required_fields)

    def get_bill_text(self, doc_id: int) -> Optional[Union[str, bytes]]:
        """
        Retrieves the text content of a bill document.

        Args:
            doc_id: LegiScan document ID

        Returns:
            Decoded text content (str) for text documents,
            raw bytes for binary content (e.g., PDFs), or
            None if retrieval fails
        """
        try:
            data = self._make_request("getBillText", {"id": doc_id})
            text_obj = data.get("text", {})
            encoded = text_obj.get("doc")
            if encoded:
                # LegiScan can return PDF or Word doc in base64
                try:
                    # First try to decode as UTF-8 text
                    decoded_bytes = base64.b64decode(encoded)

                    # Check if content appears to be a binary format (PDF, DOC, etc.)
                    # Common binary file signatures
                    binary_signatures = [
                        b'%PDF-',  # PDF
                        b'\xD0\xCF\x11\xE0',  # MS Office
                        b'PK\x03\x04'  # ZIP (often used for DOCX, XLSX)
                    ]

                    if any(decoded_bytes.startswith(sig) for sig in binary_signatures):
                        # Return as binary data with content type
                        return decoded_bytes
                    else:
                        # Attempt to decode as text
                        return decoded_bytes.decode("utf-8", errors="ignore")
                except Exception as e:
                    logger.warning(f"Error decoding document {doc_id}: {e}")
                    # Return raw bytes as fallback
                    return base64.b64decode(encoded)
            return None
        except ApiError as e:
            logger.error(f"get_bill_text({doc_id}) failed: {e}")
            return None

    # ------------------------------------------------------------------------
    # DB Save/Update
    # ------------------------------------------------------------------------
    def save_bill_to_db(self, bill_data: Dict[str, Any], detect_relevance: bool = True) -> Optional[Legislation]:
        """
        Creates or updates a bill record in the database based on LegiScan data.

        Args:
            bill_data: Bill information from LegiScan API
            detect_relevance: Whether to calculate relevance scores for Texas public health

        Returns:
            Updated or created Legislation object, or None on failure
        """
        if not bill_data or not self._validate_bill_data(bill_data):
            logger.warning("Invalid bill data provided to save_bill_to_db")
            return None

        try:
            # Check if we are monitoring this state
            if bill_data.get("state") not in self.monitored_jurisdictions:
                logger.debug(f"Skipping bill from unmonitored state: {bill_data.get('state')}")
                return None

            # Convert LegiScan's "state" to GovtTypeEnum
            govt_type = GovtTypeEnum.FEDERAL if bill_data["state"] == "US" else GovtTypeEnum.STATE
            external_id = str(bill_data["bill_id"])

            # Start a transaction
            transaction = self.db_session.begin_nested()

            try:
                # Check if bill already exists
                existing = self.db_session.query(Legislation).filter(
                    and_(
                        Legislation.data_source == DataSourceEnum.LEGISCAN,
                        Legislation.external_id == external_id
                    )
                ).first()

                # Map the status numeric ID to BillStatusEnum
                new_status = self._map_bill_status(bill_data.get("status"))

                # Build the upsert attributes
                attrs = {
                    "external_id": external_id,
                    "data_source": DataSourceEnum.LEGISCAN,
                    "govt_type": govt_type,
                    "govt_source": bill_data.get("session", {}).get("session_name", "Unknown Session"),
                    "bill_number": bill_data.get("bill_number", ""),
                    "bill_type": bill_data.get("bill_type"),
                    "title": bill_data.get("title", ""),
                    "description": bill_data.get("description", ""),
                    "bill_status": new_status,
                    "url": bill_data.get("url"),
                    "state_link": bill_data.get("state_link"),
                    "change_hash": bill_data.get("change_hash"),
                    "raw_api_response": bill_data,
                }

                # Convert date strings if available
                introduced_str = bill_data.get("introduced_date", "")
                if introduced_str:
                    try:
                        attrs["bill_introduced_date"] = datetime.strptime(introduced_str, "%Y-%m-%d")
                    except ValueError:
                        logger.warning(f"Invalid introduced_date format: {introduced_str}")

                status_str = bill_data.get("status_date", "")
                if status_str:
                    try:
                        attrs["bill_status_date"] = datetime.strptime(status_str, "%Y-%m-%d")
                    except ValueError:
                        logger.warning(f"Invalid status_date format: {status_str}")

                last_action_str = bill_data.get("last_action_date", "")
                if last_action_str:
                    try:
                        attrs["bill_last_action_date"] = datetime.strptime(last_action_str, "%Y-%m-%d")
                    except ValueError:
                        logger.warning(f"Invalid last_action_date format: {last_action_str}")

                # Track when we last checked this bill
                attrs["last_api_check"] = datetime.utcnow()

                if existing:
                    # Update existing record
                    for k, v in attrs.items():
                        setattr(existing, k, v)
                    bill_obj = existing
                else:
                    # Create new record
                    bill_obj = Legislation(**attrs)
                    self.db_session.add(bill_obj)

                # Flush to get bill_obj.id if it's a new record
                self.db_session.flush()

                # Save sponsors
                self._save_sponsors(bill_obj, bill_data.get("sponsors", []))

                # Save bill text if present
                self._save_legislation_texts(bill_obj, bill_data.get("texts", []))

                # Calculate relevance scores if requested
                if detect_relevance and HAS_PRIORITY_MODEL:
                    self._calculate_bill_relevance(bill_obj)

                # Process amendments if present
                if "amendments" in bill_data and bill_data["amendments"]:
                    self._track_amendments(bill_obj, bill_data["amendments"])

                # Commit all changes
                transaction.commit()
                return bill_obj

            except Exception as e:
                transaction.rollback()
                raise e

        except SQLAlchemyError as e:
            logger.error(f"Database error in save_bill_to_db: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Error in save_bill_to_db: {e}", exc_info=True)
            return None

    def _calculate_bill_relevance(self, bill_obj: Legislation) -> None:
        """
        Calculate relevance scores for Texas public health and local government.
        Updates or creates a LegislationPriority record.

        Args:
            bill_obj: Legislation database object
        """
        # First check if LegislationPriority is available
        if not HAS_PRIORITY_MODEL:
            logger.warning("Cannot calculate bill relevance: LegislationPriority model not available")
            return

        combined_text = f"{bill_obj.title} {bill_obj.description}"

        # Calculate health relevance score
        health_score = 0
        for keyword in self.health_keywords:
            if keyword.lower() in combined_text.lower():
                health_score += 10

        # Calculate local government relevance score        
        local_govt_score = 0
        for keyword in self.local_govt_keywords:
            if keyword.lower() in combined_text.lower():
                local_govt_score += 10

        # Cap scores at 100
        health_score = min(100, health_score)
        local_govt_score = min(100, local_govt_score)

        # Calculate overall priority as average of the two
        overall_score = (health_score + local_govt_score) // 2

        # Now that we've checked HAS_PRIORITY_MODEL, we can safely import the model
        from app.models import LegislationPriority

        # Set priority scores
        if hasattr(bill_obj, 'priority') and bill_obj.priority:
            bill_obj.priority.public_health_relevance = health_score
            bill_obj.priority.local_govt_relevance = local_govt_score
            bill_obj.priority.overall_priority = overall_score
            bill_obj.priority.auto_categorized = True
        else:
            # Create new priority record
            priority = LegislationPriority(
                legislation_id=bill_obj.id,
                public_health_relevance=health_score,
                local_govt_relevance=local_govt_score,
                overall_priority=overall_score,
                auto_categorized=True,
                auto_categories={"health": health_score > 30, "local_govt": local_govt_score > 30}
            )
            self.db_session.add(priority)

    def _save_sponsors(self, bill: Legislation, sponsors: List[Dict[str, Any]]) -> None:
        """
        Saves or updates bill sponsors.

        Args:
            bill: Legislation database object
            sponsors: List of sponsor dictionaries from LegiScan
        """
        # Clear old sponsors
        self.db_session.query(LegislationSponsor).filter(
            LegislationSponsor.legislation_id == bill.id
        ).delete()

        # Add new sponsors
        for sp in sponsors:
            sponsor_obj = LegislationSponsor(
                legislation_id=bill.id,
                sponsor_external_id=str(sp.get("people_id", "")),
                sponsor_name=sp.get("name", ""),
                sponsor_title=sp.get("role", ""),
                sponsor_state=sp.get("district", ""),
                sponsor_party=sp.get("party", ""),
                sponsor_type=str(sp.get("sponsor_type", "")),
            )
            self.db_session.add(sponsor_obj)
        self.db_session.flush()

    def _save_legislation_texts(self, bill: Legislation, texts: List[Dict[str, Any]]) -> None:
        """
        Saves or updates bill text versions.

        Args:
            bill: Legislation database object
            texts: List of text version dictionaries from LegiScan
        """
        for text_info in texts:
            version_num = text_info.get("version", 1)

            # Check if this text version already exists
            existing = self.db_session.query(LegislationText).filter_by(
                legislation_id=bill.id,
                version_num=version_num
            ).first()

            # Parse text date
            text_date_str = text_info.get("date", "")
            text_date = datetime.utcnow()
            if text_date_str:
                try:
                    text_date = datetime.strptime(text_date_str, "%Y-%m-%d")
                except ValueError:
                    logger.warning(f"Invalid text date format: {text_date_str}")

            # Pre-fetch text content if missing and document is important
            # This helps avoid making extra API calls later when analyzing legislation
            doc_id = text_info.get("doc_id")
            content = None
            content_is_binary = False

            # For version 1 (introduced) or final versions, we'll retrieve the text now
            if doc_id and (version_num == 1 or text_info.get("type") in ("Enrolled", "Chaptered")):
                doc_base64 = text_info.get("doc")
                if not doc_base64:  # If doc not included in API response
                    try:
                        # Attempt to get the text content now
                        content = self.get_bill_text(doc_id)
                        # Check if content is binary
                        content_is_binary = isinstance(content, bytes)
                    except Exception as e:
                        logger.error(f"Failed to fetch text for bill {bill.id}, doc_id {doc_id}: {e}")
                else:
                    # Decode provided base64 content
                    try:
                        decoded_content = base64.b64decode(doc_base64)
                        # Try to decode as UTF-8 text
                        try:
                            content = decoded_content.decode("utf-8", errors="ignore")
                        except UnicodeDecodeError:
                            # Store as binary if can't decode
                            content = decoded_content
                            content_is_binary = True
                    except Exception as e:
                        logger.error(f"Failed to decode text for bill {bill.id}, doc_id {doc_id}: {e}")

            # Prepare attributes for insert/update
            attrs = {
                "legislation_id": bill.id,
                "version_num": version_num,
                "text_type": text_info.get("type", ""),
                "text_date": text_date,
                "text_hash": text_info.get("text_hash"),
            }

            # Add content if available
            if content is not None:
                attrs["text_content"] = content
                # If binary content, store metadata about the content type
                if content_is_binary:
                    # Store content type in metadata if we have it
                    text_metadata = {'is_binary': True}
                    if hasattr(LegislationText, 'text_metadata'):
                        attrs["text_metadata"] = text_metadata

            # Update or insert
            if existing:
                for k, v in attrs.items():
                    setattr(existing, k, v)
            else:
                new_text = LegislationText(**attrs)
                self.db_session.add(new_text)

        self.db_session.flush()

    def _map_bill_status(self, status_val) -> BillStatusEnum:
        """
        Maps LegiScan numeric status to BillStatusEnum.

        Args:
            status_val: LegiScan status value

        Returns:
            Corresponding BillStatusEnum value
        """
        if not status_val:
            return BillStatusEnum.NEW

        mapping = {
            "1": BillStatusEnum.INTRODUCED,
            "2": BillStatusEnum.UPDATED,
            "3": BillStatusEnum.UPDATED,
            "4": BillStatusEnum.PASSED,
            "5": BillStatusEnum.VETOED,
            "6": BillStatusEnum.DEFEATED,
            "7": BillStatusEnum.ENACTED
        }
        # Convert to string to ensure lookup works with different input types
        status_str = str(status_val)
        return mapping.get(status_str, BillStatusEnum.UPDATED)

    def _track_amendments(self, bill: Legislation, amendments: List[Dict[str, Any]]) -> int:
        """
        Track amendments back to their parent bills.

        Args:
            bill: Parent legislation object
            amendments: List of amendment data from LegiScan

        Returns:
            Number of amendments processed
        """
        processed_count = 0

        # Start a nested transaction for amendment processing
        with self.db_session.begin_nested():
            # Process each amendment
            for amend_data in amendments:
                amendment_id = amend_data.get("amendment_id")
                if not amendment_id:
                    continue

                # If Amendment model is available, use it
                if HAS_AMENDMENT_MODEL:
                    # Import models within the conditional block to ensure they exist
                    from app.models import Amendment, AmendmentStatusEnum

                    # Check if amendment already exists
                    existing = self.db_session.query(Amendment).filter_by(
                        amendment_id=str(amendment_id),
                        legislation_id=bill.id
                    ).first()

                    # Parse amendment date
                    amend_date = None
                    date_str = amend_data.get("date")
                    if date_str and isinstance(date_str, str):
                        try:
                            amend_date = datetime.strptime(date_str, "%Y-%m-%d")
                        except ValueError:
                            logger.warning(f"Invalid amendment date format: {date_str}")

                    # Convert adopted flag to boolean
                    is_adopted = bool(amend_data.get("adopted", 0))

                    # Determine status enum value
                    status_value = AmendmentStatusEnum.ADOPTED if is_adopted else AmendmentStatusEnum.PROPOSED

                    if existing:
                        # Update existing record - use setattr to avoid type checking issues
                        # with SQLAlchemy Column attributes
                        setattr(existing, 'adopted', is_adopted)
                        setattr(existing, 'status', status_value)
                        setattr(existing, 'amendment_date', amend_date)
                        setattr(existing, 'title', amend_data.get("title", ""))
                        setattr(existing, 'description', amend_data.get("description", ""))
                        setattr(existing, 'amendment_hash', amend_data.get("amendment_hash", ""))
                    else:
                        # Create new record
                        new_amendment = Amendment(
                            amendment_id=str(amendment_id),
                            legislation_id=bill.id,
                            adopted=is_adopted,
                            status=status_value,
                            amendment_date=amend_date,
                            title=amend_data.get("title", ""),
                            description=amend_data.get("description", ""),
                            amendment_hash=amend_data.get("amendment_hash", ""),
                            amendment_url=amend_data.get("state_link")
                        )
                        self.db_session.add(new_amendment)
                else:
                # Store amendments in raw_api_response if Amendment model not available
                    try:
                        # Get the current raw_api_response, defaulting to empty dict
                        raw_data = {}
                        if bill.raw_api_response is not None:
                            # Try to convert to dict if it's JSON data
                            if hasattr(bill.raw_api_response, 'items'):  # Check if dict-like
                                raw_data = dict(bill.raw_api_response)
                            elif isinstance(bill.raw_api_response, str):
                                import json
                                raw_data = json.loads(bill.raw_api_response)
                            else:
                                # Convert other types to dict if possible
                                raw_data = dict(bill.raw_api_response) if hasattr(bill.raw_api_response, '__iter__') else {}

                        # Ensure amendments is a list
                        if "amendments" not in raw_data:
                            raw_data["amendments"] = []
                        elif not isinstance(raw_data["amendments"], list):
                            raw_data["amendments"] = []

                        # Check if this amendment is already tracked
                        amendments_list = raw_data["amendments"]
                        existing_ids = []
                        for a in amendments_list:
                            if isinstance(a, dict) and "amendment_id" in a:
                                existing_ids.append(a.get("amendment_id"))

                        # Add the new amendment if not already tracked
                        if amendment_id not in existing_ids:
                            amendments_list.append(amend_data)

                            # Use setattr to update the raw_api_response
                            setattr(bill, "raw_api_response", raw_data)

                    except Exception as e:
                        logger.warning(f"Error storing amendment in raw_api_response: {e}")

                    processed_count += 1

        return processed_count

    # ------------------------------------------------------------------------
    # Sync Operations
    # ------------------------------------------------------------------------
    def run_sync(self, sync_type: str = "daily") -> Dict[str, Any]:
        """
        Runs a complete sync operation for all monitored jurisdictions.

        Args:
            sync_type: Type of sync (e.g., "daily", "weekly", "manual")

        Returns:
            Dictionary with sync statistics and status including:
            - new_bills: Number of new bills added
            - bills_updated: Number of bills updated
            - errors: List of error messages
            - start_time: When the sync started
            - end_time: When the sync completed
            - status: Final status of the sync operation
            - amendments_tracked: Number of amendments processed
        """
        sync_start = datetime.utcnow()

        # Create a sync metadata record
        sync_meta = SyncMetadata(
            last_sync=sync_start,
            status=SyncStatusEnum.IN_PROGRESS,
            sync_type=sync_type
        )
        self.db_session.add(sync_meta)
        self.db_session.commit()

        summary = {
            "new_bills": 0,
            "bills_updated": 0,
            "errors": [],
            "start_time": sync_start,
            "end_time": None,
            "status": "in_progress",
            "amendments_tracked": 0
        }

        try:
            # Process each jurisdiction
            for state in self.monitored_jurisdictions:
                # Get active sessions
                active_sessions = self._get_active_sessions(state)

                for session in active_sessions:
                    session_id = session.get("session_id")
                    if not session_id:
                        continue

                    # Get the master bill list with change_hash
                    master_list = self.get_master_list_raw(session_id)
                    if not master_list:
                        summary["errors"].append(f"Failed to get master list for session {session_id}")
                        continue

                    # Get list of bills that need updating
                    changed_bill_ids = self._identify_changed_bills(master_list)

                    # Process each changed bill
                    for bill_id in changed_bill_ids:
                        try:
                            bill_data = self.get_bill(bill_id)
                            if not bill_data:
                                continue

                            bill_obj = self.save_bill_to_db(bill_data, detect_relevance=True)

                            if bill_obj:
                                if bill_obj.created_at == bill_obj.updated_at:
                                    summary["new_bills"] += 1
                                else:
                                    summary["bills_updated"] += 1

                                # Track amendments if present
                                if "amendments" in bill_data and bill_data["amendments"]:
                                    amendments_count = self._track_amendments(bill_obj, bill_data["amendments"])
                                    summary["amendments_tracked"] += amendments_count

                        except Exception as e:
                            error_msg = f"Error processing bill {bill_id}: {str(e)}"
                            logger.error(error_msg)
                            summary["errors"].append(error_msg)

                            # Record the error
                            sync_error = SyncError(
                                sync_id=sync_meta.id,
                                error_type="bill_processing",
                                error_message=error_msg
                            )
                            self.db_session.add(sync_error)
                            self.db_session.commit()

            # Update sync metadata
            sync_meta.bills_updated = summary["bills_updated"]
            sync_meta.new_bills = summary["new_bills"]
            # Use setattr to avoid SQLAlchemy Column assignment issues
            setattr(sync_meta, "last_successful_sync", datetime.now(timezone.utc))

            if summary["errors"]:
                setattr(sync_meta, 'status', SyncStatusEnum.PARTIAL)
                setattr(sync_meta, 'errors', {"count": len(summary["errors"]), "samples": summary["errors"][:5]})
            else:
                setattr(sync_meta, "status", SyncStatusEnum.COMPLETED)
            summary["status"] = str(sync_meta.status)
            summary["end_time"] = datetime.utcnow()

        except Exception as e:
            # Handle critical errors
            error_msg = f"Fatal error in sync operation: {str(e)}"
            logger.error(error_msg, exc_info=True)

            sync_meta.status = SyncStatusEnum.FAILED
            setattr(sync_meta, 'errors', {"critical_error": error_msg})

            sync_error = SyncError(
                sync_id=sync_meta.id,
                error_type="fatal_error",
                error_message=error_msg,
                stack_trace=str(sys.exc_info())
            )
            self.db_session.add(sync_error)

            summary["status"] = "failed"
            summary["errors"].append(error_msg)
            summary["end_time"] = datetime.utcnow()

        finally:
            # Ensure we commit any pending changes
            try:
                self.db_session.commit()
            except SQLAlchemyError as e:
                logger.error(f"Failed to commit sync metadata updates: {e}")
                self.db_session.rollback()

        return summary

    def _get_active_sessions(self, state: str) -> List[Dict[str, Any]]:
        """
        Gets active legislative sessions for a state.

        Args:
            state: Two-letter state code

        Returns:
            List of active session dictionaries
        """
        sessions = self.get_session_list(state)
        active_sessions = []

        current_year = datetime.now().year

        for session in sessions:
            # Consider active if year_end is current year or later,
            # or if sine_die is 0 (session not adjourned)
            if (session.get("year_end", 0) >= current_year or 
                session.get("sine_die", 1) == 0):
                active_sessions.append(session)

        return active_sessions

    def _identify_changed_bills(self, master_list: Dict[str, Any]) -> List[int]:
        """
        Identifies bills that need updating based on change_hash comparison.

        Args:
            master_list: Master bill list from LegiScan API

        Returns:
            List of bill IDs that need updating
        """
        if not master_list:
            return []

        changed_bill_ids = []

        for key, bill_info in master_list.items():
            if key == "0":  # Skip metadata
                continue

            bill_id = bill_info.get("bill_id")
            change_hash = bill_info.get("change_hash")

            if not bill_id or not change_hash:
                continue

            # Check if we have this bill and if the change_hash is different
            existing = self.db_session.query(Legislation).filter(
                Legislation.external_id == str(bill_id),
                Legislation.data_source == DataSourceEnum.LEGISCAN
            ).first()

            if not existing or existing.change_hash != change_hash:
                changed_bill_ids.append(bill_id)

        return changed_bill_ids

    def lookup_bills_by_keywords(self, keywords: List[str], limit: int = 100) -> List[Dict[str, Any]]:
        """
        Searches for bills matching the given keywords using LegiScan's search API.

        Args:
            keywords: List of keywords to search for
            limit: Maximum number of results to return

        Returns:
            List of bill information dictionaries
        """
        if not keywords:
            return []

        results = []
        query = " AND ".join(keywords)

        # Search in monitored jurisdictions
        for state in self.monitored_jurisdictions:
            try:
                # Start with state-specific search
                data = self._make_request("getSearchRaw", {
                    "state": state,
                    "query": query,
                    "year": 2  # Current sessions
                })

                search_results = data.get("searchresult", {})

                # Skip the summary info
                for key, item in search_results.items():
                    if key != "summary" and isinstance(item, dict):
                        results.append({
                            "bill_id": item.get("bill_id"),
                            "change_hash": item.get("change_hash"),
                            "relevance": item.get("relevance", 0),
                            "state": state,
                            "bill_number": item.get("bill_number"),
                            "title": item.get("title", "")
                        })

                        if len(results) >= limit:
                            break

            except Exception as e:
                logger.error(f"Error searching bills with keywords {keywords} in {state}: {e}")

        return results

    def get_bill_relevance_score(self, bill_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Calculates relevance scores for public health and local government.

        Args:
            bill_data: Bill information dictionary

        Returns:
            Dictionary with relevance scores for health, local government, and overall
        """
        if not bill_data:
            return {"health_relevance": 0, "local_govt_relevance": 0, "overall_relevance": 0}

        combined_text = f"{bill_data.get('title', '')} {bill_data.get('description', '')}"

        # Calculate health relevance
        health_score = 0
        for keyword in self.health_keywords:
            if keyword.lower() in combined_text.lower():
                health_score += 10

        # Calculate local government relevance
        local_govt_score = 0
        for keyword in self.local_govt_keywords:
            if keyword.lower() in combined_text.lower():
                local_govt_score += 10

        # Cap scores at 100
        health_score = min(100, health_score)
        local_govt_score = min(100, local_govt_score)

        return {
            "health_relevance": health_score,
            "local_govt_relevance": local_govt_score,
            "overall_relevance": (health_score + local_govt_score) // 2
        }

    def get_relevant_texas_legislation(self, relevance_type: str = "health", min_score: int = 50, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieves legislation particularly relevant to Texas public health or local government.

        Args:
            relevance_type: Type of relevance to filter by ("health", "local_govt", or "both")
            min_score: Minimum relevance score (0-100)
            limit: Maximum number of results to return

        Returns:
            List of relevant legislation dictionaries
        """
        try:
            # Skip if LegislationPriority is not available
            if not HAS_PRIORITY_MODEL:
                logger.warning("Cannot get relevant Texas legislation: LegislationPriority model not available")
                return []

            # Build the query based on relevance type
            query = self.db_session.query(Legislation).join(
                LegislationPriority,
                Legislation.id == LegislationPriority.legislation_id
            )

            # Filter by Texas
            query = query.filter(
                or_(
                    and_(
                        Legislation.govt_type == GovtTypeEnum.STATE,
                        Legislation.govt_source.ilike("%Texas%")
                    ),
                    Legislation.govt_type == GovtTypeEnum.FEDERAL
                )
            )

            # Apply relevance filter
            if relevance_type == "health":
                query = query.filter(LegislationPriority.public_health_relevance >= min_score)
                query = query.order_by(LegislationPriority.public_health_relevance.desc())
            elif relevance_type == "local_govt":
                query = query.filter(LegislationPriority.local_govt_relevance >= min_score)
                query = query.order_by(LegislationPriority.local_govt_relevance.desc())
            else:  # "both" or any other value
                query = query.filter(
                    or_(
                        LegislationPriority.public_health_relevance >= min_score,
                        LegislationPriority.local_govt_relevance >= min_score
                    )
                )
                query = query.order_by(LegislationPriority.overall_priority.desc())

            # Get results
            legislation_list = query.limit(limit).all()

            # Format results
            results = []
            for leg in legislation_list:
                results.append({
                    "id": leg.id,
                    "bill_number": leg.bill_number,
                    "title": leg.title,
                    "description": leg.description[:200] + "..." if len(leg.description or "") > 200 else leg.description,
                    "status": leg.bill_status.value if leg.bill_status else None,
                    "introduced_date": leg.bill_introduced_date.isoformat() if leg.bill_introduced_date else None,
                    "govt_type": leg.govt_type.value if leg.govt_type else None,
                    "url": leg.url,
                    "health_relevance": leg.priority.public_health_relevance if leg.priority else 0,
                    "local_govt_relevance": leg.priority.local_govt_relevance if leg.priority else 0,
                    "overall_priority": leg.priority.overall_priority if leg.priority else 0
                })

            return results

        except SQLAlchemyError as e:
            logger.error(f"Database error getting relevant Texas legislation: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Error getting relevant Texas legislation: {e}", exc_info=True)
            return []