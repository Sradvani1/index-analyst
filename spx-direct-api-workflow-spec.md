# SPX / SCHK Direct API Workflow — Technical Scope, Specification, and Phase 1 Implementation Package

## Purpose

This document specifies a Phase 1 direct-API analysis engine for the user's S&P 500 / SCHK tactical trading workflow. The engine is intended to replace the current recurring Space-based process that is constrained by upload limits, while preserving the methodology, daily multimodal analysis pattern, and future ability to support an interactive chatbot-style discussion layer on top of the same analysis core [cite:79][cite:81].

The build target for Phase 1 is a headless, testable, file-driven analysis system that can ingest a daily chart pack, load the standing methodology, fetch external context, reason over recent historical outputs, and emit both a full human-readable markdown report and a structured JSON memory object for future continuity [cite:183][cite:143][cite:167].

The design goal is to make Phase 1 production-grade enough that Phase 2 can add a private web application and a conversational agent without rewriting the core orchestration, schemas, or memory architecture [cite:187][cite:188][cite:192].

## Product goals

### Phase 1 goals

- Accept a dated folder of approximately 15 charts plus a manifest file for a given trading day [cite:40][cite:81].
- Load the S&P 500 / SCHK methodology markdown as the governing framework and preserve its required workflow order and non-negotiable rules [cite:79].
- Fetch a small set of daily external inputs such as VIX, Treasury yield, sentiment, credit context, and selected market headlines, then freeze those inputs to disk for reproducibility [cite:79].
- Read recent historical memory so the model can reason about short-term trend development across several days instead of treating each day as isolated [cite:141][cite:144][cite:156].
- Generate two first-class outputs: a full markdown report for human review and a structured JSON state object for machine memory and future chat continuity [cite:183][cite:107][cite:167].
- Be runnable from the command line, testable locally, and schedulable later via cron or another automation layer [cite:186].

### Phase 2 goals

- Add a private web interface for uploading charts, running the engine, browsing prior analyses, and viewing state history [cite:187][cite:192].
- Add an interactive conversational layer so the user can discuss the day’s analysis, challenge assumptions, compare days, and ask follow-up questions using the same stored memory and analysis artifacts rather than a separate chat-only memory system [cite:188][cite:156].

## Non-goals for Phase 1

- No polished browser UI in Phase 1.
- No multi-user authentication or permissions model in Phase 1.
- No attempt to fully automate chart creation or brokerage integration in Phase 1.
- No replacement of the methodology with an agent that invents its own process; the methodology remains the source of truth [cite:79].

## Guiding architecture principles

1. **Core engine first, UI later.** The direct API engine is the durable backbone; the future chat app is a presentation and interaction layer over the same services and files [cite:187][cite:188].
2. **Structured memory over raw transcript memory.** The system stores compact state and narrative summaries outside the live context window rather than relying on infinitely growing chat history [cite:143][cite:174][cite:167].
3. **Full report + compressed state.** Every run emits a rich markdown report for the human and a concise JSON state object for the machine [cite:183][cite:167].
4. **Reproducibility.** Every daily run should be reconstructable from saved inputs, prompt payloads, external context, outputs, and validation logs.
5. **Stable schemas.** Phase 1 should establish durable contracts for manifests, external context, daily state, and chat context so Phase 2 can reuse them without migration pain [cite:183][cite:113].
6. **Methodology fidelity over creativity.** The engine must execute the methodology in order and preserve its hard constraints, including elevated VIX handling, Monte Carlo threshold behavior, no forced signals, and mandatory decision matrix output [cite:79].

## Recommended technology stack

### Phase 1

- **Language:** Python 3.11+
- **Model provider:** Anthropic Claude API
- **Primary model:** Claude Opus for final analysis and report generation [cite:41][cite:125]
- **Optional later helper model:** a cheaper Claude or Gemini model for lower-risk preprocessing tasks if needed [cite:121][cite:126]
- **Validation:** Pydantic
- **Storage:** local filesystem first
- **Configuration:** `.env` + typed config module
- **CLI:** Typer or argparse
- **Testing:** pytest
- **Logging:** structured JSON logging plus text logs

