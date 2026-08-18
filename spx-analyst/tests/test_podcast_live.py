"""Live smoke test for Gemini TTS (requires GOOGLE_API_KEY)."""

from __future__ import annotations

import pytest

from src.config import get_settings
from src.podcast_tts import PodcastTTSClient


@pytest.mark.live
def test_live_tts_short_clip(tmp_path) -> None:
    settings = get_settings()
    if not settings.google_api_key:
        pytest.skip("GOOGLE_API_KEY not set")

    client = PodcastTTSClient(settings=settings)
    out = tmp_path / "live.mp3"
    duration = client.synthesize("Welcome to the daily SPX brief.", out)

    assert out.is_file()
    assert out.stat().st_size > 0
    assert 0.5 < duration < 30.0