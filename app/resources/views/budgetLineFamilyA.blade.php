@extends('layout')

@section('head')
	<meta name="description" content="{{ $snippet }}" />
@endsection

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
@php
	// ⚠ The page computes nothing it is served. Every figure below is a key the
	// endpoint returned.
	$rows  = $fam['rows'] ?? [];
	$lines = $fam['budget_lines'] ?? [];
	// ⚠ Falls back to the bare code list, so an older payload still renders a
	// table rather than an empty section — the #247 seam, degrading visibly.
	$lineRows = $fam['budget_line_rows'] ?? array_map(function ($c) {
		return ['code' => $c, 'title' => null, 'projects' => null];
	}, $lines);

	$fmtM = function ($v) {
		// ⚠ `null` is "the City publishes no such figure" and `0` is a published
		// zero — rendering both as "$0" turns an absence into a claim.
		if ($v === null || $v === '' || !is_numeric($v)) return 'Not published';
		$v = (float) $v;
		if (abs($v) >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
		if (abs($v) >= 1000000) return '$' . number_format($v / 1000000, 1) . 'M';
		return '$' . number_format($v);
	};
	// ⚠⚠ SUMMED IN PHP FROM THE SERVED ROWS, not recomputed from another source.
	// Two independent computations of one number is the defect this whole
	// section was rebuilt to end. `null` is SKIPPED, never added as zero.
	$planned = $spent = 0; $inPlan = 0; $sched = 0;
	foreach ($rows as $r) {
		if ($r['planned_total_usd'] !== null) $planned += (float) $r['planned_total_usd'];
		if ($r['spent_total_usd'] !== null)   $spent   += (float) $r['spent_total_usd'];
		if (!empty($r['in_current_plan'])) $inPlan++;
		if (!empty($r['forecast_completion'])) $sched++;
	}
@endphp

	<div class="inner_container">
		<div class="container">

			<div class="db-profile-kicker mt-4"><span class="db-type-label">Budget-line family</span></div>
			{{-- ⚠ ONE `<h1>`, and the CASE IS NOT TRANSFORMED — these are the City's
			     own labels (`EDP Equipment and Finance Costs`). --}}
			<h1 class="db-profile-title mb-1">{{ $family }}</h1>
			<p class="db-page-lead mb-3">{{ number_format($fam['budget_line_count'] ?? 0) }} budget {{ ($fam['budget_line_count'] ?? 0) == 1 ? 'line' : 'lines' }} · {{ number_format($fam['count'] ?? 0) }} {{ ($fam['count'] ?? 0) == 1 ? 'project' : 'projects' }}</p>

			{{-- ⚠⚠ THE SENTENCE THAT STOPS THIS PAGE BEING MISREAD, AND IT IS THE
			     ENDPOINT'S OWN — echoed, never retyped. A project can be funded
			     through lines in more than one family, so these lists overlap and
			     summing families would double-count. --}}
			<p class="db-note mb-3">{{ $fam['note'] ?? '' }}</p>

			<x-db.stat-grid class="mb-4">
				<x-db.stat label="Projects">{{ number_format($fam['count'] ?? 0) }}</x-db.stat>
				<x-db.stat label="In the current plan">{{ number_format($inPlan) }}</x-db.stat>
				<x-db.stat label="Budget lines">{{ number_format($fam['budget_line_count'] ?? 0) }}</x-db.stat>
				<x-db.stat label="Planned commitments">{{ $fmtM($planned) }}</x-db.stat>
				<x-db.stat label="Spent">{{ $fmtM($spent) }}</x-db.stat>
				<x-db.stat label="With a published schedule">{{ number_format($sched) }}</x-db.stat>
			</x-db.stat-grid>

			<h2 class="mt-4">Budget lines in this family</h2>
			<p class="db-note-small mb-2">Every line the City funds these projects through. A line is one level finer than a family, and the count is how many of this family's projects that line funds &mdash; a project funded through several lines appears against each.</p>
			{{-- ⚠⚠ A TABLE, NOT TAGS (owner request). 103 undifferentiated badges
			     told a reader only that the codes existed; ranked by how many of
			     this family's projects each line funds, the same data says which
			     lines carry the family — WM-0001 funds 236 of Sewers' 444.
			     ⚠ The title is the City's own `Budget Line Title` from
			     `capitalbudget`, joined through `modules/budgetline` on BOTH sides:
			     that table spells a line `AG 0001` and the spine `AG-0001`, so the
			     raw join returns nothing, which reads as "the City publishes no
			     title" rather than as our punctuation. 99 of 103 resolve here; the
			     rest fall back to an em dash rather than dropping the row, because
			     a line we cannot name is still a line that funds these projects. --}}
			<div class="table-responsive mb-4">
				<table id="blTable" class="db-table display table-hover" style="width:100%;">
					<thead>
						<tr>
							<th scope="col">Budget line</th>
							<th scope="col">Title</th>
							<th scope="col" class="text-end">Projects in this family</th>
						</tr>
					</thead>
					<tbody>
						@forelse($lineRows as $row)
							<tr>
								{{-- ⚠ `db-tap` gives these 1-9 character links a 32px touch
								     target at phone width; without it they are ~19px, under
								     every published minimum. --}}
								<td><a class="db-tap" href="{{ route('budgetLine', ['blcode' => $row['code']]) }}">{{ $row['code'] }}</a></td>
								<td>{{ $row['title'] ?? '—' }}</td>
								<td class="text-end">{{ number_format($row['projects'] ?? 0) }}</td>
							</tr>
						@empty
							<tr><td colspan="3" class="text-muted">No budget lines are recorded for this family.</td></tr>
						@endforelse
					</tbody>
				</table>
			</div>

			<h2 class="mt-4">Projects</h2>
			<div class="table-responsive">
				<table id="myTable" class="db-table display table-hover" style="width:100%;">
					<thead>
						<tr>
							@foreach($details['hdrs'] as $h)<th scope="col">{{ $h }}</th>@endforeach
						</tr>
					</thead>
					<tbody></tbody>
				</table>
			</div>

			{{-- ⚠ The same shell every other projects page uses. `rowCounts()` reads
			     the pipeline registry, so the counts are server-rendered rather than
			     fetched from a route that does not exist. --}}
			<div class="row my-4"><div class="col-12">
				<x-db.data-provenance :datasets="$datasets"
					:count="count($datasets)"
					:records="array_sum(array_map(function ($d) { return (int) preg_replace('/[^0-9]/', '', (string) (array_values((array) $d)[4] ?? 0)); }, $datasets))"
					id="famSources" />
			</div></div>

		</div>
	</div>

	<script>
		$(document).ready(function () {
			// ⚠ The SERVED rows, rendered through the SPINE field contract. `main`'s
			// contract multiplies money by 1000 for the retired series' thousands
			// and would render this family's $2.7B as $2.7T.
			// ⚠ 103 lines is a scroll, not a table. Paged at 10 (owner request) and
			// left in the endpoint's own order — most projects first — so page 1 is
			// the lines that actually carry the family rather than an alphabetical
			// accident.
			// ⚠⚠ `order: []` IS LOAD-BEARING. DataTables sorts by the first column
			// ascending by default, which would silently re-rank these by CODE and
			// throw away the ranking the endpoint computed.
			// ⚠ No `columnDefs` type guessing on the count column: it is a plain
			// integer with no unit, so DataTables detects `num` correctly — the
			// `data-order` rule this repo documents applies to cells whose visible
			// text is not monotonic in their value ($100K vs $79.8M), not to these.
			$('#blTable').DataTable({
				pageLength: 10,
				lengthMenu: [[10, 25, 50, -1], [10, 25, 50, 'All']],
				order: [],
				autoWidth: false,
				language: { search: 'Filter lines:', lengthMenu: 'Show _MENU_ lines' }
			});

			$('#myTable').DataTable({
				ajax: function (url, cb) { fapireq("{!! $prjsUrl !!}", cb) },
				deferRender: true,
				pageLength: 25,
				order: {!! json_encode($details['order']) !!},
				columns: [
					@foreach ($details['flds'] as $i=>$f)
						@if ($i > 0),@endif
						{ data: {!! $f !!}@if (preg_match('~^function ~i', $f)), type: 'html'@endif }
					@endforeach
				]
			});
		});
	</script>
@endsection
