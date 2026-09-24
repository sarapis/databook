@extends('layout')


@section('head')
	<meta name="description" content="A webpage for every NYC-funded capital project" />
	<meta rel="canonical" href="{!! route('projects') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')

@php
	// ⚠⚠ THE PAGE COMPUTES NOTHING IT CAN BE SERVED. Every count below is a key
	// the endpoint returned. Two independent computations of one number is the
	// defect this whole capital rebuild exists to end — and on these two
	// endpoints it was live: `?has_location=false` listed 12,464 projects while
	// the map drew 4,560 pins for projects the list had excluded.
	//
	// ⚠ Conditional phrases are precomputed here because a Blade directive glued
	// to a word character is not compiled and 500s the page.
	$cl        = is_array($capList ?? null) ? $capList : [];
	$clOk      = !empty($cl['available']);
	$rows      = $cl['rows'] ?? [];
	$total     = $cl['total'] ?? null;
	$pages     = (int) ($cl['pages'] ?? 0);
	$page      = (int) ($capPage ?? 1);
	$perPage   = (int) ($cl['per_page'] ?? 50);

	$opt       = is_array($capOptions ?? null) ? $capOptions : [];
	$optFlags  = $opt['flags'] ?? [];
	$programme = $optFlags['projects'] ?? null;

	$f         = is_array($capFilters ?? null) ? $capFilters : [];
	$fv        = function ($k) use ($f) { return $f[$k] ?? ''; };

	$fmtN = function ($v) { return is_numeric($v) ? number_format((float) $v) : '—'; };
	$fmtM = function ($v) {
		if (!is_numeric($v)) return '—';
		$v = (float) $v;
		if (abs($v) >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
		if (abs($v) >= 1000000) return '$' . number_format($v / 1000000, 1) . 'M';
		if (abs($v) >= 1000) return '$' . number_format($v / 1000, 0) . 'K';
		return '$' . number_format($v);
	};

	// The row range this page shows, from the served page/per_page/total — never
	// from count($rows), which would read "1-50 of 50" on the last page.
	//
	// ⚠⚠ A PAGE PAST THE END HAS NO RANGE, AND ARITHMETIC ALONE PRODUCES A LIE.
	// `?page=99999` rendered "Showing 4,999,901–17,024" — a first row past the
	// last row, over a list of 341 pages — because the formula is only valid
	// where rows exist. The ceiling cannot be clamped before the request (the
	// page count is only known from the response) and clamping it after would
	// silently answer a different URL, so the page SAYS it is past the end.
	$pastEnd  = $pages > 0 && $page > $pages;
	$hasRows  = count($rows) > 0;
	$firstRow = ($total && $hasRows) ? (($page - 1) * $perPage) + 1 : 0;
	$lastRow  = ($total && $hasRows) ? min($page * $perPage, (int) $total) : 0;

	// ⚠ Pagination links carry the CURRENT filters. Dropping them is how a
	// reader lands on page 2 of a different question.
	$pageUrl = function ($p) use ($f, $capSort, $capDirection) {
		return route('projects') . '?' . http_build_query(array_merge($f, [
			'sort' => $capSort, 'direction' => $capDirection, 'page' => $p,
		]));
	};
	$anyFilter = count($f) > 0;

	// ⚠ Counted from the rendered rows, so the sentence and the table cannot
	// disagree. `countCell` writes a formatted number or the words "not
	// tracked"; only the numeric ones are summed, and the dataset count is the
	// number of rows shown either way — a dataset we cannot count is still a
	// dataset we read.
	$dsCount = count($datasets);
	$dsRecords = 0;
	foreach ($datasets as $ds_) {
		$cell = $ds_[4] ?? '';
		if (preg_match('/>([\d,]+)</', $cell, $mm))
			$dsRecords += (int) str_replace(',', '', $mm[1]);
	}

	// ⚠⚠ PRECOMPUTED, BECAUSE A BLADE DIRECTIVE GLUED TO A WORD CHARACTER IS NOT
	// COMPILED. The first draft of this sentence ended `... tracked@endif.` —
	// Blade compiled the `@if` and left the `@endif` as literal text, and the
	// page 500'd with "unexpected end of file". `php -l` passes on it either way,
	// because the file is valid PHP whichever way Blade reads it. Conditional
	// phrases live here.
	$matchPhrase = $anyFilter ? 'projects match these filters' : 'projects tracked';
	if ($anyFilter && is_numeric($programme))
		$matchPhrase .= ', of ' . $fmtN($programme) . ' tracked';
	$matchPhrase .= '.';
	$showingPhrase = '';
	if ($pastEnd)
		$showingPhrase = 'Page ' . $fmtN($page) . ' is past the end of this list, which has ' . $fmtN($pages) . ' pages.';
	elseif ($total && $hasRows)
		$showingPhrase = 'Showing ' . $fmtN($firstRow) . '–' . $fmtN($lastRow) . '.';
@endphp

	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-12 organization_data pb-1">
					<div class="db-eyebrow">Projects</div>
					<h1 class="db-profile-title">Capital Projects</h1>
					<p class="lead">Capital projects are managed by city agencies and use city funds to produce, improve and maintain city infrastructure and assets like roads, sewers, schools and sanitation trucks, and more.</p>
				</div>
			</div>

			@if (!$clOk)
				{{-- ⚠ An unavailable section says so. A silently empty table reads
				     as "the City has no capital projects". --}}
				<div class="alert alert-secondary" role="alert">
					The capital project list is not available right now.
				</div>
			@else

			<div class="row mb-3">
				<div class="col-12">
					{{-- ⚠ The unfiltered form of this line — "17,024 projects tracked. Showing
					     1–50." — was removed at the owner's request: on the default view it
					     restates the tile above it and the pager below it.
					     ⚠⚠ IT IS GATED, NOT DELETED, AND THE `$pastEnd` ARM IS THE REASON.
					     `?page=99999` once rendered "Showing 4,999,901–17,024" — a first row
					     past the last row — and the sentence saying the page is past the end
					     is what replaced that lie. Dropping the whole block would bring it
					     back on any unfiltered out-of-range page. The filtered count is kept
					     too: there, "N match these filters, of 17,024 tracked" is the answer
					     to the question the reader just asked. --}}
					@if ($anyFilter || $pastEnd)
						<p class="mb-1">
							<strong>{{ $fmtN($total) }}</strong> {{ $matchPhrase }} {{ $showingPhrase }}
						</p>
					@endif
					{{-- ⚠ A FILTER WITH NO CONTROL MUST STILL BE VISIBLE AND REMOVABLE.
					     `budget_line` is set only by a link (from a budget-line page), so
					     without this line the reader sees a narrowed list and no reason
					     for it — and has no way back except editing the URL. --}}
					@if ($fv('budget_line') !== '')
						<p class="mb-1 small">
							Filtered to budget line <strong>{{ $fv('budget_line') }}</strong>.
							<a href="{!! route('projects') !!}?{!! http_build_query(array_diff_key($f, ['budget_line' => ''])) !!}">Remove this filter</a>
						</p>
					@endif
					<p class="text-muted small mb-0">
						Every figure on this page is read from Databook’s capital project spine, which is built from the current Capital Commitment Plan, the Capital Projects Dashboard and the 2023 project detail data. <a href="{!! route('capital') !!}">See the programme overview</a> for what each money measure means — they are six separate measures, not stages of one pot.
					</p>
				</div>
			</div>


					{{-- ⚠⚠ MOVED HERE FROM /procurement (owner request). These tiles and
					     the Checkbook capital-spend chart were added to a PROCUREMENT page
					     on 2026-07-13, when no rebuilt capital section existed and
					     CheckbookNYC published no capital feed. With /projects and
					     /projects/about built they were simply the same figures in two
					     places — which is what produced the 5,128-vs-12,929 disagreement
					     this section has already paid for once.
					     ⚠ Every tile states what it is OVER, because no two of the four
					     share a denominator: the plan is 12,929 of 17,024 tracked, planned
					     money covers 9,213 projects, spent 7,118, and a published schedule
					     8,483 of all 17,024. Without those, the grid reads as 66% of the
					     plan being scheduled where the truth is 51%. --}}
        @php
            // ⚠⚠ THESE TILES USED TO READ `globStats`, i.e. `cached_stats` over
            // `capitalprojectsdollarscomp` — the series NYC RETIRED 2023-10-26.
            // They showed 5,128 projects while the rebuilt /projects/capital
            // showed 12,929, and the comment here claimed the two "match
            // exactly". Two pages, one subject, different numbers.
            //
            // ⚠ `Amount Over Budget` is NOT reproduced. It is the label this
            // repo documents as carrying two definitions — every row's budget
            // difference globally, but only the negative ones per district —
            // and the rebuilt Overview drops it rather than repointing it.
            $pCap    = is_array($capital ?? null) ? $capital : [];
            $pCapOk  = !empty($pCap['available']) && !empty($pCap['projects']);
            $pSched  = $pCap['schedule'] ?? [];
            $pMoney  = [];
            foreach (($pCap['money']['measures'] ?? []) as $pm) {
                $pMoney[$pm['key'] ?? ''] = $pm;
            }
            $pFmtN = function ($v) { return is_numeric($v) ? number_format((float) $v) : '—'; };
            $pFmtB = function ($v) {
                if (!is_numeric($v)) return '—';
                $v = (float) $v;
                if (abs($v) >= 1000000000) return '$' . number_format($v / 1000000000, 1) . 'B';
                if (abs($v) >= 1000000) return '$' . number_format($v / 1000000, 1) . 'M';
                return '$' . number_format($v);
            };
            $pPlanned = $pMoney['planned_usd']['value'] ?? null;
            $pSpent   = $pMoney['spent_usd']['value'] ?? null;

            // >> THESE FOUR TILES MIXED TWO SCOPES SILENTLY, AND THE RATIO A
            // READER FORMS FROM THEM WAS WRONG BY 15 POINTS. Tile 1 counts the
            // 12,929 projects in the current plan; "with a published schedule"
            // is 8,483 of ALL 17,024 tracked, of which only 6,561 are in the
            // plan. Read together they say 66% of the plan is scheduled; the
            // real figure is 51%, and 1,922 of the 8,483 are not in the plan at
            // all. The money measures carry their own populations too (9,213
            // planned, 7,118 spent) - none of these four is over the same set.
            // So every tile now states what it is over, which is exactly what
            // the Overview does with `population` per measure.
            $pPlannedPop = $pMoney['planned_usd']['population'] ?? null;
            $pSpentPop   = $pMoney['spent_usd']['population'] ?? null;
            $pTracked    = $pCap['projects'] ?? null;
            $pOfTracked  = is_numeric($pTracked) ? 'of ' . $pFmtN($pTracked) . ' tracked' : null;
            $pOfProjects = function ($n) use ($pFmtN) {
                return is_numeric($n) ? $pFmtN($n) . ' projects' : null;
            };
        @endphp
        @if ($pCapOk)
        <div class="db-stat-grid mb-4">
            <a href="{{ route('capital') }}" class="db-stat" style="text-decoration:none;">
                <div class="db-stat-label">Projects in the current plan</div>
                <div class="db-stat-value">{{ $pFmtN($pCap['in_current_plan'] ?? null) }}</div>
                @if($pOfTracked)<div class="db-stat-sub">{{ $pOfTracked }}</div>@endif
            </a>
            <a href="{{ route('capital') }}" class="db-stat" style="text-decoration:none;">
                <div class="db-stat-label">Planned commitments</div>
                <div class="db-stat-value">{{ $pFmtB($pPlanned) }}</div>
                @if($pOfProjects($pPlannedPop))<div class="db-stat-sub">{{ $pOfProjects($pPlannedPop) }}</div>@endif
            </a>
            <a href="{{ route('capital') }}" class="db-stat is-accent" style="text-decoration:none;">
                <div class="db-stat-label">Spent</div>
                <div class="db-stat-value">{{ $pFmtB($pSpent) }}</div>
                @if($pOfProjects($pSpentPop))<div class="db-stat-sub">{{ $pOfProjects($pSpentPop) }}</div>@endif
            </a>
            <a href="{{ route('capital') }}" class="db-stat" style="text-decoration:none;">
                <div class="db-stat-label">With a published schedule</div>
                <div class="db-stat-value">{{ $pFmtN($pSched['with_published_schedule'] ?? null) }}</div>
                @if($pOfTracked)<div class="db-stat-sub">{{ $pOfTracked }}</div>@endif
            </a>
        </div>
        {{-- ⚠ Planned and spent are two of SIX separate measures that do not sum
             or nest; the Overview carries all six with their populations and the
             note explaining why. Showing two here without that link would invite
             exactly the subtraction the note exists to prevent. --}}
        <p class="small text-muted mb-4">
            Planned commitments and spending are two of six separate measures the
            City publishes; they do not sum or nest.
            <a href="{{ route('capital') }}">See all six, with what each covers</a>.
        </p>
        @else
        <div class="alert alert-secondary" role="alert">
            Capital programme figures are not available right now.
        </div>
        @endif
        {{-- Actual capital spending by fiscal year — Checkbook 'Capital Contracts' payments (cash paid out; distinct from the CPDB budget/cost figures above) --}}
        @if(!empty($capitalSpend['values']))
        <div class="db-card mb-5" style="overflow:hidden; padding:var(--db-space-4);">
            <div class="db-chart-head"><span class="db-chart-title">Actual Capital Spending by Fiscal Year @include('procurement.partials.source_badge', ['source' => 'checkbook'])</span></div>
            <div class="db-chart-body" style="height: 280px;"><canvas id="capitalSpendChart"></canvas></div>
        </div>
        @endif

		<div class="row">
				<div id="map_container" class="col-12 mb-0 position-relative" style="min-height:540px!important;">
					<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;"></div>

					<!-- Map-scoped loading overlay (not the full-page .loading) -->
					<div id="mapLoadingOverlay" style="display:none; position:absolute; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.55); z-index:400; align-items:center; justify-content:center; flex-direction:column; border-radius:8px;">
						<div style="width:40px; height:40px; border:3px solid rgba(255,255,255,0.3); border-top-color:#fff; border-radius:50%; animation:mapSpin 0.8s linear infinite;"></div>
						<div style="color:#fff; margin-top:12px; font-size:14px; font-weight:500;">Loading project locations&hellip;</div>
					</div>
					<style>@keyframes mapSpin { to { transform: rotate(360deg); } }</style>

					{{-- Address search, top-left — the same overlay pattern /districts
					     uses, replacing the combined "Search & Layers" flyout. --}}
					<div class="db-map-search" style="top: var(--db-space-2); left: var(--db-space-2);">
						<i class="bi bi-search"></i>
						<input id="addrSearch" type="text" placeholder="Search an address…" aria-label="Enter address to find capital projects" onkeydown="addrSearchKeyPress(this)" autocomplete="off">
						<button class="db-map-search-go" id="addrSearchBtn" type="button" onclick="addrSearch();" data-bs-toggle="popover" data-content="" data-placement="bottom" data-trigger="manual" aria-label="Search address"><i class="bi bi-arrow-right"></i></button>
					</div>

					{{-- Boundary overlays, top-right.
					     ⚠ THE SWITCH IDS ARE LOAD-BEARING AND UNCHANGED. `script.js`
					     binds each layer by ID — `$('#'+code+'-switch').change(...)` —
					     so renaming one silently stops that boundary toggling while the
					     control still looks fine.
					     ⚠ The `<hr>` in each row is not decoration: the same helper does
					     `$('label[for="'+code+'-switch"] hr').attr('style', 'background-color: …')`
					     to paint the layer's colour swatch. The old panel had no `<hr>`,
					     so this page has been showing boundary toggles with no colour key
					     at all. --}}
					<div class="db-map-control" id="boundaries-control" style="top: var(--db-space-2); right: var(--db-space-2);">
						<button type="button" class="db-btn db-btn-outline db-btn-sm" id="boundaries-toggle" aria-haspopup="true" aria-expanded="false" style="background:#fff;">
							<i class="bi bi-bounding-box-circles"></i> Show District Boundaries <i class="bi bi-chevron-down db-caret"></i>
						</button>
						<div class="db-map-control-menu" id="boundaries_controls">
							<p class="db-map-control-label">Overlay boundaries</p>
							@php
								$boundaryLayers = [
									'cd' => 'Community Districts',
									'ed' => 'Election Districts',
									'pp' => 'Police Precincts',
									'dsny' => 'Sanitation Districts',
									'fb' => 'Fire Battalions',
									'sd' => 'School Districts',
									'hc' => 'Health Center Districts',
									'cc' => 'City Council Districts',
									'nycongress' => 'Congressional Districts',
									'sa' => 'State Assembly Districts',
									'ss' => 'State Senate Districts',
									'bid' => 'Business Improvement Districts',
									'nta' => 'Neighborhood Tabulation Areas',
									'zipcode' => 'Zip Code',
								];
							@endphp
							@foreach ($boundaryLayers as $code => $label)
								<label class="db-map-control-row" for="{{ $code }}-switch">
									<input type="checkbox" id="{{ $code }}-switch">
									<span>{{ $label }}</span>
									<hr class="border-sample db-map-swatch">
								</label>
							@endforeach
						</div>
					</div>
				</div>
				</div>

				{{-- ⚠⚠ THE LEGEND IS THE ENDPOINT'S OWN `coverage.note`, RENDERED
				     VERBATIM BY THE MAP CALLBACK — never a sentence typed here with
				     numbers in it. A typed denominator is the defect this repo has
				     shipped repeatedly ("the largest 20 families — 88.0% of value"
				     against a computed 87.7%), and here it would go stale the moment
				     any filter is applied. It is empty until the map answers, and it
				     says so. --}}
				<div class="row mt-2 mb-4">
					<div class="col-12">
						<p id="mapCoverageNote" class="text-muted small mb-1">Loading project locations&hellip;</p>
						<div id="mapLegend" class="small" style="display:none;">
							<span class="me-3"><strong>Phase:</strong></span>
							<span class="me-3"><span class="db-map-key" style="background:#ff7c7c"></span> Pre-Design</span>
							<span class="me-3"><span class="db-map-key" style="background:#78c0a8"></span> Design</span>
							<span class="me-3"><span class="db-map-key" style="background:#beedb9"></span> Construction Procurement</span>
							<span class="me-3"><span class="db-map-key" style="background:#36c726"></span> Construction</span>
							<span class="me-3"><span class="db-map-key" style="background:#f2c45a"></span> Close-out</span>
							<span class="me-3"><span class="db-map-key" style="background:#53777a"></span> No schedule published</span>
						</div>
						<style>.db-map-key{display:inline-block;width:11px;height:11px;border-radius:50%;vertical-align:middle;margin-right:4px;}</style>
					</div>
				</div>

		</div>

		<div class="container">
			<div class="inner_container">

				{{-- ================= FILTERS ================= --}}
				<form method="GET" action="{!! route('projects') !!}" class="row g-2 align-items-end mb-3" id="capFilterForm">
					{{-- ⚠⚠ A GET FORM SUBMITS ONLY ITS OWN FIELDS, so a filter that arrives
					     in the URL and has no control here is SILENTLY DROPPED the moment
					     the reader touches any other filter. `budget_line` has no control
					     on purpose — there are 1,913 of them — so it travels as a hidden
					     field. This is the same rule as "pagination links carry the current
					     filters", one submit button over. --}}
					@if($fv('budget_line') !== '')
						<input type="hidden" name="budget_line" value="{{ $fv('budget_line') }}">
					@endif
					<div class="col-md-3">
						<label class="form-label small mb-1" for="fq">Search descriptions</label>
						<input class="form-control form-control-sm" type="search" id="fq" name="q" value="{{ $fv('q') }}" placeholder="e.g. reconstruction" autocomplete="off">
					</div>
					<div class="col-md-3">
						<label class="form-label small mb-1" for="fagency">Managing agency</label>
						<select class="form-select form-select-sm" id="fagency" name="agency">
							<option value="">All agencies</option>
							{{-- ⚠⚠ THIS LIST WAS TWO VOCABULARIES — 34 agencies with names and 21
							     bare FMS codes labelled with themselves, because `agency_acro` is
							     NULL on the 4,095 projects outside the current plan. `850` was the
							     THIRD-LARGEST entry and named nothing, and choosing
							     "Department of Parks and Recreation" returned 2,798 of its 3,429
							     projects. The endpoint resolves a code to its agency wherever the
							     code carries exactly one, so 55 options became 31 and they sum to
							     the whole spine. ⚠ `801` is deliberately still a code: it is three
							     organisations (SBS, Brooklyn Navy Yard, Trust for Governors
							     Island) and its 121 unnamed rows belong to one of them. --}}
							@foreach($opt['agencies'] ?? [] as $a)
								<option value="{{ $a['value'] }}" {{ $fv('agency') === $a['value'] ? 'selected' : '' }}>{{ $a['label'] }} ({{ $fmtN($a['n']) }})</option>
							@endforeach
						</select>
					</div>
					<div class="col-md-3">
						<label class="form-label small mb-1" for="fborough">Borough</label>
						<select class="form-select form-select-sm" id="fborough" name="borough">
							<option value="">All boroughs</option>
							@foreach($opt['boroughs'] ?? [] as $b)
								@if($b['value'] !== '')
									<option value="{{ $b['value'] }}" {{ strtoupper($fv('borough')) === $b['value'] ? 'selected' : '' }}>{{ ucwords(strtolower($b['value'])) }} ({{ $fmtN($b['n']) }})</option>
								@endif
							@endforeach
						</select>
					</div>
					<div class="col-md-3">
						<label class="form-label small mb-1" for="fcategory">Asset category</label>
						<select class="form-select form-select-sm" id="fcategory" name="category">
							<option value="">All categories</option>
							@foreach($opt['categories'] ?? [] as $c)
								@if($c['value'] !== '')
									<option value="{{ $c['value'] }}" {{ $fv('category') === $c['value'] ? 'selected' : '' }}>{{ $c['value'] }} ({{ $fmtN($c['n']) }})</option>
								@endif
							@endforeach
						</select>
					</div>

					<div class="col-md-3">
						<label class="form-label small mb-1" for="fphase">Phase or status</label>
						{{-- ⚠⚠ TWO VOCABULARIES WERE MIXED IN ONE FLAT LIST, ORDERED BY COUNT,
						     so `(Pending)` at 1,854 led a dropdown labelled "Phase or status"
						     and `Construction` at 825 sat fourth. Measured 2026-09-10: **5** of
						     the 39 options are the phases the City publishes a schedule for
						     (Pre-Design, Design, Construction Procurement, Construction,
						     Close-out); the other **34** are parenthesised NON-phases meaning
						     "no schedule is required".
						     ⚠ The split is READ FROM THE PAYLOAD (`is_standard`), never
						     re-derived here from the brackets — the endpoint owns it, and a
						     second rule spelled in a template is how two lists of one thing
						     come to disagree.
						     ⚠⚠ THEY ARE GROUPED, NEVER MERGED. `(Construction)` 18 is NOT
						     `Construction` 825 — the parentheses are the publisher's own mark
						     that no schedule applies, so collapsing them would be a judgement
						     about what the City meant, not a normalisation. The only safe
						     collapse is case, and the endpoint already does it
						     (`Construction Procurement` 317 + `Construction procurement` 6 =
						     one option worth 323).
						     ⚠ The labels keep their published spelling, parentheses included.
						     The endpoint's own comment says the label is a representative
						     stored spelling and never a re-cased invention; stripping the
						     brackets here would be this page correcting a publisher it is
						     quoting. The optgroup says what they mean instead. --}}
						@php
							$phaseOpts = $opt['phases'] ?? [];
							$phStd = array_values(array_filter($phaseOpts, function ($p) { return !empty($p['is_standard']); }));
							$phOther = array_values(array_filter($phaseOpts, function ($p) { return empty($p['is_standard']); }));
						@endphp
						<select class="form-select form-select-sm" id="fphase" name="phase">
							<option value="">Any phase or status</option>
							@if($phStd)
								<optgroup label="Phase &mdash; the City publishes a schedule">
									@foreach($phStd as $p)
										<option value="{{ $p['label'] }}" {{ strtolower($fv('phase')) === strtolower($p['label']) ? 'selected' : '' }}>{{ $p['label'] }} ({{ $fmtN($p['n']) }})</option>
									@endforeach
								</optgroup>
							@endif
							@if($phOther)
								<optgroup label="Status &mdash; no schedule is required">
									@foreach($phOther as $p)
										<option value="{{ $p['label'] }}" {{ strtolower($fv('phase')) === strtolower($p['label']) ? 'selected' : '' }}>{{ $p['label'] }} ({{ $fmtN($p['n']) }})</option>
									@endforeach
								</optgroup>
							@endif
						</select>
					</div>
					<div class="col-md-2">
						<label class="form-label small mb-1" for="fin_plan">Current plan</label>
						<select class="form-select form-select-sm" id="fin_plan" name="in_plan">
							<option value="">Either</option>
							<option value="1" {{ $fv('in_plan') === 'true' ? 'selected' : '' }}>In the plan ({{ $fmtN($optFlags['in_plan'] ?? null) }})</option>
							<option value="0" {{ $fv('in_plan') === 'false' ? 'selected' : '' }}>Dropped ({{ $fmtN($optFlags['not_in_plan'] ?? null) }})</option>
						</select>
					</div>
					<div class="col-md-2">
						<label class="form-label small mb-1" for="fhas_schedule">Schedule</label>
						<select class="form-select form-select-sm" id="fhas_schedule" name="has_schedule">
							<option value="">Either</option>
							<option value="1" {{ $fv('has_schedule') === 'true' ? 'selected' : '' }}>Published ({{ $fmtN($optFlags['has_schedule'] ?? null) }})</option>
							<option value="0" {{ $fv('has_schedule') === 'false' ? 'selected' : '' }}>None ({{ $fmtN($optFlags['no_schedule'] ?? null) }})</option>
						</select>
					</div>
					<div class="col-md-2">
						<label class="form-label small mb-1" for="fhas_location">Location</label>
						<select class="form-select form-select-sm" id="fhas_location" name="has_location">
							<option value="">Either</option>
							<option value="1" {{ $fv('has_location') === 'true' ? 'selected' : '' }}>Published ({{ $fmtN($optFlags['has_location'] ?? null) }})</option>
							<option value="0" {{ $fv('has_location') === 'false' ? 'selected' : '' }}>None ({{ $fmtN($optFlags['no_location'] ?? null) }})</option>
						</select>
					</div>
					<div class="col-md-3">
						<label class="form-label small mb-1" for="fsort">Sort by</label>
						<div class="input-group input-group-sm">
							<select class="form-select form-select-sm" id="fsort" name="sort">
								@foreach(['planned' => 'Planned commitments', 'adopted' => 'Adopted budget', 'committed' => 'Committed', 'spent' => 'Spent', 'agency' => 'Agency', 'id' => 'Project ID'] as $k => $lbl)
									<option value="{{ $k }}" {{ $capSort === $k ? 'selected' : '' }}>{{ $lbl }}</option>
								@endforeach
							</select>
							<select class="form-select form-select-sm" id="fdirection" name="direction" aria-label="Sort direction">
								<option value="desc" {{ $capDirection === 'desc' ? 'selected' : '' }}>High → low</option>
								<option value="asc" {{ $capDirection === 'asc' ? 'selected' : '' }}>Low → high</option>
							</select>
						</div>
					</div>
					<div class="col-md-3">
						<button type="submit" class="btn btn-sm btn-primary">Apply filters</button>
						@if($anyFilter)<a href="{!! route('projects') !!}" class="btn btn-sm btn-outline-secondary">Clear</a>@endif
					</div>
				</form>

				{{-- ================= TABLE ================= --}}
				<div class="table-responsive">
					<table class="db-table table table-hover" id="capProjectsTable" style="width:100%;">
						<thead>
							<tr>
								<th scope="col">Project</th>
								<th scope="col">Agency</th>
								<th scope="col">Category</th>
								<th scope="col">Phase</th>
								<th scope="col" class="text-end">Planned</th>
								<th scope="col" class="text-end">Committed</th>
								<th scope="col" class="text-end">Spent</th>
								<th scope="col">Location</th>
							</tr>
						</thead>
						<tbody>
						@forelse($rows as $r)
							@php
								// ⚠ THE CANONICAL URL ID IS THE AGENCY-CONCATENATED FORM.
								// A bare FMS id does not identify a project — 1,160 ids are
								// carried by more than one agency across 2,371 rows — so a
								// link built from `fms_id` alone can send a reader to
								// another agency's project under this one's number.
								$pid  = ($r['agency_key'] ?? '') . ($r['fms_id'] ?? '');
								$desc = trim((string) ($r['description'] ?? '')) ?: ($r['fms_id'] ?? 'Untitled project');
								$purl = '/p/' . rawurlencode($pid) . '_' . \Illuminate\Support\Str::slug($desc);
							@endphp
							<tr>
								<td>
									<a href="{{ $purl }}">{{ $desc }}</a>
									<div class="text-muted small">{{ $pid }}@if(!($r['in_current_plan'] ?? false)) · <span class="db-badge db-badge-neutral">not in the current plan</span>@endif</div>
								</td>
								<td>
									@if(!empty($r['wegov_org_id']))
										<a href="/o/{{ $r['wegov_org_id'] }}-{{ \Illuminate\Support\Str::slug($r['agency_name'] ?? $r['agency_acro'] ?? '') }}/projects">{{ $r['agency_acro'] ?? $r['agency_key'] }}</a>
									@else
										{{ $r['agency_acro'] ?? $r['agency_key'] }}
									@endif
								</td>
								<td>{{ $r['type_category'] ?? '—' }}</td>
								<td>{{ $r['current_phase'] ?? 'Not published' }}</td>
								<td class="text-end">{{ $fmtM($r['planned_total_usd'] ?? null) }}</td>
								<td class="text-end">{{ $fmtM($r['commit_total_usd'] ?? null) }}</td>
								<td class="text-end">{{ $fmtM($r['spent_total_usd'] ?? null) }}</td>
								<td>{{ ($r['has_location'] ?? false) ? ($r['borough'] ?: 'Mapped') : 'Not published' }}</td>
							</tr>
						@empty
							<tr><td colspan="8" class="text-center text-muted py-4">{{ $pastEnd ? 'There is no page ' . $fmtN($page) . '.' : 'No project matches these filters.' }} @if($pastEnd)<a href="{{ $pageUrl(1) }}">Go to the first page</a>@endif</td></tr>
						@endforelse
						</tbody>
					</table>
				</div>

				{{-- ================= PAGINATION =================
				     ⚠⚠ A DISABLED CONTROL RENDERS A `<span>`, NEVER AN `<a>` (#321).
				     The old markup put `disabled` on the `<li>` and left a live href
				     on the `<a>` inside it; a CSS class never stopped a crawler, so
				     "Previous" from page 1 linked to page 0, from 0 to -1, downward
				     with no floor — 453 requests carrying a negative page in one
				     10-minute window, and a 1.2 GB cache. The controller floors and
				     casts as well; one half alone is useless. --}}
				@if($pages > 1)
				<nav aria-label="Project list pages" class="mt-3">
					<ul class="pagination pagination-sm">
						@if($page > 1)
							<li class="page-item"><a class="page-link" href="{{ $pageUrl($page - 1) }}">Previous</a></li>
						@else
							<li class="page-item disabled"><span class="page-link">Previous</span></li>
						@endif
						<li class="page-item disabled"><span class="page-link">Page {{ $fmtN($page) }} of {{ $fmtN($pages) }}</span></li>
						@if($page < $pages)
							<li class="page-item"><a class="page-link" href="{{ $pageUrl($page + 1) }}">Next</a></li>
						@else
							<li class="page-item disabled"><span class="page-link">Next</span></li>
						@endif
					</ul>
				</nav>
				@endif

				@endif {{-- $clOk --}}

				<div class="row my-4">
					{{-- ⚠ ONE SHELL, from `<x-db.data-provenance>`. Fifteen views hand-rolled this
					     accordion and thirteen also hand-rolled `loadTableStat()`, which
					     fetched a route that has never existed and then DELETED the rows it
					     had just rendered. --}}
					<div class="col-12">
						<x-db.data-provenance :datasets="$datasets" :count="$dsCount" :records="$dsRecords" />
					</div>
					</div>
				</div>
			</div>
		</div>

	</div>

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<script src="https://typeahead.js.org/releases/latest/typeahead.bundle.js"></script>

	<script>
		// ⚠⚠ THE MAP'S URL IS BUILT BY THE CONTROLLER FROM THE SAME ARRAY THE LIST
		// REQUEST USED. The page never assembles its own filter string — that is
		// the second computation that let the map and the table disagree.
		var CAP_GEOJSON_URL = '{!! $capGeojsonUrl !!}';

		// Colour by the five standard phases the Dashboard publishes. Everything
		// else it emits is a parenthesised status meaning "no schedule required",
		// so it shares one neutral colour rather than being drawn as a phase.
		const CAP_PHASE_COLORS = {
			'pre-design': '#ff7c7c',
			'design': '#78c0a8',
			'construction procurement': '#beedb9',
			'construction': '#36c726',
			'close-out': '#f2c45a'
		};

		function capPhaseColor(phase) {
			if (!phase) return '#53777a';
			return CAP_PHASE_COLORS[String(phase).trim().toLowerCase()] || '#53777a';
		}

		function getBounds(coords, bounds) {		// recursively walks over multilevel object calculating leaves-points coords
			if (typeof coords[0][0] == 'object')
				return coords.reduce(function (bounds, subcoords) {
						return getBounds(subcoords, bounds)
					},
					bounds
				)
			else {
				return coords.reduce(function (bounds, coord) {
							return bounds.extend(coord);
						}, (typeof bounds == 'undefined') ? new mapboxgl.LngLatBounds(coords[0], coords[0]) : bounds
					);
			}
		}

		function addrSearchPopover(msg) {
			$('#searchBtn').attr('data-content', msg)
			$('#searchBtn').popover('show')
			setTimeout(function(){
				$('#searchBtn').popover('hide')
			}, 2000);
		}

		function mapPopup(e) {
			var obj = e.features[0].properties;
			var pid = (obj.agency_key || '') + (obj.fms_id || '');
			var desc = obj.description || pid;
			var money = (obj.planned_usd === null || obj.planned_usd === undefined || obj.planned_usd === '')
				? 'Not published' : toFinShortK(parseFloat(obj.planned_usd) / 1000, 1);
			var description = `<table><tbody>
				<tr><th scope="row">Project</th><td><a href="/p/${encodeURIComponent(pid)}_${slug(desc)}">${desc}</a></td></tr>
				<tr><th scope="row">Agency</th><td>${obj.agency || ''}</td></tr>
				<tr><th scope="row">Category</th><td>${obj.category || 'Not published'}</td></tr>
				<tr><th scope="row">Phase</th><td>${obj.phase || 'Not published'}</td></tr>
				<tr><th scope="row">Planned commitments</th><td>${money}</td></tr>
				<tr><th scope="row">Pin</th><td>${obj.geometry_kind === 'polygon' ? 'Centroid of the published outline, not an address' : 'Published point'}</td></tr>
			</tbody></table>`;

			var W = parseFloat(obj.W), S = parseFloat(obj.S), E = parseFloat(obj.E), N = parseFloat(obj.N);
			if ([W, S, E, N].every(Number.isFinite) && (W || S || E || N)) {
				map.fitBounds([[W, S], [E, N]], {
					padding: [50, 50], maxZoom: 16, duration: 1000, animate: true, essential: true,
				});
			} else {
				map.easeTo({
					center: e.lngLat, zoom: Math.max(map.getZoom(), 14), duration: 1000, essential: true,
				});
			}

			if (popup)
				popup.remove();

			popup = new mapboxgl.Popup()
				.setLngLat(e.lngLat)
				.setHTML(description)
				.addTo(map);
			initPopovers();
		}


		function addrSearchKeyPress() {
			if(event.key === 'Enter') {
				addrSearch();
			}
		}

		function addrSearch() {
			var addr = $('#addrSearch').val()
			if (!addr || (addr.length < 6)) {
				addrSearchPopover('Please enter valid address')
				return
			}

			$.ajax({
				url: 'https://api.nyc.gov/geo/geoclient/v1/search.json',
				data: {input: addr},
				headers: {'Ocp-Apim-Subscription-Key': '{{ config('apis.geoclient_key') }}'},
				success: function (dd) {
					if (dd.status != 'OK') {
						addrSearchPopover('Not found, please try again')
						return
					}
					r = dd.results[0].response
					var addr = `${r.houseNumber} ${r.firstStreetNameNormalized}, ${r.uspsPreferredCityName}`.replace('  ', ' ').replace(' ,', '')
					var description = `
						<h4 style="font-size:18px;">${addr}</h4>
						<table><tbody>
							<tr><th scope="row">Community District</th>
								<td>
									<a href="/d/cd-${r.communityDistrict}-community-district-${r.communityDistrict}/city-council-discretionary">${r.communityDistrict}</a>
								</td>
							</tr>
							<tr><th scope="row">City Council District</th>
								<td>
									<a href="/d/cc-${r.cityCouncilDistrict.replace(/^0+/g, '')}-city-council-district-${r.cityCouncilDistrict.replace(/^0+/g, '')}/city-council-discretionary">${r.cityCouncilDistrict}</a>
								</td>
							</tr>
							<tr><th scope="row">School District</th>
								<td>
									<a href="/d/sd-${r.communitySchoolDistrict}-community-school-district-${r.communitySchoolDistrict}/schools">${r.communitySchoolDistrict}</a>
								</td>
							</tr>
							<tr><th scope="row">Zip Code</th><td>${r.zipCode}</td></tr>
							<tr><th scope="row">Election District</th><td>${r.electionDistrict}</td></tr>
							<tr><th scope="row">State Assembly District</th><td>${r.assemblyDistrict}</td></tr>
							<tr><th scope="row">State Senate District</th><td>${r.stateSenatorialDistrict}</td></tr>
							<tr><th scope="row">Congressional District</th><td>${r.congressionalDistrict}</td></tr>
							<tr><th scope="row">Police Precinct</th><td>${r.policePrecinct}</td></tr>
							<tr><th scope="row">Sanitation District</th><td>${r.sanitationDistrict}</td></tr>
							<tr><th scope="row">Fire Battilion</th><td>${r.fireBattalion}</td></tr>
							<tr><th scope="row">Health Center District</th><td>${r.healthCenterDistrict}</td></tr>
						</tbody></table>`

					map.fitBounds([
						[r.longitude - 0.002,r.latitude - 0.0005],
						[r.longitude + 0.002,r.latitude + 0.0035]
					], {
						padding: [50, 50], maxZoom: 15, duration: 1500, animate: true, essential: true,
					})

					if (popup)
						popup.remove()

					popup = new mapboxgl.Popup()
						.setLngLat([r.longitude,r.latitude])
						.setHTML(description)
						.addTo(map)

				}
			});
		}

		// ⚠⚠ THE FETCH AND THE MAP'S STYLE LOAD ARE A RACE, AND THE OLD PAGE HID
		// IT BEHIND ITS OWN SLOWNESS. `projectsMapInit()` adds the `route` source
		// inside mapbox's `load` event; `drawCapitalMap()` calls
		// `projectsMapDrawFeatures`, which does `map.getSource('route').setData`.
		// The old page fetched 13.7 MB, so the style always won and the race was
		// invisible. A 1.68 MB centroid payload — or a filtered one of 12 kB —
		// can arrive FIRST, and then `getSource('route')` is undefined,
		// `setData` throws inside the AJAX success handler, and the map stays
		// empty for ever. Caught headless on the first run, where the style
		// loads slowest; the in-app browser pane cannot composite Mapbox at all,
		// so there it would have read as "the map is broken" with no cause.
		//
		// So: hold whatever arrives first and draw when BOTH are ready.
		var CAP_PENDING_FEATURES = null;
		var CAP_MAP_READY = false;

		function capDrawWhenReady(features) {
			if (features) CAP_PENDING_FEATURES = features;
			if (!CAP_MAP_READY || CAP_PENDING_FEATURES === null) return;
			var ff = CAP_PENDING_FEATURES;
			CAP_PENDING_FEATURES = null;
			projectsMapDrawFeatures(ff, true);
			window.CAP_MAP_FEATURES = ff.length;
		}

		$(document).ready(function() {
			projectsMapInit();
			// `load` may already have fired by the time this binds; `loaded()`
			// covers that, and mapbox no-ops a late `on('load')` handler.
			if (typeof map !== 'undefined') {
				if (map.loaded && map.loaded()) { CAP_MAP_READY = true; capDrawWhenReady(null); }
				map.on('load', function () { CAP_MAP_READY = true; capDrawWhenReady(null); });
			}
			setTimeout(function(){
					$('#cd-switch').click();
				}, 2500);
			drawCapitalMap();

			// Boundary overlay control (.db-map-control) — open/close, aria sync,
			// outside-click close. Lifted from /districts so both maps behave the
			// same way; it replaces the old combined "Search & Layers" flyout.
			var boundariesControl = document.getElementById('boundaries-control');
			var boundariesToggle = document.getElementById('boundaries-toggle');
			if (boundariesControl && boundariesToggle) {
				boundariesToggle.addEventListener('click', function (e) {
					e.stopPropagation();
					var open = boundariesControl.classList.toggle('is-open');
					boundariesToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
				});
				document.addEventListener('click', function (e) {
					if (!e.target.closest || !e.target.closest('#boundaries-control')) {
						boundariesControl.classList.remove('is-open');
						boundariesToggle.setAttribute('aria-expanded', 'false');
					}
				});
			}

			$('.dropdown-menu').click(function (e) {
				e.stopPropagation();
			});

			// addr search autocomplete
			var autocomplete = new Bloodhound({
			  datumTokenizer: Bloodhound.tokenizers.whitespace,
			  queryTokenizer: Bloodhound.tokenizers.whitespace,
			  remote: {
				url: 'https://geosearch.planninglabs.nyc/v2/autocomplete?text=%QUERY',
				wildcard: '%QUERY',
				transform: function (resp) {
				  var rr = []
				  resp.features.forEach(function (f) {
					  rr.push(f['properties']['label'].replace('NY, ', ''))
				  })
				  return rr
				}
			  }
			});
			$('#addrSearch').typeahead(null, {
			  name: 'autocomplete',
			  limit: 16,
			  source: autocomplete
			});
			autocomplete.clearPrefetchCache();
			autocomplete.initialize(true);
		})


		/**
		 * Draw the centroids for THIS page's filters.
		 *
		 * ⚠ Centroids, not footprints: the published outlines are ~20 MB citywide
		 * and the largest single one is 618 kB. A project's real outline is
		 * fetched one at a time on its own page.
		 */
		function drawCapitalMap() {
			$('#mapLoadingOverlay').css('display', 'flex');
			$.ajax({
				url: CAP_GEOJSON_URL,
				dataType: 'json',
				success: function (fc) {
					var features = (fc && fc.features) ? fc.features : [];
					features.forEach(function (ft) {
						var c = ft.geometry && ft.geometry.coordinates;
						if (!ft.properties) ft.properties = {};
						// The shared draw helper reads W/S/E/N to fit the view; a
						// centroid is its own bounding box.
						if (c && c.length === 2) {
							ft.properties.W = ft.properties.E = parseFloat(c[0]);
							ft.properties.S = ft.properties.N = parseFloat(c[1]);
						}
						ft.properties.custom_color = capPhaseColor(ft.properties.phase);
					});

					// ⚠ The note is the SERVED sentence, printed as it came. It
					// carries the denominator for the filters actually applied.
					var cov = (fc && fc.coverage) ? fc.coverage : null;
					$('#mapCoverageNote').text(cov && cov.note ? cov.note
						: 'Location coverage is not available right now.');
					$('#mapLegend').show();

					window.CAP_MAP_COVERAGE = cov;
					capDrawWhenReady(features);
				},
				error: function () {
					// ⚠ A FAILED REQUEST IS NOT AN EMPTY MAP. Saying nothing here
					// would render zero pins and read as "no project has a location".
					$('#mapCoverageNote').text('Project locations could not be loaded. This is a problem with this page, not a statement about the capital programme.');
					window.CAP_MAP_FEATURES = null;
				},
				complete: function () {
					$('#mapLoadingOverlay').hide();
					window.CAP_MAP_DONE = true;
				}
			});
		}
	</script>


	{{-- ⚠⚠ THE WHOLE BLOCK IS GONE, MARKUP AND SCRIPT TOGETHER. It held a
	     DataTable init over a JS mirror of `$datasets`, plus `loadTableStat()`,
	     which fetched `/get/pstats-records_no/{table}` — a route that has never
	     existed in this repo's history — and on the 404 ran `datasets.splice(i,1)`
	     + `row(i).remove()`, so six failed lookups deleted six real rows and the
	     table read "No data available in table". `<x-db.data-provenance>` renders
	     those rows server-side, so there is nothing to hydrate and nothing that
	     can splice a row away because a request failed. --}}
	{{-- Actual Capital Spending by Fiscal Year — moved here with the tiles.
	     ⚠ Chart.js is loaded PER PAGE (procurement does the same). `DBChart`
	     comes from the layout and is global, but `Chart` is NOT — measured:
	     `typeof Chart` was `undefined` on this page — and `DBChart.apply(Chart)`
	     needs it, so the canvas would have stayed blank with no error.
	     ⚠ The canvas must stay inside its fixed-height `.db-chart-body`: a
	     `maintainAspectRatio:false` chart in an unsized box grows without bound
	     (#61). --}}
	@if(!empty($capitalSpend['values']))
	<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
	<script>
		(function () {
			if (typeof Chart === 'undefined' || typeof DBChart === 'undefined') return;
			DBChart.apply(Chart);
			var capEl = document.getElementById('capitalSpendChart');
			if (!capEl) return;
			var money = DBChart.money;
			new Chart(capEl, {
				type: 'bar',
				data: {
					labels: {!! json_encode($capitalSpend['labels'] ?? []) !!},
					datasets: [{
						label: 'Capital Spending',
						data: {!! json_encode($capitalSpend['values'] ?? []) !!},
						backgroundColor: DBChart.navy, borderRadius: 4
					}]
				},
				options: {
					responsive: true, maintainAspectRatio: false,
					plugins: { legend: { display: false } },
					scales: {
						y: { beginAtZero: true, grid: { color: DBChart.grid }, ticks: { callback: money } },
						x: { grid: { display: false } }
					}
				}
			});
		})();
	</script>
	@endif

@endsection