### Phase 2

- **Web app:** Next.js
- **UI/chat SDK:** Vercel AI SDK for model-agnostic chat orchestration and future provider flexibility [cite:187][cite:192]
- **Backend options:** Python service behind API routes, or TypeScript orchestration that calls the same analysis service

## Repository structure

```text
spx-analyst/
  README.md
  .env.example
  requirements.txt
  pyproject.toml

  framework/
    SP500-SCHK-Trading-Methodology.md

  data/
    runs/
      2026-06-12/
        charts/
          01_spx_daily.png
          02_spx_weekly.png
          03_vix_daily.png
          04_breadth_daily.png
          05_breadth_weekly.png
          06_fear_greed.png
          07_put_call.png
          08_credit_spreads.png
          09_us10y.png
          10_schk_daily.png
          11_schk_weekly.png
          12_market_breadth_alt.png
          13_sector_leadership.png
          14_monte_carlo_input.png
          15_positioning_or_sentiment.png
        manifest.json
        external_context.json

  memory/
    daily_states/
      2026-06-09-state.json
      2026-06-10-state.json
      2026-06-11-state.json
    daily_reports/
      2026-06-09-analysis.md
      2026-06-10-analysis.md
      2026-06-11-analysis.md
    rolling/
      recent_summary.md
      recent_memory.json

  output/
    2026-06-12/
      2026-06-12-analysis.md
      2026-06-12-state.json
      request_snapshot.json
      response_raw.json
      run_log.json
      validation_report.json

  src/
    __init__.py
    config.py
    schemas.py
    files.py
    prompts.py
    external_data.py
    memory.py
    anthropic_client.py
    analysis_engine.py
    validation.py
    cli.py
    chat_context.py
    chat_service.py

  tests/
    test_schemas.py
    test_manifest_loading.py
    test_memory_rollup.py
    test_prompt_builder.py
    test_validation.py
```

This layout is intentionally file-centric so it works immediately in a script workflow while also functioning later as the persistence layer for a private web app and chat agent [cite:178][cite:188].

## Functional requirements

### FR-1 Daily run ingestion

The system shall accept a daily run directory keyed by trade date. Each run directory shall contain a `charts/` folder, a `manifest.json`, and an `external_context.json` file after fetch completion.

### FR-2 Framework loading

The system shall load the methodology markdown from `framework/SP500-SCHK-Trading-Methodology.md` and treat it as a first-class instruction source. The methodology defines the required layers, sequence, confirmation rules, risk gates, and mandatory ending decision matrix [cite:79].

### FR-3 Multi-image reasoning

The system shall send all chart images in a single multimodal request in a stable, manifest-controlled order so the model can reason across the whole evidence set jointly rather than as isolated per-image tasks [cite:40][cite:61].

### FR-4 Historical continuity

The system shall retrieve recent prior state files so the model can compare today against the last several sessions and identify regime persistence, signal transitions, and trend development [cite:141][cite:156].

### FR-5 External context

The system shall fetch and persist a bounded set of external daily market context fields and selected headlines so the analysis includes current information while remaining reproducible.

### FR-6 Structured output

The system shall validate a daily JSON output against a schema using structured-output generation where feasible to improve reliability and downstream reuse [cite:183][cite:113].

### FR-7 Human-readable report

The system shall write a markdown analysis report for the day that follows the methodology order and ends with the Updated Decision Matrix required by the methodology [cite:79].

### FR-8 Auditability

The system shall save raw request and response artifacts, validation results, and run logs for troubleshooting and reproducibility.

### FR-9 CLI operation

The system shall be invocable from a command line for local testing and future scheduling.

### FR-10 Future chat compatibility

