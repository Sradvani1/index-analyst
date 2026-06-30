import { RunHeader } from "@/components/run-header";
import { SectionTabs } from "@/components/report/section-tabs";
import { ReportMarkdown } from "@/components/report-markdown";
import { viewerSections } from "@/lib/report";
import type { DailyState } from "@/lib/types";

interface ReportArticleProps {
  markdown: string;
  dailyState: DailyState;
}

export function ReportArticle({ markdown, dailyState }: ReportArticleProps) {
  const sections = viewerSections(markdown);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <article className="mx-auto min-w-0 max-w-[70ch]">
        <RunHeader state={dailyState} reportMarkdown={markdown} />

        {sections.length === 0 ? (
          <div className="mt-8">
            <ReportMarkdown markdown={markdown} variant="article" />
          </div>
        ) : (
          <SectionTabs sections={sections} dailyState={dailyState} />
        )}
      </article>
    </div>
  );
}
