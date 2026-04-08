"""Publishing API Router (FR-6).

Handles publishing of approved posts to LinkedIn and/or Twitter/X,
with graceful fallback to clipboard / copy mode.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.database import GeneratedPostORM, PublishRecordORM, get_db
from src.models.schemas import (
    Platform,
    PublishRecord,
    PublishRequest,
    PublishStatus,
    ReviewStatus,
)
from src.services.linkedin_service import LinkedInService
from src.services.twitter_service import TwitterService
from src.utils.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/",
    response_model=list[PublishRecord],
    summary="Publish approved posts",
)
async def publish_posts(
    request: PublishRequest,
    db: Session = Depends(get_db),
) -> list[PublishRecord]:
    """Publish a batch of approved posts to specified platforms.

    Gracefully degrades to clipboard mode when APIs are unavailable.

    Args:
        request: Publish request specifying post IDs and target platforms.
        db: SQLAlchemy session dependency.

    Returns:
        List of PublishRecord objects with status for each post.
    """
    linkedin_svc = LinkedInService()
    twitter_svc = TwitterService()
    records: list[PublishRecord] = []

    for post_id in request.post_ids:
        post_orm = (
            db.query(GeneratedPostORM)
            .filter(GeneratedPostORM.post_id == post_id)
            .first()
        )
        if not post_orm:
            logger.warning("publish_post_not_found", post_id=post_id)
            continue

        if post_orm.review_status != ReviewStatus.APPROVED:
            logger.warning("publish_post_not_approved", post_id=post_id)
            continue

        hashtags = json.loads(post_orm.hashtags_json or "[]")
        full_text = post_orm.body_copy or ""
        if hashtags:
            full_text += "\n\n" + " ".join(hashtags)

        for platform in request.platforms:
            record_id = str(uuid.uuid4())

            if platform == Platform.LINKEDIN:
                result = linkedin_svc.publish_post(full_text)
                status = (
                    PublishStatus.POSTED
                    if result["success"]
                    else PublishStatus.CLIPBOARD
                )
                platform_post_id = result.get("post_id")
                error = result.get("error")

            elif platform == Platform.TWITTER:
                tweet_text = full_text[:280]  # enforce limit
                result = twitter_svc.publish_tweet(tweet_text)
                status = (
                    PublishStatus.POSTED
                    if result["success"]
                    else PublishStatus.CLIPBOARD
                )
                platform_post_id = result.get("tweet_id")
                error = result.get("error")

            else:
                continue

            record = PublishRecord(
                record_id=record_id,
                post_id=post_id,
                platform=platform,
                publish_status=status,
                platform_post_id=platform_post_id,
                error_message=error,
                published_at=datetime.utcnow()
                if status == PublishStatus.POSTED
                else None,
            )
            records.append(record)

            orm = PublishRecordORM(
                record_id=record_id,
                post_id=post_id,
                platform=platform,
                publish_status=status,
                platform_post_id=platform_post_id,
                error_message=error,
                published_at=record.published_at,
            )
            db.add(orm)

    db.commit()
    logger.info("publish_batch_complete", count=len(records))
    return records
