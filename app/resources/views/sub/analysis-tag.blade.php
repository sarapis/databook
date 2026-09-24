{{-- The Analysis identity as a TAG rather than a banner, for leaf pages where the
     full orange box crowds the header. ⚠⚠ THE CAVEAT STAYS VISIBLE: the summary
     itself reads "prompts to investigate, not determinations" without opening
     anything, and the full sentence is the disclosure body. This is the same
     shape the owner granted for the capital profile's money note -- a disclosure
     is allowed ONLY because the part a reader must not miss is on its face.
     A <details>, not a hover-only tooltip: hover does not exist on a phone, and
     a tap opens this. Desktop hover opens it too (CSS). --}}
<details class="db-analysis-tag" role="note">
    <summary>
        <i class="bi bi-stars"></i>
        <strong>AI analysis</strong>
        <span class="db-analysis-tag-hint">&mdash; prompts to investigate, not official determinations</span>
    </summary>
    <div class="db-analysis-tag-body">
        Most of Databook is official NYC open data &mdash; normalized, but not altered. This page is
        different: it adds an interpretation layer (analyst classifications and AI-generated signals
        such as build-vs-buy, license detection, and review flags) to support decisions. Treat these
        signals as prompts to investigate, not official determinations.
        {{-- Optional page detail (owner, 2026-09-18): the Products index used to
             stack this tag, a reviewed-share paragraph and the scope note as
             three separate explanations before its first figure. A page that
             passes `$reviewed` gets the share here, inside the one disclosure. --}}
        @isset($reviewed)
            <div style="margin-top: var(--db-space-1); padding-top: var(--db-space-1); border-top: 1px solid var(--db-border);">
                <strong>{{ number_format($reviewed['families'] ?? 0) }} families, {{ $reviewed['share'] ?? 0 }}% of the
                value here, carry a hand-reviewed classification</strong>; the rest, and license detection
                itself, are AI-derived and unreviewed.
                <a href="#method">What this is built from, and what it cannot tell you.</a>
                @isset($modelNote)@if($modelNote) Classified by {{ $modelNote }}.@endif @endisset
            </div>
        @endisset
    </div>
</details>
