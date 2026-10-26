"""Photos of handwritten family recipes, cookbook scans, screenshots, PDFs.

Images and PDFs are passed to Claude as vision/document blocks, so the
converter reads them directly (handwriting, Arabic, French all fine).
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from . import RawSource

IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
               ".webp": "image/webp", ".gif": "image/gif"}


def _heic_to_jpeg(path: Path) -> tuple[bytes, str]:
    try:
        from PIL import Image
        import pillow_heif  # type: ignore
        pillow_heif.register_heif_opener()
        import io
        buf = io.BytesIO()
        Image.open(path).convert("RGB").save(buf, "JPEG", quality=90)
        return buf.getvalue(), "image/jpeg"
    except Exception as exc:
        raise RuntimeError("HEIC needs `pip install pillow pillow-heif`, or export the photo as JPEG.") from exc


def _shrink(data: bytes, mime: str, max_side: int = 2000) -> tuple[bytes, str]:
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        if max(img.size) <= max_side and len(data) < 4_500_000:
            return data, mime
        img.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=88)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return data, mime


def image_block(data: bytes, mime: str) -> dict:
    data, mime = _shrink(data, mime)
    return {"type": "image", "source": {"type": "base64", "media_type": mime,
                                        "data": base64.b64encode(data).decode()}}


def pdf_block(data: bytes) -> dict:
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                           "data": base64.b64encode(data).decode()}}


def extract_bytes(data: bytes, filename: str) -> RawSource:
    suffix = Path(filename).suffix.lower()
    if suffix in (".txt", ".md"):
        return RawSource(kind="text", text=data.decode("utf-8", "ignore"), title=Path(filename).stem)
    if suffix == ".pdf":
        return RawSource(kind="pdf", title=Path(filename).stem, media=[pdf_block(data)],
                         text="The recipe is in the attached PDF.")
    mime = IMAGE_TYPES.get(suffix) or mimetypes.guess_type(filename)[0] or "image/jpeg"
    return RawSource(kind="image", title=Path(filename).stem, media=[image_block(data, mime)],
                     text="The recipe is in the attached photo (may be handwritten, Arabic/French/German).")


def extract_file(path: Path) -> RawSource:
    if path.suffix.lower() == ".heic":
        data, _ = _heic_to_jpeg(path)
        return extract_bytes(data, path.with_suffix(".jpg").name)
    return extract_bytes(path.read_bytes(), path.name)
