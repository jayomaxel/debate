import math
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Optional


def estimate_duration_from_text(
    text: str, *, chars_per_second: float = 2.5, min_seconds: int = 1
) -> int:
    if not isinstance(text, str):
        return 0
    stripped = text.strip()
    if not stripped:
        return 0
    cps = float(chars_per_second) if chars_per_second else 0.0
    if cps <= 0:
        return 0
    estimated = int(math.ceil(len(stripped) / cps))
    return max(int(min_seconds), estimated) if estimated > 0 else 0


def resolve_local_upload_path_from_audio_url(audio_url: str) -> Optional[Path]:
    if not isinstance(audio_url, str) or not audio_url.strip():
        return None
    url = audio_url.strip().split("?", 1)[0].split("#", 1)[0]
    if url.startswith("http://") or url.startswith("https://"):
        return None
    if "/uploads/" in url:
        idx = url.find("/uploads/")
        rel = url[idx + 1 :].lstrip("/")
    else:
        rel = url.lstrip("/")
    if not rel.startswith("uploads/"):
        return None
    path = Path(rel)
    if any(part == ".." for part in path.parts):
        return None
    return path


def get_audio_duration_seconds(file_path: Path) -> Optional[int]:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        print(f"音频文件不存在,path:{path.as_posix()}")
        return 0

    ext = path.suffix.lower().lstrip(".")
    if ext == "wav":
        try:
            with wave.open(str(path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if not rate:
                    return 0
                return int(math.ceil(frames / float(rate)))
        except Exception:
            return 0
    else:
        return 0




if __name__ == "__main__":
    file_path="/uploads/audio/c7e1a17c-ec8a-4ad4-8ef3-74d5105b872f_71f24992-d42b-4933-939b-74dbe4b3d016_1770141117612.wav"
    file_path=resolve_local_upload_path_from_audio_url(file_path)
    duration=get_audio_duration_seconds(file_path)
    print(duration)