The system shall expose outputs and memory in a way that a later conversational agent can load a day’s report and state plus recent historical memory and discuss them interactively without depending on the raw original request transcript [cite:188][cite:167].

## Non-functional requirements

- **Determinism:** use stable prompt templates, fixed manifest order, and schema validation.
- **Traceability:** persist run artifacts and validation logs.
- **Portability:** keep Phase 1 usable on a single machine with no cloud database requirement.
- **Extensibility:** allow later replacement of filesystem storage with Postgres, S3, or object storage.
- **Cost discipline:** enable prompt caching for the static framework and bounded memory context to control token costs [cite:89][cite:125].
- **Latency tolerance:** prioritize correctness and reproducibility over speed in Phase 1.

## Input contracts

### 1. Chart manifest schema

Example:

```json
{
  "date": "2026-06-12",
  "index_symbol": "SPX",
  "instrument_symbol": "SCHK",
  "close": 7450.25,
  "chart_count": 15,
  "charts": [
    {
      "order": 1,
      "file": "01_spx_daily.png",
      "label": "SPX daily price with RSI, MFI, Bollinger Bands",
      "category": "technical",
      "timeframe": "daily"
    },
    {
      "order": 2,
      "file": "02_spx_weekly.png",
      "label": "SPX weekly trend regime",
      "category": "technical",
      "timeframe": "weekly"
    }
  ]
}
```

Requirements:
- `order` must be unique and contiguous.
- `file` must exist in `charts/`.
- filenames should be prefixed numerically to make review simple.
- `label` should be concise and descriptive, not a mini-prompt.

### 2. External context schema

Example:

```json
{
  "date": "2026-06-12",
  "vix": 18.4,
  "us10y": 4.31,
  "fear_greed": 63,
  "fear_greed_zone": "greed",
  "put_call": 0.82,
  "high_yield_spread": 3.55,
  "headlines": [
    "Treasury yields drift lower after softer inflation data",
    "Large-cap tech leads broad market higher"
  ],
  "notes": "Inputs frozen at end of trading session"
}
```

The engine should be able to generate this file if it does not already exist.

## Output contracts

### 1. Daily markdown report

Filename:

```text
output/YYYY-MM-DD/YYYY-MM-DD-analysis.md
```

Purpose:
- Primary human-readable artifact.
- Must follow methodology order and preserve its risk rules.
- Must end with the Updated Decision Matrix [cite:79].

### 2. Daily JSON state

Filename:

```text
output/YYYY-MM-DD/YYYY-MM-DD-state.json
```

Purpose:
- Operational memory artifact.
- Canonical machine-readable state for future runs and future chat.
- Includes a compact narrative summary derived from but separate from the full report [cite:143][cite:167].

Example shape:

```json
{
  "date": "2026-06-12",
  "framework_version": "2026-05-12",
  "spx_close": 7450.25,
  "schk_close": 28.14,
  "base_case": "bullish_but_extended",
  "trend_regime": "bullish",
  "valuation_bucket": "cautious",
  "signals": {
    "pct_vs_50dma": 1.8,
    "pct_vs_200dma": 8.9,
    "bollinger_position": "upper_half",
    "rsi14": 66.2,
    "mfi": 72.1,
    "vix": 18.4,
    "vix_regime": "moderate",
    "fear_greed": 63,
    "fear_greed_zone": "greed",
    "put_call": 0.82,
    "high_yield_spread": 3.55,
    "monte_carlo_probability": 0.68
  },
  "what_changed_today": [
    "Breadth improved compared with the prior session",
    "Momentum remained extended near the upper band",
    "VIX eased but stayed in a standard, non-crisis regime"
  ],
  "narrative_summary": "Trend remains bullish, but extension and firmer sentiment reduce immediate re-entry edge. Signals are mixed rather than overwhelmingly favorable, so the framework posture remains hold and monitor.",
  "open_questions": [
    "Can breadth continue improving if price stalls near resistance?",
    "Will volatility stay below the elevated-risk threshold?"
  ],
  "decision_matrix": {
    "valuation": "cautious",
    "technicals": "bullish_but_stretched",
    "sentiment": "greed",
    "risk": "moderate",
    "recommended_action": "hold_and_monitor"
  }
}
```

