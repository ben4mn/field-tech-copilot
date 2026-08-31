from __future__ import annotations

import secrets
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from fieldtech.config import Settings
from fieldtech.core.database import Database
from fieldtech.core.models import DeviceContext, DiagnosticCase
from fieldtech.core.service import (
    CaseNotFound,
    DiagnosticService,
    InvalidCaseAction,
)
from fieldtech.knowledge.store import KnowledgeStore
from fieldtech.providers import build_provider

STATIC_DIR = Path(__file__).parent / "static"


class CreateCaseRequest(BaseModel):
    complaint: str = Field(min_length=1, max_length=8_000)
    title: str | None = Field(default=None, max_length=300)
    device: DeviceContext = Field(default_factory=DeviceContext)


class ObservationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8_000)
    source: Literal["customer", "technician", "system"] = "technician"


class CompleteTestRequest(BaseModel):
    result: str = Field(min_length=1, max_length=8_000)
    outcome: Literal["pass", "fail", "inconclusive", "blocked", "other"] = "other"
    confirmed: bool = False


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    database = Database(settings.database_path)
    database.initialize()
    knowledge = KnowledgeStore(database)
    model = build_provider(settings)
    service = DiagnosticService(database=database, knowledge=knowledge, model=model)
    session_token = secrets.token_urlsafe(32)

    app = FastAPI(
        title="Field Tech Copilot",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    allowed_hosts = ["*"] if settings.allow_remote else ["127.0.0.1", "localhost", "::1"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def require_token(x_fieldtech_token: str | None = Header(default=None)) -> None:
        if not x_fieldtech_token or not secrets.compare_digest(
            x_fieldtech_token, session_token
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    auth = [Depends(require_token)]

    @app.middleware("http")
    async def security_headers(request: object, call_next: object) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(CaseNotFound)
    async def case_not_found_handler(request: object, exc: CaseNotFound) -> Response:
        return PlainTextResponse("Case not found", status_code=status.HTTP_404_NOT_FOUND)

    @app.exception_handler(InvalidCaseAction)
    async def invalid_action_handler(request: object, exc: InvalidCaseAction) -> Response:
        return PlainTextResponse(str(exc), status_code=status.HTTP_409_CONFLICT)

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace("__FIELDTECH_TOKEN__", session_token)
        return HTMLResponse(html)

    @app.get("/api/health", dependencies=auth)
    def health() -> dict[str, object]:
        model_ready, model_message = model.health()
        return {
            "status": "ready" if model_ready else "degraded",
            "model_ready": model_ready,
            "model": settings.model_name if settings.model_provider != "mock" else "mock",
            "model_message": model_message,
            "knowledge_cards": database.count_knowledge_cards(),
            "offline_only": not settings.allow_remote,
        }

    @app.get("/api/cases", response_model=list[DiagnosticCase], dependencies=auth)
    def list_cases() -> list[DiagnosticCase]:
        return service.list_cases()

    @app.post(
        "/api/cases",
        response_model=DiagnosticCase,
        status_code=status.HTTP_201_CREATED,
        dependencies=auth,
    )
    def create_case(request: CreateCaseRequest) -> DiagnosticCase:
        return service.create_case(
            complaint=request.complaint,
            title=request.title,
            device=request.device,
        )

    @app.get("/api/cases/{case_id}", response_model=DiagnosticCase, dependencies=auth)
    def get_case(case_id: str) -> DiagnosticCase:
        return service.get_case(case_id)

    @app.post(
        "/api/cases/{case_id}/observations",
        response_model=DiagnosticCase,
        dependencies=auth,
    )
    def add_observation(case_id: str, request: ObservationRequest) -> DiagnosticCase:
        return service.add_observation(case_id, request.text, request.source)

    @app.post(
        "/api/cases/{case_id}/tests/{test_id}/complete",
        response_model=DiagnosticCase,
        dependencies=auth,
    )
    def complete_test(
        case_id: str, test_id: str, request: CompleteTestRequest
    ) -> DiagnosticCase:
        return service.complete_test(
            case_id=case_id,
            test_id=test_id,
            result=request.result,
            outcome=request.outcome,
            confirmed=request.confirmed,
        )

    @app.post(
        "/api/cases/{case_id}/refresh",
        response_model=DiagnosticCase,
        dependencies=auth,
    )
    def refresh_case(case_id: str) -> DiagnosticCase:
        return service.refresh_assessment(service.get_case(case_id))

    @app.post(
        "/api/cases/{case_id}/close",
        response_model=DiagnosticCase,
        dependencies=auth,
    )
    def close_case(case_id: str) -> DiagnosticCase:
        return service.close_case(case_id)

    @app.delete(
        "/api/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=auth
    )
    def delete_case(case_id: str) -> Response:
        service.delete_case(case_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/api/cases/{case_id}/export", dependencies=auth)
    def export_case(case_id: str) -> PlainTextResponse:
        content = service.export_markdown(case_id)
        return PlainTextResponse(
            content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="fieldtech-{case_id}.md"'
            },
        )

    return app

