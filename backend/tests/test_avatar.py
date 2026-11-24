"""Profile pictures (Phase 12B): upload, re-encoding, limits and privacy - against the TEST database."""

import io

import pytest
from PIL import Image

from app.database import models as m
from app.services import avatar_service
from tests.test_api_phase11 import client, error_code, login, runner  # noqa: F401 (fixtures)

pytestmark = pytest.mark.integration


def image_bytes(fmt="PNG", size=(640, 480), color=(20, 120, 220), mode="RGB", exif=None) -> bytes:
    img = Image.new(mode, size, color)
    out = io.BytesIO()
    kwargs = {"exif": exif} if exif is not None else {}
    img.save(out, fmt, **kwargs)
    return out.getvalue()


def put(client, headers, data, content_type="image/png"):
    return client.put("/api/auth/me/avatar", content=data, headers={**headers, "Content-Type": content_type})


# ---------------------------------------------------------------- unit: processing
def test_process_image_makes_a_square_webp_without_metadata():
    exif = Image.Exif()
    exif[0x8825] = {2: (12.0, 58.0, 0.0)}  # a GPS latitude, as phone photos carry
    exif[0x010F] = "PhoneMaker"
    out = avatar_service.process_image(image_bytes("JPEG", (1200, 800), exif=exif))
    with Image.open(io.BytesIO(out)) as img:
        assert img.format == "WEBP" and img.size == (256, 256)
        assert not img.getexif() and "exif" not in img.info
    assert len(out) < 262144


def test_process_image_keeps_transparency():
    out = avatar_service.process_image(image_bytes("PNG", (300, 300), (0, 0, 0, 0), mode="RGBA"))
    with Image.open(io.BytesIO(out)) as img:
        assert img.mode == "RGBA"


@pytest.mark.parametrize("raw, code", [
    (b"", "invalid_image"),
    (b"not an image at all", "invalid_image"),
    (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "invalid_image"),  # a PNG signature with nothing behind it
])
def test_process_image_rejects_non_images(raw, code):
    with pytest.raises(avatar_service.AvatarError) as exc:
        avatar_service.process_image(raw)
    assert exc.value.code == code


def test_process_image_rejects_other_formats_and_pixel_bombs():
    with pytest.raises(avatar_service.AvatarError) as exc:
        avatar_service.process_image(image_bytes("GIF", (64, 64), mode="P", color=1))
    assert exc.value.code == "unsupported_media_type"
    # 8000 x 8000 of one colour compresses to a small file but would need 256 MB to decode
    with pytest.raises(avatar_service.AvatarError) as exc:
        avatar_service.process_image(image_bytes("PNG", (8000, 8000), mode="L", color=0))
    assert exc.value.code == "invalid_image"


# ---------------------------------------------------------------- API
def test_upload_get_and_remove_avatar(client, clean_db):
    headers = login(client)
    assert client.get("/api/auth/me", headers=headers).json()["user"]["avatar_version"] is None
    assert error_code(client.get("/api/auth/me/avatar", headers=headers)) == "avatar_not_found"

    r = put(client, headers, image_bytes("JPEG", (900, 600)), "image/jpeg")
    assert r.status_code == 200, r.text
    version = r.json()["user"]["avatar_version"]
    assert isinstance(version, int)
    assert client.get("/api/auth/me", headers=headers).json()["user"]["avatar_version"] == version

    got = client.get("/api/auth/me/avatar", headers=headers)
    assert got.status_code == 200 and got.headers["content-type"] == "image/webp"
    assert got.headers["x-content-type-options"] == "nosniff" and "private" in got.headers["cache-control"]
    with Image.open(io.BytesIO(got.content)) as img:
        assert img.size == (256, 256)
    stored = clean_db[m.USER_AVATARS].find_one({})
    assert stored["size_bytes"] == len(got.content) and "password_hash" not in stored

    # replacing keeps one document per user
    assert put(client, headers, image_bytes("PNG", (300, 300), (200, 30, 30))).status_code == 200
    assert clean_db[m.USER_AVATARS].count_documents({}) == 1

    r = client.delete("/api/auth/me/avatar", headers=headers)
    assert r.status_code == 200 and r.json()["user"]["avatar_version"] is None
    assert clean_db[m.USER_AVATARS].count_documents({}) == 0
    assert client.get("/api/auth/me/avatar", headers=headers).status_code == 404


def test_avatar_errors(client, clean_db):
    headers = login(client)
    assert error_code(put(client, headers, image_bytes(), "image/gif")) == "unsupported_media_type"
    assert error_code(put(client, headers, image_bytes(), "text/plain")) == "unsupported_media_type"
    r = put(client, headers, b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/png")
    assert r.status_code == 422 and error_code(r) == "invalid_image"
    big = b"\x00" * (avatar_service.MAX_UPLOAD_BYTES + 1)
    r = put(client, headers, big, "image/png")
    assert r.status_code == 413 and error_code(r) == "file_too_large"
    assert clean_db[m.USER_AVATARS].count_documents({}) == 0


def test_avatar_needs_login_and_is_per_user(client, clean_db):
    assert put(client, {}, image_bytes()).status_code == 401
    assert client.get("/api/auth/me/avatar").status_code == 401
    asha = login(client)
    ravi = login(client, email="ravi@example.com")
    assert put(client, asha, image_bytes()).status_code == 200
    assert client.get("/api/auth/me/avatar", headers=asha).status_code == 200
    assert client.get("/api/auth/me/avatar", headers=ravi).status_code == 404
