import { ReportTabs } from "@/components/report-tabs";
import { ReportMarkdown } from "@/components/report-markdown";
import { Card, CardContent } from "@/components/ui/card";
import { viewerSections } from "@/lib/report";
import type { DailyState } from "@/lib/types";

interface ReportViewProps {
  markdown: string;
  dailyState: DailyState;
}

export function ReportView({ markdown, dailyState }: ReportViewProps) {
  const sections = viewerSections(markdown);

  if (sections.length === 0) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-6">
        <Card className="border-border-soft bg-surface-0 shadow-editorial-1">
          <CardContent>
            <ReportMarkdown markdown={markdown} />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-6">
      <ReportTabs sections={sections} dailyState={dailyState} />
    </div>
  );
}
