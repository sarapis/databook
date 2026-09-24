@extends('layout')

@section('head')
<style>
    /* Digital Services Analysis: the data lens (section plan §5c Phase A).
       ⚠⚠ NO `.db-page-lead { max-width: none }` HERE, AND THE REASON IS
       MEASURED. @yield('head') is emitted BEFORE the stylesheet links, so an
       inline rule at equal specificity LOSES to databook-components.css — the
       documented responsive.css trap, one mechanism over. Verified in the
       browser: document.styleSheets lists this block first and components.css
       second, and the lead computes 728px (70ch) either way.
       ⚠ digital-reform-master-agreements.blade.php carries that rule and it is
       inert there too; left alone rather than silently restyling a page this
       change is not about. */
    /* The two-column split is the whole point of the tools table, so the pair
       reads as one cell group rather than two unrelated money columns. */
    .dl-split-a { border-left: 3px solid var(--db-border); }
    /* The agency and product tables share a row, so on a desktop column they can
       be wider than their box. They SCROLL rather than clip: the section's
       wrapper is overflow:hidden above the mobile breakpoint. An id selector
       outranks it, which an equal-specificity rule in this block would not. */
    #content-agencies .dataTables_wrapper,
    #content-products .dataTables_wrapper { overflow-x: auto; }
