"""
models.py

SQLAlchemy-based data models for the PolicyPulse legislative tracking system.
Includes:
  - A BaseModel with audit fields
  - User-related models (User, UserPreference, SearchHistory, AlertPreference, AlertHistory)
  - Legislation models (Legislation, LegislationText, LegislationAnalysis, LegislationSponsor, Amendment,
    LegislationPriority, ImpactRating, ImplementationRequirement)
  - Synchronization metadata and error tracking models
  - Database initialization logic with robust error handling and connection retries

This module is designed with extensibility and clarity in mind, using PostgreSQL-specific features
(where applicable) and JSONB for flexible data storage. It implements proper type handling for
both text and binary content and provides comprehensive field validation.
"""

import enum
import os
import time
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional, Union, Callable, Type, cast, TYPE_CHECKING

from sqlalchemy import (create_engine, Column, Integer, String, DateTime, Text,
                        LargeBinary, ForeignKey, Boolean, UniqueConstraint,
                        Index, Float, Enum as SQLEnum, func, and_, or_, text,
                        event)
from sqlalchemy.dialects.postgresql import JSONB, BYTEA
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session, validates
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.engine import Engine
from sqlalchemy.event import listen
from sqlalchemy_utils import TSVectorType
from sqlalchemy.types import TypeDecorator
from sqlalchemy import event
# Configure logging for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create the base class for declarative models
Base = declarative_base()

tz = ZoneInfo('America/Chicago')
dt = datetime.now(tz)


# -----------------------------------------------------------------------------
# 1) Abstract Base Model with Audit Fields
# -----------------------------------------------------------------------------
class BaseModel(Base):
    """
    Abstract base model that provides common audit fields for all inheriting models.

    Attributes:
        created_at: Timestamp when the record was created
        updated_at: Timestamp when the record was last updated
        created_by: User who created the record
        updated_by: User who last updated the record
    """
    __abstract__ = True

    created_at = Column(
        DateTime(timezone=True),
        default=func.now(),  # Use function reference
        nullable=False,
        doc="Timestamp when the record was created")
    updated_at = Column(
        DateTime(timezone=True),
        default=func.now(),  # Use function reference
        onupdate=func.now(),  # Use function reference
        nullable=False,
        doc="Timestamp when the record was last updated")
    created_by = Column(String(50),
                        nullable=True,
                        doc="User who created the record")
    updated_by = Column(String(50),
                        nullable=True,
                        doc="User who last updated the record")


# -----------------------------------------------------------------------------
# 2) Custom Type for Text/Binary Content
# -----------------------------------------------------------------------------
class FlexibleContentType(TypeDecorator):
    """
    A custom SQLAlchemy type that can store both text and binary content.
    For PostgreSQL, uses Text for text content and BYTEA for binary content.
    For other databases, uses LargeBinary which can store both types but
    requires explicit type handling when retrieving.

    This type automatically detects if the content is text or binary based on the
    input data type and stores it accordingly.
    """
    impl = Text  # Default implementation is Text
    cache_ok = True

    def __init__(self, binary_type=None, **kwargs):
        """
        Initialize the flexible content type.

        Args:
            binary_type: SQLAlchemy column type to use for binary data (defaults to BYTEA for PostgreSQL)
            **kwargs: Additional keyword arguments for the column
        """
        self.binary_type = binary_type or BYTEA
        super().__init__(**kwargs)

    def load_dialect_impl(self, dialect):
        """
        Load the appropriate dialect implementation.

        Args:
            dialect: SQLAlchemy dialect

        Returns:
            Dialect-specific implementation type
        """
        if dialect.name == 'postgresql':
            # PostgreSQL can use Text for strings and BYTEA for binary
            return dialect.type_descriptor(self.impl)
        else:
            # For other databases, use LargeBinary which can store both
            return dialect.type_descriptor(LargeBinary)

    def process_bind_param(self, value, dialect) -> Optional[str]:
        if value is None:
            return None

        if isinstance(value, str):
            return value

        if isinstance(value, bytes):
            # Decode bytes for all dialects, even PostgreSQL.
            return value.decode('utf-8', errors='replace')

        return str(value)

    def process_result_value(self, value, dialect):
        """
        Process the value retrieved from the database.

        Args:
            value: The value retrieved
            dialect: SQLAlchemy dialect

        Returns:
            Processed value ready for Python
        """
        if value is None:
            return None

        # If it's bytes, return as is (binary content)
        if isinstance(value, bytes):
            return value

        # If it's a string, return as is
        if isinstance(value, str):
            return value

        # For any other case, return as is
        return value


# -----------------------------------------------------------------------------
# 2) Enumerations
# -----------------------------------------------------------------------------
class DataSourceEnum(enum.Enum):
    """
    Enumeration for the source of legislative data.

    Values:
        LEGISCAN: Data from the LegiScan API
        CONGRESS_GOV: Data from the Congress.gov website
        OTHER: Data from other sources
    """
    legiscan = "legiscan"
    CONGRESS_GOV = "congress_gov"
    OTHER = "other"


class GovtTypeEnum(enum.Enum):
    """
    Enumeration for government types.

    Values:
        FEDERAL: Federal government (e.g., U.S. Congress)
        STATE: State government (e.g., Texas Legislature)
        COUNTY: County government
        CITY: Municipal/city government
    """
    federal = "federal"
    state = "state"
    county = "county"
    city = "city"


