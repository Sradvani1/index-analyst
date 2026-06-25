# SPX Daily Analysis — design.md

## Project Intent
A publication-first front end for daily SPX market analysis. The product should feel like **Substack meets Seeking Alpha**: calm, readable, editorial on first impression, but finance-native in information density and archive navigation.

This is not a dashboard-first terminal and not a generic marketing blog. The homepage should feel like a serious market publication, the report page should feel like a premium long-form article, and the supporting UI should expose structured market state without interrupting reading flow.

---

## 1. Visual Theme & Atmosphere

### Core Mood
- Quiet authority.
- Editorial, analytical, credible.
- Clean and disciplined rather than flashy.
- Slightly premium, but not luxurious.
- Dense enough for market readers, airy enough for long-form reading.

### Design Philosophy
- Reading is the primary job.
- Navigation should support archive discovery and context switching.
- Structured state should appear as companion context, not as the main canvas.
- The design should feel closer to a top-tier financial publication than to SaaS software.
- The eventual chatbot should feel like an embedded research assistant, not a floating gimmick.

### Density
- Article pages: medium density.
- Homepage/archive: medium-high density.
- Side rails and metadata modules: compact.
- Mobile: simplified hierarchy with aggressive collapsing of secondary context.

### Reference Blend
- **Primary influence:** Substack editorial simplicity.
- **Secondary influence:** Seeking Alpha information architecture.
- **Tertiary influence:** Medium-style readability and rhythm.

### Brand Character
- Confident.
- Rational.
- Timely.
- Calm under pressure.
- Never sensational.

---

## 2. Color Palette & Roles

### Palette Strategy
Use a restrained editorial palette with warm neutrals, deep ink text, a financial green as the primary accent, and a muted amber/red system for caution and risk. The UI should look trustworthy in both light and dark mode.

### Semantic Palette

| Token | Hex | Role |
|---|---:|---|
| Ink 900 | `#151922` | Primary text, main headings, high-contrast UI text |
| Ink 700 | `#2B3443` | Secondary headings, table headers, strong labels |
| Ink 500 | `#5E6A7D` | Muted text, metadata, timestamps |
| Paper 50 | `#FAF8F3` | Primary page background |
| Paper 100 | `#F3F0E8` | Alternate section background |
| Surface 0 | `#FFFFFF` | Cards, article body surface, inputs |
| Surface 1 | `#F7F5EF` | Secondary cards, inline modules |
| Border Soft | `#E6E0D4` | Dividers, subtle card borders |
| Market Green | `#0E6B57` | Primary actions, positive state, active accents |
| Market Green Hover | `#0A5848` | Hover state for primary accent |
| Signal Blue | `#295C9B` | Links, secondary interactive accents, info states |
| Caution Amber | `#A56A17` | Watch states, caution badges, intermediate warnings |
| Risk Red | `#A23A3A` | Risk states, negative market posture, destructive actions |
| Gold Note | `#C59A2E` | Highlight accents for premium/archive moments, use sparingly |
| Dark Canvas | `#0F131A` | Dark mode background |
| Dark Surface | `#171C24` | Dark mode cards and navigation surfaces |
| Dark Border | `#2A3240` | Dark mode dividers and borders |
| Dark Text | `#E9EDF3` | Primary dark mode text |
| Dark Muted | `#98A3B5` | Secondary dark mode text |

### Functional Color Rules
- Green is for action, positive posture, and active emphasis.
- Blue is for navigation and links, not for primary calls to action.
- Amber is for caution, incomplete confirmation, or watch states.
- Red is for risk, drawdown, or defensive posture.
- Gold is decorative-academic and should appear sparingly.
- Most of the interface should remain neutral.

---

## 3. Typography Rules

### Font Families
- **Display / Headline:** `Newsreader`, fallback `Georgia, serif`
- **Body / UI Sans:** `Inter`, fallback `system-ui, sans-serif`
- **Data / Numeric Optional:** `IBM Plex Sans` or `Inter Tight`, fallback `Inter, system-ui, sans-serif`

### Typography Intent
- Serif headlines create authority and editorial character.
- Sans-serif body text keeps market content clean and modern.
- Numeric tables, badges, and state modules should use tabular figures.

### Hierarchy Table

