# Landing-page harmonisation + design-tokens package adoption

> Handoff from the 2026-08-13 design-unification session (govoss/UNNYC side).
> Written to be executed by a Databook-focused session with no other context.
> Owner decision this implements: **unify the WeGov/Databook/govoss properties on
> `@wegovnyc/design-tokens`**, per Devin, 2026-08-13. That decision REVERSES the
> 2026-08-05 call that kept Databook deliberately out of the package — update KI
> `wegovnyc-design-system` (and `databook-design-system`) when Phase 2 lands.

## Read before touching anything

1. `CLAUDE.md` in this workspace — deploy conventions, the JWT history, what not to do.
2. `docs/DATABOOK-STYLE.md` — the token vocabulary and hard conventions. Ground truth.
3. KI `wegovnyc-design-system` (`search_knowledge` → `get_knowledge_artifact`) — the
   two-tier token architecture, the custom-property substitution trap, the
   verification discipline. The traps section is load-bearing; every one of them
   bit during the UNNYC work.
4. https://databook.nyc/styleguide — the living reference for what Databook looks like.

## What the sending session already measured — do NOT re-derive

All measured against the LIVE site 2026-08-13, not inferred:

- **The landing is already half on-system.** It loads `databook-tokens.css` AND
  `databook-components.css`; `.db-hero` reads `var(--db-primary)`; the wordmark is
  token orange `#ff941f`; Public Sans is loaded and rendering (verified via
  `document.fonts.check`, not the computed stack). Do not plan an "off Bootstrap"
  migration — that framing is wrong, and was corrected mid-session.
- **The drift is in `app/public/css/style.css`** (served as `/css/style.css`):
  **47 of its 54 distinct hex colours are off-palette.** The big ones, with their
  token targets:

  | drifted | count | replace with |
  |---|---|---|
  | `#f0f0f0` `#f1f1f1` `#f9f9f9` `#e4e4e4` | 17 | the `--db-gray-*` ramp (050/100/200) |
  | `#112f4e` `#0d1c30` `#1a3a5c` `#212533` `#1c1d1f` | 13 | `--db-navy-*` ramp / `--db-primary` |
  | `#4299e1` `#0097cf` | 9 | `--db-accent` `#2491ff` (or `--db-link` where it's a link) |
  | `#767676` `#000000` | 4 | `--db-text-muted` / `--db-gray-900` |
  | `#f5a623` | 1 | `--db-brand` `#ff941f` — but check use: orange is WORDMARK + ANALYSIS ONLY |

- **Bootstrap default gray `#6c757d`** renders on `.briefing-date`,
  `.time-window-count`, `.ticker-agency` — token muted is `#757575`.
- The City Briefing area is flat white, zero radius, no band surfaces — the system
  look (styleguide, and the family's) is cards on a navy-050 band with 8px radius
  and `--db-shadow-sm`.

## Phase 1 — the approved visual change (landing only)

Devin approved this treatment on a live A/B override, 2026-08-13, and invited two
tweaks: *chip weight* and *card shadows* may be softened if they read heavy in
context. Starting CSS, as approved (translate into `style.css` /
`databook-components.css` per this repo's conventions — and read tokens, don't
paste literals; the `:root` block below existed only because the demo was injected
into a live page):

```css
/* page band behind the briefing, cards float on it */
.inner_container { background: var(--db-navy-050); padding-bottom: 24px; }
.time-window {
  background: var(--db-white); border: 1px solid var(--db-navy-100);
  border-radius: var(--db-radius); box-shadow: var(--db-shadow-sm);
  margin: 12px 0; overflow: hidden;
}
.time-window-header {
  background: var(--db-navy-050); border-bottom: 1px solid var(--db-navy-100);
  padding: 10px 14px;
}
.time-window-label { color: var(--db-primary); font-weight: 600; }
.time-window-count { color: var(--db-text-muted); }
/* date chips: navy pills instead of flat Bootstrap-gray text */
.briefing-date {
  background: var(--db-navy-100); color: var(--db-navy-600);
  border-radius: var(--db-radius); padding: 1px 8px; font-weight: 600;
  font-size: 12.5px; border: 0;
}
.ticker-today .briefing-date { background: var(--db-accent-soft); color: var(--db-link); }
.ticker-row { border-bottom: 1px solid var(--db-gray-100); }
.ticker-row:hover { background: var(--db-navy-050); }
.ticker-agency { color: var(--db-text-muted); }
```

Plus the mechanical colour harmonisation per the table above. Two rules from
DATABOOK-STYLE.md that constrain it:

- **Orange is reserved** for the wordmark and Analysis surfaces. If `#f5a623` is
  being used as a general accent somewhere, the fix is `--db-accent`, not
  `--db-brand`.
- **Money/values in navy, green for status only.** Don't "fix" a green that is
  actually status.

### Definition of done, Phase 1

- `grep -oE '#[0-9a-fA-F]{6}' app/public/css/style.css | sort -u` — every value is
  either in the token palette or individually justified in the commit message.
- The briefing renders as cards-on-band per the approved treatment.
- Hero, nav, wordmark, search: byte-identical CSS (they were already right).
- Verify per the KI discipline: computed values via DOM, `document.fonts.ready`
  awaited, controlled before/after on the same probe. **Do not trust screenshots**
  — the browser pane returned stale frames twice during the sending session.

## Phase 2 — adopt the package (plumbing, zero visual change)

Add a `databook` variant to `sarapis/wegovnyc-design-tokens` and have Databook
consume the package instead of its own copy of the token file.

- The package's reference values were **harvested from Databook's token file**, so
  this is value-identical by construction. Prove it anyway: capture every consumed
  token's resolved value before/after (the KI documents the exact method and its
  three traps).
- The variant remaps the SEMANTIC tier only (`--wg-*`); never edit reference
  values in `core.css` — they're shared with wegov.nyc and UNNYC. The
  custom-property substitution trap is real: a semantic already substituted at
  `:root` does not re-resolve when a descendant overrides the reference it came
  from. Remap semantics, on the variant selector.
- Version-bump the package (it's at v0.6.0 after UNNYC's flag accents — see that
  commit, `237b615`, as the template for a variant change).
- Databook is Blade + Bootstrap with **no build step** — decide how it consumes
  the package (git dependency + copy step, or vendored file with a sync check à la
  govoss's `vendor/ctfg`). Flag the choice in the PR rather than deciding silently.
- Update the two KIs: Databook is IN the system as of this change; the 2026-08-05
  "deliberately out" decision is superseded by owner decision 2026-08-13.

## Deploy discipline

This is a production Laravel app with real security history (read the JWT section
of CLAUDE.md). Whatever this repo's convention is — PR, staging, docker compose
rebuild — follow it; do not hand-edit anything on the server. Phase 1 is
CSS-only and independently shippable; do not couple it to Phase 2.

## Explicitly out of scope

- The app's inner pages beyond the shared CSS files (the system already covers them).
- Any rebrand: the identity (navy, orange wordmark, Public Sans) is right and stays.
- The `--db-*` → reference-tier rename discussed in the package's "warts" list —
  separate decision, do not bundle.
- districts (the one surface the 2026-06-17 unification deliberately skipped).
