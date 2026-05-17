# Approach Document — SHL Assessment Concierge

## 1. Design Choices

### Architecture
The system is a stateless RAG (Retrieval-Augmented Generation) agent built on FastAPI. Every POST /chat call receives the full conversation history — no server-side session state. This makes the service horizontally scalable and robust against cold starts on free-tier hosting.

**LLM:** Groq (llama-3.3-70b-versatile) as primary — chosen for sub-5s response times on free tier, well within the 30s evaluator cap. OpenRouter (deepseek-v4-flash) as fallback. The client is configured as AsyncOpenAI with a 25s asyncio timeout, leaving a 5s buffer.

**Retrieval:** TF-IDF with trigrams (scikit-learn). The catalog name is repeated 3× in the document text to boost exact-name match scores. Threshold set at 0.01 to avoid dropping valid low-frequency terms. Top-20 candidates are passed to the LLM as a grounded context block.

**Anti-hallucination:** Every LLM-emitted recommendation is verified against the catalog via `_ground()`. Names are matched exactly, then by substring. Any item not found in the catalog is silently dropped before the response is returned. URLs are never constructed — only copied verbatim from catalog entries.

### Schema Compliance
Pydantic models enforce the exact three-field response schema (`reply`, `recommendations`, `end_of_conversation`) at the serialization layer. The LLM is instructed to output only a JSON object — markdown fences and extra text are stripped by `_parse()` before deserialization.

## 2. Retrieval Setup

The catalog (369 Individual Test Solutions, pre-packaged Job Solutions filtered out) is indexed at startup using TF-IDF with:
- `ngram_range=(1, 3)` — captures multi-word names like "Java 8 New", "Verify G+"
- `sublinear_tf=True` — dampens high-frequency terms
- `max_features=30000` — covers the full vocabulary
- Name repeated 3× in document text — boosts exact-name retrieval

Query is built from all user turns concatenated, giving the retriever full conversational context rather than just the latest message. This significantly improves recall on refinement turns where the user references a role mentioned earlier.

## 3. Prompt Design

The system prompt uses a **decision tree** structure rather than a flat list of rules:

1. Is the query vague? → CLARIFY (max 2 questions, then commit)
2. Is it a comparison request? → COMPARE (catalog data only, recs=[])
3. Is it off-topic? → REFUSE
4. Is it a refinement? → REFINE (keep qualifying items)
5. Otherwise → RECOMMEND (1–10 items)

Each turn's user prompt includes: turn number, remaining turns, full conversation history, top-20 catalog candidates with name/url/test_type/duration/keys/description, and the current user message. The turn counter creates urgency — at remaining≤2, the agent is instructed to commit to recommendations regardless of remaining gaps.

**What didn't work:** Flat rule lists caused the LLM to occasionally recommend on turn 1 for vague queries. The decision tree structure with explicit YES/NO branching eliminated this. Also, passing only the latest user message to the retriever caused poor recall on refinement turns — switching to all-user-turns concatenation fixed it.

## 4. Evaluation Approach

**Hard evals verified:**
- Schema compliance: Pydantic enforces exact fields on every response
- Catalog-only items: `_ground()` drops any name not in `retriever.by_name`
- Turn cap: HTTP 400 returned if `len(messages) > 8`
- Response time: asyncio.wait_for(timeout=25) ensures sub-30s responses

**Behavior probes tested manually:**
- Vague query ("I need an assessment") → clarifies, recs=[]
- JD paste → recommends immediately without clarification
- "Add personality test" → updates shortlist, keeps prior items
- "OPQ vs GSA?" → factual comparison, recs=[]
- "What salary?" → refuses, recs=[], end=false
- "Perfect, thanks" → end_of_conversation=true, repeats shortlist

**Recall@10 strategy:** Retrieval returns top-20 candidates; LLM selects the most relevant 1–10. Role-type stacking rules in the prompt (technical=knowledge+cognitive+OPQ; leadership=OPQ32r+report; graduate=ability+SJT+personality) improve coverage of the expected shortlist across diverse personas.

## 5. Tools Used

- **Kiro (agentic coding):** Used for rapid iteration on server.py, retriever.py, and frontend components. All design decisions — retrieval strategy, prompt structure, grounding logic — were made and can be defended independently.
- **scikit-learn:** TF-IDF retrieval implementation.
- **Groq free tier:** Primary LLM — llama-3.3-70b-versatile, chosen for speed and JSON adherence.
- **Render + Netlify:** Free-tier deployment for backend and frontend respectively.
