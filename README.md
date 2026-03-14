# MeaningMap

MeaningMap is an AI-powered audience interpretation simulator. You paste a message — a startup pitch, product launch, cold email, or social post — and the system generates multiple audience personas, runs each one as an independent interpretation agent, then surfaces where your audience aligns, where it splits, and which personas see red flags. The output is a visual "interpretation space" map, per-persona reactions with first-person quotes, and actionable misunderstanding risks with AI-powered rewrites.

## Why This Exists

Every message lands differently depending on who reads it. A founder's pitch that excites an early adopter may trigger skepticism in a risk-averse decision maker. MeaningMap makes that divergence visible *before* you hit send. It answers the question: "How will your audience read this?"

## DigitalOcean Gradient AI Full Stack

MeaningMap uses six DigitalOcean Gradient AI platform capabilities end-to-end:

| Layer | DO Service | Usage |
|---|---|---|
| **AI Inference** | Gradient GenAI API | LLM calls for persona generation, interpretation agents, and AI rewrites |
| **Embeddings** | Gradient Embeddings API | Vector embeddings for every analyzed message, enabling semantic search |
| **Agent Framework** | Gradient ADK | `@entrypoint` decorator, agent configuration, local dev via `gradient agent run` |
| **Agent Platform** | Gradient Agent Platform | Deployed agent accessible at `agents.do-ai.run` for programmatic invocation, with tracing and logs |
| **Database** | Managed PostgreSQL + pgvector | Persistent storage for analyses with vector similarity search via HNSW index |
| **Hosting** | App Platform | Web app deployment with health checks and auto-deploy from GitHub |

## What the Pipeline Does

1. **Persona generation** — Given a message and its type, the LLM generates a realistic distribution of audience personas (e.g. "Skeptical Pragmatist", "Budget-Conscious Buyer"), each with a worldview, priorities, and audience share percentage.
2. **Interpretation agents** — One LLM call per persona simulates how that person reads the message. Each agent returns a structured interpretation, a first-person quote, and five signal scores.
3. **Signal scoring** — Every persona is scored on five dimensions:
   - **Clarity** — How understandable the message feels
   - **Trust** — How trustworthy the message feels
   - **Hype** — How overhyped or exaggerated it sounds
   - **Confusion** — How confusing or ambiguous it feels
   - **Credibility** — How grounded and believable it seems
