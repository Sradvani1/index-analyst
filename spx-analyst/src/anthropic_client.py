"""Anthropic Claude wrapper for the two-pass pipeline.

Handles multimodal image encoding (with resize), prompt caching of the static
framework block, forced tool-use for structured state, one transient retry, and
secret-scrubbed request/response snapshots.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from pathlib import Path
from typing import Any

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import Settings, get_settings
from .pipeline_client import CallResult, PassTelemetry, PipelineClientError
from .pipeline_utils import encode_image
from .prompts import EVIDENCE_AND_TENSIONS_HEADING, PASS2_PROSE_SECTIONS, PromptBundle
from .schemas import DailyState, EmitDailyStateInput, SubstackArticle
from .substack import SUBSTACK_INSTRUCTIONS, build_substack_prompt, parse_substack_response

logger = logging.getLogger(__name__)

STATE_TOOL_NAME = "emit_daily_state"
SUBSTACK_TOOL_NAME = "emit_substack_article"

# Pass 2 stub preambles observed on claude-opus-4-8 when tools are present with
# tool_choice=none — model announces emit_daily_state instead of writing markdown.
_PASS2_STUB_PHRASES = (
    "emit the structured daily state",
    "emit structured daily state",
    "emit_daily_state",
)

# Positive signals that Pass 2 returned real investor-template prose (PR-7).
_INVESTOR_PROSE_MARKERS = (
    f"## {PASS2_PROSE_SECTIONS[0]}",
    f"## {PASS2_PROSE_SECTIONS[1]}",
    f"## {EVIDENCE_AND_TENSIONS_HEADING}",
)

# Legacy workflow headings — still treated as non-stub for retries and drift.
_LEGACY_REPORT_MARKERS = (
    "## 0.",
    "## 1.",
    "## Structural Regime",
    "## Updated Decision Matrix",
)

_TRANSIENT_ERRORS = (
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.OverloadedError,
)


class AnthropicError(PipelineClientError):
    """Raised when the provider response is missing or unusable."""


def _system_blocks(bundle: PromptBundle, cache_enabled: bool) -> list[dict[str, Any]]:
    framework_block: dict[str, Any] = {"type": "text", "text": bundle.framework}
    if cache_enabled:
        framework_block["cache_control"] = {"type": "ephemeral"}
    return [{"type": "text", "text": bundle.system_role}, framework_block]


def _state_tool() -> dict[str, Any]:
    """The emit_daily_state tool for Pass 1 (and optional Pass 2 cache prefix).

    Uses the flat ``EmitDailyStateInput`` schema to avoid Claude's XML-string
    serialization of nested object properties. The repair pass
    (``repair_structured_state``) still uses the nested ``DailyState`` schema.
    """
    return {
        "name": STATE_TOOL_NAME,
        "description": "Emit the structured daily analysis state for the session.",
        "input_schema": EmitDailyStateInput.model_json_schema(),
    }


def _is_pass2_stub_response(text: str) -> bool:
    """True when Pass 2 returned a preamble instead of investor prose sections."""
    if len(text) >= 3000:
        return False
    if any(marker in text for marker in _INVESTOR_PROSE_MARKERS):
        return False
    if any(marker in text for marker in _LEGACY_REPORT_MARKERS):
        return False
    if text.startswith("# SPX"):
        return True
    lower = text.lower()
    if any(phrase in lower for phrase in _PASS2_STUB_PHRASES):
        return True
    return len(text) < 500 and "## " not in text


def _user_content(bundle: PromptBundle, image_paths: list[Path], max_dim: int) -> list[dict[str, Any]]:
    # Images are NOT cached: they live in the messages layer, and Pass 1 forces the
    # tool while Pass 2 does not — the differing tool_choice invalidates the messages
    # cache, so an image breakpoint would only incur write cost with no read.
    content: list[dict[str, Any]] = []
    for p in image_paths:
        encoded = encode_image(p, max_dim)
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": encoded.media_type,
                "data": encoded.base64_data,
            },
        })
    content.append({"type": "text", "text": bundle.body})
    return content


def _snapshot(
    *,
    model: str,
    system_blocks: list[dict[str, Any]],
    body_text: str,
    image_paths: list[Path],
    tool_name: str | None,
    pass2_audit: dict[str, Any] | None = None,
    telemetry: PassTelemetry | None = None,
) -> dict[str, Any]:
    """Reproducibility metadata. Excludes secrets and raw image bytes."""
    snap: dict[str, Any] = {
        "model": model,
        "system_role_chars": len(system_blocks[0]["text"]),
        "framework_chars": len(system_blocks[1]["text"]),
        "framework_cached": "cache_control" in system_blocks[1],
        "body_chars": len(body_text),
        "analysis_context_included": "Precomputed analysis context" in body_text,
        "images": [p.name for p in image_paths],
        "image_count": len(image_paths),
        "forced_tool": tool_name,
    }
    if telemetry is not None:
        snap["telemetry"] = dataclasses.asdict(telemetry)
    if pass2_audit:
        snap.update(pass2_audit)
    return snap


class AnthropicClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.anthropic_api_key:
            raise AnthropicError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)

    @retry(
        retry=retry_if_exception_type(_TRANSIENT_ERRORS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _create(self, **kwargs: Any):
        return self._client.messages.create(**kwargs)

    def run_structured_state(self, bundle: PromptBundle, image_paths: list[Path]) -> CallResult:
        """Pass 1: force the model to emit DailyState via tool use."""
        system_blocks = _system_blocks(bundle, self.settings.prompt_cache_enabled)
        content = _user_content(bundle, image_paths, self.settings.image_max_dimension)
        t0 = time.monotonic()
        response = self._create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            system=system_blocks,
            tools=[_state_tool()],
            tool_choice={"type": "tool", "name": STATE_TOOL_NAME},
            messages=[{"role": "user", "content": content}],
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        tool_input = _extract_tool_input(response, STATE_TOOL_NAME)
        usage = response.usage
        telemetry = PassTelemetry(
            provider="anthropic",
            model=self.settings.model,
            pass_name="state",
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
            latency_ms=elapsed_ms,
            image_count=len(image_paths),
            request_shape_version="1.0",
        )
        return CallResult(
            text=None,
            tool_input=tool_input,
            raw_response=response.model_dump(mode="json"),
            request_snapshot=_snapshot(
                model=self.settings.model,
                system_blocks=system_blocks,
                body_text=bundle.body,
                image_paths=image_paths,
                tool_name=STATE_TOOL_NAME,
                telemetry=telemetry,
            ),
        )

    def repair_structured_state(self, invalid: dict[str, Any], errors: str) -> CallResult:
        """One repair pass: ask the model to fix a schema-invalid state.

        Lightweight (no framework/images) since this only corrects structure.
        """
        import json

        tool = {
            "name": STATE_TOOL_NAME,
            "description": "Emit the corrected daily analysis state.",
            "input_schema": DailyState.model_json_schema(),
        }
        message = (
            "The previous structured output failed schema validation. Fix it and call "
            f"`{STATE_TOOL_NAME}` again with corrected values, preserving the analysis.\n\n"
            f"Validation errors:\n{errors}\n\n"
            f"Invalid output:\n```json\n{json.dumps(invalid, indent=2)}\n```"
        )
        t0 = time.monotonic()
        response = self._create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            tools=[tool],
            tool_choice={"type": "tool", "name": STATE_TOOL_NAME},
            messages=[{"role": "user", "content": message}],
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        usage = response.usage
        telemetry = PassTelemetry(
            provider="anthropic",
            model=self.settings.model,
            pass_name="repair",
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
            latency_ms=elapsed_ms,
            image_count=0,
            request_shape_version="1.0",
        )
        request_snapshot: dict[str, Any] = {"model": self.settings.model, "mode": "repair"}
        request_snapshot["telemetry"] = dataclasses.asdict(telemetry)
        return CallResult(
            text=None,
            tool_input=_extract_tool_input(response, STATE_TOOL_NAME),
            raw_response=response.model_dump(mode="json"),
            request_snapshot=request_snapshot,
        )

    def run_markdown_report(
        self,
        bundle: PromptBundle,
        image_paths: list[Path],
        *,
        pass2_audit: dict[str, Any] | None = None,
    ) -> CallResult:
        """Pass 2: free-form markdown report.

        First attempt sends the same tools as Pass 1 with tool_choice=none so the
        tools+system cache prefix from Pass 1 can be reused. Some models (notably
        claude-opus-4-8) respond with a short stub preamble instead of markdown;
        when detected, one retry omits tools entirely.
        """
        system_blocks = _system_blocks(bundle, self.settings.prompt_cache_enabled)
        max_dim = (
            self.settings.pass2_image_max_dimension
            if self.settings.pass2_image_optimization_enabled
            else self.settings.image_max_dimension
        )
        content = _user_content(bundle, image_paths, max_dim)
        messages = [{"role": "user", "content": content}]

        t0 = time.monotonic()
        response = self._create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            system=system_blocks,
            tools=[_state_tool()],
            tool_choice={"type": "none"},
            messages=messages,
        )
        text = _extract_text(response)
        stub_retry = False
        tools_in_request = True
        attempt_count = 1
        retry_reason: str | None = None

        if _is_pass2_stub_response(text):
            logger.warning(
                "Pass 2 stub response (%d chars); retrying without tools",
                len(text),
            )
            stub_retry = True
            tools_in_request = False
            attempt_count = 2
            retry_reason = "stub_response"
            t0 = time.monotonic()
            response = self._create(
                model=self.settings.model,
                max_tokens=self.settings.max_output_tokens,
                system=system_blocks,
                messages=messages,
            )
            text = _extract_text(response)
            if _is_pass2_stub_response(text):
                raise AnthropicError(
                    f"Pass 2 returned stub markdown after retry ({len(text)} chars)"
                )

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        usage = response.usage
        telemetry = PassTelemetry(
            provider="anthropic",
            model=self.settings.model,
            pass_name="report",
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
            latency_ms=elapsed_ms,
            attempt_count=attempt_count,
            retry_reason=retry_reason,
            image_count=len(image_paths),
            request_shape_version="1.0",
        )
        audit = dict(pass2_audit or {})
        audit["pass2_image_max_dimension_used"] = max_dim
        audit["pass2_tools_in_request"] = tools_in_request
        audit["pass2_stub_retry"] = stub_retry
        return CallResult(
            text=text,
            tool_input=None,
            raw_response=response.model_dump(mode="json"),
            request_snapshot=_snapshot(
                model=self.settings.model,
                system_blocks=system_blocks,
                body_text=bundle.body,
                image_paths=image_paths,
                tool_name=None,
                pass2_audit=audit,
                telemetry=telemetry,
            ),
        )

    def run_text_structured_state(self, bundle: PromptBundle) -> CallResult:
        """Text-only structured state extraction (e.g. Perplexity migration)."""
        system_blocks = _system_blocks(bundle, self.settings.prompt_cache_enabled)
        tool = {
            "name": STATE_TOOL_NAME,
            "description": "Emit the structured daily analysis state for the session.",
            "input_schema": DailyState.model_json_schema(),
        }
        t0 = time.monotonic()
        response = self._create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            system=system_blocks,
            tools=[tool],
            tool_choice={"type": "tool", "name": STATE_TOOL_NAME},
            messages=[{"role": "user", "content": bundle.body}],
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        usage = response.usage
        telemetry = PassTelemetry(
            provider="anthropic",
            model=self.settings.model,
            pass_name="state",
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
            latency_ms=elapsed_ms,
            image_count=0,
            request_shape_version="1.0",
        )
        return CallResult(
            text=None,
            tool_input=_extract_tool_input(response, STATE_TOOL_NAME),
            raw_response=response.model_dump(mode="json"),
            request_snapshot=_snapshot(
                model=self.settings.model,
                system_blocks=system_blocks,
                body_text=bundle.body,
                image_paths=[],
                tool_name=STATE_TOOL_NAME,
                telemetry=telemetry,
            ),
        )

    def run_text_markdown_report(self, bundle: PromptBundle) -> CallResult:
        """Text-only markdown report generation (e.g. Perplexity migration)."""
        system_blocks = _system_blocks(bundle, self.settings.prompt_cache_enabled)
        t0 = time.monotonic()
        response = self._create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": bundle.body}],
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        text = _extract_text(response)
        usage = response.usage
        telemetry = PassTelemetry(
            provider="anthropic",
            model=self.settings.model,
            pass_name="report",
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
            latency_ms=elapsed_ms,
            image_count=0,
            request_shape_version="1.0",
        )
        return CallResult(
            text=text,
            tool_input=None,
            raw_response=response.model_dump(mode="json"),
            request_snapshot=_snapshot(
                model=self.settings.model,
                system_blocks=system_blocks,
                body_text=bundle.body,
                image_paths=[],
                tool_name=None,
                telemetry=telemetry,
            ),
        )

    def run_substack_article(
        self, daily_state: DailyState, report_markdown: str
    ) -> tuple[SubstackArticle, dict[str, Any]]:
        """Generate the editorial article with the selected Anthropic model."""
        import json

        body = build_substack_prompt(daily_state, report_markdown)
        tool = {
            "name": SUBSTACK_TOOL_NAME,
            "description": "Emit the validated Substack article.",
            "input_schema": SubstackArticle.model_json_schema(),
        }
        t0 = time.monotonic()
        try:
            response = self._create(
                model=self.settings.model,
                max_tokens=3000,
                system=SUBSTACK_INSTRUCTIONS,
                tools=[tool],
                tool_choice={"type": "tool", "name": SUBSTACK_TOOL_NAME},
                messages=[{"role": "user", "content": body}],
            )
        except AnthropicError:
            raise
        except Exception as exc:
            raise AnthropicError("Anthropic Substack request failed") from exc
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        payload = _extract_tool_input(response, SUBSTACK_TOOL_NAME)
        try:
            article = parse_substack_response(json.dumps(payload))
        except ValueError as exc:
            raise AnthropicError("Anthropic Substack response was invalid") from exc
        usage = response.usage
        telemetry = PassTelemetry(
            provider="anthropic",
            model=self.settings.model,
            pass_name="substack",
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
            latency_ms=elapsed_ms,
            image_count=0,
            request_shape_version="1.0",
        )
        return article, {
            "model": self.settings.model,
            "mode": "substack",
            "telemetry": dataclasses.asdict(telemetry),
            "body_chars": len(body),
            "response_raw": response.model_dump(mode="json"),
        }


def _extract_tool_input(response: Any, tool_name: str) -> dict[str, Any]:
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
            return dict(block.input)
    raise AnthropicError(f"response did not contain a '{tool_name}' tool_use block")


def _extract_text(response: Any) -> str:
    parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    text = "\n".join(parts).strip()
    if not text:
        raise AnthropicError("response did not contain any text content")
    return text
