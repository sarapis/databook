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
		{{-- ⚠ The map's scope, handed to the one owner in `script.js`. Built by the
		     CONTROLLER from the same scope the list request uses, so the map and
		     the table cannot answer one question two ways. --}}
		capMap.init('{!! $capGeojsonUrl ?? '' !!}');

		function details(r) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
			  {{-- ⚠ `?? []`, NOT `(array)$details['details']` ALONE. The cast handles a
			       null but not a MISSING KEY, and an undefined index is an
			       ErrorException in Laravel — this page 500'd with
			       `Undefined index: details` the moment the capital tab moved to the
			       spine contract, which deliberately declares no expander.
			       ⚠ The spine has no expander by design: the old one showed nine
			       fields from the retired series (Original Budget, Prior Spending,
			       Community Boards Served, Site Description…) that the spine does not
			       carry in that form. All of it, and more, is on the project profile
			       the Project ID column links to — which is where it belongs rather
			       than duplicated into a row expander. --}}
			  @foreach ((array)($details['details'] ?? []) as $h=>$f)
				'<tr><td>{{ $h }}:</td><td>' + {!! $f !!} + '</td></tr>' +
			  @endforeach
			'</table>';
		}

		var datatable = null

		// ⚠ Loaded independently of the historical table: the current plan is the
		// answer to "what is happening now" and must not depend on whether the
		// retired series happens to hold rows for this organization.
		var CCP_CAP = 100;
		// ⚠⚠ DOLLARS. Both money keys are normalised to dollars by the endpoint and
		// suffixed _usd precisely so nothing re-scales them here — the retired
		// series is published in THOUSANDS and carrying that unit across is the
		// 1000x defect this page already shipped once.
		function altMoney(x) {
			var n = parseFloat(x);
			if (!isFinite(n)) { return '<span class="db-text-muted">\u2014</span>'; }
			if (n === 0) { return '$0'; }
			return toFinShortK(n, 1);
		}

		// ⚠ `unionStatsActive` IS GONE WITH THE LOOP IT GUARDED. It existed so a
		// late `loadFinStat()` reply could not overwrite these figures with '-';
		// with that loop deleted it had no reader, and a flag guarding nothing
		// reads as a live race to the next person.
		function loadUnionStats(unionRowCount) {
			// ⚠⚠ SHOW THIS BLOCK AND HIDE THE SPINE GRID. An org on this path holds
			// no spine row, so the grid above is correctly rendering "no projects in
			// Databook's capital spine" — true, and a contradiction sitting directly
			// above real figures. The two are mutually exclusive by construction:
			// this path is only taken when the by-org list came back empty, and the
			// `org` stats scope is grouped on the same column.
			$('#spine-stats').hide();
			$('#union_stats').show();
			$('#projects_no').text(unionRowCount.toLocaleString());
			$.getJSON("{!! $unionStatsUrl !!}", function (p) {
				var r = (p && p.rows && p.rows[0]) || null;
				if (!r) { return; }
				// ⚠ Money arrives in DOLLARS (converted once, server-side) so the
				// multiplier is 1 here — the legacy tiles pass 1000 because the retired
				// series publishes thousands, and carrying that across is the 1000x
				// defect this page already shipped.
				// ⚠ `over_budg_am` IS SERVED AND DELIBERATELY NOT RENDERED — the one
				// label this section documents as carrying two definitions. Dropping
				// it costs nothing a reader can use: `over_budg_no` beside it counts
				// the projects over budget, which is unambiguous.
				[['#orig_cost', r.orig_cost], ['#curr_cost', r.curr_cost]
				].forEach(function (pair) {
					var v = parseFloat(pair[1]);
					if (!isFinite(v)) { $(pair[0]).text('\u2014'); return; }
					$(pair[0]).text(toFinShortK(v, 1)).attr('data-content', toFin(v, 1));
				});
				[['#long_no', r.long_no], ['#over_budg_no', r.over_budg_no],
				 ['#late_start_no', r.late_start_no], ['#late_end_no', r.late_end_no]
				].forEach(function (pair) {
					$(pair[0]).text(pair[1] == null ? '\u2014' : Number(pair[1]).toLocaleString());
				});
				// ⚠⚠ STATE THE DENOMINATOR. Budget and schedule variance exist only in
				// the retired series — the current plan publishes neither — so these
				// seven tiles cover FEWER projects than the count beside them. Without
				// this line they read as covering the whole table above.
				if (r.budget_basis != null && r.budget_basis < unionRowCount) {
					$('#stats-basis').text(
						'Budget and schedule figures cover the ' + r.budget_basis +
						' of these ' + unionRowCount + ' projects carried by the 2023 ' +
						'series; the 2026 plan publishes no original-vs-current budget ' +
						'or start/end variance.').show();
				}
				setTimeout(function () { initPopovers(); }, 500);
			});
		}

		// ⚠⚠ THE UNLINKED FALLBACK IS THE POINT, not an afterthought. When an org id
		// does not resolve we still show the plan's own agency string — dropping the
		// agency entirely would turn a resolution miss into missing data, which is
		// the failure this page has already made twice (a blank cell and an em dash
		// both read as "the City did not say").
		function agencyCell(r) {
			var esc = function (t) { return $('<div>').text(t == null ? '' : t).html(); };
			var id = r.agency_org_id, nm = r.agency_name;
			if (!id || !nm) { return esc(r.agency); }
			// The agency's own capital-projects page: /o/{id}-{slug}/projects
			return '<a href="/o/' + encodeURIComponent(id) + '-' + slug(nm) +
				'/projects">' + esc(nm) + '</a>';
		}

		function renderAltUnion(rows) {
			var esc = function (t) { return $('<div>').text(t == null ? '' : t).html(); };
			var html = '';
			rows.forEach(function (r) {
				var pid = (r.project_id || '').trim();
				var badge = r.in_current && r.in_retired ? 'both'
					: (r.in_current ? '2026' : '2023');
				html += '<tr><td><a href="/p/' + encodeURIComponent(pid) + '">' +
					esc(pid) + '</a></td><td>' + esc(r.name) + '</td><td>' +
					agencyCell(r) + '</td><td>' +
					esc(r.boro) + '</td><td>' + badge + '</td><td>' +
					esc(r.start_date || '\u2014') + '</td><td>' +
					esc(r.end_date || '\u2014') + '</td><td class="text-end">' +
					altMoney(r.orig_cost_usd) + '</td><td class="text-end">' +
					altMoney(r.budget_usd) + '</td></tr>';
			});
			$('#alt-union-body').html(html);
			// ⚠ COUNTED FROM THE ROWS, never typed. Projects that appear only in the
			// 2026 plan carry no original/current cost at all — that plan publishes
			// neither — so the table shows them with two blanks. Saying how many, and
			// what they are worth, is what stops a blank reading as "no money".
			var nocost = rows.filter(function (r) {
				return !isFinite(parseFloat(r.orig_cost_usd)) &&
				       !isFinite(parseFloat(r.budget_usd));
			});
			// ⚠ Date coverage is stated for the same reason the cost coverage is: a
			// column of em dashes reads as "this project has no schedule" when the
			// truth is that the 2026 plan publishes no schedule and 1899 sentinels
			// were suppressed. Counted from the rows, never typed.
			var nodate = rows.filter(function (r) { return !r.start_date && !r.end_date; });
			if (nodate.length) {
				$('#alt-nodate-note').html(' Start and end dates come from the 2023 series ' +
					'only, so ' + nodate.length + ' of ' + rows.length + ' rows show none.');
			}
			if (nocost.length) {
				var pc = nocost.reduce(function (a, r) {
					var v = parseFloat(r.planned_commit_usd);
					return a + (isFinite(v) ? v : 0);
				}, 0);
				$('#alt-nocost-note').html(
					nocost.length + ' of these ' + rows.length + ' projects appear only in ' +
					'the 2026 plan, which publishes no cost comparison, so both columns ' +
					'are blank for them' + (pc > 0 ?
						' &mdash; they carry ' + toFinShortK(pc, 1) + ' of planned commitment' : '') +
					'.');
			}
		}

		$(document).ready(function () {
			$.getJSON("{!! $currentPlanUrl !!}", function (p) {
				var rows = (p && p.rows) || [];
				if (!rows.length) { return; }
				var money = function (x) {
					// ⚠⚠ THE PLAN PUBLISHES DOLLARS, NOT THOUSANDS. Verified three
					// ways, because a units error here is off by 1000x and still
					// looks like a number: one lump sum reads 652594000 ($652.6M,
					// not $652B); Parks totals 9,818,811,000 ($9.82B); citywide
					// planned commitment totals 201,809,204,000 ($201.8B) against
					// NYC's ~$185-190B Ten-Year Capital Strategy. The thousands
					// reading makes all three impossible.
					var n = parseFloat(x);
					// ⚠ An em dash means NO DATA. A literal 0 is the City's own
					// claim -- EDC's projects are future-dated and legitimately
					// carry no commitment yet -- so it renders $0, never a dash.
					if (!isFinite(n)) { return '\u2014'; }
					if (n === 0) { return '$0'; }
					return toFinShortK(n, 1);
				};
				var total = 0, html = '';
				rows.forEach(function (r) {
					var pc = parseFloat(r.plannedcommit_total); if (isFinite(pc)) { total += pc; }
				});
				rows.slice(0, CCP_CAP).forEach(function (r) {
					var pid = (r.projectid || '').trim();
					html += '<tr><td><a href="/p/' + encodeURIComponent(pid) + '">' + pid +
						'</a></td><td>' + (r.description || '') + '</td><td>' +
						(r.magencyacro || r.magency || '') + '</td><td>' +
						(r.typecategory || '\u2014') + '</td><td>' + (r.mindate || '') +
						'</td><td>' + (r.maxdate || '') + '</td><td class="text-end">' +
						money(r.plannedcommit_total) + '</td><td class="text-end">' +
						money(r.spent_total) + '</td></tr>';
				});
				$('#ccp-body').html(html);
				$('#ccp-version').text(rows[0].ccpversion || '');
				$('#ccp-summary').html('<strong>' + rows.length.toLocaleString() +
					'</strong> projects in the current plan, <strong>' +
					money(total) + '</strong> planned commitment.');
				// ⚠ COUNT BEFORE YOU CAP, and say so — a truncated list presented as
				// complete is a defect this repo has shipped more than once.
				if (rows.length > CCP_CAP) {
					$('#ccp-capped').text('Showing the ' + CCP_CAP +
						' largest by planned commitment, of ' + rows.length.toLocaleString() +
						'.').show();
				}
				$('#current-plan-block').show();
			});
		});

		$(document).ready(function() {
			
			datatable = $('#myTable').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $url !!}", function (payload) {
						var rows = (payload && payload.data) || [];
						// ⚠⚠ A FAILED REQUEST IS NOT AN EMPTY RESULT. fapireq returns
						// {data: [], error, status} on failure, so without this check a
						// 500 or a 429 would render "this dataset does not list this
						// organization" — a confident claim about coverage made from a
						// broken request. fapireq's own comment warns about exactly this
						// and the first version of this note ignored it.
						if (payload && payload.error) { cb(payload); return; }
						if (rows.length) { cb(payload); return; }

						// Empty AND the request was fine. Does this organization have
						// capital projects carried on ANOTHER agency's budget?
						$.getJSON("{!! $altProjectsUrl !!}", function (alt) {
							var arows = (alt && alt.rows) || [];
							if (arows.length) {
								// ⚠ The count is len(rows) from the endpoint — ONE row per
								// project — so the note cannot disagree with the table under
								// it. The previous version counted distinct projects across
								// all 14 publication dates (15) while the retired series'
								// DataTable filtered to the newest publication (9).
								$('#alt-projects-count').text(alt.projects || arows.length);
								$('#alt-projects-note').show();
								renderAltUnion(arows);
								loadUnionStats(arows.length);
								$('#alt-union-block').show();
								$('#myTable_wrapper').hide();
								// ⚠ The Publication Date selector filters the retired
								// series' table, which is hidden here — and it is
								// populated FROM that table, so it holds nothing but its
								// own placeholder. A control that cannot do anything is
								// worse than no control.
								$('#pub_date_row').hide();
								// ⚠ Open the stats by default HERE ONLY. On a normal agency
								// page the collapsed default is the owner's existing choice
								// and the spine grid is a summary of the table below it; on
								// this page the stats ARE the substance above an empty
								// table, and a reader has no reason to guess there is a
								// panel to open.
								// ⚠ The button's own state must move with it or Bootstrap's
								// first click reads as "already closed" and does nothing.
								$('#stats_collapse').addClass('show');
								$('[data-bs-target="#stats_collapse"]')
									.attr('aria-expanded', 'true').removeClass('collapsed');
								cb({ data: [] });
								return;
							}
							// No alternative either — then say why the table is empty.
							$('#section-scope-note').show();
							$('#myTable_wrapper').hide();
							$.getJSON("{!! $coverageUrl !!}", function (c) {
								var n = c && c.rows && c.rows[0] && c.rows[0].orgs;
								if (n) {
									$('#section-scope-detail').text(
										'This dataset covers ' + n + ' organizations in total.');
								}
							});
							cb(payload);
						}).fail(function () { cb(payload); });
					});
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
						$("div.toolbar .row").append('<button id="map_button" class="btn map_btn col" style="margin:0 20px 0 10px; z-index: 10; max-width: 40px;" onclick="toggleMap();"><img src="/img/map_location.png" alt=""></button>');

						@foreach ($details['filters'] as $i=>$v)
							@if ($v)
								setTimeout(function(){
									$('#filter-{{ $i }}').find('[value*="{!! $v !!}"]').prop('selected',true).trigger('change')
								}, 500 + 1000 * {{ $i }});
							@endif
						@endforeach


						{{-- ⚠⚠ THE PUBLICATION-DATE FILTER BELONGS TO THE RETIRED SERIES, AND
						     LEAVING IT ON THE SPINE SILENTLY FILTERED THE TABLE TO ONE ROW.
						     It hardcodes `columns([1])` and then auto-selects that column's
						     LAST option. Under `capitalprojectsdollarscomp` — 9 headers plus a
						     details expander — column 1 was `Publication Date`, and selecting
						     its newest value was the point. The spine has 8 headers and no
						     expander, so column 1 is `Name`: the control built a dropdown of
						     2,798 project names and picked the last one, leaving
						     "Showing 1 to 1 of 1 (filtered from 2,798 total entries)".
						     ⚠ The rows, the headers and the payload were all correct — only
						     the visible count was wrong, which is why this needed looking at
						     the rendered table rather than the response.
						     ⚠ Gated on a CONTRACT FLAG rather than deleted, so a dataset that
						     genuinely has a publication-date column can switch it back on. The
						     spine has no per-row publication date: it is a derived spine, and
						     its vintage is a property of the build, not of a row. --}}
						{{-- ⚠⚠ ONE KEY AND ONE MECHANISM, ALIGNED 2026-09-10. This gate read
						     `pubDateFilter` while `orgSection` — the other consumer of
						     OrgsDatasets — reads `pubdate_filter`, and two names for one
						     concept is how a contract ends up declaring the key the other
						     view checks. Worse, the column was hardcoded `columns([1])`
						     INSIDE the gate, so a contract could turn the control on and
						     still point it at the wrong column: the gate said "there is a
						     publication-date filter" without saying WHERE. The column now
						     comes from the contract, exactly as `orgSection` and the two
						     capital project views take it.
						     ⚠ Behaviourally a no-op today: no OrgsDatasets contract
						     declares either key for this tab, so the control stays off —
						     which is the point, the spine has no per-row publication date.
						     Verified before and after: the rendered page emits no
						     publication-date control either way. --}}
						@if ($details['pubdate_filter'] ?? null)
						/* custom pub_date filter on top-right */
						this.api().columns([{{ array_keys($details['pubdate_filter'])[0] }}]).every(function (c,a,i) {
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

						{{-- ⚠ The column and the selector both come from the contract now.
						     Hardcoding `#filter-1` here had the same weakness as the
						     `columns([1])` above, and one more: `#filter-1` is also the id
						     the GENERAL filter loop gives column 1, so this line could
						     auto-pick a value from a completely different dropdown. --}}
						setTimeout(function(){
							$('#filter-{{ array_keys($details['pubdate_filter'])[0] }}').find('{{ array_values($details['pubdate_filter'])[0] }}').prop('selected',true).trigger('change')
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
					initPopovers();
				}
			});

			$('#myTable_length label').html($('#myTable_length label').html().replace(' entries', ''));

			// ⚠ Redraws the map from the SERVED features intersected with the rows
			// the table is currently showing, so a client-side search moves both.
			// (This comment said "draws projects from GEO_JSON field", which
			// stopped being true when the table moved to the spine.)
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
				console.log(data, d)
				m = 1
				for (const[rg, tmpM] of [[/K$/g, 1000], [/M$/g, 1000000], [/B$/g, 1000000000]]) {
					if (d.match(rg)) {
						m = tmpM;
						d = d.replace(rg, '');
					}
				}
				d = d.match(/[-\d\.]+/g) ? parseFloat(d) * m : d;
				console.log(data, d);
				return d;
			};
			
		});


		// Boundary overlay control — same open/close + aria behaviour as the other
		// maps. Bound on ready; the control is in the DOM whether or not the map
		// panel is currently shown.
		$(document).ready(function () {
			var bc = document.getElementById('boundaries-control');
			var bt = document.getElementById('boundaries-toggle');
			if (bc && bt) {
				bt.addEventListener('click', function (e) {
					e.stopPropagation();
					bt.setAttribute('aria-expanded', bc.classList.toggle('is-open') ? 'true' : 'false');
				});
				document.addEventListener('click', function (e) {
					if (!e.target.closest || !e.target.closest('#boundaries-control')) {
						bc.classList.remove('is-open');
						bt.setAttribute('aria-expanded', 'false');
					}
				});
			}
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
		
		// ⚠⚠ THE RETIRED-SERIES LOOP IS GONE, NOT LEFT INERT — the same call the
		// district tab made. The capital tiles are server-rendered from the spine
		// now, so there is nothing to hydrate; but the loop still NAMED
		// `#over_budg_am`, `#orig_cost` and `#curr_cost` and still multiplied by
		// 1000, and dead code naming the thing we removed is how a later reader
		// concludes the tiles are still AJAX-hydrated from `pstats-*`.
		// ⚠ It also read `$('#filter-1 option:selected').val()` — the
		// publication-date control, gated off by the spine contract, so the value
		// it was about to substitute into eight URLs did not exist. That is why
		// this ran zero times and left eight blank tiles rather than throwing.
		// The function survives because its caller relies on the popovers.
		function loadFinStat() {
			setTimeout(function(){
				initPopovers();
			}, 1000);
		}
		
		{{-- ⚠⚠ THIS BODY READ `r['GEO_JSON']` OFF THE TABLE, AND THE TABLE HAS
		     BEEN THE SPINE SINCE THIS TAB WAS MIGRATED (`94e6379`) — a column the
		     spine does not serve. Measured on the rendered page 2026-09-10 by
		     reading `map.getSource('route')._data.features.length`, the map drew
		     **0 features** while its table held **2,798** projects. Container, style load and console were
		     all clean, so a status code, a row count and a JS-error check every
		     one of them passed. This is the eight-blank-tiles finding on the same
		     tab, one organ over: the tab was verified by its TABLE.
		     ⚠ `capMap` in `script.js` is the ONE owner now; this page held one of
		     three byte-identical copies. --}}
		function drawProjects(pages) {	// 'all',     'current'
			capMap.draw(pages);
		}
		
	</script>

	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-9 organization_data">
					@if(array_search($section, $menu) === false)
						<h4>{{ ($dataset['Name'] ?? null) ?: ($details['fullname'] ?? $section) }}</h4>
					@endif	
					<p>{!! nl2br($details['description'] ?? ($dataset['Descripton'] ?? '')) !!}</p>
				</div>
				<div class="col-md-3 mt-2" id="org_summary">
					<table class="table-sm stats-table" width="100%">
					<thead>
						{{-- ⚠ The LABEL and the selector are separate cells, so hiding
						     only #pub_date_filter leaves "Publication Date" captioning an
						     empty box. The row carries the id so both go together. --}}
						@if ($details['pubdate_filter'] ?? null)
						<tr id="pub_date_row">
						<th scope="col" width="50%" class="text-center px-0" data-content="See the project info published on specific dates.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
						<th scope="col" width="50%" id="pub_date_filter"></th>
						</tr>
						@endif
					</thead>
					<tbody>
						<tr>
							<td colspan=2 class="text-right px-0 pt-0 pb-3">
								<button class="type-label my-2 dropdown-toggle" data-bs-toggle="collapse" data-bs-target="#stats_collapse" aria-expanded="false" aria-controls="stats_collapse"><small>Show/Hide Stats</small></button>
							</td>
						</tr>
					</tbody>
					</table>
				</div>
			</div>
			
			<div id="stats_collapse" class="collapse mt-2 mb-4">
				{{-- ⚠⚠ SERVER-RENDERED FROM THE SPINE, and these eight tiles were
				     BLANK before it. They hydrated by AJAX from
				     `/get/orgs/pstats-*/{id}/pubdate` over `capitalprojectsdollarscomp`,
				     multiplying by 1000 because that series is denominated in
				     THOUSANDS — and the only call to `loadFinStat()` lived inside the
				     `pubdate_filter` block, which the spine contract
				     turns off. So once the tab moved to the spine nothing called it:
				     measured on the rendered page, eight tiles reading `&nbsp;` and
				     zero pstats requests, while the table beside them was right.
				     ⚠⚠ `Amount Over Budget` IS DELIBERATELY NOT REPRODUCED, here or in
				     the union block below. It is the label this section documents as
				     carrying TWO definitions — every row's budget difference globally,
				     but only the NEGATIVE ones per district — so repointing it under
				     new data would preserve the defect. The rebuilt Overview drops it,
				     the district tab drops it, and so does this. --}}
				<div id="spine-stats" class="db-stat-grid">
					@php
						$oCap   = is_array($capital ?? null) ? $capital : [];
						$oCapOk = !empty($oCap['available']) && !empty($oCap['found']);
						$oSched = $oCap['schedule'] ?? [];
						$oMoney = [];
						foreach (($oCap['money']['measures'] ?? []) as $om)
							$oMoney[$om['key'] ?? ''] = $om;
						$oFmtN = function ($v) { return is_numeric($v) ? number_format((float) $v) : '—'; };
						$oFmtB = function ($v) {
							if (!is_numeric($v)) return '—';
							$v = (float) $v;
							if (abs($v) >= 1000000000) return '$' . number_format($v / 1000000000, 1) . 'B';
							if (abs($v) >= 1000000) return '$' . number_format($v / 1000000, 1) . 'M';
							return '$' . number_format($v);
						};
						// ⚠ Populations travel with the money, because no two of these
						// measures are over the same set of projects (⚑ F). A total over
						// 1,635 projects beside one over 2,149 reads as a leaking funnel
						// unless both denominators are on the page.
						$oPop = function ($k) use ($oMoney, $oFmtN) {
							$n = $oMoney[$k]['population'] ?? null;
							return is_numeric($n) ? $oFmtN($n) . ' projects' : null;
						};
						$oTracked = $oCap['projects'] ?? null;
					@endphp
					@if ($oCapOk)
						<div class="db-stat">
							<div class="db-stat-label">Projects attributed here</div>
							<div class="db-stat-value">{{ $oFmtN($oTracked) }}</div>
						</div>
						<div class="db-stat">
							<div class="db-stat-label">In the current plan</div>
							<div class="db-stat-value">{{ $oFmtN($oCap['in_current_plan'] ?? null) }}</div>
							@if(is_numeric($oTracked))<div class="db-stat-sub">of {{ $oFmtN($oTracked) }} attributed here</div>@endif
						</div>
						<div class="db-stat">
							<div class="db-stat-label">Planned commitments</div>
							<div class="db-stat-value">{{ $oFmtB($oMoney['planned_usd']['value'] ?? null) }}</div>
							@if($oPop('planned_usd'))<div class="db-stat-sub">{{ $oPop('planned_usd') }}</div>@endif
						</div>
						<div class="db-stat is-accent">
							<div class="db-stat-label">Spent</div>
							<div class="db-stat-value">{{ $oFmtB($oMoney['spent_usd']['value'] ?? null) }}</div>
							@if($oPop('spent_usd'))<div class="db-stat-sub">{{ $oPop('spent_usd') }}</div>@endif
						</div>
						<div class="db-stat">
							<div class="db-stat-label">With a published schedule</div>
							<div class="db-stat-value">{{ $oFmtN($oSched['with_published_schedule'] ?? null) }}</div>
							@if(is_numeric($oTracked))<div class="db-stat-sub">of {{ $oFmtN($oTracked) }} attributed here</div>@endif
						</div>
					@else
						{{-- ⚠ A silently missing block reads as "this organization has no
						     capital programme". Zero is not failure, and failure is not
						     zero — and an org whose projects sit on ANOTHER agency's
						     budget lands here legitimately, which is what the union
						     block below is for. --}}
						<div class="db-stat"><div class="db-stat-label">Capital programme</div><div class="db-stat-value">—</div><div class="db-stat-sub">no projects in Databook&rsquo;s capital spine under this organization</div></div>
					@endif
				</div>

				{{-- ⚠⚠ THE UNION PATH'S OWN TILES, and they are a DIFFERENT CLAIM from
				     the grid above: these are the 2023 series' budget and schedule
				     variance for projects the plan text merely NAMES this organization
				     in. Shown only by `loadUnionStats()`, which also hides the spine
				     grid — an org on this path holds no spine row at all, so the two
				     can never be true at once, and showing "no projects in the spine"
				     above real figures would read as a contradiction.
				     ⚠ Every money tile here is labelled with its series, because the
				     current plan publishes no original-vs-current budget and no
				     start/end variance: they exist ONLY in the retired series, over a
				     SMALLER set of projects than the count beside them. `#stats-basis`
				     states that denominator. --}}
				<div id="union_stats" style="display:none">
					<p id="stats-basis" class="db-text-muted mb-2"
					   style="display:none; font-size:var(--db-text-2xs)"></p>
					<div class="db-stat-grid">
						<div class="db-stat">
							<div class="db-stat-label">Projects naming this organization</div>
							<div class="db-stat-value prj_stat" id="projects_no">—</div>
						</div>
						<div class="db-stat">
							<div class="db-stat-label">Original cost</div>
							<div class="db-stat-value prj_stat" id="orig_cost">—</div>
							<div class="db-stat-sub">2023 series</div>
						</div>
						<div class="db-stat">
							<div class="db-stat-label">Current cost</div>
							<div class="db-stat-value prj_stat" id="curr_cost">—</div>
							<div class="db-stat-sub">2023 series</div>
						</div>
						<div class="db-stat">
							<div class="db-stat-label">Over budget</div>
							<div class="db-stat-value prj_stat" id="over_budg_no">—</div>
							<div class="db-stat-sub">2023 series</div>
						</div>
						<div class="db-stat">
							<div class="db-stat-label">Running long</div>
							<div class="db-stat-value prj_stat" id="long_no">—</div>
							<div class="db-stat-sub">2023 series</div>
						</div>
						<div class="db-stat">
							<div class="db-stat-label">Starting late</div>
							<div class="db-stat-value prj_stat" id="late_start_no">—</div>
							<div class="db-stat-sub">2023 series</div>
						</div>
						<div class="db-stat">
							<div class="db-stat-label">Ending late</div>
							<div class="db-stat-value prj_stat" id="late_end_no">—</div>
							<div class="db-stat-sub">2023 series</div>
						</div>
					</div>
				</div>
			</div>

			<div class="row justify-content-center map_right">
				@if ($map ?? null)
					<div id="map_container" class="col-6 position-relative" style="display:none;">
						<button id="map_button_alt" class="btn btn-outline map_btn" style="margin:0 20px 20px 10px; z-index: 10; max-width: 40px; float:right;" onclick="toggleMap();"><img src="/img/map_location.png" alt=""></button>
						{{-- Boundary overlays, top-right — the same control /districts,
						     /projects, /schools and the project profile carry. It replaces
						     the `.select_district` flyout, which was this page's own older
						     pattern.
						     ⚠ The switch IDs are unchanged and load-bearing: `setBoundary()`
						     binds each layer by `#{code}-switch` and paints its colour into
						     that row's `<hr>`. The old markup had the `<hr>` too, so the
						     swatches are not new here — the control around them is.
						     ⚠ NO ADDRESS SEARCH: this map is opened beside a filtered project
						     TABLE, and a second search surface for one question is how a map
						     and a table come to disagree. --}}
						<div class="db-map-control" id="boundaries-control" style="top: var(--db-space-2); right: var(--db-space-2);">
							<button type="button" class="db-btn db-btn-outline db-btn-sm" id="boundaries-toggle" aria-haspopup="true" aria-expanded="false" style="background:#fff;">
								<i class="bi bi-bounding-box-circles"></i> Boundaries <i class="bi bi-chevron-down db-caret"></i>
							</button>
							<div class="db-map-control-menu" id="boundaries_controls">
								<p class="db-map-control-label">Overlay boundaries</p>
								@php
									$boundaryLayers = [
										'cd' => 'Community Districts', 'ed' => 'Election Districts',
										'pp' => 'Police Precincts', 'dsny' => 'Sanitation Districts',
										'fb' => 'Fire Battalions', 'sd' => 'School Districts',
										'hc' => 'Health Center Districts', 'cc' => 'City Council Districts',
										'nycongress' => 'Congressional Districts', 'sa' => 'State Assembly Districts',
										'ss' => 'State Senate Districts', 'bid' => 'Business Improvement Districts',
										'nta' => 'Neighborhood Tabulation Areas', 'zipcode' => 'Zip Code',
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
							     and a link out, so a map beside a table of thousands of
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
					{{-- ⚠⚠ THE CURRENT PLAN, ABOVE THE RETIRED ONE. The table further down
					     is `capitalprojectsdollarscomp`, which NYC RETIRED in October 2023
					     (is_active=false, no socrata_id, never ingested, newest PUB_DATE
					     20231026) — so this tab showed ~3-year-old data on every agency.
					     It is KEPT rather than replaced because the live successor carries
					     no LAT/LNG (the map), no borough, no scope text and none of the
					     budget/timeline change columns; swapping would have silently
					     deleted the map and five columns from 25 agency pages. --}}
					<div id="current-plan-block" style="display:none">
						<h5 class="mb-1">Current Capital Commitment Plan
							<span class="db-badge db-badge-neutral" id="ccp-version"></span></h5>
						<p class="db-text-muted" style="font-size:var(--db-text-sm)">
							<span id="ccp-summary"></span>
							<br>
							⚠ The detail table below is the older <em>Capital Project Detail</em>
							series, which the City stopped publishing in October 2023. It is kept
							because it carries the project map, borough, scope text and the
							budget- and timeline-change columns that the current plan does not.
						</p>
						<div class="table-responsive mb-4">
							<table class="db-table table-striped" style="width:100%">
								<thead><tr>
									<th>Project</th><th>Name</th><th>Agency</th><th>Category</th>
									<th>Start</th><th>End</th>
									<th class="text-end">Planned</th><th class="text-end">Spent</th>
								</tr></thead>
								<tbody id="ccp-body"></tbody>
							</table>
						</div>
						<p id="ccp-capped" class="db-text-muted"
						   style="font-size:var(--db-text-2xs); display:none"></p>
					</div>

					{{-- Shown ONLY when this organization has no capital rows of its
					     own but the plan names it on other agencies' budgets. --}}
					<div id="alt-projects-note" class="db-alert db-alert-info mt-3" style="display:none">
						<div class="db-alert-body">
							<i class="bi bi-info-circle"></i>
							<strong>These projects are not managed or sponsored by this organization.</strong>
							It holds no capital budget line of its own, so it never appears as a
							managing or sponsoring agency in the Capital Commitment Plan. It delivers
							capital work under contract, and the projects below &mdash;
							<strong><span id="alt-projects-count"></span></strong> of them &mdash; are
							carried on the capital budgets of the agencies that contract it.
							<br>
							<span class="db-text-muted" style="font-size:var(--db-text-2xs)">
								⚠ Matched because the plan&rsquo;s own project description or scope text
								names this organization. That is evidence it is involved, not a record
								of who holds the contract &mdash; the Plan publishes no contractor field.
							</span>
						</div>
					</div>

					{{-- ⚠⚠ THE UNION RENDERS ITS OWN TABLE, and it has to. The retired
					     series' DataTable is built around columns the current plan does
					     not have (SCOPE_TEXT, BORO, BUDG_ORIG/CURR/DIFF, END_DIFF) and
					     applies its own PUB_DATE filter — which is exactly how the note
					     came to say 15 while 9 rows showed beneath it. --}}
					<div id="alt-union-block" class="mt-3" style="display:none">
						<div class="table-responsive">
							<table id="alt-union-table" class="display table-striped table-hover" style="width:100%;">
								<thead>
									<tr>
										<th scope="col">Project ID</th>
										<th scope="col">Name</th>
										<th scope="col">Agency</th>
										<th scope="col">Borough</th>
										<th scope="col">In plan</th>
										{{-- ⚠ 2023 series ONLY. The 2026 plan's mindate/maxdate are
										     fiscal-year plan boundaries (96% land on 06/01), not a
										     schedule, and agree with these on 0.8% of overlapping
										     projects — so they are a different measure, not a
										     fallback. --}}
										<th scope="col">Start<br>
											<span class="db-text-muted" style="font-weight:400; font-size:var(--db-text-2xs)">2023 series</span></th>
										<th scope="col">End<br>
											<span class="db-text-muted" style="font-weight:400; font-size:var(--db-text-2xs)">2023 series</span></th>
										<th scope="col" class="text-end">Original cost<br>
											<span class="db-text-muted" style="font-weight:400; font-size:var(--db-text-2xs)">2023 series</span></th>
										<th scope="col" class="text-end">Current cost<br>
											<span class="db-text-muted" style="font-weight:400; font-size:var(--db-text-2xs)">2023 series</span></th>
									</tr>
								</thead>
								<tbody id="alt-union-body"></tbody>
							</table>
						</div>
						{{-- ⚠⚠ THIS NOTE HAD TO CHANGE WITH THE COLUMNS. It used to explain
						     that the two figures came from DIFFERENT plans and must never be
						     added. Both now come from the 2023 series, so that sentence is
						     false — and a stale disclosure describing a layout the page no
						     longer has is the typed-figure defect in prose form. What the
						     reader now needs to know is the opposite: these two ARE
						     comparable (the gap is budget growth), and which rows carry
						     neither. --}}
						<p class="db-text-muted mt-2" style="font-size:var(--db-text-2xs)">
							⚠ Both cost figures come from the 2023 series, so the difference
							between them is that project&rsquo;s budget growth.
							<span id="alt-nocost-note"></span><span id="alt-nodate-note"></span>
						</p>
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

		@if (($dataset['Public Note'] ?? null))
			<div class="col-md-12">
				<h4 class="note_bottom">{{ nl2br($dataset['Public Note']) }}</h4>
			</div>
		@endif
		@if ($dataset)
		<div class="col-md-12">
			<div class="bottom_lastupdate">
				<p class="lead"><img src="/img/info.png" alt=""> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] }}</a><span class="float-right" style="font-weight: 300;"><i>Last updated {{ explode(' ', $dataset['Last Updated'] ?? '')[0] }}</i></span></p>
			</div>
		</div>
		@endif
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