"""Curated mock data for development and testing.

When ``USE_MOCK_DATA=true`` all agents pull from these fixtures instead of
hitting live platform APIs, avoiding rate-limits and costs during demos.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Mock LinkedIn / Twitter profile raw payloads
# ---------------------------------------------------------------------------

MOCK_USER_PROFILE: dict[str, Any] = {
    "platform": "linkedin",
    "username": "jane-ai-engineer",
    "full_name": "Jane Doe",
    "headline": "Senior AI/ML Engineer | LangChain & LangGraph | Open-Source Contributor",
    "bio": (
        "Building production-grade AI systems. Passionate about agentic workflows, "
        "RAG pipelines, and making LLMs actually useful. 10 years in Python. "
        "Speaker at PyCon 2024."
    ),
    "follower_count": 4800,
    "connection_count": 3100,
    "recent_posts": [
        {
            "id": "p001",
            "text": "Just shipped a multi-agent RAG pipeline using LangGraph 🚀 "
            "Key learning: state machines make agent orchestration far more "
            "predictable. Thread 🧵",
            "likes": 312,
            "comments": 47,
            "shares": 28,
            "format": "thread",
            "topics": ["LangGraph", "RAG", "agents"],
            "posted_at": "2024-05-10T09:00:00Z",
        },
        {
            "id": "p002",
            "text": "Hot take: most 'AI agents' are just glorified if-else chains. "
            "Here is what separates real agents from demos…",
            "likes": 891,
            "comments": 134,
            "shares": 76,
            "format": "short_post",
            "topics": ["AI", "agents", "opinion"],
            "posted_at": "2024-05-07T14:30:00Z",
        },
        {
            "id": "p003",
            "text": "5 things I wish I knew before building my first production RAG system",
            "likes": 654,
            "comments": 89,
            "shares": 112,
            "format": "listicle",
            "topics": ["RAG", "production", "lessons-learned"],
            "posted_at": "2024-05-03T08:00:00Z",
        },
    ],
    "posting_frequency_per_week": 3.2,
    "primary_topics": ["LangChain", "LangGraph", "RAG", "Python", "MLOps"],
    "content_formats": ["thread", "short_post", "listicle", "article"],
}

MOCK_COMPETITOR_PROFILES: list[dict[str, Any]] = [
    {
        "platform": "linkedin",
        "username": "alex-llm-builder",
        "full_name": "Alex Chen",
        "headline": "AI Engineer | Building with LLMs | Founder @AgentForge",
        "follower_count": 18500,
        "recent_posts": [
            {
                "id": "c1p001",
                "text": "Why every team needs a prompt registry in 2024",
                "likes": 1200,
                "comments": 203,
                "shares": 189,
                "format": "article",
                "topics": ["prompts", "LLMOps", "engineering"],
            }
        ],
        "primary_topics": ["LLMOps", "prompt-engineering", "production-AI"],
        "posting_frequency_per_week": 5.0,
    },
    {
        "platform": "twitter",
        "username": "sarah_ml_hacks",
        "full_name": "Sarah Park",
        "headline": "ML hacks & LLM tips daily",
        "follower_count": 31200,
        "recent_posts": [
            {
                "id": "c2p001",
                "text": "🔥 LangGraph cheatsheet — 15 patterns in one thread",
                "likes": 2400,
                "comments": 312,
                "shares": 567,
                "format": "thread",
                "topics": ["LangGraph", "cheatsheet", "agents"],
            }
        ],
        "primary_topics": ["LangGraph", "Python", "AI-tips"],
        "posting_frequency_per_week": 7.0,
    },
    {
        "platform": "linkedin",
        "username": "david-vector-db",
        "full_name": "David Osei",
        "headline": "Vector DB Evangelist | Weaviate | RAG at Scale",
        "follower_count": 9400,
        "recent_posts": [
            {
                "id": "c3p001",
                "text": "FAISS vs ChromaDB vs Weaviate — the honest comparison",
                "likes": 876,
                "comments": 145,
                "shares": 234,
                "format": "article",
                "topics": ["vectorDB", "RAG", "comparison"],
            }
        ],
        "primary_topics": ["VectorDB", "RAG", "search"],
        "posting_frequency_per_week": 2.5,
    },
]

MOCK_CONTENT_CALENDAR_SEED: dict[str, Any] = {
    "period_days": 14,
    "platforms": ["linkedin", "twitter"],
    "user_niche": "AI Engineering & Agentic Systems",
}