| Level | Use | Font | Weight | Size Desktop | Size Mobile | Line Height |
|---|---|---|---:|---:|---:|---:|
| H1 Hero | Homepage lead story / report title | Newsreader | 600 | 48px | 34px | 1.08 |
| H1 Article | Daily report title | Newsreader | 600 | 42px | 32px | 1.1 |
| H2 | Section headings in reports | Newsreader | 600 | 30px | 24px | 1.15 |
| H3 | Subsections / rail module titles | Inter | 600 | 20px | 18px | 1.25 |
| H4 | Card titles / metadata labels | Inter | 600 | 16px | 15px | 1.3 |
| Body L | Long-form reading paragraphs | Inter | 400 | 19px | 18px | 1.72 |
| Body M | Standard cards / archive text | Inter | 400 | 16px | 16px | 1.6 |
| Body S | Metadata / filters / support text | Inter | 500 | 14px | 14px | 1.45 |
| Caption | Timestamps / secondary state | Inter | 500 | 12px | 12px | 1.4 |
| Numeric XL | Price, bias, signal callouts | Inter | 700 | 28px | 24px | 1.15 |
| Numeric M | Tables / badges / metric chips | Inter | 600 | 14px | 14px | 1.2 |

### Typography Rules
- Maximum article line length: 68–72ch.
- Use tabular numerals for all prices, percentages, dates, and matrix values.
- Body copy should never drop below 16px.
- Headings may use serif; UI chrome should remain sans-serif.
- Avoid more than two font families in the shipped UI.
- Paragraph spacing should be generous to support heavy analytical text.

---

## 4. Component Stylings

### Buttons

#### Primary Button
- Background: Market Green.
- Text: white.
- Radius: 10px.
- Padding: 12px 18px.
- Hover: darken to Market Green Hover.
- Active: inset shadow plus 1px downward motion.
- Use for: Subscribe, Open latest report, Ask the market assistant.

#### Secondary Button
- Background: transparent.
- Text: Ink 900.
- Border: 1px solid Border Soft.
- Hover: Surface 1 background.
- Use for: View archive, Filter, Export, Copy link.

#### Ghost Button
- Background: transparent.
- Text: Signal Blue or Ink 700.
- Hover: subtle tinted background.
- Use for inline actions in cards and rail modules.

### Cards
- Background: Surface 0.
- Border: 1px solid Border Soft.
- Radius: 14px.
- Padding: 20px desktop / 16px mobile.
- Shadow: very light, editorial not SaaS-heavy.
- Cards should feel like paper modules, not floating app widgets.

#### Archive Card
- Strong title hierarchy.
- Date and structural bias visible above the fold.
- Include 2–3 metadata chips max: Structural Bias, Recommended Action, Valuation Posture.
- Hover should increase border contrast and shadow slightly.

#### Signal Card
- Compact, denser, more data-forward.
- Left accent bar is allowed only if ultra-subtle and semantic; avoid thick colorful stripes.

### Inputs
- Background: Surface 0.
- Border: 1px solid Border Soft.
- Radius: 10px.
- Height: 44–48px minimum.
- Placeholder text: Ink 500.
- Focus: 2px ring in a low-alpha Market Green.
- Search and chatbot inputs should feel like premium editorial tools, not enterprise forms.

### Navigation

#### Top Nav
- Height: 64–72px.
- Sticky on scroll.
- White or Paper 50 backdrop with slight blur.
- Left: wordmark.
- Center or right: Archive, Latest, Themes, About, Search.
- Future: assistant entry point should live in header but remain quiet.

#### Right Rail Modules
- Sticky after hero/title block.
- Modules: Today’s State, Key Levels, Decision Matrix Snapshot, Related Runs.
- Use compact typography and subtle borders.

#### Inline Links
- Color: Signal Blue.
- Underline on hover.
- Article body links should read like publishing links, not app links.

---

## 5. Layout Principles

### Spacing Scale
Use an 8px-based spacing rhythm.

| Token | Value |
|---|---:|
| `space-1` | 4px |
| `space-2` | 8px |
| `space-3` | 12px |
| `space-4` | 16px |
| `space-5` | 20px |
| `space-6` | 24px |
| `space-8` | 32px |
| `space-10` | 40px |
| `space-12` | 48px |
| `space-16` | 64px |
| `space-20` | 80px |

### Grid System
- Desktop article page: 12-column grid.
- Reading column: 7 columns.
- Right rail: 3 columns.
- Gutter / breathing room: 2 columns distributed or used for offsets.
- Archive/grid views: 3 columns desktop, 2 tablet, 1 mobile.

### Whitespace Philosophy
- Generous vertical whitespace between narrative sections.
- Tighten spacing inside metadata clusters and chips.
- Let article titles breathe.
- Avoid over-fragmenting paragraphs with too many boxes.

### Page Patterns
- Homepage: lead story + latest reports stream + topic rails.
- Archive: filterable but visually calm.
- Report page: title block, metadata row, reading column, sticky right rail.
- Chat panel: eventually collapsible, secondary to report content.

---

## 6. Depth & Elevation

### Surface Hierarchy

| Level | Use |
|---|---|
| Background | Global page canvas, Paper 50 or Dark Canvas |
| Surface Base | Main article paper, cards, content modules |
| Surface Subtle | Secondary modules, chips, filter bars |
| Surface Emphasis | Active selections, highlighted notes, callouts |

