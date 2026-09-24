{{-- ============================================================
     OPEN-SOURCE ALTERNATIVES — the three review bands and the gaps in the
     open-source commons. Moved off the Products page onto its own page
     (owner, 2026-09-23); the Products page links here from under the
     family table. Needs $lic (the /oce/licenses payload).
     ⚠⚠ THE BANDS ARE NEVER MERGED. Only the reviewed band names a
     replacement (#146), and the API scopes it to curated rows.
     ============================================================ --}}
@php
    $catMeta    = $lic['catalogue'] ?? [];
    $gaps       = $catMeta['known_gaps']['no_results_observed_for'] ?? [];
    // ISO timestamp -> plain date; the raw string read as noise mid-sentence.
    $catDate    = !empty($catMeta['generated_at']) ? substr(trim((string) $catMeta['generated_at']), 0, 10) : '';
    $oss        = $lic['oss'] ?? [];
    $ossCur     = $oss['curated'] ?? [];
    $ossRev     = $oss['review'] ?? [];
    $ossCurTot  = $oss['curated_total'] ?? ['families' => 0, 'contracts' => 0, 'value' => 0];
    $ossRevTot  = $oss['review_total'] ?? ['families' => 0, 'contracts' => 0, 'value' => 0];
    // Precomputed: a Blade directive glued to a word character is not compiled.
    $ossHorizonYear = substr((string) ($oss['horizon'] ?? '2030-01-01'), 0, 4);
    $ossNone    = $oss['no_alternative'] ?? [];
    $ossNoneTot = $oss['no_alternative_total'] ?? ['families' => 0, 'contracts' => 0, 'value' => 0];
@endphp
@if(count($ossCur) || count($ossRev) || count($ossNone))
<div class="db-table-wrap mb-5" id="open-source">
    <div class="px-3 pt-3">
        <h2 class="lic-h2"><i class="bi bi-arrow-repeat"></i> Open-source alternatives</h2>
        <p class="lic-sub">
            Products the City licenses that have a credible open-source substitute,
            <strong>ordered by how much is up for renewal before {{ $ossHorizonYear }}</strong> &mdash;
            a renewal is the moment a switch costs least.
            {{-- ⚠⚠ TWO BANDS, NEVER MERGED. Only the reviewed one names a
                 replacement; that is #146's rule, and the query behind it is
                 scoped to curated rows so an unreviewed candidate cannot reach
                 this page by omission. --}}
            
        </p>
    </div>

    @if(count($ossCur))
    <div class="px-3">
        <h3 style="font-size: var(--db-text-base);">Reviewed, with a named alternative</h3>
        <p class="lic-sub">
            {{ number_format($ossCurTot['families']) }}
            {{ $ossCurTot['families'] == 1 ? 'product' : 'products' }} &mdash;
            <strong>{{ number_format($ossCurTot['contracts']) }} contracts worth
            ${{ number_format($ossCurTot['value'] / 1000000, 1) }}M</strong> expiring before
            {{ $ossHorizonYear }}. Each alternative was checked by hand and carries its
            source; <em>government adopters</em> counts other public bodies known to run it.
        </p>
    </div>
    <div class="table-responsive">
        <table class="db-table db-table-striped db-dt">
            <thead><tr>
                <th>Product</th><th>Open-source alternative</th><th>Confidence</th>
                <th class="lic-num">Gov. adopters</th>
                <th class="lic-num">Expiring value</th><th>Soonest end</th>
            </tr></thead>
            <tbody>
            @foreach($ossCur as $o)
                <tr>
                    <td>
                        @if($o['slug'] !== '')
                            <a href="{{ route('research.digital-reform.product-family', ['slug' => $o['slug']]) }}">{{ $o['family'] }}</a>
                        @else
                            {{ $o['family'] }}
                        @endif
                    </td>
                    <td>
                        @if($o['url'] !== '')
                            <a href="{{ $o['url'] }}" target="_blank" rel="noopener noreferrer">{{ $o['candidate'] }}</a>
                        @else
                            {{ $o['candidate'] }}
                        @endif
                        @if(($o['licence'] ?? '') !== '')
                            <span class="text-muted small">({{ $o['licence'] }})</span>
                        @endif
                    </td>
                    <td><span class="db-badge db-badge-neutral">{{ $o['confidence'] }}</span></td>
                    <td class="lic-num">{{ $o['gov_adopters'] !== null ? number_format($o['gov_adopters']) : '—' }}</td>
                    <td class="lic-num">${{ number_format($o['expiring_value'] / 1000000, 2) }}M</td>
                    <td>{{ $o['soonest_end'] }}</td>
                </tr>
            @endforeach
            </tbody>
        </table>
    </div>
    @endif

    @if(count($ossRev))
    <div class="px-3 pt-3">
        <h3 style="font-size: var(--db-text-base);">Worth reviewing &mdash; no alternative picked yet</h3>
        <p class="lic-sub mb-2">
            {{ number_format($ossRevTot['families']) }} further
            {{ $ossRevTot['families'] == 1 ? 'product' : 'products' }}
            (<strong>{{ number_format($ossRevTot['contracts']) }} contracts,
            ${{ number_format($ossRevTot['value'] / 1000000, 1) }}M expiring</strong>) were rated
            <em>replaceable</em> by the classifier, but <strong>no one has reviewed them and
            no substitute is named here</strong>.
        </p>
        <details class="lic-more mb-2">
            <summary>Why no alternative is named</summary>
            <p class="lic-sub mb-0">
            Naming one on an unreviewed judgement is exactly what the list above exists to avoid.
            This is a queue of things to look at, not a recommendation.
            {{-- ⚠ The rating is only shown for software-licence purchases: asking
                 "could we build this?" of hosting answers "no" and hides the money. --}}
            Only outright software licences are considered &mdash; the question is
            meaningless for hosting or a support tier.
            </p>
        </details>
        <p class="mb-3">
            @foreach($ossRev as $o)
                @if($o['slug'] !== '')
                    <a class="db-badge db-badge-info" style="text-decoration: none;"
                       href="{{ route('research.digital-reform.product-family', ['slug' => $o['slug']]) }}">{{ $o['family'] }}</a>
                @else
                    <span class="db-badge db-badge-neutral">{{ $o['family'] }}</span>
                @endif
            @endforeach
        </p>
    </div>
    @endif

    @if(count($ossNone))
    <div class="px-3 pb-3">
        <h3 style="font-size: var(--db-text-base);">Reviewed &mdash; no credible alternative found</h3>
        <p class="lic-sub mb-2">
            {{-- ⚠ These are FINDINGS, not gaps in the review. Left in the
                 table above they rendered as a blank alternative under a
                 heading promising a named one. --}}
            {{ number_format($ossNoneTot['families']) }}
            {{ $ossNoneTot['families'] == 1 ? 'product was' : 'products were' }}
            reviewed and <strong>no credible open-source substitute was
            found</strong> &mdash; {{ number_format($ossNoneTot['contracts']) }}
            {{ $ossNoneTot['contracts'] == 1 ? 'contract' : 'contracts' }},
            ${{ number_format($ossNoneTot['value'] / 1000000, 1) }}M expiring. A result, not an omission.
        </p>
        <p class="mb-0">
            @foreach($ossNone as $o)
                @if($o['slug'] !== '')
                    <a class="db-badge db-badge-neutral" style="text-decoration: none;"
                       href="{{ route('research.digital-reform.product-family', ['slug' => $o['slug']]) }}">{{ $o['family'] }}</a>
                @else
                    <span class="db-badge db-badge-neutral">{{ $o['family'] }}</span>
                @endif
            @endforeach
        </p>
    </div>
    @endif
</div>
@endif

{{-- After the bands: on its own page the reader came for the alternatives. --}}
@if(count($gaps))
<div class="lic-note mb-5">
    <div class="lic-tag">Gaps in the open-source commons</div>
    <p style="margin: 4px 0 6px;">
        Categories where the European public-sector catalogues have <strong>nothing</strong> &mdash;
        asserted by the catalogue itself, not merely a search that came back empty:
    </p>
    <ul style="margin: 0 0 6px; padding-left: 1.2rem;">
        @foreach($gaps as $g)
            <li>{{ $g }}</li>
        @endforeach
    </ul>
    <div class="lic-sub">
        The two largest lines rated most replaceable fall in these gaps.
        @if($catDate !== '')
            Catalogue data as of <strong>{{ $catDate }}</strong> &mdash; its
            JSON is regenerated weekly but redeployed by hand, so this date is the honest
            freshness signal.
        @endif
        @if(!empty($catMeta['mapped_products']))
            <i class="bi bi-exclamation-triangle"></i> The catalogue's replacement index maps {{ $catMeta['mapped_products'] }} proprietary
            products out of {{ number_format($catMeta['entries'] ?? 0) }} entries, so any OTHER
            blank means "not mapped", never "no alternative exists".
        @endif
    </div>
</div>
@endif
