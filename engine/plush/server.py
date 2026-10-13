"""Local web service for the editor. Run: uv run uvicorn plush.server:app --host 127.0.0.1 --port 8765

It listens on this Mac only. The real entry point (`app`) refuses to start unless
OPENROUTER_API_KEY and PLUSH_VISION_MODEL are set; `create_app` builds the same service
for tests, with picture reading left out.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import asdict
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, ValidationError

from plush.geometry.assemble import assemble
from plush.parts import parse_kit
from plush.pattern import build_pattern
from plush.projects import ApprovalError, Projects
from plush.settings import Settings, load_settings

REQUIRED_ENV = ("OPENROUTER_API_KEY", "PLUSH_VISION_MODEL")
DEFAULT_PROJECTS = Path(__file__).resolve().parents[2] / "projects"
PICTURE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


class NewProject(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    picture_base64: str
    media_type: str


class Height(BaseModel):
    finished_height_in: float = Field(gt=2, le=60)


def create_app(projects_root: Path, settings: Settings | None = None) -> FastAPI:
    projects = Projects(projects_root)
    settings = settings or load_settings()
    app = FastAPI(title="Plush pattern engine")

    def folder(slug: str):
        try:
            return projects.folder(slug)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e

    @app.get("/api/settings")
    def get_settings():
        return asdict(settings)

    @app.post("/api/projects")
    def new_project(body: NewProject):
        if body.media_type not in PICTURE_TYPES:
            raise HTTPException(415, f"picture must be one of {sorted(PICTURE_TYPES)}")
        try:
            picture = base64.b64decode(body.picture_base64, validate=True)
        except binascii.Error as e:
            raise HTTPException(400, "picture_base64 is not valid base64") from e
        return {"slug": projects.create(body.name, picture, PICTURE_TYPES[body.media_type])}

    @app.get("/api/projects")
    def list_projects():
        return {"projects": projects.list()}

    @app.get("/api/projects/{slug}")
    def project(slug: str):
        folder(slug)
        drafts = projects.drafts(slug)
        return {"slug": slug, "drafts": len(drafts), "approved": projects.approved(slug),
                "has_pattern": projects.pdf_path(slug).exists()}

    @app.put("/api/projects/{slug}/kit")
    def save_kit(slug: str, kit: dict):
        folder(slug)
        try:
            parsed = parse_kit(json.dumps(kit))
        except ValidationError as e:
            return JSONResponse(status_code=422, content={"error": "invalid part kit", "detail": e.errors(include_url=False)})
        return {"draft": projects.save_draft(slug, parsed)}

    @app.get("/api/projects/{slug}/kit")
    def latest_kit(slug: str):
        folder(slug)
        try:
            return projects.latest(slug).model_dump(mode="json")
        except ApprovalError as e:
            raise HTTPException(404, str(e)) from e

    @app.post("/api/projects/{slug}/mesh")
    def mesh(slug: str, body: Height):
        folder(slug)
        try:
            kit = projects.latest(slug)
        except ApprovalError as e:
            raise HTTPException(404, str(e)) from e
        placed = assemble(kit, body.finished_height_in)
        return {"parts": {name: {"part": p.part_id, "kind": p.kind,
                                 "vertices": np.round(p.mesh.vertices, 4).tolist(),
                                 "faces": p.mesh.faces.tolist()} for name, p in placed.items()}}

    @app.post("/api/projects/{slug}/approve")
    def approve(slug: str, body: Height):
        folder(slug)
        try:
            return {"version_id": projects.approve(slug, body.finished_height_in)}
        except ApprovalError as e:
            raise HTTPException(409, str(e)) from e

    @app.post("/api/projects/{slug}/pattern")
    def pattern(slug: str):
        folder(slug)
        try:
            kit, height, version_check = projects.check_approved(slug)
        except ApprovalError as e:
            raise HTTPException(409, str(e)) from e
        result = build_pattern(kit, height, settings, projects.pdf_path(slug), version_check)
        version = projects.approved(slug)["version_id"]
        projects.save_report(slug, result.checks, version)
        report = {"version_id": version, "passed": result.passed, "checks": [asdict(c) for c in result.checks]}
        return JSONResponse(status_code=200 if result.passed else 409, content=report)

    @app.get("/api/projects/{slug}/pattern.pdf")
    def pattern_pdf(slug: str):
        path = projects.pdf_path(folder(slug).name)
        if not path.exists():
            raise HTTPException(404, "no printable pattern: build one that passes all seven checks")
        return FileResponse(path, media_type="application/pdf", filename=f"{slug}-pattern.pdf")

    return app


def app_from_env() -> FastAPI:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"cannot start: set {' and '.join(missing)} (see README)")
    return create_app(Path(os.environ.get("PLUSH_PROJECTS_DIR", DEFAULT_PROJECTS)))


def __getattr__(name: str):
    # `uvicorn plush.server:app` builds the real app only when asked, so importing this module
    # in tests does not require the environment to be set
    if name == "app":
        return app_from_env()
    raise AttributeError(name)
