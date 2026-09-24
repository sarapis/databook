@extends('layout')

@section('head')
	<meta name="robots" content="noindex" />
@endsection

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')

@php
	// ⚠⚠ THIS PAGE EXISTS BECAUSE AN FMS ID IS NOT A PROJECT. Measured over the
	// 17,024-row spine: 1,160 ids are carried by more than one agency, covering
	// 2,371 rows. Before this, `/p/110WLM` returned 200 and showed ONE of them —
	// DCAS's project under an id that agency 068 also uses. Picking silently is
	// the failure; asking is the fix.
	$choices = $cap['choices'] ?? [];
	$note = $cap['note'] ?? '';
@endphp

<div class="inner_container">
	<div class="container">
		<div class="row my-4">
			<div class="col-md-10">
				<div class="db-eyebrow">Capital Project</div>
				<h1 class="mb-2">{{ $prjId }}</h1>
				{{-- ⚠ The endpoint's own sentence, echoed. It states the rule; a
				     version retyped here could drift from the behaviour. --}}
				<p class="lead">{{ $note }}</p>

				<div class="list-group mt-4">
					@foreach($choices as $c)
						@php
							$cid = ($c['agency_key'] ?? '') . ($c['fms_id'] ?? '');
							$desc = trim((string) ($c['description'] ?? '')) ?: $cid;
							// ⚠ The link uses the AGENCY-CONCATENATED id, which is unique
							// across all 17,024 rows — not the bare id that got us here.
							$href = '/p/' . rawurlencode($cid) . '_' . \Illuminate\Support\Str::slug($desc);
							$agencyLabel = $c['agency_name'] ?: ($c['agency_key'] ?? '');
						@endphp
						<a class="list-group-item list-group-item-action" href="{{ $href }}">
							<div class="d-flex justify-content-between align-items-start">
								<div>
									<strong>{{ $desc }}</strong>
									<div class="text-muted small">
										{{ $agencyLabel }} · {{ $cid }}
										@if(!($c['in_current_plan'] ?? false)) · not in the current plan @endif
									</div>
								</div>
								<i class="bi bi-chevron-right"></i>
							</div>
						</a>
					@endforeach
				</div>

				<p class="text-muted small mt-4">
					The agency code is part of how the City names these projects — the Capital Projects Database, the Parks tracker and Climate Budgeting all publish it. A link above is the unambiguous form.
				</p>
			</div>
		</div>
	</div>
</div>

@endsection
