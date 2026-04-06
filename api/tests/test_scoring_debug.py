"""
测试评分逻辑 - 调试辩论结束时评分为0的问题
"""
import asyncio
import sys
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal, init_engine
from models.debate import Debate, DebateParticipation
from models.speech import Speech
from models.score import Score
from services.scoring_service import ScoringService
from agents.judge_agent import JudgeAgent
from logging_config import get_logger

logger = get_logger(__name__)


async def test_scoring_for_debate(debate_id: str):
    """
    测试指定辩论的评分逻辑
    
    Args:
        debate_id: 辩论ID
    """
    init_engine()
    
    if SessionLocal is None:
        logger.error("数据库未初始化")
        return
    
    db = SessionLocal()
    
    try:
        # 1. 检查辩论是否存在
        debate = db.execute(
            select(Debate).where(Debate.id == debate_id)
        ).scalar_one_or_none()
        
        if not debate:
            logger.error(f"辩论不存在: {debate_id}")
            return
        
        logger.info(f"找到辩论: {debate.topic}, 状态: {debate.status}")
        
        # 2. 获取所有发言
        speeches = db.execute(
            select(Speech).where(
                Speech.debate_id == debate_id
            ).order_by(Speech.timestamp)
        ).scalars().all()
        
        logger.info(f"找到 {len(speeches)} 条发言")
        
        if not speeches:
            logger.warning("没有发言记录，无法评分")
            return
        
        # 3. 检查现有评分
        existing_scores = db.execute(
            select(Score).join(
                DebateParticipation,
                Score.participation_id == DebateParticipation.id
            ).where(
                DebateParticipation.debate_id == debate_id
            )
        ).scalars().all()
        
        logger.info(f"现有评分记录: {len(existing_scores)} 条")
        
        for score in existing_scores:
            logger.info(f"  - Speech ID: {score.speech_id}, Overall Score: {score.overall_score}")
        
        # 4. 测试裁判AI配置
        logger.info("测试裁判AI配置...")
        try:
            judge = JudgeAgent(db)
            await judge._get_config()
            logger.info(f"裁判AI配置正常: bot_id={judge.bot_id}")
        except Exception as e:
            logger.error(f"裁判AI配置错误: {e}", exc_info=True)
            return
        
        # 5. 测试单条发言评分
        test_speech = speeches[0]
        logger.info(f"\n测试评分第一条发言:")
        logger.info(f"  - Speaker: {test_speech.speaker_role}")
        logger.info(f"  - Phase: {test_speech.phase}")
        logger.info(f"  - Content: {test_speech.content[:100]}...")
        
        # 构建上下文
        context = []
        for speech in speeches[:10]:  # 只取前10条作为上下文
            context.append({
                "speaker_role": speech.speaker_role,
                "speaker_type": speech.speaker_type,
                "phase": speech.phase,
                "content": speech.content,
                "timestamp": speech.timestamp.isoformat()
            })
        
        # 调用评分
        try:
            score_breakdown = await judge.score_speech(
                speech_content=test_speech.content,
                speaker_role=test_speech.speaker_role,
                phase=test_speech.phase,
                context=context
            )
            
            logger.info(f"\n评分结果:")
            logger.info(f"  - 逻辑性: {score_breakdown.logic_score}")
            logger.info(f"  - 论据质量: {score_breakdown.argument_score}")
            logger.info(f"  - 反应速度: {score_breakdown.response_score}")
            logger.info(f"  - 说服力: {score_breakdown.persuasion_score}")
            logger.info(f"  - 团队配合: {score_breakdown.teamwork_score}")
            logger.info(f"  - 综合得分: {score_breakdown.overall_score}")
            logger.info(f"  - 反馈: {score_breakdown.feedback}")
            
            if score_breakdown.overall_score == 0:
                logger.error("⚠️ 评分为0！这是问题所在！")
            elif score_breakdown.overall_score == 70:
                logger.warning("⚠️ 评分为默认值70，可能是AI调用失败")
            else:
                logger.info("✓ 评分正常")
                
        except Exception as e:
            logger.error(f"评分过程出错: {e}", exc_info=True)
        
        # 6. 检查参与记录
        participations = db.execute(
            select(DebateParticipation).where(
                DebateParticipation.debate_id == debate_id
            )
        ).scalars().all()
        
        logger.info(f"\n参与记录: {len(participations)} 条")
        for p in participations:
            logger.info(f"  - User ID: {p.user_id}, Role: {p.role}, Stance: {p.stance}")
        
        # 7. 检查是否所有发言都有对应的参与记录
        for speech in speeches:
            if speech.speaker_type == "human":
                participation = db.execute(
                    select(DebateParticipation).where(
                        DebateParticipation.debate_id == debate_id,
                        DebateParticipation.user_id == speech.speaker_id
                    )
                ).scalar_one_or_none()
                
                if not participation:
                    logger.warning(f"⚠️ 发言 {speech.id} 没有对应的参与记录！")
        
    finally:
        db.close()


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python test_scoring_debug.py <debate_id>")
        print("示例: python test_scoring_debug.py 12345678-1234-1234-1234-123456789abc")
        return
    
    debate_id = sys.argv[1]
    await test_scoring_for_debate(debate_id)


if __name__ == "__main__":
    asyncio.run(main())
