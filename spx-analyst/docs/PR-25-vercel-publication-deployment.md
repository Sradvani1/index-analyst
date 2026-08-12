# PR-25: Vercel Publication Deployment

**Status:** Implemented and deployed
**Scope:** Deploy the Next.js publication viewer and its FastAPI read API to Vercel. Keep the daily analysis engine and research assistant local-only.
**Builds on:** PR-17 publication viewer, PR-24 daily engine fixes.
**Primary deployment model:** One Vercel project using Vercel Services.

**Implementation record (2026-08-10):**

- Vercel project: `sameer-advanis-projects/spx-analyst`
- Production: https://spx-analyst.vercel.app
- Verified preview: https://spx-analyst-bc817bwnh-sameer-advanis-projects.vercel.app
- Both frontend and backend Services reached `Ready`.
- Backend bundle: 122.14 MB; frontend bundle: 825.26 KB.
- `SPX_CHAT_ENABLED=false` is configured for Production and Preview.
- Vercel SSO Deployment Protection is disabled so server-side same-origin API fetches can reach the public backend service.
- Local verification passed: `pytest` (437 tests), `npm run lint`, and `npm run build`.
- Production verification passed for the homepage, health API, known report, disabled Assistant page, and disabled chat API.

---

## 1. Summary

The publication viewer currently requires two local processes:

1. A Next.js server in `web/` on port 3000.
2. A FastAPI server in `src/web/` on port 8000.

The daily analysis engine remains a local operator tool. It generates the canonical state and report artifacts in `memory/`, and the viewer reads those artifacts without recomputing analysis.

This PR will deploy the viewer and read API to Vercel:

```text
One Vercel project
├── frontend service: web/ -> Next.js
└── backend service: .    -> src.web.app:app (FastAPI)
```

Vercel's top-level routing will send `/api/*` requests to FastAPI and all other requests to Next.js. The current report and state files will be committed to git so the read-only FastAPI function can load them from its deployment bundle. No database, object store, or Python storage adapter is needed for this first deployment.

The research assistant will remain local-only. Its navigation link will be removed, its pages will return 404 in Vercel deployments, and its FastAPI routes will not be registered when `SPX_CHAT_ENABLED=false`.

Chart packs are explicitly deferred. The current publication UI does not render chart images, and adding the packs to git would create significant repository growth without providing a user-visible feature.

---

## 2. Goals

### 2.1 In scope

- Deploy the publication homepage, archive, report reader, about page, and health/read API to Vercel.
- Run the existing FastAPI viewer app with Vercel's Python ASGI runtime.
- Preserve the current archive of valid state/report pairs.
- Keep local development behavior for the viewer unchanged.
- Keep the local research assistant available by direct local URL.
- Make the deployed site expose no assistant navigation, assistant pages, or chat API routes.
- Establish a repeatable publish workflow: run locally, commit archive artifacts, push, and let Vercel deploy.
- Add an early deployment spike to validate the nested service-root layout and Python bundle.

### 2.2 Explicitly out of scope

- Deploying the daily analysis engine.
- Running yfinance, chart generation, Claude analysis, OpenAI pipeline analysis, or PDF export on Vercel.
- Deploying the research assistant or OpenAI chat integration.
- Persisting chat sessions in a cloud database.
- Uploading chart packs to git, Vercel Blob, or another asset store.
- Adding authentication or private deployment protection to the public viewer.
- Replacing the file archive with Postgres, Redis, Blob, or another database.
- Changing the analytical schemas or report-generation behavior.

---

## 3. First-Principles Constraints

### 3.1 What Vercel will run

Vercel can load `src.web.app:app` as an ASGI FastAPI application through its Python runtime. The deployed backend is a serverless function, not a long-running `uvicorn` process.

The backend must therefore:

- Use only dependencies available in the deployment bundle.
- Read immutable archive files from the bundle or a remote store.
- Avoid relying on persistent local writes.
- Avoid the heavy daily-engine dependencies when they are not needed by the viewer import graph.

