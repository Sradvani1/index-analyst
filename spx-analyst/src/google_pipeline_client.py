"""Google AI Studio Gemini wrapper for the two-pass analytical pipeline."""

from __future__ import annotations

import base64
import dataclasses
import json
import time
from pathlib import Path
from typing import Any

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from .config import Settings, get_settings
from .pipeline_client import CallResult, PassTelemetry, PipelineClientError
from .pipeline_utils import encode_image
from .podcast import PODCAST_INSTRUCTIONS, build_podcast_prompt, parse_podcast_response
from .prompts import PromptBundle
from .schemas import DailyState, EmitDailyStateInput, PodcastScript, SubstackArticle
from .substack import SUBSTACK_INSTRUCTIONS, build_substack_prompt, parse_substack_response


class GooglePipelineError(PipelineClientError):
    """Raised when the Gemini response is missing or unusable."""


def _is_transient_error(exc: BaseException) -> bool:
    """Retry network, rate-limit, and temporary server failures only."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status is not None:
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = None
    if status in {408, 429, 500, 502, 503, 504}:
        return True
    return exc.__class__.__name__ in {
        "ConnectError",
        "DeadlineExceeded",
        "InternalServerError",
        "ReadTimeout",
        "RemoteProtocolError",
        "ServiceUnavailable",
        "TimeoutException",
    }


def _model_dump(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    if isinstance(response, dict):
        return response
    return {"response": repr(response)}


def _response_text(response: Any) -> str:
    try:
        text = getattr(response, "text", None)
    except (AttributeError, ValueError) as exc:
        raise GooglePipelineError(
            "Gemini response text was unavailable"
        ) from exc
    if text:
        return str(text).strip()
    candidates = getattr(response, "candidates", None) or []
    parts: list[str] = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            value = getattr(part, "text", None)
            if value:
                parts.append(str(value))
    text = "\n".join(parts).strip()
    if not text:
        raise GooglePipelineError("Gemini response did not contain any text")
    return text


def _parse_json(raw_text: str) -> dict[str, Any]:
    try:
        value = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise GooglePipelineError("Gemini structured output was not valid JSON") from exc
    if not isinstance(value, dict):
        raise GooglePipelineError("Gemini structured output was not a JSON object")
    return value


def _usage(response: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None, None, None
    input_tokens = getattr(usage, "prompt_token_count", None)
    output_tokens = getattr(usage, "candidates_token_count", None)
    thoughts_tokens = getattr(usage, "thoughts_token_count", None) or 0
    if output_tokens is not None:
        output_tokens += thoughts_tokens
    cached_tokens = getattr(usage, "cached_content_token_count", None)
    return input_tokens, output_tokens, cached_tokens


def _user_content(
    bundle: PromptBundle, image_paths: list[Path], max_dim: int, types: Any
) -> Any:
    parts: list[Any] = []
    for path in image_paths:
        encoded = encode_image(path, max_dim)
        parts.append(
            types.Part.from_bytes(
                data=base64.b64decode(encoded.base64_data),
                mime_type=encoded.media_type,
            )
        )
    parts.append(types.Part.from_text(text=bundle.body))
    return types.Content(role="user", parts=parts)


def _snapshot(
    *,
    model: str,
    thinking_level: str,
    max_output_tokens: int,
    system_instruction: str,
    body_text: str,
    image_paths: list[Path],
    mode: str,
    telemetry: PassTelemetry | None = None,
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "model": model,
        "thinking_level": thinking_level or None,
        "max_output_tokens": max_output_tokens,
        "system_instruction_chars": len(system_instruction),
        "body_chars": len(body_text),
        "analysis_context_included": "Precomputed analysis context" in body_text,
        "images": [path.name for path in image_paths],
        "image_count": len(image_paths),
        "mode": mode,
    }
    if telemetry is not None:
        snapshot["telemetry"] = dataclasses.asdict(telemetry)
    return snapshot


class GooglePipelineClient:
    """Gemini Developer API implementation of ``PipelineLLMClient``."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
        types_module: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        if not self.settings.google_api_key and client is None:
            raise GooglePipelineError("GOOGLE_API_KEY is not set")
        self._model = self.settings.google_pipeline_model.strip() or "gemini-3.7-flash"
        self._client = client or self._build_client()
        self._types_module = types_module

    def _build_client(self) -> Any:
        try:
            from google import genai
        except ImportError as exc:
            raise GooglePipelineError(
                "google-genai package is not installed; add google-genai>=1.0.0"
            ) from exc
        return genai.Client(api_key=self.settings.google_api_key)

    @retry(
        retry=retry_if_exception(_is_transient_error),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _generate(self, **kwargs: Any) -> Any:
        return self._client.models.generate_content(**kwargs)

    def _types(self) -> Any:
        if self._types_module is not None:
            return self._types_module
        try:
            from google.genai import types
        except ImportError as exc:
            raise GooglePipelineError(
                "google-genai package is not installed; add google-genai>=1.0.0"
            ) from exc
        return types

    def _thinking_level(self, pass_name: str) -> str:
        phase_level = getattr(self.settings, f"google_{pass_name}_thinking_level")
        return (phase_level.strip() or self.settings.google_thinking_level.strip()).upper()

    def _call(
        self,
        *,
        system_instruction: str | None,
        contents: Any,
        schema: type | None = None,
        thinking_level: str = "",
        max_output_tokens: int | None = None,
    ) -> Any:
        types = self._types()
        config_kwargs: dict[str, Any] = {
            "max_output_tokens": max_output_tokens or self.settings.google_max_output_tokens,
        }
        thinking_level = thinking_level.strip().upper()
        if thinking_level:
            if thinking_level not in {"MINIMAL", "LOW", "MEDIUM", "HIGH"}:
                raise GooglePipelineError(
                    "SPX_GOOGLE_THINKING_LEVEL must be MINIMAL, LOW, MEDIUM, or HIGH"
                )
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=thinking_level
            )
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if schema is not None:
            config_kwargs.update(
                response_mime_type="application/json",
                # The Pydantic schema contains numeric enums. The SDK's
                # response_schema converter only accepts string enums, while
                # response_json_schema preserves the valid JSON Schema.
                response_json_schema=schema.model_json_schema(),
            )
        return self._generate(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )

    def run_structured_state(self, bundle: PromptBundle, image_paths: list[Path]) -> CallResult:
        system_instruction = bundle.system_role + "\n\n" + bundle.framework
        t0 = time.monotonic()
        types = self._types()
        response = self._call(
            system_instruction=system_instruction,
            contents=[
                _user_content(
                    bundle, image_paths, self.settings.image_max_dimension, types
                )
            ],
            schema=EmitDailyStateInput,
            thinking_level=self._thinking_level("state"),
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        input_tokens, output_tokens, cached_tokens = _usage(response)
        telemetry = PassTelemetry(
            provider="google",
            model=self._model,
            pass_name="state",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cached_tokens,
            latency_ms=elapsed_ms,
            image_count=len(image_paths),
            request_shape_version="google-generate-content-1.0",
        )
        return CallResult(
            text=None,
            tool_input=_parse_json(_response_text(response)),
            raw_response=_model_dump(response),
            request_snapshot=_snapshot(
                model=self._model,
                thinking_level=self._thinking_level("state"),
                max_output_tokens=self.settings.google_max_output_tokens,
                system_instruction=system_instruction,
                body_text=bundle.body,
                image_paths=image_paths,
                mode="state",
                telemetry=telemetry,
            ),
        )

    def repair_structured_state(self, invalid: dict[str, Any], errors: str) -> CallResult:
        message = (
            "The previous structured output failed schema validation. Fix it while preserving "
            "the analysis.\n\n"
            f"Validation errors:\n{errors}\n\n"
            f"Invalid output:\n```json\n{json.dumps(invalid, indent=2)}\n```"
        )
        types = self._types()
        t0 = time.monotonic()
        response = self._call(
            system_instruction=None,
            contents=[
                types.Content(role="user", parts=[types.Part.from_text(text=message)])
            ],
            schema=DailyState,
            thinking_level=self._thinking_level("state"),
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        input_tokens, output_tokens, cached_tokens = _usage(response)
        telemetry = PassTelemetry(
            provider="google",
            model=self._model,
            pass_name="repair",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cached_tokens,
            latency_ms=elapsed_ms,
            image_count=0,
            request_shape_version="google-generate-content-1.0",
        )
        return CallResult(
            text=None,
            tool_input=_parse_json(_response_text(response)),
            raw_response=_model_dump(response),
            request_snapshot={
                "model": self._model,
                "mode": "repair",
                "thinking_level": self._thinking_level("state") or None,
                "max_output_tokens": self.settings.google_max_output_tokens,
                "telemetry": dataclasses.asdict(telemetry),
            },
        )

    def run_markdown_report(
        self,
        bundle: PromptBundle,
        image_paths: list[Path],
        *,
        pass2_audit: dict[str, Any] | None = None,
    ) -> CallResult:
        system_instruction = bundle.system_role + "\n\n" + bundle.framework
        max_dim = (
            self.settings.pass2_image_max_dimension
            if self.settings.pass2_image_optimization_enabled
            else self.settings.image_max_dimension
        )
        t0 = time.monotonic()
        types = self._types()
        response = self._call(
            system_instruction=system_instruction,
            contents=[_user_content(bundle, image_paths, max_dim, types)],
            thinking_level=self._thinking_level("report"),
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        text = _response_text(response)
        input_tokens, output_tokens, cached_tokens = _usage(response)
        telemetry = PassTelemetry(
            provider="google",
            model=self._model,
            pass_name="report",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cached_tokens,
            latency_ms=elapsed_ms,
            image_count=len(image_paths),
            request_shape_version="google-generate-content-1.0",
        )
        snapshot = _snapshot(
            model=self._model,
            thinking_level=self._thinking_level("report"),
            max_output_tokens=self.settings.google_max_output_tokens,
            system_instruction=system_instruction,
            body_text=bundle.body,
            image_paths=image_paths,
            mode="report",
            telemetry=telemetry,
        )
        snapshot.update(pass2_audit or {})
        return CallResult(
            text=text,
            tool_input=None,
            raw_response=_model_dump(response),
            request_snapshot=snapshot,
        )

    def run_substack_article(
        self, daily_state: DailyState, report_markdown: str
    ) -> tuple[SubstackArticle, dict[str, Any]]:
        """Generate the editorial article with Gemini's default thinking behavior."""
        body = build_substack_prompt(daily_state, report_markdown)
        t0 = time.monotonic()
        types = self._types()
        try:
            response = self._call(
                system_instruction=SUBSTACK_INSTRUCTIONS,
                contents=[types.Content(
                    role="user", parts=[types.Part.from_text(text=body)]
                )],
                schema=SubstackArticle,
                # Empty thinking_level intentionally leaves Gemini's default behavior enabled.
                thinking_level="",
                max_output_tokens=self.settings.google_substack_max_output_tokens,
            )
        except GooglePipelineError:
            raise
        except Exception as exc:
            raise GooglePipelineError("Gemini Substack request failed") from exc
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        raw_text = _response_text(response)
        input_tokens, output_tokens, cached_tokens = _usage(response)
        telemetry = PassTelemetry(
            provider="google",
            model=self._model,
            pass_name="substack",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cached_tokens,
            latency_ms=elapsed_ms,
            image_count=0,
            request_shape_version="google-generate-content-1.0",
        )
        try:
            article = parse_substack_response(raw_text)
        except ValueError as exc:
            raise GooglePipelineError("Gemini Substack response was invalid") from exc
        return article, {
            "model": self._model,
            "mode": "substack",
            "thinking_level": None,
            "telemetry": dataclasses.asdict(telemetry),
            "body_chars": len(body),
            "response_raw": _model_dump(response),
        }

    def run_podcast_script(
        self, substack_markdown: str
    ) -> tuple[PodcastScript, dict[str, Any]]:
        """Generate the condensed ~3-minute podcast script from the Substack article."""
        body = build_podcast_prompt(substack_markdown)
        t0 = time.monotonic()
        types = self._types()
        try:
            response = self._call(
                system_instruction=PODCAST_INSTRUCTIONS,
                contents=[types.Content(
                    role="user", parts=[types.Part.from_text(text=body)]
                )],
                schema=PodcastScript,
                # Empty thinking_level intentionally leaves Gemini's default behavior enabled.
                thinking_level="",
                max_output_tokens=self.settings.google_podcast_max_output_tokens,
            )
        except GooglePipelineError:
            raise
        except Exception as exc:
            raise GooglePipelineError("Gemini podcast request failed") from exc
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        raw_text = _response_text(response)
        input_tokens, output_tokens, cached_tokens = _usage(response)
        telemetry = PassTelemetry(
            provider="google",
            model=self._model,
            pass_name="podcast_script",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cached_tokens,
            latency_ms=elapsed_ms,
            image_count=0,
            request_shape_version="google-generate-content-1.0",
        )
        try:
            script = parse_podcast_response(raw_text)
        except ValueError as exc:
            raise GooglePipelineError("Gemini podcast response was invalid") from exc
        return script, {
            "model": self._model,
            "mode": "podcast_script",
            "thinking_level": None,
            "telemetry": dataclasses.asdict(telemetry),
            "body_chars": len(body),
            "response_raw": _model_dump(response),
        }
