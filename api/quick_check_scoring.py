"""
快速检查最近辩论的评分情况
"""
import asyncio
from sqlalchemy import select, desc
from database import SessionLocal, init_engine,get_db
from models.debate import Debate, DebateParticipation
from models.speech import Speech
from models.score import Score
from logging_config import get_logger

logger = get_logger(__name__)


async def check_recent_debates(limit: int = 5):
    """
    检查最近的辩论评分情况
    
    Args:
        limit: 检查最近几场辩论
    """
    init_engine()
    
    if SessionLocal is None:
        print("错误: 数据库未初始化")
        return
    
    db = SessionLocal()
    
    try:
        # 获取最近的辩论
        debates = db.execute(
            select(Debate).order_by(desc(Debate.created_at)).limit(limit)
        ).scalars().all()
        
        print(f"\n{'='*80}")
        print(f"最近 {len(debates)} 场辩论的评分情况")
        print(f"{'='*80}\n")
        
        for i, debate in enumerate(debates, 1):
            print(f"{i}. 辩论: {debate.topic}")
            print(f"   ID: {debate.id}")
            print(f"   状态: {debate.status}")
            print(f"   创建时间: {debate.created_at}")
            
            # 获取发言数
            speeches = db.execute(
                select(Speech).where(Speech.debate_id == debate.id)
            ).scalars().all()
            
            print(f"   发言数: {len(speeches)}")
            
            # 获取评分数
            participations = db.execute(
                select(DebateParticipation).where(
                    DebateParticipation.debate_id == debate.id
                )
            ).scalars().all()
            
            all_scores = []
            for p in participations:
                scores = db.execute(
                    select(Score).where(Score.participation_id == p.id)
                ).scalars().all()
                all_scores.extend(scores)
            
            print(f"   评分数: {len(all_scores)}")
            
            if len(all_scores) == 0:
                print(f"   ⚠️  警告: 没有评分记录！")
            else:
                zero_scores = [s for s in all_scores if s.overall_score == 0]
                if zero_scores:
                    print(f"   ⚠️  警告: {len(zero_scores)} 条评分为0！")
                else:
                    avg_score = sum(s.overall_score for s in all_scores) / len(all_scores)
                    print(f"   ✓  平均分: {avg_score:.2f}")
            
            print()
        
        print(f"{'='*80}\n")
        
    finally:
        db.close()


async def check_specific_debate(debate_id: str):
    """
    检查特定辩论的详细评分情况
    
    Args:
        debate_id: 辩论ID
    """
    init_engine()
    
    if SessionLocal is None:
        print("错误: 数据库未初始化")
        return
    
    db = SessionLocal()
    
    try:
        import uuid
        debate_uuid = uuid.UUID(debate_id)
        
        debate = db.execute(
            select(Debate).where(Debate.id == debate_uuid)
        ).scalar_one_or_none()
        
        if not debate:
            print(f"辩论不存在: {debate_id}")
            return
        
        print(f"\n{'='*80}")
        print(f"辩论详情")
        print(f"{'='*80}\n")
        print(f"辩题: {debate.topic}")
        print(f"状态: {debate.status}")
        print(f"开始: {debate.start_time}")
        print(f"结束: {debate.end_time}\n")
        
        # 发言统计
        speeches = db.execute(
            select(Speech).where(Speech.debate_id == debate_uuid).order_by(Speech.timestamp)
        ).scalars().all()
        
        print(f"发言统计:")
        print(f"  总数: {len(speeches)}")
        print(f"  人类: {len([s for s in speeches if s.speaker_type == 'human'])}")
        print(f"  AI: {len([s for s in speeches if s.speaker_type == 'ai'])}\n")
        
        # 参与者统计
        participations = db.execute(
            select(DebateParticipation).where(
                DebateParticipation.debate_id == debate_uuid
            )
        ).scalars().all()
        
        print(f"参与者:")
        for p in participations:
            print(f"  - {p.role} ({p.stance})")
            
            # 该参与者的评分
            scores = db.execute(
                select(Score).where(Score.participation_id == p.id)
            ).scalars().all()
            
            if scores:
                avg = sum(s.overall_score for s in scores) / len(scores)
                print(f"    评分数: {len(scores)}, 平均分: {avg:.2f}")
                
                zero_count = len([s for s in scores if s.overall_score == 0])
                if zero_count > 0:
                    print(f"    ⚠️  {zero_count} 条评分为0")
            else:
                print(f"    ⚠️  无评分记录")
        
        print(f"\n{'='*80}\n")
        
    finally:
        db.close()


async def main(debate_id):
    """主函数"""
    await check_specific_debate(debate_id)


if __name__ == "__main__":
    asyncio.run(main("e99c75b0-a600-4a4d-b311-4f616f78f0d9"))
