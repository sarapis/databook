@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects commitments." />
	<meta rel="canonical" href="{!! route('prjCommitments') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')

	{{-- ⚠ PINNED TO THE VERSION THIS SECTION ALREADY USES (3.8.0, as
	     budgetLinesA pins it) with its integrity hash — a second Chart.js major
	     on one site is how two charts come to render differently. --}}
	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<style>
		.toolbar {float: right; width: 45%;}
		select.filter-top {width: 46%;}
	</style>
	<script>
		var table = null
		
		// ⚠ Every money field in this payload is a STRING. `+` on two of them
		// concatenates, which is what produced a $634 quadrillion total below.
		var num = function (v) { return Number(v) || 0 }
		
		var data = {!! json_encode($data) !!}


		$(document).ready(function() {
			table = $('#prjsCats').DataTable( {
				pageLength: 20,
				deferRender: true,
				order: [[1, 'asc']],
				//dom: '<"toolbar"<"row">>frtip',
				dom: '<"toolbar container-flex"<"row ml-4">>frtip',
				data: data,
				
				columns: [
					{data: 'Published Date', visible: false},
					{data: function (r) {
							return '<a href="/capital/budget-lines/' + r['Budget Line'] + '">' + r['Budget Line'] + '</a>'
						},
						type: 'html'
					},
					{data: 'Budget Line Description'},
					{data: 'Funding Type'},
					{data: 'First Fiscal Year'},
					{data: function (r) { return toFin(r['Fiscal Year 1 Amount'] * 1000) }, type: 'html'},
					{data: function (r) { return toFin(r['Fiscal Year 2 Amount'] * 1000) }, type: 'html'},
					{data: function (r) { return toFin(r['Fiscal Year 3 Amount'] * 1000) }, type: 'html'},
					{data: function (r) { return toFin(r['Fiscal Year 4 Amount'] * 1000) }, type: 'html'},
					{{-- ⚠⚠ TWO DEFECTS IN ONE CELL, both measured on the rendered page.
					     (1) THE AMOUNTS ARE STRINGS, so `+` concatenated them: budget line
					     AG0001, whose four years total $19,244,000, rendered
					     **$634,158,196,199,885,056**. Every row on the page was wrong.
					     (2) A COLUMN HEADED "Total Commitment Value" SUMMED FOUR OF FIVE
					     YEARS. `Number of Years Presented` is 4 or 5, and 867 of 5,074
					     rows carry a fifth — **$34.4B**, 12% of the FY1-4 total, silently
					     outside a figure calling itself the total.
					     ⚠ The fifth year now has its own column too, so the total is
					     something a reader can check by adding up the row rather than
					     something they have to trust. --}}
					{data: function (r) { return toFin(num(r['Fiscal Year 5 Amount']) * 1000) }, type: 'html'},
					{data: function (r) { return toFin((num(r['Fiscal Year 1 Amount']) + num(r['Fiscal Year 2 Amount']) + num(r['Fiscal Year 3 Amount']) + num(r['Fiscal Year 4 Amount']) + num(r['Fiscal Year 5 Amount'])) * 1000) }, type: 'html'},
                ],
				@if ($defSearch ?? null)
					search: {
						'search': '{{ $defSearch }}'
				    },
				@endif	

				initComplete: function () {
					this.api().columns([4]).every(function () {						// First Fiscal Year
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- First Fiscal Year -</option></select>')
							.appendTo($('div.toolbar .row'))
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
							select.append( '<option value="'+d+'">'+d+'</option>' )
						});

						setTimeout(function(){
							select.val(tt[tt.length-1]).trigger('change')
							//select.val('20210426').trigger('change')
						}, 700);
					});

					
					this.api().columns([0]).every(function () {						// pubdate
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- Published Date -</option></select>')
							.appendTo($('div.toolbar .row'))
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
							//select.val('20210426').trigger('change')
						}, 700);
					});


				}
			});

			{{-- ⚠⚠ BOUND TO THE TABLE, NOT THE PAYLOAD. `data` holds three
			     publication dates of the same plan; summing them is not a figure.
			     `DBTableCharts` redraws on every `draw`, so the charts follow the
			     First Fiscal Year filter and the search box.
			     ⚠ ×1000 on every amount, matching the columns above — this payload
			     is denominated in THOUSANDS, and carrying the multiplier on the
			     table but not the chart is invariant 2 (it renders $288.7B as
			     $288.7M). --}}
			DBTableCharts.bind(table, [
				{
					canvas: 'ccByYear', type: 'bar', order: 'label',
					// One row funds up to five fiscal years; `expand` is what stops
					// this charting the first and dropping $34.4B of the fifth.
					expand: function (r) {
						var y0 = Number(r['First Fiscal Year']) || 0, out = [];
						for (var i = 1; i <= 5; i++)
							out.push([String(y0 + i - 1), num(r['Fiscal Year ' + i + ' Amount']) * 1000]);
						return out;
					},
				},
				{
					canvas: 'ccByFund', type: 'doughnut',
					label: function (r) { return r['Funding Type'] },
					value: function (r) {
						return (num(r['Fiscal Year 1 Amount']) + num(r['Fiscal Year 2 Amount'])
							+ num(r['Fiscal Year 3 Amount']) + num(r['Fiscal Year 4 Amount'])
							+ num(r['Fiscal Year 5 Amount'])) * 1000;
					},
				},
				{
					canvas: 'ccByLine', type: 'bar', horizontal: true, top: 10,
					restLabel: 'All other budget lines',
					label: function (r) { return r['Budget Line'] },
					value: function (r) {
						return (num(r['Fiscal Year 1 Amount']) + num(r['Fiscal Year 2 Amount'])
							+ num(r['Fiscal Year 3 Amount']) + num(r['Fiscal Year 4 Amount'])
							+ num(r['Fiscal Year 5 Amount'])) * 1000;
					},
				},
			])
		});
	</script>
