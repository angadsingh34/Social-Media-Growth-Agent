"""Streamlit UI — The interactive front-end for the Social Growth Agent.

Provides a multi-step wizard covering:
  1. Profile Analysis
  2. Competitive Landscape
  3. Content Calendar with HITL review
  4. Content Generation & Review
  5. Publishing
"""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from src.agents.competitive_landscape_agent import CompetitiveLandscapeAgent
from src.agents.copy_agent import CopyAgent
from src.agents.hashtag_agent import HashtagAgent
from src.agents.profile_intelligence_agent import ProfileIntelligenceAgent
from src.agents.visual_concept_agent import VisualConceptAgent
from src.config import get_settings
from src.models.schemas import (
    GeneratedPost,
    Platform,
    ProfileIntelligenceReport,
    ReviewStatus,
)
from src.orchestrator.calendar_orchestrator import CalendarOrchestrator
from src.services.linkedin_service import LinkedInService
from src.services.twitter_service import TwitterService
from src.utils.logging_config import configure_logging

configure_logging()
settings = get_settings()

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Social Growth Agent",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Session State Init ────────────────────────────────────────────────────────
def init_state() -> None:
    """Initialise all session state keys if not already set."""
    defaults: dict[str, Any] = {
        "step": 1,
        "profile_report": None,
        "competitive_report": None,
        "calendar": None,
        "generated_posts": [],
        "publish_records": [],
        "username": "",
        "platform": "linkedin",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_state()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Social Media Growth Agent")
    st.markdown("---")
    st.markdown("**Pipeline Progress**")
    steps = [
        "1. Profile Analysis",
        "2. Competitive Intelligence",
        "3. Content Calendar",
        "4. Content Generation",
        "5. Review & Publish",
    ]
    for i, s in enumerate(steps, 1):
        icon = (
            "✅"
            if st.session_state.step > i
            else ("🔵" if st.session_state.step == i else "⚪")
        )
        st.markdown(f"{icon} {s}")

    st.markdown("---")
    st.markdown(f"**Mode:** {' Demo' if settings.use_mock_data else ' Live'}")
    st.markdown(
        f"**Publishing:** {' Live' if settings.enable_publishing else ' Clipboard'}"
    )


# ── Helper ────────────────────────────────────────────────────────────────────
def show_step_header(title: str, subtitle: str) -> None:
    """Render a styled step header.

    Args:
        title: Main heading text.
        subtitle: Supporting sub-text.
    """
    st.title(title)
    st.caption(subtitle)
    st.markdown("---")


# ── Step 1: Profile Analysis ──────────────────────────────────────────────────
if st.session_state.step == 1:
    show_step_header(
        "Step 1: Profile Intelligence",
        "Analyse your LinkedIn or X (Twitter) profile to build your content DNA.",
    )

    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input(
            "Profile Username / Handle", placeholder="jane-doe or @jane_doe"
        )
        platform = st.selectbox("Platform", ["linkedin", "twitter"])

    if st.button("Analyse Profile", type="primary", disabled=not username):
        with st.spinner("Analysing profile… this may take a moment."):
            clean_username = username.lstrip("@")

            # Validate against mock data before running analysis
            from src.utils.mock_data import MOCK_USER_PROFILE, MOCK_COMPETITOR_PROFILES

            known_usernames = {MOCK_USER_PROFILE["username"]} | {
                p["username"] for p in MOCK_COMPETITOR_PROFILES
            }
            if clean_username not in known_usernames:
                st.error(
                    f"Username **{clean_username}** not found in mock data. "
                    f"Try: `{MOCK_USER_PROFILE['username']}` or one of "
                    f"{sorted(known_usernames - {MOCK_USER_PROFILE['username']})}."
                )
            else:
                agent = ProfileIntelligenceAgent()
                try:
                    report = agent.run(
                        platform=Platform(platform),
                        username=clean_username,
                    )
                    st.session_state.profile_report = report.model_dump()
                    st.session_state.username = clean_username
                    st.session_state.platform = platform
                    st.success("Profile analysis complete!")
                except Exception as exc:
                    st.error(f"Analysis failed: {exc}")

    if st.session_state.profile_report:
        r = st.session_state.profile_report
        st.subheader(f"📋 Content DNA: {r['full_name']}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Followers", f"{r['follower_count']:,}")
        col2.metric("Posts / Week", r.get("posting_cadence_per_week", 0))
        col3.metric("Top Topics", len(r.get("top_topics", [])))

        st.markdown("**🖊️ Writing Style**")
        ws = r.get("writing_style", {})
        st.info(
            f"Tone: **{ws.get('tone', '-')}** | "
            f"Vocabulary: **{ws.get('vocabulary_level', '-')}** | "
            f"Avg length: **{ws.get('avg_post_length', '-')} words**"
        )

        st.markdown("**🏷️ Top Topics**")
        st.write(", ".join(r.get("top_topics", [])))

        st.markdown("**💡 Content DNA Summary**")
        st.write(r.get("content_dna_summary", ""))

        if st.button("Continue to Competitive Analysis"):
            st.session_state.step = 2
            st.rerun()


# ── Step 2: Competitive Landscape ─────────────────────────────────────────────
elif st.session_state.step == 2:
    show_step_header(
        "Step 2: Competitive Intelligence",
        "Discover and benchmark competitor profiles to surface content gaps and opportunities.",
    )

    if st.button("Run Competitive Analysis", type="primary"):
        with st.spinner("Analysing competitor landscape…"):
            profile_report = ProfileIntelligenceReport(
                **st.session_state.profile_report
            )
            agent = CompetitiveLandscapeAgent()
            try:
                comp_report = agent.run(
                    user_profile_report=profile_report, use_mock=True
                )
                st.session_state.competitive_report = comp_report.model_dump()
                st.success("Competitive analysis complete!")
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")

    if st.session_state.competitive_report:
        cr = st.session_state.competitive_report

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📊 Content Gaps")
            for gap in cr.get("content_gaps", []):
                with st.expander(f"🔸 {gap['topic_or_format']}"):
                    st.write(f"**Competitor:** {gap['competitor_name']}")
                    st.write(f"**Signal:** {gap['engagement_signal']}")
                    st.write(f"**Recommendation:** {gap['recommendation']}")

        with col2:
            st.subheader("🌟 Strategic Opportunities")
            for opp in cr.get("strategic_opportunities", []):
                st.success(opp)

        st.subheader("Trending Topics in Your Niche")
        st.write(", ".join(cr.get("trending_topics_in_niche", [])))

        if st.button("Generate Content Calendar"):
            st.session_state.step = 3
            st.rerun()


# ── Step 3: Content Calendar + HITL ──────────────────────────────────────────
elif st.session_state.step == 3:
    show_step_header(
        "Step 3: Content Calendar",
        "Review, refine, and approve your data-driven content calendar.",
    )

    if st.session_state.calendar is None:
        period_days = st.slider("Calendar period (days)", 3, 14, 7)
        if st.button("Generate Calendar", type="primary"):
            with st.spinner("Building your personalised content calendar…"):
                from src.models.schemas import CompetitiveAnalysisReport

                orch = CalendarOrchestrator()
                profile_report = ProfileIntelligenceReport(
                    **st.session_state.profile_report
                )
                comp_report = CompetitiveAnalysisReport(
                    **st.session_state.competitive_report
                )
                calendar = orch.generate(
                    username=st.session_state.username,
                    period_days=period_days,
                    profile_report=profile_report,
                    competitive_report=comp_report,
                )
                st.session_state.calendar = calendar.model_dump()
                st.rerun()

    if st.session_state.calendar:
        cal = st.session_state.calendar
        st.subheader(
            f"📅 {cal['period_days']}-Day Calendar ({len(cal['entries'])} entries)"
        )

        # Display calendar as table
        import pandas as pd

        df = pd.DataFrame(
            [
                {
                    "Day": e["day_number"],
                    "Platform": e["platform"].upper(),
                    "Format": e["content_format"].replace("_", " ").title(),
                    "Topic": e["topic"],
                    "Time": e["scheduled_time"],
                    "Rationale": e["rationale"],
                }
                for e in cal["entries"]
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        # HITL Feedback
        st.subheader("💬 Provide Feedback")
        feedback = st.text_area(
            "What would you like to change?",
            placeholder='e.g. "Replace Day 3 topic with LangGraph best practices" or "Move the thread to Friday"',
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Revise Calendar") and feedback:
                with st.spinner("Revising calendar…"):
                    from src.models.schemas import ContentCalendar

                    orch = CalendarOrchestrator()
                    calendar_obj = ContentCalendar(**cal)
                    revised = orch.revise(calendar_obj, feedback)
                    st.session_state.calendar = revised.model_dump()
                    st.rerun()
        with col2:
            if st.button("Approve & Finalise Calendar", type="primary"):
                from src.models.schemas import ContentCalendar

                orch = CalendarOrchestrator()
                calendar_obj = ContentCalendar(**st.session_state.calendar)
                finalised = orch.finalise(calendar_obj)
                st.session_state.calendar = finalised.model_dump()
                st.session_state.step = 4
                st.rerun()


# ── Step 4: Content Generation & Review ──────────────────────────────────────
elif st.session_state.step == 4:
    show_step_header(
        "Step 4: Content Generation",
        "Review AI-generated post copy, hashtags, and visual concepts.",
    )

    if not st.session_state.generated_posts:
        if st.button("Generate All Content", type="primary"):
            from src.models.schemas import CalendarEntry, ContentCalendar

            calendar = ContentCalendar(**st.session_state.calendar)
            copy_agent = CopyAgent()
            hashtag_agent = HashtagAgent()
            visual_agent = VisualConceptAgent()
            posts = []

            progress = st.progress(0, text="Generating content…")
            total = len(calendar.entries)
            for idx, entry in enumerate(calendar.entries):
                import uuid

                body = copy_agent.run(entry=entry, username=st.session_state.username)
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
                posts.append(post.model_dump())
                progress.progress(
                    (idx + 1) / total, text=f"Generated {idx + 1}/{total}"
                )

            st.session_state.generated_posts = posts
            st.rerun()

    if st.session_state.generated_posts:
        posts = st.session_state.generated_posts
        approved_count = sum(1 for p in posts if p.get("review_status") == "approved")
        st.info(f"✅ {approved_count}/{len(posts)} posts approved")

        for idx, post in enumerate(posts):
            platform_icon = "🔗" if post["platform"] == "linkedin" else "✖️"
            with st.expander(
                f"{platform_icon} Post {idx + 1} — {post['platform'].upper()} | Status: {post.get('review_status', 'pending').upper()}",
                expanded=idx == 0,
            ):
                tab1, tab2, tab3 = st.tabs(
                    ["📝 Body Copy", "#️⃣ Hashtags", "🎨 Visual Concept"]
                )
                with tab1:
                    new_body = st.text_area(
                        "Body Copy",
                        value=post["body_copy"],
                        key=f"body_{idx}",
                        height=150,
                    )
                with tab2:
                    st.write(" ".join(post["hashtags"]))
                with tab3:
                    st.write(post["visual_prompt"])

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Approve", key=f"approve_{idx}"):
                        st.session_state.generated_posts[idx]["review_status"] = (
                            "approved"
                        )
                        st.session_state.generated_posts[idx]["body_copy"] = new_body
                        st.rerun()
                with col2:
                    if st.button("🔄 Regenerate Body", key=f"regen_{idx}"):
                        entry_dict = next(
                            (
                                e
                                for e in st.session_state.calendar["entries"]
                                if e["entry_id"] == post["calendar_entry_id"]
                            ),
                            None,
                        )
                        if entry_dict:
                            from src.models.schemas import CalendarEntry

                            entry = CalendarEntry(**entry_dict)
                            copy_agent = CopyAgent()
                            st.session_state.generated_posts[idx]["body_copy"] = (
                                copy_agent.run(
                                    entry=entry, username=st.session_state.username
                                )
                            )
                            st.session_state.generated_posts[idx]["review_status"] = (
                                "pending"
                            )
                            st.rerun()

        if approved_count > 0 and st.button("Proceed to Publishing", type="primary"):
            st.session_state.step = 5
            st.rerun()


# ── Step 5: Publish ───────────────────────────────────────────────────────────
elif st.session_state.step == 5:
    show_step_header(
        "Step 5: Review & Publish",
        "Publish your approved content to LinkedIn and/or X (Twitter).",
    )

    approved_posts = [
        p
        for p in st.session_state.generated_posts
        if p.get("review_status") == "approved"
    ]
    st.info(f"**{len(approved_posts)}** posts ready to publish.")

    for post in approved_posts:
        platform_icon = "🔗" if post["platform"] == "linkedin" else "✖️"
        with st.expander(f"{platform_icon} {post['platform'].upper()} post"):
            st.write(post["body_copy"])
            st.caption(" ".join(post["hashtags"]))

            if st.button("📤 Publish this post", key=f"pub_{post['post_id']}"):
                if settings.enable_publishing:
                    svc = (
                        LinkedInService()
                        if post["platform"] == "linkedin"
                        else TwitterService()
                    )
                    text = post["body_copy"] + "\n\n" + " ".join(post["hashtags"])
                    result = (
                        svc.publish_post(text)
                        if post["platform"] == "linkedin"
                        else svc.publish_tweet(text[:280])
                    )
                    if result.get("success"):
                        st.success("Published successfully!")
                    else:
                        st.error(f"Failed: {result.get('error')}")
                else:
                    st.code(post["body_copy"] + "\n\n" + " ".join(post["hashtags"]))
                    st.info(
                        "📋 Publishing is disabled. Copy the text above to post manually."
                    )

    if st.button("Start New Pipeline"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
