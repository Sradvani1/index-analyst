import { notFound } from "next/navigation";

import { BackendUnavailable } from "@/components/backend-unavailable";
import { ReportView } from "@/components/report-view";
import { getRun } from "@/lib/api";
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

  return (
    <ReportView markdown={run.report_markdown} dailyState={run.daily_state} />
  );
}

export async function generateMetadata({ params }: RunPageProps) {
  const { date } = await params;
  return {
    title: `${date} · SPX Analyst`,
  };
}
