# SHL Assessment Concierge

A conversational AI agent that takes hiring managers from vague intent to a grounded shortlist of SHL Individual Test Solutions through dialogue.

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
    │   ├── ChatInterface.jsx   # Main chat UI
    │   ├── MessageBubble.jsx   # Message rendering
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
