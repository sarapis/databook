{{-- ============================================================
     THE AGREEMENTS BOOK — vendors holding the most running headroom, the
     agreements running out soonest, ceiling running in each year. ONE partial
     for the Overview's Agreements band AND the Agreements page, which leads
     with it (2026-09-23). Needs $agrBlocks
     (ProcurementController::_agreementsBookBlocks). The JS half is
     `agreements-book-js`.
     ⚠ Every figure is a CEILING, never spend.
     ============================================================ --}}
@php
    $ab = $agrBlocks ?? null;
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
            @if($ab)
            @php
                $agrActive = $ab['active'] ?? ['count' => 0, 'ceiling' => 0];
                $agrEnded  = max(0, ($ab['count'] ?? 0) - (int) ($agrActive['count'] ?? 0));
            @endphp
            <div class="row g-4 mb-4">
                <div class="col-lg-6">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head">
                            <span class="db-chart-title">Vendors holding the most running headroom</span>
                        </div>
                        <div class="db-table-wrap">
                            <table class="db-table">
                                <thead><tr>
                                    <th>Vendor</th><th class="text-end">Agreements</th>
                                    <th class="text-end">Active ceiling</th>
                                </tr></thead>
                                <tbody>
                                @foreach($ab['vendors_active'] ?? [] as $v)
                                    <tr>
                                        {{-- ⚠ Linked only where the name resolved to exactly ONE
                                             supplier id. 48 vendor names hold more than one row,
                                             and a link there sends a reader to an arbitrary one
                                             of two companies. --}}
                                        <td>
                                            @if(!empty($v['vendor_id']))
                                            <a href="{{ route('procurement.vendor', ['id' => $v['vendor_id']]) }}">{{ $v['vendor_name'] ?? '' }}</a>
                                            @else
                                            {{ $v['vendor_name'] ?? '' }}
                                            @endif
                                        </td>
                                        <td class="text-end">{{ number_format($v['agreements'] ?? 0) }}</td>
                                        <td class="text-end">{{ $fmtM($v['ceiling'] ?? 0) }}</td>
                                    </tr>
                                @endforeach
                                </tbody>
                            </table>
                        </div>
                        <p class="ds-chart-note">
                            Top {{ count($ab['vendors_active'] ?? []) }} of
                            {{ number_format($ab['vendors_active_n'] ?? 0) }} vendors holding an
                            agreement that is still running. Ceiling, not spend.
                        </p>
                    </div>
                </div>
                <div class="col-lg-6">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head">
                            <span class="db-chart-title">Running out soonest</span>
                        </div>
                        <div class="db-table-wrap">
                            <table class="db-table">
                                <thead><tr>
                                    <th>Agreement</th><th class="text-end">Ends</th>
                                    <th class="text-end">Ceiling</th><th class="text-end">Spent to date</th>
                                </tr></thead>
                                <tbody>
                                @foreach($ab['soonest'] ?? [] as $r)
                                    <tr>
                                        <td>
                                            @if(!empty($r['ctr_id']))
                                            <a href="{{ route('procurement.contract', ['id' => $r['ctr_id']]) }}">{{ $r['title'] ?: $r['contract_id'] }}</a>
                                            @else
                                            {{ $r['title'] ?: $r['contract_id'] }}
                                            @endif
                                        </td>
                                        <td class="text-end text-muted">{{ $r['end_date'] ?? '' }}</td>
                                        <td class="text-end">{{ $fmtM($r['ceiling'] ?? 0) }}</td>
                                        {{-- ⚠⚠ "Not tracked here", NEVER "$0". Of 182 agreements only
                                             {{ $ab['tracked'] }} carry a Checkbook record at all and
                                             {{ $ab['drawn'] }} show any payment; a rendered $0 would
                                             invert this page's own finding by asserting the City has
                                             paid nothing against an agreement it may be drawing on. --}}
                                        <td class="text-end text-muted">
                                            @if(($r['spent'] ?? null) === null)
                                                Not tracked here
                                            @else
                                                {{ $fmtM($r['spent']) }}
                                            @endif
                                        </td>
                                    </tr>
                                @endforeach
                                </tbody>
                            </table>
                        </div>
                        <p class="ds-chart-note">
                            The {{ count($ab['soonest'] ?? []) }} nearest of
                            {{ number_format((int) ($agrActive['count'] ?? 0)) }} still running.
                            {{ number_format($agrEnded) }} of {{ number_format($ab['count'] ?? 0) }}
                            have already ended.
                        </p>
                    </div>
                </div>
            </div>

            <div class="db-chart-card mb-3">
                <div class="db-chart-head">
                    <span class="db-chart-title">Ceiling running in each year</span>
                </div>
                <div class="db-chart-body" style="height: 300px;"><canvas id="ovAgrYearChart"></canvas></div>
                {{-- ⚠⚠ THESE BARS DO NOT SUM TO THE TOTAL, AND THE NOTE SAYS SO.
                     An agreement counts in EVERY year of its term, so the series
                     adds to far more than the $3.2B of ceiling that exists —
                     adding them answers no question. It is "how much headroom was
                     live that year", not "how much was signed".
                     ⚠⚠ AND THERE IS NO SPEND SERIES BESIDE IT BECAUSE THERE IS
                     NONE TO DRAW. Measured against the spending lake itself:
                     ZERO of the 182 agreements carry a payment under their own
                     contract id (a positive control of 8 ordinary contracts was
                     found by the identical query, so the probe works). Checkbook
                     publishes one cumulative figure per contract with no year
                     dimension. Drawdowns are filed under the purchase orders
                     agencies raise, which carry their own ids. --}}
                <p class="ds-chart-note">
                    Headroom live in each year. An agreement counts in every year of its term, so
                    <strong>these bars are not added together</strong> and do not sum to the
                    {{ $fmtM($ab['ceiling'] ?? 0) }} on the books. There is no spending line: no
                    agreement has payments by year under its own contract id, and the
                    {{ number_format($ab['drawn'] ?? 0) }} with a Checkbook figure give only a lifetime total.
                </p>
            </div>
            <p class="ds-chart-note">
                {{ number_format($ab['count'] ?? 0) }} agreements,
                {{ $fmtM($ab['ceiling'] ?? 0) }} of ceiling in total;
                {{ number_format((int) ($agrActive['count'] ?? 0)) }} still running
                ({{ $fmtM($agrActive['ceiling'] ?? 0) }}).
            </p>
            @else
            <p class="text-muted">Agreement data is not available right now.</p>
            @endif
