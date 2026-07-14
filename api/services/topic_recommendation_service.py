"""
Candidate debate topic recommendation service.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from config import settings
from models.debate import Debate
from models.document import Document
from models.teaching_design import TopicRecommendationItem, TopicRecommendationRun
from services.config_service import ConfigService
from services.teaching_design_service import TeachingDesignService


class TopicRecommendationService:
    ROOM_META_KEY = "__room_meta"
    DEBATE_CONFIG_META_KEY = "debate_config_meta"
    DEFAULT_PREFERRED_COUNT = 4
    MIN_CANDIDATE_COUNT = 3
    MAX_CANDIDATE_COUNT = 5
    ALLOWED_MODES = {"competition", "teaching"}
    ALLOWED_DIFFICULTY = {"low", "medium", "high", "mixed"}
    RESPONSE_STATUS_READY = "ready"
    RESPONSE_STATUS_PARTIAL = "partial"
    RESPONSE_STATUS_UNAVAILABLE = "unavailable"

    @staticmethod
    def _uuid(value: Any) -> Optional[uuid.UUID]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_optional_string(value: Any) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _clean_string_list(value: Any) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("候选辩题输入中的列表字段必须是数组")
        result: List[str] = []
        seen = set()
        for item in value:
            cleaned = TopicRecommendationService._clean_optional_string(item)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
        return result

    @staticmethod
    def _clean_activity_focus(value: Optional[Dict[str, Any]]) -> Dict[str, Optional[str]]:
        value = value or {}
        if not isinstance(value, dict):
            raise ValueError("activity_focus 必须是对象")
        return {
            "chapter_focus": TopicRecommendationService._clean_optional_string(value.get("chapter_focus")),
            "training_focus": TopicRecommendationService._clean_optional_string(value.get("training_focus")),
            "classroom_scene": TopicRecommendationService._clean_optional_string(value.get("classroom_scene")),
        }

    @staticmethod
    def _preferred_count(value: Any) -> int:
        if value is None:
            return TopicRecommendationService.DEFAULT_PREFERRED_COUNT
        try:
            preferred_count = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("preferred_count 必须是整数") from exc
        preferred_count = max(TopicRecommendationService.MIN_CANDIDATE_COUNT, preferred_count)
        preferred_count = min(TopicRecommendationService.MAX_CANDIDATE_COUNT, preferred_count)
        return preferred_count

    @staticmethod
    def _extract_first_json(text: str) -> Any:
        if not text:
            raise ValueError("LLM 返回为空")
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except Exception:
            pass

        start_positions = [idx for idx, ch in enumerate(stripped) if ch in {"{", "["}]
        for start in start_positions:
            for end in range(len(stripped) - 1, start, -1):
                if stripped[end] not in {"}", "]"}:
                    continue
                snippet = stripped[start : end + 1]
                try:
                    return json.loads(snippet)
                except Exception:
                    continue
        raise ValueError("无法解析 LLM 返回的 JSON")

    @staticmethod
    def _summarize_text(text: Optional[str], *, limit: int = 180) -> Optional[str]:
        cleaned = " ".join((text or "").split())
        if not cleaned:
            return None
        return cleaned[:limit] + ("..." if len(cleaned) > limit else "")

    @staticmethod
    def _normalize_datetime_filter(value: Optional[str], *, field_name: str) -> Optional[datetime]:
        cleaned = TopicRecommendationService._clean_optional_string(value)
        if not cleaned:
            return None
        try:
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} 格式不正确，应为 ISO datetime 或 date") from exc

    @staticmethod
    def _apply_run_time_filters(
        query,
        *,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ):
        start_dt = TopicRecommendationService._normalize_datetime_filter(
            date_from,
            field_name="date_from",
        )
        end_dt = TopicRecommendationService._normalize_datetime_filter(
            date_to,
            field_name="date_to",
        )
        if start_dt and end_dt and start_dt > end_dt:
            raise ValueError("date_from 不能晚于 date_to")
        if start_dt is not None:
            query = query.filter(TopicRecommendationRun.created_at >= start_dt)
        if end_dt is not None:
            query = query.filter(TopicRecommendationRun.created_at <= end_dt)
        return query

    @staticmethod
    def _resolve_support_document_summaries(
        db: Session,
        support_document_ids: List[str],
    ) -> List[Dict[str, Any]]:
        if not support_document_ids:
            return []

        document_uuids = [
            TopicRecommendationService._uuid(item)
            for item in support_document_ids
        ]
        valid_document_uuids = [item for item in document_uuids if item is not None]
        if not valid_document_uuids:
            return []

        documents = (
            db.query(Document)
            .filter(Document.id.in_(valid_document_uuids))
            .all()
        )
        document_by_id = {str(document.id): document for document in documents}

        summaries: List[Dict[str, Any]] = []
        for raw_id in support_document_ids:
            document = document_by_id.get(str(raw_id))
            if document is None:
                summaries.append(
                    {
                        "document_id": raw_id,
                        "filename": None,
                        "summary": None,
                        "status": "missing",
                    }
                )
                continue

            summary = TopicRecommendationService._summarize_text(document.content)
            summaries.append(
                {
                    "document_id": str(document.id),
                    "filename": document.filename,
                    "summary": summary or "文档已上传，但当前尚未提取正文摘要。",
                    "status": document.embedding_status or "pending",
                }
            )
        return summaries

    @staticmethod
    def _build_context(
        teaching_design_payload: Dict[str, Any],
        *,
        mode: str,
        activity_focus: Dict[str, Optional[str]],
        objective: List[str],
        knowledge_points: List[str],
        support_summaries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        merged_objectives = teaching_design_payload.get("learning_objectives") or []
        if objective:
            merged_objectives = list(dict.fromkeys([*merged_objectives, *objective]))

        merged_knowledge_points = teaching_design_payload.get("knowledge_points") or []
        if knowledge_points:
            merged_knowledge_points = list(dict.fromkeys([*merged_knowledge_points, *knowledge_points]))

        return {
            "mode": mode,
            "course_title": teaching_design_payload.get("course_title"),
            "chapter_theme": teaching_design_payload.get("chapter_theme"),
            "learning_objectives": merged_objectives,
            "knowledge_points": merged_knowledge_points,
            "key_difficulties": teaching_design_payload.get("key_difficulties") or [],
            "capability_targets": teaching_design_payload.get("capability_targets") or [],
            "grade_level": teaching_design_payload.get("grade_level"),
            "time_constraints": teaching_design_payload.get("time_constraints"),
            "debate_focuses": teaching_design_payload.get("debate_focuses") or [],
            "forbidden_boundaries": teaching_design_payload.get("forbidden_boundaries") or [],
            "source_summary": teaching_design_payload.get("source_summary"),
            "activity_focus": activity_focus,
            "support_summaries": support_summaries,
        }

    @staticmethod
    def _infer_teaching_design_status(payload: Dict[str, Any]) -> str:
        status = TeachingDesignService.infer_extraction_status(payload)
        if status == "completed":
            return "available"
        if status == "partial":
            return "partial"
        return "insufficient"

    @staticmethod
    def _call_endpoint(api_endpoint: str) -> str:
        api_endpoint = api_endpoint.strip()
        if not api_endpoint:
            api_endpoint = f"{settings.OPENAI_BASE_URL}/chat/completions"
        if api_endpoint.endswith("/chat/completions"):
            return api_endpoint
        if api_endpoint.endswith("/v1") or api_endpoint.endswith("/compatible-mode/v1"):
            return f"{api_endpoint}/chat/completions"
        return f"{api_endpoint.rstrip('/')}/chat/completions"

    @staticmethod
    async def _request_llm_json(
        db: Session,
        *,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> Tuple[str, str]:
        config_service = ConfigService(db)
        model_config = await config_service.get_model_config()
        api_key = (model_config.api_key or "").strip() or (settings.OPENAI_API_KEY or "").strip()
        if not api_key:
            raise ValueError("未配置可用的 LLM API Key")

        endpoint = TopicRecommendationService._call_endpoint(model_config.api_endpoint or "")
        payload = {
            "model": (model_config.model_name or "").strip() or settings.OPENAI_MODEL_NAME,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": min(int(model_config.max_tokens or max_tokens), max_tokens),
        }
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code != 200:
            raise ValueError(f"LLM 调用失败: {response.status_code} - {response.text}")

        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return content, "llm"

    @staticmethod
    def _validate_candidates(
        raw_candidates: Any,
        *,
        preferred_count: int,
        context: Dict[str, Any],
        fallback_generated: bool = False,
    ) -> List[Dict[str, Any]]:
        if isinstance(raw_candidates, dict):
            raw_candidates = raw_candidates.get("candidates")
        if not isinstance(raw_candidates, list):
            raise ValueError("候选辩题结果不是数组")

        default_objectives = context.get("learning_objectives") or []
        default_knowledge_points = context.get("knowledge_points") or []
        default_scene = (
            (context.get("activity_focus") or {}).get("classroom_scene")
            or (context.get("activity_focus") or {}).get("chapter_focus")
            or "课堂讨论"
        )
        source_basis_defaults = []
        if context.get("course_title"):
            source_basis_defaults.append(f"课程：{context['course_title']}")
        if context.get("chapter_theme"):
            source_basis_defaults.append(f"章节：{context['chapter_theme']}")
        for item in context.get("support_summaries") or []:
            if item.get("filename"):
                source_basis_defaults.append(f"资料：{item['filename']}")

        seen_topics = set()
        validated: List[Dict[str, Any]] = []
        for raw_item in raw_candidates:
            if not isinstance(raw_item, dict):
                continue
            topic_text = TopicRecommendationService._clean_optional_string(raw_item.get("topic_text"))
            if not topic_text or topic_text in seen_topics:
                continue
            seen_topics.add(topic_text)

            course_objectives = TopicRecommendationService._clean_string_list(
                raw_item.get("course_objectives")
                if isinstance(raw_item.get("course_objectives"), list)
                else default_objectives
            ) or default_objectives
            knowledge_points = TopicRecommendationService._clean_string_list(
                raw_item.get("knowledge_points")
                if isinstance(raw_item.get("knowledge_points"), list)
                else default_knowledge_points
            ) or default_knowledge_points
            classroom_scene = (
                TopicRecommendationService._clean_optional_string(raw_item.get("classroom_scene"))
                or default_scene
            )
            debatability_reason = (
                TopicRecommendationService._clean_optional_string(raw_item.get("debatability_reason"))
                or "该题具备明确立场分歧，适合形成正反交锋。"
            )
            difficulty_level = (
                TopicRecommendationService._clean_optional_string(raw_item.get("difficulty_level"))
                or "medium"
            )
            recommendation_reason = (
                TopicRecommendationService._clean_optional_string(raw_item.get("recommendation_reason"))
                or "该题与当前教学目标和知识点存在较强对应关系。"
            )
            source_basis = raw_item.get("source_basis")
            if not isinstance(source_basis, list):
                source_basis = list(source_basis_defaults)
            source_basis = TopicRecommendationService._clean_string_list(source_basis) or list(source_basis_defaults)

            quality_flags: List[str] = []
            if not course_objectives:
                quality_flags.append("missing_course_objectives")
            if not knowledge_points:
                quality_flags.append("missing_knowledge_points")
            if fallback_generated:
                quality_flags.append("fallback_generated")

            quality_score = 60.0
            if course_objectives:
                quality_score += 15.0
            if knowledge_points:
                quality_score += 15.0
            if source_basis:
                quality_score += 10.0

            validated.append(
                {
                    "topic_text": topic_text,
                    "course_objectives": course_objectives,
                    "knowledge_points": knowledge_points,
                    "classroom_scene": classroom_scene,
                    "debatability_reason": debatability_reason,
                    "difficulty_level": difficulty_level,
                    "recommendation_reason": recommendation_reason,
                    "source_basis": source_basis,
                    "quality_score": min(100.0, quality_score),
                    "quality_flags": quality_flags,
                }
            )
            if len(validated) >= preferred_count:
                break

        if len(validated) < TopicRecommendationService.MIN_CANDIDATE_COUNT:
            raise ValueError("候选辩题数量不足")
        return validated

    @staticmethod
    def _build_llm_messages(
        *,
        context: Dict[str, Any],
        preferred_count: int,
        difficulty_preference: Optional[str],
    ) -> List[Dict[str, str]]:
        system_prompt = (
            "你是高校辩论式教学设计助手。请根据给定的课程教学设计和课堂活动目标，生成候选辩题。"
            "你只能输出 JSON，不要输出任何额外说明。"
            "输出格式固定为 {\"candidates\":[...]}。"
            "每个 candidate 必须包含 topic_text, course_objectives, knowledge_points, classroom_scene, "
            "debatability_reason, difficulty_level, recommendation_reason, source_basis。"
            "辩题必须具有明确的正反立场，避免过空、过泛、无法交锋。"
        )
        user_payload = {
            "preferred_count": preferred_count,
            "difficulty_preference": difficulty_preference or "mixed",
            "context": context,
        }
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]

    @staticmethod
    def _build_repair_messages(
        *,
        raw_content: str,
        preferred_count: int,
    ) -> List[Dict[str, str]]:
        system_prompt = (
            "你是 JSON 修复助手。请把用户提供的内容整理成严格 JSON。"
            "只输出 JSON，不要输出任何解释。"
            "格式必须是 {\"candidates\":[...]}，且 candidates 至少包含 "
            f"{TopicRecommendationService.MIN_CANDIDATE_COUNT} 条，不超过 {preferred_count} 条。"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_content},
        ]

    @staticmethod
    def _build_fallback_candidates(
        context: Dict[str, Any],
        *,
        preferred_count: int,
        difficulty_preference: Optional[str],
    ) -> List[Dict[str, Any]]:
        chapter_theme = context.get("chapter_theme") or context.get("course_title") or "本单元内容"
        knowledge_points = context.get("knowledge_points") or ["核心概念", "应用场景", "问题边界"]
        objectives = context.get("learning_objectives") or context.get("capability_targets") or ["培养论证能力"]
        scene = (
            (context.get("activity_focus") or {}).get("classroom_scene")
            or (context.get("activity_focus") or {}).get("chapter_focus")
            or "课堂讨论"
        )
        training_focus = (context.get("activity_focus") or {}).get("training_focus") or "辩论训练"

        topics: List[Dict[str, Any]] = []
        templates = [
            "围绕{knowledge_point}的学习，课堂更应强调{objective}还是{training_focus}？",
            "在{chapter_theme}教学中，是否应将{knowledge_point}作为课堂辩论的核心判断标准？",
            "针对{knowledge_point}的理解与应用，学生应优先追求规范准确还是开放创新？",
            "在{scene}情境下，{chapter_theme}相关问题更适合通过立场辩论还是协作共识来推进学习？",
            "围绕{chapter_theme}，课堂讨论应优先关注{knowledge_point}的理论阐释还是现实应用？",
        ]

        for index, template in enumerate(templates):
            knowledge_point = knowledge_points[index % len(knowledge_points)]
            objective = objectives[index % len(objectives)]
            topic_text = template.format(
                knowledge_point=knowledge_point,
                objective=objective,
                training_focus=training_focus,
                chapter_theme=chapter_theme,
                scene=scene,
            )
            topics.append(
                {
                    "topic_text": topic_text,
                    "course_objectives": [objective],
                    "knowledge_points": [knowledge_point],
                    "classroom_scene": scene,
                    "debatability_reason": "题目含有可比较的价值取向或策略取向，能够形成正反立场。",
                    "difficulty_level": difficulty_preference or ("medium" if index < 2 else "high"),
                    "recommendation_reason": f"该题直接对应 {chapter_theme} 的学习重点，并能服务于 {training_focus}。",
                    "source_basis": [
                        f"章节主题：{chapter_theme}",
                        f"知识点：{knowledge_point}",
                        f"学习目标：{objective}",
                    ],
                }
            )
            if len(topics) >= preferred_count:
                break
        return topics

    @staticmethod
    def _serialize_item(item: TopicRecommendationItem) -> Dict[str, Any]:
        return TopicRecommendationService._serialize_item_with_adoption(item, adoption_stats=None)

    @staticmethod
    def _empty_adoption_summary() -> Dict[str, Any]:
        return {
            "total_adoptions": 0,
            "direct_adoptions": 0,
            "edited_adoptions": 0,
            "debate_adoptions": 0,
            "reservation_adoptions": 0,
            "distinct_candidates_adopted": 0,
            "last_adopted_at": None,
        }

    @staticmethod
    def _empty_candidate_adoption_stats() -> Dict[str, Any]:
        return {
            "is_adopted": False,
            "total_adoptions": 0,
            "direct_adoptions": 0,
            "edited_adoptions": 0,
            "debate_adoptions": 0,
            "reservation_adoptions": 0,
            "last_adopted_at": None,
        }

    @staticmethod
    def _build_candidate_leaderboards(
        runs: List[TopicRecommendationRun],
        adoption_index: Dict[str, Dict[str, Any]],
        *,
        top_n: int = 5,
    ) -> Dict[str, List[Dict[str, Any]]]:
        candidates: List[Dict[str, Any]] = []
        for run in runs:
            run_id = str(run.id)
            run_adoption = adoption_index.get(run_id, {})
            candidate_index = run_adoption.get("candidates") or {}
            for item in sorted(run.items, key=lambda current: current.candidate_order):
                stats = dict(
                    TopicRecommendationService._empty_candidate_adoption_stats(),
                    **(candidate_index.get(str(item.id)) or {}),
                )
                candidates.append(
                    {
                        "run_id": run_id,
                        "candidate_id": str(item.id),
                        "candidate_order": item.candidate_order,
                        "topic_text": item.topic_text,
                        "difficulty_level": item.difficulty_level,
                        "recommendation_reason": item.recommendation_reason,
                        "total_adoptions": stats["total_adoptions"],
                        "direct_adoptions": stats["direct_adoptions"],
                        "edited_adoptions": stats["edited_adoptions"],
                        "debate_adoptions": stats["debate_adoptions"],
                        "reservation_adoptions": stats["reservation_adoptions"],
                        "last_adopted_at": stats["last_adopted_at"],
                    }
                )

        top_n = max(1, min(int(top_n or 5), 20))
        top_adopted = sorted(
            candidates,
            key=lambda item: (
                item["total_adoptions"],
                item["direct_adoptions"],
                item["last_adopted_at"] or "",
            ),
            reverse=True,
        )[:top_n]
        top_edited = sorted(
            candidates,
            key=lambda item: (
                item["edited_adoptions"],
                item["total_adoptions"],
                item["last_adopted_at"] or "",
            ),
            reverse=True,
        )[:top_n]

        return {
            "top_adopted_candidates": top_adopted,
            "top_edited_candidates": top_edited,
        }

    @staticmethod
    def _build_candidate_observations(
        runs: List[TopicRecommendationRun],
        adoption_index: Dict[str, Dict[str, Any]],
        *,
        top_n: int = 5,
        min_quality_score: float = 80.0,
    ) -> Dict[str, List[Dict[str, Any]]]:
        candidates: List[Dict[str, Any]] = []
        for run in runs:
            run_id = str(run.id)
            run_adoption = adoption_index.get(run_id, {})
            candidate_index = run_adoption.get("candidates") or {}
            for item in sorted(run.items, key=lambda current: current.candidate_order):
                stats = dict(
                    TopicRecommendationService._empty_candidate_adoption_stats(),
                    **(candidate_index.get(str(item.id)) or {}),
                )
                quality_score = float(item.quality_score or 0.0)
                candidates.append(
                    {
                        "run_id": run_id,
                        "candidate_id": str(item.id),
                        "candidate_order": item.candidate_order,
                        "topic_text": item.topic_text,
                        "difficulty_level": item.difficulty_level,
                        "recommendation_reason": item.recommendation_reason,
                        "quality_score": quality_score,
                        "quality_flags": item.quality_flags or [],
                        "total_adoptions": stats["total_adoptions"],
                        "direct_adoptions": stats["direct_adoptions"],
                        "edited_adoptions": stats["edited_adoptions"],
                        "last_adopted_at": stats["last_adopted_at"],
                    }
                )

        top_n = max(1, min(int(top_n or 5), 20))
        high_quality_low_adoption = [
            item for item in candidates
            if item["quality_score"] >= float(min_quality_score) and item["total_adoptions"] == 0
        ]
        high_quality_low_adoption.sort(
            key=lambda item: (
                item["quality_score"],
                -(item["candidate_order"] or 0),
                item["topic_text"] or "",
            ),
            reverse=True,
        )
        high_quality_edited_only = [
            item for item in candidates
            if item["quality_score"] >= float(min_quality_score)
            and item["edited_adoptions"] > 0
            and item["direct_adoptions"] == 0
        ]
        high_quality_edited_only.sort(
            key=lambda item: (
                item["edited_adoptions"],
                item["quality_score"],
                item["last_adopted_at"] or "",
            ),
            reverse=True,
        )

        return {
            "high_quality_low_adoption_candidates": high_quality_low_adoption[:top_n],
            "high_quality_edited_only_candidates": high_quality_edited_only[:top_n],
        }

    @staticmethod
    def _build_version_breakdown(
        runs: List[TopicRecommendationRun],
        adoption_index: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        version_map: Dict[str, Dict[str, Any]] = {}

        for run in runs:
            version_id = str(run.teaching_design_version_id) if run.teaching_design_version_id else "unbound"
            version_info = version_map.setdefault(
                version_id,
                {
                    "teaching_design_version_id": None if version_id == "unbound" else version_id,
                    "version_name": None,
                    "title": None,
                    "is_active": None,
                    "total_runs": 0,
                    "total_candidates": 0,
                    "adopted_run_count": 0,
                    "adopted_candidate_count": 0,
                    "total_adoptions": 0,
                    "direct_adoptions": 0,
                    "edited_adoptions": 0,
                    "run_adoption_rate": 0.0,
                    "candidate_adoption_rate": 0.0,
                    "last_generated_at": None,
                    "last_adopted_at": None,
                },
            )

            if run.teaching_design_version is not None:
                version_info["version_name"] = run.teaching_design_version.version_name
                version_info["title"] = run.teaching_design_version.title
                version_info["is_active"] = run.teaching_design_version.is_active

            version_info["total_runs"] += 1
            items = sorted(run.items, key=lambda current: current.candidate_order)
            version_info["total_candidates"] += len(items)

            run_adoption = adoption_index.get(str(run.id), {})
            summary = run_adoption.get("summary") or TopicRecommendationService._empty_adoption_summary()
            if summary.get("total_adoptions", 0) > 0:
                version_info["adopted_run_count"] += 1
            version_info["adopted_candidate_count"] += int(summary.get("distinct_candidates_adopted", 0) or 0)
            version_info["total_adoptions"] += int(summary.get("total_adoptions", 0) or 0)
            version_info["direct_adoptions"] += int(summary.get("direct_adoptions", 0) or 0)
            version_info["edited_adoptions"] += int(summary.get("edited_adoptions", 0) or 0)

            generated_at = run.created_at.isoformat() if run.created_at else None
            if generated_at and (
                version_info["last_generated_at"] is None
                or generated_at > version_info["last_generated_at"]
            ):
                version_info["last_generated_at"] = generated_at

            last_adopted_at = summary.get("last_adopted_at")
            if last_adopted_at and (
                version_info["last_adopted_at"] is None
                or last_adopted_at > version_info["last_adopted_at"]
            ):
                version_info["last_adopted_at"] = last_adopted_at

        result: List[Dict[str, Any]] = []
        for item in version_map.values():
            total_runs = int(item["total_runs"] or 0)
            total_candidates = int(item["total_candidates"] or 0)
            item["run_adoption_rate"] = round(
                item["adopted_run_count"] / total_runs,
                4,
            ) if total_runs else 0.0
            item["candidate_adoption_rate"] = round(
                item["adopted_candidate_count"] / total_candidates,
                4,
            ) if total_candidates else 0.0
            result.append(item)

        result.sort(
            key=lambda item: (
                item["total_runs"],
                item["last_generated_at"] or "",
            ),
            reverse=True,
        )
        return result

    @staticmethod
    def _build_version_comparison_summary(
        version_breakdown: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        comparable = [
            item for item in version_breakdown
            if item.get("teaching_design_version_id") is not None
        ]
        if len(comparable) < 2:
            return None

        current = comparable[0]
        previous = comparable[1]

        current_total_runs = int(current.get("total_runs") or 0)
        previous_total_runs = int(previous.get("total_runs") or 0)
        current_total_adoptions = int(current.get("total_adoptions") or 0)
        previous_total_adoptions = int(previous.get("total_adoptions") or 0)
        current_direct_adoptions = int(current.get("direct_adoptions") or 0)
        previous_direct_adoptions = int(previous.get("direct_adoptions") or 0)
        current_edited_adoptions = int(current.get("edited_adoptions") or 0)
        previous_edited_adoptions = int(previous.get("edited_adoptions") or 0)

        current_direct_adoption_rate = round(
            current_direct_adoptions / current_total_adoptions,
            4,
        ) if current_total_adoptions else 0.0
        previous_direct_adoption_rate = round(
            previous_direct_adoptions / previous_total_adoptions,
            4,
        ) if previous_total_adoptions else 0.0
        current_edited_adoption_rate = round(
            current_edited_adoptions / current_total_adoptions,
            4,
        ) if current_total_adoptions else 0.0
        previous_edited_adoption_rate = round(
            previous_edited_adoptions / previous_total_adoptions,
            4,
        ) if previous_total_adoptions else 0.0

        return {
            "current_version": current,
            "previous_version": previous,
            "delta": {
                "total_runs": current_total_runs - previous_total_runs,
                "total_adoptions": current_total_adoptions - previous_total_adoptions,
                "direct_adoptions": current_direct_adoptions - previous_direct_adoptions,
                "edited_adoptions": current_edited_adoptions - previous_edited_adoptions,
                "run_adoption_rate": round(
                    float(current.get("run_adoption_rate") or 0.0)
                    - float(previous.get("run_adoption_rate") or 0.0),
                    4,
                ),
                "candidate_adoption_rate": round(
                    float(current.get("candidate_adoption_rate") or 0.0)
                    - float(previous.get("candidate_adoption_rate") or 0.0),
                    4,
                ),
                "direct_adoption_share": round(
                    current_direct_adoption_rate - previous_direct_adoption_rate,
                    4,
                ),
                "edited_adoption_share": round(
                    current_edited_adoption_rate - previous_edited_adoption_rate,
                    4,
                ),
            },
        }

    @staticmethod
    def _build_version_comparison_summary_for_pair(
        version_breakdown: List[Dict[str, Any]],
        *,
        current_version_id: Optional[str] = None,
        previous_version_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not current_version_id and not previous_version_id:
            return TopicRecommendationService._build_version_comparison_summary(version_breakdown)

        breakdown_by_id = {
            item["teaching_design_version_id"]: item
            for item in version_breakdown
            if item.get("teaching_design_version_id") is not None
        }

        current = breakdown_by_id.get(current_version_id) if current_version_id else None
        previous = breakdown_by_id.get(previous_version_id) if previous_version_id else None

        if current_version_id and current is None:
            raise ValueError("current_version_id 不存在于当前统计范围内")
        if previous_version_id and previous is None:
            raise ValueError("previous_version_id 不存在于当前统计范围内")

        if current is None and previous is not None:
            comparable = [item for item in version_breakdown if item.get("teaching_design_version_id") is not None]
            current = next((item for item in comparable if item["teaching_design_version_id"] != previous["teaching_design_version_id"]), None)
        if previous is None and current is not None:
            comparable = [item for item in version_breakdown if item.get("teaching_design_version_id") is not None]
            previous = next((item for item in comparable if item["teaching_design_version_id"] != current["teaching_design_version_id"]), None)

        if current is None or previous is None:
            return None

        return TopicRecommendationService._build_version_comparison_summary([current, previous])

    @staticmethod
    def _extract_topic_provenance(debate: Debate) -> Optional[Dict[str, str]]:
        report = debate.report if isinstance(debate.report, dict) else {}
        room_meta = report.get(TopicRecommendationService.ROOM_META_KEY)
        if not isinstance(room_meta, dict):
            return None
        config_meta = room_meta.get(TopicRecommendationService.DEBATE_CONFIG_META_KEY)
        if not isinstance(config_meta, dict):
            return None

        run_id = TopicRecommendationService._clean_optional_string(config_meta.get("topic_recommendation_run_id"))
        candidate_id = TopicRecommendationService._clean_optional_string(config_meta.get("selected_topic_candidate_id"))
        topic_source = TopicRecommendationService._clean_optional_string(config_meta.get("topic_source")) or "manual"
        if not run_id or not candidate_id:
            return None
        if topic_source not in {"ai_recommended", "ai_recommended_edited"}:
            return None
        return {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "topic_source": topic_source,
        }

    @staticmethod
    def _build_adoption_index(
        db: Session,
        *,
        class_id: str,
        run_ids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        if not run_ids:
            return {}

        class_uuid = TopicRecommendationService._uuid(class_id)
        if class_uuid is None:
            return {}

        safe_run_ids = {run_id for run_id in run_ids if TopicRecommendationService._uuid(run_id) is not None}
        if not safe_run_ids:
            return {}

        run_index: Dict[str, Dict[str, Any]] = {
            run_id: {
                "summary": TopicRecommendationService._empty_adoption_summary(),
                "candidates": {},
            }
            for run_id in safe_run_ids
        }

        debates = db.query(Debate).filter(Debate.class_id == class_uuid).all()
        for debate in debates:
            provenance = TopicRecommendationService._extract_topic_provenance(debate)
            if not provenance:
                continue

            run_id = provenance["run_id"]
            candidate_id = provenance["candidate_id"]
            topic_source = provenance["topic_source"]
            if run_id not in run_index:
                continue

            is_reservation = str(getattr(debate, "mode", "")) == "teacher_reserved"
            adopted_at = debate.created_at.isoformat() if debate.created_at else None

            run_stats = run_index[run_id]["summary"]
            run_stats["total_adoptions"] += 1
            if topic_source == "ai_recommended":
                run_stats["direct_adoptions"] += 1
            else:
                run_stats["edited_adoptions"] += 1
            if is_reservation:
                run_stats["reservation_adoptions"] += 1
            else:
                run_stats["debate_adoptions"] += 1
            if adopted_at and (
                run_stats["last_adopted_at"] is None or adopted_at > run_stats["last_adopted_at"]
            ):
                run_stats["last_adopted_at"] = adopted_at

            candidate_stats = run_index[run_id]["candidates"].setdefault(
                candidate_id,
                TopicRecommendationService._empty_candidate_adoption_stats(),
            )
            candidate_stats["is_adopted"] = True
            candidate_stats["total_adoptions"] += 1
            if topic_source == "ai_recommended":
                candidate_stats["direct_adoptions"] += 1
            else:
                candidate_stats["edited_adoptions"] += 1
            if is_reservation:
                candidate_stats["reservation_adoptions"] += 1
            else:
                candidate_stats["debate_adoptions"] += 1
            if adopted_at and (
                candidate_stats["last_adopted_at"] is None or adopted_at > candidate_stats["last_adopted_at"]
            ):
                candidate_stats["last_adopted_at"] = adopted_at

        for run_id, payload in run_index.items():
            payload["summary"]["distinct_candidates_adopted"] = len(payload["candidates"])
        return run_index

    @staticmethod
    def _serialize_item_with_adoption(
        item: TopicRecommendationItem,
        *,
        adoption_stats: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        candidate_adoption_stats = dict(TopicRecommendationService._empty_candidate_adoption_stats())
        if isinstance(adoption_stats, dict):
            candidate_adoption_stats.update(adoption_stats)
        return {
            "candidate_id": str(item.id),
            "candidate_order": item.candidate_order,
            "topic_text": item.topic_text,
            "mapped_course_objectives": item.course_objectives or [],
            "mapped_knowledge_points": item.knowledge_points or [],
            "recommended_classroom_scene": item.classroom_scene,
            "evidence_basis": item.source_basis or [],
            "course_objectives": item.course_objectives or [],
            "knowledge_points": item.knowledge_points or [],
            "classroom_scene": item.classroom_scene,
            "debatability_reason": item.debatability_reason,
            "difficulty_level": item.difficulty_level,
            "recommendation_reason": item.recommendation_reason,
            "source_basis": item.source_basis or [],
            "quality_score": item.quality_score,
            "quality_flags": item.quality_flags or [],
            "adoption_stats": candidate_adoption_stats,
        }

    @staticmethod
    def _serialize_response_status(run: TopicRecommendationRun) -> str:
        if run.status == TopicRecommendationService.RESPONSE_STATUS_UNAVAILABLE:
            return TopicRecommendationService.RESPONSE_STATUS_UNAVAILABLE
        if run.status in {
            TopicRecommendationService.RESPONSE_STATUS_READY,
            TopicRecommendationService.RESPONSE_STATUS_PARTIAL,
        }:
            return run.status
        if run.teaching_design_status in {"partial", "insufficient"}:
            return TopicRecommendationService.RESPONSE_STATUS_PARTIAL
        return TopicRecommendationService.RESPONSE_STATUS_READY

    @staticmethod
    def _serialize_run(
        run: TopicRecommendationRun,
        *,
        adoption_index: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        response_status = TopicRecommendationService._serialize_response_status(run)
        run_adoption = (adoption_index or {}).get(str(run.id), {})
        candidate_index = run_adoption.get("candidates") or {}
        return {
            "run_id": str(run.id),
            "recommendation_run_id": str(run.id),
            "status": response_status,
            "legacy_status": run.status,
            "teaching_design_status": run.teaching_design_status,
            "teaching_design_version_id": str(run.teaching_design_version_id) if run.teaching_design_version_id else None,
            "mode": run.mode,
            "activity_focus": ((run.request_payload or {}).get("activity_focus") or {}),
            "generation_source": run.provider,
            "provider": run.provider,
            "generation_quality": run.generation_quality,
            "retry_count": run.retry_count,
            "warnings": run.warnings or [],
            "generated_at": run.created_at.isoformat() if run.created_at else None,
            "adoption_summary": dict(
                TopicRecommendationService._empty_adoption_summary(),
                **(run_adoption.get("summary") or {}),
            ),
            "candidates": [
                TopicRecommendationService._serialize_item_with_adoption(
                    item,
                    adoption_stats=candidate_index.get(str(item.id)),
                )
                for item in sorted(run.items, key=lambda current: current.candidate_order)
            ],
        }

    @staticmethod
    def _serialize_run_summary(
        run: TopicRecommendationRun,
        *,
        adoption_index: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        response_status = TopicRecommendationService._serialize_response_status(run)
        items = sorted(run.items, key=lambda current: current.candidate_order)
        run_adoption = (adoption_index or {}).get(str(run.id), {})
        return {
            "run_id": str(run.id),
            "recommendation_run_id": str(run.id),
            "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
            "status": response_status,
            "legacy_status": run.status,
            "teaching_design_status": run.teaching_design_status,
            "teaching_design_version_id": str(run.teaching_design_version_id) if run.teaching_design_version_id else None,
            "mode": run.mode,
            "activity_focus": ((run.request_payload or {}).get("activity_focus") or {}),
            "generation_source": run.provider,
            "provider": run.provider,
            "generation_quality": run.generation_quality,
            "retry_count": run.retry_count,
            "preferred_count": run.preferred_count,
            "difficulty_preference": run.difficulty_preference,
            "warnings": run.warnings or [],
            "generated_at": run.created_at.isoformat() if run.created_at else None,
            "candidate_count": len(items),
            "candidate_topics": [item.topic_text for item in items[:3] if item.topic_text],
            "adoption_summary": dict(
                TopicRecommendationService._empty_adoption_summary(),
                **(run_adoption.get("summary") or {}),
            ),
        }

    @staticmethod
    async def generate_recommendations(
        db: Session,
        *,
        class_id: str,
        created_by: Optional[str],
        teaching_design_version_id: Optional[str] = None,
        mode: Optional[str] = None,
        activity_focus: Optional[Dict[str, Any]] = None,
        objective: Optional[List[str]] = None,
        knowledge_points: Optional[List[str]] = None,
        support_document_ids: Optional[List[str]] = None,
        preferred_count: Optional[int] = None,
        difficulty_preference: Optional[str] = None,
        regenerate_from_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        class_uuid = TopicRecommendationService._uuid(class_id)
        if class_uuid is None:
            raise ValueError("无效的班级ID")

        parent_run: Optional[TopicRecommendationRun] = None
        if regenerate_from_run_id:
            parent_run = (
                db.query(TopicRecommendationRun)
                .filter(TopicRecommendationRun.id == TopicRecommendationService._uuid(regenerate_from_run_id))
                .first()
            )
            if parent_run is None:
                raise ValueError("待重新生成的候选辩题记录不存在")
            if str(parent_run.class_id) != str(class_uuid):
                raise ValueError("待重新生成的候选辩题记录不属于当前班级")

        parent_payload = parent_run.request_payload if parent_run and isinstance(parent_run.request_payload, dict) else {}
        inherited_mode = TopicRecommendationService._clean_optional_string(mode)
        if inherited_mode is None and parent_run is not None:
            inherited_mode = TopicRecommendationService._clean_optional_string(parent_run.mode)
        normalized_mode = inherited_mode or "competition"
        if normalized_mode not in TopicRecommendationService.ALLOWED_MODES:
            raise ValueError("mode 仅支持 competition 或 teaching")

        inherited_difficulty = TopicRecommendationService._clean_optional_string(difficulty_preference)
        if inherited_difficulty is None and parent_run is not None:
            inherited_difficulty = TopicRecommendationService._clean_optional_string(parent_run.difficulty_preference)
        normalized_difficulty = inherited_difficulty
        if normalized_difficulty and normalized_difficulty not in TopicRecommendationService.ALLOWED_DIFFICULTY:
            raise ValueError("difficulty_preference 不合法")

        inherited_preferred_count = preferred_count
        if inherited_preferred_count is None and parent_run is not None:
            inherited_preferred_count = parent_run.preferred_count
        preferred_count = TopicRecommendationService._preferred_count(inherited_preferred_count)

        inherited_activity_focus = activity_focus
        if inherited_activity_focus is None and parent_payload:
            inherited_activity_focus = parent_payload.get("activity_focus")
        normalized_activity_focus = TopicRecommendationService._clean_activity_focus(inherited_activity_focus)

        inherited_objective = objective
        if inherited_objective is None and parent_payload:
            inherited_objective = parent_payload.get("objective")
        normalized_objective = TopicRecommendationService._clean_string_list(inherited_objective)

        inherited_knowledge_points = knowledge_points
        if inherited_knowledge_points is None and parent_payload:
            inherited_knowledge_points = parent_payload.get("knowledge_points")
        normalized_knowledge_points = TopicRecommendationService._clean_string_list(inherited_knowledge_points)

        inherited_support_document_ids = support_document_ids
        if inherited_support_document_ids is None and parent_payload:
            inherited_support_document_ids = parent_payload.get("support_document_ids")
        normalized_support_document_ids = TopicRecommendationService._clean_string_list(inherited_support_document_ids)

        teaching_design = None
        if teaching_design_version_id:
            teaching_design = TeachingDesignService.get_version_by_id(db, teaching_design_version_id)
            if teaching_design is None:
                raise ValueError("教学设计版本不存在")
            if teaching_design and str(teaching_design.class_id) != str(class_uuid):
                raise ValueError("教学设计版本不属于当前班级")
        elif parent_run is not None and parent_run.teaching_design_version_id is not None:
            teaching_design = TeachingDesignService.get_version_by_id(db, str(parent_run.teaching_design_version_id))
        else:
            teaching_design = TeachingDesignService.get_active_version(db, class_id)

        if teaching_design is None:
            return {
                "run_id": None,
                "recommendation_run_id": None,
                "status": "unavailable",
                "legacy_status": "unavailable",
                "teaching_design_status": "missing",
                "teaching_design_version_id": None,
                "mode": normalized_mode,
                "activity_focus": normalized_activity_focus,
                "generation_source": "none",
                "provider": "none",
                "generation_quality": "unavailable",
                "retry_count": 0,
                "warnings": ["当前班级尚未配置教学设计，暂无法生成候选辩题。"],
                "generated_at": None,
                "candidates": [],
            }

        teaching_design_payload = TeachingDesignService.normalize_payload(
            teaching_design.extracted_payload or {}
        )
        teaching_design_status = TopicRecommendationService._infer_teaching_design_status(teaching_design_payload)
        support_summaries = TopicRecommendationService._resolve_support_document_summaries(
            db,
            normalized_support_document_ids,
        )
        context = TopicRecommendationService._build_context(
            teaching_design_payload,
            mode=normalized_mode,
            activity_focus=normalized_activity_focus,
            objective=normalized_objective,
            knowledge_points=normalized_knowledge_points,
            support_summaries=support_summaries,
        )

        warnings: List[str] = []
        if teaching_design_status == "partial":
            warnings.append("当前教学设计抽取结果不完整，本次推荐基于部分字段生成。")
        elif teaching_design_status == "insufficient":
            warnings.append("当前教学设计有效字段不足，本次推荐将更多依赖模板化补全。")
        if normalized_support_document_ids and not any(item.get("summary") for item in support_summaries):
            warnings.append("本次未使用到有效的支持材料摘要。")

        provider = "fallback"
        generation_quality = "fallback"
        retry_count = 0
        candidates_payload: List[Dict[str, Any]]

        raw_content: Optional[str] = None
        try:
            raw_content, provider = await TopicRecommendationService._request_llm_json(
                db,
                messages=TopicRecommendationService._build_llm_messages(
                    context=context,
                    preferred_count=preferred_count,
                    difficulty_preference=normalized_difficulty,
                ),
            )
            parsed = TopicRecommendationService._extract_first_json(raw_content)
            candidates_payload = TopicRecommendationService._validate_candidates(
                parsed,
                preferred_count=preferred_count,
                context=context,
            )
            generation_quality = "validated"
        except Exception:
            if raw_content:
                try:
                    retry_count = 1
                    repaired_content, provider = await TopicRecommendationService._request_llm_json(
                        db,
                        messages=TopicRecommendationService._build_repair_messages(
                            raw_content=raw_content,
                            preferred_count=preferred_count,
                        ),
                        temperature=0.0,
                        max_tokens=900,
                    )
                    parsed = TopicRecommendationService._extract_first_json(repaired_content)
                    candidates_payload = TopicRecommendationService._validate_candidates(
                        parsed,
                        preferred_count=preferred_count,
                        context=context,
                    )
                    generation_quality = "repaired"
                except Exception:
                    retry_count = 2
                    warnings.append("LLM 输出不稳定，已使用模板化候选辩题降级结果。")
                    candidates_payload = TopicRecommendationService._validate_candidates(
                        TopicRecommendationService._build_fallback_candidates(
                            context,
                            preferred_count=preferred_count,
                            difficulty_preference=normalized_difficulty,
                        ),
                        preferred_count=preferred_count,
                        context=context,
                        fallback_generated=True,
                    )
                    provider = "fallback"
                    generation_quality = "fallback"
            else:
                warnings.append("当前无法使用 LLM 服务，已使用模板化候选辩题降级结果。")
                candidates_payload = TopicRecommendationService._validate_candidates(
                    TopicRecommendationService._build_fallback_candidates(
                        context,
                        preferred_count=preferred_count,
                        difficulty_preference=normalized_difficulty,
                    ),
                    preferred_count=preferred_count,
                    context=context,
                    fallback_generated=True,
                )
                provider = "fallback"
                generation_quality = "fallback"

        run = TopicRecommendationRun(
            parent_run_id=parent_run.id if parent_run is not None else None,
            class_id=class_uuid,
            teaching_design_version_id=teaching_design.id,
            created_by=TopicRecommendationService._uuid(created_by),
            mode=normalized_mode,
            status=(
                TopicRecommendationService.RESPONSE_STATUS_PARTIAL
                if teaching_design_status in {"partial", "insufficient"}
                else TopicRecommendationService.RESPONSE_STATUS_READY
            ),
            teaching_design_status=teaching_design_status,
            provider=provider,
            generation_quality=generation_quality,
            retry_count=retry_count,
            preferred_count=preferred_count,
            difficulty_preference=normalized_difficulty,
            request_payload={
                "activity_focus": normalized_activity_focus,
                "objective": normalized_objective,
                "knowledge_points": normalized_knowledge_points,
                "support_document_ids": normalized_support_document_ids,
            },
            context_snapshot=context,
            warnings=warnings,
        )
        db.add(run)
        db.flush()

        for index, candidate in enumerate(candidates_payload, start=1):
            db.add(
                TopicRecommendationItem(
                    run_id=run.id,
                    candidate_order=index,
                    topic_text=candidate["topic_text"],
                    course_objectives=candidate["course_objectives"],
                    knowledge_points=candidate["knowledge_points"],
                    classroom_scene=candidate["classroom_scene"],
                    debatability_reason=candidate["debatability_reason"],
                    difficulty_level=candidate["difficulty_level"],
                    recommendation_reason=candidate["recommendation_reason"],
                    source_basis=candidate["source_basis"],
                    quality_score=candidate["quality_score"],
                    quality_flags=candidate["quality_flags"],
                )
            )

        db.commit()
        db.refresh(run)
        return TopicRecommendationService._serialize_run(run)

    @staticmethod
    def get_run(
        db: Session,
        *,
        run_id: str,
        created_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        run_uuid = TopicRecommendationService._uuid(run_id)
        if run_uuid is None:
            return None
        query = db.query(TopicRecommendationRun).filter(TopicRecommendationRun.id == run_uuid)
        creator_uuid = TopicRecommendationService._uuid(created_by)
        if creator_uuid is not None:
            query = query.filter(TopicRecommendationRun.created_by == creator_uuid)
        run = query.first()
        if run is None:
            return None
        adoption_index = TopicRecommendationService._build_adoption_index(
            db,
            class_id=str(run.class_id),
            run_ids=[str(run.id)],
        )
        return TopicRecommendationService._serialize_run(run, adoption_index=adoption_index)

    @staticmethod
    def list_runs(
        db: Session,
        *,
        class_id: str,
        created_by: Optional[str] = None,
        limit: int = 20,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        class_uuid = TopicRecommendationService._uuid(class_id)
        if class_uuid is None:
            raise ValueError("无效的班级ID")

        query = (
            db.query(TopicRecommendationRun)
            .filter(TopicRecommendationRun.class_id == class_uuid)
            .order_by(TopicRecommendationRun.created_at.desc())
        )
        creator_uuid = TopicRecommendationService._uuid(created_by)
        if creator_uuid is not None:
            query = query.filter(TopicRecommendationRun.created_by == creator_uuid)
        query = TopicRecommendationService._apply_run_time_filters(
            query,
            date_from=date_from,
            date_to=date_to,
        )

        safe_limit = max(1, min(int(limit or 20), 100))
        runs = query.limit(safe_limit).all()
        adoption_index = TopicRecommendationService._build_adoption_index(
            db,
            class_id=class_id,
            run_ids=[str(run.id) for run in runs],
        )
        return [
            TopicRecommendationService._serialize_run_summary(run, adoption_index=adoption_index)
            for run in runs
        ]

    @staticmethod
    def get_class_analytics(
        db: Session,
        *,
        class_id: str,
        created_by: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        class_uuid = TopicRecommendationService._uuid(class_id)
        if class_uuid is None:
            raise ValueError("鏃犳晥鐨勭彮绾D")

        query = (
            db.query(TopicRecommendationRun)
            .filter(TopicRecommendationRun.class_id == class_uuid)
            .order_by(TopicRecommendationRun.created_at.desc())
        )
        creator_uuid = TopicRecommendationService._uuid(created_by)
        if creator_uuid is not None:
            query = query.filter(TopicRecommendationRun.created_by == creator_uuid)
        query = TopicRecommendationService._apply_run_time_filters(
            query,
            date_from=date_from,
            date_to=date_to,
        )

        runs = query.all()
        run_ids = [str(run.id) for run in runs]
        adoption_index = TopicRecommendationService._build_adoption_index(
            db,
            class_id=class_id,
            run_ids=run_ids,
        )

        quality_counts = {
            "validated": 0,
            "repaired": 0,
            "fallback": 0,
        }
        provider_counts: Dict[str, int] = {}
        status_counts: Dict[str, int] = {
            TopicRecommendationService.RESPONSE_STATUS_READY: 0,
            TopicRecommendationService.RESPONSE_STATUS_PARTIAL: 0,
            TopicRecommendationService.RESPONSE_STATUS_UNAVAILABLE: 0,
        }

        total_candidates = 0
        adopted_run_count = 0
        adopted_candidate_count = 0
        total_adoptions = 0
        direct_adoptions = 0
        edited_adoptions = 0
        debate_adoptions = 0
        reservation_adoptions = 0
        last_generated_at: Optional[str] = None
        last_adopted_at: Optional[str] = None

        for run in runs:
            response_status = TopicRecommendationService._serialize_response_status(run)
            status_counts[response_status] = status_counts.get(response_status, 0) + 1

            generation_quality = TopicRecommendationService._clean_optional_string(run.generation_quality) or "fallback"
            if generation_quality not in quality_counts:
                quality_counts[generation_quality] = 0
            quality_counts[generation_quality] += 1

            provider = TopicRecommendationService._clean_optional_string(run.provider) or "unknown"
            provider_counts[provider] = provider_counts.get(provider, 0) + 1

            items = sorted(run.items, key=lambda current: current.candidate_order)
            total_candidates += len(items)

            run_adoption = adoption_index.get(str(run.id), {})
            summary = run_adoption.get("summary") or TopicRecommendationService._empty_adoption_summary()
            if summary.get("total_adoptions", 0) > 0:
                adopted_run_count += 1
            adopted_candidate_count += int(summary.get("distinct_candidates_adopted", 0) or 0)
            total_adoptions += int(summary.get("total_adoptions", 0) or 0)
            direct_adoptions += int(summary.get("direct_adoptions", 0) or 0)
            edited_adoptions += int(summary.get("edited_adoptions", 0) or 0)
            debate_adoptions += int(summary.get("debate_adoptions", 0) or 0)
            reservation_adoptions += int(summary.get("reservation_adoptions", 0) or 0)

            generated_at = run.created_at.isoformat() if run.created_at else None
            if generated_at and (last_generated_at is None or generated_at > last_generated_at):
                last_generated_at = generated_at
            summary_last_adopted = summary.get("last_adopted_at")
            if summary_last_adopted and (last_adopted_at is None or summary_last_adopted > last_adopted_at):
                last_adopted_at = summary_last_adopted

        total_runs = len(runs)
        candidate_adoption_rate = round(adopted_candidate_count / total_candidates, 4) if total_candidates else 0.0
        run_adoption_rate = round(adopted_run_count / total_runs, 4) if total_runs else 0.0
        fallback_rate = round(quality_counts.get("fallback", 0) / total_runs, 4) if total_runs else 0.0
        repaired_rate = round(quality_counts.get("repaired", 0) / total_runs, 4) if total_runs else 0.0
        validated_rate = round(quality_counts.get("validated", 0) / total_runs, 4) if total_runs else 0.0
        version_breakdown = TopicRecommendationService._build_version_breakdown(
            runs,
            adoption_index,
        )
        version_comparison_summary = TopicRecommendationService._build_version_comparison_summary(
            version_breakdown,
        )

        return {
            "class_id": class_id,
            "date_from": date_from,
            "date_to": date_to,
            "total_runs": total_runs,
            "total_candidates": total_candidates,
            "adopted_run_count": adopted_run_count,
            "adopted_candidate_count": adopted_candidate_count,
            "total_adoptions": total_adoptions,
            "direct_adoptions": direct_adoptions,
            "edited_adoptions": edited_adoptions,
            "debate_adoptions": debate_adoptions,
            "reservation_adoptions": reservation_adoptions,
            "run_adoption_rate": run_adoption_rate,
            "candidate_adoption_rate": candidate_adoption_rate,
            "average_candidates_per_run": round(total_candidates / total_runs, 4) if total_runs else 0.0,
            "quality_counts": quality_counts,
            "provider_counts": provider_counts,
            "status_counts": status_counts,
            "quality_rates": {
                "validated_rate": validated_rate,
                "repaired_rate": repaired_rate,
                "fallback_rate": fallback_rate,
            },
            "version_breakdown": version_breakdown,
            "version_comparison_summary": version_comparison_summary,
            "last_generated_at": last_generated_at,
            "last_adopted_at": last_adopted_at,
            "latest_run_id": run_ids[0] if run_ids else None,
        }

    @staticmethod
    def get_dashboard_payload(
        db: Session,
        *,
        class_id: str,
        created_by: Optional[str] = None,
        recent_limit: int = 5,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        leaderboard_limit: int = 5,
        observation_limit: int = 5,
    ) -> Dict[str, Any]:
        safe_recent_limit = max(1, min(int(recent_limit or 5), 20))
        analytics = TopicRecommendationService.get_class_analytics(
            db=db,
            class_id=class_id,
            created_by=created_by,
            date_from=date_from,
            date_to=date_to,
        )
        recent_runs = TopicRecommendationService.list_runs(
            db=db,
            class_id=class_id,
            created_by=created_by,
            limit=safe_recent_limit,
            date_from=date_from,
            date_to=date_to,
        )

        latest_run = recent_runs[0] if recent_runs else None
        latest_adopted_run = next(
            (
                run for run in recent_runs
                if ((run.get("adoption_summary") or {}).get("total_adoptions", 0) or 0) > 0
            ),
            None,
        )
        leaderboard_query = (
            db.query(TopicRecommendationRun)
            .filter(TopicRecommendationRun.class_id == TopicRecommendationService._uuid(class_id))
            .order_by(TopicRecommendationRun.created_at.desc())
        )
        creator_uuid = TopicRecommendationService._uuid(created_by)
        if creator_uuid is not None:
            leaderboard_query = leaderboard_query.filter(TopicRecommendationRun.created_by == creator_uuid)
        leaderboard_query = TopicRecommendationService._apply_run_time_filters(
            leaderboard_query,
            date_from=date_from,
            date_to=date_to,
        )
        leaderboard_runs = leaderboard_query.all()
        leaderboard_adoption_index = TopicRecommendationService._build_adoption_index(
            db,
            class_id=class_id,
            run_ids=[str(run.id) for run in leaderboard_runs],
        )
        leaderboards = TopicRecommendationService._build_candidate_leaderboards(
            leaderboard_runs,
            leaderboard_adoption_index,
            top_n=leaderboard_limit,
        )
        observations = TopicRecommendationService._build_candidate_observations(
            leaderboard_runs,
            leaderboard_adoption_index,
            top_n=observation_limit,
        )

        return {
            "class_id": class_id,
            "date_from": date_from,
            "date_to": date_to,
            "summary": {
                "total_runs": analytics["total_runs"],
                "total_candidates": analytics["total_candidates"],
                "adopted_run_count": analytics["adopted_run_count"],
                "adopted_candidate_count": analytics["adopted_candidate_count"],
                "total_adoptions": analytics["total_adoptions"],
                "run_adoption_rate": analytics["run_adoption_rate"],
                "candidate_adoption_rate": analytics["candidate_adoption_rate"],
                "average_candidates_per_run": analytics["average_candidates_per_run"],
                "direct_adoptions": analytics["direct_adoptions"],
                "edited_adoptions": analytics["edited_adoptions"],
                "debate_adoptions": analytics["debate_adoptions"],
                "reservation_adoptions": analytics["reservation_adoptions"],
            },
            "quality": {
                "quality_counts": analytics["quality_counts"],
                "quality_rates": analytics["quality_rates"],
                "provider_counts": analytics["provider_counts"],
                "status_counts": analytics["status_counts"],
                "version_breakdown": analytics["version_breakdown"],
                "version_comparison_summary": analytics["version_comparison_summary"],
            },
            "timeline": {
                "latest_run_id": analytics["latest_run_id"],
                "last_generated_at": analytics["last_generated_at"],
                "last_adopted_at": analytics["last_adopted_at"],
                "latest_run": latest_run,
                "latest_adopted_run": latest_adopted_run,
            },
            "leaderboards": leaderboards,
            "observations": observations,
            "recent_runs": recent_runs,
        }

    @staticmethod
    def get_version_comparison_payload(
        db: Session,
        *,
        class_id: str,
        created_by: Optional[str] = None,
        current_version_id: Optional[str] = None,
        previous_version_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        analytics = TopicRecommendationService.get_class_analytics(
            db=db,
            class_id=class_id,
            created_by=created_by,
            date_from=date_from,
            date_to=date_to,
        )
        comparison = TopicRecommendationService._build_version_comparison_summary_for_pair(
            analytics["version_breakdown"],
            current_version_id=current_version_id,
            previous_version_id=previous_version_id,
        )
        return {
            "class_id": class_id,
            "date_from": date_from,
            "date_to": date_to,
            "current_version_id": current_version_id,
            "previous_version_id": previous_version_id,
            "version_comparison_summary": comparison,
            "version_breakdown": analytics["version_breakdown"],
        }
