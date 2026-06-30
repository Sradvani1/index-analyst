"""Render investor-facing PDF from daily report markdown."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

import markdown

from .web.report_parse import split_sections, strip_inline_markdown

_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_DATE_IN_TITLE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_FRAMEWORK_VERSION_RE = re.compile(r"\*\*Framework version:\*\*\s*(.+)", re.IGNORECASE)
_CLOSE_LINE_RE = re.compile(
    r"\*\*Close:\*\*\s*([\d,]+(?:\.\d+)?)"
    r"(?:\s*\(([-+][\d,.]+),\s*([-+][\d.]+%)\))?"
    r"(?:\s*\|\s*\*\*Structural Bias:\*\*\s*([^|*]+))?"
    r"(?:\s*\|\s*\*\*Posture:\*\*\s*([^|*\n]+))?",
    re.IGNORECASE,
)
_DECISION_MATRIX_RE = re.compile(r"decision matrix", re.IGNORECASE)
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")
_SEPARATOR_ROW_RE = re.compile(r"^:?-{2,}:?$")

_MD = markdown.Markdown(extensions=["tables", "sane_lists", "nl2br"], output_format="html5")


@dataclass(frozen=True)
class ReportMeta:
    date: str
    title: str
    framework_version: str | None = None
    close: str | None = None
    structural_bias: str | None = None
    posture: str | None = None
    change: str | None = None
    change_pct: str | None = None
    change_direction: str | None = None


def tone_for(text: str | None) -> str:
    """Classify a signal/action string into a semantic tone."""
    t = (text or "").lower()
    if not t:
        return "neutral"
    if re.search(r"\bhold\b|monitor|\bwatch\b", t):
        return "caution"
    if re.search(r"\btrim\b|\bbear\b|extreme fear|\bsell\b|reduce", t):
        return "bear"
    if re.search(r"\bbull\b|\bbuy\b|aligned_buy", t):
        return "bull"
    if re.search(r"caution|insufficient|elevated|moderate|\bfear\b|thin|mixed|neutral", t):
        return "caution"
    return "neutral"


def _parse_table_row(line: str) -> list[str] | None:
    match = _TABLE_ROW_RE.match(line.strip())
    if not match:
        return None
    return [cell.strip() for cell in match.group(1).split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return all(_SEPARATOR_ROW_RE.match(cell.replace(" ", "")) for cell in cells)


def parse_report_meta(markdown_text: str, *, fallback_date: str | None = None) -> ReportMeta:
    """Extract title and header metadata from report preamble."""
    title_match = _HEADING_RE.search(markdown_text)
    title = title_match.group(1).strip() if title_match else "SPX Daily Analysis"
    date_match = _DATE_IN_TITLE_RE.search(title)
    date = date_match.group(1) if date_match else (fallback_date or "unknown")

    framework_version: str | None = None
    fw_match = _FRAMEWORK_VERSION_RE.search(markdown_text)
    if fw_match:
        framework_version = fw_match.group(1).strip()

    close: str | None = None
    structural_bias: str | None = None
    posture: str | None = None
    change: str | None = None
    change_pct: str | None = None
    change_direction: str | None = None

    close_match = _CLOSE_LINE_RE.search(markdown_text)
    if close_match:
        close = close_match.group(1)
        change = close_match.group(2)
        change_pct = close_match.group(3)
        if change:
            change_direction = "down" if change.startswith("-") else "up"
        structural_bias = (close_match.group(4) or "").strip() or None
        posture = (close_match.group(5) or "").strip() or None

    return ReportMeta(
        date=date,
        title=title,
        framework_version=framework_version,
        close=close,
        structural_bias=structural_bias,
        posture=posture,
        change=change,
        change_pct=change_pct,
        change_direction=change_direction,
    )


def _render_markdown(body: str) -> str:
    _MD.reset()
    return _MD.convert(body.strip())


def _render_decision_matrix(body: str) -> str:
    rows: list[list[str]] = []
    for line in body.splitlines():
        cells = _parse_table_row(line)
        if cells is not None:
            rows.append(cells)

    if len(rows) < 2:
        return _render_markdown(body)

    headers = [strip_inline_markdown(cell) for cell in rows[0]]
    data_rows = [row for row in rows[1:] if not _is_separator_row(row)]

    parts = ['<div class="matrix-wrap"><table class="matrix">', "<thead><tr>"]
    for header in headers:
        parts.append(f"<th>{html.escape(header)}</th>")
    parts.append("</tr></thead><tbody>")

    for row in data_rows:
        cleaned = [strip_inline_markdown(cell) for cell in row]
        signal_text = cleaned[-1] if cleaned else ""
        tone = tone_for(signal_text)
        is_action = bool(cleaned and re.search(r"recommended action", cleaned[0], re.I))
        row_class = " ".join(
            filter(None, ["matrix-row", f"tone-{tone}", "matrix-action" if is_action else None])
        )
        parts.append(f'<tr class="{row_class}">')
        for cell in cleaned:
            parts.append(f"<td>{html.escape(cell)}</td>")
        parts.append("</tr>")

    parts.extend(["</tbody></table></div>"])
    return "\n".join(parts)


def _header_html(meta: ReportMeta) -> str:
    close_display = html.escape(meta.close) if meta.close else "—"
    return (
        f'<header class="report-header">'
        f'<div class="header-meta">'
        f'<span class="header-item">{html.escape(meta.date)}</span>'
        f'<span class="header-item header-close">{close_display}</span>'
        f"</div></header>"
    )


def _report_css() -> str:
    return """
