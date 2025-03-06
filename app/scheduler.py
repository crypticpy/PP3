"""
scheduler.py

Runs the APScheduler for nightly syncs with LegiScan and immediate AI analysis 
of all new and changed bills. Also provides database seeding capabilities for
historical legislation.

Features:
- Daily LegiScan sync focused on US Congress and Texas
- Immediate AI analysis of all new/changed bills from each sync
- Historical bill seeding for data since January 1, 2025
- Amendment tracking to parent bills
- Automated notifications for high-priority legislation
"""

import sys
import signal
import logging
import time
import traceback
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Set, Any, Optional, Tuple, Union, cast

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import and_, or_, not_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models import init_db, SyncMetadata, SyncError as DBSyncError, SyncStatusEnum
from app.models import Legislation, LegislationText, LegislationAnalysis
from legiscan_api import LegiScanAPI
from ai_analysis import AIAnalysis

# Try to import optional models
try:
    from models import LegislationPriority
    HAS_PRIORITY_MODEL = True
except ImportError:
    HAS_PRIORITY_MODEL = False

# Try to import Amendment model if it exists
try:
    from models import Amendment, AmendmentStatusEnum
    HAS_AMENDMENT_MODEL = True
except ImportError:
    HAS_AMENDMENT_MODEL = False

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SyncError(Exception):
    """Base exception for sync-related errors."""
    pass


class DataSyncError(SyncError):
    """Exception raised when syncing data from external APIs."""
    pass


class AnalysisError(SyncError):
    """Exception raised when analyzing legislation."""
    pass


