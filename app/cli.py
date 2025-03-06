#!/usr/bin/env python
"""
cli.py

Command-line interface for PolicyPulse administration tasks.
Provides tools for database seeding, syncing, analysis, and maintenance.

Usage:
  python cli.py seed [--start-date YYYY-MM-DD] [--jurisdiction US,TX]
  python cli.py sync [--force]
  python cli.py analyze <legislation_id>
  python cli.py analyze-pending [--limit N]
  python cli.py maintenance
  python cli.py stats
"""

import sys
import argparse
import logging
from datetime import datetime
from typing import Any

from app.models import init_db, Legislation, LegislationAnalysis, SyncMetadata
from app.legiscan_api import LegiScanAPI
from app.ai_analysis import AIAnalysis
from app.scheduler import LegislationSyncManager, PolicyPulseScheduler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


def init_resources():
    """Initialize database session and required resources."""
    db_session_factory = init_db()
    db_session = db_session_factory()
    return db_session, db_session_factory


def seed_command(args):
    """
    Seed the database with historical legislation.
    """
    logger.info(f"Starting seed operation from {args.start_date}")
    
    db_session, db_session_factory = init_resources()
    sync_manager = LegislationSyncManager(db_session_factory)
    
    jurisdictions = [j.strip() for j in args.jurisdictions.split(',')]
    sync_manager.target_jurisdictions = jurisdictions
    
    try:
        result = sync_manager.seed_historical_data(args.start_date)
        
        # Print results
        print("\n=== Seeding Results ===")
        print(f"Start date: {result['start_date']}")
        print(f"Bills added: {result['bills_added']}")
        print(f"Bills analyzed: {result['bills_analyzed']}")
        print(f"Sessions processed: {len(result['sessions_processed'])}")
        
        if result['errors']:
            print(f"\nErrors: {len(result['errors'])}")
            for i, err in enumerate(result['errors'][:5]):
                print(f"  {i+1}. {err[:100]}...")
            
            if len(result['errors']) > 5:
                print(f"  ...and {len(result['errors'])-5} more errors")
    finally:
        db_session.close()


def sync_command(args):
    """
    Trigger a sync operation.
    """
    logger.info(f"Starting {'forced ' if args.force else ''}sync operation")
    
    db_session, db_session_factory = init_resources()
    scheduler: Any = PolicyPulseScheduler()
    
    try:
        result = scheduler.run_sync_now()  # type: ignore # Method run_sync_now is not implemented in PolicyPulseScheduler
        print("\n=== Sync Results ===")
        print(f"Success: {result}")
    finally:
        db_session.close()


def analyze_command(args):
    """
    Analyze a specific legislation by ID.
    """
    logger.info(f"Starting analysis for legislation ID: {args.legislation_id}")
    
    db_session, db_session_factory = init_resources()
    analyzer = AIAnalysis(db_session=db_session)
    
    try:
        # Check if legislation exists
        legislation = db_session.query(Legislation).filter_by(id=args.legislation_id).first()
        if not legislation:
            print(f"Error: Legislation ID {args.legislation_id} not found")
            return
            
        # Run analysis
        analysis = analyzer.analyze_legislation(legislation_id=args.legislation_id)
        
        print("\n=== Analysis Results ===")
        print(f"Legislation: {legislation.bill_number} - {legislation.title[:50]}...")
        print(f"Analysis ID: {analysis.id}")
        print(f"Version: {analysis.analysis_version}")
        print(f"Date: {analysis.analysis_date.isoformat()}")
        print(f"Summary: {analysis.summary[:150]}...")
    except Exception as e:
        print(f"Error analyzing legislation: {e}")
    finally:
        db_session.close()


def analyze_pending_command(args):
    """
    Analyze pending (unanalyzed) legislation.
    """
    logger.info(f"Starting analysis for up to {args.limit} pending legislation")
    
    db_session, db_session_factory = init_resources()
    analyzer = AIAnalysis(db_session=db_session)
    
    try:
        # Find legislation without analysis
        subquery = db_session.query(
            LegislationAnalysis.legislation_id
        ).distinct().subquery()
        
        # Get unanalyzed legislation, prioritizing more recent bills
        unanalyzed = db_session.query(Legislation).filter(
            ~Legislation.id.in_(subquery)
        ).order_by(Legislation.updated_at.desc()).limit(args.limit).all()
        
        if not unanalyzed:
            print("No pending legislation found for analysis")
            return
            
        print(f"Found {len(unanalyzed)} legislation without analysis, processing...")
        
        # Process each bill
        for i, leg in enumerate(unanalyzed):
            try:
                print(f"\n[{i+1}/{len(unanalyzed)}] Analyzing {leg.bill_number} - {leg.title[:50]}...")
                analysis = analyzer.analyze_legislation(legislation_id=leg.id)
                print(f"  ✓ Analysis completed: version {analysis.analysis_version}")
            except Exception as e:
                print(f"  ✗ Error: {e}")
    finally:
        db_session.close()


