import { cn } from "@/lib/utils";
import { TONE_DOT, toneFor } from "@/lib/report";
import type { DecisionMatrix as StateMatrix } from "@/lib/types";

interface DecisionMatrixProps {
  matrix: StateMatrix;
}

const HEADERS = ["Signal Layer", "Current Reading", "Signal"];

export function DecisionMatrix({ matrix }: DecisionMatrixProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b text-left">
            {HEADERS.map((h) => (
              <th
                key={h}
                className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.rows.map((row, ri) => {
            const isAction = /recommended action/i.test(row.signal_layer);
            const tone = toneFor(row.signal);
            return (
              <tr
                key={ri}
                className={cn(
                  "border-b align-top",
                  isAction
                    ? "bg-muted/60 font-semibold"
                    : ri % 2 === 1
                      ? "bg-muted/20"
                      : undefined,
                )}
              >
                <td className="px-3 py-2 leading-snug">{row.signal_layer}</td>
                <td className="px-3 py-2 leading-snug">{row.current_reading}</td>
                <td className="px-3 py-2 leading-snug">
                  <span className="inline-flex items-start gap-2">
                    <span
                      className={cn(
                        "mt-1.5 size-2 shrink-0 rounded-full",
                        TONE_DOT[tone],
                      )}
                      aria-hidden
                    />
                    <span>{row.signal}</span>
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
