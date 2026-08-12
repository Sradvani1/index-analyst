import { BackendUnavailable } from "@/components/backend-unavailable";
import { ReportMarkdown } from "@/components/report-markdown";
import { getFramework } from "@/lib/api";

export const metadata = {
  title: "Framework · SPX Analyst",
};

interface FrameworkHeading {
  id: string;
  label: string;
}

function frameworkHeadings(markdown: string): FrameworkHeading[] {
  return markdown
    .split("\n")
    .flatMap((line) => {
      const match = line.match(/^##\s+(.+?)\s*$/);
      if (!match) {
        return [];
      }
      const label = match[1].trim();
      return [{ id: slugify(label), label }];
    });
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default async function FrameworkPage() {
  let documents;
  try {
    documents = await getFramework();
  } catch {
    return <BackendUnavailable />;
  }

  const headings = frameworkHeadings(documents.framework_markdown);

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="max-w-3xl">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Methodology</p>
        <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-ink-900 sm:text-5xl">
          SPX Analysis Framework
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-ink-700">
          The complete methodology and Claude role instructions used to produce each daily report.
          This page publishes the source documents directly, so the public explanation stays aligned
          with the analysis engine.
        </p>
        <p className="mt-4 text-sm leading-relaxed text-ink-500">
          Educational market research only. This is not personalized investment advice, a guarantee,
          or a recommendation to buy or sell securities.
        </p>
      </header>

      <div className="mt-10 grid gap-10 lg:grid-cols-[15rem_minmax(0,1fr)] lg:items-start">
        <aside className="lg:sticky lg:top-24">
          <nav aria-label="Framework contents" className="rounded-[14px] border border-border-soft bg-surface-0 p-4 shadow-editorial-1">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Contents</p>
            <ul className="mt-3 space-y-1">
              {headings.map((heading) => (
                <li key={heading.id}>
                  <a
                    href={`#${heading.id}`}
                    className="block rounded-lg px-2 py-2 text-sm leading-snug text-ink-700 hover:bg-surface-1 hover:text-ink-900"
                  >
                    {heading.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <main className="min-w-0 max-w-[72ch]">
          <section aria-labelledby="framework-document-title">
            <h2 id="framework-document-title" className="sr-only">
              SPX Daily Analysis Framework
            </h2>
            <ReportMarkdown markdown={documents.framework_markdown} variant="article" />
          </section>

          <section className="mt-16 border-t border-border-soft pt-10" aria-labelledby="role-block-title">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Execution instructions</p>
            <h2 id="role-block-title" className="mt-2 font-display text-3xl font-semibold text-ink-900">
              Claude Role Instructions
            </h2>
            <p className="mt-3 text-base leading-relaxed text-ink-700">
              This role block defines how Claude applies the framework and explains the prepared
              evidence. It does not replace the framework or independently set the daily posture.
            </p>
            <div className="mt-6">
              <ReportMarkdown markdown={documents.role_block_markdown} variant="article" />
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