### 3.2 What stays on the local machine

The CLI and analysis pipeline continue to run locally because they use:

- yfinance and market-data downloads.
- NumPy, pandas, matplotlib, and chart-generation code.
- Anthropic or OpenAI pipeline clients.
- WeasyPrint and local PDF/export dependencies.
- Local input chart packs under `data/runs/`.

The Vercel deployment is a publication surface, not a hosted analysis worker.

### 3.3 Archive persistence choice

The current viewer data is small and append-only for this stage. The simplest deployment-compatible solution is to commit the valid archive files to git:

```text
memory/daily_states/YYYY-MM-DD-state.json
memory/daily_reports/YYYY-MM-DD-analysis.md
```

Vercel includes those tracked files in the Python function bundle. The existing `src/web/service.py` can continue to read them with `Path` and does not need a storage abstraction.

This is intentionally a first-stage tradeoff. It makes each publish a git commit and deployment. It avoids introducing a cloud storage dependency before the basic viewer is proven.

### 3.4 Chart-pack choice

Chart packs remain ignored:

```text
data/runs/
../Images/
daily_pdfs/
```

Current observations:

- `data/runs/` is approximately 104 MB today.
- Recent chart packs add approximately 1.5 MB per run, with earlier packs reaching approximately 5.7 MB.
- Individual chart files are small enough for GitHub's per-file limit.
- The viewer currently has no chart route, chart API, image references in reports, or chart-rendering component.

Therefore, including charts now would increase repository and deployment size without changing the user-visible product. A future chart build should add an actual asset-delivery design first, then store images in an asset store or a deliberately curated static set.

---

## 4. Target Architecture

### 4.1 Vercel Services

The repository root is the Vercel project root. The services are:

| Service | Root | Framework | Entrypoint | Responsibility |
|---|---|---|---|---|
| `frontend` | `web/` | Next.js | framework default | Pages, layouts, report rendering, public assets |
| `backend` | `.` | FastAPI | `src.web.app:app` | Health, archive listing, and report detail API |

Top-level routing is ordered from specific to general:

```text
/api/(.*) -> backend service
/(.*)     -> frontend service
```

Vercel routing is final. If a request reaches the backend, the backend owns the response and Vercel does not fall through to the frontend service.

### 4.2 Request paths

The backend receives the existing `/api/...` path unchanged:

```text
GET /api/health       -> FastAPI /api/health
GET /api/runs         -> FastAPI /api/runs
GET /api/runs/{date}  -> FastAPI /api/runs/{date}
```

The Next.js browser code uses relative `/api/...` URLs. Server-rendered Next.js code uses an absolute URL because Node's server-side `fetch` cannot reliably parse a relative URL:

```text
https://${VERCEL_URL}/api/runs
```

The deployment protection setting must remain disabled for this same-origin server fetch to reach the public rewrite without an authentication cookie.

### 4.3 Local request paths

Local development keeps the current two-process workflow:

```text
Browser -> Next.js :3000 -> /api/* rewrite -> FastAPI :8000
Server page -> http://127.0.0.1:8000/api/*
```

The local research assistant remains available at:

```text
http://localhost:3000/assistant
```

It will be accessed directly because its navigation link is removed from both local and deployed navigation.

---

## 5. Implementation Plan

### Phase 0: Deployment preflight and spike

Before committing the full deployment configuration, validate the highest-risk Vercel assumptions.

1. Confirm the Vercel account/team and project target with `vercel whoami`.
2. Use a temporary branch or temporary local config to deploy the FastAPI service alone from the repository root.
3. Use the trimmed Python requirements file and the `src.web.app:app` entrypoint.
4. Confirm that the Python service root can be `.` while the final frontend service root will be `web/`.
5. Confirm that the custom install command is used instead of installing the full engine dependency set from `pyproject.toml`.
6. Confirm that the function bundle excludes `data/`, `web/`, tests, documentation, and local tooling while retaining `memory/` and `framework/`.
7. Confirm the temporary deployment responds to:

   ```text
   GET /api/health
   GET /api/runs
   ```

