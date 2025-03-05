
#!/usr/bin/env python
"""
fetch_initial_bills.py

Script to fetch initial bills from LegiScan API and analyze them.
This script:
1. Fetches a set of bills from LegiScan (US Congress and Texas)
2. Saves them to the database
3. Runs AI analysis on them
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from sqlalchemy.orm import Session

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import init_db, Legislation
from app.legiscan_api import LegiScanAPI
from app.ai_analysis import AIAnalysis

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_and_analyze_bills(limit=5, analyze=True):
    """
    Fetch and analyze bills.
    
    Args:
        limit: Maximum number of bills to fetch
        analyze: Whether to run AI analysis on the bills
    """
    # Initialize database session
    db_session_factory = init_db()
    db_session = db_session_factory()
    
    try:
        # Initialize LegiScan API client
        api = LegiScanAPI(db_session)
        
        # Get some recent US Congress bills
        logger.info("Fetching US Congress bills...")
        us_bills = fetch_bills_for_jurisdiction(api, "US", limit // 2)
        
        # Get some recent Texas bills
        logger.info("Fetching Texas bills...")
        tx_bills = fetch_bills_for_jurisdiction(api, "TX", limit // 2)
        
        # Combine results
        all_bills = us_bills + tx_bills
        logger.info(f"Fetched {len(all_bills)} bills in total.")
        
        # Run AI analysis if requested
        if analyze and all_bills:
            run_analysis(db_session, all_bills)
            
        return all_bills
        
    except Exception as e:
        logger.error(f"Error fetching and analyzing bills: {e}", exc_info=True)
        return []
    finally:
        db_session.close()

def fetch_bills_for_jurisdiction(api, state_code, limit):
    """
    Fetch bills for a specific jurisdiction.
    
    Args:
        api: LegiScanAPI instance
        state_code: Two-letter state code
        limit: Maximum number of bills to fetch
        
    Returns:
        List of fetched bills
    """
    fetched_bills = []
    
    try:
        # Get active sessions for this jurisdiction
        sessions = api.get_session_list(state_code)
        if not sessions:
            logger.warning(f"No sessions found for {state_code}")
            return []
        
        # Use the most recent session
        session = sessions[0]  # Assumes sessions are returned in chronological order
        session_id = session.get("session_id")
        
        if not session_id:
            logger.warning(f"No session ID found for {state_code}")
            return []
            
        # Get bill list for this session
        master_list = api.get_master_list(session_id)
        if not master_list:
            logger.warning(f"No bills found for session {session_id}")
            return []
            
        # Get most recent bills (skipping metadata at key "0")
        bill_ids = []
        items = [(k, v) for k, v in master_list.items() if k != "0"]
        
        # Sort by last action date (most recent first)
        sorted_items = sorted(
            items,
            key=lambda x: x[1].get("last_action_date", "1900-01-01"),
            reverse=True
        )
        
        # Take the top N bills
        for _, bill_info in sorted_items[:limit]:
            bill_id = bill_info.get("bill_id")
            if bill_id:
                bill_ids.append(bill_id)
                
        # Fetch full bill details and save to database
        for bill_id in bill_ids:
            bill_data = api.get_bill(bill_id)
            if bill_data:
                bill_obj = api.save_bill_to_db(bill_data, detect_relevance=True)
                if bill_obj:
                    fetched_bills.append(bill_obj)
                    logger.info(f"Saved bill {bill_obj.bill_number} to database.")
        
        return fetched_bills
        
    except Exception as e:
        logger.error(f"Error fetching bills for {state_code}: {e}", exc_info=True)
        return []

def run_analysis(db_session, bills):
    """
    Run AI analysis on a list of bills.
    
    Args:
        db_session: SQLAlchemy session
        bills: List of Legislation objects to analyze
    """
    logger.info(f"Running AI analysis on {len(bills)} bills...")
    
    try:
        # Initialize AI analysis
        analyzer = AIAnalysis(db_session)
        
        for bill in bills:
            try:
                logger.info(f"Analyzing bill: {bill.bill_number}")
                analysis = analyzer.analyze_legislation(bill.id)
                logger.info(f"Analysis complete for {bill.bill_number}, version: {analysis.analysis_version}")
            except Exception as e:
                logger.error(f"Error analyzing bill {bill.bill_number}: {e}")
    except Exception as e:
        logger.error(f"Error initializing AI analysis: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and analyze initial bills.")
    parser.add_argument('--limit', type=int, default=6, help='Number of bills to fetch')
    parser.add_argument('--no-analysis', action='store_true', help='Skip AI analysis')
    
    args = parser.parse_args()
    
    logger.info(f"Starting bill fetch with limit={args.limit}, analyze={not args.no_analysis}")
    fetch_and_analyze_bills(limit=args.limit, analyze=not args.no_analysis)
    logger.info("Complete!")
