"""
api.py

A production-ready FastAPI application that exposes REST endpoints for:
 - Users & Preferences
 - Legislation listing, search, detail
 - Texas-specific legislation for public health and local governments
 - Triggering AI-based analysis on legislation
 - Dashboard analytics for impact assessment

Key features:
 - Comprehensive input validation with Pydantic models
 - Consistent error handling and appropriate HTTP status codes
 - Proper resource management with dependency injection
 - Background task processing with cleanup
 - Detailed API documentation with examples
 - Type safety throughout the codebase

Requirements:
   pip install fastapi uvicorn sqlalchemy openai psycopg2

Run:
   uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import logging
import traceback
from typing import Optional, List, Dict, Any, Type, Union, Callable, TypeVar, cast, AsyncGenerator
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from functools import wraps

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, Response, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, EmailStr, HttpUrl, field_validator, model_validator, constr, conint, confloat, AnyUrl
from pydantic import ValidationError as PydanticValidationError
from contextlib import asynccontextmanager

# 1) Import your custom modules
from data_store import DataStore, ConnectionError, ValidationError, DatabaseOperationError, BillStore
from ai_analysis import AIAnalysis, analyze_bill
from legiscan_api import LegiScanAPI
from models import (
    BillStatusEnum,
    ImpactLevelEnum,
    ImpactCategoryEnum,
    DataSourceEnum,
    GovtTypeEnum,
    Legislation
)

# 2) Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# -----------------------------------------------------------------------------
# Application Lifecycle Handler
# -----------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifecycle event handler for setup and teardown of application resources.
    """
    global data_store, ai_analyzer, legiscan_api

    # Startup: Initialize resources
    try:
        data_store = DataStore(max_retries=3)
        # Ensure db_session is available before initializing other services
        if not data_store.db_session:
            raise ValueError("Database session is not initialized")

        ai_analyzer = AIAnalysis(db_session=data_store.db_session)
        legiscan_api = LegiScanAPI(db_session=data_store.db_session, api_key=os.getenv("LEGISCAN_API_KEY"))
        logger.info("Services initialized on startup.")
    except Exception as e:
        logger.critical(f"Failed to initialize services: {e}", exc_info=True)
        raise

    # Yield control back to FastAPI - make sure this is awaitable
    yield

    # Shutdown: Clean up resources
    if data_store:
        try:
            data_store.close()
            logger.info("DataStore closed on shutdown.")
        except Exception as e:
            logger.error(f"Error closing DataStore: {e}", exc_info=True)

    # Set global variables to None
    data_store = None
    ai_analyzer = None
    legiscan_api = None

# 3) Prepare the FastAPI application
app = FastAPI(
    title="PolicyPulse API",
    description="Legislation tracking and analysis for public health and local government",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development, in production specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5) Provide service instances for the whole app
data_store: Optional[DataStore] = None
ai_analyzer: Optional[AIAnalysis] = None
legiscan_api: Optional[LegiScanAPI] = None

# Initialize data store
bill_store = BillStore()

# Models
class BillSummary(BaseModel):
    bill_id: int
    state: str
    bill_number: str
    title: str
    description: str
    status: str
    last_action: Optional[str] = None
    last_action_date: Optional[str] = None

class BillDetail(BillSummary):
    text: Optional[str] = None
    sponsors: List[str] = []
    history: List[dict] = []
    votes: List[dict] = []

class AnalysisResult(BaseModel):
    summary: str
    key_points: List[str]
    potential_impacts: str
    sentiment: float

# -----------------------------------------------------------------------------
# Custom Exception Handlers
# -----------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler for validation errors to provide more user-friendly error messages.

    Args:
        request: The request that caused the validation error
        exc: The validation error

    Returns:
        JSONResponse with detailed error information
    """
    errors = []
    for error in exc.errors():
        error_location = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "location": error_location,
            "message": error["msg"],
            "type": error["type"]
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Input validation error",
            "details": errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Generic exception handler to provide consistent error responses.

    Args:
        request: The request that caused the exception
        exc: The exception that was raised

    Returns:
        JSONResponse with error details
    """
    # Log the error with traceback
    logger.error(f"Unhandled exception processing {request.method} {request.url}: {exc}")
    logger.error(traceback.format_exc())

    # Return a standard error response
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "An unexpected error occurred",
            "error_type": type(exc).__name__
        }
    )