:root {
  --ink-900: #151922;
  --ink-700: #2b3443;
  --ink-500: #5e6a7d;
  --paper-50: #faf8f3;
  --paper-100: #f3f0e8;
  --surface-0: #ffffff;
  --surface-1: #f7f5ef;
  --border-soft: #e6e0d4;
  --market-green: #0e6b57;
  --signal-blue: #295c9b;
  --caution-amber: #a56a17;
  --risk-red: #a23a3a;
  --shadow-2: 0 6px 18px rgba(18, 24, 32, 0.06);
  --max-width: 52rem;
}

* { box-sizing: border-box; }

html {
  font-size: 16px;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

body {
  margin: 0;
  background: var(--paper-50);
  color: var(--ink-900);
  font-family: "Source Serif 4", "Iowan Old Style", "Palatino Linotype", Palatino, serif;
  line-height: 1.72;
}

.report {
  max-width: calc(var(--max-width) + 4rem);
  margin: 0 auto;
  padding: 0 0 2rem;
}

.report-header {
  display: block;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-soft);
  text-align: right;
}

.header-meta {
  display: block;
}

.header-meta .header-item {
  display: block;
}

.header-item {
  font-family: "DM Sans", system-ui, sans-serif;
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.3;
  color: var(--ink-900);
}

.header-close {
  font-variant-numeric: tabular-nums;
}