class LegislationSyncManager:
    """
    Orchestrates the actual data sync from LegiScan and manages
    AI analysis for all new and updated bills.
    """

    def __init__(self, db_session_factory: sessionmaker):
        """
        Initialize the sync manager with the provided database session factory.

        Args:
            db_session_factory: SQLAlchemy sessionmaker for creating database sessions
        """
        self.db_session_factory = db_session_factory

        # Keywords for determining relevance to Texas public health
        self.health_keywords = [
            "health", "healthcare", "public health", "medicaid", "medicare",
            "hospital", "physician", "vaccine", "immunization", "disease",
            "epidemic", "pandemic", "mental health", "substance abuse",
            "addiction", "opioid", "healthcare workforce"
        ]

        # Keywords for determining relevance to Texas local government
        self.local_govt_keywords = [
            "municipal", "county", "local government", "city council",
            "zoning", "property tax", "infrastructure", "public works",
            "community development", "ordinance", "school district",
            "special district", "county commissioner"
        ]

        self.target_jurisdictions = ["US", "TX"]

    def run_nightly_sync(self) -> Dict[str, Any]:
        """
            Performs nightly sync with LegiScan and triggers immediate AI analysis
            for all new and changed bills.

            Returns:
                Dictionary with summary of sync operations including:
                - new_bills: Number of new bills added
                - bills_updated: Number of existing bills updated
                - bills_analyzed: Number of bills successfully analyzed by AI
                - errors: List of error messages
                - amendments_tracked: Number of amendments processed
            """
        db_session = self.db_session_factory()
        summary = {
            "new_bills": 0,
            "bills_updated": 0,
            "bills_analyzed": 0,
            "errors": [],
            "amendments_tracked": 0,
            "start_time": datetime.now(timezone.utc),
            "end_time": None
        }

        # Initialize sync_meta outside try/except to ensure it's available in all blocks
        sync_meta = None

        try:
            # Create LegiScan API client
            api = LegiScanAPI(db_session)

            # 1. Create a sync metadata record to track this operation
            sync_meta = SyncMetadata(last_sync=datetime.now(timezone.utc),
                                     status=SyncStatusEnum.IN_PROGRESS,
                                     sync_type="nightly")
            db_session.add(sync_meta)
            db_session.commit()

            # List to track all changed/new bills for analysis
            bills_to_analyze = []

            # 2. Process each target jurisdiction (US Federal and Texas)
            for state in self.target_jurisdictions:
                try:
                    # Get active legislative sessions
                    sessions = self._get_active_sessions(api, state)

                    for session in sessions:
                        session_id = session.get("session_id")
                        if not session_id:
                            continue

                        # Get master list for change detection
                        master_list = api.get_master_list_raw(session_id)
                        if not master_list:
                            error_msg = f"Failed to retrieve master list for session {session_id} in {state}"
                            logger.warning(error_msg)
                            summary["errors"].append(error_msg)
                            continue

                        # Process changed or new bills
                        bill_ids = self._identify_changed_bills(
                            db_session, master_list)

                        # Process each bill
                        for bill_id in bill_ids:
                            try:
                                # Get full bill details
                                bill_data = api.get_bill(bill_id)
                                if not bill_data:
                                    continue

                                # Save bill to database
                                bill_obj = api.save_bill_to_db(
                                    bill_data, detect_relevance=True)

                                # Update summary counts
                                if bill_obj:
                                    # Track for analysis
                                    bills_to_analyze.append(bill_obj.id)

                                    if bill_obj.created_at == bill_obj.updated_at:
                                        summary["new_bills"] += 1
                                    else:
                                        summary["bills_updated"] += 1

                                    # Track amendments back to parent bills
                                    if "amendments" in bill_data and bill_data[
                                            "amendments"]:
                                        amendments_count = self._track_amendments(
                                            db_session, bill_obj,
                                            bill_data["amendments"])
                                        summary[
                                            "amendments_tracked"] += amendments_count

                            except Exception as e:
                                error_msg = f"Failed to save bill {bill_id}: {str(e)}"
                                logger.error(error_msg, exc_info=True)
                                summary["errors"].append(error_msg)

                                # Log error to database
                                sync_error = DBSyncError(
                                    sync_id=sync_meta.id,
                                    error_type="bill_processing",
                                    error_message=error_msg,
                                    stack_trace=traceback.format_exc())
                                db_session.add(sync_error)
                                db_session.commit()
                except Exception as e:
                    error_msg = f"Error processing jurisdiction {state}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    summary["errors"].append(error_msg)

                    # Record error but continue with other jurisdictions
                    sync_error = DBSyncError(
                        sync_id=sync_meta.id,
                        error_type="jurisdiction_processing",
                        error_message=error_msg,
                        stack_trace=traceback.format_exc())
                    db_session.add(sync_error)
                    db_session.commit()

            # 3. Immediately analyze all changed/new bills
            if bills_to_analyze:
                analyzer = AIAnalysis(db_session=db_session)

                for leg_id in bills_to_analyze:
                    try:
                        analyzer.analyze_legislation(legislation_id=leg_id)
                        summary["bills_analyzed"] += 1
                    except Exception as e:
                        error_msg = f"Error analyzing legislation {leg_id}: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        summary["errors"].append(error_msg)

                        # Log analysis error
                        sync_error = DBSyncError(
                            sync_id=sync_meta.id,
                            error_type="analysis_error",
                            error_message=error_msg,
                            stack_trace=traceback.format_exc())
                        db_session.add(sync_error)
                        db_session.commit()

            # 4. Update sync metadata record
            if sync_meta:  # Check if sync_meta exists (it might not if an exception occurred early)
                sync_meta.status = SyncStatusEnum.COMPLETED if not summary[
                    "errors"] else SyncStatusEnum.PARTIAL
                sync_meta.last_successful_sync = datetime.now(timezone.utc)
                sync_meta.bills_updated = summary["bills_updated"]
                sync_meta.new_bills = summary["new_bills"]

                if summary["errors"]:
                    sync_meta.errors = json.dumps({  # type: ignore
                        "count":
                        len(summary["errors"]),
                        "samples":
                        summary["errors"][:5]
                    })

                db_session.commit()

            logger.info(
                f"Nightly sync completed. New bills: {summary['new_bills']}, "
                f"Updated: {summary['bills_updated']}, "
                f"Analyzed: {summary['bills_analyzed']}, "
                f"Amendments: {summary['amendments_tracked']}, "
                f"Errors: {len(summary['errors'])}")

        except DataSyncError as e:
            logger.error(f"Data sync error in nightly sync: {e}",
                         exc_info=True)
            summary["errors"].append(f"Data sync error: {str(e)}")
            if sync_meta:
                self._record_critical_error(db_session, sync_meta, e,
                                            "data_sync_error")
        except AnalysisError as e:
            logger.error(f"Analysis error in nightly sync: {e}", exc_info=True)
            summary["errors"].append(f"Analysis error: {str(e)}")
            if sync_meta:
                self._record_critical_error(db_session, sync_meta, e,
                                            "analysis_error")
        except SQLAlchemyError as e:
            logger.error(f"Database error in nightly sync: {e}", exc_info=True)
            summary["errors"].append(f"Database error: {str(e)}")
            if sync_meta:
                self._record_critical_error(db_session, sync_meta, e,
                                            "database_error")
        except Exception as e:
            logger.error(f"Fatal error in nightly sync: {e}", exc_info=True)
            summary["errors"].append(f"Fatal error: {str(e)}")
            if sync_meta:
                self._record_critical_error(db_session, sync_meta, e,
                                            "fatal_error")
        finally:
            summary["end_time"] = datetime.now(timezone.utc)
            try:
                db_session.close()
            except Exception:
                # Ignore errors on close
                pass

        return summary

    def _record_critical_error(self, db_session: Session,
                               sync_meta: SyncMetadata, exception: Exception,
                               error_type: str) -> None:
        """
        Record a critical error in the sync metadata and error log.

        Args:
            db_session: Database session
            sync_meta: SyncMetadata record
            exception: The exception that occurred
            error_type: Type of error
        """
        try:
            sync_meta.status = SyncStatusEnum.FAILED
            sync_meta.errors = {"critical_error": str(exception)}

            sync_error = DBSyncError(sync_id=sync_meta.id,
                                     error_type=error_type,
                                     error_message=str(exception),
                                     stack_trace=traceback.format_exc())
            db_session.add(sync_error)
            db_session.commit()
        except Exception as e:
            logger.error(f"Failed to record critical error: {e}")
            try:
                db_session.rollback()
            except Exception:
                pass

    def _get_active_sessions(self, api: LegiScanAPI,
                             state: str) -> List[Dict[str, Any]]:
        """
        Gets active legislative sessions for a state.

        Args:
            api: LegiScanAPI instance
            state: Two-letter state code

        Returns:
            List of active session dictionaries

        Raises:
            DataSyncError: If unable to retrieve sessions
        """
        try:
            sessions = api.get_session_list(state)
            if not sessions:
                logger.warning(f"No sessions found for state {state}")
                return []

            active_sessions = []
            current_year = datetime.now().year

            for session in sessions:
                # Consider active if year_end is current year or later,
                # or if sine_die is 0 (session not adjourned)
                if (session.get("year_end", 0) >= current_year
                        or session.get("sine_die", 1) == 0):
                    active_sessions.append(session)

            return active_sessions
        except Exception as e:
            error_msg = f"Error retrieving active sessions for {state}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise DataSyncError(error_msg) from e

    def _identify_changed_bills(self, db_session: Session,
                                master_list: Dict[str, Any]) -> List[int]:
        """
        Identifies bills that have been added or changed since last sync.

        Args:
            db_session: SQLAlchemy database session
            master_list: Master bill list from LegiScan API

        Returns:
            List of bill IDs that need updating

        Raises:
            DataSyncError: If unable to process the master list
        """
        if not master_list:
            return []

        try:
            changed_bill_ids = []

            for key, bill_info in master_list.items():
                if key == "0":  # Skip metadata
                    continue

                bill_id = bill_info.get("bill_id")
                change_hash = bill_info.get("change_hash")

                if not bill_id or not change_hash:
                    continue

                # Check if we have this bill and if the change_hash is different
                existing = db_session.query(Legislation).filter(
                    Legislation.external_id == str(bill_id),
                    Legislation.data_source ==
                    "legiscan"  # Using string instead of enum for simplicity
                ).first()

                if not existing or existing.change_hash != change_hash:
                    changed_bill_ids.append(bill_id)

            return changed_bill_ids
        except SQLAlchemyError as e:
            error_msg = f"Database error while identifying changed bills: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise DataSyncError(error_msg) from e
        except Exception as e:
            error_msg = f"Error identifying changed bills: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise DataSyncError(error_msg) from e

    def _track_amendments(self, db_session: Session, bill: Legislation,
                          amendments: List[Dict[str, Any]]) -> int:
        """
        Track amendments back to their parent bills. This helps maintain relationships
        between bills and their amendments.

        Args:
            db_session: Database session
            bill: Parent legislation object
            amendments: List of amendment data from LegiScan

        Returns:
            Number of amendments processed

        Raises:
            DataSyncError: If unable to process amendments
        """
        try:
            processed_count = 0

            # Process each amendment
            for amend_data in amendments:
                amendment_id = amend_data.get("amendment_id")
                if not amendment_id:
                    continue

                # If we have a dedicated Amendment model, use it
                if HAS_AMENDMENT_MODEL:
                    # Import needed only within this scope if model exists
                    from models import Amendment, AmendmentStatusEnum

                    existing = db_session.query(Amendment).filter_by(
                        amendment_id=str(amendment_id),
                        legislation_id=bill.id).first()

                    # Parse amendment date
                    amend_date = None
                    date_str = amend_data.get("date")
                    if date_str and isinstance(date_str, str):
                        try:
                            amend_date = datetime.strptime(
                                date_str, "%Y-%m-%d")
                        except ValueError:
                            logger.warning(
                                f"Invalid amendment date format: {date_str}")

                    # Convert adopted flag to boolean
                    is_adopted = bool(amend_data.get("adopted", 0))

                    # Determine status enum value
                    status_value = AmendmentStatusEnum.ADOPTED if is_adopted else AmendmentStatusEnum.PROPOSED

                    if existing:
                        # Update existing record using dict update approach
                        # This avoids the SQLAlchemy Column assignment type issues
                        update_data = {
                            "adopted": is_adopted,
                            "status": status_value,
                            "amendment_date": amend_date,
                            "title": amend_data.get("title", ""),
                            "description": amend_data.get("description", ""),
                            "amendment_hash":
                            amend_data.get("amendment_hash", "")
                        }

                        # Use orm.attributes to update the object
                        for key, value in update_data.items():
                            setattr(existing, key, value)
                    else:
                        # Create new record
                        # For the constructor, we don't have the same type checking issues
                        new_amendment = Amendment(
                            amendment_id=str(amendment_id),
                            legislation_id=bill.id,
                            adopted=is_adopted,
                            status=status_value,
                            amendment_date=amend_date,
                            title=amend_data.get("title", ""),
                            description=amend_data.get("description", ""),
                            amendment_hash=amend_data.get(
                                "amendment_hash", ""),
                            amendment_url=amend_data.get("state_link", ""))
                        db_session.add(new_amendment)
                else:
                    # Store amendments in raw_api_response if Amendment model doesn't exist
                    raw_data = bill.raw_api_response or {}

                    # Make sure raw_data is a dictionary
                    if not isinstance(raw_data, dict):
                        raw_data = {}

                    # Initialize amendments list if it doesn't exist
                    if "amendments" not in raw_data:
                        raw_data["amendments"] = []

                    # Check if this amendment is already tracked
                    existing_ids = [
                        a.get("amendment_id") for a in raw_data["amendments"]
                    ]
                    if amendment_id not in existing_ids:
                        raw_data["amendments"].append(amend_data)

                        # Use setattr to avoid type checking issues with Column assignment
                        setattr(bill, "raw_api_response", raw_data)

                processed_count += 1

            # Commit changes
            db_session.commit()
            return processed_count

        except SQLAlchemyError as e:
            db_session.rollback()
            error_msg = f"Database error while tracking amendments: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise DataSyncError(error_msg) from e
        except Exception as e:
            db_session.rollback()
            error_msg = f"Error tracking amendments: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise DataSyncError(error_msg) from e

    def seed_historical_data(self,
                             start_date: str = "2025-01-01") -> Dict[str, Any]:
        """
        Seed the database with historical legislation since the specified start date.
        Default is January 1, 2025.

        Args:
            start_date: ISO format date string (YYYY-MM-DD)

        Returns:
            Dictionary with seeding statistics including:
            - start_date: The starting date used
            - bills_added: Number of new bills added
            - bills_analyzed: Number of bills analyzed with AI
            - errors: List of error messages
            - sessions_processed: Information about legislative sessions processed
        """
        db_session = self.db_session_factory()
        api = LegiScanAPI(db_session)

        try:
            # Parse start date
            start_datetime = datetime.fromisoformat(start_date)
        except ValueError:
            logger.error(
                f"Invalid start date format: {start_date}. Using 2025-01-01.")
            start_datetime = datetime.fromisoformat("2025-01-01")

        summary = {
            "start_date": start_date,
            "bills_added": 0,
            "bills_analyzed": 0,
            "errors": [],
            "sessions_processed": [],
            "start_time": datetime.now(timezone.utc),
            "end_time": None
        }

        try:
            # Process each target jurisdiction
            for state in self.target_jurisdictions:
                try:
                    # Get all sessions for the state
                    all_sessions = api.get_session_list(state)
                    if not all_sessions:
                        warning_msg = f"No sessions found for state {state}"
                        logger.warning(warning_msg)
                        summary["errors"].append(warning_msg)
                        continue

                    # Filter sessions that overlap with our target date range
                    relevant_sessions = []
                    for session in all_sessions:
                        # If session covers our start date or later
                        if session.get(
                                "year_start",
                                0) >= start_datetime.year or session.get(
                                    "year_end", 0) >= start_datetime.year:
                            relevant_sessions.append(session)

                    # Process each relevant session
                    for session in relevant_sessions:
                        session_id = session.get("session_id")
                        if not session_id:
                            continue

                        logger.info(
                            f"Seeding historical data from {state} session: {session.get('session_name')}"
                        )

                        # Keep track of session bills for the summary
                        session_summary = {
                            "state": state,
                            "session_id": session_id,
                            "session_name": session.get("session_name"),
                            "bills_found": 0,
                            "bills_added": 0,
                            "bills_analyzed": 0,
                            "errors": []
                        }

                        try:
                            # Get master list for this session
                            master_list = api.get_master_list(
                                session_id)  # Use full master list
                            if not master_list:
                                error_msg = f"Failed to retrieve master list for session {session_id}"
                                logger.error(error_msg)
                                session_summary["errors"].append(error_msg)
                                summary["sessions_processed"].append(
                                    session_summary)
                                continue

                            # Process each bill
                            for key, bill_info in master_list.items():
                                if key == "0":  # Skip metadata
                                    continue

                                bill_id = bill_info.get("bill_id")
                                if not bill_id:
                                    continue

                                # Check if bill already exists in our database
                                existing = db_session.query(
                                    Legislation).filter(
                                        Legislation.external_id == str(
                                            bill_id), Legislation.data_source
                                        == "legiscan").first()

                                session_summary["bills_found"] += 1

                                if not existing:
                                    try:
                                        # Get full bill data
                                        bill_data = api.get_bill(bill_id)
                                        if not bill_data:
                                            continue

                                        # Check if bill matches our date criteria
                                        bill_date_str = bill_data.get(
                                            "status_date", "")
                                        if bill_date_str:
                                            try:
                                                bill_date = datetime.strptime(
                                                    bill_date_str, "%Y-%m-%d")
                                                if bill_date < start_datetime:
                                                    # Skip bills before our start date
                                                    continue
                                            except ValueError:
                                                # If date parsing fails, include the bill
                                                pass

                                        # Save the bill
                                        bill_obj = api.save_bill_to_db(
                                            bill_data, detect_relevance=True)
                                        if bill_obj:
                                            summary["bills_added"] += 1
                                            session_summary["bills_added"] += 1

                                            # Process amendments if any
                                            if "amendments" in bill_data and bill_data[
                                                    "amendments"]:
                                                self._track_amendments(
                                                    db_session, bill_obj,
                                                    bill_data["amendments"])
                                    except Exception as e:
                                        error_msg = f"Error processing bill {bill_id}: {str(e)}"
                                        logger.error(error_msg, exc_info=True)
                                        session_summary["errors"].append(
                                            error_msg)
                                        summary["errors"].append(error_msg)

                            # Add session to processed list
                            summary["sessions_processed"].append(
                                session_summary)

                        except Exception as e:
                            error_msg = f"Error processing session {session_id}: {str(e)}"
                            logger.error(error_msg, exc_info=True)
                            session_summary["errors"].append(error_msg)
                            summary["errors"].append(error_msg)
                            summary["sessions_processed"].append(
                                session_summary)

                except Exception as e:
                    error_msg = f"Error processing state {state}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    summary["errors"].append(error_msg)

            # Analyze all newly added bills
            if summary["bills_added"] > 0:
                # Get list of bills that need analysis (added in this seeding)
                analyzer = AIAnalysis(db_session=db_session)

                # Find bills without analysis
                no_analysis = db_session.query(Legislation.id).outerjoin(
                    LegislationAnalysis, Legislation.id ==
                    LegislationAnalysis.legislation_id).filter(
                    LegislationAnalysis.id.is_(None)).all()

                bills_to_analyze = [bill.id for bill in no_analysis]

                # Process each bill (could be batched or prioritized)
                for leg_id in bills_to_analyze:
                    try:
                        analyzer.analyze_legislation(legislation_id=leg_id)
                        summary["bills_analyzed"] += 1

                        # Update session summary if we can match it
                        for session_summary in summary["sessions_processed"]:
                            # This isn't efficient but it's a one-time operation
                            bill = db_session.query(Legislation).filter(
                                Legislation.id == leg_id).first()
                            if bill:
                                bill_data = bill.raw_api_response
                                if bill_data and bill_data.get(
                                        "state") == session_summary["state"]:
                                    session_id = bill_data.get(
                                        "session", {}).get("session_id")
                                    if session_id == session_summary[
                                            "session_id"]:
                                        session_summary["bills_analyzed"] += 1
                    except Exception as e:
                        error_msg = f"Error analyzing legislation {leg_id}: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        summary["errors"].append(error_msg)

            logger.info(
                f"Seeding completed. Added {summary['bills_added']} bills, "
                f"analyzed {summary['bills_analyzed']} bills, "
                f"processed {len(summary['sessions_processed'])} sessions")

        except DataSyncError as e:
            logger.error(f"Data sync error in seeding: {e}", exc_info=True)
            summary["errors"].append(f"Data sync error: {str(e)}")
        except AnalysisError as e:
            logger.error(f"Analysis error in seeding: {e}", exc_info=True)
            summary["errors"].append(f"Analysis error: {str(e)}")
        except SQLAlchemyError as e:
            logger.error(f"Database error in seeding: {e}", exc_info=True)
            summary["errors"].append(f"Database error: {str(e)}")
        except Exception as e:
            logger.error(f"Fatal error in historical seeding: {e}",
                         exc_info=True)
            summary["errors"].append(f"Fatal error: {str(e)}")
        finally:
            summary["end_time"] = datetime.now(timezone.utc)
            try:
                db_session.close()
            except Exception:
                # Ignore errors on close
                pass

        return summary


