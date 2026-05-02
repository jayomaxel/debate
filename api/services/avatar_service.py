"""
Avatar service for default avatar metadata and custom avatar storage.
"""
import base64
import imghdr
import io
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from config import BASE_DIR, settings
from models.user import User

DEFAULT_AVATAR_DIR = BASE_DIR / settings.UPLOAD_DIR / "defaults" / "avatars"
MAX_AVATAR_BYTES = settings.AVATAR_MAX_UPLOAD_SIZE
ALLOWED_IMAGE_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}
DEFAULT_AVATAR_SPECS = [
    {
        "key": "minimal-block-01",
        "label": "海盐方格",
        "filename": "default-avatar-01.png",
        "palette": ["#F4EFE6", "#2E4057", "#D96C54", "#F0C66E"],
    },
    {
        "key": "minimal-block-02",
        "label": "松石拼片",
        "filename": "default-avatar-02.png",
        "palette": ["#EFF7F6", "#4F6D7A", "#56A3A6", "#C0D6DF"],
    },
    {
        "key": "minimal-block-03",
        "label": "日曜矩阵",
        "filename": "default-avatar-03.png",
        "palette": ["#F7F3E9", "#264653", "#E76F51", "#E9C46A"],
    },
    {
        "key": "minimal-block-04",
        "label": "雾蓝叠片",
        "filename": "default-avatar-04.png",
        "palette": ["#F8FAFC", "#3A506B", "#5BC0BE", "#CDE7F0"],
    },
    {
        "key": "minimal-block-05",
        "label": "暖棕几何",
        "filename": "default-avatar-05.png",
        "palette": ["#FAF7F2", "#5C4B51", "#C17767", "#E6C79C"],
    },
]


def _base64_data_uri(mime_type: str, data: bytes) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _normalize_public_path(path: Path) -> str:
    relative = path.relative_to(BASE_DIR / settings.UPLOAD_DIR).as_posix()
    return f"/uploads/{relative}"


class AvatarService:
    @staticmethod
    def ensure_default_avatar_dir() -> None:
        DEFAULT_AVATAR_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_default_avatar_specs() -> List[Dict[str, Any]]:
        AvatarService.ensure_default_avatar_dir()
        specs: List[Dict[str, Any]] = []
        for item in DEFAULT_AVATAR_SPECS:
            image_path = DEFAULT_AVATAR_DIR / item["filename"]
            specs.append(
                {
                    "key": item["key"],
                    "label": item["label"],
                    "palette": item["palette"],
                    "avatar_url": _normalize_public_path(image_path),
                }
            )
        return specs

    @staticmethod
    def validate_default_key(default_key: str) -> str:
        normalized = (default_key or "").strip()
        valid_keys = {item["key"] for item in DEFAULT_AVATAR_SPECS}
        if normalized not in valid_keys:
            raise ValueError("默认头像不存在")
        return normalized

    @staticmethod
    def _resolve_default_avatar_url(default_key: Optional[str]) -> Optional[str]:
        if not default_key:
            return None
        for item in AvatarService.get_default_avatar_specs():
            if item["key"] == default_key:
                return item["avatar_url"]
        return None

    @staticmethod
    def _detect_image_type(content: bytes) -> str:
        image_type = imghdr.what(None, h=content)
        if image_type == "jpg":
            image_type = "jpeg"
        if image_type not in ALLOWED_IMAGE_TYPES:
            raise ValueError("仅支持 PNG、JPEG 或 WebP 头像")
        return image_type

    @staticmethod
    def normalize_avatar_upload(content: bytes, filename: Optional[str]) -> Dict[str, Any]:
        if not content:
            raise ValueError("头像文件不能为空")
        if len(content) > MAX_AVATAR_BYTES:
            raise ValueError("头像文件不能超过 2MB")

        image_type = AvatarService._detect_image_type(content)
        mime_type = ALLOWED_IMAGE_TYPES[image_type]
        suffix = "jpg" if image_type == "jpeg" else image_type
        safe_name = (filename or f"avatar.{suffix}").strip() or f"avatar.{suffix}"

        # Keep storage compact by reusing the original bytes unless we can optimize
        # via Pillow. Falling back silently keeps the upload path reliable.
        optimized = content
        try:
            from PIL import Image, ImageOps  # type: ignore

            image = Image.open(io.BytesIO(content))
            image = ImageOps.exif_transpose(image)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if image_type == "png" else "RGB")
            image.thumbnail((512, 512))
            out = io.BytesIO()
            if image_type == "png":
                image.save(out, format="PNG", optimize=True)
            elif image_type == "webp":
                image.save(out, format="WEBP", quality=88, method=6)
            else:
                if image.mode == "RGBA":
                    image = image.convert("RGB")
                image.save(out, format="JPEG", quality=88, optimize=True)
            optimized = out.getvalue() or content
        except Exception:
            optimized = content

        if len(optimized) > MAX_AVATAR_BYTES:
            raise ValueError("头像压缩后仍超过 2MB，请上传更小的图片")

        return {
            "blob": optimized,
            "mime_type": mime_type,
            "filename": safe_name,
        }

    @staticmethod
    def apply_custom_avatar(
        db: Session,
        user: User,
        content: bytes,
        filename: Optional[str],
    ) -> Dict[str, Any]:
        normalized = AvatarService.normalize_avatar_upload(content, filename)
        user.avatar_blob = normalized["blob"]
        user.avatar_mime_type = normalized["mime_type"]
        user.avatar_filename = normalized["filename"]
        user.avatar_default_key = None
        db.commit()
        db.refresh(user)
        return AvatarService.build_avatar_payload(user)

    @staticmethod
    def apply_default_avatar(
        db: Session,
        user: User,
        default_key: str,
    ) -> Dict[str, Any]:
        normalized_key = AvatarService.validate_default_key(default_key)
        user.avatar_blob = None
        user.avatar_mime_type = None
        user.avatar_filename = None
        user.avatar_default_key = normalized_key
        db.commit()
        db.refresh(user)
        return AvatarService.build_avatar_payload(user)

    @staticmethod
    def clear_avatar(db: Session, user: User) -> Dict[str, Any]:
        user.avatar_blob = None
        user.avatar_mime_type = None
        user.avatar_filename = None
        user.avatar_default_key = None
        db.commit()
        db.refresh(user)
        return AvatarService.build_avatar_payload(user)

    @staticmethod
    def build_avatar_payload(user: User) -> Dict[str, Any]:
        avatar_mode = "none"
        avatar_url = None
        if user.avatar_blob and user.avatar_mime_type:
            avatar_mode = "custom"
            avatar_url = _base64_data_uri(user.avatar_mime_type, user.avatar_blob)
        elif user.avatar_default_key:
            avatar_mode = "default"
            avatar_url = AvatarService._resolve_default_avatar_url(user.avatar_default_key)

        return {
            "avatar": avatar_url,
            "avatar_url": avatar_url,
            "avatar_mode": avatar_mode,
            "avatar_default_key": user.avatar_default_key,
        }

    @staticmethod
    def list_default_avatars() -> List[Dict[str, Any]]:
        return AvatarService.get_default_avatar_specs()

    @staticmethod
    def get_user(db: Session, user_id: str) -> User:
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if not user:
            raise ValueError("用户不存在")
        return user
