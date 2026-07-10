"""Image encoding tests — EncodedImage shape and byte-identical baseline."""

from __future__ import annotations

from pathlib import Path

from src.pipeline_utils import EncodedImage, encode_image


def test_encode_image_produces_expected_encoded_image(tmp_path):
    png = tmp_path / "test.png"
    from PIL import Image

    Image.new("RGB", (64, 48), color=(10, 20, 30)).save(png)

    result = encode_image(png, max_dim=1568)
    assert isinstance(result, EncodedImage)
    assert result.media_type == "image/png"
    assert isinstance(result.base64_data, str)
    assert len(result.base64_data) > 0
    assert result.width == 64
    assert result.height == 48
    assert result.source_path == str(png)


def test_encode_image_respects_max_dim(tmp_path):
    from PIL import Image

    png = tmp_path / "large.png"
    Image.new("RGB", (2000, 1500), color=(0, 0, 0)).save(png)

    result = encode_image(png, max_dim=1568)
    assert result.width <= 1568
    assert result.height <= 1568
    assert result.source_path == str(png)


def test_encode_image_deterministic_and_decodable(tmp_path):
    """encode_image produces deterministic, valid PNG output.

    Encodes a known image twice and verifies:
    - Repeated calls produce identical base64
    - The base64 decodes to a valid PNG with the correct dimensions
    """
    import base64
    import io

    from PIL import Image

    png = tmp_path / "fixture.png"
    Image.new("RGB", (32, 32), color=(128, 128, 128)).save(png)

    first = encode_image(png, max_dim=1568)
    second = encode_image(png, max_dim=1568)

    # Deterministic across calls
    assert first.base64_data == second.base64_data

    # Decodes to a valid PNG with correct properties
    decoded = Image.open(io.BytesIO(base64.b64decode(first.base64_data)))
    assert decoded.size == (32, 32)
    assert decoded.mode == "RGB"