4. **Outlier detection** — Any persona with trust < 30 is flagged as an outlier. The frontend surfaces these with dedicated alert cards and visual treatments on the map.
5. **Risk extraction** — Misunderstanding risks are collected from all personas, attributed to the personas that raised them, and ranked by severity (derived from the affected personas' trust scores).
6. **Map projection** — Trust maps to the X axis, credibility maps to the Y axis, producing a 2D interpretation space where persona clustering and outlier distance are immediately visible.

## Key Features

### Cinematic loading flow
When you submit a message, the UI plays a staged 4-phase animation: persona avatars appear one by one, a progress bar fills while agents "think", divergence is called out dramatically if an outlier exists, and results reveal section by section with staggered fade-up animations.

### Interpretation space map
A full-width SVG scatter plot with labeled quadrants (High trust + credibility / Low trust + confused / High hype, low trust / Skeptical but engaged). Non-outlier personas are enclosed in a dashed cluster ellipse. Outlier personas are rendered with red dashed rings and connector lines back to the cluster centroid. Dots animate in with a spring pop; outlier dots get a pulse-ring attention animation. Clicking a dot highlights the corresponding persona card and scrolls to it.

### Outlier alert card
When a persona's trust drops below 30, a "Critical outlier" card renders with the persona's inner monologue as the lead element (large, italic, red-accented), followed by trust/share metadata and semantic signal chips (e.g. "Low trust", "High confusion") color-coded by severity — no raw numbers, just signal.

### Persona cards
A 2-column card grid where each card shows an avatar with initials, persona name, audience share, a color-coded trust bar (green > 60%, amber 35–60%, red < 35%), and a first-person italic quote. Outlier cards get a red "outlier" pill badge. Clicking a card expands it to show the full signal breakdown as colored tags. Only one card expands at a time; non-selected map dots dim to focus attention.

### Signal cards with visual encoding
Three stat cards — Alignment (with a 36px SVG donut arc), Divergence (color shifts from green to amber to red based on severity), and Lowest Trust (persona name in red with trust percentage).

### Fix with AI
Every misunderstanding risk item has a "Fix with AI" button. Clicking it opens a slide-in drawer showing the original message and an AI-generated rewrite that addresses the specific risk for the affected persona. The drawer includes "Copy rewrite" and "Use this version" (which replaces the input textarea content) buttons.

### Pre-submit state
Before any submission, three ghosted skeleton cards are shown with a prompt overlay: "Submit a message to map how different audiences will interpret it." This sets expectations and prevents a blank page.

### Accessibility
All entrance animations are wrapped in `@media (prefers-reduced-motion: no-preference)` and are disabled for users who prefer reduced motion.

### Past analyses & semantic search
All analyses are automatically saved to a DigitalOcean Managed PostgreSQL database with pgvector. Each saved analysis includes a vector embedding of the original message (generated via the Gradient Embeddings API), enabling semantic search across your history. The "Past Analyses" panel sits above the input form, collapsed by default into a lightweight trigger row showing the saved count. Clicking it expands the list with a semantic search bar — e.g. searching "pricing concerns" finds past analyses of messages that discussed pricing, even if different words were used. Clicking any history item reloads that analysis with the full cinematic reveal. The collapsed/expanded state is persisted in localStorage.

## Project Structure

```
main.py                            Gradient ADK entrypoint (run(payload, context))
backend/
  app.py                           FastAPI server — routes: /, /health, /api/analyze, /api/fix, /api/history, /api/search
  core/
    pipeline.py                    Orchestrates persona generation + parallel interpretation agents
    schemas.py                     Pydantic models (request, persona, interpretation, signals, map points, summary)
    analysis.py                    Scoring math: pairwise distances, map projection, summary + structured risk extraction
    client.py                      OpenAI-compatible LLM client (Gradient inference API)
    embeddings.py                  Gradient Embeddings API client for vector generation
    prompts.py                     System prompts for persona generation and interpretation
    db.py                          PostgreSQL + pgvector: schema init, CRUD, semantic search
  run_local.py                     CLI runner for testing without the web server
frontend/public/
  index.html                       Page structure: input form, history panel, loading stage, results sections, fix drawer
  favicon.ico                      App favicon
  assets/
    styles.css                     Dark theme, animations, history/search panel styles, responsive breakpoints
    app.js                         All UI logic: cinematic loading, map, persona cards, risk list, fix drawer, history, search
  sample-result.json               Bundled demo result for offline/demo use
tests/
  test_analysis.py                 Deterministic tests for normalization, pairwise distances, summary, map bounds
sample_request.json                Example API request payload
.env.example                       Template for environment variables
.gradient/agent.yml                Gradient ADK agent configuration
.do/app.yaml                       App Platform spec (DATABASE_URL points to a Managed PostgreSQL cluster)
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set in `.env`:

| Variable | Required | Default | Description |
|---|---|---|---|
| `GRADIENT_MODEL_ACCESS_KEY` | Yes | — | API key for Gradient inference (must start with `sk-do-`) |
| `GRADIENT_MODEL_ID` | No | `openai-gpt-oss-120b` | Model identifier |
| `GRADIENT_BASE_URL` | No | `https://inference.do-ai.run/v1/` | Inference API base URL |
| `GRADIENT_EMBEDDING_MODEL_ID` | No | `text-embedding-3-small` | Embedding model for semantic search |
| `DATABASE_URL` | No | — | PostgreSQL connection string (enables persistence + semantic search) |
| `DIGITALOCEAN_API_TOKEN` | Deploy only | — | Required for `gradient agent deploy` |

## Running Locally

### Web app

```bash
uvicorn backend.app:app --reload --port 3000
```

Open `http://localhost:3000`. The UI supports:

- **Live mode** — Submit a message to run the full AI pipeline via `/api/analyze`
- **Demo mode** — Click "Load Demo Result" to render a bundled sample without an API key

### CLI (without web server)

```bash
python -m backend.run_local --payload-file sample_request.json
python -m backend.run_local --payload-file sample_request.json --output-file output.json
```

### Tests

```bash
python -m pytest tests/ -v
```

## Deploy to DigitalOcean App Platform (Web App)

The App Platform spec at `.do/app.yaml` deploys the FastAPI web service. The database is a separately provisioned **Managed PostgreSQL cluster** (not an App Platform dev database), because pgvector requires a full managed cluster.

1. Push this codebase to GitHub.
2. Edit `.do/app.yaml` and set:
   - `services[0].git.repo_clone_url` to your repo URL
   - `services[0].git.branch` to your deploy branch
   - `GRADIENT_MODEL_ACCESS_KEY` to your real key (starts with `sk-do-`)
3. Create a Managed PostgreSQL cluster with pgvector support:

```bash
doctl databases create meaning-map-db --engine pg --version 16 --size db-s-1vcpu-1gb --region nyc1 --num-nodes 1
```

4. Get the connection URI and set it as `DATABASE_URL` in `.do/app.yaml` (or via the console):

```bash
doctl databases connection <DB_ID> --format URI --no-header
```

5. Authenticate and create the app:

```bash
doctl auth init --access-token "$DIGITALOCEAN_API_TOKEN"
doctl apps spec validate .do/app.yaml
doctl apps create --spec .do/app.yaml
```

6. Watch rollout and verify:

```bash
doctl apps list
doctl apps logs <APP_ID> --type run
curl https://<app-url>/health   # Should return {"status":"ok","database":true}
```

7. Future deploys — push to the configured branch, then:

```bash
doctl apps update <APP_ID> --spec .do/app.yaml
```

Notes:
- `/health` returns `{"status": "ok", "database": true}` when PostgreSQL + pgvector is connected.
- The frontend and API are served by the same FastAPI service.
- The app works without `DATABASE_URL` (history/search disabled), but `/api/analyze` always requires `GRADIENT_MODEL_ACCESS_KEY`.

## Running with Gradient ADK

```bash
gradient agent configure \
  --entrypoint-file main.py \
  --agent-workspace-name meaning-map \
  --deployment-name meaning-map \
  --description "MeaningMap interpretation pipeline" \
  --no-interactive
gradient agent run
```

Then invoke:

```bash
curl -X POST http://localhost:8080/run \
  -H 'Content-Type: application/json' \
  -d @sample_request.json
```

## Deploy Gradient ADK Agent

The agent can also be deployed to the **Gradient Agent Platform**, which provides a managed REST endpoint, execution tracing, and runtime logs. This is separate from the App Platform web app — the web app is the browser-facing UI, while the agent endpoint is a machine-facing JSON API for programmatic invocation by other services or agents.

```bash
gradient agent deploy
```

Once deployed, invoke the agent directly:

```bash
curl -X POST https://agents.do-ai.run/v1/<workspace-id>/meaning-map/run \
  -H "Authorization: Bearer $DIGITALOCEAN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d @sample_request.json
```

Monitor with:

```bash
gradient agent logs
gradient agent traces
```

## API Reference

### `POST /api/analyze`

Runs the full interpretation pipeline.

**Request:**

```json
{
  "content": "We built an AI copilot for founders...",
  "message_type": "startup_pitch",
  "num_personas": 5
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `content` | string | Yes | The message to analyze |
| `message_type` | string | No | One of: `startup_pitch`, `social_post`, `product_launch`, `cold_email`, `general` |
| `num_personas` | int | No | Number of personas to generate (2–8, default 5) |
| `context` | string | No | Where this message will be seen |
| `objective` | string | No | Desired audience response |
| `temperature` | float | No | LLM temperature (0–1, default 0.2) |

**Response:** Returns a `MeaningMapResult` object containing `personas`, `interpretations` (with `quote`, `outlier`, and `signals`), `map_points`, `pairwise_distances`, and `summary` (with structured `key_misunderstanding_risks` including `text`, `severity`, and `personas`).

### `POST /api/fix`

Generates an AI rewrite addressing a specific risk for a specific persona.

**Request:**

```json
{
  "content": "Original message text",
  "risk": "Pricing ambiguity creates hesitation",
  "persona": "Budget-Conscious Buyer"
}
```

**Response:**

```json
{
  "rewrite": "Rewritten message that addresses the risk..."
}
```

### `GET /api/history`

Returns recent analyses (requires `DATABASE_URL`).

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 20 | Max items to return (1–100) |
| `offset` | int | 0 | Pagination offset |

**Response:** `{"items": [...], "db_available": true}`

### `GET /api/history/{id}`

Returns the full result for a saved analysis by UUID.

### `GET /api/search`

Semantic search across past analyses using pgvector cosine similarity. The query is embedded via the Gradient Embeddings API and matched against stored analysis embeddings.

| Param | Type | Default | Description |
|---|---|---|---|
| `q` | string | required | Search query |
| `limit` | int | 10 | Max results (1–50) |

**Response:** `{"results": [{..., "similarity": 0.92}, ...], "db_available": true}`

### `GET /health`

Returns `{"status": "ok", "database": true|false}`.

### `GET /sample-result`

Returns the bundled demo `MeaningMapResult` JSON.
