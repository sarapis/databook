{{-- The datasets accordion, as ONE component.

     ⚠⚠ FIFTEEN VIEWS HAND-ROLLED THIS, and thirteen of them also hand-rolled
     `loadTableStat()` — which fetched `/get/pstats-records_no/{table}`, a route
     that has never existed. On a non-200 the caller ran `datasets.splice(i,1)`,
     so those pages rendered their dataset rows and then DELETED them, leaving
     "No data available in table" and two blank counters. One shell means one
     place that can be wrong.

     ⚠⚠ TWO MODES, BECAUSE THERE ARE TWO QUESTIONS, and merging them is the one
     thing this component must not do:
       page   — "what data feeds this KIND of page", with each dataset's total
                record count. Identical on every project profile.
       record — "which publications carry THIS record", with presence and the
                VERSION each figure came from. Different on every one.
     A dataset's total record count and this record's presence in it are
     different claims. One row carrying both invites "475,136 records" to be
     read as being about this project.

     Usage:
       <x-db.data-provenance :datasets="$datasets" :count="$dsCount" :records="$dsRecords" />
       <x-db.data-provenance mode="record" :coverage="$cov" />
--}}
@props([
    'mode' => 'page',       // page | scoped | record
    'datasets' => [],       // page/scoped: rows of [name, section, description, updated, records]
    'count' => null,        // optional override; derived from $datasets when null
    'records' => null,
    'coverage' => [],       // record mode: the endpoint's source_coverage block
    'statUrl' => null,      // scoped mode: a URL template containing `tblname`
    'scopeLabel' => null,   // scoped mode: what the counts are scoped TO, in words
    'id' => 'dataProvenance',
])
@php
    $rows = $coverage['rows'] ?? [];

    // ⚠⚠ DERIVED HERE, ONCE, rather than in each of eleven views. The counts are
    // read back out of the rendered cell `countCell()` wrote, so the sentence and
    // the table cannot disagree — two independent computations of one number is
    // the defect this section keeps paying for. A dataset whose count is "not
    // tracked" still counts as a DATASET; only numeric cells are summed.
    if ($mode !== 'record') {
        $count = $count ?? count($datasets);
        if ($records === null) {
            $records = 0;
            foreach ($datasets as $d_) {
                $cell = (array_values((array) $d_)[4] ?? '');
                if (preg_match('/>([\d,]+)</', $cell, $mm_))
                    $records += (int) str_replace(',', '', $mm_[1]);
            }
        }
    }

    // ⚠ Scoped mode fills its counts from the page's own scoped endpoint, so the
    // keys have to travel with the rows. `stats_data_sources` keys by table.
    $statKeys = ($mode === 'scoped') ? array_keys((array) $datasets) : [];
    // ⚠ Present-first so the block leads with what this record HAS, while still
    // accounting for every source. Sorting is presentation; it never drops a row.
    if ($mode === 'record') {
        usort($rows, function ($a, $b) {
            return ($b['present'] <=> $a['present']) ?: ($a['retired'] <=> $b['retired']);
        });
    }
    $btn = $id . 'Btn';
@endphp

