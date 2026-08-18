"""Tests for Gemini TTS synthesis and MP3 encoding."""

from __future__ import annotations

import base64
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.podcast_tts import (
    PodcastTTSError,
    PodcastTTSClient,
    TTS_DIRECTIVE,
    _decode_audio_data,
    _probe_duration,
    _run_ffmpeg,
)
from tests.conftest import make_settings


def _audio(data: str | bytes | None) -> SimpleNamespace:
    return SimpleNamespace(data=data)


def test_decode_audio_base64_string() -> None:
    pcm = b"\x00\x01" * 100
    assert _decode_audio_data(_audio(base64.b64encode(pcm).decode())) == pcm


def test_decode_audio_bytes_passthrough() -> None:
    pcm = b"\x00\x01" * 100
    assert _decode_audio_data(_audio(pcm)) == pcm


def test_decode_audio_missing_data_raises() -> None:
    with pytest.raises(PodcastTTSError, match="audio data"):
        _decode_audio_data(_audio(None))


def test_decode_audio_bad_base64_raises() -> None:
    with pytest.raises(PodcastTTSError, match="base64"):
        _decode_audio_data(_audio("not-base64-!!!"))


def test_synthesize_encodes_pcm_and_returns_duration(tmp_path, monkeypatch) -> None:
    client_sdk = Mock()
    pcm = b"\x00\x01" * 64
    client_sdk.interactions.create.return_value = SimpleNamespace(
        output_audio=SimpleNamespace(
            data=base64.b64encode(pcm).decode(), sample_rate=48000, channels=2
        )
    )

    calls: dict[str, object] = {}
    monkeypatch.setattr(
        "src.podcast_tts._run_ffmpeg",
        lambda data, path, **kwargs: calls.update(pcm=data, path=path, **kwargs),
    )
    monkeypatch.setattr("src.podcast_tts._probe_duration", lambda path: 183.0)

    tts = PodcastTTSClient(make_settings(tmp_path), client=client_sdk)
    out = Path(tmp_path) / "podcast.mp3"
    duration = tts.synthesize("Hello world.", out)

    assert duration == 183.0
    assert calls["pcm"] == pcm
    assert calls["path"] == out
    assert calls["sample_rate"] == 48000
    assert calls["channels"] == 2
    request = client_sdk.interactions.create.call_args
    assert request.kwargs["model"] == "gemini-3.1-flash-tts-preview"
    assert request.kwargs["input"] == f"{TTS_DIRECTIVE} Hello world."
    assert request.kwargs["response_format"] == {"type": "audio"}
    assert request.kwargs["generation_config"] == {"speech_config": [{"voice": "Orus"}]}


def test_tts_directive_is_set() -> None:
    assert isinstance(TTS_DIRECTIVE, str)
    assert TTS_DIRECTIVE.startswith("Read the following in a calm, measured")
    assert TTS_DIRECTIVE.endswith(":")


def test_synthesize_falls_back_to_default_audio_format(tmp_path, monkeypatch) -> None:
    client_sdk = Mock()
    pcm = b"\x00\x01" * 64
    client_sdk.interactions.create.return_value = SimpleNamespace(
        output_audio=SimpleNamespace(data=base64.b64encode(pcm).decode())
    )

    calls: dict[str, object] = {}
    monkeypatch.setattr(
        "src.podcast_tts._run_ffmpeg",
        lambda data, path, **kwargs: calls.update(pcm=data, path=path, **kwargs),
    )
    monkeypatch.setattr("src.podcast_tts._probe_duration", lambda path: 60.0)

    tts = PodcastTTSClient(make_settings(tmp_path), client=client_sdk)
    tts.synthesize("Hello world.", Path(tmp_path) / "podcast.mp3")

    assert calls["sample_rate"] == 24000
    assert calls["channels"] == 1


def test_synthesize_missing_output_audio_raises(tmp_path, monkeypatch) -> None:
    client_sdk = Mock()
    client_sdk.interactions.create.return_value = SimpleNamespace(output_audio=None)

    tts = PodcastTTSClient(make_settings(tmp_path), client=client_sdk)
    with pytest.raises(PodcastTTSError, match="output_audio"):
        tts.synthesize("Hello", Path(tmp_path) / "x.mp3")


def test_synthesize_empty_audio_raises(tmp_path, monkeypatch) -> None:
    client_sdk = Mock()
    client_sdk.interactions.create.return_value = SimpleNamespace(
        output_audio=SimpleNamespace(data=base64.b64encode(b"").decode())
    )
    monkeypatch.setattr(
        "src.podcast_tts._run_ffmpeg", lambda data, path, **kwargs: None
    )

    tts = PodcastTTSClient(make_settings(tmp_path), client=client_sdk)
    with pytest.raises(PodcastTTSError, match="empty audio"):
        tts.synthesize("Hello", Path(tmp_path) / "x.mp3")


def test_synthesize_ffmpeg_failure_raises(tmp_path, monkeypatch) -> None:
    client_sdk = Mock()
    client_sdk.interactions.create.return_value = SimpleNamespace(
        output_audio=SimpleNamespace(data=base64.b64encode(b"\x00" * 64).decode())
    )

    def boom(_data: bytes, _path: Path, **_kwargs: object) -> None:
        raise PodcastTTSError("ffmpeg failed to encode")

    monkeypatch.setattr("src.podcast_tts._run_ffmpeg", boom)
    tts = PodcastTTSClient(make_settings(tmp_path), client=client_sdk)
    with pytest.raises(PodcastTTSError, match="ffmpeg failed"):
        tts.synthesize("Hello", Path(tmp_path) / "x.mp3")


def test_synthesize_retries_on_transient_error(tmp_path, monkeypatch) -> None:
    class _RateLimit(Exception):
        status_code = 429

    client_sdk = Mock()
    client_sdk.interactions.create.side_effect = [
        _RateLimit(),
        SimpleNamespace(
            output_audio=SimpleNamespace(data=base64.b64encode(b"\x00\x01" * 8).decode())
        ),
    ]
    monkeypatch.setattr(
        "src.podcast_tts._run_ffmpeg", lambda data, path, **kwargs: None
    )
    monkeypatch.setattr("src.podcast_tts._probe_duration", lambda path: 60.0)

    tts = PodcastTTSClient(make_settings(tmp_path), client=client_sdk)
    duration = tts.synthesize("Hello", Path(tmp_path) / "x.mp3")

    assert duration == 60.0
    assert client_sdk.interactions.create.call_count == 2


def test_real_ffmpeg_encodes_pcm_to_mp3(tmp_path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not available on this machine")

    silence = b"\x00\x00" * (24000 * 1)  # 1 second of 24 kHz 16-bit mono silence
    out = tmp_path / "tone.mp3"
    _run_ffmpeg(silence, out)

    assert out.is_file()
    assert out.stat().st_size > 0
    assert 0.8 < _probe_duration(out) < 2.5