import { BackendUnavailable } from "@/components/backend-unavailable";
import { LeadStory } from "@/components/home/lead-story";
import { RecentStream } from "@/components/home/recent-stream";
import { listRuns } from "@/lib/api";

export default async function HomePage() {
  let runs;
  try {
    runs = await listRuns();
  } catch {
    return <BackendUnavailable />;
  }

  if (runs.length === 0) {
    return (
      <div className="mx-auto flex max-w-7xl flex-1 flex-col items-center justify-center gap-3 px-4 py-16 text-center">
        <h1 className="font-display text-xl font-semibold text-ink-900">No archived runs</h1>
        <p className="max-w-md text-sm text-ink-500">
          Run the analysis engine to populate{" "}
          <code className="rounded bg-surface-1 px-1 py-0.5">memory/daily_reports</code> and{" "}
          <code className="rounded bg-surface-1 px-1 py-0.5">memory/daily_states</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <div className="flex flex-col gap-10">
        <LeadStory run={runs[0]} />
        <RecentStream runs={runs.slice(1)} />
      </div>
    </div>
  );
}
