"use client";

import { useState } from "react";

import { DecisionMatrix } from "@/components/decision-matrix";
import { ReportMarkdown } from "@/components/report-markdown";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  isDecisionMatrixSection,
  isEvidenceSection,
  sectionTabLabel,
  type ReportSection,
} from "@/lib/report";
import type { DailyState } from "@/lib/types";

interface ReportTabsProps {
  sections: ReportSection[];
  dailyState?: DailyState;
}

export function ReportTabs({ sections, dailyState }: ReportTabsProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  if (sections.length === 0) {
    return null;
  }

  return (
    <div className="flex min-w-0 flex-col gap-5">
      <div className="-mx-1 overflow-x-auto px-1 pb-1">
        <div
          role="tablist"
          aria-label="Report sections"
          className="flex min-w-max gap-1"
        >
          {sections.map((section, index) => {
            const selected = index === activeIndex;
            const label = sectionTabLabel(section.title);
            return (
              <button
                key={section.id}
                type="button"
                role="tab"
                id={`tab-${section.id}`}
                aria-selected={selected}
                aria-controls={`panel-${section.id}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => setActiveIndex(index)}
                style={
                  selected
                    ? {
                        backgroundColor: "#0e6b57",
                        borderColor: "#0e6b57",
                        color: "#ffffff",
                      }
                    : undefined
                }
                className={cn(
                  "appearance-none rounded-lg border px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors",
                  selected
                    ? "font-semibold"
                    : "border-transparent bg-surface-1 text-ink-700 hover:border-border-soft hover:bg-paper-100 hover:text-ink-900",
                )}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {sections.map((section, index) => (
        <div
          key={section.id}
          role="tabpanel"
          id={`panel-${section.id}`}
          aria-labelledby={`tab-${section.id}`}
          hidden={index !== activeIndex}
          className={index === activeIndex ? "block min-w-0" : "hidden"}
        >
          <SectionContent section={section} dailyState={dailyState} />
        </div>
      ))}
    </div>
  );
}

function SectionContent({
  section,
  dailyState,
}: {
  section: ReportSection;
  dailyState?: DailyState;
}) {
  if (isDecisionMatrixSection(section.title)) {
    return (
      <SectionCard section={section} accent>
        {dailyState?.decision_matrix ? (
          <DecisionMatrix matrix={dailyState.decision_matrix} />
        ) : (
          <SectionBody body={section.body} />
        )}
      </SectionCard>
    );
  }

  if (isEvidenceSection(section.title)) {
    return (
      <Card
        className={cn(
          "overflow-visible border-border-soft shadow-editorial-1",
          "bg-[color-mix(in_srgb,var(--caution-amber)_8%,var(--surface-0))]",
        )}
      >
        <CardHeader>
          <CardTitle className="font-display text-lg text-ink-900">
            {section.title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <SectionBody body={section.body} />
        </CardContent>
      </Card>
    );
  }

  return (
    <SectionCard section={section}>
      <SectionBody body={section.body} />
    </SectionCard>
  );
}

function SectionBody({ body }: { body: string }) {
  const trimmed = body.trim();
  if (!trimmed) {
    return <p className="text-sm text-ink-500">No content for this section.</p>;
  }
  return <ReportMarkdown markdown={trimmed} />;
}

function SectionCard({
  section,
  accent,
  children,
}: {
  section: ReportSection;
  accent?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Card
      className={cn(
        "overflow-visible border-border-soft bg-surface-0 text-ink-900 shadow-editorial-1",
        accent && "ring-1 ring-market-green/25",
      )}
    >
      <CardHeader>
        <CardTitle className="font-display text-lg text-ink-900">
          {section.title}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-ink-900">{children}</CardContent>
    </Card>
  );
}
