@extends('layout')

@section('head')
	<meta name="description" content="{{ $snippet }}" />
	<meta rel="canonical" href="{!! $canonicalUrl !!}" />
@endsection

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')

@php
	// ⚠⚠ THE PAGE COMPUTES NOTHING IT IS SERVED. Every figure, every definition
	// and every "not published" sentence below is a key the endpoint returned.
	// Two independent computations of one number is the defect this section is
	// being rebuilt to end.
	$hdr   = $cap['header'] ?? [];
	$pres  = $cap['presence'] ?? [];
	$kf    = $cap['key_facts'] ?? [];
	$money = $cap['money'] ?? [];
	$sched = $cap['schedule'] ?? [];
	$hist  = $cap['history'] ?? [];
	$hbs   = $cap['history_by_source'] ?? [];
	$comm  = $cap['commitments'] ?? [];
	$dist  = $cap['districts'] ?? [];
	$geo   = $cap['geometry'] ?? [];
	$parks = $cap['parks_tracker'] ?? [];
	$clim  = $cap['climate'] ?? [];
	$miles = $cap['milestones_2023'] ?? [];
	$rel   = $cap['related'] ?? [];
	$sameLine = $rel['same_budget_line'] ?? [];
	$awards   = $rel['council_awards'] ?? [];
	$srcs  = $cap['sources'] ?? [];
	$slip    = $cap['slippage'] ?? [];
	$cov     = $cap['source_coverage'] ?? [];
	// ⚠ Ordered present-first so the table leads with what this project HAS,
	// while still accounting for every source — sorting is presentation, and it
	// never drops a row.
	$covRows = $cov['rows'] ?? [];
	usort($covRows, function ($a, $b) {
		return ($b['present'] <=> $a['present']) ?: ($a['retired'] <=> $b['retired']);
	});

	$name = $hdr['description'] ?: $canonId;

	$fmtM = function ($v) {
		// ⚠ `null` is "the City publishes no such figure" and `0` is a published
		// zero. Rendering both as "$0" would turn an absence into a claim.
		if ($v === null || $v === '' || !is_numeric($v)) return 'Not published';
		$v = (float) $v;
		if (abs($v) >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
		if (abs($v) >= 1000000) return '$' . number_format($v / 1000000, 1) . 'M';
		return '$' . number_format($v);
	};
	$txt = function ($v) { return ($v === null || $v === '') ? '—' : $v; };

	// ⚠⚠ THE ORG SHELL IS GONE, AND WHAT REPLACES IT IS TWO VALUES, NOT A
	// COMPONENT. `sub.orgheader` emitted a SECOND `<h1>` (the agency's) plus
	// 380px of tab navigation for a different entity — About · Notices · Work ·
	// People — none of which is about this project. Its NYCHA dropdown override
	// and its "Also known as" line are both about an ORG page and do not apply
	// here; `Breadcrumbs::orgPrj(...)` is what actually carries the org context
	// on this page and it is unchanged.
	//
	// ⚠ For the 4,568 projects carrying no `wegov_org_id` the controller passes
	// `$org = null`, and this degrades to the agency's name with no link —
	// never to a broken link or an empty line.
	$orgDisp = $org ? (($org['display_name'] ?? null) ?: ($org['name'] ?? '')) : null;
	$orgUrl  = ($org && !empty($org['id']))
		? route('orgProfile', ['id' => $org['id'], 'orgslug' => \Illuminate\Support\Str::slug($orgDisp)])
		: null;
	$parentName = $org ? trim((string) ($org['parent_name'] ?? '')) : '';
	// ⚠ A `Classification`/`Official` parent has no profile page of its own —
	// the org header has always rendered those as plain text, and linking them
	// would send a reader to a 404.
	$parentUrl = ($org && !empty($org['parent_id']) && $parentName !== ''
		&& !preg_match('~Classification|Official~si', $org['parent_type'] ?? ''))
		? route('orgProfile', ['id' => $org['parent_id'], 'orgslug' => $org['parent_id']])
		: null;

	// ⚠ PRECOMPUTED — a Blade directive glued to a word character is not
	// compiled and 500s the page.
	//
	// ⚠⚠ ONE MEANING PER BADGE VARIANT. `db-badge-neutral` was carrying four
	// different meanings on this page — presence, a retired-series warning, a
	// grain caveat and a district id — so the strongest signal on the page
	// (a figure from a series NYC retired in 2023) looked exactly like the
	// weakest. Here `neutral` means PRESENCE and nothing else; the retired
	// warning is `warning`, the grain caveat is `info`, districts are links.
	$badges = [];
	if (!empty($pres['in_current_plan'])) $badges[] = 'In the current plan';
	else $badges[] = 'Not in the current plan';
	if (!empty($sched['available'])) $badges[] = 'Schedule published';
	if (!empty($geo['available'])) $badges[] = 'Location published';

	$subLine = array_filter([
		$canonId,
		$hdr['agency_name'] ?: $hdr['agency_acro'],
		$hdr['type_category'] ?? null,
		$hdr['borough'] ?? null,
	]);

	// ⚠⚠ "COMMUNITY BOARD" IS THE WRONG LABEL FOR MOST OF THIS COLUMN, and the
	// split is measured: of the 8,373 projects where the City publishes a value,
	// **3,110 carry a district number** ("Brooklyn 01") and **5,263 name only a
	// borough** ("Brooklyn", "Citywide"). Calling the second kind a community
	// board tells a reader the City located the project more precisely than it
	// did — on 63% of the rows that have any value at all.
	//
	// ⚠ The QUALIFIER is now a short parenthetical with the full sentence in a
	// `title`, not a 14-word clause inside a table cell. The property is
	// unchanged — a borough-only value must never read as a community district.
	$cb = trim((string) ($hdr['community_board'] ?? ''));
	$cbHasDistrict = $cb !== '' && preg_match('/[0-9]/', $cb) === 1;
	$cbNote = 'The City publishes no community district for this project — only the borough.';

	// ⚠ One label per stored method, and an unknown key falls back to itself
	// rather than being dropped — a placement we cannot name is still a
	// placement, and silently omitting it would overstate the ones we can name.
	$placeLabels = [
		'geometry' => 'the location the City publishes for it',
		'community_board_text' => 'the community district named in its record',
	];
	// ⚠ Computed HERE rather than beside the map, because the placement sentence
	// below needs it and the map block is 250 lines further down.
	$hasGeom = (bool) ($geo['available'] ?? false);
	$methods = array_values(array_unique(array_column($dist['rows'] ?? [], 'method')));
	$placedNames = implode(' and ', array_map(
		function ($m) use ($placeLabels) { return $placeLabels[$m] ?? $m; }, $methods));
	// ⚠⚠ ONE SENTENCE, NOT THREE (owner, 2026-09-10). The page carried the same
	// fact three times in two columns: the map said "The City publishes no
	// location for this project. The districts it is recorded in are highlighted
	// above", the placement line said how it was placed, and a third line said a
	// council, school or neighborhood district can only be derived from a
	// location. The first and third are the SAME fact, and the third is implied
	// by "placed by the community district named in its record" once the empty
	// rows are gone. So: no location, what the map is showing, and how it was
	// placed — in one clause each.
	$placedLine = !$methods ? ''
		: ($hasGeom
			? 'Placed by ' . $placedNames . '.'
			: 'The City publishes no location for this project — it is placed by '
			  . $placedNames . ', highlighted on the map.');

	// ⚠⚠ ONE ROW PER BOUNDARY SET, ALWAYS ALL FOUR — the owner's decision, and
	// the shape map.databook.nyc's own "Overlapping Boundaries" panel uses
	// (type on the left, count on the right, opening to the members).
	//
	// ⚠⚠ AND A COUNT OF ZERO IS NOT THE SAME CLAIM AS AN UNANSWERABLE ONE.
	// `count === null` means the api could not ask: council, school and
	// neighborhood districts can ONLY be derived from a published location, so
	// on the 5,333 projects with none, "No districts identified" would assert
	// the City placed this project in no school district. It did not — it is in
	// one, and nothing we hold says which. `count === 0` is a real finding and
	// happens on 20 / 19 / 21 / 1 projects that DO have geometry and fall
	// outside a boundary set. Both measured 2026-09-10; invariant 20 on a new
	// surface.
	//
	// ⚠ A fallback for an api that predates `groups`, so a stale payload renders
	// the four rows as unknown rather than throwing an undefined index.
	$distGroups = $dist['groups'] ?? array_map(function ($t) {
		return ['dist_type' => $t, 'count' => null, 'dists' => []];
	}, \App\Custom\DistrictName::TYPES);
	// ⚠⚠ ONLY THE SETS THIS PROJECT IS ACTUALLY IN ARE RENDERED (owner,
	// 2026-09-10), which REVERSES the earlier decision that a type with nothing
	// shows a line rather than being omitted. The reasoning that made that
	// decision right has not gone away — an omitted row and an empty one are
	// indistinguishable — it has MOVED into the sentence below the table, which
	// states there is no published location and therefore only one kind of
	// placement. Three rows reading "Not determinable" said the same thing three
	// times and buried the one row that carried data.
	// ⚠ The PAYLOAD still answers for all four, including the null/zero
	// distinction; this is a rendering choice, so nothing measured is lost.
	$distGroups = array_values(array_filter($distGroups, function ($g) {
		return !empty($g['count']);
	}));

	// ⚠⚠ HIDING EMPTY SECTIONS REVERSES §5.3 ("every empty section renders its
	// 'not published' line, not nothing"), AND IT IS ONLY SAFE BECAUSE THE
	// SOURCE TABLE BELOW ACCOUNTS FOR EVERY SOURCE. The original rule existed
	// because an absent section and an empty one are indistinguishable, and here
	// the absence is often the finding. That information does not disappear — it
	// moves to one place.
	//
	// ⚠⚠ AND THE NAMING MOVED TO THE TOP, WHICH IS WHY THIS IS A PRECOMPUTED MAP
	// RATHER THAN THE `$show()` CLOSURE IT REPLACES. That closure appended to
	// `$hidden` as each section rendered, so the list could only be printed
	// AFTER the last section — 9,000px below the fold. A reader who needs to
	// know what is missing needs it before they start reading, not after.
	// ⚠⚠ `Scope` IS NO LONGER HERE, and that is not an omission. It became a
	// FIELD in the About table (owner, 2026-09-10), and a field is not a
	// section: an absent one renders an em dash in its own row, the way every
	// other attribute does, so there is nothing to hide and nothing to name.
	// Leaving it in this map would have put "Scope" in the "Nothing published
	// for:" sentence for every project the 2023 series never carried — naming a
	// missing SECTION that no longer exists.
	$sections = [
		'Schedule' => !empty($sched['available']),
		'How the completion forecast has moved' => !empty($slip['available']),
		'Milestones (2023)' => !empty($miles['available']),
		'NYC Parks project tracker' => !empty($parks['available']),
		'Budget and schedule over time' => !empty($hbs['available']),
		'Climate Budgeting ratings' => !empty($clim['available']),
		'Districts' => !empty($dist['available']),
		'Planned commitments' => !empty($comm['available']),
		'Other projects on the same budget line' => !empty($sameLine['available']),
		'City Council capital awards' => !empty($awards['available']),
	];
	$hidden = array_keys(array_filter($sections, function ($ok) { return !$ok; }));
	// ⚠⚠ THE TWO LISTS OVERLAP, AND UNSUBTRACTED THEY PRINT THE SAME NAMES TWICE
	// IN ONE SENTENCE. `sources_absent` names PUBLICATIONS the City does not
	// carry this project in; `$hidden` names SECTIONS with nothing to render.
	// Where a section is fed by exactly one publication the two are the same
	// words, so the strip read: "Not published in: NYC Parks project tracker,
	// City Council capital awards. Nothing published for: NYC Parks project
	// tracker, City Council capital awards." Both halves were correct and the
	// sentence was still wrong.
	// ⚠ SUBTRACTED, NOT MERGED: the publication list is the stronger statement
	// (it is about the SOURCE, and the sources table below elaborates it), so it
	// wins, and `$hiddenOnly` carries whatever is left — the sections with no
	// one-to-one publication, which would otherwise go unnamed. Neither list may
	// simply be dropped; that is the §5.3 defect returning.
	$hiddenOnly = array_values(array_diff($hidden, $kf['sources_absent'] ?? []));

	// ⚠⚠ THE TOC IS DERIVED FROM `$sections`, NOT A SECOND LIST. Two independent
	// lists of the same sections is how a menu comes to name a section that is
	// not there — and this page HIDES a section when the City publishes nothing
	// for it, so a hand-typed TOC would link to an anchor that does not exist on
	// exactly the projects where the absence is the finding. `null` means the
	// section always renders; a string is the `$sections` key that gates it.
	$toc = [];
	foreach ([
		['about', 'About this project', null],
		['where', "What districts it's in", 'Districts'],
		['schedule', 'Schedule', 'Schedule'],
		['slippage', 'Forecast movement', 'How the completion forecast has moved'],
		['history', 'Budget history', 'Budget and schedule over time'],
		['milestones', 'Milestones (2023)', 'Milestones (2023)'],
		['parks', 'Parks tracker', 'NYC Parks project tracker'],
		['climate', 'Climate ratings', 'Climate Budgeting ratings'],
		['commitments', 'Planned commitments', 'Planned commitments'],
		['sameline', 'Same budget line', 'Other projects on the same budget line'],
		['awards', 'Council awards', 'City Council capital awards'],
		['sources', 'Where figures come from', null],
	] as $t) {
		if ($t[2] === null || !empty($sections[$t[2]])) $toc[] = $t;
	}

	$variance = $sched['variance_days'] ?? null;
	$varianceLine = is_numeric($variance)
		? (((int) $variance) > 0
			? number_format((int) $variance) . ' days later than first forecast'
			: number_format(abs((int) $variance)) . ' days earlier than first forecast')
		: null;
	// ⚠ The sub-line under Forecast completion. Both halves are the endpoint's;
	// this only joins them into a phrase.
	$slipLine = ($kf['slip_months'] ?? null) !== null
		? abs($kf['slip_months']) . ' months ' . $kf['slip_direction'] . ' than first forecast'
		: null;

	// ⚠⚠ PHASE AND FORECAST ARE HEADER FACTS, NOT TILES (owner, 2026-09-10).
	// They were two `is-text` tiles in a grid of otherwise-money tiles, which
	// made the strip answer two different questions in one row and cost the six
	// money measures the space they needed. They are properties of the PROJECT,
	// like its agency and its borough, so they belong with those in the header.
	// ⚠ PRECOMPUTED, because a Blade directive glued to a word character is not
	// compiled and 500s the page — the trap this file already records.
	// ⚠ `null` is "the City publishes no schedule for this project", rendered as
	// a sentence. Never a blank, and never a zero.
	// ⚠ The Scope field's citation, on its info icon. Precomputed because it is
	// used twice on one element (`title` and `aria-label`) and a Blade directive
	// glued to a word character is not compiled.
	$scopeCite = 'As published in the 2023 project detail series, which NYC retired on 26 October 2023.';
	$phaseText    = $kf['current_phase'] ?? 'No schedule published';
	$forecastText = $kf['forecast_completion_label'] ?? 'Not published';

	// ⚠⚠ ALL SIX MEASURES, AND THERE IS NOWHERE ELSE THEY LIVE. The strip used to
	// show four with a Money section further down carrying all six; the owner
	// folded that section into the strip (2026-09-10), so these tiles ARE the
	// ⚑ F set. `_STRIP_MONEY` is derived from `capitalmoney.MEASURES` in the
	// router, so "every measure" is true by construction rather than by two
	// lists agreeing — and the order is the publisher-canonical one the
	// definitions under the tiles are listed in, so a tile and its definition
	// cannot fall out of step.
	// ⚠ ⚑ F IS UNCHANGED BY THE MOVE: six measures, six populations, never
	// merged, never summed, never subtracted. Losing one to fit the row is the
	// one thing this may not do.
	$kfMoney = $kf['money'] ?? [];

	$anyPhaseDate = array_filter($sched['actual'] ?? []);
	$actualLabels = $sched['actual_labels'] ?? [];

	// ⚠ Column formatting only — this decides how to PRINT a served value, never
	// what the value is. A `_usd` column is money; everything else is text the
	// endpoint already formatted (periods and dates arrive as `*_label`).
	$histCell = function ($col, $row) use ($fmtM, $txt) {
		return substr($col, -4) === '_usd' ? $fmtM($row[$col] ?? null) : $txt($row[$col] ?? null);
	};
@endphp

	<div class="inner_container">
		<div class="container">

			{{-- ===================== HEADER ===================== --}}
			<div class="db-profile-kicker mt-4"><span class="db-type-label">Capital Project</span></div>
			{{-- ⚠ ONE `<h1>` PER PAGE, and it is the PROJECT's. The agency's used to
			     be emitted by `sub.orgheader` above it, so this page had two and a
			     screen reader's document outline named the wrong subject first.
			     ⚠ `.db-profile-title` sizes it at `--db-text-2xl` (30px) rather than
			     the 36px h1 default. The CASE IS NOT TRANSFORMED — `CSO`, `OH-015`
			     and `GI` are the City's own tokens and title-casing destroys them. --}}
			<h1 class="db-profile-title mb-1">{{ $name }}</h1>
			<p class="db-page-lead mb-1">{{ implode(' · ', $subLine) }}</p>
			<p class="small mb-2">
				@if($orgUrl)
					A <a href="{{ $orgUrl }}">{{ $orgDisp }}</a> project
				@elseif($orgDisp)
					A {{ $orgDisp }} project
				@else
					A {{ $hdr['agency_name'] ?: $hdr['agency_acro'] }} project
				@endif
				@if($parentUrl)
					· reports to <a href="{{ $parentUrl }}">{{ $parentName }}</a>
				@elseif($parentName !== '')
					· reports to {{ $parentName }}
				@endif
			</p>
			<p class="mb-1">
				@foreach($badges as $b)<span class="db-badge db-badge-neutral me-1">{{ $b }}</span>@endforeach
			</p>
			{{-- ⚠⚠ WHERE PHASE AND FORECAST COMPLETION LIVE NOW. They were tiles in
			     the key-facts strip; the strip is the six money measures alone, so a
			     grid of `$5.1M`-shaped values no longer has `Construction
			     Procurement` and a date sitting in it answering a different question.
			     ⚠ `.db-profile-meta` / `.db-meta-item` is the EXISTING header
			     component for exactly this — a muted label with the value in
			     `--db-text` — so this needs no new CSS and inherits the flex-wrap
			     that keeps a long phase name readable at 390px. A badge would have
			     been wrong: badges on this page mean PRESENCE and nothing else
			     (one meaning per variant), and these are values, not flags.
			     ⚠ The slip line travels WITH the forecast. Detached from the date it
			     is describing, "4 months later than first forecast" names no
			     subject. --}}
			<div class="db-profile-meta mb-3">
				<span class="db-meta-item"><i class="bi bi-signpost-split"></i>Phase <strong>{{ $phaseText }}</strong></span>
				<span class="db-meta-item">
					<i class="bi bi-calendar-event"></i>Forecast completion <strong>{{ $forecastText }}</strong>
					@if($slipLine)
						<span>&middot; {{ $slipLine }}</span>
					@endif
				</span>
			</div>

			{{-- ===================== KEY FACTS ===================== --}}
			{{-- ⚠ FULL WIDTH, NOT `col-md-7`. In a 7/12 column the six tiles wrapped to
			     two rows on an ordinary desktop (owner review, 2026-09-08); across the
			     container they sit on one. The map keeps its right-hand column in the
			     row BELOW, beside the attribute table. --}}
					{{-- ⚠⚠ THE FOUR QUESTIONS A READER ARRIVES WITH, ABOVE THE FOLD.
					     Before this, Money began at 1,216px and Schedule at 1,716px —
					     the entire first screen was chrome, and "how much, what phase,
					     when, is it late" were unanswered until the second. Every value
					     here is the endpoint's `key_facts` block, which runs no query
					     and computes no figure; it restates what `money`, `schedule`
					     and `slippage` already carry. --}}
					<x-db.stat-grid class="mb-2">
						@foreach($kfMoney as $m)
							<x-db.stat :label="$m['label']">{{ $fmtM($m['value']) }}</x-db.stat>
						@endforeach
					</x-db.stat-grid>

					{{-- ⚠⚠ ONE HELP BLOCK, DIRECTLY UNDER THE FIGURES IT IS ABOUT. The
					     not-a-funnel note and the publisher's definitions used to be two
					     things in the Money section, ~300px below the tiles that raised
					     the question. A reader who wonders whether adopted minus spent is
					     an amount outstanding wonders it AT THE TILES.
					     ⚠⚠ THE NOTE IS OUTSIDE THE `<details>`, AND THAT IS LOAD-BEARING
					     — invariant 6, and a guard enforces it. A sentence that stops a
					     reader misusing a number is not decoration, and a caveat behind a
					     disclosure triangle is a caveat nobody reads. The DEFINITIONS are
					     reference material and stay one click away: 130 words of them,
					     four differing by a single word and each repeating its publisher,
					     is what the disclosure exists for.
					     ⚠ `.db-note`'s left rule is what makes these one block rather than
					     two stacked paragraphs, and it deliberately does NOT mute the
					     text — muting a caveat is the defect the class was added for. --}}
					<div class="db-note mb-3">
						<details>
							{{-- ⚠⚠ THE SUMMARY CARRIES THE WARNING ITSELF, and that is what
							     keeps this honest. Invariant 6 says a caveat is never behind
							     a click, and the note WAS outside this disclosure for exactly
							     that reason — the owner asked for one show/hide holding all of
							     it (2026-09-10), so the load-bearing half is in the line a
							     reader sees WITHOUT opening anything. "Not stages of one pot"
							     is the sentence that stops someone subtracting spent from
							     adopted; it is visible, and the four sentences elaborating it
							     are one click away with the definitions.
							     ⚠ THE OTHER TWO CAVEATS ON THIS PAGE ARE UNCHANGED and stay
							     outside any disclosure — `awards.note` and
							     `coverage.retired_note`. The guard was narrowed to this one
							     measure's note, not switched off. --}}
							<summary class="small">How to read these six figures &mdash; they are not stages of one pot</summary>
							<p class="small mt-2 mb-2">{{ $money['note'] ?? '' }}</p>
							<p class="small mb-1"><strong>What each measure counts, in the publisher's words</strong></p>
							<dl class="small mt-2 mb-1">
								@foreach($money['measures'] ?? [] as $m)
									<dt>{{ $m['label'] }}</dt>
									<dd>{{ $m['definition'] }} <em>&mdash; {{ $m['source'] }}</em></dd>
								@endforeach
							</dl>
							@if(!empty($money['publisher_caveat']))
								<p class="small mb-0">{{ $money['publisher_caveat'] }} <em>&mdash; {{ $money['publisher_caveat_source'] ?? '' }}</em></p>
							@endif
						</details>
					</div>

			{{-- ===================== ABOUT + MONEY | MAP + WHERE ===================== --}}
			{{-- ⚠ LEFT: what the project IS and what it COSTS. RIGHT: where it is — the
			     map, and the districts beneath it, because they are one facet (location)
			     and were 3,000px apart. Both `h2`s here sit ABOVE the table of contents,
			     so the TOC's "About this project" entry scrolls back to the top. --}}
			@php
				// ⚠⚠ `$hasMap` MEANS "THIS PAGE RENDERS A MAP", not "the City
				// published geometry". Geometry exists for only 4,560 of 17,024
				// projects, but 8,373 carry a published district — so a boundary map
				// highlighting those districts is real published data, not
				// decoration, and it is what fills the right column that used to be
				// empty here.
				// ⚠ HONESTY: a highlighted COMMUNITY DISTRICT is not a point. This
				// project is placed by `community_board_text`, and the placement line
				// below says so per method; the map must not imply more precision
				// than the method carries.
				// ⚠ `$hasGeom` is set in the top @php block — the placement sentence
				// needs it there. Not reassigned here, so there is one owner.
				$distRows = $dist['rows'] ?? [];
				$hasMap = $hasGeom || !empty($distRows);
				// Only the four types the shared `filtFields` can filter on can be
				// highlighted; the rest still render as toggleable overlays.
				$mapHighlight = [];
				foreach ($distRows as $d) {
					$t = $d['dist_type'] ?? null;
					if (in_array($t, ['cd', 'cc', 'nta', 'sd'], true) && isset($d['dist']))
						$mapHighlight[$t][] = (string) $d['dist'];
				}
			@endphp
			{{-- ⚠⚠ THE LAYOUT DEPENDS ON WHETHER THERE IS A MAP, and that is the
			     owner-reported defect: with no map this row rendered a col-md-7 of
			     About beside a col-md-5 holding only a short districts block —
			     measured on /p/826HED-545 as 848px of content next to 848px of
			     mostly white space. Geometry exists for 4,560 of 17,024 projects,
			     so the map-less page is the COMMON case, not the exception.
			     With no map the TOC moves up here instead, so the page is two
			     honest columns from just under the stats down. --}}
			{{-- ⚠⚠ THE TOC IS NOT IN THIS ROW ANY MORE (owner, 2026-09-10). With no
			     map it used to render here as a `col-md-3`, so About was squeezed to
			     `col-md-9` on exactly the pages that had nothing to put in the right
			     column. About now takes the FULL WIDTH when there is no map and sits
			     LEFT OF THE MAP when there is one, and the table of contents starts
			     below this row in both cases — one slot, one condition, instead of
			     two slots and a spacer.
			     ⚠ The map's own reason for `col-md-5` is unchanged: these are real
			     footprints (the Gravesend Bay sewer network spans ~2.5km) and a
			     narrower column zooms a polygon to illegibility. --}}
			<div class="row mb-4 mt-3">
				<div class="{{ $hasMap ? 'col-md-7' : 'col-12 px-0 px-md-3' }}">
			{{-- ===================== ABOUT ===================== --}}
			<h2 id="about" class="db-anchor mt-0">About this project</h2>
			<div class="table-responsive">
				<table class="db-table table table-sm">
					<tbody>
						<tr><th scope="row" style="width:38%;">Managing agency</th><td>
							@if(!empty($hdr['wegov_org_id']))
								<a href="/o/{{ $hdr['wegov_org_id'] }}-{{ \Illuminate\Support\Str::slug($hdr['agency_name'] ?? $hdr['agency_acro'] ?? '') }}/projects">{{ $txt($hdr['agency_name'] ?: $hdr['agency_acro']) }}</a>
							@else
								{{ $txt($hdr['agency_name'] ?: $hdr['agency_acro']) }}
							@endif
						</td></tr>
						<tr><th scope="row">Sponsoring agency</th><td>{{ $txt($hdr['sponsor_agency'] ?? null) }}</td></tr>
						<tr><th scope="row">Asset category</th><td>{{ $txt($hdr['type_category'] ?? null) }}</td></tr>
						{{-- ⚠ LINKED, because this is the one facet whose page answers about
						     THIS project: `/projects/categories/{slug}` now lists the SPINE's
						     projects in the category (repointed 2026-09-08 — it listed 2 where
						     the spine has 268 for one real category). The slug is built the
						     way the endpoint matches it, on both sides. --}}
						<tr><th scope="row">Ten-Year Strategy category</th><td>
							@if(!empty($hdr['ten_year_category']))
								<a class="db-tap" href="{{ route('prjStratCategory', ['cslug' => \Illuminate\Support\Str::slug($hdr['ten_year_category'])]) }}">{{ $hdr['ten_year_category'] }}</a>
							@else — @endif
						</td></tr>
						{{-- ⚠⚠ LINKED NOW, AND TO ITS OWN DIMENSION — NOT TO `/projects/types`.
						     Measured 2026-09-08: this column is the distinct set of
						     **budget-line families** a project is funded through —
						     `{L-0101, L-D002, PU-0025}` → `{New York Research Library, EDP
						     Equipment and Finance Costs}`, the deduplicated prefix set
						     (`P`→Parks and Recreation, `HW`→Highways, `PW`→Public
						     Buildings). **39 values.** `/projects/types/{slug}` is keyed on
						     `capitalstrategy."Project Type Description"` — **236 values**,
						     the Ten-Year Strategy's WORK type — and the two share **5
						     names, every one a coincidence**. Linking there would have
						     404'd on 34 of 39 and misled on the rest.
						     ⭐ `/projects/budget-lines/families/{slug}` is that dimension's
						     own page, and it can list projects because the family is
						     project-level (12,929 rows, exactly the current plan) where the
						     strategy's work type has no project key at all. --}}
						<tr><th scope="row">Budget-line family</th><td>
							@if(count($hdr['project_types'] ?? []))
								@foreach($hdr['project_types'] as $ft)<a class="db-tap" href="{{ route('budgetLineFamily', ['fslug' => \Illuminate\Support\Str::slug($ft)]) }}">{{ $ft }}</a>@if(!$loop->last), @endif @endforeach
							@else — @endif
						</td></tr>
						<tr><th scope="row">Budget line</th><td>
							{{-- ⚠ MULTI-VALUED BECAUSE IT IS — 1 to 34 lines per project. --}}
							@if(count($hdr['budget_lines'] ?? []))
								@foreach($hdr['budget_lines'] as $bl)<a class="db-tap" href="{!! route('budgetLine', ['blcode' => $bl]) !!}">{{ $bl }}</a>@if(!$loop->last), @endif @endforeach
							@else — @endif
						</td></tr>
						{{-- ⚠⚠ SCOPE IS A FIELD, NOT A SECTION (owner, 2026-09-10). It was
						     an `<h3>` with a vintage line and a paragraph, sitting below the
						     table it belongs in — the only free-text attribute the City
						     publishes, formatted unlike every other attribute.
						     ⚠ THE VINTAGE DID NOT GO, IT MOVED TO THE ICON. This is the one
						     field on the page sourced from a series NYC RETIRED on
						     2023-10-26, so a reader who takes it as current is being
						     misled — the citation travels with the value rather than being
						     dropped to make the row tidy.
						     ⚠ `title` + `aria-label`, which is the pattern the community
						     district row one line below already uses; this page loads no
						     popover JS, and inventing a mechanism for one cell would be a
						     dependency for a tooltip. --}}
						<tr><th scope="row">Scope</th><td>
							@if(!empty($hdr['scope_2023']))
								{{ $hdr['scope_2023'] }}
								<i class="bi bi-info-circle db-muted ms-1" role="img" aria-label="{{ $scopeCite }}" title="{{ $scopeCite }}"></i>
							@else — @endif
						</td></tr>
						<tr><th scope="row">Community district</th><td>
							@if($cb === '')
								—
							@elseif($cbHasDistrict)
								{{ $cb }}
							@else
								{{ $cb }} <span class="db-muted small" title="{{ $cbNote }}">(borough only)</span>
							@endif
						</td></tr>
					</tbody>
				</table>
			</div>

			{{-- ⚠⚠ THERE IS NO "MONEY" SECTION ANY MORE, and this note is here so the
			     next reader does not rebuild it. Its six-row table restated the six
			     tiles in the key-facts strip at a second grain, ~300px lower; its
			     note and its definitions now sit in one help block directly under
			     those tiles, where the question is actually asked. ⚑ F is unchanged:
			     all six measures render, in the publisher's order, with the
			     publisher's own definition on each — see the strip above.
			     ⚠ The `#money` TOC entry went with it. A menu entry pointing at an
			     anchor the page no longer emits is the dead-link defect
			     `verify_toc.py` exists to catch, and it checks BOTH directions. --}}

				@if($hasMap)
				</div>
				<div class="col-md-5">
					{{-- ⚠⚠ THE MAP SITS HERE, TOP-RIGHT, matching the layout the previous
					     project page used (`orgproject.blade.php`: col-md-8 content +
					     col-md-4 map, line 269). `col-md-5` rather than 4 because these
					     are real footprints — the Gravesend Bay sewer network spans about
					     2.5km — and a narrower column zooms a polygon to illegibility.
					     ⚠⚠ THE `col-*` CLASS IS LOAD-BEARING, not a layout preference.
					     `style.css:1509` sets `#map_container { float: right }`, and a
					     floated block with no declared width shrinks to fit its in-flow
					     children; mapbox positions everything inside absolutely, so
					     without a width the container computes to 0px and the map is
					     invisible while every other check passes. That shipped once. --}}
				@endif
					@if($hasMap)
						<div class="row">
							<div id="map_container" class="col-12 mb-2 position-relative" style="min-height:300px;">
								<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;"></div>

								{{-- Boundary overlays, top-right — the same control /districts,
								     /projects and /schools carry.
								     ⚠ NO ADDRESS SEARCH HERE, deliberately: this map answers
								     "where is THIS project", and an address box invites a
								     question the page cannot answer.
								     ⚠ The switch IDs are load-bearing — `setBoundary()` binds
								     each layer by `#{code}-switch` and paints its colour into
								     that row's `<hr>`. --}}
								<div class="db-map-control" id="boundaries-control" style="top: var(--db-space-2); right: var(--db-space-2);">
									<button type="button" class="db-btn db-btn-outline db-btn-sm" id="boundaries-toggle" aria-haspopup="true" aria-expanded="false" style="background:#fff;">
										<i class="bi bi-bounding-box-circles"></i> Boundaries <i class="bi bi-chevron-down db-caret"></i>
									</button>
									<div class="db-map-control-menu" id="boundaries_controls">
										<p class="db-map-control-label">Overlay boundaries</p>
										@php
											$boundaryLayers = [
												'cd' => 'Community Districts', 'ed' => 'Election Districts',
												'pp' => 'Police Precincts', 'dsny' => 'Sanitation Districts',
												'fb' => 'Fire Battalions', 'sd' => 'School Districts',
												'hc' => 'Health Center Districts', 'cc' => 'City Council Districts',
												'nycongress' => 'Congressional Districts', 'sa' => 'State Assembly Districts',
												'ss' => 'State Senate Districts', 'bid' => 'Business Improvement Districts',
												'nta' => 'Neighborhood Tabulation Areas', 'zipcode' => 'Zip Code',
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
							{{-- ⚠ THE "no location" NOTE MOVED to the placement sentence under the
							     district table (owner, 2026-09-10) — it was the same fact said
							     twice, in two columns. What it was for is unchanged and still
							     said there: the reader sees highlighted districts and would
							     otherwise infer the City located the project inside them, when it
							     published a district and not a point. --}}
						</div>
						{{-- ⚠⚠ GATED ON GEOMETRY, BECAUSE THE ONLY THING THAT REPLACES THIS
						     TEXT IS. The AJAX that sets `#mapNote` sits inside `@if($hasGeom)`,
						     so on a project with no published location this rendered
						     "Loading the published outline…" FOREVER — a stuck loading state
						     on a page that had finished loading, reported by the owner. A
						     spinner that never resolves is invariant 7's fourth thing: it says
						     nothing at all, while looking like it is about to. --}}
						@if($hasGeom)
							<p class="text-muted small" id="mapNote">Loading the published outline&hellip;</p>
						@endif
					@endif
			{{-- ================ WHAT DISTRICTS IT'S IN ================ --}}
			{{-- ⚠ The MAP is in the top-right column; what remains here is the
			     districts the project falls in and how it was placed. --}}
			@if($sections['Districts'])
				<h2 id="where" class="db-anchor mt-3">What districts it's in</h2>
				{{-- ⚠⚠ THIS WAS A FLAT RUN OF BADGES WITH NO GROUPING — `/p/826HED-545`
				     rendered `CD 107  CD 108  CD 207  CD 208` and nothing else, so a
				     reader could not tell which boundary sets had been answered, which
				     had not, or what `CD` meant. One row per SET now, which is the
				     owner's decision and the shape map.databook.nyc's own "Overlapping
				     Boundaries" panel uses.
				     ⚠⚠ THE SINGLE-DISTRICT ROW IS THE DEFAULT, NOT THE FALLBACK — it is
				     the majority case on three of the four sets, measured over the whole
				     crosswalk: cc 4,001 of 4,527 · nta 3,786 of 4,526 · sd 4,067 of
				     4,528. Only `cd` is different, at 3,611 of 9,879 in more than one.
				     ⚠ The names are NOT invented and NOT parsed out of the id — see
				     App\Custom\DistrictName, which is the one owner and takes the
				     borough from a curated map rather than from the first digit. --}}
				<div class="table-responsive">
					<table class="db-table table table-sm mb-2">
						<tbody>
							@foreach($distGroups as $g)
								@php
									$t = $g['dist_type'];
									$n = $g['count'];
									$ids = $g['dists'] ?? [];
									$link = function ($id) use ($t) {
										return route('districtsPreset', ['type' => $t, 'id' => $id, 'dslug' => 'district', 'section' => 'projects']);
									};
								@endphp
								<tr>
									<th scope="row" style="width:38%;">{{ \App\Custom\DistrictName::PLURAL[$t] }}</th>
									<td>
										{{-- ⚠⚠ THE EMPTY AND UNANSWERABLE BRANCHES ARE GONE, NOT DISABLED.
										     `$distGroups` is filtered above, so `$n` is always >= 1 here
										     and a `$n === 0` arm would be unreachable — dead code that
										     reads as a live claim is worse than no code at all, which is
										     why this repo deletes rather than gates. The distinction the
										     two branches carried is still MEASURED in the payload and is
										     now said once, in the sentence below the table. --}}
										@if($n === 1)
											{{-- ⚠ ONE DISTRICT SHOWS ITS NAME, and the label is
											     byte-identical to the title of the page it links to. --}}
											<a class="db-tap" href="{{ $link($ids[0]) }}">{{ \App\Custom\DistrictName::label($t, $ids[0]) }}</a>
										@else
											{{-- ⚠⚠ EXPAND IN PLACE, NOT A MODAL. The largest real case is
											     **94 NTAs** on one project (850HWCRCDB, which also carries 46
											     community, 45 council and 30 school districts) — that is a
											     list, and a dialog sized for it is a worse list. A `<details>`
											     needs no new JS and no focus management, neither of which
											     this page has.
											     ⚠ This does NOT widen invariant 6. That rule governs
											     CAVEATS; a district list is data, and the one owner-granted
											     exception remains `money.note`. The caveat on this section
											     is the line BELOW the table, outside every disclosure. --}}
											<details>
												<summary class="db-tap">{{ \App\Custom\DistrictName::unit($t, $n) }}</summary>
												<ul class="list-unstyled mt-2 mb-1">
													@foreach($ids as $id)
														<li><a class="db-tap" href="{{ $link($id) }}">{{ \App\Custom\DistrictName::label($t, $id) }}</a></li>
													@endforeach
												</ul>
											</details>
										@endif
									</td>
								</tr>
							@endforeach
						</tbody>
					</table>
				</div>
				{{-- ⚠ HOW a project was placed is part of the claim: geometry is the
				     City's own published location, a community-board match is our
				     inference from a text field. Both are real; they are not equally
				     strong, so the page says which applies.
				     ⚠ And the METHOD IS TRANSLATED, not printed raw — this line
				     published the literal column value `community_board_text` to
				     readers. A stored key is storage; it is not copy. --}}
				<p class="db-note-small">{{ $placedLine }}</p>
			@endif

				</div>
			</div>

			{{-- ⚠ A COMPANION TO THE LENGTH FIXES, NOT ONE OF THEM. The page went
			     9,636px -> 4,988px at 1440 before this existed; a table of contents
			     over an 11-screen page would have been decoration on a problem. At
			     ~5.5 screens with up to 13 sections it is navigation.
			     ⚠ `col-md-3` + `col-md-9` is the convention the contract, vendor and
			     solicitation profiles already use — and it starts BELOW the about/map row,
			     so About, Money and the map are reachable without it and the TOC's own
			     first entries scroll UP to them. --}}
			<div class="row">
				<div class="col-md-3 d-none d-md-block">
					{{-- ⚠ ONE TOC PER PAGE, AND THIS IS NOW ITS ONLY SLOT. It used to be
					     included here OR beside the About row depending on `$hasMap`,
					     with whichever column lost out left behind as a grid spacer. One
					     unconditional include cannot render twice, and cannot leave an
					     empty column behind either. --}}
					@include('partials.capital_toc')
				</div>
				{{-- ⚠ `px-0 px-md-3`: the TOC is `d-none` below `md`, but the column
				     GUTTER is not — so adding the sidebar cost 312px of page height at
				     390px for a component that does not render there, by narrowing
				     every table and paragraph by 24px. Measured, not guessed: 9,184px
				     before the TOC, 9,496px after, 9,190px with the gutter dropped. --}}
				<div class="col-md-9 px-0 px-md-3">

			{{-- ===================== SCHEDULE ===================== --}}
			@if($sections['Schedule'])
				<h2 id="schedule" class="db-anchor mt-4">Schedule</h2>
				<div class="row">
					<div class="col-md-6">
						{{-- ⚠ EVERY DATE HERE IS THE SERVED `*_label`. The page carried TWO
						     date formats — `02/23/2030` in this table and the chart,
						     `26 Oct 2023` in the history — because the schedule printed the
						     raw value and the history printed a formatted one. There is one
						     formatter now and it lives at the endpoint (`_mdy_label`); a
						     second formatter in the view is how the two formats arrived. --}}
						<table class="db-table table table-sm"><tbody>
							<tr><th scope="row" style="width:45%;">Current phase</th><td>{{ $txt($sched['current_phase']) }}</td></tr>
							<tr><th scope="row">Phase started</th><td>{{ $txt($sched['phase_start_label']) }}</td></tr>
							<tr><th scope="row">Forecast phase end</th><td>{{ $txt($sched['forecast_phase_end_label']) }}</td></tr>
							<tr><th scope="row">Forecast completion</th><td>{{ $txt($sched['forecast_completion_label']) }}</td></tr>
							@if($varianceLine)
								<tr><th scope="row">Change against first forecast</th><td>{{ $varianceLine }}</td></tr>
							@endif
							<tr><th scope="row">Reason given</th><td>
								{{-- ⚠ 296 of 372 delayed rows carry a reason. A blank one means
								     NYC published none, and must never read as "no delay". --}}
								{{ $sched['delay_reason'] ?: 'The City published no reason.' }}
							</td></tr>
						</tbody></table>
					</div>
					<div class="col-md-6">
						<h3 class="db-text-base">Dates the City reports as actual</h3>
						@if(count($anyPhaseDate))
							<table class="db-table table table-sm"><tbody>
								<tr><th scope="row" style="width:45%;">Design</th><td>{{ $txt($actualLabels['design_start'] ?? null) }} – {{ $txt($actualLabels['design_end'] ?? null) }}</td></tr>
								<tr><th scope="row">Procurement</th><td>{{ $txt($actualLabels['procurement_start'] ?? null) }} – {{ $txt($actualLabels['procurement_end'] ?? null) }}</td></tr>
								<tr><th scope="row">Construction</th><td>{{ $txt($actualLabels['construction_start'] ?? null) }} – {{ $txt($actualLabels['construction_end'] ?? null) }}</td></tr>
							</tbody></table>
						@else
							<p class="db-note-small">No phase has a published actual date.</p>
						@endif
					</div>
				</div>
			@endif

			{{-- ===================== FORECAST SLIPPAGE ===================== --}}
			{{-- ⭐ THE ONE CHART HERE THAT SAYS SOMETHING THE TABLES DO NOT. A phase
			     gantt would re-render dates already in the Schedule table; a
			     completion forecast that MOVES is a fact no single row shows.
			     2,319 projects have a forecast that moved more than once.
			     ⚠ Every figure is the endpoint's — the page draws, it does not
			     compute. ⚠ And the axis is MONTHS LATER THAN THE FIRST PUBLISHED
			     FORECAST, not a date axis: Chart.js needs a date adapter for the
			     latter, and the exact dates are in the tooltip where they read
			     better anyway.
			     ⚠ IT SITS DIRECTLY BENEATH THE SCHEDULE AND ABOVE THE HISTORY: it is
			     the schedule history's story, and the table below is the receipt. --}}
			@if($sections['How the completion forecast has moved'])
				<h2 id="slippage" class="db-anchor mt-4">How the completion forecast has moved</h2>
				<p class="mb-1">
					The City's forecast completion date for this project has moved
					<strong>{{ abs($slip['total_months']) }} months {{ $slip['direction'] }}</strong>
					across {{ $slip['publications'] }} reporting periods —
					{{-- ⚠ NO `?? $slip[...]['forecast_completion']` FALLBACK. It looked
					     defensive and was the one hole left through which a raw
					     `MM/DD/YYYY` could reach the page — `_mdy_label` already falls
					     back to the raw string itself when a value will not parse, so
					     the second fallback could only ever fire by printing the format
					     item K exists to remove. --}}
					from {{ $slip['first']['forecast_completion_label'] }} ({{ $slip['first']['period_label'] }})
					to {{ $slip['latest']['forecast_completion_label'] }} ({{ $slip['latest']['period_label'] }}).
				</p>
				<p class="db-note-small mb-2">{{ $slip['note'] }}</p>
				<div class="db-chart-card mb-2">
					{{-- ⚠⚠ THE FIXED-HEIGHT WRAPPER IS REQUIRED (#61). A
					     `maintainAspectRatio:false` canvas outside `.db-chart-body`
					     grows without bound and takes the page with it. --}}
					<div class="db-chart-body"><canvas id="slipChart"></canvas></div>
				</div>
				<p class="db-note-small">{{ $slip['other_series_note'] }}</p>
			@endif

			{{-- ===================== BUDGET HISTORY ===================== --}}
			@if($sections['Budget and schedule over time'])
				<h2 id="history" class="db-anchor mt-4">Budget and schedule over time</h2>
				{{-- ⚠⚠ ONE BLOCK PER PUBLICATION, NOT ONE UNIONED TABLE. Four sources
				     with different columns forced into one 45 × 14 grid made half the
				     cells `—` and pushed the per-row source label into a cell that
				     wrapped to five lines on a phone. Each source now carries only the
				     columns it actually publishes — MEASURED per source over the whole
				     205,503-row history, not assumed — and its label is the block
				     HEADING rather than a cell repeated on every row.
				     ⚠ AND NOTHING IS DEDUPED ACROSS SOURCES. The Dashboard's main table
				     and its schedule history agree on 98% of periods and disagree on 2%
				     (371 of 17,764, measured). That disagreement is a fact about the
				     City's two tables and both stay visible. --}}
				<p class="db-note-small mb-2">{{ $hbs['note'] ?? '' }}</p>
				@foreach($hbs['groups'] ?? [] as $gi => $g)
					@php $gid = 'hist' . $gi; @endphp
					<div class="mb-2">
						<h3 class="db-text-base mb-1">
							{{ $g['source_label'] }}
							@if($g['retired'])<span class="db-badge db-badge-warning">retired 2023</span>@endif
						</h3>
						<p class="small mb-1">
							{{ $g['summary'] }} —
							<a data-bs-toggle="collapse" href="#{{ $gid }}" role="button" aria-expanded="false" aria-controls="{{ $gid }}">show snapshots</a>
						</p>
						<div class="collapse" id="{{ $gid }}">
							{{-- ⚠ UNCHANGED ROWS ARE IN THE DOM, HIDDEN — never dropped. A
							     project republished unchanged is a fact about the City's
							     publishing, and a table silently missing rows is the defect
							     this repo keeps paying for. The default view is the rows that
							     changed something. --}}
							@if($g['count'] > $g['changed_count'])
								<p class="small mb-1">
									<label><input type="checkbox" class="hist-all" data-target="{{ $gid }}"> show the {{ $g['count'] - $g['changed_count'] }} unchanged snapshots too</label>
								</p>
							@endif
							<div class="table-responsive">
								<table class="db-table table table-sm">
									<thead><tr>
										@foreach($g['headings'] as $ci => $hd)
											<th scope="col" @if(substr($g['columns'][$ci], -4) === '_usd') class="text-end" @endif>{{ $hd }}</th>
										@endforeach
									</tr></thead>
									<tbody>
									@foreach($g['rows'] as $r)
										<tr class="@if(!$r['changed']) hist-unchanged d-none @endif">
											@foreach($g['columns'] as $col)
												<td @if(substr($col, -4) === '_usd') class="text-end" @endif>{{ $histCell($col, $r) }}</td>
											@endforeach
										</tr>
									@endforeach
									</tbody>
								</table>
							</div>
						</div>
					</div>
				@endforeach
			@endif

			{{-- ===================== MILESTONES (2023) ===================== --}}
			@if($sections['Milestones (2023)'])
				<h2 id="milestones" class="db-anchor mt-4">Milestones (2023)</h2>
				{{-- ⚠ A RETIRED SERIES, SAID SO. Every date below is a 2023 statement;
				     presenting them beside the live schedule without that sentence
				     invites a reader to read them as current. --}}
				<p class="db-note mb-2">From the project milestone series NYC retired on 26 October 2023. These are the tasks as published then, not a current schedule.</p>
				{{-- ⚠ ITEM B'S PATTERN, REUSED: the CAVEAT above is visible and the ROWS
				     are one click away. This is a retired series, so a reader needs to
				     know it exists and what it is before they need its 10 task rows —
				     and a caveat behind a disclosure triangle is a caveat nobody reads,
				     which is why the note sits outside the collapse and not in it. --}}
				<p class="small mb-1">
					{{ count($miles['rows']) }} {{ count($miles['rows']) == 1 ? 'task' : 'tasks' }} as published —
					<a data-bs-toggle="collapse" href="#milesTable" role="button" aria-expanded="false" aria-controls="milesTable">show them</a>
				</p>
				<div class="collapse" id="milesTable">
				<div class="table-responsive">
					<table class="db-table table table-sm">
						<thead><tr><th scope="col">#</th><th scope="col">Task</th><th scope="col">Originally planned</th><th scope="col">As published in 2023</th></tr></thead>
						<tbody>
						@foreach($miles['rows'] as $m)
							<tr>
								<td>{{ $txt($m['seq']) }}</td>
								<td>{{ $txt(trim((string) $m['task'])) }}</td>
								<td class="small">{{ $txt($m['orig_start_label']) }} – {{ $txt($m['orig_end_label']) }}</td>
								<td class="small">{{ $txt($m['start_date_label']) }} – {{ $txt($m['end_date_label']) }}</td>
							</tr>
						@endforeach
						</tbody>
					</table>
				</div>
				</div>
			@endif

			{{-- ===================== PARKS TRACKER ===================== --}}
			@if($sections['NYC Parks project tracker'])
				<h2 id="parks" class="db-anchor mt-4">NYC Parks project tracker</h2>
				{{-- ⚠ A LIST, NOT A SUMMARY. 37 of 1,660 tracked projects carry more
				     than one tracker row (up to 13) because Parks tracks sub-projects
				     under one FMS id. Collapsing them would invent a single
				     percent-complete for work Parks reports separately. --}}
				@if($parks['count'] > 1)
					<p class="db-note-small">NYC Parks tracks {{ $parks['count'] }} separate pieces of work under this project id.</p>
				@endif
				<div class="table-responsive">
					<table class="db-table table table-sm">
						<thead><tr><th scope="col">Tracker</th><th scope="col">Phase</th><th scope="col" class="text-end">Design</th><th scope="col" class="text-end">Procurement</th><th scope="col" class="text-end">Construction</th><th scope="col">Projected completion</th><th scope="col">Funding band</th></tr></thead>
						<tbody>
						@foreach($parks['rows'] as $t)
							<tr>
								<td>{{ $txt($t['title']) }}<div class="db-muted small">{{ $txt($t['tracker_id']) }}</div></td>
								<td>{{ $txt($t['current_phase']) }}</td>
								<td class="text-end">{{ $t['design_pct'] === '' ? '—' : $t['design_pct'] . '%' }}</td>
								<td class="text-end">{{ $t['procurement_pct'] === '' ? '—' : $t['procurement_pct'] . '%' }}</td>
								<td class="text-end">{{ $t['construction_pct'] === '' ? '—' : $t['construction_pct'] . '%' }}</td>
								<td>{{ $txt($t['construction_projected_label']) }}</td>
								<td class="small">{{ $txt($t['total_funding']) }}</td>
							</tr>
						@endforeach
						</tbody>
					</table>
				</div>
			@endif

			{{-- ===================== CLIMATE ===================== --}}
			@if($sections['Climate Budgeting ratings'])
				<h2 id="climate" class="db-anchor mt-4">Climate Budgeting ratings</h2>
				{{-- ⚠⚠ ONE ROW PER BUDGET LINE, AT THE LATEST VINTAGE, AND BOTH HALVES
				     ARE MEASURED. Across vintages a rating genuinely moves — 3,182 of
				     12,126 projects carry more than one GHG rating — so this is the
				     latest publication only, and it says which. Within one vintage the
				     rating varies only where a project spans several budget lines;
				     per (project, vintage, budget line) it is constant on all 37,245
				     triples. A single rating per project would therefore be a summary
				     of things OMB rated separately. --}}
				<p class="db-note-small">OMB rates a project's climate alignment per budget line. Showing the most recent publication carrying this project.</p>
				<div class="table-responsive">
					<table class="db-table table table-sm">
						<thead><tr><th scope="col">Published</th><th scope="col">Budget line</th><th scope="col">Greenhouse gas</th><th scope="col">Flood resiliency</th><th scope="col">Heat resiliency</th></tr></thead>
						<tbody>
						@foreach($clim['rows'] as $c)
							<tr>
								<td>{{ $txt($c['published_label']) }}</td>
								<td>{{ $txt($c['budget_line']) }}<div class="db-muted small">{{ $txt($c['budget_line_title']) }}</div></td>
								<td>{{ $txt($c['ghg_mitigation']) }}</td>
								<td>{{ $txt($c['flood_resiliency']) }}</td>
								<td>{{ $txt($c['heat_resiliency']) }}</td>
							</tr>
						@endforeach
						</tbody>
					</table>
				</div>
			@endif

			{{-- ===================== ALSO FUNDED HERE ===================== --}}
			@if($sections['Planned commitments'])
				<h2 id="commitments" class="db-anchor mt-4">Planned commitments</h2>
				<p class="db-note-small">{{ $comm['count'] }} commitment {{ $comm['count'] == 1 ? 'line' : 'lines' }} in the current Capital Commitment Plan. One project is funded by many commitments.</p>
				<div class="table-responsive">
					<table class="db-table table table-sm">
						<thead><tr><th scope="col">Budget line</th><th scope="col">Type</th><th scope="col">Planned date</th><th scope="col">Description</th><th scope="col" class="text-end">Total</th><th scope="col" class="text-end">City</th><th scope="col" class="text-end">Non-city</th></tr></thead>
						<tbody>
						@foreach($comm['rows'] as $c)
							<tr>
								<td>{{ $txt($c['budgetline']) }}</td>
								<td class="small">{{ $txt($c['projecttype']) }}</td>
								<td>{{ $txt($c['plancommdate_label']) }}</td>
								<td class="small">{{ $txt($c['commitmentdescription']) }}</td>
								<td class="text-end">{{ $fmtM($c['plannedcommit_total']) }}</td>
								<td class="text-end">{{ $fmtM($c['plannedcommit_citycost']) }}</td>
								<td class="text-end">{{ $fmtM($c['plannedcommit_noncitycost']) }}</td>
							</tr>
						@endforeach
						</tbody>
					</table>
				</div>
			@endif

			@if($sections['Other projects on the same budget line'])
				<h2 id="sameline" class="db-anchor mt-4">Other projects on the same budget line</h2>
				{{-- ⚠ COUNT BEFORE YOU CAP. The total is the endpoint's, measured on the
				     unsliced set; the largest budget line carries over a thousand
				     projects, and a capped list under a heading implying all of them is
				     a defect this repo has shipped more than once.
				     ⚠⚠ AND THE "SEE ALL" LINK IS BUILT FROM THE SERVED `filter`, never
				     from a query string composed here. The endpoint knows which of a
				     project's 1-to-34 budget lines the link can answer for; a string
				     typed in this view would be a second, silently diverging copy of
				     that decision. --}}
				<p class="db-note-small">
					Showing {{ number_format($sameLine['showing']) }} of {{ number_format($sameLine['count']) }}, largest planned commitments first.
					@if(!empty($sameLine['filter']['budget_line']))
						<a href="{{ route('projects') }}?budget_line={{ rawurlencode($sameLine['filter']['budget_line']) }}">See all on budget line {{ $sameLine['filter']['budget_line'] }} →</a>
					@endif
				</p>
				<div class="table-responsive">
					<table class="db-table table table-sm">
						<thead><tr><th scope="col">Project</th><th scope="col">Agency</th><th scope="col" class="text-end">Planned</th></tr></thead>
						<tbody>
						@foreach($sameLine['rows'] as $r)
							@php $rid = ($r['agency_key'] ?? '') . ($r['fms_id'] ?? ''); $rd = trim((string)($r['description'] ?? '')) ?: $rid; @endphp
							<tr>
								<td><a href="/p/{{ rawurlencode($rid) }}_{{ \Illuminate\Support\Str::slug($rd) }}">{{ $rd }}</a>
									<div class="db-muted small">{{ $rid }}</div></td>
								<td>{{ $txt($r['agency_acro']) }}</td>
								<td class="text-end">{{ $fmtM($r['planned_total_usd']) }}</td>
							</tr>
						@endforeach
						</tbody>
					</table>
				</div>
			@endif

			@if($sections['City Council capital awards'])
				<h2 id="awards" class="db-anchor mt-4">City Council capital awards on this budget line</h2>
				{{-- ⚠⚠ AN AWARD ON A BUDGET LINE IS NOT AN AWARD TO THIS PROJECT. The
				     Council states the LINE, not the project. The endpoint's own
				     sentence says so and is echoed, because presenting these as this
				     project's funding is an inference the source does not support.
				     ⚠ IT IS A NOTE, NOT GREY 12px TEXT. This is one of the three
				     sentences on the page that stop a published number being misread;
				     styling it as the smallest, faintest thing here inverted that. --}}
				<p class="db-note mb-2">{{ $awards['note'] ?? '' }}</p>
				<p class="db-note-small">Showing {{ number_format($awards['showing']) }} of {{ number_format($awards['count']) }}.</p>
				<div class="table-responsive">
					<table class="db-table table table-sm">
						<thead><tr><th scope="col">FY</th><th scope="col">Sponsor</th><th scope="col">Award</th><th scope="col">Budget line</th><th scope="col" class="text-end">Amount</th><th scope="col">District</th></tr></thead>
						<tbody>
						@foreach($awards['rows'] as $a)
							<tr>
								<td>{{ $txt($a['fiscal_year']) }}</td>
								<td>{{ $txt($a['sponsor']) }}</td>
								<td class="small">{{ $txt($a['title']) }}</td>
								<td>{{ $txt($a['budget_line']) }}</td>
								<td class="text-end">{{ $fmtM($a['award']) }}</td>
								<td>{{ $txt($a['council_district']) }}</td>
							</tr>
						@endforeach
						</tbody>
					</table>
				</div>
			@endif

			{{-- ===================== SOURCES ===================== --}}
			<h2 id="sources" class="db-anchor mt-4">Where these figures come from</h2>
			{{-- ⚠⚠ THE SAME COMPONENT THE REST OF THE SITE USES, in `record` mode.
			     The accordion is a pattern on fifteen views; this page had a bespoke
			     table instead, so a reader who had learned the pattern elsewhere met
			     something different here. Same shell, same place, two extra columns —
			     `In this record?` and `Version` — which are the two things a
			     page-scoped listing cannot say.
			     ⚠⚠ AND IT IS NOT MERGED WITH THE PAGE-SCOPED MODE. A dataset's total
			     record count and this project's presence in it are different claims;
			     one row carrying both invites "475,136 records" to be read as being
			     about this project.
			     ⚠ The key-facts strip at the top says HOW MANY sources carry the
			     project; this says WHICH, with each one's version. Both, never one. --}}
			{{-- ⚠⚠ THE COUNT AND THE ABSENCES MOVED HERE (owner, 2026-09-10), from
			     under the key-facts strip. It is the same sentence and the same two
			     lists; what changed is that it now sits with the table it summarises
			     instead of ~2,700px above it, under a heading that asks its exact
			     question.
			     ⚠ IT WAS AT THE TOP FOR A REASON AND THE REASON WEAKENED. The §5.3
			     defect was this text sitting 9,000px below the fold on a 9,636px
			     page with nothing else accounting for the absences. The page is
			     ~3,200px now, the TOC links straight to this heading, and the
			     coverage table beside it names every source with its version — so
			     "a reader learns what is missing only after reading everything" no
			     longer describes it.
			     ⚠ BOTH LISTS STILL PRINT, and subtracted. `sources_absent` names
			     PUBLICATIONS and `$hiddenOnly` names SECTIONS; printing them
			     unsubtracted repeated the same two names twice in one sentence, and
			     dropping either leaves a whole class of absence named nowhere. --}}
			<p class="small mb-2">
				In {{ $kf['sources_present'] ?? 0 }} of {{ $kf['sources_read'] ?? 0 }} sources Databook reads.
				@if(count($kf['sources_absent'] ?? []))
					Not published in: {{ implode(', ', $kf['sources_absent']) }}.
				@endif
				@if(count($hiddenOnly))
					Nothing published for: {{ implode(', ', $hiddenOnly) }}.
				@endif
			</p>
			<x-db.data-provenance mode="record" :coverage="$cov" id="prjSources" />

				</div>
			</div>

		</div>
	</div>

@if(!empty($hbs['available']))
	<script>
		// ⚠ The unchanged snapshots are already in the DOM, hidden — this only
		// toggles them. Nothing is fetched and nothing is recomputed.
		$(document).ready(function () {
			$('.hist-all').on('change', function () {
				var $rows = $('#' + $(this).data('target')).find('tr.hist-unchanged');
				if (this.checked) { $rows.removeClass('d-none'); } else { $rows.addClass('d-none'); }
			});
		});
	</script>
@endif

@if(!empty($slip['available']))
	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>
		// ⚠ Points come from the payload verbatim. The page renders; it does not
		// recompute a figure the endpoint already published.
		var SLIP = {!! json_encode($slip['points']) !!};
		$(document).ready(function () {
			if (typeof Chart === 'undefined') return;
			DBChart.apply(Chart);
			var el = document.getElementById('slipChart');
			if (!el) return;
			window.SLIP_CHART = new Chart(el.getContext('2d'), {
				type: 'line',
				data: {
					labels: SLIP.map(function (p) { return p.period_label; }),
					datasets: [{
						label: 'Months later than the first published forecast',
						data: SLIP.map(function (p) { return p.months_later; }),
						borderColor: DBChart.navy,
						backgroundColor: DBChart.navyFill,
						fill: true, tension: 0.15, pointRadius: 4
					}]
				},
				options: {
					responsive: true, maintainAspectRatio: false,
					plugins: {
						legend: { display: false },
						tooltip: {
							callbacks: {
								// ⚠ The tooltip carries the ACTUAL forecast date and the
								// City's own stated reason. The axis is a derived unit; the
								// date is the thing the City published.
								// ⚠ THE SERVED LABEL, not the raw `MM/DD/YYYY`. The tooltip
								// was the last place on the page still printing the other
								// date format.
								label: function (ctx) {
									var p = SLIP[ctx.dataIndex];
									var out = ['Forecast: ' + (p.forecast_completion_label || p.forecast_completion)];
									if (p.months_later) out.push(p.months_later + ' months later than the first');
									if (p.delay_reason) out.push('Reason given: ' + p.delay_reason);
									return out;
								}
							}
						}
					},
					scales: {
						y: { title: { display: true, text: 'Months later than first forecast' },
						     grid: { color: DBChart.grid } },
						x: { grid: { display: false } }
					}
				}
			});
		});
	</script>
@endif

@if($hasMap)
	<script>
		// ⚠⚠ THE OUTLINE IS FETCHED ONE PROJECT AT A TIME, ON PURPOSE. Citywide
		// footprints are a 20 MB payload (1,784 polygons, largest 618 kB), which is
		// why the index map serves centroids. Here the real geometry is affordable
		// and is what a reader wants.
		var PRJ_GEOJSON_URL = '{!! $geojsonUrl !!}';
		var PRJ_MAP_READY = false, PRJ_PENDING = null;

		// ⚠ The fetch and mapbox's style load are a RACE, and the source only
		// exists inside `load`. On /projects a small payload beat the style and
		// `getSource('route')` was undefined, so `setData` threw inside the AJAX
		// handler and the map stayed empty for ever. Same shape, same fix.
		function prjDrawWhenReady(features) {
			if (features) PRJ_PENDING = features;
			if (!PRJ_MAP_READY || PRJ_PENDING === null) return;
			var ff = PRJ_PENDING; PRJ_PENDING = null;
			projectsMapDrawFeatures(ff, true);
			window.PRJ_MAP_FEATURES = ff.length;
		}

		// ⚠ The four types the shared `filtFields` can filter on; anything else
		// still renders as a toggleable overlay, just not highlighted.
		var PRJ_HIGHLIGHT = {!! json_encode($mapHighlight) !!};

		function prjAddBoundaries() {
			// The same 14 overlays /districts, /projects and /schools offer, from
			// the static `/data/{code}.geojson` sets. `setBoundary` also wires each
			// `#{code}-switch` and paints its colour swatch.
			if (typeof zones === 'undefined' || typeof setBoundary !== 'function') return;
			for (var code in zones) {
				try { setBoundary(code, zones[code], zones[code]); } catch (e) {}
			}
			// ⚠⚠ HIGHLIGHT ONLY WHAT THE CITY PUBLISHED FOR THIS PROJECT. The ids
			// come from `capital_project_districts`; `setFilter` adds the fill layer
			// and `map.setFilter` narrows it to those districts, which is exactly
			// what /districts does for a single district.
			for (var t in PRJ_HIGHLIGHT) {
				try {
					if (typeof setFilter === 'function') setFilter(t, filtFields[t]);
					map.setFilter(t + 'FH', ['in', filtFields[t]].concat(PRJ_HIGHLIGHT[t]));
					map.setLayoutProperty(t + 'L', 'visibility', 'visible');
					map.setLayoutProperty(t + 'S', 'visibility', 'visible');
					$('#' + t + '-switch').prop('checked', true);
				} catch (e) {}
			}
		}

		$(document).ready(function () {
			// Boundary overlay control — same open/close + aria behaviour as the
			// other four maps.
			var bc = document.getElementById('boundaries-control');
			var bt = document.getElementById('boundaries-toggle');
			if (bc && bt) {
				bt.addEventListener('click', function (e) {
					e.stopPropagation();
					bt.setAttribute('aria-expanded', bc.classList.toggle('is-open') ? 'true' : 'false');
				});
				document.addEventListener('click', function (e) {
					if (!e.target.closest || !e.target.closest('#boundaries-control')) {
						bc.classList.remove('is-open');
						bt.setAttribute('aria-expanded', 'false');
					}
				});
			}
			projectsMapInit();
			if (typeof map !== 'undefined') {
				if (map.loaded && map.loaded()) { PRJ_MAP_READY = true; prjDrawWhenReady(null); }
				map.on('load', function () { PRJ_MAP_READY = true; prjAddBoundaries(); prjDrawWhenReady(null); });
				if (map.loaded && map.loaded()) { PRJ_MAP_READY = true; prjAddBoundaries(); prjDrawWhenReady(null); }
			}
			// ⚠ Only fetch geometry when there IS geometry — on a district-only
			// project this endpoint has nothing to serve, and a failed fetch would
			// hit the error branch and print a location warning on a page whose
			// map is doing something else entirely.
			@if($hasGeom)
			$.ajax({
				url: PRJ_GEOJSON_URL, dataType: 'json',
				success: function (fc) {
					var features = (fc && fc.features) ? fc.features : [];
					features.forEach(function (ft) {
						if (!ft.properties) ft.properties = {};
						ft.properties.custom_color = '#36c726';
						var b = ft.bbox;
						if (b && b.length === 4) {
							ft.properties.W = b[0]; ft.properties.S = b[1];
							ft.properties.E = b[2]; ft.properties.N = b[3];
						}
					});
					// ⚠ The served sentence, printed as it came — never a description
					// of the geometry typed here.
					$('#mapNote').text((fc && fc.note) ? fc.note : '');
					prjDrawWhenReady(features);
				},
				error: function () {
					// ⚠ A FAILED REQUEST IS NOT AN ABSENT LOCATION.
					$('#mapNote').text('The published outline could not be loaded. This is a problem with this page, not a statement about the project.');
					window.PRJ_MAP_FEATURES = null;
				},
				complete: function () { window.PRJ_MAP_DONE = true; }
			});
			@else
			window.PRJ_MAP_DONE = true;
			@endif
		});
	</script>
@endif

@endsection
