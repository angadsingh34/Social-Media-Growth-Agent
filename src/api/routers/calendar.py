"""Content Calendar API Router.

Handles calendar generation, HITL review rounds, and finalisation.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.agents.competitive_landscape_agent import CompetitiveLandscapeAgent
from src.agents.profile_intelligence_agent import ProfileIntelligenceAgent
from src.models.database import ContentCalendarORM, ProfileIntelligenceORM, get_db
from src.models.schemas import (
    CalendarFeedbackRequest,
    CalendarGenerationRequest,
    CompetitiveAnalysisReport,
    ContentCalendar,
    Platform,
    ProfileIntelligenceReport,
)
from src.orchestrator.calendar_orchestrator import CalendarOrchestrator
from src.utils.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)
_orch = CalendarOrchestrator()


@router.post(
    "/generate",
    response_model=ContentCalendar,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a content calendar",
)
async def generate_calendar(
    request: CalendarGenerationRequest,
    db: Session = Depends(get_db),
) -> ContentCalendar:
    """Generate a new data-driven content calendar.

    Args:
        request: Calendar generation parameters.
        db: SQLAlchemy session dependency.

    Returns:
        Generated ContentCalendar (not yet finalised).

    Raises:
        HTTPException 404: If no profile report exists for the user.
    """
    # Load stored profile report
    profile_record = (
        db.query(ProfileIntelligenceORM)
        .filter(ProfileIntelligenceORM.username == request.user_username)
        .order_by(ProfileIntelligenceORM.created_at.desc())
        .first()
    )
    if not profile_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run /profile/analyse for '{request.user_username}' first.",
        )

    profile_report = ProfileIntelligenceReport(**json.loads(profile_record.report_json))

    # Generate competitive report on the fly
    comp_agent = CompetitiveLandscapeAgent()
    competitive_report = comp_agent.run(
        user_profile_report=profile_report, use_mock=True
    )

    calendar = _orch.generate(
        username=request.user_username,
        period_days=request.period_days,
        profile_report=profile_report,
        competitive_report=competitive_report,
    )

    # Persist calendar
    cal_orm = ContentCalendarORM(
        calendar_id=calendar.calendar_id,
        user_username=calendar.user_username,
        period_days=calendar.period_days,
        calendar_json=calendar.model_dump_json(),
        is_finalised=False,
    )
    db.add(cal_orm)
    db.commit()

    return calendar


@router.post(
    "/feedback",
    response_model=ContentCalendar,
    summary="Submit HITL feedback on a calendar",
)
async def submit_feedback(
    request: CalendarFeedbackRequest,
    db: Session = Depends(get_db),
) -> ContentCalendar:
    """Submit feedback for an HITL calendar review round.

    Args:
        request: Feedback request with calendar_id, feedback text, and approve flag.
        db: SQLAlchemy session dependency.

    Returns:
        Revised (or finalised) ContentCalendar.

    Raises:
        HTTPException 404: If the calendar is not found.
    """
    cal_orm = (
        db.query(ContentCalendarORM)
        .filter(ContentCalendarORM.calendar_id == request.calendar_id)
        .first()
    )
    if not cal_orm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calendar '{request.calendar_id}' not found.",
        )

    calendar = ContentCalendar(**json.loads(cal_orm.calendar_json))

    if request.approve:
        calendar = _orch.finalise(calendar)
    elif request.feedback:
        calendar = _orch.revise(calendar, request.feedback)

    cal_orm.calendar_json = calendar.model_dump_json()
    cal_orm.is_finalised = calendar.is_finalised
    db.commit()

    return calendar


@router.get(
    "/{calendar_id}",
    response_model=ContentCalendar,
    summary="Retrieve a calendar by ID",
)
async def get_calendar(
    calendar_id: str,
    db: Session = Depends(get_db),
) -> ContentCalendar:
    """Retrieve a stored content calendar.

    Args:
        calendar_id: The UUID of the calendar to retrieve.
        db: SQLAlchemy session dependency.

    Returns:
        The stored ContentCalendar.

    Raises:
        HTTPException 404: If not found.
    """
    cal_orm = (
        db.query(ContentCalendarORM)
        .filter(ContentCalendarORM.calendar_id == calendar_id)
        .first()
    )
    if not cal_orm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calendar '{calendar_id}' not found.",
        )
    return ContentCalendar(**json.loads(cal_orm.calendar_json))
