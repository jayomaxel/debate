"""
辩论管理服务
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.debate import Debate, DebateParticipation
from models.user import User
from models.class_model import Class
from services.assessment_service import AssessmentService
from services.config_service import ConfigService
from config import settings
from logging_config import get_logger
import uuid
import random
import string
import json
import httpx

logger = get_logger(__name__)


class DebateService:
    """辩论管理服务类"""

    ROLE_ORDER = ["debater_1", "debater_2", "debater_3", "debater_4"]
    ROLE_REASON = {
        "debater_1": "立论陈词,奠定基调",
        "debater_2": "补充论据,强化逻辑",
        "debater_3": "反驳对方,抓住漏洞",
        "debater_4": "总结陈词,升华观点",
    }
    
    @staticmethod
    def generate_invitation_code() -> str:
        """
        生成唯一的6位邀请码
        
        Returns:
            6位字母数字组合的邀请码
        """
        characters = string.ascii_uppercase + string.digits
        return ''.join(random.choices(characters, k=6))

    @staticmethod
    def _extract_first_json(text: str) -> Any:
        if not text:
            raise ValueError("LLM返回为空")
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass

        start_positions = [i for i, ch in enumerate(text) if ch in ["{", "["]]
        if not start_positions:
            raise ValueError("LLM返回不包含JSON")
        for start in start_positions:
            for end in range(len(text) - 1, start, -1):
                if text[end] not in ["}", "]"]:
                    continue
                snippet = text[start : end + 1]
                try:
                    return json.loads(snippet)
                except Exception:
                    continue
        raise ValueError("无法解析LLM返回JSON")

    @staticmethod
    def _fallback_assign_roles(assessments: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
        remaining = list(assessments.keys())
        role_to_weight = {
            "debater_1": {"expression_willingness": 0.45, "knowledge": 0.35, "critical_thinking": 0.2},
            "debater_2": {"logical_thinking": 0.5, "knowledge": 0.3, "critical_thinking": 0.2},
            "debater_3": {"critical_thinking": 0.55, "logical_thinking": 0.3, "expression_willingness": 0.15},
            "debater_4": {"balanced": 1.0},
        }

        def score(user_id: str, role: str) -> float:
            a = assessments[user_id]
            expression = float(a.get("expression_willingness", 50))
            logical = float(a.get("logical_thinking", 50))
            knowledge = (float(a.get("stablecoin_knowledge", 50)) + float(a.get("financial_knowledge", 50))) / 2.0
            critical = float(a.get("critical_thinking", 50))
            if role == "debater_4":
                return (expression + logical + knowledge + critical) / 4.0
            w = role_to_weight[role]
            return (
                w.get("expression_willingness", 0) * expression
                + w.get("logical_thinking", 0) * logical
                + w.get("knowledge", 0) * knowledge
                + w.get("critical_thinking", 0) * critical
            )

        assignments: Dict[str, str] = {}
        for role in DebateService.ROLE_ORDER[: len(remaining)]:
            best_user_id = max(remaining, key=lambda uid: score(uid, role))
            assignments[best_user_id] = role
            remaining.remove(best_user_id)
        return assignments

    @staticmethod
    async def _openai_assign_roles(
        db: Session,
        students: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        config_service = ConfigService(db)
        model_config = await config_service.get_model_config()
        api_key = (model_config.api_key or "").strip() or (settings.OPENAI_API_KEY or "").strip()
        if not api_key:
            raise ValueError("OpenAI API key not configured")

        api_endpoint = (model_config.api_endpoint or "").strip()
        if not api_endpoint:
            api_endpoint = f"{settings.OPENAI_BASE_URL}/chat/completions"

        if api_endpoint.endswith("/chat/completions"):
            endpoint = api_endpoint
        elif api_endpoint.endswith("/v1") or api_endpoint.endswith("/compatible-mode/v1"):
            endpoint = f"{api_endpoint}/chat/completions"
        else:
            endpoint = f"{api_endpoint.rstrip('/')}/chat/completions"

        model_name = (model_config.model_name or "").strip() or settings.OPENAI_MODEL_NAME

        system_prompt = (
            "你是辩论教练。请基于学生能力评估，为本场辩论分配角色：debater_1(一辩)、debater_2(二辩)、debater_3(三辩)、debater_4(四辩)。"
            "你必须保证：每个学生最多一个角色、每个角色最多分配给一名学生。"
            "严禁按输入顺序直接分配（例如第1个学生=debater_1等），必须依据能力数值做判断。"
            "你只输出JSON，不要输出任何额外文字。"
            "输出格式：{\"assignments\":[{\"user_id\":\"...\",\"role\":\"debater_1\"},...]}"
        )

        role_name = {
            "debater_1": "一辩",
            "debater_2": "二辩",
            "debater_3": "三辩",
            "debater_4": "四辩",
        }

        students_cn = []
        for s in students:
            uid = s.get("user_id")
            if not uid:
                continue
            students_cn.append(
                {
                    "user_id": uid,
                    "姓名": s.get("name") or "",
                    "表达意愿": s.get("expression_willingness", 50),
                    "逻辑建构力": s.get("logical_thinking", 50),
                    "AI伦理与科技素养": s.get("stablecoin_knowledge", 50),
                    "AI通识知识水平": s.get("financial_knowledge", 50),
                    "批判性思维": s.get("critical_thinking", 50),
                    "系统推荐角色": role_name.get(s.get("recommended_role"), "") if s.get("recommended_role") else "",
                }
            )

        user_payload = {
            "评分说明": "所有能力维度取值范围为0-100，数值越高代表该能力越强。",
            "角色说明": {
                "debater_1": "一辩：立论陈词，奠定基调（适合表达强、主题把控强）",
                "debater_2": "二辩：攻辩反击，强化论据（适合逻辑强、论证细致）",
                "debater_3": "三辩：快速反驳，抓漏洞（适合反应快、批判强）",
                "debater_4": "四辩：总结升华，收束全场（适合综合能力强、总结能力强）",
            },
            "可用角色列表": [{"role": r, "名称": role_name[r]} for r in DebateService.ROLE_ORDER[: len(students_cn)]],
            "学生列表": students_cn,
        }

        print(f"students_cn:{students_cn}")

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "temperature": 0.2,
            "max_tokens": min(int(model_config.max_tokens or 300), 600),
        }

        def parse_assignments(data: Dict[str, Any]) -> Dict[str, str]:
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            parsed = DebateService._extract_first_json(content)
            assignments = parsed.get("assignments") if isinstance(parsed, dict) else None
            if not isinstance(assignments, list):
                raise ValueError("OpenAI返回格式不正确")

            valid_user_ids = {s["user_id"] for s in students if s.get("user_id")}
            valid_roles = set(DebateService.ROLE_ORDER[: len(students_cn)])
            result: Dict[str, str] = {}
            used_roles = set()
            for item in assignments:
                if not isinstance(item, dict):
                    continue
                user_id = item.get("user_id")
                role = item.get("role")
                if user_id in valid_user_ids and role in valid_roles and role not in used_roles and user_id not in result:
                    result[user_id] = role
                    used_roles.add(role)
            if len(result) != len(students_cn):
                raise ValueError("OpenAI分配结果不完整")
            return result

        async def call_once(extra_system: Optional[str] = None) -> Dict[str, str]:
            req_payload = payload
            if extra_system:
                req_payload = {
                    **payload,
                    "messages": [
                        {"role": "system", "content": system_prompt + extra_system},
                        payload["messages"][1],
                    ],
                    "temperature": 0.0,
                }

            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=req_payload,
                )
            if response.status_code != 200:
                raise ValueError(f"OpenAI调用失败: {response.status_code} - {response.text}")
            return parse_assignments(response.json())

        def is_trivial_by_input_order(result: Dict[str, str]) -> bool:
            ordered_ids = [s.get("user_id") for s in students_cn]
            expected = {uid: DebateService.ROLE_ORDER[i] for i, uid in enumerate(ordered_ids) if uid}
            return result == expected

        llm_result = await call_once()
        if is_trivial_by_input_order(llm_result):
            deterministic = DebateService._fallback_assign_roles(
                {s["user_id"]: {
                    "expression_willingness": s.get("表达意愿", 50),
                    "logical_thinking": s.get("逻辑建构力", 50),
                    "stablecoin_knowledge": s.get("AI伦理与科技素养", 50),
                    "financial_knowledge": s.get("AI通识知识水平", 50),
                    "critical_thinking": s.get("批判性思维", 50),
                } for s in students_cn}
            )
            if deterministic != llm_result:
                try:
                    llm_result = await call_once(extra_system="如果你发现自己倾向于按输入顺序分配，请立即改为按能力最匹配的方式重新分配。")
                except Exception as e:
                    logger.warning(f"OpenAI重试分组失败，使用兜底规则: {e}")
                    llm_result = deterministic
            else:
                logger.info("OpenAI分配结果与兜底一致，虽按顺序但仍接受该结果")

        return llm_result
    
    @staticmethod
    async def create_debate(
        db: Session,
        teacher_id: str,
        class_id: str,
        topic: str,
        duration: int,
        description: Optional[str] = None,
        student_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        创建辩论任务
        
        Args:
            db: 数据库会话
            teacher_id: 教师ID
            class_id: 班级ID
            topic: 辩题
            duration: 时长（分钟）
            description: 描述（可选）
            student_ids: 学生ID列表（可选）
            
        Returns:
            包含辩论信息的字典
            
        Raises:
            ValueError: 如果班级不存在或邀请码生成失败
        """
        # 验证班级是否存在且属于该教师
        cls = db.query(Class).filter(
            Class.id == uuid.UUID(class_id),
            Class.teacher_id == uuid.UUID(teacher_id)
        ).first()
        
        if not cls:
            raise ValueError("班级不存在或无权限")
        
        # 生成唯一的邀请码（最多尝试10次）
        max_attempts = 10
        invitation_code = None
        
        for _ in range(max_attempts):
            code = DebateService.generate_invitation_code()
            existing = db.query(Debate).filter(Debate.invitation_code == code).first()
            if not existing:
                invitation_code = code
                break
        
        if not invitation_code:
            raise ValueError("生成邀请码失败，请重试")
        
        # 创建辩论
        debate = Debate(
            id=uuid.uuid4(),
            topic=topic,
            description=description,
            duration=duration,
            invitation_code=invitation_code,
            class_id=uuid.UUID(class_id),
            teacher_id=uuid.UUID(teacher_id),
            status='published'
        )
        
        try:
            db.add(debate)
            db.commit()
            db.refresh(debate)
            
            # 如果提供了学生ID列表，创建参与记录
            if student_ids:
                selected_student_ids = student_ids[:4]
                users = (
                    db.query(User)
                    .filter(User.id.in_([uuid.UUID(sid) for sid in selected_student_ids]))
                    .all()
                )
                user_name_by_id = {str(u.id): (u.name or "") for u in users}
                student_assessments: Dict[str, Dict[str, Any]] = {}
                students_payload: List[Dict[str, Any]] = []
                for sid in selected_student_ids:
                    assessment = AssessmentService.get_assessment(db=db, user_id=sid) or {}
                    student_assessments[sid] = assessment
                    students_payload.append(
                        {
                            "user_id": sid,
                            "name": user_name_by_id.get(sid, ""),
                            "expression_willingness": assessment.get("expression_willingness", 50),
                            "logical_thinking": assessment.get("logical_thinking", 50),
                            "stablecoin_knowledge": assessment.get("stablecoin_knowledge", 50),
                            "financial_knowledge": assessment.get("financial_knowledge", 50),
                            "critical_thinking": assessment.get("critical_thinking", 50),
                            "recommended_role": assessment.get("recommended_role"),
                        }
                    )

                try:
                    role_by_user_id = await DebateService._openai_assign_roles(db=db, students=students_payload)
                except Exception as e:
                    logger.warning(f"OpenAI分组失败，使用兜底规则: {e}")
                    role_by_user_id = DebateService._fallback_assign_roles(student_assessments)

                for sid in selected_student_ids:
                    role = role_by_user_id.get(sid)
                    if role not in DebateService.ROLE_ORDER:
                        raise ValueError("智能分组失败")
                    participation = DebateParticipation(
                        id=uuid.uuid4(),
                        debate_id=debate.id,
                        user_id=uuid.UUID(sid),
                        role=role,
                        stance="positive",
                        role_reason=DebateService.ROLE_REASON.get(role),
                    )
                    db.add(participation)
                db.commit()
            
        except IntegrityError:
            db.rollback()
            raise ValueError("创建辩论失败")
        
        participations = db.query(DebateParticipation).filter(DebateParticipation.debate_id == debate.id).all()
        user_ids = [str(p.user_id) for p in participations]
        grouping = []
        if participations:
            users = db.query(User).filter(User.id.in_([p.user_id for p in participations])).all()
            user_by_id = {u.id: u for u in users}
            role_rank = {r: i for i, r in enumerate(DebateService.ROLE_ORDER)}
            participations_sorted = sorted(participations, key=lambda p: role_rank.get(p.role, 99))
            grouping = [
                {
                    "user_id": str(p.user_id),
                    "name": (user_by_id.get(p.user_id).name if user_by_id.get(p.user_id) else ""),
                    "role": p.role,
                    "role_reason": p.role_reason,
                }
                for p in participations_sorted
            ]

        return {
            "id": str(debate.id),
            "topic": debate.topic,
            "description": debate.description,
            "duration": debate.duration,
            "invitation_code": debate.invitation_code,
            "class_id": str(debate.class_id),
            "teacher_id": str(debate.teacher_id),
            "status": debate.status,
            "student_ids": user_ids,
            "grouping": grouping,
            "created_at": debate.created_at.isoformat()
        }
    
    @staticmethod
    async def update_debate(
        db: Session,
        teacher_id: str,
        debate_id: str,
        topic: Optional[str] = None,
        duration: Optional[int] = None,
        description: Optional[str] = None,
        student_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        更新辩论任务
        
        Args:
            db: 数据库会话
            teacher_id: 教师ID
            debate_id: 辩论ID
            topic: 辩题（可选）
            duration: 时长（可选）
            description: 描述（可选）
            student_ids: 学生ID列表（可选）
            
        Returns:
            更新后的辩论信息
            
        Raises:
            ValueError: 如果辩论不存在或无权限
        """
        debate = db.query(Debate).filter(
            Debate.id == uuid.UUID(debate_id),
            Debate.teacher_id == uuid.UUID(teacher_id)
        ).first()
        
        if not debate:
            raise ValueError("辩论不存在或无权限")
        
        # 允许修改 draft 和 published 状态，但进行中和已完成的不建议大幅修改
        # 这里暂时不做严格限制，由前端控制，或者仅限制无法修改已开始的辩论的关键参数
        if debate.status in ['in_progress', 'completed']:
             # 如果已经开始，仅允许修改描述
             if topic is not None and topic != debate.topic:
                 raise ValueError("无法修改进行中或已完成辩论的主题")
             if duration is not None and duration != debate.duration:
                 raise ValueError("无法修改进行中或已完成辩论的时长")
        
        # 更新基本字段
        if topic is not None:
            debate.topic = topic
        if duration is not None:
            debate.duration = duration
        if description is not None:
            debate.description = description
            
        # 更新参与学生
        if student_ids is not None:
            if debate.status in ["in_progress", "completed"]:
                raise ValueError("无法修改进行中或已完成辩论的辩手")

            selected_student_ids = student_ids[:4]
            users = (
                db.query(User)
                .filter(User.id.in_([uuid.UUID(sid) for sid in selected_student_ids]))
                .all()
            )
            user_name_by_id = {str(u.id): (u.name or "") for u in users}
            student_assessments: Dict[str, Dict[str, Any]] = {}
            students_payload: List[Dict[str, Any]] = []
            for sid in selected_student_ids:
                assessment = AssessmentService.get_assessment(db=db, user_id=sid) or {}
                student_assessments[sid] = assessment
                students_payload.append(
                    {
                        "user_id": sid,
                        "name": user_name_by_id.get(sid, ""),
                        "expression_willingness": assessment.get("expression_willingness", 50),
                        "logical_thinking": assessment.get("logical_thinking", 50),
                        "stablecoin_knowledge": assessment.get("stablecoin_knowledge", 50),
                        "financial_knowledge": assessment.get("financial_knowledge", 50),
                        "critical_thinking": assessment.get("critical_thinking", 50),
                        "recommended_role": assessment.get("recommended_role"),
                    }
                )

            try:
                role_by_user_id = await DebateService._openai_assign_roles(db=db, students=students_payload)
            except Exception as e:
                logger.warning(f"OpenAI分组失败，使用兜底规则: {e}")
                role_by_user_id = DebateService._fallback_assign_roles(student_assessments)

            db.query(DebateParticipation).filter(DebateParticipation.debate_id == debate.id).delete()

            for sid in selected_student_ids:
                role = role_by_user_id.get(sid)
                if role not in DebateService.ROLE_ORDER:
                    raise ValueError("智能分组失败")
                participation = DebateParticipation(
                    id=uuid.uuid4(),
                    debate_id=debate.id,
                    user_id=uuid.UUID(sid),
                    role=role,
                    stance="positive",
                    role_reason=DebateService.ROLE_REASON.get(role),
                )
                db.add(participation)
        
        try:
            db.commit()
            db.refresh(debate)
        except IntegrityError:
            db.rollback()
            raise ValueError("更新辩论失败")
        
        participations = db.query(DebateParticipation).filter(DebateParticipation.debate_id == debate.id).all()
        user_ids = [str(p.user_id) for p in participations]
        grouping = []
        if participations:
            users = db.query(User).filter(User.id.in_([p.user_id for p in participations])).all()
            user_by_id = {u.id: u for u in users}
            role_rank = {r: i for i, r in enumerate(DebateService.ROLE_ORDER)}
            participations_sorted = sorted(participations, key=lambda p: role_rank.get(p.role, 99))
            grouping = [
                {
                    "user_id": str(p.user_id),
                    "name": (user_by_id.get(p.user_id).name if user_by_id.get(p.user_id) else ""),
                    "role": p.role,
                    "role_reason": p.role_reason,
                }
                for p in participations_sorted
            ]

        return {
            "id": str(debate.id),
            "topic": debate.topic,
            "description": debate.description,
            "duration": debate.duration,
            "invitation_code": debate.invitation_code,
            "class_id": str(debate.class_id),
            "teacher_id": str(debate.teacher_id),
            "status": debate.status,
            "student_ids": user_ids,
            "grouping": grouping,
            "created_at": debate.created_at.isoformat()
        }
    
    @staticmethod
    def publish_debate(
        db: Session,
        debate_id: str
    ) -> Dict[str, Any]:
        """
        发布辩论任务
        
        Args:
            db: 数据库会话
            debate_id: 辩论ID
            
        Returns:
            更新后的辩论信息
            
        Raises:
            ValueError: 如果辩论不存在或状态不正确
        """
        debate = db.query(Debate).filter(Debate.id == uuid.UUID(debate_id)).first()
        
        if not debate:
            raise ValueError("辩论不存在")
        
        if debate.status != 'draft':
            raise ValueError("只能发布草稿状态的辩论")
        
        debate.status = 'published'
        db.commit()
        db.refresh(debate)
        
        return {
            "id": str(debate.id),
            "topic": debate.topic,
            "invitation_code": debate.invitation_code,
            "status": debate.status
        }
    
    @staticmethod
    def get_debates(
        db: Session,
        teacher_id: Optional[str] = None,
        class_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取辩论列表
        
        Args:
            db: 数据库会话
            teacher_id: 教师ID（可选）
            class_id: 班级ID（可选）
            status: 状态（可选）
            
        Returns:
            辩论列表
        """
        query = db.query(Debate)
        
        if teacher_id:
            query = query.filter(Debate.teacher_id == uuid.UUID(teacher_id))
        if class_id:
            query = query.filter(Debate.class_id == uuid.UUID(class_id))
        if status:
            query = query.filter(Debate.status == status)
        
        debates = query.order_by(Debate.created_at.desc()).all()
        
        result = []
        for debate in debates:
            # 获取参与学生
            participations = db.query(DebateParticipation).filter(
                DebateParticipation.debate_id == debate.id
            ).all()
            
            student_ids = [str(p.user_id) for p in participations]
            
            result.append({
                "id": str(debate.id),
                "topic": debate.topic,
                "description": debate.description,
                "duration": debate.duration,
                "invitation_code": debate.invitation_code,
                "class_id": str(debate.class_id),
                "status": debate.status,
                "participant_count": len(participations),
                "student_ids": student_ids,
                "created_at": debate.created_at.isoformat()
            })
        
        return result

    @staticmethod
    def get_debate(
        db: Session,
        debate_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取单个辩论详情
        
        Args:
            db: 数据库会话
            debate_id: 辩论ID
            
        Returns:
            辩论详情，如果不存在返回None
        """
        debate = db.query(Debate).filter(Debate.id == uuid.UUID(debate_id)).first()
        
        if not debate:
            return None
            
        # 获取参与学生
        participations = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate.id
        ).all()
        
        student_ids = [str(p.user_id) for p in participations]
        grouping = []
        if participations:
            users = db.query(User).filter(User.id.in_([p.user_id for p in participations])).all()
            user_by_id = {u.id: u for u in users}
            role_rank = {r: i for i, r in enumerate(DebateService.ROLE_ORDER)}
            participations_sorted = sorted(participations, key=lambda p: role_rank.get(p.role, 99))
            grouping = [
                {
                    "user_id": str(p.user_id),
                    "name": (user_by_id.get(p.user_id).name if user_by_id.get(p.user_id) else ""),
                    "role": p.role,
                    "role_reason": p.role_reason,
                }
                for p in participations_sorted
            ]
        
        return {
            "id": str(debate.id),
            "topic": debate.topic,
            "description": debate.description,
            "duration": debate.duration,
            "invitation_code": debate.invitation_code,
            "class_id": str(debate.class_id),
            "teacher_id": str(debate.teacher_id),
            "status": debate.status,
            "participant_count": len(participations),
            "student_ids": student_ids,
            "grouping": grouping,
            "created_at": debate.created_at.isoformat()
        }
    
    @staticmethod
    def get_available_debates(
        db: Session,
        student_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取学生可参与的辩论列表
        
        Args:
            db: 数据库会话
            student_id: 学生ID
            
        Returns:
            可参与的辩论列表
        """
        # 获取学生的班级
        student = db.query(User).filter(User.id == uuid.UUID(student_id)).first()
        if not student or not student.class_id:
            return []
        
        # 获取该班级已发布的辩论
        debates = db.query(Debate).filter(
            Debate.class_id == student.class_id,
            Debate.status.in_(['published', 'draft'])
        ).order_by(Debate.created_at.desc()).all()
        
        result = []
        for debate in debates:
            # 检查学生是否已参与
            participation = db.query(DebateParticipation).filter(
                DebateParticipation.debate_id == debate.id,
                DebateParticipation.user_id == uuid.UUID(student_id)
            ).first()
            
            # 统计当前参与人数
            participant_count = db.query(DebateParticipation).filter(
                DebateParticipation.debate_id == debate.id
            ).count()

            participants = None
            if participation is not None:
                all_participations = db.query(DebateParticipation).filter(
                    DebateParticipation.debate_id == debate.id
                ).all()
                users = db.query(User).filter(User.id.in_([p.user_id for p in all_participations])).all()
                user_by_id = {u.id: u for u in users}
                role_rank = {r: i for i, r in enumerate(DebateService.ROLE_ORDER)}
                all_participations_sorted = sorted(all_participations, key=lambda p: role_rank.get(p.role, 99))

                def overall_score_for(uid: str) -> int:
                    assessment = AssessmentService.get_assessment(db=db, user_id=uid) or {}
                    values = [
                        float(assessment.get("logical_thinking", 50)),
                        float(assessment.get("expression_willingness", 50)),
                        float(assessment.get("stablecoin_knowledge", 50)),
                        float(assessment.get("financial_knowledge", 50)),
                        float(assessment.get("critical_thinking", 50)),
                    ]
                    return int(round(sum(values) / len(values)))

                participants = [
                    {
                        "user_id": str(p.user_id),
                        "name": (user_by_id.get(p.user_id).name if user_by_id.get(p.user_id) else ""),
                        "role": p.role,
                        "role_reason": p.role_reason,
                        "overall_score": overall_score_for(str(p.user_id)),
                    }
                    for p in all_participations_sorted
                ]
            
            result.append({
                "id": str(debate.id),
                "topic": debate.topic,
                "description": debate.description,
                "duration": debate.duration,
                "invitation_code": debate.invitation_code,
                "participant_count": participant_count,
                "is_joined": participation is not None,
                "role": participation.role if participation else None,
                "role_reason": participation.role_reason if participation else None,
                "participants": participants,
                "created_at": debate.created_at.isoformat()
            })
        
        return result

    @staticmethod
    def get_debate_participants_for_student(
        db: Session,
        debate_id: str,
        student_id: str
    ) -> List[Dict[str, Any]]:
        try:
            debate_uuid = uuid.UUID(debate_id)
            student_uuid = uuid.UUID(student_id)
        except ValueError as e:
            raise ValueError("Invalid debate_id or student_id") from e

        participation = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate_uuid,
            DebateParticipation.user_id == student_uuid
        ).first()
        if not participation:
            raise ValueError("您未参与该辩论")

        all_participations = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate_uuid
        ).all()

        users = db.query(User).filter(User.id.in_([p.user_id for p in all_participations])).all()
        user_by_id = {u.id: u for u in users}
        role_rank = {r: i for i, r in enumerate(DebateService.ROLE_ORDER)}
        all_participations_sorted = sorted(all_participations, key=lambda p: role_rank.get(p.role, 99))

        def overall_score_for(uid: str) -> int:
            assessment = AssessmentService.get_assessment(db=db, user_id=uid) or {}
            values = [
                float(assessment.get("logical_thinking", 50)),
                float(assessment.get("expression_willingness", 50)),
                float(assessment.get("stablecoin_knowledge", 50)),
                float(assessment.get("financial_knowledge", 50)),
                float(assessment.get("critical_thinking", 50)),
            ]
            return int(round(sum(values) / len(values)))

        return [
            {
                "user_id": str(p.user_id),
                "name": (user_by_id.get(p.user_id).name if user_by_id.get(p.user_id) else ""),
                "role": p.role,
                "role_reason": p.role_reason,
                "overall_score": overall_score_for(str(p.user_id)),
            }
            for p in all_participations_sorted
        ]

    @staticmethod
    def get_debate_participants_for_teacher(
        db: Session,
        debate_id: str,
    ) -> List[Dict[str, Any]]:
        try:
            debate_uuid = uuid.UUID(debate_id)
        except ValueError as e:
            raise ValueError("Invalid debate_id") from e

        all_participations = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate_uuid
        ).all()

        user_ids = [p.user_id for p in all_participations if p.user_id]
        users = []
        if user_ids:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_by_id = {u.id: u for u in users}

        role_rank = {r: i for i, r in enumerate(DebateService.ROLE_ORDER)}
        all_participations_sorted = sorted(all_participations, key=lambda p: role_rank.get(p.role, 99))

        def overall_score_for(uid: str) -> int:
            assessment = AssessmentService.get_assessment(db=db, user_id=uid) or {}
            values = [
                float(assessment.get("logical_thinking", 50)),
                float(assessment.get("expression_willingness", 50)),
                float(assessment.get("stablecoin_knowledge", 50)),
                float(assessment.get("financial_knowledge", 50)),
                float(assessment.get("critical_thinking", 50)),
            ]
            return int(round(sum(values) / len(values)))

        return [
            {
                "user_id": str(p.user_id),
                "name": (user_by_id.get(p.user_id).name if user_by_id.get(p.user_id) else ""),
                "role": p.role,
                "role_reason": p.role_reason,
                "overall_score": overall_score_for(str(p.user_id)) if p.user_id else 0,
            }
            for p in all_participations_sorted
        ]
    
    @staticmethod
    def join_debate_by_code(
        db: Session,
        student_id: str,
        invitation_code: str
    ) -> Dict[str, Any]:
        """
        通过邀请码加入辩论
        
        Args:
            db: 数据库会话
            student_id: 学生ID
            invitation_code: 邀请码
            
        Returns:
            辩论信息
            
        Raises:
            ValueError: 如果邀请码无效或已满员
        """
        # 查找辩论
        debate = db.query(Debate).filter(
            Debate.invitation_code == invitation_code,
            Debate.status.in_(['published', 'draft'])
        ).first()
        
        if not debate:
            raise ValueError("邀请码无效或辩论未发布")
        
        # 检查是否已参与
        existing = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate.id,
            DebateParticipation.user_id == uuid.UUID(student_id)
        ).first()
        
        if existing:
            return {
                "id": str(debate.id),
                "topic": debate.topic,
                "description": debate.description,
                "duration": debate.duration,
                "status": debate.status,
                "invitation_code": debate.invitation_code,
                "role": existing.role,
                "role_reason": existing.role_reason,
                "is_joined": True,
                "message": "验证成功，进入辩论"
            }
            
        # 如果未参与，提示不在邀请名单中
        # 根据需求：老师创建房间并指定学生，学生只能验证进入，不能动态加入
        raise ValueError("您不在该辩论的邀请名单中")
