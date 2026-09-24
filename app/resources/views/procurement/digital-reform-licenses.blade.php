@extends('layout')

@section('head')
{{-- PUBLISHED 2026-08-11, after the top-20 review was completed and accepted by
     the owner. This page was `noindex` + absent from the nav for as long as every
     judgement on it was unreviewed AI output; it is now in the Digital Services
     Analysis submenu and indexable.
     ⚠ The Analysis banner and the stated limits below are what carry the caveats
     now -- they are the reason publishing is defensible, so do not strip them.
     ⚠ THE REVIEWED SHARE IS NOW COMPUTED, NOT TYPED. It used to read "the largest
     20 product families -- 88.0% of the value" as literal text while the page's
     own concentration strip said 87.7% and the seed had grown past 20. Every
     figure on this page must come from the payload. If you are about to type a
     number here, add it to the API instead. --}}
@include('procurement.partials.lic-styles')
@include('procurement.partials.ds-styles')
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    // ⚠ PLAIN TEXT ONLY in these strings: they are echoed through Blade escaping,
    // so an HTML entity here would reach the reader literally. (That is exactly
    // how the Build-vs-buy filter came to read "High &mdash; easily replaceable".)
    $available = (bool) ($lic['available'] ?? false);
    $sum   = $lic['summary'] ?? [];
    $conc  = $lic['concentration'] ?? [];
    $fams  = $lic['families'] ?? [];
    $years = $lic['by_year']['years'] ?? [];
    $noEnd = $lic['by_year']['no_end_date'] ?? 0;
    $ended = $lic['by_year']['ended'] ?? ['contracts' => 0, 'value' => 0];
    $byAg  = $lic['by_agency'] ?? [];
    $byVen = $lic['by_vendor'] ?? [];
    $generic = $lic['generic'] ?? null;
    $grouped = (bool) ($lic['grouped'] ?? false);
    // ⚠ Full lengths of every list the API truncates. Rendering a capped table
    // with no denominator is how "By vendor" implied it showed all 88 vendors
    // while showing 25.
    $totals = $lic['totals'] ?? [];
    // ⚠ Consolidation is NOT RENDERED on this page (owner, 2026-09-18): no badge,
    // no count, no filter. `fragmented`, `consolidation_candidate` and
    // `consolidation_rule` are still SERVED for API consumers.
    // "Bought through" column sources, measured by the API. When the notice half
    // never loaded ($resNotice false) the note must not claim notice coverage —
    // describing a source that silently dropped out is the stale-disclosure defect.
    $resMeta   = $lic['resellers_meta'] ?? [];
    $resNotice = (bool) ($resMeta['available'] ?? false);

    // ⚠ ACTUALS, and the only figures on this page that are not awarded value.
    // Every number in this block is served, including the coverage caveat and the
    // name of the largest contract with no payments — a "58% of value" with no
    // subject reads as a matching bug rather than as one citywide master.
    // AWARDED by year — a commitment, and the only view in which a citywide master
    // agreement appears at all (it carries no payments under its own id).
    $award      = $lic['award_by_year'] ?? [];
    $awardOK    = (bool) ($award['available'] ?? false);
    $awardYears = $award['years'] ?? [];
    $awardPart  = $award['partial'] ?? [];
    $awardDrop  = $award['dropped'] ?? ['contracts' => 0, 'value' => 0, 'before' => 0];
    // ⚠ SELECTED from the served rows, not recomputed: the biggest award year and
    // what dominates it. A $794.1M bar with no subject reads as a broad-based surge
    // rather than as one Microsoft renewal.
    $awardTop = null;
    foreach ($awardYears as $y) {
        if ($awardTop === null || (float) $y['value'] > (float) $awardTop['value']) {
            $awardTop = $y;
        }
    }

    $spend      = $lic['spend_by_year'] ?? [];
    $spendOK    = (bool) ($spend['available'] ?? false);
    // Scanned off the request path, so "not here yet" is a normal state for a few
    // seconds after an API restart — and a different state from "unavailable".
    $spendPending = !$spendOK && (bool) ($spend['pending'] ?? false);
    $spendYears = $spend['years'] ?? [];
    $spendDrop  = $spend['dropped'] ?? ['paid' => 0, 'before' => 0];
    // Master agreements vs ordinary contracts — the SHAPE of the unpaid gap, which
    // is what answers "is this a matching failure?". Served, because the counts move
    // whenever the inventory does.
    $spendKinds = [];
    foreach (($spend['coverage']['by_kind'] ?? []) as $k) {
        $spendKinds[$k['kind']] = $k;
    }
    $spendMaster = $spendKinds['master'] ?? null;
    $spendPlain  = $spendKinds['contract'] ?? null;
    // The fiscal year in progress, reported rather than drawn: a partial bar looks
    // like a collapse. Normally exactly one; a list because the payload cannot
    // promise that and silently dropping the rest is the defect _by_year had.
    $spendPart  = $spend['partial'] ?? [];
    $spendCov   = $spend['coverage'] ?? [];
    $spendBig   = $spendCov['largest_unmatched'] ?? null;
    $spendFirst = count($spendYears) ? ($spendYears[0]['label'] ?? '') : '';
    $spendLast  = count($spendYears) ? ($spendYears[count($spendYears) - 1]['label'] ?? '') : '';

    $fmtM = function ($v) {
        $v = (float) $v;
        if ($v >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
        if ($v >= 1000000)    return '$' . number_format($v / 1000000, 1) . 'M';
        if ($v >= 1000)       return '$' . number_format($v / 1000, 0) . 'K';
        return '$' . number_format($v, 0);
    };
    $maxYearVal = count($years) ? max(array_map(function ($y) { return (float) $y['value']; }, $years)) : 0;
    $totalValue = (float) ($sum['total_value'] ?? 0);
    // Share of total value, as a percentage string. ⚠ Replaces a bar whose width
    // was max(2, round(100*v/max)) -- with the largest family at 47%, every other
    // row rendered at the identical 2% floor, so the column looked like a
    // measurement and carried no information.
    $pctOf = function ($v) use ($totalValue) {
        if ($totalValue <= 0) return '-';
        $p = 100 * (float) $v / $totalValue;
        return $p >= 0.1 ? number_format($p, 1) . '%' : '<0.1%';
    };
    // MM/DD/YYYY -> YYYY, for a compact term span. Blank stays blank rather than
    // becoming a wrong year.
    $yr = function ($d) {
        $d = trim((string) $d);
        return strlen($d) === 10 ? substr($d, -4) : '';
    };

    $expRoute = route('research.digital-reform.review');
    // Per-family URL, with a fallback to the old query-param view for any family
    // that has no slug yet (which happens only if the mapping table is absent).
    $famUrl = function ($f) {
        return !empty($f['slug'])
            ? route('research.digital-reform.product-family', ['slug' => $f['slug']])
            : route('research.digital-reform.products') . '?family=' . urlencode($f['key']) . '#family-detail';
    };
    $methods = $lic['by_method'] ?? [];
    $amb = $sum['ambiguity'] ?? [];
    $byClass = $lic['by_class'] ?? [];
    $byCap = $lic['by_capability'] ?? [];
    // ⚠ NO $capWords MAP HERE. Function labels are served by the API from
    // api/seed/license_capability_vocab.csv, because the two copies that used to
    // live in this file and in the capability view had both fallen behind the
    // seed -- 18 of 46 tags rendered as raw kebab-case keys on a published page.
    // ⚠ One owner for the class labels (App\Custom\PurchaseClass), shared with
    // the family page and the Products book's "Value by kind" pie.
    $classWords = \App\Custom\PurchaseClass::LABELS;
    $classColors = [
        'software-licence' => '#162E51', 'managed-hosting' => '#2b5c8a',
        'support-maintenance' => '#d9730d', 'content-subscription' => '#4d8fbe',
        'cloud-infrastructure' => '#7ab3d4', 'oss-support-tier' => '#a3c9e0',
        'professional-services' => '#c9a227', '(unclassified)' => '#b9bfc9',
    ];
    $leverWords = [
        'open-source-substitute' => 'Is there an open-source substitute?',
        'benchmark-then-self-host' => 'Is the price right? Rate cards are public.',
        'price-and-rightsizing' => 'Right-sized? Committed-use pricing in place?',
        'is-the-paid-tier-needed' => 'Does the paid tier earn its price?',
        'is-the-content-needed' => 'Is the content needed? Cheaper source?',
        'scope-and-rate-review' => 'Scope and day rate review.',
    ];

    // ⚠ Deliberately NOT a "not competitively bid" percentage. That figure is a
    // true 100% -- no license used competitive sealed bid or proposal -- and
    // printing it as a headline would insinuate a scandal that the breakdown
    // disproves: most contracts take the small-purchase route and 149 ride an
    // already-competed federal GSA schedule. Show the route, not a verdict.
    $topMethodName = count($methods) ? $methods[0]['key'] : 'Unknown';
    $topMethodPct  = (count($methods) && ($sum['contracts'] ?? 0) > 0)
        ? round(100 * $methods[0]['contracts'] / $sum['contracts'])
        : 0;
    // ⚠ AND ITS VALUE SHARE, because the two disagree violently: the leading
    // route is 61% of contracts and about 6% of the money. The count alone
    // implied the opposite of what the routes section carefully argues.
    $topMethodValPct = (count($methods) && $totalValue > 0)
        ? round(100 * $methods[0]['value'] / $totalValue)
        : 0;
    // Precomputed so no Blade directive ends up glued to a word character
    // (a directive touching one is not compiled and the page 500s).
    $modelNote = implode(' + ', $sum['ai_models'] ?? []);
    $reviewed = $sum['reviewed'] ?? ['families' => 0, 'share' => 0];
    $endedPct = ($sum['contracts'] ?? 0) > 0
        ? round(100 * $ended['contracts'] / $sum['contracts'])
        : 0;
    $largestFamily = count($fams) ? $fams[0]['key'] : '';
    $concLabels = ['top1' => 'Largest family', 'top3' => 'Top 3', 'top5' => 'Top 5',
                   'top10' => 'Top 10', 'top20' => 'Top 20'];
    // ⚠ Unregistered purchasing vehicles moved to the Overview (#247), which holds
    // the section-level figure; this page points there. The locals that fed the old
    // table are deleted rather than left assigned to nothing — an unused $pipeCount
    // reads as "the block is still here somewhere" to the next person.
    // ⚠ The FAMILY pages still render their own title-matched vehicles from
    // `pipeline_vehicles`, which is a different view and not a second total.
    // Jump navigation, in reading order.
    $ossRef = $lic['oss'] ?? [];   // for the link to the open-source page only
    $jumps = [
        'families'  => 'Product families',
        'classes'   => 'Kind of purchase',
        'functions' => 'By function',
        'routes'    => 'How they are bought',
        'agencies'  => 'Agencies & vendors',
        'licenses'  => 'Software licenses',
        'method'    => 'Method & limits',
    ];
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <a href="{{ route('research.digital-reform') }}" class="db-btn db-btn-ghost db-btn-sm mb-2"><i class="bi bi-arrow-left"></i> Digital Services</a>
        <h1 style="margin-bottom: var(--db-space-1);">Products</h1>
        {{-- ⚠ THE ANALYSIS IDENTITY, AS THE TAG (owner, 2026-09-18): "Products", with the
             caveat on the tag's face. The h1 used to carry the word "Analysis" for the
             provenance guard; the guard accepts the tag and pins that its summary keeps
             the warning. --}}
        @include('sub.analysis-tag', ['reviewed' => $reviewed, 'modelNote' => $modelNote])
        <p class="db-page-lead">
            The software the City licenses, grouped into <strong>product families</strong>: one product
            bought by eight agencies on eight contracts is one line here. The grouping is ours; a
            hand-reviewed family says so on its row.
                        </p>
        @include('sub.digital-scope-note', ['scope' => ['mode' => 'derived', 'positive' => true]])


        {{-- ⚠ THIS BLOCK USED TO SAY "Unlisted draft ... not linked from the site
             navigation and marked noindex". Publishing the page made its own
             self-description false, and it was still rendering that sentence after
             the meta tag came out. Whatever this note says must stay true.
             ⚠ It also used to restate the whole 92%/1-in-12 passage that the
             methods note at the foot of the page already carries word for word,
             so the reader met the same caveat three times before any data. One
             sentence here, the detail there, and a link between them. --}}

        {{-- ONE scope note for the whole section — see the partial. A guard asserts
             all three pages include it, because three pages explaining themselves
             three different ways is how the section ended up with two universes. --}}

        @if(!$available)
            <div class="db-alert db-alert-warning mt-3">
                <i class="bi bi-exclamation-triangle"></i>
                License analysis is not available right now.
                @if(!empty($lic['reason']))
                    <span class="lic-sub">Reason: {{ $lic['reason'] }}</span>
                @endif
            </div>
        @else

        <div class="lic-jump">
            @foreach($jumps as $anchor => $label)
                <a class="db-btn db-btn-ghost db-btn-sm" href="#{{ $anchor }}">{{ $label }}</a>
            @endforeach
        </div>

        {{-- ---------- Summary ---------- --}}
        <div class="db-stat-grid mt-2 mb-2">
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-diagram-3"></i> Product families</div>
                <div class="db-stat-value">{{ number_format($sum['families'] ?? 0) }}</div>
                <div class="db-stat-sub">Across {{ number_format($sum['vendors'] ?? 0) }} vendors</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Total current value</div>
                <div class="db-stat-value">{{ $fmtM($sum['total_value'] ?? 0) }}</div>
                {{-- ⚠ Multi-year TERM values spanning 2019-2031, not annual spend,
                     and most of it is already historical. Both facts belong on the
                     tile a reader will quote. --}}
                <div class="db-stat-sub">Multi-year term values; {{ $fmtM($sum['active_value'] ?? 0) }} on contracts still running</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-key"></i> License contracts</div>
                <div class="db-stat-value">{{ number_format($sum['contracts'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ number_format($sum['active_contracts'] ?? 0) }} not known to have ended</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-hourglass-split"></i> Expiring before 2030</div>
                <div class="db-stat-value">{{ number_format($sum['expiring'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ $fmtM($sum['expiring_value'] ?? 0) }}; ends between today and 2030</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-building"></i> Agencies</div>
                <div class="db-stat-value">{{ number_format($sum['agencies'] ?? 0) }}</div>
                <div class="db-stat-sub">Buying licenses separately</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-signpost-split"></i> Most common route</div>
                <div class="db-stat-value" style="font-size: var(--db-text-lg); line-height: 1.2;">{{ $topMethodPct }}% of contracts</div>
                <div class="db-stat-sub">{{ $topMethodName }} &mdash; but only {{ $topMethodValPct }}% of the value</div>
            </div>
        </div>

        {{-- ============ THE PRODUCTS BOOK — the SAME three views the Overview's
             Products band previews (one partial, one controller fold). ============ --}}
        <div class="mb-4">
            @include('procurement.partials.products-book')
        </div>


        {{-- ---------- Concentration ---------- --}}
        {{-- ---------- Families ---------- --}}
        {{-- ⚠ `id="fragmented"` is kept as a second anchor so links to the merged-away
             table still land here rather than nowhere. --}}
        <div class="db-table-wrap mb-3" id="families"><span id="fragmented"></span>
            <div class="px-3 pt-3">
                <div class="lic-section-head" style="display: flex; align-items: flex-start; gap: var(--db-space-2);">
                    <div style="flex: 1 1 auto; min-width: 0;">
                        <h2 class="lic-h2"><i class="bi bi-collection"></i> Product families</h2>
                        <p class="lic-sub mb-0">
                            @if($grouped)
                                All {{ number_format(count($fams)) }} families, grouped by the curated mapping; search, or sort any column.
                            @else
                                <strong>Ungrouped</strong> &mdash; the family mapping table is missing, so each spelling is its own row.
                            @endif
                            <span class="db-badge db-badge-neutral lic-legacy">legacy</span> marks mainframe-era platforms &mdash; an editorial call.
                        </p>
                        {{-- ⚠ The sources sentence is worded from SERVED figures and served
                             availability. The City publishes no usable sub-vendor data (the
                             sub_vendor field holds 2 distinct values), so this column must
                             say what it combines rather than imply supply-chain coverage. --}}
                        <details class="lic-more">
                            <summary>More on this table</summary>
                        <p class="lic-sub mb-0 lic-gap">
                            <strong>Sellers</strong> counts the vendors on a family&rsquo;s contracts
                            @if($resNotice)
                                plus vendors awarded a City Record notice naming the product
                                ({{ number_format($resMeta['links'] ?? 0) }} notices across
                                {{ number_format($resMeta['families'] ?? 0) }} families) &mdash; often the reseller.
                            @else
                                &mdash; notice-derived resellers are unavailable right now.
                            @endif
                            Names are on each family page. Not sub-vendor data.
                        </p>
                        </details>
                        {{-- ⚠ THIS REPLACED A SEPARATE TABLE. "One product, many separate
                             contracts" showed the 8 strongest of these same rows, ranked by
                             agencies instead of value — one dataset, twice, with nothing
                             saying so. The finding survives as a badge, a count and a
                             filter; the ranking survives as a column you can sort. --}}
                        @if(!empty($conc))
                        {{-- ⭐ CONCENTRATION LIVES WITH THE LIST IT DESCRIBES. Top-1/3/5/10/20 share
                             is a property of THIS table, and it sat in its own card above two
                             charts, ~4,000px from the rows it summarises. --}}
                        <div class="lic-rule" style="display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--db-space-1) var(--db-space-3);">
                            <span class="lic-tag">Concentration</span>
                            @foreach($concLabels as $k => $label)
                                @if(isset($conc[$k]))
                                    <span title="Share of total license value held by the {{ strtolower($label) }}"><strong style="font-size: var(--db-text-base);">{{ $conc[$k] }}%</strong>
                                        <span class="lic-sub">{{ $k === 'top1' && $largestFamily !== '' ? $largestFamily : $label }}</span></span>
                                @endif
                            @endforeach
                            <span class="lic-sub">share of total license value; a high top-1 share means one vendor relationship dominates the City&rsquo;s exposure</span>
                        </div>
                        @endif
                    </div>
                    <a class="db-btn db-btn-ghost db-btn-sm" style="flex: 0 0 auto;" href="{{ rtrim(config('apis.fapi_public_entry', 'https://api.databook.nyc'), '/') }}/oce/licenses/export"><i class="bi bi-download"></i> CSV</a>
                </div>
            </div>
            <table class="db-table" id="licFamilyTable">
                <thead>
                    <tr>
                        <th>Family</th>
                        <th>Kind</th>
                        <th>Function</th>
                        <th class="lic-num">Contracts</th>
                        <th class="lic-num">Agencies</th>
                        {{-- Carried over from the merged table: how many different
                             vendors sell the same family. --}}
                        <th class="lic-num">Sellers</th>
                        <th class="lic-num">Value</th>
                        <th class="lic-num">Share</th>
                        <th class="lic-num">Expiring</th>
                        {{-- Sole source or negotiated acquisition only — the Renewal Review
                             Queue's rule (owner, 2026-09-24). --}}
                        <th class="lic-num" style="white-space: normal;" title="Contracts awarded by sole source or negotiated acquisition">Sole source / negotiated</th>
                    </tr>
                </thead>
                <tbody>
                @foreach($fams as $f)
                    <tr>
                        <td>
                            <a href="{{ $famUrl($f) }}">{{ $f['key'] }}</a>
                            @if(!empty($f['legacy']))
                                <span class="db-badge db-badge-neutral lic-legacy">legacy</span>
                            @endif
                            @if($f['curated'])
                                <span class="lic-sub" title="Spellings merged by the curated mapping"><i class="bi bi-link-45deg"></i></span>
                            @endif
                            @if(!empty($f['summary']))
                                <span class="lic-prod lic-clamp" title="{{ $f['summary'] }}">{{ $f['summary'] }}</span>
                            @elseif(count($f['products'] ?? []) > 1)
                                <span class="lic-prod">{{ implode(' / ', array_slice($f['products'], 0, 4)) }}</span>
                            @endif
                        </td>
                        @php
                            $fKind = $classWords[$f['purchase_class'] ?? ''] ?? '';
                            $fTier = $f['class_tier'] ?? '';
                        @endphp
                        <td class="lic-sub" data-order="{{ $fKind !== '' ? $fKind : 'zzz' }}">
                            @if($fKind !== '')
                                <a href="{{ route('research.digital-reform.products') }}?class={{ urlencode($f['purchase_class']) }}#family-detail" title="{{ $fTier === 'curated' ? 'Reviewed by hand' : 'Classified by AI, not yet reviewed' }}">{{ $fKind }}</a>
                            @else
                                -
                            @endif
                        </td>
                        <td class="lic-sub" data-order="{{ !empty($f['capability_label']) ? $f['capability_label'] : 'zzz' }}">
                            @if(!empty($f['capability']) && $f['capability'] !== 'other')
                                <a href="{{ route('research.digital-reform.product-capability', ['cap' => $f['capability']]) }}">{{ $f['capability_label'] }}</a>
                            @elseif(!empty($f['capability_label']))
                                <span title="The classifier declined to name a function">{{ $f['capability_label'] }}</span>
                            @else
                                -
                            @endif
                        </td>
                        <td class="lic-num" data-order="{{ (int) $f['contracts'] }}">{{ number_format($f['contracts']) }}</td>
                        <td class="lic-num" data-order="{{ (int) $f['agencies'] }}">{{ number_format($f['agencies']) }}</td>
                        {{-- ⚠ Names are the API's capped display list; the counts are full.
                             The visible text is not monotonic in the count, so data-order
                             carries the sort (the #248 rule). † = notice-derived, no
                             contract in this set — explained once, in the note above. --}}
                        @php
                            $res = $f['resellers'] ?? ['names' => [], 'total' => 0];
                            $resMore = max(0, ($res['total'] ?? 0) - count($res['names'] ?? []));
                            // Names are e()-escaped by hand because the joined string is
                            // emitted raw. The dagger itself is CSS (.lic-notice-only::after):
                            // this view's @php strings are guarded entity-free (the &mdash;
                            // regression), and one raw-echoed exception would weaken that
                            // guard for every string the view escapes.
                            $resParts = [];
                            foreach (($res['names'] ?? []) as $rn) {
                                $resParts[] = !empty($rn['notice_only'])
                                    ? '<span class="lic-notice-only">' . e($rn['name']) . '</span>'
                                    : e($rn['name']);
                            }
                        @endphp
                        {{-- ⚠ THE COUNT, NOT THE NAMES. The names cost this table its width
                             (Microsoft's cell ran to "+28 more") and every one is on the family
                             page under "Who sells it". The count is the MERGED seller total --
                             contract vendors plus notice-only -- the same 32 the family page and
                             its tile state. Same sort key as before. --}}
                        <td class="lic-num" data-order="{{ (int) ($res['total'] ?? 0) }}"
                            title="{{ (int) ($res['contract'] ?? 0) }} hold a contract in this set; {{ (int) ($res['notice_only'] ?? 0) }} appear only on a City Record notice">{{ number_format((int) ($res['total'] ?? 0)) }}</td>
                        <td class="lic-num" data-order="{{ (int) $f['value'] }}">{{ $fmtM($f['value']) }}</td>
                        <td class="lic-num" data-order="{{ (int) $f['value'] }}">{{ $pctOf($f['value']) }}</td>
                        {{-- ⚠ `data-order` is what makes these SORT. Rendering "-" for zero
                             with no sort key made DataTables treat the column as text, so
                             "9" sorted after "12" — a sortable column that sorted wrongly.
                             The expiring cell also carries the queue link the merged table
                             had; a number you cannot click is a dead end. --}}
                        <td class="lic-num" data-order="{{ (int) $f['expiring'] }}">
                            @if($f['expiring'] > 0)
                                <a href="{{ $expRoute }}?expiring_license=1&expiring_product={{ urlencode($f['key']) }}#expiring-contracts">{{ number_format($f['expiring']) }}</a>
                            @else
                                <span class="lic-sub">-</span>
                            @endif
                        </td>
                        <td class="lic-num" data-order="{{ (int) $f['non_competitive'] }}">{{ $f['non_competitive'] > 0 ? number_format($f['non_competitive']) : '-' }}</td>
                        {{-- ⚠ Replaces the separate "Long-running relationships" table,
                             which listed the same families with the same spans. --}}
                        @php $s = $yr($f['first_start'] ?? ''); $e = $yr($f['last_end'] ?? ''); @endphp
                    </tr>
                @endforeach
                @if($generic)
                    <tr>
                        <td class="lic-generic">
                            (unidentified product)
                            <span class="lic-prod">the classifier could not name a product for these</span>
                        </td>
                        <td class="lic-sub lic-generic" data-order="zzz">-</td>
                        <td class="lic-sub lic-generic" data-order="zzz">-</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['contracts'] }}">{{ number_format($generic['contracts']) }}</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['agencies'] }}">{{ number_format($generic['agencies']) }}</td>
                        {{-- No product name means no notice match is possible; the cell
                             stays empty rather than implying "no resellers". --}}
                        <td class="lic-num lic-generic" data-order="0">-</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['value'] }}">{{ $fmtM($generic['value']) }}</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['value'] }}">{{ $pctOf($generic['value']) }}</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['expiring'] }}">{{ $generic['expiring'] > 0 ? number_format($generic['expiring']) : '-' }}</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['non_competitive'] }}">{{ $generic['non_competitive'] > 0 ? number_format($generic['non_competitive']) : '-' }}</td>
                    </tr>
                @endif
                </tbody>
            </table>
        </div>

        {{-- The open-source alternatives have their own page (owner, 2026-09-23),
             linked from here the way Contracts links the Renewal Review Queue.
             `id="open-source"` stays so old links to this anchor still land. --}}
        <div class="d-flex flex-wrap align-items-center gap-3 mb-5" id="open-source">
            <a href="{{ route('research.digital-reform.open-source') }}" class="db-btn db-btn-primary">
                <i class="bi bi-arrow-repeat"></i> Open-source alternatives <i class="bi bi-arrow-right"></i>
            </a>
            <span class="text-muted" style="font-size: var(--db-text-sm);">
                @if(($ossRef['curated_total']['families'] ?? 0) > 0)
                    {{ number_format($ossRef['curated_total']['families']) }} products with a reviewed substitute,
                    {{ number_format($ossRef['review_total']['families'] ?? 0) }} still to review,
                    and the categories where no public-sector catalogue has one.
                @else
                    Products with a credible open-source substitute, and the gaps in the public-sector catalogues.
                @endif
            </span>
        </div>

        {{-- ---------- Family / agency / class drill-down ---------- --}}
        <div id="family-detail"></div>
        @if($drill && ($drill['available'] ?? false))
        @php
            $drillLabel = $family !== '' ? $family : ($agencySel !== '' ? $agencySel
                          : ($classWords[$classSel] ?? $classSel));
            $drillRows  = $drill['rows'] ?? [];
        @endphp
        <div class="db-table-wrap mb-5">
            <div class="px-3 pt-3">
                <div class="lic-section-head">
                    <div>
                        <h2 class="lic-h2"><i class="bi bi-list-ul"></i> Contracts: {{ $drillLabel }}</h2>
                        <p class="lic-sub mb-0">
                            {{ number_format($drill['total'] ?? 0) }} contracts, {{ $fmtM($drill['value'] ?? 0) }}.
                            @if($drill['truncated'] ?? false)
                                <strong>Showing the first {{ number_format(count($drillRows)) }}</strong> by value.
                            @endif
                        </p>
                    </div>
                    <a class="db-btn db-btn-ghost db-btn-sm" href="{{ route('research.digital-reform.products') }}"><i class="bi bi-x-lg"></i> Clear</a>
                </div>
            </div>
            <table class="db-table db-dt">
                <thead>
                    <tr>
                        <th>Contract</th><th>Product</th><th>Agency</th><th>Vendor</th>
                        <th class="lic-num">Current value</th><th>Term</th><th>Method</th>
                    </tr>
                </thead>
                <tbody>
                @foreach($drillRows as $r)
                    <tr>
                        <td>
                            <a href="{{ route('procurement.contract', $r['contract_id']) }}">{{ $r['contract_id'] }}</a>
                            @if(!empty($r['contract_title']))
                                <span class="lic-prod">{{ $r['contract_title'] }}</span>
                            @endif
                        </td>
                        <td>
                            {{ $r['product'] ?? '' }}
                            @if(!empty($r['purpose']))
                                <span class="lic-prod">{{ $r['purpose'] }}</span>
                            @endif
                        </td>
                        <td>
                            @if(!empty($r['agency']))
                                <a href="{{ route('agency.procurement', ['name' => $r['agency']]) }}">{{ $r['agency'] }}</a>
                            @endif
                        </td>
                        <td>{{ $r['vendor_name'] ?? '' }}</td>
                        <td class="lic-num">{{ $fmtM($r['current_amount'] ?: $r['award_amount']) }}</td>
                        <td class="lic-sub">
                            {{ $r['start_date'] ?? '' }} to {{ $r['end_date'] ?? '' }}
                            @if($r['expiring'] ?? false)
                                <span class="db-badge db-badge-warning">expiring</span>
                            @endif
                        </td>
                        <td class="lic-sub">{{ $r['procurement_method'] ?? '' }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </div>
        @endif

        

        {{-- ---------- What kind of purchase (the view the rating hides) ---------- --}}
        @if(count($byClass))
        <div class="db-table-wrap mb-5" id="classes">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-tags"></i> What kind of purchase is this spend?</h2>
                <p class="lic-sub mb-0">
                    Each kind of purchase carries its own question. Asking &ldquo;could the City build
                    this?&rdquo; of hosting is how infrastructure spend vanished from the replaceability view.
                        </p>
            </div>
            @php
                // The one visual anchor on an otherwise all-table page: the whole
                // argument of this section as a single bar.
                $mixTotal = 0;
                foreach ($byClass as $bc) { $mixTotal += (float) $bc['value']; }
            @endphp
            @if($mixTotal > 0)
            <div class="px-3 pt-3">
                <div class="lic-mix">
                    @foreach($byClass as $bc)
                        @php
                            $segPct = 100 * (float) $bc['value'] / $mixTotal;
                            $segCol = $classColors[$bc['key']] ?? '#b9bfc9';
                            $segLab = $classWords[$bc['key']] ?? $bc['key'];
                        @endphp
                        <div class="lic-mix-seg" style="width: {{ $segPct }}%; background: {{ $segCol }};"
                             title="{{ $segLab }}: {{ number_format($segPct, 1) }}%"></div>
                    @endforeach
                </div>
                <div class="lic-mix-key">
                    @foreach($byClass as $bc)
                        @php
                            $segPct = 100 * (float) $bc['value'] / $mixTotal;
                            $segCol = $classColors[$bc['key']] ?? '#b9bfc9';
                            $segLab = $classWords[$bc['key']] ?? $bc['key'];
                        @endphp
                        <span><i class="lic-swatch" style="background: {{ $segCol }};"></i>{{ $segLab }} {{ number_format($segPct, 1) }}%</span>
                    @endforeach
                </div>
            </div>
            @endif
            <table class="db-table db-dt">
                <thead><tr><th>Class</th><th class="lic-num">Contracts</th><th class="lic-num">Families</th><th class="lic-num">Value</th><th>The question to ask</th></tr></thead>
                <tbody>
                @foreach($byClass as $bc)
                    <tr>
                        {{-- ⚠ The page's headline lens was the one table with no
                             drill-down: families and functions both clicked
                             through, classes dead-ended. --}}
                        <td><strong><a href="{{ route('research.digital-reform.products') }}?class={{ urlencode($bc['key']) }}#family-detail">{{ $classWords[$bc['key']] ?? $bc['key'] }}</a></strong></td>
                        <td class="lic-num">{{ number_format($bc['contracts']) }}</td>
                        <td class="lic-num">{{ number_format($bc['families']) }}</td>
                        <td class="lic-num">{{ $fmtM($bc['value']) }}</td>
                        <td class="lic-sub">{{ $leverWords[$bc['lever']] ?? '' }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
            <div class="px-3 pb-3">
                <details class="lic-more">
                    <summary>More on this table</summary>
                <p class="lic-sub mb-2">
                    Managed hosting spans commodity hosting with a public rate card (WP Engine, Pantheon)
                    and bespoke hosted platforms (Axon Evidence, ShotSpotter, Ivalua); only the first can be
                    price-checked.
                        </p>
                </details>
                <details class="lic-more">
                    <summary>How reviewed is this?</summary>
                <p class="lic-sub mb-0">
                    {{ number_format($reviewed['families'] ?? 0) }} families are hand-classified; the rest are
                    AI-assigned and unreviewed. <em>Not yet classified</em> is its own row, so the table never
                    overstates what has been assessed.
                        </p>
                </details>
                
            </div>
        </div>
        @endif

        {{-- ---------- Same job, many products, many agencies ---------- --}}
        @if(count($byCap))
        <div class="db-table-wrap mb-5" id="functions">
            <div class="px-3 pt-3">
                <div class="lic-section-head">
                    <div>
                        <h2 class="lic-h2"><i class="bi bi-grid-3x3-gap"></i> Software by function, across agencies</h2>
                        <p class="lic-sub mb-0">
                            How many different products the City buys to do one job, and in how many
                            agencies: 2 products across 18 agencies is a citywide agreement; 32 is not.
                        </p>
                    </div>
                    <a class="db-btn db-btn-ghost db-btn-sm" href="{{ rtrim(config('apis.fapi_public_entry', 'https://api.databook.nyc'), '/') }}/oce/licenses/capabilities/export"><i class="bi bi-download"></i> CSV</a>
                </div>
            </div>
            {{-- ⚠⚠ THE FRAGMENTATION MAP. The table below ranks functions by distinct
                 products; this plots the two numbers against each other so the
                 finding is visible at a glance: top-left is one or two products used
                 citywide (an agreement working), top-right is many products across
                 many agencies (the consolidation question). Bubble area is value.
                 "Function not identified" is left out — it is not a function. --}}
            <div class="px-3">
                <div class="db-chart-body" style="height: 340px;"><canvas id="licFragChart"></canvas></div>
                <p class="lic-sub mb-2">Each bubble is a function, sized by value. Click one to open it;
                    the table below is ordered by distinct products.</p>
            </div>
            <table class="db-table db-dt" id="licFunctionTable">
                <thead>
                    <tr>
                        <th>Function</th>
                        <th class="lic-num">Distinct products</th>
                        <th class="lic-num">Agencies</th>
                        <th class="lic-num">Contracts</th>
                        <th class="lic-num">Value</th>
                        
                    </tr>
                </thead>
                <tbody>
                @foreach($byCap as $bcap)
                    <tr>
                        {{-- ⚠ `label` comes from the API, which reads it from the
                             capability vocabulary seed. The map that used to live
                             here rendered 18 of these as raw kebab-case keys. --}}
                        <td><a href="{{ route('research.digital-reform.product-capability', ['cap' => $bcap['key']]) }}">{{ $bcap['label'] ?? $bcap['key'] }}</a></td>
                        <td class="lic-num"><strong>{{ number_format($bcap['products']) }}</strong></td>
                        <td class="lic-num">{{ number_format($bcap['agencies']) }}</td>
                        <td class="lic-num">{{ number_format($bcap['contracts']) }}</td>
                        <td class="lic-num" data-order="{{ (int) $bcap['value'] }}">{{ $fmtM($bcap['value']) }}</td>
                        
                    </tr>
                @endforeach
                </tbody>
            </table>
            <div class="px-3 pb-3">
                {{-- ⚠ The badge rule is stated where the badge appears. Without the
                     value floor and the top-10 cap this flag landed on 26 of 46
                     rows, which is wallpaper rather than a signal. --}}
                <p class="lic-sub mb-0">
                            <em>Function not identified</em> is shown, listed last and never flagged. Tags are AI-assigned and unreviewed.
                        </p>
            </div>
        </div>
        @endif

        {{-- ---------- How licenses are bought ---------- --}}
        @if(count($methods))
        <div class="db-table-wrap mb-5" id="routes">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-signpost-split"></i> How these licenses are bought</h2>
                <p class="lic-sub mb-0">
                    None of these {{ number_format($sum['contracts'] ?? 0) }} contracts used competitive sealed bid or proposal. A license usually
                    has one seller, so competition happens when the platform is chosen, not at renewal.
                    Intergovernmental GSA/OGS ({{ number_format($sum['intergov_contracts'] ?? 0) }} here) rides an already-competed schedule. The route worth
                    questioning is a large <strong>Sole Source</strong>.
                    </p>
                {{-- ⚠ The route name reads as either a scandal or an M/WBE program to
                     anyone who has not met it. It is neither. Grounded in PPB Rule
                     3-08 (nyc.gov/site/mocs), not in recall. --}}
                <details class="lic-more">
                    <summary>What these routes mean</summary>
                <p class="lic-sub mb-0" style="margin-top: var(--db-space-2);">
                    <strong>MWBE Non Competitive Small Purchase</strong> is Procurement Policy Board Rule 3-08:
                    direct purchase from a City-certified M/WBE without competition, up to $1.5M (raised from
                    $500,000 in 2020).
                        </p>
                @if(($amb['multi_method'] ?? 0) > 0)
                <p class="lic-sub mb-0" style="margin-top: var(--db-space-2);">
                    {{ number_format($amb['multi_method']) }} contracts record more than one route across their amendments; one row per contract
                    (highest current value) counts each once, so these shares are indicative.
                    </p>
                @endif
                </details>
            </div>
            <table class="db-table db-dt">
                <thead><tr><th>Procurement route</th><th class="lic-num">Contracts</th><th class="lic-num">Share</th><th class="lic-num">Value</th></tr></thead>
                <tbody>
                @foreach($methods as $m)
                    @php $pct = ($sum['contracts'] ?? 0) > 0 ? round(100 * $m['contracts'] / $sum['contracts'], 1) : 0; @endphp
                    <tr>
                        <td>{{ $m['key'] }}</td>
                        <td class="lic-num">{{ number_format($m['contracts']) }}</td>
                        <td class="lic-num">{{ $pct }}%</td>
                        <td class="lic-num">{{ $fmtM($m['value']) }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
            @if(($totals['by_method'] ?? 0) > count($methods))
            <div class="px-3 pb-3">
                <p class="lic-sub mb-0">Showing the {{ count($methods) }} most-used of
                    {{ number_format($totals['by_method']) }} routes.</p>
            </div>
            @endif
        </div>
        @endif

        {{-- ---------- Agencies + vendors ---------- --}}
        <div class="row mb-5" id="agencies">
            <div class="col-lg-6">
                <div class="db-table-wrap">
                    <div class="px-3 pt-3">
                        <h2 class="lic-h2"><i class="bi bi-building"></i> By agency</h2>
                        <p class="lic-sub mb-0">License value per buying agency.
                            @if(($totals['by_agency'] ?? 0) > count($byAg))
                                Showing the top {{ count($byAg) }} of {{ number_format($totals['by_agency']) }};
                                the CSV has them all.
                            @endif
                        </p>
                    </div>
                    <div class="ds-rank px-3 pb-2">
                        @php $barMax = max(1, (float) ($byAg[0]['value'] ?? 1)); @endphp
                        @foreach(array_slice($byAg, 0, 10) as $bx)
                            <a class="ds-bar-row" href="{{ route('research.digital-reform.products') }}?agency={{ urlencode($bx['key']) }}#family-detail">
                                <span class="ds-bar-name">{{ $bx['key'] }}</span>
                                <span class="ds-bar-val">{{ $fmtM($bx['value']) }}</span>
                                <span class="ds-bar-track" aria-hidden="true"><i style="width: {{ max(1, round(100 * $bx['value'] / $barMax)) }}%;"></i></span>
                            </a>
                        @endforeach
                    </div>
                    <details class="px-3 pb-3">
                        <summary class="lic-sub">All {{ number_format($totals['by_agency'] ?? count($byAg)) }} agencies, sortable</summary>
                    <table class="db-table db-dt">
                        <thead><tr><th>Agency</th><th class="lic-num">Contracts</th><th class="lic-num">Value</th></tr></thead>
                        <tbody>
                        @foreach($byAg as $a)
                            <tr>
                                <td>
                                    <a href="{{ route('research.digital-reform.products') }}?agency={{ urlencode($a['key']) }}#family-detail">{{ $a['key'] }}</a>
                                    <span class="lic-prod"><a href="{{ route('agency.procurement', ['name' => $a['key']]) }}">agency profile</a></span>
                                </td>
                                <td class="lic-num">{{ number_format($a['contracts']) }}</td>
                                <td class="lic-num">{{ $fmtM($a['value']) }}</td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                    </details>
                </div>
            </div>
            <div class="col-lg-6">
                <div class="db-table-wrap">
                    <div class="px-3 pt-3">
                        <h2 class="lic-h2"><i class="bi bi-briefcase"></i> By vendor</h2>
                        {{-- ⚠ Named, but NOT by rank: "the largest line is a reseller"
                             would become false the moment the ordering changed. --}}
                        <p class="lic-sub mb-0">Who the City buys licenses from. A reseller can outrank the maker &mdash; Dell Marketing resells the Microsoft agreement.
                            @if(($totals['by_vendor'] ?? 0) > count($byVen))
                                Showing the top {{ count($byVen) }} of {{ number_format($totals['by_vendor']) }};
                                the CSV has them all.
                            @endif
                        </p>
                    </div>
                    <div class="ds-rank px-3 pb-2">
                        @php $barMax = max(1, (float) ($byVen[0]['value'] ?? 1)); @endphp
                        @foreach(array_slice($byVen, 0, 10) as $bx)
                            <a class="ds-bar-row" href="{{ !empty($bx['vendor_id']) ? route('procurement.vendor', $bx['vendor_id']) : route('research.digital-reform.products') . '#agencies' }}">
                                <span class="ds-bar-name">{{ $bx['key'] }}</span>
                                <span class="ds-bar-val">{{ $fmtM($bx['value']) }}</span>
                                <span class="ds-bar-track" aria-hidden="true"><i style="width: {{ max(1, round(100 * $bx['value'] / $barMax)) }}%;"></i></span>
                            </a>
                        @endforeach
                    </div>
                    <details class="px-3 pb-3">
                        <summary class="lic-sub">All {{ number_format($totals['by_vendor'] ?? count($byVen)) }} vendors, sortable</summary>
                    <table class="db-table db-dt">
                        <thead><tr><th>Vendor</th><th class="lic-num">Contracts</th><th class="lic-num">Value</th></tr></thead>
                        <tbody>
                        @foreach($byVen as $v)
                            <tr>
                                <td>
                                    @if(!empty($v['vendor_id']))
                                        <a href="{{ route('procurement.vendor', $v['vendor_id']) }}">{{ $v['key'] }}</a>
                                    @else
                                        {{ $v['key'] }}
                                        <span class="lic-sub" title="Name does not resolve to exactly one PASSPort supplier id, so it is left unlinked rather than linked to a guess">(no unique profile)</span>
                                    @endif
                                </td>
                                <td class="lic-num">{{ number_format($v['contracts']) }}</td>
                                <td class="lic-num">{{ $fmtM($v['value']) }}</td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                    </details>
                </div>
            </div>
        </div>


        <span id="licenses"></span>
        @if($awardOK || $spendOK || $spendPending)
        <div class="db-chart-card mb-4" id="spending">
            <div class="db-chart-head">
                <span class="db-chart-title"><i class="bi bi-graph-up"></i> What was committed, and what was actually paid</span>
                <span class="lic-sub">last {{ (int) ($award['window_years'] ?? $spend['window_years'] ?? 10) }} complete years, plus the year in progress</span>
            </div>
            <div class="lic-two-charts">
                @if($awardOK)
                <div>
                    <div class="lic-tag">Awarded &mdash; contracts starting that year</div>
                    {{-- ⚠ FIXED-HEIGHT WRAPPER IS LOAD-BEARING: a
                         maintainAspectRatio:false canvas with no bounded parent grows
                         without limit (#61). --}}
                    <div class="db-chart-body" style="height: 260px;">
                        <canvas id="licAwardChart"></canvas>
                    </div>
                </div>
                @endif
                @if($spendOK)
                <div>
                    <div class="lic-tag">Paid &mdash; Checkbook payments by City fiscal year</div>
                    <div class="db-chart-body" style="height: 260px;">
                        <canvas id="licSpendChart"></canvas>
                    </div>
                </div>
                @elseif($spendPending)
                {{-- ⚠ SAY SO, do not just omit the card. The payment series is scanned
                     off the request path (a cold scan is ~16s, past the page's API
                     timeout), so for the first few seconds after an API restart there
                     is genuinely nothing to draw. A silently missing chart is
                     indistinguishable from a feature that broke. --}}
                <div>
                    <div class="lic-tag">Paid &mdash; Checkbook payments by City fiscal year</div>
                    <div class="db-chart-body db-empty" style="height: 260px; display: flex; align-items: center; justify-content: center;">
                        <span class="lic-sub">Payment data is still loading &mdash; reload in a moment.</span>
                    </div>
                </div>
                @else
                {{-- ⚠ A FAILED scan says so too. Before 2026-09-23 this half simply
                     vanished, leaving the awarded chart alone under a heading that
                     promises "what was actually paid". --}}
                <div>
                    <div class="lic-tag">Paid &mdash; Checkbook payments by City fiscal year</div>
                    <div class="db-chart-body db-empty" style="height: 260px; display: flex; align-items: center; justify-content: center;">
                        <span class="lic-sub">Payment data could not be loaded{{ !empty($spend['reason']) ? ': ' . $spend['reason'] : '' }}.</span>
                    </div>
                </div>
                @endif
            </div>
            <div style="padding: 0 var(--db-space-3) var(--db-space-3);">
                @if($awardOK)
                <details class="lic-more">
                    <summary>How to read the awarded chart</summary>
                <p class="lic-sub mb-1">
                    <strong>Awarded is a commitment, not cash</strong>: contracts whose term starts that year, over multi-year terms.
                    @if($awardTop && !empty($awardTop['top_family']))
                        {{ $awardTop['label'] }} reads {{ $fmtM($awardTop['value']) }} largely because of
                        one agreement: {{ $awardTop['top_family'] }},
                        {{ $fmtM($awardTop['top_family_value']) }}.
                    @endif
                    @foreach($awardPart as $p)
                        {{ $p['label'] }} is still in progress and is not drawn:
                        {{ $fmtM($p['value']) }} over {{ number_format($p['contracts']) }} contracts so far.
                    @endforeach
                    @if(($awardDrop['contracts'] ?? 0) > 0)
                        {{ number_format($awardDrop['contracts']) }} earlier contracts
                        ({{ $fmtM($awardDrop['value']) }}) start before {{ $awardDrop['before'] }} and are
                        outside the window.
                    @endif
                </p>
                </details>
                @endif
                @if($spendOK)
                <details class="lic-more">
                    <summary>How to read the paid chart</summary>
                <p class="lic-sub mb-1">
                    <strong>Paid is cash out the door</strong>, by City fiscal year (July&ndash;June), so
                    {{ $spendFirst }} begins in the same calendar year as the first award bar.
                    @foreach($spendPart as $p)
                        {{ $p['label'] }} is in progress and is not drawn: {{ $fmtM($p['paid']) }} so far
                        over {{ number_format($p['payments']) }} payments.
                    @endforeach
                    @if(($spendDrop['paid'] ?? 0) > 0)
                        {{ $fmtM($spendDrop['paid']) }} was paid before FY{{ $spendDrop['before'] }} and is
                        outside the window.
                    @endif
                    @if(!empty($spend['as_of']))
                        Latest payment recorded {{ $spend['as_of'] }}.
                    @endif
                </p>
                {{-- ⚠⚠ THE HONEST ANSWER TO "why is paid so much smaller?", and it is
                     NOT a matching failure: a master agreement is a VEHICLE, and
                     agencies buy against it on their own purchase orders, which carry
                     their own contract ids. Every figure here is served. --}}
                </details>
                <details class="lic-sub mb-0"><summary><strong>Why the two do not reconcile</strong> &mdash; paid is a floor</summary>
                <p class="lic-sub mb-0 mt-1">
                    @if($spendMaster && $spendPlain)
                        All {{ number_format($spendMaster['contracts']) }} master agreements on this page
                        &mdash; {{ $fmtM($spendMaster['value']) }} of awarded value &mdash; have
                        {{ ($spendMaster['paid_contracts'] ?? 0) === 0 ? 'no payments at all' : number_format($spendMaster['paid_contracts']) . ' with payments' }}
                        filed under their own contract id, while
                        {{ number_format($spendPlain['paid_contracts']) }} of
                        {{ number_format($spendPlain['contracts']) }} ordinary contracts do.
                    @else
                        {{ number_format($spendCov['contracts_paid'] ?? 0) }} of
                        {{ number_format($spendCov['contracts'] ?? 0) }} contracts have at least one payment.
                    @endif
                    @if($spendBig)
                        The largest with none is {{ $fmtM($spendBig['value']) }}
                        {{ $spendBig['title'] }} ({{ $spendBig['vendor'] }}).
                    @endif
                    That spending is in Checkbook under the purchase orders raised against each agreement, not under the agreement itself, so <strong>treat paid as a floor</strong>: where a contract is visible, it matches Checkbook's own per-contract figure.
                </p>
                </details>
                @endif
            </div>
        </div>
        @endif

        {{-- ---------- Unregistered purchasing vehicles: MOVED ---------- --}}
        {{-- ⚠⚠ THE BLOCK ITSELF NOW LIVES ON THE OVERVIEW, and this is a pointer
             rather than a second copy. The reason is a measured one: scoped to
             vendors who sell licences it was 121 agreements / $1.61B, while the
             same idea scoped to the whole technology universe is 257 / $3.22B.
             Two pages publishing two figures for one question is the defect this
             section spent a week removing, so there is exactly one now — and the
             wider one, because the blind spot is section-level, not licence-level.
             The anchor is kept so old links still land somewhere sensible. --}}
        {{-- Pointers, not copies. Both anchors are kept so old links still land. --}}
        <p class="lic-sub mb-5" id="pipeline">
            <span id="calendar"></span>
            <i class="bi bi-signpost"></i> Only registered contracts are counted here.
            Agreements still in the pipeline, including the citywide vehicles, are on
            <a href="{{ route('research.digital-reform.agreements') }}#awaiting-registration">Agreements</a>
            (as ceilings, added to nothing); the renewal calendar for every technology contract is on
            <a href="{{ route('research.digital-reform.contracts') }}#calendar">Contracts</a>.
        </p>

        {{-- ---------- Fragmentation: the headline ---------- --}}
        {{-- ⚠⚠ "One product, many separate contracts" MERGED INTO THE FAMILY TABLE
             (2026-08-13). It was a filtered, re-sorted subset of that table — same
             rows, same numbers, ranked by agencies instead of value — so a reader
             comparing the two had to work out that they were one dataset shown twice.
             The threshold now renders as a badge on the family rows and a filter above
             them, which keeps the finding and loses the duplicate. --}}
        {{-- ---------- Renewal calendar: MOVED ---------- --}}
        {{-- ⚠⚠ THE CALENDAR NOW LIVES ON THE CONTRACTS PAGE, over the whole
             technology universe rather than licences alone (Phase 2 of the
             2026-08-21 reorg). This is a pointer, not a second copy: two
             calendars answering "what renews when?" with different denominators
             is the two-expiring-figures defect this section spent a week
             removing. The anchor is kept so old links land somewhere sensible. --}}

        {{-- ---------- Method + limits ---------- --}}
        <div class="lic-note" id="method">
            <strong><i class="bi bi-info-circle"></i> How this is built, and what it cannot tell you</strong>
            <ul style="margin: var(--db-space-2) 0 0; padding-left: 1.2rem;">
                <li><strong>License detection is AI, unreviewed.</strong> Two models agreed 92% on a 40-contract sample, so about 1 row in 12 may be wrong either way.</li>
                <li><strong>Classification review is partial.</strong> {{ number_format($reviewed['families'] ?? 0) }} families ({{ $reviewed['share'] ?? 0 }}% of value) carry a hand-reviewed class in a version-controlled seed; the rest were classified in bulk.</li>
                <li><strong>Grouping is curated.</strong> Case and punctuation merge automatically; real aliases come from a mapping file, so a wrong merge is a reviewable change.</li>
                <li><strong>No unit prices.</strong> The data holds no seat or license counts, so no per-seat comparison is possible; value differences reflect scope as much as price.</li>
                <li><strong>No utilization.</strong> Only about 19% of these contracts have Checkbook spend metadata.</li>
                <li><strong>Value</strong> is current value where set, else the award, summed over the term &mdash; not annual spend. <strong>One row per contract</strong> (highest current value); joining amendment rows would inflate totals about 6%.</li>
                <li><strong>Only registered contracts are counted.</strong> Agreements still in approval have no number and are absent; the largest sit under <a href="#pipeline">agreements in the pipeline</a> as ceilings.</li>
                <li><strong>Building on a platform is not licensing it.</strong> Implementation is bought as services, so a platform&rsquo;s licence line can be a fraction of what the City spends on it.</li>
                <li><strong>Most of it has already happened.</strong> {{ number_format($ended['contracts']) }} of {{ number_format($sum['contracts'] ?? 0) }} contracts ({{ $endedPct }}%) had ended before this page was built; an expired term is the base rate, not a finding.</li>
                <li><strong>Route is reported, not judged</strong> &mdash; see <a href="#routes">how these licenses are bought</a>.</li>
            </ul>
        </div>

        @endif
    </div>
</div>
@endsection

@section('scripts')
{{-- ⚠ Sorting/paging only. These tables are SERVER-RENDERED, so DataTables is
     enhancing existing markup, not fetching -- and `order: []` preserves the
     order the API chose. That matters: the function table is deliberately ranked
     by distinct products with "Function not identified" pinned last, and an
     initial client sort would undo both. Money columns carry `data-order` with
     the raw number, or "$643.5M" would sort as a string. --}}
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
{{-- ⚠ The series is passed as JSON, never re-derived here: the year buckets, the
     exclusion of the fiscal year in progress and the payment counts are all
     decided by the API. A chart that recomputed any of them could disagree with
     the caption printed directly beneath it. --}}
document.addEventListener('DOMContentLoaded', function () {
    if (typeof Chart === 'undefined') { return; }
    if (window.DBChart) { DBChart.apply(Chart); }
    var money = function (v) { return window.DBChart ? DBChart.money(v) : v; };

    // ⚠ ONE bar builder for both charts. Two copies is how the licences page came to
    // hold three divergent copies of a label map, 18 tags of which rendered raw.
    var bars = function (canvasId, rows, valueOf, tip) {
        var el = document.getElementById(canvasId);
        if (!el || !rows.length) { return; }
        new Chart(el, {
            type: 'bar',
            data: {
                labels: rows.map(function (y) { return y.label; }),
                datasets: [{
                    data: rows.map(valueOf),
                    // ⚠ Navy, not the section's orange: money is navy across the whole
                    // site, and the orange here is the Analysis identity rather than a
                    // data colour.
                    backgroundColor: (window.DBChart ? DBChart.navy : '#162e51'),
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { ticks: { callback: money } } },
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: function (c) { return tip(rows[c.dataIndex]); } } }
                }
            }
        });
    };

    // Awarded. The tooltip names the year's largest family, because one agreement
    // can BE the bar.
    bars('licAwardChart', @json($awardYears),
        function (y) { return y.value; },
        function (y) {
            var out = ['$' + Math.round(y.value).toLocaleString() + ' awarded',
                       y.contracts.toLocaleString() + ' contracts'];
            if (y.top_family) {
                out.push('largest: ' + y.top_family + ' ' + money(y.top_family_value));
            }
            return out;
        });

    // Paid. The payment and contract counts say how many contracts the year's total
    // is spread across, which is what stops one big renewal reading as a trend.
    bars('licSpendChart', @json($spendYears),
        function (y) { return y.paid; },
        function (y) {
            return ['$' + Math.round(y.paid).toLocaleString() + ' paid',
                    y.payments.toLocaleString() + ' payments',
                    y.contracts.toLocaleString() + ' contracts'];
        });

    // ---- The Products book (shared with the Overview's Products band) ----
    @include('procurement.partials.slice-pies-js')
    @include('procurement.partials.products-book-js')
    paintLegends();

    // ---- The fragmentation map ------------------------------------------
    // ⚠ Points are built in the CONTROLLER (fragPoints) from the served
    // by_capability rows — the same rows the table renders — so the script
    // derives nothing and a bubble cannot disagree with its row. The
    // abstention ("Function not identified") is left out there.
    (function () {
        var el = document.getElementById('licFragChart');
        var fp = @json($fragPoints ?? ['many' => [], 'other' => []]);
        if (!el || !(fp.many.length + fp.other.length)) { return; }
        var capBase = @json(route('research.digital-reform.product-capability', ['cap' => '__CAP__']));
        new Chart(el, {
            type: 'bubble',
            data: { datasets: [
                { label: 'Many products, many agencies', data: fp.many,
                  backgroundColor: 'rgba(194,133,12,0.55)', borderColor: DBChart.slice[3] },
                { label: 'Other functions', data: fp.other,
                  backgroundColor: 'rgba(22,46,81,0.35)', borderColor: DBChart.navy }
            ] },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: { x: { title: { display: true, text: 'Distinct products' }, beginAtZero: true },
                          y: { title: { display: true, text: 'Buying agencies' }, beginAtZero: true } },
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, padding: 10, font: { size: 11 } } },
                    tooltip: { callbacks: {
                        title: function (items) { return items[0].raw.row.label; },
                        label: function (c) { var r = c.raw.row;
                            return [r.products + ' products · ' + r.agencies + ' agencies',
                                    r.contracts + ' contracts · ' + money(r.value)]; }
                    } }
                },
                onClick: function (e, els) {
                    if (!els.length) { return; }
                    var r = this.data.datasets[els[0].datasetIndex].data[els[0].index].row;
                    window.location = capBase.replace('__CAP__', encodeURIComponent(r.key));
                }
            }
        });
    })();
});
</script>
<script>
$(document).ready(function () {
    if ($.fn.DataTable) {
        if ($('#licFamilyTable').length) {
            var famTable = $('#licFamilyTable').DataTable({
                order: [],
                // ⚠ Not a literal: the section's page size has one owner in
                // js/db-tables.js. This table is not on `db-dt` because the
                // families table keeps its own init for the CSV/search layout, but it must not drift.
                pageLength: (window.DB_TABLE_PAGE || 10),
                deferRender: true,
                lengthChange: false,
                // ⚠ Was `'<"lic-dt-top"f>rtip'`, and `lic-dt-top` is styled by
                // NOTHING — grep it: the class appears in this one line and in no
                // stylesheet, so this table's search box has always rendered raw
                // while `info` and the pager sat loose in the wrapper. Same layout
                // as every other table in the section now (js/db-tables.js).
                dom: "<'db-table-toolbar'f>rt<'db-table-footer'ip>"
            });
        }
        // ⚠ #licFunctionTable's bespoke init is GONE -- it now carries `db-dt` and
        // is initialised by js/db-tables.js like every other table in the section.
        // It used to be `paging: false`; the standard gives it 10 a page. Its
        // deliberate ranking (by distinct products, "Function not identified"
        // pinned last) survives because the shared init also passes `order: []`.
    }
});
</script>
@endsection
