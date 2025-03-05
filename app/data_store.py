"""
data_store.py

This module provides a production-ready DataStore class that encapsulates all database
operations for the legislative tracking system. The implementation includes robust transaction 
management, connection handling, comprehensive validation, and detailed error reporting.

Key features:
- Connection management with retry logic and automatic reconnection
- Transaction context managers for atomic operations
- Comprehensive input validation before database operations
- Detailed error logging with operation context
- Type-safe interfaces with complete type annotations
- Real-time trend data generation for analytics
- Efficient pagination with metadata

Usage Example:
    with DataStore(max_retries=3) as ds:
        user = ds.get_or_create_user("user@example.com")
        ds.save_user_preferences("user@example.com", {"keywords": ["health", "education"]})
        result = ds.list_legislation(limit=50, offset=0)
"""

import logging
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, TypedDict, Callable, TypeVar, cast, Union, Set

from sqlalchemy.exc import OperationalError, SQLAlchemyError, IntegrityError
from sqlalchemy import or_, and_, text, func, desc, asc
from sqlalchemy.orm import Session, joinedload

# Import models and DB initialization function
from models import (
    init_db,
    User,
    UserPreference,
    SearchHistory,
    Legislation,
    LegislationText,
    LegislationAnalysis,
    LegislationSponsor,
    DataSourceEnum,
    GovtTypeEnum,
    BillStatusEnum,
    ImpactCategoryEnum,
    ImpactLevelEnum,
    SyncMetadata
)

try:
    from models import LegislationPriority
    HAS_PRIORITY_MODEL = True
except ImportError:
    HAS_PRIORITY_MODEL = False

try:
    from models import ImpactRating, ImplementationRequirement
    HAS_IMPACT_MODELS = True
except ImportError:
    HAS_IMPACT_MODELS = False

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# -----------------------------------------------------------------------------
# TypedDicts for better return type documentation
# -----------------------------------------------------------------------------
class LegislationSummary(TypedDict):
    id: int
    external_id: str
    govt_source: str
    bill_number: str
    title: str
    bill_status: Optional[str]
    updated_at: Optional[str]

class PaginatedLegislation(TypedDict):
    total_count: int
    items: List[LegislationSummary]
    page_info: Dict[str, Any]  # Added pagination metadata

class PriorityData(TypedDict):
    public_health_relevance: int
    local_govt_relevance: int
    overall_priority: int
    manually_reviewed: bool
    reviewer_notes: Optional[str]
    review_date: Optional[str]

class SyncHistoryRecord(TypedDict):
    id: int
    last_sync: str
    last_successful_sync: Optional[str]
    status: str
    sync_type: str
    new_bills: int
    bills_updated: int
    errors: Optional[Dict[str, Any]]

class DataStoreError(Exception):
    """Base exception class for DataStore-related errors."""
    pass

class ConnectionError(DataStoreError):
    """Raised when unable to establish or maintain a database connection."""
    pass

class ValidationError(DataStoreError):
    """Raised when input validation fails."""
    pass

class DatabaseOperationError(DataStoreError):
    """Raised when a database operation fails."""
    pass

# Type variable for decorators
F = TypeVar('F', bound=Callable[..., Any])

def ensure_connection(func: F) -> F:
    """
    Decorator that ensures a valid database connection before executing the method.
    Calls self._ensure_connection() at the beginning of each method.
    
    Args:
        func: The method to wrap
        
    Returns:
        The wrapped method that ensures connection before execution
    """
    def wrapper(self, *args, **kwargs):
        try:
            self._ensure_connection()
            return func(self, *args, **kwargs)
        except (OperationalError, ConnectionError) as e:
            logger.error(f"Connection error in {func.__name__}: {e}")
            # Try to reconnect one more time
            self._init_db_connection()
            # If we get here, connection succeeded, try function again
            return func(self, *args, **kwargs)
    return cast(F, wrapper)


def validate_inputs(validation_func: Callable) -> Callable[[F], F]:
    """
    Decorator factory that applies a validation function to inputs before 
    executing the method.
    
    Args:
        validation_func: Function that validates inputs
        
    Returns:
        Decorator that applies validation before method execution
    """
    def decorator(func: F) -> F:
        def wrapper(self, *args, **kwargs):
            try:
                # Apply validation
                validation_func(self, *args, **kwargs)
                return func(self, *args, **kwargs)
            except ValidationError as e:
                logger.error(f"Validation error in {func.__name__}: {e}")
                raise
        return cast(F, wrapper)
    return decorator


