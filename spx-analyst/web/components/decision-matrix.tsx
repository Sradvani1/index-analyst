import { cn } from "@/lib/utils";
import { TONE_DOT, type DecisionMatrix as Matrix } from "@/lib/report";

interface DecisionMatrixProps {
  matrix: Matrix;
}

export function DecisionMatrix({ matrix }: DecisionMatrixProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b text-left">
            {matrix.headers.map((h, i) => (
              <th
                key={i}
                className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.rows.map((row, ri) => (
            <tr
              key={ri}
              className={cn(
                "border-b align-top",
                row.isAction
                  ? "bg-muted/60 font-semibold"
                  : ri % 2 === 1
                    ? "bg-muted/20"
                    : undefined,
              )}
            >
              {row.cells.map((cell, ci) => {
                const isLast = ci === row.cells.length - 1;
                return (
                  <td key={ci} className="px-3 py-2 leading-snug">
                    {isLast && row.cells.length > 1 ? (
                      <span className="inline-flex items-start gap-2">
                        <span
                          className={cn(
                            "mt-1.5 size-2 shrink-0 rounded-full",
                            TONE_DOT[row.tone],
                          )}
                          aria-hidden
                        />
                        <span>{cell}</span>
                      </span>
                    ) : (
                      cell
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
