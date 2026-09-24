@php
	$dpTypeLabel  = ['cd' => 'Community District', 'cc' => 'City Council District', 'nta' => 'Neighborhood', 'sd' => 'School District'][$type] ?? 'District';
	$dpTypePlural = ['cd' => 'Community Districts', 'cc' => 'City Council', 'nta' => 'Neighborhoods (NTA)', 'sd' => 'School Districts'][$type] ?? 'Districts';
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
					<h1 class="db-profile-title" style="display:inline-block; margin-right: var(--db-space-2);"></h1>
					@if($altName)
						<a class="dp-census" href="https://popfactfinder.planning.nyc.gov/explorer/cdtas/{{ $altName }}/" target="_blank" rel="nofollow">View District Census Data <i class="bi bi-box-arrow-up-right"></i></a>
					@endif
					<h5 id="linked_agency" class="db-profile-subtitle mt-2 mb-0" style="font-size: var(--db-text-md);"></h5>
					@if($member['NAME'] ?? null)
						<p class="db-profile-subtitle mt-1 mb-0">Member:
							<a href="https://council.nyc.gov/district-{{ $id }}/" target="_blank"><strong>{{ $member['NAME'] }}</strong></a>, {{ $member['POLITICAL PARTY'] }}, {{ $member['BOROUGH'] }}
						</p>
					@endif
				</div>
			</div>
		</div>
	</div>
</div>

@include('sub.distheader', ['active' => $section])