<div class="accordion social_media mb-3" id="{{ $id }}">
    <div>
        <div id="{{ $btn }}">
            <button class="social_btn" type="button" data-bs-toggle="collapse"
                    data-bs-target="#{{ $id }}Body" aria-expanded="false"
                    aria-controls="{{ $id }}Body">
                @if($mode === 'record')
                    {{-- ⚠ THE SUMMARY IS THE FINDING. "9 of 11" is what a reader
                         needs before deciding whether to open anything, and on
                         this section an ABSENCE is often the finding. --}}
                    We’re using normalized data from {{ number_format($coverage['sources_read'] ?? 0) }} {{ ($coverage['sources_read'] ?? 0) == 1 ? 'dataset' : 'datasets' }}. This record appears in {{ number_format($coverage['sources_present'] ?? 0) }} of them. Click here to learn more.
                @elseif($mode === 'scoped')
                    {{-- ⚠ The counts here are SCOPED — records in each dataset for
                         THIS type / category / budget line, not the dataset's size.
                         The sentence says so, because "N records" under a scoped
                         heading otherwise reads as the whole dataset. --}}
                    We’re using normalized data from {{ number_format($count ?? 0) }} {{ ($count ?? 0) == 1 ? 'dataset' : 'datasets' }}, counting the records in each @if($scopeLabel){{ $scopeLabel }}@else for this page @endif. Click here to learn more.
                @else
                    We’re using normalized data from {{ number_format($count ?? 0) }} {{ ($count ?? 0) == 1 ? 'dataset' : 'datasets' }} containing {{ number_format($records ?? 0) }} records. Click here to learn more.
                @endif
            </button>
        </div>
        <div id="{{ $id }}Body" class="collapse hide" aria-labelledby="{{ $btn }}">
            <div class="card-text table-responsive">
                @if($mode === 'record')
                    <table class="db-table display table-hover table-borderless" style="width:100%;">
                        <thead><tr>
                            <th scope="col">Publication</th>
                            <th scope="col">Publisher</th>
                            <th scope="col">In this record?</th>
                            <th scope="col">Version</th>
                            <th scope="col">Table</th>
                        </tr></thead>
                        <tbody>
                        @foreach($rows as $c)
                            <tr>
                                <td>
                                    {{ $c['label'] }}
                                    {{-- ⚠ ONE MEANING PER VARIANT: a retired series is a
                                         WARNING (a figure from it is a 2023 statement), a
                                         coarser grain is INFO (the figure is real, it is
                                         just not per record). --}}
                                    @if($c['retired'])<span class="db-badge db-badge-warning">retired 2023</span>@endif
                                    @if(($c['grain'] ?? 'project') !== 'project')<span class="db-badge db-badge-info">by budget line</span>@endif
                                </td>
                                <td class="small">{{ $c['publisher'] }}</td>
                                <td>
                                    {{-- ⚠ "Not published", never 0 or blank: a dataset with
                                         205,503 rows and none for this record is not empty. --}}
                                    {{ $c['present'] ? 'Yes' : 'Not published' }}
                                    @if($c['detail'])<span class="db-muted small">· {{ $c['detail'] }}</span>@endif
                                </td>
                                <td>{{ ($c['version'] === null || $c['version'] === '') ? '—' : $c['version'] }}</td>
                                <td class="small db-muted">{{ implode(', ', $c['tables'] ?? []) }}</td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                @else
                    <table class="db-table display table-hover table-borderless" style="width:100%;">
                        <thead><tr>
                            <th scope="col">Name</th>
                            <th scope="col">Section</th>
                            <th scope="col">Description</th>
                            <th scope="col">Last Updated</th>
                            <th scope="col">Dataset Records</th>
                        </tr></thead>
                        <tbody>
                        @foreach($datasets as $d)
                            <tr>@foreach(array_values((array) $d) as $cell)<td>{!! $cell !!}</td>@endforeach</tr>
                        @endforeach
                        </tbody>
                    </table>
                @endif
            </div>
            {{-- ⚠ The record mode's three notes stay OUTSIDE the table and are the
                 endpoint's own — the grain caveat, the exclusions, and the
                 retired-series notice. The last one is the sentence that stops a
                 2023 figure being read as current, so it is a `db-note`, not the
                 faintest text on the page. --}}
            @if($mode === 'record')
                {{-- ⚠ These three DESCRIBE the table and belong with it. --}}
                <p class="db-note-small mb-1">{{ $coverage['note'] ?? '' }}</p>
                <p class="db-note-small mb-1">{{ $coverage['grain_note'] ?? '' }}</p>
                <p class="db-note-small mb-0">{{ $coverage['excluded_note'] ?? '' }}</p>
            @endif
        </div>
    </div>
</div>
@if($mode === 'record' && !empty($coverage['retired_note']))
    {{-- ⚠⚠ OUTSIDE THE COLLAPSE, DELIBERATELY, AND A GUARD CAUGHT IT BEING
         INSIDE. This is the sentence that stops a 2023 figure being read as
         current — one of the three this section calls load-bearing — and a
         caveat behind a disclosure triangle is a caveat nobody reads. Folding
         the table into the shared accordion took it with it; it comes back out.
         ⚠ The other three notes stay inside because they DESCRIBE the table:
         they are unreadable without the rows they are about. --}}
    <p class="db-note">{{ $coverage['retired_note'] }}</p>
@endif

