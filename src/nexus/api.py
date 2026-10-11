"""Nexus V1 local API. No external APIs, task dispatch, or consumer-chat automation."""

import hashlib
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from nexus import __version__
from nexus.importers import (
    MAX_UPLOAD_BYTES,
    PARSER_VERSION,
    ImportProblem,
    load_synthetic,
    safe_json_payload,
    validate_account_alias,
)
from nexus.settings import database_path
from nexus.store import Store


class NewProject(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    repo_url: str | None = Field(default=None, max_length=500)


class SetProject(BaseModel):
    project_id: str | None = None


def create_app(path: Path | None = None) -> FastAPI:
    app = FastAPI(title="ARK Nexus Local API", version=__version__)
    app.state.store = Store(path or database_path())

    @app.middleware("http")
    async def same_origin_write(request: Request, call_next):
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            origin = request.headers.get("origin")
            allowed = {
                "http://127.0.0.1:8788", "http://localhost:8788",
                "http://127.0.0.1:5173", "http://localhost:5173",
            }
            if origin is not None and origin not in allowed:
                return JSONResponse({"detail": "Cross-site write not permitted"}, status_code=403)
        return await call_next(request)

    @app.get("/api/v1/health")
    def health():
        return {"status": "ready", "version": __version__, "offline": True,
                "mode": "synthetic_fixture_only", "external_providers_connected": False}

    @app.get("/api/v1/sources")
    def sources():
        return {"items": app.state.store.sources(),
                "available_importers": ["chatgpt:synthetic-v1", "claude:synthetic-v1"],
                "limitations": "No live chat synchronization; real export parsing not validated"}

    @app.post("/api/v1/imports", status_code=201)
    async def create_import(
        provider: Annotated[Literal["chatgpt", "claude"], Form()],
        account_alias: Annotated[str, Form()],
        file: Annotated[UploadFile, File()],
        dry_run: Annotated[bool, Form()] = False,
    ):
        try:
            alias = validate_account_alias(account_alias)
            blob = await file.read(MAX_UPLOAD_BYTES + 1)
            filename = file.filename or "unknown"
            content = safe_json_payload(blob, filename)
            parsed = load_synthetic(content, provider)
        except ImportProblem as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
        if dry_run:
            return {"status": "dry_run", "provider": provider,
                    "conversations": len(parsed), "messages": sum(len(x.messages) for x in parsed),
                    "parser_version": PARSER_VERSION, "persisted": False}
        try:
            return app.state.store.import_conversations(
                provider=provider, account_alias=alias,
                import_hash=hashlib.sha256(blob).hexdigest(),
                parser_version=PARSER_VERSION, conversations=parsed,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/imports/{batch_id}")
    def receipt(batch_id: str):
        result = app.state.store.receipt(batch_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Import batch not found")
        return result

    @app.get("/api/v1/conversations")
    def list_conversations(source_id: str | None = None, project_id: str | None = None):
        return {"items": app.state.store.conversations(source_id, project_id)}

    @app.get("/api/v1/conversations/{conversation_id}/messages")
    def list_messages(conversation_id: str):
        return {"items": app.state.store.messages(conversation_id)}

    @app.get("/api/v1/search")
    def search(q: Annotated[str, Query(max_length=300)],
               project_id: str | None = None, source_id: str | None = None):
        return {"items": app.state.store.search(q, project_id, source_id)}

    @app.get("/api/v1/projects")
    def projects():
        return {"items": app.state.store.projects()}

    @app.post("/api/v1/projects", status_code=201)
    def create_project(body: NewProject):
        return app.state.store.create_project(body.name, body.repo_url)

    @app.patch("/api/v1/conversations/{conversation_id}")
    def assign_project(conversation_id: str, body: SetProject):
        try:
            found = app.state.store.assign_conversation(conversation_id, body.project_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not found:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"conversation_id": conversation_id, "project_id": body.project_id}

    return app


app = create_app()
