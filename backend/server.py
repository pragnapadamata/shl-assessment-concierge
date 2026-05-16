"""SHL Conversational Assessment Recommender — FastAPI service.

Assignment compliance:
  GET  /health  → {"status": "ok"} HTTP 200
  POST /chat    → stateless, full history, strict schema
  Schema: reply(str), recommendations([] or 1-10 items), end_of_conversation(bool)
  Behaviors: clarify, recommend, refine, compare, refuse
  Catalog-only URLs, anti-hallucination grounding, 8-turn cap, 30s timeout
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import List, Literal

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from retriever import CatalogRetriever

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("shl-agent")

# ── LLM configuration ────────────────────────────────────────────────────────
# Priority: Groq (fastest) → OpenRouter → Gemini → OpenAI
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY     = os.environ.get("OPENAI_API_KEY", "")


def _make_client():
    from openai import AsyncOpenAI
    if GROQ_API_KEY:
        logger.info("LLM: Groq / llama-3.3-70b-versatile")
        return AsyncOpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        ), "llama-3.3-70b-versatile"
    if OPENROUTER_API_KEY:
        logger.info("LLM: OpenRouter / deepseek/deepseek-v4-flash:free")
        return AsyncOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://shl-assessment-concierge.onrender.com",
                "X-Title": "SHL Assessment Concierge",
            },
        ), "deepseek/deepseek-v4-flash:free"
    if GEMINI_API_KEY:
        logger.info("LLM: Gemini / gemini-2.0-flash")
        return AsyncOpenAI(
            api_key=GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        ), "gemini-2.0-flash"
    if OPENAI_API_KEY:
        logger.info("LLM: OpenAI / gpt-4o-mini")
        return AsyncOpenAI(api_key=OPENAI_API_KEY), "gpt-4o-mini"
    return None, None


_client, _model = _make_client()

MAX_TURNS   = 8
MAX_RECS    = 10
RETRIEVAL_K = 20

# ── Catalog ───────────────────────────────────────────────────────────────────
retriever = CatalogRetriever()
logger.info("Catalog loaded: %d assessments", len(retriever.catalog))

# ── Pydantic schemas — non-negotiable per assignment ─────────────────────────
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)

class ChatResponse(BaseModel):
    reply: str
    recommendations: List[Recommendation] = Field(default_factory=list)
    end_of_conversation: bool = False

class HealthResponse(BaseModel):
    status: str

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an SHL Assessment Recommender Agent.
Your job is to help users select appropriate SHL assessments through conversation.

STRICT OUTPUT FORMAT — return ONLY this JSON, nothing else:
{
  "reply": "string",
  "recommendations": [{"name": "string", "url": "string", "test_type": "K|P|A|S|J"}],
  "end_of_conversation": false
}

HARD RULES:
1. Output ONLY the JSON object. No text before or after it. No markdown fences.
2. Every name and url must be copied VERBATIM from CATALOG CANDIDATES. Never invent.
3. recommendations = [] when clarifying, comparing, or refusing.
4. recommendations = 1-10 items when recommending.
5. Each recommendation has ONLY: name, url, test_type.
6. end_of_conversation = true ONLY when user confirms satisfaction.
7. end_of_conversation = false for refusals, clarifications, comparisons.

BEHAVIOR DECISION TREE:

STEP 1 — Is the query vague? (missing role OR seniority OR skill area)
  YES → CLARIFY: ask ONE specific question, recommendations=[]
  NO  → go to STEP 2

STEP 2 — Is user asking to compare assessments?
  YES → COMPARE: explain using catalog data only, recommendations=[]
  NO  → go to STEP 3

STEP 3 — Is user asking something outside SHL assessments?
  YES → REFUSE: "I can only help with SHL assessments.", recommendations=[]
  NO  → go to STEP 4

STEP 4 — Is user refining/changing previous recommendations?
  YES → REFINE: update shortlist, keep qualifying items, add new fits
  NO  → RECOMMEND: provide 1-10 assessments from CATALOG CANDIDATES

CLARIFY rules:
- Ask max 1 question per turn, max 2 questions total in a conversation
- After 2 clarifying turns, ALWAYS recommend regardless of remaining gaps
- Good questions: "What seniority level?", "Selection or development?", "What skills to measure?"

RECOMMEND rules:
- Job description pasted = full context → recommend immediately, no clarification
- Stack by role: Technical=knowledge+cognitive+OPQ; Leadership=OPQ32r+Leadership Report; Graduate=ability+SJT+personality; Contact centre=SVAR+simulation+behavioral
- Write one sentence per item in reply explaining the fit

REFINE rules:
- Triggers: "add", "remove", "also", "actually", "instead", "drop", "only", "under X min"
- Keep items that still qualify, swap those that don't, add new fits
- Never restart the conversation

END rules:
- Set end_of_conversation=true when user says: "perfect", "that works", "confirmed", "thanks", "good"
- Repeat the final shortlist in the closing turn

TEST TYPES: K=Knowledge/Skills | P=Personality/Behavior | A=Ability/Aptitude | S=Simulation | J=Situational Judgment/Biodata"""

# ── Helpers ───────────────────────────────────────────────────────────────────
_JSON_RE = re.compile(r"\{[\s\S]*?\}", re.DOTALL)
_JSON_FULL = re.compile(r"\{[\s\S]*\}", re.DOTALL)


def _build_query(conv: List[ChatMessage]) -> str:
    return " ".join(m.content for m in conv if m.role == "user")


