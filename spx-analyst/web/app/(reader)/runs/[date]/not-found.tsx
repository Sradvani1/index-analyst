import Link from "next/link";

export default function RunNotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
      <h1 className="text-xl font-semibold">Run not found</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        That date is not in the canonical memory archive.
      </p>
      <Link href="/" className="text-sm font-medium underline underline-offset-4">
        Back to archive
      </Link>
    </div>
  );
}