### 3. Request snapshot

Purpose:
- Save the exact payload elements used for the run, excluding secrets.
- Enable debugging and reproducibility.

### 4. Raw model response

Purpose:
- Save the unprocessed provider response for audits and parser debugging.

### 5. Validation report

Purpose:
- Record schema validation result, methodology-section presence checks, and any warnings.

## Memory design

The application should use three memory layers.

### Static memory

- Full methodology markdown.
- Stable instruction blocks.
- Provider prompt-cacheable prefix where possible [cite:89].

### Rolling operational memory

- Last 5 to 10 daily JSON state objects.
- This is the main continuity mechanism for trend and regime analysis [cite:143][cite:156].

### Human archive memory

- Full markdown reports for every day.
- Use for audit, review, and occasional retrieval when nuance matters.

### Why this pattern

The Claude API is effectively stateless at the application level, so persistent memory must be stored and reintroduced by the application rather than assumed to live in the provider session [cite:141][cite:144]. Best-practice context engineering favors compact memory objects and note-taking outside the live context window instead of replaying raw conversation history forever [cite:143][cite:174].

## Prompt and orchestration strategy

### Recommended run model: two-pass pipeline

#### Pass 1: Structured state generation

Goal:
- Produce schema-valid JSON state using structured outputs if possible [cite:183][cite:113].

Inputs:
- System instructions
- Methodology markdown
- Recent daily JSON states
- Today’s external context
- Chart manifest
- Chart images

Output:
- `DailyState`

#### Pass 2: Markdown report generation

Goal:
- Produce a complete daily markdown report using the validated JSON state as a scaffold.

Inputs:
- Same context as Pass 1
- Validated `DailyState`

Output:
- `analysis.md`

### Why two-pass is recommended

A two-pass design separates machine reliability from human readability. Structured outputs are much more dependable when they are not competing with long prose generation in the same response, and a separate report pass can then produce a more readable final artifact using the validated state as a backbone [cite:183][cite:190].

## Prompt composition

Each run prompt should be built from these blocks in this order:

1. **System role block**
   - define the analyst role
   - require use of the methodology
   - restate hard constraints such as VIX > 20 note, Monte Carlo < 65% no action, no forced signals, always end with Updated Decision Matrix [cite:79]

2. **Framework block**
   - full methodology markdown
   - ideally cacheable [cite:89]

3. **Historical memory block**
   - compact summary of last several states
   - full JSON of last 5 to 10 states

4. **Current external context block**
   - VIX, yields, sentiment, headlines, spreads

5. **Current charts block**
   - chart manifest as text
   - image attachments in manifest order [cite:40]

6. **Task block**
   - instruct exact methodology order
   - require balanced analysis of confirming and conflicting evidence
   - require explicit “hold and monitor” when data are mixed [cite:79]

## Phase 1 Python modules

### `config.py`

Responsibilities:
- Load environment variables.
- Define typed configuration.
- Resolve directory paths.

Key settings:
- Anthropic API key
- default model
- cache enabled flag
- recent state count
- max report length hint
- input/output directories

### `schemas.py`

Responsibilities:
- Define Pydantic models for all file contracts.

Required models:
- `ChartEntry`
- `DailyManifest`
- `ExternalContext`
- `SignalSet`
- `DecisionMatrix`
- `DailyState`
- `ValidationReport`
- `ChatSessionContext` (for future Phase 2)

### `files.py`

Responsibilities:
- Discover daily run directories.
- Validate required files.
- Load/save JSON and markdown.
- Copy canonical outputs into memory folders.