8. Delete the temporary config or branch after the spike. Do not leave a second deployment configuration in the final repository.

If Vercel rejects the nested roots or cannot build the shared-root backend, use the two-project fallback in Section 11 rather than redesigning the Python package for this first deployment.

### Phase 1: Make the archive deployable

#### 1.1 Update `.gitignore`

Remove only these ignore rules:

```gitignore
memory/daily_states/*.json
memory/daily_reports/*.md
```

Keep the following generated or local-only areas ignored:

```gitignore
memory/rolling/*
memory/chat/
memory/rag/
data/runs/*/
output/*/
daily_pdfs/*.pdf
```

Do not remove or modify unrelated ignore rules.

#### 1.2 Validate the archive before staging

Use the existing local service behavior to identify state/report pairs that the viewer can load. The first deployment should preserve the existing valid archive, not introduce a new archive format.

Validation requirements:

- A state must pass `DailyState.model_validate`.
- A report must exist for the same date.
- Dates must match the existing `YYYY-MM-DD` filename contract.
- Orphan or invalid artifacts must not be presented as valid runs.

The implementation should use the existing `list_runs()` behavior as the source of truth for this check. Do not add a second validation implementation solely for deployment.

#### 1.3 Track the archive

Stage the valid existing pairs under:

```text
memory/daily_states/
memory/daily_reports/
```

Keep the existing `.gitkeep` files. Do not stage chart packs, raw intake images, local chat sessions, rolling memory, or local environment files.

#### 1.4 Define the publishing workflow

After a successful local analysis run:

```bash
git add memory/daily_states memory/daily_reports
git commit -m "Publish SPX report YYYY-MM-DD"
git push
```

Vercel's git integration then builds and deploys the new archive. If a deployment fails, the previous successful deployment remains live; the report is not considered published until the new deployment passes its checks.

No `sync-memory` command is required for this git-backed first stage.

### Phase 2: Separate deployment dependencies

Add `requirements-deploy.txt` at the repository root:

```text
fastapi>=0.115.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
python-dotenv>=1.0.1
```

Do not include these engine-only dependencies in the Vercel install file:

```text
anthropic
typer
Pillow
tenacity
uvicorn
yfinance
numpy
pandas
matplotlib
markdown
weasyprint
openai
```

Rationale:

- Vercel supplies the ASGI execution environment, so `uvicorn` is not required by the deployed function.
- The viewer import graph does not import the engine's chart, data, PDF, or provider modules.
- The chat router is disabled in the deployed environment, and `openai` is imported lazily by the local chat implementation.
- The full local `pyproject.toml` and `requirements.txt` remain unchanged for engine development.

### Phase 3: Make chat explicitly local-only

#### 3.1 Add a typed chat flag

Add a setting to `src/config.py`:

```python
chat_enabled: bool = Field(default=True, alias="SPX_CHAT_ENABLED")
```

Local behavior remains enabled by default. The Vercel project will define:

```text
SPX_CHAT_ENABLED=false
```

for the relevant Vercel environments.

#### 3.2 Gate FastAPI chat routes

In `src/web/app.py`:

- Continue importing the existing chat module so local tests and local development retain the current code path.
- Register `chat_router` only when `get_settings().chat_enabled` is true.
- Keep health and archive routes unconditional.

Expected behavior:

| Environment | `/api/chat/*` |
|---|---|
| Local, flag absent | Existing chat behavior |
| Vercel, `SPX_CHAT_ENABLED=false` | 404, no chat router |

The implementation must not change the local chat session files or OpenAI behavior.

#### 3.3 Remove the navigation link

In `web/components/site-header.tsx`:

- Remove the `Assistant` object from `NAV_LINKS`.
- Do not add client-side Vercel environment detection.
- This single list drives desktop and mobile navigation.

The Assistant remains available locally by direct URL, but it is not advertised in the publication UI.

#### 3.4 Gate Assistant pages

In both pages below:

