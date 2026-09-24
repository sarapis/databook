@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects strategy | {{ $catName }}" />
	<meta rel="canonical" href="{!! route('prjStratCategory', ['cslug' => $cslug]) !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>

	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>if(window.DBChart&&window.Chart)DBChart.apply(window.Chart);</script>
	<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0"></script>

	<script>
		{{-- ⚠ The map's scope, handed to the one owner in `script.js`. Built by the
		     CONTROLLER from the same scope the list request uses, so the map and
		     the table cannot answer one question two ways. --}}
		capMap.init('{!! $capGeojsonUrl ?? '' !!}');

		function details(r) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
			  {{-- ⚠ `?? []`: the expander config is OPTIONAL — a dataset contract without
			     one is legitimate (the spine table has no expander), and a missing
			     key must never 500 the page. Same shape as the budget-line defect. --}}
			  @foreach ((array)($details['details'] ?? []) as $h=>$f)
				'<tr><td>{{ $h }}:</td><td>' + {!! $f !!} + '</td></tr>' +
			  @endforeach
			'</table>';
		}

		var datatable = null
		var catdata = {!! json_encode($data) !!}
		var datasets = {!! json_encode(array_values($datasets)) !!}
		
		$(document).ready(function() {

			// top data filter
			
			var select = $('<select class="filter" id="filter-top" style="width: 100%;"><option value="" selected>-Published Date-</option></select>')
				.appendTo($("#pub_date_filter"))
				.on('change', function () {
					var val = $(this).val()
					catUpdate(val);
				})
			select.wrap('<div class="drop_dowm_select col"></div>');
			var tt = []
			catdata.forEach(function (d, j) {
				tt.push(d['Published Date'])
			})
			tt = [...new Set(tt)]
			tt.sort().forEach(function (d, j) {
				select.append('<option value="'+d+'">'+toDashDate(d)+'</option>')
			})
			setTimeout(function(){
				select.val(tt[tt.length-1]).trigger('change')
			}, 700)
			
			
			// chart
			
			var canvas1 = document.getElementById("costChart");
			
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
					  grid: {display: false},
					  beginAtZero: true,
					  ticks: {
						callback: function(value, index, ticks) {
							return '$' + Chart.Ticks.formatters.numeric.apply(this, [value, index, ticks]);
						}
					  }
					}
				  }
				},
			};
			window.chart1 = new Chart(canvas1, config1);
			
			
			
			datatable = $('#myTable').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $prjsUrl !!}", cb);
			    },
				buttons: [{
                    extend: 'colvis',
                    "className": 'btn_eyeicon',
                    columnText: function ( dt, idx, title ) {
                        return (idx+1)+': '+(title ? title : 'details');
                    }
                }],
				deferRender: true,
				dom: '<"toolbar container-flex"<"row">>Bfrtip',
				columns: [
                    @if ($details['detFlag'])
                        {
                            "className": 'details-control',
                            "orderable": false,
                            "data":  null,
                            "defaultContent": ''
                        },
                    @endif
                    @foreach ($details['flds'] as $i=>$f)
                        @if ($i > 0)
                            ,
                        @endif
                        {
                        data: {!! $f !!},
						@if (preg_match('~^function ~i', $f))
							type: 'html',
                        @endif
                        @if ($details['visible'][$i])
                            visible: true
                        @else
                            visible: false
                        @endif
                        }
                    @endforeach
					,
                    {
                        className: 'record',
                        data:  null,
                        defaultContent: null,
                        visible: false,
                        searchable: false
                    }
                ],
				// ⚠⚠ THIS TEST WAS `data.GEO_JSON != ''`, AND ON A SPINE ROW THAT
				// KEY IS UNDEFINED — `undefined != ''` is TRUE, so every row was
				// marked as located, including the majority the City publishes no
				// location for. The set comes from the geojson the map actually
				// received, so the marker and the pins cannot disagree.
				createdRow: function(row, data, dataIndex) {
					if (capMap.isLocated(data && data.id)) {
						$(row).addClass('have_coords');
					}
				}

				@if ($details['filters'])
					,
					initComplete: function () {
						this.api().columns([{{ $details['fltsCols'] }}]).every(function (c,a,i) {
							var delim = {!! json_encode($details['fltDelim']) !!};
							var column = this;
							var select = $('<select class="filter" id="filter-' + column[0][0] + '" name="filter-' + column[0][0] + '" aria-controls="myTable"><option value="" selected>- ' + $(column.header()).text() + ' -</option></select>')
								.appendTo($("div.toolbar .row"))
								.on('change', function () {
									var val = $(this).val()
									column
										.search(val ? val : '', false, false)
										.draw();
								});
							select.wrap('<div class="drop_dowm_select col"></div>');
							//$('div.toolbar').insertAfter('#myTable_filter');

							var tt = []
							dd = column.data()

							column.data().each(function (d, j) {
								d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
								if (c in delim && typeof d == 'string') {
									d.split(delim[c]).forEach(function (v, k) {
										tt.push(v)
									})
								}
								else
									tt.push(d)
							})
							tt = [...new Set(tt)]

							tt.sort().forEach(function (d, j) {
								select.append('<option value="'+d+'">'+d+'</option>')
							});
						});


						{{-- ⚠⚠ GATED ON THE CONTRACT — AND UNGATED THIS BLOCK WAS FILTERING
						     EVERY CATEGORY PAGE TO ONE ARBITRARY AGENCY. Invariant 10: a
						     control indexed on a COLUMN POSITION must be gated on the
						     contract, because the position's MEANING moves. `columns([1])`
						     was `Publication Date` under `capitalprojectsdollarscomp`
						     (whose contract declares a details expander, so `get()`
						     prepends a column); on the `spine` contract this page has read
						     since it was migrated, column 1 is `Agency`. So it built a
						     dropdown of agency names, and the `option:last-child`
						     auto-select below picked one.

						     Measured on the rendered pages, 2026-09-10:

						       Neighborhood Parks, Playgrounds and Ballfields
						           "Showing 1 to 3 of 3 (filtered from 1,036)"  — DOT
						       Large, Major and Regional Park Reconstruction
						           "Showing 1 to 1 of 1 (filtered from 367)"    — NYPD
						       Routine Reconstruction
						           "Showing 1 to 10 of 409 (filtered from 447)" — H+H

						     A PARKS category page showing ONE project, and that project
						     the Police Department's. The payload, the headers and the rows
						     were correct throughout — only the visible count and the
						     selection were wrong, which is why a row count could not see
						     it. Identical to the org capital tab's "Showing 1 to 1 of 1
						     (filtered from 2,798)".
						     ⚠ The auto-select below goes with it: `#filter-1` is ALSO the
						     id the general filter loop gives column 1, so gating this
						     block alone would leave the agency dropdown being picked from.
						     `spine` declares no `pubdate_filter`, so neither is emitted. --}}
						@if ($details['pubdate_filter'] ?? null)
						/* pub_date filter */
						this.api().columns([{{ array_keys($details['pubdate_filter'])[0] }}]).every(function (c,a,i) {
							var delim = {!! json_encode($details['fltDelim']) !!};
							var column = this;
							var select = $('<select class="filter mt-1" style="width:100%;" id="filter-' + column[0][0] + '" name="filter-' + column[0][0] + '" aria-controls="myTable"><option value="" selected>- ' + $(column.header()).text() + ' -</option></select>')
								.appendTo($("#pub_date_prj_filter"))
								.on('change', function () {
									var val = $(this).val()
									column
										.search(val ? val : '', false, false)
										.draw();
									loadFinStat();
								});
							select.wrap('<div class="drop_dowm_select col"></div>');
							$('div.toolbar').insertAfter('#myTable_filter');

							var tt = []
							dd = column.data()

							column.data().each(function (d, j) {
								d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
								if (c in delim && typeof d == 'string') {
									d.split(delim[c]).forEach(function (v, k) {
										tt.push(v)
									})
								}
								else
									tt.push(d)
							})
							tt = [...new Set(tt)]

							tt.sort().forEach(function (d, j) {
								select.append('<option value="'+d+'">'+d+'</option>')
							});
						});

						setTimeout(function(){
							$('#filter-{{ array_keys($details['pubdate_filter'])[0] }}').find('{{ array_values($details['pubdate_filter'])[0] }}').prop('selected',true).trigger('change')
						}, 500);
						@endif
						
						setTimeout(function(){
							initPopovers();
						}, 1000);


						$("div.toolbar .row").append('<button id="map_button" class="btn map_btn col" style="margin:0 20px 0 10px; z-index: 10; max-width: 40px;" onclick="toggleMap();"><img src="/img/map_location.png" alt=""></button>');

						@foreach ($details['filters'] as $i=>$v)
							@if ($v)
								setTimeout(function(){
									$('#filter-{{ $i }}').find('[value*="{!! $v !!}"]').prop('selected',true).trigger('change')
								}, 500 + 1000 * {{ $i }});
							@endif
						@endforeach
						
					}
				@endif

				@if ($details['order'])
					,
					order: {!! json_encode($details['order']) !!}
				@endif
			});

			$('a.toggle-vis').on('click', function (e) {
				e.preventDefault();
				var column = datatable.column($(this).attr('data-column'));
				column.visible(!column.visible());
			});

			$('#myTable tbody').on('click', 'td.details-control', function () {
				var tr = $(this).closest('tr');
				var row = datatable.row(tr);

				if (row.child.isShown()) {
					row.child.hide();
					tr.removeClass('shown');
                    tr.next('tr').removeClass('child-row');
				}
				else {
					row.child(details(row.data())).show();
					tr.addClass('shown');
                    tr.next('tr').addClass('child-row');
					initPopovers();
				}
			});

			//$('#myTable_length label').html($('#myTable_length label').html().replace(' entries', ''));

			// ⚠ Redraws the map from the SERVED features intersected with the rows
			// the table is currently showing, so a client-side search moves both.
			// (This comment said "draws projects from GEO_JSON field", which
			// stopped being true when the table moved to the spine.)
			datatable.on('draw', function () {
				drawProjects('current');
				capMap.markLocated();
				// ⚠⚠ THE TILES' ONLY CALLER USED TO LIVE INSIDE THE PUBLICATION-DATE
				// GATE, and gating that block left all five reading `&nbsp;` — the
				// org capital tab's eight-blank-tiles defect, reproduced here in the
				// same change that removed the filter. "When a contract changes, ask
				// what CALLED the code the old contract fed, not just what read it."
				// Caught by `verify_retired_sweep`, which counts blank `prj_stat`
				// cells; 5 of 5 blank, 0 uncaught JS, 0 requests.
				// ⚠ `draw` is also the RIGHT trigger, not merely an available one:
				// `loadFinStat()` sums the rows matching the table's current search,
				// so the tiles are meant to move with it.
				loadFinStat();
            });
			
			$('#myTable tbody').on('click', 'td:not(.details-control)', function () {
				var mapIsActive = !$('#map_container').attr('style')
				if (!mapIsActive) 
					return;
				var tr = $(this).closest('tr');
				var row = datatable.row(tr);
				var r = row.data()
				// ⚠ Looked up in the SERVED features by the same agency-concatenated
				// id the table renders, because the spine row has no geometry on it.
				// A project the City publishes no location for zooms nowhere, which
				// is the honest answer rather than a jump to the last click.
				capMap.zoomTo(r && r.id);
			})
			
			// makes sortable html fields like 9.4 years late, $25,764 over, $64.2M over
			$.fn.dataTable.ext.type.order['html-pre'] = function (data) {
				var d = data.replace(/>-</g, '>0<');
				d = d.replace(/<span class="(bad)"[^>]*>/g, '-');
				d = d.replace(/[,$]|years|late|<[^>]+>|earl\S+|%/g, '');
				d = d.replace(/NA|NaN|on time/g, '0');
				//console.log(data, d)
				m = 1
				for (const[rg, tmpM] of [[/K$/g, 1000], [/M$/g, 1000000], [/B$/g, 1000000000]]) {
					if (d.match(rg)) {
						m = tmpM;
						d = d.replace(rg, '');
					}
				}
				d = d.match(/[-\d\.]+/g) ? parseFloat(d) * m : d;
				//console.log(data, d);
				return d;
			};
			

		});


		function toggleMap() {
			var isActive = !$('#map_container').attr('style')
			var cc = [{{ $details['hide_on_map_open'] }}];
			if (isActive) {
				$('#map_button').show()
				$('#data_container').attr('class', 'col')
				$('.toolbar ').show()
				$('#map_container').hide()
				$('#myTable').dataTable().api().columns(cc).every(function () {
					this.visible(true);
				});
			} else {
				$('#map_button').hide()
				$('#data_container').attr('class', 'col col-6')
				$('#map_container').show()
				projectsMapInit();
				$('#myTable').dataTable().api().columns(cc).every(function () {
					this.visible(false);
				});
				// ⚠⚠ THIS REPLACES A BARE `setTimeout(…, 3000)`, which is a GUESS
				// about the style load rather than a synchronisation with it. `load`
				// may already have fired by the time this binds, so `loaded()`
				// covers that; mapbox no-ops a late `on('load')` handler.
				if (typeof map !== 'undefined') {
					if (map.loaded && map.loaded()) capMap.ready();
					map.on('load', function () { capMap.ready(); });
				}
				capMap.draw('all');
			}
			initPopovers();			
		}
		
		
		// ⚠⚠ THESE TILES WERE COMPUTED FROM THE RETIRED SERIES' COLUMN NAMES —
		// `BUDG_ORIG`, `BUDG_CURR`, `BUDG_DIFF`, `DURATION_DIFF`, `START_DIFF`,
		// `END_DIFF` — so pointing the table at the spine made every one throw
		// `Cannot read properties of undefined (reading 'replace')`.
		// ⭐ AND THE ROWS STILL RENDERED. The table showed all 447 projects with
		// correct money while the tiles above it were blank and the console threw
		// on every filter change. A 200 and a row count both passed; only reading
		// the rendered page found it.
		//
		// ⚠⚠ `Amount Over Budget` IS DELETED, NOT REPOINTED. It is the label this
		// section documents as carrying TWO definitions, and the standing rule is
		// to drop it rather than preserve the defect under new data — the same
		// call `/projects` made when it lost its four globStats tiles.
		// ⚠ The three lateness tiles go too, for a different reason: they compared
		// an ORIGINAL against a CURRENT date, and the spine carries a forecast
		// HISTORY per project rather than one "original" per row. Inventing one
		// here would publish a lateness figure the City never stated. The
		// per-project forecast movement is on the profile, where the series shows.
		//
		// ⚠ Still computed from the FILTERED rows, so the tiles keep tracking the
		// table. `rows({search:'applied'}).data()` returns row OBJECTS.
		function loadFinStat() {
			var rows = datatable.rows({search: 'applied'}).data()
			var n = 0, inPlan = 0, planned = 0, spent = 0, sched = 0
			rows.each(function (b) {
				n += 1
				if (b['in_current_plan']) inPlan += 1
				// ⚠ null is "NYC publishes no such figure", not zero — skipped rather
				// than added, so a category of unpublished figures reads as
				// unpublished rather than as $0.
				if (b['planned_total_usd'] != null) planned += parseFloat(b['planned_total_usd']) || 0
				if (b['spent_total_usd'] != null)   spent   += parseFloat(b['spent_total_usd']) || 0
				if (b['forecast_completion']) sched += 1
			})
			var stats = {'#projects_no': n, '#in_plan_no': inPlan,
			             '#planned_cost': planned, '#spent_cost': spent,
			             '#sched_no': sched}
			for (let sel in stats) {
				var v = stats[sel] ?? '-'
				// ⚠⚠ MULTIPLIER 1, NOT 1000. The old tiles used `toFin(v, 1000)`
				// because the retired series published THOUSANDS; the spine publishes
				// USD, and reusing that multiplier renders a $385M category as $385B.
				if (['#planned_cost', '#spent_cost'].includes(sel) && v !== '-') {
					$(sel).text(toFinShortK(v, 1))
					$(sel).attr('data-content', toFin(v, 1))
				}
				else
					$(sel).text(v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","))
			}
			setTimeout(function(){
				initPopovers();
			}, 1000);
		}
		
		
		{{-- ⚠⚠ THIS BODY READ `r['GEO_JSON']` OFF THE TABLE, AND THE TABLE HAS
		     BEEN THE SPINE SINCE THIS PAGE WAS MIGRATED — a column the spine does
		     not serve. Measured on the rendered page 2026-09-10 by reading
		     `map.getSource('route')._data.features.length`, the map drew
		     **0 features** while its table held 447 projects (`routine-reconstruction`)
			     and 1,036 (`neighborhood-parks-...`). Container, style load
		     and console were all clean, so a status code, a row count and a
		     JS-error check every one of them passed.
		     ⚠ `capMap` in `script.js` is the ONE owner now; this page held one of
		     three byte-identical copies. --}}
		function drawProjects(pages) {	// 'all',     'current'
			capMap.draw(pages);
		}
		
		function catUpdate(date) {
			var datasets = []
			var labels = {}
			//var colors = {'City': 'rgba(59, 129, 135, 0.85)', 'Federal': 'rgba(0, 156, 167, 0.77)', 'State': 'rgba(0, 94, 162, .7)', 'Privat': 'rgba(22, 46, 81, .8)'}
			var colors = {'City': '#1f5673', 'Federal': '#759FBC', 'State': '#90C3C8', 'Private': '#B9B8D3'}
			$('#costStats thead').html('<tr><th scope="col">Funding Type</th><th scope="col">First Fiscal Year</th><th scope="col">Ten-Year Total</th></tr>');
			var aggregated = {};
		catdata.forEach(function (d, i) {
			if (d['Published Date'] == date) {
				var ft = d['Funding Type'];
				if (!aggregated[ft]) {
					aggregated[ft] = {ft: ft, fy: d['First Fiscal Year'], total: 0, fy1: 0, fy2: 0, fy3: 0, fy4: 0, fy5: 0, fy6: 0, fy7: 0, fy8: 0, fy9: 0, fy10: 0};
				}
				aggregated[ft].total += d['Ten-Year Total'];
				aggregated[ft].fy1 += d['Fiscal Year 1 Amount'];
				aggregated[ft].fy2 += d['Fiscal Year 2 Amount'];
				aggregated[ft].fy3 += d['Fiscal Year 3 Amount'];
				aggregated[ft].fy4 += d['Fiscal Year 4 Amount'];
				aggregated[ft].fy5 += d['Fiscal Year 5 Amount'];
				aggregated[ft].fy6 += d['Fiscal Year 6 Amount'];
				aggregated[ft].fy7 += d['Fiscal Year 7 Amount'];
				aggregated[ft].fy8 += d['Fiscal Year 8 Amount'];
				aggregated[ft].fy9 += d['Fiscal Year 9 Amount'];
				aggregated[ft].fy10 += d['Fiscal Year 10 Amount'];
			}
		});
		Object.values(aggregated).forEach(function (d) {
			$('<tr><td><b>' + d.ft + '</b></td><td>' + d.fy + '</td><td>' + toFin(d.total * 1000) + '</td></tr>').appendTo('#costStats thead');
			labels = [d.fy - 9, d.fy - 8, d.fy - 7, d.fy - 6, d.fy - 5, d.fy - 4, d.fy - 3, d.fy - 2, d.fy - 1, d.fy]
			datasets.push({
				label: d.ft,
				data: [d.fy1 * 1000, d.fy2 * 1000, d.fy3 * 1000, d.fy4 * 1000, d.fy5 * 1000, d.fy6 * 1000, d.fy7 * 1000, d.fy8 * 1000, d.fy9 * 1000, d.fy10 * 1000],
				fill: false,
				borderColor: colors[d.ft],
				borderWidth: 2,
				pointBackgroundColor: 'transparent',
				pointBorderColor: '#CCCCCC',
				pointBorderWidth: 3,
				pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
				pointHoverBorderWidth: 6,
				tension: 0.1,
				datalabels: {display: false},
			})
		})
			
			// ⚠⚠ A CATEGORY CAN HAVE PROJECTS AND NO TEN-YEAR PLAN. `capitalstrategy`
			// is a PROGRAMME table with no project key — measured,
			// `Neighborhood Parks, Playgrounds and Ballfields` has **0 strategy rows
			// and 1,036 spine projects**. Handing Chart.js empty labels threw
			// `n.slice is not a function` from `buildTicks`, which killed the rest of
			// the ready handler on exactly the pages this rebuild just gave content.
			// ⚠ The panel is HIDDEN and SAID SO, never left as an empty chart frame:
			// "no ten-year plan is published for this category" is a finding about
			// the City's plan, not a rendering failure.
			if (!labels.length || !datasets.length) {
				$('#costChart').closest('.row').hide()
				$('#costStats').closest('.row').hide()
				$('#planNote').text('NYC publishes no Ten-Year Capital Strategy amounts for this category. The projects below are what the City has assigned to it.').show()
				return
			}
			window.chart1.data.labels = labels
			window.chart1.data.datasets = datasets
			window.chart1.update()			
		}
		

	</script>

	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-12 mt-4">
					<p class="lead">The 10-Year Capital Strategy is organized by thematic “10-Year Categories.” Every capital project is associated with one of these categories.</p> 
				</div>
				<div class="col-md-8 organization_data">
					<div class="db-eyebrow">Projects</div>
					{{-- ⚠ `$catName`, not `$data[0][...]`. `capitalstrategy` is a programme
					     plan table with no project key, and a category can be absent from it
					     while the spine holds 1,036 projects in it — subscripting row 0 of an
					     empty source is what 500'd those pages. --}}
					<h1 class="db-profile-title">{{ $catName }}</h1>
					{{-- ⚠ Filled by catUpdate when the strategy has nothing for this
					     category. Empty and hidden otherwise. --}}
					<p id="planNote" class="db-note" style="display:none"></p>
					@if (count($prjTypes ?? []) > 0)
						<h6>
							Project Type:&nbsp;
							@foreach($prjTypes as $t=>$u)
							  <a href="{!! $u !!}">{{ $t }}</a> 
							@endforeach
						</h6>
					@endif
				</div>
				<div class="col-md-4 mt-2 pt-3">
					<table class="table-sm stats-table" width="100%">
						<thead>
						  <tr>
							<th scope="col" width="50%" class="text-center px-0" data-content="See the category info published on specific dates.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
							<th scope="col" width="50%" id="pub_date_filter"></th>
						  </tr>
						</thead>
					</table>
				</div>
			</div>
			
			<div class="row justify-content-center mb-5">
				<div class="col-md-4">
					<div class="table table-sm">
						<table width="100%" id="costStats" class="db-table">
							<thead>								
							</thead>
							<tbody>
							</tbody>
						</table>
					</div>
					
				</div>
				
				<div class="col-md-8" id="costChartOuter">
					<h4 class="mb-2">Cost Over Time</h4>
					<canvas id="costChart" height="200" style="width:100%; height:200px;"></canvas>
				</div>
			</div>


			
			<div class="row justify-content-center">
				{{-- ⚠⚠ THE WIDTH FOLLOWS WHETHER THE SIBLING RENDERS, and it did not.
				     This column was a fixed `col-md-8` paired with the publication-date
				     control's `col-md-4` — a balanced 12. Gating that control off for the
				     spine contract (it is a retired-series artifact) left this column
				     ALONE in a `justify-content-center` row, so bootstrap centred it and
				     the heading sat **268 px** from the left while every other heading on
				     the page sat at 35. Reported by the owner.
				     ⚠ Invariant 19's shape at the LAYOUT layer: gating a block can change
				     the thing NEXT to it, not just remove the block. `pubdate_filter` is
				     set only by `OrgsDatasets`, so on this page the control never renders
				     and a bare `col-md-12` would be correct today — it stays conditional
				     so the pair cannot silently unbalance again if a contract sets it. --}}
				<div class="col-md-{{ ($details['pubdate_filter'] ?? null) ? '8' : '12' }} organization_data">
					<h2>Projects</h2>
				</div>
				{{-- ⚠⚠ THE LABEL GOES WITH THE CONTROL, GATED ON THE SAME KEY. This
				     cell is where the publication-date `<select>` was appended, and the
				     script that built it is now gated on `$details['pubdate_filter']`.
				     Ungated markup renders the caption *"Project Publication Date"* and
				     its ⓘ beside an EMPTY cell — invariant 7's fourth thing, a blank
				     that says nothing at all, and what eight tiles on the org capital
				     tab did for weeks. The spine has no publication-date dimension: it
				     is one row per project, not one row per project per vintage. --}}
				@if ($details['pubdate_filter'] ?? null)
				<div class="col-md-4 mt-2" id="org_summary">
					<table class="table-sm stats-table" width="100%">
					<tbody>
						<tr class="align-middle"> 
							<td class="text-center px-0 pt-0" data-content="See the projects info published on specific dates." style="position:relative; top: -2px;">
								Project Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small>
							</td>
							<td class="pt-0" width="40%" id="pub_date_prj_filter" style="position:relative; top: -2px;"></td>
						{{--<td class="text-right px-0 pt-0 pb-3">
								<button class="type-label my-2 dropdown-toggle" data-bs-toggle="collapse" data-bs-target="#stats_collapse" aria-expanded="false" aria-controls="stats_collapse"><small>Show/Hide Stats</small></button>
							</td>
						--}}	
						</tr>
					</tbody>
					</table>
				</div>
				@endif
			</div>
			
			{{--<div id="stats_collapse" class="collapse mt-2 mb-4">--}}
			<div id="stats_collapse" class="mt-2 mb-4">
				{{-- ⚠ FIVE SPINE TILES, replacing eight computed from the retired
				     series. `Amount Over Budget` is DELETED rather than repointed (it
				     carries two definitions), and the three lateness tiles with it —
				     they needed an "original" date the spine does not carry as a
				     single value. --}}
				<div class="row justify-content-center my-2">
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Projects in this category
									<div id="projects_no" class="db-stat-value prj_stat">&nbsp;</div>
								</div>
							</div>
						</div>
					</div>
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									In the current plan
									<div id="in_plan_no" class="db-stat-value prj_stat">&nbsp;</div>
								</div>
							</div>
						</div>
					</div>
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Planned commitments
									<div id="planned_cost" class="db-stat-value prj_stat">&nbsp;</div>
								</div>
							</div>
						</div>
					</div>
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Spent
									<div id="spent_cost" class="db-stat-value prj_stat">&nbsp;</div>
								</div>
							</div>
						</div>
					</div>
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									With a published schedule
									<div id="sched_no" class="db-stat-value prj_stat">&nbsp;</div>
								</div>
							</div>
						</div>
					</div>
				</div>
							</div>
						</div>
					</div>
				
				</div>
					
			</div>
					
				
			<div class="row justify-content-center map_right mb-5">
				@if ($map ?? null)
					<div id="map_container" class="col-6" style="display:none;">
						<button id="map_button_alt" class="btn btn-outline map_btn" style="margin:0 20px 20px 10px; z-index: 10; max-width: 40px; float:right;" onclick="toggleMap();"><img src="/img/map_location.png" alt=""></button>
						<!-- toggles -->
						<div class="select_district" id="toggles" style="left:0px;">
							<img src="/img/eyes.png" alt="">
							<ul class="inner_district">
								<li class="dropdown">
									<a class="dropdown-toggle" id="toggle_boundries" role="button" aria-haspopup="true" aria-expanded="true">Show District Boundaries</a>
									<div class="dropdown-menu" style="width:100%;padding:0px 0px 0px 10px;">
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="cd-switch">
											<label class="custom-control-label" for="cd-switch">Community Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="ed-switch">
											<label class="custom-control-label" for="ed-switch">Election Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="pp-switch">
											<label class="custom-control-label" for="pp-switch">Police Precincts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="dsny-switch">
											<label class="custom-control-label" for="dsny-switch">Sanitation Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="fb-switch">
											<label class="custom-control-label" for="fb-switch">Fire Battilion<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="sd-switch">
											<label class="custom-control-label" for="sd-switch">School Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="hc-switch">
											<label class="custom-control-label" for="hc-switch">Health Center Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="cc-switch">
											<label class="custom-control-label" for="cc-switch">City Council Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="nycongress-switch">
											<label class="custom-control-label" for="nycongress-switch">Congressional Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="sa-switch">
											<label class="custom-control-label" for="sa-switch">State Assembly Dist...<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="ss-switch">
											<label class="custom-control-label" for="ss-switch">State Senate Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="bid-switch">
											<label class="custom-control-label" for="bid-switch">Business Improvem...<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="nta-switch">
											<label class="custom-control-label" for="nta-switch">Neighborhood Tab...<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="zipcode-switch">
											<label class="custom-control-label" for="zipcode-switch">Zip Code<hr class="border-sample"></label>
										</div>
									</div>
								</li>
							</ul>
						</div>
						<!-- /toggles -->
						<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;border:4px solid #112F4E; position:relative; min-height:800px;"></div>
						<div id="location_coverage" class="" style="width:100%;border:1px solid #112F4E; margin-top:20px; padding: 32px;">
							<h4>Why some projects are not on the map</h4>
							{{-- ⚠⚠ THIS REPLACES A CLAIM THAT IS NO LONGER TRUE. The copy here
							     read "NYC's government doesn't publish the locations of capital
							     projects (!?), so volunteers are using the information they do
							     publish to determine where the projects are actually located",
							     with a link to a Notion volunteer page. The City DOES publish
							     locations — Databook holds published geometry for 4,560
							     projects, from DCP's CPDB points and polygons — so the sentence
							     told a reader the opposite of what the map beside it was
							     drawing. What is true is that coverage is partial and uneven,
							     and the project index states the exact denominator for whatever
							     filters are applied rather than a number typed here. --}}
							<p>The City publishes a location for some capital projects and not others, and the gap is not evenly spread &mdash; several agencies publish none at all. A project with no pin is not missing from the capital programme; the City has not published where it is.</p>
							{{-- ⚠⚠ THE DENOMINATOR FOR THIS SCOPE, PRINTED AS THE ENDPOINT
							     SERVED IT. This panel carried only the general sentence above
							     and a link out, so a map beside a table of hundreds of
							     projects had nothing on the page reconciling the two — and
							     the map was in fact drawing 0. The figures are not typed
							     here: `/get/capital/geojson` computes `mapped`, `unmapped`
							     and `matching_filters` for the filters actually applied, and
							     this prints its `note`. Empty until the map is opened, which
							     is when the fetch runs. --}}
							<p id="mapCoverageNote" class="db-text-muted mb-2" style="font-size:var(--db-text-2xs)"></p>
							<p><a href="{!! route('projects') !!}" class="learn_more">See every project, with the location coverage for each filter</a></p>
						</div>
					</div>
				@endif
				<div id="data_container" class="col float-left">
					<div class="table-responsive">
						<div class="filter_icon">
							<i class="bi bi-funnel-fill"></i>
						</div>
						<table id="myTable" class="display table-striped table-hover" style="width:100%;">
							<thead>
								<tr>
									@if ($details['detFlag'])
										<th></th>
									@endif
									@foreach ($details['hdrs'] as $name)
										<th>{{ $name }}</th>
									@endforeach
									<th></th>
								</tr>
							</thead>
						</table>
					</div>
				</div>
			</div>
		</div>

		<div class="container">
			<div class="row my-4">
				{{-- One shell, from the shared provenance component. This markup was
				     hand-rolled on fifteen views, each with its own per-page fetch. --}}
				<x-db.data-provenance mode="scoped" :datasets="$datasets" :statUrl="$tblStatsUrl" scope-label="Ten-Year category" id="categoryADs" />
			</div>
		</div>

	</div>


	<script>
		function changeToggle (e) {
			$('#change_district').html($(e.target).next("label")[0].innerHTML);
		}
		$('#toggle_boundries').click( function (e) {
			$(this).next('.dropdown-menu').toggleClass('show');
		})

		$(".filter_icon").click(function() {
			if(!$('.toolbar').is(':visible')) {
				$('.filter_icon').addClass('position_change');
			}else {
				$('.filter_icon').removeClass('position_change');
			}
			$(".toolbar").toggle();
		});
	</script>

@endsection