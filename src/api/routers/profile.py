"""Profile Intelligence API Router.

Exposes endpoints for triggering profile analysis and retrieving stored reports.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.agents.profile_intelligence_agent import ProfileIntelligenceAgent
from src.models.database import ProfileIntelligenceORM, get_db
from src.models.schemas import (
    Platform,
    ProfileAnalysisRequest,
    ProfileIntelligenceReport,
)
from src.utils.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/analyse",
    response_model=ProfileIntelligenceReport,
    status_code=status.HTTP_201_CREATED,
    summary="Analyse a social media profile",
    description="Triggers the Profile Intelligence Agent to analyse the given profile.",
)
async def analyse_profile(
    request: ProfileAnalysisRequest,
    db: Session = Depends(get_db),
) -> ProfileIntelligenceReport:
    """Analyse a social media profile and return the intelligence report.

    Args:
        request: Profile analysis request with platform and username.
        db: SQLAlchemy session dependency.

    Returns:
        Fully populated ProfileIntelligenceReport.

    Raises:
        HTTPException 422: If profile analysis fails.
    """
    logger.info(
        "api_profile_analyse", platform=request.platform, username=request.username
    )
    agent = ProfileIntelligenceAgent()
    try:
        report = agent.run(platform=request.platform, username=request.username)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Profile analysis failed: {exc}",
        ) from exc

    # Persist to DB
    record = ProfileIntelligenceORM(
        platform=report.platform,
        username=report.username,
        full_name=report.full_name,
        follower_count=report.follower_count,
        content_dna_summary=report.content_dna_summary,
        report_json=report.model_dump_json(),
    )
    db.add(record)
    db.commit()

    return report


@router.get(
    "/{username}",
    response_model=ProfileIntelligenceReport,
    summary="Retrieve the most recent profile report",
)
async def get_profile_report(
    username: str,
    db: Session = Depends(get_db),
) -> ProfileIntelligenceReport:
    """Retrieve the most recently stored profile intelligence report.

    Args:
        username: The profile username to look up.
        db: SQLAlchemy session dependency.

    Returns:
        The stored ProfileIntelligenceReport.

    Raises:
        HTTPException 404: If no report exists for the given username.
    """
    record = (
        db.query(ProfileIntelligenceORM)
        .filter(ProfileIntelligenceORM.username == username)
        .order_by(ProfileIntelligenceORM.created_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No profile report found for username '{username}'.",
        )
    return ProfileIntelligenceReport(**json.loads(record.report_json))
