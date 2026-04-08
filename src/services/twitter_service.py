"""Twitter/X data ingestion and publishing service.

Uses Tweepy for v2 API access. Supports mock mode for demo and development.
"""

from __future__ import annotations

from typing import Any, Optional

import tweepy

from src.config import get_settings
from src.utils.logging_config import get_logger
from src.utils.mock_data import MOCK_COMPETITOR_PROFILES, MOCK_USER_PROFILE

logger = get_logger(__name__)
settings = get_settings()


class TwitterService:
    """Client for Twitter/X profile data fetching and tweet publishing.

    Attributes:
        use_mock: Whether to use mock fixture data.
        _client: Tweepy Client instance (initialised lazily).
    """

    def __init__(self, use_mock: Optional[bool] = None) -> None:
        """Initialise the service.

        Args:
            use_mock: Override the global ``USE_MOCK_DATA`` setting.
        """
        self.use_mock: bool = (
            use_mock if use_mock is not None else settings.use_mock_data
        )
        self._client: Optional[tweepy.Client] = None

    def _get_client(self) -> tweepy.Client:
        """Return a lazily-initialised Tweepy Client.

        Returns:
            Authenticated Tweepy Client.

        Raises:
            RuntimeError: If required credentials are missing.
        """
        if self._client is None:
            if not settings.twitter_bearer_token:
                raise RuntimeError("TWITTER_BEARER_TOKEN not configured.")
            self._client = tweepy.Client(
                bearer_token=settings.twitter_bearer_token,
                consumer_key=settings.twitter_api_key,
                consumer_secret=settings.twitter_api_secret,
                access_token=settings.twitter_access_token,
                access_token_secret=settings.twitter_access_secret,
                wait_on_rate_limit=True,
            )
        return self._client

    # ------------------------------------------------------------------
    # Profile Data Fetching
    # ------------------------------------------------------------------

    def fetch_profile(self, username: str) -> dict[str, Any]:
        """Fetch a Twitter profile and recent tweets.

        Args:
            username: Twitter/X handle (without @).

        Returns:
            Normalised profile dict.
        """
        if self.use_mock:
            logger.info("twitter_fetch_profile_mock", username=username)
            mock = dict(MOCK_USER_PROFILE)
            mock["platform"] = "twitter"
            mock["username"] = username
            return mock

        return self._fetch_profile_live(username)

    def _fetch_profile_live(self, username: str) -> dict[str, Any]:
        """Fetch profile using Tweepy v2 Client.

        Args:
            username: Twitter handle.

        Returns:
            Normalised profile dict, or mock on error.
        """
        try:
            client = self._get_client()
            user_resp = client.get_user(
                username=username,
                user_fields=["public_metrics", "description"],
            )
            if not user_resp.data:
                raise ValueError(f"User @{username} not found.")

            user = user_resp.data
            metrics = user.public_metrics or {}

            tweets_resp = client.get_users_tweets(
                id=user.id,
                max_results=10,
                tweet_fields=["public_metrics", "created_at", "text"],
            )

            recent_posts = []
            if tweets_resp.data:
                for tweet in tweets_resp.data:
                    pm = tweet.public_metrics or {}
                    recent_posts.append(
                        {
                            "id": str(tweet.id),
                            "text": tweet.text,
                            "likes": pm.get("like_count", 0),
                            "comments": pm.get("reply_count", 0),
                            "shares": pm.get("retweet_count", 0),
                            "format": "short_post",
                            "topics": [],
                            "posted_at": str(tweet.created_at),
                        }
                    )

            return {
                "platform": "twitter",
                "username": username,
                "full_name": user.name,
                "bio": user.description or "",
                "follower_count": metrics.get("followers_count", 0),
                "following_count": metrics.get("following_count", 0),
                "recent_posts": recent_posts,
                "posting_frequency_per_week": 0.0,
                "primary_topics": [],
                "content_formats": [],
            }
        except Exception as exc:
            logger.error("twitter_fetch_failed", error=str(exc), username=username)
            mock = dict(MOCK_USER_PROFILE)
            mock["platform"] = "twitter"
            mock["username"] = username
            return mock

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish_tweet(self, text: str) -> dict[str, Any]:
        """Publish a tweet using the Twitter v2 API.

        Args:
            text: Tweet body (≤280 characters for standard tweets).

        Returns:
            Dict with keys: success (bool), tweet_id (str|None), error (str|None).
        """
        if not settings.enable_publishing:
            logger.info("twitter_publish_disabled_clipboard_mode")
            return {
                "success": False,
                "tweet_id": None,
                "error": "Publishing disabled; use clipboard mode.",
            }

        try:
            client = self._get_client()
            response = client.create_tweet(text=text)
            tweet_id = str(response.data["id"]) if response.data else None
            logger.info("tweet_published", tweet_id=tweet_id)
            return {"success": True, "tweet_id": tweet_id, "error": None}
        except Exception as exc:
            logger.error("twitter_publish_failed", error=str(exc))
            return {"success": False, "tweet_id": None, "error": str(exc)}
