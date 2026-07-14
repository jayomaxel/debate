"""
Mode policy service for work package A.

This module is deliberately pure: it does not read routes, database rows, or
front-end parameters. B/E owned context can be mapped into PromptBuildContext
after their contracts are frozen.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable


SUPPORTED_MODES = ("competition", "teaching")
SUPPORTED_AGENTS = ("debater", "judge", "mentor", "report")
SUPPORTED_PHASES = ("opening", "questioning", "free_debate", "closing", "report")
DEFAULT_MODE = "competition"


class ModePolicyService:
    """Builds stable competition/teaching policy blocks for prompts and reports."""

    _MODE_POLICIES: Dict[str, Dict[str, Any]] = {
        "competition": {
            "mode": "competition",
            "primary_goal": "win the debate through clear claims, valid evidence, direct response, and controlled turns.",
            "judge_focus": [
                "argument_strength",
                "response_effectiveness",
                "turn_control",
                "critical_mistakes",
            ],
            "mentor_focus": [
                "tactical_next_step",
                "pressure_point",
                "risk_warning",
            ],
            "report_focus": [
                "turning_points",
                "decisive_reasons",
                "side_comparison",
            ],
            "tone": "concise, tactical, evidence-aware",
            "mentor_length": {"min_chars": 80, "max_chars": 120},
        },
        "teaching": {
            "mode": "teaching",
            "primary_goal": "support learning transfer, curriculum reflection, and actionable improvement.",
            "judge_focus": [
                "knowledge_transfer",
                "learning_objective_alignment",
                "reasoning_process",
                "reflection_quality",
            ],
            "mentor_focus": [
                "learning_gap",
                "revision_action",
                "reflection_prompt",
            ],
            "report_focus": [
                "learning_objectives",
                "common_issues",
                "improvement_actions",
            ],
            "tone": "diagnostic, constructive, classroom-aware",
            "mentor_length": {"min_chars": 120, "max_chars": 180},
        },
    }

    _AGENT_POLICIES: Dict[str, Dict[str, Any]] = {
        "debater": {
            "task": "produce phase-aware debate speech",
            "must_do": ["stay on stance", "answer the current phase objective", "avoid unsupported claims"],
            "must_not_do": ["invent unavailable documents", "explain internal scoring rules"],
        },
        "judge": {
            "task": "score and explain debate performance",
            "must_do": ["return machine-checkable JSON", "anchor scores to evidence", "mark uncertainty"],
            "must_not_do": ["hide fallback scoring", "change score field names"],
        },
        "mentor": {
            "task": "give private tactical or learning suggestions",
            "must_do": ["be brief", "give the next action", "separate tactic from reflection by mode"],
            "must_not_do": ["announce hidden model details", "rewrite the whole speech"],
        },
        "report": {
            "task": "summarize the debate into the frozen report contract",
            "must_do": ["include report_meta", "include evidence anchors when available", "preserve legacy score fields"],
            "must_not_do": ["claim scientific validation", "omit degraded quality markers"],
        },
    }

    _PHASE_POLICIES: Dict[str, Dict[str, Any]] = {
        "opening": {
            "objective": "define the core frame, establish main claims, and state burden clearly.",
            "expected_evidence": ["definition", "framework", "main_claim"],
        },
        "questioning": {
            "objective": "test assumptions, expose missing evidence, and force useful clarification.",
            "expected_evidence": ["question", "follow_up", "answer_quality"],
        },
        "free_debate": {
            "objective": "respond directly, compare impacts, and keep pressure on the strongest clash.",
            "expected_evidence": ["rebuttal", "weighing", "turn_control"],
        },
        "closing": {
            "objective": "weigh the debate, crystallize decisive issues, and explain why the side wins.",
            "expected_evidence": ["summary", "weighing", "winner_reason"],
        },
        "report": {
            "objective": "produce a reviewable report with scoring quality and evidence anchors.",
            "expected_evidence": ["score", "anchor", "improvement_action"],
        },
    }

    @classmethod
    def normalize_mode(cls, mode: str | None) -> str:
        normalized = str(mode or DEFAULT_MODE).strip().lower()
        return normalized if normalized in SUPPORTED_MODES else DEFAULT_MODE

    @classmethod
    def normalize_agent(cls, agent: str | None) -> str:
        normalized = str(agent or "debater").strip().lower()
        return normalized if normalized in SUPPORTED_AGENTS else "debater"

    @classmethod
    def normalize_phase(cls, phase: str | None) -> str:
        normalized = str(phase or "opening").strip().lower()
        return normalized if normalized in SUPPORTED_PHASES else "opening"

    @classmethod
    def get_policy(
        cls,
        mode: str | None = None,
        agent: str | None = None,
        phase: str | None = None,
    ) -> Dict[str, Any]:
        normalized_mode = cls.normalize_mode(mode)
        normalized_agent = cls.normalize_agent(agent)
        normalized_phase = cls.normalize_phase(phase)

        policy = deepcopy(cls._MODE_POLICIES[normalized_mode])
        policy["agent"] = normalized_agent
        policy["phase"] = normalized_phase
        policy["agent_policy"] = deepcopy(cls._AGENT_POLICIES[normalized_agent])
        policy["phase_policy"] = deepcopy(cls._PHASE_POLICIES[normalized_phase])
        return policy

    @classmethod
    def supported_modes(cls) -> Iterable[str]:
        return tuple(SUPPORTED_MODES)

    @classmethod
    def supported_agents(cls) -> Iterable[str]:
        return tuple(SUPPORTED_AGENTS)

    @classmethod
    def supported_phases(cls) -> Iterable[str]:
        return tuple(SUPPORTED_PHASES)


def get_mode_policy(
    mode: str | None = None,
    agent: str | None = None,
    phase: str | None = None,
) -> Dict[str, Any]:
    return ModePolicyService.get_policy(mode=mode, agent=agent, phase=phase)
