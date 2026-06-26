export default function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
      <h1 className="font-display text-3xl font-semibold text-ink-900">About</h1>
      <p className="mt-4 text-[19px] leading-[1.72] text-ink-700">
        SPX Analyst is a publication-style archive for daily S&amp;P 500 tactical analysis. Each
        report is assembled by the analysis engine from validated structured state and archived
        markdown — the viewer displays canonical artifacts only and does not recompute market
        outputs.
      </p>
    </div>
  );
}
