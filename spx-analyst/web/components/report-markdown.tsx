import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

interface ReportMarkdownProps {
  markdown: string;
}

const components: Components = {
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="border-b text-left">{children}</thead>,
  th: ({ children }) => (
    <th className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </th>
  ),
  tr: ({ children }) => <tr className="border-b align-top">{children}</tr>,
  td: ({ children }) => (
    <td className="px-3 py-2 leading-snug">{children}</td>
  ),
  a: ({ children, href }) => (
    <a
      href={href}
      className="font-medium text-primary underline underline-offset-4"
      target="_blank"
      rel="noreferrer"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-muted px-1.5 py-0.5 text-[0.85em]">
      {children}
    </code>
  ),
};

export function ReportMarkdown({ markdown }: ReportMarkdownProps) {
  return (
    <div className="prose prose-neutral max-w-none dark:prose-invert prose-headings:font-semibold prose-h3:text-base prose-p:leading-relaxed prose-li:leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
