@php
	$dpTypeLabel  = ['cd' => 'Community District', 'cc' => 'City Council District', 'nta' => 'Neighborhood', 'sd' => 'School District'][$type] ?? 'District';
	$dpTypePlural = ['cd' => 'Community Districts', 'cc' => 'City Council', 'nta' => 'Neighborhoods (NTA)', 'sd' => 'School Districts'][$type] ?? 'Districts';
	$dpCensusUrl  = $altName
		? "https://popfactfinder.planning.nyc.gov/explorer/cdtas/{$altName}/"
		: ($type == 'nta' ? "https://popfactfinder.planning.nyc.gov/explorer/ntas/{$id}/" : null);
@endphp

<div class="db-profile-header">
	<div class="inner_container">
		<div class="container">
			<nav class="db-breadcrumb" aria-label="breadcrumb">
				<a href="{{ route('districts') }}">Districts</a>
				<span class="db-breadcrumb-sep">/</span>
				<a href="{{ route('districtsPresetType', ['type' => $type]) }}">{{ $dpTypePlural }}</a>
			</nav>

			<div class="db-profile-header-top">
				<div class="db-profile-main">
					<div class="db-profile-kicker">
						<span class="db-type-label">{{ $dpTypeLabel }}</span>
					</div>
					{{-- mapAction() writes the district name into this h1 --}}
					<h1 class="db-profile-title" style="display:inline-block; margin-right: var(--db-space-2);"></h1>
					@if($dpCensusUrl)
						<a class="dp-census" href="{{ $dpCensusUrl }}" target="_blank" rel="nofollow">View District Census Data <i class="bi bi-box-arrow-up-right"></i></a>
					@endif

					@if($member['NAME'] ?? null)
						<p class="db-profile-subtitle mt-2 mb-0">Represented by
							<strong>{{ $member['NAME'] }}</strong>, a {{ $member['POLITICAL PARTY'] }} in {{ $member['BOROUGH'] }}.
							See their <a href="https://intro.nyc/councilmembers/{{ $id }}/" target="_blank" rel="nofollow">legislative record</a>.
						</p>
					@endif

					@if($linkedAgencyUrl ?? null)
						<span id="linked_agency_wrapper" style="display: none;">
							<h2 id="linked_agency" class="db-profile-subtitle mt-2 mb-0" style="font-size: var(--db-text-md);"></h2>
							<div class="dp-meta">
								<div class="dp-row"><span class="dp-label">Chair</span><span class="dp-value" id="cb-chair"></span></div>
								<div class="dp-row"><span class="dp-label">Office Address</span><span class="dp-value" id="cb-address"></span></div>
								<div class="dp-row"><span class="dp-label">Office Phone</span><span class="dp-value" id="cb-phone"></span></div>
								<div class="dp-row"><span class="dp-label">District Manager</span><span class="dp-value" id="cb-manager"></span></div>
								<div class="dp-row"><span class="dp-label">Board Meeting</span><span class="dp-value" id="cb-bmeeting"></span></div>
								<div class="dp-row"><span class="dp-label">Office Fax</span><span class="dp-value" id="cb-fax"></span></div>
								<div class="dp-row"><span class="dp-label">Website</span><span class="dp-value"><a target="_blank" href="" id="cb-site-a"><span id="cb-site"></span></a></span></div>
								<div class="dp-row"><span class="dp-label">Cabinet Meeting</span><span class="dp-value" id="cb-cmeeting"></span></div>
								<div class="dp-row"><span class="dp-label">Office Email</span><span class="dp-value" id="cb-email"></span></div>
							</div>
						</span>
					@endif
				</div>
			</div>

			@if($type == 'sd')
				<div id="stats_collapse" class="collapse show">
					<div class="db-stat-grid mt-3 mb-2">
						<div class="db-stat"><div class="db-stat-label"># of Schools</div><div id="schools_no" class="db-stat-value prj_stat">&nbsp;</div></div>
						<div class="db-stat"><div class="db-stat-label"># of Students</div><div id="students_no" class="db-stat-value prj_stat">&nbsp;</div></div>
						<div class="db-stat"><div class="db-stat-label"># of Projects</div><div id="prj_no" class="db-stat-value prj_stat">&nbsp;</div></div>
						<div class="db-stat"><div class="db-stat-label">Projects Budget</div><div id="prj_budget" class="db-stat-value prj_stat">&nbsp;</div></div>
						<div class="db-stat"><div class="db-stat-label">Project Costs</div><div id="prj_costs" class="db-stat-value prj_stat">&nbsp;</div></div>
						<div class="db-stat"><div class="db-stat-label">Cost per Student</div><div id="pcosts_per_student" class="db-stat-value prj_stat">&nbsp;</div></div>
					</div>
					{{-- ⚠ A FAILED STATS REQUEST IS NOT AN EMPTY DISTRICT. Written by
					     `schoolStatTiles`; hidden while the figures are fine. --}}
					<p id="schoolStatsNote" class="text-muted small mb-0" style="display:none;"></p>
				</div>
			@endif
		</div>
	</div>