### `external_data.py`

Responsibilities:
- Fetch external market context.
- Normalize sources to the `ExternalContext` schema.
- Persist the normalized result.

### `memory.py`

Responsibilities:
- Load recent prior states.
- Build compact historical summary.
- Provide memory windows for analysis and for future chat sessions.

### `prompts.py`

Responsibilities:
- Build Pass 1 and Pass 2 prompt blocks.
- Keep prompts templated and version-controlled.
- Ensure stable order and consistent wording.

### `anthropic_client.py`

Responsibilities:
- Wrap Claude API calls.
- Support prompt caching and file/image handling where appropriate [cite:89][cite:112].
- Save request/response payload snapshots.

### `analysis_engine.py`

Responsibilities:
- Orchestrate the full run.
- Invoke validation.
- Save outputs.
- Return a run result object.

### `validation.py`

Responsibilities:
- Validate schema conformance.
- Validate methodology-section presence in markdown.
- Validate Updated Decision Matrix presence.
- Emit warning/error report.

### `cli.py`

Responsibilities:
- Expose CLI commands for run, validate, rebuild-summary, and later chat.

### `chat_context.py` and `chat_service.py` (future-ready stubs)

Responsibilities:
- Define the retrieval contract for Phase 2 chat.
- Load a day’s analysis and recent state memory.
- Serve follow-up conversational prompts without mutating the canonical daily-state memory.

## Pydantic schema outline

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class ChartEntry(BaseModel):
    order: int
    file: str
    label: str
    category: str
    timeframe: Optional[str] = None

class DailyManifest(BaseModel):
    date: str
    index_symbol: str
    instrument_symbol: str
    close: float
    chart_count: int
    charts: List[ChartEntry]

class ExternalContext(BaseModel):
    date: str
    vix: Optional[float] = None
    us10y: Optional[float] = None
    fear_greed: Optional[int] = None
    fear_greed_zone: Optional[str] = None
    put_call: Optional[float] = None
    high_yield_spread: Optional[float] = None
    headlines: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

class DecisionMatrix(BaseModel):
    valuation: str
    technicals: str
    sentiment: str
    risk: str
    recommended_action: str

class SignalSet(BaseModel):
    pct_vs_50dma: Optional[float] = None
    pct_vs_200dma: Optional[float] = None
    bollinger_position: Optional[str] = None
    rsi14: Optional[float] = None
    mfi: Optional[float] = None
    vix: Optional[float] = None
    vix_regime: Optional[str] = None
    fear_greed: Optional[int] = None
    fear_greed_zone: Optional[str] = None
    put_call: Optional[float] = None
    high_yield_spread: Optional[float] = None
    monte_carlo_probability: Optional[float] = None

class DailyState(BaseModel):
    date: str
    framework_version: str
    spx_close: float
    schk_close: Optional[float] = None
    base_case: str
    trend_regime: str
    valuation_bucket: str
    signals: SignalSet
    what_changed_today: List[str]
    narrative_summary: str
    open_questions: List[str]
    decision_matrix: DecisionMatrix
