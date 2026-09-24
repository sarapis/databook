@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects Budget Lines." />
	<meta rel="canonical" href="{!! route('budgetLines') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/rowgroup/1.1.4/js/dataTables.rowGroup.min.js"></script>
	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>if(window.DBChart&&window.Chart)DBChart.apply(window.Chart);</script>

	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<style>
		select.filter {width: 46%;}
	</style>
	<script>
		var FAMILY_SLUGS = {!! json_encode(array_values($famSlugs ?? [])) !!}
		var table = null
		
		var data = {!! json_encode($data) !!}
		var colors = ['#1f5673', '#759FBC', '#90C3C8', '#B9B8D3', '#463730']

		$(document).ready(function() {
			table = $('#budgLines').DataTable( {
				pageLength: 20,
				deferRender: true,
				order: [[1, 'asc']],
				dom: '<"toolbar container-flex"<"row ml-4">>frtip',
				ajax: function (url, cb) {
					fapireq("{!! $dataUrl !!}", cb);
			    },
				columns: [
					{data: 'Published Date', visible: false},
					{data: function (r) {
							return '<a href="/projects/budget-lines/' + r['Budget Line'] + '">' + r['Budget Line'] + '</a>'
						},
						type: 'html'
					},
					// ⚠⚠ `Project Type Name`, NOT `wegov-prjtype-name`. The payload from
					// `/get/capitalbudget/bydate/recent` has never carried the second, so
					// this column was undefined and the rowGroup below put **all 749
					// rows under one "No group" header** — the family grouping this page
					// is built around was dead. Same renamed key that 500'd every
					// budget-line detail page.
					{data: 'Project Type Name', visible: false},
					{data: 'Budget Line Title', type: 'html'},
					{data: 'Funding Type', type: 'html'},
					{data: 'First Fiscal Year'},
					{data: function (r) { return toFin(r['Fiscal Year 4 Amount']) }, type: 'html'},
					{data: null, visible: false},
                ],
				rowGroup: {
					dataSrc: 'Project Type Name',
					// ⚠ The group header is the BUDGET-LINE FAMILY, and it links to that
					// family's own page — 39 values, project-level. Never to
					// `/projects/types`, which is the Ten-Year Strategy's 236-value work
					// type and shares only 5 names with this vocabulary, by coincidence.
					startRender: function (rows, group) {
						if (!group) return 'Not published'
						var slug = group.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')
						var label = group + ' <span class="db-muted">(' + rows.count() + ')</span>'
						// ⚠⚠ LINKED ONLY WHERE THE PAGE EXISTS, from the SERVED slug set.
						// This index's family names come from `capitalbudget` (41 values)
						// and the family pages from the spine (39); only 25 slugs match —
						// `PARKS` here is `Parks and Recreation` there. Linking all of them
						// would 404 on 39%, and a link landing on a 404 is worse than text.
						if (FAMILY_SLUGS.indexOf(slug) !== -1)
							label = '<a href="/projects/budget-lines/families/' + slug + '">' +
								group + '</a> <span class="db-muted">(' + rows.count() + ')</span>'
						return $('<tr/>').append($('<td colspan="99"/>').html(label))
					}
				},
				@if ($defSearch ?? null)
					search: {
						'search': '{{ $defSearch }}'
				    },
				@endif	

				initComplete: function () {
					this.api().columns([2,4]).every(function () {						// pubdate
						var tt = {2: 'Project Type Name', 4: 'Funding Type'}
						var column = this;
						var select = $('<select class="filter" id="filter-' + column[0][0] + '" aria-controls="budgLines"><option value="">- ' + $(column.header()).text() + ' -</option></select>')
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
							tt.push(d)
						})
						tt = [...new Set(tt)]

						tt.sort().forEach(function (d, j) {
							select.append( '<option value="'+d+'">'+d+'</option>' )
						});
					});

					this.api().columns([0]).every(function () {						// pubdate
						var column = this;
						var select = $('<select class="filter" style="width: 100%;" id="filter-' + column[0][0] + '" aria-controls="budgLines"><option value="">- Published Date -</option></select>')
							//.appendTo($('div.toolbar .row'))
							.appendTo($('#pub_date_filter'))
							.on('change', function () {
								var val = $.fn.dataTable.util.escapeRegex(
									$(this).val()
								);
								column
									.search(val ? val : '', false, false)
									.draw();
								graphsUpdate();
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
			
			
			var canvas1 = document.getElementById("byPrgTypeChart");

			var config1 = {
			  type: 'pie',
			  data: {
				  labels: [],
				  datasets: [{
					label: 'Dataset',
					data: [],
					fill: false,
					backgroundColor: (window.DBChart ? DBChart.palette.concat(DBChart.palette, DBChart.palette) : ['#162e51']),
					borderColor: 'rgba(0, 0, 0, 0.2)',
					hoverBorderColor: 'rgba(0, 0, 0, 0.7)',
					borderWidth: 1,
					hoverOffset: 3,
					datalabels: {
					  color: 'rgba(0, 0, 0, 0.8)',
					  align: 'center',
					  anchor: 'end',
					  //display: 'auto',
					  clip: false,
					  font: {
						  size: 12,
					  }
					}
				  }]
				},
				options: {
					layout: {
						autoPadding: true,
						padding: 5,
					},
					responsive: false,
					radius: '96%',
					showAllTooltips: true,
					onHover: function(evt, elements, chart) {
						if (elements.length) {
							pie_label_on('.byPrgTypeChart', elements[0].index)
						} else {
							pie_labels_off('.byPrgTypeChart')
						}
					},
					plugins: {
					  legend: {
						display: false,
					  },
					  tooltip: {
						enabled: false,
					  },
					  /*
					  datalabels: {
						formatter: function(value, context) {
						  var perc = (value / context.dataset.data.reduce((partialSum, a) => partialSum + a, 0) * 100).toFixed(1)
						  return `${context.chart.data.labels[context.dataIndex]}: ${value} (${perc} %)`
						}
					  }
					  */
					  
					},
				}
			}
			window.chart1 = new Chart(canvas1, config1)


			{{-- ⚠⚠ THE FUNDING-SOURCE PIE IS GONE (owner, 2026-09-11), AND SO IS ITS
			     CHART OBJECT. A `new Chart(null, …)` throws "can't acquire context
			     from the given item", and this whole `$(document).ready` block would
			     have gone with it — every function on the page undefined while the
			     page still returned 200, which is the failure mode this view has
			     already shipped once.
			     ⚠ `stats['byfund']` is still COMPUTED and still used: the line chart
			     beside it plots the same four sources across four fiscal years, so
			     the reducer stays and nothing about funding is actually lost — the
			     removed pie showed the first year's split, which is that chart's
			     2027 point. --}}
	
	
			// budgets dynamics by funding type
			
			var canvas3 = document.getElementById("ftChart");
			
			var config3 = {
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
					  {{-- ⚠ THE SAME FORMATTER THE PIE LEGENDS USE. The axis read
					       `$30,000,000,000` per tick — correct, and unreadable at 200px
					       tall beside legends that say `$5.66B`. `toFinShortK` already
					       emits its own `$`, so the old `'$' +` prefix must go with it or
					       the axis reads `$$30B`. --}}
					  ticks: {
						callback: function(value) { return toFinShortK(value) }
					  }
					}
				  }
				},
			};
			window.chart3 = new Chart(canvas3, config3);
	
			initPopovers();
		});

		function pie_labels_off(selector) {
			$(selector + ' .pie_legend li').removeAttr('class')
		}
		
		function pie_label_on(selector, i) {
			pie_labels_off(selector)
			$(selector + ` .pie_legend li[idx="${selector}_${i}"]`).attr('class', 'pie_label_h')
		}
		
		function pie_sectors_off(chart, selector) {
			chart.setActiveElements([{datasetIndex: 1, index: 0}])
			chart.update()
		}
		
		function pie_sector_on(chart, selector, i) {
			pie_sectors_off(chart, selector)
			var dd = [{datasetIndex: 0, index: parseInt(i)}]
			res = chart.setActiveElements(dd);
			chart.update()
		}
		
		function pieChartUpd(chart, selector, dd) {
			//$('#positionsChart').attr('width', 280)
			var s = 0
			if (dd.length == 0) {
				$(selector + ' .pie_legend').replaceWith('<p class="my-4 mx-3">No Positions to Display</p>')
				return
			}
			chart.data.labels = []
			chart.data.datasets[0].data = []
			dd.forEach(function (d, i) {
				const [label, value] = d
				chart.data.labels.push(label)
				chart.data.datasets[0].data.push(value)
				s += value
			})
			//chart.data.labels.forEach(function (l, i, ll) {
			l = chart.data.labels.length
			c = chart.data.datasets[0].backgroundColor.length
			$(selector + ' .pie_legend').text('')
			for (let i = 1; i <= l; i++) {
				if (i < 11) {
					var perc = (chart.data.datasets[0].data[l-i] / s * 100).toFixed(1)
					$(`<li idx="${selector}_${l-i}"><i class="bi bi-square-fill" style="color: ${chart.data.datasets[0].backgroundColor[(l-i) % c]};"></i>&nbsp;&nbsp;${chart.data.labels[l-i]}: ${toFinShortK(chart.data.datasets[0].data[l-i])} (${perc} %)</li>`).appendTo(selector + ' .pie_legend')
					console.log(selector + ' .pie_legend', perc)
				}
			}
			if (chart.data.labels.length > 10) {
				$('<li>...</li>').appendTo(selector + ' .pie_legend')
			}

			//$(selector + ' canvas').attr('width', 300)
			chart.update()
			
			$(selector + ' .pie_legend li').mouseover(function (evt) {
				var idx = $(this).attr('idx')
				pie_sectors_off(chart, selector)
				pie_sector_on(chart, selector, idx.split('_')[1])
			}).mouseout(function (evt) {
				pie_sectors_off(chart, selector)
			})
		}

		function graphsUpdate() {
			const tt = {'C': 'City', 'F': 'Federal', 'S': 'State', 'P': 'Private', 'E': 'City'}
			const vv = table.column(7, {search: 'applied'}).data()
			
			// ⚠⚠ `+ b['Fiscal Year 1 Amount']` WAS STRING CONCATENATION, AND IT BROKE
			// ALL THREE CHARTS ON THIS PAGE. `/get/capitalbudget/bydate/recent`
			// serves every amount as a STRING — `'129000'`, measured on all 749 rows
			// — so `0 + '129000'` is `'0129000'`, and 749 of those in a row build a
			// numeric string hundreds of digits long. The rendered symptoms were a
			// y-axis reading **$7E141**, both pie legends reading **"undefined
			// (NaN %)"**, and neither pie drawing a single slice.
			// ⚠ It cannot be fixed at the endpoint alone: the values reach this
			// reducer through DataTables' row objects, so the coercion belongs where
			// the arithmetic is. `Number(v) || 0` also absorbs '' and null, which the
			// old `?? 0` only caught for a MISSING key, never an empty string.
			const n = function (v) { return Number(v) || 0 }
			// ⚠⚠ AND THE FISCAL YEARS RAN BACKWARDS. `First Fiscal Year` is the FIRST
			// year of the budget line's four-year window, so FY1 belongs to that year
			// and FY2/3/4 to the three AFTER it. This mapped FY4 to `First - 3` and
			// FY1 to `First`, i.e. the window in reverse. Measured on the live
			// payload: `First Fiscal Year` is uniformly 2027 and the totals are
			// FY1 $29.1B, FY2 $21.3B, FY3 $19.1B, FY4 $15.9B — a declining forward
			// forecast, which the old mapping drew as a steep RISE into 2027 with
			// three flat years before it. The shape of the line was the exact
			// opposite of the data.
			var stats = vv.reduce( function (a, b) {
					t = tt[b['Funding Type']]
					const y0 = Number(b['First Fiscal Year'])
					a['byprj'][b['Project Type Name']] 	= (a['byprj'][b['Project Type Name']] ?? 0) + n(b['Fiscal Year 1 Amount'])
					a['byfund'][t] 						= (a['byfund'][t] ?? 0) + n(b['Fiscal Year 1 Amount'])
					a['byft4yr'][t][y0]					= (a['byft4yr'][t][y0] ?? 0) + n(b['Fiscal Year 1 Amount'])
					a['byft4yr'][t][y0 + 1]				= (a['byft4yr'][t][y0 + 1] ?? 0) + n(b['Fiscal Year 2 Amount'])
					a['byft4yr'][t][y0 + 2]				= (a['byft4yr'][t][y0 + 2] ?? 0) + n(b['Fiscal Year 3 Amount'])
					a['byft4yr'][t][y0 + 3]				= (a['byft4yr'][t][y0 + 3] ?? 0) + n(b['Fiscal Year 4 Amount'])
					return a
				}, {'byprj': {}, 'byfund': {}, 'byft4yr': {'City': {}, 'Federal': {}, 'State': {}, 'Private': {}}})
			stats = {
					'byprj': Object.entries(stats['byprj']).sort(([,a],[,b]) => a - b),
					'byfund': Object.entries(stats['byfund']).sort(([,a],[,b]) => a - b),
					'byft4yr': {
						'City': 		stats['byft4yr']['City'],
						'Federal': 		stats['byft4yr']['Federal'],
						'State': 		stats['byft4yr']['State'],
						'Private': 		stats['byft4yr']['Private'],
					}
				}

			pieChartUpd(window.chart1, '.byPrgTypeChart', stats['byprj'])
			ftChartUpd(window.chart3, stats['byft4yr'])
		}

		function ftChartUpd(chart, data) {
			var datasets = []
			var labels = {}
			var colors = {'City': '#1f5673', 'Federal': '#759FBC', 'State': '#90C3C8', 'Private': '#B9B8D3'}
			for (const [label, dd] of Object.entries(data)) {
				console.log(dd)
				if (dd) {
					labels = Object.keys(dd)
					datasets.push({
						label: label,
						data: Object.values(dd),
						fill: false,
						borderColor: colors[label],
						borderWidth: 2,
						pointBackgroundColor: 'transparent',
						pointBorderColor: '#CCCCCC',
						pointBorderWidth: 3,
						pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
						pointHoverBorderWidth: 6,
						tension: 0.1,
						datalabels: {display: false},
					})
				}
			}
			
			chart.data.labels = labels
			chart.data.datasets = datasets
			chart.update()			
		}

				
	</script>
<div class="inner_container">

	<div class="db-eyebrow mt-4">Projects</div>
	<h1 class="db-profile-title">Budget Lines</h1>
	<div class="row justify-content-center">
		<div class="col-md-9 my-4">
			<p class="lead">The Mayor submits an <a target="_blank" href="https://data.cityofnewyork.us/City-Government/Capital-Budget/46m8-77gv/about_data">Executive Capital Budget</a> for approval by the City Council every year. That budget contains budget lines that are used to fund specific capital projects.</p>
		</div>
		<div class="col-md-3 mt-2" id="org_summary">
			<table class="table-sm stats-table" width="100%">
				<thead>
					<tr>
					<th scope="col" width="50%" class="text-center px-0" data-content="See the project info published on specific dates.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px; position:relative;"></i></small></th>
					<th scope="col" width="50%" id="pub_date_filter"></th>
					</tr>
				</thead>
			</table>
		</div>
	</div>

	<div class="container">
	
		<div class="row justify-content-center mb-5">
			<div class="col-md-5" id="costChartOuter">
				{{-- ⚠ THE TITLE SAID "Annual 1st Year Budget Total" while the chart plots
				     FOUR fiscal years — the budget line's whole window, FY1 through FY4.
				     "1st Year" belongs to the two PIE charts beside it, which really do
				     plot the first year only. --}}
				<h4 class="mb-2" data-content="City Exempt (C) and City Not Except (E) are combined in the chart.">Budget by Fiscal Year and Source <i class="bi bi-question-circle-fill ml-1" style="top:-1px; position:relative; font-size:.8rem;"></i></h4>
				<canvas id="ftChart" height="200" style="width:100%; height:200px;"></canvas>
			</div>
			
			{{-- ⚠⚠ `col-md-7`, NOT `col`, AND THE LEGEND/PIE PAIR IS A FLEX ROW —
			     both so this chart stays on ONE line beside the fiscal-year chart.
			     It used to be an auto-width `col` sharing 7/12 with the
			     funding-source pie, so it computed to ~400px; the legend is
			     inline-block with no width and its longest row is "WATER MAINS,
			     SOURCES AND TREATMENT: $1.06B (3.6 %)", which does not fit beside a
			     285px canvas in 400px. The pie therefore wrapped BELOW its own
			     legend, which is what the owner reported. Flex makes it structural:
			     the legend takes what is left and the canvas keeps its declared
			     285px rather than the two competing for an inline-block line box.
			     ⚠ `flex-wrap: wrap` and `min-width: 0` are the narrow-screen half —
			     at 390px there is no room for both, and the pair must wrap rather
			     than force the page to scroll sideways. This view has already
			     shipped a 40px sideways scroll from exactly this row.
			     ⚠⚠ `position: absolute` WITH NO POSITIONED ANCESTOR RESOLVES AGAINST
			     THE VIEWPORT, so the canvas's old `right: -40px` put it 40px past
			     the window rather than past its column, and BOTH pies landed in the
			     identical box — measured at 1440 AND 390, 285x200, 100% overlap, one
			     chart never visible. It flows in the layout now; do not re-introduce
			     positioning here. --}}
			<div class="col-md-7 byPrgTypeChart">
				<h4 class="mb-2">1st Year Budget by Project Type</h4>
				<div style="display: flex; flex-wrap: wrap; align-items: flex-start; gap: 12px;">
					<div style="flex: 1 1 300px; min-width: 0;">
						<ul class="pie_legend">
						</ul>
					</div>
					<div style="flex: 0 0 285px; max-width: 100%;">
						<canvas id="byPrgTypeChart" height="200" width="285" style="width:100%; height:200px;"></canvas>
					</div>
				</div>
			</div>
			{{-- ⚠ THE FUNDING-SOURCE PIE WAS HERE and is removed (owner,
			     2026-09-11). Nothing about funding is lost: the chart to the left
			     plots the same four sources — City / Federal / State / Private,
			     bucketed from `Funding Type` by the same reducer — across four
			     fiscal years, and the removed pie showed the FIRST year's split,
			     which is that chart's 2027 point. --}}
		</div>

		<div class="row justify-content-center">
			<div class="col-md-12 organization_data">
                <div class="table-responsive">
                    <table id="budgLines" class="db-table display table" style="width:100%; padding-top: 2px;">
                        <thead>
                            <tr>
								<th scope="col"></th>
								<th scope="col">Budget Line ID</th>
								<th scope="col">Project Type Name</th>
								<th scope="col">Budget Line Title</th>
								<th scope="col">Funding Type</th>
								<th scope="col">First Fiscal Year</th>
								<th scope="col">4 Year Budget Value</th>
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
