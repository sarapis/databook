@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects taxonomy | {{ $data[0]['prjtypename'] }}" />
	<meta rel="canonical" href="{!! route('prjType', ['tslug' => Str::slug($data[0]['prjtypename'], '-')]) !!}" />

	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>if(window.DBChart&&window.Chart)DBChart.apply(window.Chart);</script>
	<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0"></script>

@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	<style>
		.toolbar {float: right; width: 25%; margin-bottom: 20px;}
		select.filter-top {width: 100%;}
		.stats-table span {font-weight: 400;}
		.commstats span {font-weight: 400;}
	</style>

	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-12 organization_data">
					<p class="lead">The <a target="_blank" href="https://www.nyc.gov/assets/omb/downloads/pdf/typ4-21.pdf">Ten-Year Capital Strategy</a> explains the Mayor’s long-term vision for the city’s capital program. It’s updated every two years and is organized into <a href="{!! route('prjTypes') !!}">project types</a>, which are often agency specific, and thematic <a href="{!! route('prjCategories') !!}">categories</a>. Both project type and categories are used to classify each capital project.</p>
				</div>
			</div>
			
			<div class="row justify-content-center">
				<div class="col-md-7">
					<div class="db-eyebrow">Projects</div>
					<h1 class="db-profile-title">{{ $data[0]['prjtypename'] }} <small>({{ $data[0]['prjtype'] }})</small></h1>
					<p>* <i>Categories can be shared by multiple project types.</i></p>
				</div>
				<div class="col-md-5">
					<table class="table-sm stats-table" width="100%">
						<thead>
						  <tr>
							<th scope="col" width="40%" class="text-center px-0" data-content="See budget line info published on specific date.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
							<th scope="col" width="60%" id="pub_date_filter" style="min-width:350px !important;"></th>
						  </tr>
						  <tr>
							{{-- ⚠ The sentence went with the columns it described. This page
							     publishes the Ten-Year Capital Strategy's AMOUNTS; it has no
							     project data at all, because `capitalstrategy` carries no
							     project key. Saying "might not offer project data" implied
							     some publications do. --}}
							<td></td><td>* <i>Amounts published in the Ten-Year Capital Strategy. Follow a category to see the projects the City has assigned to it.</i></td>
						  </tr>
						</thead>
					</table>
				</div>
			</div>


			<div class="row justify-content-center">
				<div id="capproject_profile" class="col-md-12 col-sm-12">
					<div class="table mb-5">
						<table width="100%" class="db-table mb-3" id="project_type_data">
							<thead>
								<tr>
									<th scope="col">Published Date</th>
									<th scope="col">Category</th>
									<th scope="col">Funding Sources</th>
									<th scope="col">Fiscal Year 1 Amount</th>
									<th scope="col">Ten Year Total</th>
								</tr>
							</thead>
							<tbody>
							</tbody>
						</table>
					</div>

					<div class="row">
						<div class="col-5">
							<h4>Budget Lines</h4>
							<table class="table-sm stats-table" width="100%">
								<thead>
									<tr>
										<th class="text-left px-0" data-content="See budget line info published on specific date." style="border-bottom: none;">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
										<th id="bl_pub_date_filter" style="border-bottom: none; padding: 0;"></th>
									</tr>
									<tr style="height: 20px;"></tr>
									<tr>
										<th id="bl-s1" scope="col"><b>Amount of Budget Lines:</b> <span></span></th>
										<th id="bl-s2" scope="col"><b>Total Budgetline Value:</b> <span></span></th>
									</tr>
								</thead>
								<tbody>
								</tbody>
							</table>
						</div>
						<div class="col-7">
							<canvas id="blChart" height="200" style="width:100%; height:200px;"></canvas>
						</div>
					</div>
					<div class="table mb-5">
						<table width="100%" class="db-table mb-3 mt-2" id="budglines">
							<thead>
								<tr>
									<th scope="col"></th>
									<th scope="col">Budget Line</th>
									<th scope="col">Budget Line Title</th>
									<th scope="col">Funding Type</th>
									<th scope="col">First Fiscal Year</th>
									<th scope="col">Fiscal Year 1 Amount</th>
									<th scope="col">Total Budget Value</th>
								</tr>
							</thead>
							<tbody>
							</tbody>
						</table>
					</div>
					
					<div class="row">
						<div class="col-5">
							<h4>Commitments</h4>
							<table class="table-sm stats-table" width="100%">
								<thead>
									<tr>
										<th class="text-left px-0" data-content="See commitment info published on specific date." style="border-bottom: none;">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
										<th id="comm_pub_date_filter" style="border-bottom: none; padding: 0;"></th>
									</tr>
									<tr style="height: 20px;"></tr>
									<tr>
										<th id="comm-s1" scope="col"><b>Amount of Budget Lines:</b> <span></span></th>
										<th id="comm-s2" scope="col"><b>Total Budgetline Value:</b> <span></span></th>
									</tr>
								</thead>
								<tbody>
								</tbody>
							</table>
						</div>
						<div class="col-7">
							<canvas id="commChart" height="200" style="width:100%; height:200px;"></canvas>
						</div>
					</div>
					<div class="table mb-5">
						<table width="100%" class="db-table mb-3 mt-2" id="commitments">
							<thead>
								<tr>
									<th scope="col"></th>
									<th scope="col">Budget Line</th>
									<th scope="col">Budget Line Description</th>
									<th scope="col">Funding Type</th>
									<th scope="col">Total Commitment Value</th>
									<th scope="col">First Fiscal Year</th>
									<th scope="col">Fiscal Year 1 Amount</th>
									<th scope="col">Fiscal Year 2 Amount</th>
									<th scope="col">Fiscal Year 3 Amount</th>
									<th scope="col">Fiscal Year 4 Amount</th>
									<th scope="col">Fiscal Year 5 Amount</th>
								</tr>
							</thead>
							<tbody>
							</tbody>
						</table>
					</div>
				</div>
			</div>
		</div>

		<div class="container">
			<div class="row my-4">
				{{-- One shell, from the shared provenance component. This markup was
				     hand-rolled on fifteen views, each with its own per-page fetch. --}}
				<x-db.data-provenance mode="scoped" :datasets="$datasets" :statUrl="$tblStatsUrl" scope-label="project type" id="prjTypeADs" />
			</div>
		</div>

	</div>
	<script>
		var datatable = null
		var blTable = null
		var commTable = null
		var colors = ['#1f5673', '#759FBC', '#90C3C8', '#B9B8D3', '#463730']
		var datasets = {!! json_encode(array_values($datasets)) !!}

		$(document).ready(function() {
			
			datatable = $('#project_type_data').DataTable({
				data: {!! json_encode($data) !!},
				deferRender: true,
				dom: '<"toolbar prjtype"<"row">>rtip',
				columns: [
					{data: 'pubdate', visible: false},
					// ⚠ `/projects/categories/…`, the live route. `/capital/categories/…`
					// is a legacy path; the category page is where a project COUNT for
					// this work belongs, because it is the one dimension the spine and
					// the strategy share (138 vs 186 values, 128 in common).
					// ⚠⚠ A CATEGORY THAT IS REALLY A FUNDING TYPE IS NOT LINKED, AND IS
					// NOT PRINTED AS A CATEGORY. Two of the eight `capitalstrategy`
					// vintages publish `City`/`Federal`/`State`/`Private` in the
					// Ten-Year Plan Category column — 533 of 2,255 rows — and this cell
					// linked them to `/projects/categories/city`, a page built from a
					// funding type. Those rows keep their AMOUNTS (correct on 20250116)
					// and lose only the label they do not have.
					{data: function (r) {
							var c = r['category']
							if (['City','Federal','State','Private'].indexOf(c) !== -1)
								return '<span class="db-muted">Not published</span>'
							return '<a href="/projects/categories/' + r['category-slug'] + '">' + c + '</a>'
						},
						type: 'html'
					},
					{data: 'fundingsource'},
					{data: function (r) { return toFin(r['year1amount'] * 1000) }, type: 'html'},
					{data: function (r) { return toFin(r['year10total'] * 1000) }, type: 'html'},
                ],

				initComplete: function () {
					this.api().columns([0]).every(function (c,a,i) {
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- Published Date -</option></select>')
							//.appendTo($('div.toolbar.prjtype'))
							.appendTo($('#pub_date_filter'))
							.on('change', function () {
								var val = $(this).val()
								column
									.search(val ? val : '', false, false)
									.draw();
							});

						var tt = []
						dd = column.data()

						column.data().each(function (d, j) {
							d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
							tt.push(d)
						})
						tt = [...new Set(tt)]

						tt.sort().forEach(function (d, j) {
							select.append('<option value="'+d+'">'+toDashDate(d)+'</option>')
						});

						setTimeout(function(){
							select.val(tt[tt.length-1]).trigger('change')
						}, 700);

					});
					
				}
			});
			

			// chart bl
			
			var canvas1 = document.getElementById("blChart");
			
			var config1 = {
				type: 'line',
				data: {
					labels: [],
					datasets: []
				},
				options: {
					responsive: false,
				  elements: { 
					point: {
					  radius: 4,
					  hitRadius: 3,
					  hoverRadius: 3
					} 
				  },
				  plugins: {
					  legend: {
						display: true,
						position: 'top',
						align: 'end',
						labels: {boxHeight: 2},
						usePointStyle: true,
					  },
					  tooltip: {
						backgroundColor: 'rgba(255, 255, 255, 0.9)',
						сolor: 'black',
						displayColors: false,
						bodyFontSize: 14,
						callbacks: {
						  label: function(tooltipItems, data) { 
							return '$' + tooltipItems.formattedValue;
						  },
						  title: function(tooltipItems, data) { 
							return '';
						  },
						  labelTextColor: function(context) {
							return '#444';
						  }
						}
					  },
				  },
				  scales: {
					x: {
					  display: true,
					  grid: {display: false},
					},
					y: {
					  display: true,
					  position: 'left',
					  grid: {display: false},
					  beginAtZero: true,
					  ticks: {
						callback: function(value, index, ticks) {
							return '$' + Chart.Ticks.formatters.numeric.apply(this, [value, index, ticks]);
						}
					  }
					},
					y1: {
					  display: true,
					  position: 'right',
					  grid: {display: false},
					  beginAtZero: true,
					}
				  }
				},
			};
			window.chart1 = new Chart(canvas1, config1);
			
			
			// blTable 
			
			blTable = $('#budglines').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $budg_lines_url !!}", cb);
			    },
				deferRender: true,
				dom: '<"toolbar blines"><"blstats">rtip',
				columns: [
					{data: 'pubdate', visible: false},
					{data: function (r) {
							return '<a href="/capital/budget-lines/' + r['budgline'] + '">' + r['budgline'] + '</a>'
						},
						type: 'html'
					},
					{data: 'budglinename'},
					{data: 'ftype'},
					{data: 'year1'},
					{data: function (r) { return toFin(r['year1amount']) }},
					{data: function (r) { return toFin(r['totalbudgetvalue']) }},
					{data: null, visible: false},
                ],

				initComplete: function () {
					this.api().columns([0]).every(function (c,a,i) {
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- Published Date -</option></select>')
							//.appendTo($('div.toolbar.blines'))
							.appendTo($('#bl_pub_date_filter'))
							.on('change', function () {
								var val = $(this).val()
								column
									.search(val ? val : '', false, false)
									.draw();
								var vv = blTable.column(6, {search: 'applied'}).data()
								$('#bl-s1 span').text(vv.length)
								$('#bl-s2 span').text(toFin(vv.reduce( function (a, b) {
									return a + parseInt(b.replace(/[\$,]/gi, ''));
								}, 0)))
								
								//console.log(vv, cc, ss);

							});

						var tt = []
						dd = column.data()

						column.data().each(function (d, j) {
							d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
							tt.push(d)
						})
						tt = [...new Set(tt)]

						tt.sort().forEach(function (d, j) {
							select.append('<option value="'+d+'">'+toDashDate(d)+'</option>')
						});

						setTimeout(function(){
							select.val(tt[tt.length-1]).trigger('change')
						}, 700);

					});
					
					var chartdd = this.api().columns([7]).data()[0].reduce(function (a, b) {
						a[b['pubdate']] = a[b['pubdate']] ?? {'count': 0, 'sum': 0}
						a[b['pubdate']]['count'] += 1
						a[b['pubdate']]['sum'] += b['totalbudgetvalue']
						a[b['pubdate']]['pubdate'] = b['pubdate']
						return a
					}, {})
					blChartUpdate(chartdd, window.chart1)
				}
			});

			
			// chart comm
			
			var canvas2 = document.getElementById("commChart");
			
			var config2 = {
				type: 'line',
				data: {
					labels: [],
					datasets: []
				},
				options: {
					responsive: false,
				  elements: { 
					point: {
					  radius: 4,
					  hitRadius: 3,
					  hoverRadius: 3
					} 
				  },
				  plugins: {
					  legend: {
						display: true,
						position: 'top',
						align: 'end',
						labels: {boxHeight: 2},
						usePointStyle: true,
					  },
					  tooltip: {
						backgroundColor: 'rgba(255, 255, 255, 0.9)',
						сolor: 'black',
						displayColors: false,
						bodyFontSize: 14,
						callbacks: {
						  label: function(tooltipItems, data) { 
							return '$' + tooltipItems.formattedValue;
						  },
						  title: function(tooltipItems, data) { 
							return '';
						  },
						  labelTextColor: function(context) {
							return '#444';
						  }
						}
					  },
				  },
				  scales: {
					x: {
					  display: true,
					  grid: {display: false},
					},
					y: {
					  display: true,
					  position: 'left',
					  grid: {display: false},
					  beginAtZero: true,
					  ticks: {
						callback: function(value, index, ticks) {
							return '$' + Chart.Ticks.formatters.numeric.apply(this, [value, index, ticks]);
						}
					  }
					},
					y1: {
					  display: true,
					  position: 'right',
					  grid: {display: false},
					  beginAtZero: true,
					}
				  }
				},
			};
			window.chart2 = new Chart(canvas2, config2);
			

			// commTable
			
			commTable = $('#commitments').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $prj_commitments_url !!}", cb);
			    },
				deferRender: true,
				dom: '<"toolbar comms"><"commstats">rtip',
				columns: [
					{data: 'pubdate', visible: false},
					{data: function (r) {
							return '<a href="/capital/budget-lines/' + r['budgline'] + '">' + r['budgline'] + '</a>'
						},
						type: 'html'
					},
					{data: 'budglinedesc'},
					{data: 'ftype'},
					{data: function (r) { return toFin(r['totalcommvalue']) }},
					{data: 'year1'},
					{data: function (r) { return toFin(r['year1amount'] * 1000) }},
					{data: function (r) { return toFin(r['year2amount'] * 1000) }},
					{data: function (r) { return toFin(r['year3amount'] * 1000) }},
					{data: function (r) { return toFin(r['year4amount'] * 1000) }},
					{data: function (r) { return toFin(r['year5amount'] * 1000) }},
					{data: null, visible: false},
                ],

				initComplete: function () {
					this.api().columns([0]).every(function (c,a,i) {
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- Published Date -</option></select>')
							//.appendTo($('div.toolbar.comms'))
							.appendTo($('#comm_pub_date_filter'))
							.on('change', function () {
								var val = $(this).val()
								column
									.search(val ? val : '', false, false)
									.draw();
								var vv = commTable.column(4, {search: 'applied'}).data()
								$('#comm-s1 span').text(vv.length)
								$('#comm-s2 span').text(toFin(vv.reduce( function (a, b) {
									return a + parseInt(b.replace(/[\$,]/gi, ''));
								}, 0)))
								
								//console.log(vv, cc, ss);

							});

						var tt = []
						dd = column.data()

						column.data().each(function (d, j) {
							d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
							tt.push(d)
						})
						tt = [...new Set(tt)]

						tt.sort().forEach(function (d, j) {
							select.append('<option value="'+d+'">'+toDashDate(d)+'</option>')
						});

						setTimeout(function(){
							select.val(tt[tt.length-1]).trigger('change')
						}, 700);

					});
					
					var chartdd = this.api().columns([11]).data()[0].reduce(function (a, b) {
						a[b['pubdate']] = a[b['pubdate']] ?? {'count': 0, 'sum': 0}
						a[b['pubdate']]['count'] += 1
						a[b['pubdate']]['sum'] += b['totalcommvalue']
						a[b['pubdate']]['pubdate'] = b['pubdate']
						return a
					}, {})
					commChartUpdate(chartdd, window.chart2)
				}
			});


		});

		function blChartUpdate(dd, chartObj) {
			var datasets = [{
						label: 'Amount of Budget Lines',
						data: [],
						fill: false,
						borderColor: colors[0],
						borderWidth: 2,
						pointBackgroundColor: 'transparent',
						pointBorderColor: '#CCCCCC',
						pointBorderWidth: 3,
						pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
						pointHoverBorderWidth: 6,
						tension: 0.1,
						datalabels: {display: false},
						yAxisID: 'y1',
					},
					{
						label: 'Total Budget Line Value',
						data: [],
						fill: false,
						borderColor: colors[1],
						borderWidth: 2,
						pointBackgroundColor: 'transparent',
						pointBorderColor: '#CCCCCC',
						pointBorderWidth: 3,
						pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
						pointHoverBorderWidth: 6,
						tension: 0.1,
						datalabels: {display: false},
						yAxisID: 'y',
					}]
			var labels = []
			//console.log(dd)
			Object.values(dd).forEach(function (d, i) {
				labels.push(toDashDate(d['pubdate']).replace(/<[^>]+>/g, ''))
				datasets[0]['data'].push(d['count'])
				datasets[1]['data'].push(d['sum'])
			})
			
			chartObj.data.labels = labels
			chartObj.data.datasets = datasets
			chartObj.update()			
		}

		
		function commChartUpdate(dd, chartObj) {
			var datasets = [{
						label: 'Amount of Commitments',
						data: [],
						fill: false,
						borderColor: colors[0],
						borderWidth: 2,
						pointBackgroundColor: 'transparent',
						pointBorderColor: '#CCCCCC',
						pointBorderWidth: 3,
						pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
						pointHoverBorderWidth: 6,
						tension: 0.1,
						datalabels: {display: false},
						yAxisID: 'y1',
					},
					{
						label: 'Total Commitment Value',
						data: [],
						fill: false,
						borderColor: colors[1],
						borderWidth: 2,
						pointBackgroundColor: 'transparent',
						pointBorderColor: '#CCCCCC',
						pointBorderWidth: 3,
						pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
						pointHoverBorderWidth: 6,
						tension: 0.1,
						datalabels: {display: false},
						yAxisID: 'y',
					}]
			var labels = []
			Object.values(dd).forEach(function (d, i) {
				labels.push(toDashDate(d['pubdate']).replace(/<[^>]+>/g, ''))
				datasets[0]['data'].push(d['count'])
				datasets[1]['data'].push(d['sum'])
			})
			
			chartObj.data.labels = labels
			chartObj.data.datasets = datasets
			chartObj.update()			
		}

		



	</script>
	<script type="application/ld+json">{!! json_encode($schema ?? []) !!}</script>
<style>
	#map_container #map {height: 800px !important;}
</style>
@endsection


