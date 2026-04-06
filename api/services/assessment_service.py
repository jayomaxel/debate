"""
能力评估服务
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from models.assessment import AbilityAssessment
import uuid
import math


class AssessmentService:
    """能力评估服务类"""
    
    @staticmethod
    def recommend_role(
        expression_willingness: int,
        logical_thinking: int,
        personality_type: Optional[str] = None
    ) -> str:
        """
        根据评估结果推荐辩论角色
        
        Args:
            expression_willingness: 表达意愿（1-10）
            logical_thinking: 逻辑思维（1-10）
            personality_type: 性格类型（可选）
            
        Returns:
            推荐的角色（debater_1/2/3/4）
        """
        # 简单的推荐逻辑
        total_score = expression_willingness + logical_thinking
        
        # 一辩：需要强逻辑和表达能力
        if logical_thinking >= 8 and expression_willingness >= 7:
            return 'debater_1'
        
        # 二辩：需要较强的逻辑和提问能力
        elif logical_thinking >= 7 and expression_willingness >= 6:
            return 'debater_2'
        
        # 三辩：需要快速反应和辩驳能力
        elif expression_willingness >= 7 and logical_thinking >= 6:
            return 'debater_3'
        
        # 四辩：需要总结和升华能力
        else:
            return 'debater_4'
    
    @staticmethod
    def submit_assessment(
        db: Session,
        user_id: str,
        personality_type: Optional[str],
        expression_willingness: int,
        logical_thinking: int,
        stablecoin_knowledge: int,
        financial_knowledge: int,
        critical_thinking: int
    ) -> Dict[str, Any]:
        """
        提交能力评估
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            personality_type: 性格类型（MBTI）
            expression_willingness: 表达意愿（0-100）
            logical_thinking: 逻辑思维（0-100）
            stablecoin_knowledge: 稳定币知识（0-100）
            financial_knowledge: 金融知识（0-100）
            critical_thinking: 批判思维（0-100）
            
        Returns:
            评估结果和推荐角色
            
        Raises:
            ValueError: 如果参数无效
        """
        def validate_score(score: int, name: str) -> None:
            if not isinstance(score, int):
                raise ValueError(f"{name}必须为整数")
            if not (0 <= score <= 100):
                raise ValueError(f"{name}必须在0-100之间")

        validate_score(expression_willingness, "语言表达")
        validate_score(logical_thinking, "逻辑思维")
        validate_score(stablecoin_knowledge, "稳定币知识")
        validate_score(financial_knowledge, "金融知识")
        validate_score(critical_thinking, "批判思维")

        expression_willingness_10 = max(1, min(10, int(math.ceil(expression_willingness / 10)) if expression_willingness > 0 else 1))
        logical_thinking_10 = max(1, min(10, int(math.ceil(logical_thinking / 10)) if logical_thinking > 0 else 1))
        
        # 推荐角色
        recommended_role = AssessmentService.recommend_role(
            expression_willingness=expression_willingness_10,
            logical_thinking=logical_thinking_10,
            personality_type=personality_type
        )
        
        # 检查是否已有评估记录
        existing = db.query(AbilityAssessment).filter(
            AbilityAssessment.user_id == uuid.UUID(user_id)
        ).first()
        
        if existing:
            # 更新现有记录
            existing.personality_type = personality_type
            existing.expression_willingness = expression_willingness_10
            existing.logical_thinking = logical_thinking_10
            existing.expression_willingness_score = expression_willingness
            existing.logical_thinking_score = logical_thinking
            existing.stablecoin_knowledge_score = stablecoin_knowledge
            existing.financial_knowledge_score = financial_knowledge
            existing.critical_thinking_score = critical_thinking
            existing.is_default = False
            existing.recommended_role = recommended_role
            db.commit()
            assessment = existing
        else:
            # 创建新记录
            assessment = AbilityAssessment(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                personality_type=personality_type,
                expression_willingness=expression_willingness_10,
                logical_thinking=logical_thinking_10,
                expression_willingness_score=expression_willingness,
                logical_thinking_score=logical_thinking,
                stablecoin_knowledge_score=stablecoin_knowledge,
                financial_knowledge_score=financial_knowledge,
                critical_thinking_score=critical_thinking,
                is_default=False,
                recommended_role=recommended_role
            )
            db.add(assessment)
            db.commit()
            db.refresh(assessment)
        
        # 角色说明
        role_descriptions = {
            'debater_1': '一辩 - 立论陈词，奠定基调',
            'debater_2': '二辩 - 攻辩反击，定点堵塞',
            'debater_3': '三辩 - 逻辑交锋，快速反应',
            'debater_4': '四辩 - 总结陈词，价值升华'
        }
        
        return {
            "id": str(assessment.id),
            "personality_type": assessment.personality_type,
            "expression_willingness": assessment.expression_willingness_score if assessment.expression_willingness_score is not None else assessment.expression_willingness * 10,
            "logical_thinking": assessment.logical_thinking_score if assessment.logical_thinking_score is not None else assessment.logical_thinking * 10,
            "stablecoin_knowledge": assessment.stablecoin_knowledge_score if assessment.stablecoin_knowledge_score is not None else 50,
            "financial_knowledge": assessment.financial_knowledge_score if assessment.financial_knowledge_score is not None else 50,
            "critical_thinking": assessment.critical_thinking_score if assessment.critical_thinking_score is not None else 50,
            "is_default": bool(getattr(assessment, "is_default", False)),
            "recommended_role": assessment.recommended_role,
            "role_description": role_descriptions.get(assessment.recommended_role, ''),
            "message": "评估完成"
        }
    
    @staticmethod
    def get_assessment(
        db: Session,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取能力评估结果
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            
        Returns:
            评估结果，如果不存在则返回None
        """
        assessment = db.query(AbilityAssessment).filter(
            AbilityAssessment.user_id == uuid.UUID(user_id)
        ).first()
        
        if not assessment:
            expression_willingness = 70
            logical_thinking = 60
            stablecoin_knowledge = 50
            financial_knowledge = 65
            critical_thinking = 75

            expression_willingness_10 = max(1, min(10, int(math.ceil(expression_willingness / 10)) if expression_willingness > 0 else 1))
            logical_thinking_10 = max(1, min(10, int(math.ceil(logical_thinking / 10)) if logical_thinking > 0 else 1))
            recommended_role = AssessmentService.recommend_role(
                expression_willingness=expression_willingness_10,
                logical_thinking=logical_thinking_10,
                personality_type=None
            )

            assessment = AbilityAssessment(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                personality_type=None,
                expression_willingness=expression_willingness_10,
                logical_thinking=logical_thinking_10,
                expression_willingness_score=expression_willingness,
                logical_thinking_score=logical_thinking,
                stablecoin_knowledge_score=stablecoin_knowledge,
                financial_knowledge_score=financial_knowledge,
                critical_thinking_score=critical_thinking,
                is_default=True,
                recommended_role=recommended_role,
            )
            db.add(assessment)
            db.commit()
            db.refresh(assessment)
        
        role_descriptions = {
            'debater_1': '一辩 - 立论陈词，奠定基调',
            'debater_2': '二辩 - 攻辩反击，定点堵塞',
            'debater_3': '三辩 - 逻辑交锋，快速反应',
            'debater_4': '四辩 - 总结陈词，价值升华'
        }
        
        return {
            "id": str(assessment.id),
            "personality_type": assessment.personality_type,
            "expression_willingness": assessment.expression_willingness_score if assessment.expression_willingness_score is not None else assessment.expression_willingness * 10,
            "logical_thinking": assessment.logical_thinking_score if assessment.logical_thinking_score is not None else assessment.logical_thinking * 10,
            "stablecoin_knowledge": assessment.stablecoin_knowledge_score if assessment.stablecoin_knowledge_score is not None else 50,
            "financial_knowledge": assessment.financial_knowledge_score if assessment.financial_knowledge_score is not None else 50,
            "critical_thinking": assessment.critical_thinking_score if assessment.critical_thinking_score is not None else 50,
            "is_default": bool(getattr(assessment, "is_default", False)),
            "recommended_role": assessment.recommended_role,
            "role_description": role_descriptions.get(assessment.recommended_role, ''),
            "created_at": assessment.created_at.isoformat()
        }