class BillStatusEnum(enum.Enum):
    """
    Enumeration for legislative bill statuses.

    Values:
        NEW: Newly added to the system
        INTRODUCED: Formally introduced in the legislature
        UPDATED: Bill has been updated since introduction
        PASSED: Bill has passed the legislature
        DEFEATED: Bill has been defeated/failed
        VETOED: Bill was vetoed by the executive
        ENACTED: Bill has become law
        PENDING: Bill is pending action
    """
    NEW = "new"
    INTRODUCED = "introduced"
    UPDATED = "updated"
    PASSED = "passed"
    DEFEATED = "defeated"
    VETOED = "vetoed"
    ENACTED = "enacted"
    PENDING = "pending"


class ImpactLevelEnum(enum.Enum):
    """
    Enumeration for overall impact levels of legislation.

    Values:
        LOW: Minimal impact
        MODERATE: Moderate impact
        HIGH: Significant impact
        CRITICAL: Critical impact requiring immediate attention
    """
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactCategoryEnum(enum.Enum):
    """
    Enumeration for categorizing impacts of legislation.

    Values:
        PUBLIC_HEALTH: Impact on public health agencies and services
        LOCAL_GOV: Impact on local government operations
        ECONOMIC: Economic impact
        ENVIRONMENTAL: Environmental impact
        EDUCATION: Impact on education
        INFRASTRUCTURE: Impact on infrastructure
        HEALTHCARE: Impact on healthcare delivery
        SOCIAL_SERVICES: Impact on social services
        JUSTICE: Impact on justice system
    """
    PUBLIC_HEALTH = "public_health"
    LOCAL_GOV = "local_gov"
    ECONOMIC = "economic"
    ENVIRONMENTAL = "environmental"
    EDUCATION = "education"
    INFRASTRUCTURE = "infrastructure"
    HEALTHCARE = "healthcare"
    SOCIAL_SERVICES = "social_services"
    JUSTICE = "justice"


class AmendmentStatusEnum(enum.Enum):
    """
    Enumeration for amendment statuses.

    Values:
        PROPOSED: Amendment has been proposed but not yet voted on
        ADOPTED: Amendment has been adopted
        REJECTED: Amendment has been rejected
        WITHDRAWN: Amendment has been withdrawn by sponsor
    """
    PROPOSED = "proposed"
    ADOPTED = "adopted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class NotificationTypeEnum(enum.Enum):
    """
    Enumeration for notification types.

    Values:
        HIGH_PRIORITY: Notification for high priority legislation
        NEW_BILL: Notification for new legislation
        STATUS_CHANGE: Notification for status changes to legislation
        ANALYSIS_COMPLETE: Notification when analysis is complete
    """
    HIGH_PRIORITY = "high_priority"
    NEW_BILL = "new_bill"
    STATUS_CHANGE = "status_change"
    ANALYSIS_COMPLETE = "analysis_complete"


class SyncStatusEnum(enum.Enum):
    """
    Enumeration for synchronization process statuses.

    Values:
        PENDING: Sync operation is scheduled but not yet started
        IN_PROGRESS: Sync operation is currently running
        COMPLETED: Sync operation completed successfully
        FAILED: Sync operation failed
        PARTIAL: Sync operation completed with some errors
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# -----------------------------------------------------------------------------
# 3) User-Related Models
# -----------------------------------------------------------------------------
class User(BaseModel):
    """
    Represents an application user.

    Attributes:
        id: Primary key
        email: User's email address (unique)
        name: User's name
        is_active: Whether the user is active
        role: User's role in the system (e.g., user, admin)
        preferences: User's preferences
        searches: User's search history
        alert_preferences: User's alert preferences
        alert_history: History of alerts sent to the user
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="user")  # e.g., user, admin

    # Relationships
    preferences = relationship("UserPreference",
                               back_populates="user",
                               uselist=False,
                               cascade="all, delete-orphan")
    searches = relationship("SearchHistory",
                            back_populates="user",
                            cascade="all, delete-orphan")
    alert_preferences = relationship("AlertPreference",
                                     back_populates="user",
                                     cascade="all, delete-orphan")
    alert_history = relationship("AlertHistory",
                                 back_populates="user",
                                 cascade="all, delete-orphan")

    @validates('email')
    def validate_email(self, key, address):
        """
        Validate email format.

        Args:
            key: Attribute name ('email')
            address: Email address value

        Returns:
            Validated email address

        Raises:
            ValueError: If email format is invalid
        """
        import re
        if not isinstance(address, str):
            raise ValueError("Email must be a string")

        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
                        address):
            raise ValueError(f"Invalid email format: {address}")

        return address


class UserPreference(BaseModel):
    """
    Stores user preferences such as keywords, focus areas, and regions.

    Attributes:
        id: Primary key
        user_id: Foreign key to User
        keywords: List of keywords the user is interested in
        health_focus: Health-related focus areas
        local_govt_focus: Local government focus areas
        regions: Geographic regions of interest
        default_view: Default view preference
        items_per_page: Number of items to display per page
        sort_by: Default sort field
        user: Relationship to User
    """
    __tablename__ = 'user_preferences'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Preference settings stored as JSONB for flexibility
    keywords = Column(JSONB, nullable=True)
    health_focus = Column(JSONB, nullable=True)
    local_govt_focus = Column(JSONB, nullable=True)
    regions = Column(JSONB, nullable=True)

    # Display preferences
    default_view = Column(String(20), default="all")
    items_per_page = Column(Integer, default=25)
    sort_by = Column(String(20), default="updated_at")

    # Relationship
    user = relationship("User", back_populates="preferences")

    @validates('items_per_page')
    def validate_items_per_page(self, key, value):
        """
        Validate items_per_page is a positive integer.

        Args:
            key: Attribute name
            value: Value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If value is not a positive integer
        """
        if not isinstance(value, int) or value <= 0:
            raise ValueError("items_per_page must be a positive integer")
        return value


