import { BackendUnavailable } from "@/components/backend-unavailable";
import { ArchiveGrid } from "@/components/archive/archive-grid";
import { listRuns } from "@/lib/api";

export const metadata = {
  title: "Archive · SPX Analyst",
};

export default async function ArchivePage() {
  let runs;
  try {
    runs = await listRuns();
  } catch {
    return <BackendUnavailable />;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="font-display text-3xl font-semibold text-ink-900 sm:text-4xl">Archive</h1>
        <p className="mt-2 text-base text-ink-500">
          {runs.length === 0
            ? "No archived runs yet."
            : `${runs.length} archived ${runs.length === 1 ? "report" : "reports"}, newest first.`}
        </p>
      </header>

      {runs.length > 0 ? (
        <ArchiveGrid runs={runs} />
      ) : (
        <p className="text-sm text-ink-500">
          Run the analysis engine or seed dev fixtures into{" "}
          <code className="rounded bg-surface-1 px-1">memory/</code>.
        </p>
      )}
    </div>
  );
}
