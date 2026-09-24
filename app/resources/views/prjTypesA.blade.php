@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects taxonomy." />
	<meta rel="canonical" href="{!! route('prjTypes') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')

	{{-- ⚠ PINNED TO THE VERSION THIS SECTION ALREADY USES (3.8.0), with its
	     integrity hash. Two Chart.js majors on one site is how two charts come
	     to render differently. --}}
	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<style>
		.toolbar {float: right; width: 25%;}
		select.filter-top {width: 100%;}
	</style>
	<script>
		var table = null

		// ⚠ ONE OWNER for the retired series' three cells. `0` from this endpoint
		// is "the join found no row", never "zero projects" — see the note on the
		// columns — so it renders an em dash. Invariant 7: a number, `0` and `—`
		// are three different claims.
		function retired(v, money) {
			var n = parseFloat(v);
			if (!isFinite(n) || n === 0)
				return '<span class="db-text-muted">\u2014</span>';
			return money ? toFin(n * 1000) : n.toLocaleString();
		}

		var data = {!! json_encode(array_values($data)) !!}
		
		var datasets = {!! json_encode(array_values($datasets)) !!}
		$(document).ready(function() {
			table = $('#prjsTypes').DataTable( {
				data: data,
				pageLength: 20,
				deferRender: true,
				order: [[1, 'asc']],
				//dom: '<"toolbar"<"row">>frtip',
				dom: '<"toolbar"<"row">>frtip',
				
				columns: [
                    {data: 'pubdate', visible: false},
                    {data: function (r) {
							// ⚠ A row with no `link` is a type whose page cannot exist —
							// 8 of 202, measured. It renders as TEXT, not as a link to a
							// 404, and not hidden: the type is real and its figures on
							// this page are real; what is missing is a page of its own.
							return r['link']
								? '<a href="' + r['link'] + '">' + r['ptype_name'] + '</a>'
								: r['ptype_name']
						},
						type: 'html'
					},
                    {data: 'catnum'},
                    {data: function (r) { return toFin(r["yr10_total"] * 1000) }, type: 'html'},
                    {data: 'blnum'},
                    {data: function (r) { return toFin(r["bl_yr4_total"]) }, type: 'html'},
                    {data: 'cnum'},
                    {data: function (r) { return toFin(r["yr1_amt"] * 1000) }, type: 'html'},
                    // ⚠⚠ THESE THREE COLUMNS COME FROM `capitalprojectsdollarscomp`,
                    // THE SERIES NYC RETIRED 2023-10-26, while every column to their
                    // left is the Ten-Year Strategy at the vintage the Publication
                    // Date control selects — 2025-05-01 by default. So the row mixed
                    // 2025 strategy money with a 2023 project count and said nothing
                    // about it. This is the defect `/get/pstats-categories_by_type`
                    // records for the per-TYPE page ("A MIXED PAGE AND NOTHING SAID
                    // SO"); the same three columns survived on the INDEX.
                    // ⚠ They cannot be repointed at the spine. `capitalstrategy` has
                    // NO project key, and the spine's own `project_types` is a
                    // different 39-value dimension (deduplicated budget-line
                    // families) whose overlap with the strategy's work types is 5,
                    // every one a coincidence. So the honest treatment is to label
                    // the series they come from, which is what the org tab's union
                    // tiles and its alt-union table already do.
                    // ⚠⚠ AND `0` MEANS "NO MATCH", NOT "NO PROJECTS". The endpoint
                    // LEFT JOINs and `COALESCE(..., 0)`s, and a matched group counts
                    // DISTINCT project ids so it can never be 0 — measured on all
                    // 531 rows, `pnum == 0` and money `== 0` agree on every one, 0
                    // disagreeing. On the default vintage 5 of 37 rows read
                    // "0 projects / $0 / $0", among them **Department of Education**.
                    // A rendered $0 is a claim the City did not make.
                    // ⚠⚠ `render` WITH ITS `type` ARGUMENT, NOT `type: 'html'`. A cell
                    // whose visible text is not monotonic in its value needs a sort
                    // key: `type: 'html'` strips the tags and compares STRINGS, so
                    // `$1,351,983,000` sorted before `$296,902,000` — that was already
                    // true of these two money columns before the em dash existed, and
                    // wrapping the count in markup would have taken `Projects` from a
                    // correct numeric sort to the same string compare. Returning the
                    // raw number for every non-display request is the DataTables
                    // mechanism for exactly this, and it fixes the pre-existing
                    // mis-sort in the same edit.
                    {data: 'pnum', render: function (d, t) {
                        return t === 'display' ? retired(d, false) : (parseFloat(d) || 0); }},
                    {data: 'budg_cost', render: function (d, t) {
                        return t === 'display' ? retired(d, true) : (parseFloat(d) || 0); }},
                    {data: 'curr_cost', render: function (d, t) {
                        return t === 'display' ? retired(d, true) : (parseFloat(d) || 0); }},
                ],
				@if ($defSearch ?? null)
					search: {
						'search': '{{ $defSearch }}'
				    },
				@endif	

				initComplete: function () {
					this.api().columns([0]).every(function () {						// pubdate
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- Published Date -</option></select>')
							//.appendTo($('div.toolbar'))
							.appendTo($('#pub_date_filter'))
							.on('change', function () {
								var val = $.fn.dataTable.util.escapeRegex(
									$(this).val()
								);
								column
									.search(val ? val : '', false, false)
									.draw();
							});
						var tt = []

						rg = />([^<]+)</g;
						column.data().each(function (d, j) {
							//while ((t = rg.exec(d)) !== null) {
							//	tt.push(t[1])
							//}
							tt.push(d)
						})
						tt = [...new Set(tt)]

						tt.sort().forEach(function (d, j) {
							select.append( '<option value="'+d+'">'+toDashDate(d)+'</option>' )
						});
						
						
						setTimeout(function(){
							select.val(tt[tt.length-1]).trigger('change')
							//select.val('20230112').trigger('change')
						}, 700);
						
					});

					
				}
			});



			{{-- ⚠ ×1000 ON THE TWO MONEY CUTS AND NOT ON THE COUNT, matching the
			     columns above exactly. `capitalstrategy` money is denominated in
			     THOUSANDS; carrying the multiplier on the table and not the chart
			     renders $30.2B as $30.2M (invariant 2). --}}
			DBTableCharts.bind(table, [
				{canvas: 'tyByTen', type: 'bar', horizontal: true, top: 10,
				 restLabel: 'All other types',
				 label: function (r) { return r['ptype_name'] },
				 value: function (r) { return (Number(r['yr10_total']) || 0) * 1000 }},
				{canvas: 'tyByYr1', type: 'bar', horizontal: true, top: 10,
				 restLabel: 'All other types',
				 label: function (r) { return r['ptype_name'] },
				 value: function (r) { return (Number(r['yr1_amt']) || 0) * 1000 }},
				{canvas: 'tyByLines', type: 'bar', horizontal: true, top: 10, money: false,
				 restLabel: 'All other types',
				 label: function (r) { return r['ptype_name'] },
				 value: function (r) { return Number(r['blnum']) || 0 }},
			])
		});
	</script>
