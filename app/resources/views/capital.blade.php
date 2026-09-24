@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects - Open Data Driven Profiles by NYC Databook." />
	<meta rel="canonical" href="{!! route('capital') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')


<div class="inner_container">

	<div class="container">
		<div class="row my-4">
			<div class="col-md-12">
				{{-- ⚠ A BARE <h1> IS A FONT SIZE. Every other capital page titles
				     itself with `.db-profile-title` (30px at 1440, 24px at 390);
				     this one rendered the browser default 36px at BOTH widths —
				     the only capital page that never shrinks on a phone. Owner
				     decision 2026-09-12: make it uniform. --}}
				<h1 class="db-profile-title">New York City’s Capital Program</h1>
				<p class="lead">Our city’s infrastructure – its roads, sewers, parks and schools – is funded and managed through the city’s capital program. This website uses NYC Open Data to explore the capital program’s four phases: Strategy, Budget, Commitments and Projects.</p>

			</div>
		</div>	
		
		<div class="row mb-4">
			<div class="col-4">
				<h2>Strategy</h2>
				<p class="lead">The Mayor’s Office of Management & Budget (OMB) updates a <a href="https://data.cityofnewyork.us/dataset/Ten-Year-Capital-Strategy/b37a-3faw" target="_blank">10-Year Strategy</a> document every 2 years, organizing the plan by project types and categories.</p>
				<div class="float-left mr-4 my-4">
					<a href="{!! route('prjTypes') !!}" class="float-left no-underline">
						<span class="type-label">View Project Types</span>
					</a>
				</div>					
				<div class="float-left mr-4 my-4">
					<a href="{!! route('prjCategories') !!}" class="float-left no-underline">
						<span class="type-label">View Categories</span>
					</a>
				</div>					
			</div>

			<div class="col-4">
				<h2>Budget</h2>
				<p class="lead">The Mayor submits an <a href="https://data.cityofnewyork.us/City-Government/Capital-Budget/46m8-77gv/" target="_blank">Executive Capital Budget</a> for approval by the City Council every year. This breaks the strategy into budget lines that will fund specific projects.</p>
				<div class="float-left mr-4 my-4">
					<a href="{!! route('budgetLines') !!}" class="float-left no-underline">
						<span class="type-label">View Budget Lines</span>
					</a>
				</div>					
			</div>
			
			<div class="col-4">
				<h2>Commitments</h2>
				<p class="lead">OMB publishes a <a href="https://data.cityofnewyork.us/City-Government/Capital-Commitment-Plan/2cmn-uidm" target="_blank">Capital Commitment Plan</a> three times a year that schedules agency capital spending. These commitments make it possible for agencies to fund projects.</p>
				<div class="float-left mr-4 my-4">
					<a href="{!! route('prjCommitments') !!}" class="float-left no-underline">
						<span class="type-label">View Commitments</span>
					</a>
				</div>					
			</div>

		</div>	

		<div class="row mb-4">

			<div class="col-12">
				<h2>Capital Projects</h2>
				<p class="lead">We combined over a dozen datasets from four different city agencies to create the most comprehensive publicly available capital project profiles.</p>

				@php
					// ⚠ THE PAGE COMPUTES NOTHING. Every figure below is a key the
					// endpoint served; two independent computations of one number is
					// what produced the 243-vs-242 and 1,195-vs-690 defects on the
					// procurement side. Conditional phrases are precomputed here
					// because a Blade directive glued to a word character is not
					// compiled and 500s the page.
					$cap        = is_array($capital ?? null) ? $capital : [];
					$capOk      = !empty($cap['available']) && !empty($cap['projects']);
					$capSched   = $cap['schedule'] ?? [];
					$capCov     = $cap['coverage'] ?? [];
					$capMoney   = $cap['money'] ?? [];
					$capMeasures= $capMoney['measures'] ?? [];
					$capSources = $cap['sources'] ?? [];

					$fmtN = function ($v) { return is_numeric($v) ? number_format((float) $v) : '—'; };
					$fmtB = function ($v) {
						if (!is_numeric($v)) return 'Not published';
						$v = (float) $v;
						if (abs($v) >= 1000000000) return '$' . number_format($v / 1000000000, 1) . 'B';
						if (abs($v) >= 1000000) return '$' . number_format($v / 1000000, 1) . 'M';
						return '$' . number_format($v);
					};
					// ⚠ The share is computed from the two served counts, never typed.
					$schedN   = $capSched['with_published_schedule'] ?? null;
					$projN    = $cap['projects'] ?? null;
					$schedPct = (is_numeric($schedN) && is_numeric($projN) && $projN > 0)
						? round(100 * $schedN / $projN) . '%' : null;
					$schedNote = $schedPct ? ($fmtN($schedN) . ' of ' . $fmtN($projN) . ' · ' . $schedPct) : '';
				@endphp

				@if (!$capOk)
					{{-- ⚠ An unavailable section says so. A silently missing block
					     reads as "the City has no capital programme". --}}
					<div class="alert alert-secondary" role="alert">
						Capital programme figures are not available right now.
					</div>
				@else
				<div id="stats_collapse" class="collapse show mt-0 mb-3">
					<div class="row justify-content-center my-1">
						<div class="col-md-3">
							<div class="card h-100">
								<div class="card-body">
									<div class="card-text text-center">
										Projects in the current plan
										<div class="db-stat-value mb-0">{{ $fmtN($cap['in_current_plan'] ?? null) }}</div>
										<small class="text-muted">of {{ $fmtN($projN) }} tracked</small>
									</div>
								</div>
							</div>
						</div>

						<div class="col-md-3">
							<div class="card h-100">
								<div class="card-body">
									<div class="card-text text-center">
										With a published schedule
										<div class="db-stat-value mb-0">{{ $fmtN($schedN) }}</div>
										<small class="text-muted">{{ $schedNote }}</small>
									</div>
								</div>
							</div>
						</div>

						<div class="col-md-3">
							<div class="card h-100">
								<div class="card-body">
									<div class="card-text text-center">
										In construction
										<div class="db-stat-value mb-0">{{ $fmtN($capSched['in_construction'] ?? null) }}</div>
										<small class="text-muted">reported by the City</small>
									</div>
								</div>
							</div>
						</div>

						<div class="col-md-3">
							<div class="card h-100">
								<div class="card-body">
									<div class="card-text text-center">
										Completed
										<div class="db-stat-value mb-0">{{ $fmtN($capSched['completed'] ?? null) }}</div>
										<small class="text-muted">reported by the City</small>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>

				{{-- ⚠⚠ SIX SEPARATE MEASURES, NOT A FUNNEL. Owner decision, 2026-09-05.
				     Each carries its own population and its publisher's own
				     definition; the note below says why they neither sum nor nest.
				     Drawn as stages, adopted funding being twice planned reads as
				     money vanishing between boxes that are not stages. --}}
				<h3 class="h5 mt-4">What the City has committed and spent</h3>
				<div class="table-responsive">
					<table class="table table-sm">
						<thead>
							<tr>
								<th scope="col">Measure</th>
								<th scope="col" class="text-right">Amount</th>
								<th scope="col" class="text-right">Projects with a figure</th>
								<th scope="col">What it means</th>
							</tr>
						</thead>
						<tbody>
						@foreach ($capMeasures as $m)
							<tr>
								<th scope="row" class="font-weight-normal">{{ $m['label'] ?? '' }}</th>
								<td class="text-right">{{ $fmtB($m['value'] ?? null) }}</td>
								<td class="text-right">{{ $fmtN($m['population'] ?? null) }}</td>
								<td>
									<small>{{ $m['definition'] ?? '' }}</small>
									{{-- ⚠ Whose definition it is, always. These are the
									     PUBLISHER'S words; writing our own account of what
									     "allocated" means would invent authority. --}}
									<br><small class="text-muted">{{ $m['source'] ?? '' }}</small>
								</td>
							</tr>
						@endforeach
						</tbody>
					</table>
				</div>
				@if (!empty($capMoney['note']))
					<p class="small text-muted">{{ $capMoney['note'] }}</p>
				@endif
				@if (!empty($capMoney['publisher_caveat']))
					<p class="small text-muted">
						{{ $capMoney['publisher_caveat'] }}
						<em>{{ $capMoney['publisher_caveat_source'] ?? '' }}</em>
					</p>
				@endif

				{{-- ⚠⚠ WHAT THE DATA DOES NOT COVER, STATED. An absent schedule or
				     location means the City publishes none — not that the project
				     has none — and the two are indistinguishable from a count. --}}
				@if (!empty($capCov))
					<h3 class="h5 mt-4">What these figures do not cover</h3>
					<ul class="small">
						<li>{{ $fmtN($capCov['without_published_schedule'] ?? null) }} projects have no published schedule.</li>
						<li>{{ $fmtN($capCov['without_published_location'] ?? null) }} projects have no published location, so they cannot be placed in a district or on a map.</li>
					</ul>
					@if (!empty($capCov['note']))
						<p class="small text-muted">{{ $capCov['note'] }}</p>
					@endif
				@endif

				{{-- ⚠ Every figure carries its vintage. Publishing a capital number
				     without saying which plan version and reporting period it came
				     from is the failure this section was rebuilt to end. --}}
				@if (!empty($capSources))
					<p class="small text-muted">
						Sources:
						@foreach ($capSources as $src)
							@php
								$vintage = $src['version'] ?? ($src['period'] ?? null);
								$vintageTxt = $vintage ? (' (' . $vintage . ')') : '';
							@endphp
							{{ $src['source'] ?? '' }}{{ $vintageTxt }}@if (!$loop->last); @endif
						@endforeach
					</p>
				@endif
				@endif

				<div class="float-left mr-4 my-4">
					<a href="{!! route('projects') !!}" class="float-left no-underline">
						<span class="type-label">View Capital Projects</span>
					</a>
				</div>
			</div>
		</div>	
		
	</div>	
	
	<div class="container">
		<div class="row mb-1">
			{{-- One shell, from the shared provenance component. This markup was
			     hand-rolled on fifteen views, each with its own per-page fetch. --}}
			<x-db.data-provenance mode="page" :datasets="$datasets" id="capitalDs" />
		</div>
		{{-- ⚠ THE "Our map uses data from …" LINE IS GONE (owner, 2026-09-11),
		     AND IT WAS FOSSIL: this page has no map. Measured on the rendered
		     page before removing it — no `mapboxgl`, no `#map_container`, no
		     `<canvas>` anywhere in 48kB of HTML. It cited the two CPDB geometry
		     datasets for a map that lives on other pages.
		     ⚠ MY FIRST VERSION OF THIS COMMENT CLAIMED the provenance block
		     above already names those two datasets, so nothing was lost. IT DOES
		     NOT — it carries "Capital Projects (CPDB)" and fourteen others, but
		     neither Projects (Polygons) nor Projects (Points). Nothing on this
		     page cites them now. That is correct here, because the page draws
		     nothing from them; the surfaces that DO draw the geometry are the
		     ones that owe the citation. --}}

		
    </div>
</div>


<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/rowgroup/1.1.4/js/dataTables.rowGroup.min.js"></script>
<script>
	var datasets = {!! json_encode(array_values($datasets)) !!}
	$(document).ready(function () {

		const globStats = {!! json_encode($globStats) !!};
		globStatView(globStats);
		
		
		//loadFinStat()
	});

</script>

@endsection
