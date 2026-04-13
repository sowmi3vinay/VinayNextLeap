You are a senior Python backend engineer. Build a clean, modular, production-quality implementation for the following system.

Tech stack:

* Python 3.11+
* FastAPI
* pandas
* Pydantic
* **Groq** for the LLM (Phase 4) — use the **Groq API** and the official **`groq`** Python SDK (or any approach Groq documents for chat completions)

General rules:

* Keep code simple, readable, and modular
* Do NOT over-engineer
* Each phase should be implemented step-by-step
* Do NOT implement everything at once
* Add comments explaining logic
* Handle edge cases properly
* Do NOT call LLM before filtering
* Limit LLM input candidates to max 30

---

## Source layout (required)

All implementation code lives under **`Source/`**, one folder per phase. **New work for a phase MUST go only in that phase’s folder** (unless a short-lived shared helper is explicitly agreed; prefer imports across phases instead of a flat `app/`).

```
Source/
  phase_1/          # Data ingestion
  phase_2/          # User preferences
  phase_3/          # Filtering & candidate selection
  phase_4/          # LLM recommendation engine
  phase_5/          # API layer (FastAPI routes, app factory)
  phase_6/          # Final integration (e.g. main entry, logging wiring)
```

* **Package names:** `phase_1`, `phase_2`, … (importable after `pip install -e .` from the repo root; packages are discovered from `Source/` via `pyproject.toml`).
* **Cross-phase imports:** e.g. `from phase_1.data_loader import load_and_process_data`, `from phase_2.models import UserPreferences`.
* **Repo root:** `config.py` uses `PROJECT_ROOT` as the parent of `Source/` (for `.env`, `data/`, etc.).
* **Future phases:** When implementing Phase *N*, add or edit files **only under `Source/phase_N/`** (plus updates to this doc if the contract changes).

Supporting folders at repo root (not tied to a single phase):

```
data/               # Local data cache / artifacts (optional)
```

---

## PHASE 1 — Data Ingestion

Goal:
Load Zomato dataset from Hugging Face and create a clean canonical schema.

Tasks:

* Use `datasets` library to load dataset
* Convert to pandas DataFrame
* Clean and normalize:

  * city → lowercase
  * cuisines → list of strings
  * rating → float
* Derive:

  * budget_tier (low, medium, high based on cost_for_two)

Output schema:
id, name, city, cuisines, rating, cost_for_two, budget_tier

Implement (under **`Source/phase_1/`**):

* `config.py` — settings (HF dataset, budget thresholds, `PROJECT_ROOT`)
* `data_loader.py` → `load_and_process_data()`
* Return pandas DataFrame

DO NOT implement API or LLM yet.

---

## PHASE 2 — User Preferences

Goal:
Define and validate user input.

Tasks:

* Create Pydantic model:

  * location
  * budget — maximum approximate **cost for two (INR)** as a positive number
  * cuisines (list optional)
  * min_rating
  * top_k (default 5, max 10)

* Normalize inputs:

  * location lowercase
  * cuisines lowercase

Implement (under **`Source/phase_2/`**):

* `models.py` → `UserPreferences` (and related enums)

---

## PHASE 3 — Filtering & Candidate Selection

Goal:
Filter dataset BEFORE LLM with smart relaxation fallback.

Tasks:

* Implement functions:
  * `filter_restaurants(df, prefs)` — strict filtering
  * `filter_with_relaxation(df, prefs)` — with smart fallback

Steps:

1. Filter by city
2. Filter by cuisines (intersection)
3. Filter by rating >= min_rating
4. Filter by budget: ``cost_for_two <=`` user's max (INR for two)

**Filter Relaxation Logic** (when no exact matches):
* Try relaxing rating by 0.5 points
* Try increasing budget by 50%
* Try removing cuisine filter
* Return relaxation info for UI display

Sort by:

* rating descending

Limit:

* max 30 candidates

Edge cases:

* If no results → try relaxed filters
* Do NOT call LLM here

Implement (under **`Source/phase_3/`**):

* `filter.py` → `filter_restaurants`, `filter_with_relaxation`, `FilterResult`

---

## PHASE 4 — LLM Recommendation Engine