.tone-bull { color: var(--market-green); background: #e6f2ef; }
.tone-bear { color: var(--risk-red); background: #f8ecec; }
.tone-caution { color: var(--caution-amber); background: #f7f0e4; }
.tone-neutral { color: var(--ink-700); background: var(--surface-1); border-color: var(--border-soft); }

.section {
  margin-bottom: 2.25rem;
  scroll-margin-top: 1rem;
}

.section h2 {
  margin: 0 0 0.85rem;
  padding-bottom: 0.45rem;
  border-bottom: 2px solid var(--border-soft);
  font-family: "DM Sans", system-ui, sans-serif;
  font-size: 1.15rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.section-body {
  max-width: var(--max-width);
  font-size: 1.05rem;
}

.section-body p { margin: 0 0 1rem; }
.section-body p:last-child { margin-bottom: 0; }

.section-body h3 {
  margin: 1.25rem 0 0.5rem;
  font-family: "DM Sans", system-ui, sans-serif;
  font-size: 1rem;
  font-weight: 600;
}

.section-body ul, .section-body ol {
  margin: 0 0 1rem;
  padding-left: 1.35rem;
}

.section-body li { margin: 0.25rem 0; }

.section-body strong { font-weight: 600; }

.section-body table:not(.matrix) {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.92rem;
}

.section-body th,
.section-body td {
  border: 1px solid var(--border-soft);
  padding: 0.45rem 0.65rem;
  text-align: left;
  vertical-align: top;
}

.matrix-wrap {
  overflow-x: auto;
  margin: 0.5rem 0 0;
  border: 1px solid var(--border-soft);
  border-radius: 0.65rem;
  background: var(--surface-0);
}

table.matrix {
  width: 100%;
  border-collapse: collapse;
  font-family: "DM Sans", system-ui, sans-serif;
  font-size: 0.82rem;
}

table.matrix th {
  padding: 0.55rem 0.7rem;
  text-align: left;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-500);
  background: var(--surface-1);
  border-bottom: 1px solid var(--border-soft);
}

table.matrix td {
  padding: 0.55rem 0.7rem;
  border-bottom: 1px solid var(--border-soft);
  vertical-align: top;
  line-height: 1.45;
}

table.matrix tr:last-child td { border-bottom: none; }

.matrix-row.matrix-action td {
  font-weight: 600;
}

.matrix-row.matrix-action.tone-bull td { background: #eef6f3; }
.matrix-row.matrix-action.tone-bear td { background: #faeeee; }
.matrix-row.matrix-action.tone-caution td { background: #f9f3e8; }

@media print {
  body { background: white; }
  .report { padding: 0; max-width: none; }
  .report-header { break-inside: avoid; }
  .section { break-inside: avoid-page; }
}

@page {
  size: letter;
  margin: 0.65in 0.75in 0.75in;
}
""".strip()


def render_investor_report_html(markdown_text: str, *, fallback_date: str | None = None) -> str:
    """Convert daily report markdown into a self-contained HTML document."""
    meta = parse_report_meta(markdown_text, fallback_date=fallback_date)
    rendered_sections: list[str] = []

    for title, body in split_sections(markdown_text):
        if _DECISION_MATRIX_RE.search(title):
            body_html = _render_decision_matrix(body)
        else:
            body_html = _render_markdown(body)

        rendered_sections.append(
            f"""
<section class="section">
  <h2>{html.escape(title)}</h2>
  <div class="section-body">{body_html}</div>
</section>
""".strip()
        )

    sections_html = "\n".join(rendered_sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(meta.title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,500&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
  <style>{_report_css()}</style>
</head>
<body>
  <article class="report">
    {_header_html(meta)}
    <main>
      {sections_html}
    </main>
  </article>
</body>
</html>
"""


def render_investor_report_pdf(
    markdown_text: str,
    *,
    fallback_date: str | None = None,
    base_url: str | Path | None = None,
) -> bytes:
    """Convert daily report markdown into PDF bytes."""
    from weasyprint import HTML

    html_doc = render_investor_report_html(markdown_text, fallback_date=fallback_date)
    return HTML(string=html_doc, base_url=str(base_url or Path.cwd())).write_pdf()


def default_investor_report_pdf_path(date: str, pdf_dir: Path) -> Path:
    """Default output path for a dated investor PDF."""
    return pdf_dir / f"{date}-investor-report.pdf"


def export_investor_report(
    source: Path,
    output: Path | None = None,
    *,
    fallback_date: str | None = None,
    pdf_dir: Path | None = None,
) -> Path:
    """Read markdown from ``source`` and write a formatted PDF to ``output``."""
    markdown_text = source.read_text(encoding="utf-8")
    meta = parse_report_meta(markdown_text, fallback_date=fallback_date)
    date = meta.date if meta.date != "unknown" else (fallback_date or "unknown")

    if output is None:
        from .config import get_settings

        dest = default_investor_report_pdf_path(date, pdf_dir or get_settings().daily_pdfs_dir)
    else:
        dest = output

    pdf_bytes = render_investor_report_pdf(
        markdown_text,
        fallback_date=fallback_date,
        base_url=source.parent,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(pdf_bytes)
    return dest