</style>
@include('procurement.partials.ds-styles')
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    // ⚠ Precomputed: a Blade directive glued to a word character is not compiled,
    // and every conditional sentence below is composed here for that reason.
    $ok       = (bool) ($d['available'] ?? false);
    $content  = $d['content']  ?? [];
    $tools    = $d['tools']    ?? [];
    $overlap  = $d['overlap']  ?? [];
    $cRows    = $content['rows'] ?? [];
    $cKinds   = $content['by_kind'] ?? [];
    // ⚠ WHOSE spend this is. Added 2026-09-16 because the Overview's Data band
    // charted it and THIS page did not — a summary showing a breakdown its own
    // target page cannot show is the seam the band design exists to close.
    // Served uncapped by /oce/licenses/data, and it sums to $content['value'].
    $cAgencies = $content['by_agency'] ?? [];
    $tRows    = $tools['rows'] ?? [];
    $oRows    = $overlap['rows'] ?? [];
    $conc     = $content['concentration'] ?? [];

    // The headline: the single tool row carrying the most content. Derived from
    // the payload, never named here, so it follows the data if it ever moves.
    $lead = null;
    foreach ($tRows as $r) {
        if (($r['content_value'] ?? 0) > 0
            && ($lead === null || $r['content_value'] > $lead['content_value'])) {
            $lead = $r;
        }
    }
    $leadShare = ($lead && ($lead['value'] ?? 0) > 0)
        ? round($lead['content_value'] / $lead['value'] * 100)
        : null;
    // The largest family inside that row that is bought as content, and the
    // largest that is not — the two halves of the row, in the reader's terms.
    $leadContentFam = null; $leadToolFam = null;
    foreach (($lead['families'] ?? []) as $f) {
        if (($f['is_content'] ?? false) && $leadContentFam === null) { $leadContentFam = $f; }
        if (!($f['is_content'] ?? false) && $leadToolFam === null)   { $leadToolFam = $f; }
    }

    // Course libraries are content, and nobody asking "what data does the City
    // buy?" means them. ⚠ The clause disappears entirely when the tag is absent,
    // rather than leaving a gap where a number was.
    $training = null;
    foreach ($cKinds as $k) { if (($k['key'] ?? '') === 'training-content') { $training = $k; } }
    $trainRowShare = ($training && ($content['contracts'] ?? 0) > 0)
        ? round($training['contracts'] / $content['contracts'] * 100) : null;
    $trainValShare = ($training && ($content['value'] ?? 0) > 0)
        ? round($training['value'] / $content['value'] * 100, 1) : null;

    $untagged = null;
    foreach ($cKinds as $k) { if (($k['key'] ?? '') === '') { $untagged = $k; } }

    $fmtM = function ($v) { return '$' . number_format(((float) $v) / 1000000, 1) . 'M'; };
    // ⚠ Composed here: a clause built with inline @if beside punctuation is the
    // directive-glued-to-text shape this page has already 500'd on once.
    $leadToolClause = ($lead && $leadToolFam)
        ? '; the tools come to ' . $fmtM($lead['tool_value'] ?? 0) . ', led by ' . $leadToolFam['key']
        : '';

    // ⚠ "1 contracts" renders on every row where a count happens to be 1,
    // and this page has several — the overlap tile is 1 on thin data.
    $n = function ($v, $one, $many = null) {
        $v = (int) $v;
        return number_format($v) . ' ' . ($v === 1 ? $one : ($many ?: $one . 's'));
    };

    // ⚠ COMPOSED HERE, NOT WITH INLINE DIRECTIVES. `of the value@if(...)` is a
    // Blade directive glued to a word character: it is not compiled, only the
    // matching @endif is, and the page 500s with "unexpected 'endif'". This
    // exact sentence hit it on the first render.
    // ⚠ Degrades by CLAUSE, not by disappearing. _concentration only emits a
    // bucket once that many products exist, so a small class has top1/top3 and
    // no top10 — and the first draft's `if (top10)` deleted a sentence that was
    // perfectly answerable. Verified against thin local data, where top10 is absent.
    // ⚠⚠ THE PAGE'S STRONGEST CLAIM — the overlap — must say whether a HUMAN
    // made the judgement it rests on. Served, never typed: on prod the two rows
    // carrying $23.1M of the $23.2M are both curated and the third is automatic.
    $ovCur = (float) ($overlap['curated_value'] ?? 0);
    $ovVal = (float) ($overlap['value'] ?? 0);
    $ovSentence = '';
    if ($ovVal > 0) {
        $ovSentence = ($ovCur >= $ovVal)
            ? 'Every one of these classifications was reviewed by hand.'
            : ($ovCur > 0
                ? '<strong>' . ('$' . number_format($ovCur / 1000000, 1) . 'M')
                  . '</strong> of this was classified by hand; the rest is the '
                  . 'classifier&rsquo;s own judgement, marked below.'
                : 'None of this has been reviewed by hand yet &mdash; every row '
                  . 'below is the classifier&rsquo;s own judgement.');
    }

    // ⚠⚠ THE REVIEWED SHARE, COMPUTED — the section plan's §5c claimed "every row
    // already tier-curated" and prod says 11 of 100 families are, carrying 87.5%
    // of the value. Both are true and neither implies the other, so both render.
    $rev = $content['reviewed'] ?? null;
    $revSentence = '';
    if ($rev && ($content['families'] ?? 0) > 0) {
        $revSentence = 'Of the ' . number_format($content['families'])
            . ' products below, <strong>' . number_format($rev['families'])
            . '</strong> have had their purchase class reviewed by hand &mdash; '
            . '<strong>' . e($rev['share']) . '%</strong> of the value. '
            . 'The rest is the classifier&rsquo;s own judgement, unreviewed.';
    }

    $concSentence = '';
    if (!empty($conc['top1'])) {
        $parts = [];
        if (!empty($conc['top10'])) {
            $parts[] = 'the ten largest products are <strong>' . e($conc['top10']) . '%</strong> of the value';
        }
        $parts[] = 'the largest alone is <strong>' . e($conc['top1']) . '%</strong>';
        $concSentence = 'It is highly concentrated: ' . implode(', and ', $parts) . '.';
    }
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <a href="{{ route('research.digital-reform') }}" class="db-btn db-btn-ghost db-btn-sm mb-2"><i class="bi bi-arrow-left"></i> Digital Services</a>
        <h1>Data</h1>
        <p class="db-page-lead">
            What the City <strong>buys as data</strong> &mdash; imagery, legal research, market
            intelligence, rented from publishers &mdash; and the <strong>tools it buys to work with
            data</strong>. The two halves overlap, so they are <strong>never added</strong>.
        </p>
        @include('sub.analysis-tag')

        @if(!$ok)
            <div class="db-alert db-alert-warning" role="alert">
                <i class="bi bi-exclamation-triangle"></i>
                <div class="db-alert-body">This analysis is not available right now. Please try again shortly.</div>
            </div>
        @else

        {{-- The same three views the Overview's Data band previews (2026-09-23). --}}
        <div class="mt-3 mb-4">
            @include('procurement.partials.data-book')
        </div>

        {{-- ⚠ The tiles are labelled by HALF, never merged into a page total, and
             the note sits OUTSIDE .db-stat-grid — a <p> inside it becomes a grid
             item (186x110px instead of full width). --}}
        <div class="db-stat-grid mb-2">
            <div class="db-stat is-accent">
                <div class="db-stat-label">Bought as data or content</div>
                <div class="db-stat-value">{{ $fmtM($content['value'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ $n($content['contracts'] ?? 0, 'contract') }} &middot;
                    {{ $n($content['families'] ?? 0, 'product') }} &middot;
                    {{ $n($content['agencies'] ?? 0, 'agency', 'agencies') }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Bought as a tool for data work</div>
                <div class="db-stat-value">{{ $fmtM($tools['tool_value'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ $n($tools['tool_contracts'] ?? 0, 'contract') }} across
                    {{ $n(count($tRows), 'function') }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Counted by both</div>
                <div class="db-stat-value">{{ $fmtM($overlap['value'] ?? 0) }}</div>
                {{-- ⚠ Phrased without a relative clause on purpose: "1 contract that
                     are data" is what a verb agreeing with the plural produces. --}}
                <div class="db-stat-sub">{{ $n($overlap['contracts'] ?? 0, 'contract') }} appearing in
                    both halves</div>
            </div>
        </div>
        <p class="text-muted small mb-4">
            These three do not add up: two answers to different questions, and the part they share.
        </p>

        {{-- ============ THE FINDING. It is about a row the section already
             publishes, so it belongs above both halves rather than inside one. --}}
        @if($lead && $leadShare !== null)
        <div class="db-alert db-alert-info mb-5" role="region" aria-label="Why the two halves overlap">
            <i class="bi bi-info-circle"></i>
            <div class="db-alert-body">
                {{-- ⚠ NEVER strtolower() a display label: it renders "geospatial / gis"
                     and "bi &amp; dashboards". The labels are the vocabulary's own
                     spelling and the sentence is built around them instead. --}}
                <strong>{{ $leadShare }}% of &ldquo;{{ $lead['label'] }}&rdquo; is purchased data, not a tool.</strong>
                <p class="mb-0 mt-1" style="font-size: var(--db-text-sm);">
                    {{ $fmtM($lead['content_value']) }} of its {{ $fmtM($lead['value']) }} is imagery
                    and reference data the City licenses to <em>use</em>{{ $leadToolClause }}.
                    Adding the halves would count
                    @if($leadContentFam)
                        {{ $leadContentFam['key'] }}
                    @else
                        the same purchase
                    @endif
                    twice.
                </p>
            </div>
        </div>
        @endif

        {{-- ============ A. bought as data ============ --}}
        <h2 class="mb-2">Data and content the City rents</h2>
        <p class="db-page-lead mb-2">
            Every contract classed as a <strong>content subscription</strong>. The question for this
            class is <strong>is the content still needed, and by how many people</strong>.
            {!! $concSentence !!}
        </p>
        @if($revSentence !== '' || ($training && $trainRowShare !== null))
        <details class="lic-more mb-3">
            <summary>What is reviewed, and what &ldquo;content&rdquo; includes</summary>
            @if($revSentence !== '')
            <p class="lic-sub mb-1 mt-1">{!! $revSentence !!}</p>
            @endif
            @if($training && $trainRowShare !== null)
            <p class="lic-sub mb-0">
                {{ number_format($training['contracts']) }} of the
                {{ $n($content['contracts'] ?? 0, 'contract') }} ({{ $trainRowShare }}%) are
                <em>course libraries</em>, not data &mdash; but only {{ $trainValShare }}% of the value.
                By money this class is data; by row count a fifth of it is staff training.
                @if($untagged)
                    A further {{ $n($untagged['contracts'], 'contract') }}
                    ({{ $n($untagged['families'], 'product') }}) carry no function tag at all
                    &mdash; unclassified, which is a different claim from unclassifiable.
                @endif
            </p>
            @endif
        </details>
        @endif

        {{-- ⚠⚠ THE CONTENT HALF ONLY, like every figure in this section of the
             page. The two halves of this lens OVERLAP by design, so an agency
             breakdown spanning both would be the one sum this page exists to
             refuse — and it would not close against anything.
             ⚠ The bar list is the top 10; the FULL, uncapped table is one click
             away, and its caption says nothing is truncated. A truncated list
             under a heading implying the whole is the `by_vendor` defect. --}}
        <div class="row g-4 mb-5">
            <div class="col-lg-4">
                <div class="db-table-wrap h-100" id="content-agencies">
                    <div class="px-3 pt-3">
                        <h3 style="font-size: var(--db-text-base);" class="mb-1"><i class="bi bi-building"></i> Which agencies buy it</h3>
                    </div>
                    <div class="ds-rank px-3 pb-2">
                        @php $agMax = max(1, (float) ($cAgencies[0]['value'] ?? 1)); @endphp
                        @foreach(array_slice($cAgencies, 0, 10) as $a)
                            @php $agHref = !empty($a['org_id']) ? route('orgProfile', ['id' => $a['org_id'], 'orgslug' => \Illuminate\Support\Str::slug($a['key'] ?? '', '-')]) : null; @endphp
                            <a class="ds-bar-row" @if($agHref) href="{{ $agHref }}" @endif>
                                <span class="ds-bar-name">{{ $a['key'] }}</span>
                                <span class="ds-bar-val">{{ $fmtM($a['value']) }}</span>
                                <span class="ds-bar-track" aria-hidden="true"><i style="width: {{ max(1, round(100 * $a['value'] / $agMax)) }}%;"></i></span>
                            </a>
                        @endforeach
                    </div>
                    <details class="px-3 pb-3">
                        <summary class="lic-sub">All {{ $n(count($cAgencies), 'agency', 'agencies') }}, sortable</summary>
                    <div class="table-responsive">
                        <table class="db-table db-table-striped db-dt">
                            <caption class="text-muted small">Every agency in this class, ranked by value &mdash;
                                nothing is truncated, and the column closes to the class total.</caption>
                            <thead>
                                <tr><th>Agency</th><th class="db-num">Products</th>
                                    <th class="db-num">Contracts</th><th class="db-num">Value</th></tr>
                            </thead>
                            <tbody>
                                @forelse($cAgencies as $a)
                                <tr>
                                    {{-- ⚠ An unnamed agency is NOT an agency called "Other" — it
                                         is a row we cannot attribute, and the endpoint names it
                                         so rather than letting it read as a body. --}}
                                    <td>
                                        @if(!empty($a['org_id']))
                                        <a href="{{ route('orgProfile', ['id' => $a['org_id'], 'orgslug' => \Illuminate\Support\Str::slug($a['key'] ?? '', '-')]) }}">{{ $a['key'] }}</a>
                                        @else
                                        {{ $a['key'] }}
                                        @endif
                                    </td>
                                    <td class="db-num">{{ number_format($a['families']) }}</td>
                                    <td class="db-num">{{ number_format($a['contracts']) }}</td>
                                    <td class="db-num" data-order="{{ (int) $a['value'] }}">${{ number_format($a['value'], 0) }}</td>
                                </tr>
                                @empty
                                <tr><td colspan="4" class="text-muted">
                                    No agency breakdown is available for this class right now.
                                </td></tr>
                                @endforelse
                            </tbody>
                        </table>
                    </div>
                    </details>
                </div>
            </div>
            <div class="col-lg-8">
                <div class="db-table-wrap h-100" id="content-products">
                    <div class="px-3 pt-3">
                        <h3 style="font-size: var(--db-text-base);" class="mb-1"><i class="bi bi-collection"></i> The products</h3>
                    </div>
                    <div class="table-responsive">
                        <table class="db-table db-table-striped db-dt">
                            <caption class="text-muted small">All
                                {{ $n($content['families'] ?? 0, 'product') }} in this class, ranked
                                by value. Nothing is truncated.</caption>
                            <thead>
                                <tr><th>Product</th><th>Kind</th><th class="db-num">Contracts</th>
                                    <th class="db-num">Agencies</th><th class="db-num">Value</th></tr>
                            </thead>
                            <tbody>
                                @forelse($cRows as $f)
                                <tr>
                                    <td>
                                        @if(!empty($f['slug']))
                                            <a href="{{ route('research.digital-reform.product-family', ['slug' => $f['slug']]) }}">{{ $f['key'] }}</a>
                                        @else
                                            {{ $f['key'] }}
                                        @endif
                                    </td>
                                    <td class="small text-muted">
                                        @if(!empty($f['capability']))
                                            <a href="{{ route('research.digital-reform.product-capability', ['cap' => $f['capability']]) }}">{{ $f['capability_label'] }}</a>
                                        @else
                                            {{ $f['capability_label'] }}
                                        @endif
                                    </td>
                                    <td class="db-num">{{ number_format($f['contracts']) }}</td>
                                    <td class="db-num">{{ number_format($f['agencies']) }}</td>
                                    <td class="db-num" data-order="{{ (int) $f['value'] }}">{{ $fmtM($f['value']) }}</td>
                                </tr>
                                @empty
                                <tr><td colspan="5" class="text-center text-muted py-4">No content subscriptions found.</td></tr>
                                @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        {{-- ============ B. bought as a tool ============ --}}
        <h2 class="mb-2">Tools the City buys to work with data</h2>
        <p class="db-page-lead mb-3">
            Mapping, dashboards, statistics, log search and field capture. Each function is
            <strong>split</strong>, because one job can hold a licence for a tool and a subscription to
            the data it reads; each bar is the same row total the
            <a href="{{ route('research.digital-reform.products') }}#functions">Products function table</a>
            publishes.
        </p>

        <div class="db-chart-card mb-2" id="tools-chart">
            <div class="db-chart-head"><span class="db-chart-title">Bought as a tool, and bought as data, by function</span></div>
            {{-- ⚠ FIXED-HEIGHT WRAPPER IS LOAD-BEARING (#61). --}}
            <div class="db-chart-body" style="height: {{ max(160, 56 * count($toolSplit['labels'] ?? [])) }}px;"><canvas id="dlToolSplitChart"></canvas></div>
            <p class="ds-chart-note">
                Stacked within a function only &mdash; nothing is added across functions or across the
                two halves.
            </p>
        </div>

        <details class="lic-more mb-5" id="tools">
            <summary>The table, with products, agencies and contract counts</summary>
        <div class="db-table-wrap mt-2">
            <div class="table-responsive">
                <table class="db-table db-table-striped db-dt">
                    <thead>
                        <tr>
                            <th>Function</th>
                            <th class="db-num">Products</th>
                            <th class="db-num">Agencies</th>
                            <th class="db-num dl-split-a">Bought as a tool</th>
                            <th class="db-num">Bought as data</th>
                            <th class="db-num">Row total</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($tRows as $r)
                        <tr>
                            <td>
                                <a href="{{ route('research.digital-reform.product-capability', ['cap' => $r['key']]) }}">{{ $r['label'] }}</a>
                                @if(($r['content_value'] ?? 0) > 0)
                                    <span class="db-badge db-badge-warning">mixed</span>
                                @endif
                            </td>
                            <td class="db-num">{{ number_format($r['products']) }}</td>
                            <td class="db-num">{{ number_format($r['agencies']) }}</td>
                            <td class="db-num dl-split-a" data-order="{{ (int) $r['tool_value'] }}">
                                ${{ number_format($r['tool_value'], 0) }}
                                <div class="text-muted small">{{ $n($r['tool_contracts'], 'contract') }}</div>
                            </td>
                            <td class="db-num" data-order="{{ (int) $r['content_value'] }}">
                                @if(($r['content_value'] ?? 0) > 0)
                                    ${{ number_format($r['content_value'], 0) }}
                                    <div class="text-muted small">{{ $n($r['content_contracts'], 'contract') }}</div>
                                @else
                                    <span class="text-muted small">&mdash;</span>
                                @endif
                            </td>
                            <td class="db-num" data-order="{{ (int) $r['value'] }}">${{ number_format($r['value'], 0) }}</td>
                        </tr>
                        @empty
                        <tr><td colspan="6" class="text-center text-muted py-4">No data-work functions found.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>
        </details>

        {{-- ============ the overlap, in full ============ --}}
        <h2 class="mb-2">Counted by both halves</h2>
        <p class="db-page-lead mb-3">
            Every contract in both halves, named rather than netted off: a subscription to somebody
            else&rsquo;s data, filed under a function the City buys tools for. {!! $ovSentence !!}
        </p>
        <div class="db-table-wrap mb-5" id="overlap">
            <div class="table-responsive">
                <table class="db-table db-table-striped db-dt">
                    <thead>
                        <tr><th>Product</th><th>Function it is filed under</th>
                            <th>Classified</th>
                            <th class="db-num">Contracts</th><th class="db-num">Value</th></tr>
                    </thead>
                    <tbody>
                        @forelse($oRows as $r)
                        <tr>
                            <td>
                                @if(!empty($r['slug']))
                                    <a href="{{ route('research.digital-reform.product-family', ['slug' => $r['slug']]) }}">{{ $r['family'] }}</a>
                                @else
                                    {{ $r['family'] }}
                                @endif
                            </td>
                            <td><a href="{{ route('research.digital-reform.product-capability', ['cap' => $r['capability']]) }}">{{ $r['capability_label'] }}</a></td>
                            {{-- ⚠ Three states, never two: reviewed, automatic, and a row
                                 whose contracts were classified at both tiers. --}}
                            <td>
                                @if(($r['tier'] ?? '') === 'curated')
                                    <span class="db-badge db-badge-success">by hand</span>
                                @elseif(($r['tier'] ?? '') === 'mixed')
                                    <span class="db-badge db-badge-warning">mixed</span>
                                @else
                                    <span class="db-badge db-badge-neutral">automatic</span>
                                @endif
                            </td>
                            <td class="db-num">{{ number_format($r['contracts']) }}</td>
                            <td class="db-num" data-order="{{ (int) $r['value'] }}">{{ $fmtM($r['value']) }}</td>
                        </tr>
                        @empty
                        <tr><td colspan="5" class="text-center text-muted py-4">Nothing is counted twice.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        <details class="lic-more">
            <summary>Where these figures come from</summary>
            <p class="lic-sub mb-0 mt-1">
                No new judgement: the purchase class is the one the
                <a href="{{ route('research.digital-reform.products') }}">Products page</a> publishes,
                resolved per product with a family fallback, and the functions are its closed
                vocabulary. Which functions count as data work is recorded in that vocabulary rather
                than derived, because the obvious derivation drops mapping &mdash; the largest &mdash;
                on a technicality of where it sits in the open-source catalogue. Contracts still in
                approval carry no contract id and are absent here, as from every figure in this section.
            </p>
        </details>
        @endif

    </div> <!-- /.container -->
</div> <!-- /.inner_container -->
@endsection

@section('scripts')
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function () {
    if (!window.Chart) { return; }
    if (window.DBChart) { DBChart.apply(Chart); }
    @include('procurement.partials.slice-pies-js')
    @include('procurement.partials.data-book-js')
    // AFTER the pies: the HTML legends are the only legend, painted from the
    // same colour resolver as the arcs.
    paintLegends();

    // ---- The tools half: tool vs data, per function ----------------------
    // ⚠ Built in the controller (_dataToolSplit), so nothing is derived here.
    // Stacked WITHIN a function only: each bar is that function's row total.
    const ts = @json($toolSplit ?? null);
    const el = document.getElementById('dlToolSplitChart');
    if (ts && ts.labels && ts.labels.length && el) {
        const money = (v) => '$' + (Number(v) / 1000000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'M';
        new Chart(el, {
            type: 'bar',
            data: {
                labels: ts.labels,
                datasets: [
                    { label: 'Bought as a tool', data: ts.tool, backgroundColor: DBChart.navy, borderRadius: 3, stack: 'row' },
                    { label: 'Bought as data',   data: ts.content, backgroundColor: DBChart.accent, borderRadius: 3, stack: 'row' },
                ],
            },
            options: {
                indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: { callbacks: { label: (c) => c.dataset.label + ': ' + money(c.raw) } },
                },
                scales: {
                    x: { stacked: true, ticks: { callback: (v) => money(v) } },
                    y: { stacked: true },
                },
                onClick: null,
            },
        });
    }
});
</script>
@endsection