class SearchHistory(BaseModel):
    """
    Records user search queries and corresponding results.

    Attributes:
        id: Primary key
        user_id: Foreign key to User
        query: The search query string
        filters: Applied filters as JSON
        results: Summary of search results as JSON
        user: Relationship to User
    """
    __tablename__ = 'search_history'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    query = Column(String, nullable=True)
    filters = Column(JSONB, nullable=True)  # Applied filters as JSON
    results = Column(JSONB, nullable=True)  # Summary of search results

    user = relationship("User", back_populates="searches")


class AlertPreference(BaseModel):
    """
    Stores alert preferences for a user including channels and criteria.

    Attributes:
        id: Primary key
        user_id: Foreign key to User
        email: User's email address for notifications
        active: Whether alerts are active for this user
        alert_channels: Notification channels (e.g., email, SMS, in-app)
        custom_keywords: Custom keywords for alerts
        ignore_list: List of items to ignore
        alert_rules: Custom rules for alerts
        health_threshold: Priority threshold for health-related alerts (0-100)
        local_govt_threshold: Priority threshold for local government alerts (0-100)
        notify_on_new: Whether to notify on new legislation
        notify_on_update: Whether to notify on legislation updates
        notify_on_analysis: Whether to notify when analysis is complete
        user: Relationship to User
    """
    __tablename__ = 'alert_preferences'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    email = Column(String(255), nullable=False)
    active = Column(Boolean, default=True)

    # Notification settings (e.g., email, SMS, in-app) stored as JSONB
    alert_channels = Column(JSONB, nullable=True)
    custom_keywords = Column(JSONB, nullable=True)
    ignore_list = Column(JSONB, nullable=True)
    alert_rules = Column(JSONB, nullable=True)

    # Priority thresholds (0-100 scale)
    health_threshold = Column(Integer, default=60)
    local_govt_threshold = Column(Integer, default=60)

    # Alert toggles
    notify_on_new = Column(Boolean, default=False)
    notify_on_update = Column(Boolean, default=False)
    notify_on_analysis = Column(Boolean, default=True)

    user = relationship("User", back_populates="alert_preferences")

    @validates('health_threshold', 'local_govt_threshold')
    def validate_threshold(self, key, value):
        """
        Validate threshold values are between 0 and 100.

        Args:
            key: Attribute name
            value: Value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If value is not between 0 and 100
        """
        if not isinstance(value, int) or value < 0 or value > 100:
            raise ValueError(f"{key} must be an integer between 0 and 100")
        return value


class AlertHistory(BaseModel):
    """
    Logs the history of alerts sent to users.

    Attributes:
        id: Primary key
        user_id: Foreign key to User
        legislation_id: Foreign key to Legislation
        alert_type: Type of alert sent
        alert_content: Content of the alert
        delivery_status: Status of the delivery (e.g., sent, error, pending)
        error_message: Error message if delivery failed
        user: Relationship to User
        legislation: Relationship to Legislation
    """
    __tablename__ = 'alert_history'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    legislation_id = Column(Integer,
                            ForeignKey('legislation.id'),
                            nullable=False)

    alert_type = Column(SQLEnum(NotificationTypeEnum), nullable=False)
    alert_content = Column(Text, nullable=True)
    delivery_status = Column(String(50),
                             nullable=True)  # e.g., sent, error, pending
    error_message = Column(Text, nullable=True)

    user = relationship("User", back_populates="alert_history")
    legislation = relationship("Legislation", back_populates="alert_history")


