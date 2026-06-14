import type { ReportSection } from "@/lib/report";

interface SectionNavProps {
  sections: ReportSection[];
}

export function SectionNav({ sections }: SectionNavProps) {
  if (sections.length === 0) {
    return null;
  }

  return (
    <nav className="sticky top-6 hidden lg:block">
      <p className="mb-2 px-2 text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">
        Sections
      </p>
      <ul className="flex flex-col gap-0.5 text-sm">
        {sections.map((section) => (
          <li key={section.id}>
            <a
              href={`#${section.id}`}
              className="block rounded-md px-2 py-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {section.title}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
