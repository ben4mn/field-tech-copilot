from __future__ import annotations

from typing import Protocol

from fieldtech.core.models import Assessment, DiagnosticCase
from fieldtech.knowledge.store import KnowledgeSnippet


class DiagnosticModel(Protocol):
    name: str

    def assess(
        self, case: DiagnosticCase, knowledge: list[KnowledgeSnippet]
    ) -> Assessment: ...

    def health(self) -> tuple[bool, str]: ...