# -----------------------------------------------------------------------------
# 4) Legislation and Related Models
# -----------------------------------------------------------------------------
class Legislation(BaseModel):
    """
    Represents a legislative bill along with its metadata and relationships.

    Attributes:
        id: Primary key
        external_id: External identifier (e.g., from LegiScan)
        data_source: Source of the legislation data
        govt_type: Type of government (federal, state, etc.)
        govt_source: Source government (e.g., "US Congress 117th")
        bill_number: Bill number (e.g., "HR 1234")
        bill_type: Type of bill (e.g., "House Bill", "Senate Resolution")
        title: Title of the bill
        description: Description or summary of the bill
        bill_status: Current status of the bill
        url: URL to the bill online
        state_link: State-specific URL to the bill
        bill_introduced_date: Date the bill was introduced
        bill_last_action_date: Date of the last action on the bill
        bill_status_date: Date of the last status change
        last_api_check: When the bill was last checked against the API
        change_hash: Hash value for change detection
        raw_api_response: Raw API response data
        search_vector: Full-text search vector
        analyses: Relationship to analyses
        texts: Relationship to text versions
        sponsors: Relationship to sponsors
        amendments: Relationship to amendments
        priority: Relationship to priority scores
        impact_ratings: Relationship to impact ratings
        implementation_requirements: Relationship to implementation requirements
        alert_history: Relationship to alert history
    """
    __tablename__ = 'legislation'

    id = Column(Integer, primary_key=True)
    external_id = Column(
        String(50),
        nullable=False)  # External identifier (e.g., from LegiScan)
    data_source = Column(SQLEnum(DataSourceEnum), nullable=False)
    govt_type = Column(SQLEnum(GovtTypeEnum), nullable=False)
    govt_source = Column(String(100),
                         nullable=False)  # e.g., "US Congress 119th"
    bill_number = Column(String(50), nullable=False)
    bill_type = Column(String(50), nullable=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    bill_status = Column(
        SQLEnum(BillStatusEnum, 
               values_callable=lambda enum_cls: [e.value for e in enum_cls],
               native_enum=True),
        default=BillStatusEnum.NEW
    )
    url = Column(Text, nullable=True)
    state_link = Column(Text, nullable=True)

    # Key dates
    bill_introduced_date = Column(DateTime, nullable=True)
    bill_last_action_date = Column(DateTime, nullable=True)
    bill_status_date = Column(DateTime, nullable=True)
    last_api_check = Column(DateTime, default=datetime.now, nullable=True)

    # API metadata
    change_hash = Column(String(50), nullable=True)
    raw_api_response = Column(JSONB, nullable=True)

    # Full-text search vector (PostgreSQL)
    search_vector = Column(TSVectorType('title', 'description'), nullable=True)

    # Relationships
    analyses = relationship("LegislationAnalysis",
                            back_populates="legislation",
                            cascade="all, delete-orphan")
    texts = relationship("LegislationText",
                         back_populates="legislation",
                         cascade="all, delete-orphan")
    sponsors = relationship("LegislationSponsor",
                            back_populates="legislation",
                            cascade="all, delete-orphan")
    amendments = relationship("Amendment",
                              back_populates="legislation",
                              cascade="all, delete-orphan")
    priority = relationship("LegislationPriority",
                            back_populates="legislation",
                            uselist=False,
                            cascade="all, delete-orphan")
    impact_ratings = relationship("ImpactRating",
                                  back_populates="legislation",
                                  cascade="all, delete-orphan")
    implementation_requirements = relationship("ImplementationRequirement",
                                               back_populates="legislation",
                                               cascade="all, delete-orphan")
    alert_history = relationship("AlertHistory",
                                 back_populates="legislation",
                                 cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('data_source',
                         'govt_source',
                         'bill_number',
                         name='unique_bill_identifier'),
        Index('idx_legislation_status', 'bill_status'),
        Index('idx_legislation_dates', 'bill_introduced_date',
              'bill_last_action_date'),
        Index('idx_legislation_change', 'change_hash'),
        Index('idx_legislation_search',
              'search_vector',
              postgresql_using='gin'),
    )

    @property
    def latest_analysis(self) -> Optional["LegislationAnalysis"]:
        """
        Return the most recent analysis based on version number.

        Returns:
            The most recent LegislationAnalysis or None if no analyses exist
        """
        if self.analyses:
            return sorted(self.analyses, key=lambda a: a.analysis_version)[-1]
        return None

    @property
    def latest_text(self) -> Optional["LegislationText"]:
        """
        Return the most recent text version based on version number.

        Returns:
            The most recent LegislationText or None if no text versions exist
        """
        if self.texts:
            return sorted(self.texts, key=lambda t: t.version_num)[-1]
        return None

    @validates('title')
    def validate_title(self, key, value):
        """
        Validate that title is not empty.

        Args:
            key: Attribute name
            value: Value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If title is empty
        """
        if not value or not value.strip():
            raise ValueError("Legislation title cannot be empty")
        return value


class LegislationAnalysis(BaseModel):
    """
    Stores AI-generated analysis of legislation with versioning.
    Captures summaries, key points, impacts, and recommendations.

    Attributes:
        id: Primary key
        legislation_id: Foreign key to Legislation
        analysis_version: Version number of the analysis
        version_tag: Tag for the version (e.g., 'initial', 'revised')
        previous_version_id: ID of the previous version of this analysis
        changes_from_previous: Changes from the previous version
        analysis_date: Date of the analysis
        impact_category: Primary impact category
        impact: Overall impact level
        summary: Summary of the legislation
        key_points: Key points from the analysis
        public_health_impacts: Impacts on public health
        local_gov_impacts: Impacts on local government
        economic_impacts: Economic impacts
        environmental_impacts: Environmental impacts
        education_impacts: Education impacts
        infrastructure_impacts: Infrastructure impacts
        stakeholder_impacts: Impacts on stakeholders
        recommended_actions: Recommended actions
        immediate_actions: Actions that should be taken immediately
        resource_needs: Resources needed for implementation
        raw_analysis: Raw analysis data
        model_version: Version of the AI model used
        confidence_score: Confidence score of the analysis
        processing_time: Time taken to process the analysis (milliseconds)
        legislation: Relationship to Legislation
        child_analyses: Relationship to child analyses
        parent_analysis: Relationship to parent analysis
    """
    __tablename__ = 'legislation_analysis'

    id = Column(Integer, primary_key=True)
    legislation_id = Column(Integer,
                            ForeignKey('legislation.id'),
                            nullable=False)

    # Versioning fields
    analysis_version = Column(Integer, default=1, nullable=False)
    version_tag = Column(String(50),
                         nullable=True)  # e.g., 'initial', 'revised'
    previous_version_id = Column(Integer,
                                 ForeignKey('legislation_analysis.id'),
                                 nullable=True)
    changes_from_previous = Column(JSONB, nullable=True)

    # Analysis metadata
    analysis_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Impact assessment
    impact_category = Column(SQLEnum(ImpactCategoryEnum), nullable=True)
    impact = Column(SQLEnum(ImpactLevelEnum), nullable=True)

    # Summary and key points
    summary = Column(Text, nullable=True)
    key_points = Column(JSONB, nullable=True)

    # Detailed impacts for various sectors
    public_health_impacts = Column(JSONB, nullable=True)
    local_gov_impacts = Column(JSONB, nullable=True)
    economic_impacts = Column(JSONB, nullable=True)
    environmental_impacts = Column(JSONB, nullable=True)
    education_impacts = Column(JSONB, nullable=True)
    infrastructure_impacts = Column(JSONB, nullable=True)
    stakeholder_impacts = Column(JSONB, nullable=True)

    # Action recommendations and resource needs
    recommended_actions = Column(JSONB, nullable=True)
    immediate_actions = Column(JSONB, nullable=True)
    resource_needs = Column(JSONB, nullable=True)

    # Raw analysis data for reference
    raw_analysis = Column(JSONB, nullable=True)

    # Additional metadata
    model_version = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)
    processing_time = Column(Integer, nullable=True)  # in milliseconds

    # Relationships
    legislation = relationship("Legislation", back_populates="analyses")
    child_analyses = relationship("LegislationAnalysis",
                                  backref="parent_analysis",
                                  remote_side=[id])

    __table_args__ = (UniqueConstraint('legislation_id',
                                       'analysis_version',
                                       name='unique_analysis_version'), )

    @validates('analysis_version')
    def validate_analysis_version(self, key, value):
        """
        Validate that analysis_version is a positive integer.

        Args:
            key: Attribute name
            value: Value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If analysis_version is not a positive integer
        """
        if not isinstance(value, int) or value <= 0:
            raise ValueError("Analysis version must be a positive integer")
        return value


