# Approach Document — SHL Assessment Concierge

## 1. Design Choices

### Where AI Is Used in the System

AI is the core of this system, not a peripheral tool. It is used in three places:

**1. The conversational agent (LLM):** Every POST /chat call invokes an LLM (Groq / llama-3.3-70b-versatile) to decide what to do next — clarify, recommend, refine, compare, or refuse. The LLM reads the full conversation history, the retrieved catalog candidates, and the current user message, then produces a structured JSON response. The agent's intelligence — knowing when to ask vs. when to recommend, how to update a shortlist on refinement, how to compare two assessments using only catalog data — all comes from the LLM guided by a carefully engineered prompt.

**2. Retrieval-Augmented Generation (RAG):** Before calling the LLM, the system retrieves the top-20 most relevant catalog items using TF-IDF similarity. This grounds the LLM — it can only recommend items from the retrieved block. Without this retrieval step, the LLM would hallucinate assessment names and URLs. The combination of retrieval + LLM is the core AI architecture of the system.

**3. Anti-hallucination grounding layer:** After the LLM responds, every recommended item is verified against the catalog by the `_ground()` function. Any name the LLM invented that doesn't exist in the catalog is silently dropped. This is a programmatic safety layer on top of the AI output.

### Architecture
Stateless RAG agent on FastAPI. Every POST /chat carries the full conversation history — no server-side session. The LLM is called asynchronously with a 25s timeout (5s buffer within the 30s evaluator cap).

**LLM:** Groq (llama-3.3-70b-versatile) — chosen for sub-5s latency on free tier. OpenRouter (deepseek-v4-flash) as fallback. Both accessed via the OpenAI-compatible SDK.

**Retrieval:** TF-IDF with trigrams (scikit-learn). Catalog name repeated 3× in document text to boost exact-name match scores. Top-20 candidates passed to LLM as grounded context.

## 2. Retrieval Setup

The catalog (369 Individual Test Solutions, Job Solutions filtered out) is indexed at startup:
- `ngram_range=(1, 3)` — captures multi-word names like "Java 8 New", "Verify G+"
- `sublinear_tf=True` — dampens high-frequency terms
- Name repeated 3× — boosts exact-name retrieval precision
- Query built from all user turns concatenated — gives retriever full conversational context, critical for refinement turns where the role was mentioned earlier

## 3. Prompt Design

The system prompt uses a **decision tree** structure:

1. Query vague (missing role/seniority/skill)? → CLARIFY — ask ONE question, recs=[]
2. Comparison request? → COMPARE — catalog data only, recs=[]
3. Off-topic? → REFUSE — recs=[], end=false
4. Refinement? → REFINE — update shortlist, keep qualifying items
5. Otherwise → RECOMMEND — 1–10 items from catalog candidates

Each turn's prompt includes: turn number + remaining turns (creates urgency at turn 6+), full conversation history, top-20 catalog candidates with name/url/test_type/duration/keys/description, and the current user message.

Role-type stacking rules guide the LLM toward high-recall shortlists:
- Technical roles: domain knowledge + Verify cognitive + OPQ if stakeholder-facing
- Leadership: OPQ32r + OPQ Leadership Report
- Graduate: ability test + situational judgment + personality
- Contact centre: SVAR spoken language + call simulation + behavioral fit

**What didn't work:** Flat rule lists caused the LLM to recommend on turn 1 for vague queries. The explicit decision tree eliminated this. Passing only the latest user message to the retriever caused poor recall on refinement turns — switching to all-user-turns concatenation fixed it.

## 4. Evaluation Approach

**Hard evals verified:**
- Schema: Pydantic enforces exact three-field response on every call
- Catalog-only: `_ground()` drops any name not in the catalog index
- Turn cap: HTTP 400 if `len(messages) > 8`
- Timeout: `asyncio.wait_for(timeout=25)` ensures sub-30s responses

**Behavior probes tested:**
- Vague query → clarifies, recs=[] ✅
- Job description paste → recommends immediately ✅
- "Add personality test" → updates shortlist, keeps prior items ✅
- "OPQ vs GSA?" → factual comparison, recs=[] ✅
- "What salary?" → refuses, recs=[], end=false ✅
- "Perfect, thanks" → end_of_conversation=true, repeats shortlist ✅

## 5. Tools Used

- **Groq (llama-3.3-70b-versatile):** Primary LLM powering all agent decisions — clarification, recommendation, refinement, comparison, refusal
- **scikit-learn TF-IDF:** Retrieval layer that grounds the LLM in catalog data
- **Kiro (agentic coding assistant):** Used for implementation — scaffolding FastAPI routes, React components, and iterating on the prompt. All architectural decisions were made and understood independently.
- **Render + Netlify:** Free-tier deployment for backend and frontend
