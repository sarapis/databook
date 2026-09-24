@extends('layout')


@section('head')
	<meta name="description" content="{{ $snippet }}" />
	<meta rel="canonical" href="{!! $canonicalUrl !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	@include('sub.orgheader', ['active' => $section])

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>

	<script>
		function details(d) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
			  @foreach ((array)$details['details'] as $h=>$f)
				(d["{{ $f }}"] ? '<tr><td>{{ $h }}:</td><td>'+d["{{ $f }}"]+'</td></tr>' : '') +
			  @endforeach
			'</table>';
		}

		function toggleMap() {
			var isActive = $('#map_button').attr('class') == 'btn btn-outline map_btn'
			if (isActive) {
				$('#map_button').attr('class', 'btn map_btn')
				$('#data_container').attr('class', 'col')
				$('.toolbar ').css('display', 'inline-block')
				$('#map_container').hide()
			} else {
				$('#data_container').attr('class', 'col col-6')
                const divHeight = $('#data_container').height()
                console.log(divHeight, '3' , $('#map_container').attr('style'));
                $('#map_container').css("min-height", divHeight+'px')
				$('#map_button').attr('class', 'btn btn-outline map_btn')
				$('#map_container').show()
				orgSectionMapInit({!! json_encode($map) !!});
			}
		}

		function mapAction(filter, code, col) {
			if (filter.length == 2)
				datatable.columns([col]).search('').draw()
			else
				datatable.columns([col]).search(filter[2]).draw()
		}

		var datatable = null
		$(document).ready(function() {
			datatable = $('#myTable').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $url !!}", function (payload) {
						cb(payload);
						// ⚠ Only on a genuinely empty result. A section with rows must
						// never show the note, or it becomes wallpaper and stops meaning
						// anything — the "worth consolidating?" badge lesson.
						try {
							// ⚠⚠ A FAILED REQUEST IS NOT AN EMPTY RESULT. fapireq returns
							// {data: [], error, status} on failure, so without this a 500
							// or a 429 would render "this dataset does not list this
							// organization" — a confident coverage claim made from a
							// broken request. fapireq's own comment warns about this and
							// the first version of the note ignored it.
							if (payload && payload.error) { return; }
							var rows = (payload && (payload.data || payload.rows)) || payload;
							if (Array.isArray(rows) && rows.length === 0) {
								$('#section-scope-note').show();
								$.getJSON("{!! $coverageUrl !!}", function (c) {
									var n = c && c.rows && c.rows[0] && c.rows[0].orgs;
									if (n) {
										$('#section-scope-detail').text(
											'This dataset covers ' + n + ' organizations in total.');
									}
								});
								$.getJSON("{!! $contractWorkUrl !!}", function (w) {
									var r = (w && w.rows) || [];
									if (!r.length) { return; }
									var total = 0, html = '';
									r.forEach(function (c) {
										var amt = parseFloat(c.amount) || 0; total += amt;
										html += '<tr><td>' + (c.ctr_id || c.contract_id || '') + '</td><td>' +
											(c.agency || '') + '</td><td>' + (c.contract_title || '') + '</td><td>' +
											(c.start_date || '') + '</td><td>' + (c.end_date || '') +
											'</td><td class="text-end">$' +
											amt.toLocaleString(undefined, {maximumFractionDigits: 0}) + '</td></tr>';
									});
									$('#ocw-body').html(html);
									$('#ocw-summary').text(
										r.length + ' contract' + (r.length === 1 ? '' : 's') +
										', $' + (total / 1e6).toLocaleString(undefined,
											{maximumFractionDigits: 1}) + 'M in total.');
									$('#org-contract-work').show();
								});
							}
						} catch (e) { /* the note is a nicety; never break the table */ }
					});
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
                        {
							data: {!! $f !!},
							@if ($details['visible'][$i])
								visible: true
							@else
								visible: false
							@endif
                        },
                    @endforeach
					{data: null, visible: false}
                ],

				@if (($details['filters'] ?? null) || ($details['pubdate_filter'] ?? null))
					initComplete: function () {
						@if ($details['filters'])
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

							@foreach ($details['filters'] as $i=>$v)
								@if ($v)
									setTimeout(function(){
										$('#filter-{{ $i }}').find('[value*="{!! $v !!}"]').prop('selected',true).trigger('change')
									}, 500 + 1000 * {{ $i }});
								@endif
							@endforeach
						@endif
						
						@if ($details['pubdate_filter'] ?? null)
							this.api().columns([{{ array_keys($details['pubdate_filter'])[0] }}]).every(function (c,a,i) {
								var column = this;
								var select = $('<select class="filter" style="width:100%;" id="filter-' + column[0][0] + '" name="filter-' + column[0][0] + '" aria-controls="myTable"></select>')
									.appendTo($("#pub_date_filter"))
									.on('change', function () {
										var val = $(this).val()
										column
											.search(val ? val : '', false, false)
											.draw();
										pubDateFilterChange();
									});
								select.wrap('<div class="drop_dowm_select"></div>');

								var tt = []
								dd = column.data()

								column.data().each(function (d, j) {
									d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
									tt.push(d)
								})
								tt = [...new Set(tt)]

								//tt.sort().forEach(function (d, j) {
								sortUsDatesList(tt).forEach(function (d, j) {
									select.append('<option value="'+d+'">'+d+'</option>')
								});
							});
							
							setTimeout(function(){
									$('#filter-{{ array_keys($details["pubdate_filter"])[0] }}').find('{{ array_values($details["pubdate_filter"])[0] }}').prop('selected',true).trigger('change')
								}, 100);
						@endif
						

						@if ($details['script'] ?? null)
							{!! $details['script'] !!}
						@endif
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
			
			setTimeout(function(){
				initPopovers();
			}, 1000);
		});
	</script>
	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				@if (($details['charts'] ?? null) || ($details['pubdate_filter'] ?? null))
				  <div class="col-md-9 organization_data">
			    @else
				  <div class="col-md-12 organization_data">
			    @endif
					<h4>{{ $details['sectionTitle'] ?? ($details['fullname'] ?? ($dataset['Name'] ?? ($slist[$section] ?? $section))) }}
						@if ($section == 'notices/events')
							&nbsp;<a title="Copy Events iCal feed link" onclick="copyLinkM(this);"><i class="bi bi-calendar-event share_icon_container" data-bs-toggle="popover" data-content="Events iCal feed link copied to clipboard" placement="left" trigger="manual" style="cursor: pointer; top:-3px;"></i></a>
						@endif
						@if ($section == 'notices/all')
							&nbsp;<a title="Copy News RSS feed link" onclick="copyLinkM(this, 'news-rss-link');"><i class="bi bi-rss share_icon_container" data-bs-toggle="popover" data-content="News RSS feed link copied to clipboard" placement="left" trigger="manual" style="cursor: pointer; top:-3px;"></i></a>
							<textarea id="news-rss-link" class="details">{!! route('orgRSSNews', ['id' => $id]) !!}</textarea>
						@endif
					</h4>
					<p>{!! nl2br($details['description'] ?? ($dataset['Descripton'] ?? '')) !!}</p>
					{{-- ⚠⚠ AN EMPTY SECTION TABLE IS AMBIGUOUS AND RESOLVES THE
					     REASSURING WAY. Every org is offered every section, so a body
					     the dataset does not cover renders an empty table that reads
					     as "this organization has none" rather than "this dataset does
					     not list organizations like this one". Revealed by JS ONLY when
					     the table actually returns zero rows, so a populated section
					     never shows it. --}}
					<div id="section-scope-note" class="db-alert db-alert-info mt-3" style="display:none">
						<div class="db-alert-body">
							<i class="bi bi-info-circle"></i> <strong>Nothing here for this organization.</strong>
							<span id="section-scope-detail"></span>
							An empty table means this dataset does not list this organization &mdash;
							not necessarily that no such activity exists. Datasets cover different sets
							of bodies: the capital plan, for example, lists only the agencies that hold
							their own capital budget lines.
						</div>
					</div>

					{{-- ⚠ THE OTHER LENS. A body that is not a City agency can still do
					     substantial City work — as a VENDOR. Shown only when the
					     agency-keyed section is empty AND we have a curated, EXACT vendor
					     name for this org, so it can never appear speculatively. --}}
					<div id="org-contract-work" class="mt-3" style="display:none">
						<h5 class="mb-1">Work delivered under contract</h5>
						<p class="db-text-muted" style="font-size:var(--db-text-sm)">
							This organization is not an agency in the dataset above, but the City
							contracts <em>with</em> it. <span id="ocw-summary"></span>
						</p>
						<div class="table-responsive">
							<table class="db-table table-striped" style="width:100%">
								<thead><tr>
									<th>Contract</th><th>Agency</th><th>Title</th>
									<th>Start</th><th>End</th><th class="text-end">Amount</th>
								</tr></thead>
								<tbody id="ocw-body"></tbody>
							</table>
						</div>
					</div>
					@if ($section == 'jobs')
						<div class="db-alert db-alert-info mt-3">
							<div class="db-alert-body">
								<i class="bi bi-info-circle"></i> <strong>Scope:</strong> this is the City's
								<strong>central careers portal</strong> only. Employers that run their own hiring
								systems do not appear here &mdash; including the Department of Education, CUNY,
								the Board of Elections, the City Council, the District Attorneys and the Borough
								Presidents. So this is <strong>not a count of every City vacancy</strong>, and an
								agency showing no openings may simply hire elsewhere.
							</div>
						</div>
					@endif
					@if ($map ?? null)
						<button id="map_button" class="btn map_btn" style="float:right;" onclick="toggleMap();"><img src="/img/map_location.png"></button>
					@endif
				</div>
				
				@if (($details['charts'] ?? null) || ($details['pubdate_filter'] ?? null))
					<div class="col-md-3 pt-4" id="org_summary">
						<table class="table-sm stats-table" width="100%">
						@if ($details['pubdate_filter'] ?? null)
							<thead>
								<tr>
								<th scope="col" width="50%" class="text-center px-0" data-content="See info published on specific dates.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
								<th scope="col" width="50%" id="pub_date_filter"></th>
								</tr>
							</thead>
						@endif
						@if ($details['charts'] ?? null)
							<tbody>
								<tr>
									<td colspan=2 class="text-right px-0 pt-0 pb-3">
										<button class="type-label my-2 dropdown-toggle" data-bs-toggle="collapse" data-bs-target="#charts_collapse" aria-expanded="true" aria-controls="charts_collapse"><small>Show/Hide Stats</small></button>
									</td>
								</tr>
							</tbody>
						@endif
						</table>
					</div>
				@endif
			</div>
			
			@if ($details['charts'] ?? null)
				<div id="charts_collapse" class="collapse my-1 show">
					<div class="row justify-content-center">
						<div class="col-12 mb-2">
							@include('orgCharts.' . $section)
						</div>
					</div>
				</div>
			@endif
				
				
			<div class="row justify-content-center map_right">
				@if ($map ?? null)
					<div id="map_container" class="col-6" style="display:none;">
						<!-- controls -->
						<div id="map-controls">
							<div class="select_district">
								<img src="/img/map_icon.png">
								<ul class="inner_district">
									<li class="dropdown">
										<a id="change_district" class="dropdown-toggle" data-bs-toggle="dropdown" href="#" role="button" aria-haspopup="true" aria-expanded="true">Select a District Type</a>
										<div class="dropdown-menu" style="width:100%;padding:0px 0px 0px 0px;">
											@foreach ($map as $code=>$col)
												<div class="custom-control custom-switch dropdown-item pl-3">
													<input type="radio" class="custom-control-input" id="{{ $code }}-filter-switch" name="filter" param="{{ $col }}" onchange="changeToggle(event)">
													<label class="custom-control-label radio_toggle" for="{{ $code }}-filter-switch">
														{{ ['cd'=>'Community Districts', 'cc'=>'City Council Districts', 'nta'=>'Neighborhood Tabulation Areas'][$code] }}
													</label>
												</div>
											@endforeach
										</div>
									</li>
								</ul>
							</div>
						</div>
						<!-- /controls -->

						<!-- toggles -->
						<div class="select_district" id="toggles">
							<img src="/img/eyes.png">
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
						<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;border:4px solid #112F4E;"></div>
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
								</tr>
							</thead>
						</table>
					</div>
				</div>
			</div>
		</div>

		@if (($dataset['Public Note'] ?? null))
			<div class="col-md-12">
				<h4 class="note_bottom">{{ nl2br($dataset['Public Note']) }}</h4>
			</div>
		@endif
		@if ($dataset)
		<div class="col-md-12">
			<div class="bottom_lastupdate">
				<p class="lead"><img src="/img/info.png"> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] }}</a><span class="float-right" style="font-weight: 300;"><i>Last updated {{ explode(' ', $dataset['Last Updated'] ?? '')[0] }}</i></span></p>
			</div>
		</div>
		@endif
	</div>
	
	<script>
		function changeToggle (e) {
			console.log($(e.target).next("label")[0].innerHTML)
			$('#change_district').html($(e.target).next("label")[0].innerHTML);
		}
		$('#toggle_boundries').click( function (e) {
			$(this).next('.dropdown-menu').toggleClass('show');
		})

		$(".filter_icon").click(function() {
			console.log($('.toolbar').is(':visible'))
			if(!$('.toolbar').is(':visible')) {
				$('.filter_icon').addClass('position_change');
			}else {
				$('.filter_icon').removeClass('position_change');
			}
			$(".toolbar").toggle();
		});
	</script>

@endsection