class LegislationText(BaseModel):
    """
    Stores text content of a legislative bill with version tracking.
    Handles both text and binary content with proper metadata.

    Attributes:
        id: Primary key
        legislation_id: Foreign key to Legislation
        version_num: Version number of the text
        text_type: Type of text (e.g., introduced, amended, enrolled)
        text_content: The actual text content (can be text or binary)
        text_hash: Hash of the text content for change detection
        text_date: Date of this text version
        text_metadata: Metadata about the text (format, encoding, etc.)
        is_binary: Whether the content is binary
        content_type: MIME type of the content
        legislation: Relationship to Legislation
    """
    __tablename__ = 'legislation_text'

    id = Column(Integer, primary_key=True)
    legislation_id = Column(Integer,
                            ForeignKey('legislation.id'),
                            nullable=False)

    version_num = Column(Integer, default=1, nullable=False)
    text_type = Column(String(50),
                       nullable=True)  # e.g., introduced, amended, enrolled

    # Use the custom type for text content that can handle both text and binary
    text_content = Column(FlexibleContentType, nullable=True)

    text_hash = Column(String(50), nullable=True)
    text_date = Column(DateTime,
                       default=datetime.now(timezone.utc),
                       nullable=True)

    # Additional fields for content metadata
    text_metadata = Column(JSONB, nullable=True)
    is_binary = Column(Boolean, default=False)
    content_type = Column(String(100), nullable=True)  # MIME type

    legislation = relationship("Legislation", back_populates="texts")

    __table_args__ = (UniqueConstraint('legislation_id',
                                       'version_num',
                                       name='unique_text_version'), )

    @validates('version_num')
    def validate_version_num(self, key, value):
        """
        Validate that version_num is a positive integer.

        Args:
            key: Attribute name
            value: Value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If version_num is not a positive integer
        """
        if not isinstance(value, int) or value <= 0:
            raise ValueError("Version number must be a positive integer")
        return value

    def set_content(self, content: Union[str, bytes]) -> None:
        """
        Set the text_content field with appropriate metadata.
        This method handles both string and binary content types appropriately.

        Args:
            content: The content to set (either string or bytes)

        Raises:
            TypeError: If content is neither string nor bytes
        """
        if content is None:
            self.text_content = None
            self.is_binary = False
            self.content_type = None
            return

        if isinstance(content, str):
            self.text_content = content
            self.is_binary = False
            self.content_type = "text/plain"

            # Store metadata
            self.text_metadata = {
                "is_binary": False,
                "encoding": "utf-8",
                "size_bytes": len(content.encode('utf-8'))
            }
        elif isinstance(content, bytes):
            self.text_content = content
            self.is_binary = True

            # Try to detect content type from bytes signature
            content_type = self._detect_content_type(content)
            self.content_type = content_type

            # Store metadata
            self.text_metadata = {
                "is_binary": True,
                "content_type": content_type,
                "size_bytes": len(content)
            }
        else:
            raise TypeError(
                f"Content must be either string or bytes, not {type(content).__name__}"
            )

    def get_content(self) -> Union[str, bytes]:
        """
        Get the text content, handling both string and binary formats.

        Returns:
            The content as either string or bytes
        """
        if self.text_content is None:
            return "" if not self.is_binary else b""
        if self.is_binary:
            return self.text_content
        else:
            # Ensure we return a string if it's not binary
            return str(self.text_content) if not isinstance(
                self.text_content, str) else self.text_content

    def _detect_content_type(self, data: bytes) -> str:
        """
        Detect the content type based on binary signatures.

        Args:
            data: Binary data to analyze

        Returns:
            Detected MIME type or 'application/octet-stream' if unknown
        """
        # Check common file signatures
        if data.startswith(b'%PDF-'):
            return 'application/pdf'
        elif data.startswith(b'\xD0\xCF\x11\xE0'):
            return 'application/msword'  # MS Office
        elif data.startswith(b'PK\x03\x04'):
            return 'application/zip'  # ZIP (could be DOCX, XLSX)
        # Add more signatures as needed

        # Default to generic binary
        return 'application/octet-stream'


