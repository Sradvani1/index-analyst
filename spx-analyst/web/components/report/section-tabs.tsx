"use client";

import { useState } from "react";

import { SectionBlock } from "@/components/report/section-block";
import { cn } from "@/lib/utils";
import { sectionTabLabel, type ReportSection } from "@/lib/report";
import type { DailyState } from "@/lib/types";

interface SectionTabsProps {
  sections: ReportSection[];
  dailyState: DailyState;
}

function initialTabIndex(sections: ReportSection[]): number {
  if (typeof window !== "undefined") {
    const hash = window.location.hash.replace(/^#/, "");
    const fromHash = sections.findIndex((section) => section.id === hash);
    if (fromHash >= 0) {
      return fromHash;
    }
  }
  const posture = sections.findIndex((section) => /today's posture/i.test(section.title));
  return posture >= 0 ? posture : 0;
}

/** One section visible at a time — tab pills swap the active panel (no long-page scroll). */
export function SectionTabs({ sections, dailyState }: SectionTabsProps) {
  const [activeIndex, setActiveIndex] = useState(() => initialTabIndex(sections));

  if (sections.length === 0) {
    return null;
  }

  const active = sections[activeIndex] ?? sections[0];

  function selectTab(index: number) {
    setActiveIndex(index);
    window.history.replaceState(null, "", `#${sections[index].id}`);
  }

  return (
    <div className="mt-8 flex min-w-0 flex-col gap-5">
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
                onClick={() => selectTab(index)}
                className={cn(
                  "min-h-11 rounded-lg border px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors",
                  selected
                    ? "border-market-green bg-market-green font-semibold text-white"
                    : "border-transparent bg-surface-1 text-ink-700 hover:border-border-soft hover:bg-paper-100 hover:text-ink-900",
                )}
              >
                {sectionTabLabel(section.title)}
              </button>
            );
          })}
        </div>
      </div>

      <div
        role="tabpanel"
        id={`panel-${active.id}`}
        aria-labelledby={`tab-${active.id}`}
        className="min-w-0"
      >
        <SectionBlock section={active} dailyState={dailyState} />
      </div>
    </div>
  );
}
