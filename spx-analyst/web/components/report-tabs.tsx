"use client";

import { useState } from "react";

import { DecisionMatrix } from "@/components/decision-matrix";
import { ReportMarkdown } from "@/components/report-markdown";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { sectionTabLabel, type ReportSection } from "@/lib/report";
import type { DailyState } from "@/lib/types";

interface ReportTabsProps {
  sections: ReportSection[];
  dailyState?: DailyState;
}

function isEvidenceSection(title: string): boolean {
  return /evidence (and tensions|reconciliation)/i.test(title);
}

function isDecisionMatrix(title: string): boolean {
  return /decision matrix/i.test(title);
}

export function ReportTabs({ sections, dailyState }: ReportTabsProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const active = sections[activeIndex] ?? sections[0];

  if (!active) {
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
                className={cn(
                  "rounded-lg border px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors",
                  selected
                    ? "border-primary/30 bg-primary text-primary-foreground"
                    : "border-transparent bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {sectionTabLabel(section.title)}
              </button>
            );
          })}
        </div>
      </div>

      <SectionPanel
        key={active.id}
        section={active}
        dailyState={dailyState}
      />
    </div>
  );
}

function SectionPanel({
  section,
  dailyState,
}: {
  section: ReportSection;
  dailyState?: DailyState;
}) {
  return (
    <div
      role="tabpanel"
      id={`panel-${section.id}`}
      aria-labelledby={`tab-${section.id}`}
    >
      <SectionContent section={section} dailyState={dailyState} />
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
  if (isDecisionMatrix(section.title)) {
    return (
      <SectionCard section={section} accent>
        {dailyState?.decision_matrix ? (
          <DecisionMatrix matrix={dailyState.decision_matrix} />
        ) : (
          <ReportMarkdown markdown={section.body} />
        )}
      </SectionCard>
    );
  }

  if (isEvidenceSection(section.title)) {
    return (
      <Card className="bg-amber-50 ring-amber-200 dark:bg-amber-950/40 dark:ring-amber-900">
        <CardHeader>
          <CardTitle className="text-amber-900 dark:text-amber-100">
            {section.title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ReportMarkdown markdown={section.body} />
        </CardContent>
      </Card>
    );
  }

  return (
    <SectionCard section={section}>
      <ReportMarkdown markdown={section.body} />
    </SectionCard>
  );
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
    <Card className={cn(accent && "ring-primary/30")}>
      <CardHeader>
        <CardTitle className="text-lg">{section.title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
