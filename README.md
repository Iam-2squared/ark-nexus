# ARK Nexus — Local-first Multi-AI Hub

**V1 engineering scaffold. Not a production provider integration.** Independent from Iam-2squared/ark-ai.

V1 accepts **synthetic-v1 fixtures only** for ChatGPT and Claude. It does not read your real chats, poll accounts, or dispatch tasks to other AIs. Real export importers require owner-authorized redacted samples and a separate security review.

## Windows quickstart
Requires Python 3.12 and (later, for dashboard) Node.js 22+.

    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -e ".[dev]"
    python -m pytest -q
    python -m uvicorn nexus.api:app --host 127.0.0.1 --port 8788

Health: http://127.0.0.1:8788/api/v1/health

## Scope / gates
- Local FastAPI + SQLite and FTS5 indexed records with provenance and manual project mapping
- Import a JSON fixture carrying nexus_fixture=synthetic-v1 and provider=chatgpt or claude
- Duplicate detection, identity conflict rollback, bounded ZIP extraction, offline search
- No API keys, live sync, browser cookie scraping, or external instruction sending
- Source data stored outside repo (NEXUS_DATA_DIR env override)
- **V1 not PASS** until redacted real-format import, security review and coverage evidence have passed

Public repo: do **not** commit actual conversation archives, credentials, or databases.
