"""Provider-neutral image encoding utilities."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class EncodedImage:
    media_type: str
    base64_data: str
    width: int
    height: int
    source_path: str


def encode_image(path: Path, max_dim: int) -> EncodedImage:
    """Resize (if needed) and base64-encode a PNG image.

    Returns a provider-neutral ``EncodedImage`` value object. Each pipeline
    client wraps this in its own multimodal request envelope.
    """
    with Image.open(path) as img:
        img = img.convert("RGB")
        original_w, original_h = img.size
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            width, height = img.size
        else:
            width, height = original_w, original_h
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
    data = base64.standard_b64encode(buffer.getvalue()).decode("ascii")
    return EncodedImage(
        media_type="image/png",
        base64_data=data,
        width=width,
        height=height,
        source_path=str(path),
    )
