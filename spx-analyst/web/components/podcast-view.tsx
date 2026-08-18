import { ReportMarkdown } from "@/components/report-markdown";

interface PodcastViewProps {
  date: string;
  script: string;
  audioAvailable: boolean;
}

export function PodcastView({ date, script, audioAvailable }: PodcastViewProps) {
  return (
    <section className="border-t border-border-soft bg-paper-100 px-4 py-12">
      <div className="mx-auto max-w-[70ch]">
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-market-green">
            Daily podcast
          </p>
          <h2 className="mt-2 font-display text-3xl font-semibold text-ink-900">
            Three-minute brief
          </h2>
        </div>
        <p className="mb-8 text-sm leading-relaxed text-ink-500">
          Listen to the audio, then upload the MP3 and script to Substack to publish
          the episode.
        </p>
        {audioAvailable ? (
          <div className="mb-8">
            <audio
              controls
              preload="metadata"
              className="w-full"
              src={`/api/runs/${date}/podcast.mp3`}
            />
          </div>
        ) : null}
        <div className="rounded-[14px] border border-border-soft bg-surface-0 p-6 shadow-editorial-1 sm:p-8">
          <ReportMarkdown markdown={script} variant="article" />
        </div>
      </div>
    </section>
  );
}