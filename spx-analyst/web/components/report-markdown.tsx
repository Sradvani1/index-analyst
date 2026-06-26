import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

interface ReportMarkdownProps {
  markdown: string;
}

const components: Components = {
  p: ({ children }) => (
    <p className="mb-4 text-[19px] leading-[1.72] text-ink-900 last:mb-0">{children}</p>
  ),
  li: ({ children }) => (
    <li className="text-[19px] leading-[1.72] text-ink-900">{children}</li>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 font-display text-lg font-semibold text-ink-900">{children}</h3>
  ),
  strong: ({ children }) => <strong className="font-semibold text-ink-900">{children}</strong>,
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto rounded-lg border border-border-soft">
      <table className="w-full border-collapse text-sm text-ink-900">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="border-b border-border-soft bg-surface-1 text-left">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
      {children}
    </th>
  ),
  tr: ({ children }) => <tr className="border-b border-border-soft align-top">{children}</tr>,
  td: ({ children }) => (
    <td className="px-3 py-2 leading-relaxed text-ink-900">{children}</td>
  ),
  a: ({ children, href }) => (
    <a
      href={href}
      className="font-medium text-signal-blue underline underline-offset-4 hover:text-ink-900"
      target="_blank"
      rel="noreferrer"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-surface-1 px-1.5 py-0.5 text-[0.85em] text-ink-700">
      {children}
    </code>
  ),
};

export function ReportMarkdown({ markdown }: ReportMarkdownProps) {
  return (
    <div className="max-w-[70ch] text-ink-900">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
