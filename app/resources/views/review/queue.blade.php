@extends('layout')

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        @php
            $items    = $queue['items'] ?? [];
            $qname    = $queue['queue'] ?? '';
            $total    = count($items);
            $settled  = 0;
            foreach ($items as $r) {
                if (!empty($r['decision']) || !empty($r['in_seed'])) $settled++;
            }
            $remaining = $total - $settled;
            $firstOpen = null;
            foreach ($items as $r) {
                if (empty($r['decision']) && empty($r['in_seed'])) { $firstOpen = $r['item_id']; break; }
            }
            $recorded = session('recorded');
        @endphp

        <div class="mb-2"><a href="{{ route('review') }}">&larr; All queues</a> &middot; <a href="{{ route('review.glossary') }}">Glossary</a></div>

        <div class="d-flex justify-content-between align-items-end flex-wrap gap-3 mb-4">
            <div>
                <div class="db-eyebrow">Queue</div>
                <h1 class="mb-1">{{ $qname }}</h1>
                <p class="db-page-lead mb-0">{{ $queue['question'] ?? '' }}</p>
            </div>
            <div class="d-flex align-items-center gap-3">
                <div class="text-end">
                    <div style="font-size: var(--db-text-xl); font-weight: var(--db-weight-bold); color: var(--db-primary); line-height: 1; font-variant-numeric: tabular-nums;">{{ number_format($settled) }} / {{ number_format($total) }}</div>
                    <div class="text-muted" style="font-size: var(--db-text-2xs);">decided</div>
                </div>
                @if ($firstOpen !== null)
                    <a class="db-btn db-btn-primary" href="{{ route('review.item', [$qname, $firstOpen]) }}">Review {{ number_format($remaining) }} remaining</a>
                @endif
            </div>
        </div>

        @if ($recorded)
            <div class="db-alert db-alert-success mb-3">Recorded your decision on <strong>{{ $recorded }}</strong>.</div>
        @endif

        <div class="db-table-wrap">
            <table class="table db-table">
                <thead>
                    <tr>
                        <th>Candidate</th>
                        <th>Kind</th>
                        <th>Confidence</th>
                        <th class="text-end">Contracts</th>
                        <th class="text-end">Vendors</th>
                        <th class="text-end">Agencies</th>
                        <th class="text-end">Committed</th>
                        <th>Decision</th>
                    </tr>
                </thead>
                <tbody>
                @foreach ($items as $r)
                    @php
                        // ⚠ Evidence is an ordered list of labelled facts, so the
                        // columns are looked up by LABEL rather than by position —
                        // a queue may show different evidence and must not silently
                        // land its values under the wrong headings.
                        $ev = [];
                        foreach (($r['evidence'] ?? []) as $e) {
                            if (!isset($ev[$e['label']])) $ev[$e['label']] = $e['value'];
                        }
                        $decision = $r['decision'] ?? null;
                        $inSeed   = !empty($r['in_seed']);
                        $muted    = ($decision || $inSeed) ? 'color: var(--db-text-muted);' : '';
                        $conf     = $r['confidence'] ?? 'none';
                        $confClass = $conf === 'high' ? 'db-badge-success'
                                   : ($conf === 'medium' ? 'db-badge-warning' : 'db-badge-neutral');
                    @endphp
                    <tr>
                        <td style="{{ $muted }}">
                            <a href="{{ route('review.item', [$qname, $r['item_id']]) }}"><strong>{{ $r['subject'] }}</strong></a>
                        </td>
                        <td><span class="db-badge db-badge-navy">{{ $r['proposal'] ?? '' }}</span></td>
                        <td><span class="db-badge {{ $confClass }}">{{ $conf }}</span></td>
                        <td class="text-end" style="{{ $muted }}">{{ $ev['contracts'] ?? '' }}</td>
                        <td class="text-end" style="{{ $muted }}">{{ $ev['vendors'] ?? '' }}</td>
                        <td class="text-end" style="{{ $muted }}">{{ $ev['agencies'] ?? '' }}</td>
                        <td class="text-end" style="{{ $muted }}">{{ $ev['value'] ?? '' }}</td>
                        <td>
                            {{-- ⚠ TWO DIFFERENT SETTLED STATES, never one flag. `in seed`
                                 was decided before this tool and is already published;
                                 a decision is yours and pending export. --}}
                            @if ($decision)
                                <span class="db-badge db-badge-success">{{ $decision['verb'] }}</span>
                                <span class="text-muted" style="font-size: var(--db-text-3xs);">{{ $decision['actor'] }}</span>
                            @elseif ($inSeed)
                                <span class="db-badge db-badge-neutral">in seed</span>
                            @else
                                <span class="text-muted">&mdash;</span>
                            @endif
                        </td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </div>

        <p class="text-muted mt-3" style="font-size: var(--db-text-2xs);">
            Showing {{ number_format($total) }}. Decided rows stay listed so a decision can be revisited &mdash;
            nothing is hidden once it is answered.
        </p>

    </div>
</div>
@endsection
