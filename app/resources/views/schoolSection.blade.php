@extends('layout')


@section('head')
	<meta name="description" content="{-- $snippet --}" />
	<meta rel="canonical" href="{--!! $canonicalUrl !!--}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	@include('sub.schoolprofile', ['active' => $section])

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>

	<script>
		var datasets = {!! json_encode(array_values($datasets)) !!}
		var tblStatsUrls = {!! json_encode($tblStatsUrls) !!}
		function details(r) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
			  @foreach ((array)$details['details'] as $h=>$f)
				'<tr><td>{{ $h }}:</td><td>' + {!! $f !!} + '</td></tr>' +
			  @endforeach
			'</table>';
		}


		var datatable = null
		$(document).ready(function() {
			
			datatable = $('#myTable').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $url !!}", cb);
			    },
					
				/*	
				ajax: {
					url: '{!! $url !!}',
					dataSrc: 'rows'
				},
				*/
				buttons: [{
                    extend: 'colvis',
                    "className": 'btn_eyeicon',
                    columnText: function ( dt, idx, title ) {
                        return (idx+1)+': '+(title ? title : 'details');
                    }
                }],
				deferRender: true,
				{{-- ⚠ A section may override the empty state, because "we hold no
				     records" and "this school cannot have these records" are
				     different claims. An elementary school has no graduating
				     cohort by definition; saying "no data" invites the reader to
				     think something is missing. Default is unchanged. --}}
				language: { emptyTable: {!! json_encode($details['emptyText'] ?? '<div class="db-empty"><div class="db-empty-icon"><i class="bi bi-inbox"></i></div><div class="db-empty-title">No data for this school</div><div class="db-empty-text">This dataset has no records for the selected school.</div></div>') !!} },
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
				createdRow: function(row, data, dataIndex) {
					if (data.GEO_JSON != '') {
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

							// ⚠ The DEFAULT VALUE half of `filters`. SchoolDatasets has
							// documented `fld no => def value or null if empty` since it was
							// written, and until 2026-09-21 only the KEYS were read — every
							// declared default was silently inert. Applied only when a
							// non-null value is declared, so every existing section (all of
							// which declare null) behaves exactly as before.
							var defs = {!! json_encode($details['fltDefaults']) !!};
							if (defs[c] !== undefined && defs[c] !== null) {
								select.val(defs[c]);
								column.search(defs[c] ? defs[c] : '', false, false).draw();
							}
						});
						setTimeout(function(){
							initPopovers();
						}, 1000);
						
					}
				@endif

				@if ($details['order'] ?? null)
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

			$('#myTable_length label').html($('#myTable_length label').html().replace(' entries', ''));

			// if map is displayed updates and draws projects from GEO_JSON field
			/*
			datatable.on('draw', function () {
				drawProjects('current');
            });
			*/
			
			$('#myTable tbody').on('click', 'td:not(.details-control)', function () {
				var mapIsActive = !$('#map_container').attr('style')
				if (!mapIsActive) 
					return;
				var tr = $(this).closest('tr');
				var row = datatable.row(tr);
				r = row.data()
				if (r['GEO_JSON']) {
					var geo_json = JSON.parse(r['GEO_JSON'].replaceAll('""', '"'))
					var pr = geo_json.properties
					fitBounds([[pr.W, pr.S], [pr.E, pr.N]])
				}
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


			// school on map
			@if ($school['LATITUDE'])
				
				//var bounds = [[feature.properties.W, feature.properties.S], [feature.properties.E, feature.properties.N]]
				var bounds = [[{{ $school['LONGITUDE'] - 0.04 }}, {{ $school['LATITUDE'] - 0.04 }}], [{{ $school['LONGITUDE'] + 0.04 }}, {{ $school['LATITUDE'] + 0.04 }}]]
				var features = [{"type":"Feature","geometry":{"type":"Point","coordinates":[{{ $school['LONGITUDE'] }},{{ $school['LATITUDE'] }}]}}]
				//console.log(features)
			
				mapboxgl.accessToken = 'pk.REPLACE_WITH_YOUR_MAPBOX_TOKEN';

				map = new mapboxgl.Map({
					container: 'map',
					style: 'mapbox://styles/mapbox/light-v10',
					center: [{{ $school['LONGITUDE'] }},{{ $school['LATITUDE'] }}],
					zoom: 10
				});
				
				map.addControl(new mapboxgl.NavigationControl());

				map.on('load', function () {
					map.addSource('route', {
							"type": "geojson",
							"data": {
								"type": "FeatureCollection",
								"features": features
							}
						});

					map.addLayer({
						'id': 'streets',
						'type': 'line',
						'source': 'route',
						'layout': {
							'line-join': 'round',
							'line-cap': 'round'
						},
						'paint': {
							'line-color': '#53777a',
							'line-width': 6
						},
						'filter': ['==', '$type', 'LineString']
					});

					map.addLayer({
						'id': 'markers',
						'type': 'circle',
						'source': 'route',
						'paint': {
							'circle-radius': 6,
							'circle-color': '#53777a'
						},
						'filter': ['==', '$type', 'Point']
					});

					map.addLayer({
						'id': 'areas',
						'type': 'fill',
						'source': 'route',
						'paint': {
							'fill-color': '#53777a',
							'fill-opacity': 1
						},
						'filter': ['==', '$type', 'Polygon']
					});
					
					for (const [code, clr] of Object.entries(zones)) {
						setBoundary(code, clr, clr);
					}
					$('#toggles').show();

					map.fitBounds(bounds);
				});
				
			@endif

			
			@if($schoolStatsUrl ?? null)
				{{-- ⚠⚠ `schoolStatTiles` (script.js) OWNS THIS READ. Six unguarded
				     `resp.data[0].<field>` reads used to live here — the same defect
				     /schools and distsection already had, still live on this page.
				     `fapireq` hands back three shapes and only one carries a row, and
				     an empty `data` is reachable on a HEALTHY 200 as well: this
				     endpoint returns `{rows: []}` for a location code it cannot
				     resolve. Measured before the fix: HTTP 500 and 200-with-no-rows
				     both threw `Cannot read properties of undefined (reading
				     'povetry_perc')`, which aborts the rest of this ready handler.
				     ⚠ The per-FIELD `!= null` guards were UNREACHABLE in exactly the
				     cases they looked written for — the throw is on the ROW deref,
				     before any of them evaluates. And their fallback was the literal
				     string 'NaN', which reads as a bug to a visitor and cannot
				     distinguish "we could not ask" from "it answered with nothing".
				     ⚠ The tile lists are PASSED IN, not forked into a second copy:
				     this page has no `schools_no` and does have `povetry_perc`. --}}
				fapireq('{!! $schoolStatsUrl !!}', function (resp) {
					schoolStatTiles(resp, 'schoolStatsNote', {
						plain: ['povetry_perc'],
						count: ['students_no', 'prj_no'],
						money: ['prj_budget', 'prj_costs', 'pcosts_per_student']
					})
				})
			@endif	

			
		});
	
	</script>



	<div class="inner_container">
		<div class="container mb-5" style="padding-top: var(--db-space-3);">
			<div class="organization_data">
				@if(array_search($section, $menu) === false)
					<h2 class="db-card-title">{{ $dataset['Name'] ?? '' }}</h2>
				@endif
				@if (trim($details['description'] ?? ($dataset['Descripton'] ?? '')))
					<p class="db-page-lead">{!! nl2br($details['description'] ?? ($dataset['Descripton'] ?? '')) !!}</p>
				@endif
			</div>

			<div class="db-table-wrap mt-3">
				<div id="data_container" class="table-responsive">
					<div class="filter_icon">
						<i class="bi bi-funnel-fill"></i>
					</div>
					<table id="myTable" class="db-table display table-striped table-hover" style="width:100%;">
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

		@if ($dataset && ($dataset['Public Note'] ?? null))
			<div class="container mb-3">
				<p class="note_bottom db-page-lead">{{ nl2br($dataset['Public Note'] ?? '') }}</p>
			</div>
		@endif

		{{--
			<div class="col-md-12" style="display:none">
				<div class="bottom_lastupdate">
		@if ($dataset)
					<p class="lead"><img src="/img/info.png"> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] ?? '' }}</a><span class="float-right" style="font-weight: 300;"><i>Last updated {{ explode(' ', $dataset['Last Updated'] ?? '')[0] }}</i></span></p>
				</div>
			</div>
		@endif
		--}}
		
		<div class="container">
			<div class="row mb-4">
				{{-- One shell, from the shared provenance component. This markup was
				     hand-rolled on fifteen views, each with its own per-page fetch. --}}
				<x-db.data-provenance mode="page" :datasets="$datasets" id="schoolSectionDs" />
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