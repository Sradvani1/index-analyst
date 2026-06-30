import { DecisionMatrix } from "@/components/decision-matrix";
import { ReportMarkdown } from "@/components/report-markdown";
import { cn } from "@/lib/utils";
import {
  isDecisionMatrixSection,
  isEvidenceSection,
  type ReportSection,
} from "@/lib/report";
import type { DailyState } from "@/lib/types";

interface SectionBlockProps {
  section: ReportSection;
  dailyState?: DailyState;
}

export function SectionBlock({ section, dailyState }: SectionBlockProps) {
  if (isDecisionMatrixSection(section.title)) {
    return (
      <section>
        <h2 className="font-display text-2xl font-semibold tracking-tight text-ink-900">
          {section.title}
        </h2>
        <div className="mt-4 rounded-[14px] border border-border-soft bg-surface-0 p-5 shadow-editorial-1 ring-1 ring-market-green/25">
          {dailyState?.decision_matrix ? (
            <DecisionMatrix matrix={dailyState.decision_matrix} />
          ) : (
            <SectionBody body={section.body} />
          )}
        </div>
      </section>
    );
  }

  if (isEvidenceSection(section.title)) {
    return (
      <section
        className={cn(
          "rounded-[14px] border border-border-soft p-5 shadow-editorial-1",
          "bg-[color-mix(in_srgb,var(--caution-amber)_8%,var(--surface-0))]",
        )}
      >
        <h2 className="font-display text-2xl font-semibold tracking-tight text-ink-900">
          {section.title}
        </h2>
        <div className="mt-4">
          <SectionBody body={section.body} />
        </div>
      </section>
    );
  }

  return (
    <section>
      <h2 className="font-display text-2xl font-semibold tracking-tight text-ink-900">
        {section.title}
      </h2>
      <div className="mt-4">
        <SectionBody body={section.body} />
      </div>
    </section>
  );
}

function SectionBody({ body }: { body: string }) {
  const trimmed = body.trim();
  if (!trimmed) {
    return <p className="text-sm text-ink-500">No content for this section.</p>;
  }
  return <ReportMarkdown markdown={trimmed} variant="article" />;
}
