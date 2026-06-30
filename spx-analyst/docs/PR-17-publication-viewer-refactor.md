# PR-17: Publication viewer refactor + assistant polish

**Status:** Complete  
**Scope:** `spx-analyst/web/` only — no backend/Python changes  
**Plan:** [.cursor/plans/frontend_refactor_upgrade_d2556015.plan.md](../../.cursor/plans/frontend_refactor_upgrade_d2556015.plan.md)

## Summary

Replaces the sidebar/tab MVP with a publication-first layout: sticky top nav, editorial homepage, scrollable report article with a structured right rail, and polished `/assistant` workspace. Structured UI reads `DailyState` / `RunSummary` only; markdown is for narrative sections.

## Navigation model

| Before | After |
|--------|-------|
| Persistent `w-72` run sidebar | Sticky `SiteHeader` in root layout |
| `/` redirects to latest run | `/` shows `LeadStory` + `RecentStream` |
| Horizontal section tabs | Scrollable article sections |
| Header duplicated facts + signals | Hero header + rail split (no field duplication) |

### Routes

| Route | Purpose |
|-------|---------|
| `/` | Editorial homepage — lead story + recent stream |
| `/archive` | Full archive grid (linked from top nav) |
| `/runs/{date}` | Scrollable article + sticky rail |
| `/assistant` | Research assistant workspace |
| `/about` | Static product note |

## Report layout

```text
SiteHeader (root layout, React.cache(listRuns))
└── report-article (max-w-7xl)
    ├── article column (max-w-[70ch])
    │   ├── RunHeader (date, title, close, action banner)
    │   ├── RunNav (prev / next / archive)
    │   └── SectionBlock × N (viewerSections)
    └── ReportRail (sticky lg+, stacked mobile)
        ├── Today's state (bias, regime, valuation, primary_tension)
        ├── Signal snapshot (SignalGrid)
        ├── Decision matrix (DecisionMatrix from JSON)
        └── Monte Carlo summary
```

**Field-authority rule:** each `DailyState` field appears in the header or rail, never both. Decision matrix section in the article renders from `daily_state.decision_matrix`; markdown table is fallback only.

## Assistant polish

| Feature | Implementation |
|---------|----------------|
| Auto-scroll | Tail ref scrolls on new messages + streaming chunks |
| Enter to send | `ChatComposer` — Enter sends, Shift+Enter newline |
| Stop streaming | `AbortController` on fetch; Stop button in composer |
| Session rename | Inline pencil edit → `renameChatSession()` |
| Suggested prompts | Empty state + new-session chips |
| Delete confirm | shadcn `AlertDialog` (replaces `window.confirm`) |
| Copy message | Ghost copy icon on assistant bubbles |
| Mobile sessions | Sheet below `md`; desktop keeps sidebar |
| Compact markdown | `ReportMarkdown variant="compact"` for bubbles |

**Out of scope:** embedded report panel, report context bridge, citation UI.

## Removed

- `components/run-list.tsx`
- `components/report-tabs.tsx`
- `components/chat/assistant-link.tsx`

## New / refactored components

| File | Role |
|------|------|
| `components/site-header.tsx` | Sticky nav + mobile Sheet |
| `components/report/report-article.tsx` | Article + rail orchestrator |
| `components/report/report-rail.tsx` | Four DailyState rail modules |
| `components/report/section-block.tsx` | Scrollable `##` section renderer |
| `components/report/run-nav.tsx` | Prev / next run links |
| `components/report/truncated-fact.tsx` | Long-string fact tiles (from RunHeader) |
| `components/chat/chat-composer.tsx` | Textarea + send/stop |
| `components/chat/message-bubble.tsx` | User/assistant bubble + copy |
| `components/ui/sheet.tsx` | Mobile nav + session list |
| `components/ui/alert-dialog.tsx` | Delete confirmation |

## Verification

```bash
cd spx-analyst && pytest tests/test_web_api.py tests/test_web_chat_api.py -q
cd spx-analyst/web && npm run lint && npm run build
```

Manual checklist (automated tests + build verified; browser pass pending operator sign-off):

- [ ] `/` shows lead story + recent stream (not redirect)
- [ ] `/archive` reachable from top nav
- [ ] `/runs/{date}` scrollable article with hero header, sections, matrix from JSON
- [ ] Rail modules match field-authority map; stack below article on mobile
- [ ] Prev/next navigation across dates
- [ ] `/assistant` streaming, auto-scroll, Enter-to-send, stop, rename, prompts, mobile Sheet
- [ ] API down → graceful empty/error states (header + error page)
- [ ] Responsive layout at 375 / 768 / 1280 / 1440

## Deferred (Tier 2)

- Section hash deep links / in-page TOC
- Dark mode toggle
- Archive client-side filtering
- Citation UI (requires backend SSE metadata)
- Embedded assistant panel on report pages
