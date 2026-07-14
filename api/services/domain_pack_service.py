"""
Domain pack service for work package A.

Default packs are intentionally small and generic. Course-specific teaching
designs and support documents must come from E-owned frozen contracts later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Sequence


DEFAULT_DOMAIN_PACK_ID = "default"
MAX_SNIPPETS_PER_PACK = 6


@dataclass(frozen=True)
class DomainSnippet:
    snippet_id: str
    text: str
    source: str = ""
    use_goal: str = "support"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snippet_id": self.snippet_id,
            "text": self.text,
            "source": self.source,
            "use_goal": self.use_goal,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class DomainPack:
    domain_pack_id: str = DEFAULT_DOMAIN_PACK_ID
    title: str = "General debate domain pack"
    principles: List[str] = field(default_factory=list)
    knowledge_snippets: List[DomainSnippet] = field(default_factory=list)
    blocked_defaults: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_pack_id": self.domain_pack_id,
            "title": self.title,
            "principles": list(self.principles),
            "knowledge_snippets": [snippet.to_dict() for snippet in self.knowledge_snippets],
            "blocked_defaults": list(self.blocked_defaults),
        }

    def render(self) -> str:
        lines = [f"domain_pack_id: {self.domain_pack_id}", f"title: {self.title}"]
        if self.principles:
            lines.append("principles:")
            lines.extend(f"- {item}" for item in self.principles)
        if self.knowledge_snippets:
            lines.append("knowledge_snippets:")
            for snippet in self.knowledge_snippets:
                source = f" source={snippet.source}" if snippet.source else ""
                lines.append(f"- [{snippet.snippet_id}]{source} {snippet.text}")
        return "\n".join(lines)


class DomainPackService:
    """Builds domain packs without owning document parsing or knowledge-base logic."""

    _BUILTIN_PACKS: Dict[str, Dict[str, Any]] = {
        "default": {
            "title": "General debate domain pack",
            "principles": [
                "Prefer arguments that are tied to the debate topic.",
                "Use evidence only when it is present in supplied snippets or common classroom context.",
                "Do not inject finance-specific stablecoin content by default.",
            ],
            "blocked_defaults": ["stablecoin", "financial_stablecoin"],
        },
        "ai_literacy": {
            "title": "AI literacy debate pack",
            "principles": [
                "Use AI concepts only when they help the argument.",
                "Balance technical accuracy with ethical and social reasoning.",
                "Separate factual claims from value judgments.",
            ],
            "blocked_defaults": [],
        },
    }

    @classmethod
    def normalize_domain_pack_id(cls, domain_pack_id: str | None) -> str:
        normalized = str(domain_pack_id or DEFAULT_DOMAIN_PACK_ID).strip().lower()
        return normalized if normalized in cls._BUILTIN_PACKS else DEFAULT_DOMAIN_PACK_ID

    @classmethod
    def build_domain_pack(
        cls,
        domain_pack_id: str | None = None,
        knowledge_snippets: Sequence[Any] | None = None,
    ) -> DomainPack:
        normalized_id = cls.normalize_domain_pack_id(domain_pack_id)
        config = cls._BUILTIN_PACKS[normalized_id]
        snippets = cls.normalize_snippets(knowledge_snippets or [])
        return DomainPack(
            domain_pack_id=normalized_id,
            title=str(config["title"]),
            principles=list(config["principles"]),
            knowledge_snippets=snippets,
            blocked_defaults=list(config["blocked_defaults"]),
        )

    @classmethod
    def normalize_snippets(cls, raw_snippets: Sequence[Any]) -> List[DomainSnippet]:
        snippets: List[DomainSnippet] = []
        for index, raw in enumerate(raw_snippets[:MAX_SNIPPETS_PER_PACK], start=1):
            snippet = cls._coerce_snippet(raw, index)
            if snippet and snippet.text:
                snippets.append(snippet)
        return snippets

    @classmethod
    def _coerce_snippet(cls, raw: Any, index: int) -> DomainSnippet | None:
        if isinstance(raw, str):
            text = raw.strip()
            return DomainSnippet(snippet_id=f"snippet_{index}", text=text) if text else None

        if isinstance(raw, Mapping):
            text = str(
                raw.get("summary")
                or raw.get("text")
                or raw.get("content")
                or raw.get("excerpt")
                or ""
            ).strip()
            if not text:
                return None
            tags = raw.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            return DomainSnippet(
                snippet_id=str(raw.get("snippet_id") or raw.get("id") or f"snippet_{index}"),
                text=text,
                source=str(raw.get("source") or raw.get("source_document_id") or ""),
                use_goal=str(raw.get("use_goal") or "support"),
                tags=[str(tag) for tag in tags],
            )

        return None

    @classmethod
    def supported_domain_pack_ids(cls) -> Iterable[str]:
        return tuple(cls._BUILTIN_PACKS.keys())


def build_domain_pack(
    domain_pack_id: str | None = None,
    knowledge_snippets: Sequence[Any] | None = None,
) -> DomainPack:
    return DomainPackService.build_domain_pack(
        domain_pack_id=domain_pack_id,
        knowledge_snippets=knowledge_snippets,
    )
