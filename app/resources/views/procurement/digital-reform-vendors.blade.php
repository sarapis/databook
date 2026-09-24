@extends('layout')

@section('head')
<style>
    /* Digital Services Analysis: Vendors — the table moved from the Overview's
       tabs in the 2026-08-21 reorg (docs/DIGITAL-REFORM-REORG-PLAN.md). */
    .db-page-lead { max-width: none; }
</style>
@include('procurement.partials.ds-styles')
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    $fmtM = function ($v) {
        $v = (float) $v;
        if ($v >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
        if ($v >= 1000000)    return '$' . number_format($v / 1000000, 1) . 'M';
        if ($v >= 1000)       return '$' . number_format($v / 1000, 0) . 'K';
        return '$' . number_format($v, 0);
    };
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <a href="{{ route('research.digital-reform') }}" class="db-btn db-btn-ghost db-btn-sm mb-2"><i class="bi bi-arrow-left"></i> Digital Services</a>
        <h1>Vendors</h1>
        <p class="db-page-lead">
            The {{ number_format($vendors['total'] ?? 0) }} companies holding at least one
            <strong>confirmed technology contract</strong>, ranked by <strong>awarded</strong> value.
        </p>
        @include('sub.analysis-tag')
        @include('sub.digital-scope-note', ['scope' => $scope ?? []])

        {{-- The same two views the Overview's Vendors band previews (2026-09-23),
             always at the DEFAULT ranking — see digitalReformVendors(). --}}
        <div class="mt-3 mb-4">
            @include('procurement.partials.vendors-book')
        </div>
        {{-- ⚠ The top-5 tiles that sat here are gone: the band's "Largest by
             awarded value" list is the same ranking, eight deep. --}}
        <details class="lic-more mb-4" style="max-width: 80ch;">
            <summary>Why awarded value, not payments</summary>
            <p class="lic-sub mb-0 mt-1">
                A vendor holding master agreements is paid under the purchase orders agencies raise
                against them, which carry their own contract ids. Ranking by payments would push
                exactly the largest relationships to the bottom.
            </p>
        </details>

        <div class="db-table-wrap mb-5" id="digital-vendors">
            <div class="px-3 pt-3">
                <form method="GET" action="{{ url()->current() }}#digital-vendors" class="db-filter-bar dr-filter-form">
                    @foreach(request()->except(['vendor_q','vendor_page']) as $k => $v)
                        <input type="hidden" name="{{ $k }}" value="{{ $v }}">
                    @endforeach
                    <div class="db-search">
                        <i class="bi bi-search"></i>
                        <input type="search" name="vendor_q" value="{{ $vendorQ }}" placeholder="Search vendors&hellip;" aria-label="Search vendors">
                    </div>
                    <button type="submit" class="db-btn db-btn-primary db-btn-sm"><i class="bi bi-search"></i> Search</button>
                    @if($vendorQ)
                        <a href="{{ url()->current() }}?{{ http_build_query(request()->except(['vendor_q','vendor_page'])) }}#digital-vendors" class="db-btn db-btn-ghost db-btn-sm">Clear</a>
                    @endif
                </form>
                {{-- ⚠ "Digital Share" retired here. It divided a vendor's tagged spend by
                     their TOTAL City spend, which ranked a physical-guard company fifth
                     at "100% digital". The honest columns are the confirmed ones. --}}
                <p class="text-muted mb-3" style="font-size: var(--db-text-sm);">
                    Technology contracts only, not a vendor&rsquo;s whole City book. <em>Sells</em>
                    lists the product families a reseller carries.
                </p>
            </div>
            <div class="table-responsive">
                <table class="db-table db-table-striped">
                    <thead>
                        <tr>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['vendor_sort' => 'name', 'vendor_order' => ($vendorSort == 'name' && $vendorOrder == 'asc') ? 'desc' : 'asc']) }}#digital-vendors" class="text-decoration-none text-dark">
                                    Vendor @if($vendorSort == 'name'){!! $vendorOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th class="db-num">
                                <a href="{{ request()->fullUrlWithQuery(['vendor_sort' => 'contracts', 'vendor_order' => ($vendorSort == 'contracts' && $vendorOrder == 'asc') ? 'desc' : 'asc']) }}#digital-vendors" class="text-decoration-none text-dark">
                                    Technology contracts @if($vendorSort == 'contracts'){!! $vendorOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th class="db-num">
                                <a href="{{ request()->fullUrlWithQuery(['vendor_sort' => 'amount', 'vendor_order' => ($vendorSort == 'amount' && $vendorOrder == 'asc') ? 'desc' : 'asc']) }}#digital-vendors" class="text-decoration-none text-dark">
                                    Technology value @if($vendorSort == 'amount'){!! $vendorOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th class="db-num">Agencies</th>
                            <th>Sells</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse(($vendors['vendors'] ?? []) as $vendor)
                        @php
                            $sells = $vendor['sells'] ?? [];
                            $sellsTotal = $vendor['sells_total'] ?? 0;
                        @endphp
                        <tr>
                            <td>
                                @if($vendor['vendor_id'] ?? null)
                                    <a href="/procurement/vendor/{{ $vendor['vendor_id'] }}">{{ $vendor['vendor_name'] }}</a>
                                @else
                                    <a href="/procurement/vendors?q={{ urlencode($vendor['vendor_name']) }}">{{ $vendor['vendor_name'] }}</a>
                                @endif
                            </td>
                            <td class="db-num">{{ number_format($vendor['contract_count'] ?? 0) }}</td>
                            <td class="db-num">{{ $fmtM($vendor['total_awarded'] ?? 0) }}</td>
                            <td class="db-num">{{ number_format($vendor['agencies'] ?? 0) }}</td>
                            <td class="small">
                                @if($sellsTotal > 0)
                                    {{ implode(', ', $sells) }}
                                    @if($sellsTotal > count($sells))
                                        <span class="text-muted">and {{ number_format($sellsTotal - count($sells)) }} more
                                        ({{ number_format($sellsTotal) }} product families in total)</span>
                                    @endif
                                @else
                                    <span class="text-muted">No licensed products &mdash; services, hardware or telecom</span>
                                @endif
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="5" class="text-center text-muted py-4">No vendors match &ldquo;{{ $vendorQ }}&rdquo;.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
            @if(($vendors['total_pages'] ?? 0) > 1)
            <div class="db-table-footer">
                <span class="db-table-count">Page {{ $vendorPage }} of {{ number_format($vendors['total_pages']) }} · {{ number_format($vendors['total'] ?? 0) }} entries</span>
                <nav aria-label="Vendors pagination">
                    <ul class="pagination db-pagination mb-0">
                        <li class="page-item {{ $vendorPage == 1 ? 'disabled' : '' }}">
                            @if($vendorPage == 1)<span class="page-link">Previous</span>@else<a class="page-link" href="{{ request()->fullUrlWithQuery(['vendor_page' => $vendorPage - 1]) }}#digital-vendors">Previous</a>@endif
                        </li>
                        <li class="page-item {{ $vendorPage >= ($vendors['total_pages'] ?? 1) ? 'disabled' : '' }}">
                            @if($vendorPage >= ($vendors['total_pages'] ?? 1))<span class="page-link">Next</span>@else<a class="page-link" href="{{ request()->fullUrlWithQuery(['vendor_page' => $vendorPage + 1]) }}#digital-vendors">Next</a>@endif
                        </li>
                    </ul>
                </nav>
            </div>
            @endif
        </div>

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
    @include('procurement.partials.vendors-book-js')
    // AFTER the pies: the HTML legends are the only legend.
    paintLegends();
});
</script>
@endsection
