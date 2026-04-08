"""General-purpose helper utilities.

Contains small, stateless functions that are reused across multiple modules.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware).

    Returns:
        Current datetime with UTC timezone.
    """
    return datetime.now(tz=timezone.utc)


def slugify(text: str) -> str:
    """Convert a human-readable string into a URL/filename-safe slug.

    Args:
        text: The input string (e.g. a post title).

    Returns:
        Lowercase alphanumeric slug with hyphens replacing spaces/punctuation.

    Example:
        >>> slugify("Hello, World! 2024")
        'hello-world-2024'
    """
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def compute_content_hash(content: str) -> str:
    """Compute a short SHA-256 hex digest of the given content string.

    Used to detect duplicate or unchanged content without storing full text.

    Args:
        content: The string to hash.

    Returns:
        First 16 characters of the SHA-256 hex digest.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def safe_json_parse(text: str) -> dict[str, Any] | list[Any] | None:
    """Attempt to parse JSON from an LLM response string.

    Strips common markdown code fences before parsing.

    Args:
        text: Raw LLM output that may contain JSON.

    Returns:
        Parsed Python object, or None if parsing fails.
    """
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip().strip("`").strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None


def truncate_text(text: str, max_chars: int = 500) -> str:
    """Truncate a string to a maximum character length, appending ellipsis.

    Args:
        text: The input string.
        max_chars: Maximum allowed character count (default 500).

    Returns:
        Original string if shorter than limit, otherwise truncated with '…'.
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def format_engagement_stats(post: dict[str, Any]) -> str:
    """Format a post's engagement stats into a readable summary string.

    Args:
        post: A post dictionary containing optional 'likes', 'comments',
              'shares' keys.

    Returns:
        Human-readable engagement summary, e.g. '❤️ 312  💬 47  🔁 28'.
    """
    likes = post.get("likes", 0)
    comments = post.get("comments", 0)
    shares = post.get("shares", post.get("reposts", 0))
    return f"❤️ {likes}  💬 {comments}  🔁 {shares}"
