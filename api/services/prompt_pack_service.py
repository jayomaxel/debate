"""
Prompt Pack V1 service for work package A.

Agents should eventually call this module instead of assembling long business
prompts inline. This first version is pure and safe to test without databases.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from services.domain_pack_service import DEFAULT_DOMAIN_PACK_ID, DomainPackService
from services.mode_policy_service import DEFAULT_MODE, ModePolicyService
from services.score_validation_service import ScoreValidationService


PROMPT_PACK_VERSION = "a.prompt_pack.v1"
PROMPT_LAYER_ORDER = (
    "global_rules",
    "mode_policy",
    "task_contract",
    "phase_objective",
    "context_block",
    "output_contract",
    "domain_pack",
)


@dataclass
class PromptBuildContext:
    agent: str = "debater"
    mode: str = DEFAULT_MODE
    phase: str = "opening"
    topic: str = ""
    role: str = "affirmative"
    speaker_role: str = "debater_1"
    stance: str = "pro"
    history: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_snippets: List[Any] = field(default_factory=list)
    assessment_summary: Dict[str, Any] = field(default_factory=dict)
    role_assignment_summary: Dict[str, Any] = field(default_factory=dict)
    output_contract: Dict[str, Any] = field(default_factory=dict)
    domain_pack_id: str = DEFAULT_DOMAIN_PACK_ID

    def __post_init__(self) -> None:
        self.agent = ModePolicyService.normalize_agent(self.agent)
        self.mode = ModePolicyService.normalize_mode(self.mode)
        self.phase = ModePolicyService.normalize_phase(self.phase)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PromptBuildContext":
        return cls(
            agent=str(data.get("agent") or "debater"),
            mode=str(data.get("mode") or DEFAULT_MODE),
            phase=str(data.get("phase") or "opening"),
            topic=str(data.get("topic") or ""),
            role=str(data.get("role") or "affirmative"),
            speaker_role=str(data.get("speaker_role") or "debater_1"),
            stance=str(data.get("stance") or "pro"),
            history=list(data.get("history") or []),
            knowledge_snippets=list(data.get("knowledge_snippets") or []),
            assessment_summary=dict(data.get("assessment_summary") or {}),
            role_assignment_summary=dict(data.get("role_assignment_summary") or {}),
            output_contract=dict(data.get("output_contract") or {}),
            domain_pack_id=str(data.get("domain_pack_id") or DEFAULT_DOMAIN_PACK_ID),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "mode": self.mode,
            "phase": self.phase,
            "topic": self.topic,
            "role": self.role,
            "speaker_role": self.speaker_role,
            "stance": self.stance,
            "history": list(self.history),
            "knowledge_snippets": list(self.knowledge_snippets),
            "assessment_summary": dict(self.assessment_summary),
            "role_assignment_summary": dict(self.role_assignment_summary),
            "output_contract": dict(self.output_contract),
            "domain_pack_id": self.domain_pack_id,
        }


@dataclass(frozen=True)
class PromptPack:
    version: str
    context: PromptBuildContext
    layers: "OrderedDict[str, Any]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "layer_order": list(self.layers.keys()),
            "context": self.context.to_dict(),
            "layers": {key: self.layers[key] for key in self.layers},
        }

    def render(self) -> str:
        rendered: List[str] = [f"prompt_pack_version: {self.version}"]
        for key, value in self.layers.items():
            rendered.append(f"\n## {key}")
            rendered.append(self._render_value(value))
        return "\n".join(rendered).strip()

    @staticmethod
    def _render_value(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


@dataclass(frozen=True)
class ScoreEvidenceSchema:
    anchor_id: str = ""
    anchor_type: str = "turn"
    turn_id: str = ""
    speaker_role: str = ""
    excerpt: str = ""
    source_document_id: str = ""
    source_location: str = ""
    evidence_relation: str = "support"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "anchor_type": self.anchor_type,
            "turn_id": self.turn_id,
            "speaker_role": self.speaker_role,
            "excerpt": self.excerpt,
            "source_document_id": self.source_document_id,
            "source_location": self.source_location,
            "evidence_relation": self.evidence_relation,
        }


@dataclass(frozen=True)
class DebateReportSchema:
    mode: str = DEFAULT_MODE
    domain_pack_id: str = DEFAULT_DOMAIN_PACK_ID
    report_meta: Dict[str, Any] = field(default_factory=dict)
    turning_points: List[Dict[str, Any]] = field(default_factory=list)
    evidence_anchors: List[Dict[str, Any]] = field(default_factory=list)
    improvement_actions: List[Dict[str, Any]] = field(default_factory=list)
    participant_scores: List[Dict[str, Any]] = field(default_factory=list)
    participants: List[Dict[str, Any]] = field(default_factory=list)
    speeches: List[Dict[str, Any]] = field(default_factory=list)
    team_summary: Dict[str, Any] = field(default_factory=dict)
    teaching_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": ModePolicyService.normalize_mode(self.mode),
            "domain_pack_id": self.domain_pack_id,
            "report_meta": dict(self.report_meta),
            "turning_points": list(self.turning_points),
            "evidence_anchors": list(self.evidence_anchors),
            "improvement_actions": list(self.improvement_actions),
            "participant_scores": list(self.participant_scores),
            "participants": list(self.participants),
            "speeches": list(self.speeches),
            "team_summary": dict(self.team_summary),
            "teaching_summary": dict(self.teaching_summary),
        }

    @classmethod
    def mock(
        cls,
        *,
        mode: str = DEFAULT_MODE,
        scoring_quality: str = "validated",
    ) -> "DebateReportSchema":
        meta = ScoreValidationService.build_report_meta(
            scoring_source="judge_model" if scoring_quality in {"validated", "repaired"} else "fallback",
            scoring_quality=scoring_quality,
            mode=mode,
        ).to_dict()
        anchor = ScoreEvidenceSchema(
            anchor_id="anchor_1",
            anchor_type="turn",
            turn_id="turn_1",
            speaker_role="debater_1",
            excerpt="sample evidence excerpt",
            evidence_relation="support",
        ).to_dict()
        return cls(
            mode=mode,
            report_meta=meta,
            turning_points=[
                {
                    "turn_id": "turn_1",
                    "summary": "sample turning point",
                    "impact": "shows why the clash matters",
                }
            ],
            evidence_anchors=[anchor],
            improvement_actions=[
                {
                    "speaker_role": "debater_1",
                    "action": "make the warrant explicit before adding examples",
                    "priority": "medium",
                }
            ],
            participant_scores=[
                {
                    "speaker_role": "debater_1",
                    "overall_score": 80,
                    "logic_score": 80,
                    "argument_score": 80,
                    "response_score": 80,
                    "persuasion_score": 80,
                    "teamwork_score": 80,
                }
            ],
            participants=[],
            speeches=[],
            team_summary={"positive": {}, "negative": {}},
            teaching_summary={} if mode == "competition" else {"learning_objectives": []},
        )


class PromptPackService:
    """Builds Prompt Pack V1 with a stable seven-layer order."""

    @classmethod
    def build_prompt(cls, context: PromptBuildContext | Mapping[str, Any]) -> PromptPack:
        ctx = context if isinstance(context, PromptBuildContext) else PromptBuildContext.from_mapping(context)
        policy = ModePolicyService.get_policy(mode=ctx.mode, agent=ctx.agent, phase=ctx.phase)
        domain_pack = DomainPackService.build_domain_pack(
            domain_pack_id=ctx.domain_pack_id,
            knowledge_snippets=ctx.knowledge_snippets,
        )

        layers: "OrderedDict[str, Any]" = OrderedDict()
        layers["global_rules"] = cls._build_global_rules(ctx)
        layers["mode_policy"] = policy
        layers["task_contract"] = cls._build_task_contract(ctx)
        layers["phase_objective"] = policy["phase_policy"]
        layers["context_block"] = cls._build_context_block(ctx)
        layers["output_contract"] = cls._build_output_contract(ctx)
        layers["domain_pack"] = domain_pack.to_dict()
        return PromptPack(version=PROMPT_PACK_VERSION, context=ctx, layers=layers)

    @classmethod
    def render_agent_prompt(cls, context, task_prompt="", extra_sections=None):
        task_prompt = str(task_prompt or "").strip()
        extra_sections = extra_sections or {}
        pack = cls.build_prompt(context)
        sections = [pack.render()]
        if task_prompt:
            sections.append("task_detail:")
            sections.append(task_prompt)
        for name, value in extra_sections.items():
            normalized_name = str(name or "extra_section").strip() or "extra_section"
            sections.append(f"{normalized_name}:")
            sections.append(PromptPack._render_value(value))
        return chr(10).join(sections).strip()

    @classmethod
    def render_agent_task_prompt(
        cls,
        context: PromptBuildContext | Mapping[str, Any],
        *,
        task_type: str,
        task_data: Mapping[str, Any] | None = None,
        extra_sections: Mapping[str, Any] | None = None,
    ) -> str:
        """Render an agent task from structured data through the Prompt Pack."""
        task_payload = {
            "task_type": str(task_type or "").strip() or "general",
            "task_data": cls._normalize_task_data(task_data or {}),
        }
        return cls.render_agent_prompt(
            context,
            task_prompt=PromptPack._render_value(task_payload),
            extra_sections=extra_sections,
        )

    @classmethod
    def _normalize_task_data(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): cls._normalize_task_data(item)
                for key, item in value.items()
                if item is not None
            }
        if isinstance(value, (list, tuple, set)):
            return [cls._normalize_task_data(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    @classmethod
    def resolve_mode_from_context(cls, history=None, mode=None):
        if mode:
            return ModePolicyService.normalize_mode(mode)
        for item in reversed(list(history or [])):
            if not isinstance(item, Mapping):
                continue
            candidates = [item.get("mode"), item.get("debate_mode")]
            meta = item.get("config_meta")
            if isinstance(meta, Mapping):
                candidates.append(meta.get("mode"))
            for candidate in candidates:
                normalized = ModePolicyService.normalize_mode(candidate)
                if candidate and normalized == str(candidate).strip().lower():
                    return normalized
        return DEFAULT_MODE

    @classmethod
    def _build_global_rules(cls, context: PromptBuildContext) -> Dict[str, Any]:
        return {
            "language": "zh-CN",
            "agent": context.agent,
            "rules": [
                "Follow the current mode and phase only.",
                "Use supplied context; do not invent B/E owned fields.",
                "Preserve frozen score and report field names.",
                "Expose degraded, repaired, fallback, or partial quality states.",
            ],
        }

    @classmethod
    def _build_task_contract(cls, context: PromptBuildContext) -> Dict[str, Any]:
        contracts = {
            "debater": {
                "input": ["topic", "stance", "phase", "history", "knowledge_snippets"],
                "output": ["speech_text"],
                "constraints": ["phase-aware", "stance-consistent", "evidence-aware"],
            },
            "judge": {
                "input": ["speech_text", "speaker_role", "phase", "history"],
                "output": list(ScoreValidationService.expected_speech_score_contract().keys()),
                "constraints": ["json_only", "score_0_100", "no_hidden_fallback"],
            },
            "mentor": {
                "input": ["topic", "stance", "phase", "history", "assessment_summary"],
                "output": ["suggestion"],
                "constraints": ["private_tip", "mode_length_control", "one_next_action"],
            },
            "report": {
                "input": ["scores", "speeches", "evidence_anchors"],
                "output": list(DebateReportSchema().to_dict().keys()),
                "constraints": ["include_report_meta", "preserve_legacy_fields"],
            },
        }
        return contracts[context.agent]

    @classmethod
    def _build_context_block(cls, context: PromptBuildContext) -> Dict[str, Any]:
        history_meta = cls._extract_history_meta(context.history)
        return {
            "topic": context.topic,
            "role": context.role,
            "speaker_role": context.speaker_role,
            "stance": context.stance,
            "history": cls._trim_history(context.history),
            "assessment_summary": dict(context.assessment_summary),
            "config_meta": history_meta.get("config_meta", {}),
            "role_assignment_summary": dict(context.role_assignment_summary)
            or history_meta.get("role_assignment_summary", {}),
            "knowledge_snippet_count": len(context.knowledge_snippets),
        }

    @classmethod
    def _build_output_contract(cls, context: PromptBuildContext) -> Dict[str, Any]:
        if context.output_contract:
            return dict(context.output_contract)
        if context.agent == "judge":
            return ScoreValidationService.expected_speech_score_contract()
        if context.agent == "report":
            return DebateReportSchema().to_dict()
        if context.agent == "mentor":
            return {"suggestion": "string"}
        return {"speech_text": "string"}

    @staticmethod
    def _trim_history(history: Sequence[Mapping[str, Any]], limit: int = 12) -> List[Dict[str, Any]]:
        trimmed: List[Dict[str, Any]] = []
        for item in list(history)[-limit:]:
            if not isinstance(item, Mapping):
                continue
            trimmed.append(
                {
                    "role": str(item.get("role") or item.get("speaker_role") or ""),
                    "content": str(item.get("content") or "")[:1200],
                }
            )
        return trimmed

    @staticmethod
    def _extract_history_meta(history: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        for item in reversed(list(history or [])):
            if not isinstance(item, Mapping):
                continue
            result: Dict[str, Any] = {}
            config_meta = item.get("config_meta")
            if isinstance(config_meta, Mapping):
                result["config_meta"] = dict(config_meta)
            role_assignment_summary = item.get("role_assignment_summary")
            if isinstance(role_assignment_summary, Mapping):
                result["role_assignment_summary"] = dict(role_assignment_summary)
            if result:
                return result
        return {}

    @classmethod
    def build_mock_report(
        cls,
        *,
        mode: str = DEFAULT_MODE,
        scoring_quality: str = "validated",
    ) -> Dict[str, Any]:
        return DebateReportSchema.mock(mode=mode, scoring_quality=scoring_quality).to_dict()

    @classmethod
    def layer_order(cls) -> Iterable[str]:
        return tuple(PROMPT_LAYER_ORDER)


def build_prompt(context: PromptBuildContext | Mapping[str, Any]) -> PromptPack:
    return PromptPackService.build_prompt(context)
