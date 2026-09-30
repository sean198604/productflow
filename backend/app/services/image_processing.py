import asyncio
import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BadRequestError
from app.models import StoredFile

settings = get_settings()


@dataclass(frozen=True, slots=True)
class TransparentImage:
    payload: bytes
    width: int
    height: int
    background_removed: bool


def _safe_png_filename(original_filename: str, digest: str) -> str:
    stem = Path(original_filename).stem
    normalized = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "-", normalized).strip("-._") or "image"
    return f"{digest[:12]}-{clean[:110]}-transparent.png"


def remove_white_background(payload: bytes) -> TransparentImage:
    """Create a cropped transparent PNG by removing edge-connected near-white pixels.

    Only pixels connected to the canvas edge are removed. This preserves white areas inside
    the product itself while handling the ordinary white studio backgrounds used by suppliers.
    Images without a white edge are still normalized to PNG but remain opaque.
    """

    try:
        with Image.open(BytesIO(payload)) as source:
            image = ImageOps.exif_transpose(source).convert("RGBA")
    except (UnidentifiedImageError, OSError) as exc:
        raise BadRequestError("图片无法生成透明 PNG。") from exc

    width, height = image.size
    rgb = image.convert("RGB")
    red, green, blue = rgb.split()
    minimum = ImageChops.darker(ImageChops.darker(red, green), blue)
    candidates = minimum.point(lambda value: 255 if value >= 215 else 0)
    seeds = {
        (0, 0),
        (max(width - 1, 0), 0),
        (0, max(height - 1, 0)),
        (max(width - 1, 0), max(height - 1, 0)),
        (width // 2, 0),
        (width // 2, max(height - 1, 0)),
        (0, height // 2),
        (max(width - 1, 0), height // 2),
    }
    for seed in seeds:
        if candidates.getpixel(seed) == 255:
            ImageDraw.floodfill(candidates, seed, 128, thresh=0)

    connected_background = candidates.point(lambda value: 255 if value == 128 else 0)
    background_pixels = connected_background.histogram()[255]
    background_removed = background_pixels > 0
    if background_removed:
        feathered_background = connected_background.filter(ImageFilter.GaussianBlur(0.8))
        foreground_alpha = ImageOps.invert(feathered_background)
        original_alpha = image.getchannel("A")
        image.putalpha(ImageChops.multiply(original_alpha, foreground_alpha))

        bounds = image.getchannel("A").getbbox()
        if bounds is not None:
            cropped = image.crop(bounds)
            padding = max(4, round(max(cropped.size) * 0.02))
            canvas = Image.new(
                "RGBA",
                (cropped.width + padding * 2, cropped.height + padding * 2),
                (0, 0, 0, 0),
            )
            canvas.paste(cropped, (padding, padding), cropped)
            image = canvas

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return TransparentImage(
        payload=output.getvalue(),
        width=image.width,
        height=image.height,
        background_removed=background_removed,
    )


class ProductImageProcessor:
    @staticmethod
    def _storage_path(storage_key: str) -> Path:
        root = settings.storage_root.resolve()
        destination = (root / storage_key).resolve()
        if root not in destination.parents:
            raise BadRequestError("图片存储路径无效。")
        return destination

    async def ensure_transparent_variant(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        original: StoredFile,
    ) -> tuple[StoredFile, bool]:
        source_path = self._storage_path(original.storage_key)
        if not source_path.is_file():
            raise BadRequestError("原始图片文件不存在，无法生成透明 PNG。")
        result = await asyncio.to_thread(remove_white_background, source_path.read_bytes())
        digest = hashlib.sha256(result.payload).hexdigest()
        stored_file = await session.scalar(
            select(StoredFile).where(
                StoredFile.tenant_id == tenant_id,
                StoredFile.sha256 == digest,
            )
        )
        storage_key = f"{tenant_id}/images/transparent/{digest[:2]}/{digest}.png"
        if stored_file is None:
            stored_file = StoredFile(
                tenant_id=tenant_id,
                storage_key=storage_key,
                original_filename=f"{Path(original.original_filename).stem}-transparent.png"[:500],
                safe_filename=_safe_png_filename(original.original_filename, digest),
                sha256=digest,
                mime_type="image/png",
                size_bytes=len(result.payload),
                width=result.width,
                height=result.height,
            )
            session.add(stored_file)
            await session.flush()
        destination = self._storage_path(stored_file.storage_key)
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
            temporary.write_bytes(result.payload)
            os.replace(temporary, destination)
        return stored_file, result.background_removed