<div class="inner_container">
	<div class="container organization_data pb-0">
		<div class="row justify-content-center">
			<div class="col-md-12">
				<div class="db-eyebrow">Projects</div>
				<h1 class="db-profile-title">Project Types</h1>
				<p class="lead">The <a target="_blank" href="https://data.cityofnewyork.us/dataset/Ten-Year-Capital-Strategy/b37a-3faw">Ten-Year Capital Strategy</a> explains the Mayor's long-term vision for the city's capital program. It's updated every two years and is organized into <a href="{!! route('prjTypes') !!}">project types</a>, which are often agency specific, and thematic <a href="{!! route('prjCategories') !!}">categories</a>. Both project type and categories are used to classify each capital project.</p>
			</div>
		</div>
		<div class="row justify-content-center">
			<div class="col-md-7">
			</div>
			<div class="col-md-5 mt-0" id="org_summary">
				<table class="table-sm stats-table" width="100%">
				<thead>
					<tr>
						{{-- ⚠⚠ THE `?` ON THIS PAGE SHOWED NOTHING, and the note below it was
						     moved behind it (owner, 2026-09-11) — so the first half of that
						     request was making the icon work at all. Measured before
						     changing anything: `initPopovers()` is called from exactly ONE
						     place in `script.js`, inside the MAP's click handler, so on a
						     page with no map it never runs. The `<th>` carried no
						     `data-toggle`, and clicking it produced **0** popovers. The
						     tooltip "See the project info published on specific dates." had
						     never been readable either.
						     ⚠⚠ AND `initPopovers()` MUST NOT BE CALLED GLOBALLY TO FIX IT.
						     It binds every `[data-content]` on the page, and `data-content`
						     is also the DATATABLES SORT KEY on every money cell in this
						     section — money columns are not monotonic in their visible text,
						     which is why they carry one. Turning it on site-wide would make
						     every money cell a popover. So this uses Bootstrap 5's own
						     `data-bs-content`, which cannot collide with that usage, and is
						     initialised for THIS button alone.
						     ⚠ A `<button>`, not an `<i>`: a popover on a non-focusable
						     element is mouse-only, and this repo already records that a
						     mouse-only tooltip is not a citation. It carries `aria-label`
						     and `tabindex` comes free with the element.
						     ⭐ SAFE TO PUT BEHIND A CLICK because the load-bearing half is
						     still on the page WITHOUT it: all three affected columns render
						     a visible `2023 series` label in their own headers, so a reader
						     who changes the vintage and sees those three sit still is told
						     why by the table itself. Same shape as the one owner-granted
						     exception to "a caveat is never behind a click" — the disclosure
						     is allowed because the warning survives outside it. --}}
						<th scope="col" width="50%" class="text-center px-0">Publication Date&nbsp;<button type="button" class="btn btn-link p-0 align-baseline db-help-btn" id="pubDateHelp"
							aria-label="About the Publication Date control and the 2023 series columns"
							data-bs-toggle="popover" data-bs-html="true" data-bs-placement="bottom" data-bs-trigger="focus"
							data-bs-title="Publication Date"
							data-bs-content="This control selects the Ten-Year Strategy vintage. The three <strong>2023 series</strong> columns come from the Capital Projects Dollars Comparison, which NYC last published 2023-10-26 and has since retired &mdash; they do not move with it, and an em dash means that series carries no row for the type."><small><i class="bi bi-question-circle-fill" style="top:-1px;position:relative;"></i></small></button></th>
						<th scope="col" width="50%" id="pub_date_filter"></th>
					</tr>
				</thead>
				</table>
			</div>
		</div>
	</div>

	<div class="container">
		{{-- ⚠⚠ DERIVED FROM THE TABLE'S FILTERED ROWS, NOT THE PAYLOAD. This
		     page serves EIGHT publication vintages in one payload and the
		     Publication Date control picks one, so charting the payload whole
		     would add every vintage together — and two of those vintages are the
		     ones this repo records as ingested wrong, so the error would not even
		     be uniform. `DBTableCharts` redraws on every `draw`, so the charts
		     move with the control. --}}
		<div class="row justify-content-center mb-4">
			<div class="col-md-4">
				<x-db.chart-card title="Largest project types by Ten-Year value">
					<canvas id="tyByTen"></canvas>
				</x-db.chart-card>
			</div>
			<div class="col-md-4">
				<x-db.chart-card title="Largest project types by first-year value">
					<canvas id="tyByYr1"></canvas>
				</x-db.chart-card>
			</div>
			<div class="col-md-4">
				<x-db.chart-card title="Budget lines per project type">
					<canvas id="tyByLines"></canvas>
				</x-db.chart-card>
			</div>
		</div>
	</div>

	<div class="container" style="margin-top: -10px;">
		<div class="row justify-content-center">
			<div class="col-md-12 organization_data pt-0">
                <div class="table-responsive">
                    <table id="prjsTypes" class="db-table display table" style="width:100%;padding-top: 30px;">
                        <thead>
                            <tr>
                                <th>Publication Date</th>
                                <th>Name</th>
                                <th>Categories</th>
                                <th>10-Year Value</th>
                                <th>Budget Lines</th>
                                <th>4-Year Value</th>
                                <th>Commitments</th>
                                <th>1-Year Value</th>
                                {{-- ⚠ LABELLED WITH THEIR SERIES, because they are not
                                     the vintage the Publication Date control selects:
                                     they are pinned at the retired series' own last
                                     publication whatever the reader picks. The
                                     alt-union table on the org capital tab labels its
                                     retired-series columns the same way.
                                     ⚠ `Difference` IS GONE. It rendered
                                     `budg_cost - curr_cost`, which is `Amount Over
                                     Budget` — the label this section documents as
                                     carrying two definitions and reproduces nowhere.
                                     It was `visible: false` and this page renders no
                                     colVis button, so it was unreachable dead config;
                                     the answer for that here is delete, not leave it
                                     inert. --}}
                                <th>Projects<br>
                                    <span class="db-text-muted" style="font-weight:400; font-size:var(--db-text-2xs)">2023 series</span></th>
                                <th>Original Budget<br>
                                    <span class="db-text-muted" style="font-weight:400; font-size:var(--db-text-2xs)">2023 series</span></th>
                                <th>Current Budget<br>
                                    <span class="db-text-muted" style="font-weight:400; font-size:var(--db-text-2xs)">2023 series</span></th>
                            </tr>
                        </thead>
                    </table>
                </div>
			</div>
		</div>
		{{--<div class="row justify-content-center">
			<div class="col-md-12">
				<div class="bottom_lastupdate">
		@if ($dataset)
					<p class="lead"><img src="/img/info.png" alt=""> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] ?? '' }}</a><span class="float-right" style="font-weight: 300;"><i>Last updated {{ \App\Custom\CapitalDate::label($dataset['Last Updated'] ?? '') }}</i></span></p>
				</div>
			</div>
		</div>
		@endif
		--}}
		
		<div class="container">
			<div class="row mb-4">
				{{-- One shell, from the shared provenance component. This markup was
				     hand-rolled on fifteen views, each with its own per-page fetch. --}}
				<x-db.data-provenance mode="page" :datasets="$datasets" id="prjTypesADs" />
			</div>
		</div>

    </div>
</div>

{{-- ⚠ A PLAIN INLINE SCRIPT, NOT `@push`. The layout uses `@yield('scripts')`,
     which pairs with `@section` — a `@push` here would be silently discarded and
     the popover would stay as dead as the `<i>` it replaced. This view already
     carries inline scripts in its content section. --}}
<script>
	// ⚠ SCOPED TO ONE ELEMENT. `initPopovers()` in script.js binds every
	// `[data-content]`, and that attribute is the DataTables sort key on the
	// money cells in this section — binding it globally would turn every money
	// cell into a popover. Bootstrap 5's own attributes are read here instead.
	document.addEventListener('DOMContentLoaded', function () {
		var el = document.getElementById('pubDateHelp');
		if (el && window.bootstrap && window.bootstrap.Popover)
			new window.bootstrap.Popover(el);
	});
</script>

@endsection
