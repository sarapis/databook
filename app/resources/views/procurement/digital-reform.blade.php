@extends('layout')

@section('head')
<style>
    /* Digital Services Analysis: Overview - page glue over the db-* design system.
       ⚠ This block is emitted by @yield('head'), which the layout renders BEFORE
       the stylesheet links, so an equal-specificity rule here LOSES to
       databook-components.css. Every selector below is a name that file does not
       carry, which is why they take effect at all. */
    .db-page-lead { max-width: 68ch; }
    .ds-scope-note summary { cursor: pointer; }

    /* ⚠ THE COMPOSITION BAR'S CSS WAS DELETED WITH ITS MARKUP (2026-09-16).
       `.ds-bar`, `.ds-seg-*`, `.ds-legend`, `.ds-sib`, `.ds-cta` and `.ds-chip`
       styled the stacked bar and the numbered lens cards, both of which the
       band redesign replaced. Verified dead in BOTH directions before removal —
       nothing in the views, the partials or the JS emits them. Dead CSS that
       still reads as live is worse than duplicated CSS, because the next reader
       believes it. */

    /* Band, ranked-list, legend and chart-note rules: see the ds-styles partial,
       which the Contracts page shares. */
    /* A tile label that is also a way in. It keeps the label's own colour and
       weight — a blue link inside a stat label reads as body copy dropped into
       a figure — and shows its nature on hover and focus. */
    .ds-tile-link { color: inherit; text-decoration: none; }
    .ds-tile-link:hover, .ds-tile-link:focus { text-decoration: underline; }

</style>
@include('procurement.partials.ds-styles')
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    $comp        = $composition ?? [];
    $segments    = $comp['segments'] ?? [];
    $bar         = $comp['bar'] ?? [];
    $compTotals  = $comp['totals'] ?? [];
    $segSel      = $contracts['segment'] ?? '';
    $segSelSlug  = $contracts['segment_slug'] ?? '';
    // The licence segment's own function mix, carried on its segment row.
    $licSeg      = null;
    foreach ($segments as $s) { if (!empty($s['functions'])) { $licSeg = $s; } }
    // Precomputed so no conditional phrase is glued to a directive: a Blade
    // directive touching a word character is not compiled at all and the page 500s.
    $barFloorPct = ($compTotals['bar_floor_share'] ?? 0.01) * 100;
@endphp

{{-- ============ STORYBOARD ============
     Full-bleed scrolling introduction (design_handoff_digital_services_storyboard),
     opening the page. Deliberately outside the .container/.inner_container below --
     every beat is full-width and centers its own content column. The rest of the
     page's original content follows it, then the "Your turn to explore" nav cards
     at the very end. --}}
