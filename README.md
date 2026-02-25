# 🤖 AI Meeting Scheduler — Enterprise-Grade Autonomous Assistant

🌍 **Live Demo**: [ai-meeting-scheduler-xlwc.onrender.com](https://ai-meeting-scheduler-xlwc.onrender.com)  
🚀 **Live API**: [ai-meeting-scheduler-xlwc.onrender.com/docs](https://ai-meeting-scheduler-xlwc.onrender.com/docs)  
📘 **API Docs**: [Swagger UI](https://ai-meeting-scheduler-xlwc.onrender.com/docs)  
🩺 **Health Check**: [/health](https://ai-meeting-scheduler-xlwc.onrender.com/health)

A highly capable GenAI Personal Assistant designed for production environments. Built with **LangGraph**, **FastAPI**, and **APScheduler**, this agent understands natural language commands to manage your calendar, send notifications, and handle emails with enterprise-grade resilience.

---

## 🚀 Key Features

- 🧠 **Multi-Agent Orchestration**: Logic powered by **LangGraph** hooks into **Groq (LLaMA 3.3)** for ultra-fast, stateful reasoning.
- 📅 **Smart Calendar Management**: Deep integration with **Google Calendar API** for real-time scheduling and event synchronization.
- 🔔 **Resilient Notifications**: Multi-channel alerts via **WhatsApp (Twilio)** and **Email (SMTP)** with built-in diagnostic logging.
- 🕒 **Timezone-Aware**: Native support for **Asia/Kolkata** ensures your global schedule remains accurate.
- 🛠 **Tool-First Architecture**: Autonomous execution of tasks like meeting listing, conflict resolution, and automated reminders.
- 🐳 **Cloud Ready**: Optimized for platforms like **Render** and **Railway** with robust Procfile and Docker support.

---

## 🧠 Architecture

The system utilizes a cyclical reasoning graph (**LangGraph**) to handle complex scheduling flows:
1. **Analyze**: Parse intent and extract entities (time, participants).
2. **Retrieve**: Query Google Calendar and local preference memory.
3. **Synthesize**: Generate optimal slots based on user habits.
4. **Execute**: Create events and dispatch multi-channel confirmations.

---

## 🛠 Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **AI/LLM**: LangChain, LangGraph, Groq (LLaMA 3.3)
- **Automation**: APScheduler (Autonomous Reminders)
- **Integrations**: Google Calendar API (OAuth/Service Account), Twilio API (WhatsApp), SMTP
- **Infrastructure**: PostgreSQL (asyncpg), Pydantic (Settings), Render/Railway

---

## � Production Enhancements

- **Centralized Config**: A single source of truth for all secrets in `app/config.py`.
- **Cloud-Safe Auth**: Native support for environment-based Google credentials (JSON strings).
- **Graceful Lifespan**: Managed startup/shutdown for the background scheduler and DB engine.
- **Enterprise Logging**: Structured telemetry for rapid debugging of notification deliveries.

---

## 📦 Project Structure

```text
ai-meeting-scheduler/
├── app/                      # Core application package
│   ├── agents/               # LangGraph logic & state nodes
│   ├── routes/               # FastAPI endpoints (Dashboard, Chat, Scheduling)
│   ├── services/             # Core logic for Calendar, Reminders, Notifications
│   ├── tools/                # Specialized AI tool definitions
│   ├── static/ & templates/  # Glassmorphism Frontend SPA
│   ├── config.py             # Cloud-ready configuration
│   ├── database.py           # DB Connectivity & Models
│   └── main.py               # Unified entry point
├── .env.example              # Environment template
└── Procfile                  # Cloud platform instructions
```

---

## ⚙️ Deployment

### Environment Variables
Required keys for your Cloud Provider:
- `GROQ_API_KEY`: LLaMA 3.3 reasoning.
- `DATABASE_URL`: Async PostgreSQL connection string.
- `GOOGLE_CALENDAR_CREDENTIALS_JSON`: Inline JSON string for auth.
- `TWILIO_ACCOUNT_SID` & `TWILIO_AUTH_TOKEN`: For WhatsApp notifications.
- `SMTP_USERNAME` & `SMTP_PASSWORD`: For email notifications.

### Running Locally
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Unified Server
uvicorn app.main:app --reload
```

---

## � Security
- **No Secrets in Repo**: All credentials managed via environment variables.
- **Strict Gitignore**: Sensitive files like `token.json` and `.env` are strictly excluded.
- **Credential Masking**: Diagnostic logs obfuscate sensitive recipient data.

---

## � Future Roadmap
- 🎙️ Voice interface integration.
- 👥 Multi-tenant support for executive teams.
- 💬 Slack/Teams orchestration.

**Maintained by Mahadev Jagtap**
