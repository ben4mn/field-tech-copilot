from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from fieldtech.core.models import RiskLevel


class ProcedureCard(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    title: str = Field(min_length=1, max_length=300)
    topics: list[str] = Field(min_length=1)
    risk: RiskLevel
    source_title: str = Field(min_length=1)
    source_url: str | None = None
    source_version: str | None = None
    verified_at: date
    review_after: date | None = None
    trust_tier: int = Field(default=1, ge=1, le=4)
    redistribution: str = "check-source-license"
    platforms: list[str] = Field(default_factory=list)
    vendors: list[str] = Field(default_factory=list)
    requires_elevation: bool = False
    prerequisites: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    rollback: str | None = None
    body: str = Field(min_length=1)
    path: str | None = None

    @model_validator(mode="after")
    def validate_destructive_metadata(self) -> ProcedureCard:
        if self.risk == RiskLevel.DESTRUCTIVE:
            if not self.prerequisites:
                raise ValueError("destructive cards require prerequisites")
            if not self.rollback:
                raise ValueError(
                    "destructive cards must describe rollback or state that none exists"
                )
        return self

    @property
    def checksum(self) -> str:
        payload = self.model_dump_json(exclude={"path"}).encode()
        return hashlib.sha256(payload).hexdigest()


def parse_card(path: Path) -> ProcedureCard:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: expected YAML frontmatter starting with ---")
    try:
        _, frontmatter, body = text.split("---", 2)
    except ValueError as exc:
        raise ValueError(f"{path}: incomplete YAML frontmatter") from exc
    metadata = yaml.safe_load(frontmatter)
    if not isinstance(metadata, dict):
        raise ValueError(f"{path}: frontmatter must be a mapping")
    return ProcedureCard.model_validate(
        {**metadata, "body": body.strip(), "path": str(path.resolve())}
    )


def find_cards(root: Path) -> list[ProcedureCard]:
    paths = [root] if root.is_file() else sorted(root.rglob("*.md"))
    paths = [
        path
        for path in paths
        if path.read_text(encoding="utf-8").startswith("---\n")
    ]
    return [parse_card(path) for path in paths]
