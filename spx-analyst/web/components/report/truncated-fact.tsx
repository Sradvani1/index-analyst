import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface TruncatedFactProps {
  label: string;
  value: string;
}

export function TruncatedFact({ label, value }: TruncatedFactProps) {
  return (
    <div className="rounded-lg border border-border-soft bg-surface-0 p-3">
      <p className="text-[0.65rem] font-medium uppercase tracking-wide text-ink-500">
        {label}
      </p>
      <Tooltip>
        <TooltipTrigger
          render={
            <p className="mt-1 line-clamp-2 cursor-default text-sm leading-snug text-ink-900" />
          }
        >
          {value}
        </TooltipTrigger>
        <TooltipContent className="max-w-sm text-left">{value}</TooltipContent>
      </Tooltip>
    </div>
  );
}
