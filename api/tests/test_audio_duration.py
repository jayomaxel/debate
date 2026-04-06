import argparse
import wave

from sqlalchemy import select

import database
from logging_config import get_logger
from models.speech import Speech
from utils.audio_duration import (
    estimate_duration_from_text,
    get_audio_duration_seconds,
    resolve_local_upload_path_from_audio_url,
)


logger = get_logger(__name__)


def test_estimate_duration_from_text_defaults():
    assert estimate_duration_from_text("你好") == 1
    assert estimate_duration_from_text("") == 0
    assert estimate_duration_from_text("   ") == 0


def test_get_audio_duration_seconds_wav(tmp_path):
    path = tmp_path / "a.wav"
    sample_rate = 8000
    seconds = 2
    frames = sample_rate * seconds
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * frames)

    assert get_audio_duration_seconds(path) == 2


def backfill_speeches_duration_from_audio(*, limit: int = 0, dry_run: bool = True) -> dict:
    database.init_engine()
    if database.SessionLocal is None:
        raise RuntimeError("数据库未初始化")

    db = database.SessionLocal()
    try:
        stmt = select(Speech).where(Speech.duration == 0)
        if int(limit or 0) > 0:
            stmt = stmt.limit(int(limit))
        speeches = db.execute(stmt).scalars().all()

        updated = 0
        missing_audio = 0
        unparsable = 0

        for speech in speeches:
            if not speech.audio_url:
                missing_audio += 1
                continue
            local_path = resolve_local_upload_path_from_audio_url(speech.audio_url)
            if not local_path:
                missing_audio += 1
                continue
            actual = get_audio_duration_seconds(local_path)
            if actual is None or actual <= 0:
                unparsable += 1
                continue
            if not dry_run:
                speech.duration = int(actual)
            updated += 1

        if not dry_run:
            db.commit()

        result = {
            "total": len(speeches),
            "updated": updated,
            "missing_audio": missing_audio,
            "unparsable": unparsable,
            "dry_run": bool(dry_run),
        }
        logger.info(f"backfill_speeches_duration_from_audio: {result}")
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()

    backfill_speeches_duration_from_audio(limit=int(args.limit), dry_run=bool(args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
