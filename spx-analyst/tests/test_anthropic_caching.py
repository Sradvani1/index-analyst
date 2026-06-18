"""Tests for the prompt-cache prefix contract and request-snapshot metadata."""

from __future__ import annotations

from pathlib import Path

from src.anthropic_client import STATE_TOOL_NAME, _snapshot, _state_tool, _system_blocks
from src.prompts import PromptBundle


def _bundle() -> PromptBundle:
    return PromptBundle(system_role="role", framework="framework", body="body")


def test_system_block_marks_framework_cached_when_enabled():
    blocks = _system_blocks(_bundle(), cache_enabled=True)
    assert blocks[1]["cache_control"] == {"type": "ephemeral"}


def test_system_block_no_cache_when_disabled():
    blocks = _system_blocks(_bundle(), cache_enabled=False)
    assert "cache_control" not in blocks[1]


def test_state_tool_is_byte_stable_across_passes():
    # Both passes must send identical tool definitions so the tools+system
    # cache prefix is reused on Pass 2.
    assert _state_tool() == _state_tool()
    assert _state_tool()["name"] == STATE_TOOL_NAME


def test_snapshot_records_image_count_and_framework_cache():
    system_blocks = [
        {"type": "text", "text": "role"},
        {"type": "text", "text": "framework", "cache_control": {"type": "ephemeral"}},
    ]
    snapshot = _snapshot(
        model="m",
        system_blocks=system_blocks,
        body_text="Precomputed analysis context body",
        image_paths=[Path("a.png"), Path("b.png")],
        tool_name=None,
    )
    assert snapshot["image_count"] == 2
    assert snapshot["framework_cached"] is True
