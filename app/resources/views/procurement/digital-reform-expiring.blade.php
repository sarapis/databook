@extends('layout')

@section('head')
<style>
    /* Expiring Digital Service Contracts (Renewal Review Queue) - page glue. */
    .db-page-lead { max-width: 68ch; }
    /* The flag mix: an HTML bar list rather than a canvas, because every row is
       a link into the filtered queue and a canvas click is invisible to the
       keyboard and to a screen reader. */
    .ds-flag-row { display: grid; grid-template-columns: 1fr auto; gap: 2px var(--db-space-2);
                   padding: 6px var(--db-space-1); border-top: 1px solid var(--db-border);
                   color: inherit; text-decoration: none; font-size: var(--db-text-sm); }
    .ds-flag-row:first-child { border-top: 0; }
    .ds-flag-row:hover { background: var(--db-navy-050); }
    .ds-flag-n { font-variant-numeric: tabular-nums; font-weight: var(--db-weight-semibold); }
    .ds-flag-bar { grid-column: 1 / -1; height: 6px; background: var(--db-navy-050); border-radius: 3px; }
    .ds-flag-bar i { display: block; height: 100%; background: var(--db-primary); border-radius: 3px; }
    #method summary { cursor: pointer; }
    .dr-filter-form { margin-bottom: var(--db-space-3); }
    .dr-filter-form .db-btn { white-space: nowrap; }
    .rr-flag { display: inline-flex; align-items: center; gap: 4px; margin: 1px 2px 1px 0; }
    .rr-flags-cell { min-width: 180px; }
    .rr-exp-date { font-weight: var(--db-weight-bold); white-space: nowrap; }
    .rr-exp-days { font-size: var(--db-text-2xs); color: var(--db-text-muted); }
    .rr-method { font-size: var(--db-text-2xs); }
    .rr-grown { font-size: var(--db-text-2xs); color: var(--db-danger-fg, #b42318); white-space: nowrap; }
    .rr-toggle { line-height: 1; }
    .rr-toggle .bi { transition: transform var(--db-transition); }
    .rr-toggle[aria-expanded="true"] .bi { transform: rotate(180deg); }
    .rr-dossier-row > td { background: var(--db-gray-050, #f8f9fb); padding: 0 !important; border-top: 0; }
    .rr-dossier { padding: var(--db-space-3); }
    .rr-dossier h6 { font-size: var(--db-text-xs); text-transform: uppercase; letter-spacing: var(--db-tracking-wide); color: var(--db-text-muted); margin: 0 0 var(--db-space-1); }
    .rr-dossier-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--db-space-3); }
    @media (max-width: 768px) { .rr-dossier-grid { grid-template-columns: 1fr; } }
    .rr-meta { list-style: none; padding: 0; margin: 0; font-size: var(--db-text-sm); }
    .rr-meta li { padding: 2px 0; }
    .rr-meta .k { color: var(--db-text-muted); margin-right: 6px; }
    .rr-why { list-style: none; padding: 0; margin: 0; }
    .rr-why li { font-size: var(--db-text-sm); padding: 3px 0; display: flex; gap: 6px; }
    .rr-notice { display: block; padding: 4px 0; font-size: var(--db-text-sm); border-bottom: 1px solid var(--db-border); }
    .rr-notice:last-child { border-bottom: 0; }
    .rr-notice .meta { color: var(--db-text-muted); font-size: var(--db-text-2xs); }
</style>
@include('procurement.partials.ds-styles')
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    // Moved-in sections (2026-08-21 reorg) read these from the shared payload.
    $segSel = $contracts['segment'] ?? '';
    $cal    = $calendar ?? [];
    // ⚠ The flag vocabulary is the controller's QUEUE_FLAGS — ONE list for this
    // page and the Contracts page's flag mix.
    $flagMeta = [];
    $flagOptions = [];
    foreach (($queueFlags ?? []) as $fk => $fv) {
        $flagMeta[$fk] = ['cls' => $fv['cls'], 'icon' => $fv['icon']];
        $flagOptions[$fk] = $fv['label'];
    }
    // Plain text only: these render through Blade escaping ({{ $bl }}), so an HTML entity
    // here reaches the user literally. Parenthetical matches $flagOptions ("Underused
    // (shelfware)") and stays ASCII per #66, which is what put "&mdash;" here.
    $buildbuyOptions = ['high' => 'High (easily replaceable)', 'medium' => 'Medium (feasible)', 'low' => 'Low (specialized)'];
    $expSummary = $expiring['summary'] ?? [];
    $expOptions = $expiring['options'] ?? ['years' => [], 'agencies' => [], 'methods' => [], 'categories' => []];
    $expFiltered = ($expiringYear || $expiringAgency || $expiringMethod || $expiringMin || $expiringFlag
                    || $expiringCategory || $expiringLicense || $expiringBuildbuy || $expiringShowNonTech
                    || $expiringProduct);
    $expCtl = ['expiring_flag','expiring_year','expiring_agency','expiring_method','expiring_min','expiring_sort',
               'expiring_page','expiring_category','expiring_license','expiring_buildbuy','expiring_shownontech'];
    // Which scope the API served, read from the payload rather than assumed.
    // ⚠ The whole section is on the derived scope as of 2026-08-13 (the Overview was
    // the last page on the old one), so this no longer distinguishes THIS page from
    // its siblings — it distinguishes a live page from a rolled-back one, which is
    // still worth reading from the payload rather than asserting in copy.
    $expScope = $expiring['scope'] ?? [];
    $expPositiveScope = (bool) ($expScope['positive'] ?? false);
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <a href="{{ route('research.digital-reform') }}" class="db-btn db-btn-ghost db-btn-sm mb-2"><i class="bi bi-arrow-left"></i> Digital Services</a>
        <h1>Contracts</h1>
        {{-- ⚠ ONE sentence. This lead used to be two drafts merged ("searchable
             below ... searchable below"), and the caveats it carried now live in
             the two disclosures under it. --}}
        <p class="db-page-lead">
            Every technology contract the City has registered: who holds it, what it
            buys, what renews before 2030, and which renewals deserve a second look.
        </p>
        @include('sub.analysis-tag')
        {{-- ONE scope note for the whole section — see the partial. A guard asserts
             all three pages include it, because three pages explaining themselves
             three different ways is how the section ended up with two universes. --}}
        @include('sub.digital-scope-note', ['scope' => $expiring['scope'] ?? []])

        {{-- ============ 1. THE WHOLE BOOK — the SAME tiles and charts the
             Overview's Contracts band previews. The band links here, so the page
             opens on what the band showed. ============ --}}
        <div class="db-stat-grid mt-3 mb-4">
            <div class="db-stat">
                <div class="db-stat-label">Technology contracts</div>
                <div class="db-stat-value">{{ number_format($stats['count'] ?? 0) }}</div>
                <div class="db-stat-sub">
                    {{ number_format($stats['active_count'] ?? 0) }} not known to have ended &middot;
                    {{ number_format($stats['ended_count'] ?? 0) }} ended
                </div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Committed value, all time</div>
                <div class="db-stat-value">${{ number_format(($stats['committed_total'] ?? 0) / 1000000, 0) }}M</div>
                <div class="db-stat-sub">
                    ${{ number_format(($stats['committed_active_total'] ?? 0) / 1000000, 0) }}M still running &middot;
                    ${{ number_format(($stats['committed_ended_total'] ?? 0) / 1000000, 0) }}M ended
                </div>
            </div>
            @if(($stats['ceiling_total'] ?? 0) > 0)
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-layers"></i> Ceilings, not spend</div>
                <div class="db-stat-value">${{ number_format(($stats['ceiling_total'] ?? 0) / 1000000, 0) }}M</div>
                <div class="db-stat-sub">{{ number_format($stats['master_count'] ?? 0) }} master agreements &mdash;
                    <a href="{{ route('research.digital-reform.agreements') }}">headroom, never added</a></div>
            </div>
            @endif
        </div>

        @include('procurement.partials.contracts-book')

        {{-- ============ ALL TECHNOLOGY CONTRACTS — the searchable index over the
             whole universe (moved from the Overview's tabs in Phase 1). Placed
             directly under the whole-book charts it drills into (2026-09-23), with
             Agency and Kind filters and the section's 10-row page.
             ⚠ Phase 1 moved the table but its heading comment was consumed by the
             tab-pane extraction, so the section rendered untitled. ============ --}}
        <h2 class="mt-4" style="font-size: var(--db-text-lg);"><i class="bi bi-list-ul"></i> All technology contracts</h2>

        <div class="db-table-wrap mb-5" id="all-digital-contracts">
            <div class="px-3 pt-3">
                <form method="GET" action="{{ url()->current() }}#all-digital-contracts" class="db-filter-bar dr-filter-form">
                    @foreach(request()->except(['contract_q','contract_method','contract_agency','contract_segment','contract_page']) as $k => $v)
                        <input type="hidden" name="{{ $k }}" value="{{ $v }}">
                    @endforeach
                    <div class="db-search">
                        <i class="bi bi-search"></i>
                        <input type="search" name="contract_q" value="{{ $contractQ }}" placeholder="Search vendor, title, agency, ID&hellip;" aria-label="Search contracts">
                    </div>
                    <div class="db-field">
                        <label for="contract_method">Procurement method</label>
                        <select name="contract_method" id="contract_method">
                            <option value="">All methods</option>
                            @foreach(($contractOptions['methods'] ?? []) as $m)
                                <option value="{{ $m }}" {{ $contractMethod === $m ? 'selected' : '' }}>{{ $m }}</option>
                            @endforeach
                        </select>
                    </div>
                    <div class="db-field">
                        <label for="contract_agency">Agency</label>
                        <select name="contract_agency" id="contract_agency">
                            <option value="">All agencies</option>
                            @foreach(($contractOptions['agencies'] ?? []) as $ag)
                                <option value="{{ $ag }}" {{ $contractAgency === $ag ? 'selected' : '' }}>{{ $ag }}</option>
                            @endforeach
                        </select>
                    </div>
                    {{-- "Kind" is the composition SEGMENT — the Kind column below and the
                         type pie above — resolved by modules/techsegments from the slug. --}}
                    <div class="db-field">
                        <label for="contract_segment">Kind</label>
                        <select name="contract_segment" id="contract_segment">
                            <option value="">All kinds</option>
                            @foreach(($composition['segments'] ?? []) as $sg)
                                @if(($sg['slug'] ?? '') !== '')
                                <option value="{{ $sg['slug'] }}" {{ ($contracts['segment_slug'] ?? '') === $sg['slug'] ? 'selected' : '' }}>{{ $sg['segment'] }}</option>
                                @endif
                            @endforeach
                        </select>
                    </div>
                    <button type="submit" class="db-btn db-btn-primary db-btn-sm"><i class="bi bi-funnel"></i> Apply</button>
                    @if($contractQ || $contractMethod || $contractAgency || $segSel !== '')
                        <a href="{{ url()->current() }}?{{ http_build_query(request()->except(['contract_q','contract_method','contract_agency','contract_segment','contract_page'])) }}#all-digital-contracts" class="db-btn db-btn-ghost db-btn-sm">Clear</a>
                    @endif
                </form>

                {{-- ⚠ The composition drill-down is NOT one of the form controls above, so
                     without this chip the table would silently be showing a subset. --}}
                @if($segSel !== '')
                <div class="mb-3" style="font-size: var(--db-text-sm);">
                    <span class="db-badge db-badge-info ds-chip">
                        <i class="bi bi-diagram-3"></i> {{ $segSel }}
                        <a href="{{ url()->current() }}?{{ http_build_query(request()->except(['contract_segment','contract_page'])) }}#all-digital-contracts"
                           title="Show all technology contracts">&times;</a>
                    </span>
                    <span class="text-muted">{{ number_format($contracts['total'] ?? 0) }} contracts in this segment.</span>
                </div>
                @endif
            </div>
            <div class="table-responsive">
                <table class="db-table db-table-striped">
                    <thead>
                        <tr>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'vendor', 'contract_order' => ($contractSort == 'vendor' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    Vendor @if($contractSort == 'vendor'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>Agency</th>
                            <th>Contract ID</th>
                            <th>Title</th>
                            <th>Method</th>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'date', 'contract_order' => ($contractSort == 'date' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    Start Date @if($contractSort == 'date'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'end_date', 'contract_order' => ($contractSort == 'end_date' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    End Date @if($contractSort == 'end_date'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th class="db-num">
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'amount', 'contract_order' => ($contractSort == 'amount' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    Amount @if($contractSort == 'amount'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>Kind</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse(($contracts['contracts'] ?? []) as $c)
                        <tr>
                            <td>
                                @if($c['vendor_id'] ?? null)
                                    <a href="/procurement/vendor/{{ $c['vendor_id'] }}">{{ $c['vendor_name'] }}</a>
                                @else
                                    <a href="/procurement/vendors?q={{ urlencode($c['vendor_name']) }}">{{ $c['vendor_name'] }}</a>
                                @endif
                            </td>
                            <td>{{ $c['agency'] }}</td>
                            <td><a href="/procurement/contract/{{ $c['ctr_id'] ?? $c['contract_id'] }}">{{ $c['contract_id'] }}</a></td>
                            <td class="text-muted small">{{ $c['contract_title'] ?? '' }}</td>
                            <td class="text-muted small">{{ $c['procurement_method'] ?? '' }}</td>
                            <td>{{ $c['start_date'] }}</td>
                            <td>{{ $c['end_date'] }}</td>
                            <td class="db-num">${{ number_format($c['award_amount'] ?? 0, 0) }}</td>
                            {{-- ⚠ The row's composition segment, resolved by the same module as
                                 the bar. It replaced a badge that read the constant "Digital". --}}
                            <td><span class="db-badge {{ ($c['is_license'] ?? false) ? 'db-badge-info' : 'db-badge-neutral' }}">{{ $c['segment'] ?? '' }}</span></td>
                        </tr>
                        @empty
                        <tr><td colspan="9" class="text-center text-muted py-4">No contracts match your filters.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
            @if(($contracts['total_pages'] ?? 0) > 1)
            <div class="db-table-footer">
                <span class="db-table-count">Page {{ $contractPage }} of {{ number_format($contracts['total_pages']) }} · {{ number_format($contracts['total'] ?? 0) }} entries</span>
                <nav aria-label="Contracts pagination">
                    <ul class="pagination db-pagination mb-0">
                        <li class="page-item {{ $contractPage == 1 ? 'disabled' : '' }}">
                            @if($contractPage == 1)<span class="page-link">Previous</span>@else<a class="page-link" href="{{ request()->fullUrlWithQuery(['contract_page' => $contractPage - 1]) }}#all-digital-contracts">Previous</a>@endif
                        </li>
                        <li class="page-item {{ $contractPage >= ($contracts['total_pages'] ?? 1) ? 'disabled' : '' }}">
                            @if($contractPage >= ($contracts['total_pages'] ?? 1))<span class="page-link">Next</span>@else<a class="page-link" href="{{ request()->fullUrlWithQuery(['contract_page' => $contractPage + 1]) }}#all-digital-contracts">Next</a>@endif
                        </li>
                    </ul>
                </nav>
            </div>
            @endif
        </div>

        {{-- ============ 2. WHAT RENEWS BEFORE 2030 ============ --}}
        @php
            $calYears  = $cal['years'] ?? [];
            $calEnded  = $cal['ended'] ?? ['contracts' => 0, 'value' => 0];
            $calNoEnd  = (int) ($cal['no_end_date'] ?? 0);
            $calTotal  = (int) ($cal['total_contracts'] ?? 0);
            $calWindow = $cal['in_queue_window'] ?? ['contracts' => 0, 'committed' => 0, 'ceiling' => 0];
            $calHorizonYear = substr((string) ($cal['horizon'] ?? '2030-01-01'), 0, 4);
            // Precomputed: a Blade directive glued to a word character is not compiled.
            $calNoEndPhrase = $calNoEnd > 0 ? '; ' . number_format($calNoEnd) . ' carry no usable end date' : '';
            // ⚠ COMMITTED MONEY AND CEILINGS ARE NOT ONE NUMBER. Master agreements
            // are headroom agencies may buy against — 0% carry a payment under
            // their own id. Summing them produced a headline that was 44% ceiling.
            $expCommitted = $expSummary['committed_value'] ?? $expSummary['total_value'] ?? 0;
            $expCeiling   = $expSummary['ceiling_value'] ?? 0;
            $expCeilingN  = $expSummary['ceiling_count'] ?? 0;
            // Blade trap: a directive glued to a word character is not compiled,
            // so the phrase is built here rather than inline.
            $expCeilingSub = $expCeilingN . ' master ' . ($expCeilingN == 1 ? 'agreement' : 'agreements');
            // ⚠ The flag mix is a SHARE OF THE QUEUE, measured over the filtered
            // set the summary describes. Rendering it is what makes a saturated
            // flag visible: one that fires on nearly every row says nothing about
            // any row, and a bare count tile hid that.
            $expCount = (int) ($expSummary['count'] ?? 0);
            $flagMix = [];
            foreach ($flagOptions as $fk => $fl) {
                $n = (int) ($expSummary[$fk] ?? 0);
                $flagMix[] = ['key' => $fk, 'label' => $fl, 'n' => $n,
                              'pct' => $expCount > 0 ? 100 * $n / $expCount : 0];
            }
            usort($flagMix, function ($a, $b) { return $b['n'] <=> $a['n']; });
        @endphp
        <section class="ds-band" id="renewals" aria-labelledby="renewals-h">
            <h2 id="renewals-h" class="ds-band-title">What renews before {{ $calHorizonYear }}</h2>
            <p class="ds-band-lead mb-3">
                {{ number_format($calWindow['contracts'] ?? 0) }} contracts end before {{ $calHorizonYear }}.
                Each one is a decision the City will make: renew it as it stands, re-bid it, or let it go.
            </p>

            <div class="db-stat-grid mb-4">
                <div class="db-stat">
                    <div class="db-stat-label">Expiring before {{ $calHorizonYear }}</div>
                    <div class="db-stat-value">{{ number_format($expSummary['count'] ?? 0) }}</div>
                    <div class="db-stat-sub">{{ $expFiltered ? 'Matching filters' : 'Technology contracts' }}</div>
                </div>
                <div class="db-stat is-accent">
                    <div class="db-stat-label">Committed value up for renewal</div>
                    <div class="db-stat-value">${{ number_format($expCommitted / 1000000, 1) }}M</div>
                    <div class="db-stat-sub">Current value, where one exists</div>
                </div>
                @if($expCeiling > 0)
                <div class="db-stat">
                    <div class="db-stat-label"><i class="bi bi-layers"></i> Ceilings, not spend</div>
                    <div class="db-stat-value">${{ number_format($expCeiling / 1000000, 1) }}M</div>
                    <div class="db-stat-sub">{{ $expCeilingSub }} &mdash; headroom to buy against</div>
                </div>
                @endif
                <div class="db-stat">
                    <div class="db-stat-label"><i class="bi bi-key"></i> Software licenses</div>
                    <div class="db-stat-value">{{ number_format($expSummary['licenses'] ?? 0) }}</div>
                    <div class="db-stat-sub">${{ number_format(($expSummary['licenses_value'] ?? 0) / 1000000, 1) }}M &middot;
                        <a href="{{ route('research.digital-reform.products') }}">analysed in full</a></div>
                </div>
            </div>

            <div class="row g-4 mb-4">
                <div class="col-lg-7">
                    {{-- ============ THE RENEWAL CALENDAR — its ONE home (Phase 2).
                         A chart now, not a table: the table rendered the same seven
                         rows the old by-year chart above it already drew. ============ --}}
                    <div class="db-chart-card h-100" id="calendar">
                        <div class="db-chart-head"><span class="db-chart-title">When they end</span></div>
                        @if($cal['available'] ?? false)
                        <div class="db-chart-body" style="height: 300px;"><canvas id="renewalCliffChart"></canvas></div>
                        <div class="ds-seglinks">
                            @foreach($calYears as $cy)
                                @if((int) ($cy['in_queue'] ?? 0) > 0)
                                    <a href="{{ route('research.digital-reform.review', ['expiring_year' => $cy['year']]) }}#expiring-contracts">{{ $cy['year'] }}: {{ number_format($cy['contracts']) }}</a>
                                @endif
                            @endforeach
                        </div>
                        <p class="ds-chart-note">
                            Committed money and master-agreement <strong>ceilings</strong> are separate
                            bars and are never added: a ceiling is the most that may be bought, not money
                            owed. Years from {{ $calHorizonYear }} are outside the review window.
                            {{-- ⚠ All three buckets are stated because a calendar that silently
                                 drops rows reads as the whole inventory. They sum to the
                                 contract count, and a guard pins that. --}}
                            Of {{ number_format($calTotal) }} contracts, {{ number_format($calEnded['contracts']) }}
                            have already ended and are not shown{{ $calNoEndPhrase }}.
                        </p>
                        @else
                        <p class="text-muted px-3 py-3" style="font-size: var(--db-text-sm);">
                            <strong>The renewal calendar is unavailable</strong> right now. The queue below is unaffected.
                        </p>
                        @endif
                    </div>
                </div>
                <div class="col-lg-5">
                    <div class="db-chart-card h-100" id="flag-mix">
                        <div class="db-chart-head"><span class="db-chart-title">Why they are flagged</span></div>
                        <div class="ds-rank px-3 pb-2">
                            @foreach($flagMix as $fm)
                                @php
                                    $fmMeta = $flagMeta[$fm['key']] ?? ['icon' => 'bi-flag'];
                                    $fmW = max(1, round($fm['pct']));
                                @endphp
                                <a class="ds-flag-row" href="{{ route('research.digital-reform.review', ['expiring_flag' => $fm['key']]) }}#expiring-contracts">
                                    <span class="ds-flag-name"><i class="bi {{ $fmMeta['icon'] }}"></i> {{ $fm['label'] }}</span>
                                    <span class="ds-flag-n">{{ number_format($fm['n']) }}</span>
                                    <span class="ds-flag-bar" aria-hidden="true"><i style="width: {{ $fmW }}%;"></i></span>
                                </a>
                            @endforeach
                        </div>
                        <p class="ds-chart-note">
                            Share of the {{ number_format($expCount) }} contracts above. A flag on nearly every
                            contract describes how the City buys technology, not which renewal to question.
                        </p>
                    </div>
                </div>
            </div>
        {{-- ============ RENEWING SOON — the ten contracts ending first, read-only.
             The working tool (filters, flags, dossiers, CSV) is the Renewal Review
             Queue's own page, linked below. This page never passes a queue
             parameter, so these are the queue's unfiltered first ten by expiry. --}}
        <div class="db-table-wrap mb-3" id="renewing-soon">
            <div class="px-3 pt-3">
                <h3 style="font-size: var(--db-text-base);" class="mb-1"><i class="bi bi-hourglass-split"></i> Renewing soon</h3>
                <p class="text-muted mb-2" style="font-size: var(--db-text-sm);">The ten technology contracts that end first.</p>
            </div>
            <div class="table-responsive">
                <table class="db-table db-table-striped">
                    <thead><tr><th>Ends</th><th>Vendor</th><th>Agency</th><th>What it buys</th><th class="db-num">Value</th><th class="db-num">Flags</th></tr></thead>
                    <tbody>
                    @forelse(array_slice($expiring['contracts'] ?? [], 0, 10) as $c)
                        @php $d = $c['days_to_expiry'] ?? null; @endphp
                        <tr>
                            <td class="text-nowrap">
                                <a href="/procurement/contract/{{ $c['ctr_id'] ?? $c['contract_id'] }}" class="rr-exp-date">{{ $c['end_date'] }}</a>
                                @if($d !== null)<div class="rr-exp-days">in {{ number_format($d) }} {{ $d == 1 ? 'day' : 'days' }}</div>@endif
                            </td>
                            <td>
                                @if($c['vendor_id'] ?? null)
                                    <a href="/procurement/vendor/{{ $c['vendor_id'] }}">{{ $c['vendor_name'] }}</a>
                                @else
                                    {{ $c['vendor_name'] }}
                                @endif
                            </td>
                            <td class="small">{{ $c['agency'] }}</td>
                            <td class="small text-muted">{{ ($c['function_category'] ?? '') !== '' ? $c['function_category'] : ($c['contract_title'] ?? '') }}</td>
                            <td class="db-num">
                                ${{ number_format($c['value'] ?? $c['award_amount'] ?? 0, 0) }}
                                @if(($c['amount_kind'] ?? 'committed') === 'ceiling')<div class="rr-grown">ceiling, not spend</div>@endif
                            </td>
                            <td class="db-num">{{ count($c['flags'] ?? []) }}</td>
                        </tr>
                    @empty
                        <tr><td colspan="6" class="text-center text-muted py-4">No technology contracts end before {{ $calHorizonYear }}.</td></tr>
                    @endforelse
                    </tbody>
                </table>
            </div>
        </div>
        <div class="d-flex flex-wrap align-items-center gap-3 mb-2">
            <a href="{{ route('research.digital-reform.review') }}" class="db-btn db-btn-primary">
                <i class="bi bi-list-check"></i> Open the Renewal Review Queue <i class="bi bi-arrow-right"></i>
            </a>
            <span class="text-muted" style="font-size: var(--db-text-sm);">
                All {{ number_format($expSummary['count'] ?? 0) }}, with filters by agency, method and review flag,
                a dossier per contract, and a CSV download.
            </span>
        </div>
        </section>



    </div> <!-- /.container -->
</div> <!-- /.inner_container -->

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {
    DBChart.apply(Chart);
    const currencyFmt = (val) => '$' + val.toLocaleString(undefined, { maximumFractionDigits: 0 });
    const chartData = @json($charts ?? []);

    {{-- ⚠ The start-year chart comes BEFORE the pie factory, as it always did:
         the band's two ovPie() calls in it resolve through function hoisting. --}}
    @include('procurement.partials.contracts-book-js')
    @include('procurement.partials.slice-pies-js')
    paintLegends();

    // ---- When they end: committed money and ceilings, SIDE BY SIDE --------
    // ⚠⚠ Two datasets, NOT stacked. A ceiling is headroom (0% of masters carry a
    // payment under their own id), so stacking it would draw undrawn headroom as
    // money owed (#294). Years past the review window are shown muted.
    const calYears = @json($calYears ?? []);
    const calHorizon = @json($calHorizonYear ?? '2030');
    const cliffEl = document.getElementById('renewalCliffChart');
    if (calYears.length && cliffEl) {
        const inWin = (d) => Number(d.in_queue) > 0 && d.year < calHorizon;
        const musd = (v) => '$' + (Number(v) / 1000000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'M';
        new Chart(cliffEl, {
            type: 'bar',
            data: {
                labels: calYears.map(d => d.year),
                datasets: [
                    { label: 'Committed', data: calYears.map(d => d.committed), borderRadius: 4,
                      backgroundColor: calYears.map(d => inWin(d) ? DBChart.navy : DBChart.sliceOther) },
                    { label: 'Master-agreement ceiling (not spend)', data: calYears.map(d => d.ceiling), borderRadius: 4,
                      backgroundColor: calYears.map(d => inWin(d) ? DBChart.slice[3] : DBChart.sliceUnknown) }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: { y: { ticks: { callback: (val) => '$' + (val / 1000000).toFixed(0) + 'M' } } },
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, padding: 10, font: { size: 11 } } },
                    tooltip: { callbacks: {
                        label: (c) => c.dataset.label + ': ' + musd(c.parsed.y),
                        afterBody: (items) => {
                            const d = calYears[items[0].dataIndex]; if (!d) { return ''; }
                            return [d.contracts + ' contracts' + (inWin(d) ? ' in the review queue' : ' (after the review window)')];
                        }
                    } }
                }
            }
        });
    }
});
</script>
@endsection
