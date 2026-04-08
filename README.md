# 🚀 Autonomous Social Media Growth Agent

A production-grade multi-agent AI system for social media profile analysis,
competitive intelligence, content calendar generation (with Human-in-the-Loop review),
content creation, and publishing to LinkedIn and X (Twitter).

## Architecture Overview

```

Profile Intelligence Agent ──┐
                             ├──▶ Calendar Orchestrator (HITL)
Competitive Landscape Agent ─┘                  │
                                                ▼
                                    ┌─── Content Pipeline ───┐
                                    │ Copy Agent             │
                                    │ Hashtag Agent          │──▶ Review Interface ──▶ Publish
                                    │ Visual Concept Agent   │
                                    └────────────────────────┘

All agents share:
• LLM Service (Groq / HuggingFace)
• RAG Retriever (FAISS + sentence-transformers)
• Structured Logging (structlog)

```

## Tech Stack

| Layer            | Technology                         |
| ---------------- | ---------------------------------- |
| Language         | Python 3.11                        |
| Agent Framework  | LangGraph + LangChain              |
| Web Framework    | FastAPI                            |
| UI               | Streamlit                          |
| LLM Provider     | Groq (free tier)                   |
| Vector Store     | FAISS + sentence-transformers      |
| Database         | SQLite (local) / PostgreSQL (prod) |
| Containerisation | Docker + docker-compose            |

## Setup — Local Development

### 1. Clone & create virtual environment

```bash
git clone https://github.com/yourname/autonomous-social-agent.git
cd autonomous-social-agent
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
export PYTHONPATH=.
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set:
#   GROQ_API_KEY=your_key_here   (get free key at console.groq.com)
#   USE_MOCK_DATA=true
```

### 3. Run with Docker (recommended)

```bash
cd docker
docker-compose up --build
```

- **FastAPI docs:** http://localhost:8000/docs
- **Streamlit UI:** http://localhost:8501

### 4. Run without Docker

```bash
# Terminal 1 — API
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — UI
streamlit run src/ui/streamlit_app.py # run export PYTHONPATH=. first if src error
```

## Running Tests

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

## API Endpoints

| Method | Path                                   | Description                           |
| ------ | -------------------------------------- | ------------------------------------- |
| GET    | /health                                | System health check                   |
| POST   | /api/v1/profile/analyse                | Trigger profile intelligence analysis |
| GET    | /api/v1/profile/{username}             | Retrieve stored profile report        |
| POST   | /api/v1/calendar/generate              | Generate content calendar             |
| POST   | /api/v1/calendar/feedback              | Submit HITL feedback / approve        |
| GET    | /api/v1/calendar/{id}                  | Retrieve calendar                     |
| POST   | /api/v1/content/generate/{calendar_id} | Run content pipeline                  |
| POST   | /api/v1/content/regenerate             | Regenerate single component           |
| PATCH  | /api/v1/content/{post_id}/approve      | Approve a post                        |
| POST   | /api/v1/publish                        | Publish approved posts                |

Full OpenAPI spec available at: http://localhost:8000/openapi.json

## Pipeline Walkthrough

1. **Profile Analysis** — Enter your LinkedIn/X handle. The Profile Intelligence Agent
   analyses your writing style, content themes, posting cadence, and engagement patterns.

2. **Competitive Intelligence** — The Competitive Landscape Agent discovers 3-5 peer
   profiles, identifies content gaps, and surfaces trending topics.

3. **Calendar Generation + HITL** — A 14-day calendar is generated from your content DNA
   and competitive intelligence. Revise it in natural language until you approve it.

4. **Content Generation** — Three specialised agents (Copy, Hashtag, Visual Concept) run
   in parallel for each calendar entry. Review and regenerate individual components.

5. **Publishing** — Publish approved posts directly via LinkedIn Share API / X API v2, or
   use clipboard mode for manual posting.

## Configuration

| Variable            | Default         | Description                          |
| ------------------- | --------------- | ------------------------------------ |
| `GROQ_API_KEY`      | —               | Groq inference API key               |
| `USE_MOCK_DATA`     | `true`          | Use fixture data (no live API calls) |
| `ENABLE_PUBLISHING` | `false`         | Allow real social-media publishing   |
| `LOG_LEVEL`         | `INFO`          | Logging verbosity                    |
| `DATABASE_URL`      | `sqlite:///...` | Database connection string           |

## Notes for Evaluators

- All components run on free-tier services and local infrastructure.
- `USE_MOCK_DATA=true` (default) enables full demo without any API credits.
- The LangGraph pipeline graph is in `src/orchestrator/graph.py`.
- The HITL review loop is implemented in `src/orchestrator/calendar_orchestrator.py`.
- Agent metrics (latency, token usage) are surfaced via the `/metrics` endpoint and logs.
