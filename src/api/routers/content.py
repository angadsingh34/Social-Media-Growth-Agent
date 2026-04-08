"""Content Generation & Review API Router (FR-4, FR-5).

Triggers the multi-agent content pipeline and handles targeted
component-level regeneration without full pipeline re-runs.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.agents.copy_agent import CopyAgent
from src.agents.hashtag_agent import HashtagAgent
from src.agents.visual_concept_agent import VisualConceptAgent
from src.models.database import (
    CalendarEntryORM,
    ContentCalendarORM,
    GeneratedPostORM,
    get_db,
)
from src.models.schemas import (
    CalendarEntry,
    ContentCalendar,
    ContentRegenerationRequest,
    GeneratedPost,
    ReviewStatus,
)
from src.utils.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/generate/{calendar_id}",
    response_model=list[GeneratedPost],
    status_code=status.HTTP_201_CREATED,
    summary="Generate content for all calendar entries",
)
async def generate_content(
    calendar_id: str,
    db: Session = Depends(get_db),
) -> list[GeneratedPost]:
    """Run the multi-agent content generation pipeline for a finalised calendar.

    Args:
        calendar_id: UUID of the target content calendar.
        db: SQLAlchemy session dependency.

    Returns:
        List of GeneratedPost objects (one per calendar entry).

    Raises:
        HTTPException 404: Calendar not found.
        HTTPException 400: Calendar not yet finalised.
    """
    cal_orm = (
        db.query(ContentCalendarORM)
        .filter(ContentCalendarORM.calendar_id == calendar_id)
        .first()
    )
    if not cal_orm:
        raise HTTPException(status_code=404, detail="Calendar not found.")
    if not cal_orm.is_finalised:
        raise HTTPException(
            status_code=400,
            detail="Calendar must be finalised before content generation.",
        )

    calendar = ContentCalendar(**json.loads(cal_orm.calendar_json))

    copy_agent = CopyAgent()
    hashtag_agent = HashtagAgent()
    visual_agent = VisualConceptAgent()

    posts: list[GeneratedPost] = []
    for entry in calendar.entries:
        body = copy_agent.run(entry=entry, username=calendar.user_username)
        tags = hashtag_agent.run(entry=entry)
        visual = visual_agent.run(entry=entry)

        post = GeneratedPost(
            post_id=str(uuid.uuid4()),
            calendar_entry_id=entry.entry_id,
            platform=entry.platform,
            body_copy=body,
            hashtags=tags,
            visual_prompt=visual,
        )
        posts.append(post)

        orm = GeneratedPostORM(
            post_id=post.post_id,
            calendar_entry_id=post.calendar_entry_id,
            platform=post.platform,
            body_copy=post.body_copy,
            hashtags_json=json.dumps(post.hashtags),
            visual_prompt=post.visual_prompt,
        )
        db.add(orm)

    db.commit()
    logger.info(
        "content_generation_complete", calendar_id=calendar_id, count=len(posts)
    )
    return posts


@router.post(
    "/regenerate",
    response_model=GeneratedPost,
    summary="Regenerate a single content component",
)
async def regenerate_component(
    request: ContentRegenerationRequest,
    db: Session = Depends(get_db),
) -> GeneratedPost:
    """Regenerate a specific component (body, hashtags, or visual) of a post.

    Args:
        request: Specifies post_id, which component to regenerate, and instructions.
        db: SQLAlchemy session dependency.

    Returns:
        Updated GeneratedPost with the regenerated component.

    Raises:
        HTTPException 404: Post not found.
        HTTPException 400: Unknown component name.
    """
    post_orm = (
        db.query(GeneratedPostORM)
        .filter(GeneratedPostORM.post_id == request.post_id)
        .first()
    )
    if not post_orm:
        raise HTTPException(status_code=404, detail="Post not found.")

    # Reconstruct CalendarEntry for agent context
    entry = CalendarEntry(
        entry_id=post_orm.calendar_entry_id,
        day_number=1,
        platform=post_orm.platform,
        topic="(retrieved from calendar)",
        content_format="short_post",  # type: ignore
        scheduled_time="09:00 AM",
        rationale="",
    )

    if request.component == "body_copy":
        agent = CopyAgent()
        post_orm.body_copy = agent.run(
            entry=entry, username="user", instructions=request.instructions
        )

    elif request.component == "hashtags":
        agent = HashtagAgent()
        new_tags = agent.run(entry=entry, instructions=request.instructions)
        post_orm.hashtags_json = json.dumps(new_tags)

    elif request.component == "visual_prompt":
        agent = VisualConceptAgent()
        post_orm.visual_prompt = agent.run(
            entry=entry, instructions=request.instructions
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown component '{request.component}'. Use: body_copy, hashtags, visual_prompt.",
        )

    post_orm.review_status = ReviewStatus.REVISION_REQUESTED
    db.commit()

    return GeneratedPost(
        post_id=post_orm.post_id,
        calendar_entry_id=post_orm.calendar_entry_id,
        platform=post_orm.platform,
        body_copy=post_orm.body_copy,
        hashtags=json.loads(post_orm.hashtags_json or "[]"),
        visual_prompt=post_orm.visual_prompt or "",
        review_status=post_orm.review_status,
    )


@router.patch(
    "/{post_id}/approve",
    response_model=GeneratedPost,
    summary="Approve a generated post",
)
async def approve_post(
    post_id: str,
    db: Session = Depends(get_db),
) -> GeneratedPost:
    """Mark a generated post as approved for publishing.

    Args:
        post_id: UUID of the post to approve.
        db: SQLAlchemy session dependency.

    Returns:
        Updated GeneratedPost with APPROVED status.
    """
    post_orm = (
        db.query(GeneratedPostORM).filter(GeneratedPostORM.post_id == post_id).first()
    )
    if not post_orm:
        raise HTTPException(status_code=404, detail="Post not found.")

    post_orm.review_status = ReviewStatus.APPROVED
    post_orm.approved_at = datetime.utcnow()
    db.commit()

    return GeneratedPost(
        post_id=post_orm.post_id,
        calendar_entry_id=post_orm.calendar_entry_id,
        platform=post_orm.platform,
        body_copy=post_orm.body_copy or "",
        hashtags=json.loads(post_orm.hashtags_json or "[]"),
        visual_prompt=post_orm.visual_prompt or "",
        review_status=ReviewStatus.APPROVED,
        approved_at=post_orm.approved_at,
    )
