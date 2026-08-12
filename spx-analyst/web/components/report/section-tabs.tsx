"use client";

import { useEffect, useState, type KeyboardEvent } from "react";

import { SectionBlock } from "@/components/report/section-block";
import { cn } from "@/lib/utils";
import { sectionTabLabel, type ReportSection } from "@/lib/report";
import type { DailyState } from "@/lib/types";

interface SectionTabsProps {
  sections: ReportSection[];
  dailyState: DailyState;
}

function initialTabIndex(sections: ReportSection[]): number {
  const posture = sections.findIndex((section) => /today's posture/i.test(section.title));
  return posture >= 0 ? posture : 0;
}

/** One section visible at a time — tab pills swap the active panel (no long-page scroll). */
export function SectionTabs({ sections, dailyState }: SectionTabsProps) {
  const [activeIndex, setActiveIndex] = useState(() => initialTabIndex(sections));

  useEffect(() => {
    function syncFromHash() {
      const hash = window.location.hash.replace(/^#/, "");
      const index = sections.findIndex((section) => section.id === hash);
      if (index >= 0) {
        setActiveIndex(index);
      }
    }

    syncFromHash();
    window.addEventListener("popstate", syncFromHash);
    window.addEventListener("hashchange", syncFromHash);
    return () => {
      window.removeEventListener("popstate", syncFromHash);
      window.removeEventListener("hashchange", syncFromHash);
    };
  }, [sections]);

  if (sections.length === 0) {
    return null;
  }

  const active = sections[activeIndex] ?? sections[0];

  function selectTab(index: number) {
    const nextIndex = (index + sections.length) % sections.length;
    setActiveIndex(nextIndex);
    window.history.pushState(null, "", `#${sections[nextIndex].id}`);
    document.getElementById(`tab-${sections[nextIndex].id}`)?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "nearest",
    });
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") {
      nextIndex = (index + 1) % sections.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (index - 1 + sections.length) % sections.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = sections.length - 1;
    }

    if (nextIndex === null) {
      return;
    }

    event.preventDefault();
    selectTab(nextIndex);
    document.getElementById(`tab-${sections[nextIndex].id}`)?.focus();
  }

  return (
    <div className="mt-8 flex min-w-0 flex-col gap-5">
      <div className="sticky top-16 z-20 -mx-1 overflow-x-auto bg-paper-50/95 px-1 pb-1 pt-1 backdrop-blur-sm">
        <div
          role="tablist"
          aria-label="Report sections"
          aria-orientation="horizontal"
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
                onKeyDown={(event) => handleKeyDown(event, index)}
                className={cn(
                  "min-h-11 rounded-lg border px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-market-green/40 focus-visible:outline-none",
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

      <nav className="flex items-center justify-between gap-3 border-t border-border-soft pt-4" aria-label="Report section navigation">
        <button
          type="button"
          onClick={() => selectTab(activeIndex - 1 < 0 ? sections.length - 1 : activeIndex - 1)}
          className="min-h-11 rounded-lg border border-border-soft px-3 text-sm font-medium text-ink-700 transition-colors hover:bg-surface-1 hover:text-ink-900 focus-visible:ring-2 focus-visible:ring-market-green/40 focus-visible:outline-none"
        >
          Previous
        </button>
        <span className="text-xs tabular-nums text-ink-500">
          {activeIndex + 1} of {sections.length}
        </span>
        <button
          type="button"
          onClick={() => selectTab((activeIndex + 1) % sections.length)}
          className="min-h-11 rounded-lg border border-border-soft px-3 text-sm font-medium text-ink-700 transition-colors hover:bg-surface-1 hover:text-ink-900 focus-visible:ring-2 focus-visible:ring-market-green/40 focus-visible:outline-none"
        >
          Next
        </button>
      </nav>
    </div>
  );
}