### Shadow System
- **Shadow 1:** `0 1px 2px rgba(18, 24, 32, 0.04)` — default cards.
- **Shadow 2:** `0 6px 18px rgba(18, 24, 32, 0.06)` — hover state, sticky nav.
- **Shadow 3:** `0 14px 34px rgba(18, 24, 32, 0.10)` — overlays, modals, assistant panel.

### Elevation Rules
- Most elements should use border-first separation.
- Heavy shadows are reserved for overlays only.
- Article content should feel grounded on the page.
- Sticky nav and rail can use mild blur plus Shadow 1 or 2.
- Dark mode should reduce shadow and rely more on border contrast.

---

## 7. Do's and Don'ts

### Do
- Design like a premium financial publication.
- Prioritize reading comfort above visual novelty.
- Use structure and typography to create authority.
- Surface market state as helpful context around the article.
- Keep archive browsing efficient and information-rich.
- Use restrained semantic color.
- Make tables and matrices feel elegant, not spreadsheet-like.

### Don't
- Do not build a crypto-terminal aesthetic.
- Do not use glowing gradients, neon accents, or animated blobs.
- Do not overuse dashboard widgets on the homepage.
- Do not make every card look interactive if it is not.
- Do not use loud red/green stock-ticker styling throughout the UI.
- Do not let the chatbot dominate the layout.
- Do not mimic generic SaaS landing pages.
- Do not center all text; editorial layouts should be predominantly left-aligned.

### Anti-Patterns
- Purple/blue AI gradients.
- Oversized hero marketing copy.
- Dense card borders everywhere.
- Excessive pill badges.
- Too many accent colors on one screen.
- Split-screen layout where article width becomes cramped.

---

## 8. Responsive Behavior

### Breakpoints

| Breakpoint | Width | Behavior |
|---|---:|---|
| Mobile S | 0–374px | Single column, rail collapses below article, condensed metadata |
| Mobile | 375–767px | Single reading column, sticky bottom actions optional |
| Tablet | 768–1023px | Reading column with collapsed or accordion rail |
| Desktop | 1024–1439px | Full article + right rail layout |
| Wide | 1440px+ | More whitespace, not wider body text |

### Responsive Rules
- Reading width should remain capped even on wide screens.
- Right rail moves below content on mobile.
- Archive grids collapse from 3 columns to 1.
- Metadata rows become stacked chips on small screens.
- Tables should scroll horizontally only as a fallback; preferred mobile treatment is stacked summary cards for critical matrix items.

### Touch Targets
- Minimum interactive target: 44px x 44px.
- Nav items and chips must remain comfortably tappable.
- Chat input and send affordance should be thumb-friendly.

### Collapsing Strategy
- Collapse filters first.
- Collapse secondary rail modules second.
- Collapse related content third.
- Never collapse the report body structure.
- Keep the report title, date, Structural Bias, and Recommended Action visible early on mobile.

---

## 9. Agent Prompt Guide

### Quick Color Reference
- Background: `#FAF8F3`
- Surface: `#FFFFFF`
- Primary Text: `#151922`
- Muted Text: `#5E6A7D`
- Primary Accent: `#0E6B57`
- Link / Secondary Accent: `#295C9B`
- Caution: `#A56A17`
- Risk: `#A23A3A`

### Prompt Framing
Use these phrases when generating UI with an agent:

- “Design a publication-first financial analysis site that feels like Substack meets Seeking Alpha.”
- “Prioritize long-form readability, archive discovery, and quiet authority over dashboard density.”
- “Use serif display headlines with modern sans-serif body text and restrained semantic color.”
- “Treat structured market state as a companion rail, not the main canvas.”
- “Avoid SaaS landing-page tropes, crypto aesthetics, and generic AI gradients.”

### Ready-to-Use Prompt
```text
Create a static front-end design for an SPX daily market analysis publication. The product should feel like Substack meets Seeking Alpha: editorial and highly readable, but with finance-native archive navigation and structured market context. Use a warm neutral background, deep ink typography, a restrained market-green accent, and a clean serif + sans pairing. The homepage should feel like a premium market publication, the article page should emphasize long-form reading with a sticky right rail for state/context, and the archive should support fast scanning of daily reports. Avoid dashboard-first layouts, crypto aesthetics, SaaS marketing tropes, glowing gradients, and overly dense widget grids. Keep the eventual chatbot visually secondary and integrated as a research assistant.
```

### Component Prompt Add-On
```text
Use subtle bordered cards, quiet shadows, sticky top navigation, strong article title hierarchy, compact metadata chips, elegant tables, and responsive collapse behavior that preserves reading comfort on mobile.
```