```

## CLI specification

### `run`

```bash
python -m src.cli run --date 2026-06-12 --input-dir data/runs/2026-06-12
```

Behavior:
- validate inputs
- fetch or load external context
- load recent memory
- call Pass 1 and Pass 2
- validate outputs
- write outputs and logs

### `validate`

```bash
python -m src.cli validate --date 2026-06-12
```

Behavior:
- reload outputs
- validate schemas and report structure
- print a validation summary

### `rebuild-summary`

```bash
python -m src.cli rebuild-summary --days 5
```

Behavior:
- load recent states
- regenerate a rolling summary artifact

### `chat` (Phase 2 stub)

```bash
python -m src.cli chat --date 2026-06-12
```

Behavior:
- load the day’s report and recent states
- open a follow-up interaction loop using a chat service abstraction

## Run sequence in detail

### Step 1: bootstrap

- load config
- resolve date and directories
- initialize logging

### Step 2: input validation

- validate manifest shape
- verify chart files exist
- verify chart count matches manifest
- reject duplicate or noncontiguous `order` values

### Step 3: external context fetch

- if `external_context.json` exists and `--refresh-context` is not set, use it
- else fetch fresh context and persist normalized result

### Step 4: memory load

- load last N `DailyState` files, default 5
- build compact textual rollup for prompt inclusion

### Step 5: Pass 1 Claude call

- send system + framework + memory + context + charts
- request structured JSON state
- save raw response

### Step 6: JSON validation

- parse into `DailyState`
- if parse fails, attempt one repair pass using the raw output
- if still invalid, fail the run with a validation report

### Step 7: Pass 2 Claude call

- send validated JSON state plus supporting context
- request markdown report
- require methodology order and Updated Decision Matrix

### Step 8: report validation

- check required sections exist
- check Updated Decision Matrix appears
- save validation result

### Step 9: finalize outputs

- write outputs to `output/YYYY-MM-DD/`
- copy canonical `state.json` and `analysis.md` into `memory/`
- update rolling summary

## Error handling policy

### Hard failures

- missing framework file
- invalid manifest
- missing chart files
- schema-invalid `DailyState` after repair attempt
- provider response missing entirely

### Soft failures / warnings

- missing external datapoint replaced with `null`
- report missing a desired but noncritical phrase
- unusually long report
- mismatch between inferred chart count and manifest count if all files still exist

### Retry policy

- one automatic retry for transient API/network failure
- one repair pass for malformed JSON
- no silent retries beyond that

## Cost and performance controls

- Use prompt caching for the framework block and any other stable prefixes to reduce repeated daily cost [cite:89][cite:125].
- Keep recent memory bounded to 5 to 10 daily states rather than replaying unlimited history [cite:143][cite:157].
- Resize images to practical dimensions before upload if needed to reduce image-token overhead [cite:132][cite:134].
- Keep the final report concise enough for decision-making rather than essay-style overproduction.

## Security and secret handling

- Store API keys only in environment variables.
- Never write secrets into request snapshots.
- Save payload metadata but scrub auth headers.
- Treat raw model outputs as internal artifacts, not public logs.
- If later moving to a web app, isolate provider credentials server-side only.

## Testing and acceptance plan

### Unit tests

- schema round-trip tests
- manifest validation tests
- file discovery tests
- memory rollup tests
- prompt construction tests

### Integration tests

- dry run with 3 sample charts
- full run with 15 charts
- rerun with same inputs to confirm deterministic structure
- backtest-style run across 5 consecutive historical days to verify continuity behavior [cite:81][cite:82]

### Acceptance criteria for Phase 1

1. A single CLI command can run a complete daily analysis from a dated folder.
2. The methodology markdown is loaded and visibly enforced in the report output [cite:79].
3. The engine emits both `analysis.md` and `state.json`.
4. `state.json` validates successfully against the schema.
5. The report ends with the Updated Decision Matrix [cite:79].
6. The engine can load recent prior states and reference day-to-day changes.
7. The saved artifacts are sufficient to reconstruct and debug a prior run.

## Phase 2 compatibility contract

Phase 2 should not change Phase 1 file contracts. Instead, the web app should consume them.

### Web app expectations

- Upload daily charts into a run folder or object-store equivalent.
- Trigger the same `analysis_engine.run()` function.
- Display `analysis.md` and `state.json` in a browser.
- Allow browsing prior runs and summaries.
- Create chat sessions that load:
  - the selected day’s report,
  - that day’s state,
  - recent prior states,
  - optional recent chat messages.

### Chat memory separation

Daily-state memory and chat-session memory should be separate stores. The daily-state memory is canonical research memory; the chat session is ephemeral reasoning memory for the current discussion [cite:188][cite:156]. This preserves analytical integrity while still allowing rich follow-up discussion.

## Suggested implementation order for Cursor

### Milestone 1: scaffolding

- create repo structure
- implement config and schemas
- implement manifest and filesystem validation

### Milestone 2: memory and external context

- implement recent-state loading
- implement rolling-summary generation
- implement external context fetch and persistence

### Milestone 3: Claude integration

- implement Anthropic client wrapper
- implement Pass 1 structured state generation
- implement Pass 2 markdown generation
- persist raw request/response snapshots

### Milestone 4: validation and CLI

- implement schema validation
- implement report validation
- implement `run`, `validate`, and `rebuild-summary`

### Milestone 5: historical continuity tests

- test multiple consecutive days
- tune memory window size and summaries
- confirm day-over-day reasoning quality

### Milestone 6: Phase 2 readiness

- add `chat_context.py` and `chat_service.py` stubs
- define API contract for future Next.js integration

## Cursor build instructions

Use the following execution guidance when implementing Phase 1:

1. Build the repository structure exactly or with minimal justified variation.
2. Implement typed Pydantic schemas first and make them the source of truth.
3. Build file validation before provider calls.
4. Implement the engine as a pure Python service that can be called from CLI now and from a web app later.
5. Use a two-pass Claude orchestration: JSON state first, markdown report second [cite:183][cite:190].
6. Keep prompt templates in dedicated files or template functions, not inline throughout the codebase.
7. Save all run artifacts for inspection.
8. Treat the methodology file as immutable runtime input rather than copying its rules into many places [cite:79].
9. Do not build the web UI yet; only prepare clear interfaces for it.
10. Leave a clean path for a future chat service that can load prior analyses and discuss them with the user.

## Minimal pseudocode for the engine

```python
from src.files import load_manifest, load_framework, save_outputs
from src.external_data import load_or_fetch_external_context
from src.memory import load_recent_states, build_recent_summary
from src.prompts import build_state_prompt, build_report_prompt
from src.anthropic_client import run_structured_state, run_markdown_report
from src.validation import validate_daily_state, validate_report


