"""Generation and validation of the daily podcast script from the Substack article."""

from __future__ import annotations

import html
import json
import re
from typing import Any

from .schemas import PodcastScript

# Written-word target for a ~3-minute read-aloud clip. Gemini TTS also pauses
# between sentences, so the spoken duration is measured separately and only
# reported as a warning.
PODCAST_MIN_WORDS = 380
PODCAST_MAX_WORDS = 520

PODCAST_INSTRUCTIONS = """You are the writer and host for a daily stock-market podcast.

Task:
Condense the supplied daily Substack article into a ~3-minute single-host script (~380-520 words) that sounds natural when read aloud.

Source authority:
- The supplied article is authoritative. Do not independently reanalyze the market or introduce new levels, signals, or conclusions.
- Preserve the article's structural bias, market conclusion, posture, and the key levels, confirmation conditions, and invalidation conditions.
- Use only facts from the supplied article.

Structure (do not use headings or labels; flow continuously):
- Open with an engaging hook that states the day's headline and closing level.
- Briefly describe what happened today.
- Explain why it matters.
- Give the concrete levels and signals to watch.
- Close with the bottom line.

Audience and style:
- Single host, calm and analytical, professional yet accessible.
- Short, clear sentences with a natural conversational flow and smooth transitions.
- Optimized for text-to-speech: spell out numbers and symbols in words (for example, "seven thousand seven hundred eighty-five", "point seven six", "S and P five hundred", "two and a half percent"). Do not use abbreviations.
- Do not use section titles, headings, bullet lists, or any Markdown formatting.
- Do not use em dashes, colons, or semicolons anywhere. Use periods or commas instead.
- Do not mention Monte Carlo, internal framework terminology, source documents, model mechanics, or the generation process.
- Do not make guarantees, provide personalized investment advice, or recommend position sizes or allocations.

Required output:
- Return only the JSON object defined by the response schema: a short episode title and the script as a single continuous prose string.
- Do not return Markdown fences, commentary, or any extra fields.
"""

_MARKDOWN_ARTIFACT_RE = re.compile(r"^#{1,6}\s|\*\*|`|^[-*]\s+", re.MULTILINE)


def build_podcast_prompt(substack_markdown: str) -> str:
    """Build the user prompt body, unescaping HTML entities from storage."""
    return (
        "SOURCE CONTEXT: DAILY SUBSTACK ARTICLE\n"
        "```markdown\n"
        f"{html.unescape(substack_markdown).strip()}\n"
        "```"
    )


def validate_podcast_script(script: PodcastScript) -> None:
    """Enforce structural constraints on a generated script."""
    if not script.title.strip() or not script.script.strip():
        raise ValueError("podcast title and script must be non-empty")
    if "\n" in script.title or _MARKDOWN_ARTIFACT_RE.search(script.title):
        raise ValueError("podcast title contains Markdown or line breaks")
    word_count = len(script.script.split())
    if not PODCAST_MIN_WORDS <= word_count <= PODCAST_MAX_WORDS:
        raise ValueError(
            f"podcast script word count {word_count} outside "
            f"[{PODCAST_MIN_WORDS}, {PODCAST_MAX_WORDS}]"
        )
    if _MARKDOWN_ARTIFACT_RE.search(script.script):
        raise ValueError("podcast script contains Markdown or heading artifacts")


def render_podcast_script(script: PodcastScript) -> str:
    """Render the script to plain transcript text for storage and display."""
    return f"# {script.title}\n\n{script.script}\n"


def parse_podcast_response(raw_text: str) -> PodcastScript:
    """Parse and validate the model's JSON response into a ``PodcastScript``."""
    try:
        payload: Any = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("podcast model returned invalid JSON") from exc
    script = PodcastScript.model_validate(payload)
    validate_podcast_script(script)
    return script