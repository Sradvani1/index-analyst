"""Provider-neutral types and Protocol for the two-pass analytical pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .prompts import PromptBundle
from .schemas import DailyState, SubstackArticle


class PipelineClientError(Exception):
    """Provider-neutral failure from an analytical or editorial client."""


@dataclass
class CallResult:
    """Provider-neutral result from a single pipeline pass.

    All fields are JSON-serialisable dicts/primitives — no provider SDK types
    leak through. The engine persists these for audit/comparison without
    inspecting their contents.
    """

    text: str | None
    tool_input: dict[str, Any] | None
    raw_response: dict[str, Any]
    request_snapshot: dict[str, Any]


@dataclass
class PassTelemetry:
    """Normalised per-pass observability payload.

    Embedded in ``CallResult.request_snapshot["telemetry"]``. Fields the
    provider cannot supply remain ``None``; the engine never parses this
    payload but persists it for cross-provider comparison.
    """

    provider: str
    model: str
    pass_name: str  # "state" | "repair" | "report"
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    latency_ms: int | None = None
    attempt_count: int = 1
    retry_reason: str | None = None
    image_count: int = 0
    request_shape_version: str = "1.0"


class PipelineLLMClient(Protocol):
    """Interface each analytical-pass provider must satisfy.

    Structural subtyping only — no inheritance required. Each method matches
    the corresponding ``AnthropicClient`` signature exactly.
    """

    def run_structured_state(
        self, bundle: PromptBundle, image_paths: list[Path]
    ) -> CallResult: ...

    def repair_structured_state(
        self, invalid: dict[str, Any], errors: str
    ) -> CallResult: ...

    def run_markdown_report(
        self,
        bundle: PromptBundle,
        image_paths: list[Path],
        *,
        pass2_audit: dict[str, Any] | None = None,
    ) -> CallResult: ...

    def run_substack_article(
        self, daily_state: DailyState, report_markdown: str
    ) -> tuple[SubstackArticle, dict[str, Any]]: ...
