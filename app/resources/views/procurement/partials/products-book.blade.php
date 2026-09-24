{{-- ============================================================
     THE PRODUCTS BOOK — value by function, the largest families, value by
     procurement route. ONE partial for the Overview's Products band AND the
     Products page, which leads with it (2026-09-23). Needs $prodBlocks
     (ProcurementController::_productsBookBlocks). The middle chart is the
     largest-families list by default and "Value by kind" when the page passes
     $prodMiddle = 'kind' (the Products page, owner 2026-09-23). The JS half is
     `products-book-js`, which needs `slice-pies-js`.
     ============================================================ --}}
@php
    $pb = $prodBlocks ?? null;
    // ⚠ Defined here when the including page has not, so the partial carries its
    // own dependencies. Same formatter and renderer as the Overview's.
    if (!isset($fmtM)) {
        $fmtM = function ($v) {
            $v = (float) $v;
            if ($v >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
            if ($v >= 1000000)    return '$' . number_format($v / 1000000, 1) . 'M';
            if ($v >= 1000)       return '$' . number_format($v / 1000, 0) . 'K';
            return '$' . number_format($v, 0);
        };
    }
    // ⚠ The link rule has ONE owner, App\Custom\SliceLinks; this is only a name for it.
    $bookLinks = function ($block, $route, $param) {
        return \App\Custom\SliceLinks::links($block, $route, $param);
    };
@endphp
            @if($pb)
            <div class="row g-4">
                <div class="col-lg-4">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head"><span class="db-chart-title">Value by function</span></div>
                        <div class="db-chart-body" style="height: 260px;"><canvas id="ovFunctionChart"></canvas></div>
                        <div class="ds-seglinks">
                            @foreach($bookLinks($pb['functions'], 'research.digital-reform.product-capability', 'cap') as $l)
                                @if($l['href'])<a href="{{ $l['href'] }}" data-c="{{ $l['color'] }}"><i class="ds-sw"></i>{{ $l['label'] }}</a>@else<span data-c="{{ $l['color'] }}"><i class="ds-sw"></i>{{ $l['label'] }}</span>@endif
                            @endforeach
                        </div>
                        {{-- ⚠ THE COVERAGE IS STATED, NOT IMPLIED. A function view
                             that reaches 98% of the money reads as the whole of it
                             unless it says otherwise, and the contracts it misses
                             were never given a function at all — which is a
                             different thing from the "not identified" wedge inside
                             the chart. --}}
                        <p class="ds-chart-note">
                            What the product is for. Covers
                            {{ $fmtM($pb['fn_value'] ?? 0) }} of
                            {{ $fmtM($pb['summary']['total_value'] ?? 0) }};
                            {{ number_format(($pb['summary']['contracts'] ?? 0) - ($pb['fn_contracts'] ?? 0)) }}
                            contracts carry no function at all and are not shown.
                        </p>
                    </div>
                </div>
                @if(($prodMiddle ?? 'families') === 'kind')
                <div class="col-lg-4">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head"><span class="db-chart-title">Value by kind</span></div>
                        <div class="db-chart-body" style="height: 260px;"><canvas id="ovPurchaseKindChart"></canvas></div>
                        <div class="ds-seglinks">
                            @foreach(\App\Custom\SliceLinks::links($pb['kinds'] ?? null, 'research.digital-reform.products', 'class', 'family-detail') as $l)
                                @if($l['href'])<a href="{{ $l['href'] }}" data-c="{{ $l['color'] }}"><i class="ds-sw"></i>{{ $l['label'] }}</a>@else<span data-c="{{ $l['color'] }}"><i class="ds-sw"></i>{{ $l['label'] }}</span>@endif
                            @endforeach
                        </div>
                        <p class="ds-chart-note">
                            What kind of purchase it is. Pick one to list its contracts;
                            <a href="#classes">the table below</a> gives each kind's lever.
                        </p>
                    </div>
                </div>
                @else
                <div class="col-lg-4">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head"><span class="db-chart-title">Largest product families</span></div>
                        <div class="ds-rank">
                            @foreach($pb['families'] as $f)
                                <a class="ds-rank-row" href="{{ route('research.digital-reform.product-family', ['slug' => $f['slug'] ?? '']) }}">
                                    <span class="ds-rank-name">{{ $f['key'] ?? '' }}</span>
                                    <span class="ds-rank-val">{{ $fmtM($f['value'] ?? 0) }}</span>
                                </a>
                            @endforeach
                        </div>
                        <p class="ds-chart-note">
                            Top {{ count($pb['families']) }} of {{ number_format($pb['totals']['families'] ?? 0) }}.
                        </p>
                    </div>
                </div>
                @endif
                <div class="col-lg-4">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head"><span class="db-chart-title">Value by procurement route</span></div>
                        <div class="db-chart-body" style="height: 260px;"><canvas id="ovRouteChart"></canvas></div>
                        <div class="ds-seglinks">
                            @foreach($bookLinks($pb['route'], 'research.digital-reform.contracts', 'contract_method') as $l)
                                @if($l['href'])<a href="{{ $l['href'] }}" data-c="{{ $l['color'] }}"><i class="ds-sw"></i>{{ $l['label'] }}</a>@else<span data-c="{{ $l['color'] }}"><i class="ds-sw"></i>{{ $l['label'] }}</span>@endif
                            @endforeach
                        </div>
                        <p class="ds-chart-note">
                            How the purchase was made. Pick one to filter the contract list.
                        </p>
                    </div>
                </div>
            </div>
            @else
            <p class="text-muted">Product analysis is not available right now.</p>
            @endif
