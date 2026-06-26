/** Pure parsing helpers for the daily report markdown. Reusable across layers. */

export type Tone = "bull" | "bear" | "caution" | "neutral";

export interface ReportHeader {
  title?: string;
  close?: string;
  change?: string;
  changePct?: string;
  changeDirection?: "up" | "down";
  instrument?: string;
  regime?: string;
}

export interface ReportSection {
  id: string;
  title: string;
  body: string;
}

export interface SplitReport {
  preamble: string;
  sections: ReportSection[];
}

export interface MatrixRow {
  cells: string[];
  tone: Tone;
  isAction: boolean;
}

export interface DecisionMatrix {
  headers: string[];
  rows: MatrixRow[];
}

/** Classify a signal/action string into a semantic tone. */
export function toneFor(text: string | null | undefined): Tone {
  const t = (text ?? "").toLowerCase();
  if (!t) {
    return "neutral";
  }
  // Standby/watch stances take precedence: a "hold ... monitor ... reentry"
  // action is a watch signal, not bullish, even though it mentions re-entry.
  if (/\bhold\b|monitor|\bwatch\b/.test(t)) {
    return "caution";
  }
  // Bearish: "extreme fear" must not be caught by the "fear" caution rule.
  if (/\btrim\b|\bbear\b|extreme fear|\bsell\b|reduce/.test(t)) {
    return "bear";
  }
  if (/\bbull\b|\bbuy\b|aligned_buy/.test(t)) {
    return "bull";
  }
  if (/caution|insufficient|elevated|moderate|\bfear\b|thin|mixed|neutral/.test(t)) {
    return "caution";
  }
  return "neutral";
}

/** Tailwind class fragments per tone — editorial semantic colors. */
export const TONE_SURFACE: Record<Tone, string> = {
  bull: "bg-[color-mix(in_srgb,var(--market-green)_12%,var(--surface-0))] text-[var(--market-green)] ring-[color-mix(in_srgb,var(--market-green)_25%,transparent)]",
  bear: "bg-[color-mix(in_srgb,var(--risk-red)_10%,var(--surface-0))] text-[var(--risk-red)] ring-[color-mix(in_srgb,var(--risk-red)_22%,transparent)]",
  caution:
    "bg-[color-mix(in_srgb,var(--caution-amber)_12%,var(--surface-0))] text-[var(--caution-amber)] ring-[color-mix(in_srgb,var(--caution-amber)_25%,transparent)]",
  neutral: "bg-muted text-foreground ring-border",
};

export const TONE_DOT: Record<Tone, string> = {
  bull: "bg-market-green",
  bear: "bg-risk-red",
  caution: "bg-caution-amber",
  neutral: "bg-muted-foreground/50",
};

export function isDecisionMatrixSection(title: string): boolean {
  return /decision matrix/i.test(title);
}

export function isEvidenceSection(title: string): boolean {
  return /evidence (and tensions|reconciliation)/i.test(title);
}

