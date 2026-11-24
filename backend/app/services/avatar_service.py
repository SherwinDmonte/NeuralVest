"""Profile pictures (Phase 12B, your request 2026-11-24).

An upload is never stored as sent. Pillow decodes it, rejects anything that is not a real JPEG,
PNG or WebP image (or is suspiciously large), applies the EXIF rotation, crops it to a centred
square and re-encodes it as a 256 x 256 WebP. Re-encoding drops all metadata, including GPS
positions in phone photos, and anything hidden after the image data. The result (usually 10 to
30 KB) is kept in the `user_avatars` collection, one document per user.
"""

import io
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError
from pymongo.database import Database

from app.database.models import SCHEMA_VERSION, USER_AVATARS, USERS
from app.utils.timing import utc_now

AVATAR_SIZE = 256
CONTENT_TYPE = "image/webp"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000  # about 7000 x 5700; refuses decompression bombs before decoding
ACCEPTED_TYPES = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


class AvatarError(ValueError):
    """An upload that cannot become a profile picture. `code` is the API error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def process_image(raw: bytes) -> bytes:
    """Validate an uploaded image and return the stored 256 x 256 WebP bytes."""
    if not raw:
        raise AvatarError("invalid_image", "The upload is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise AvatarError("file_too_large", f"The image is over {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in ACCEPTED_TYPES.values():
                raise AvatarError("unsupported_media_type", "Use a JPEG, PNG or WebP image.")
            if source.width * source.height > MAX_PIXELS:
                raise AvatarError("invalid_image", "The image has too many pixels.")
            image = ImageOps.exif_transpose(source)  # first frame of an animation; rotation applied
            image.load()
    except AvatarError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError) as exc:
        raise AvatarError("invalid_image", "The file is not a readable image.") from exc

    has_alpha = image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info)
    image = image.convert("RGBA" if has_alpha else "RGB")
    square = ImageOps.fit(image, (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    out = io.BytesIO()
    square.save(out, "WEBP", quality=85, method=4)  # no exif/icc passed: metadata is dropped
    return out.getvalue()


def save_avatar(db: Database, user_id: str, data: bytes) -> None:
    now = utc_now()
    db[USER_AVATARS].update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "content_type": CONTENT_TYPE, "data": data, "size_bytes": len(data),
                  "width": AVATAR_SIZE, "height": AVATAR_SIZE, "updated_at": now, "schema_version": SCHEMA_VERSION}},
        upsert=True,
    )
    db[USERS].update_one({"user_id": user_id}, {"$set": {"avatar_updated_at": now, "updated_at": now}})


def get_avatar(db: Database, user_id: str) -> dict[str, Any] | None:
    return db[USER_AVATARS].find_one({"user_id": user_id}, {"_id": 0, "data": 1, "content_type": 1, "updated_at": 1})


def delete_avatar(db: Database, user_id: str) -> bool:
    deleted = db[USER_AVATARS].delete_one({"user_id": user_id}).deleted_count > 0
    db[USERS].update_one({"user_id": user_id}, {"$unset": {"avatar_updated_at": ""}, "$set": {"updated_at": utc_now()}})
    return deleted