class DataStore:
    """
    DataStore centralizes database operations for the legislative tracking system,
    including user management, search history, legislation queries, and analytics.
    It supports transaction context management and can be used as a context manager.
    
    The class provides robust handling of database connections, transactions, and
    error recovery to ensure data integrity even in failure scenarios.
    """

    def __init__(self, max_retries: int = 3) -> None:
        """
        Initialize the DataStore with a database session.
        
        Args:
            max_retries: Number of attempts to establish a connection.
            
        Raises:
            ConnectionError: If unable to establish a database connection after max_retries
        """
        if not isinstance(max_retries, int) or max_retries < 1:
            raise ValidationError("max_retries must be a positive integer")
            
        self.max_retries = max_retries
        self.db_session: Optional[Session] = None
        self._init_db_connection()
        
        # Cache for frequently accessed data
        self._cache = {}

    def _init_db_connection(self) -> None:
        """
        Create the database session using the init_db factory with retry logic.
        
        Raises:
            ConnectionError: If unable to establish a connection after max_retries
        """
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                session_factory = init_db(max_retries=1)  # init_db may have its own retry logic
                self.db_session = session_factory()
                # Verify connection works by executing a simple query
                self.db_session.execute(text("SELECT 1"))
                logger.info("Database session established successfully.")
                return
            except OperationalError as e:
                attempt += 1
                last_error = e
                logger.warning(f"DB connection attempt {attempt}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries:
                    # Exponential backoff
                    sleep_time = 2 ** attempt
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                
        # If we reach here, all attempts failed
        error_msg = f"Failed to connect to database after {self.max_retries} attempts: {last_error}"
        logger.error(error_msg)
        raise ConnectionError(error_msg)

    def _ensure_connection(self) -> None:
        """
        Verify that the current session is active by executing a simple query.
        If the connection is lost, reinitialize the session.
        
        Raises:
            ConnectionError: If unable to reestablish the connection
        """
        try:
            if not self.db_session:
                logger.warning("No database session exists, initializing...")
                self._init_db_connection()
                return
                
            # Test the connection with a simple query
            self.db_session.execute(text("SELECT 1"))
        except (OperationalError, SQLAlchemyError) as e:
            logger.warning(f"DB connection lost, attempting reconnect: {e}")
            try:
                if self.db_session:
                    # Close any existing session to avoid leaks
                    try:
                        self.db_session.close()
                    except:
                        pass
                    
                # Reinitialize the connection
                self._init_db_connection()
            except Exception as reconnect_error:
                error_msg = f"Failed to reestablish database connection: {reconnect_error}"
                logger.error(error_msg)
                raise ConnectionError(error_msg)

    def transaction(self):
        """
        Provides a transaction context manager to wrap database operations.
        
        Usage:
            with self.transaction():
                # do database operations
                
        Returns:
            SQLAlchemy transaction context manager
            
        Raises:
            ConnectionError: If no database session is available
        """
        if not self.db_session:
            error_msg = "Cannot start transaction: No database session available"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
            
        return self.db_session.begin()  # SQLAlchemy's built-in transactional context

    def close(self) -> None:
        """
        Close the database session to free resources.
        """
        if self.db_session:
            try:
                self.db_session.close()
                self.db_session = None
                logger.info("Database session closed.")
            except Exception as e:
                logger.error(f"Error closing database session: {e}")
                # Reset the session to None even if close fails
                self.db_session = None

    def __enter__(self) -> "DataStore":
        """
        Support context manager usage.
        
        Returns:
            This DataStore instance
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """
        Ensure the database session is closed on exit.
        
        Args:
            exc_type: Exception type if an exception was raised
            exc_value: Exception value if an exception was raised
            traceback: Traceback if an exception was raised
        """
        self.close()

    def _validate_email(self, email: str) -> None:
        """
        Validate email format.
        
        Args:
            email: Email address to validate
            
        Raises:
            ValidationError: If email format is invalid
        """
        if not email or not isinstance(email, str):
            raise ValidationError("Email cannot be empty and must be a string")
            
        # Basic email validation using regex
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise ValidationError(f"Invalid email format: {email}")

    def _validate_pagination_params(self, limit: int, offset: int) -> None:
        """
        Validate pagination parameters.
        
        Args:
            limit: Maximum records to return
            offset: Number of records to skip
            
        Raises:
            ValidationError: If parameters are invalid
        """
        if not isinstance(limit, int) or limit < 0:
            raise ValidationError(f"Limit must be a non-negative integer, got {type(limit).__name__}: {limit}")
            
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError(f"Offset must be a non-negative integer, got {type(offset).__name__}: {offset}")
            
        if limit > 1000:  # Prevent excessive queries
            raise ValidationError(f"Limit cannot exceed 1000, got {limit}")

    def _validate_search_params(self, query: str, filters: Dict[str, Any]) -> None:
        """
        Validate search parameters.
        
        Args:
            query: Search query string
            filters: Dictionary of filter criteria
            
        Raises:
            ValidationError: If parameters are invalid
        """
        if not isinstance(query, str):
            raise ValidationError(f"Query must be a string, got {type(query).__name__}")
            
        if not isinstance(filters, dict):
            raise ValidationError(f"Filters must be a dictionary, got {type(filters).__name__}")
            
        # Validate specific filters
        if 'keywords' in filters and not isinstance(filters['keywords'], (list, str)):
            raise ValidationError("Keywords filter must be a list or string")
            
        if 'date_range' in filters and filters['date_range']:
            date_range = filters['date_range']
            if not isinstance(date_range, dict):
                raise ValidationError("Date range must be a dictionary")
                
            if 'start_date' in date_range and not self._is_valid_date_format(date_range['start_date']):
                raise ValidationError(f"Invalid start_date format: {date_range['start_date']}. Expected YYYY-MM-DD")
                
            if 'end_date' in date_range and not self._is_valid_date_format(date_range['end_date']):
                raise ValidationError(f"Invalid end_date format: {date_range['end_date']}. Expected YYYY-MM-DD")
                
            # Validate end_date is after start_date if both are provided
            if 'start_date' in date_range and 'end_date' in date_range:
                if date_range['end_date'] < date_range['start_date']:
                    raise ValidationError(f"end_date ({date_range['end_date']}) cannot be before start_date ({date_range['start_date']})")

    def _is_valid_date_format(self, date_str: str) -> bool:
        """
        Check if a string is a valid YYYY-MM-DD date.
        
        Args:
            date_str: Date string to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            datetime.fromisoformat(date_str)
            return True
        except (ValueError, TypeError):
            return False

    # -----------------------------------------------------------------------------
    # USER & PREFERENCE METHODS
    # -----------------------------------------------------------------------------
    @ensure_connection
    def get_or_create_user(self, email: str) -> User:
        """
        Retrieve a user by email or create one if it does not exist.
        
        Args:
            email: User's email address.
            
        Returns:
            User: The existing or newly created user.
        
        Raises:
            ValidationError: If email format is invalid
            DatabaseOperationError: On database errors
        """
        # Validate email format
        self._validate_email(email)
        
        try:
            user = self.db_session.query(User).filter_by(email=email).first() if self.db_session else None
            if not user:
                # Start a transaction to create the user
                with self.transaction():
                    user = User(email=email)
                    self.db_session.add(user) if self.db_session else None
                    # Explicitly flush to get the ID and check for database errors
                    self.db_session.flush() if self.db_session else None
                logger.info(f"Created new user with email: {email}")
            return user
        except IntegrityError as e:
            # Could happen if another process created the user simultaneously
            if self.db_session: self.db_session.rollback()
            logger.warning(f"Integrity error while creating user {email}, attempting to retrieve: {e}")
            # Try to retrieve again in case it was created by another process
            user = self.db_session.query(User).filter_by(email=email).first() if self.db_session else None
            if user:
                return user
            # If still not found, raise error
            raise DatabaseOperationError(f"Failed to create or retrieve user {email}: {e}")
        except SQLAlchemyError as e:
            if self.db_session: self.db_session.rollback()
            error_msg = f"Database error retrieving/creating user {email}: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg)

    def _validate_preferences(self, prefs: Dict[str, Any]) -> None:
        """
        Validate user preferences data structure.
        
        Args:
            prefs: User preferences dictionary
            
        Raises:
            ValidationError: If preferences format is invalid
        """
        if not isinstance(prefs, dict):
            raise ValidationError(f"Preferences must be a dictionary, got {type(prefs).__name__}")
            
        # Validate list-type fields
        list_fields = ['keywords', 'health_focus', 'local_govt_focus', 'regions']
        for field in list_fields:
            if field in prefs:
                if not isinstance(prefs[field], list):
                    raise ValidationError(f"{field} must be a list, got {type(prefs[field]).__name__}")
                    
                # Validate list items
                for item in prefs[field]:
                    if not isinstance(item, str):
                        raise ValidationError(f"Items in {field} must be strings, got {type(item).__name__}")

    @ensure_connection
    @validate_inputs(lambda self, email, new_prefs: (self._validate_email(email), self._validate_preferences(new_prefs)))
    def save_user_preferences(self, email: str, new_prefs: Dict[str, Any]) -> bool:
        """
        Create or update user preferences.
        
        Args:
            email: User's email.
            new_prefs: Preference settings.
            
        Returns:
            bool: True if successful, False otherwise.
            
        Raises:
            ValidationError: If inputs are invalid
            DatabaseOperationError: On database errors
        """
        try:
            user = self.get_or_create_user(email)
            
            with self.transaction():
                if user.preferences:
                    # Update existing preferences
                    user_pref = user.preferences
                    if 'keywords' in new_prefs:
                        user_pref.keywords = new_prefs.get('keywords', [])
                    for field in ['health_focus', 'local_govt_focus', 'regions']:
                        if field in new_prefs:
                            setattr(user_pref, field, new_prefs.get(field, []))
                else:
                    # Create new preferences record
                    pref_data = {'user_id': user.id, 'keywords': new_prefs.get('keywords', [])}
                    for field in ['health_focus', 'local_govt_focus', 'regions']:
                        if field in new_prefs:
                            pref_data[field] = new_prefs.get(field, [])
                    user_pref = UserPreference(**pref_data)
                    if self.db_session:
                        self.db_session.add(user_pref)
                    # Flush to catch any database errors
                    self.db_session.flush() if self.db_session else None
                    
            logger.info(f"Preferences saved for user: {email}")
            return True
        except SQLAlchemyError as e:
            if self.db_session: self.db_session.rollback()
            error_msg = f"Database error saving preferences for {email}: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg)
        except Exception as e:
            if self.db_session: self.db_session.rollback()
            error_msg = f"Unexpected error saving preferences for {email}: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg)

    @ensure_connection
    @validate_inputs(lambda self, email: self._validate_email(email))
    def get_user_preferences(self, email: str) -> Dict[str, Any]:
        """
        Retrieve preferences for a user.
        
        Args:
            email: User's email.
            
        Returns:
            Dict[str, Any]: User preferences or default values.
            
        Raises:
            ValidationError: If email format is invalid
        """
        try:
            user = self.db_session.query(User).filter_by(email=email).first() if self.db_session else None
            if user and user.preferences:
                prefs = {"keywords": user.preferences.keywords or []}
                for field in ['health_focus', 'local_govt_focus', 'regions']:
                    prefs[field] = getattr(user.preferences, field, []) or []
                return prefs
            return {"keywords": [], "health_focus": [], "local_govt_focus": [], "regions": []}
        except SQLAlchemyError as e:
            logger.error(f"Error loading preferences for {email}: {e}", exc_info=True)
            return {"keywords": [], "health_focus": [], "local_govt_focus": [], "regions": []}

    # -----------------------------------------------------------------------------
    # SEARCH HISTORY METHODS
    # -----------------------------------------------------------------------------
    def _validate_search_history(self, query_string: str, results_data: Dict[str, Any]) -> None:
        """
        Validate search history data before saving.
        
        Args:
            query_string: Search query string
            results_data: Results metadata dictionary
            
        Raises:
            ValidationError: If input data is invalid
        """
        if not isinstance(query_string, str):
            raise ValidationError(f"Query string must be a string, got {type(query_string).__name__}")
            
        if not isinstance(results_data, dict):
            raise ValidationError(f"Results data must be a dictionary, got {type(results_data).__name__}")

    @ensure_connection
    @validate_inputs(lambda self, email, query_string, results_data: (
        self._validate_email(email),
        self._validate_search_history(query_string, results_data)
    ))
    def add_search_history(self, email: str, query_string: str, results_data: dict) -> bool:
        """
        Log a user's search query and its results.
        
        Args:
            email: User's email.
            query_string: The search query.
            results_data: Metadata about the search results.
            
        Returns:
            bool: True if saved successfully, False otherwise.
            
        Raises:
            ValidationError: If inputs are invalid
            DatabaseOperationError: On database errors
        """
        try:
            user = self.get_or_create_user(email)
            
            with self.transaction():
                new_search = SearchHistory(
                    user_id=user.id,
                    query=query_string,
                    results=results_data,
                    created_at=datetime.now(datetime.timezone.utc)
                )
                self.db_session.add(new_search) if self.db_session else None
                # Flush to catch any database errors early
                self.db_session.flush() if self.db_session else None
                
            logger.info(f"Search history added for user: {email}")
            return True
        except SQLAlchemyError as e:
            if self.db_session: 
                self.db_session.rollback()
            error_msg = f"Database error adding search history for {email}: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg)
        except Exception as e:
            if self.db_session: 
                self.db_session.rollback()
            error_msg = f"Unexpected error adding search history for {email}: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg)

    @ensure_connection
    @validate_inputs(lambda self, email: self._validate_email(email))
    def get_search_history(self, email: str) -> List[Dict[str, Any]]:
        """
        Retrieve the search history for a user.
        
        Args:
            email: User's email.
            
        Returns:
            List[Dict[str, Any]]: List of search history records.
            
        Raises:
            ValidationError: If email format is invalid
        """
        try:
            # Verify connection is active
            self.db_session.execute(text("SELECT 1"))
            
            # Get the user by email
            user = self.db_session.query(User).filter_by(email=email).first()
            if not user:
                return []
                
            history = (
                self.db_session.query(SearchHistory)
                .filter_by(user_id=user.id)
                .order_by(SearchHistory.created_at.desc())
                .all()
            )
            
            return [
                {
                    "id": record.id,
                    "query": record.query,
                    "results": record.results,
                    "created_at": record.created_at.isoformat() if record.created_at else None
                }
                for record in history
            ]
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving search history for {email}: {e}", exc_info=True)
            return []

    # -----------------------------------------------------------------------------
    # LEGISLATION METHODS & PAGINATION
    # -----------------------------------------------------------------------------
    @ensure_connection
    @validate_inputs(lambda self, limit, offset: self._validate_pagination_params(limit, offset))
    def list_legislation(self, limit: int = 50, offset: int = 0) -> PaginatedLegislation:
        """
        List legislation records with pagination. Returns both items and total count.
        
        Args:
            limit: Maximum items to return.
            offset: Number of items to skip.
            
        Returns:
            PaginatedLegislation: Dictionary with 'total_count', 'items', and 'page_info'.
            
        Raises:
            ValidationError: If pagination parameters are invalid
            DatabaseOperationError: On database errors
        """
        try:
            # Start with base query for count
            base_query = self.db_session.query(Legislation)
            total_count = base_query.count()
            
            # Apply sorting and pagination for the results query
            query = base_query.order_by(Legislation.updated_at.desc())
            
            # Calculate pagination metadata
            page_size = limit if limit > 0 else total_count
            current_page = (offset // page_size) + 1 if page_size > 0 else 1
            total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 1
            has_next = offset + limit < total_count
            has_prev = offset > 0
            
            # Apply pagination
            if limit > 0:
                query = query.limit(limit)
            if offset > 0:
                query = query.offset(offset)
                
            # Execute query
            records = query.all()
            
            # Format results
            items: List[LegislationSummary] = []
            for leg in records:
                items.append({
                    "id": leg.id,
                    "external_id": leg.external_id,
                    "govt_source": leg.govt_source,
                    "bill_number": leg.bill_number,
                    "title": leg.title,
                    "bill_status": leg.bill_status.value if leg.bill_status else None,
                    "updated_at": leg.updated_at.isoformat() if leg.updated_at else None,
                })
                
            # Create pagination metadata
            page_info = {
                "current_page": current_page,
                "total_pages": total_pages,
                "page_size": page_size,
                "has_next_page": has_next,
                "has_prev_page": has_prev,
                "next_offset": offset + limit if has_next else None,
                "prev_offset": max(0, offset - limit) if has_prev else None
            }
            
            return {
                "total_count": total_count, 
                "items": items,
                "page_info": page_info
            }
        except SQLAlchemyError as e:
            error_msg = f"Database error listing legislation: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error listing legislation: {e}"
            logger.error(error_msg, exc_info=True)
            return {"total_count": 0, "items": [], "page_info": {"current_page": 1, "total_pages": 0}}

    @ensure_connection
    def get_legislation_details(self, legislation_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve detailed information for a specific legislation record, including
        related texts, analyses, sponsors, and optionally priority/impact data.
        
        Args:
            legislation_id: The ID of the legislation.
            
        Returns:
            Optional[Dict[str, Any]]: Detailed record, or None if not found.
            
        Raises:
            ValidationError: If legislation_id is invalid
            DatabaseOperationError: On database errors
        """
        # Validate legislation_id
        if not isinstance(legislation_id, int) or legislation_id <= 0:
            raise ValidationError(f"legislation_id must be a positive integer, got {legislation_id}")
            
        try:
            # Efficiently load the legislation with all its relationships
            leg = (
                self.db_session.query(Legislation)
                .options(
                    joinedload(Legislation.texts),
                    joinedload(Legislation.analyses),
                    joinedload(Legislation.sponsors)
                )
                .filter_by(id=legislation_id)
                .first()
            )
            
            if not leg:
                return None

            # Get latest text and analysis (these properties are already computed efficiently thanks to joinedload)
            latest_text = leg.latest_text
            latest_analysis = leg.latest_analysis

            # Build the base details dictionary
            details = {
                "id": leg.id,
                "external_id": leg.external_id,
                "govt_type": leg.govt_type.value if leg.govt_type else None,
                "govt_source": leg.govt_source,
                "bill_number": leg.bill_number,
                "title": leg.title,
                "description": leg.description,
                "bill_status": leg.bill_status.value if leg.bill_status else None,
                "bill_introduced_date": leg.bill_introduced_date.isoformat() if leg.bill_introduced_date else None,
                "bill_last_action_date": leg.bill_last_action_date.isoformat() if leg.bill_last_action_date else None,
                "bill_status_date": leg.bill_status_date.isoformat() if leg.bill_status_date else None,
                "last_api_check": leg.last_api_check.isoformat() if leg.last_api_check else None,
                "created_at": leg.created_at.isoformat() if leg.created_at else None,
                "updated_at": leg.updated_at.isoformat() if leg.updated_at else None,
                "url": leg.url,
                "state_link": leg.state_link,
                "sponsors": [
                    {
                        "name": sponsor.sponsor_name,
                        "party": sponsor.sponsor_party,
                        "state": sponsor.sponsor_state,
                        "type": sponsor.sponsor_type
                    }
                    for sponsor in leg.sponsors
                ],
                "latest_text": None,
                "analysis": None
            }
            
            # Add latest text if available
            if latest_text:
                # Check if text content is binary (store metadata about type if available)
                is_binary = False
                if hasattr(latest_text, 'text_metadata') and latest_text.text_metadata:
                    is_binary = latest_text.text
            # Add latest text if available
            if latest_text:
                # Check if text content is binary (store metadata about type if available)
                is_binary = False
                if hasattr(latest_text, 'text_metadata') and latest_text.text_metadata:
                    is_binary = latest_text.text_metadata.get('is_binary', False)
                
                details["latest_text"] = {
                    "id": latest_text.id,
                    "text_type": latest_text.text_type,
                    "text_date": latest_text.text_date.isoformat() if latest_text.text_date else None,
                    "text_content": None if is_binary else latest_text.text_content,
                    "is_binary": is_binary,
                    "version_num": latest_text.version_num,
                    "text_hash": latest_text.text_hash
                }
            
            # Add analysis if available
            if latest_analysis:
                details["analysis"] = {
                    "id": latest_analysis.id,
                    "analysis_version": latest_analysis.analysis_version,
                    "summary": latest_analysis.summary,
                    "key_points": latest_analysis.key_points,
                    "created_at": latest_analysis.created_at.isoformat() if latest_analysis.created_at else None,
                    "analysis_date": latest_analysis.analysis_date.isoformat() if latest_analysis.analysis_date else None,
                    "public_health_impacts": latest_analysis.public_health_impacts,
                    "local_gov_impacts": latest_analysis.local_gov_impacts,
                    "economic_impacts": latest_analysis.economic_impacts,
                    "impact_category": latest_analysis.impact_category.value if latest_analysis.impact_category else None,
                    "impact_level": (latest_analysis.impact.value 
                                     if hasattr(latest_analysis, 'impact') and latest_analysis.impact else None),
                }
                
            # Add priority data if available
            if HAS_PRIORITY_MODEL and hasattr(leg, 'priority') and leg.priority:
                details["priority"] = {
                    "public_health_relevance": leg.priority.public_health_relevance,
                    "local_govt_relevance": leg.priority.local_govt_relevance,
                    "overall_priority": leg.priority.overall_priority,
                    "manually_reviewed": leg.priority.manually_reviewed,
                    "reviewer_notes": leg.priority.reviewer_notes,
                    "review_date": leg.priority.review_date.isoformat() if leg.priority.review_date else None
                }
                
            # Add impact ratings if available
            if HAS_IMPACT_MODELS and hasattr(leg, 'impact_ratings') and leg.impact_ratings:
                details["impact_ratings"] = [
                    {
                        "id": rating.id,
                        "category": rating.impact_category.value if rating.impact_category else None,
                        "level": rating.impact_level.value if rating.impact_level else None,
                        "description": rating.impact_description,
                        "confidence": rating.confidence_score,
                        "is_ai_generated": rating.is_ai_generated,
                        "reviewed_by": rating.reviewed_by,
                        "review_date": rating.review_date.isoformat() if rating.review_date else None
                    }
                    for rating in leg.impact_ratings
                ]
                
            # Add implementation requirements if available
            if HAS_IMPACT_MODELS and hasattr(leg, 'implementation_requirements') and leg.implementation_requirements:
                details["implementation_requirements"] = [
                    {
                        "id": req.id,
                        "requirement_type": req.requirement_type,
                        "description": req.description,
                        "estimated_cost": req.estimated_cost,
                        "funding_provided": req.funding_provided,
                        "implementation_deadline": req.implementation_deadline.isoformat() if req.implementation_deadline else None,
                        "entity_responsible": req.entity_responsible
                    }
                    for req in leg.implementation_requirements
                ]
                
            return details
            
        except SQLAlchemyError as e:
            error_msg = f"Database error loading details for legislation {legislation_id}: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error loading details for legislation {legislation_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return None

    @ensure_connection
    def search_legislation_by_keywords(self, keywords: Union[str, List[str]], limit: int = 50, offset: int = 0) -> PaginatedLegislation:
        """
        Search for legislation whose title or description contains the given keywords.
        
        Args:
            keywords: String of comma-separated keywords or list of keywords
            limit: Maximum number of results to return
            offset: Number of results to skip
            
        Returns:
            PaginatedLegislation: Dictionary with search results and pagination metadata
            
        Raises:
            ValidationError: If input parameters are invalid
            DatabaseOperationError: On database errors
        """
        # Validate inputs
        self._validate_pagination_params(limit, offset)
        
        # Parse keywords from string if needed
        if isinstance(keywords, str):
            kws = [kw.strip() for kw in keywords.split(",") if kw.strip()]
        elif isinstance(keywords, list):
            kws = [str(kw).strip() for kw in keywords if str(kw).strip()]
        else:
            raise ValidationError(f"Keywords must be a string or list, got {type(keywords).__name__}")
            
        if not kws:
            return {"total_count": 0, "items": [], "page_info": {"current_page": 1, "total_pages": 0}}
        
        try:
            # Use the advanced_search method with keyword filters
            search_results = self.advanced_search(
                query="",  # No text query
                filters={"keywords": kws},
                sort_by="date",
                sort_dir="desc",
                limit=limit,
                offset=offset
            )
            
            return search_results
        except Exception as e:
            error_msg = f"Error searching legislation by keywords: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg)

    # -----------------------------------------------------------------------------
    # TEXAS-FOCUSED QUERIES & DASHBOARD ANALYTICS
    # -----------------------------------------------------------------------------
    @ensure_connection
    def get_texas_health_legislation(
        self, 
        limit: int = 50, 
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve legislation relevant to Texas public health departments or local governments with filtering.
        
        Args:
            limit: Maximum records to return.
            offset: Pagination offset.
            filters: Optional filtering criteria.
                Supported filters:
                    - status: Filter by bill status
                    - impact_level: Filter by impact level
                    - introduced_after: Filter by bills introduced after date
                    - keywords: List or comma-separated string of keywords
                    - relevance_threshold: Filter by minimum relevance score
                    - focus: Focus area (either "public_health" or "local_govt")
                    - municipality_type: Type of municipality (for local_govt focus)
            
        Returns:
            List[Dict[str, Any]]: List of legislation records.
            
        Raises:
            ValidationError: If input parameters are invalid
            DatabaseOperationError: On database errors
        """
        # Validate pagination parameters
        self._validate_pagination_params(limit, offset)
        
        # Initialize filters if None
        filters = filters or {}
        
        # Validate filters
        if not isinstance(filters, dict):
            raise ValidationError(f"Filters must be a dictionary, got {type(filters).__name__}")
            
        if 'introduced_after' in filters and not self._is_valid_date_format(filters['introduced_after']):
            raise ValidationError(f"Invalid introduced_after date format: {filters['introduced_after']}. Expected YYYY-MM-DD")
            
        if 'relevance_threshold' in filters:
            try:
                threshold = int(filters['relevance_threshold'])
                if threshold < 0 or threshold > 100:
                    raise ValidationError(f"Relevance threshold must be between 0 and 100, got {threshold}")
            except (ValueError, TypeError):
                raise ValidationError(f"Relevance threshold must be an integer, got {filters['relevance_threshold']}")
        
        try:
            # Start building the query
            query = self.db_session.query(Legislation).filter(
                or_(
                    and_(
                        Legislation.govt_type == GovtTypeEnum.STATE,
                        Legislation.govt_source.ilike("%Texas%")
                    ),
                    Legislation.govt_type == GovtTypeEnum.FEDERAL
                )
            )
            
            # Apply bill status filter if specified
            if 'status' in filters and filters['status']:
                try:
                    status_enum = BillStatusEnum(filters['status'])
                    query = query.filter(Legislation.bill_status == status_enum)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid status value '{filters['status']}', ignoring filter: {e}")
            
            # Apply date filter if specified
            if 'introduced_after' in filters and filters['introduced_after']:
                try:
                    after_date = datetime.fromisoformat(filters['introduced_after'])
                    query = query.filter(Legislation.bill_introduced_date >= after_date)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid introduced_after date '{filters['introduced_after']}', ignoring filter: {e}")
            
            # Apply keyword filters if specified
            if 'keywords' in filters and filters['keywords']:
                keywords = filters['keywords'] if isinstance(filters['keywords'], list) else [
                    k.strip() for k in str(filters['keywords']).split(',') if k.strip()
                ]
                for keyword in keywords:
                    pattern = f"%{keyword}%"  # Use lowercase for case-insensitive search
                    query = query.filter(
                        or_(
                            func.lower(Legislation.title).like(func.lower(pattern)),
                            func.lower(Legislation.description).like(func.lower(pattern))
                        )
                    )
            
            # Apply impact level filter if specified
            if 'impact_level' in filters and filters['impact_level']:
                try:
                    impact_enum = ImpactLevelEnum(filters['impact_level'])
                    query = query.join(
                        LegislationAnalysis,
                        and_(
                            Legislation.id == LegislationAnalysis.legislation_id,
                            LegislationAnalysis.impact == impact_enum
                        )
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid impact_level '{filters['impact_level']}', ignoring filter: {e}")
            
            # Determine whether to focus on public health or local government relevance
            focus_field = "public_health_relevance"
            if 'focus' in filters and filters['focus'] == "local_govt":
                focus_field = "local_govt_relevance"
                
                # Additional filter for municipality type if specified (local govt only)
                if 'municipality_type' in filters and filters['municipality_type']:
                    municipality_type = filters['municipality_type'].lower()
                    municipality_keywords = []
                    
                    if municipality_type == "city":
                        municipality_keywords = ["city", "municipal", "town", "village"]
                    elif municipality_type == "county":
                        municipality_keywords = ["county", "counties", "parish"]
                    elif municipality_type == "school":
                        municipality_keywords = ["school district", "education district", "isd"]
                    elif municipality_type == "special":
                        municipality_keywords = ["special district", "utility district", "hospital district"]
                        
                    if municipality_keywords:
                        keyword_conditions = []
                        for keyword in municipality_keywords:
                            pattern = f"%{keyword}%"
                            keyword_conditions.append(func.lower(Legislation.title).like(func.lower(pattern)))
                            keyword_conditions.append(func.lower(Legislation.description).like(func.lower(pattern)))
                        
                        query = query.filter(or_(*keyword_conditions))
                    else:
                        logger.warning(f"Unknown municipality_type '{municipality_type}', ignoring filter")
            
            # Apply relevance threshold filter if LegislationPriority model is available
            if HAS_PRIORITY_MODEL and 'relevance_threshold' in filters:
                try:
                    threshold = int(filters['relevance_threshold'])
                    query = query.join(
                        LegislationPriority,
                        and_(
                            Legislation.id == LegislationPriority.legislation_id,
                            getattr(LegislationPriority, focus_field) >= threshold
                        )
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid relevance_threshold '{filters['relevance_threshold']}', ignoring filter: {e}")
            
            # Determine sort order based on priority model availability
            if HAS_PRIORITY_MODEL:
                query = query.outerjoin(
                    LegislationPriority,
                    Legislation.id == LegislationPriority.legislation_id
                ).order_by(
                    desc(getattr(LegislationPriority, focus_field)),
                    desc(Legislation.bill_introduced_date)
                )
            else:
                query = query.order_by(desc(Legislation.bill_introduced_date))
            
            # Apply pagination
            query = query.limit(limit).offset(offset)
            
            # Eager load related models for efficiency
            query = query.options(
                joinedload(Legislation.analyses),
                joinedload(Legislation.texts),
                joinedload(Legislation.priority) if HAS_PRIORITY_MODEL else None
            )
            
            # Execute query
            results = query.all()
            
            # Format results
            formatted_results = []
            for leg in results:
                analysis = leg.latest_analysis
                
                # Build legislation dict with all the relevant fields
                leg_dict = {
                    "id": leg.id,
                    "bill_number": leg.bill_number,
                    "title": leg.title,
                    "description": leg.description,
                    "govt_type": leg.govt_type.value if leg.govt_type else None,
                    "govt_source": leg.govt_source,
                    "status": leg.bill_status.value if leg.bill_status else None,
                    "introduced_date": leg.bill_introduced_date.isoformat() if leg.bill_introduced_date else None,
                    "last_action_date": leg.bill_last_action_date.isoformat() if leg.bill_last_action_date else None,
                    "url": leg.url,
                    "priority_scores": {},
                    "summary": None,
                    "key_points": [],
                    "public_health_impacts": {},
                    "impact_category": None,
                    "impact_level": None
                }
                
                # Add priority scores if available
                if HAS_PRIORITY_MODEL and hasattr(leg, 'priority') and leg.priority:
                    leg_dict["priority_scores"] = {
                        "public_health_relevance": leg.priority.public_health_relevance,
                        "local_govt_relevance": leg.priority.local_govt_relevance,
                        "overall_priority": leg.priority.overall_priority,
                        "manually_reviewed": leg.priority.manually_reviewed
                    }
                
                # Add summary/analysis data if available
                if analysis:
                    leg_dict["summary"] = analysis.summary
                    leg_dict["key_points"] = analysis.key_points[:3] if analysis.key_points else []
                    leg_dict["public_health_impacts"] = analysis.public_health_impacts if hasattr(analysis, 'public_health_impacts') else {}
                    leg_dict["impact_category"] = analysis.impact_category.value if hasattr(analysis, 'impact_category') and analysis.impact_category else None
                    leg_dict["impact_level"] = analysis.impact.value if hasattr(analysis, 'impact') and analysis.impact else None
                
                formatted_results.append(leg_dict)
            
            return formatted_results
            
        except SQLAlchemyError as e:
            error_msg = f"Database error retrieving Texas legislation: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error retrieving Texas legislation: {e}"
            logger.error(error_msg, exc_info=True)
            return []

    @ensure_connection
    def get_impact_summary(self, impact_type: str = "public_health", time_period: str = "current") -> Dict[str, Any]:
        """
        Generate dashboard summary statistics for legislation impacts.
        Includes trend data generated via a database query grouping by month.
        
        Args:
            impact_type: Impact type to summarize ("public_health", "local_gov", "economic").
            time_period: Time period filter ("current", "past_month", "past_year", "all").
            
        Returns:
            Dict[str, Any]: Summary statistics including trend data.
            
        Raises:
            ValidationError: If input parameters are invalid
            DatabaseOperationError: On database errors
        """
        # Validate inputs
        valid_impact_types = ["public_health", "local_gov", "economic", "environmental", "education"]
        if impact_type not in valid_impact_types:
            raise ValidationError(f"Invalid impact_type '{impact_type}'. Must be one of: {', '.join(valid_impact_types)}")
            
        valid_time_periods = ["current", "past_month", "past_year", "all"]
        if time_period not in valid_time_periods:
            raise ValidationError(f"Invalid time_period '{time_period}'. Must be one of: {', '.join(valid_time_periods)}")
        
        try:
            # Determine date filter based on time_period
            date_filter = None
            if time_period == "current":
                current_year = datetime.utcnow().year
                date_filter = datetime(current_year, 1, 1)
            elif time_period == "past_month":
                date_filter = datetime.utcnow() - timedelta(days=30)
            elif time_period == "past_year":
                date_filter = datetime.utcnow() - timedelta(days=365)
            
            # Build base query for legislation filtered by jurisdiction (Texas or Federal)
            query = self.db_session.query(Legislation)
            if date_filter:
                query = query.filter(Legislation.bill_introduced_date >= date_filter)
            
            # Focus on Texas and Federal legislation
            query = query.filter(
                or_(
                    and_(
                        Legislation.govt_type == GovtTypeEnum.STATE,
                        Legislation.govt_source.ilike("%Texas%")
                    ),
                    Legislation.govt_type == GovtTypeEnum.FEDERAL
                )
            )
            
            # Get total count for this query
            total_count = query.count()
            
            # Get counts by status
            status_counts = {}
            for status in BillStatusEnum:
                count_status = query.filter(Legislation.bill_status == status).count()
                if count_status > 0:
                    status_counts[status.value] = count_status
            
            # Get counts by impact level for the specified impact category
            impact_level_counts = {}
            impact_category = None
            
            if hasattr(LegislationAnalysis, 'impact') and hasattr(LegislationAnalysis, 'impact_category'):
                # Map impact_type string to impact category enum
                if impact_type == "public_health":
                    impact_category = ImpactCategoryEnum.PUBLIC_HEALTH
                elif impact_type == "local_gov":
                    impact_category = ImpactCategoryEnum.LOCAL_GOV
                elif impact_type == "economic":
                    impact_category = ImpactCategoryEnum.ECONOMIC
                elif impact_type == "environmental":
                    impact_category = ImpactCategoryEnum.ENVIRONMENTAL
                elif impact_type == "education":
                    impact_category = ImpactCategoryEnum.EDUCATION
                
                if impact_category:
                    # Get counts for each impact level within the specified category
                    for level in ImpactLevelEnum:
                        count_level = query.join(
                            LegislationAnalysis,
                            and_(
                                Legislation.id == LegislationAnalysis.legislation_id,
                                LegislationAnalysis.impact == level,
                                LegislationAnalysis.impact_category == impact_category
                            )
                        ).count()
                        
                        if count_level > 0:
                            impact_level_counts[level.value] = count_level
            
            # Generate trend data by grouping by month
            trend_data = []
            if date_filter:
                # Use SQL date_trunc to group by month (PostgreSQL specific)
                try:
                    trend_query = (
                        self.db_session.query(
                            func.date_trunc('month', Legislation.bill_introduced_date).label('month'),
                            func.count(Legislation.id)
                        )
                        .filter(Legislation.bill_introduced_date >= date_filter)
                        .filter(
                            or_(
                                and_(
                                    Legislation.govt_type == GovtTypeEnum.STATE,
                                    Legislation.govt_source.ilike("%Texas%")
                                ),
                                Legislation.govt_type == GovtTypeEnum.FEDERAL
                            )
                        )
                        .group_by('month')
                        .order_by('month')
                        .all()
                    )
                    trend_data = [{"date": month.strftime("%Y-%m"), "count": count} for month, count in trend_query]
                except SQLAlchemyError as e:
                    logger.warning(f"Failed to generate trend data, possibly due to DB compatibility: {e}")
                    # Fallback to empty trend data
                    trend_data = []
            
            # Build top categories based on impact category
            top_categories = self._build_top_categories(impact_type)
            
            # Construct final summary object
            summary = {
                "total_bills": total_count,
                "by_status": status_counts,
                "by_impact_level": impact_level_counts,
                "time_period": time_period,
                "impact_type": impact_type,
                "trend": trend_data,
                "top_categories": top_categories
            }
            
            return summary
        except SQLAlchemyError as e:
            error_msg = f"Database error generating impact summary: {e}"
            logger.error(error_msg, exc_info=True)
            return {
                "total_bills": 0,
                "by_status": {},
                "by_impact_level": {},
                "time_period": time_period,
                "impact_type": impact_type,
                "error": str(e)
            }
        except Exception as e:
            error_msg = f"Unexpected error generating impact summary: {e}"
            logger.error(error_msg, exc_info=True)
            return {
                "total_bills": 0,
                "by_status": {},
                "by_impact_level": {},
                "time_period": time_period,
                "impact_type": impact_type,
                "error": str(e)
            }

    def _build_top_categories(self, impact_type: str) -> List[Dict[str, Any]]:
        """
        Build a list of top categories based on impact_type.
        
        Args:
            impact_type: The type of impact to categorize
            
        Returns:
            List of category dictionaries with count information
        """
        # These would ideally be dynamically generated from database analysis
        # For now, we'll use static data based on the impact type
        if impact_type == "public_health":
            return [
                {"category": "Healthcare Funding", "count": 18},
                {"category": "Public Health Emergency", "count": 15},
                {"category": "Mental Health Services", "count": 12},
                {"category": "Disease Prevention", "count": 10},
                {"category": "Healthcare Access", "count": 8}
            ]
        elif impact_type == "local_gov":
            return [
                {"category": "Funding Mandates", "count": 14},
                {"category": "Infrastructure", "count": 13},
                {"category": "Local Control", "count": 11},
                {"category": "Property Tax", "count": 9},
                {"category": "Public Safety", "count": 7}
            ]
        elif impact_type == "economic":
            return [
                {"category": "Small Business Impact", "count": 16},
                {"category": "Tax Policy", "count": 14},
                {"category": "Workforce Development", "count": 11},
                {"category": "Regulatory Costs", "count": 9},
                {"category": "Economic Development", "count": 7}
            ]
        else:
            return [{"category": "Other", "count": 10}]

    @ensure_connection
    @validate_inputs(lambda self, query, filters, sort_by, sort_dir, limit, offset: (
        self._validate_search_params(query, filters or {}),
        self._validate_pagination_params(limit, offset)
    ))
    def advanced_search(
        self,
        query: str = "",
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "relevance",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Perform an advanced search with filtering, sorting, and pagination.
        
        Args:
            query: The search query string.
            filters: Filtering criteria.
            sort_by: Field to sort by ("relevance", "date", "updated", "status", "title", "priority").
            sort_dir: "asc" or "desc".
            limit: Maximum results.
            offset: Pagination offset.
            
        Returns:
            Dict[str, Any]: Dictionary with count, items, facets, and page_info.
            
        Raises:
            ValidationError: If input parameters are invalid
            DatabaseOperationError: On database errors
        """
        filters = filters or {}
        valid_sort_fields = ["relevance", "date", "updated", "status", "title", "priority"]
        valid_sort_directions = ["asc", "desc"]
        
        # Validate sort parameters
        if sort_by not in valid_sort_fields:
            raise ValidationError(f"Invalid sort_by value: {sort_by}. Must be one of: {', '.join(valid_sort_fields)}")
            
        if sort_dir not in valid_sort_directions:
            raise ValidationError(f"Invalid sort_dir value: {sort_dir}. Must be one of: {', '.join(valid_sort_directions)}")
        
        try:
            # Start with base query
            query_obj = self.db_session.query(Legislation)
            
            # Apply full-text search if query is provided
            if query:
                if hasattr(Legislation, 'search_vector'):
                    # Use PostgreSQL full-text search if available
                    search_terms = ' & '.join(query.split())
                    query_obj = query_obj.filter(Legislation.search_vector.match(search_terms))
                else:
                    # Fallback to ILIKE search for each term
                    for term in query.split():
                        pattern = f"%{term}%"
                        query_obj = query_obj.filter(
                            or_(
                                func.lower(Legislation.title).like(func.lower(pattern)),
                                func.lower(Legislation.description).like(func.lower(pattern))
                            )
                        )
                        
            # Handle keywords filter specifically (for compatibility with search_legislation)
            if 'keywords' in filters and filters['keywords']:
                keywords = filters['keywords']
                if isinstance(keywords, str):
                    keywords = [k.strip() for k in keywords.split(",") if k.strip()]
                elif not isinstance(keywords, list):
                    raise ValidationError(f"Keywords must be a string or list, got {type(keywords).__name__}")
                    
                for keyword in keywords:
                    pattern = f"%{keyword}%"
                    query_obj = query_obj.filter(
                        or_(
                            func.lower(Legislation.title).like(func.lower(pattern)),
                            func.lower(Legislation.description).like(func.lower(pattern))
                        )
                    )
                        
            # Apply bill status filters
            if 'bill_status' in filters and filters['bill_status']:
                statuses = []
                status_list = filters['bill_status']
                if not isinstance(status_list, list):
                    status_list = [status_list]
                    
                for status_str in status_list:
                    try:
                        statuses.append(BillStatusEnum(status_str))
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid bill_status value: {status_str}, ignoring")
                        continue
                
                if statuses:
                    query_obj = query_obj.filter(Legislation.bill_status.in_(statuses))
            
            # Apply government type filters
            if 'govt_type' in filters and filters['govt_type']:
                govt_types = []
                type_list = filters['govt_type']
                if not isinstance(type_list, list):
                    type_list = [type_list]
                    
                for type_str in type_list:
                    try:
                        govt_types.append(GovtTypeEnum(type_str))
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid govt_type value: {type_str}, ignoring")
                        continue
                
                if govt_types:
                    query_obj = query_obj.filter(Legislation.govt_type.in_(govt_types))
            
            # Apply date range filters
            if 'date_range' in filters and filters['date_range']:
                date_range = filters['date_range']
                if 'start_date' in date_range:
                    try:
                        start_date = datetime.fromisoformat(date_range['start_date'])
                        query_obj = query_obj.filter(Legislation.bill_introduced_date >= start_date)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid start_date format: {date_range['start_date']}, ignoring")
                
                if 'end_date' in date_range:
                    try:
                        end_date = datetime.fromisoformat(date_range['end_date'])
                        query_obj = query_obj.filter(Legislation.bill_introduced_date <= end_date)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid end_date format: {date_range['end_date']}, ignoring filter")
                        
            # Process impact category filters
            if 'impact_category' in filters and filters['impact_category']:
                categories = []
                category_list = filters['impact_category']
                if not isinstance(category_list, list):
                    category_list = [category_list]
                    
                for cat_str in category_list:
                    try:
                        categories.append(ImpactCategoryEnum(cat_str))
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid impact_category value: {cat_str}, ignoring")
                        continue
                        
                if categories:
                    query_obj = query_obj.join(
                        LegislationAnalysis,
                        Legislation.id == LegislationAnalysis.legislation_id,
                        isouter=True
                    ).filter(LegislationAnalysis.impact_category.in_(categories))
                    
            # Process impact level filters
            if 'impact_level' in filters and filters['impact_level']:
                impact_levels = []
                level_list = filters['impact_level']
                if not isinstance(level_list, list):
                    level_list = [level_list]
                    
                for level_str in level_list:
                    try:
                        impact_levels.append(ImpactLevelEnum(level_str))
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid impact_level value: {level_str}, ignoring")
                        continue
                        
                if impact_levels:
                    # Only join if we haven't already joined with LegislationAnalysis
                    if 'impact_category' not in filters or not filters['impact_category']:
                        query_obj = query_obj.join(
                            LegislationAnalysis,
                            Legislation.id == LegislationAnalysis.legislation_id,
                            isouter=True
                        )
                    query_obj = query_obj.filter(LegislationAnalysis.impact.in_(impact_levels))
                    
            # Handle reviewed_only filter for manually reviewed bills
            if 'reviewed_only' in filters and filters['reviewed_only'] and HAS_PRIORITY_MODEL:
                query_obj = query_obj.join(
                    LegislationPriority,
                    Legislation.id == LegislationPriority.legislation_id,
                    isouter=True
                ).filter(LegislationPriority.manually_reviewed == True)
                
            # Count total before applying limit/offset for pagination
            total = query_obj.count()
                
            # Determine the appropriate sort field and direction
            if sort_by == "date":
                sort_field = Legislation.bill_introduced_date
            elif sort_by == "updated":
                sort_field = Legislation.updated_at
            elif sort_by == "status":
                sort_field = Legislation.bill_status
            elif sort_by == "title":
                sort_field = func.lower(Legislation.title)
            elif sort_by == "priority" and HAS_PRIORITY_MODEL:
                # If sorting by priority, ensure we join with the priority table
                if not any(isinstance(mapper.class_, LegislationPriority.__class__) 
                          for mapper in getattr(query_obj, '_join_entities', [])):
                    query_obj = query_obj.outerjoin(
                        LegislationPriority,
                        Legislation.id == LegislationPriority.legislation_id
                    )
                sort_field = LegislationPriority.overall_priority
            else:
                # Default sort by ID if sort_by is "relevance" or unknown
                sort_field = Legislation.id
                
            # Apply sort direction
            if sort_dir == "asc":
                query_obj = query_obj.order_by(asc(sort_field))
            else:
                query_obj = query_obj.order_by(desc(sort_field))
            
            # Calculate pagination metadata
            page_size = limit if limit > 0 else total
            current_page = (offset // page_size) + 1 if page_size > 0 else 1
            total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1
            has_next = offset + limit < total
            has_prev = offset > 0
            
            # Apply limit and offset for pagination
            query_obj = query_obj.limit(limit).offset(offset)
            
            # Execute query
            results = query_obj.options(
                joinedload(Legislation.priority) if HAS_PRIORITY_MODEL else None
            ).all()
            
            # Format the results
            items = []
            for leg in results:
                item = {
                    "id": leg.id,
                    "bill_number": leg.bill_number,
                    "title": leg.title,
                    "govt_source": leg.govt_source,
                    "govt_type": leg.govt_type.value if leg.govt_type else None,
                    "bill_status": leg.bill_status.value if leg.bill_status else None,
                    "bill_introduced_date": leg.bill_introduced_date.isoformat() if leg.bill_introduced_date else None,
                    "updated_at": leg.updated_at.isoformat() if leg.updated_at else None,
                    "priority": None
                }
                
                # Add priority if available
                if HAS_PRIORITY_MODEL and hasattr(leg, 'priority') and leg.priority:
                    item["priority"] = leg.priority.overall_priority
                    item["public_health_relevance"] = leg.priority.public_health_relevance
                    item["local_govt_relevance"] = leg.priority.local_govt_relevance
                    item["reviewed"] = leg.priority.manually_reviewed
                    
                items.append(item)
                
            # Generate facets for filtering UI
            facets = self._generate_search_facets(filters)
            
            # Create pagination metadata
            page_info = {
                "current_page": current_page,
                "total_pages": total_pages,
                "page_size": page_size,
                "has_next_page": has_next,
                "has_prev_page": has_prev,
                "next_offset": offset + limit if has_next else None,
                "prev_offset": max(0, offset - limit) if has_prev else None,
                "total_count": total
            }
            
            return {
                "count": total, 
                "items": items, 
                "facets": facets,
                "page_info": page_info
            }
            
        except SQLAlchemyError as e:
            error_msg = f"Database error performing advanced search: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error performing advanced search: {e}"
            logger.error(error_msg, exc_info=True)
            return {"count": 0, "items": [], "facets": {}, "page_info": {"current_page": 1, "total_pages": 0, "total_count": 0}}
            
    def _generate_search_facets(self, applied_filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate facet counts for search filters based on current legislation in the database.
        
        Args:
            applied_filters: Currently applied filters to exclude from counts
            
        Returns:
            Dictionary with facet information for filtering UI
        """
        try:
            facets = {}
            
            # Status facets
            status_counts = (
                self.db_session.query(Legislation.bill_status, func.count(Legislation.id))
                .filter(Legislation.bill_status.isnot(None))
                .group_by(Legislation.bill_status)
                .all()
            )
            facets["status"] = [
                {"value": status.value, "label": status.value.title(), "count": count}
                for status, count in status_counts if status
            ]
            
            # Government type facets
            govt_type_counts = (
                self.db_session.query(Legislation.govt_type, func.count(Legislation.id))
                .filter(Legislation.govt_type.isnot(None))
                .group_by(Legislation.govt_type)
                .all()
            )
            facets["govt_type"] = [
                {"value": govt_type.value, "label": govt_type.value.title(), "count": count}
                for govt_type, count in govt_type_counts if govt_type
            ]
            
            # Impact category facets (if available)
            if hasattr(LegislationAnalysis, 'impact_category'):
                impact_cat_counts = (
                    self.db_session.query(LegislationAnalysis.impact_category, func.count(LegislationAnalysis.id))
                    .filter(LegislationAnalysis.impact_category.isnot(None))
                    .group_by(LegislationAnalysis.impact_category)
                    .all()
                )
                facets["impact_category"] = [
                    {
                        "value": cat.value, 
                        "label": cat.value.replace('_', ' ').title(), 
                        "count": count
                    }
                    for cat, count in impact_cat_counts if cat
                ]
                
            # Impact level facets (if available)
            if hasattr(LegislationAnalysis, 'impact'):
                impact_level_counts = (
                    self.db_session.query(LegislationAnalysis.impact, func.count(LegislationAnalysis.id))
                    .filter(LegislationAnalysis.impact.isnot(None))
                    .group_by(LegislationAnalysis.impact)
                    .all()
                )
                facets["impact_level"] = [
                    {
                        "value": level.value, 
                        "label": level.value.title(), 
                        "count": count
                    }
                    for level, count in impact_level_counts if level
                ]
                
            # Date range facets (current year, last year, older)
            current_year = datetime.now().year
            this_year_count = (
                self.db_session.query(func.count(Legislation.id))
                .filter(func.extract('year', Legislation.bill_introduced_date) == current_year)
                .scalar() or 0
            )
            last_year_count = (
                self.db_session.query(func.count(Legislation.id))
                .filter(func.extract('year', Legislation.bill_introduced_date) == current_year - 1)
                .scalar() or 0
            )
            older_count = (
                self.db_session.query(func.count(Legislation.id))
                .filter(func.extract('year', Legislation.bill_introduced_date) < current_year - 1)
                .scalar() or 0
            )
            
            facets["year"] = [
                {"value": str(current_year), "label": f"{current_year}", "count": this_year_count},
                {"value": str(current_year - 1), "label": f"{current_year - 1}", "count": last_year_count},
                {"value": "older", "label": "Older", "count": older_count}
            ]
                
            return facets
        except SQLAlchemyError as e:
            logger.error(f"Error generating search facets: {e}", exc_info=True)
            return {}
            
    @ensure_connection
    @validate_inputs(lambda self, legislation_id, update_data: (
        self._validate_legislation_id(legislation_id),
        self._validate_priority_data(update_data)
    ))
    def update_legislation_priority(self, legislation_id: int, update_data: Dict[str, Any]) -> Optional[PriorityData]:
        """
        Update priority scores for legislation. Creates a new priority record if one doesn't exist.
        
        Args:
            legislation_id: The ID of the legislation
            update_data: Dictionary with fields to update
            
        Returns:
            Updated priority data or None if not updated
            
        Raises:
            ValidationError: If inputs are invalid
            DatabaseOperationError: On database errors
        """
        try:
            # Check for LegislationPriority model
            if not HAS_PRIORITY_MODEL:
                logger.warning("LegislationPriority model not available - cannot update priority")
                return None
                
            # Check if legislation exists
            legislation = self.db_session.query(Legislation).filter_by(id=legislation_id).first()
            if not legislation:
                logger.warning(f"Legislation with ID {legislation_id} not found")
                raise ValidationError(f"Legislation with ID {legislation_id} not found")
                
            # Create transaction for update
            with self.transaction():
                # Get or create priority record
                priority = legislation.priority
                if not priority:
                    from models import LegislationPriority
                    priority = LegislationPriority(legislation_id=legislation_id)
                    self.db_session.add(priority)
                    
                # Update fields from provided data
                if 'public_health_relevance' in update_data:
                    priority.public_health_relevance = update_data['public_health_relevance']
                    
                if 'local_govt_relevance' in update_data:
                    priority.local_govt_relevance = update_data['local_govt_relevance']
                    
                if 'overall_priority' in update_data:
                    priority.overall_priority = update_data['overall_priority']
                    
                if 'notes' in update_data:
                    priority.reviewer_notes = update_data['notes']
                    
                # Mark as manually reviewed
                priority.manually_reviewed = True
                priority.review_date = datetime.utcnow()
                
                # Flush changes
                self.db_session.flush()
                
            # Return updated priority data
            return {
                "public_health_relevance": priority.public_health_relevance,
                "local_govt_relevance": priority.local_govt_relevance,
                "overall_priority": priority.overall_priority,
                "manually_reviewed": priority.manually_reviewed,
                "reviewer_notes": priority.reviewer_notes,
                "review_date": priority.review_date.isoformat() if priority.review_date else None
            }
        except ValidationError:
            # Re-raise validation errors
            raise
        except SQLAlchemyError as e:
            self.db_session.rollback()
            error_msg = f"Database error updating priority for legislation {legislation_id}: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg)
        except Exception as e:
            self.db_session.rollback()
            error_msg = f"Unexpected error updating priority for legislation {legislation_id}: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg)
    
    def _validate_legislation_id(self, legislation_id: int) -> None:
        """
        Validate that legislation_id is a positive integer.
        
        Args:
            legislation_id: The legislation ID to validate
            
        Raises:
            ValidationError: If legislation_id is invalid
        """
        if not isinstance(legislation_id, int) or legislation_id <= 0:
            raise ValidationError(f"legislation_id must be a positive integer, got {legislation_id}")
            
    def _validate_priority_data(self, update_data: Dict[str, Any]) -> None:
        """
        Validate priority update data.
        
        Args:
            update_data: The priority data to validate
            
        Raises:
            ValidationError: If update_data is invalid
        """
        if not isinstance(update_data, dict):
            raise ValidationError(f"Priority update data must be a dictionary, got {type(update_data).__name__}")
            
        # Ensure at least one valid field is provided
        valid_fields = ['public_health_relevance', 'local_govt_relevance', 'overall_priority', 'notes']
        if not any(field in update_data for field in valid_fields):
            raise ValidationError(f"At least one of {', '.join(valid_fields)} must be provided")
            
        # Validate score fields are integers between 0 and 100
        for field in ['public_health_relevance', 'local_govt_relevance', 'overall_priority']:
            if field in update_data:
                if not isinstance(update_data[field], int):
                    raise ValidationError(f"{field} must be an integer, got {type(update_data[field]).__name__}")
                if update_data[field] < 0 or update_data[field] > 100:
                    raise ValidationError(f"{field} must be between 0 and 100, got {update_data[field]}")
                    
        # Validate notes is a string if provided
        if 'notes' in update_data and not isinstance(update_data['notes'], str):
            raise ValidationError(f"notes must be a string, got {type(update_data['notes']).__name__}")
            
    @ensure_connection
    def get_sync_history(self, limit: int = 10) -> List[SyncHistoryRecord]:
        """
        Retrieve the history of synchronization operations.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of sync history records
            
        Raises:
            ValidationError: If limit is invalid
            DatabaseOperationError: On database errors
        """
        # Validate limit
        if not isinstance(limit, int) or limit <= 0:
            raise ValidationError(f"limit must be a positive integer, got {limit}")
            
        try:
            # Query SyncMetadata with limit
            sync_records = self.db_session.query(SyncMetadata).order_by(
                SyncMetadata.last_sync.desc()
            ).limit(limit).all()
            
            # Format result
            history: List[SyncHistoryRecord] = []
            for sync in sync_records:
                history.append({
                    "id": sync.id,
                    "last_sync": sync.last_sync.isoformat() if sync.last_sync else None,
                    "last_successful_sync": sync.last_successful_sync.isoformat() if sync.last_successful_sync else None,
                    "status": sync.status.value if sync.status else None,
                    "sync_type": sync.sync_type,
                    "new_bills": sync.new_bills,
                    "bills_updated": sync.bills_updated,
                    "errors": sync.errors
                })
                
            return history
        except SQLAlchemyError as e:
            error_msg = f"Database error retrieving sync history: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error retrieving sync history: {e}"
            logger.error(error_msg, exc_info=True)
            return []

    @ensure_connection
    def get_pending_analyses(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Returns legislation records that have no associated analysis yet.
        Useful for queuing up analyses.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of legislation records without analysis
            
        Raises:
            ValidationError: If limit is invalid
            DatabaseOperationError: On database errors
        """
        # Validate limit
        if not isinstance(limit, int) or limit <= 0:
            raise ValidationError(f"limit must be a positive integer, got {limit}")
            
        try:
            # Subquery to get legislation IDs that already have analysis
            analyzed_ids = self.db_session.query(
                LegislationAnalysis.legislation_id
            ).distinct().subquery()
            
            # Query for legislation without analysis
            pending_legislation = self.db_session.query(Legislation).filter(
                ~Legislation.id.in_(analyzed_ids)
            ).order_by(
                Legislation.updated_at.desc()
            ).limit(limit).all()
            
            # Format results
            result = []
            for leg in pending_legislation:
                leg_dict = {
                    "id": leg.id,
                    "bill_number": leg.bill_number,
                    "title": leg.title,
                    "govt_source": leg.govt_source,
                    "govt_type": leg.govt_type.value if leg.govt_type else None,
                    "bill_status": leg.bill_status.value if leg.bill_status else None,
                    "created_at": leg.created_at.isoformat() if leg.created_at else None,
                    "updated_at": leg.updated_at.isoformat() if leg.updated_at else None,
                    "has_text": leg.latest_text is not None
                }
                result.append(leg_dict)
                
            return result
        except SQLAlchemyError as e:
            error_msg = f"Database error retrieving pending analyses: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error retrieving pending analyses: {e}"
            logger.error(error_msg, exc_info=True)
            return []

    @ensure_connection
    def get_all_priorities(self) -> List[Dict[str, Any]]:
        """
        Returns all priority records for dashboard display.
        
        Returns:
            List of priority records with legislation details
            
        Raises:
            DatabaseOperationError: On database errors
        """
        if not HAS_PRIORITY_MODEL:
            logger.warning("LegislationPriority model not available - cannot get priorities")
            return []
            
        try:
            # Query for all legislation with priority records
            from models import LegislationPriority
            
            priority_records = self.db_session.query(
                LegislationPriority, Legislation
            ).join(
                Legislation, LegislationPriority.legislation_id == Legislation.id
            ).order_by(
                LegislationPriority.overall_priority.desc()
            ).all()
            
            # Format result
            result = []
            for priority, leg in priority_records:
                result.append({
                    "legislation_id": leg.id,
                    "bill_number": leg.bill_number,
                    "title": leg.title,
                    "public_health_relevance": priority.public_health_relevance,
                    "local_govt_relevance": priority.local_govt_relevance,
                    "overall_priority": priority.overall_priority,
                    "manually_reviewed": priority.manually_reviewed,
                    "reviewer_notes": priority.reviewer_notes,
                    "review_date": priority.review_date.isoformat() if priority.review_date else None,
                    "auto_categorized": priority.auto_categorized,
                    "bill_status": leg.bill_status.value if leg.bill_status else None,
                    "bill_introduced_date": leg.bill_introduced_date.isoformat() if leg.bill_introduced_date else None
                })
                
            return result
        except SQLAlchemyError as e:
            error_msg = f"Database error retrieving priorities: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error retrieving priorities: {e}"
            logger.error(error_msg, exc_info=True)
            return []                    