@if($mode === 'scoped' && $statUrl)
<script>
(function () {
    // ⚠⚠ THIS REPLACES `loadTableStat()`, WHICH DELETED THE ROWS IT HAD JUST
    // RENDERED. Its callback was `if (resp.data[0].res) { fill } else { splice }`,
    // so a scoped count of **0** — a fact, meaning this dataset holds nothing for
    // this type — removed the row entirely, and a FAILED request did the same.
    // Measured on `/projects/types/animal-care`: 3 datasets requested, **1 row
    // survived**. On the seven pages whose stat route does not exist at all it
    // threw `Cannot read properties of undefined (reading 'res')` instead, once
    // per dataset, leaving both counters blank.
    //
    // ⚠ THREE OUTCOMES, THREE DIFFERENT CELLS, and no row is ever removed:
    //     a number   the scoped count
    //     0          this dataset holds nothing for this scope — a finding
    //     —          the request failed; we do not know, and must not imply 0
    var KEYS = @json($statKeys);
    var TPL  = {!! json_encode($statUrl) !!};
    var total = 0, counted = 0;
    KEYS.forEach(function (k) {
        var cell = document.getElementById('stats_' + k);
        if (!cell) return;
        $.ajax({
            url: TPL.replace('tblname', k), dataType: 'json',
            success: function (d) {
                var rows = (d && d.rows) ? d.rows : [];
                // ⚠ A MISSING ROW IS NOT A ZERO. `rows[0].res` absent means the
                // endpoint answered without a figure, which is "unknown".
                if (!rows.length || rows[0].res === undefined || rows[0].res === null) {
                    cell.textContent = '—';
                    cell.className = 'db-muted';
                    return;
                }
                var n = Number(rows[0].res) || 0;
                cell.textContent = n.toLocaleString();
                // ⚠⚠ TWO ROWS IN THIS PANEL CAN BE COUNTED DIFFERENTLY, AND THE
                // GAP IS LARGE. A source that carries the scope dimension is
                // counted on its OWN column; one that does not is counted
                // through the PROJECT its rows belong to, via the capital
                // spine. On a budget line those differ by 82 against 568,
                // because a project is funded through several lines. Serving
                // `via` and marking it is what stops the two being read as one
                // kind of figure — the same reason record mode badges a coarser
                // grain instead of hiding it.
                // ⚠⚠ A RETIRED-SERIES FIGURE IS LABELLED HERE TOO, not only in
                // record mode. Measured on the category panel before this: the
                // 2023 series' **2,671** sat beside four current sources
                // (413 / 953 / 3,465) with a BLANK "Last Updated" and nothing
                // saying the series stops in October 2023. A reader forms a
                // ratio from adjacency, and this section's standing rule is
                // that no capital figure from that series goes unlabelled.
                if (d.retired) {
                    var rb = document.createElement('span');
                    rb.className = 'db-badge db-badge-warning ms-1';
                    rb.textContent = 'retired ' + String(d.retired).slice(0, 4);
                    rb.title = 'NYC stopped publishing this series on ' +
                        d.retired + '. The figure is real, and it is a ' +
                        'statement about that date rather than about today.';
                    cell.appendChild(rb);
                }
                if (d.via === 'crosswalk') {
                    var b = document.createElement('span');
                    b.className = 'db-badge db-badge-info ms-1';
                    b.textContent = 'via project';
                    b.title = 'This dataset carries no ' +
                        String(d.scope_type || '').replace(/_/g, ' ') +
                        ' column, so its records are counted through the ' +
                        'capital projects they belong to.';
                    cell.appendChild(b);
                }
                total += n; counted += 1;
                // ⚠⚠ AND THE SCOPED SENTENCE MUST NOT STATE THIS TOTAL. No
                // `{{ $id }}Total` element exists in scoped mode, so this is a
                // no-op there — deliberately. Since the widening, a scoped panel
                // mixes own-column counts with crosswalked ones (82 records
                // naming a budget line beside 60 belonging to projects funded
                // through it), and adding those two kinds of figure produces a
                // number that is about nothing. The scoped sentence therefore
                // states the DATASET COUNT only; the per-row cells carry the
                // figures, each labelled with how it was counted. Same rule as
                // "a ceiling is not spend, never sum the two".
                var t = document.getElementById('{{ $id }}Total');
                if (t) t.textContent = total.toLocaleString();
            },
            error: function () {
                // ⚠ A FAILED REQUEST IS NOT AN EMPTY RESULT — the rule this repo
                // has paid for repeatedly. The row stays and says we do not know.
                cell.textContent = '—';
                cell.className = 'db-muted';
            }
        });
    });
})();
</script>
@endif
