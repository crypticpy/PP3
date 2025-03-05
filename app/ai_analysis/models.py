"""
Pydantic models for structured validation of AI analysis results.
"""

from typing import Dict, List, Any, Literal
from pydantic import BaseModel, Field, model_validator


class KeyPoint(BaseModel):
    """Model representing a key point in the legislation analysis."""
    point: str = Field(..., description="The text of the bullet point")
    impact_type: Literal["positive", "negative", "neutral"] = Field(
        ..., description="The overall tone or impact of this point"
    )


class PublicHealthImpacts(BaseModel):
    """Model representing public health impacts of the legislation."""
    direct_effects: List[str] = Field(default_factory=list)
    indirect_effects: List[str] = Field(default_factory=list)
    funding_impact: List[str] = Field(default_factory=list)
    vulnerable_populations: List[str] = Field(default_factory=list)


class LocalGovernmentImpacts(BaseModel):
    """Model representing local government impacts of the legislation."""
    administrative: List[str] = Field(default_factory=list)
    fiscal: List[str] = Field(default_factory=list)
    implementation: List[str] = Field(default_factory=list)


class EconomicImpacts(BaseModel):
    """Model representing economic impacts of the legislation."""
    direct_costs: List[str] = Field(default_factory=list)
    economic_effects: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    long_term_impact: List[str] = Field(default_factory=list)


class ImpactSummary(BaseModel):
    """Model representing the overall impact summary."""
    primary_category: Literal["public_health", "local_gov", "economic", 
                             "environmental", "education", "infrastructure"]
    impact_level: Literal["low", "moderate", "high", "critical"]
    relevance_to_texas: Literal["low", "moderate", "high"]


class LegislationAnalysisResult(BaseModel):
    """Complete model for structured analysis results from the AI model."""
    summary: str
    key_points: List[KeyPoint]
    public_health_impacts: PublicHealthImpacts
    local_government_impacts: LocalGovernmentImpacts
    economic_impacts: EconomicImpacts
    environmental_impacts: List[str] = Field(default_factory=list)
    education_impacts: List[str] = Field(default_factory=list)
    infrastructure_impacts: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    immediate_actions: List[str] = Field(default_factory=list)
    resource_needs: List[str] = Field(default_factory=list)
    impact_summary: ImpactSummary

    model_config = {
        "extra": "forbid",  # Prevent extra fields
    }