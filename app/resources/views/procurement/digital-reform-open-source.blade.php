@extends('layout')

@section('head')
{{-- Open-source alternatives: moved off the Products page onto its own page
     (owner, 2026-09-23), linked from under Products' family table the way
     Contracts links the Renewal Review Queue. Same /oce/licenses payload, so
     the figures here and on Products are one computation. --}}
@include('procurement.partials.lic-styles')
@include('procurement.partials.ds-styles')
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    $available = (bool) ($lic['available'] ?? false);
    $sum = $lic['summary'] ?? [];
    $reviewed = $sum['reviewed'] ?? ['families' => 0, 'share' => 0];
    $modelNote = implode(' + ', $sum['ai_models'] ?? []);
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <a href="{{ route('research.digital-reform.products') }}" class="db-btn db-btn-ghost db-btn-sm mb-2"><i class="bi bi-arrow-left"></i> Products</a>
        <h1 style="margin-bottom: var(--db-space-1);">Open-source alternatives</h1>
        @include('sub.analysis-tag', ['reviewed' => $reviewed, 'modelNote' => $modelNote])
        <p class="db-page-lead">
            Licensed products with a credible open-source substitute, ordered by how much is up
            for renewal soonest. Only a hand-reviewed row names an alternative.
        </p>
        @include('sub.digital-scope-note', ['scope' => ['mode' => 'derived', 'positive' => true]])

        @if(!$available)
            <div class="db-alert db-alert-warning mt-3">
                <i class="bi bi-exclamation-triangle"></i>
                License analysis is not available right now.
                @if(!empty($lic['reason']))
                    <span class="lic-sub">Reason: {{ $lic['reason'] }}</span>
                @endif
            </div>
        @else
            <div class="mt-3">
                @include('procurement.partials.open-source-alternatives')
            </div>
        @endif
    </div>
</div>
@endsection