<div class="inner_container">
	<div class="mt-4 mx-3">
		<div class="db-eyebrow">Projects</div>
		{{-- ⚠ AN h1, NOT AN h2. This page had NO h1 anywhere while its title
		     rendered at the same 30px as every sibling — the "a heading tag is a
		     font size" defect the 2026-09-10 pass fixed on ten other capital
		     pages, still live here because that pass worked from a hand-typed
		     list this view was not on. `h1.db-profile-title` is qualified so it
		     ties `style.css`'s legacy `.organization_data h1` on specificity;
		     a bare class loses and the title jumps to 32px. --}}
		<h1 class="db-profile-title">Commitments</h1>
		<p class="lead">The Mayor's Office of Management and Budget (OMB) publishes a <a target="_blank" href="https://data.cityofnewyork.us/City-Government/Capital-Commitment-Plan/2cmn-uidm/about_data">Capital Commitment Plan</a> scheduling agency capital spending three times a year. These commitments make funding available to projects.</p>
	</div>
	<div class="container">
		{{-- ⚠⚠ THESE CHARTS READ THE TABLE'S FILTERED ROWS, NOT THE PAYLOAD.
		     The payload carries THREE publication dates (5,074 rows over 20260512
		     / 20260217 / 20250930), so charting it whole would add three
		     publications of the same plan together — a number about nothing. One
		     owner for the mechanism: `DBTableCharts.bind`. --}}
		<div class="row justify-content-center mb-4">
			<div class="col-md-4">
				<x-db.chart-card title="Commitments by fiscal year">
					<canvas id="ccByYear"></canvas>
				</x-db.chart-card>
			</div>
			<div class="col-md-4">
				<x-db.chart-card title="City and non-City funding">
					<canvas id="ccByFund"></canvas>
				</x-db.chart-card>
			</div>
			<div class="col-md-4">
				<x-db.chart-card title="Largest budget lines">
					<canvas id="ccByLine"></canvas>
				</x-db.chart-card>
			</div>
		</div>
		<div class="row justify-content-center">
			<div class="col-md-12 organization_data">
                <div class="table-responsive">
                    <table id="prjsCats" class="db-table display table" style="width:100%;padding-top: 30px;">
                        <thead>
                            <tr>
								<th scope="col">Published Date</th>
								<th scope="col">Budget Line</th>
								<th scope="col">Budget Line Description</th>
								<th scope="col">Funding Type</th>
								<th scope="col">First Fiscal Year</th>
								<th scope="col">Fiscal Year 1 Amount</th>
								<th scope="col">Fiscal Year 2 Amount</th>
								<th scope="col">Fiscal Year 3 Amount</th>
								<th scope="col">Fiscal Year 4 Amount</th>
								<th scope="col">Fiscal Year 5 Amount</th>
								<th scope="col">Total Commitment Value</th>
                            </tr>
                        </thead>
                    </table>
                </div>
			</div>
		</div>
		<div class="row justify-content-center">
			<div class="col-md-12">
				<div class="bottom_lastupdate">
		@if ($dataset)
					<p class="lead"><img src="/img/info.png" alt=""> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] ?? '' }}</a><span class="float-right" style="font-weight: 300;"><i>Last updated {{ \App\Custom\CapitalDate::label($dataset['Last Updated'] ?? '') }}</i></span></p>
				</div>
			</div>
		</div>
		@endif

    </div>
</div>
@endsection