def _format_candidates(cands: List[dict]) -> str:
    lines = []
    for i, c in enumerate(cands, 1):
        lines.append(
            f"[{i}] name: {c['name']}\n"
            f"    url: {c.get('url', '')}\n"
            f"    test_type: {c.get('test_type', 'K')}\n"
            f"    duration: {c.get('duration') or 'n/a'} | remote: {c.get('remote') or 'n/a'}\n"
            f"    job_levels: {', '.join(c.get('job_levels') or []) or 'n/a'}\n"
            f"    keys: {', '.join(c.get('keys') or []) or 'n/a'}\n"
            f"    description: {(c.get('description') or '')[:180]}"
        )
    return "\n\n".join(lines)


def _parse(text: str) -> dict:
    if not text:
        raise ValueError("empty LLM response")
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    # Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # Extract JSON object
    m = _JSON_FULL.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    raise ValueError(f"Cannot parse JSON from: {text[:300]}")


def _ground(raw: List[dict]) -> List[Recommendation]:
    """Verify every rec against catalog. Drop hallucinations. Dedupe. Cap at 10."""
    out: List[Recommendation] = []
    seen: set[str] = set()
    for r in (raw or []):
        if not isinstance(r, dict):
            continue
        name = r.get("name", "")
        if not isinstance(name, str) or not name.strip():
            continue
        item = retriever.get_by_name(name)
        if not item or not item.get("url"):
            logger.warning("Hallucination dropped: %r", name)
            continue
        key = item["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(Recommendation(
            name=item["name"],
            url=item["url"],
            test_type=item.get("test_type", "K"),
        ))
        if len(out) >= MAX_RECS:
            break
    return out


async def _call_llm(conv: List[ChatMessage], candidates: List[dict]) -> dict:
    if not _client:
        raise HTTPException(
            status_code=500,
            detail="No LLM API key configured. Set GROQ_API_KEY or OPENROUTER_API_KEY in .env"
        )

    turn = len(conv)
    remaining = MAX_TURNS - turn
    history = "\n".join(f"{m.role.upper()}: {m.content}" for m in conv[:-1]) or "(first turn)"
    catalog = _format_candidates(candidates) if candidates else "(no matches — ask clarifying question)"

    prompt = (
        f"TURN {turn}/{MAX_TURNS} (remaining: {remaining})\n\n"
        "CONVERSATION SO FAR:\n"
        f"{history}\n\n"
        "CATALOG CANDIDATES (ONLY use these exact names and URLs):\n"
        f"{catalog}\n\n"
        "CURRENT USER MESSAGE:\n"
        f"{conv[-1].content}\n\n"
        "Rules for this turn:\n"
        "- Turn 1 vague query → clarify, recommendations=[]\n"
        "- Enough context → recommend 1-10 items from catalog\n"
        "- remaining<=2 → MUST recommend even if incomplete\n"
        "- User confirms → end_of_conversation=true, repeat shortlist\n"
        "Output ONE JSON object only. No other text."
    )

    try:
        resp = await asyncio.wait_for(
            _client.chat.completions.create(
                model=_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1200,
            ),
            timeout=25.0  # 25s hard limit — leaves 5s buffer for the 30s evaluator cap
        )
        text = resp.choices[0].message.content or ""
        logger.info("LLM (%s) reply: %s", _model, text[:200])
        return _parse(text)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="LLM timed out (>25s)")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")


# ── Core handler ──────────────────────────────────────────────────────────────
async def _handle_chat(req: ChatRequest) -> ChatResponse:
    conv = req.messages or []

    if not conv:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    if conv[-1].role != "user":
        raise HTTPException(status_code=400, detail="Last message must be role='user'")
    if len(conv) > MAX_TURNS:
        raise HTTPException(status_code=400, detail=f"Exceeds {MAX_TURNS}-turn cap")

    query      = _build_query(conv)
    candidates = retriever.search(query, k=RETRIEVAL_K) if query else []
    logger.info("Turn %d/%d | %d candidates | %s", len(conv), MAX_TURNS, len(candidates), query[:60])

    raw      = await _call_llm(conv, candidates)
    reply    = str(raw.get("reply") or "").strip()
    end_flag = bool(raw.get("end_of_conversation", False))
    grounded = _ground(raw.get("recommendations") or [])

    if not reply:
        reply = "Could you tell me more about the role and what you want to measure?"

    # Guardrail: no recs → end must be false (refusals/clarifications don't end conversation)
    if not grounded:
        end_flag = False

    # Guardrail: force recs at turn cap so conversation always ends with a shortlist
    if not grounded and len(conv) >= MAX_TURNS - 1 and candidates:
        logger.warning("Forcing recs at turn cap")
        grounded = _ground([{"name": c["name"]} for c in candidates[:5]])

    # Auto-end at cap
    if len(conv) >= MAX_TURNS - 1:
        end_flag = True

    return ChatResponse(reply=reply, recommendations=grounded, end_of_conversation=end_flag)


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="SHL Assessment Concierge",
    description="Conversational SHL assessment recommender — SHL Labs AI Intern Assignment",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Readiness probe — returns HTTP 200 with {"status": "ok"}"""
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Stateless conversational recommender. Full history sent each call."""
    return await _handle_chat(req)


@app.get("/")
async def root():
    return {
        "service": "SHL Assessment Concierge",
        "model": _model or "not configured",
        "catalog_size": len(retriever.catalog),
        "endpoints": ["/health", "/chat"],
    }


# /api prefix — for frontend proxy compatibility
api_router = APIRouter(prefix="/api")

@api_router.get("/health", response_model=HealthResponse)
async def health_api():
    return HealthResponse(status="ok")

@api_router.post("/chat", response_model=ChatResponse)
async def chat_api(req: ChatRequest):
    return await _handle_chat(req)

@api_router.get("/")
async def root_api():
    return {"service": "SHL Assessment Concierge", "model": _model, "catalog_size": len(retriever.catalog)}

app.include_router(api_router)