```text
web/app/assistant/page.tsx
web/app/assistant/[sessionId]/page.tsx
```

Check `SPX_CHAT_ENABLED` on the server and call `notFound()` when it is explicitly false.

Expected behavior:

| Environment | `/assistant` |
|---|---|
| Local, flag absent | Existing Assistant workspace |
| Vercel, flag false | Next.js 404 |

This keeps the local tool intact while preventing direct access in the deployed UI.

### Phase 4: Correct frontend-to-backend URL handling

#### 4.1 Update server-side API base resolution

Update `web/lib/api.ts` so it distinguishes browser and server execution:

```ts
function apiBase(): string {
  if (typeof window !== "undefined") {
    return "";
  }

  if (process.env.VERCEL_URL) {
    return `https://${process.env.VERCEL_URL}`;
  }

  return process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
}
```

This produces:

- Browser: relative `/api/...` request through the Vercel rewrite.
- Vercel server component: absolute `https://${VERCEL_URL}/api/...` request through the Vercel rewrite.
- Local server component: existing `API_BASE_URL` or `127.0.0.1:8000` behavior.

Do not use an empty string for server-side `fetch`; Node's fetch requires an absolute URL.

The local-only `web/lib/chat-api.ts` can retain its existing browser-relative behavior. If it is refactored for shared URL handling, preserve local chat behavior and do not introduce production chat calls.

#### 4.2 Make the development rewrite conditional

Update `web/next.config.ts` so the localhost rewrite is emitted only for `next dev`:

```ts
async rewrites() {
  if (process.env.NODE_ENV !== "development") {
    return [];
  }

  return [
    {
      source: "/api/:path*",
      destination: "http://127.0.0.1:8000/api/:path*",
    },
  ];
}
```

Without this change, the production Next.js routing table would try to send `/api/*` to `127.0.0.1:8000` instead of using the Vercel Services rewrite.

#### 4.3 Make dynamic rendering explicit

Add:

```ts
export const dynamic = "force-dynamic";
```

to `web/app/layout.tsx`, which calls `listRuns()` for the shell on every page. This makes the runtime API dependency explicit and prevents a build-time attempt to fetch a backend that is not deployed yet.

The existing `cache: "no-store"` fetch behavior remains in place. Do not add static data caching for the archive in this PR.

### Phase 5: Add the Vercel Services configuration