</div>

@include('sub.distheader', ['active' => $section])

<script>
		var datasets = {!! json_encode(array_values($datasets)) !!}
		function details(d) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
			  @foreach ((array)$details['details'] as $h=>$f)
				(d["{{ $f }}"] ? '<tr><td>{{ $h }}:</td><td>'+d["{{ $f }}"]+'</td></tr>' : '') +
			  @endforeach
			'</table>';
		}


		var datatable = null
		$(document).ready(function() {
			datatable = $('#myTable').DataTable({
				ajax: function (url, cb) {
					fapireq('{!! $url !!}', cb);
			    },

				buttons: [{
                    extend: 'colvis',
                    "className": 'btn_eyeicon',
                    columnText: function ( dt, idx, title ) {
                        return (idx+1)+': '+(title ? title : 'details');
                    }
                }],
				deferRender: true,
				language: { emptyTable: '<div class="db-empty"><div class="db-empty-icon"><i class="bi bi-inbox"></i></div><div class="db-empty-title">No data for this district</div><div class="db-empty-text">This dataset has no records for the selected district.</div></div>' },
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
                        defaultContent: '',
                        @if ($details['visible'][$i])
                            visible: true
                        @else
                            visible: false
                        @endif
                        }
                    @endforeach
                ],

				@if ($details['filters'])
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

							// ⚠ The DEFAULT VALUE half of `filters`, mirroring
							// schoolSection.blade.php. Applied only when a non-null value
							// is declared, so every pre-existing district section (all of
							// which declare null) behaves exactly as before.
							var defs = {!! json_encode($details['fltDefaults'] ?? (object)[]) !!};
							if (defs[c] !== undefined && defs[c] !== null) {
								select.val(defs[c]);
								column.search(defs[c] ? defs[c] : '', false, false).draw();
							}
						});

						@foreach ($details['filters'] as $i=>$v)
							@if ($v)
								setTimeout(function(){
									$('#filter-{{ $i }}').find('[value*="{!! $v !!}"]').prop('selected',true).trigger('change')
								}, 500 + 1000 * {{ $i }});
							@endif
						@endforeach
					}
				@endif
			});

			$('#filter-1').find('[value*="20190619"]').prop('selected',true).trigger('change');

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
				}
			});

			$('#myTable_length label').html($('#myTable_length label').html().replace(' entries', ''));

			@if($linkedAgencyUrl ?? null)
				fapireq('{!! $linkedAgencyUrl !!}', function (resp) {
					if (resp['data'][0]) {
						$('#linked_agency_wrapper').show()
						dd = resp['data'][0]
						$('#linked_agency').html(`Represented by <a href="/o/${resp['data'][0]['id']}-${slug(resp['data'][0]['name'])}" rel="nofollow">${dd['name']}</a>`)
						var cb_details = {'cb-chair': dd['CB Chair'], 'cb-address': dd['CB Office Address'], 'cb-phone': dd['CB Office Phone'], 'cb-manager': dd['CB District Manager'], 'cb-bmeeting': dd['CB Board Meeting'], 'cb-fax': dd['CB Office Fax'], 'cb-site': dd['CB Website'], 'cb-cmeeting': dd['CB Cabinet Meeting'], 'cb-email': dd['CB Office Email']}
						for (const [k, v] of Object.entries(cb_details))
							$('#' + k).html(v)
						$('#cb-site-a').attr('href', dd['CB Website'])
					}
				})
			@endif


			@if($sdStatsUrl ?? null)
				{{-- ⚠ Guarded by `schoolStatTiles` (script.js): this block was the
				     same unguarded `resp.data[0]` read that threw on /schools. --}}
				fapireq('{!! $sdStatsUrl !!}', function (resp) {
					schoolStatTiles(resp, 'schoolStatsNote')
				})
			@endif




		});
</script>
<div class="inner_container">
	<div class="container mb-5" style="padding-top: var(--db-space-3);">
		@if (trim($details['description'] ?? ($dataset['Descripton'] ?? '')))
			<p class="db-page-lead organization_data">{!! nl2br($details['description'] ?? ($dataset['Descripton'] ?? '')) !!}</p>
		@endif
		<div class="db-table-wrap mt-3">
			<div id="data_container" class="table-responsive">
				<table id="myTable" class="db-table display table-striped table-hover" style="width:100%;">
					<thead>
						<tr>
							@if ($details['detFlag'])
								<th></th>
							@endif
							@foreach ($details['hdrs'] as $name)
								<th>{{ $name }}</th>
							@endforeach
						</tr>
					</thead>
				</table>
			</div>
		</div>
	</div>
	@if (($dataset['Public Note'] ?? null))
		<div class="container mb-3">
			<p class="note_bottom db-page-lead">{{ nl2br($dataset['Public Note']) }}</p>
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
			<x-db.data-provenance mode="page" :datasets="$datasets" id="distsectionDs" />
		</div>
	</div>


</div>
