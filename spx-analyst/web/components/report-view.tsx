import { ReportTabs } from "@/components/report-tabs";
import { ReportMarkdown } from "@/components/report-markdown";
import { Card, CardContent } from "@/components/ui/card";
import { viewerSections } from "@/lib/report";
import type { DailyState } from "@/lib/types";

interface ReportViewProps {
  markdown: string;
  dailyState?: DailyState;
}

export function ReportView({ markdown, dailyState }: ReportViewProps) {
  const sections = viewerSections(markdown);

  if (sections.length === 0) {
    return (
      <Card>
        <CardContent>
          <ReportMarkdown markdown={markdown} />
        </CardContent>
      </Card>
    );
  }

  return <ReportTabs sections={sections} dailyState={dailyState} />;
}
