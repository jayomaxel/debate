"""
Class-scoped teaching design version service.
"""

from __future__ import annotations

from io import BytesIO
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import PyPDF2
import docx
from sqlalchemy.orm import Session

from models.teaching_design import ClassTeachingDesignVersion


class TeachingDesignService:
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024
    SUPPORTED_FILE_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    REQUIRED_SIGNAL_FIELDS = (
        "course_title",
        "chapter_theme",
        "learning_objectives",
        "knowledge_points",
        "capability_targets",
        "debate_focuses",
    )
    CONTRACT_EXTRACTION_FIELDS = (
        "course_objectives",
        "knowledge_points",
        "chapter_topics",
        "key_and_difficult_points",
        "competency_goals",
        "applicable_grade",
        "class_hour_constraints",
        "teacher_notes",
    )
    CONTRACT_STATUSES = {"extracting", "ready", "needs_review", "failed"}
    LEGACY_TO_CONTRACT_FIELDS = {
        "learning_objectives": "course_objectives",
        "knowledge_points": "knowledge_points",
        "chapter_theme": "chapter_topics",
        "key_difficulties": "key_and_difficult_points",
        "capability_targets": "competency_goals",
        "grade_level": "applicable_grade",
        "time_constraints": "class_hour_constraints",
        "teacher_notes": "teacher_notes",
    }
    FIELD_LABELS = {
        "course_title": ["课程名称", "课程名", "course title", "course"],
        "chapter_theme": ["章节主题", "章节", "单元主题", "chapter theme", "theme"],
        "learning_objectives": ["课程目标", "教学目标", "学习目标", "objectives"],
        "knowledge_points": ["知识点", "核心知识", "重点知识", "key concepts"],
        "key_difficulties": ["重点难点", "难点", "教学难点", "key difficulties"],
        "capability_targets": ["能力目标", "核心素养", "能力培养目标", "competency"],
        "grade_level": ["适用年级", "授课对象", "年级", "grade"],
        "time_constraints": ["课时", "学时", "时间安排", "time"],
        "debate_focuses": ["辩论焦点", "争议焦点", "讨论焦点", "debate focus"],
        "forbidden_boundaries": ["不适合辩论", "禁区", "边界提醒", "forbidden"],
    }
    GENERIC_SECTION_LABELS = tuple(
        label
        for labels in FIELD_LABELS.values()
        for label in labels
    )

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
            raise ValueError("教学设计列表字段必须是数组")

        result: List[str] = []
        seen = set()
        for item in value:
            cleaned = TeachingDesignService._clean_optional_string(item)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
        return result

    @staticmethod
    def _split_list_items(value: str) -> List[str]:
        parts = re.split(r"[\n\r,，;；、]+", value or "")
        result: List[str] = []
        seen = set()
        for item in parts:
            cleaned = re.sub(
                r"^(?:[\-\u2022]\s*|\d+[\.\)）、]\s*|\(?\d+\)\s*|（[\u4e00-\u9fff]+）\s*|[\u4e00-\u9fff]+、\s*)",
                "",
                item or "",
            ).strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
        return result

    @staticmethod
    def _normalize_text(raw_text: Optional[str]) -> str:
        text = (raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _looks_like_heading(line: str) -> bool:
        stripped = (line or "").strip()
        if not stripped:
            return False
        compact = stripped.replace(" ", "").lower()
        if compact.endswith(":") or compact.endswith("："):
            return True
        if re.match(r"^(第[一二三四五六七八九十0-9]+[章节单元课]|[一二三四五六七八九十]+、|\(?[0-9]+\)|（[一二三四五六七八九十]+）)", stripped):
            return True
        return any(label.replace(" ", "").lower() in compact for label in TeachingDesignService.GENERIC_SECTION_LABELS)

    @staticmethod
    def _slice_after_label(line: str, label: str) -> Optional[str]:
        compact_label = label.replace(" ", "").lower()
        compact_line = line.replace(" ", "").lower()
        if compact_label not in compact_line:
            return None
        position = compact_line.find(compact_label)
        raw = line[position + len(label):].strip(" ：:-")
        return raw or None

    @staticmethod
    def _extract_section(lines: List[str], labels: List[str]) -> List[str]:
        for index, line in enumerate(lines):
            compact_line = line.replace(" ", "").lower()
            if not any(label.replace(" ", "").lower() in compact_line for label in labels):
                continue

            collected: List[str] = []
            for label in labels:
                sliced = TeachingDesignService._slice_after_label(line, label)
                if sliced:
                    collected.extend(TeachingDesignService._split_list_items(sliced))
                    break

            cursor = index + 1
            while cursor < len(lines):
                next_line = lines[cursor].strip()
                if not next_line:
                    cursor += 1
                    if collected:
                        break
                    continue
                if TeachingDesignService._looks_like_heading(next_line):
                    break
                collected.extend(TeachingDesignService._split_list_items(next_line))
                cursor += 1

            if collected:
                return list(dict.fromkeys(collected))
        return []

    @staticmethod
    def resolve_upload_file_type(*, filename: Optional[str], content_type: Optional[str]) -> str:
        normalized_filename = (filename or "").lower()
        normalized_content_type = (content_type or "").lower()
        if normalized_content_type == "application/pdf" or normalized_filename.endswith(".pdf"):
            return "application/pdf"
        if (
            normalized_content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or normalized_filename.endswith(".docx")
        ):
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        raise ValueError("教学设计仅支持 PDF 或 DOCX 文件")

    @staticmethod
    def _normalize_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
        confidence = payload.get("confidence")
        source_excerpt_map = payload.get("source_excerpt_map")
        missing_fields = payload.get("missing_fields")
        return {
            "confidence": {
                str(key): max(0.0, min(1.0, float(value)))
                for key, value in (confidence or {}).items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            }
            if isinstance(confidence, dict)
            else {},
            "missing_fields": [str(item) for item in (missing_fields or []) if str(item).strip()]
            if isinstance(missing_fields, list)
            else [],
            "source_excerpt_map": {
                str(key): str(value).strip()
                for key, value in (source_excerpt_map or {}).items()
                if str(value).strip()
            }
            if isinstance(source_excerpt_map, dict)
            else {},
        }

    @staticmethod
    def normalize_extraction_result(result: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
        if result is None:
            result = {}
        if not isinstance(result, dict):
            raise ValueError("Teaching design extraction result must be an object")
        return {
            key: TeachingDesignService._clean_string_list(result.get(key))
            for key in TeachingDesignService.CONTRACT_EXTRACTION_FIELDS
        }

    @staticmethod
    def extraction_result_from_legacy(payload: Dict[str, Any]) -> Dict[str, List[str]]:
        legacy = TeachingDesignService.normalize_payload(payload)
        return TeachingDesignService.normalize_extraction_result({
            "course_objectives": legacy["learning_objectives"],
            "knowledge_points": legacy["knowledge_points"],
            "chapter_topics": [legacy["chapter_theme"]] if legacy["chapter_theme"] else [],
            "key_and_difficult_points": legacy["key_difficulties"],
            "competency_goals": legacy["capability_targets"],
            "applicable_grade": [legacy["grade_level"]] if legacy["grade_level"] else [],
            "class_hour_constraints": [legacy["time_constraints"]] if legacy["time_constraints"] else [],
            "teacher_notes": legacy.get("teacher_notes", []),
        })

    @staticmethod
    def legacy_payload_from_extraction_result(
        result: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_result = TeachingDesignService.normalize_extraction_result(result)
        metadata = TeachingDesignService._normalize_metadata(metadata or {})
        chapter_topics = normalized_result["chapter_topics"]
        applicable_grade = normalized_result["applicable_grade"]
        class_hour_constraints = normalized_result["class_hour_constraints"]
        return TeachingDesignService.normalize_payload({
            "course_title": chapter_topics[0] if chapter_topics else None,
            "chapter_theme": chapter_topics[0] if chapter_topics else None,
            "learning_objectives": normalized_result["course_objectives"],
            "knowledge_points": normalized_result["knowledge_points"],
            "key_difficulties": normalized_result["key_and_difficult_points"],
            "capability_targets": normalized_result["competency_goals"],
            "grade_level": applicable_grade[0] if applicable_grade else None,
            "time_constraints": class_hour_constraints[0] if class_hour_constraints else None,
            "debate_focuses": normalized_result["knowledge_points"][:3],
            "source_summary": "\n".join(normalized_result["teacher_notes"]) or None,
            "teacher_notes": normalized_result["teacher_notes"],
            **metadata,
        })

    @staticmethod
    def contract_metadata_from_legacy(payload: Dict[str, Any]) -> Dict[str, Any]:
        metadata = TeachingDesignService._normalize_metadata(payload)
        reverse_map = TeachingDesignService.LEGACY_TO_CONTRACT_FIELDS

        def contract_key(key: str) -> str:
            return reverse_map.get(key, key)

        return {
            "confidence": {
                contract_key(key): value
                for key, value in metadata["confidence"].items()
            },
            "missing_fields": [contract_key(key) for key in metadata["missing_fields"]],
            "source_excerpt_map": {
                contract_key(key): value
                for key, value in metadata["source_excerpt_map"].items()
            },
        }

    @staticmethod
    def normalize_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("Teaching design extraction result must be an object")

        if isinstance(payload.get("extraction_result"), dict):
            metadata = TeachingDesignService._normalize_metadata(payload)
            base_payload = TeachingDesignService.legacy_payload_from_extraction_result(
                payload["extraction_result"],
                metadata,
            )
            payload = {**base_payload, **payload}

        metadata = TeachingDesignService._normalize_metadata(payload)
        return {
            "course_title": TeachingDesignService._clean_optional_string(payload.get("course_title")),
            "chapter_theme": TeachingDesignService._clean_optional_string(payload.get("chapter_theme")),
            "learning_objectives": TeachingDesignService._clean_string_list(payload.get("learning_objectives")),
            "knowledge_points": TeachingDesignService._clean_string_list(payload.get("knowledge_points")),
            "key_difficulties": TeachingDesignService._clean_string_list(payload.get("key_difficulties")),
            "capability_targets": TeachingDesignService._clean_string_list(payload.get("capability_targets")),
            "grade_level": TeachingDesignService._clean_optional_string(payload.get("grade_level")),
            "time_constraints": TeachingDesignService._clean_optional_string(payload.get("time_constraints")),
            "debate_focuses": TeachingDesignService._clean_string_list(payload.get("debate_focuses")),
            "forbidden_boundaries": TeachingDesignService._clean_string_list(payload.get("forbidden_boundaries")),
            "source_summary": TeachingDesignService._clean_optional_string(payload.get("source_summary")),
            "teacher_notes": TeachingDesignService._clean_string_list(payload.get("teacher_notes")),
            **metadata,
        }

    @staticmethod
    def extract_text_from_bytes(*, file_data: bytes, file_type: str) -> str:
        if len(file_data or b"") > TeachingDesignService.MAX_UPLOAD_SIZE:
            raise ValueError("教学设计文件大小不能超过 10MB")
        if file_type not in TeachingDesignService.SUPPORTED_FILE_TYPES:
            raise ValueError("不支持的教学设计文件类型")

        if file_type == "application/pdf":
            reader = PyPDF2.PdfReader(BytesIO(file_data))
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(page_text)
            return TeachingDesignService._normalize_text("\n\n".join(text_parts))

        document = docx.Document(BytesIO(file_data))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text and paragraph.text.strip()]
        return TeachingDesignService._normalize_text("\n\n".join(paragraphs))

    @staticmethod
    def infer_payload_from_raw_text(raw_text: Optional[str]) -> Dict[str, Any]:
        normalized_text = TeachingDesignService._normalize_text(raw_text)
        lines = [line.strip() for line in normalized_text.split("\n") if line.strip()]

        first_line = lines[0] if lines else None
        chapter_line = next((line for line in lines if re.search(r"第.+[章节单元课]", line)), None)

        learning_objectives = TeachingDesignService._extract_section(lines, TeachingDesignService.FIELD_LABELS["learning_objectives"])
        knowledge_points = TeachingDesignService._extract_section(lines, TeachingDesignService.FIELD_LABELS["knowledge_points"])
        key_difficulties = TeachingDesignService._extract_section(lines, TeachingDesignService.FIELD_LABELS["key_difficulties"])
        capability_targets = TeachingDesignService._extract_section(lines, TeachingDesignService.FIELD_LABELS["capability_targets"])
        debate_focuses = TeachingDesignService._extract_section(lines, TeachingDesignService.FIELD_LABELS["debate_focuses"])
        forbidden_boundaries = TeachingDesignService._extract_section(lines, TeachingDesignService.FIELD_LABELS["forbidden_boundaries"])

        course_title = TeachingDesignService._extract_section(lines, TeachingDesignService.FIELD_LABELS["course_title"])
        chapter_theme = TeachingDesignService._extract_section(lines, TeachingDesignService.FIELD_LABELS["chapter_theme"])
        grade_level = TeachingDesignService._extract_section(lines, TeachingDesignService.FIELD_LABELS["grade_level"])
        time_constraints = TeachingDesignService._extract_section(lines, TeachingDesignService.FIELD_LABELS["time_constraints"])

        if not debate_focuses and knowledge_points:
            debate_focuses = knowledge_points[:3]
        if not capability_targets and learning_objectives:
            capability_targets = learning_objectives[:3]

        payload = {
            "course_title": course_title[0] if course_title else first_line,
            "chapter_theme": chapter_theme[0] if chapter_theme else chapter_line,
            "learning_objectives": learning_objectives,
            "knowledge_points": knowledge_points,
            "key_difficulties": key_difficulties,
            "capability_targets": capability_targets,
            "grade_level": grade_level[0] if grade_level else None,
            "time_constraints": time_constraints[0] if time_constraints else None,
            "debate_focuses": debate_focuses,
            "forbidden_boundaries": forbidden_boundaries,
            "source_summary": normalized_text[:240] + ("..." if len(normalized_text) > 240 else ""),
        }
        field_names = (
            'course_title',
            'chapter_theme',
            'learning_objectives',
            'knowledge_points',
            'key_difficulties',
            'capability_targets',
            'grade_level',
            'time_constraints',
            'debate_focuses',
            'forbidden_boundaries',
        )
        payload['missing_fields'] = [key for key in field_names if not payload.get(key)]
        payload['confidence'] = {
            key: (0.9 if payload.get(key) else 0.0) for key in field_names
        }
        payload['source_excerpt_map'] = {
            key: next(
                (
                    line[:240]
                    for line in lines
                    if any(
                        label.replace(' ', '').lower() in line.replace(' ', '').lower()
                        for label in TeachingDesignService.FIELD_LABELS.get(key, [])
                    )
                ),
                (lines[0][:240] if lines and payload.get(key) else ''),
            )
            for key in field_names
            if payload.get(key)
        }
        return TeachingDesignService.normalize_payload(payload)

    @staticmethod
    def infer_extraction_status(payload: Dict[str, Any]) -> str:
        hit_count = 0
        for key in TeachingDesignService.REQUIRED_SIGNAL_FIELDS:
            value = payload.get(key)
            if isinstance(value, list) and value:
                hit_count += 1
            elif isinstance(value, str) and value.strip():
                hit_count += 1

        if hit_count >= 4:
            return "completed"
        if hit_count >= 2:
            return "partial"
        return "insufficient"

    @staticmethod
    def infer_contract_status(extraction_result: Dict[str, Any]) -> str:
        normalized = TeachingDesignService.normalize_extraction_result(extraction_result)
        populated_field_count = sum(1 for value in normalized.values() if value)
        if populated_field_count >= 4:
            return "ready"
        return "needs_review"

    @staticmethod
    def _contract_file_type(source_file_type: Optional[str]) -> Optional[str]:
        value = (source_file_type or "").strip().lower()
        if value == "application/pdf" or value == "pdf":
            return "pdf"
        if (
            value == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or value.endswith(".docx")
            or value == "docx"
        ):
            return "docx"
        return value or None

    @staticmethod
    def upsert_current_version(
        db: Session,
        *,
        class_id: str,
        created_by: Optional[str],
        extracted_payload: Optional[Dict[str, Any]] = None,
        extraction_result: Optional[Dict[str, Any]] = None,
        version_name: Optional[str] = None,
        title: Optional[str] = None,
        raw_text: Optional[str] = None,
        source_type: str = "manual",
        source_filename: Optional[str] = None,
        source_file_type: Optional[str] = None,
        source_file_size: Optional[int] = None,
        derived_from_version_id: Optional[str] = None,
        correction_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        class_uuid = TeachingDesignService._uuid(class_id)
        if class_uuid is None:
            raise ValueError("无效的班级ID")

        if extracted_payload is None and extraction_result is None:
            raise ValueError("Teaching design extraction result is required")

        normalized_payload = TeachingDesignService.normalize_payload(extracted_payload or {})
        normalized_result = TeachingDesignService.normalize_extraction_result(
            extraction_result
            if extraction_result is not None
            else TeachingDesignService.extraction_result_from_legacy(normalized_payload)
        )
        contract_metadata = TeachingDesignService.contract_metadata_from_legacy(extracted_payload or {})
        if extraction_result is not None:
            normalized_payload = TeachingDesignService.legacy_payload_from_extraction_result(
                normalized_result,
                contract_metadata,
            )
        extraction_status = TeachingDesignService.infer_extraction_status(normalized_payload)
        contract_status = TeachingDesignService.infer_contract_status(normalized_result)

        db.query(ClassTeachingDesignVersion).filter(
            ClassTeachingDesignVersion.class_id == class_uuid,
            ClassTeachingDesignVersion.is_active.is_(True),
        ).update(
            {ClassTeachingDesignVersion.is_active: False},
            synchronize_session=False,
        )

        record = ClassTeachingDesignVersion(
            class_id=class_uuid,
            created_by=TeachingDesignService._uuid(created_by),
            version_name=TeachingDesignService._clean_optional_string(version_name),
            title=TeachingDesignService._clean_optional_string(title),
            source_type=TeachingDesignService._clean_optional_string(source_type) or "manual",
            source_filename=TeachingDesignService._clean_optional_string(source_filename),
            source_file_type=TeachingDesignService._clean_optional_string(source_file_type),
            source_file_size=int(source_file_size) if source_file_size is not None else None,
            raw_text=TeachingDesignService._clean_optional_string(raw_text),
            extraction_result=normalized_result,
            confidence=contract_metadata.get("confidence") or TeachingDesignService.contract_metadata_from_legacy(normalized_payload)["confidence"],
            missing_fields=contract_metadata.get("missing_fields") or TeachingDesignService.contract_metadata_from_legacy(normalized_payload)["missing_fields"],
            source_excerpt_map=contract_metadata.get("source_excerpt_map") or TeachingDesignService.contract_metadata_from_legacy(normalized_payload)["source_excerpt_map"],
            status=contract_status,
            extracted_payload=normalized_payload,
            extraction_status=extraction_status,
            derived_from_version_id=TeachingDesignService._uuid(derived_from_version_id),
            correction_notes=TeachingDesignService._clean_optional_string(correction_notes),
            is_active=True,
            activated_at=datetime.utcnow(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return TeachingDesignService.serialize_version(record)

    @staticmethod
    def upload_and_extract_current_version(
        db: Session,
        *,
        class_id: str,
        created_by: Optional[str],
        file_data: bytes,
        filename: str,
        file_type: str,
        version_name: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_file_type = TeachingDesignService.resolve_upload_file_type(
            filename=filename,
            content_type=file_type,
        )
        raw_text = TeachingDesignService.extract_text_from_bytes(
            file_data=file_data,
            file_type=resolved_file_type,
        )
        extracted_payload = TeachingDesignService.infer_payload_from_raw_text(raw_text)
        return TeachingDesignService.upsert_current_version(
            db=db,
            class_id=class_id,
            created_by=created_by,
            extracted_payload=extracted_payload,
            version_name=version_name,
            title=title or filename,
            raw_text=raw_text,
            source_type="upload",
            source_filename=filename,
            source_file_type=resolved_file_type,
            source_file_size=len(file_data or b""),
        )

    @staticmethod
    def get_active_version(db: Session, class_id: str) -> Optional[ClassTeachingDesignVersion]:
        class_uuid = TeachingDesignService._uuid(class_id)
        if class_uuid is None:
            return None
        return (
            db.query(ClassTeachingDesignVersion)
            .filter(
                ClassTeachingDesignVersion.class_id == class_uuid,
                ClassTeachingDesignVersion.is_active.is_(True),
            )
            .order_by(ClassTeachingDesignVersion.created_at.desc())
            .first()
        )

    @staticmethod
    def list_versions(db: Session, class_id: str) -> List[Dict[str, Any]]:
        class_uuid = TeachingDesignService._uuid(class_id)
        if class_uuid is None:
            return []
        versions = (
            db.query(ClassTeachingDesignVersion)
            .filter(ClassTeachingDesignVersion.class_id == class_uuid)
            .order_by(
                ClassTeachingDesignVersion.is_active.desc(),
                ClassTeachingDesignVersion.created_at.desc(),
            )
            .all()
        )
        return [TeachingDesignService.serialize_version(version) for version in versions]

    @staticmethod
    def get_version_by_id(db: Session, version_id: str) -> Optional[ClassTeachingDesignVersion]:
        version_uuid = TeachingDesignService._uuid(version_id)
        if version_uuid is None:
            return None
        return (
            db.query(ClassTeachingDesignVersion)
            .filter(ClassTeachingDesignVersion.id == version_uuid)
            .first()
        )

    @staticmethod
    def activate_version(
        db: Session,
        *,
        class_id: str,
        version_id: str,
    ) -> Dict[str, Any]:
        class_uuid = TeachingDesignService._uuid(class_id)
        version = TeachingDesignService.get_version_by_id(db, version_id)
        if class_uuid is None or version is None or version.class_id != class_uuid:
            raise ValueError("教学设计版本不存在或不属于当前班级")

        db.query(ClassTeachingDesignVersion).filter(
            ClassTeachingDesignVersion.class_id == class_uuid,
            ClassTeachingDesignVersion.is_active.is_(True),
        ).update(
            {ClassTeachingDesignVersion.is_active: False},
            synchronize_session=False,
        )
        version.is_active = True
        version.activated_at = datetime.utcnow()
        db.commit()
        db.refresh(version)
        return TeachingDesignService.serialize_version(version)

    @staticmethod
    def create_corrected_version(
        db: Session,
        *,
        class_id: str,
        version_id: str,
        created_by: Optional[str],
        extracted_payload: Dict[str, Any],
        version_name: Optional[str] = None,
        title: Optional[str] = None,
        correction_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        base_version = TeachingDesignService.get_version_by_id(db, version_id)
        class_uuid = TeachingDesignService._uuid(class_id)
        if class_uuid is None or base_version is None or base_version.class_id != class_uuid:
            raise ValueError("教学设计版本不存在或不属于当前班级")

        return TeachingDesignService.upsert_current_version(
            db=db,
            class_id=class_id,
            created_by=created_by,
            extracted_payload=extracted_payload,
            version_name=version_name or base_version.version_name,
            title=title or base_version.title,
            raw_text=base_version.raw_text,
            source_type="corrected",
            source_filename=base_version.source_filename,
            source_file_type=base_version.source_file_type,
            source_file_size=base_version.source_file_size,
            derived_from_version_id=str(base_version.id),
            correction_notes=correction_notes,
        )

    @staticmethod
    def serialize_version(version: Optional[ClassTeachingDesignVersion]) -> Optional[Dict[str, Any]]:
        if version is None:
            return None
        legacy_payload = TeachingDesignService.normalize_payload(version.extracted_payload or {})
        extraction_result = TeachingDesignService.normalize_extraction_result(
            version.extraction_result
            if version.extraction_result is not None
            else TeachingDesignService.extraction_result_from_legacy(legacy_payload)
        )
        contract_metadata = TeachingDesignService.contract_metadata_from_legacy(legacy_payload)
        confidence = version.confidence if isinstance(version.confidence, dict) else contract_metadata["confidence"]
        missing_fields = version.missing_fields if isinstance(version.missing_fields, list) else contract_metadata["missing_fields"]
        source_excerpt_map = (
            version.source_excerpt_map
            if isinstance(version.source_excerpt_map, dict)
            else contract_metadata["source_excerpt_map"]
        )
        if version.extraction_status == "failed":
            status = "failed"
        elif version.extraction_result is None:
            status = TeachingDesignService.infer_contract_status(extraction_result)
        elif version.status in TeachingDesignService.CONTRACT_STATUSES:
            status = version.status
        else:
            status = TeachingDesignService.infer_contract_status(extraction_result)
        uploaded_at = version.created_at.isoformat() if version.created_at else None
        return {
            # Frozen TeachingDesignSchema version fields.
            "version_id": str(version.id),
            "uploaded_at": uploaded_at,
            "source_file_type": TeachingDesignService._contract_file_type(version.source_file_type),
            "source_file_name": version.source_filename,
            "extraction_result": extraction_result,
            "confidence": confidence,
            "missing_fields": missing_fields,
            "source_excerpt_map": source_excerpt_map,
            "status": status,
            # Transitional aliases used by the existing teacher UI and topic service.
            "id": str(version.id),
            "class_id": str(version.class_id),
            "created_by": str(version.created_by) if version.created_by else None,
            "version_name": version.version_name,
            "title": version.title,
            "source_type": version.source_type,
            "source_filename": version.source_filename,
            "source_file_mime_type": version.source_file_type,
            "source_file_size": version.source_file_size,
            "raw_text": version.raw_text,
            "extracted_payload": legacy_payload,
            "extraction_status": version.extraction_status,
            "derived_from_version_id": str(version.derived_from_version_id) if version.derived_from_version_id else None,
            "correction_notes": version.correction_notes,
            "is_active": bool(version.is_active),
            "activated_at": version.activated_at.isoformat() if version.activated_at else None,
            "created_at": uploaded_at,
            "updated_at": version.updated_at.isoformat() if version.updated_at else None,
        }

    @staticmethod
    def serialize_design(db: Session, class_id: str) -> Dict[str, Any]:
        class_uuid = TeachingDesignService._uuid(class_id)
        if class_uuid is None:
            raise ValueError("Invalid class ID")

        versions = (
            db.query(ClassTeachingDesignVersion)
            .filter(ClassTeachingDesignVersion.class_id == class_uuid)
            .order_by(
                ClassTeachingDesignVersion.is_active.desc(),
                ClassTeachingDesignVersion.created_at.desc(),
            )
            .all()
        )
        serialized_versions = [TeachingDesignService.serialize_version(version) for version in versions]
        current = next((item for item in serialized_versions if item["is_active"]), None)
        return {
            "design_id": f"teaching-design:{class_uuid}",
            "class_id": str(class_uuid),
            "current_version_id": current["version_id"] if current else None,
            "versions": [
                {
                    key: item[key]
                    for key in (
                        "version_id",
                        "uploaded_at",
                        "source_file_type",
                        "source_file_name",
                        "extraction_result",
                        "confidence",
                        "missing_fields",
                        "source_excerpt_map",
                        "status",
                    )
                }
                for item in serialized_versions
            ],
        }
