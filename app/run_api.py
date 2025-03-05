"""
run_api.py

This module sets up and runs the FastAPI server for the PolicyPulse application.
It defines the API endpoints for legislation tracking and analysis.
"""

import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.models import init_db, Legislation, LegislationAnalysis
from app.legiscan_api import LegiScanAPI
from app.ai_analysis import AIAnalysis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PolicyPulse API",
    description=
    "API for tracking and analyzing legislation with focus on Texas public health and local government impacts",
    version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Initialize database session factory
db_session_factory = init_db()


# Define Pydantic models for API requests/responses
class BillSummary(BaseModel):
    id: int
    bill_number: str
    title: str
    status: str
    introduced_date: Optional[datetime] = None
    last_action_date: Optional[datetime] = None
    government_type: str
    government_source: str


class AnalysisSummary(BaseModel):
    id: int
    legislation_id: int
    version: int
    summary: str
    impact_category: Optional[str] = None
    impact_level: Optional[str] = None


class SearchParams(BaseModel):
    query: Optional[str] = None
    status: Optional[str] = None
    govt_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


# Dependency to get database session
def get_db():
    db = db_session_factory()
    try:
        yield db
    finally:
        db.close()


# API Routes
@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "name":
        "PolicyPulse API",
        "version":
        "1.0.0",
        "description":
        "Legislation tracking and analysis for public health and local government"
    }


@app.get("/api/bills", response_model=List[BillSummary])
async def get_bills(db: Session = Depends(get_db),
                    query: Optional[str] = None,
                    status: Optional[str] = None,
                    govt_type: Optional[str] = None,
                    limit: int = Query(20, le=100),
                    offset: int = 0):
    """
    Get a list of bills with optional filtering.
    """
    try:
        query_obj = db.query(Legislation)

        # Apply filters if provided
        if query:
            query_obj = query_obj.filter(Legislation.title.ilike(f"%{query}%"))
        if status:
            query_obj = query_obj.filter(Legislation.bill_status == status)
        if govt_type:
            query_obj = query_obj.filter(Legislation.govt_type == govt_type)

        # Order by most recent action
        query_obj = query_obj.order_by(
            Legislation.bill_last_action_date.desc())

        # Apply pagination
        results = query_obj.offset(offset).limit(limit).all()

        # Transform to response model
        bills = []
        for bill in results:
            bills.append({
                "id":
                bill.id,
                "bill_number":
                bill.bill_number,
                "title":
                bill.title,
                "status":
                bill.bill_status if bill.bill_status else "unknown",
                "introduced_date":
                bill.bill_introduced_date,
                "last_action_date":
                bill.bill_last_action_date,
                "government_type":
                bill.govt_type if bill.govt_type else "unknown",
                "government_source":
                bill.govt_source
            })

        return bills
    except Exception as e:
        logger.error(f"Error getting bills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bills/{bill_id}")
async def get_bill(bill_id: int, db: Session = Depends(get_db)):
    """
    Get detailed information about a specific bill.
    """
    try:
        bill = db.query(Legislation).filter(Legislation.id == bill_id).first()
        if not bill:
            raise HTTPException(status_code=404,
                                detail=f"Bill with ID {bill_id} not found")

        # Get the latest text if available
        latest_text = None
        if bill.texts and len(bill.texts) > 0:
            latest_text = bill.latest_text

        # Format response
        response = {
            "id": bill.id,
            "bill_number": bill.bill_number,
            "title": bill.title,
            "description": bill.description,
            "status": bill.bill_status if bill.bill_status else "unknown",
            "introduced_date": bill.bill_introduced_date,
            "last_action_date": bill.bill_last_action_date,
            "government_type": bill.govt_type if bill.govt_type else "unknown",
            "government_source": bill.govt_source,
            "url": bill.url,
            "state_link": bill.state_link,
            "has_text": latest_text is not None,
            "has_analysis": bill.analyses is not None
            and len(bill.analyses) > 0
        }

        # Add sponsor information if available
        if bill.sponsors and len(bill.sponsors) > 0:
            response["sponsors"] = [{
                "name": sponsor.sponsor_name,
                "title": sponsor.sponsor_title,
                "party": sponsor.sponsor_party,
                "state": sponsor.sponsor_state,
                "type": sponsor.sponsor_type
            } for sponsor in bill.sponsors]

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bill {bill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bills/{bill_id}/analysis")
async def get_bill_analysis(bill_id: int, db: Session = Depends(get_db)):
    """
    Get the analysis for a specific bill.
    """
    try:
        bill = db.query(Legislation).filter(Legislation.id == bill_id).first()
        if not bill:
            raise HTTPException(status_code=404,
                                detail=f"Bill with ID {bill_id} not found")

        # Get the latest analysis
        latest_analysis = bill.latest_analysis
        if not latest_analysis:
            # If no analysis exists, try to generate one
            analyzer = AIAnalysis(db_session=db)
            try:
                latest_analysis = analyzer.analyze_legislation(bill_id)
            except Exception as analysis_error:
                logger.error(
                    f"Error analyzing bill {bill_id}: {analysis_error}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error generating analysis: {str(analysis_error)}")

        # Format response with all analysis data
        response = {
            "id":
            latest_analysis.id,
            "legislation_id":
            latest_analysis.legislation_id,
            "version":
            latest_analysis.analysis_version,
            "date":
            latest_analysis.analysis_date,
            "summary":
            latest_analysis.summary,
            "impact_category":
            latest_analysis.impact_category
            if latest_analysis.impact_category else None,
            "impact_level":
            latest_analysis.impact if latest_analysis.impact else None,
            "key_points":
            latest_analysis.key_points,
            "public_health_impacts":
            latest_analysis.public_health_impacts,
            "local_gov_impacts":
            latest_analysis.local_gov_impacts,
            "economic_impacts":
            latest_analysis.economic_impacts,
            "environmental_impacts":
            latest_analysis.environmental_impacts,
            "education_impacts":
            latest_analysis.education_impacts,
            "infrastructure_impacts":
            latest_analysis.infrastructure_impacts,
            "recommended_actions":
            latest_analysis.recommended_actions,
            "immediate_actions":
            latest_analysis.immediate_actions,
            "resource_needs":
            latest_analysis.resource_needs,
            "model_version":
            latest_analysis.model_version
        }

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis for bill {bill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint to verify API and database are working.
    """
    try:
        # Check database connection by running a simple query
        bill_count = db.query(Legislation).count()
        analysis_count = db.query(LegislationAnalysis).count()

        return {
            "status": "healthy",
            "database": "connected",
            "bills_count": bill_count,
            "analyses_count": analysis_count,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }


def start_api_server(host="0.0.0.0", port=3000):
    """
    Start the FastAPI server.
    
    Args:
        host: Host to listen on
        port: Port to listen on
    """
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_api_server()
