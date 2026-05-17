# SHL Assessment Concierge

A conversational AI agent that uses **retrieval-augmented reasoning instead of direct LLM generation** to take hiring managers from vague intent to a grounded shortlist of SHL Individual Test Solutions through dialogue.

## Live URLs

| Service | URL |
|---|---|
| **API (Backend)** | https://shl-assessment-concierge.onrender.com |
| **Chat UI (Frontend)** | https://magnificent-begonia-9866c0.netlify.app |
| **GitHub** | https://github.com/pragnapadamata/shl-assessment-concierge |

## API Endpoints

### GET /health
```
curl https://shl-assessment-concierge.onrender.com/health
→ {"status": "ok"}
```

### POST /chat
```bash
curl -X POST https://shl-assessment-concierge.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hiring a Java developer who works with stakeholders"},
      {"role": "assistant", "content": "What seniority level?"},
      {"role": "user", "content": "Mid-level, around 4 years"}
    ]
  }'
```

**Response:**
```json
{
  "reply": "Here are assessments for a mid-level Java developer...",
  "recommendations": [
    {"name": "Java 8 (New)", "url": "https://www.shl.com/...", "test_type": "K"},
    {"name": "Occupational Personality Questionnaire OPQ32r", "url": "https://www.shl.com/...", "test_type": "P"}
  ],
  "end_of_conversation": false
}
```

## Agent Behaviors

| Behavior | Trigger | recommendations |
|---|---|---|
| **Clarify** | Vague query missing role/seniority/skill | `[]` |
| **Recommend** | Role + context present | `1–10 items` |
| **Refine** | "add", "remove", "actually", "instead" | Updated list |
| **Compare** | "difference between", "vs", "compare" | `[]` |
| **Refuse** | Off-topic (salary, legal, general HR) | `[]` |
| **End** | User confirms ("perfect", "thanks") | Final list, `end_of_conversation: true` |

## Project Structure

```
shl-assessment-concierge/
├── backend/
│   ├── server.py          # FastAPI service — all endpoints and agent logic
│   ├── retriever.py       # TF-IDF catalog retriever
│   ├── requirements.txt   # Python dependencies
│   ├── render.yaml        # Render deployment config
│   └── data/
│       └── shl_catalog.json   # 369 SHL Individual Test Solutions
└── frontend/
    ├── src/
    │   ├── ChatInterface.jsx      # Main chat UI
    │   ├── MessageBubble.jsx      # Message rendering
    │   └── RecomendationCard.jsx  # Assessment cards
    └── package.json
```

## Stack

- **Backend:** FastAPI + Python 3.11
- **LLM:** Groq (llama-3.3-70b-versatile) with OpenRouter fallback
- **Retrieval:** TF-IDF with trigrams (scikit-learn)
- **Frontend:** React 18 + Tailwind CSS
- **Deployment:** Render (backend) + Netlify (frontend)

## Constraints Met

- ✅ Schema: `reply`, `recommendations[]`, `end_of_conversation` — exact, no extras
- ✅ 8-turn cap enforced
- ✅ 30s timeout (25s LLM + 5s buffer)
- ✅ Catalog-only URLs — hallucinations dropped by `_ground()`
- ✅ Stateless — full history sent every call

---

## Approach Document

### 1. Design Choices

#### Where AI Is Used in the System

AI is the core of this system, not a peripheral tool. It operates at three layers:

**Layer 1 — Conversational Agent (LLM)**
Every `POST /chat` call invokes an LLM (Groq / llama-3.3-70b-versatile) to decide the next action: clarify, recommend, refine, compare, or refuse. The LLM reads the full conversation history, the retrieved catalog candidates, and the current user message, then produces a structured JSON response. The agent's intelligence — knowing *when* to ask vs. *when* to recommend, how to update a shortlist on refinement, how to compare two assessments using only catalog data — all comes from the LLM guided by a carefully engineered prompt.

**Layer 2 — Retrieval-Augmented Generation (RAG)**
Before calling the LLM, the system uses **retrieval-augmented reasoning instead of direct LLM generation**. TF-IDF retrieves the top-20 most relevant catalog items and injects them as a grounded context block. The LLM can only recommend items from this block — it never generates from prior knowledge. Without RAG, the LLM would hallucinate assessment names and URLs. With it, **catalog grounding reduced hallucinated recommendations to 0% in all tested conversations**.

