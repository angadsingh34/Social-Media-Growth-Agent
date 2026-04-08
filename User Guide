### End User Guides

#### Step 1 — Profile Analysis

What it does: Analyses your LinkedIn or X profile to understand your content identity — your writing voice, top topics, posting cadence, and what kinds of posts get the most engagement.

**How to use it:**

1. Type your profile username in the text box.
   - For LinkedIn, use your profile URL slug — e.g. if your URL is `linkedin.com/in/jane-doe`, enter `jane-doe`.
   - For Twitter/X, use your handle without the `@` — e.g. if your handle is `@jane_doe`, enter `jane_doe`.
2. Select your platform from the dropdown.
3. Click **Analyse Profile**.
4. Review the Content DNA report that appears. It shows:
   - Your top topics and content formats
   - How often you typically post
   - What kind of posts get the most engagement
   - A plain-English summary of your content identity

**What if the numbers look wrong?** In `USE_MOCK_DATA=true` mode (the default), the report is generated from sample data. It's designed to be realistic and represents a typical AI/tech professional profile. Your real data will appear when live API credentials are configured.

---

#### Step 2 — Competitive Intelligence

What it does: Identifies 3-5 creators in your niche and benchmarks them against your profile. Surfaces topics you're under-covering, content formats that drive outsized engagement in your space, and strategic opportunities specific to your niche.

**How to use it:**

1. Click **Run Competitive Analysis**.
2. Review the results:
   - **Content gaps** — topics your competitors cover that you don't, with specific recommendations.
   - **Strategic opportunities** — actionable suggestions for growing your presence.
   - **Trending topics** — what's generating engagement in your niche right now.

---

#### Step 3 — Content Calendar

What it does: Generates a personalised content calendar grounded in your profile analysis and competitive intelligence. Every post topic has a rationale — it's not arbitrary.

**How to use it:**

1. Use the slider to choose how many days you want the calendar to cover (7–30 days).
2. Click **Generate Calendar**.
3. Read through the calendar. Each row shows:
   - The day number and scheduled time
   - The platform (LinkedIn or Twitter)
   - The content format (thread, short post, article, etc.)
   - The topic
   - Why this topic was chosen (rationale)

**Revising the calendar:**

Type your feedback in the text box at the bottom and click **Revise Calendar**. You can say things like:

- _"Replace Day 3 with a post about LangGraph memory management"_
- _"Move the Thursday thread to Friday morning"_
- _"Add more Twitter posts in the second week"_
- _"Remove all poll entries — I don't like polls"_

You can revise as many times as you like. The system keeps the full revision history.

**Approving the calendar:**

When you're happy with the calendar, click **Approve & Finalise Calendar**. This locks the calendar and moves you to content generation. Once approved, the calendar cannot be revised — you'd need to start a new pipeline run.

---

#### Step 4 — Content Generation & Review

What it does: Three AI agents run for each calendar entry to produce complete, ready-to-post content:

- **Copy Agent** — writes the post body in your voice
- **Hashtag Agent** — picks platform-optimised hashtags
- **Visual Concept Agent** — writes a detailed image prompt you can use with any image generation tool

**How to use it:**

1. Click **Generate All Content**.
2. A progress bar shows generation happening in real time. For a 14-day calendar this typically takes 1–3 minutes.
3. For each post, you'll see three tabs:
   - **Body Copy** — the full post text, editable in place
   - **Hashtags** — the selected hashtags
   - **Visual Concept** — the image generation prompt
4. Actions per post:
   - **Approve** — marks the post as ready to publish
   - **Regenerate Body** — asks the AI to rewrite just the body copy

You can also edit the body copy directly in the text area before approving.

---

#### Step 5 — Review & Publish

What it does: Shows all approved posts and lets you publish them to LinkedIn and/or Twitter.

**Publishing options:**

- If **ENABLE_PUBLISHING=false** (the default), the post text is shown in a code box — copy it and paste it directly into LinkedIn or Twitter manually. This is called "clipboard mode."
- If **ENABLE_PUBLISHING=true** and API credentials are configured, clicking **Publish this post** sends it directly to the platform and shows you a confirmation with the platform's post ID.

**Starting a new pipeline:** Click **Start New Pipeline** at the bottom of the page to reset all state and begin again.

---

### Docker Setup (Recommended)

Docker is the recommended setup path — it handles all dependency conflicts, the embedding model download, and service orchestration automatically.

#### 1. Clone and configure

```bash
git clone https://github.com/yourname/autonomous-social-agent.git
cd autonomous-social-agent
cp .env.example .env
# Edit .env — set GROQ_API_KEY at minimum
```

#### 2. Build and start all services

```bash
cd docker
docker-compose up --build
```

First build takes ~4 minutes (downloads Python packages and the 90 MB embedding model). Subsequent starts take ~15 seconds.

**Services started:**

| Service      | Port | URL                     |
| ------------ | ---- | ----------------------- |
| FastAPI API  | 8000 | `http://localhost:8000` |
| Streamlit UI | 8501 | `http://localhost:8501` |

#### 3. Verify

```bash
# In a new terminal
curl http://localhost:8000/health
```

#### 4. Useful Docker commands

```bash
# View live logs from both services
docker-compose logs -f

# Restart a single service (e.g. after .env change)
docker-compose restart api

# Stop all services
docker-compose down

# Stop and remove volumes (full reset)
docker-compose down -v

# Rebuild after requirements.txt changes
docker-compose up --build
```

---