class LegislationSponsor(BaseModel):
    """
    Represents a sponsorassociated with a legislative bill.

    Attributes:
        id: Primary key
        legislation_id: Foreign key to Legislation
        sponsor_external_id: External identifier for the sponsor
        sponsor_name: Name of the sponsor
        sponsor_title: Title of the sponsor
        sponsor_state: State the sponsor represents
        sponsor_party: Political party of the sponsor
        sponsor_type: Type of sponsorship (e.g., primary, co-sponsor)
        legislation: Relationship to Legislation
    """
    __tablename__ = 'legislation_sponsors'

    id = Column(Integer, primary_key=True)
    legislation_id = Column(Integer,
                            ForeignKey('legislation.id'),
                            nullable=False)

    sponsor_external_id = Column(String(50), nullable=True)
    sponsor_name = Column(String(255), nullable=False)
    sponsor_title = Column(String(100), nullable=True)
    sponsor_state = Column(String(50), nullable=True)
    sponsor_party = Column(String(50), nullable=True)
    sponsor_type = Column(String(50),
                          nullable=True)  # e.g., primary, co-sponsor

    legislation = relationship("Legislation", back_populates="sponsors")

    @validates('sponsor_name')
    def validate_sponsor_name(self, key, value):
        """
        Validate that sponsor_name is not empty.

        Args:
            key: Attribute name
            value: Value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If sponsor_name is empty
        """
        if not value or not value.strip():
            raise ValueError("Sponsor name cannot be empty")
        return value


