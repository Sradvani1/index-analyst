"""Anthropic Claude wrapper for the two-pass pipeline.

Handles multimodal image encoding (with resize), prompt caching of the static
framework block, forced tool-use for structured state, one transient retry, and
secret-scrubbed request/response snapshots.
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic
from PIL import Image
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import Settings, get_settings
from .prompts import PromptBundle
from .schemas import DailyState

logger = logging.getLogger(__name__)

STATE_TOOL_NAME = "emit_daily_state"

_TRANSIENT_ERRORS = (
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


class AnthropicError(Exception):
    """Raised when the provider response is missing or unusable."""


@dataclass
class CallResult:
    text: str | None
    tool_input: dict[str, Any] | None
    raw_response: dict[str, Any]
    request_snapshot: dict[str, Any]


def _encode_image(path: Path, max_dim: int) -> dict[str, Any]:
    with Image.open(path) as img:
        img = img.convert("RGB")
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
    data = base64.standard_b64encode(buffer.getvalue()).decode("ascii")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": data},
    }


def _system_blocks(bundle: PromptBundle, cache_enabled: bool) -> list[dict[str, Any]]:
    framework_block: dict[str, Any] = {"type": "text", "text": bundle.framework}
    if cache_enabled:
        framework_block["cache_control"] = {"type": "ephemeral"}
    return [{"type": "text", "text": bundle.system_role}, framework_block]


def _state_tool() -> dict[str, Any]:
    """The emit_daily_state tool, built identically for both passes.

    Both passes must send byte-identical tool definitions so the cached
    tools+system prefix (framework) is reused on Pass 2. Pass 2 sets
    tool_choice="none" so it still returns free-form markdown.
    """
    return {
        "name": STATE_TOOL_NAME,
        "description": "Emit the structured daily analysis state for the session.",
        "input_schema": DailyState.model_json_schema(),
    }


def _user_content(bundle: PromptBundle, image_paths: list[Path], max_dim: int) -> list[dict[str, Any]]:
    # Images are NOT cached: they live in the messages layer, and Pass 1 forces the
    # tool while Pass 2 does not — the differing tool_choice invalidates the messages
    # cache, so an image breakpoint would only incur write cost with no read.
    content: list[dict[str, Any]] = [_encode_image(p, max_dim) for p in image_paths]
    content.append({"type": "text", "text": bundle.body})
    return content


def _snapshot(
    *,
    model: str,
    system_blocks: list[dict[str, Any]],
    body_text: str,
    image_paths: list[Path],
    tool_name: str | None,
) -> dict[str, Any]:
    """Reproducibility metadata. Excludes secrets and raw image bytes."""
    return {
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


class AnthropicClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.anthropic_api_key:
            raise AnthropicError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)

    @retry(
        retry=retry_if_exception_type(_TRANSIENT_ERRORS),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _create(self, **kwargs: Any):
        return self._client.messages.create(**kwargs)

    def run_structured_state(self, bundle: PromptBundle, image_paths: list[Path]) -> CallResult:
        """Pass 1: force the model to emit DailyState via tool use."""
        system_blocks = _system_blocks(bundle, self.settings.prompt_cache_enabled)
        content = _user_content(bundle, image_paths, self.settings.image_max_dimension)
        response = self._create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            system=system_blocks,
            tools=[_state_tool()],
            tool_choice={"type": "tool", "name": STATE_TOOL_NAME},
            messages=[{"role": "user", "content": content}],
        )
        tool_input = _extract_tool_input(response, STATE_TOOL_NAME)
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
        response = self._create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            tools=[tool],
            tool_choice={"type": "tool", "name": STATE_TOOL_NAME},
            messages=[{"role": "user", "content": message}],
        )
        return CallResult(
            text=None,
            tool_input=_extract_tool_input(response, STATE_TOOL_NAME),
            raw_response=response.model_dump(mode="json"),
            request_snapshot={"model": self.settings.model, "mode": "repair"},
        )

    def run_markdown_report(self, bundle: PromptBundle, image_paths: list[Path]) -> CallResult:
        """Pass 2: free-form markdown report.

        Sends the same tools as Pass 1 (with tool_choice="none") so the cached
        tools+system prefix is reused; the model still returns markdown text.
        """
        system_blocks = _system_blocks(bundle, self.settings.prompt_cache_enabled)
        content = _user_content(bundle, image_paths, self.settings.image_max_dimension)
        response = self._create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            system=system_blocks,
            tools=[_state_tool()],
            tool_choice={"type": "none"},
            messages=[{"role": "user", "content": content}],
        )
        text = _extract_text(response)
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
        response = self._create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            system=system_blocks,
            tools=[tool],
            tool_choice={"type": "tool", "name": STATE_TOOL_NAME},
            messages=[{"role": "user", "content": bundle.body}],
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
            ),
        )

    def run_text_markdown_report(self, bundle: PromptBundle) -> CallResult:
        """Text-only markdown report generation (e.g. Perplexity migration)."""
        system_blocks = _system_blocks(bundle, self.settings.prompt_cache_enabled)
        response = self._create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": bundle.body}],
        )
        text = _extract_text(response)
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
            ),
        )


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
