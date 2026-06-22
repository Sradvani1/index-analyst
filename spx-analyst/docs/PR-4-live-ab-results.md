# 2026-06-10 Pass 2 image optimization A/B

**Date run:** 2026-06-21  
**Model:** `claude-opus-4-8`  
**Chart pack:** `data/runs/2026-06-10/charts/` (15 real charts)  
**Memory:** isolated under `output/ab-test/memory-*` (`SPX_INCLUDE_MEMORY=false`) so production `memory/` was not overwritten.

Related: [PR-4](PR-4-pass2-image-optimization.md) · [PR-4.1](PR-4.1-pass2-stub-response-fix.md) (stub fix after initial A/B)

## Commands

```bash
cd spx-analyst

# A — optimization OFF (baseline Pass 2 behavior)
SPX_PASS2_IMAGE_OPTIMIZATION=false \
SPX_OUTPUT_DIR=output/ab-test/off \
SPX_MEMORY_DIR=output/ab-test/memory-off \
SPX_INCLUDE_MEMORY=false \
python -m src.cli run --date 2026-06-10

# B — optimization ON (PR-4)
SPX_PASS2_IMAGE_OPTIMIZATION=true \
SPX_OUTPUT_DIR=output/ab-test/on \
SPX_MEMORY_DIR=output/ab-test/memory-on \
SPX_INCLUDE_MEMORY=false \
python -m src.cli run --date 2026-06-10
```

## Selector / observability (arm B)

| Metric | OFF | ON |
|--------|-----|-----|
| `pass1_chart_count` | 15 | 15 |
| `pass2_chart_count` | 15 | **11** |
| `pass2_charts_omitted` | 0 | 4 (`02_spx_5day.png`, `06_spx_1year.png`, `07_spx_3year.png`, `12_put_call_ratio.png`) |
| Pass 2 encode max edge | 1568 | **1092** |
| `chart_count` (backward compat) | 15 | 15 |

**Omitted charts were not sent as image bytes** (confirmed via `request_snapshot.json` → `report_pass.images`).

## Provider token usage (API `usage` from `response_raw.json`)

| Pass | OFF input | ON input | Δ |
|------|-----------|----------|---|
| Pass 1 (`state_pass`) | 24,687 | 24,687 | 0 (expected — identical) |
| Pass 2 (`report_pass`) | 30,747 | 16,794 | **−13,953 (−45%)** |
| **Run total input** | **55,434** | **41,481** | **−13,953 (−25%)** |

Initial A/B Pass 2 output was a 25-token stub preamble on both arms (fixed in PR-4.1). Input-token comparison remains valid for multimodal cost.

## Post-PR-4.1 verification (optimization ON)

```bash
SPX_PASS2_IMAGE_OPTIMIZATION=true \
SPX_OUTPUT_DIR=output/ab-test/on-fixed \
SPX_MEMORY_DIR=output/ab-test/memory-on-fixed \
SPX_INCLUDE_MEMORY=false \
python -m src.cli run --date 2026-06-10

SPX_OUTPUT_DIR=output/ab-test/on-fixed python -m src.cli validate --date 2026-06-10
```

| Metric | Pre-fix A/B | Post-fix (`on-fixed`) |
|--------|-------------|------------------------|
| `daily_state` validation | PASS | **PASS** |
| `report` validation | FAIL (stub) | **PASS** |
| Pass 2 charts attached | 11 | 9 |
| Report output tokens | 25 | 6,891 |
| `pass2_stub_retry` | n/a | `false` |
| `pass2_tools_in_request` | n/a | `true` |

Artifacts (local, gitignored): `output/ab-test/on-fixed/2026-06-10/`

## Conclusion

PR-4 mechanics verified on live 2026-06-10 data:

- Pass 1 unchanged (15 charts @ 1568).
- Pass 2 subset with auditable `pass2_selection_reasons`.
- ~45% Pass 2 input token reduction; ~25% total run input reduction.
- Reference-only charts omitted from API payload.
- Full report + `validate_report` after [PR-4.1](PR-4.1-pass2-stub-response-fix.md).
