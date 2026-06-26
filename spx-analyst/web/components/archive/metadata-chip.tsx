import { cn } from "@/lib/utils";
import { TONE_SURFACE, toneFor, type Tone } from "@/lib/report";

interface MetadataChipProps {
  label: string;
  tone?: Tone;
  className?: string;
}

export function MetadataChip({ label, tone = "neutral", className }: MetadataChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-lg px-2.5 py-1 text-xs font-semibold ring-1 ring-inset",
        TONE_SURFACE[tone],
        className,
      )}
    >
      {label}
    </span>
  );
}

interface MetadataChipFromTextProps {
  text: string;
  tone?: Tone;
  className?: string;
}

export function MetadataChipFromText({ text, tone, className }: MetadataChipFromTextProps) {
  return <MetadataChip label={text} tone={tone ?? toneFor(text)} className={className} />;
}
