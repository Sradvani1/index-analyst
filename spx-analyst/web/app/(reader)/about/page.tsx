export default function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
      <h1 className="font-display text-3xl font-semibold text-ink-900 sm:text-4xl">
        About SPX Analyst
      </h1>
      <p className="mt-4 text-lg leading-relaxed text-ink-700">
        A daily read on the S&amp;P 500 market structure, built for investors who
        want a disciplined tactical posture, not a hot take.
      </p>

      <section className="mt-10">
        <h2 className="font-display text-xl font-semibold text-ink-900">What you get</h2>
        <p className="mt-3 text-[19px] leading-[1.72] text-ink-700">
          Each trading day, one archived report: where the index closed, the current structural
          regime, the recommended posture for the next session, and the evidence behind it. Reports
          use the same sections every time: posture, regime, price and trend, technicals and
          sentiment, valuation, risk, tactical levels, evidence, and a decision matrix.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="font-display text-xl font-semibold text-ink-900">
          What every run is trying to answer
        </h2>
        <p className="mt-3 text-[19px] leading-[1.72] text-ink-700">
          The analysis is governed by a fixed daily framework. Each run works through the same
          questions in the same order:
        </p>
        <ol className="mt-4 list-decimal space-y-2 pl-5 text-[19px] leading-[1.72] text-ink-700">
          <li>What is the current structural market regime?</li>
          <li>Is the market extended, balanced, or under pressure?</li>
          <li>Is valuation supportive, neutral, or restrictive?</li>
          <li>Does the evidence support action, patience, or defense?</li>
          <li>What is the exact tactical posture for the next session?</li>
        </ol>
        <p className="mt-4 text-[19px] leading-[1.72] text-ink-700">
          The framework is not designed to force trades. Its job is to organize evidence, weigh
          signal quality, and translate structure into a clear stance, including when the right
          answer is to wait.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="font-display text-xl font-semibold text-ink-900">How it works</h2>
        <p className="mt-3 text-[19px] leading-[1.72] text-ink-700">
          Analysis runs in layers, always in sequence. First, a structural regime classification
          sets the master context: whether the backdrop reads as early bull, mid bull, late bull /
          topping, or bear market, using extension, equity risk premium, credit, and breadth
          together, not any single indicator in isolation.
        </p>
        <p className="mt-4 text-[19px] leading-[1.72] text-ink-700">
          On top of that foundation, four evidence layers are evaluated every run:
        </p>
        <ul className="mt-4 list-disc space-y-2 pl-5 text-[19px] leading-[1.72] text-ink-700">
          <li>
            <strong className="font-semibold text-ink-900">Fundamental valuation:</strong> forward
            earnings, yields, and the equity risk premium versus bonds
          </li>
          <li>
            <strong className="font-semibold text-ink-900">Technical structure:</strong> trend,
            extension, support and resistance, momentum, and where the close finished in the day&apos;s
            range
          </li>
          <li>
            <strong className="font-semibold text-ink-900">Sentiment and leverage:</strong>{" "}
            psychology, breadth participation, credit spreads, and volatility regime
          </li>
          <li>
            <strong className="font-semibold text-ink-900">Monte Carlo probability:</strong>{" "}
            Brownian drift-based, regime-aware estimates of near-term upside vs downside paths,
            with explicit thresholds for when an edge is actionable
          </li>
        </ul>
        <p className="mt-4 text-[19px] leading-[1.72] text-ink-700">
          Those layers feed a seven-step daily workflow, from price recentering through valuation,
          leverage, Monte Carlo, tactical levels, and a written synthesis. Each run closes with an
          updated decision matrix that lines up each signal layer with a current reading and a
          verdict. The recommended action at the bottom is the distilled output of that table, not
          a separate opinion.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="font-display text-xl font-semibold text-ink-900">Disciplined process</h2>
        <ul className="mt-4 list-disc space-y-2 pl-5 text-[19px] leading-[1.72] text-ink-700">
          <li>
            <strong className="font-semibold text-ink-900">Repeatable process.</strong> Same
            framework, same section order, same matrix every day, built for continuity across
            sessions.
          </li>
          <li>
            <strong className="font-semibold text-ink-900">Evidence before action.</strong> Signals
            need alignment across independent layers; mixed or ambiguous evidence defaults to
            patience, not a forced call.
          </li>
          <li>
            <strong className="font-semibold text-ink-900">Structure over story.</strong> Regime,
            valuation bucket, and recommended action come from validated structured state; the
            narrative explains the reasoning in plain language.
          </li>
          <li>
            <strong className="font-semibold text-ink-900">Honest about tension.</strong> When
            bullish price action conflicts with breadth, credit, or valuation, the report names
            that conflict. It does not smooth it over.
          </li>
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="font-display text-xl font-semibold text-ink-900">What this is not</h2>
        <p className="mt-3 text-[19px] leading-[1.72] text-ink-700">
          SPX Analyst is tactical index structure analysis for the S&amp;P 500, not stock picking,
          not portfolio management, and not personalized investment advice. The publication archive
          displays each day&apos;s canonical report as produced by the engine. The viewer does not
          recompute indicators or rewrite conclusions in the browser.
        </p>
      </section>
    </div>
  );
}
