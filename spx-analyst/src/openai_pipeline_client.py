"""OpenAI Responses API wrapper for the two-pass analytical pipeline.

Pass 1 uses Structured Outputs (``text.format: json_schema``).
Pass 2 uses standard text generation.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import time
from pathlib import Path
from typing import Any

import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import Settings, get_settings
from .pipeline_client import CallResult, PassTelemetry
from .pipeline_utils import encode_image
from .prompts import PromptBundle
from .schemas import DailyState, EmitDailyStateInput, SubstackArticle
from .substack import build_substack_prompt, parse_substack_response

logger = logging.getLogger(__name__)

_RESPONSE_TRANSIENT_ERRORS = (
    openai.APIConnectionError,
    openai.RateLimitError,
)


class OpenAIPipelineError(Exception):
    """Raised when the provider response is missing or unusable."""


def _build_input_payload(body: str, image_paths: list[Path], max_dim: int) -> list[dict[str, Any]]:
    """Build the ``input`` list for ``responses.create()``.

    Text-only when ``image_paths`` is empty; multimodal with ``input_image``
    and ``input_text`` content blocks otherwise.
    """
    if not image_paths:
        return [{"role": "user", "content": body}]
    content: list[dict[str, Any]] = []
    for p in image_paths:
        encoded = encode_image(p, max_dim)
        content.append({
            "type": "input_image",
            "image_url": f"data:{encoded.media_type};base64,{encoded.base64_data}",
        })
    content.append({"type": "input_text", "text": body})
    return [{"role": "user", "content": content}]


def _make_strict_schema(model: type) -> dict[str, Any]:
    """OpenAI strict mode requires every property to be listed in ``required``."""
    schema = model.model_json_schema()
    schema["required"] = list(schema["properties"].keys())
    schema.setdefault("additionalProperties", False)
    return schema


def _structured_response_text() -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "name": "emit_daily_state",
            "schema": _make_strict_schema(EmitDailyStateInput),
            "strict": True,
        }
    }


def _repair_response_text() -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "name": "emit_daily_state",
            "schema": _make_strict_schema(DailyState),
            "strict": True,
        }
    }


def _substack_response_text() -> dict[str, Any]:
    schema = _make_strict_schema(SubstackArticle)
    return {
        "format": {
            "type": "json_schema",
            "name": "emit_substack_article",
            "schema": schema,
            "strict": True,
        }
    }


def _snapshot(
    *,
    model: str,
    instructions: str,
    body_text: str,
    image_paths: list[Path],
    mode: str,
    telemetry: PassTelemetry | None = None,
) -> dict[str, Any]:
    snap: dict[str, Any] = {
        "model": model,
        "instructions_chars": len(instructions),
        "body_chars": len(body_text),
        "analysis_context_included": "Precomputed analysis context" in body_text,
        "images": [p.name for p in image_paths],
        "image_count": len(image_paths),
        "mode": mode,
    }
    if telemetry is not None:
        snap["telemetry"] = dataclasses.asdict(telemetry)
    return snap


def _build_telemetry(
    *,
    provider: str,
    model: str,
    pass_name: str,
    response: Any,
    elapsed_ms: int,
    image_count: int,
    attempt_count: int = 1,
    retry_reason: str | None = None,
) -> PassTelemetry:
    usage = getattr(response, "usage", None)
    cached_tokens = None
    if usage:
        details = getattr(usage, "input_tokens_details", None)
        if details:
            cached_tokens = getattr(details, "cached_tokens", None)
    return PassTelemetry(
        provider=provider,
        model=model,
        pass_name=pass_name,
        input_tokens=getattr(usage, "input_tokens", None) if usage else None,
        output_tokens=getattr(usage, "output_tokens", None) if usage else None,
        cache_read_tokens=cached_tokens,
        cache_write_tokens=None,
        latency_ms=elapsed_ms,
        attempt_count=attempt_count,
        retry_reason=retry_reason,
        image_count=image_count,
        request_shape_version="2.0",
    )


def _extract_output_text(response: Any) -> str:
    """Extract text from a Responses API response.

    Checks for refusals in output items before reading ``output_text``.
    """
    if not getattr(response, "output", None):
        raise OpenAIPipelineError("response had no output items")

    for item in response.output:
        if getattr(item, "type", None) == "refusal":
            raise OpenAIPipelineError(
                f"response output contains a refusal: {getattr(item, 'refusal', 'unknown')}"
            )

    text = getattr(response, "output_text", None)
    if not text:
        raise OpenAIPipelineError("response output_text is empty")
    return text


def _parse_json_response(raw_text: str) -> dict[str, Any]:
    """Parse the first complete JSON value from *raw_text*.

    Handles cases where the model appends extra text after the JSON payload.
    """
    raw_text = raw_text.strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        idx = 0
        while idx < len(raw_text):
            if raw_text[idx] in ("{", "["):
                try:
                    obj, end = decoder.raw_decode(raw_text, idx)
                    return obj
                except json.JSONDecodeError:
                    idx += 1
            else:
                idx += 1
        raise OpenAIPipelineError(
            "Structured Outputs returned no valid JSON in response"
        )


def _resolve_openai_model(settings: Settings) -> str:
    candidate = settings.openai_pipeline_model.strip()
    return candidate if candidate else "gpt-5.6-sol"


class OpenAIPipelineClient:
    """OpenAI Responses API implementation of PipelineLLMClient."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.openai_api_key:
            raise OpenAIPipelineError("OPENAI_API_KEY is not set")
        self._client = openai.OpenAI(api_key=self.settings.openai_api_key)
        self._model = _resolve_openai_model(self.settings)

    @retry(
        retry=retry_if_exception_type(_RESPONSE_TRANSIENT_ERRORS),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _create(self, **kwargs: Any):
        return self._client.responses.create(**kwargs)

    def run_structured_state(self, bundle: PromptBundle, image_paths: list[Path]) -> CallResult:
        """Pass 1: structured state via Responses API + json_schema format."""
        instructions = bundle.system_role + "\n\n" + bundle.framework
        input_payload = _build_input_payload(
            bundle.body, image_paths, self.settings.image_max_dimension
        )

        t0 = time.monotonic()
        response = self._create(
            model=self._model,
            instructions=instructions,
            input=input_payload,
            text=_structured_response_text(),
            max_output_tokens=self.settings.max_output_tokens,
            store=False,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        raw_text = _extract_output_text(response)
        tool_input = _parse_json_response(raw_text)

        telemetry = _build_telemetry(
            provider="openai",
            model=self._model,
            pass_name="state",
            response=response,
            elapsed_ms=elapsed_ms,
            image_count=len(image_paths),
        )
        return CallResult(
            text=None,
            tool_input=tool_input,
            raw_response=response.model_dump(mode="json"),
            request_snapshot=_snapshot(
                model=self._model,
                instructions=instructions,
                body_text=bundle.body,
                image_paths=image_paths,
                mode="state",
                telemetry=telemetry,
            ),
        )

    def repair_structured_state(self, invalid: dict[str, Any], errors: str) -> CallResult:
        """Repair pass: Responses API with json_schema format, nested DailyState schema."""
        message = (
            "The previous structured output failed schema validation. Fix it and call "
            "`emit_daily_state` again with corrected values, preserving the analysis.\n\n"
            f"Validation errors:\n{errors}\n\n"
            f"Invalid output:\n```json\n{json.dumps(invalid, indent=2)}\n```"
        )

        t0 = time.monotonic()
        response = self._create(
            model=self._model,
            input=[{"role": "user", "content": message}],
            text=_repair_response_text(),
            max_output_tokens=self.settings.max_output_tokens,
            store=False,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        raw_text = _extract_output_text(response)
        tool_input = _parse_json_response(raw_text)

        telemetry = _build_telemetry(
            provider="openai",
            model=self._model,
            pass_name="repair",
            response=response,
            elapsed_ms=elapsed_ms,
            image_count=0,
        )
        return CallResult(
            text=None,
            tool_input=tool_input,
            raw_response=response.model_dump(mode="json"),
            request_snapshot={
                "model": self._model,
                "mode": "repair",
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
        """Pass 2: prose report via standard Responses API text generation."""
        max_dim = (
            self.settings.pass2_image_max_dimension
            if self.settings.pass2_image_optimization_enabled
            else self.settings.image_max_dimension
        )
        instructions = bundle.system_role + "\n\n" + bundle.framework
        input_payload = _build_input_payload(
            bundle.body, image_paths, max_dim,
        )

        t0 = time.monotonic()
        response = self._create(
            model=self._model,
            instructions=instructions,
            input=input_payload,
            max_output_tokens=self.settings.max_output_tokens,
            store=False,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        text = _extract_output_text(response)

        telemetry = _build_telemetry(
            provider="openai",
            model=self._model,
            pass_name="report",
            response=response,
            elapsed_ms=elapsed_ms,
            image_count=len(image_paths),
        )
        snapshot = _snapshot(
            model=self._model,
            instructions=instructions,
            body_text=bundle.body,
            image_paths=image_paths,
            mode="report",
            telemetry=telemetry,
        )
        audit = dict(pass2_audit or {})
        audit.setdefault("pass2_image_max_dimension_used", max_dim)
        snapshot.update(audit)
        return CallResult(
            text=text,
            tool_input=None,
            raw_response=response.model_dump(mode="json"),
            request_snapshot=snapshot,
        )

    def run_substack_article(
        self, daily_state: DailyState, report_markdown: str
    ) -> tuple[SubstackArticle, dict[str, Any]]:
        """Generate the short editorial article from validated analysis."""
        instructions = (
            "You are the daily editor for a serious market publication. Return only valid JSON. "
            "The supplied validated state is authoritative. Simplify the report without changing "
            "its posture, recommendation, or conclusions."
        )
        body = build_substack_prompt(daily_state, report_markdown)
        t0 = time.monotonic()
        response = self._create(
            model=self.settings.openai_substack_model,
            instructions=instructions,
            input=[{"role": "user", "content": body}],
            text=_substack_response_text(),
            max_output_tokens=3000,
            store=False,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        raw_text = _extract_output_text(response)
        telemetry = _build_telemetry(
            provider="openai",
            model=self.settings.openai_substack_model,
            pass_name="substack",
            response=response,
            elapsed_ms=elapsed_ms,
            image_count=0,
        )
        article = parse_substack_response(raw_text)
        logger.info("generated Substack article for %s", daily_state.date)
        return article, {
            "model": self.settings.openai_substack_model,
            "mode": "substack",
            "telemetry": dataclasses.asdict(telemetry),
            "body_chars": len(body),
            "response_raw": response.model_dump(mode="json"),
        }