class Amendment(BaseModel):
    """
    Tracks amendments to legislation with a link back to the parent bill.
    Facilitates tracking the history of legislative changes.

    Attributes:
        id: Primary key
        amendment_id: External amendment ID from LegiScan
        legislation_id: Foreign key to Legislation
        adopted: Whether the amendment was adopted
        status: Status of the amendment
        amendment_date: Date of the amendment
        title: Title of the amendment
        description: Description of the amendment
        amendment_hash: Hash for change detection
        amendment_text: Text of the amendment
        amendment_url: URL to the amendment
        state_link: State-specific URL to the amendment
        chamber: Originating chamber
        sponsor_info: Information about the amendment's sponsor
        legislation: Relationship to Legislation
    """
    __tablename__ = 'amendments'

    id = Column(Integer, primary_key=True)
    amendment_id = Column(
        String(50), nullable=False)  # External amendment ID from LegiScan
    legislation_id = Column(Integer,
                            ForeignKey('legislation.id'),
                            nullable=False)

    adopted = Column(Boolean, default=False)
    status = Column(SQLEnum(AmendmentStatusEnum),
                    default=AmendmentStatusEnum.PROPOSED)
    amendment_date = Column(DateTime, nullable=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    amendment_hash = Column(String(50), nullable=True)

    amendment_text = Column(FlexibleContentType, nullable=True)
    amendment_url = Column(String(255), nullable=True)
    state_link = Column(String(255), nullable=True)

    chamber = Column(String(50), nullable=True)  # Originating chamber
    sponsor_info = Column(JSONB, nullable=True)  # Sponsor details as JSON

    # Additional metadata field for binary content
    text_metadata = Column(JSONB, nullable=True)
    is_binary_text = Column(Boolean, default=False)

    legislation = relationship("Legislation", back_populates="amendments")

    __table_args__ = (
        Index('idx_amendments_legislation', 'legislation_id'),
        Index('idx_amendments_date', 'amendment_date'),
    )

    def set_amendment_text(self, content: Union[str, bytes]) -> None:
        """
        Set the amendment_text field with appropriate metadata.

        Args:
            content: The content to set (either string or bytes)

        Raises:
            TypeError: If content is neither string nor bytes
        """
        if content is None:
            self.amendment_text = None
            self.is_binary_text = False
            return

        if isinstance(content, str):
            self.amendment_text = content
            self.is_binary_text = False
            self.text_metadata = {
                "is_binary": False,
                "encoding": "utf-8",
                "size_bytes": len(content.encode('utf-8'))
            }
        elif isinstance(content, bytes):
            self.amendment_text = content
            self.is_binary_text = True

            # Try to detect content type
            content_type = self._detect_content_type(content)

            # Store metadata
            self.text_metadata = {
                "is_binary": True,
                "content_type": content_type,
                "size_bytes": len(content)
            }
        else:
            raise TypeError(
                f"Content must be either string or bytes, not {type(content).__name__}"
            )

    def _detect_content_type(self, data: bytes) -> str:
        """
        Detect the content type based on binary signatures.

        Args:
            data: Binary data to analyze

        Returns:
            Detected MIME type or 'application/octet-stream' if unknown
        """
        # Check common file signatures
        if data.startswith(b'%PDF-'):
            return 'application/pdf'
        elif data.startswith(b'\xD0\xCF\x11\xE0'):
            return 'application/msword'  # MS Office
        elif data.startswith(b'PK\x03\x04'):
            return 'application/zip'  # ZIP (could be DOCX, XLSX)

        # Default to generic binary
        return 'application/octet-stream'


class LegislationPriority(BaseModel):
    """
    Tracks prioritization scores for legislation based on relevance to Texas public health
    and local government. Supports automatic categorization as well as manual review.

    Attributes:
        id: Primary key
        legislation_id: Foreign key to Legislation
        public_health_relevance: Relevance score for public health (0-100)
        local_govt_relevance: Relevance score for local government (0-100)
        overall_priority: Overall priority score (0-100)
        auto_categorized: Whether this was automatically categorized
        auto_categories: Automatically determined categories
        manually_reviewed: Whether this has been manually reviewed
        manual_priority: Manually set priority score (0-100)
        reviewer_notes: Notes from the reviewer
        review_date: Date of the review
        should_notify: Whether notifications should be sent
        notification_sent: Whether a notification has been sent
        notification_date: Date when notification was sent
        legislation: Relationship to Legislation
    """
    __tablename__ = 'legislation_priorities'

    id = Column(Integer, primary_key=True)
    legislation_id = Column(Integer,
                            ForeignKey('legislation.id'),
                            nullable=False)

    public_health_relevance = Column(Integer, default=0)
    local_govt_relevance = Column(Integer, default=0)
    overall_priority = Column(Integer, default=0)

    auto_categorized = Column(Boolean, default=False)
    auto_categories = Column(JSONB, nullable=True)

    manually_reviewed = Column(Boolean, default=False)
    manual_priority = Column(Integer, default=0)
    reviewer_notes = Column(Text, nullable=True)
    review_date = Column(DateTime, nullable=True)

    should_notify = Column(Boolean, default=False)
    notification_sent = Column(Boolean, default=False)
    notification_date = Column(DateTime, nullable=True)

    legislation = relationship("Legislation", back_populates="priority")

    __table_args__ = (
        Index('idx_priority_health', 'public_health_relevance'),
        Index('idx_priority_local_govt', 'local_govt_relevance'),
        Index('idx_priority_overall', 'overall_priority'),
    )

    @validates('public_health_relevance', 'local_govt_relevance',
               'overall_priority', 'manual_priority')
    def validate_score(self, key, value):
        """
        Validate that priority scores are integers between 0 and 100.

        Args:
            key: Attribute name
            value: Value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If value is not an integer between 0 and 100
        """
        if value is None:
            return 0

        if not isinstance(value, int) or value < 0 or value > 100:
            raise ValueError(f"{key} must be an integer between 0 and 100")
        return value


class ImpactRating(BaseModel):
    """
    Stores specific impact ratings for legislation based on AI analysis and manual review.
    Provides granular details on impact category, level, and confidence in the rating.

    Attributes:
        id: Primary key
        legislation_id: Foreign key to Legislation
        impact_category: Category of the impact
        impact_level: Level of the impact
        impact_description: Detailed description of the impact
        affected_entities: Entities affected by the legislation
        confidence_score: Confidence score for the rating (0.0-1.0)
        is_ai_generated: Whether the rating was generated by AI
        reviewed_by: Who reviewed the rating
        review_date: When the rating was reviewed
        legislation: Relationship to Legislation
    """
    __tablename__ = 'impact_ratings'

    id = Column(Integer, primary_key=True)
    legislation_id = Column(Integer,
                            ForeignKey('legislation.id'),
                            nullable=False)

    impact_category = Column(SQLEnum(ImpactCategoryEnum), nullable=False)
    impact_level = Column(SQLEnum(ImpactLevelEnum), nullable=False)

    impact_description = Column(Text, nullable=True)
    affected_entities = Column(JSONB, nullable=True)
    confidence_score = Column(Float, nullable=True)

    is_ai_generated = Column(Boolean, default=True)
    reviewed_by = Column(String(100), nullable=True)
    review_date = Column(DateTime, nullable=True)

    legislation = relationship("Legislation", back_populates="impact_ratings")

    @validates('confidence_score')
    def validate_confidence_score(self, key, value):
        """
        Validate that confidence_score is a float between 0.0 and 1.0.

        Args:
            key: Attribute name
            value: Value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If value is not a float between 0.0 and 1.0
        """
        if value is None:
            return None

        if not isinstance(value, (int, float)) or value < 0 or value > 1:
            raise ValueError(
                "Confidence score must be a number between 0.0 and 1.0")
        return float(value)


class ImplementationRequirement(BaseModel):
    """
    Captures specific implementation requirements and timelines for legislation affecting public health
    and local government, detailing the type of requirement, estimated cost, and responsible entity.

    Attributes:
        id: Primary key
        legislation_id: Foreign key to Legislation
        requirement_type: Type of requirement
        description: Description of the requirement
        estimated_cost: Estimated cost of implementation
        funding_provided: Whether funding is provided
        implementation_deadline: Deadline for implementation
        entity_responsible: Entity responsible for implementation
        legislation: Relationship to Legislation
    """
    __tablename__ = 'implementation_requirements'

    id = Column(Integer, primary_key=True)
    legislation_id = Column(Integer,
                            ForeignKey('legislation.id'),
                            nullable=False)

    requirement_type = Column(
        String(50),
        nullable=False)  # e.g., "training", "staffing", "reporting"
    description = Column(Text, nullable=False)
    estimated_cost = Column(String(100), nullable=True)
    funding_provided = Column(Boolean, default=False)
    implementation_deadline = Column(DateTime, nullable=True)
    entity_responsible = Column(String(100), nullable=True)

    legislation = relationship("Legislation",
                               back_populates="implementation_requirements")

    @validates('requirement_type', 'description')
    def validate_required_fields(self, key, value):
        """
        Validate that required fields are not empty.

        Args:
            key: Attribute name
            value: Value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If required field is empty
        """
        if not value or not str(value).strip():
            raise ValueError(f"{key} cannot be empty")
        return value


# -----------------------------------------------------------------------------
# 5) Synchronization Metadata and Error Tracking Models
# -----------------------------------------------------------------------------
class SyncMetadata(BaseModel):
    __tablename__ = 'sync_metadata'

    id: Mapped[int] = mapped_column(primary_key=True)
    last_sync: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    last_successful_sync: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[SyncStatusEnum] = mapped_column(SQLEnum(SyncStatusEnum),
                                                       default=SyncStatusEnum.PENDING,
                                                       nullable=False)
    sync_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_bills: Mapped[int] = mapped_column(Integer, default=0)
    bills_updated: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    sync_errors: Mapped[List["SyncError"]] = relationship("SyncError", back_populates="sync_metadata")



class SyncError(BaseModel):
    """
    Logs errors encountered during synchronization operations.
    Associates each error with a specific sync operation.

    Attributes:
        id: Primary key
        sync_id: Foreign key to SyncMetadata
        error_type: Type of error
        error_message: Error message
        stack_trace: Stack trace of the error
        error_time: When the error occurred
        sync_metadata: Relationship to SyncMetadata
    """
    __tablename__ = 'sync_errors'

    id = Column(Integer, primary_key=True)
    sync_id = Column(Integer, ForeignKey('sync_metadata.id'), nullable=False)
    error_type = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    stack_trace = Column(Text, nullable=True)
    error_time = Column(DateTime, default=datetime.utcnow, nullable=False)

    sync_metadata = relationship("SyncMetadata", back_populates="sync_errors")


# -----------------------------------------------------------------------------
# 6) PostgreSQL-Specific Optimizations
# -----------------------------------------------------------------------------


# Configure PostgreSQL to use BYTEA for binary data and enable full-text search
def setup_postgres_extensions(dbapi_connection, connection_record):
    """Set up PostgreSQL extensions (pgcrypto, pg_trgm, unaccent) on the raw DBAPI connection."""
    try:
        with dbapi_connection.cursor() as cursor:
            cursor.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')
            cursor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
            cursor.execute('CREATE EXTENSION IF NOT EXISTS unaccent')
        dbapi_connection.commit()
    except Exception as e:
        logger.warning(f"Failed to create PostgreSQL extension: {e}")

# Register the event listener properly
event.listen(Engine, "connect", setup_postgres_extensions)


# -----------------------------------------------------------------------------
# 7) Database Initialization Logic
# -----------------------------------------------------------------------------
def init_db(db_url: Optional[str] = None,
            echo: bool = False,
            max_retries: int = 3) -> sessionmaker:
    """
    Initializes the database engine and returns a session factory.
    Includes robust error handling and connection retry logic.

    Args:
        db_url: The database connection URL. If not provided, defaults to the DATABASE_URL environment variable.
        echo: If True, SQLAlchemy will log all SQL statements.
        max_retries: Maximum number of attempts to establish a database connection.

    Returns:
        A SQLAlchemy sessionmaker bound to the engine.

    Raises:
        Exception: If database connection fails after maximum retries
    """
    db_url = db_url or os.environ.get(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/policypulse")
    engine = None
    attempt = 0

    while attempt < max_retries:
        try:
            # Create the engine with appropriate options
            engine = create_engine(
                db_url,
                echo=echo,
                pool_pre_ping=True,  # Test connections before using them
                pool_recycle=3600,  # Recycle connections after 1 hour
                pool_size=10,  # Connection pool size
                max_overflow=20  # Max additional connections
            )

            # Test connection with a simple query
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))

            logger.info("Database connection established successfully")
            break
        except Exception as e:
            attempt += 1
            logger.warning(
                f"Database connection attempt {attempt} failed: {e}")
            if attempt >= max_retries:
                logger.error(
                    f"Exceeded maximum retries ({max_retries}) for database connection."
                )
                raise

            # Exponential backoff
            wait_time = 2**attempt
            logger.info(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    # Create all tables if they don't exist
    try:
        Base.metadata.create_all(engine)
        logger.info("Database schema created or verified successfully")
    except Exception as e:
        logger.error(f"Failed to create database schema: {e}")
        raise

    # Return a sessionmaker bound to the engine
    return sessionmaker(bind=engine, expire_on_commit=False)