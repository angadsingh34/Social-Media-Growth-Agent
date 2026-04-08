"""LangGraph orchestration graph for the full agent pipeline.

Defines the stateful directed graph that routes through:
  Profile Analysis → Competitive Analysis → Calendar Generation →
  Calendar HITL Review → Content Generation → Content Review → Publishing

Uses a TypedDict state object shared across all nodes.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.competitive_landscape_agent import CompetitiveLandscapeAgent
from src.agents.copy_agent import CopyAgent
from src.agents.hashtag_agent import HashtagAgent
from src.agents.profile_intelligence_agent import ProfileIntelligenceAgent
from src.agents.visual_concept_agent import VisualConceptAgent
from src.models.schemas import (
    CompetitiveAnalysisReport,
    ContentCalendar,
    GeneratedPost,
    PipelineStage,
    Platform,
    ProfileIntelligenceReport,
    ReviewStatus,
)
from src.orchestrator.calendar_orchestrator import CalendarOrchestrator
from src.rag.retriever import RAGRetriever
from src.services.llm_service import LLMService
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class PipelineState(TypedDict, total=False):
    """Shared state object passed between LangGraph nodes.

    Attributes:
        run_id: Unique identifier for this pipeline execution.
        username: The target user's social media handle.
        platform: Primary social media platform.
        stage: Current pipeline stage.
        profile_report: Output of the Profile Intelligence Agent.
        competitive_report: Output of the Competitive Landscape Agent.
        calendar: The generated (and optionally revised) content calendar.
        calendar_feedback: Latest HITL feedback from the user.
        calendar_approved: Whether the user has approved the calendar.
        generated_posts: List of fully generated post content objects.
        error: Error message if a node fails.
    """

    run_id: str
    username: str
    platform: str
    period_days: int
    stage: str
    profile_report: Optional[dict[str, Any]]
    competitive_report: Optional[dict[str, Any]]
    calendar: Optional[dict[str, Any]]
    calendar_feedback: Optional[str]
    calendar_approved: bool
    generated_posts: list[dict[str, Any]]
    error: Optional[str]


def build_pipeline(
    llm: Optional[LLMService] = None,
    retriever: Optional[RAGRetriever] = None,
) -> StateGraph:
    """Build and return the compiled LangGraph pipeline.

    Args:
        llm: Shared LLM service for all agents.
        retriever: Shared RAG retriever for all agents.

    Returns:
        A compiled StateGraph ready for invocation.
    """
    shared_llm = llm or LLMService()
    shared_retriever = retriever or RAGRetriever()

    profile_agent = ProfileIntelligenceAgent(llm=shared_llm, retriever=shared_retriever)
    competitive_agent = CompetitiveLandscapeAgent(
        llm=shared_llm, retriever=shared_retriever
    )
    calendar_orch = CalendarOrchestrator(llm=shared_llm, retriever=shared_retriever)
    copy_agent = CopyAgent(llm=shared_llm, retriever=shared_retriever)
    hashtag_agent = HashtagAgent(llm=shared_llm, retriever=shared_retriever)
    visual_agent = VisualConceptAgent(llm=shared_llm, retriever=shared_retriever)

    # -----------------------------------------------------------------------
    # Node Definitions
    # -----------------------------------------------------------------------

    def node_profile_analysis(state: PipelineState) -> PipelineState:
        """Run the Profile Intelligence Agent."""
        logger.info(
            "pipeline_node", node="profile_analysis", run_id=state.get("run_id")
        )
        try:
            report = profile_agent.run(
                platform=Platform(state["platform"]),
                username=state["username"],
            )
            return {
                **state,
                "profile_report": report.model_dump(),
                "stage": PipelineStage.COMPETITIVE_ANALYSIS.value,
            }
        except Exception as exc:
            return {**state, "error": f"Profile analysis failed: {exc}"}

    def node_competitive_analysis(state: PipelineState) -> PipelineState:
        """Run the Competitive Landscape Agent."""
        logger.info(
            "pipeline_node", node="competitive_analysis", run_id=state.get("run_id")
        )
        try:
            profile_report = ProfileIntelligenceReport(**state["profile_report"])
            report = competitive_agent.run(
                user_profile_report=profile_report,
                use_mock=True,
            )
            return {
                **state,
                "competitive_report": report.model_dump(),
                "stage": PipelineStage.CALENDAR_GENERATION.value,
            }
        except Exception as exc:
            return {**state, "error": f"Competitive analysis failed: {exc}"}

    def node_calendar_generation(state: PipelineState) -> PipelineState:
        """Generate the initial content calendar."""
        logger.info(
            "pipeline_node", node="calendar_generation", run_id=state.get("run_id")
        )
        try:
            calendar = calendar_orch.generate(
                username=state["username"],
                period_days=state.get("period_days", 14),
                profile_report=ProfileIntelligenceReport(**state["profile_report"]),
                competitive_report=CompetitiveAnalysisReport(
                    **state["competitive_report"]
                ),
            )
            return {
                **state,
                "calendar": calendar.model_dump(),
                "calendar_approved": False,
                "stage": PipelineStage.CALENDAR_REVIEW.value,
            }
        except Exception as exc:
            return {**state, "error": f"Calendar generation failed: {exc}"}

    def node_calendar_review(state: PipelineState) -> PipelineState:
        """Apply user HITL feedback to the calendar (or approve it)."""
        logger.info("pipeline_node", node="calendar_review", run_id=state.get("run_id"))
        if state.get("calendar_approved"):
            return {
                **state,
                "stage": PipelineStage.CONTENT_GENERATION.value,
            }

        feedback = state.get("calendar_feedback")
        if feedback:
            calendar = ContentCalendar(**state["calendar"])
            revised = calendar_orch.revise(calendar, feedback)
            return {
                **state,
                "calendar": revised.model_dump(),
                "stage": PipelineStage.CALENDAR_REVIEW.value,
            }

        # No feedback yet — stay in review stage
        return {**state, "stage": PipelineStage.CALENDAR_REVIEW.value}

    def node_content_generation(state: PipelineState) -> PipelineState:
        """Run all three content sub-agents for every calendar entry."""
        logger.info(
            "pipeline_node", node="content_generation", run_id=state.get("run_id")
        )
        try:
            calendar = ContentCalendar(**state["calendar"])
            posts: list[dict[str, Any]] = []

            for entry in calendar.entries:
                post_id = str(uuid.uuid4())
                body = copy_agent.run(entry=entry, username=state["username"])
                tags = hashtag_agent.run(entry=entry)
                visual = visual_agent.run(entry=entry)

                post = GeneratedPost(
                    post_id=post_id,
                    calendar_entry_id=entry.entry_id,
                    platform=entry.platform,
                    body_copy=body,
                    hashtags=tags,
                    visual_prompt=visual,
                )
                posts.append(post.model_dump())

            return {
                **state,
                "generated_posts": posts,
                "stage": PipelineStage.CONTENT_REVIEW.value,
            }
        except Exception as exc:
            return {**state, "error": f"Content generation failed: {exc}"}

    def node_complete(state: PipelineState) -> PipelineState:
        """Mark the pipeline as complete."""
        logger.info("pipeline_complete", run_id=state.get("run_id"))
        return {**state, "stage": PipelineStage.COMPLETE.value}

    # -----------------------------------------------------------------------
    # Routing Functions
    # -----------------------------------------------------------------------

    def route_after_profile(state: PipelineState) -> str:
        return "error" if state.get("error") else "competitive_analysis"

    def route_after_competitive(state: PipelineState) -> str:
        return "error" if state.get("error") else "calendar_generation"

    def route_after_calendar_gen(state: PipelineState) -> str:
        return "error" if state.get("error") else "calendar_review"

    def route_after_calendar_review(state: PipelineState) -> str:
        if state.get("error"):
            return "error"
        if state.get("calendar_approved"):
            return "content_generation"
        return "calendar_review"  # loop until approved

    def route_after_content_gen(state: PipelineState) -> str:
        return "error" if state.get("error") else "complete"

    # -----------------------------------------------------------------------
    # Graph Assembly
    # -----------------------------------------------------------------------

    graph = StateGraph(PipelineState)

    graph.add_node("profile_analysis", node_profile_analysis)
    graph.add_node("competitive_analysis", node_competitive_analysis)
    graph.add_node("calendar_generation", node_calendar_generation)
    graph.add_node("calendar_review", node_calendar_review)
    graph.add_node("content_generation", node_content_generation)
    graph.add_node("complete", node_complete)
    graph.add_node("error", lambda s: {**s, "stage": "error"})

    graph.add_edge(START, "profile_analysis")
    graph.add_conditional_edges("profile_analysis", route_after_profile)
    graph.add_conditional_edges("competitive_analysis", route_after_competitive)
    graph.add_conditional_edges("calendar_generation", route_after_calendar_gen)
    graph.add_conditional_edges("calendar_review", route_after_calendar_review)
    graph.add_conditional_edges("content_generation", route_after_content_gen)
    graph.add_edge("complete", END)
    graph.add_edge("error", END)

    return graph.compile()
