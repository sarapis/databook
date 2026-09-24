{{-- ============================================================
     THE VENDORS BOOK — vendors by how they mostly get in, and the largest by
     awarded value. ONE partial for the Overview's Vendors band AND the Vendors
     page, which leads with it (2026-09-23). Needs $vm, $vmSlices, $vendTop and
     $vendTotal (ProcurementController::_vendorsBookBlocks). The JS half is
     `vendors-book-js`, which needs `slice-pies-js`.
     ============================================================ --}}
@php
    if (!isset($fmtM)) {
        $fmtM = function ($v) {
            $v = (float) $v;
            if ($v >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
            if ($v >= 1000000)    return '$' . number_format($v / 1000000, 1) . 'M';
            if ($v >= 1000)       return '$' . number_format($v / 1000, 0) . 'K';
            return '$' . number_format($v, 0);
        };
    }
@endphp
            @if($vmSlices && count($vmSlices['items'] ?? []))
            <div class="row g-4 mb-4">
                <div class="col-lg-6">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head">
                            <span class="db-chart-title">Vendors by how they mostly get in</span>
                        </div>
                        <div class="db-chart-body" style="height: 280px;"><canvas id="ovVendorMethodChart"></canvas></div>
                        <div class="ds-seglinks">
                            @foreach($vmSlices['items'] ?? [] as $it)
                                <span data-c="{{ $it['color'] }}"><i class="ds-sw"></i>{{ $it['label'] }}</span>
                            @endforeach
                        </div>
                        {{-- ⚠⚠ THE WEDGE IS A COUNT OF VENDORS, NOT MONEY, and the two
                             answer different questions. By vendor count the head is
                             small-purchase; by the value those vendors hold it is
                             Renewal, with small-purchase sixth. The note carries the
                             money so a reader is not left to assume the wedge is it,
                             and the page never adds the two together.
                             ⚠ "Dominant" is measured by VALUE inside each vendor: a
                             vendor's largest route describes the relationship, where
                             counting its contracts would let a hundred small orders
                             outvote the agreement that is the relationship. --}}
                        <p class="ds-chart-note">
                            Each of the {{ number_format($vm['vendors'] ?? 0) }} vendors counted once,
                            under the procurement route carrying most of its value. Slices are
                            <strong>vendors, not dollars</strong> &mdash; the largest group by count is not
                            the largest by money, and the two are never added.
                        </p>
                    </div>
                </div>
                <div class="col-lg-6">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head"><span class="db-chart-title">Largest by awarded value</span></div>
                        <div class="db-table-wrap">
                        <table class="db-table">
                            <thead><tr>
                                <th>Vendor</th><th class="text-end">Contracts</th>
                                <th class="text-end">Agencies</th><th class="text-end">Awarded</th>
                            </tr></thead>
                    <tbody>
                    @foreach($vendTop ?? [] as $v)
                        <tr>
                            <td>
                                @if(!empty($v['vendor_id']))
                                <a href="{{ route('procurement.vendor', ['id' => $v['vendor_id']]) }}">{{ $v['vendor_name'] ?? '' }}</a>
                                @else
                                {{ $v['vendor_name'] ?? '' }}
                                @endif
                            </td>
                            <td class="text-end">{{ number_format($v['contract_count'] ?? 0) }}</td>
                            <td class="text-end">{{ number_format($v['agencies'] ?? 0) }}</td>
                            <td class="text-end">{{ $fmtM($v['total_awarded'] ?? 0) }}</td>
                        </tr>
                    @endforeach
                        </tbody>
                        </table>
                        </div>
                        {{-- ⚠ RANKED BY AWARDED, not by payments: a master-heavy vendor files
                             its drawdowns under other contract ids, so ranking by payments
                             would zero the largest relationships on the page. --}}
                        <p class="ds-chart-note">
                            Top {{ count($vendTop ?? []) }} of {{ number_format($vendTotal ?? 0) }} vendors, by awarded value.
                        </p>
                    </div>
                </div>
            </div>
            @else
            <p class="text-muted">Vendor data is not available right now.</p>
            @endif
