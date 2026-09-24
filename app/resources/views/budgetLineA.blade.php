@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects strategy | {{ $data[0]['Budget Line Title'] }}" />
	<meta rel="canonical" href="{!! route('budgetLine', ['blcode' => $data[0]['Budget Line']]) !!}" />
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
		{{-- ⚠ The map's scope, handed to the one owner. Built by the CONTROLLER
		     from the same budget line the list request uses, so the two cannot
		     answer differently. --}}
		capMap.init('{!! $capGeojsonUrl !!}');

		function details(r) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
			  {{-- ⚠⚠ `?? []`, AND THIS EXACT LINE 500'd THE PAGE ON THE MIGRATION.
			       The expander config is OPTIONAL — the `spine` contract declares no
			       `details`, so `get()` computes `detFlag = 0` and the table renders
			       no expander column — and a bare subscript on a missing key is an
			       ErrorException in Laravel, not a null. `categoryA` fixed this when
			       it migrated and its comment says "same shape as the budget-line
			       defect"; the budget-line page had simply not been migrated yet.
			       ⚠ The function is emitted whether or not an expander exists, so it
			       must degrade to an empty table rather than fail to compile. --}}
			  @foreach ((array)($details['details'] ?? []) as $h=>$f)
				'<tr><td>{{ $h }}:</td><td>' + {!! $f !!} + '</td></tr>' +
			  @endforeach
			'</table>';
		}


		function commDetails(d) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
				(d["maprojid"] 		? '<tr><td>Mapped Project ID:</td><td>'+d["maprojid"]+'</td></tr>' : '') +
				(d["typc"] 			? '<tr><td>Type Code:</td><td>'+d["typc"]+'</td></tr>' : '') +
				(d["typcname"] 		? '<tr><td>Type Code Name:</td><td>'+d["typcname"]+'</td></tr>' : '') +
				(d["ccnonexempt"] 	? '<tr><td>City Nonexempt:</td><td>'+toFin(d["ccnonexempt"])+'</td></tr>' : '') +
				(d["ccexempt"] 		? '<tr><td>City Exempt:</td><td>'+d["ccexempt"]+'</td></tr>' : '') +
				(d["totalcityplannedcommit"] ? '<tr><td>Total City Planned:</td><td>'+toFin(d["totalcityplannedcommit"])+'</td></tr>' : '') +
				(d["nccstate"] 		? '<tr><td>State Cost:</td><td>'+d["nccstate"]+'</td></tr>' : '') +
				(d["nccfederal"] 	? '<tr><td>Federal Cost:</td><td>'+d["nccfederal"]+'</td></tr>' : '') +
				(d["nccother"] 		? '<tr><td>Other Cost:</td><td>'+d["nccother"]+'</td></tr>' : '') +
				(d["totalnoncityplannedcommit"] ? '<tr><td>Total Noncity Planned:</td><td>'+toFin(d["totalnoncityplannedcommit"])+'</td></tr>' : '') +
				(d["totalplannedcommit"] ? '<tr><td>Total Planned:</td><td>'+toFin(d["totalplannedcommit"])+'</td></tr>' : '') +
				(d["sagencyname"] 	? '<tr><td>Agency Name:</td><td>'+d["sagencyname"]+'</td></tr>' : '') +
				(d["ccpversion"] 	? '<tr><td>Version:</td><td>'+d["ccpversion"]+'</td></tr>' : '') +
			'</table>';
		}

		var datatable = null
		var commdatatable = null
		var bldata = {!! json_encode($data) !!}
		var capcommdata = {}
		var types = {'C': 'City Exempt', 'F': 'Federal', 'S': 'State', 'P': 'Private', 'E': 'City Not Exempt'}
		var colors = ['#1f5673', '#759FBC', '#90C3C8', '#B9B8D3', '#463730']
		var datasets = {!! json_encode(array_values($datasets)) !!}
		
		$(document).ready(function() {

			// top data filter
			
			var select = $('<select class="filter" id="filter-top" style="width: 100%;"></select>')
				.appendTo($("#pub_date_filter"))
				.on('change', function () {
					var val = $(this).val()
					blUpdate(val);
				})
			select.wrap('<div class="drop_dowm_select col"></div>');
			var tt = []
			bldata.forEach(function (d, j) {
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
			
			
			// capcomm data filter

			var capcommselect = $('<select class="filter" id="filter-comm" style="width: 100%;"></select>')
				.appendTo($("#comm_pub_date_filter"))
				.on('change', function () {
					var val = $(this).val()
					capCommUpdate(val);
				})
			capcommselect.wrap('<div class="drop_dowm_select col"></div>');
			
			
			// chart
			
			var canvas2 = document.getElementById("capCommChart");
			
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
			window.chart2 = new Chart(canvas2, config2);
			
			
			fapireq("{!! $capCommUrl !!}", function (resp) {
				capcommdata = resp['data']
				var tt = []
				capcommdata.forEach(function (d, j) {
					tt.push(d['Published Date'])
				})
				tt = [...new Set(tt)]
				tt.sort().forEach(function (d, j) {
					capcommselect.append('<option value="'+d+'">'+toDashDate(d)+'</option>')
				})
				setTimeout(function(){
					capcommselect.val(tt[tt.length-1]).trigger('change')
				}, 700)
			});


			// commitments DCP datatable
			
			commdatatable = $('#commDatatable').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $commUrl !!}", cb);
			    },
				deferRender: true,
				dom: '<"toolbar container-flex">rt',
				columns: [
					{
						"className": 'details-control',
						"orderable": false,
						"data":  null,
						"defaultContent": ''
					},
					{data: 'maprojid'},
					{data: 'projectdescription'},
					{data: function (r) {
							var slug = r['wegov-prjtype-name'].toLowerCase().replace(/\W+/g, '-')
							return '<a href="/capital/project-types/' + slug + '">' + r['wegov-prjtype-name'] + '</a>'
						},
						type: 'html'
					},
					// ⚠ The LABEL, falling back to the raw value. The endpoint serves
					// both; reading only the raw one is how this table published
					// `06/01/2026` beside a sources table saying `1 Jun 2026`.
					{data: function (r) { return r['plancommdate_label'] || r['plancommdate'] || '' }},
					{data: 'commitmentdescription'},
					{data: 'typcname'},
                    {data: function (r) {
							return '<a href="/organization/' + r['wegov-org-id'] + '">' + r['wegov-org-name'] + '</a>'
						},
						type: 'html'
					}                ]
			});

			$('#commDatatable tbody').on('click', 'td.details-control', function () {
				var tr = $(this).closest('tr');
				var row = commdatatable.row(tr);

				if (row.child.isShown()) {
					row.child.hide();
					tr.removeClass('shown');
                    tr.next('tr').removeClass('child-row');
				}
				else {
					row.child(commDetails(row.data())).show();
					tr.addClass('shown');
                    tr.next('tr').addClass('child-row');
					initPopovers();
				}
			});



			// projects datatable
			
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
				dom: '<"toolbar container-flex"<"row">>Blfrtip',
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
				// ⚠⚠ THIS TEST WAS `data.GEO_JSON != ''`, AND ON A SPINE ROW THAT KEY
				// IS UNDEFINED — `undefined != ''` is TRUE, so every row would have
				// been marked as located, including the 40 of 60 on this line the
				// City publishes no location for. The set comes from the geojson the
				// map actually received, so the marker and the pins cannot disagree.
				// ⚠ Guarded on the set EXISTING, because the fetch and the first draw
				// are a race: `capMap.markLocated()` re-applies this for every row once
				// the fetch lands, and on every subsequent draw.
				// ⚠⚠ AND THIS PROPERTY MUST NOT SIMPLY BE DELETED. The Blade
				// conditional below emits a LEADING comma, so removing the last
				// unconditional property here leaves `], , initComplete:` and the
				// whole script block fails to parse with `Unexpected token ','`.
				// Measured while making this change: `toggleMap`, `drawProjects` and
				// every other function on the page became undefined while the page
				// still returned 200 and rendered its table.
				// ⚠ Nor may that conditional be NAMED with its directive spelling in
				// a comment here: Blade compiles directives inside `//` comments in a
				// script block too, so writing it out turns this explanation into a
				// PHP `if` with no condition and 500s the page — which is exactly
				// what happened on the first attempt at this comment.
				createdRow: function (row, data, dataIndex) {
					if (capMap.isLocated(data && data.id))
						$(row).addClass('have_coords');
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


						{{-- ⚠⚠ GATED ON THE CONTRACT, BECAUSE IT IS INDEXED ON A COLUMN
						     POSITION (invariant 10). `columns([1])` meant `Publication
						     Date` under `capitalprojectsdollarscomp` (whose contract
						     declares a details expander, so column 0 is the expander and
						     column 1 the date). On the spine contract column 1 is
						     `Agency`, and this block would build a dropdown of 60 agency
						     names, auto-select the last and filter the table to it — the
						     defect that shipped on the org capital tab, where the page
						     read "Showing 1 to 1 of 1 (filtered from 2,798)" with a
						     correct payload, correct headers and correct rows.
						     ⚠ Measured on THIS page before the migration: the control
						     picked `2023-10-26`, the last of 15 dates, and the table read
						     *"Showing 1 to 1 of 1 entries (filtered from 34 total
						     entries)"* under a tile saying 60 projects.
						     `spine` declares no `pubdate_filter`, so nothing is emitted;
						     `main` declares column 1, which is where it always was. --}}
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

			$('.btn_eyeicon').hide();

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
			// (This comment said "draws projects from GEO_JSON field", which stopped
			// being true when the table moved to the spine.)
			datatable.on('draw', function () {
				drawProjects('current');
				capMap.markLocated();
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
				// about the style load, not a synchronisation with it. `load` may
				// already have fired by the time this binds, so `loaded()` covers
				// that; mapbox no-ops a late `on('load')` handler.
				if (typeof map !== 'undefined') {
					if (map.loaded && map.loaded()) capMap.ready();
					map.on('load', function () { capMap.ready(); });
				}
				capMap.draw('all');
			}
			initPopovers();			
		}
		
		
		// ⚠⚠ THE RETIRED-SERIES LOOP IS GONE, NOT LEFT INERT. It summed the
		// table's currently-filtered `capitalprojectsdollarscomp` rows into eight
		// tiles and multiplied the money by 1000, and its `#over_budg_am` line
		// accumulated `-BUDG_DIFF` independently of the two costs beside it — which
		// is how the grid came to read $502M original, $474M current and $297M over
		// budget at the same time. The tiles are server-rendered from the spine now.
		// ⚠ The function survives because its callers rely on the popovers.
		function loadFinStat() {
			setTimeout(function(){
				initPopovers();
			}, 1000);
		}
		
		
		{{-- ⚠⚠ ONE OWNER: `capMap` IN `script.js`. This page held its own copy of
		     the fetch, the race and the marker; `categoryA` and
		     `orgprojectsection` held a third and fourth copy of the same
		     GEO_JSON-reading `drawProjects`, and ALL of them drew 0 features once
		     their tables moved to the spine. Three byte-identical copies of a
		     race-sensitive block is what this repo keeps paying for; the helper
		     carries the reasoning and the measurements. --}}
		function drawProjects(pages) {	// 'all',     'current'
			capMap.draw(pages);
		}

		function blUpdate(date) {
			var datasets = []
			var labels = {}
			$('#costStats tbody').html('')
			bldata.forEach(function (d, i) {
				if (d['Published Date'] == date) {
					$('<tr><td>' + types[d['Funding Type']] + '</td><td>' + d['First Fiscal Year'] + '</td><td>' + toFin(parseInt(d['Fiscal Year 1 Amount']) + parseInt(d['Fiscal Year 2 Amount']) + parseInt(d['Fiscal Year 3 Amount']) + parseInt(d['Fiscal Year 4 Amount'])) + '</td></tr>').appendTo('#costStats tbody');
					
					labels = [d['First Fiscal Year'], parseInt(d['First Fiscal Year']) + 1, parseInt(d['First Fiscal Year']) + 2, parseInt(d['First Fiscal Year']) + 3]
				
					datasets.push({
						label: types[d['Funding Type']],
						data: [d['Fiscal Year 1 Amount'], d['Fiscal Year 2 Amount'], d['Fiscal Year 3 Amount'], d['Fiscal Year 4 Amount']],
						fill: false,
						borderColor: colors[datasets.length],
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
			})
			
			window.chart1.data.labels = labels
			window.chart1.data.datasets = datasets
			window.chart1.update()			
		}
		
		function capCommUpdate(date) {
			var datasets = []
			// ⚠⚠ `[]`, NOT `{}` — AND THIS WAS AN UNCAUGHT `TypeError` ON A LIVE PAGE.
			// `labels` was initialised as an OBJECT and only ever assigned an array
			// inside the loop, so a budget line with no matching commitment row left
			// `{}` here, `chart2.data.labels = {}`, and Chart.js's `buildTicks` threw
			// `n.slice is not a function`. Measured 2026-09-10 on
			// `/projects/budget-lines/P I001`, where `capitalcommitmentplan` has **0
			// rows** for the line: the page returned 200, the console showed one
			// uncaught TypeError, and every check on the page passed.
			// ⚠ PRE-EXISTING, and not caused by the spine migration — the block that
			// fetches this data and triggers this call is untouched by it. Fixed here
			// because it makes "did this page throw?" answerable again, which is what
			// the headless verifier now asserts.
			var labels = []
			$('#capCommStats tbody').html('')
			capcommdata.forEach(function (d, i) {
				if (d['Published Date'] == date) {
					$('<tr><td>' + d['Funding Type'] + '</td><td>' + d['comm_no'] + '</td><td>' + d['First Fiscal Year'] + '</td><td>' + toFin((d['yr1amount'] + d['yr2amount'] + d['yr3amount'] + d['yr4amount'] + d['yr5amount']) * 1000) + '</td></tr>').appendTo('#capCommStats tbody');
					
					labels = [d['First Fiscal Year'], parseInt(d['First Fiscal Year']) + 1, parseInt(d['First Fiscal Year']) + 2, parseInt(d['First Fiscal Year']) + 3, parseInt(d['First Fiscal Year']) + 4]
				
					datasets.push({
						label: d['Funding Type'],
						data: [d['yr1amount'] * 1000, d['yr2amount'] * 1000, d['yr3amount'] * 1000, d['yr4amount'] * 1000, d['yr5amount'] * 1000],
						fill: false,
						borderColor: colors[datasets.length],
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
			})
			
			// ⚠⚠ NOTHING TO PLOT IS NOT AN EMPTY CHART. `P I001` is a real budget
			// line with 1,135 capital projects and NO commitment-plan rows, and an
			// axis-less empty canvas under a heading reading "Commitments (OMB)"
			// says the City committed nothing — which is a claim about the City,
			// not about this dataset's coverage. Same rule as `drawPrjstatChart`,
			// which showed its canvas whenever its callback fired, 0 rows included.
			if (!datasets.length) {
				$('#capCommChartOuter').hide();
				$('#capCommEmpty').text('NYC publishes no capital commitment plan '
					+ 'rows for this budget line. That is a gap in this dataset, not '
					+ 'a statement that nothing was committed.').show();
				return;
			}
			$('#capCommEmpty').hide();
			$('#capCommChartOuter').show();
			window.chart2.data.labels = labels
			window.chart2.data.datasets = datasets
			window.chart2.update()			
		}



		
	</script>

	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center mb-2">
				<div class="col-md-12 organization_data pb-3">
					<div class="db-eyebrow">Projects</div>
					<h1 class="db-profile-title">{{ $data[0]['Budget Line Title'] }}</h1>
					<div class="row mx-0 my-1">
						<div class="col-2">
							<small class="text-muted">ID</small><br />
							<h6>{{ $data[0]['Budget Line'] }}</h6>
						</div>
						<div class="col-10">
							{{-- ⚠⚠ NOT LINKED TO `prjType`, AND THAT IS MEASURED, NOT CAUTION.
							     `capitalbudget."Project Type Name"` is the BUDGET-LINE FAMILY
							     vocabulary — 41 values, **24 of them shared with the spine's
							     39 families and only 5 with the 236-value Ten-Year Strategy
							     work types that `/projects/types/{slug}` is keyed on**. So this
							     link 404'd on most values and, on the handful that resolved,
							     sent a reader to a page about a different dimension that
							     happens to share a name — which is worse, because a 404 says
							     something is missing and a plausible wrong page does not.
							     ⚠ Plain text until the family pages exist; see
							     docs/CAPITAL-PROFILE-PROVENANCE-AND-FACETS.md Part 3.
							     ⚠ And `?? '—'`: a missing display label must never 500 the
							     page, which is exactly what it did here. --}}
							<small class="text-muted">Project type (budget-line family)</small><br />
							<h6>{{ $data[0]['wegov-prjtype-name'] ?? '—' }}</h6>
						</div>
					</div>
				</div>
			</div>


			<div class="row justify-content-center">
				<div class="col-md-6 pr-5">
					<div class="row justify-content-center">
						<div class="col-md-6 organization_data">
							<h4 class="mb-2">Budget</h4>
						</div>
						<div class="col-md-6 mt-2">
							<table class="table-sm stats-table" width="100%">
								<thead>
								  <tr>
									<th scope="col" width="50%" class="text-center px-0" data-content="See budget line info published on specific date.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
									<th scope="col" width="50%" id="pub_date_filter"></th>
								  </tr>
								</thead>
							</table>
						</div>
					</div>


					<div class="row justify-content-center mb-4">
						<div class="col-md-12" id="statsOuter">
							<table class="db-table table table-sm" id="costStats">
							  <thead>
								<tr>
								  <th scope="col">Funding Type</th>
								  <th scope="col">First Fiscal Year</th>
								  <th scope="col">4 Year Allocation</th>
								</tr>
							  </thead>
							  <tbody>
							  </tbody>
							</table>
						</div>
					</div>
					<div class="row justify-content-center mb-5">
						<div class="col-md-12" id="costChartOuter">
							<canvas id="costChart" height="200" style="width:100%; height:200px;"></canvas>
						</div>
					</div>
				</div>

				<div class="col-md-6 pl-5">
					<div class="row justify-content-center">
						<div class="col-md-6 organization_data">
							<h4 class="mb-2">Commitments (OMB)</h4>
						</div>
						<div class="col-md-6 mt-2">
							<table class="table-sm stats-table" width="100%">
								<thead>
								  <tr>
									<th scope="col" width="50%" class="text-center px-0" data-content="See commitment info published on specific date.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
									<th scope="col" width="50%" id="comm_pub_date_filter"></th>
								  </tr>
								</thead>
							</table>
						</div>
					</div>

					<div class="row justify-content-center mb-4">
						<div class="col-md-12" id="statsOuter">
							<table class="db-table table table-sm" id="capCommStats">
							  <thead>
								<tr>
								  <th scope="col">Funding Type</th>
								  <th scope="col">Projects No</th>
								  <th scope="col">First Fiscal Year</th>
								  <th scope="col">Total Commitment</th>
								</tr>
							  </thead>
							  <tbody>
							  </tbody>
							</table>
						</div>
					</div>
					<div class="row justify-content-center mb-5">
						{{-- ⚠ The empty state for the commitments chart, hidden until the
						     callback finds nothing. A blank canvas and a sentence saying
						     the City publishes nothing here are different claims. --}}
						<div class="col-md-12"><p id="capCommEmpty" class="db-text-muted mb-0" style="display:none; font-size:var(--db-text-2xs)"></p></div>
						<div class="col-md-12" id="capCommChartOuter">
							<canvas id="capCommChart" height="200" style="width:100%; height:200px;"></canvas>
						</div>
					</div>
			

				</div>
			</div>




			<div class="row justify-content-center">
				<div class="col-md-12 organization_data">
					<h4 class="mb-2">Commitments (DCP)</h4>
					<div class="table-responsive">
						<table id="commDatatable" class="db-table mb-2 mt-0" width="100%">
							<thead>
								<tr>
									<th scope="col"></th>
									<th scope="col">Enhanced Project Id</th>
									<th scope="col">Description</th>
									<th scope="col">Project Type</th>
									<th scope="col">Plan Commitment Date</th>
									<th scope="col">Commitment Description</th>
									<th scope="col">Commitment Type</th>
									<th scope="col">Managing Agency Name</th>
								</tr>
							</thead>
						</table>
					</div>
				</div>
			</div>

			
			<div class="row justify-content-center mt-2">
				{{-- ⚠⚠ THE WIDTH FOLLOWS WHETHER THE SIBLING RENDERS, and it did not.
				     This column was a fixed `col-md-7` paired with the publication-date
				     control's `col-md-5` — a balanced 12. Gating that control off for the
				     spine contract (it is a retired-series artifact) left this column
				     ALONE in a `justify-content-center` row, so bootstrap centred it and
				     the heading sat **327 px** from the left while every other heading on
				     the page sat at 35. Reported by the owner.
				     ⚠ Invariant 19's shape at the LAYOUT layer: gating a block can change
				     the thing NEXT to it, not just remove the block. `pubdate_filter` is
				     set only by `OrgsDatasets`, so on this page the control never renders
				     and a bare `col-md-12` would be correct today — it stays conditional
				     so the pair cannot silently unbalance again if a contract sets it. --}}
				<div class="col-md-{{ ($details['pubdate_filter'] ?? null) ? '7' : '12' }} organization_data">
					<h2>Projects</h2>
				</div>
				{{-- ⚠⚠ THE LABEL GOES WITH THE CONTROL, GATED ON THE SAME KEY. This
				     cell is where the publication-date `<select>` is appended, and the
				     script that builds it is gated on `$details['pubdate_filter']`.
				     Leaving the markup unconditional would render the caption
				     *"Project Publication Date"* with its ⓘ beside an EMPTY cell — a
				     label for a control that does not exist, which is invariant 7's
				     fourth thing: a blank says nothing at all, and it is what eight
				     tiles on the org capital tab did for weeks. The spine has no
				     publication-date dimension: it is one row per project, not one row
				     per project per vintage. --}}
				@if ($details['pubdate_filter'] ?? null)
				<div class="col-md-5 mt-2" id="org_summary">
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
			
			{{-- ⚠⚠ SERVER-RENDERED FROM THE SPINE, AND THE EIGHT TILES THAT WERE HERE
			     CONTRADICTED EACH OTHER IN ONE GRID. They were computed in the browser
			     by summing the retired series' rows currently shown in the table below,
			     times 1000. Measured on the rendered `/projects/budget-lines/EP-0007`
			     2026-09-10:

			         Projects 1        Original Cost $502M
			         Current Cost $474M    Amount Over Budget $297M

			     $502M against $474M is $28M UNDER budget, beside a tile claiming $297M
			     over — because `BUDG_DIFF` is the publisher's own difference column and
			     does not reconcile with the two costs shown next to it. That is exactly
			     why this section reproduces `Amount Over Budget` nowhere.
			     ⚠⚠ AND `Projects 1` WHERE THE SPINE HAS **60**. The endpoint feeding the
			     table is `SELECT * FROM capitalprojectsdollarscomp WHERE BUDGET_LINE = …`
			     — 34 rows for 9 distinct projects across 14 publication dates — and the
			     tiles counted whatever the publication filter left showing. This is the
			     "2 projects where the spine has 268" defect the category page already
			     fixed, on the page next door.
			     ⚠ `Amount Over Budget` is not repointed, it is dropped: the district tab,
			     the org tab and the rebuilt Overview all drop it, and repointing a label
			     with two definitions preserves the defect under fresher data. --}}
			<div id="stats_collapse" class="mt-2 mb-4">
				<div class="db-stat-grid">
					@php
						$bCap   = is_array($capital ?? null) ? $capital : [];
						$bCapOk = !empty($bCap['available']) && !empty($bCap['found']);
						$bSched = $bCap['schedule'] ?? [];
						$bMoney = [];
						foreach (($bCap['money']['measures'] ?? []) as $bm)
							$bMoney[$bm['key'] ?? ''] = $bm;
						$bFmtN = function ($v) { return is_numeric($v) ? number_format((float) $v) : '—'; };
						$bFmtB = function ($v) {
							if (!is_numeric($v)) return '—';
							$v = (float) $v;
							if (abs($v) >= 1000000000) return '$' . number_format($v / 1000000000, 1) . 'B';
							if (abs($v) >= 1000000) return '$' . number_format($v / 1000000, 1) . 'M';
							return '$' . number_format($v);
						};
						// ⚠ Populations travel with the money (⚑ F). On EP-0007 the planned
						// total is over 46 projects and the spent total over 48 — no two of
						// the six measures are over the same set, so a bare total beside
						// another bare total reads as a funnel that leaks.
						$bPop = function ($k) use ($bMoney, $bFmtN) {
							$n = $bMoney[$k]['population'] ?? null;
							return is_numeric($n) ? $bFmtN($n) . ' projects' : null;
						};
						$bTracked = $bCap['projects'] ?? null;
					@endphp
					@if ($bCapOk)
						<div class="db-stat">
							<div class="db-stat-label">Projects on this budget line</div>
							<div class="db-stat-value">{{ $bFmtN($bTracked) }}</div>
						</div>
						<div class="db-stat">
							<div class="db-stat-label">In the current plan</div>
							<div class="db-stat-value">{{ $bFmtN($bCap['in_current_plan'] ?? null) }}</div>
							@if(is_numeric($bTracked))<div class="db-stat-sub">of {{ $bFmtN($bTracked) }} on this line</div>@endif
						</div>
						<div class="db-stat">
							<div class="db-stat-label">Planned commitments</div>
							<div class="db-stat-value">{{ $bFmtB($bMoney['planned_usd']['value'] ?? null) }}</div>
							@if($bPop('planned_usd'))<div class="db-stat-sub">{{ $bPop('planned_usd') }}</div>@endif
						</div>
						<div class="db-stat is-accent">
							<div class="db-stat-label">Spent</div>
							<div class="db-stat-value">{{ $bFmtB($bMoney['spent_usd']['value'] ?? null) }}</div>
							@if($bPop('spent_usd'))<div class="db-stat-sub">{{ $bPop('spent_usd') }}</div>@endif
						</div>
						<div class="db-stat">
							<div class="db-stat-label">With a published schedule</div>
							<div class="db-stat-value">{{ $bFmtN($bSched['with_published_schedule'] ?? null) }}</div>
							@if(is_numeric($bTracked))<div class="db-stat-sub">of {{ $bFmtN($bTracked) }} on this line</div>@endif
						</div>
					@else
						{{-- ⚠ Zero is not failure and failure is not zero. A budget line the
						     spine carries no project for is a real answer; so is the stats
						     table being absent. Neither may render as nothing. --}}
						<div class="db-stat"><div class="db-stat-label">Projects on this budget line</div><div class="db-stat-value">—</div><div class="db-stat-sub">no projects in Databook&rsquo;s capital spine on this line</div></div>
					@endif
				</div>
				{{-- ⚠⚠ THIS SENTENCE HAD TO CHANGE WITH THE TABLE, and leaving it would
				     have been the stale-disclosure defect. It read: *"The table below is
				     the 2023 project detail series, one row per publication date, which
				     is a different and older view."* That was TRUE and load-bearing
				     while the tiles said 60 and the table showed 1 — it was what stopped
				     the two reading as a contradiction (invariant 9). The table is now
				     the same spine at the same grain, so the disclosure describes a page
				     that no longer exists, and a reader would discount a table that
				     agrees with the tiles exactly.
				     ⚠ The link is KEPT. It is no longer reconciling two views; it goes
				     to the citywide index filtered to this line, where the same 60
				     projects can be sorted and filtered against every other. --}}
				@if ($bCapOk)
					<p class="db-text-muted mt-2 mb-0" style="font-size:var(--db-text-2xs)">
						These figures come from Databook&rsquo;s capital project spine, and
						so does the table below &mdash; one row per project, on the same
						{{ $bFmtN($bTracked) }} projects.
						<a href="{!! route('projects') !!}?budget_line={{ urlencode($blCode ?? '') }}">See them in the citywide project index</a>,
						where they can be compared with every other capital project.
					</p>
				@endif
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
							{{-- ⚠⚠ THE DENOMINATOR FOR THIS BUDGET LINE, PRINTED AS THE ENDPOINT
							     SERVED IT. Until now this panel carried only the general
							     sentence above and a link out, so a map drawing 20 pins beside a
							     tile saying 60 projects had nothing on the page reconciling
							     them — and the map was in fact drawing 0. The figures are not
							     typed here: `/get/capital/geojson` computes `mapped`,
							     `unmapped` and `matching_filters` for the filters actually
							     applied, and this prints its `note`. It stays empty until the
							     map is opened, which is when the fetch runs. --}}
							<p id="mapCoverageNote" class="db-text-muted mb-2" style="font-size:var(--db-text-2xs)"></p>
							<p><a href="{!! route('projects') !!}?budget_line={{ urlencode($blCode ?? '') }}" class="learn_more">See every project on this line, with its location coverage</a></p>
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
				<x-db.data-provenance mode="scoped" :datasets="$datasets" :statUrl="$tblStatsUrl" scope-label="budget line" id="budgetLineADs" />
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