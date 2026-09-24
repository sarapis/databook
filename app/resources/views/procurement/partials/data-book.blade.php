{{-- ============================================================
     THE DATA BOOK — value by kind, the largest data products, data spend by
     agency. ONE partial for the Overview's Data band AND the Data page, which
     leads with it (2026-09-23). Needs $dataBlocks
     (ProcurementController::_dataBookBlocks). The JS half is `data-book-js`,
     which needs `slice-pies-js`.
     ⚠ The CONTENT half only: the lens's two halves overlap by design.
     ============================================================ --}}
@php
    $db = $dataBlocks ?? null;
    // ⚠ Defined here when the including page has not, so the partial carries
    // its own dependencies. Same formatter as the Overview's.
    if (!isset($fmtM)) {
        $fmtM = function ($v) {
            $v = (float) $v;
            if ($v >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
            if ($v >= 1000000)    return '$' . number_format($v / 1000000, 1) . 'M';
            if ($v >= 1000)       return '$' . number_format($v / 1000, 0) . 'K';
            return '$' . number_format($v, 0);
        };
    }
    // `orgProfile` takes an id AND a decorative slug; Str::slug is correct here
    // because the id carries identity. ⚠ NULL id -> plain text: an agency the
    // alias seed cannot resolve would otherwise deep-link to the wrong profile.
    $dbOrgHref = function ($id, $name) {
        return $id ? route('orgProfile', ['id' => $id,
                     'orgslug' => \Illuminate\Support\Str::slug($name ?? '', '-')]) : null;
    };
@endphp
            @if($db)
            <div class="row g-4">
                <div class="col-lg-4">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head"><span class="db-chart-title">Value by kind</span></div>
                        <div class="db-chart-body" style="height: 260px;"><canvas id="ovKindChart"></canvas></div>
                        <div class="ds-seglinks">
                            @foreach(\App\Custom\SliceLinks::links($db['kind'], 'research.digital-reform.product-capability', 'cap') as $l)
                                @if($l['href'])<a href="{{ $l['href'] }}" data-c="{{ $l['color'] }}"><i class="ds-sw"></i>{{ $l['label'] }}</a>@else<span data-c="{{ $l['color'] }}"><i class="ds-sw"></i>{{ $l['label'] }}</span>@endif
                            @endforeach
                        </div>
                        {{-- ⚠⚠ THE BIGGEST WEDGE IS AN ABSTENTION, AND THE NOTE SAYS SO.
                             "Function not identified" is the largest slice here by a
                             distance, so a reader who does not look at the legend would
                             take this chart as a breakdown of known kinds. It wears the
                             neutral AND states its share; a chart whose dominant wedge
                             means "we do not know" has to admit that in words. --}}
                        @php
                            $kindTot = array_sum($db['kind']['values'] ?? []);
                            $kindUnk = 0;
                            foreach (($db['kind']['labels'] ?? []) as $ki => $kl) {
                                if (stripos($kl, 'not identified') !== false
                                    || stripos($kl, 'not yet tagged') !== false) {
                                    $kindUnk += $db['kind']['values'][$ki] ?? 0;
                                }
                            }
                        @endphp
                        <p class="ds-chart-note">
                            What sort of data it is.
                            @if($kindTot > 0 && $kindUnk > 0)
                                {{ number_format(100 * $kindUnk / $kindTot, 0) }}% of it
                                carries no identified kind.
                            @endif
                        </p>
                    </div>
                </div>
                <div class="col-lg-4">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head"><span class="db-chart-title">Largest data products</span></div>
                        <div class="ds-rank">
                            @foreach($db['products'] as $f)
                                <a class="ds-rank-row" href="{{ route('research.digital-reform.product-family', ['slug' => $f['slug'] ?? '']) }}">
                                    <span class="ds-rank-name">{{ $f['key'] ?? '' }}</span>
                                    <span class="ds-rank-val">{{ $fmtM($f['value'] ?? 0) }}</span>
                                </a>
                            @endforeach
                        </div>
                        <p class="ds-chart-note">
                            Top {{ count($db['products']) }} of {{ number_format($db['families']) }}.
                        </p>
                    </div>
                </div>
                <div class="col-lg-4">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head"><span class="db-chart-title">Data spend by agency</span></div>
                        <div class="db-chart-body" style="height: 260px;"><canvas id="ovDataAgencyChart"></canvas></div>
                        <div class="ds-seglinks">
                            @foreach($db['agency']['items'] ?? [] as $it)
                                @php $oh = (!$it['grey'] && ($it['slug'] ?? '') !== '') ? $dbOrgHref($it['slug'], $it['label']) : null; @endphp
                                @if($oh)<a href="{{ $oh }}" data-c="{{ $it['color'] }}"><i class="ds-sw"></i>{{ $it['label'] }}</a>@else<span data-c="{{ $it['color'] }}"><i class="ds-sw"></i>{{ $it['label'] }}</span>@endif
                            @endforeach
                        </div>

                        {{-- ⚠ THE CONTENT HALF ONLY. That page's two halves overlap by
                             design, so there is no combined figure to show here and a
                             chart spanning both would be the one sum it exists to refuse. --}}
                        <p class="ds-chart-note">
                            Bought <em>as</em> data: {{ $fmtM($db['value']) }} over
                            {{ number_format($db['contracts']) }} contracts.
                        </p>
                    </div>
                </div>
            </div>
            @else
            <p class="text-muted">The data lens is not available right now.</p>
            @endif
