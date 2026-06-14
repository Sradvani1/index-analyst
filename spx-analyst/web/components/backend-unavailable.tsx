export function BackendUnavailable() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
      <h1 className="text-xl font-semibold">Backend unavailable</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        Start the FastAPI server on port 8000, then refresh this page.
      </p>
    </div>
  );
}