<script>
		var datasets = {!! json_encode(array_values($datasets)) !!}
		function details(d) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
			  @foreach ((array)($details['details'] ?? []) as $h=>$f)
				(d["{{ $f }}"] ? '<tr><td>{{ $h }}:</td><td>'+d["{{ $f }}"]+'</td></tr>' : '') +
			  @endforeach
			'</table>';
		}

		var datatable = null
		$(document).ready(function() {
			loadFinStat();
			datatable = $('#myTable').DataTable({
				ajax: function (url, cb) {
					fapireq('{!! $url !!}', cb);
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

						@foreach ($details['filters'] as $i=>$v)
							@if ($v)
								setTimeout(function(){
									$('#filter-{{ $i }}').find('[value*="{!! $v !!}"]').prop('selected',true).trigger('change')
								}, 500 + 1000 * {{ $i }});
							@endif
						@endforeach

						{{-- ⚠⚠ THE PUBLICATION-DATE FILTER BELONGS TO THE RETIRED SERIES.
						     It hardcodes `columns([1])` and auto-selects that column's LAST
						     option. Under `capitalprojectsdollarscomp` column 1 was
						     `Publication Date`; on the spine it is `Agency`, so the control
						     would build a dropdown of agency names, pick the last, and filter
						     the table to one agency — the same defect that read
						     "Showing 1 to 1 of 1 (filtered from 2,798)" on the ORG tab, which
						     is why this one was gated before it could ship rather than after.
						     ⚠ Gated on a contract flag, not deleted, so a dataset that really
						     has a publication-date column can switch it back on. --}}
						@if ($details['pubDateFilter'] ?? false)
						/* custom pub_date filter on top-right */
						this.api().columns([1]).every(function (c,a,i) {
							var delim = {!! json_encode($details['fltDelim']) !!};
							var column = this;
							var select = $('<select class="filter mt-1" style="width:100%;" id="filter-' + column[0][0] + '" name="filter-' + column[0][0] + '" aria-controls="myTable"><option value="" selected>- ' + $(column.header()).text() + ' -</option></select>')
								.appendTo($("#pub_date_filter"))
								.on('change', function () {
									var val = $(this).val()
									column
										.search(val ? val : '', false, false)
										.draw();
									loadFinStat();
								});
							select.wrap('<div class="drop_dowm_select"></div>');

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
							$('#filter-1 option:last-child').prop('selected',true).trigger('change')
						}, 500);						
						
						@endif
						setTimeout(function(){
							initPopovers();
						}, 1000);

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
				}
			});

			$('#myTable_length label').html($('#myTable_length label').html().replace(' entries', ''));
		
			// makes sortable html fields like 9.4 years late, $25,764 over, $64.2M over
			$.fn.dataTable.ext.type.order['html-pre'] = function (data) {
				var d = data.replace(/-/g, '');
				d = d.replace(/<span class="(bad)"[^>]*>/g, '-');
				d = d.replace(/[,$]|years|late|<[^>]+>|earl\S+/g, '');
				d = d.replace(/NA|NaN|on time|^-$/g, '0');
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
		
		});
		
		// ⚠⚠ THE RETIRED-SERIES LOOP IS GONE, NOT LEFT INERT. The capital tiles are
		// server-rendered from the spine now, so `$finStatUrls` is empty and this
		// loop could never run — but it still NAMED `#over_budg_am`, `#orig_cost`
		// and `#curr_cost` and still multiplied by 1000. Dead code that names the
		// thing we removed is how a later reader concludes the tiles are still
		// AJAX-hydrated from the retired series; the answer for dead code here is
		// delete, not leave it unreachable.
		// ⚠ It also read `$('#filter-1 option:selected')` — the publication-date
		// control, which is gated off on the spine, so the value was about to
		// become an agency name silently substituted into a URL.
		// The function survives because its two callers rely on the popovers.
		function loadFinStat() {
			setTimeout(function(){
				initPopovers();
			}, 1000);
		}
		
		
</script>

<div class="inner_container">
	<div class="container mb-5">
		<div class="row">
			<div class="col-md-9 organization_data">
				<p class="mb-0">{!! nl2br($details['description'] ?? ($dataset['Descripton'] ?? '')) !!}</p>
			</div>
			<div class="col-md-3 mt-2" id="org_summary">
				<table class="table-sm stats-table" width="100%">
				<thead>
					<tr>
					<th scope="col" width="50%" class="text-center px-0" data-content="See the project info published on specific dates.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
					<th scope="col" width="50%" id="pub_date_filter"></th>
					</tr>
				</thead>
				<tbody>
					<tr>
						<td colspan=2 class="text-right px-0 pt-0 pb-3">
							<button class="type-label my-2 dropdown-toggle" data-bs-toggle="collapse" data-bs-target="#stats_collapse" aria-expanded="true" aria-controls="stats_collapse"><small>Show/Hide Stats</small></button>
						</td>
					</tr>
				</tbody>
				</table>
			</div>
		</div>
	
		<div id="stats_collapse" class="collapse show mt-2 mb-4">
			<div class="db-stat-grid">
				@php
					// ⚠⚠ SERVER-RENDERED FROM THE SPINE. These eight tiles used to
					// hydrate by AJAX from `/get/districts/pstats-*/…/pubdate` over
					// `capitalprojectsdollarscomp`, multiplying by 1000 because that
					// series is denominated in THOUSANDS.
					// ⚠⚠ `Amount Over Budget` IS DELIBERATELY NOT REPRODUCED. It is the
					// label this section documents as carrying TWO definitions — every
					// row's budget difference globally, but only the NEGATIVE ones per
					// district — so repointing it would preserve the defect under new
					// data. The rebuilt Overview drops it and so does this.
					$dCap   = is_array($capital ?? null) ? $capital : [];
					$dCapOk = !empty($dCap['available']) && !empty($dCap['found']);
					$dSched = $dCap['schedule'] ?? [];
					$dMoney = [];
					foreach (($dCap['money']['measures'] ?? []) as $dm)
						$dMoney[$dm['key'] ?? ''] = $dm;
					$dFmtN = function ($v) { return is_numeric($v) ? number_format((float) $v) : '—'; };
					$dFmtB = function ($v) {
						if (!is_numeric($v)) return '—';
						$v = (float) $v;
						if (abs($v) >= 1000000000) return '$' . number_format($v / 1000000000, 1) . 'B';
						if (abs($v) >= 1000000) return '$' . number_format($v / 1000000, 1) . 'M';
						return '$' . number_format($v);
					};
					// ⚠ Populations travel with the money, because no two of these
					// measures are over the same set of projects.
					$dPop = function ($k) use ($dMoney, $dFmtN) {
						$n = $dMoney[$k]['population'] ?? null;
						return is_numeric($n) ? $dFmtN($n) . ' projects' : null;
					};
					$dTracked = $dCap['projects'] ?? null;
				@endphp
				@if ($dCapOk)
					<div class="db-stat">
						<div class="db-stat-label">Projects in this district</div>
						<div class="db-stat-value">{{ $dFmtN($dTracked) }}</div>
					</div>
					<div class="db-stat">
						<div class="db-stat-label">In the current plan</div>
						<div class="db-stat-value">{{ $dFmtN($dCap['in_current_plan'] ?? null) }}</div>
						@if(is_numeric($dTracked))<div class="db-stat-sub">of {{ $dFmtN($dTracked) }} attributed here</div>@endif
					</div>
					<div class="db-stat">
						<div class="db-stat-label">Planned commitments</div>
						<div class="db-stat-value">{{ $dFmtB($dMoney['planned_usd']['value'] ?? null) }}</div>
						@if($dPop('planned_usd'))<div class="db-stat-sub">{{ $dPop('planned_usd') }}</div>@endif
					</div>
					<div class="db-stat is-accent">
						<div class="db-stat-label">Spent</div>
						<div class="db-stat-value">{{ $dFmtB($dMoney['spent_usd']['value'] ?? null) }}</div>
						@if($dPop('spent_usd'))<div class="db-stat-sub">{{ $dPop('spent_usd') }}</div>@endif
					</div>
					<div class="db-stat">
						<div class="db-stat-label">With a published schedule</div>
						<div class="db-stat-value">{{ $dFmtN($dSched['with_published_schedule'] ?? null) }}</div>
						@if(is_numeric($dTracked))<div class="db-stat-sub">of {{ $dFmtN($dTracked) }} attributed here</div>@endif
					</div>
				@else
					{{-- ⚠ A silently missing block reads as "this district has no capital
					     programme". Zero is not failure, and failure is not zero. --}}
					<div class="db-stat"><div class="db-stat-label">Capital programme</div><div class="db-stat-value">—</div><div class="db-stat-sub">figures not available right now</div></div>
				@endif
			</div>
		</div>

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
</div>


@if (($dataset['Public Note'] ?? null))
	<div class="container mb-3">
		<p class="note_bottom db-page-lead">{{ str_replace('\\n', '', nl2br($dataset['Public Note'])) }}</p>
	</div>
@endif
<div class="inner_container">
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
			<x-db.data-provenance mode="page" :datasets="$datasets" id="distprojectsectionDs" />
		</div>
	</div>
</div>