/** Parse the H1 title and the bold subtitle line for close, day change, regime. */
export function parseHeader(markdown: string): ReportHeader {
  const header: ReportHeader = {};

  const titleMatch = markdown.match(/^#\s+(.+?)\s*$/m);
  if (titleMatch) {
    header.title = titleMatch[1].trim();
  }

  // Subtitle example:
  // **Close: 7,431.46 (+37.16, +0.50%) | Instrument: SCHK | Regime: Golden Cross intact**
  const closeMatch = markdown.match(
    /Close:\s*([\d,]+(?:\.\d+)?)\s*\(([-+][\d,.]+),\s*([-+][\d.]+%)\)/i,
  );
  if (closeMatch) {
    header.close = closeMatch[1];
    header.change = closeMatch[2];
    header.changePct = closeMatch[3];
    header.changeDirection = closeMatch[2].startsWith("-") ? "down" : "up";
  } else {
    const closeOnly = markdown.match(/Close:\s*([\d,]+(?:\.\d+)?)/i);
    if (closeOnly) {
      header.close = closeOnly[1];
    }
  }

  const instrumentMatch = markdown.match(/Instrument:\s*([^|*\n]+)/i);
  if (instrumentMatch) {
    header.instrument = instrumentMatch[1].trim();
  }

  const regimeMatch = markdown.match(/Regime:\s*([^|*\n]+)/i);
  if (regimeMatch) {
    header.regime = regimeMatch[1].trim();
  }

  return header;
}

function slugify(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Split the report on `## ` headings into ordered sections plus a preamble. */
export function splitSections(markdown: string): SplitReport {
  const lines = markdown.split("\n");
  const sections: ReportSection[] = [];
  const preambleLines: string[] = [];

  let current: { title: string; lines: string[] } | null = null;
  const usedIds = new Set<string>();

  const flush = () => {
    if (current) {
      let id = slugify(current.title) || "section";
      let n = 2;
      while (usedIds.has(id)) {
        id = `${slugify(current.title)}-${n++}`;
      }
      usedIds.add(id);
      sections.push({ id, title: current.title, body: current.lines.join("\n").trim() });
    }
  };

  for (const line of lines) {
    const headingMatch = line.match(/^##\s+(.+?)\s*$/);
    if (headingMatch) {
      flush();
      current = { title: headingMatch[1].trim(), lines: [] };
      continue;
    }
    if (current) {
      current.lines.push(line);
    } else {
      preambleLines.push(line);
    }
  }
  flush();

  return { preamble: preambleLines.join("\n").trim(), sections };
}

const POSTURE_SECTION = /today's posture/i;

/** Sections shown in the run viewer — drops header snapshot / hero fields above Today's Posture. */
export function viewerSections(markdown: string): ReportSection[] {
  const { sections } = splitSections(markdown);
  const start = sections.findIndex((section) => POSTURE_SECTION.test(section.title));
  return start === -1 ? sections : sections.slice(start);
}

const SECTION_TAB_LABELS: Array<{ match: RegExp; label: string }> = [
  { match: /today's posture/i, label: "Posture" },
  { match: /market regime/i, label: "Regime" },
  { match: /price and trend/i, label: "Price & Trend" },
  { match: /technicals and sentiment/i, label: "Technicals" },
  { match: /valuation and erp/i, label: "Valuation" },
  { match: /risk and monte carlo/i, label: "Risk / MC" },
  { match: /tactical levels/i, label: "Tactical" },
  { match: /evidence (and tensions|reconciliation)/i, label: "Evidence" },
  { match: /decision matrix/i, label: "Matrix" },
];

/** Short tab label for a report section heading. */
export function sectionTabLabel(title: string): string {
  for (const { match, label } of SECTION_TAB_LABELS) {
    if (match.test(title)) {
      return label;
    }
  }
  return title;
}

function parseTableRow(line: string): string[] | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("|")) {
    return null;
  }
  // Strip leading/trailing pipes, then split.
  return trimmed
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());
}

function isSeparatorRow(cells: string[]): boolean {
  return cells.every((c) => /^:?-{2,}:?$/.test(c.replace(/\s/g, "")));
}

function stripInlineMarkdown(text: string): string {
  return text.replace(/\*\*/g, "").replace(/\*/g, "").trim();
}

/** Parse a GFM table from a Decision Matrix section body. */
export function parseDecisionMatrix(sectionBody: string): DecisionMatrix | null {
  const rows: string[][] = [];
  for (const line of sectionBody.split("\n")) {
    const cells = parseTableRow(line);
    if (cells) {
      rows.push(cells);
    }
  }
  if (rows.length < 2) {
    return null;
  }

  const headers = rows[0].map(stripInlineMarkdown);
  const dataRows = rows.slice(1).filter((cells) => !isSeparatorRow(cells));

  const matrixRows: MatrixRow[] = dataRows.map((cells) => {
    const cleaned = cells.map(stripInlineMarkdown);
    const isAction = /recommended action/i.test(cleaned[0] ?? "");
    // Tone keys off the last column (the Signal verdict) when present.
    const signalText = cleaned[cleaned.length - 1] ?? "";
    return { cells: cleaned, tone: toneFor(signalText), isAction };
  });

  return { headers, rows: matrixRows };
}
