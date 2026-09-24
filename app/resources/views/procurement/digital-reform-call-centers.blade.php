@extends('layout')

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    // ⚠ Every conditional sentence is composed HERE. A Blade directive glued to a
    // word character does not compile — `2030@else` cost this section a 500 — and
    // a Blade comment eats the newline after it, which cost /districts every
    // function on the page. Both are documented traps in this repo.
    $ok   = (bool) ($d['available'] ?? false);
    $ins  = $d['inside']     ?? ['contracts' => 0, 'value' => 0];
    $out  = $d['outside']    ?? ['contracts' => 0, 'value' => 0];
    $all  = $d['lens_total'] ?? ['contracts' => 0, 'value' => 0];
    $kinds = $d['kinds'] ?? [];
    $rows  = $d['contracts'] ?? [];
    $strad = $d['straddling'] ?? [];
    $programs = $d['programs'] ?? [];
    $vendorRows = $d['vendors'] ?? [];
    $reviewed = (int) ($d['reviewed'] ?? 0);

    $m = function ($v) { return '$' . number_format(((float) $v) / 1000000, 2) . 'M'; };
    $pct = function ($a, $b) {
        $b = (float) $b;
        return $b > 0 ? number_format(100 * ((float) $a) / $b, 0) . '%' : '—';
    };
@endphp

