@extends('layout')

@section('head')
<style>
    /* Digital Services Analysis: Master Agreements (2026-08-21 reorg). */
    .db-page-lead { max-width: none; }
</style>
@include('procurement.partials.ds-styles')
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    // Precomputed — a Blade directive glued to a word character is not compiled.
    $maRows  = $ma['rows'] ?? [];
    $maCount = (int) ($ma['count'] ?? 0);
    $maCeil  = (float) ($ma['total_ceiling'] ?? 0);
    $maDraw  = $ma['drawdown'] ?? ['tracked' => 0, 'drawn' => 0, 'drawn_value' => 0, 'untracked' => 0];
    $fmtM = function ($v) {
        $v = (float) $v;
        if ($v >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
        if ($v >= 1000000)    return '$' . number_format($v / 1000000, 1) . 'M';
        if ($v >= 1000)       return '$' . number_format($v / 1000, 0) . 'K';
        return '$' . number_format($v, 0);
    };
    // Precomputed: a Blade directive beside punctuation is how this section 500'd.
    $drawnNote = ($maDraw['drawn_value'] ?? 0) > 0
        ? ', $' . number_format($maDraw['drawn_value'] / 1000000, 1) . 'M in total' : '';
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <a href="{{ route('research.digital-reform') }}" class="db-btn db-btn-ghost db-btn-sm mb-2"><i class="bi bi-arrow-left"></i> Digital Services</a>
        <h1>Agreements</h1>
        {{-- ⚠ RENAMED "Master Agreements" -> "Agreements" (owner, 2026-09-16), in
             the submenu, the heading and the URL together. The prose below still
             says "master agreement" where it names the INSTRUMENT, because that is
             what PASSPort calls it and what the contract ids encode (MA/MMA) — the
             page title is a label, the instrument is a fact. --}}
        <p class="db-page-lead">
            The master agreements agencies buy technology <em>against</em>. Each figure is a
            <strong>ceiling &mdash; the most that may be bought, not spend</strong>. Agreements still in
            approval are <a href="#awaiting-registration">listed separately</a>.
        </p>
        @include('sub.analysis-tag')

        @if(!($ma['available'] ?? false))
            <div class="db-alert db-alert-warning" role="alert">
                <i class="bi bi-exclamation-triangle"></i>
                <div class="db-alert-body">Master agreement data is not available right now. Please try again shortly.</div>
            </div>
        @else

        {{-- The same three views the Overview's Agreements band previews (2026-09-23). --}}
        <div class="mt-3 mb-4">
            @include('procurement.partials.agreements-book')
        </div>

        <div class="db-stat-grid mb-4">
            <div class="db-stat">
                <div class="db-stat-label">Registered master agreements</div>
                <div class="db-stat-value">{{ number_format($maCount) }}</div>
                <div class="db-stat-sub">MA and MMA instruments in the technology universe</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Combined ceiling</div>
                <div class="db-stat-value">${{ number_format($maCeil / 1000000, 0) }}M</div>
                <div class="db-stat-sub">The most that may be bought &mdash; <strong>not</strong> spend</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Agencies &middot; vendors</div>
                <div class="db-stat-value">{{ number_format($ma['agencies'] ?? 0) }} &middot; {{ number_format($ma['vendors'] ?? 0) }}</div>
                <div class="db-stat-sub">Holding agencies and counterparties</div>
            </div>
        </div>

        {{-- ============ THE MECHANISM, explained once, with measured numbers.
             This story previously lived in footnotes across three pages. ============ --}}
        <div class="db-alert db-alert-info mb-5" role="region" aria-label="How master agreements are drawn against">
            <i class="bi bi-info-circle"></i>
            <div class="db-alert-body">
                <strong>Why these agreements look unspent</strong>
                <p class="mb-1 mt-1" style="font-size: var(--db-text-sm);">
                    <strong>{{ number_format($maDraw['drawn']) }} of {{ number_format($maCount) }} show any
                    payment under their own contract id</strong>. That is how the instrument works: an
                    agency buying against a master raises its own purchase order, and the payment is
                    filed there.
                </p>
                <details class="lic-more">
                    <summary>The clearest example, and what a blank cell means</summary>
                    <p class="lic-sub mb-0 mt-1">
                        The City has paid <strong>Dell Marketing $1.86bn across 29,822 contract ids</strong>,
                        while the $573.8M Citywide Microsoft agreement it holds shows <strong>zero</strong>
                        under its own. Reading that zero as "unused" would be exactly backwards.
                        {{-- ⚠ Only 22 of 186 carry a Checkbook record at all, so a blank
                             cell means "not tracked under this id", never "$0". --}}
                        Where a figure is shown below it is CheckbookNYC's own per-contract record
                        ({{ number_format($maDraw['tracked']) }} of {{ number_format($maCount) }} have
                        one{{ $drawnNote }});
                        the rest read <em>not tracked here</em>, never zero.
                    </p>
                </details>
            </div>
        </div>

        {{-- ============ All registered agreements ============ --}}
        <h2 class="mb-2" style="font-size: var(--db-text-lg);"><i class="bi bi-journal-check"></i> All registered agreements</h2>
        <div class="row g-4 mb-3">
            <div class="col-lg-6">
                <div class="db-chart-card h-100">
                    <div class="db-chart-head"><span class="db-chart-title">Ceiling by holding agency</span></div>
                    <div class="db-chart-body" style="height: 240px;"><canvas id="agrAgencyChart"></canvas></div>
                    <div class="ds-seglinks">
                        @foreach($agrSlices['agency']['items'] ?? [] as $it)
                            @php $oh = (!$it['grey'] && ($it['slug'] ?? '') !== '') ? route('orgProfile', ['id' => $it['slug'], 'orgslug' => \Illuminate\Support\Str::slug($it['label'] ?? '', '-')]) : null; @endphp
                            @if($oh)<a href="{{ $oh }}" data-c="{{ $it['color'] }}"><i class="ds-sw"></i>{{ $it['label'] }}</a>@else<span data-c="{{ $it['color'] }}"><i class="ds-sw"></i>{{ $it['label'] }}</span>@endif
                        @endforeach
                    </div>
                    <p class="ds-chart-note">
                        Which agency holds the agreement.
                        @if(($agrSlices['top_share'] ?? null) !== null)
                            {{ $agrSlices['top_agency'] }} holds {{ $agrSlices['top_share'] }}% of the ceiling:
                            most are citywide vehicles agencies buy against.
                        @endif
                    </p>
                </div>
            </div>
            <div class="col-lg-6">
                <div class="db-chart-card h-100">
                    <div class="db-chart-head"><span class="db-chart-title">Still running, or ended</span></div>
                    <div class="db-chart-body" style="height: 240px;"><canvas id="agrStatusChart"></canvas></div>
                    <div class="ds-seglinks">
                        @foreach($agrSlices['status']['items'] ?? [] as $it)
                            <span data-c="{{ $it['color'] }}"><i class="ds-sw"></i>{{ $it['label'] }}: {{ $fmtM($it['value']) }}</span>
                        @endforeach
                    </div>
                    <p class="ds-chart-note">
                        {{ number_format($agrSlices['active_n'] ?? 0) }} of {{ number_format($maCount) }}
                        agreements are still running. Ceiling, not spend.
                    </p>
                </div>
            </div>
        </div>

        <div class="db-table-wrap mb-5" id="master-agreements">
            <div class="table-responsive">
                <table class="db-table db-table-striped db-dt">
                    <thead>
                        <tr><th>Agreement</th><th>Kind</th><th>Vendor</th><th>Agency</th>
                            <th>Title</th><th>Ends</th><th class="db-num">Ceiling</th>
                            <th class="db-num">Paid under this id</th></tr>
                    </thead>
                    <tbody>
                        @forelse($maRows as $r)
                        {{-- The id is what a pending agreement below links to. --}}
                        <tr id="ma-{{ $r['contract_id'] }}">
                            <td>
                                @if($r['ctr_id'] !== '')
                                    <a href="/procurement/contract/{{ $r['ctr_id'] }}">{{ $r['contract_id'] }}</a>
                                @else
                                    {{ $r['contract_id'] }}
                                @endif
                            </td>
                            <td><span class="db-badge db-badge-warning">{{ $r['kind'] }}</span></td>
                            {{-- ⚠ Same rule as the Overview's band: linked only where
                                 `vendorids.unique_map` resolved the name to exactly ONE
                                 supplier id. Adding the link here too, rather than only
                                 on the summary, so the Overview never out-links the page
                                 it summarises. --}}
                            <td class="small">
                                @if(!empty($r['vendor_id']))
                                <a href="{{ route('procurement.vendor', ['id' => $r['vendor_id']]) }}">{{ $r['vendor_name'] }}</a>
                                @else
                                {{ $r['vendor_name'] }}
                                @endif
                            </td>
                            {{-- ⚠ Same rule as everywhere else: linked only where the
                                 shared two-tier resolver named an org. --}}
                            <td class="small">
                                @if(!empty($r['org_id']))
                                <a href="{{ route('orgProfile', ['id' => $r['org_id'], 'orgslug' => \Illuminate\Support\Str::slug($r['agency'] ?? '', '-')]) }}">{{ $r['agency'] }}</a>
                                @else
                                {{ $r['agency'] }}
                                @endif
                            </td>
                            <td class="text-muted small">{{ \Illuminate\Support\Str::limit($r['title'], 70) }}</td>
                            <td class="small">{{ $r['end_date'] }}</td>
                            <td class="db-num" data-order="{{ (float) $r['ceiling'] }}">{{ $fmtM($r['ceiling']) }}</td>
                            {{-- ⚠ null, not 0: "not tracked here" is a different
                                 statement from "nothing was paid", and only one of
                                 them is supported by the data. --}}
                            <td class="db-num">
                                @if(($r['spent'] ?? null) === null)
                                    <span class="text-muted small">not tracked here</span>
                                @else
                                    {{ $fmtM($r['spent']) }}
                                @endif
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="8" class="text-center text-muted py-4">No registered master agreements found.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>
        @endif

        {{-- ============ AGREEMENTS IN THE PIPELINE (moved from the Contracts page,
             2026-09-23). ⚠⚠ CEILINGS ON UNSIGNED PAPER, NEVER ADDED TO ANY TOTAL.
             PASSPort assigns a contract id only at registration, and every other
             figure in this section keys on it, so none of them counts these.
             ⚠ Selected by VENDOR, not by classification: an unregistered row has no
             contract id for the classifier to reach, so this is every pending
             agreement from a vendor holding at least one confirmed technology
             contract — and some are not technology at all. The page says so. --}}
        @if(($pipe['count'] ?? 0) > 0)
        @php
            // Precomputed: a Blade directive glued to a word character is not compiled.
            $pipeStaleNote = ($pipe['stale_n'] ?? 0) > 0
                ? ' ' . number_format($pipe['stale_n']) . ' of the rows shown have a start date more than two years past and are still unregistered.'
                : '';
        @endphp
        <h2 class="mt-2" style="font-size: var(--db-text-lg);" id="awaiting-registration"><i class="bi bi-hourglass"></i> Awaiting registration</h2>
        <p class="text-muted" style="font-size: var(--db-text-sm); max-width: 80ch;">
            {{ number_format($pipe['count']) }} agreements from {{ number_format($pipe['vendors'] ?? 0) }} vendors
            ({{ number_format($pipe['masters'] ?? 0) }} of them masters) are still in approval: a combined
            <em>ceiling</em> of ${{ number_format(($pipe['ceiling'] ?? 0) / 1000000, 1) }}M, never added to anything
            above. Showing the {{ number_format(count($pipe['rows'] ?? [])) }} above
            ${{ number_format(($pipe['floor'] ?? 0) / 1000000, 0) }}M.{{ $pipeStaleNote }}
        </p>
        <details class="lic-more mb-2" style="max-width: 80ch;">
            <summary>Why some of these are not technology</summary>
            <p class="lic-sub mb-0 mt-1">
                An unregistered agreement has no contract id for the classifier to reach, so these are
                selected by vendor: every pending agreement from a vendor holding at least one confirmed
                technology contract.
            </p>
        </details>
        <div class="db-table-wrap mb-5">
            <div class="table-responsive">
                <table class="db-table db-table-striped db-dt">
                    <thead>
                        <tr><th>Vendor</th><th>Agency</th><th>Agreement</th><th>Status</th><th>Starts</th>
                            <th class="db-num">Ceiling</th><th>Registered with the same vendor and agency</th></tr>
                    </thead>
                    <tbody>
                        @foreach(($pipe['rows'] ?? []) as $p)
                        <tr>
                            <td class="small">{{ $p['vendor_name'] }}
                                @if($p['is_master'] ?? false)<span class="db-badge db-badge-warning">Master</span>@endif
                            </td>
                            <td class="small">{{ $p['agency'] }}</td>
                            <td class="text-muted small">{{ $p['contract_title'] }}</td>
                            <td class="small">{{ $p['status'] }}</td>
                            <td class="small text-nowrap" data-order="{{ substr($p['start_date'] ?? '', 6, 4) . substr($p['start_date'] ?? '', 0, 2) . substr($p['start_date'] ?? '', 3, 2) }}">
                                {{ $p['start_date'] }}
                                @if($p['stale'] ?? false)<div><span class="db-badge db-badge-danger" title="Start date passed more than two years ago; still not registered">over two years late</span></div>@endif
                            </td>
                            <td class="db-num" data-order="{{ (float) ($p['ceiling'] ?? 0) }}">{{ $fmtM($p['ceiling'] ?? 0) }}</td>
                            <td class="small">
                                @forelse(($p['registered'] ?? []) as $rg)
                                    <div><a href="#ma-{{ $rg['contract_id'] }}">{{ $rg['contract_id'] }}</a>
                                        <span class="text-muted">ends {{ $rg['end_date'] }}</span></div>
                                @empty
                                    <span class="text-muted">none</span>
                                @endforelse
                                @if(($p['registered_n'] ?? 0) > count($p['registered'] ?? []))
                                    <div class="text-muted">+ {{ number_format($p['registered_n'] - count($p['registered'])) }} more</div>
                                @endif
                            </td>
                        </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </div>
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
    @include('procurement.partials.agreements-book-js')
    ovPie('agrAgencyChart', @json($agrSlices['agency'] ?? null));
    ovPie('agrStatusChart', @json($agrSlices['status'] ?? null));
    // AFTER the pies: the HTML legends are the only legend, painted from the
    // same colour resolver as the arcs.
    paintLegends();
});
</script>
@endsection
