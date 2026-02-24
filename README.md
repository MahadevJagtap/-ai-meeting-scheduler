

<!-- Frontend: http://localhost:8000/
API Docs: http://localhost:8000/docs
Health: http://localhost:8000/health

Comment
Ctrl+Alt+M
# AI Meeting Scheduler -->

Multi-agent autonomous meeting scheduling system powered by **LangGraph**, **FastAPI**, **PostgreSQL/pgvector**, **OpenAI gpt-4o**, **Google Calendar**, **Twilio**, and **SMTP**.

## Architecture

```
User Request (NL)
       │
  ┌────▼──────────┐
  │ analyze_request│  ← gpt-4o parses intent
  └────┬──────────┘
  ┌────▼───────────┐
  │retrieve_context │  ← Google Calendar + pgvector RAG
  └────┬───────────┘
  ┌────▼───────────┐
  │synthesize_slots │  ← gpt-4o ranks slots by preferences
  └────┬───────────┘     ↑ retry loop on conflicts
  ┌────▼────────────────┐
  │execute_scheduling    │  ← Creates event + sends notifications
  └────┬────────────────┘
       │
  [Email + WhatsApp confirmations]
  [APScheduler: 24h + 15min reminders]
```

## Quick Start

```bash
# 1. Clone & setup
cd pa
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt

# 2. Configure environment
copy .env.example .env
# Edit .env with your API keys

# 3. Start PostgreSQL with pgvector
# Ensure PostgreSQL is running with the pgvector extension

# 4. Run the server
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/schedule` | Schedule a meeting via NL request |
| `POST` | `/api/preferences` | Add a user preference |
| `GET` | `/api/preferences/{user_id}` | List user preferences |
| `DELETE` | `/api/preferences/{id}` | Remove a preference |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |

## Example Request

```bash
curl -X POST http://localhost:8000/api/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "request_text": "Schedule a 45-minute bug triage with alice@company.com tomorrow morning, it is urgent",
    "participants": ["alice@company.com"]
  }'
```

## Environment Variables

See [.env.example](.env.example) for all required configuration.

## Tech Stack

- **Agent Framework**: LangGraph (stateful, cyclical graph)
- **LLM**: OpenAI gpt-4o (function calling + text generation)
- **Backend**: FastAPI + Uvicorn
- **Database**: PostgreSQL + pgvector (RAG memory)
- **Calendar**: Google Calendar API v3
- **Messaging**: Twilio (WhatsApp) + aiosmtplib (Email)
- **Scheduler**: APScheduler (async autonomous reminders)
