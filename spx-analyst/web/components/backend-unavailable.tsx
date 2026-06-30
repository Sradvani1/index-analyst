"use client";

interface BackendUnavailableProps {
  onRetry?: () => void;
}

export function BackendUnavailable({ onRetry }: BackendUnavailableProps) {
  const command = "uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload";

  return (
    <div className="mx-auto flex max-w-lg flex-1 flex-col items-center justify-center gap-4 px-4 py-16 text-center">
      <h1 className="font-display text-xl font-semibold text-ink-900">Backend unavailable</h1>
      <p className="text-sm text-ink-500">
        Start the FastAPI server on port 8000 from the{" "}
        <code className="rounded bg-surface-1 px-1 py-0.5">spx-analyst</code> directory, then
        refresh.
      </p>
      <div className="w-full rounded-lg border border-border-soft bg-surface-0 p-3 text-left">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Command</p>
        <code className="mt-2 block break-all text-sm text-ink-900">{command}</code>
        <button
          type="button"
          onClick={() => void navigator.clipboard.writeText(command)}
          className="mt-3 text-sm font-medium text-market-green hover:text-market-green-hover"
        >
          Copy command
        </button>
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg bg-market-green px-4 py-2 text-sm font-semibold text-white hover:bg-market-green-hover"
        >
          Retry
        </button>
      ) : (
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded-lg bg-market-green px-4 py-2 text-sm font-semibold text-white hover:bg-market-green-hover"
        >
          Retry
        </button>
      )}
    </div>
  );
}
