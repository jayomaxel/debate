"""
修复评分为0的问题
诊断并重新评分
"""
import asyncio
import sys
import uuid as uuid_lib
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


async def diagnose_and_fix_scoring(debate_id: str, force_rescore: bool = False):
    """
    诊断并修复评分问题
    
    Args:
        debate_id: 辩论ID
        force_rescore: 是否强制重新评分
    """
    init_engine()
    
    if SessionLocal is None:
        logger.error("数据库未初始化")
        return
    
    db = SessionLocal()
    
    try:
        # 转换debate_id为UUID
        try:
            debate_uuid = uuid_lib.UUID(debate_id)
        except ValueError:
            logger.error(f"无效的辩论ID: {debate_id}")
            return
        
        # 1. 检查辩论
        debate = db.execute(
            select(Debate).where(Debate.id == debate_uuid)
        ).scalar_one_or_none()
        
        if not debate:
            logger.error(f"辩论不存在: {debate_id}")
            return
        
        logger.info(f"\n{'='*60}")
        logger.info(f"辩论信息:")
        logger.info(f"  - ID: {debate.id}")
        logger.info(f"  - 辩题: {debate.topic}")
        logger.info(f"  - 状态: {debate.status}")
        logger.info(f"  - 开始时间: {debate.start_time}")
        logger.info(f"  - 结束时间: {debate.end_time}")
        logger.info(f"{'='*60}\n")
        
        # 2. 获取所有发言
        speeches = db.execute(
            select(Speech).where(
                Speech.debate_id == debate_uuid
            ).order_by(Speech.timestamp)
        ).scalars().all()
        
        logger.info(f"发言统计:")
        logger.info(f"  - 总发言数: {len(speeches)}")
        human_speeches = [s for s in speeches if s.speaker_type == "human"]
        ai_speeches = [s for s in speeches if s.speaker_type == "ai"]
        logger.info(f"  - 人类发言: {len(human_speeches)}")
        logger.info(f"  - AI发言: {len(ai_speeches)}\n")
        
        if not speeches:
            logger.warning("没有发言记录，无需评分")
            return
        
        # 3. 检查参与记录
        participations = db.execute(
            select(DebateParticipation).where(
                DebateParticipation.debate_id == debate_uuid
            )
        ).scalars().all()
        
        logger.info(f"参与记录:")
        logger.info(f"  - 总参与人数: {len(participations)}")
        for p in participations:
            logger.info(f"    * User ID: {p.user_id}, Role: {p.role}, Stance: {p.stance}")
        logger.info("")
        
        # 4. 检查现有评分
        existing_scores = db.execute(
            select(Score)
        ).scalars().all()
        
        # 过滤出本辩论的评分
        debate_scores = []
        for score in existing_scores:
            participation = db.execute(
                select(DebateParticipation).where(
                    DebateParticipation.id == score.participation_id
                )
            ).scalar_one_or_none()
            if participation and participation.debate_id == debate_uuid:
                debate_scores.append(score)
        
        logger.info(f"现有评分:")
        logger.info(f"  - 评分记录数: {len(debate_scores)}")
        
        zero_scores = [s for s in debate_scores if s.overall_score == 0]
        if zero_scores:
            logger.warning(f"  - ⚠️ 发现 {len(zero_scores)} 条评分为0的记录！")
        
        for score in debate_scores[:5]:  # 只显示前5条
            logger.info(f"    * Speech ID: {score.speech_id}, Score: {score.overall_score}")
        logger.info("")
        
        # 5. 测试裁判AI配置
        logger.info("检查裁判AI配置...")
        try:
            judge = JudgeAgent(db)
            await judge._get_config()
            logger.info(f"  ✓ 裁判AI配置正常")
            logger.info(f"    - Bot ID: {judge.bot_id}")
            logger.info(f"    - Base URL: {judge.base_url}\n")
        except Exception as e:
            logger.error(f"  ✗ 裁判AI配置错误: {e}")
            logger.error("    请检查数据库中的coze配置，确保judge_bot_id已设置\n")
            return
        
        # 6. 决定是否需要重新评分
        need_rescore = force_rescore or len(debate_scores) == 0 or len(zero_scores) > 0
        
        if not need_rescore:
            logger.info("✓ 评分记录正常，无需重新评分")
            return
        
        logger.info(f"{'='*60}")
        logger.info("开始重新评分...")
        logger.info(f"{'='*60}\n")
        
        # 7. 删除现有评分（如果强制重新评分）
        if force_rescore and debate_scores:
            logger.info(f"删除现有的 {len(debate_scores)} 条评分记录...")
            for score in debate_scores:
                db.delete(score)
            db.commit()
            logger.info("✓ 删除完成\n")
        
        # 8. 构建上下文
        context = []
        for speech in speeches:
            context.append({
                "speaker_role": speech.speaker_role,
                "speaker_type": speech.speaker_type,
                "phase": speech.phase,
                "content": speech.content,
                "timestamp": speech.timestamp.isoformat()
            })
        
        # 9. 重新评分
        scored_count = 0
        failed_count = 0
        
        for i, speech in enumerate(speeches, 1):
            try:
                logger.info(f"[{i}/{len(speeches)}] 评分发言: {speech.speaker_role} ({speech.speaker_type})")
                logger.info(f"  内容: {speech.content[:80]}...")
                
                # 获取或创建参与记录
                if speech.speaker_type == "ai":
                    # AI发言
                    ai_stance = "negative"
                    participation = db.execute(
                        select(DebateParticipation).where(
                            DebateParticipation.debate_id == debate_uuid,
                            DebateParticipation.role == speech.speaker_role,
                            DebateParticipation.stance == ai_stance
                        )
                    ).scalar_one_or_none()
                    
                    if not participation:
                        participation = DebateParticipation(
                            debate_id=debate_uuid,
                            user_id=None,
                            role=speech.speaker_role,
                            stance=ai_stance
                        )
                        db.add(participation)
                        db.flush()
                        logger.info(f"  创建AI参与记录: {participation.id}")
                else:
                    # 人类发言
                    participation = db.execute(
                        select(DebateParticipation).where(
                            DebateParticipation.debate_id == debate_uuid,
                            DebateParticipation.user_id == speech.speaker_id
                        )
                    ).scalar_one_or_none()
                    
                    if not participation:
                        logger.warning(f"  ⚠️ 未找到参与记录，跳过")
                        failed_count += 1
                        continue
                
                # 检查是否已评分
                existing = db.execute(
                    select(Score).where(Score.speech_id == speech.id)
                ).scalar_one_or_none()
                
                if existing and not force_rescore:
                    logger.info(f"  已有评分: {existing.overall_score}")
                    scored_count += 1
                    continue
                
                # 调用评分服务
                score = await ScoringService.score_speech(
                    db=db,
                    speech_id=str(speech.id),
                    participation_id=str(participation.id),
                    speech_content=speech.content,
                    speaker_role=speech.speaker_role,
                    phase=speech.phase,
                    context=context
                )
                
                logger.info(f"  ✓ 评分完成: {score.overall_score}")
                logger.info(f"    - 逻辑: {score.logic_score}, 论据: {score.argument_score}")
                logger.info(f"    - 反应: {score.response_score}, 说服: {score.persuasion_score}")
                logger.info(f"    - 团队: {score.teamwork_score}")
                
                if score.overall_score == 0:
                    logger.warning(f"  ⚠️ 评分为0，可能存在问题")
                
                scored_count += 1
                
            except Exception as e:
                logger.error(f"  ✗ 评分失败: {e}", exc_info=True)
                failed_count += 1
                continue
        
        logger.info(f"\n{'='*60}")
        logger.info(f"评分完成:")
        logger.info(f"  - 成功: {scored_count}/{len(speeches)}")
        logger.info(f"  - 失败: {failed_count}/{len(speeches)}")
        logger.info(f"{'='*60}\n")
        
        # 10. 验证评分结果
        final_scores = db.execute(
            select(Score)
        ).scalars().all()
        
        final_debate_scores = []
        for score in final_scores:
            participation = db.execute(
                select(DebateParticipation).where(
                    DebateParticipation.id == score.participation_id
                )
            ).scalar_one_or_none()
            if participation and participation.debate_id == debate_uuid:
                final_debate_scores.append(score)
        
        logger.info(f"最终评分统计:")
        logger.info(f"  - 总评分数: {len(final_debate_scores)}")
        
        zero_count = len([s for s in final_debate_scores if s.overall_score == 0])
        if zero_count > 0:
            logger.warning(f"  - ⚠️ 仍有 {zero_count} 条评分为0")
        else:
            logger.info(f"  - ✓ 所有评分都正常")
        
        avg_score = sum(s.overall_score for s in final_debate_scores) / len(final_debate_scores) if final_debate_scores else 0
        logger.info(f"  - 平均分: {avg_score:.2f}")
        
    finally:
        db.close()


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python fix_scoring_issue.py <debate_id> [--force]")
        print("示例: python fix_scoring_issue.py 12345678-1234-1234-1234-123456789abc")
        print("      python fix_scoring_issue.py 12345678-1234-1234-1234-123456789abc --force")
        print("")
        print("参数:")
        print("  debate_id  辩论ID (UUID格式)")
        print("  --force    强制重新评分（删除现有评分）")
        return
    
    debate_id = sys.argv[1]
    force_rescore = "--force" in sys.argv
    
    await diagnose_and_fix_scoring(debate_id, force_rescore)


if __name__ == "__main__":
    asyncio.run(main())
