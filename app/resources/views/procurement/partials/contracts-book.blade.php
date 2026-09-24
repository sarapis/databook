{{-- ============================================================
     THE WHOLE BOOK — value by agency, value by type, committed money by start
     year. ONE partial for the Overview's Contracts band AND the Contracts page,
     which leads with it: the band is a preview of that page, so two copies of
     these charts would be two chances for the preview to show something the
     page does not.
     Needs $ovAgencySlices / $ovTypeSlices (ProcurementController::
     _contractsBookSlices), $awardByStartYear and $stats. The JS half is
     `contracts-book-js`, which needs `slice-pies-js` loaded first.
     ============================================================ --}}
@php
    // ⚠ Defined here when the including page has not, so the partial carries
    // its own dependency rather than silently rendering unlinked agencies.
    if (!isset($orgHref)) {
        $orgHref = function ($id, $name) {
            return $id ? route('orgProfile', ['id' => $id,
                         'orgslug' => \Illuminate\Support\Str::slug($name ?? '', '-')]) : null;
        };
    }
    // Where a type slice lands: the contracts index on the Contracts page.
    $bookSegFragment = '#all-digital-contracts';
@endphp
            <div class="row g-4 mb-4">
                <div class="col-lg-6">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head"><span class="db-chart-title">Value by agency</span></div>
                        <div class="db-chart-body" style="height: 280px;"><canvas id="ovAgencyChart"></canvas></div>
                        <div class="ds-seglinks">
                            @foreach($ovAgencySlices['items'] ?? [] as $it)
                                @php $oh = (!$it['grey'] && ($it['slug'] ?? '') !== '') ? $orgHref($it['slug'], $it['label']) : null; @endphp
                                @if($oh)<a href="{{ $oh }}" data-c="{{ $it['color'] }}"><i class="ds-sw"></i>{{ $it['label'] }}</a>@else<span data-c="{{ $it['color'] }}"><i class="ds-sw"></i>{{ $it['label'] }}</span>@endif
                            @endforeach
                        </div>
                        <p class="ds-chart-note">Pick an agency to open its profile.</p>
                    </div>
                </div>
                <div class="col-lg-6">
                    <div class="db-chart-card h-100">
                        <div class="db-chart-head"><span class="db-chart-title">Value by type</span></div>
                        <div class="db-chart-body" style="height: 280px;"><canvas id="ovTypeChart"></canvas></div>
                        {{-- ⚠⚠ THE DRILL-DOWN, AS REAL LINKS. The composition bar this
                             replaced was clickable, and `techsegments.resolve_slug` plus
                             the `contract_segment` parameter have NO OTHER CONSUMER —
                             dropping the affordance would leave a whole filter built and
                             wired to nothing, which this repo has shipped before.
                             ⚠ Anchors, not a canvas click handler: a click target painted
                             on a canvas is invisible to the keyboard and to a screen
                             reader. --}}
                        <div class="ds-seglinks">
                            @foreach($ovTypeSlices['items'] ?? [] as $it)
                                @if(!$it['grey'] && $it['slug'] !== '')
                                    <a href="{{ route('research.digital-reform.contracts', ['contract_segment' => $it['slug']]) }}{{ $bookSegFragment }}" data-c="{{ $it['color'] }}"><i class="ds-sw"></i>{{ $it['label'] }}</a>
                                @else
                                    <span data-c="{{ $it['color'] }}"><i class="ds-sw"></i>{{ $it['label'] }}</span>
                                @endif
                            @endforeach
                        </div>
                        <p class="ds-chart-note">
                            One segment per contract, so these add up. Pick one to filter
                            the contract list.
                        </p>
                    </div>
                </div>
            </div>

        {{-- ---------- Committed money by start year ----------
             ⚠⚠ THE BARS ARE COMMITTED MONEY ONLY. Master ceilings are reported
             beside them and NEVER stacked into them (#294): a ceiling bar makes an
             undrawn agreement look like the year's largest spend, and 2023 alone
             carries $913.1M of it. The chart this replaced summed the two under the
             label "Awarded Amount".
             ⚠ The active/ended split is the whole point — 83% of these contracts
             have already ended, so a single series reads as a live book. --}}
        @php
            $aby      = $awardByStartYear ?? [];
            $abyOK    = (bool) ($aby['available'] ?? false);
            $abyYears = $aby['years'] ?? [];
            $abyCur   = $aby['current_year'] ?? '';
            $abyUnusable = $aby['unusable_start_date'] ?? ['contracts' => 0, 'value' => 0];
            // ⚠ Reconciliation, not a headline: the totals the page states come from
            // `stats` (the tiles' own figures). These exist so a series that stops
            // closing to them is visible rather than silent.
            $abyRec   = $aby['reconciles'] ?? [];
            // ⚠⚠ COUNT **AND** VALUE. A count-only check is what let a real defect
            // through: a NULL master test dropped 2 contracts / $2,500,000 out of
            // every money aggregate while COUNT(*) still counted them, so the
            // contract reconciliation closed perfectly on a series that was $2.5M
            // short. Value needs a tolerance because award_amount is Postgres
            // `real`: the tile accumulates ~4,400 additions in float32 and lands
            // ~$8,800 (7e-7) off an exact numeric sum, so an equality test would
            // read as permanently broken. 0.01% is ~140x that noise and ~4x
            // smaller than the defect it exists to catch (2.4e-4).
            $abyCloseN = $abyOK && (int) ($abyRec['contracts'] ?? -1) === (int) ($stats['count'] ?? -2);
            // CEILING-PLUS-COMMITTED-OK: the ONE legitimate sum of the two, and only
            // because `stats.total` counts masters as well — so reconstructing the
            // grand total is the only way to check the series against it. This value
            // is never rendered as spend; it appears solely in the does-not-close
            // warning below. Any other addition of the two is the #294 defect, and a
            // guard caps this marker at one use.
            $abySum    = (float) ($abyRec['committed'] ?? 0) + (float) ($abyRec['ceiling'] ?? 0);
            $abyTot    = (float) ($stats['total'] ?? 0);
            $abyCloseV = $abyOK && $abyTot > 0 && abs($abySum - $abyTot) / $abyTot < 0.0001;
            $abyClose  = $abyCloseN && $abyCloseV;
            // The largest committed year, SELECTED from the served rows rather than
            // recomputed — a tall bar with no subject reads as a broad-based surge.
            $abyTop = null;
            foreach ($abyYears as $y) {
                $c = (float) $y['committed_active'] + (float) $y['committed_ended'];
                if ($abyTop === null || $c > $abyTop['c']) { $abyTop = ['y' => $y['year'], 'c' => $c]; }
            }
            $abyCeilTot = 0.0;
            foreach ($abyYears as $y) { $abyCeilTot += (float) $y['ceiling']; }
        @endphp
        <div class="db-chart-card mb-4" id="by-start-year">
            <div class="db-chart-head">
                <span class="db-chart-title">What the City committed, by the year the contract started</span>
            </div>
            @if($abyOK)
            <div class="db-chart-body" style="height: 340px;"><canvas id="digitalStartYearChart"></canvas></div>
            <p class="text-muted px-3" style="font-size: var(--db-text-2xs);">
                Bars show <strong>committed money</strong> &mdash; contracts whose value the City
                has agreed to pay &mdash; split by whether the contract is still running or has
                already ended.
                {{-- ⚠ Stated, not implied: this is the #294 rule made visible to the reader. --}}
                <strong>Master agreement ceilings are not in the bars.</strong> A master is
                headroom agencies buy against, drawn down under other contract ids, so adding
                ${{ number_format($abyCeilTot / 1000000, 1) }}M of ceiling to committed money
                would count agreements nobody has drawn against as spend; hover a bar to see
                that year's ceiling separately.
                @if($abyCur !== '')
                    {{ $abyCur }} is <strong>still in progress</strong> and its bar is partial.
                @endif
                @if((int) ($abyUnusable['contracts'] ?? 0) > 0)
                    {{ number_format($abyUnusable['contracts']) }} contracts carry no usable
                    start date and are not shown.
                @else
                    Every contract in scope carries a usable start date, so nothing is omitted.
                @endif
            </p>
            @if(!$abyClose)
            {{-- ⚠ A series that no longer closes to the tiles is a real problem and
                 says so, rather than being quietly rendered as if it were complete. --}}
            <p class="px-3 text-muted" style="font-size: var(--db-text-2xs);">
                <i class="bi bi-exclamation-triangle"></i>
                @if(!$abyCloseN)
                    This chart covers {{ number_format($abyRec['contracts'] ?? 0) }} contracts against
                    the {{ number_format($stats['count'] ?? 0) }} counted above &mdash; the two should
                    agree, so treat the yearly split as incomplete.
                @else
                    {{-- The failure mode a count check cannot see: every contract present,
                         money missing. --}}
                    This chart's yearly figures add to
                    ${{ number_format($abySum / 1000000, 1) }}M against the
                    ${{ number_format($abyTot / 1000000, 1) }}M counted above &mdash; the two
                    should agree, so treat the yearly split as incomplete.
                @endif
            </p>
            @endif
            @elseif(($aby['reason'] ?? '') !== '')
            <p class="text-muted px-3 py-3" style="font-size: var(--db-text-sm);">
                No technology contracts are in scope, so there is nothing to chart.
            </p>
            @else
            {{-- Distinct from "no contracts": the query failed, and the page says which. --}}
            <p class="text-muted px-3 py-3" style="font-size: var(--db-text-sm);">
                <strong>The by-year view is unavailable</strong> &mdash; the yearly breakdown
                could not be computed. Every other figure on this page is unaffected.
            </p>
            @endif
        </div>
