import { notFound } from "next/navigation";

import { BackendUnavailable } from "@/components/backend-unavailable";
import { ReportView } from "@/components/report-view";
import { RunHeader } from "@/components/run-header";
import { SectionNav } from "@/components/section-nav";
import { getRun } from "@/lib/api";
import { splitSections } from "@/lib/report";
import { ApiError } from "@/lib/types";

interface RunPageProps {
  params: Promise<{ date: string }>;
}

export default async function RunPage({ params }: RunPageProps) {
  const { date } = await params;

  let run;
  try {
    run = await getRun(date);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    return <BackendUnavailable />;
  }

  const { sections } = splitSections(run.report_markdown);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-8">
      <RunHeader state={run.daily_state} reportMarkdown={run.report_markdown} />
      <div className="grid gap-8 lg:grid-cols-[200px_minmax(0,1fr)]">
        <SectionNav sections={sections} />
        <div className="min-w-0">
          <ReportView markdown={run.report_markdown} />
        </div>
      </div>
    </div>
  );
}

export async function generateMetadata({ params }: RunPageProps) {
  const { date } = await params;
  return {
    title: `${date} · SPX Analyst`,
  };
}