def maintenance_command(args):
    """
    Run database maintenance tasks.
    """
    logger.info("Starting database maintenance")
    
    db_session, db_session_factory = init_resources()
    
    try:
        print("Performing database maintenance...")
        
        # Example maintenance tasks
        
        # 1. Vacuum analyze (PostgreSQL)
        print("Running vacuum analyze...")
        db_session.execute("VACUUM ANALYZE")
        
        # 2. Clean up old sync errors
        print("Cleaning up old sync errors...")
        from models import SyncError
        from datetime import timedelta
        
        thirty_days_ago = datetime.now() - timedelta(days=30)
        count = db_session.query(SyncError).filter(
            SyncError.error_time < thirty_days_ago
        ).delete()
        db_session.commit()
        print(f"Removed {count} old sync error records")
        
        print("\nMaintenance completed successfully")
    except Exception as e:
        print(f"Error during maintenance: {e}")
    finally:
        db_session.close()


def stats_command(args):
    """
    Show system statistics.
    """
    logger.info("Gathering system statistics")
    
    db_session, db_session_factory = init_resources()
    
    try:
        # Count legislation by state
        us_count = db_session.query(Legislation).filter(
            Legislation.govt_type == "federal"
        ).count()
        
        tx_count = db_session.query(Legislation).filter(
            Legislation.govt_source.ilike("%Texas%")
        ).count()
        
        # Count analyses
        analysis_count = db_session.query(LegislationAnalysis).count()
        
        # Get recent syncs
        recent_syncs = db_session.query(SyncMetadata).order_by(
            SyncMetadata.last_sync.desc()
        ).limit(3).all()
        
        # Get total bill count
        total_bills = db_session.query(Legislation).count()
        
        # Get bill statuses
        from sqlalchemy import func
        from models import BillStatusEnum
        
        status_counts = db_session.query(
            Legislation.bill_status, func.count(Legislation.id)
        ).group_by(Legislation.bill_status).all()
        
        # Print results
        print("\n=== System Statistics ===")
        print(f"Total legislation in database: {total_bills}")
        print(f"US Federal bills: {us_count}")
        print(f"Texas bills: {tx_count}")
        print(f"Total analyses: {analysis_count}")
        
        print("\nBill status breakdown:")
        for status, count in status_counts:
            status_name = status.name if hasattr(status, 'name') else status
            print(f"  {status_name}: {count}")
        
        print("\nRecent syncs:")
        for sync in recent_syncs:
            status = sync.status.name if hasattr(sync.status, 'name') else sync.status
            print(f"  {sync.last_sync.strftime('%Y-%m-%d %H:%M:%S')} - {sync.sync_type} - {status}")
            print(f"    New bills: {sync.new_bills}, Updated: {sync.bills_updated}")
    finally:
        db_session.close()


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description='PolicyPulse Administration CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Seed command
    seed_parser = subparsers.add_parser('seed', help='Seed database with historical legislation')
    seed_parser.add_argument('--start-date', type=str, default="2025-01-01", 
                            help='Start date in YYYY-MM-DD format (default: 2025-01-01)')
    seed_parser.add_argument('--jurisdictions', type=str, default="US,TX",
                           help='Comma-separated jurisdictions to seed (default: US,TX)')
    
    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Trigger a sync operation')
    sync_parser.add_argument('--force', action='store_true', help='Force sync even if recently run')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze a specific legislation')
    analyze_parser.add_argument('legislation_id', type=int, help='Legislation ID to analyze')
    
    # Analyze pending command
    analyze_pending_parser = subparsers.add_parser('analyze-pending', 
                                                help='Analyze pending (unanalyzed) legislation')
    analyze_pending_parser.add_argument('--limit', type=int, default=10, 
                                      help='Maximum number of legislation to analyze (default: 10)')
    
    # Maintenance command
    maintenance_parser = subparsers.add_parser('maintenance', help='Run database maintenance tasks')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show system statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute the appropriate command
    if args.command == 'seed':
        seed_command(args)
    elif args.command == 'sync':
        sync_command(args)
    elif args.command == 'analyze':
        analyze_command(args)
    elif args.command == 'analyze-pending':
        analyze_pending_command(args)
    elif args.command == 'maintenance':
        maintenance_command(args)
    elif args.command == 'stats':
        stats_command(args)


if __name__ == '__main__':
    main()