<div class="inner_container db-home">
    <h1 class="db-profile-title">What the City buys when it buys a phone line</h1>

    @if(!$ok)
        <x-db.alert kind="info">This lens is not available right now.</x-db.alert>
    @else
    <p class="db-page-lead">
        Some City services reach the public by telephone. This page follows
        <strong>{{ number_format($all['contracts']) }} such contracts worth {{ $m($all['value']) }}</strong>
        and shows where this section's own boundary falls across them &mdash; because it
        falls through the middle.
    </p>

    {{-- ⚠⚠ THE TWO HALVES ARE DISJOINT, so the lens total above is a real figure.
         The hazard here is NOT double-counting (that is the data lens's problem);
         it is that the OUTSIDE half is money this section has deliberately
         excluded from "how NYC buys technology". It must never be added to the
         committed headline, and the note below says so in as many words. --}}
    <div class="db-stat-grid mt-3 mb-2">
        <div class="db-stat is-accent">
            <div class="db-stat-label">Counted as technology</div>
            <div class="db-stat-value">{{ $m($ins['value']) }}</div>
            <div class="db-stat-sub">{{ number_format($ins['contracts']) }} contracts &middot;
                {{ $pct($ins['value'], $all['value']) }} of the phone-delivered total</div>
        </div>
        <div class="db-stat">
            <div class="db-stat-label">Not counted as technology</div>
            <div class="db-stat-value">{{ $m($out['value']) }}</div>
            <div class="db-stat-sub">{{ number_format($out['contracts']) }} contracts &middot;
                {{ $pct($out['value'], $all['value']) }} of it</div>
        </div>
    </div>
    <p class="text-muted mb-4" style="font-size: var(--db-text-2xs);" id="lensScopeNote">
        <strong>The second figure is not technology spending and is not part of any total
        elsewhere in this section.</strong> These are contracts the classification put
        outside "how NYC buys technology" on purpose. They are shown here so the boundary
        can be seen, not so it can be counted back in.
        {{ $reviewed }} of the {{ number_format($all['contracts']) }} were placed outside
        by hand rather than by the classifier.
    </p>

    <h2 class="db-section-title mt-4">The rule the boundary is following</h2>
    <p class="db-page-lead">
        Sorted by what the contract actually buys, the split is almost perfectly
        consistent: <strong>buy the channel and it counts as technology; buy the care
        or the help delivered through it and it does not.</strong>
    </p>
    <div class="table-responsive">
        <table class="db-table db-table-striped">
            <thead>
                <tr>
                    <th>What the contract buys</th>
                    <th class="text-end">Counted</th>
                    <th class="text-end">Value</th>
                    <th class="text-end">Not counted</th>
                    <th class="text-end">Value</th>
                </tr>
            </thead>
            <tbody>
            @foreach($kinds as $k)
                <tr>
                    <td>{{ $k['label'] ?: $k['kind'] }}</td>
                    <td class="text-end">{{ number_format($k['inside_contracts']) }}</td>
                    <td class="text-end" data-order="{{ (int) $k['inside_value'] }}">{{ $m($k['inside_value']) }}</td>
                    <td class="text-end">{{ number_format($k['outside_contracts']) }}</td>
                    <td class="text-end" data-order="{{ (int) $k['outside_value'] }}">{{ $m($k['outside_value']) }}</td>
                </tr>
            @endforeach
            </tbody>
        </table>
    </div>

    @if(count($strad) > 0)
    @php
        // ⚠ `straddling` is a list of PROGRAM rows (same shape as $programs), not
        // the vendor rows it once was. Changing the payload and leaving this
        // reading the old keys is what 500'd the page on `Undefined index:
        // vendor` — the #247 seam, found by rendering and by nothing else.
        $s0 = $strad[0];
        $s0in  = (int) $s0['inside_contracts'];
        $s0out = (int) $s0['outside_contracts'];
        $stradSentence = $s0['program'] . ' runs across ' . ($s0in + $s0out)
            . ' contracts, of which ' . $s0in . ' ' . ($s0in === 1 ? 'is' : 'are')
            . ' counted as technology and ' . $s0out . ' '
            . ($s0out === 1 ? 'is' : 'are') . ' not.';
        $stradMore = count($strad) > 1
            ? ' ' . (count($strad) - 1) . ' other program falls on both sides too.'
            : '';
        if (count($strad) > 2) {
            $stradMore = ' ' . (count($strad) - 1) . ' other programs fall on both sides too.';
        }
    @endphp
    <h2 class="db-section-title mt-4">Where it breaks</h2>
    <p class="db-page-lead">
        {{ $stradSentence }}{{ $stradMore }}
        {{-- ⚠ "same vendor" was TRUE of the UFT example this sentence was written for
             and FALSE of NYC 311, which the value ordering now puts first: its
             contracts run through different vendors. The claim is about the
             PROGRAM, so it says program. --}}
        One program, one answer expected &mdash; and instead two. That is the clearest
        evidence available that this boundary is a judgement rather than a property
        of the data.
    </p>
    @endif

    <h2 class="db-section-title mt-4">By program</h2>
    @php
        $liveProgs = 0;
        foreach ($programs as $pp) { if ($pp['current_annual'] !== null) { $liveProgs++; } }
        $deadProgs = count($programs) - $liveProgs;
    @endphp
    <p class="db-page-lead">
        The unit a reader usually means. Several run across more than one contract,
        and two fall on both sides of the boundary at once.
        <strong>Total, all terms</strong> adds up every contract a program has ever
        had here, so it spans several years; <strong>per year, now</strong> annualises
        only the contracts running today, which is what the program currently costs.
        {{-- ⚠ The two columns answer different questions and are never added. The
             per-year figure is NOT the total divided by anything: these programs are
             mostly CONSECUTIVE renewals, so summing their annual rates would report
             roughly twice what a program costs — while the NYC Benefits line runs
             three vendors CONCURRENTLY, where the sum is right. Annualising only
             what is live today is correct in both shapes. --}}
        @if($deadProgs > 0)
            A dash means no contract is running today: <strong>{{ $deadProgs }} of
            {{ count($programs) }}</strong> of these programs have none on record.
        @endif
    </p>
    <div class="table-responsive">
        <table class="db-table db-table-striped db-dt" id="ccPrograms">
            <thead>
                <tr>
                    <th>Program</th>
                    <th class="text-end">Vendors</th>
                    <th class="text-end">Contracts</th>
                    <th class="text-end">Total, all terms</th>
                    <th class="text-end">Per year, now</th>
                    <th class="text-end">Counted as technology</th>
                    <th class="text-end">Not counted</th>
                </tr>
            </thead>
            <tbody>
            @foreach($programs as $p)
                <tr>
                    <td>
                        {{ $p['program'] }}
                        @if($p['straddles'])<span class="db-badge db-badge-warning">both sides</span>@endif
                    </td>
                    <td class="text-end">{{ number_format($p['vendor_count']) }}</td>
                    <td class="text-end">{{ number_format($p['contracts']) }}</td>
                    <td class="text-end" data-order="{{ (int) $p['value'] }}">{{ $m($p['value']) }}</td>
                    {{-- ⚠ A dash here means NO CONTRACT IS RUNNING, not "unknown" —
                         the sentence above the table says so. Rendering $0.00 would
                         be a claim the City never made. --}}
                    <td class="text-end" data-order="{{ (int) ($p['current_annual'] ?? -1) }}">
                        @if($p['current_annual'] === null)
                            <span class="text-muted">&mdash;</span>
                        @else
                            {{ $m($p['current_annual']) }}
                        @endif
                    </td>
                    <td class="text-end" data-order="{{ (int) $p['inside_value'] }}">{{ $m($p['inside_value']) }}</td>
                    <td class="text-end" data-order="{{ (int) $p['outside_value'] }}">{{ $m($p['outside_value']) }}</td>
                </tr>
            @endforeach
            </tbody>
        </table>
    </div>

    <h2 class="db-section-title mt-4">By vendor</h2>
    <p class="db-page-lead">
        <strong>These are the phone-service contracts only, not each vendor's City
        business.</strong> Safe Horizon holds 107 contracts worth $441.3M and The Mental
        Health Association 34 worth $315.1M &mdash; almost none of them phone lines.
        Reading a vendor's whole book into one program is the error this table is
        scoped to avoid.
    </p>
    <div class="table-responsive">
        <table class="db-table db-table-striped db-dt" id="ccVendors">
            <thead>
                <tr>
                    <th>Vendor</th>
                    <th>Program</th>
                    <th class="text-end">Contracts</th>
                    <th class="text-end">In this lens</th>
                    <th class="text-end">Counted as technology</th>
                    <th class="text-end">Not counted</th>
                </tr>
            </thead>
            <tbody>
            @foreach($vendorRows as $v)
                <tr>
                    <td>{{ $v['vendor'] }}</td>
                    {{-- ⚠ Joined from a LIST, not printed as a single value. Measured
                         2026-09-15: every vendor here serves exactly one programme, and
                         rendering a bare string would bake that in — a vendor picking up
                         a second would then silently show only one. --}}
                    <td>{{ implode(', ', $v['programs'] ?? []) }}</td>
                    <td class="text-end">{{ number_format($v['contracts']) }}</td>
                    <td class="text-end" data-order="{{ (int) $v['value'] }}">{{ $m($v['value']) }}</td>
                    <td class="text-end" data-order="{{ (int) $v['inside_value'] }}">{{ $m($v['inside_value']) }}</td>
                    <td class="text-end" data-order="{{ (int) $v['outside_value'] }}">{{ $m($v['outside_value']) }}</td>
                </tr>
            @endforeach
            </tbody>
        </table>
    </div>

    <h2 class="db-section-title mt-4">Every contract in this lens</h2>
    <div class="table-responsive">
        <table class="db-table db-table-striped db-dt" id="ccTable">
            <thead>
                <tr>
                    <th>Contract</th>
                    <th>Agency</th>
                    <th>Vendor</th>
                    <th>What it buys</th>
                    <th>Counted?</th>
                    <th class="text-end">Value</th>
                </tr>
            </thead>
            <tbody>
            @foreach($rows as $r)
                @php
                    $badge = $r['inside'] ? 'Technology' : 'Not counted';
                    $tone  = $r['inside'] ? 'db-badge-info' : 'db-badge-neutral';
                @endphp
                <tr>
                    <td>{{ $r['title'] }}</td>
                    <td>{{ $r['agency'] }}</td>
                    <td>{{ $r['vendor'] }}</td>
                    <td>{{ $r['kind'] }}</td>
                    <td><span class="db-badge {{ $tone }}">{{ $badge }}</span></td>
                    <td class="text-end" data-order="{{ (int) $r['value'] }}">{{ $m($r['value']) }}</td>
                </tr>
            @endforeach
            </tbody>
        </table>
    </div>

    <p class="text-muted mt-3" style="font-size: var(--db-text-2xs);">
        Membership of this lens is a reviewed list, not a text search. Three separate
        title patterns were tried first and every one over-matched &mdash; on a
        geotechnical contract number, on a shelter's street address, and on crisis
        shelters &mdash; producing a total half again too large. The list is curated in
        <code>api/seed/phone_service_contracts.csv</code>; whether each contract counts as
        technology is read live from the classification, never stored beside it.
    </p>
    @endif
</div>
@endsection