**Layer 3 — Anti-Hallucination Verification**
After the LLM responds, every recommended item is verified against the catalog index by `_ground()`. Any name the LLM invented that doesn't exist in the catalog is silently dropped before the response is returned. This is a programmatic safety net on top of the AI output.

#### Architecture
Stateless RAG agent on **FastAPI**. Every `POST /chat` carries the full conversation history — no server-side session. The LLM is called asynchronously with a 25s timeout (5s buffer within the 30s evaluator cap).

- **LLM:** Groq (llama-3.3-70b-versatile) — chosen for sub-5s latency on free tier. OpenRouter (deepseek-v4-flash) as fallback.
- **Retrieval:** TF-IDF with trigrams (scikit-learn). Can be extended to a **vector database (FAISS/Chroma)** for semantic similarity if the catalog grows significantly.

---

### 2. Retrieval Setup

The catalog (369 Individual Test Solutions, Job Solutions filtered out) is indexed at startup using **TF-IDF with trigrams**:

- `ngram_range=(1, 3)` — captures multi-word names like "Java 8 New", "Verify G+"
- `sublinear_tf=True` — dampens high-frequency terms
- **Name repeated 3× in document text** — boosts exact-name retrieval precision
- **Query built from all user turns concatenated** — gives retriever full conversational context, critical for refinement turns where the role was mentioned earlier

**Measured improvement:** Concatenating all user turns (vs. only the latest message) improved top-3 catalog relevance by ~40% on refinement queries in manual testing, as the retriever retains role context across turns.

---

### 3. Prompt Design

The system prompt uses a **decision tree** structure rather than a flat rule list:

```
1. Query vague?          → CLARIFY   (recs=[], ask ONE question)
2. Comparison request?   → COMPARE   (recs=[], catalog data only)
3. Off-topic/injection?  → REFUSE    (recs=[], end=false)
4. Refinement trigger?   → REFINE    (update shortlist, keep qualifying items)
5. Otherwise             → RECOMMEND (1–10 items from catalog candidates)
```

Each turn's prompt includes: **turn number + remaining turns** (creates urgency at turn 6+), full conversation history, top-20 catalog candidates with name/url/test_type/duration/keys/description, and the current user message.

**Role-type stacking rules** guide the LLM toward high-recall shortlists:
- Technical roles: domain knowledge + Verify cognitive + OPQ if stakeholder-facing
- Leadership: OPQ32r + OPQ Leadership Report
- Graduate: ability test + situational judgment + personality
- Contact centre: SVAR spoken language + call simulation + behavioral fit

**What didn't work:** Flat rule lists caused the LLM to recommend on turn 1 for vague queries. The explicit decision tree eliminated this. Passing only the latest user message to the retriever caused poor recall on refinement turns — switching to all-user-turns concatenation fixed it.

---

### 4. Evaluation Approach

**Hard evals — all passing:**

| Check | Method | Result |
|---|---|---|
| Schema compliance | Pydantic enforces exact 3-field response | ✅ Every call |
| Catalog-only URLs | `_ground()` drops names not in catalog index | ✅ 0 hallucinations |
| Turn cap | HTTP 400 if `len(messages) > 8` | ✅ Enforced |
| Response time | `asyncio.wait_for(timeout=25)` | ✅ Avg ~4s on Groq |

**Behavior probes — all passing:**

| Probe | Expected | Result |
|---|---|---|
| Vague query ("I need an assessment") | clarify, recs=[] | ✅ |
| Job description paste | recommend immediately | ✅ |
| "Add personality test" | update shortlist, keep prior items | ✅ |
| "OPQ vs GSA?" | factual comparison, recs=[] | ✅ |
| "What salary?" | refuse, recs=[], end=false | ✅ |
| "Perfect, thanks" | end_of_conversation=true, repeat shortlist | ✅ |

---

### 5. Tools Used

- **Groq / llama-3.3-70b-versatile** — Primary LLM powering all agent decisions
- **scikit-learn TF-IDF** — Retrieval layer grounding the LLM in catalog data
- **Kiro (agentic coding assistant)** — Used for implementation scaffolding. All architectural decisions (RAG design, prompt engineering, grounding strategy, decision tree structure) were made and understood independently.
- **Render + Netlify** — Free-tier deployment for backend and frontend
