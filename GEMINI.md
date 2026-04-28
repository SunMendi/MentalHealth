# GEMINI.md - AI Mental Health Support System

## Project Overview
This is a specialized AI-driven mental health support platform designed to provide 24/7 guided emotional assistance. It is built as a **Guided Chat System** rather than a general-purpose chatbot, focusing on structured clinical frameworks like CBT and DBT.

### Core Technologies
- **Backend:** Django 6.0+, Django REST Framework (DRF)
- **Database:** PostgreSQL
- **Authentication:** JWT (SimpleJWT)
- **AI/LLM:** Integrated via an orchestrator for intent classification, risk detection, and response generation.
- **Voice:** Groq Whisper (STT) and Edge TTS (planned).

## Project Structure
- `core/`: Django project root.
    - `core/`: Main configuration (settings, URLs, ASGI/WSGI).
    - `users/`: Custom user management including emergency contact features.
    - `chat/`: Core engine for sessions, messages, and the mental health "brain."
- `.venv/`: Python virtual environment.
- `AGENTS.md`: Detailed design document and roadmap.

## Building and Running
### Prerequisites
- Python 3.12+
- PostgreSQL
- `.env` file with `DB_NAME`, `DB_USER`, `DB_PASS`, etc.

### Commands
- **Install Dependencies:** `pip install -r requirements.txt` (or manually install via `.venv`)
- **Run Migrations:** `python core/manage.py migrate`
- **Start Server:** `python core/manage.py runserver`
- **Create Superuser:** `python core/manage.py createsuperuser`

## Architectural Mandates
1. **Safety First:** Any mention of self-harm or suicide MUST trigger a deterministic "Crisis Mode" response, bypassing normal LLM generation.
2. **Guided Routing:** User inputs are processed through a "Mental Health Router" that classifies intent and risk before selecting a specific flow (CBT, DBT, Panic, etc.).
3. **Structured RAG:** Retrieval Augmented Generation is used for clinical protocols and localized scripts, NOT for safety-critical logic.
4. **Context Integrity:** Maintain chat sessions with clear sender types (`user` vs `assistant`).

## Development Conventions
- **Surgical Updates:** When modifying models or views, ensure existing session/message logic is preserved.
- **Validation:** Always verify API responses for `user_message` and `assistant_message` pairs in chat endpoints.
- **Modularity:** Keep the "Brain" logic (intent/risk detection) decoupled from the database services in `core/chat/services.py`.

## Roadmap (MVP)
- **Phase 1:** Auth and basic chat API (Complete).
- **Phase 2:** Chat brain implementation (Risk + Intent detection).
- **Phase 3:** RAG integration and Voice flow.
- **Phase 4:** 7-day support plans and anonymous community features.
