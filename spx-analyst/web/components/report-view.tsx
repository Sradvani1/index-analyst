import { DecisionMatrix } from "@/components/decision-matrix";
import { ReportMarkdown } from "@/components/report-markdown";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  parseDecisionMatrix,
  splitSections,
  type ReportSection,
} from "@/lib/report";

interface ReportViewProps {
  markdown: string;
}

function isEvidenceReconciliation(title: string): boolean {
  return /evidence reconciliation/i.test(title);
}

function isDecisionMatrix(title: string): boolean {
  return /decision matrix/i.test(title);
}

export function ReportView({ markdown }: ReportViewProps) {
  const { sections } = splitSections(markdown);

  if (sections.length === 0) {
    return (
      <Card>
        <CardContent>
          <ReportMarkdown markdown={markdown} />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {sections.map((section) => (
        <Section key={section.id} section={section} />
      ))}
    </div>
  );
}

function Section({ section }: { section: ReportSection }) {
  if (isDecisionMatrix(section.title)) {
    const matrix = parseDecisionMatrix(section.body);
    return (
      <SectionCard section={section} accent>
        {matrix ? (
          <DecisionMatrix matrix={matrix} />
        ) : (
          <ReportMarkdown markdown={section.body} />
        )}
      </SectionCard>
    );
  }

  if (isEvidenceReconciliation(section.title)) {
    return (
      <Card
        id={section.id}
        className="scroll-mt-6 bg-amber-50 ring-amber-200 dark:bg-amber-950/40 dark:ring-amber-900"
      >
        <CardHeader>
          <CardTitle className="text-amber-900 dark:text-amber-100">
            {section.title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ReportMarkdown markdown={section.body} />
        </CardContent>
      </Card>
    );
  }

  return (
    <SectionCard section={section}>
      <ReportMarkdown markdown={section.body} />
    </SectionCard>
  );
}

function SectionCard({
  section,
  accent,
  children,
}: {
  section: ReportSection;
  accent?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Card id={section.id} className={cn("scroll-mt-6", accent && "ring-primary/30")}>
      <CardHeader>
        <CardTitle className="text-lg">{section.title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
