@extends('layout')

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        @php
            $qname    = $queue['queue'] ?? '';
            $verbs    = $queue['verbs'] ?? [];
            $decision = $item['decision'] ?? null;
            $inSeed   = !empty($item['in_seed']);
            $conf     = $item['confidence'] ?? 'none';
            $confClass = $conf === 'high' ? 'db-badge-success'
                       : ($conf === 'medium' ? 'db-badge-warning' : 'db-badge-neutral');
            // ⚠ Every evidence item is now a stat: the matched contracts moved
            // out of `evidence` and into `records`, because they are a table with
            // shared columns rather than a set of labelled facts.
            $stats = $item['evidence'] ?? [];
            $links       = $item['links'] ?? [];
            $sourceCount = 0;
            foreach ($links as $l) { if (!empty($l['is_source'])) $sourceCount++; }
            $records     = $item['records'] ?? [];
            $cols        = $item['record_columns'] ?? [];
            $recordsNote = $item['records_note'] ?? '';
            $pct = $total > 0 ? round(($position / $total) * 100, 1) : 0;
            $canAmend = in_array('amend', $verbs, true);
            $error = session('error');
        @endphp

        <div class="mb-2"><a href="{{ route('review.queue', [$qname]) }}">&larr; {{ $qname }}</a> &middot; <a href="{{ route('review.glossary') }}">Glossary</a></div>

        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-1">
            <p class="mb-0">{{ $queue['question'] ?? '' }}</p>
            <span class="text-muted" style="font-size: var(--db-text-2xs); font-variant-numeric: tabular-nums;">{{ $position }} of {{ $total }}</span>
        </div>
        <div style="height: 3px; background: var(--db-navy-100); border-radius: var(--db-radius-pill); overflow: hidden;" class="mb-4">
            <div style="width: {{ $pct }}%; height: 100%; background: var(--db-primary);"></div>
        </div>

        @if ($error)
            <div class="db-alert db-alert-danger mb-3">{{ $error }}</div>
        @endif

        {{-- ⚠ An already-settled item is shown, never hidden — but it says WHICH
             kind of settled, because "the project already published this" and
             "I answered this a minute ago" are different things to a reviewer. --}}
        @if ($inSeed)
            <div class="db-alert db-alert-info mb-3">
                Already curated into this queue&rsquo;s seed before this tool existed. Deciding again here
                will not remove it &mdash; edit the seed if it is wrong.
            </div>
        @elseif ($decision)
            <div class="db-alert db-alert-success mb-3">
                <strong>{{ $decision['verb'] }}</strong> by {{ $decision['actor'] }}. Deciding again replaces that answer.
            </div>
        @endif

        <div class="row g-4">
            <div class="col-lg-7">
                @php $pair = $queue['pair_labels'] ?? []; @endphp
                @if (count($pair) === 2)
                    {{-- ⚠⚠ A MATCH QUEUE ASKS "IS A THE SAME AS B", SO A AND B MUST
                         CARRY THE SAME WEIGHT. The single-subject layout below makes
                         one an <h1> and the other a small badge, which reads as a
                         title with a tag rather than as two candidates for the same
                         entity — and that layout was built for `program-names`, the
                         one queue that is NOT a comparison. --}}
                    <div class="row g-3 align-items-stretch mb-3">
                        <div class="col-sm-5">
                            <div class="db-card h-100"><div class="db-card-body">
                                <div class="db-eyebrow mb-1">{{ $pair[0] }}</div>
                                <div style="font-size: var(--db-text-lg); font-weight: var(--db-weight-semibold);">{{ $item['subject'] }}</div>
                            </div></div>
                        </div>
                        <div class="col-sm-2 d-flex align-items-center justify-content-center">
                            <span class="db-text-muted" style="font-size: var(--db-text-sm);">same&nbsp;entity?</span>
                        </div>
                        <div class="col-sm-5">
                            <div class="db-card h-100"><div class="db-card-body">
                                <div class="db-eyebrow mb-1">{{ $pair[1] }}</div>
                                <div style="font-size: var(--db-text-lg); font-weight: var(--db-weight-semibold);">{{ $item['proposal'] ?? '' }}</div>
                            </div></div>
                        </div>
                    </div>
                    <div class="mb-3"><span class="db-badge {{ $confClass }}">{{ $conf }} confidence</span></div>
                @else
                    <div class="d-flex align-items-start gap-3 flex-wrap mb-3">
                        <h1 class="mb-0">{{ $item['subject'] }}</h1>
                        <div class="d-flex gap-2" style="padding-top: 8px;">
                            <span class="db-badge db-badge-navy">{{ $item['proposal'] ?? '' }}</span>
                            <span class="db-badge {{ $confClass }}">{{ $conf }} confidence</span>
                        </div>
                    </div>
                @endif

                @if (!empty($item['why']))
                    <div style="border-left: 3px solid var(--db-navy-100); padding-left: var(--db-space-2);" class="mb-4">
                        <div class="db-eyebrow mb-1">What the extractor says</div>
                        <p class="mb-0">{{ $item['why'] }}</p>
                    </div>
                @endif

                <div class="db-stat-grid mb-4">
                    @foreach ($stats as $s)
                        <div class="db-stat">
                            <div class="db-stat-label">{{ $s['label'] }}</div>
                            <div class="db-stat-value">{{ $s['value'] }}</div>
                        </div>
                    @endforeach
                </div>

                @if (count($records) > 0)
                    <div class="db-eyebrow mb-2">Contracts it matched</div>
                    <div class="db-table-wrap">
                        <table class="table db-table">
                            <thead>
                                <tr>
                                    {{-- ⚠ Columns come from the QUEUE, not from this view. A
                                         second queue showing different records needs no change
                                         here — the licence-label lesson applied to a table. --}}
                                    @foreach ($cols as $c)
                                        <th @if (($c[2] ?? 'left') === 'right') class="text-end" @endif>{{ $c[1] }}</th>
                                    @endforeach
                                </tr>
                            </thead>
                            <tbody>
                            @foreach ($records as $r)
                                <tr>
                                    @foreach ($cols as $c)
                                        @php
                                            $key   = $c[0];
                                            $align = ($c[2] ?? 'left') === 'right' ? 'text-end' : '';
                                            $val   = $r[$key] ?? '';
                                            $isAmt = ($key === 'amount');
                                            // ⚠⚠ A CEILING IS NOT SPEND. A master agreement's
                                            // figure is headroom drawn down under other ids
                                            // (#261/#294/#301). Labelled, never silently summed
                                            // into a column of amounts.
                                            $ceiling = !empty($r['is_ceiling']);
                                            $amtTxt = $isAmt && $val !== ''
                                                ? '$' . number_format((float)$val)
                                                : $val;
                                        @endphp
                                        <td class="{{ $align }}" style="{{ $isAmt ? 'font-variant-numeric: tabular-nums;' : '' }}">
                                            @if ($key === 'title' && !empty($r['href']))
                                                <a href="{{ $r['href'] }}" target="_blank" rel="noopener">{{ $val }}</a>
                                            @elseif ($isAmt && $ceiling)
                                                {{ $amtTxt }}
                                                <span class="db-badge db-badge-warning">ceiling</span>
                                            @else
                                                {{ $amtTxt }}
                                            @endif
                                        </td>
                                    @endforeach
                                </tr>
                            @endforeach
                            </tbody>
                        </table>
                    </div>
                    @if ($recordsNote !== '')
                        <p class="text-muted mt-2" style="font-size: var(--db-text-2xs);">{{ $recordsNote }}</p>
                    @endif
                @endif
            </div>

            <div class="col-lg-5">
                <div class="db-card">
                    <div class="db-card-body">
                        <div class="db-eyebrow mb-3">Your decision</div>

                        <form method="POST" action="{{ route('review.decide', [$qname, $item['item_id']]) }}">
                            @csrf
                            <input type="hidden" name="next" value="{{ $nextId }}">

                            @if ($canAmend)
                                <label class="form-label" style="font-size: var(--db-text-2xs); font-weight: var(--db-weight-semibold);">Kind</label>
                                {{-- ⚠ Amend carries a VALUE, which is why it is a field and not
                                     just a third button: the common correction here is not
                                     "wrong" but "wrong kind". --}}
                                <select name="value" class="form-select mb-3">
                                    {{-- ⚠ The kinds the API SERVES, never a list typed here.
                                         A hardcoded one omitted labor_code, agency and unclear
                                         — three of the nine the classifier can emit, and two of
                                         them are 37 real candidates a reviewer could not amend
                                         to. Same defect as the licence capability labels. --}}
                                    @foreach ($kinds as $k)
                                        <option value="{{ $k }}" @if (($item['proposal_value'] ?? '') === $k) selected @endif>{{ $k }}</option>
                                    @endforeach
                                </select>
                            @endif

                            <label class="form-label" style="font-size: var(--db-text-2xs); font-weight: var(--db-weight-semibold);">Note</label>
                            <textarea name="note" class="form-control mb-3" rows="3"
                                placeholder="Why this decision, for whoever reads the seed later"></textarea>

                            <div class="d-grid gap-2">
                                {{-- ⚠ Only the verbs THIS queue accepts. `dismiss` exists for
                                     untrusted public submissions and must never appear on a
                                     generator queue, where spam is not a thing that happens. --}}
                                {{-- ⚠⚠ LABELS COME FROM THE QUEUE, NEVER FROM HERE. Hardcoding
                                     them put program-names' "Not a program" on the reject
                                     button of every queue: on org-vendors, the answer to
                                     "The Nation vs NATION GROUP INC" read as "Not a
                                     program". A label that is right on the queue it was
                                     written for and nonsense elsewhere is invisible to
                                     whoever writes it. --}}
                                @php $vl = $queue['verb_labels'] ?? []; @endphp
                                @if (in_array('accept', $verbs, true))
                                    <button class="db-btn db-btn-primary" name="verb" value="accept" type="submit">{{ $vl['accept'] ?? 'Accept' }}</button>
                                @endif
                                @if ($canAmend)
                                    <button class="db-btn db-btn-outline" name="verb" value="amend" type="submit">{{ $vl['amend'] ?? 'Amend' }}</button>
                                @endif
                                @if (in_array('reject', $verbs, true))
                                    <button class="db-btn db-btn-outline" name="verb" value="reject" type="submit"
                                        style="color: var(--db-danger-fg); border-color: var(--db-danger-border);">{{ $vl['reject'] ?? 'Reject' }}</button>
                                @endif
                                @if (in_array('dismiss', $verbs, true))
                                    <button class="db-btn db-btn-ghost" name="verb" value="dismiss" type="submit">Dismiss</button>
                                @endif
                            </div>
                        </form>
                    </div>
                </div>

                <div class="db-card mt-3">
                    <div class="db-card-body">
                        <div class="db-eyebrow mb-1">Related links</div>
                        {{-- ⚠ "Related links", not "Citations": most links a reviewer wants
                             here are leads, context or things to come back to. Only the
                             ones flagged below become Source clauses, and the reviewer
                             picks — a research trail and a published citation are not the
                             same thing. --}}
                        <p class="text-muted mb-3" style="font-size: var(--db-text-2xs);">
                            Anything worth keeping against this item. Flag the ones you stand
                            behind and they become
                            <span style="font-family: var(--db-font-mono);">Source:</span>
                            clauses on the seed row; the rest stay here as research.
                        </p>

                        @foreach ($links as $l)
                            @php
                                // ⚠ The URL was scheme-checked server-side before storage.
                                // Blade escaping alone does NOT make an href safe — a
                                // `javascript:` URL still executes — so the API refuses
                                // anything but http/https rather than relying on this.
                                $lnote  = trim((string)($l['note'] ?? ''));
                                $isSrc  = !empty($l['is_source']);
                                $flagTo = $isSrc ? '0' : '1';
                                $flagLabel = $isSrc ? 'Unflag' : 'Use as source';
                            @endphp
                            <div class="mb-3 pb-3" style="border-bottom: 1px solid var(--db-gray-200);">
                                <div class="d-flex align-items-start gap-2">
                                    @if ($isSrc)
                                        <span class="db-badge db-badge-success">source</span>
                                    @endif
                                    <a href="{{ $l['url'] }}" target="_blank" rel="noopener noreferrer"
                                       style="font-size: var(--db-text-2xs); word-break: break-all;">{{ $l['url'] }}</a>
                                </div>
                                @if ($lnote !== '')
                                    <div style="font-size: var(--db-text-2xs); color: var(--db-text);" class="mt-1">{{ $lnote }}</div>
                                @endif
                                <div class="d-flex justify-content-between align-items-center mt-1">
                                    <span class="text-muted" style="font-size: var(--db-text-3xs);">{{ $l['actor'] ?? '' }}</span>
                                    <div class="d-flex gap-1">
                                        <form method="POST" action="{{ route('review.linksource', [$qname, $item['item_id'], $l['id']]) }}">
                                            @csrf
                                            <input type="hidden" name="is_source" value="{{ $flagTo }}">
                                            <button type="submit" class="db-btn db-btn-ghost db-btn-sm">{{ $flagLabel }}</button>
                                        </form>
                                        <form method="POST" action="{{ route('review.unlink', [$qname, $item['item_id'], $l['id']]) }}">
                                            @csrf
                                            <button type="submit" class="db-btn db-btn-ghost db-btn-sm">Remove</button>
                                        </form>
                                    </div>
                                </div>
                            </div>
                        @endforeach

                        {{-- ⚠ A separate form from the decision, deliberately: a link is
                             research and accumulates BEFORE an answer. Sharing the decision
                             form would mean you could not park a link without deciding. --}}
                        <form method="POST" action="{{ route('review.link', [$qname, $item['item_id']]) }}">
                            @csrf
                            <input type="url" name="url" class="form-control mb-2"
                                   placeholder="https://" required>
                            <input type="text" name="note" class="form-control mb-2"
                                   placeholder="What this link shows">
                            <div class="d-flex justify-content-between align-items-center">
                                <label style="font-size: var(--db-text-2xs); color: var(--db-text-muted);">
                                    <input type="checkbox" name="is_source" value="1"> use as source
                                </label>
                                <button type="submit" class="db-btn db-btn-outline db-btn-sm">Add link</button>
                            </div>
                        </form>

                        {{-- ⚠ Shows exactly what an export would write, rather than leaving
                             the reviewer to infer it from a flag. --}}
                        @if ($sourceCount > 0)
                            <p class="text-muted mt-3 mb-0" style="font-size: var(--db-text-3xs);">
                                {{ $sourceCount }} of {{ count($links) }} will be written as
                                <span style="font-family: var(--db-font-mono);">Source:</span> on the seed row.
                            </p>
                        @endif
                    </div>
                </div>

                <div class="db-card mt-3" style="background: var(--db-bg-band);">
                    <div class="db-card-body">
                        <div class="db-eyebrow mb-2">Where this goes</div>
                        <p class="mb-0" style="font-size: var(--db-text-2xs);">
                            Recorded now against <strong>{{ $editor ? $editor : 'not identified' }}</strong>.
                            Exporting to <span style="font-family: var(--db-font-mono);">{{ $queue['seed'] ?? '' }}</span>
                            opens a pull request &mdash; nothing reaches the site without review.
                        </p>
                    </div>
                </div>
            </div>
        </div>

    </div>
</div>
@endsection