@include('procurement.partials.digital-services-storyboard')

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <h1>Overview</h1>
        {{-- ⚠ THE SECTION'S FRAMING, owner 2026-09-16, near-verbatim. Plainer and
             more first-person than the copy it replaces: it names WHERE the data
             comes from and admits the limits of the method in the same breath,
             which is the register the rest of the section should follow. --}}
        <p class="db-page-lead" style="max-width: 68ch;">
            New York City spends huge amounts of time and money on technologies for its various
            agencies. By combining disparate datasets from
            <a href="https://opendata.cityofnewyork.us/" target="_blank" rel="noopener">NYC Open Data</a>,
            the Mayor's Office of Contract Services and
            <a href="https://www.checkbooknyc.com/" target="_blank" rel="noopener">CheckbookNYC</a>,
            some insider knowledge and some AI analysis, we're doing our best to better
            understand the city's technology ecosystem.
        </p>
        @include('sub.analysis-banner')
        @include('sub.digital-scope-note', ['scope' => $scope ?? []])

        {{-- ============ SECTION SEARCH (Phase 6). Scoped to this section: the
             site-wide box returns notices, people and schools, none of which this
             section is about. ============ --}}
        <div class="db-search mb-4" style="position: relative; max-width: 640px;">
            <i class="bi bi-search"></i>
            <input type="search" id="dsSearch" autocomplete="off"
                   placeholder="Search products, vendors, agencies and contracts&hellip;"
                   aria-label="Search the Digital Services section"
                   aria-controls="dsSearchResults" role="combobox" aria-expanded="false">
            <div id="dsSearchResults" role="listbox"
                 style="display:none; position:absolute; z-index:40; left:0; right:0; top:100%;
                        background:var(--db-surface,#fff); border:1px solid var(--db-border);
                        border-radius:var(--db-radius-sm); box-shadow:var(--db-shadow-md);
                        max-height:420px; overflow-y:auto;"></div>
        </div>

        {{-- Headline tiles. ⚠ Each carries its active/ended split, because the totals
             are all-time and a bare figure reads as current exposure: measured, most
             of these contracts have already ended. --}}
        <div class="db-stat-grid mt-3 mb-4">
            <div class="db-stat">
                <div class="db-stat-label"><a href="{{ route('research.digital-reform.contracts') }}" class="ds-tile-link">Technology contracts</a></div>
                <div class="db-stat-value">{{ number_format($stats['count'] ?? 0) }}</div>
                <div class="db-stat-sub">
                    {{ number_format($stats['active_count'] ?? 0) }} not known to have ended &middot;
                    {{ number_format($stats['ended_count'] ?? 0) }} ended
                </div>
            </div>
            {{-- ⚠⚠ COMMITTED MONEY, NOT THE BLENDED TOTAL — owner decision 2026-09-15.
                 This read "Total value, all time" over `total`, which sums master-agreement
                 CEILINGS into money the City has agreed to pay, while the by-start-year
                 chart below states in its own copy that ceilings are "not money committed,
                 so it is not in these bars". One sum, two claims, one page — #294.
                 ⚠ The CONTRACT COUNT beside it still includes masters, deliberately: #261
                 settled that masters stay in the queue and only the SUMMING stops.
                 ⚠ The running/ended split is COMMITTED-SCOPED, not the all-contracts one —
                 a headline over one population with a sub-line over another is
                 /procurement's "no two of the four tiles shared a denominator". --}}
            <div class="db-stat is-accent">
                <div class="db-stat-label">Committed value, all time</div>
                <div class="db-stat-value">${{ number_format(($stats['committed_total'] ?? 0) / 1000000, 0) }}M</div>
                <div class="db-stat-sub">
                    ${{ number_format(($stats['committed_active_total'] ?? 0) / 1000000, 0) }}M still running &middot;
                    ${{ number_format(($stats['committed_ended_total'] ?? 0) / 1000000, 0) }}M ended
                </div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><a href="{{ route('research.digital-reform.vendors') }}" class="ds-tile-link">Vendors</a></div>
                <div class="db-stat-value">{{ number_format($stats['vendor_count'] ?? 0) }}</div>
                <div class="db-stat-sub">Hold at least one confirmed technology contract</div>
            </div>
        </div>

        {{-- ⚠⚠ THE CEILING DISCLOSURE, AND IT SITS OUTSIDE `.db-stat-grid` ON
             PURPOSE. A <p> inside that grid becomes a GRID ITEM: #400 measured
             exactly that at 186x110px against 1376x21 for the same sentence
             placed outside. Same reason `schoolStatsNote` lives outside its grid.
             ⚠ And this exists because the page CONTRADICTED ITSELF: the
             by-start-year chart below states that master ceilings are "headroom
             ... not money committed, so it is not in these bars", while the tile
             above summed that same money into "Total value". Measured
             2026-09-15 while reviewing the Staffing/consulting segment, whose
             largest cluster is DoITT's SI panel — thirteen contracts at exactly
             $50.00M apiece, every one of them a per-vendor cap.
             ⚠ The two figures are shown SEPARATELY and never added, which is the
             #261/#294 rule; the headline stays `total` so no published figure
             moves without the owner deciding it should. --}}
        @php
            $stCeil = (float) ($stats['ceiling_total'] ?? 0);
            $stComm = (float) ($stats['committed_total'] ?? 0);
            $stMast = (int) ($stats['master_count'] ?? 0);
        @endphp
        @if($stCeil > 0)
        <p class="text-muted mb-4" style="font-size: var(--db-text-2xs);" id="ceilingNote">
            <strong>That counts the {{ number_format(($stats['count'] ?? 0) - $stMast) }}
            ordinary contracts only.</strong>
            A further <strong>${{ number_format($stCeil / 1000000, 0) }}M</strong> is the ceiling on
            {{ number_format($stMast) }} master agreements &mdash; headroom agencies buy against,
            drawn down under other contract ids, so it is not money the City has agreed to pay.
            Those agreements are still counted in the contract total beside it. The two figures
            answer different questions and are not added anywhere on this page.
            <a href="{{ route('research.digital-reform.agreements') }}">See the agreements</a>.
        </p>
        @endif

        {{-- ============ THE COMPOSITION: this page's argument ============ --}}

        {{-- ============================================================
             ONE BAND PER SUBMENU ITEM (owner, 2026-09-16). Each band says what
             its page answers, shows a few figures drawn from THAT PAGE'S OWN
             endpoint, and links in.

             ⚠⚠ THE OVERVIEW STILL COMPUTES NOTHING. Every figure below is a key
             the linked page serves; the only thing done here is the
             presentational fold to five slices plus a NAMED remainder
             (ProcurementController::_slices). Two independent computations of
             one number is what produced the 243-vs-242 and 1,195-vs-690 defects
             this section has already paid for.
             ============================================================ --}}
        @php
            // ⚠ ONE formatter for every figure in these bands, byte-identical to
            // the Products page's own, so a number formatted here reads exactly
            // as it does on the page it links to.
            $fmtM = function ($v) {
                $v = (float) $v;
                if ($v >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
                if ($v >= 1000000)    return '$' . number_format($v / 1000000, 1) . 'M';
                if ($v >= 1000)       return '$' . number_format($v / 1000, 0) . 'K';
                return '$' . number_format($v, 0);
            };
            $pb = $prodBlocks ?? null;
        @endphp

        {{-- ============ 1. CONTRACTS ============ --}}
        <section class="ds-band" id="s-contracts" aria-labelledby="s-contracts-h">
            <div class="ds-band-head">
                <div>
                    <h2 id="s-contracts-h" class="ds-band-title">Contracts</h2>
                    <p class="ds-band-lead">
                        Every technology contract we can identify &mdash; which agency signed it,
                        what kind of thing it buys, and when the money was committed.
                        {{-- ⚠ THE RENEWAL FIGURE SURVIVED THE REDESIGN. It was the whole
                             point of the lens card these bands replaced, and it is the one
                             number on this page a reader can act on. Served by the
                             Contracts page's own summary, never recomputed. --}}
                        @if(($expiring['summary']['count'] ?? 0) > 0)
                            <strong>{{ number_format($expiring['summary']['count']) }}</strong>
                            of them ({{ $fmtM($expiring['summary']['committed_value'] ?? $expiring['summary']['total_value'] ?? 0) }})
                            expire before 2030.
                        @endif
                    </p>
                </div>
                <a href="{{ route('research.digital-reform.contracts') }}" class="db-btn db-btn-primary ds-band-cta">
                    All contracts <i class="bi bi-arrow-right"></i>
                </a>
            </div>
            @include('procurement.partials.contracts-book')
        </div>
        </section>

        {{-- ============ 2. PRODUCTS ============ --}}
        <section class="ds-band" id="s-products" aria-labelledby="s-products-h">
            <div class="ds-band-head">
                <div>
                    <h2 id="s-products-h" class="ds-band-title">Products</h2>
                    <p class="ds-band-lead">
                        The software and subscriptions underneath those contracts, grouped into
                        product families so the same thing bought ten times reads as one thing.
                    </p>
                </div>
                <a href="{{ route('research.digital-reform.products') }}" class="db-btn db-btn-primary ds-band-cta">
                    All products <i class="bi bi-arrow-right"></i>
                </a>
            </div>
            @include('procurement.partials.products-book')
        </section>

        {{-- ============ 3. DATA ============ --}}
        <section class="ds-band" id="s-data" aria-labelledby="s-data-h">
            <div class="ds-band-head">
                <div>
                    <h2 id="s-data-h" class="ds-band-title">Data</h2>
                    <p class="ds-band-lead">
                        What the City buys <em>as</em> data &mdash; somebody else's imagery, records or
                        content, rented by subscription.
                    </p>
                </div>
                <a href="{{ route('research.digital-reform.data') }}" class="db-btn db-btn-primary ds-band-cta">
                    The data lens <i class="bi bi-arrow-right"></i>
                </a>
            </div>
            @include('procurement.partials.data-book')
        </section>

        {{-- ============ 4. AGREEMENTS ============ --}}
        <section class="ds-band" id="s-agreements" aria-labelledby="s-agreements-h">
            <div class="ds-band-head">
                <div>
                    <h2 id="s-agreements-h" class="ds-band-title">Agreements</h2>
                    <p class="ds-band-lead">
                        Citywide agreements agencies buy against. Each figure is a
                        <strong>ceiling</strong> &mdash; headroom, not money committed &mdash; so it is
                        never added to the totals above.
                    </p>
                </div>
                <a href="{{ route('research.digital-reform.agreements') }}" class="db-btn db-btn-primary ds-band-cta">
                    All agreements <i class="bi bi-arrow-right"></i>
                </a>
            </div>
            @include('procurement.partials.agreements-book')
        </section>

        {{-- ============ 5. VENDORS ============ --}}
        <section class="ds-band" id="s-vendors" aria-labelledby="s-vendors-h">
            <div class="ds-band-head">
                <div>
                    <h2 id="s-vendors-h" class="ds-band-title">Vendors</h2>
                    <p class="ds-band-lead">
                        Who the City buys technology from, ranked by what it has been awarded.
                    </p>
                </div>
                <a href="{{ route('research.digital-reform.vendors') }}" class="db-btn db-btn-primary ds-band-cta">
                    All vendors <i class="bi bi-arrow-right"></i>
                </a>
            </div>
            @include('procurement.partials.vendors-book')
        </section>

        {{-- Research Notes --}}
        <div class="db-alert db-alert-info mt-4" role="alert">
            <i class="bi bi-info-circle"></i>
            <div class="db-alert-body">
                <strong>Research and Methodology Notes</strong>
                <p class="mb-0">
                    Whether a contract is technology, whether it is a licence and what function it
                    serves are produced by an AI pass over each contract's title, purpose and
                    related City Record notices &mdash; a prompt to investigate, not a
                    determination. Where a figure has been reviewed by hand, the section says so.
                    Function categories are the classifier's own free-text buckets and carry no
                    curation layer, which is why corrections are recorded per contract in a
                    version-controlled file rather than edited into a page.
                    Thanks to the
                    <a href="https://github.com/htownley/nyc-tech-spending" target="_blank" rel="noopener" class="fw-semibold">nyc-tech-spending</a>
                    project, whose vendor tags and contract-analysis methodology this section grew
                    out of and has now replaced with a full-population classification.
                </p>
            </div>
        </div>

    </div> <!-- /.container -->
</div> <!-- /.inner_container -->

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="{{ asset('js/digital-services-storyboard.js') }}?v={{ filemtime(public_path('js/digital-services-storyboard.js')) }}"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {
    DBChart.apply(Chart);
    const currencyFmt = (val) => '$' + val.toLocaleString(undefined, { maximumFractionDigits: 0 });
    const chartData = @json($charts ?? []);

    {{-- ⚠ The start-year chart comes BEFORE the pie factory, as it always did:
         the band's two ovPie() calls in it resolve through function hoisting. --}}
    @include('procurement.partials.contracts-book-js')
    @include('procurement.partials.slice-pies-js')
    @include('procurement.partials.products-book-js')
    @include('procurement.partials.data-book-js')
    @include('procurement.partials.vendors-book-js')

    @include('procurement.partials.agreements-book-js')

    // ⚠ AFTER the pies, so a chart that failed to build cannot leave its legend
    // unpainted while the others are fine — they share one resolver and one pass.
    paintLegends();

    // ---- Section search (Phase 6) --------------------------------------
    // ⚠ EVERY GROUP IS RENDERED, including empty ones, because the API returns
    // them all. "Nothing matched" and "that arm is broken" were byte-identical
    // for eight weeks in the site-wide search (#256); here they are not.
    (function () {
        const box = document.getElementById('dsSearch');
        const out = document.getElementById('dsSearchResults');
        if (!box || !out) { return; }
        let timer = null, lastQ = '';

        const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g,
            (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

        function close() { out.style.display = 'none'; box.setAttribute('aria-expanded', 'false'); }

        function render(data) {
            const groups = (data.groups || []).filter(g => (g.count || 0) > 0);
            if (data.unavailable) {
                out.innerHTML = '<div class="p-3 text-muted small">Search is unavailable right now.</div>';
            } else if (!groups.length) {
                out.innerHTML = '<div class="p-3 text-muted small">No matches in this section for &ldquo;'
                    + esc(data.query) + '&rdquo;.</div>';
            } else {
                out.innerHTML = groups.map(g =>
                    '<div class="px-3 pt-2 pb-1 text-muted" style="font-size:var(--db-text-2xs);'
                    + 'text-transform:uppercase;letter-spacing:.04em;">' + esc(g.label) + '</div>'
                    + g.rows.map(r => {
                        const meta = r.meta ? '<span class="text-muted small"> &middot; ' + esc(r.meta) + '</span>' : '';
                        const body = esc(r.label) + meta;
                        return r.url
                            ? '<a class="d-block px-3 py-1 text-decoration-none" role="option" href="' + esc(r.url) + '">' + body + '</a>'
                            // ⚠ No link: an ambiguous vendor name resolves to more
                            // than one supplier id, so we show it rather than guess.
                            : '<div class="px-3 py-1" role="option">' + body + '</div>';
                    }).join('')
                ).join('');
            }
            out.style.display = 'block';
            box.setAttribute('aria-expanded', 'true');
        }

        box.addEventListener('input', function () {
            const q = box.value.trim();
            if (q === lastQ) { return; }
            lastQ = q;
            clearTimeout(timer);
            if (q.length < 2) { close(); return; }
            timer = setTimeout(function () {
                fetch('{{ route('research.digital-reform.search') }}?q=' + encodeURIComponent(q))
                    .then(r => r.json()).then(render)
                    .catch(() => { out.innerHTML =
                        '<div class="p-3 text-muted small">Search is unavailable right now.</div>';
                        out.style.display = 'block'; });
            }, 200);
        });
        box.addEventListener('keydown', (e) => { if (e.key === 'Escape') { close(); } });
        document.addEventListener('click', (e) => {
            if (!e.target.closest || !e.target.closest('.db-search')) { close(); }
        });
    })();
});
</script>
@endsection