def run_daily_analysis(date: str, input_dir: str):
    framework = load_framework()
    manifest = load_manifest(input_dir)
    external_context = load_or_fetch_external_context(date, input_dir)
    recent_states = load_recent_states(limit=5)
    recent_summary = build_recent_summary(recent_states)

    state_prompt = build_state_prompt(
        framework=framework,
        manifest=manifest,
        external_context=external_context,
        recent_states=recent_states,
        recent_summary=recent_summary,
    )

    daily_state, raw_state_response = run_structured_state(
        prompt=state_prompt,
        chart_dir=f"{input_dir}/charts",
        manifest=manifest,
    )
    validate_daily_state(daily_state)

    report_prompt = build_report_prompt(
        framework=framework,
        daily_state=daily_state,
        manifest=manifest,
        external_context=external_context,
        recent_states=recent_states,
        recent_summary=recent_summary,
    )

    report_md, raw_report_response = run_markdown_report(
        prompt=report_prompt,
        chart_dir=f"{input_dir}/charts",
        manifest=manifest,
    )
    validate_report(report_md)

    save_outputs(
        date=date,
        daily_state=daily_state,
        report_md=report_md,
        raw_state_response=raw_state_response,
        raw_report_response=raw_report_response,
    )
```

## Final recommendation

The correct Phase 1 build is a **headless direct API engine with durable structured memory, reproducible daily artifacts, and a future-ready service boundary**. That architecture solves the current upload-limit problem, preserves methodology fidelity, and creates a clean base for the later private web app and conversational agent the user wants [cite:79][cite:81][cite:188].

The system should be treated as an analysis platform, not merely a chat wrapper. The chat experience can and should come next, but only after the file contracts, schemas, orchestration, and memory model are stable and tested [cite:187][cite:188][cite:192].
