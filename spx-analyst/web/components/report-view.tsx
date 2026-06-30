import { ReportArticle } from "@/components/report/report-article";
import type { DailyState } from "@/lib/types";

interface ReportViewProps {
  markdown: string;
  dailyState: DailyState;
}

export function ReportView({ markdown, dailyState }: ReportViewProps) {
  return <ReportArticle markdown={markdown} dailyState={dailyState} />;
}
