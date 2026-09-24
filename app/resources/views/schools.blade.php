@extends('layout')


@section('head')
	<meta name="description" content="A webpage for NYC schools" />
	<meta rel="canonical" href="{!! route('schools') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')

	{{-- ⚠ typeahead.bundle.js provides BOTH `Bloodhound` and `$.fn.typeahead`,
	     and the address-search wiring below has always used both. It was never
	     loaded here, so every page load threw `Bloodhound is not defined` and
	     the rest of the ready handler after that line never ran. Same tag, same
	     version, as the two sibling pages that share this wiring:
	     projects.blade.php and districts.blade.php. --}}
	<script src="https://typeahead.js.org/releases/latest/typeahead.bundle.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>

	<script>

		var datatable = null
		var dataurl = '{!! $url !!}'
		var datasets = {!! json_encode(array_values($datasets)) !!}
		var tblStatsUrls = {!! json_encode($tblStatsUrls) !!}
		// ⚠⚠ THE TABLE'S FETCH AND THE MAP'S STYLE LOAD ARE A RACE.
		// `projectsMapInit()` adds the `route` source inside mapbox's `load`
		// event; `drawProjects()` calls `projectsMapDrawFeatures`, which does
		// `map.getSource('route').setData`. The DataTable's `draw` event fires as
		// soon as its AJAX lands, and that regularly beats the style -- measured
		// headless, it beat it on EVERY run, with and without an artificial style
		// delay. `getSource('route')` is then undefined, `setData` throws inside
		// the draw handler, and the map stays empty for ever with 40 schools
		// loaded in the table beside it.
		//
		// Same defect and same fix as /projects (CAP_PENDING_FEATURES) and
		// /p/{id} (PRJ_PENDING): hold whatever arrives first, draw when BOTH are
		// ready. ⚠ Unlike those two, `drawProjects` fires again on every redraw
		// -- pagination, a filter, a sort -- so this must keep working after the
		// map is ready, not just once.
		var SCH_PENDING_FEATURES = null;
		var SCH_MAP_READY = false;

		function schDrawWhenReady(features) {
			if (features) SCH_PENDING_FEATURES = features;
			if (!SCH_MAP_READY || SCH_PENDING_FEATURES === null) return;
			var ff = SCH_PENDING_FEATURES;
			SCH_PENDING_FEATURES = null;
			projectsMapDrawFeatures(ff);
			window.SCH_MAP_FEATURES = ff.length;
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
						[r.longitude - 0.002,r.latitude - 0.0005], // southwestern corner of the bounds
						[r.longitude + 0.002,r.latitude + 0.0035] // northeastern corner of the bounds
					], {
						padding: [50, 50],
						maxZoom: 15,
						duration: 1500,
						animate: true,
						essential: true,
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




		$(document).ready(function() {
			// Boundary overlay control (.db-map-control) — open/close, aria sync,
			// outside-click close. Same behaviour as /districts and /projects.
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


			datatable = $('#myTable').DataTable({
				ajax: function (url, cb) {
					fapireq(dataurl, cb);
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
					@if ($details['detFlag'] ?? null)
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
				]

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
						});
						$("div.toolbar .row").append('');

						@foreach ($details['filters'] as $i=>$v)
							@if ($v)
								setTimeout(function(){
									$('#filter-{{ $i }}').find('[value*="{!! $v !!}"]').prop('selected',true).trigger('change')
								}, 500 + 1000 * {{ $i }});
							@endif
						@endforeach
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

			$('#myTable_length label').html($('#myTable_length label').html().replace(' entries', ''));

			// if map is displayed updates and draws projects from GEO_JSON field
			datatable.on('draw', function () {
				drawProjects('all');
			});

			$('#myTable tbody').on('click', 'td:not(.details-control)', function () {
				var tr = $(this).closest('tr');
				var row = datatable.row(tr);
				r = row.data()
				if (r['GEO_JSON']) {
					var geo_json = JSON.parse(r['GEO_JSON'].replaceAll('""', '"'))
					var pr = geo_json.properties
					fitBounds([[pr.W, pr.S], [pr.E, pr.N]])
				}
			})


			// makes sortable html fields like 9.4 years late, $25,764 over
			$.fn.dataTable.ext.type.order['html-pre'] = function (data) {
				var d = data.replace(/>-</g, '>0<');
				d = d.replace(/<span class="(bad)"[^>]*>/g, '-');
				d = d.replace(/[,$]|years|late|<[^>]+>|earl\S+|%/g, '');
				d = d.replace(/NA|NaN|on time/g, '0');
				m = 1
				for (const[rg, tmpM] of [[/K$/g, 1000], [/M$/g, 1000000], [/B$/g, 1000000000]]) {
					if (d.match(rg)) {
						m = tmpM;
						d = d.replace(rg, '');
					}
				}
				d = d.match(/[-\d\.]+/g) ? parseFloat(d) * m : d;
				return d;
			};

			@if($sdStatsUrl ?? null)
				{{-- ⚠ `schoolStatTiles` (script.js) owns the read, because this
				     block was duplicated verbatim in distsection.blade.php and both
				     copies dereferenced `resp.data[0]` unguarded. --}}
				fapireq('{!! $sdStatsUrl !!}', function (resp) {
					schoolStatTiles(resp, 'schoolStatsNote')
				})
			@endif



			// Initialize Map
			projectsMapInit();
			// `load` may already have fired by the time this binds; `loaded()`
			// covers that, and mapbox no-ops a late `on('load')` handler.
			if (typeof map !== 'undefined') {
				if (map.loaded && map.loaded()) { SCH_MAP_READY = true; schDrawWhenReady(null); }
				map.on('load', function () { SCH_MAP_READY = true; schDrawWhenReady(null); });
			}
			
			// Initialize District Switch
			setTimeout(function(){
					$('#sd-switch').click();
			}, 2500);

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


		function goSdOnClick(e) {
			var bbox = [
				[e.point.x, e.point.y],
				[e.point.x, e.point.y]
			];
			var features = map.queryRenderedFeatures(bbox, {
				layers: ['sdFHH']
			});

			var filter = features.reduce(
				function(memo, feature) {
					memo.push(feature.properties['nameCol']);
					return memo;
				},
				['in', 'nameCol']
			);

			window.open(`/d/sd-${filter[2]}-schools-district-${filter[2]}/schools`, '_self');
		}

		// Legacy toggleMap removed.
		// Legacy drawProjects updated:

		function drawProjects(pages) {	// 'all',     'current'
			// Always active now
			// var mapIsActive = !$('#map_container').attr('style')
			// if (!mapIsActive) return;

			var api = $('#myTable').dataTable().api();
			var modifier = {
				order:  'current',  // 'current', 'applied', 'index',  'original'
				page:   pages,      // 'all',     'current'
				search: 'applied',     // 'none',    'applied', 'removed'
			}
			var features = [];
			
			// Define color palette for school categories
			const categoryColors = {
				'Elementary': '#4e79a7',      // Blue
				'Junior High-Intermediate-Middle': '#f28e2b', // Orange
				'High school': '#e15759',     // Red
				'K-12 all grades': '#76b7b2', // Teal
				'K-8': '#59a14f',             // Green
				'Early Childhood': '#edc948', // Yellow
				'Secondary School': '#b07aa1',// Purple
				'Collaborative or Multi-graded': '#ff9da7', // Pink
				'Ungraded': '#9c755f'         // Brown
			};
			const defaultColor = '#bab0ac'; // Gray

			api.rows('', modifier).data().each(function (r, i) {
				if (r['GEO_JSON']) {
					try {
						r['GEO_JSON'] = r['GEO_JSON'].replaceAll('""', '"')
						geo_json = null
						geo_json = JSON.parse(r['GEO_JSON'])
						
						// Assign color based on Category
						// Check if Category exists in properties, otherwise fallback
						const category = geo_json.properties['CATEGORY']; 
						geo_json.properties['custom_color'] = categoryColors[category] || defaultColor;

						features.push(geo_json)
					} catch (error) {
						console.error(error);
					}
				}
			});
			schDrawWhenReady(features);
		}


	</script>

	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-12 organization_data">
					<h2>NYC Schools</h2>
					<p class="lead">We’ve created profiles for all NYC schools that combines data from over a dozen datasets from multiple city agencies.</p>
				</div>
			</div>


			<div id="stats_collapse" class="collapse show mt-2 mb-4">
				<div class="row justify-content-center my-2">
					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									# of Schools
									<h2 id="schools_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									# of Students
									<h2 id="students_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									# of Projects
									<h2 id="prj_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									Projects Budget
									<h2 id="prj_budget" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									Project Costs
									<h2 id="prj_costs" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									Project Cost per Student
									<h2 id="pcosts_per_student" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

				</div>

				{{-- ⚠ A FAILED STATS REQUEST IS NOT AN EMPTY CITY. Written by
				     `schoolStatTiles`; hidden while the figures are fine. --}}
				<div class="row justify-content-center">
					<div class="col-md-12">
						<p id="schoolStatsNote" class="text-center text-muted small mb-0" style="display:none;"></p>
					</div>
				</div>

			</div>


			<div class="row">
				<div id="map_container" class="col-12 mb-0 position-relative" style="min-height:540px!important;">
					<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;"></div>
					
					{{-- Address search, top-left — the same overlay pattern /districts
					     and /projects use, replacing the combined "Search & Layers" flyout. --}}
					<div class="db-map-search" style="top: var(--db-space-2); left: var(--db-space-2);">
						<i class="bi bi-search"></i>
						<input id="addrSearch" type="text" placeholder="Search an address…" aria-label="Enter address to find schools" onkeydown="addrSearchKeyPress(this)" autocomplete="off">
						<button class="db-map-search-go" id="addrSearchBtn" type="button" onclick="addrSearch();" data-bs-toggle="popover" data-content="" data-placement="bottom" data-trigger="manual" aria-label="Search address"><i class="bi bi-arrow-right"></i></button>
					</div>

					{{-- Boundary overlays, top-right.
					     ⚠ THE SWITCH IDS ARE LOAD-BEARING AND UNCHANGED — `script.js` binds
					     each layer by ID, so a renamed control still looks right while
					     toggling nothing.
					     ⚠ The `<hr>` per row is the layer's colour key, painted by
					     `$('label[for="…-switch"] hr').attr('style', 'background-color: …')`.
					     The old panel had none, so this page showed boundary toggles with no
					     colour swatches at all. --}}
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


			<div class="row justify-content-center map_right">
				<div id="data_container" class="col-12">
					<div class="table-responsive" style="position:relative;">
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
					<x-db.data-provenance mode="page" :datasets="$datasets" id="schoolsDs" />
				</div>
		</div>

	</div>

	<script>
		function changeToggle (e) {
			//console.log($(e.target).next("label")[0].innerHTML)
			$('#change_district').html($(e.target).next("label")[0].innerHTML);
		}
		$('#toggle_boundries').click( function (e) {
			$(this).next('.dropdown-menu').toggleClass('show');
		})

		$(".filter_icon").click(function() {
			//console.log($('.toolbar').is(':visible'))
			if(!$('.toolbar').is(':visible')) {
				$('.filter_icon').addClass('position_change');
			}else {
				$('.filter_icon').removeClass('position_change');
			}
			$(".toolbar").toggle();
		});
	</script>

@endsection
