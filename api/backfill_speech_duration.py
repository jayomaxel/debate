import argparse

from sqlalchemy import select

import database
from logging_config import get_logger
from models.speech import Speech
from utils.audio_duration import (
    get_audio_duration_seconds,
    resolve_local_upload_path_from_audio_url,
)


logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chars-per-second", type=float, default=2.5)
    parser.add_argument("--min-seconds", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()

    database.init_engine()
    if database.SessionLocal is None:
        logger.error("数据库未初始化")
        return 2

    db = database.SessionLocal()
    try:
        stmt = select(Speech).where(Speech.duration == 0)
        if args.limit and args.limit > 0:
            stmt = stmt.limit(int(args.limit))
        speeches = db.execute(stmt).scalars().all()

        updated = 0
        skipped = 0
        for speech in speeches:
            if not speech.audio_url:
                skipped += 1
                continue
            local_path = resolve_local_upload_path_from_audio_url(speech.audio_url)
            if not local_path:
                skipped += 1
                continue
            new_duration = get_audio_duration_seconds(local_path)


            if not new_duration or new_duration <= 0:
                skipped += 1
                continue
            if not args.dry_run:
                speech.duration = int(new_duration)
            updated += 1

        if not args.dry_run:
            db.commit()

        logger.info(
            f"speech_duration_backfill done: total={len(speeches)} updated={updated} skipped={skipped} dry_run={args.dry_run}"
        )
        return 0
    except Exception as e:
        db.rollback()
        logger.error(f"speech_duration_backfill failed: {e}", exc_info=True)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
