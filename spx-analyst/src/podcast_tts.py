"""Gemini TTS synthesis via the Interactions API, encoded to MP3 with ffmpeg.

The TTS models return 16-bit mono PCM at 24 kHz. The SDK's
``interaction.output_audio.data`` is a base64 string; it is decoded and piped
straight into ffmpeg for MP3 encoding.
"""

from __future__ import annotations

import base64
import subprocess
from pathlib import Path
from typing import Any

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from .config import Settings, get_settings
from .google_pipeline_client import GooglePipelineError, _is_transient_error

PCM_SAMPLE_RATE = 24000
PCM_CHANNELS = 1

# Style directive prepended to the TTS input (the Gemini TTS API has no separate
# style field; tone is controlled inline, e.g. "Say cheerfully: ..."). Kept
# call-time only so the stored script/transcript remains the clean prose.
TTS_DIRECTIVE = (
    "Read the following in a calm, measured, professional financial-news tone, "
    "with steady even pacing and an understated, confident delivery:"
)


class PodcastTTSError(Exception):
    """Raised when Gemini TTS or MP3 encoding fails."""


def _decode_audio_data(audio: Any) -> bytes:
    data = getattr(audio, "data", None)
    if data is None:
        raise PodcastTTSError("Gemini TTS response did not contain audio data")
    if isinstance(data, str):
        try:
            return base64.b64decode(data)
        except (ValueError, TypeError) as exc:
            raise PodcastTTSError("Gemini TTS audio data was not valid base64") from exc
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise PodcastTTSError(f"Gemini TTS audio data had unexpected type {type(data).__name__}")


def _run_ffmpeg(
    pcm: bytes,
    output_path: Path,
    *,
    sample_rate: int = PCM_SAMPLE_RATE,
    channels: int = PCM_CHANNELS,
) -> None:
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "s16le", "-ar", str(sample_rate), "-ac", str(channels),
        "-i", "-",
        "-codec:a", "libmp3lame", "-q:a", "4",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, input=pcm, capture_output=True)
    except FileNotFoundError as exc:
        raise PodcastTTSError("ffmpeg is required for podcast encoding but was not found") from exc
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "ignore").strip()
        raise PodcastTTSError(f"ffmpeg failed to encode podcast audio: {stderr[:300]}")


def _probe_duration(path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise PodcastTTSError("ffprobe is required for duration measurement but was not found")
    if result.returncode != 0 or not result.stdout.strip():
        raise PodcastTTSError("ffprobe could not read the generated podcast audio")
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise PodcastTTSError("ffprobe returned an unparseable duration") from exc


class PodcastTTSClient:
    """Thin wrapper around the Gemini Interactions TTS endpoint."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client or self._build_client()

    def _build_client(self) -> Any:
        if not self.settings.google_api_key:
            raise PodcastTTSError("GOOGLE_API_KEY is not set")
        try:
            from google import genai
        except ImportError as exc:
            raise PodcastTTSError(
                "google-genai package is not installed; add google-genai>=1.0.0"
            ) from exc
        return genai.Client(api_key=self.settings.google_api_key)

    @retry(
        retry=retry_if_exception(_is_transient_error),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _create_audio(self, text: str) -> Any:
        return self._client.interactions.create(
            model=self.settings.google_tts_model,
            input=f"{TTS_DIRECTIVE} {text}",
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": self.settings.podcast_voice}]},
        )

    def synthesize(self, text: str, output_path: Path) -> float:
        """Synthesize ``text`` to an MP3 at ``output_path`` and return its duration in seconds."""
        try:
            interaction = self._create_audio(text)
        except PodcastTTSError:
            raise
        except Exception as exc:
            raise PodcastTTSError("Gemini TTS request failed") from exc
        audio = getattr(interaction, "output_audio", None)
        if audio is None:
            raise PodcastTTSError("Gemini TTS response did not include output_audio")
        pcm = _decode_audio_data(audio)
        if not pcm:
            raise PodcastTTSError("Gemini TTS returned empty audio data")
        sample_rate = getattr(audio, "sample_rate", None) or PCM_SAMPLE_RATE
        channels = getattr(audio, "channels", None) or PCM_CHANNELS
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _run_ffmpeg(pcm, output_path, sample_rate=sample_rate, channels=channels)
        return _probe_duration(output_path)