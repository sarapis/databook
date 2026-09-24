@extends('layout')

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        {{-- ⚠ Every conditional phrase is precomputed: a Blade directive glued
             to a word character is not compiled and only its @endif is, which
             500s the page while `php -l` passes. --}}
        @php
            $rows = is_array($queues) ? $queues : [];
            $awaiting = 0;
            foreach ($rows as $q) {
                if (is_numeric($q['awaiting'] ?? null)) $awaiting += (int)$q['awaiting'];
            }
            $editorLabel = $editor ? $editor : 'not identified';
        @endphp

        <div class="mb-4">
            <div class="d-flex justify-content-between align-items-start">
                <div class="db-eyebrow">Review queues</div>
                <a href="{{ route('review.glossary') }}" style="font-size: var(--db-text-2xs);">Glossary</a>
            </div>
            <h1 class="mb-1">{{ number_format($awaiting) }} decisions waiting</h1>
            <p class="db-page-lead">
                Each queue counts only what is genuinely unreviewed &mdash; measured with that
                queue&rsquo;s own rule, not a shared flag.
            </p>
            <p class="text-muted" style="font-size: var(--db-text-2xs);">
                Signed in as <strong>{{ $editorLabel }}</strong>. Decisions are recorded against this name.
            </p>
        </div>

        @foreach ($rows as $q)
            @php
                $name      = $q['queue'] ?? '';
                $broken    = array_key_exists('error', $q);
                $count     = $q['awaiting'] ?? null;
                $isEmpty   = (!$broken && (int)$count === 0);
                $rowStyle  = $isEmpty ? 'background: var(--db-bg-tertiary);' : '';
                $countTxt  = $broken ? '!' : number_format((int)$count);
                $safe      = !empty($q['safe_by_construction']);
                $inGit     = !empty($q['in_git']);
            @endphp
            <div class="db-card mb-3" style="{{ $rowStyle }}">
                <div class="db-card-body d-flex align-items-center gap-4 flex-wrap">
                    <div style="min-width: 76px; text-align: right;">
                        <div style="font-size: 2rem; font-weight: var(--db-weight-bold); color: var(--db-primary); line-height: 1; font-variant-numeric: tabular-nums;">{{ $countTxt }}</div>
                    </div>
                    <div class="flex-grow-1" style="min-width: 320px;">
                        <div class="d-flex align-items-center gap-2 flex-wrap mb-1">
                            <span class="db-card-title mb-0">{{ $name }}</span>
                            @if ($inGit)
                                <span class="db-badge db-badge-success">seed in git</span>
                            @else
                                <span class="db-badge db-badge-warning">seed NOT in git</span>
                            @endif
                            @if ($safe)
                                <span class="db-badge db-badge-success">safe by construction</span>
                            @else
                                <span class="db-badge db-badge-warning">not safe by construction</span>
                            @endif
                        </div>
                        <div>{{ $q['question'] ?? '' }}</div>
                        <div class="text-muted" style="font-size: var(--db-text-2xs); font-family: var(--db-font-mono);">{{ $q['seed'] ?? '' }}</div>
                        {{-- ⚠ A queue whose generator table is absent says so. A zero here
                             would read as "worked through", which is #256's defect. --}}
                        @if ($broken)
                            <div class="db-badge db-badge-danger mt-2">generator unavailable: {{ $q['error'] }}</div>
                        @endif
                    </div>
                    <div>
                        @if (!$broken && !$isEmpty)
                            <a class="db-btn db-btn-primary" href="{{ route('review.queue', [$name]) }}">Review</a>
                        @else
                            <span class="db-badge db-badge-neutral">{{ $broken ? 'unavailable' : 'clear' }}</span>
                        @endif
                    </div>
                </div>
            </div>
        @endforeach

    </div>
</div>
@endsection
