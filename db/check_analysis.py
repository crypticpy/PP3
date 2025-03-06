
#!/usr/bin/env python
"""
Script to query the database for AI analyses stored in the system.
"""
import os
import sys
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import database models and connection utilities
from app.models import init_db, LegislationAnalysis, Legislation
from sqlalchemy.orm import Session
from sqlalchemy import desc

def format_date(dt):
    """Format datetime for display"""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def print_analysis_detail(analysis):
    """Print detailed information about an analysis"""
    print(f"\n=== ANALYSIS ID: {analysis.id} (Version {analysis.analysis_version}) ===")
    print(f"Legislation ID: {analysis.legislation_id}")
    print(f"Analysis Date: {format_date(analysis.analysis_date)}")
    print(f"Model Version: {analysis.model_version}")
    
    # Print impact information if available
    if hasattr(analysis, 'impact_category') and analysis.impact_category:
        print(f"Impact Category: {analysis.impact_category.value}")
    if hasattr(analysis, 'impact') and analysis.impact:
        print(f"Impact Level: {analysis.impact.value}")
    
    # Print summary
    print("\nSUMMARY:")
    print(analysis.summary)
    
    # Print key points if available
    if analysis.key_points:
        print("\nKEY POINTS:")
        for point in analysis.key_points:
            impact_type = point.get('impact_type', 'neutral')
            print(f"- [{impact_type}] {point.get('point', 'No point text')}")
    
    # Print recommended actions if available
    if analysis.recommended_actions:
        print("\nRECOMMENDED ACTIONS:")
        for action in analysis.recommended_actions:
            print(f"- {action}")

def main():
    # Initialize database session
    db_session_factory = init_db()
    db_session = db_session_factory()
    
    try:
        # Get the total count of analyses
        analysis_count = db_session.query(LegislationAnalysis).count()
        print(f"Total AI analyses in database: {analysis_count}")
        
        if analysis_count == 0:
            print("No analyses found in the database.")
            return
            
        # Get recent analyses (limit to 5 for display)
        recent_analyses = db_session.query(LegislationAnalysis)\
            .order_by(desc(LegislationAnalysis.analysis_date))\
            .limit(5)\
            .all()
            
        print(f"\nMost recent {len(recent_analyses)} analyses:")
        for idx, analysis in enumerate(recent_analyses, 1):
            legislation = db_session.query(Legislation).filter_by(id=analysis.legislation_id).first()
            bill_number = legislation.bill_number if legislation else "Unknown"
            
            print(f"{idx}. ID: {analysis.id}, Bill: {bill_number}, Date: {format_date(analysis.analysis_date)}")
        
        # Ask if user wants to see details of a specific analysis
        if recent_analyses:
            try:
                choice = int(input("\nEnter the number of the analysis to view details (0 to skip): "))
                if 1 <= choice <= len(recent_analyses):
                    print_analysis_detail(recent_analyses[choice-1])
            except ValueError:
                print("Invalid input, skipping details.")
        
        # Display API endpoints for accessing analyses
        print("\n=== API ENDPOINTS FOR ACCESSING ANALYSES ===")
        print("1. Get analysis for a legislation: GET /api/legislation/{legislation_id}/analysis")
        print("2. Get analysis history: GET /api/legislation/{legislation_id}/analysis/history")
        print("3. Request a new analysis: POST /api/legislation/{legislation_id}/analysis")
        
    finally:
        db_session.close()

if __name__ == "__main__":
    main()