**LLM provider:** **Groq** via the **Groq Cloud API**. Implementation should use Groq's documented chat/completions API and a current **Llama / Mixtral / etc.** model id as listed in [Groq's models documentation](https://console.groq.com/docs/models) (pick one stable id for the project).

**API key:** Create a **Groq API key** from the [Groq console](https://console.groq.com/) when you are ready to **implement or test Phase 4**. Store it only in environment variables or `.env` (e.g. `GROQ_API_KEY` — exact name to match `phase_4` / shared `config` when coded); **do not commit** keys. You do **not** need the key until you run code that calls Groq (Phase 4 onward).

Goal:
Rank and explain filtered restaurants with unique, personalized insights.

Tasks:

* Implement `llm.py`:
  `recommend_with_llm(candidates, prefs)`

Prompt rules:

* ONLY use given candidates

* DO NOT hallucinate new restaurants

* Return STRICT JSON:
  {
  "recommendations": [
  {"id": "...", "rank": 1, "explanation": "..."}
  ]
  }

* **Unique Explanations:** Each explanation must be distinct and personalized
  * Compare restaurants to highlight what makes each special
  * Mention specific strengths (best-rated, most affordable, perfect for dates)
  * Include vibe/atmosphere based on cost + rating combination
  * Use conversational, varied language (avoid repetitive phrases)

* **Contextual Statistics:** Include dataset statistics in prompts:
  * Average rating of candidates
  * Average cost
  * Highest rating
  * Lowest cost
  * This enables comparative explanations like "15% below average cost"

* Retry once if JSON parsing fails

* If LLM fails → fallback:

  * return top candidates with default explanation

Implement (under **`Source/phase_4/`**):

* `llm.py`

---

## PHASE 5 — API Layer (backend)

Goal:
Expose a JSON API for recommendations (**no frontend in this phase**).

Tasks:

* FastAPI **router** and **`POST /recommend`**
* Flow: validate input → load dataset (via app state / dependency) → filter candidates → call LLM → merge results

Response format (each item):

* name
* cuisines
* rating
* cost
* explanation
* **maps_url** — Google Maps search URL generated from restaurant name + city

Envelope fields: `recommendations`, `fallback`, `candidates_considered`.

**What-If Suggestions:**
* Generated when user has matching results
* Suggests alternative scenarios:
  * Higher budget → premium options
  * Lower rating → more variety
  * Different cuisine → new flavors
* Shows example restaurant names

Implement (under **`Source/phase_5/`**):

* `api.py` — router, `POST /recommend` handler, `_generate_what_if_suggestions()`
* `schemas.py` — `RecommendRequest`, `RecommendationItem`, `RecommendResponse`, `WhatIfSuggestion`, `FilterRelaxation`
* `merge.py` — join LLM output with candidate rows, generate Google Maps URLs
* `deps.py` — `get_restaurant_df` (startup-loaded or lazy)

**Runnable app:** `Source/phase_6/main.py` creates `FastAPI`, loads data in **lifespan**, and **`include_router`** from `phase_5` (see Phase 6).

**Backend tests:** `tests/test_phase5_api.py` — API tests with a **mocked** restaurant table and **mocked** `recommend_with_llm` (no Hugging Face or Groq required). Run: `pytest tests/test_phase5_api.py -v`.

---

## Frontend UI (web/)

* Static files live in **`web/`** (`index.html`, `app.js`, `styles.css`).
* **`phase_6.main`** mounts them at **`/ui/`** and redirects **`/`** → **`/ui/`** when `web/` exists.
* The page uses **`fetch("/localities")`** to fill the **locality** dropdown and **`fetch("/recommend")`** for results (same origin — no CORS setup).
* Open **`http://127.0.0.1:8000/`** or **`http://127.0.0.1:8000/ui/`** after starting Uvicorn.

### UI Features

**Design System:**
* Light theme with purple accent colors
* Card-based layout matching modern design patterns
* Food-themed background pattern (subtle emoji pattern)
* Responsive grid layout (sidebar + results)

**Preferences Panel:**
* **Locality dropdown** — Dynamic loading from dataset
* **Budget slider** — Range input (₹100 - ₹10,000) with live value display
* **Cuisine pills** — Multi-select pill buttons (Mexican, Italian, Asian, etc.)
* **Rating selector** — Pill buttons (3+, 4+, 4.5+)
* **Top K slider** — Range input (1-10 results)
* **Clear All** button for cuisines
* Purple gradient styling with hover effects

**Results Cards:**
* Colorful gradient image placeholders (rotating colors)
* Rating badge with star icon
* AI Match Score percentage
* Restaurant name + cost display
* Cuisine tags as pills
* **AI Insight** box with unique explanation
* **View on Google Maps** link

**Interactive Elements:**
* Live budget value updates while dragging slider
* Hover effects on all interactive elements
* Loading states during API calls
* Dynamic subtitle updates with selected location

**Smart Features:**
* **What-If Suggestions** — Yellow banner showing alternative options
  * "If you increase budget to ₹3000, you could explore 5 premium options"
  * Shows example restaurant names
* **Filter Relaxation Banner** — Blue banner when filters are relaxed
  * "No exact matches found. Showing results with relaxed rating (3.5+)"
  * Shows what was adjusted (rating/budget/cuisine)

---

## PHASE 6 — Final Integration

Goal:
Wire everything for a runnable service and operational basics.

Tasks:

* Ensure everything works end-to-end
* Add basic logging
* Handle empty results properly

Implement (under **`Source/phase_6/`**):

* `main.py` — FastAPI app creation, include routers from `phase_5`, lifespan / startup hooks if needed
* Optional: `logging_config.py` or similar

---

## Deployment

### Backend Deployment (Streamlit Cloud)

**Why Streamlit:**
* Simple Python deployment without managing servers
* Built-in UI capabilities for demo and debugging
* Free tier available
* Easy way to expose the recommendation workflow

**Required files:**

1. **`app.py`** at repo root:
   * This is the actual Streamlit Cloud entry file
   * It imports the recommendation pipeline from the `app/phase_*` packages
   * It provides a Streamlit-native UI for recommendations

2. **`requirements-streamlit.txt`**:
   * Include `streamlit`, `fastapi`, `uvicorn`, `groq`, and dataset dependencies

3. **Environment variables / secrets:**
   * Set `HF_TOKEN` in Streamlit secrets if needed
   * Set `GROQ_API_KEY` in Streamlit secrets
   * Optional: set `ALLOWED_ORIGINS` and `VERCEL_ORIGIN_REGEX`

**Deploy to Streamlit Cloud:**
1. Push code to GitHub
2. Connect repo to [share.streamlit.io](https://share.streamlit.io)
3. Use **main file path: `app.py`**
4. Add secrets in the Streamlit dashboard
5. Deploy

### Frontend Deployment (Vercel)

**Why Vercel:**
* Free static site hosting
* Automatic HTTPS
* Global CDN
* Easy GitHub integration

**Changes Required:**

1. **Create `vercel.json`** at repo root:
   * Configure build settings
   * Set output directory to `web/`
   * Configure API rewrites to Streamlit backend

2. **Update `web/app.js`**:
   * Change API base URL to Streamlit backend URL
   * Use environment variable for API endpoint
   * Add CORS handling if needed

3. **Create `.env.production`**:
   * `VITE_API_URL=https://your-streamlit-app.streamlit.app`

**Deploy to Vercel:**
1. Push code to GitHub
2. Import project on [vercel.com](https://vercel.com)
3. Set environment variables
4. Deploy

### Architecture Changes

**Backend (`app/phase_6/main.py`):**
* FastAPI app with CORS middleware for frontend deployment
* Regex-based support for Vercel preview/production domains
* Static UI mounted at `/ui/` for local development

**Streamlit entry (`app.py`):**
* Root-level Streamlit app for Streamlit Cloud deployment
* Reuses the same filtering, LLM ranking, merge, what-if, and relaxation pipeline

**Frontend (`web/app.js`):**
* Configurable API base URL
* Fallback for local development
* Error handling for cross-origin requests

---

## Run / install

From the **repository root**:

```bash
pip install -e .
python -m phase_1.data_loader
```

**API server + basic UI (after Phase 5–6):**

```bash
uvicorn phase_6.main:app --reload --host 127.0.0.1 --port 8000
```

Then browse **`http://127.0.0.1:8000/`** (tester UI) or **`http://127.0.0.1:8000/docs`** (Swagger).

**If the browser says “This site can’t be reached” / connection refused:**

1. **Start the server** from the **repository root** (the folder that contains `Source/` and `web/`), after `pip install -e .`:
   `uvicorn phase_6.main:app --host 127.0.0.1 --port 8000`
   (add `--reload` while developing). Leave that terminal **open**; stopping it closes the site.
2. Use **`http://`** not `https://`, and the exact host/port shown in the Uvicorn log (default **8000**).
3. **Do not** open `web/index.html` as a file from Explorer — `fetch("/recommend")` only works when the page is served by this app (**`http://127.0.0.1:8000/ui/`**).
4. The **first** “Get recommendations” may take **several minutes** while the Hugging Face dataset downloads; the home page itself should load as soon as Uvicorn starts.

**Phase 5 API tests (mocked, no network):**

```bash
pip install -e ".[dev]"
pytest tests/test_phase5_api.py -v
```

Use `requirements.txt` for a non-editable install is optional; `pyproject.toml` lists runtime dependencies for `pip install -e .`.

---

Now start with ONLY Phase 1.
Generate code for:

* `Source/phase_1/data_loader.py`
* `Source/phase_1/config.py`

Do not proceed further.
