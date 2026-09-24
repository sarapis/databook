# Product family page — execution plan (top 20 families first)

> `/research/digital-reform/products/{slug}` · endpoint `/oce/licenses/family/{slug}`
> (`api/routers/licenses.py::family`, line ~1536) · view
> `app/resources/views/procurement/digital-reform-license-family.blade.php` (718 lines)
> · controller `ProcurementController::digitalReformLicenseFamily` (passes the whole
> payload as `$fam` plus `$webEstate`).
>
> Written 2026-09-18 for a fresh session to execute. Every figure was measured on
> the local stack, which `scripts/seed-local-derived.sh` makes identical to prod for
> this section. **Owner decision 2026-09-18: do the top 20 families first.** The
> other 794 get the same skeleton with an honest thin state (§2G), not a dossier.

## STATUS — MERGED AND DEPLOYED (2026-09-19)

**PR #412 merged to `main` 2026-09-19 03:44Z** (retargeted from `feat/digital-services`,
which had itself merged the day before) and **live on prod**: verified 2026-09-19 at the
origin (`cf-cache-status: MISS`) — `/oce/licenses/family/microsoft` serves `maker`
(Microsoft Corporation, MSFT), `same_maker`, `sellers.total = 32`, `peers`, `reviewed`,
and the rendered page carries `#section-maker`. So the `license_family_maker` seed was
loaded on prod. Suite on `main`: **1,464 passed** (`#413` added 11 after #412's 1,453).
⚠ #412 was a stacked PR while open and got NO CI; the suite and five headless
verifiers (`verify_family_page`, `verify_products_index`, `verify_uncaught_js`,
`verify_overflow`, `verify_retired_sweep` 0 of 20) were run locally and stated as such.

| phase | state |
|---|---|
| 0 — research the 7 unverified families | done by hand against stable sources (see the citation finding below) |
| 1 — reorder and consolidate | shipped. First spend figure 1,850px -> the header |
| 2 — capability peers | shipped, derived, no seed |
| 3 — maker seed and company card | shipped. `api/seed/license_family_maker.csv`, 20 rows, 76.0% of value |
| 4 — products with evidence grades | shipped, no seed needed |
| 5 — market competitors | **NOT started — owner decision ⚑ C** |
| 6 — `why` / `note` split | **NOT started — owner decision ⚑ D** |

### What shipped after the phases, on owner feedback the same day
- **Family page**: back link "Products"; the Analysis banner became a compact TAG
  (`sub.analysis-tag`) whose visible text keeps "prompts to investigate, not official
  determinations"; description LEFT, maker card RIGHT, tiles, then a sellers/agencies
  rollup — all above a 1440x900 fold on six family shapes (Microsoft 899px, Westlaw
  791px; ⚠ Microsoft's 1px margin is fragile, `verify_family_page` asserts it from
  `window.innerHeight`). One card treatment + a named `is-compact` variant, caveats
  shortened never hidden (only provenance behind `<details>`), 5 rows a page on a
  phone (15,246 -> 13,262px at 390), same-maker cross-links.
- **Products INDEX**: "Products" h1 + the tag (reviewed share inside its disclosure),
  the family table directly under the tiles as the spine (Kind · Function · Sellers
  merged), one-line descriptions, four lenses, a Software licenses section holding the
  awarded-vs-paid charts, then method. Family table 5,052px -> 760px down; copy
  1,887 -> 1,190 words; page 8,418 -> 7,746px. Consolidation badges/filter and the
  Open-source column REMOVED at the owner's word — do not bring them back.

### Still open for the owner
⚑ C market competitors (Phase 5) · ⚑ D the `why`/`note` split (Phase 6) · the
`Microsoft Office` ($18K) / `Citrix Workspace` merge findings (they render as PEERS of
their parent family; merging is a curated-seed decision).

### ⚠⚠ THE EXISTING RESEARCH'S CITATIONS ARE DEAD, so Phase 0 changed shape
Every `Sources:` link in `docs/license-identity-review.md` is a Google grounding
redirect, and **measured 2026-09-18 every one returns 404**. Re-running
`verify_license_identities.py` would mint sources that expire the same way. So
the seven families were researched by hand against stable primary sources
(the maker's own site, SEC/company filings, the City's own press release), and a
guard rejects a `vertexaisearch` URL outright. The `--out` flag the plan asked
for was never needed, because the script was not re-run.

### What the research found that the page can now show
- **AT&T Fleet Management IS Geotab's platform**, resold with AT&T
  connectivity. The City's AT&T Vehicle Tracking ($16.6M) and Geotab ($42.1M)
  families are one underlying product bought two ways at one agency. Still
  deliberately unmerged; the maker card makes the relationship visible instead.
- **Intergraph CAD has had three corporate owners** — Intergraph Corporation,
  then Hexagon AB, then Octave, spun out as an independent company in 2026. The
  City's contract names the owner two steps back, and Octave is not a
  registered City vendor.
- **Broadcom is not a registered City vendor** and neither is CA Technologies,
  so all $17.3M reaches it through Dell, CompuLink and QATC.
- **Talkspace's contract is with a professional corporation** employing
  clinicians, which is the firmest evidence for the classifier's own note that
  this is therapists' time rather than a licence.

### Defects found and fixed in passing
- The view rendered a **typed "88.0% of the value"** that `_reviewed()` was
  written to remove. It was removed from the index and never swept here.
  Measured: the top 20 are 76.0%, the curated seed covers 90.6%.
- **The page and the index gave two seller counts** for one family (6 vs 32).
- A **semicolon inside a `--` DDL comment** broke the builder with an opaque
  asyncpg error.
- The maker card first rendered **LL34 officers as corporate ones**, which said
  Microsoft's chief executive is Dana Barnes. Found only by looking.

### Three of my own checks were wrong before the code was
All three are this repo's documented traps, arriving in the verification:
1. a case-sensitive `innerText` scan missed an uppercased `.lic-tag`, and I
   debugged a working feature for four steps;
2. the same fault had made the verifier's build-vs-buy check **permanently
   blind**, and case-folding it then made it fire on a correct page because the
   sentence explaining the block's absence quotes its heading. Anchored on an
   element id now;
3. two guards were satisfied by a sibling — one by a neighbouring `@else`
   branch, one by a line the mutation left untouched.

### Still open for the owner
See the STATUS block at the top — ⚑ C, ⚑ D, and the Office/Workspace merge finding.
Phase 5 would add products the City does *not* buy, which is editorial and needs a
source per row; the derived peers band already answers "what else does this job".

## 0. Read first

- `CLAUDE.md` sections *"Current status (2026-08-13) — the Software Licenses
  analysis"* and *"Licence family pages: the notice panel now carries money"*.
  The rules that bind this page: only `tier='curated'` renders; a caveat is
  never behind a click; no per-seat arithmetic; a reviewed/auto marker on every
  classification; count before you cap; a `why` never restates the family's own
  scope figures (`test_curated_reasoning_never_restates_the_familys_own_scope`).
- `docs/license-identity-review.md` — the cited identity pass. It holds the
  maker facts for 13 of the 20 (§3.1). **Excluded from the public snapshot**
  (`sync-public.sh` line 97) because its findings are unreviewed.
- `api/tests/test_license_families.py` (69 guards) and
  `test_family_resellers.py` (11). Several anchor on the current markup and WILL
  fire on Phase 1. Re-express each against what the code then does and
  mutation-verify it; never relax one.

Run the suite as
`SPENDING_DATA_BASE=/nonexistent-local-lake BUDGET_REVENUE_BASE=/nonexistent-local-lake pytest api/tests/`
(5s; without those two env vars it reaches S3 and can hang).

## 1. Starting state, measured

Microsoft page: **7,360px** at 1440, **12,532px** at 390, 0 uncaught JS, no
sideways scroll. Render order today:

    h1 · summary · purchase class (+ 3-row mix table + `why` prose) ·
    could the City build it · bought under these names · OSS replacements ·
    what the contracts say it is for · 5 tiles · Agencies | Vendors ·
    Observed on the public web (4 h3) · When these end · Procurement routes ·
    City Record notices · All 24 contracts

The first figure about City spend is **~1,850px** down. No section says who
makes the product, which products the family contains, or what else does the
job. The `products` key is the merged **contract spellings** (`Microsoft ELA`,
`Microsoft Premier Support`), not products.

| asked for | today | coverage (814 families) |
|---|---|---|
| company that makes it | none — `vendors` is who the City PAID; Microsoft's leads with Dell Marketing | 0 |
| products in the family | contract spellings only | real products via web estate on 8 families |
| competitors | the capability link is the City's own competitor set, unlabelled | 99 tagged = 90.6% of value |
| open-source alternatives | built, curated only | 47 = 41.4% of value |
| contracts · when they end | built, two blocks 1,400px apart | all |
| City Record mentions | built (#287/#288), reseller + amount | 430 have ≥1 |
| agencies | built | all |
| vendors selling it | built, ⚠ page shows **6** vendors, index row shows **32 resellers (26 notice-only)** for the same family | all |
| observed on public web | built, fails soft | 8 families |

551 of 814 families hold one contract. Top 20 = **76.0%** of value.

### The 20 families

| # | family | slug | $M | contracts | agencies | vendors | class curated | identity verified | lead vendor (supplier id) |
|---:|---|---|---:|---:|---:|---:|---|---|---|
| 1 | Microsoft | `microsoft` | 643.6 | 24 | 17 | 6 | yes | yes | DELL MARKETING LP; maker MICROSOFT CORPORATION is vendor **1632138** |
| 2 | Axon | `axon` | 112.5 | 7 | 4 | 1 | yes | yes | AXON ENTERPRISE INC 1647619 |
| 3 | Intergraph CAD | `intergraph-cad` | 65.1 | 1 | 1 | 1 | no | yes | INTERGRAPH CORPORATION 1643612 |
| 4 | NICE | `nice` | 57.4 | 5 | 3 | 2 | yes | yes | NICE SYSTEMS INCORPORATED 1742794 |
| 5 | Casebuilder | `casebuilder` | 46.1 | 1 | 1 | 1 | no | yes | SoundThinking Inc 1654198 |
| 6 | SoundThinking (ShotSpotter) | `soundthinking-shotspotter` | 43.9 | 2 | 1 | 1 | yes | yes | SoundThinking Inc 1654198 |
| 7 | Summer | `summer` | 43.4 | 1 | 1 | 1 | no | **no** | Summer PBC 2024688 |
| 8 | Geotab | `geotab` | 42.1 | 3 | 1 | 2 | no | **no** | AT&T MOBILITY LLC; GEOTAB USA INC 1958123 |
| 9 | Ivalua | `ivalua` | 37.9 | 1 | 1 | 1 | no | yes | Ivalua Inc 1845404 |
| 10 | ConvergeOne Call Center Solution | `convergeone-call-center-solution` | 30.3 | 1 | 1 | 1 | no | yes | CONVERGEONE GOVERNMENT SOLUTIONS LLC 1872405 |
| 11 | Itineris UMAX | `itineris-umax` | 29.5 | 1 | 1 | 1 | no | **no** | ITINERIS NA INC 1879546 |
| 12 | Citrix | `citrix` | 27.5 | 15 | 9 | 8 | yes | yes | CLOUD SOFTWARE GROUP, INC. 1624955 |
| 13 | Talkspace | `talkspace` | 26.0 | 1 | 1 | 1 | no | **no** | Talkspace Medical Services NY PC 1995866 |
| 14 | LexisNexis | `lexisnexis` | 25.9 | 8 | 3 | 3 | yes | **no** | RELX INC 1647609 (+ Risk Solutions, VitalChek) |
| 15 | Cyclomedia | `cyclomedia` | 20.0 | 1 | 1 | 1 | no | yes | CYCLOMEDIA TECHNOLOGY INC 1656606 |
| 16 | AssetWorks | `assetworks` | 18.5 | 3 | 2 | 1 | no | **no** | ASSETWORKS INC 1649691 |
| 17 | Gartner | `gartner` | 17.5 | 2 | 2 | 1 | no | yes | GARTNER INC 1629347 |
| 18 | Broadcom (CA) | `broadcom-ca` | 17.3 | 4 | 2 | 3 | yes | yes | DELL MARKETING LP; COMPULINK; QATC — maker Broadcom is NOT among them |
| 19 | AT&T Vehicle Tracking | `at-t-vehicle-tracking` | 16.6 | 2 | 1 | 1 | yes | **no** | AT&T MOBILITY LLC 1624688 |
| 20 | Salesforce | `salesforce` | 16.1 | 4 | 4 | 3 | no | yes | CENTER FOR NYC NEIGHBORHOODS; CARAHSOFT; MTX — maker Salesforce, Inc. is NOT among them |

Seven need identity research (§3.1). Three families (Microsoft, Broadcom,
Salesforce) are bought through resellers, so their maker is not one of their
vendors — that is what the maker concept exists to say. Two are not software
products (ConvergeOne is a managed NICE CXone service; Gartner is research
content) and one is a fleet-telematics *bundle* (AT&T Vehicle Tracking) — the
card must be able to say "service" or "bundle", not force a maker.

⚠ Casebuilder and SoundThinking share one maker and vendor; the identity pass
records Casebuilder as *"CrimeCenter and ShotSpotter Investigate"*. They stay
two families (owner decision, CLAUDE.md) and the maker card links each to the
other under "Same maker".

## 2. The page, redesigned

Left sidebar TOC (`.db-toc`, the pattern in `vendor_profile.blade.php` and
`partials/capital_toc.blade.php`), content in this order.

**A. Header** — `h1` · one-line what-it-is (curated or AI summary, marker
unchanged) · chip row: purchase class · function (linked) · reviewed/auto.

**B. The company behind it** *(Phase 3)* — a card: maker · parent / formerly ·
HQ · ticker or private · website · **"In PASSPort as"** → vendor profile when
the maker has a supplier id, else *"not a registered City vendor; bought
through N resellers"*. When the maker IS a PASSPort vendor the card hydrates
address, revenue band, ticker and LL34 principal officers from the vendor
endpoint (`/oce/vendor/{id}` → `passport.entity`, `doing_business.people`),
never retyped into the seed. No curated row → *"Maker not yet identified"*.

**C. Products in this family** *(Phase 4)* — (1) *Bought under these names*:
the existing spelling chips, demoted to a `<details>` (they are merge
evidence); (2) *Products likely in scope*, each with a visible evidence grade,
strongest first: `named on a contract` · `recorded purpose` · `City Record
notice` · `observed on a City host` · `curated: in the agreement's published
scope`.

**D. What else does this job** — (1) *What the City already buys for this
job*: the capability peers, DERIVED from the same data the capability page
serves, linked, with value and agency count *(Phase 2)*; (2) *Market
competitors*: curated with a rendered source *(Phase 5)*; (3) *Open-source
replacements*: the existing block, unchanged.

**E. The City's records** *(Phase 1)* — tiles · **Related contracts** with an
end-year column and a one-line calendar strip above it (*"1 of 24 expires
before 2030 ($57.0M, 2027); 21 have ended"*) so *When these end* has one home
· **Agencies buying it** | **Who sells it** — ONE list through
`modules/resellers.merge` (contract vendors first with profile links, † for
notice-only), so the page and the index agree · **City Record notices** ·
**Observed on the public web** · procurement routes as a chip strip under the
tiles, not a table.

**F. How we classified it** *(Phase 1)* — purchase class + mix table + lever ·
build-vs-buy distribution with the 75% caveat · recorded purposes · merge
evidence · tier status. Moved together to the end; every existing caveat stays
visible (not behind a click).

**G. Thin families** — same skeleton; B/C/D collapse to what exists; no empty
headings.

## 3. Phases

Each phase is its own PR, lands with before/after measured on the RENDERED
page (height at 1440 and 390, px-to-first-figure, section order, 0 uncaught
JS, no sideways scroll) and the suite green. Owner reviews the deltas.

### Phase 0 — research the seven unverified families (no code)

Run the identity pass for Summer, Geotab, Itineris UMAX, Talkspace,
LexisNexis, AssetWorks, AT&T Vehicle Tracking.

⚠⚠ **`verify_license_identities.py --family X` OVERWRITES
`docs/license-identity-review.md` with ONLY the named families** (line ~285
opens the path with `"w"`). Running it naively destroys the 40-family record.
Either add an `--out` argument first, or run it in a scratch checkout and merge
the seven sections in by hand. Cost ≈ $0.05/family on `gemini-3.5-flash`; do
not switch to the lite model (returns no grounding).

⚠ Every `Sources:` link in that doc is a `vertexaisearch…/grounding-api-redirect`
URL. **Resolve each to its real URL before it enters a seed** (`curl -sI` and
read `Location`); a redirect through Google is not a citation a public page can
carry.

Done when: all 20 have `Is` / `Same vendor as` / `Renamed from` / resolved
sources, recorded in the review doc.

### Phase 1 — reorder and consolidate (no new claims)

Files: the view; `licenses.py::family` (one new key); `test_license_families.py`.

1. Add the TOC. Copy the shape from `vendor_profile.blade.php`; anchor ids on
   every `h2`. `px-0 px-md-3` on the content column (a `d-none` sidebar still
   costs mobile width — measured 312px on the capital profile).
2. Header card (§A). Move the class box, build-vs-buy box, spellings and
   purposes to §F at the bottom, unchanged in content.
3. **Who sells it.** In `family()` add `"sellers": resellers.merge(vendor_names,
   notice_rows)` using the family's value-ranked contract vendors and the
   notice rows already fetched by `_notices_for_family`. Render it in place of
   *Vendors selling it*: contract vendors carry `vendor_id` links (through the
   existing `vendorids.unique_map`, never a name join — 48 names resolve to >1
   id), notice-only names carry †. State the three counts (`total / contract /
   notice_only`). `test_family_resellers.py::test_the_router_merges_through_the_one_owner`
   already pins the index; extend it to the family endpoint.
4. Fold the calendar. Keep `by_year` in the payload; render it as the one-line
   strip above the contracts table (it already serves `ended` and
   `no_end_date`, so the sentence discloses all three buckets — the
   `_by_year` guard `test_the_calendar_discloses_the_contracts_it_drops` must
   keep passing on the new sentence). Add an *Ends* column to the contracts
   table (`end_date`, `expiring` badge already per row).
5. Routes → chip strip from `by_method` under the tiles.
6. Web-estate panel: unchanged, keep its independent-audit label.

Guards to add (mutation-verified, landing probe = "mutated text is present"):
- section ORDER: the h2 for *The City's records* precedes the h2 for *How we
  classified it*; the class-mix table is below the tiles.
- the seller list on the page is built from the served `sellers` key, not from
  `vendors` (assert the view echoes `sellers` and the `vendors` block is gone).
- the calendar strip names all three buckets (contracts + ended + no_end_date
  == `summary.contracts`).

Expect to re-express: `test_family_pages_are_published_with_their_provenance_markers`,
`test_replaceability_is_shown_as_a_distribution_not_a_verdict`,
`test_the_family_page_states_a_mixed_class_instead_of_absorbing_it`,
`test_the_class_tier_is_surfaced…`, `test_capped_lists_carry_their_full_length`
(the notices cap sentence), `test_views_read_api_keys_with_their_stored_spelling`.

Done when: Microsoft page ≤ ~5,500px at 1440, first tile ≤ ~700px from top,
`verify_overflow.py`, `verify_uncaught_js.py`, `verify_retired_sweep.py`
(0 of 20) green, all 20 slugs return 200 with the same `summary.contracts` as
before.

### Phase 2 — capability peers (derived, no seed)

In `family()`: when `fam_class.capability` is set, compute the other families
with the same tag from `data["rows"]` via `_agg(rows, "family")` — the same
call `capability()` makes — and serve `"peers": [{family, slug, value,
contracts, agencies}]` sorted by value, capped at 10 with `peers_total`.
Render as §D1 with the capability page link as "see all N".

Guards: `peers` never contains the family itself; `peers_total` equals the
capability endpoint's `summary.products - 1` for the same tag (reconcile in
`scripts/headless/verify_family_page.py`, new — ⚠ `verify_family.py` already
exists and checks CAPITAL budget-line families; do not reuse the name).

### Phase 3 — maker seed and company card

New seed `api/seed/license_family_maker.csv` (comment header, quoted CSV):

    family, maker, maker_kind, maker_vendor_id, parent, formerly, hq, ticker,
    website, source_url, as_of, why, note
      maker_kind ∈ company | service-provider | bundle
      maker_vendor_id: PASSPort supplier id, blank when the maker is not a City vendor

Bootstrap the 20 rows from the identity review (13) plus Phase 0 (7). Known
values to carry: Axon ← TASER International; Intergraph CAD → Hexagon, now
Octave; NICE Ltd.; Casebuilder + SoundThinking → SoundThinking, Inc. (formerly
ShotSpotter, Inc.); Ivalua ← Directworks; ConvergeOne → C1, a *service* over
NICE CXone; Citrix → Cloud Software Group; Cyclomedia Technology B.V.;
Gartner, Inc., *service*; Broadcom ← CA Technologies; Salesforce, Inc.;
Microsoft → vendor 1632138 (ticker MSFT, Redmond, in PASSPort).
`maker_vendor_id` must be checked against `vendors."PASSPort Supplier-ID"`
on the local DB before committing; a wrong id links a company card to a
different company.

Loader: `build_license_procurement.py` — a `license_family_maker` table beside
`license_family_class` (DDL in the same block, `read_seed`, load under
`tier='curated'`). Serve through `_load()` as `data["makers"]` keyed on family;
`family()` adds `"maker": makers.get(name)`. In the controller, when
`maker_vendor_id` is set, fetch `/oce/vendor/{id}` (`reqOCE`, fail soft to
null) and pass `$makerVendor` — ⚠ `ProcurementController` names every view-data
key; a key the view reads and the controller does not pass degrades silently.

Render §B. **Only a curated row renders**; absent → "Maker not yet identified".
`maker_kind = service-provider` renders *"a service, delivered by …"*; `bundle`
renders *"a bundle sold by …"* (AT&T Vehicle Tracking).

Guards: seed well-formed (`source_url` and `as_of` required, mirrors
`test_rate_card_seed_requires_a_source_and_a_date`); the seed is CONSUMED
(mirrors `test_the_rate_card_seed_is_actually_consumed` — a seed nothing reads
has happened here before); `maker_vendor_id` values resolve through
`unique_map`; the card renders nothing for a family with no row (mutation:
drop a row, assert the empty-state string); `why` does not restate the
family's own figures (extend the existing guard to the new seed).

Add `license_family_maker` to `scripts/seed-local-derived.sh`'s table list.
⚠ **Prod gets the seed only when `build_license_procurement.py --apply` runs
there** — editing the CSV changes nothing served (the #235 lesson). Put it in
the deploy note.

### Phase 4 — products seed and evidence grades

New seed `api/seed/license_family_products.csv`:

    family, product, evidence, source_url, why
      evidence ∈ contract-name | recorded-purpose | notice | web-observed | curated-scope

Three grades can be pre-filled from data and only need confirming: contract
spellings that name a product (`Microsoft SQL Server`), recorded purposes that
name one (`Database management`), web-estate components (`Microsoft Azure`,
`Entra`, `IIS`, `Power BI`). `curated-scope` rows (what an ELA covers) carry a
source. Table + `_load()` key + `"products_in_scope"` on `family()`, rendered
as §C(2) with the grade as a badge; the spellings chips move into a `<details>`.

Guards: every row's `evidence` is in the vocabulary; a `curated-scope` row has
a `source_url`; the web-observed rows are labelled as the audit's inference
(the web-estate panel's existing wording, reused not retyped).

### Phase 5 — market competitors

New seed `api/seed/license_family_competitors.csv`:

    family, competitor, competitor_family, source_url, why
      competitor_family: our slug when the City also buys it, else blank

Curated only, one public source per row (an analyst report, the vendor's own
comparison page, a government procurement record naming them as alternatives).
Renders as §D2 under the derived peers. Where `competitor_family` is set, link
to that family page. Guards mirror Phase 3's.

### Phase 6 — deferred: `why` / `note` split

The existing seed `why` columns render verbatim and much of the text explains
past defects of ours (*"…what produced a false 50.3% support-maintenance
headline"*; *"This row exists to stop the match being re-derived as a
saving"*). Split into public `why` + internal `note` across
`license_family_class.csv` (99), `license_replacement_candidates.csv` (63),
`license_family_curated.csv` (119). Hand pass required afterwards (#240: automated
edits to hand-written prose leave awkward openings). Own PR; ⚑ owner to say go.

## 4. Assumptions the executing session proceeds under

Stated here so they can be overturned in one line rather than discovered late.

1. **Curated only renders** for maker, products-in-scope and competitors — the
   OSS candidates' rule (#146). A wrong claim about a named company is the
   harmful direction. If the owner wants AI rows visible they need the Data
   lens's *automatic · unreviewed* banner and a guard that fails without it.
2. **Competitors need a rendered source** per row (the Gartner provenance
   rule). The derived capability peers need no source; they are our data.
3. **The maker card hydrates from the vendor endpoint** rather than duplicating
   company facts in the seed. One owner for company facts.
4. Phase 6 waits for the owner.

## 5. Traps that apply here (all already paid for once)

- `<x-db.stat>` takes its value as the SLOT, not `:value`.
- A Blade comment eats the newline after it; `@php` inside a Blade comment
  pairs with the next real `@endphp`; a directive glued to a word char does
  not compile. Run `php scripts/blade-lint.php` and RENDER the page.
- Locally, `resources/views` and `public` are bind-mounted; controllers,
  routes and `api/` are NOT. A controller or router change needs
  `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build app api`
  (⚠ without `-f docker-compose.local.yml` the bind mounts vanish and Blade
  edits stop reaching the page), then `view:clear && config:clear`. Opcache
  holds compiled Blade across `view:clear`; mutation-test against the SERVED
  HTML after `docker compose restart app`.
- `conftest.py` mocks the `modules` package; load `resellers`/`vendorids`/
  `licenseclass` by path in tests.
- `innerText` applies `text-transform`; any label scan must be case-folded.
- A guard that searches a region is satisfied by a sibling: count sites or
  slice per block.
- A mutation must REMOVE the property; the landing probe asserts the mutated
  text is present, never that the original is absent.
- New `docs/*-PLAN.md` files publish by default via `sync-public.sh`; this
  file names no host or credential. The identity review stays excluded.

## 6. Deploy notes for whoever ships it

1. `git pull` on the box; `docker compose up -d --build app api`; wait for the
   api to leave `starting`.
2. `docker compose exec -T api python build_license_procurement.py --apply`
   — loads the new seeds. Without this step the code ships, every page
   renders, and every card reads "not yet identified".
3. `docker compose exec -T app php artisan view:clear && … config:clear`.
4. Verify on prod: all 20 slugs 200; Microsoft's card names Microsoft
   Corporation and links to vendor 1632138; Broadcom's card says the maker is
   not among its vendors; `verify_retired_sweep.py` 0 of 20; 0 uncaught JS.
5. `bash scripts/prod-smoke.sh`.