class PolicyPulseScheduler:
    """
    Manages scheduled jobs for PolicyPulse, including:
    - Nightly LegiScan sync at 10 PM, followed by immediate AI analysis
    - Historical data seeding (manual trigger)
    - Daily database maintenance
    """

    def __init__(self):
        """Initialize the scheduler with APScheduler."""
        self.scheduler = BackgroundScheduler(timezone=timezone.utc)
        # Initialize DB once for entire process
        self.db_session_factory = init_db()
        self.is_running = False
        # Create sync manager
        self.sync_manager = LegislationSyncManager(self.db_session_factory)

    def _nightly_sync_job(self):
        """
        Run the nightly sync job with immediate AI analysis of all new/changed bills.
        """
        logger.info(
            "Starting nightly LegiScan sync job with immediate analysis...")
        try:
            summary = self.sync_manager.run_nightly_sync()
            logger.info(
                f"Nightly sync completed. New bills: {summary['new_bills']}, "
                f"Updated: {summary['bills_updated']}, "
                f"Analyzed: {summary['bills_analyzed']}, "
                f"Errors: {len(summary['errors'])}")

            # Optional: Alert on high error count
            if len(summary['errors']) > 10:
                logger.warning(
                    f"High error count in nightly sync: {len(summary['errors'])} errors"
                )

        except Exception as e:
            logger.error(f"Nightly sync job failed: {e}", exc_info=True)

    def _daily_maintenance_job(self):
        """Perform daily database maintenance tasks."""
        logger.info("Starting daily database maintenance job...")

        db_session = self.db_session_factory()
        try:
            # Clean up old sync error records (older than 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            deleted_count = db_session.query(DBSyncError).filter(
                DBSyncError.error_time < thirty_days_ago).delete()

            # Vacuum analyze if using PostgreSQL
            try:
                db_session.execute("VACUUM ANALYZE")
                vacuum_success = True
            except Exception as e:
                vacuum_success = False
                logger.warning(f"VACUUM ANALYZE failed: {e}")

            logger.info(
                f"Daily maintenance completed. Removed {deleted_count} old error records. VACUUM success: {vacuum_success}"
            )
            db_session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Database error in maintenance job: {e}",
                         exc_info=True)
            db_session.rollback()
        except Exception as e:
            logger.error(f"Daily maintenance job failed: {e}", exc_info=True)
            db_session.rollback()
        finally:
            db_session.close()

    def _job_listener(self, event):
        """Event listener for scheduled jobs."""
        if event.exception:
            logger.error(f"Job {event.job_id} failed: {event.exception}")
        else:
            logger.info(f"Job {event.job_id} completed successfully")

    def start(self):
        """Start the scheduler with configured jobs."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return False

        try:
            # Register event listener for job execution events
            self.scheduler.add_listener(self._job_listener,
                                        EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

            # Add the nightly sync job (runs at 10 PM UTC)
            self.scheduler.add_job(self._nightly_sync_job,
                                   CronTrigger(hour=22, minute=0),
                                   id='nightly_sync',
                                   name='LegiScan Nightly Sync',
                                   replace_existing=True)

            # Add daily maintenance job (runs at 4 AM UTC)
            self.scheduler.add_job(self._daily_maintenance_job,
                                   CronTrigger(hour=4, minute=0),
                                   id='daily_maintenance',
                                   name='Daily Database Maintenance',
                                   replace_existing=True)

            # Start the scheduler
            self.scheduler.start()
            self.is_running = True
            logger.info(
                "Scheduler started. Nightly sync scheduled for 10 PM UTC, maintenance for 4 AM UTC."
            )
            return True
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}", exc_info=True)
            return False

    def stop(self):
        """Stop the scheduler."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        try:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}", exc_info=True)

    def run_manual_sync(self):
        """
        Manually trigger a sync job.

        Returns:
            Dictionary with sync operation summary
        """
        logger.info("Starting manual sync job...")
        return self.sync_manager.run_nightly_sync()

    def run_historical_seeding(self, start_date="2025-01-01"):
        """
        Manually trigger historical data seeding.

        Args:
            start_date: ISO format date string (YYYY-MM-DD)

        Returns:
            Dictionary with seeding operation summary
        """
        logger.info(f"Starting historical data seeding from {start_date}...")
        return self.sync_manager.seed_historical_data(start_date)

    def run_on_demand_analysis(self, legislation_id):
        """
        Run AI analysis for a specific piece of legislation.

        Args:
            legislation_id: Database ID of legislation to analyze

        Returns:
            Boolean indicating success or failure
        """
        logger.info(
            f"Running on-demand analysis for legislation ID {legislation_id}")
        db_session = self.db_session_factory()
        try:
            analyzer = AIAnalysis(db_session=db_session)
            analyzer.analyze_legislation(legislation_id=legislation_id)
            logger.info(
                f"On-demand analysis completed for legislation ID {legislation_id}"
            )
            return True
        except Exception as e:
            logger.error(
                f"On-demand analysis failed for legislation ID {legislation_id}: {e}",
                exc_info=True)
            return False
        finally:
            db_session.close()


def handle_signal(sig, frame):
    """Signal handler for graceful shutdown."""
    logger.info(f"Received signal {sig}. Shutting down...")
    if 'scheduler' in globals() and scheduler.is_running:
        scheduler.stop()
    sys.exit(0)


if __name__ == "__main__":
    # Set up logging to console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info("Starting PolicyPulse scheduler...")

    # Create and start scheduler
    scheduler = PolicyPulseScheduler()
    scheduler.start()

    # Run seeding if requested via command line argument
    if len(sys.argv) > 1 and sys.argv[1] == '--seed':
        start_date = "2025-01-01"  # Default
        if len(sys.argv) > 2:
            start_date = sys.argv[2]
        logger.info(f"Running historical data seeding from {start_date}...")
        scheduler.run_historical_seeding(start_date)

    # Keep main thread alive
    try:
        while scheduler.is_running:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        if scheduler.is_running:
            scheduler.stop()
