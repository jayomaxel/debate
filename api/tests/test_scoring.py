import asyncio
import sys
import os
from uuid import UUID

# Ensure api directory is in sys.path
sys.path.append(os.getcwd())

from database import get_db, init_engine
from services.room_manager import DebateRoomManager
from models.debate import Debate
from sqlalchemy import select

async def main():
    debate_id_str = "e0db9fc0-5f44-4c01-a375-2e994db2c0d8"
    try:
        debate_id = UUID(debate_id_str)
    except ValueError:
        print(f"Invalid UUID: {debate_id_str}")
        return
    
    init_engine()
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        print(f"Starting manual scoring for debate {debate_id}...")
        
        # Check if debate exists
        debate = db.execute(select(Debate).where(Debate.id == debate_id)).scalar_one_or_none()
        if not debate:
            print(f"Error: Debate {debate_id} not found!")
            return
        
        # Ensure status is completed (though not strictly required for scoring logic, good for consistency)
        if debate.status != "completed":
            print(f"Warning: Debate status is '{debate.status}', expected 'completed'. Scoring anyway...")

        manager = DebateRoomManager()
        # This function handles finding speeches, scoring them, and generating the report
        await manager._auto_score_and_generate_report(db, debate_id)
        
        print("Scoring process finished.")
        
        # Verify report data
        # Need to commit or refresh to see changes if they were committed in the function
        db.expire_all() 
        debate = db.execute(select(Debate).where(Debate.id == debate_id)).scalar_one()
        
        if debate.report:
            print("SUCCESS: Report data generated and saved.")
            # Print a summary of the report to verify structure
            report = debate.report
            print(f"Winner: {report.get('winner')}")
            print(f"Winning Reason: {report.get('winning_reason')}")
            print(f"Scores: {report.get('scores')}")
        else:
            print("FAILURE: Report field is empty after processing.")
            
    except Exception as e:
        print(f"Error during scoring: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
