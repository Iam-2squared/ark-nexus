"""Nexus V1 local API. No external APIs, task dispatch, or consumer-chat automation."""

import hashlib
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from nexus import __version__
from nexus.access import local_access_key
from nexus.connectors import connection_catalog
from nexus.importers import (
    MAX_UPLOAD_BYTES,
    PARSER_VERSION,
    ImportProblem,
    load_synthetic,
    safe_json_payload,
    validate_account_alias,
)
from nexus.security import LocalBoundary
from nexus.settings import database_path
from nexus.store import Store


class NewProject(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    repo_url: str | None = Field(default=None, max_length=500)


class SetProject(BaseModel):
    project_id: str | None = None


def create_app(path: Path | None = None) -> FastAPI:
    def initialize(app, database):
        app.state.store = Store(database)
        # Serialize startup key creation with other instances using the same database.
        with app.state.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            app.state.access_key = local_access_key(app.state.store.path.parent)

    @asynccontextmanager
    async def lifespan(app):
        if path is None:
            initialize(app, database_path())
        yield

    app = FastAPI(title="ARK Nexus Local API", version=__version__, lifespan=lifespan)
    # Importing this module must not create a database in the user's profile.
    if path is not None:
        initialize(app, path)
    app.add_middleware(LocalBoundary, key=lambda: app.state.access_key)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc):
        return JSONResponse({"detail": "Invalid request fields"}, status_code=422)

    @app.exception_handler(sqlite3.Error)
    async def storage_error(_request, _exc):
        return JSONResponse({"detail": "Local storage unavailable"}, status_code=503)

    @app.get("/api/v1/health")
    def health():
        return {"status": "ready", "version": __version__, "offline": True,
                "mode": "synthetic_fixture_only", "external_providers_connected": False}

    @app.get("/api/v1/overview")
    def overview():
        return app.state.store.overview()

    @app.get("/api/v1/integrity")
    def integrity():
        return app.state.store.integrity_report()

    @app.get("/api/v1/connections")
    def connections():
        return {"items": connection_catalog(), "checked_at": "2026-10-11",
                "execution_enabled": False}

    @app.get("/api/v1/imports")
    def list_imports(limit: Annotated[int, Query(ge=1, le=200)] = 100,
                     offset: Annotated[int, Query(ge=0)] = 0):
        return app.state.store.imports(limit, offset)

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
    def list_conversations(source_id: str | None = None, project_id: str | None = None,
                           limit: Annotated[int, Query(ge=1, le=500)] = 100,
                           offset: Annotated[int, Query(ge=0)] = 0):
        return app.state.store.conversations_page(source_id, project_id, limit, offset)

    @app.get("/api/v1/conversations/{conversation_id}/messages")
    def list_messages(conversation_id: str,
                      limit: Annotated[int, Query(ge=1, le=1000)] = 200,
                      offset: Annotated[int, Query(ge=0)] = 0):
        result = app.state.store.messages_page(conversation_id, limit, offset)
        if result is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return result

    @app.get("/api/v1/search")
    def search(q: Annotated[str, Query(max_length=300)],
               project_id: str | None = None, source_id: str | None = None,
               limit: Annotated[int, Query(ge=1, le=100)] = 100,
               offset: Annotated[int, Query(ge=0)] = 0):
        return app.state.store.search_page(q, project_id, source_id, limit, offset)

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
