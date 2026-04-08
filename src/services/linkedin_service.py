"""LinkedIn data ingestion and publishing service.

Supports two modes:
- Live mode: Uses Proxycurl for profile data, LinkedIn Share API for publishing.
- Mock mode: Returns fixtures from ``utils/mock_data.py``.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from src.config import get_settings
from src.utils.logging_config import get_logger
from src.utils.mock_data import MOCK_COMPETITOR_PROFILES, MOCK_USER_PROFILE

logger = get_logger(__name__)
settings = get_settings()

_PROXYCURL_BASE = "https://nubela.co/proxycurl/api/v2"
_LINKEDIN_API_BASE = "https://api.linkedin.com/v2"


class LinkedInService:
    """Client for LinkedIn profile data fetching and content publishing.

    Attributes:
        use_mock: Whether to bypass live API calls with mock data.
    """

    def __init__(self, use_mock: Optional[bool] = None) -> None:
        """Initialise the service.

        Args:
            use_mock: Override the global ``USE_MOCK_DATA`` setting.
        """
        self.use_mock: bool = (
            use_mock if use_mock is not None else settings.use_mock_data
        )

    # ------------------------------------------------------------------
    # Profile Data Fetching
    # ------------------------------------------------------------------

    def fetch_profile(self, username: str) -> dict[str, Any]:
        """Fetch a LinkedIn profile by username/slug.

        Falls back to mock data if ``use_mock`` is True or the API call fails.

        Args:
            username: LinkedIn profile URL slug (e.g. 'jane-doe').

        Returns:
            A normalised profile dict consumed by the Profile Intelligence Agent.
        """
        if self.use_mock:
            logger.info("linkedin_fetch_profile_mock", username=username)
            profile = dict(MOCK_USER_PROFILE)
            profile["username"] = username
            return profile

        return self._fetch_profile_live(username)

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(2), reraise=False)
    def _fetch_profile_live(self, username: str) -> dict[str, Any]:
        """Call Proxycurl API to retrieve a LinkedIn profile.

        Args:
            username: LinkedIn slug.

        Returns:
            Normalised profile dict, or mock data on failure.
        """
        if not settings.proxycurl_api_key:
            logger.warning("proxycurl_key_missing_falling_back_to_mock")
            return dict(MOCK_USER_PROFILE)

        url = f"{_PROXYCURL_BASE}/linkedin"
        params = {
            "linkedin_profile_url": f"https://www.linkedin.com/in/{username}/",
            "extra": "include",
            "skills": "include",
            "personal_contact_number": "exclude",
        }
        headers = {"Authorization": f"Bearer {settings.proxycurl_api_key}"}

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                raw = resp.json()
                return self._normalise_proxycurl(raw, username)
        except httpx.HTTPError as exc:
            logger.error("proxycurl_fetch_failed", error=str(exc), username=username)
            return dict(MOCK_USER_PROFILE)

    def _normalise_proxycurl(
        self, raw: dict[str, Any], username: str
    ) -> dict[str, Any]:
        """Map a Proxycurl API response to our internal profile shape.

        Args:
            raw: Raw Proxycurl JSON response.
            username: The queried LinkedIn slug.

        Returns:
            Normalised profile dict.
        """
        return {
            "platform": "linkedin",
            "username": username,
            "full_name": f"{raw.get('first_name', '')} {raw.get('last_name', '')}".strip(),
            "headline": raw.get("headline", ""),
            "bio": raw.get("summary", ""),
            "follower_count": raw.get("follower_count", 0),
            "connection_count": raw.get("connections", 0),
            "recent_posts": [],  # Proxycurl free tier does not include posts
            "posting_frequency_per_week": 0.0,
            "primary_topics": [],
            "content_formats": [],
        }

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish_post(
        self, body: str, access_token: Optional[str] = None
    ) -> dict[str, Any]:
        """Publish a post to LinkedIn via the Share API.

        Args:
            body: The post text to publish.
            access_token: OAuth2 access token. Falls back to settings value.

        Returns:
            Dict with keys: success (bool), post_id (str|None), error (str|None).
        """
        if not settings.enable_publishing:
            logger.info("linkedin_publish_disabled_clipboard_mode")
            return {
                "success": False,
                "post_id": None,
                "error": "Publishing disabled; use clipboard mode.",
            }

        token = access_token or settings.linkedin_access_token
        if not token:
            return {
                "success": False,
                "post_id": None,
                "error": "No LinkedIn access token configured.",
            }

        return self._publish_live(body, token)

    def _publish_live(self, body: str, token: str) -> dict[str, Any]:
        """Execute the LinkedIn UGC Post API call.

        Args:
            body: Post body text.
            token: OAuth2 bearer token.

        Returns:
            Publish result dict.
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        payload = {
            "author": "urn:li:person:me",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": body},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    f"{_LINKEDIN_API_BASE}/ugcPosts", json=payload, headers=headers
                )
                resp.raise_for_status()
                post_id = resp.headers.get("x-restli-id", "")
                logger.info("linkedin_post_published", post_id=post_id)
                return {"success": True, "post_id": post_id, "error": None}
        except httpx.HTTPError as exc:
            logger.error("linkedin_publish_failed", error=str(exc))
            return {"success": False, "post_id": None, "error": str(exc)}