Add `vercel.json` at the repository root:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "services": {
    "frontend": {
      "root": "web/",
      "framework": "nextjs"
    },
    "backend": {
      "root": ".",
      "framework": "fastapi",
      "entrypoint": "src.web.app:app",
      "installCommand": "pip install -r requirements-deploy.txt",
      "functions": {
        "src/web/app.py": {
          "includeFiles": "{memory/**,framework/**}",
          "excludeFiles": "{data/**,tests/**,docs/**,scripts/**,daily_pdfs/**,output/**,web/**,.venv/**}"
        }
      }
    }
  },
  "rewrites": [
    {
      "source": "/api/(.*)",
      "destination": { "service": "backend" }
    },
    {
      "source": "/(.*)",
      "destination": { "service": "frontend" }
    }
  ]
}
```

Configuration requirements:

- Keep the backend function key as `src/web/app.py`, the resolved Python entrypoint.
- Explicitly include `memory/**` and `framework/**` because the backend reads those files dynamically rather than importing them as Python modules.
- Use brace-style glob expansion for `excludeFiles`.
- Do not exclude `memory/`; committed state/report files must be available to the backend.
- Do not exclude `framework/`; it is part of the committed application package and remains available to local-only chat code.
- Exclude `data/`; it contains approximately 104 MB of engine inputs and chart packs that the viewer does not use.
- Do not add top-level `framework`, `installCommand`, `functions`, or `outputDirectory` settings; in Services mode those settings belong to the owning service.

### Phase 6: Configure the Vercel project

In the Vercel dashboard or CLI:

1. Link the repository to a new Vercel project.
2. Enable access to Vercel system environment variables so `VERCEL_URL` is available during build and runtime.
3. Set `SPX_CHAT_ENABLED=false` for Production and Preview environments for the project. If service-specific environment configuration is required, set it for both frontend and backend services.
4. Disable Deployment Protection because the publication is intentionally public and server-side frontend requests use the deployment URL.
5. Do not add `OPENAI_API_KEY`, `OPENAI_VECTOR_STORE_ID`, Anthropic keys, or Blob/KV credentials for this first deployment.

`VERCEL_URL` is used only as a host for same-deployment API requests. It is not a secret.

### Phase 7: Deploy and verify

Deploy in two stages.

#### 7.1 Backend spike

Use the temporary backend-only configuration from Phase 0 and verify:

```text
GET /api/health -> 200 and {"status":"ok"}
GET /api/runs -> 200 and a JSON list containing the committed archive
GET /api/runs/{known-date} -> 200 with report_markdown and daily_state
GET /api/chat/sessions -> 404 when SPX_CHAT_ENABLED=false
```

Also inspect the build output for:

- Successful installation from `requirements-deploy.txt`.
- No attempted installation of WeasyPrint, matplotlib, pandas, yfinance, or other engine-only packages.
- Backend bundle size well below the Python function limit.
- `memory/` present in the deployed bundle.
- `data/` and `web/` excluded from the backend bundle.

#### 7.2 Full Services deployment

Deploy the final `vercel.json` and verify:

```text
GET /api/health -> backend service
GET /api/runs -> backend service
GET /api/runs/{known-date} -> backend service
GET / -> frontend service
GET /archive -> frontend service
GET /runs/{known-date} -> frontend service
GET /about -> frontend service
GET /assistant -> 404
GET /api/chat/sessions -> 404
```

Verify the root layout loads its run list during server rendering. A failure here must be treated as a deployment failure, not as an empty archive.

### Phase 8: Document the operating workflow

Update `README.md` after implementation with a concise deployment section covering:

- Local engine remains the source of new reports.
- Reports become public only after archive files are committed and pushed.
- Charts are not deployed in PR-25.
- Assistant is local-only and available at direct local `/assistant` URL.
- Vercel project environment variable `SPX_CHAT_ENABLED=false`.
- The local commands for running FastAPI and Next.js.

This PR record remains the detailed implementation and verification reference.

---

## 6. File-Level Change List

### New files

| File | Purpose |
|---|---|
| `vercel.json` | Vercel Services definitions and top-level routing |
| `requirements-deploy.txt` | Minimal Python dependencies for the deployed viewer API |
| `docs/PR-25-vercel-publication-deployment.md` | This implementation plan and verification record |

### Modified files

| File | Change |
|---|---|
| `.gitignore` | Track daily state and daily report artifacts; keep engine inputs and local-only data ignored |
| `src/config.py` | Add `SPX_CHAT_ENABLED`, defaulting to true locally |
| `src/web/app.py` | Register chat router only when chat is enabled |
| `web/components/site-header.tsx` | Remove Assistant navigation item |
| `web/app/assistant/page.tsx` | Return 404 when chat is disabled |
| `web/app/assistant/[sessionId]/page.tsx` | Return 404 when chat is disabled |
| `web/lib/api.ts` | Use absolute `VERCEL_URL` for server-side requests and relative URLs in the browser |
| `web/next.config.ts` | Keep localhost API rewrite for development only |
| `web/app/layout.tsx` | Explicitly force dynamic rendering for the API-backed shell |
| `README.md` | Add deployment and publishing workflow after implementation |

### Files intentionally not modified

| Area | Reason |
|---|---|
| `src/web/service.py` | Existing filesystem archive access remains valid when archive files are bundled |
| `src/chat_service.py` and chat implementation | Local assistant behavior must remain unchanged |
| `pyproject.toml` and `requirements.txt` | Local engine dependency installation remains unchanged |
| `data/runs/` and chart files | Chart deployment is deferred |
| `memory/chat/` | Local assistant session data is not deployed |
| `memory/rolling/` | Not required by the publication viewer |
| `memory/rag/` | Not required by the publication viewer or deployed chat |

---

## 7. Testing Strategy

### 7.1 Python tests

Run the existing web and full test suites:

```bash
source .venv/bin/activate
pytest tests/test_web_api.py tests/test_web_chat_api.py -q
pytest
```

Required checks:

- Default local settings keep chat enabled.
- Existing web API tests continue to read temporary local filesystem artifacts.
- Existing chat API tests continue to register and exercise the local chat router.
- Archive listing and detail behavior do not change.
- No engine tests require the deploy requirements file.

If the app-level chat flag makes route registration difficult to test in-process, cover the disabled branch with the deployed smoke test and a focused settings test rather than introducing a new application factory solely for this PR.

### 7.2 Web checks

```bash
cd web
npm run lint
npm run build
```

Required checks:

- The production build does not retain the Assistant navigation item.
- The root layout remains dynamic.
- No production Next rewrite points to `127.0.0.1:8000`.
- Local `next dev` retains the development API rewrite.
- Local direct `/assistant` remains available.

### 7.3 Archive checks

Before the first deployment:

- Confirm every intended date has both a state and report file.
- Confirm `list_runs()` returns the expected dates locally.
- Confirm no chart files are staged.
- Confirm no `.env`, chat session, or rolling-memory files are staged.
- Confirm the archive files are below GitHub per-file limits.

### 7.4 Production smoke checks

Use one known current date and one older date:

- `/api/health` returns HTTP 200.
- `/api/runs` returns newest-first summaries.
- `/api/runs/{date}` returns the exact report and validated state.
- `/` renders the lead story and recent stream.
- `/archive` renders the archive.
- `/runs/{date}` renders the article and structured rail.
- `/assistant` returns HTTP 404.
- `/api/chat/sessions` returns HTTP 404.
- A missing date returns HTTP 404.
- An invalid date path does not escape the archive contract.

---

## 8. Publish Workflow After Implementation

The daily operator workflow remains local:

```bash
# Generate and validate the report locally
python -m src.cli prepare --date YYYY-MM-DD
python -m src.cli run --date YYYY-MM-DD
python -m src.cli validate --date YYYY-MM-DD

# Publish only the canonical viewer artifacts
git add memory/daily_states memory/daily_reports
git commit -m "Publish SPX report YYYY-MM-DD"
git push
```

The push triggers a Vercel deployment. The chart pack remains local and is not part of the publish command.

If the report should remain private or unpublished, do not commit/push its archive files. The local viewer can still read files present on the local filesystem.

---

## 9. Edge Cases and Contracts

### 9.1 Missing archive files

The existing service contract remains unchanged:

- A state without a report is not listed.
- A report without a state is not listed.
- Invalid state JSON is skipped by archive listing and results in a missing run.
- A direct request for a missing or invalid date returns 404.

### 9.2 Preview deployments

Each preview deployment contains the archive from its source commit. A new local report is not visible on an older preview deployment. This is expected for a git-backed archive.

### 9.3 Runtime filesystem

The deployed FastAPI function must not write to `memory/`, `data/`, or any other project path. The archive is read-only. Local chat writes remain local and never run in the deployed process because the chat router is disabled.

### 9.4 Server-side URL resolution

`VERCEL_URL` must be used only for server-side Next.js calls. Browser code must keep relative URLs so the browser stays on the public deployment origin. An empty API base must never be returned for server-side Node fetches.

### 9.5 Deployment Protection

The public publication depends on unauthenticated browser and server-side access. Deployment Protection must remain disabled unless the URL strategy is changed to a service binding or an explicit protection bypass.

### 9.6 Chat flag

The absence of `SPX_CHAT_ENABLED` means enabled for local development. Vercel must explicitly set it to `false`; a missing Vercel variable is a configuration error and must be caught in deployment verification.

### 9.7 Chart growth

Chart files must not be reintroduced into the archive commit workflow by broad staging commands. Future chart work must define an asset retention and delivery policy before changing `.gitignore`.

---

## 10. Security and Operational Notes

- The publication is intentionally public and read-only.
- No provider API keys are needed for the deployed viewer-only scope.
- `.env` remains ignored and must never be committed.
- The deployed Python dependency set must not include provider or engine packages unnecessarily.
- The backend exposes only health and archive routes when `SPX_CHAT_ENABLED=false`.
- The frontend must not expose `OPENAI_API_KEY`, Anthropic credentials, or local filesystem paths.
- Vercel system environment variables must be enabled only through project settings; no generated environment values should be committed.

---

## 11. Fallback: Two Vercel Projects

Use this only if the Services spike shows that a backend root of `.` cannot coexist with the frontend root `web/`.

### Backend project

- Root: repository root.
- Framework: FastAPI.
- Entrypoint: `src.web.app:app`.
- Install command: `pip install -r requirements-deploy.txt`.
- Public URL: backend deployment URL.

### Frontend project

- Root: `web/`.
- Framework: Next.js.
- Production API base: backend deployment URL.
- Production rewrite: `/api/:path*` to the backend deployment URL.
- Local rewrite: `/api/:path*` to `http://127.0.0.1:8000/api/:path*`.

The backend CORS configuration would then need the production frontend origin added. The two-project fallback is less desirable because it creates two deployment surfaces and requires separate project configuration, but it preserves the same application code and archive strategy.

---

## 12. Future Chart Build

Chart delivery is a separate product change, not a deployment follow-up hidden inside PR-25.

A future chart PR should first decide:

- Which chart types and dates are public.
- Whether charts are shown on report pages, a chart gallery, or both.
- Whether historical charts are retained indefinitely.
- Whether chart images are private or public assets.
- Whether images are generated locally and uploaded after each run.
- Whether the source of truth is Vercel Blob, another object store, or a curated `web/public/` set.
- How image URLs are represented in report/state data.
- How image delivery affects mobile performance and Vercel costs.

Until those decisions exist, chart packs remain local engine inputs.

---

## 13. Sequencing Summary

1. Validate the current archive and deployment prerequisites.
2. Run a temporary backend-only Vercel spike.
3. Remove the two daily archive ignore rules and stage valid state/report pairs.
4. Add `requirements-deploy.txt`.
5. Add the explicit `SPX_CHAT_ENABLED` setting and gate backend chat registration.
6. Remove the Assistant navigation link and gate Assistant pages.
7. Correct server-side API URL resolution with `VERCEL_URL`.
8. Make the Next.js localhost rewrite development-only.
9. Mark the root layout dynamic.
10. Add final `vercel.json` Services configuration.
11. Configure Vercel system variables, `SPX_CHAT_ENABLED=false`, and disabled Deployment Protection.
12. Run Python tests, web lint/build, archive checks, and the full deployment smoke checklist.
13. Update `README.md` with the publish workflow and local-only Assistant note.
14. Record the final deployment URL and any Vercel-specific operational notes in this PR record.

---

## 14. Acceptance Criteria

PR-25 is complete when all of the following are true:

- The Vercel project builds both Services successfully.
- The backend function installs only the trimmed deployment dependencies.
- The deployed backend can read committed `memory/daily_states` and `memory/daily_reports`.
- The deployed homepage, archive, and report pages render valid published runs.
- Server-rendered API calls use `VERCEL_URL` and do not fail due to relative Node fetch URLs.
- The production Next.js build contains no localhost production rewrite.
- The production navigation contains no Assistant link.
- `/assistant` returns 404 on Vercel.
- `/api/chat/*` returns 404 on Vercel.
- Local direct `/assistant` still works with the existing two-process workflow.
- Chart packs remain untracked and are not included in the deployment bundle.
- The daily publish workflow is documented and verified with one new report.
- `pytest`, `npm run lint`, and `npm run build` pass.
- If Services cannot support the nested roots, the documented two-project fallback is used and its CORS/API wiring passes the same smoke tests.