# -----------------------------------------------------------------------------
# Utility Functions and Decorators
# -----------------------------------------------------------------------------
def log_api_call(func: Callable):
    """
    Decorator to log API calls with timing information.

    Args:
        func: The API endpoint function to wrap

    Returns:
        Wrapped function with logging
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):  # Removed request: Request = None
        request = kwargs.get('request')  # Retrieve request from kwargs
        if request is None:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

        if request is None:
            raise ValueError("Request object must be provided to the `wrapper` function.")

        # Get client IP and method+path
        client_ip = request.client.host if request and hasattr(request, 'client') and request.client is not None else 'unknown'
        endpoint = f"{request.method} {request.url.path}" if request else func.__name__

        # Log the request
        logger.info(f"API call from {client_ip}: {endpoint}")

        # Track timing
        start_time = datetime.now()
        try:
            # Execute the endpoint function
            response = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            # Log successful completion with timing
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"API call completed: {endpoint} ({elapsed:.2f}ms)")
            return response
        except Exception as e:
            # Log exception with timing
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"API call failed: {endpoint} ({elapsed:.2f}ms) - {str(e)}")
            raise

    return wrapper


@contextmanager
def error_handler(operation_name: str, error_map: Optional[Dict[Type[Exception], int]] = None):
    """
    Context manager for consistent error handling in API endpoints.

    Args:
        operation_name: Name of the operation for logging
        error_map: Mapping of exception types to HTTP status codes

    Yields:
        Control to the wrapped code block

    Raises:
        HTTPException: With the appropriate status code and detail message
    """
    # Default error mapping if none provided
    if error_map is None:
        error_map = {
            ValidationError: status.HTTP_400_BAD_REQUEST,
            ConnectionError: status.HTTP_503_SERVICE_UNAVAILABLE,
            DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            Exception: status.HTTP_500_INTERNAL_SERVER_ERROR
        }

    try:
        yield
    except tuple(error_map.keys()) as e:
        # Get the exception type
        exc_type = type(e)

        # Find the most specific matching exception type in the error map
        matching_types = [t for t in error_map.keys() if issubclass(exc_type, t)]
        most_specific_type = min(matching_types, key=lambda t: len(t.__mro__))

        # Get the status code for this exception type
        status_code = error_map[most_specific_type]

        # Log the error with appropriate severity
        if status_code >= 500:
            logger.error(f"Error in {operation_name}: {e}", exc_info=True)
        else:
            logger.warning(f"Error in {operation_name}: {e}")

        # Raise HTTPException with appropriate status code and detail
        raise HTTPException(
            status_code=status_code,
            detail=f"{operation_name} failed: {str(e)}"
        )


def run_in_background(func):
    """
    Decorator to run a function in a background task with proper error handling.

    Args:
        func: The function to run in the background

    Returns:
        Wrapped function that executes in a background task
    """
    @wraps(func)
    def wrapper(background_tasks: BackgroundTasks, *args, **kwargs):
        # Define a wrapper that handles exceptions
        def background_wrapper():
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in background task {func.__name__}: {e}", exc_info=True)

        # Add the task to the background tasks list
        background_tasks.add_task(background_wrapper)

        # Return a simple status message
        return {
            "status": "processing",
            "message": f"Task {func.__name__} started in the background"
        }

    return wrapper


# -----------------------------------------------------------------------------
# Pydantic Models for request/response bodies
# -----------------------------------------------------------------------------
class UserPrefsPayload(BaseModel):
    """Request model for user preferences."""
    keywords: List[str] = Field(default_factory=list, description="User-defined keywords for tracking legislation")
    health_focus: List[str] = Field(default_factory=list, description="Health department focus areas")
    local_govt_focus: List[str] = Field(default_factory=list, description="Local government focus areas")
    regions: List[str] = Field(default_factory=list, description="Texas regions of interest")

    @field_validator('keywords', 'health_focus', 'local_govt_focus', 'regions')
    def validate_string_lists(cls, v):
        """Validate that list items are non-empty strings."""
        if not all(isinstance(item, str) and item.strip() for item in v):
            raise ValueError("All list items must be non-empty strings")
        return [item.strip() for item in v]

    class Config:
        schema_extra = {
            "example": {
                "keywords": ["healthcare", "funding", "education"],
                "health_focus": ["mental health", "preventative care"],
                "local_govt_focus": ["zoning", "public safety"],
                "regions": ["Central Texas", "Gulf Coast"]
            }
        }


class UserSearchPayload(BaseModel):
    """Request/response model for search history."""
    query: str = Field(..., min_length=1, description="Search query string")
    results: Dict[str, Any] = Field(default_factory=dict, description="Search result metadata")

    class Config:
        schema_extra = {
            "example": {
                "query": "healthcare funding",
                "results": {"total_hits": 42, "search_time_ms": 156}
            }
        }


class AIAnalysisPayload(BaseModel):
    """Request model for AI analysis options."""
    model_name: Optional[str] = Field(None, description="Name of the AI model to use for analysis")
    focus_areas: Optional[List[str]] = Field(None, description="Specific areas to focus the analysis on")
    force_refresh: bool = Field(False, description="Whether to force a refresh of existing analysis")

    @field_validator('model_name')
    def validate_model_name(cls, v):
        """Validate that the model name is a recognized model."""
        if v is not None:
            valid_models = ["gpt-4o", "gpt-4o-2024-08-06", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]
            if v not in valid_models and not v.startswith(tuple(valid_models)):
                raise ValueError(f"Model name '{v}' is not a recognized model. Valid options include: {', '.join(valid_models)}")
        return v

    class Config:
        schema_extra = {
            "example": {
                "model_name": "gpt-4o",
                "focus_areas": ["public health", "local government"],
                "force_refresh": False
            }
        }


class AnalysisOptions(BaseModel):
    """Options for controlling analysis behavior."""
    deep_analysis: bool = Field(False, description="Whether to perform a more thorough analysis")
    texas_focus: bool = Field(True, description="Whether to focus analysis on Texas impacts")
    focus_areas: Optional[List[str]] = Field(None, description="Specific areas to focus the analysis on")
    model_name: Optional[str] = Field(None, description="Name of the AI model to use for analysis")

    @field_validator('focus_areas')
    def validate_focus_areas(cls, v):
        """Validate that focus areas are valid."""
        if v is not None:
            valid_areas = ["public health", "local government", "economic", "environmental", "healthcare", 
                           "social services", "education", "infrastructure", "justice"]
            for area in v:
                if area.lower() not in valid_areas:
                    raise ValueError(f"'{area}' is not a recognized focus area")
        return v

    @field_validator('model_name')
    def validate_model_name(cls, v):
        """Validate that the model name is a recognized model."""
        if v is not None:
            valid_models = ["gpt-4o", "gpt-4o-2024-08-06", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]
            if v not in valid_models and not v.startswith(tuple(valid_models)):
                raise ValueError(f"Model name '{v}' is not a recognized model. Valid options include: {', '.join(valid_models)}")
        return v

    class Config:
        schema_extra = {
            "example": {
                "deep_analysis": True,
                "texas_focus": True,
                "focus_areas": ["public health", "municipal governments"],
                "model_name": "gpt-4o"
            }
        }


class DateRange(BaseModel):
    """Model representing a date range for filtering."""
    start_date: str = Field(..., pattern="^\\d{4}-\\d{2}-\\d{2}$", description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., pattern="^\\d{4}-\\d{2}-\\d{2}$", description="End date in YYYY-MM-DD format")

    @field_validator('end_date')
    def end_date_must_be_after_start_date(cls, v, values):
        """Validate that end date is after start date."""
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

    @field_validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        """Validate that dates are in a valid format."""
        try:
            datetime.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid date format: {v}. Expected YYYY-MM-DD")


class BillSearchFilters(BaseModel):
    """Model for search filters."""
    bill_status: Optional[List[str]] = Field(None, description="Filter by bill status values")
    impact_category: Optional[List[str]] = Field(None, description="Filter by impact category")
    impact_level: Optional[List[str]] = Field(None, description="Filter by impact level")
    govt_type: Optional[List[str]] = Field(None, description="Filter by government type")
    date_range: Optional[DateRange] = Field(None, description="Filter by date range")
    reviewed_only: Optional[bool] = Field(None, description="Filter to only include reviewed legislation")

    @field_validator('bill_status')
    def validate_bill_status(cls, v):
        """Validate bill status values."""
        if v is not None:
            valid_statuses = [status.value for status in BillStatusEnum]
            for status in v:
                if status not in valid_statuses:
                    raise ValueError(f"Invalid bill_status: {status}. Valid values: {', '.join(valid_statuses)}")
        return v

    @field_validator('impact_category')
    def validate_impact_category(cls, v):
        """Validate impact category values."""
        if v is not None:
            valid_categories = [cat.value for cat in ImpactCategoryEnum]
            for category in v:
                if category not in valid_categories:
                    raise ValueError(f"Invalid impact_category: {category}. Valid values: {', '.join(valid_categories)}")
        return v

    @field_validator('impact_level')
    def validate_impact_level(cls, v):
        """Validate impact level values."""
        if v is not None:
            valid_levels = [level.value for level in ImpactLevelEnum]
            for level in v:
                if level not in valid_levels:
                    raise ValueError(f"Invalid impact_level: {level}. Valid values: {', '.join(valid_levels)}")
        return v

    @field_validator('govt_type')
    def validate_govt_type(cls, v):
        """Validate government type values."""
        if v is not None:
            valid_types = [gtype.value for gtype in GovtTypeEnum]
            for gtype in v:
                if gtype not in valid_types:
                    raise ValueError(f"Invalid govt_type: {gtype}. Valid values: {', '.join(valid_types)}")
        return v


class BillSearchQuery(BaseModel):
    """Advanced search parameters."""
    query: str = Field("", description="Search query string")
    filters: BillSearchFilters = Field(default_factory=lambda: BillSearchFilters(), description="Search filters")
    sort_by: str = Field("relevance", description="Field to sort results by")
    sort_dir: str = Field("desc", description="Sort direction (asc or desc)")
    limit: int = Field(50, description="Maximum number of results to return", ge=1, le=100)
    offset: int = Field(0, description="Number of results to skip", ge=0)

    @field_validator('sort_by')
    def validate_sort_by(cls, v):
        """Validate sort field is supported."""
        valid_sort_fields = ["relevance", "date", "updated", "status", "title", "priority"]
        if v not in valid_sort_fields:
            raise ValueError(f"sort_by must be one of: {', '.join(valid_sort_fields)}")
        return v

    @field_validator('sort_dir')
    def validate_sort_dir(cls, v):
        """Ensure sort direction is valid."""
        if v not in ['asc', 'desc']:
            raise ValueError('sort_dir must be either "asc" or "desc"')
        return v

    class Config:
        schema_extra = {
            "example": {
                "query": "healthcare funding",
                "filters": {
                    "bill_status": ["introduced", "passed"],
                    "impact_category": ["public_health"],
                    "impact_level": ["high", "critical"],
                    "govt_type": ["federal", "state"],
                    "date_range": {
                        "start_date": "2023-01-01",
                        "end_date": "2023-12-31"
                    },
                    "reviewed_only": True
                },
                "sort_by": "priority",
                "sort_dir": "desc",
                "limit": 20,
                "offset": 0
            }
        }


class SetPriorityPayload(BaseModel):
    """Manual priority setting payload."""
    public_health_relevance: Optional[int] = Field(
        None, description="Public health relevance score (0-100)", ge=0, le=100
    )
    local_govt_relevance: Optional[int] = Field(
        None, description="Local government relevance score (0-100)", ge=0, le=100
    )
    overall_priority: Optional[int] = Field(
        None, description="Overall priority score (0-100)", ge=0, le=100
    )
    notes: Optional[str] = Field(None, description="Reviewer notes")

    @model_validator(mode='after')
    def check_at_least_one_field(self):
        """Ensure at least one field is provided."""
        if not any(getattr(self, field) is not None for field in ['public_health_relevance', 'local_govt_relevance', 'overall_priority', 'notes']):
            raise ValueError('At least one field must be provided')
        return self

    class Config:
        schema_extra = {
            "example": {
                "public_health_relevance": 85,
                "local_govt_relevance": 70,
                "overall_priority": 80,
                "notes": "Significant impact on local health departments' funding"
            }
        }


# Response models
class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""
    status: str = Field(..., description="API status")
    message: str = Field(..., description="Status message")
    version: str = Field(..., description="API version")


class UserPreferencesResponse(BaseModel):
    """Response model for user preferences."""
    email: str = Field(..., description="User email")
    preferences: Dict[str, Any] = Field(..., description="User preferences")


class SearchHistoryResponse(BaseModel):
    """Response model for search history."""
    email: str = Field(..., description="User email")
    history: List[Dict[str, Any]] = Field(..., description="Search history items")


class LegislationListResponse(BaseModel):
    """Response model for legislation listing endpoints."""
    count: int = Field(..., description="Number of items returned")
    items: List[Dict[str, Any]] = Field(..., description="Legislation items")
    page_info: Dict[str, Any] = Field(default_factory=dict, description="Pagination metadata")
    facets: Optional[Dict[str, Any]] = Field(None, description="Search facets for filtering")


class AnalysisStatusResponse(BaseModel):
    """Response model for analysis status."""
    status: str = Field(..., description="Analysis status (processing or completed)")
    message: Optional[str] = Field(None, description="Status message")
    legislation_id: int = Field(..., description="Legislation ID")
    analysis_id: Optional[int] = Field(None, description="Analysis ID if completed")
    analysis_version: Optional[str] = Field(None, description="Analysis version if completed")
    analysis_date: Optional[str] = Field(None, description="Analysis date if completed")


class AnalysisHistoryResponse(BaseModel):
    """Response model for analysis history."""
    legislation_id: int = Field(..., description="Legislation ID")
    analysis_count: int = Field(..., description="Number of analyses")
    analyses: List[Dict[str, Any]] = Field(..., description="Analysis history items")


class PriorityUpdateResponse(BaseModel):
    """Response model for priority updates."""
    status: str = Field(..., description="Update status")
    message: str = Field(..., description="Status message")
    priority: Dict[str, Any] = Field(..., description="Updated priority values")


class SyncStatusResponse(BaseModel):
    """Response model for sync status."""
    sync_history: List[Dict[str, Any]] = Field(..., description="Sync history records")
    count: int = Field(..., description="Number of sync records")


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------
def get_data_store() -> DataStore:
    """
    Dependency that yields the global data_store.

    Returns:
        DataStore instance

    Raises:
        HTTPException: If DataStore is not initialized
    """
    if not data_store:
        logger.critical("Attempted to access DataStore before initialization")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please try again later."
        )
    return data_store


def get_ai_analyzer() -> AIAnalysis:
    """
    Dependency that yields the global ai_analyzer.

    Returns:
        AIAnalysis instance

    Raises:
        HTTPException: If AIAnalysis is not initialized
    """
    if not ai_analyzer:
        logger.critical("Attempted to access AIAnalysis before initialization")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI analysis service unavailable. Please try again later."
        )
    return ai_analyzer


def get_legiscan_api() -> LegiScanAPI:
    """
    Dependency that yields the global legiscan_api.

    Returns:
        LegiScanAPI instance

    Raises:
        HTTPException: If LegiScanAPI is not initialized
    """
    if not legiscan_api:
        logger.critical("Attempted to access LegiScanAPI before initialization")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Legislative data service unavailable. Please try again later."
        )
    return legiscan_api


# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------
@app.get("/health", tags=["Utility"], response_model=HealthResponse)
@log_api_call
def health_check():
    """
    Basic health endpoint to verify the API is alive.

    Returns:
        Health status information
    """
    return {
        "status": "ok", 
        "message": "PolicyPulse API up and running", 
        "version": "2.0.0"
    }


# -----------------------------------------------------------------------------
# User & Preferences
# -----------------------------------------------------------------------------
@app.post("/users/{email}/preferences", tags=["User"], response_model=Dict[str, str])
@log_api_call
def update_user_preferences(
    email: str,
    prefs: UserPrefsPayload,
    store: DataStore = Depends(get_data_store)
):
    """
    Update or create user preferences for the given email.
    This includes keywords, health focus areas, local government focus areas,
    and regions of interest.

    Args:
        email: User's email address
        prefs: Preference data
        store: DataStore instance

    Returns:
        Status message

    Raises:
        HTTPException: If email is invalid or preferences cannot be saved
    """
    with error_handler("Update user preferences", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        ConnectionError: status.HTTP_503_SERVICE_UNAVAILABLE,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Convert payload to dict for storage
        prefs_dict = prefs.dict(exclude_unset=True)

        # Save preferences
        success = store.save_user_preferences(email, prefs_dict)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update preferences."
            )

        return {
            "status": "success", 
            "message": f"Preferences updated for {email}"
        }


@app.get("/users/{email}/preferences", tags=["User"], response_model=UserPreferencesResponse)
@log_api_call
def get_user_preferences(
    email: str,
    store: DataStore = Depends(get_data_store)
):
    """
    Retrieve user preferences for the given email, including focus areas
    and regions of interest.

    Args:
        email: User's email address
        store: DataStore instance

    Returns:
        User preferences

    Raises:
        HTTPException: If email is invalid
    """
    with error_handler("Get user preferences", {
        ValidationError: status.HTTP_400_BAD_REQUEST
    }):
        prefs = store.get_user_preferences(email)
        return {"email": email, "preferences": prefs}


# -----------------------------------------------------------------------------
# Search History
# -----------------------------------------------------------------------------
@app.post("/users/{email}/search", tags=["Search"], response_model=Dict[str, str])
@log_api_call
def add_search_history(
    email: str,
    payload: UserSearchPayload,
    store: DataStore = Depends(get_data_store)
):
    """
    Add search history item for a user.

    Args:
        email: User email address
        payload: Search query and results
        store: DataStore instance

    Returns:
        Status message

    Raises:
        HTTPException: If email is invalid or search history cannot be saved
    """
    with error_handler("Add search history", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        ok = store.add_search_history(email, payload.query, payload.results)

        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add search history."
            )

        return {
            "status": "success", 
            "message": f"Search recorded for {email}"
        }


@app.get("/users/{email}/search", tags=["Search"], response_model=SearchHistoryResponse)
@log_api_call
def get_search_history(
    email: str,
    store: DataStore = Depends(get_data_store)
):
    """
    Retrieve search history for a user.

    Args:
        email: User email address
        store: DataStore instance

    Returns:
        Search history items

    Raises:
        HTTPException: If email is invalid
    """
    with error_handler("Get search history", {
        ValidationError: status.HTTP_400_BAD_REQUEST
    }):
        history = store.get_search_history(email)
        return {"email": email, "history": history}


# -----------------------------------------------------------------------------
# Basic Legislation Endpoints
# -----------------------------------------------------------------------------
@app.get("/legislation", tags=["Legislation"], response_model=LegislationListResponse)
@log_api_call
def list_legislation(
    limit: int = 50,
    offset: int = 0,
    store: DataStore = Depends(get_data_store)
):
    """
    Returns a paginated list of legislation records.

    Args:
        limit: Maximum number of results to return
        offset: Number of results to skip
        store: DataStore instance

    Returns:
        Paginated legislation list

    Raises:
        HTTPException: If pagination parameters are invalid
    """
    with error_handler("List legislation", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Validate pagination parameters
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")
        if offset < 0:
            raise ValidationError("Offset cannot be negative")

        result = store.list_legislation(limit=limit, offset=offset)
        return {
            "count": result["total_count"], 
            "items": result["items"],
            "page_info": result.get("page_info", {})
        }


@app.get("/legislation/{leg_id}", tags=["Legislation"])
@log_api_call
def get_legislation_detail(
    leg_id: int,
    store: DataStore = Depends(get_data_store)
):
    """
    Retrieve a single legislation record with detail, including
    latest text and analysis if present.

    Args:
        leg_id: Legislation ID
        store: DataStore instance

    Returns:
        Detailed legislation information

    Raises:
        HTTPException: If legislation is not found or ID is invalid
    """
    with error_handler("Get legislation details", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Validate legislation ID
        if leg_id <= 0:
            raise ValidationError("Legislation ID must be a positive integer")

        details = store.get_legislation_details(leg_id)
        if not details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Legislation with ID {leg_id} not found"
            )

        return details


@app.get("/legislation/search", tags=["Legislation"], response_model=LegislationListResponse)
@log_api_call
def search_legislation(
    keywords: str,
    store: DataStore = Depends(get_data_store)
):
    """
    Search for legislation whose title or description contains the given keywords (comma-separated).
    Example: /legislation/search?keywords=health,education

    Args:
        keywords: Comma-separated list of keywords
        store: DataStore instance

    Returns:
        Legislation items matching the keywords

    Raises:
        HTTPException: If keywords are invalid
    """
    with error_handler("Search legislation", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        if not keywords or not keywords.strip():
            raise ValidationError("Keywords parameter cannot be empty")

        # Parse keywords
        kws = [kw.strip() for kw in keywords.split(",") if kw.strip()]
        if not kws:
            return {"count": 0, "items": [], "page_info": {}}

        # Using the advanced_search method with keyword query
        search_results = store.advanced_search(
            query="",  # No text query
            filters={"keywords": kws},
            sort_by="date",
            sort_dir="desc",
            limit=50,
            offset=0
        )

        return {
            "count": search_results["count"], 
            "items": search_results["items"],
            "page_info": search_results.get("page_info", {}),
            "facets": search_results.get("facets", {})
        }


# -----------------------------------------------------------------------------
# Texas-Focused Endpoints
# -----------------------------------------------------------------------------
@app.get("/texas/health-legislation", tags=["Texas"], response_model=LegislationListResponse)
@log_api_call
def list_texas_health_legislation(
    limit: int = 50,
    offset: int = 0,
    bill_status: Optional[str] = None,  # Changed from 'status' to 'bill_status'
    impact_level: Optional[str] = None,
    introduced_after: Optional[str] = None,
    keywords: Optional[str] = None,
    relevance_threshold: Optional[int] = None,
    store: DataStore = Depends(get_data_store)
):
    """
    Returns legislation relevant to Texas public health departments,
    with filtering options.

    Args:
        limit: Maximum number of results to return
        offset: Number of results to skip
        bill_status: Filter by bill status
        impact_level: Filter by impact level
        introduced_after: Filter by bills introduced after date (YYYY-MM-DD)
        keywords: Comma-separated list of keywords
        relevance_threshold: Minimum relevance score (0-100)
        store: DataStore instance

    Returns:
        Filtered legislation list

    Raises:
        HTTPException: If filter parameters are invalid
    """
    with error_handler("List Texas health legislation", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        Exception: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Validate pagination parameters
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")
        if offset < 0:
            raise ValidationError("Offset cannot be negative")

        # Validate optional parameters
        if bill_status and bill_status not in [s.value for s in BillStatusEnum]:
            raise ValidationError(f"Invalid bill_status: {bill_status}")

        if impact_level and impact_level not in [il.value for il in ImpactLevelEnum]:
            raise ValidationError(f"Invalid impact_level: {impact_level}")

        if introduced_after:
            try:
                datetime.fromisoformat(introduced_after)
            except ValueError:
                raise ValidationError(f"Invalid introduced_after date: {introduced_after}. Format should be YYYY-MM-DD")

        if relevance_threshold is not None and (relevance_threshold < 0 or relevance_threshold > 100):
            raise ValidationError("Relevance threshold must be between 0 and 100")

        # Build filters
        filters = {}

        if bill_status:
            filters["status"] = bill_status
        if impact_level:
            filters["impact_level"] = impact_level
        if introduced_after:
            filters["introduced_after"] = introduced_after
        if keywords:
            filters["keywords"] = [k.strip() for k in keywords.split(",") if k.strip()]
        if relevance_threshold is not None:
            filters["relevance_threshold"] = relevance_threshold

        # Get legislation
        legislation = store.get_texas_health_legislation(limit=limit, offset=offset, filters=filters)

        # Format as LegislationListResponse
        return {"count": len(legislation), "items": legislation}


@app.get("/texas/local-govt-legislation", tags=["Texas"], response_model=LegislationListResponse)
@log_api_call
def list_texas_local_govt_legislation(
    limit: int = 50,
    offset: int = 0,
    bill_status: Optional[str] = None,  # Changed from 'status' to 'bill_status'
    impact_level: Optional[str] = None,
    introduced_after: Optional[str] = None,
    keywords: Optional[str] = None,
    municipality_type: Optional[str] = None,
    relevance_threshold: Optional[int] = None,
    store: DataStore = Depends(get_data_store)
):
    """
    Returns legislation relevant to Texas local governments,
    with filtering options including municipality type.

    Args:
        limit: Maximum number of results to return
        offset: Number of results to skip
        bill_status: Filter by bill status
        impact_level: Filter by impact level
        introduced_after: Filter by bills introduced after date (YYYY-MM-DD)
        keywords: Comma-separated list of keywords
        municipality_type: Type of municipality (city, county, school, special)
        relevance_threshold: Minimum relevance score (0-100)
        store: DataStore instance

    Returns:
        Filtered legislation list

    Raises:
        HTTPException: If filter parameters are invalid
    """
    with error_handler("List Texas local government legislation", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        Exception: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Validate pagination parameters
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")
        if offset < 0:
            raise ValidationError("Offset cannot be negative")

        # Validate optional parameters
        if bill_status and bill_status not in [s.value for s in BillStatusEnum]:
            raise ValidationError(f"Invalid bill_status: {bill_status}")

        if impact_level and impact_level not in [il.value for il in ImpactLevelEnum]:
            raise ValidationError(f"Invalid impact_level: {impact_level}")

        if introduced_after:
            try:
                datetime.fromisoformat(introduced_after)
            except ValueError:
                raise ValidationError(f"Invalid introduced_after date: {introduced_after}. Format should be YYYY-MM-DD")

        if municipality_type and municipality_type not in ["city", "county", "school", "special"]:
            raise ValidationError(f"Invalid municipality_type: {municipality_type}. Must be one of: city, county, school, special")

        if relevance_threshold is not None and (relevance_threshold < 0 or relevance_threshold > 100):
            raise ValidationError("Relevance threshold must be between 0 and 100")

        # Build filters
        filters = {"focus": "local_govt"}  # Set focus to local government

        if bill_status:
            filters["status"] = bill_status
        if impact_level:
            filters["impact_level"] = impact_level
        if introduced_after:
            filters["introduced_after"] = introduced_after
        if keywords:
            filters["keywords"] = ",".join([k.strip() for k in keywords.split(",") if k.strip()])
        if municipality_type:
            filters["municipality_type"] = municipality_type
        if relevance_threshold is not None:
            filters["relevance_threshold"] = str(relevance_threshold)

        # Get legislation
        legislation = store.get_texas_health_legislation(limit=limit, offset=offset, filters=filters)

        # Format as LegislationListResponse
        return {"count": len(legislation), "items": legislation}

# -----------------------------------------------------------------------------
# Dashboard Analytics
# -----------------------------------------------------------------------------
@app.get("/dashboard/impact-summary", tags=["Dashboard"])
@log_api_call
def get_impact_summary(
    impact_type: str = "public_health",
    time_period: str = "current",
    store: DataStore = Depends(get_data_store)
):
    """
    Returns summary statistics on legislation impacts for dashboard display.

    Args:
        impact_type: Type of impact to summarize (public_health, local_gov, economic)
        time_period: Time period to cover (current, past_month, past_year, all)
        store: DataStore instance

    Returns:
        Impact summary statistics

    Raises:
        HTTPException: If parameters are invalid
    """
    with error_handler("Get impact summary", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Validate parameters
        valid_impact_types = ["public_health", "local_gov", "economic", "environmental", "education"]
        if impact_type not in valid_impact_types:
            raise ValidationError(f"Invalid impact_type: {impact_type}. Must be one of: {', '.join(valid_impact_types)}")

        valid_time_periods = ["current", "past_month", "past_year", "all"]
        if time_period not in valid_time_periods:
            raise ValidationError(f"Invalid time_period: {time_period}. Must be one of: {', '.join(valid_time_periods)}")

        # Get summary data
        return store.get_impact_summary(impact_type=impact_type, time_period=time_period)


# Ensure the store dependency is correctly provided and setup
@app.get("/dashboard/recent-activity", tags=["Dashboard"])
@log_api_call
def get_recent_activity(
    days: int = 30,
    limit: int = 10,
    store: DataStore = Depends(get_data_store)
):
    """
    Returns recent legislative activity for dashboard display.

    Args:
        days: Number of days to look back
        limit: Maximum number of results to return
        store: DataStore instance

    Returns:
        Recent legislative activity

    Raises:
        HTTPException: If parameters are invalid
    """
    # Ensure db_session is initialized
    if not store.db_session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session is not initialized. Please try again later."
        )

    with error_handler("Get recent activity", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        Exception: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Validate parameters
        if days < 1 or days > 365:
            raise ValidationError("Days must be between 1 and 365")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            # Use the store's db_session to query for recently updated legislation
            recent_legs = store.db_session.query(Legislation).filter(
                Legislation.updated_at >= cutoff_date
            ).order_by(Legislation.updated_at.desc()).limit(limit).all()

            # Format response
            activity = []
            for leg in recent_legs:
                activity.append({
                    "id": leg.id,
                    "bill_number": leg.bill_number,
                    "title": leg.title,
                    "status": leg.bill_status if leg.bill_status else None,
                    "updated_at": leg.updated_at.isoformat() if leg.updated_at else None,
                    "govt_type": leg.govt_type if leg.govt_type else None
                })

            return {"recent_legislation": activity, "time_period_days": days}
        except Exception as e:
            logger.error(f"Error getting recent activity: {e}", exc_info=True)
            raise


# -----------------------------------------------------------------------------
# Advanced Search
# -----------------------------------------------------------------------------
@app.post("/search/advanced", tags=["Search"], response_model=LegislationListResponse)
@log_api_call
def advanced_search(
    search_params: BillSearchQuery,
    store: DataStore = Depends(get_data_store)
):
    """
    Performs advanced search with filtering, sorting and faceted results.

    Args:
        search_params: Search parameters and filters
        store: DataStore instance

    Returns:
        Search results with facets

    Raises:
        HTTPException: If search parameters are invalid
    """
    with error_handler("Advanced search", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Convert filters to dict, excluding None values
        filters_dict = search_params.filters.dict(exclude_none=True)

        # Execute search
        result = store.advanced_search(
            query=search_params.query,
            filters=filters_dict,
            sort_by=search_params.sort_by,
            sort_dir=search_params.sort_dir,
            limit=search_params.limit,
            offset=search_params.offset
        )

        return {
            "count": result["count"], 
            "items": result["items"],
            "page_info": result.get("page_info", {}),
            "facets": result.get("facets", {})
        }


# -----------------------------------------------------------------------------
# AI Analysis Endpoint
# -----------------------------------------------------------------------------
@app.post("/legislation/{leg_id}/analysis", tags=["Analysis"], response_model=AnalysisStatusResponse)
@log_api_call
def analyze_legislation_ai(
    leg_id: int,
    options: Optional[AnalysisOptions] = None,
    background_tasks: Optional[BackgroundTasks] = None,
    analyzer: AIAnalysis = Depends(get_ai_analyzer),
    store: DataStore = Depends(get_data_store)
):
    """
    Trigger an AI-based structured analysis for the specified Legislation ID.

    Args:
        leg_id: Legislation ID to analyze
        options: Optional analysis parameters
        background_tasks: FastAPI background tasks for async processing
        analyzer: AIAnalysis instance
        store: DataStore instance

    Returns:
        Analysis status and results

    Raises:
        HTTPException: If legislation is not found or analysis fails
    """
    with error_handler("AI analysis", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        Exception: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Validate legislation ID
        if leg_id <= 0:
            raise ValidationError("Legislation ID must be a positive integer")

        # Check if db_session is available and retrieve the legislation
        if store.db_session is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                detail="Database session is not initialized. Please try again later."
            )

        # Check if legislation exists
        leg_obj = store.db_session.query(Legislation).filter_by(id=leg_id).first()
        if not leg_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Legislation with ID {leg_id} not found"
            )

        # Set default options if none provided
        if options is None:
            options = AnalysisOptions(deep_analysis=False, texas_focus=True, focus_areas=None, model_name=None)

        # Asynchronous processing if requested and background_tasks available
        if background_tasks and options.deep_analysis:
            async def run_analysis_task():
                try:
                    analyzer.analyze_legislation(legislation_id=leg_id)
                except Exception as e:
                    logger.error(f"Error in background analysis task for legislation ID={leg_id}: {e}", exc_info=True)

            # Add task to background tasks
            background_tasks.add_task(run_analysis_task)

            return {
                "status": "processing", 
                "message": "Analysis started in the background. Check back later.",
                "legislation_id": leg_id
            }

        # Synchronous processing
        try:
            # Set model parameters if needed
            if hasattr(options, "model_name") and options.model_name:
                analyzer.model_name = options.get("model_name", "default_model") if isinstance(options, dict) else "default_model"  # type: ignore

            # Run analysis
            analysis_obj = analyzer.analyze_legislation(legislation_id=leg_id)

            return {
                "status": "completed",
                "legislation_id": leg_id,
                "analysis_id": analysis_obj.id,
                "analysis_version": analysis_obj.analysis_version,
                "analysis_date": analysis_obj.analysis_date.isoformat() if analysis_obj.analysis_date else None
            }
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
        except Exception as e:
            logger.error(f"Error analyzing legislation ID={leg_id} with AI: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI analysis failed.")


@app.get("/legislation/{leg_id}/analysis/history", tags=["Analysis"], response_model=AnalysisHistoryResponse)
@log_api_call
def get_legislation_analysis_history(
    leg_id: int,
    store: DataStore = Depends(get_data_store)
):
    """
    Returns the history of analyses for a legislation, showing how assessments
    have changed over time.

    Args:
        leg_id: Legislation ID
        store: DataStore instance

    Returns:
        Analysis history

    Raises:
        HTTPException: If legislation is not found or analysis history cannot be retrieved
    """
    with error_handler("Get analysis history", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        Exception: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Validate legislation ID
        if leg_id <= 0:
            raise ValidationError("Legislation ID must be a positive integer")

        # Check if legislation exists
        leg = store.db_session.query(Legislation).filter_by(id=leg_id).first() if store.db_session else None
        if not leg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Legislation with ID {leg_id} not found"
            )

        # Get and format analyses
        analyses = []
        sorted_analyses = sorted(leg.analyses, key=lambda a: a.analysis_version)

        for analysis in sorted_analyses:
            analyses.append({
                "id": analysis.id,
                "version": analysis.analysis_version,
                "date": analysis.analysis_date.isoformat() if analysis.analysis_date else None,
                "summary": analysis.summary,
                "impact_category": analysis.impact_category.value if analysis.impact_category else None,
                "impact_level": analysis.impact.value if hasattr(analysis, 'impact') and analysis.impact else None,
                "model_version": analysis.model_version
            })

        return {
            "legislation_id": leg_id,
            "analysis_count": len(analyses),
            "analyses": analyses
        }


# -----------------------------------------------------------------------------
# Priority Update
# -----------------------------------------------------------------------------
@app.post("/legislation/{leg_id}/priority", tags=["Priority"], response_model=PriorityUpdateResponse)
@log_api_call
def update_priority(
    leg_id: int,
    payload: SetPriorityPayload,
    store: DataStore = Depends(get_data_store)
):
    """
    Update the priority scores for a specific legislation.

    Args:
        leg_id: Legislation ID
        payload: Priority data to update
        store: DataStore instance

    Returns:
        Updated priority data

    Raises:
        HTTPException: If legislation is not found or priority cannot be updated
    """
    with error_handler("Update priority", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        Exception: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Validate legislation ID
        if leg_id <= 0:
            raise ValidationError("Legislation ID must be a positive integer")

        try:
            # Check if legislation exists
            leg = store.db_session.query(Legislation).filter_by(id=leg_id).first() if store.db_session else None
            if not leg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Legislation with ID {leg_id} not found"
                )

            # Check if LegislationPriority model is available
            try:
                from models import LegislationPriority
                has_priority_model = True
            except ImportError:
                has_priority_model = False
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail="Priority updates not supported: LegislationPriority model not available"
                )

            # Use the DataStore method to update priority
            update_data = payload.model_dump(exclude_unset=True)
            updated_priority = store.update_legislation_priority(leg_id, update_data)

            if not updated_priority:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update priority"
                )

            return {
                "status": "success",
                "message": f"Priority updated for legislation ID {leg_id}",
                "priority": updated_priority
            }

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Error updating priority for legislation {leg_id}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# -----------------------------------------------------------------------------
# Sync Status
# -----------------------------------------------------------------------------
@app.get("/sync/status", tags=["Sync"], response_model=SyncStatusResponse)
@log_api_call
def get_sync_status(
    store: DataStore = Depends(get_data_store)
):
    """
    Retrieve the history of sync operations.

    Args:
        store: DataStore instance

    Returns:
        Sync history records

    Raises:
        HTTPException: If sync history cannot be retrieved
    """
    with error_handler("Get sync status", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        Exception: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        try:
            # Get sync history from data store
            sync_history = store.get_sync_history(limit=10)

            return {
                "sync_history": sync_history,
                "count": len(sync_history)
            }
        except Exception as e:
            logger.error(f"Error retrieving sync history: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# -----------------------------------------------------------------------------
# Manual Sync Endpoint
# -----------------------------------------------------------------------------
@app.post("/sync/trigger", tags=["Sync"])
@log_api_call
def trigger_sync(
    force: bool = False,
    background_tasks: Optional[BackgroundTasks] = None,
    api: LegiScanAPI = Depends(get_legiscan_api)
):
    """
    Manually trigger a synchronization with LegiScan.

    Args:
        force: Whether to force a sync even if one was recently run
        background_tasks: FastAPI background tasks for async processing
        api: LegiScanAPI instance

    Returns:
        Status of the sync operation

    Raises:
        HTTPException: If sync fails or API is unavailable
    """
    with error_handler("Trigger sync", {
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        Exception: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Run sync in background if background_tasks is available
        if background_tasks:
            async def run_sync_task():
                try:
                    api.run_sync(sync_type="manual")
                except Exception as e:
                    logger.error(f"Error in background sync task: {e}", exc_info=True)

            # Add task to background tasks
            background_tasks.add_task(run_sync_task)

            return {
                "status": "processing",
                "message": "Sync operation started in the background"
            }

        # Run sync synchronously
        try:
            # Run a sync operation
            result = api.run_sync(sync_type="manual")

            return {
                "status": "success",
                "message": "Sync operation completed successfully",
                "details": {
                    "new_bills": result["new_bills"],
                    "bills_updated": result["bills_updated"],
                    "error_count": len(result["errors"]),
                    "start_time": result["start_time"].isoformat() if result["start_time"] else None,
                    "end_time": result["end_time"].isoformat() if result["end_time"] else None
                }
            }
        except Exception as e:
            logger.error(f"Error triggering sync: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Add missing imports if needed at the top of the file
try:
    import asyncio
except ImportError:
    pass

@app.get("/")
async def root():
    """Root endpoint to verify API is running."""
    return {"message": "Legislative Analysis API is running"}

@app.get("/bills/", response_model=List[BillSummary])
async def get_bills(
    state: Optional[str] = Query(None, description="Filter by state (e.g., 'CA', 'NY')"),
    keyword: Optional[str] = Query(None, description="Search by keyword in title or description"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of bills to return"),
    offset: int = Query(0, ge=0, description="Number of bills to skip")
):
    """
    Get a list of bills with optional filtering.
    """
    try:
        bills = bill_store.get_bills(state=state, keyword=keyword, limit=limit, offset=offset)
        return bills
    except Exception as e:
        logger.error(f"Error retrieving bills: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving bills: {str(e)}")

@app.get("/bills/{bill_id}", response_model=BillDetail)
async def get_bill(bill_id: int):
    """
    Get detailed information about a specific bill.
    """
    try:
        bill = bill_store.get_bill(bill_id)
        if not bill:
            raise HTTPException(status_code=404, detail=f"Bill with ID {bill_id} not found")
        return bill
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving bill {bill_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving bill: {str(e)}")

@app.get("/bills/{bill_id}/analysis", response_model=AnalysisResult)
async def get_bill_analysis(bill_id: int):
    """
    Get AI analysis for a specific bill.
    """
    try:
        # Get the bill details
        bill = bill_store.get_bill(bill_id)
        if not bill:
            raise HTTPException(status_code=404, detail=f"Bill with ID {bill_id} not found")

        # Check if bill has text
        if not bill.get("text"):
            # Try to fetch text from LegiScan if not available
            try:
                bill_text = legiscan_api.get_bill_text(bill_id) if legiscan_api else None
                if bill_text:
                    # Update the bill in the store with the text
                    bill["text"] = bill_text
                    bill_store.update_bill(bill)
                else:
                    raise HTTPException(status_code=404, detail="Bill text not available")
            except Exception as e:
                logger.error(f"Error fetching bill text from LegiScan: {str(e)}")
                raise HTTPException(status_code=404, detail="Bill text not available")

        # Analyze the bill
        analysis = analyze_bill(
            bill_text=bill["text"],
            bill_title=bill.get("title"),
            state=bill.get("state")
        )

        return analysis
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing bill {bill_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing bill: {str(e)}")

@app.get("/states/", response_model=List[str])
async def get_states():
    """
    Get a list of available states.
    """
    try:
        states = bill_store.get_states()
        return states
    except Exception as e:
        logger.error(f"Error retrieving states: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving states: {str(e)}")

@app.post("/refresh/")
async def refresh_data(state: Optional[str] = None):
    """
    Refresh bill data from LegiScan API.
    """
    try:
        # This would typically be an admin-only endpoint with authentication
        count = bill_store.refresh_from_legiscan(legiscan_api, state=state)
        return {"message": f"Successfully refreshed {count} bills"}
    except Exception as e:
        logger.error(f"Error refreshing data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error refreshing data: {str(e)}")

@app.post("/legislation/{leg_id}/analysis/async", tags=["Analysis"], response_model=AnalysisStatusResponse)
@log_api_call
async def analyze_legislation_ai_async(
    leg_id: int,
    options: Optional[AnalysisOptions] = None,
    analyzer: AIAnalysis = Depends(get_ai_analyzer),
    store: DataStore = Depends(get_data_store)
):
    """
    Trigger an asynchronous AI-based structured analysis for the specified Legislation ID.

    Args:
        leg_id: Legislation ID to analyze
        options: Optional analysis parameters
        analyzer: AIAnalysis instance
        store: DataStore = Depends(get_data_store)

    Returns:
        Analysis status and results
    """
    with error_handler("Async AI analysis", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        Exception: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        # Validate legislation ID
        if leg_id <= 0:
            raise ValidationError("Legislation ID must be a positive integer")

        # Query the legislation object
        leg_obj = store.db_session.query(Legislation).filter_by(id=leg_id).first() if store.db_session else None
        if not leg_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Legislation with ID {leg_id} not found"
            )

        # Set default options if none provided
        if options is None:
            options = AnalysisOptions(
                deep_analysis=False,
                texas_focus=True,
                focus_areas=None,
                model_name=None
            )

        try:
            if hasattr(options, "model_name") and options.model_name:
                analyzer.model_name = options.get("model_name", "default_model") if isinstance(options, dict) else "default_model"  # type: ignore

            # Run analysis asynchronously
            analysis_obj = await analyzer.analyze_legislation_async(legislation_id=leg_id)

            return {
                "status": "completed",
                "legislation_id": leg_id,
                "analysis_id": analysis_obj.id,
                "analysis_version": analysis_obj.analysis_version,
                "analysis_date": analysis_obj.analysis_date.isoformat() if analysis_obj.analysis_date else None
            }
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
        except Exception as e:
            logger.error(f"Error analyzing legislation ID={leg_id} with AI: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Async AI analysis failed.")

@app.post("/legislation/batch-analyze", tags=["Analysis"])
@log_api_call
async def batch_analyze_legislation(
    legislation_ids: List[int], 
    max_concurrent: int = Query(5, ge=1, le=10, description="Maximum number of concurrent analyses"),
    analyzer: AIAnalysis = Depends(get_ai_analyzer)
):
    """
    Analyze multiple pieces of legislation in parallel.

    Args:
        legislation_ids: List of legislation IDs to analyze
        max_concurrent: Maximum number of concurrent analyses
        analyzer: AIAnalysis instance

    Returns:
        Results of batch analysis
    """
    with error_handler("Batch analyze legislation", {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DatabaseOperationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        Exception: status.HTTP_500_INTERNAL_SERVER_ERROR
    }):
        if not legislation_ids:
            raise ValidationError("No legislation IDs provided")

        if len(legislation_ids) > 50:  # Set a reasonable limit
            raise ValidationError("Too many legislation IDs (maximum 50)")

        # Run batch analysis
        try:
            results = await analyzer.batch_analyze_async(legislation_ids, max_concurrent)
            return results
        except Exception as e:
            logger.error(f"Error in batch analysis: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Batch analysis failed: {str(e)}"
            )