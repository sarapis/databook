{{--
    Digital Services Analysis — Overview storyboard.

    Recreated from design_handoff_digital_services_storyboard (Claude Design).
    Markup, copy, SVG diagrams and animation timings are transcribed verbatim
    from the handoff — colors/type/spacing match the --db-* token sheet
    (bespoke diagram hues are the handoff's own "diagram blues" palette, not
    tokens, per its own README). Behavior lives in
    public/js/digital-services-storyboard.js.

    Beat 08 "Conclusion" is intentionally NOT here — its four-link-row layout
    was reused to restyle the Overview's own nav cards instead (see
    digital-reform.blade.php), per the handoff review. This partial is beats
    01–07 only, and the left rail has 7 dots to match.
--}}
<div id="dsStoryboard">

@php
    // ⚠⚠ EVERY FIGURE ON THIS PAGE USED TO BE TYPED. 793 lines, 38 figures in
    // rendered copy, and the only four Blade expressions in the whole partial
    // were `route()` calls — so nothing here could move when the data did, and
    // several had already drifted badly. Measured against the live payload
    // 2026-09-14, worst first:
    //
    //   beat 05   "$1.37B / 948 contracts / 431 products / top-10 79%"
    //             -> $1.77B / 1,601 / 814 / 63.4%  (the pre-#239 figures; the
    //             product count understated by 47%)
    //   tabs 01   "686 contracts ($3,637M) expire before 2030" -> 650
    //   tabs 02   "ArcGIS ... 24 contracts"                    -> 23
    //
    // ⚠ The headline tiles (4,397 / $10.6B / 967 vendors) were still CORRECT.
    // They are computed anyway — a figure that happens to be right today is not
    // a measurement, and this page's whole claim on a reader is that it measures.
    $sbStats = $stats ?? [];
    $sbCount = (int) ($sbStats['count'] ?? 0);
    $sbTotal = (float) ($sbStats['total'] ?? 0);
    $sbVendors = (int) ($sbStats['vendor_count'] ?? 0);
    // ⭐ ONE money spelling for the whole partial, so two beats cannot round the
    // same figure differently — which is how "$13.3M" and "$13.30M" came to sit
    // on one page describing one contract set.
    $sbB = function ($v, $dp = 1) {
        return $v >= 1e9 ? '$' . number_format($v / 1e9, $dp) . 'B'
                         : '$' . number_format($v / 1e6, 0) . 'M';
    };
    $sbQueue = ($calendar ?? [])['in_queue_window'] ?? [];

    // The master-agreement figures come from `award_by_start_year.reconciles`,
    // which the Overview already has — not a second API call, and not a second
    // definition of "master". ⚠ A ceiling is NEVER added to committed money
    // anywhere on this page; it is stated on its own, which is the whole point
    // of the beat these figures sit in.
    $sbRec       = ($awardByStartYear ?? [])['reconciles'] ?? [];
    $sbMasters   = (int) (($maStory['count'] ?? null) ?: ($sbRec['master_contracts'] ?? 0));
    $sbMaCeiling = (float) (($maStory['ceiling'] ?? null) ?: ($maCeiling ?? ($sbRec['ceiling'] ?? 0)));
    // ⚠ The two numbers this sentence needs are DIFFERENT CLAIMS and the copy
    // used to merge them: 22 masters carry a Checkbook spend record, 8 show an
    // actual payment. Composed here rather than inline, for the glued-directive
    // reason recorded above.
    // ⚠⚠ AND IT MUST DEGRADE TO PROSE, NEVER TO AN EMPTY PARAGRAPH. The first
    // draft left `$sbMaLine` as '' when the masters endpoint was unreachable, and
    // the beat rendered a blank <p> — indistinguishable from a page with nothing
    // to say. Found by rendering against a stack where that endpoint 500s, which
    // is the only reason the branch was exercised at all.
    $sbMaLine = 'Most master agreements show no payment under their own id at all — they are '
        . 'ceilings, and the buying happens under separate purchase-order ids.';
    if ($maStory && $sbMasters > 0) {
        $sbMaLine = 'Only ' . number_format($maStory['with_payment']) . ' of the City\'s '
            . number_format($sbMasters) . ' master agreements show any payment under their own id at all, and only '
            . number_format($maStory['with_record']) . ' carry a spending record of any kind — the rest are '
            . 'ceilings with nothing visible drawn against them.';
    }
    $sbArc       = $licStory['arcgis'] ?? null;
    // ⚠⚠ A MISSING FAMILY MUST NOT LEAVE A HOLE IN A SENTENCE. With `$sbArc`
    // null the inline version rendered "bought on separate contracts by
    // different agencies" — grammatical wreckage, not a degraded state. Composed
    // here so the numeric clause is present or absent as a WHOLE.
    $sbArcScope = $sbArc
        ? 'bought on ' . number_format($sbArc['contracts']) . ' separate contracts by '
          . number_format($sbArc['agencies']) . ' different agencies'
        : 'bought separately by many agencies';
    $sbArcLine = $sbArc
        ? $sbB($sbArc['value']) . ' across ' . number_format($sbArc['contracts'])
          . ' contracts and ' . number_format($sbArc['agencies']) . ' agencies.'
        : 'Bought separately across many contracts and agencies.';

    // ⚠⚠ THE SLAB LABELS WERE TYPED, AND ON THIN DATA THE PAGE CONTRADICTED
    // ITSELF IN ADJACENT SENTENCES: "581 technology contracts worth $2.8B in
    // total" sat directly above "Contracted staffing $2.9B" — a segment larger
    // than the whole. On production the typed values happened to agree, which is
    // exactly why nobody could see it; only rendering against other data did.
    //
    // ⭐ THE LABELS ARE THE PAYLOAD'S OWN, not the friendlier ones typed here
    // ("Contracted staffing" for "Staffing/consulting"). Two names for one
    // segment is how this section came to have two vocabularies, and the
    // composition table further down the SAME page uses these.
    // ⚠ The GLOSS is keyed on the segment's stable `slug`, never on position — a
    // list that reorders would otherwise hand "the wires and networks" to
    // hardware. An unknown slug simply gets no gloss.
    $sbGloss = [
        'staffing-consulting'     => 'people, not software',
        'hardware-infrastructure' => 'machines and devices',
        'telecom-network'         => 'the wires and networks',
        'software-licences'       => 'the right to use it',
    ];
    $sbSegsAll = collect(($composition ?? [])['segments'] ?? [])
        ->sortByDesc(function ($x) { return (float) ($x['value'] ?? 0); })->values();
    $sbSegs  = $sbSegsAll->take(4);
    $sbRest  = $sbSegsAll->slice(4)->sum(function ($x) { return (float) ($x['value'] ?? 0); });
    $sbRestN = max(0, $sbSegsAll->count() - 4);
    $sbSegLine = function ($seg) use ($sbB, $sbGloss) {
        if (!$seg) { return ''; }
        $g = $sbGloss[$seg['slug'] ?? ''] ?? '';
        return $sbB((float) ($seg['value'] ?? 0)) . ($g ? ' — ' . $g : '');
    };

    // ⚠⚠ BOTH SENTENCES ARE COMPOSED HERE, NOT INLINE, AND THAT IS NOT STYLE.
    // The first draft wrote `expire before 2030@else …` straight into the copy —
    // a Blade directive GLUED TO A WORD CHARACTER, which Blade does not compile.
    // Only the `@endif` compiled, and the page 500'd on an unclosed `if`. The
    // trap is already recorded in this repo (`derived@if`) and I reproduced it
    // within the hour; composing the phrase in PHP removes the shape entirely.
    $sbQueueLine = $sbQueue
        ? number_format($sbQueue['contracts'] ?? 0) . ' contracts ('
          . $sbB((float) ($sbQueue['committed'] ?? 0)) . ' committed) expire before 2030'
        : 'Contracts expiring before 2030';

    // ⚠ The top-10 share is OMITTED rather than guessed when the controller could
    // not compute it (see `licStory`) — a sentence that silently drops a clause
    // is honest; one that prints a share of an unknown denominator is not.
    if ($licStory) {
        $sbLicLine = 'Software licenses alone come to <strong style="color: #162e51;">'
            . $sbB($licStory['total_value']) . '</strong> across <strong style="color: #162e51;">'
            . number_format($licStory['contracts']) . ' contracts</strong> covering <strong style="color: #162e51;">'
            . number_format($licStory['families']) . ' different products</strong>.';
        if ($licStory['top10_share'] !== null) {
            $sbLicLine .= ' Ten products account for ' . number_format($licStory['top10_share'], 0) . '% of the money.';
        }
    } else {
        $sbLicLine = 'Software licenses are a large share of this, spread over hundreds of separate products.';
    }
@endphp

    {{-- ⚠⚠ THE ONLY RULES IN THIS FILE THAT ARE NOT INLINE, AND THEY HAVE TO BE.
         Every layout here is an inline `style=` attribute transcribed from the
         design handoff, which no media query can reach — so this partial had
         ZERO responsive rules in 928 lines, and beat 07's "Ways in" panels laid
         out two desktop columns with a 76px indent on a phone. Measured at 390:
         27 elements of the four illustrative tables sat past the right edge
         with no scrollable ancestor, i.e. unreachable — "Ceiling", "Paid under
         this id", "Contracts", "Sells" and every value under them.

         `!important` is not a shortcut here, it is the only weight that beats an
         inline style. Scoped to `[data-x7-panel]` so it cannot reach anything
         else, and the mini-tables get `overflow-x: auto` rather than a narrower
         grid because one of the four needs 354px of minimum column even after
         the indent goes — the site's own rule for a table wider than its box. --}}
    <style>
        @media (max-width: 767.98px) {
            [data-x7-panel] > div {
                grid-template-columns: minmax(0, 1fr) !important;
                gap: 18px !important;
                padding-left: 0 !important;
            }
            /* The bordered mini-table: its own `overflow: hidden` is what makes
               the far columns unreachable rather than merely off-screen. */
            [data-x7-panel] > div > div[style*="border-radius: 8px"] {
                overflow-x: auto !important;
            }
            /* A pill that wraps draws its rounded border around each fragment,
               so "Sole source" rendered as two half-pills. The cell it sits in
               scrolls now, so keeping it on one line costs nothing. */
            [data-x7-panel] span[style*="border-radius: 999px"] {
                white-space: nowrap;
            }

            /* ⚠ THE BAR ROW OVERFLOWED BY ITS LABELS, NOT ITS BARS. Nine
               columns at `flex: 1` cannot shrink below their own min-content
               width, and that is the money label — "$1.20B" is 47px at 13px
               mono. Nine of those plus eight gaps need 415px against a 336px
               row, so the last two years sat past the right edge of a 390px
               screen with nothing to scroll. Shrinking the type to fit would
               need about 8px; hiding the labels would delete the figures. The
               row scrolls instead, which is what this site already does with a
               table wider than its box, and every year keeps its real value at
               a readable size. */
            [data-sb-bars] {
                overflow-x: auto !important;
                padding-bottom: 6px;
            }
            [data-sb-bar] {
                flex: 0 0 auto !important;
                min-width: 54px;
            }
        }
    </style>

    {{-- Returning-visitor collapsed state. Shown instead of the full story
         when localStorage remembers a previous "Collapse story" click. A uniform
         "Show story" control in the SAME spot as "Collapse story" below, with
         identical styling, so the two are one toggle occupying one location
         rather than two different controls. A down chevron marks it as the
         "expand" action, mirroring the up chevron on "Collapse story" below.

         Normal document flow, NOT position:fixed -- reads as one more row of
         the site's own nav (which is itself position:static, not sticky) and
         scrolls away with the page exactly the same way, rather than
         floating over the content and having to be explicitly hidden/shown
         past some scroll distance. No background -- just the text, dark navy
         since it always sits on this wrapper's own white (data-ds-collapsed
         carries no background of its own, so it's whatever's behind it: the
         page's white). --}}
    <div data-ds-collapsed hidden>
        <button type="button" data-ds-replay hidden style="display: flex; width: 100%; align-items: center; justify-content: center; gap: 6px; background: none; border: 0; padding: 10px 16px; font: 700 13px 'Public Sans', sans-serif; color: #162e51; cursor: pointer;">
            Show story
            <svg viewBox="0 0 16 16" style="width: 12px; height: 12px;" aria-hidden="true"><path d="M4 6 L8 10 L12 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
        </button>
    </div>

    {{-- ⚠ No overflow here. Setting only overflow-x makes browsers compute
         overflow-y as auto too, which turns this wrapper into a scroll
         container -- and that becomes the "nearest scrolling ancestor" for
         beat 07's sticky stage, breaking the pin (it just scrolls past
         instead of sticking). The prototype could get away with overflow-x:
         hidden because ITS beat 07 had its own dedicated overflow-y:auto
         scrollport nested inside, isolated from this wrapper; ours pins
         against the real window per the README's own instruction, so this
         wrapper must stay a plain block. Horizontal overflow from the
         full-bleed negative margin below is guarded per-beat instead (each
         SVG/diagram is capped with min()/max-width, verified with no
         horizontal scrollbar). --}}
    <div data-ds-full style="position: relative; font-family: 'Public Sans', system-ui, sans-serif; color: #162e51; background: #ffffff; margin: 0 calc(50% - 50vw);">

        {{-- Normal document flow (no position:fixed, no absolute), same
             reasoning as "Show story" above: reads as a plain row, not a
             floating control.

             Deliberately a SIBLING before beat 01's <section>, not nested
             inside it -- that section is display:flex; align-items:center
             with min-height:100vh, so anything inside its content column is
             vertically CENTERED in the viewport rather than anchored to the
             section's own top edge. A first attempt nested the button there
             and tried to cancel that with a negative margin; it measured
             correctly (gap:0) in this session's own small test viewport by
             coincidence, then showed a real gap on an actual, taller browser
             window, because centering (not a fixed offset) is what actually
             governs the column's position and a margin on one item inside it
             doesn't change that. Sitting BEFORE the section avoids the
             centering math entirely -- normal flow, immediately after
             whatever precedes it, unaffected by viewport height.

             Explicit background: #12294a (beat 01's own navy), not
             transparent -- since it's no longer nested inside that section,
             it can't rely on the section's background showing through
             behind it (that was the original white-strip bug, from sitting
             on data-ds-full's white before this fix existed). Painting the
             same navy directly on the button is what makes it blend
             seamlessly with beat 01 immediately below, regardless of DOM
             nesting. --}}
        <button type="button" data-ds-skip style="display: flex; width: 100%; align-items: center; justify-content: center; gap: 6px; background: #12294a; border: 0; padding: 10px 16px; font: 700 13px 'Public Sans', sans-serif; color: #ffffff; cursor: pointer;">
            Collapse story
            <svg viewBox="0 0 16 16" style="width: 12px; height: 12px;" aria-hidden="true"><path d="M4 10 L8 6 L12 10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
        </button>

        {{-- Starts HIDDEN and is placed by initRail(). It is position:fixed, so
             nothing in the flow can push it aside, and it was measured painting
             over the Overview's own data cards at every width below 1600 -- so
             the failing-open state (no JS, JS error) must be "no rail", never
             "a rail over the data". --}}
        <nav style="position: fixed; left: 26px; top: 50%; transform: translateY(-50%); z-index: 40; display: none; flex-direction: column; gap: 13px; align-items: center;">
            <div data-rail-dot="0" style="width: 9px; height: 9px; border-radius: 999px; background: #ff941f; transition: all .3s ease;"></div>
            <div data-rail-dot="1" style="width: 7px; height: 7px; border-radius: 999px; background: #c9ced3; transition: all .3s ease;"></div>
            <div data-rail-dot="2" style="width: 7px; height: 7px; border-radius: 999px; background: #c9ced3; transition: all .3s ease;"></div>
            <div data-rail-dot="3" style="width: 7px; height: 7px; border-radius: 999px; background: #c9ced3; transition: all .3s ease;"></div>
            <div data-rail-dot="4" style="width: 7px; height: 7px; border-radius: 999px; background: #c9ced3; transition: all .3s ease;"></div>
            <div data-rail-dot="5" style="width: 7px; height: 7px; border-radius: 999px; background: #c9ced3; transition: all .3s ease;"></div>
            <div data-rail-dot="6" style="width: 7px; height: 7px; border-radius: 999px; background: #c9ced3; transition: all .3s ease;"></div>
            <div data-rail-dot="7" style="width: 7px; height: 7px; border-radius: 999px; background: #c9ced3; transition: all .3s ease;"></div>
            <div data-rail-dot="8" style="width: 7px; height: 7px; border-radius: 999px; background: #c9ced3; transition: all .3s ease;"></div>
        </nav>

        {{-- ============ BEAT 01 — Welcome — navy ============ --}}
        <section data-beat="0" data-screen-label="01 Welcome" style="min-height: 100vh; display: flex; align-items: center; background: #12294a; padding: 96px 0;">
            <div style="width: min(1120px, 88vw); margin: 0 auto;">
                <div data-reveal style="font: 700 20px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #ff941f;">Welcome to the Databook digital services analysis</div>
                <h1 data-reveal data-delay="80" style="font: 700 clamp(34px, 4.2vw, 58px)/1.1 'Public Sans', sans-serif; letter-spacing: -0.015em; color: #ffffff; margin: 18px 0 0; max-width: 22ch;">We want to know: what does the city actually get when it buys technology?</h1>
                <p data-reveal data-delay="150" style="font: 400 17px/1.65 'Public Sans', sans-serif; color: #c8d6e8; margin: 20px 0 0; max-width: 64ch;">Databook collects dozens of datasets New York City already publishes — agencies, staff, job postings, construction projects, contracts, budgets and official notices — and links them together so they can be read as one. Every number comes from a published city source.</p>

                <div style="margin-top: 52px; display: flex; justify-content: center;">
                    <svg viewBox="0 0 900 300" style="width: min(100%, 900px); height: auto; overflow: visible;">
                        <g data-reveal data-delay="240">
                            <rect x="0" y="16" width="200" height="34" rx="4" fill="none" stroke="#5b7ea8" stroke-width="1.6"></rect>
                            <text x="16" y="38" style="font: 400 13px 'Roboto Mono', monospace; fill: #c8d6e8;">Checkbook NYC</text>
                            <rect x="0" y="62" width="200" height="34" rx="4" fill="none" stroke="#5b7ea8" stroke-width="1.6"></rect>
                            <text x="16" y="84" style="font: 400 13px 'Roboto Mono', monospace; fill: #c8d6e8;">City Record notices</text>
                            <rect x="0" y="108" width="200" height="34" rx="4" fill="none" stroke="#5b7ea8" stroke-width="1.6"></rect>
                            <text x="16" y="130" style="font: 400 13px 'Roboto Mono', monospace; fill: #c8d6e8;">NYC Jobs</text>
                            <rect x="0" y="154" width="200" height="34" rx="4" fill="none" stroke="#5b7ea8" stroke-width="1.6"></rect>
                            <text x="16" y="176" style="font: 400 13px 'Roboto Mono', monospace; fill: #c8d6e8;">Capital projects</text>
                            <rect x="0" y="200" width="200" height="34" rx="4" fill="none" stroke="#5b7ea8" stroke-width="1.6"></rect>
                            <text x="16" y="222" style="font: 400 13px 'Roboto Mono', monospace; fill: #c8d6e8;">Adopted budget</text>
                            <text x="16" y="264" style="font: 400 13px 'Roboto Mono', monospace; fill: #7f9dc2;">+ dozens more official datasets</text>
                        </g>
                        <g data-reveal data-delay="360">
                            <path data-draw data-delay="420" d="M204 33 C 280 33, 300 125, 366 125" fill="none" stroke="#5b7ea8" stroke-width="1.6"></path>
                            <path data-draw data-delay="460" d="M204 79 C 280 79, 300 125, 366 125" fill="none" stroke="#5b7ea8" stroke-width="1.6"></path>
                            <path data-draw data-delay="500" d="M204 125 H366" fill="none" stroke="#5b7ea8" stroke-width="1.6"></path>
                            <path data-draw data-delay="540" d="M204 171 C 280 171, 300 125, 366 125" fill="none" stroke="#5b7ea8" stroke-width="1.6"></path>
                            <path data-draw data-delay="580" d="M204 217 C 280 217, 300 125, 366 125" fill="none" stroke="#5b7ea8" stroke-width="1.6"></path>
                        </g>
                        <g data-reveal data-delay="560">
                            <rect x="366" y="34" width="190" height="52" rx="6" fill="#1c3a63" stroke="#5b7ea8" stroke-width="1.6"></rect>
                            <text x="382" y="58" style="font: 700 13.5px 'Public Sans', sans-serif; fill: #ffffff;">Data storage</text>
                            <text x="382" y="76" style="font: 400 11.5px 'Public Sans', sans-serif; fill: #9db6d2;">loaded, versioned, dated</text>
                            <rect x="366" y="99" width="190" height="52" rx="6" fill="#1c3a63" stroke="#ff941f" stroke-width="1.6"></rect>
                            <text x="382" y="123" style="font: 700 13.5px 'Public Sans', sans-serif; fill: #ffffff;">AI analysis</text>
                            <text x="382" y="141" style="font: 400 11.5px 'Public Sans', sans-serif; fill: #ffb056;">classify, match, suggest links</text>
                            <rect x="366" y="164" width="190" height="52" rx="6" fill="#1c3a63" stroke="#ff941f" stroke-width="1.6"></rect>
                            <text x="382" y="188" style="font: 700 13.5px 'Public Sans', sans-serif; fill: #ffffff;">Human analysis</text>
                            <text x="382" y="206" style="font: 400 11.5px 'Public Sans', sans-serif; fill: #ffb056;">review, confirm, correct</text>
                            <path data-draw data-delay="620" d="M461 88 V97" fill="none" stroke="#5b7ea8" stroke-width="1.6"></path>
                            <path data-draw data-delay="650" d="M461 153 V162" fill="none" stroke="#5b7ea8" stroke-width="1.6"></path>
                        </g>
                        <g data-reveal data-delay="660">
                            <path data-draw data-delay="700" d="M560 60 C 578 60, 578 125, 598 125 M560 125 H598 M560 190 C 578 190, 578 125, 598 125" fill="none" stroke="#ff941f" stroke-width="1.6"></path>
                            <path d="M590 118 l9 7 l-9 7" fill="none" stroke="#ff941f" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>
                        </g>
                        <g data-reveal data-delay="740">
                            <rect x="608" y="30" width="292" height="190" rx="8" fill="#ffffff"></rect>
                            <text x="630" y="62" style="font: 700 12px 'Public Sans', sans-serif; letter-spacing: .06em; fill: #71767a;">ONE PLACE</text>
                            <text x="630" y="92" style="font: 700 17px 'Public Sans', sans-serif; fill: #162e51;">Separate datasets become</text>
                            <text x="630" y="114" style="font: 700 17px 'Public Sans', sans-serif; fill: #162e51;">one navigable picture.</text>
                            <path d="M630 132 H878" stroke="#dfe1e2" stroke-width="1.4"></path>
                            <path d="M630 206 H736" stroke="#dfe1e2" stroke-width="1.2"></path>
                            <rect x="630" y="188" width="12" height="18" rx="1.5" fill="#2e5c9a"><animate attributeName="height" from="0" to="18" dur="0.7s" begin="1.1s" fill="freeze"></animate><animate attributeName="y" from="206" to="188" dur="0.7s" begin="1.1s" fill="freeze"></animate></rect>
                            <rect x="651" y="180" width="12" height="26" rx="1.5" fill="#2e5c9a"><animate attributeName="height" from="0" to="26" dur="0.7s" begin="1.2s" fill="freeze"></animate><animate attributeName="y" from="206" to="180" dur="0.7s" begin="1.2s" fill="freeze"></animate></rect>
                            <rect x="672" y="172" width="12" height="34" rx="1.5" fill="#2e5c9a"><animate attributeName="height" from="0" to="34" dur="0.7s" begin="1.3s" fill="freeze"></animate><animate attributeName="y" from="206" to="172" dur="0.7s" begin="1.3s" fill="freeze"></animate></rect>
                            <rect x="693" y="178" width="12" height="28" rx="1.5" fill="#2e5c9a"><animate attributeName="height" from="0" to="28" dur="0.7s" begin="1.4s" fill="freeze"></animate><animate attributeName="y" from="206" to="178" dur="0.7s" begin="1.4s" fill="freeze"></animate></rect>
                            <rect x="714" y="160" width="12" height="46" rx="1.5" fill="#ff941f"><animate attributeName="height" from="0" to="46" dur="0.7s" begin="1.5s" fill="freeze"></animate><animate attributeName="y" from="206" to="160" dur="0.7s" begin="1.5s" fill="freeze"></animate></rect>
                            <text x="630" y="150" style="font: 700 10.5px 'Public Sans', sans-serif; letter-spacing: .06em; fill: #a9aeb1;">SPEND BY YEAR</text>
                            <path d="M748 142 V208" stroke="#dfe1e2" stroke-width="1.2"></path>
                            <text x="768" y="150" style="font: 700 10.5px 'Public Sans', sans-serif; letter-spacing: .06em; fill: #a9aeb1;">TRACKED NOW</text>
                            <text x="768" y="176" style="font: 700 19px 'Roboto Mono', monospace; fill: #162e51;">{{ $sbB($sbTotal) }}<animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="1.5s" fill="freeze"></animate></text>
                            <text x="768" y="200" style="font: 400 12.5px 'Public Sans', sans-serif; fill: #71767a;">{{ number_format($sbCount) }} contracts<animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="1.7s" fill="freeze"></animate></text>
                        </g>
                    </svg>
                </div>
            </div>
        </section>

        {{-- ============ BEAT 02 — Introduction — gray ============ --}}
        <section data-beat="1" data-screen-label="02 Introduction" style="min-height: 100vh; display: flex; align-items: center; background: #f9fafb; padding: 96px 0;">
            <div style="width: min(1080px, 86vw); margin: 0 auto;">
                <div data-reveal style="font: 700 20px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #ff941f;">Digital services analysis · an introduction</div>
                <h1 data-reveal data-delay="80" style="font: 700 clamp(34px, 4.4vw, 60px)/1.1 'Public Sans', sans-serif; letter-spacing: -0.015em; color: #162e51; margin: 18px 0 0; max-width: 18ch;">Since 2018, the city's technology spending has grown sharply.</h1>
                @php
                    // ⚠⚠ THESE NINE BARS USED TO BE TYPED, AND THEY WERE COMMITTED
                    // MONEY PLUS MASTER-AGREEMENT CEILINGS ADDED TOGETHER. Measured
                    // 2026-09-14 against the live payload, all nine matched
                    // `committed + ceiling` TO THE DOLLAR and not one matched
                    // committed alone: 2023 read $2.42B against $1.51B committed,
                    // the difference being $913M of ceiling.
                    //
                    // That is #294's defect — the one the calendar was split in two
                    // to remove, and the one the Overview's own by-start-year chart
                    // was REBUILT to remove — reproduced in hand-typed text directly
                    // above that rebuilt chart. A ceiling bar makes an undrawn
                    // agreement look like the year's largest spend.
                    //
                    // ⭐ AND THE BLEND MOVED THE `PEAK` BADGE ONTO THE WRONG YEAR.
                    // It was typed onto 2023, which leads only once ceilings are
                    // added; by committed money the peak is 2022 ($1.74B vs $1.51B).
                    // The badge is derived now, so it cannot disagree with the bars.
                    //
                    // The ceiling is NOT dropped — it is stated beneath, never added,
                    // which is the same treatment `award_by_start_year` already gives
                    // it in the payload and the chart below gives it in the tooltip.
                    $abyRows = collect($awardByStartYear['years'] ?? [])
                        ->filter(function ($r) { return (int) ($r['year'] ?? 0) >= 2018; })
                        ->map(function ($r) {
                            $committed = (float) ($r['committed_active'] ?? 0) + (float) ($r['committed_ended'] ?? 0);
                            return [
                                'year'      => (string) ($r['year'] ?? ''),
                                'committed' => $committed,
                                'ceiling'   => (float) ($r['ceiling'] ?? 0),
                            ];
                        })
                        ->values();
                    $abyMax  = $abyRows->max('committed') ?: 0;
                    $abyPeak = $abyMax > 0 ? ($abyRows->firstWhere('committed', $abyMax)['year'] ?? null) : null;
                    $abyCeil = $abyRows->sum('ceiling');
                @endphp
                <p data-reveal data-delay="160" style="font: 400 17px/1.65 'Public Sans', sans-serif; color: #3d4551; margin: 20px 0 0; max-width: 62ch;">Each bar is the money <strong style="color: #162e51;">committed</strong> under technology contracts that started in that year. Most are evergreen or renewable, so the city is billed for them annually.@if ($abyCeil > 0) A further <strong style="color: #162e51;">{{ $sbB($abyCeil, 2) }}</strong> sits in master-agreement ceilings over the same years — headroom that may be bought against, not money committed, so it is not in these bars.@endif</p>

                @if ($abyRows->isNotEmpty())
                <div data-sb-bars style="display: flex; align-items: flex-end; gap: clamp(8px, 1.6vw, 22px); height: 320px; margin: 56px 0 0; border-bottom: 1px solid #dfe1e2;">
                    @foreach ($abyRows as $i => $r)
                        @php
                            // 260px is the tallest bar the typed version drew, kept so
                            // the beat's height is unchanged; the RATIO is measured.
                            $h = $abyMax > 0 ? max(4, (int) round(260 * $r['committed'] / $abyMax)) : 4;
                            $d = 200 + $i * 60;
                        @endphp
                        <div data-sb-bar style="flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 8px;">
                            @if ($r['year'] === $abyPeak)
                                <div data-reveal data-delay="{{ $d }}" style="font: 700 11px 'Public Sans', sans-serif; letter-spacing: .06em; color: #a15c00; background: #ffefd9; border-radius: 999px; padding: 4px 9px;">PEAK</div>
                            @endif
                            <div data-reveal data-delay="{{ $d }}" style="font: 700 13px/1 'Roboto Mono', monospace; color: #162e51;">{{ $sbB($r['committed'], 2) }}</div>
                            <div data-grow="{{ $h }}" data-delay="{{ $d }}" style="width: 100%; max-width: 64px; background: linear-gradient(180deg, #2e5c9a, #162e51); border-radius: 3px 3px 0 0;"></div>
                        </div>
                    @endforeach
                </div>
                <div style="display: flex; gap: clamp(8px, 1.6vw, 22px); margin-top: 12px;">
                    @foreach ($abyRows as $r)
                        <div style="flex: 1; text-align: center; font: 400 13px/1 'Roboto Mono', monospace; color: #71767a;">{{ $r['year'] }}</div>
                    @endforeach
                </div>
                @endif
            </div>
        </section>

        {{-- ============ BEAT 03 — What technology means — white ============ --}}
        <section data-beat="2" data-screen-label="03 What technology means" style="min-height: 100vh; display: flex; align-items: center; background: #ffffff; padding: 110px 0;">
            <div style="width: min(1140px, 88vw); margin: 0 auto;">
                <div data-reveal style="font: 700 20px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #ff941f;">BUT WHAT EXACTLY IS 'TECHNOLOGY'?</div>
                <h2 data-reveal data-delay="80" style="font: 700 clamp(30px, 3.6vw, 48px)/1.15 'Public Sans', sans-serif; letter-spacing: -0.012em; color: #162e51; margin: 16px 0 0; max-width: 24ch;">Mostly licenses, people, wires, and machines.</h2>
                <p data-reveal data-delay="140" style="font: 400 17px/1.65 'Public Sans', sans-serif; color: #3d4551; margin: 18px 0 0; max-width: 66ch;">Databook has found <b>{{ number_format($sbCount) }}</b> technology contracts worth <b>{{ $sbB($sbTotal) }}</b> in total. Sorted by what the money actually buys, four kinds account for most of it.</p>

                <div style="margin-top: 40px; display: flex; justify-content: center;">
                    <svg viewBox="0 0 700 470" style="width: min(100%, 820px); height: auto; overflow: visible;">
                        <ellipse cx="200" cy="432" rx="180" ry="15" fill="#eef1f5"></ellipse>
                        <g data-reveal data-delay="160">
                            <path d="M40 333 L300 333 L300 420 L40 420 Z" fill="#d3e0ee" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path d="M40 333 L300 333 L340 311 L80 311 Z" fill="#b6cae2" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path d="M300 333 L340 311 L340 398 L300 420 Z" fill="#9db6d2" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path data-draw data-delay="300" d="M344 370 L392 370" fill="none" stroke="#a9aeb1" stroke-width="1.5" stroke-linecap="round"></path>
                            <text x="400" y="368" style="font: 700 15px 'Public Sans', sans-serif; fill: #162e51;">{{ $sbSegs[0]['segment'] ?? '' }}</text>
                            <text x="400" y="388" style="font: 400 13px 'Roboto Mono', monospace; fill: #71767a;">{{ $sbSegLine($sbSegs[0] ?? null) }}</text>
                        </g>
                        <g data-reveal data-delay="240">
                            <path d="M40 249 L300 249 L300 333 L40 333 Z" fill="#dee7f2" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path d="M40 249 L300 249 L340 227 L80 227 Z" fill="#c5d5e8" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path d="M300 249 L340 227 L340 311 L300 333 Z" fill="#adc3da" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path data-draw data-delay="380" d="M344 286 L392 286" fill="none" stroke="#a9aeb1" stroke-width="1.5" stroke-linecap="round"></path>
                            <text x="400" y="284" style="font: 700 15px 'Public Sans', sans-serif; fill: #162e51;">{{ $sbSegs[1]['segment'] ?? '' }}</text>
                            <text x="400" y="304" style="font: 400 13px 'Roboto Mono', monospace; fill: #71767a;">{{ $sbSegLine($sbSegs[1] ?? null) }}</text>
                        </g>
                        <g data-reveal data-delay="320">
                            <path d="M40 192 L300 192 L300 249 L40 249 Z" fill="#e9eff6" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path d="M40 192 L300 192 L340 170 L80 170 Z" fill="#d4e0ee" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path d="M300 192 L340 170 L340 227 L300 249 Z" fill="#bccbe0" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path data-draw data-delay="460" d="M344 216 L392 216" fill="none" stroke="#a9aeb1" stroke-width="1.5" stroke-linecap="round"></path>
                            <text x="400" y="214" style="font: 700 15px 'Public Sans', sans-serif; fill: #162e51;">{{ $sbSegs[2]['segment'] ?? '' }}</text>
                            <text x="400" y="234" style="font: 400 13px 'Roboto Mono', monospace; fill: #71767a;">{{ $sbSegLine($sbSegs[2] ?? null) }}</text>
                        </g>
                        <g data-reveal data-delay="400">
                            <path d="M40 138 L300 138 L300 192 L40 192 Z" fill="#f3f6fa" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path d="M40 138 L300 138 L340 116 L80 116 Z" fill="#e2eaf3" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path d="M300 138 L340 116 L340 170 L300 192 Z" fill="#cbd7e6" stroke="#162e51" stroke-width="2" stroke-linejoin="round"></path>
                            <path data-draw data-delay="540" d="M344 162 L392 162" fill="none" stroke="#a9aeb1" stroke-width="1.5" stroke-linecap="round"></path>
                            <text x="400" y="160" style="font: 700 15px 'Public Sans', sans-serif; fill: #162e51;">{{ $sbSegs[3]['segment'] ?? '' }}</text>
                            <text x="400" y="180" style="font: 400 13px 'Roboto Mono', monospace; fill: #71767a;">{{ $sbSegLine($sbSegs[3] ?? null) }}</text>
                        </g>
                        <g data-reveal data-delay="480">
                            <path d="M40 102 L300 102 L300 138 L40 138 Z" fill="#f7f8f9" stroke="#a9aeb1" stroke-width="2" stroke-linejoin="round"></path>
                            <path d="M40 102 L300 102 L340 80 L80 80 Z" fill="#eceff2" stroke="#a9aeb1" stroke-width="2" stroke-linejoin="round"></path>
                            <path d="M300 102 L340 80 L340 116 L300 138 Z" fill="#dcdfe3" stroke="#a9aeb1" stroke-width="2" stroke-linejoin="round"></path>
                            <path data-draw data-delay="620" d="M344 118 L392 118" fill="none" stroke="#a9aeb1" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="4 4"></path>
                            <text x="400" y="116" style="font: 700 15px 'Public Sans', sans-serif; fill: #71767a;">Everything else</text>
                            <text x="400" y="136" style="font: 400 13px 'Roboto Mono', monospace; fill: #a9aeb1;">{{ $sbB($sbRest) }} across {{ $sbRestN }} smaller segments</text>
                        </g>
                        <g data-reveal data-delay="560">
                            <path data-draw data-delay="660" d="M26 86 h-12 v334 h12" fill="none" stroke="#ff941f" stroke-width="2" stroke-linecap="round"></path>
                            <text x="8" y="253" text-anchor="middle" transform="rotate(-90 8 253)" style="font: 700 14px 'Public Sans', sans-serif; letter-spacing: .04em; fill: #a15c00;">{{ $sbB($sbTotal) }} · {{ number_format($sbCount) }} contracts</text>
                        </g>
                    </svg>
                </div>
            </div>
        </section>

        {{-- ============ BEAT 04 — What the record omits — navy ============ --}}
        <section data-beat="3" data-screen-label="04 What the record omits" style="min-height: 100vh; display: flex; align-items: center; background: #12294a; padding: 110px 0;">
            <div style="width: min(1080px, 86vw); margin: 0 auto;">
                <div data-reveal style="font: 700 20px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #ff8a7a;">What the public record does not say</div>
                <h2 data-reveal data-delay="80" style="font: 700 clamp(30px, 3.6vw, 48px)/1.15 'Public Sans', sans-serif; letter-spacing: -0.012em; color: #ffffff; margin: 16px 0 0; max-width: 24ch;">The data NYC publishes on its technology spending is incomplete.</h2>

                <div style="display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 360px); gap: 56px; align-items: center; margin-top: 44px;">
                    <div style="display: flex; flex-direction: column; gap: 28px;">
                        <div data-reveal data-delay="140" style="padding-left: 22px; border-left: 2px solid rgba(255,255,255,.25);">
                            <div style="font: 700 17px/1.3 'Public Sans', sans-serif; color: #ffffff;">Contracts records only show totals</div>
                            <p style="font: 400 15px/1.65 'Public Sans', sans-serif; color: #c8d6e8; margin: 6px 0 0;">Contracts don't specify how many seats, licences, or devices the money bought. A unit price cannot be calculated, limiting our ability to compare with another agency's bill or another product's price. If you can't compare, you can't negotiate.</p>
                        </div>
                        <div data-reveal data-delay="220" style="padding-left: 22px; border-left: 2px solid rgba(255,255,255,.25);">
                            <div style="font: 700 17px/1.3 'Public Sans', sans-serif; color: #ffffff;">The City's own product codes skip software</div>
                            <p style="font: 400 15px/1.65 'Public Sans', sans-serif; color: #c8d6e8; margin: 6px 0 0;">The city has a standard list of codes for describing what it buys in the public record. Those codes are only attached to about a quarter of all contracts. To make things worse, a code is only recorded when a purchase goes out for competitive bid. Since software licenses rarely go out for bid, they have no code attached, making them exceedingly difficult to track.</p>
                        </div>
                        <div data-reveal data-delay="300" style="padding-left: 22px; border-left: 2px solid #ff8a7a;">
                            <div style="font: 700 17px/1.3 'Public Sans', sans-serif; color: #ffffff;">Records don't exist until registration</div>
                            <p style="font: 400 15px/1.65 'Public Sans', sans-serif; color: #c8d6e8; margin: 6px 0 0;">The city has a procurement system of record called PASSPort, where every agency contract is solicited, awarded and registered. It gives a contract an ID number once it is registered, which is the last approval step. Every total here is built from those IDs, so contracts still working through approval appear nowhere — including citywide purchasing agreements larger than some of the totals themselves.</p>
                        </div>
                    </div>

                    <svg viewBox="0 0 400 510" style="width: 100%; height: auto; overflow: visible;">
                        <path data-reveal d="M30 20 H320 L370 70 V480 H30 Z" fill="#ffffff" stroke="#8fb4e0" stroke-width="2.2" stroke-linejoin="round"></path>
                        <path data-reveal d="M320 20 L370 70 H320 Z" fill="#dbe4f0" stroke="#8fb4e0" stroke-width="2.2" stroke-linejoin="round"></path>
                        <text x="52" y="58" style="font: 700 12px 'Public Sans', sans-serif; letter-spacing: .06em; fill: #162e51;">CONTRACT RECORD</text>
                        <path data-draw data-delay="200" d="M52 78 H348" fill="none" stroke="#dfe1e2" stroke-width="1.6"></path>
                        <g data-reveal data-delay="220">
                            <text x="52" y="115" style="font: 400 13px 'Public Sans', sans-serif; fill: #3d4551;">Vendor</text>
                            <rect x="230" y="105" width="118" height="11" rx="2" fill="#35608F"></rect>
                            <text x="52" y="155" style="font: 400 13px 'Public Sans', sans-serif; fill: #3d4551;">Agency</text>
                            <rect x="230" y="145" width="98" height="11" rx="2" fill="#35608F"></rect>
                            <text x="52" y="195" style="font: 400 13px 'Public Sans', sans-serif; fill: #3d4551;">Award amount</text>
                            <rect x="230" y="185" width="76" height="11" rx="2" fill="#35608F"></rect>
                            <text x="52" y="235" style="font: 400 13px 'Public Sans', sans-serif; fill: #3d4551;">Start and end dates</text>
                            <rect x="230" y="225" width="106" height="11" rx="2" fill="#35608F"></rect>
                            <text x="52" y="275" style="font: 400 13px 'Public Sans', sans-serif; fill: #3d4551;">Recorded purpose</text>
                            <rect x="230" y="265" width="118" height="11" rx="2" fill="#35608F"></rect>
                        </g>
                        <path data-draw data-delay="380" d="M52 310 H348" fill="none" stroke="#dfe1e2" stroke-width="1.6" stroke-dasharray="4 4"></path>
                        <text data-reveal data-delay="400" x="52" y="336" style="font: 700 11px 'Public Sans', sans-serif; letter-spacing: .06em; fill: #d9524a;">NOT IN THE RECORD</text>
                        <g data-reveal data-delay="440">
                            <text x="52" y="378" style="font: 400 13px 'Public Sans', sans-serif; fill: #a9aeb1;">Seats or units bought</text>
                            <rect x="230" y="368" width="118" height="11" rx="2" fill="none" stroke="#e8998f" stroke-width="1.4" stroke-dasharray="4 3"></rect>
                            <text x="52" y="418" style="font: 400 13px 'Public Sans', sans-serif; fill: #a9aeb1;">Product code (what was bought)</text>
                            <rect x="230" y="408" width="118" height="11" rx="2" fill="none" stroke="#e8998f" stroke-width="1.4" stroke-dasharray="4 3"></rect>
                            <text x="52" y="458" style="font: 400 13px 'Public Sans', sans-serif; fill: #a9aeb1;">What was actually spent</text>
                            <rect x="230" y="448" width="118" height="11" rx="2" fill="none" stroke="#e8998f" stroke-width="1.4" stroke-dasharray="4 3"></rect>
                        </g>
                    </svg>
                </div>
            </div>
        </section>

        {{-- ============ BEAT 05 — The same job, many times — white ============ --}}
        <section data-beat="4" data-screen-label="05 The same job, many times" style="min-height: 100vh; display: flex; align-items: center; background: #ffffff; padding: 110px 0;">
            <div style="width: min(1080px, 86vw); margin: 0 auto;">
                <div data-reveal style="font: 700 20px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #ff941f;">The same job, bought many times</div>
                <h2 data-reveal data-delay="80" style="font: 700 clamp(30px, 3.6vw, 48px)/1.15 'Public Sans', sans-serif; letter-spacing: -0.012em; color: #162e51; margin: 16px 0 0; max-width: 24ch;">Dozens of agencies license the same kinds of software, each on its own contract.</h2>
                <p data-reveal data-delay="140" style="font: 400 17px/1.65 'Public Sans', sans-serif; color: #3d4551; margin: 18px 0 0; max-width: 66ch;">{!! $sbLicLine !!} Because this data is not easily searchable and vendor products are purchased per-seat, each agency is buying separately for the same purpose, each negotiating its own price.</p>

                <svg viewBox="0 0 1020 330" style="width: 100%; height: auto; margin-top: 36px; overflow: visible;">
                    <line x1="0" y1="250" x2="1020" y2="250" stroke="#dfe1e2" stroke-width="1.5"></line>
                    <g data-reveal data-delay="140">
                        <path d="M20 250 V152 L80 112 L140 152 V250 Z" fill="#eef2f7" stroke="#162e51" stroke-width="2.2" stroke-linejoin="round"></path>
                        <rect x="42" y="172" width="22" height="20" fill="#ffffff" stroke="#162e51" stroke-width="1.8"></rect>
                        <rect x="96" y="172" width="22" height="20" fill="#ffffff" stroke="#162e51" stroke-width="1.8"></rect>
                        <rect x="65" y="212" width="30" height="38" fill="#162e51"></rect>
                        <text x="80" y="278" text-anchor="middle" style="font: 400 13px 'Public Sans', sans-serif; fill: #71767a;">Agency one</text>
                    </g>
                    <g data-reveal data-delay="230">
                        <path d="M180 250 V152 L240 112 L300 152 V250 Z" fill="#eef2f7" stroke="#162e51" stroke-width="2.2" stroke-linejoin="round"></path>
                        <rect x="202" y="172" width="22" height="20" fill="#ffffff" stroke="#162e51" stroke-width="1.8"></rect>
                        <rect x="256" y="172" width="22" height="20" fill="#ffffff" stroke="#162e51" stroke-width="1.8"></rect>
                        <rect x="225" y="212" width="30" height="38" fill="#162e51"></rect>
                        <text x="240" y="278" text-anchor="middle" style="font: 400 13px 'Public Sans', sans-serif; fill: #71767a;">Agency two</text>
                    </g>
                    <g data-reveal data-delay="320">
                        <path d="M340 250 V152 L400 112 L460 152 V250 Z" fill="#eef2f7" stroke="#162e51" stroke-width="2.2" stroke-linejoin="round"></path>
                        <rect x="362" y="172" width="22" height="20" fill="#ffffff" stroke="#162e51" stroke-width="1.8"></rect>
                        <rect x="416" y="172" width="22" height="20" fill="#ffffff" stroke="#162e51" stroke-width="1.8"></rect>
                        <rect x="385" y="212" width="30" height="38" fill="#162e51"></rect>
                        <text x="400" y="278" text-anchor="middle" style="font: 400 13px 'Public Sans', sans-serif; fill: #71767a;">Agency three</text>
                    </g>
                    <g data-reveal data-delay="410">
                        <path d="M500 250 V152 L560 112 L620 152 V250 Z" fill="#eef2f7" stroke="#162e51" stroke-width="2.2" stroke-linejoin="round"></path>
                        <rect x="522" y="172" width="22" height="20" fill="#ffffff" stroke="#162e51" stroke-width="1.8"></rect>
                        <rect x="576" y="172" width="22" height="20" fill="#ffffff" stroke="#162e51" stroke-width="1.8"></rect>
                        <rect x="545" y="212" width="30" height="38" fill="#162e51"></rect>
                        <text x="560" y="278" text-anchor="middle" style="font: 400 13px 'Public Sans', sans-serif; fill: #71767a;">Agency four</text>
                    </g>
                    <g data-reveal data-delay="500">
                        <path d="M660 250 V152 L720 112 L780 152 V250 Z" fill="#eef2f7" stroke="#162e51" stroke-width="2.2" stroke-linejoin="round"></path>
                        <rect x="682" y="172" width="22" height="20" fill="#ffffff" stroke="#162e51" stroke-width="1.8"></rect>
                        <rect x="736" y="172" width="22" height="20" fill="#ffffff" stroke="#162e51" stroke-width="1.8"></rect>
                        <rect x="705" y="212" width="30" height="38" fill="#162e51"></rect>
                        <text x="720" y="278" text-anchor="middle" style="font: 400 13px 'Public Sans', sans-serif; fill: #71767a;">Agency five</text>
                    </g>
                    <g data-reveal data-delay="590">
                        <path d="M840 250 V152 L900 112 L960 152 V250 Z" fill="none" stroke="#a9aeb1" stroke-width="2" stroke-dasharray="6 5" stroke-linejoin="round"></path>
                        <text x="900" y="196" text-anchor="middle" style="font: 700 17px 'Roboto Mono', monospace; fill: #71767a;">…</text>
                        <text x="900" y="278" text-anchor="middle" style="font: 400 13px 'Public Sans', sans-serif; fill: #71767a;">and so on</text>
                    </g>
                    <g data-reveal data-delay="640">
                        <path data-draw data-delay="700" d="M20 302 V314 H780 V302" fill="none" stroke="#ff941f" stroke-width="2" stroke-linecap="round"></path>
                        <text x="400" y="332" text-anchor="middle" style="font: 700 14px 'Public Sans', sans-serif; fill: #a15c00;">five different products, one job</text>
                    </g>
                </svg>
            </div>
        </section>

        {{-- ============ BEAT 06 — What is a master agreement? — navy ============
             Defines the term before beat 07 makes an argument about it, and
             before red flag #3 depends on both. Deliberately structural only
             (parent contract, child orders, why cities use them) — the
             oversight consequence is beat 07's job, not this one's, so it
             isn't repeated here. --}}
        <section data-beat="5" data-screen-label="06 What is a master agreement?" style="min-height: 100vh; display: flex; align-items: center; background: #12294a; padding: 110px 0;">
            <div style="width: min(1080px, 86vw); margin: 0 auto;">
                <div data-reveal style="font: 700 20px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #ff941f;">How master agreements work</div>
                <h2 data-reveal data-delay="80" style="font: 700 clamp(30px, 3.6vw, 48px)/1.15 'Public Sans', sans-serif; letter-spacing: -0.012em; color: #ffffff; margin: 16px 0 0; max-width: 22ch;">One contract, many orders.</h2>
                <p data-reveal data-delay="140" style="font: 400 17px/1.65 'Public Sans', sans-serif; color: #c8d6e8; margin: 20px 0 0; max-width: 74ch;">A master agreement is a parent contract the City signs with a vendor to lock in prices and terms in advance. Agencies then draw against it with their own smaller orders as needs come up, skipping a new bidding process each time &mdash; which is why cities use them for supplies, repairs, and other recurring needs where the exact quantity or timing isn't known ahead of time.</p>

                <svg viewBox="0 0 1020 260" style="width: 100%; height: auto; margin-top: 40px; overflow: visible;">
                    <g data-reveal data-delay="180">
                        <rect x="360" y="10" width="300" height="66" rx="8" fill="#1f3a63" stroke="#8fb4e0" stroke-width="2"></rect>
                        <text x="510" y="34" text-anchor="middle" style="font: 700 11px 'Public Sans', sans-serif; letter-spacing: .06em; fill: #8fb4e0;">MASTER AGREEMENT</text>
                        <text x="510" y="60" text-anchor="middle" style="font: 700 16px 'Public Sans', sans-serif; fill: #ffffff;">One vendor, prices locked in</text>
                    </g>
                    <g data-reveal data-delay="280">
                        <path data-draw data-delay="320" d="M510 76 V110 M140 110 H860 M140 110 V128 M380 110 V128 M620 110 V128 M860 110 V128" fill="none" stroke="#5b7ea8" stroke-width="1.8" stroke-linecap="round"></path>
                    </g>
                    <g data-reveal data-delay="380">
                        <rect x="60" y="128" width="160" height="88" rx="6" fill="#ffffff" stroke="#8fb4e0" stroke-width="1.8"></rect>
                        <text x="140" y="156" text-anchor="middle" style="font: 700 12px 'Public Sans', sans-serif; letter-spacing: .05em; fill: #71767a;">ORDER #1</text>
                        <text x="140" y="180" text-anchor="middle" style="font: 700 15px 'Public Sans', sans-serif; fill: #162e51;">Agency A</text>
                        <text x="140" y="202" text-anchor="middle" style="font: 400 11px 'Roboto Mono', monospace; fill: #162e51;">Contract ID: 4521873</text>
                    </g>
                    <g data-reveal data-delay="440">
                        <rect x="300" y="128" width="160" height="88" rx="6" fill="#ffffff" stroke="#8fb4e0" stroke-width="1.8"></rect>
                        <text x="380" y="156" text-anchor="middle" style="font: 700 12px 'Public Sans', sans-serif; letter-spacing: .05em; fill: #71767a;">ORDER #2</text>
                        <text x="380" y="180" text-anchor="middle" style="font: 700 15px 'Public Sans', sans-serif; fill: #162e51;">Agency B</text>
                        <text x="380" y="202" text-anchor="middle" style="font: 400 11px 'Roboto Mono', monospace; fill: #162e51;">Contract ID: 5098234</text>
                    </g>
                    <g data-reveal data-delay="500">
                        <rect x="540" y="128" width="160" height="88" rx="6" fill="#ffffff" stroke="#8fb4e0" stroke-width="1.8"></rect>
                        <text x="620" y="156" text-anchor="middle" style="font: 700 12px 'Public Sans', sans-serif; letter-spacing: .05em; fill: #71767a;">ORDER #3</text>
                        <text x="620" y="180" text-anchor="middle" style="font: 700 15px 'Public Sans', sans-serif; fill: #162e51;">Agency C</text>
                        <text x="620" y="202" text-anchor="middle" style="font: 400 11px 'Roboto Mono', monospace; fill: #162e51;">Contract ID: 4867012</text>
                    </g>
                    <g data-reveal data-delay="560">
                        <rect x="780" y="128" width="160" height="88" rx="6" fill="none" stroke="#5b7ea8" stroke-width="1.8" stroke-dasharray="6 5"></rect>
                        <text x="860" y="178" text-anchor="middle" style="font: 700 17px 'Roboto Mono', monospace; fill: #8fb4e0;">&hellip;</text>
                        <text x="860" y="202" text-anchor="middle" style="font: 400 13px 'Public Sans', sans-serif; fill: #c8d6e8;">and so on</text>
                    </g>
                    <g data-reveal data-delay="640">
                        <text x="510" y="248" text-anchor="middle" style="font: 700 14px 'Public Sans', sans-serif; fill: #ff941f;">Every order is its own contract, filed separately from the agreement above it.</text>
                    </g>
                </svg>
            </div>
        </section>

        {{-- ============ BEAT 07 — Ceilings, not purchases — navy ============
             The consequence of the structure beat 06 just defined. Uses the
             same worked example as the Master Agreements page (docs: 186
             masters / $3,337.4M ceiling; Dell Marketing $1.86B / 29,822 ids
             vs the $573.8M Microsoft ELA's own $0), so this beat cannot
             disagree with the page it is teaching a reader to read. --}}
        <section data-beat="6" data-screen-label="07 Ceilings, not purchases" style="min-height: 100vh; display: flex; align-items: center; background: #12294a; padding: 110px 0;">
            <div style="width: min(1080px, 86vw); margin: 0 auto;">
                <div data-reveal style="font: 700 20px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #ff941f;">This Creates Visibility Problems</div>
                <h2 data-reveal data-delay="80" style="font: 700 clamp(30px, 3.6vw, 48px)/1.15 'Public Sans', sans-serif; letter-spacing: -0.012em; color: #ffffff; margin: 16px 0 0; max-width: 26ch;">Some of the biggest price tags are ceilings, not purchases.</h2>
                <p data-reveal data-delay="140" style="font: 400 17px/1.65 'Public Sans', sans-serif; color: #c8d6e8; margin: 20px 0 0; max-width: 74ch;">New York City holds {{ number_format($sbMasters) }} master agreements worth a combined <strong style="color: #ffffff;">{{ $sbB($sbMaCeiling) }}</strong> in buying power &mdash; the most that may be bought under them, not what has been spent. Agencies draw against a master through their own purchase orders, which carry their own contract IDs, so the master's own record can show nothing while the buying happens somewhere else entirely.</p>

                <svg viewBox="0 0 1020 240" style="width: 100%; height: auto; margin-top: 40px; overflow: visible;">
                    <g data-reveal data-delay="180">
                        <rect x="10" y="16" width="380" height="200" rx="8" fill="none" stroke="#5b7ea8" stroke-width="2" stroke-dasharray="7 6"></rect>
                        <text x="34" y="48" style="font: 700 12px 'Public Sans', sans-serif; letter-spacing: .06em; fill: #8fb4e0;">MASTER AGREEMENT</text>
                        <text x="34" y="82" style="font: 700 21px 'Public Sans', sans-serif; fill: #ffffff;">Citywide Microsoft ELA</text>
                        <text x="34" y="112" style="font: 700 16px 'Roboto Mono', monospace; fill: #ffffff;">$573.8M ceiling</text>
                        <path d="M34 132 H366" stroke="#3a5a83" stroke-width="1.5"></path>
                        <text x="34" y="176" style="font: 700 32px 'Roboto Mono', monospace; fill: #e8998f;">$0</text>
                        <text x="34" y="200" style="font: 400 13px 'Public Sans', sans-serif; fill: #c8d6e8;">paid under this agreement's own id</text>
                    </g>
                    <g data-reveal data-delay="340">
                        <path data-draw data-delay="400" d="M410 116 H598" fill="none" stroke="#ff941f" stroke-width="2.4" stroke-linecap="round"></path>
                        <path d="M582 102 L600 116 L582 130" fill="none" stroke="#ff941f" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"></path>
                    </g>
                    <g data-reveal data-delay="460">
                        <rect x="630" y="16" width="380" height="200" rx="8" fill="#ffffff" stroke="#8fb4e0" stroke-width="2"></rect>
                        <text x="654" y="48" style="font: 700 12px 'Public Sans', sans-serif; letter-spacing: .06em; fill: #71767a;">WHERE THE MONEY ACTUALLY IS</text>
                        <text x="654" y="82" style="font: 700 21px 'Public Sans', sans-serif; fill: #162e51;">Dell Marketing L.P.</text>
                        <text x="654" y="112" style="font: 700 16px 'Roboto Mono', monospace; fill: #162e51;">$1.86B paid</text>
                        <path d="M654 132 H986" stroke="#dfe1e2" stroke-width="1.5"></path>
                        <text x="654" y="160" style="font: 400 14px 'Public Sans', sans-serif; fill: #71767a;">Across 29,822 separate contract IDs &mdash;</text>
                        <text x="654" y="182" style="font: 400 14px 'Public Sans', sans-serif; fill: #71767a;">each its own purchase order, none of</text>
                        <text x="654" y="204" style="font: 400 14px 'Public Sans', sans-serif; fill: #71767a;">them the master agreement itself.</text>
                    </g>
                </svg>

                <p data-reveal data-delay="620" style="font: 700 15px/1.6 'Public Sans', sans-serif; color: #ffffff; margin: 32px 0 0; max-width: 66ch; padding-left: 18px; border-left: 2px solid #d9524a;">{{ $sbMaLine }}</p>
            </div>
        </section>

        {{-- ============ BEAT 08 — The Red Flags — white ============
             Three findings this analysis surfaces, each a short case made
             elsewhere in the storyboard: #1 restates the closed-software cost
             beat, #2 restates "the same job, many times", #3 depends on the
             two master-agreement beats directly above. Same #ffffff
             background and dark text as beat 03's "What technology means",
             on purpose -- red is still the accent so the warning reads as its
             own register, but the background matches an existing light beat
             rather than standing out as a fourth colour. --}}
        <section data-beat="7" data-screen-label="08 The Red Flags" style="min-height: 100vh; display: flex; align-items: center; background: #ffffff; padding: 110px 0;">
            <div style="width: min(1080px, 86vw); margin: 0 auto;">
                <div data-reveal style="font: 700 20px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #d9524a;">The Red Flags</div>
                <h2 data-reveal data-delay="80" style="font: 700 clamp(30px, 3.6vw, 48px)/1.15 'Public Sans', sans-serif; letter-spacing: -0.012em; color: #162e51; margin: 16px 0 0; max-width: 24ch;">Closed software is invisible and costly to the city.</h2>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 40px; margin-top: 44px;">
                    <div data-reveal data-delay="140" style="padding-top: 20px; border-top: 3px solid #d9524a;">
                        <div style="font: 700 19px/1.3 'Public Sans', sans-serif; color: #162e51;">Paying more, with no way to check</div>
                        <p style="font: 400 15px/1.6 'Public Sans', sans-serif; color: #3d4551; margin: 8px 0 0;">Renewals rarely get checked against free, open-source alternatives before the same proprietary licence renews at whatever price is quoted. With no public price list to compare against, the public can't tell whether that price is fair.</p>
                    </div>
                    <div data-reveal data-delay="220" style="padding-top: 20px; border-top: 3px solid #d9524a;">
                        <div style="font: 700 19px/1.3 'Public Sans', sans-serif; color: #162e51;">The same job, bought again</div>
                        <p style="font: 400 15px/1.6 'Public Sans', sans-serif; color: #3d4551; margin: 8px 0 0;">Purchasing information isn't shared between agencies, so dozens of them license the same kind of software separately &mdash; each one negotiating its own price for a problem another agency already paid to solve.</p>
                    </div>
                    <div data-reveal data-delay="300" style="padding-top: 20px; border-top: 3px solid #d9524a;">
                        <div style="font: 700 19px/1.3 'Public Sans', sans-serif; color: #162e51;">Billions with little visible oversight</div>
                        <p style="font: 400 15px/1.6 'Public Sans', sans-serif; color: #3d4551; margin: 8px 0 0;">Master agreements set a ceiling on what can be bought, not a record of what was. {{ $sbB($sbMaCeiling) }} in buying power exists citywide under these agreements, and most of it moves through purchase orders that leave the agreement's own record showing nothing.</p>
                    </div>
                </div>
            </div>
        </section>

        {{-- ============ BEAT 09 — Open source as leverage — gray ============ --}}
        <section data-beat="8" data-screen-label="09 Open source as leverage" style="min-height: 100vh; display: flex; align-items: center; background: #f9fafb; padding: 110px 0;">
            <div style="width: min(1080px, 86vw); margin: 0 auto;">
                <div data-reveal style="font: 700 20px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #ff941f;">CONSIDERING ALTERNATIVE OPTIONS GIVES THE CITY LEVERAGE</div>
                <h2 data-reveal data-delay="80" style="font: 700 clamp(30px, 3.6vw, 48px)/1.15 'Public Sans', sans-serif; letter-spacing: -0.012em; color: #162e51; margin: 16px 0 0; max-width: 24ch;">Open source software solutions keep the records public.</h2>
                <p data-reveal data-delay="140" style="font: 400 17px/1.65 'Public Sans', sans-serif; color: #3d4551; margin: 18px 0 0; max-width: 66ch;">Databook checks every product the city licenses automatically against a catalogue of <strong style="color: #162e51;">1,995</strong> free, open-source projects already used by governments, turning up close matches covering <strong style="color: #162e51;">$19.06M</strong> of spending. These solutions are built once and kept open so other agencies can reuse them, with no renewing of contracts.</p>

                <svg viewBox="0 0 1020 220" style="width: 100%; height: auto; margin-top: 40px; overflow: visible;">
                    <g data-reveal data-delay="140">
                        <text x="20" y="42" style="font: 700 12px 'Public Sans', sans-serif; letter-spacing: .06em; fill: #71767a;">CURRENTLY LICENSED</text>
                        <text x="20" y="80" style="font: 700 30px 'Public Sans', sans-serif; fill: #162e51;">Esri ArcGIS</text>
                        <text x="20" y="112" style="font: 700 18px 'Roboto Mono', monospace; fill: #162e51;">{{ $sbArc ? $sbB($sbArc['value']) : '—' }}</text>
                        <text x="20" y="140" style="font: 400 14px 'Public Sans', sans-serif; fill: #71767a;">Mapping software, {{ $sbArcScope }}.</text>
                        <text x="20" y="160" style="font: 400 14px 'Public Sans', sans-serif; fill: #71767a;">It is the most expensive line in</text>
                        <text x="20" y="180" style="font: 400 14px 'Public Sans', sans-serif; fill: #71767a;">the licence data with a known substitute.</text>
                        <text x="20" y="208" style="font: 700 14px 'Public Sans', sans-serif; fill: #2e8540;">But a free alternative exists.</text>
                    </g>
                    <g data-reveal data-delay="260">
                        <circle cx="510" cy="96" r="40" fill="#ffffff" stroke="#162e51" stroke-width="2.4"></circle>
                        <path data-draw data-delay="420" d="M492 84 h30 l-9 -9 M528 108 h-30 l9 9" fill="none" stroke="#ff941f" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>
                        <text x="510" y="164" text-anchor="middle" style="font: 700 12px 'Public Sans', sans-serif; letter-spacing: .06em; fill: #71767a;">MATCHED</text>
                    </g>
                    <g data-reveal data-delay="360">
                        <text x="620" y="42" style="font: 700 12px 'Public Sans', sans-serif; letter-spacing: .06em; fill: #2e8540;">IN THE CATALOGUE</text>
                        <text x="620" y="80" style="font: 700 30px 'Public Sans', sans-serif; fill: #162e51;">QGIS</text>
                        <text x="620" y="112" style="font: 700 15px 'Roboto Mono', monospace; fill: #2e8540;">free and open source</text>
                        <text x="620" y="140" style="font: 400 14px 'Public Sans', sans-serif; fill: #71767a;">69 government bodies already run QGIS — the highest</text>
                        <text x="620" y="160" style="font: 400 14px 'Public Sans', sans-serif; fill: #71767a;">count in the catalogue. It is free under the GPL-2.0</text>
                        <text x="620" y="180" style="font: 400 14px 'Public Sans', sans-serif; fill: #71767a;">licence, and both ArcGIS Desktop and ArcGIS Pro map</text>
                        <text x="620" y="200" style="font: 400 14px 'Public Sans', sans-serif; fill: #71767a;">onto it at strong confidence.</text>
                    </g>
                </svg>

                <div data-reveal style="font: 700 13px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #71767a; margin: 52px 0 0;">Three ways that changes things</div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 40px; margin-top: 22px;">
                    <div data-reveal data-delay="120">
                        <svg viewBox="0 0 60 44" style="width: 52px; height: 38px;">
                            <path data-draw data-delay="200" d="M6 16 h38 l-9 -9 M50 30 h-38 l9 9" fill="none" stroke="#2e8540" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"></path>
                        </svg>
                        <div style="font: 700 19px/1.3 'Public Sans', sans-serif; color: #162e51; margin-top: 12px;">Replace</div>
                        <p style="font: 400 15px/1.6 'Public Sans', sans-serif; color: #3d4551; margin: 8px 0 0;">A vendor product can be swapped, and open documentation makes that move a known quantity. The code and the migration notes are public, so an agency can see in advance what the work involves and follow a path other governments have already published.</p>
                    </div>
                    <div data-reveal data-delay="200">
                        <svg viewBox="0 0 60 44" style="width: 52px; height: 38px;">
                            <circle cx="12" cy="22" r="6" fill="none" stroke="#2e8540" stroke-width="2.6"></circle>
                            <circle cx="46" cy="10" r="6" fill="none" stroke="#2e8540" stroke-width="2.6"></circle>
                            <circle cx="46" cy="34" r="6" fill="none" stroke="#2e8540" stroke-width="2.6"></circle>
                            <path data-draw data-delay="280" d="M17 19 L41 12 M17 25 L41 32" fill="none" stroke="#2e8540" stroke-width="2.2" stroke-linecap="round"></path>
                        </svg>
                        <div style="font: 700 19px/1.3 'Public Sans', sans-serif; color: #162e51; margin-top: 12px;">Reuse</div>
                        <p style="font: 400 15px/1.6 'Public Sans', sans-serif; color: #3d4551; margin: 8px 0 0;">Once one agency has already done the work of getting it running, the next agency starts from that setup instead of a new purchase — and the city pays for support once rather than solving the same problem department by department.</p>
                    </div>
                    <div data-reveal data-delay="280">
                        <svg viewBox="0 0 60 44" style="width: 52px; height: 38px;">
                            <path d="M30 6 v32" stroke="#2e8540" stroke-width="2.6" stroke-linecap="round"></path>
                            <path data-draw data-delay="360" d="M12 14 h36" fill="none" stroke="#2e8540" stroke-width="2.6" stroke-linecap="round"></path>
                            <path d="M12 14 l-6 12 h12 z" fill="none" stroke="#2e8540" stroke-width="2.2" stroke-linejoin="round"></path>
                            <path d="M48 14 l-6 12 h12 z" fill="none" stroke="#2e8540" stroke-width="2.2" stroke-linejoin="round"></path>
                        </svg>
                        <div style="font: 700 19px/1.3 'Public Sans', sans-serif; color: #162e51; margin-top: 12px;">Negotiate</div>
                        <p style="font: 400 15px/1.6 'Public Sans', sans-serif; color: #3d4551; margin: 8px 0 0;">An agency that knows its open source alternatives has leverage when negotiating with vendors. Even if it never switches, a documented alternative changes the conversation at renewal, and can result in lowered costs.</p>
                    </div>
                </div>
            </div>
        </section>

        {{-- ============ BEAT 10 — Ways in — navy (the interactive beat) ============
             The prototype pins this beat's stage inside its own scrollport
             because the design tool's html/body never scroll. Here the window
             scrolls, so the stage is a plain page-level `position: sticky`
             element and public/js/digital-services-storyboard.js resolves the
             active row against window.innerHeight instead of a port's
             scrollTop. --}}
        <section data-beat="9" data-screen-label="10 Ways in" style="background: #0f2340;">
            <div data-x7 style="height: 560vh; position: relative;">
                <div aria-hidden="true" style="position: absolute; inset: 0; display: flex; flex-direction: column; pointer-events: none;">
                    <div data-x7-cue="-1" style="flex: 5;"></div>
                    <div data-x7-cue="0" style="flex: 18.75;"></div>
                    <div data-x7-cue="-1" style="flex: 5;"></div>
                    <div data-x7-cue="1" style="flex: 18.75;"></div>
                    <div data-x7-cue="-1" style="flex: 5;"></div>
                    <div data-x7-cue="2" style="flex: 18.75;"></div>
                    <div data-x7-cue="-1" style="flex: 5;"></div>
                    <div data-x7-cue="3" style="flex: 18.75;"></div>
                    <div data-x7-cue="-1" style="flex: 5;"></div>
                </div>
                <div data-x7-stage style="position: sticky; top: 0; height: 100vh; display: flex; align-items: center; overflow: hidden;">
                    <div data-x7-inner style="width: min(1080px, 86vw); margin: 0 auto; padding: 24px 0;">

                        <div style="font: 700 20px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #ff941f;">How to use Databook</div>
                        <h2 style="font: 700 clamp(24px, 2.8vw, 34px)/1.2 'Public Sans', sans-serif; letter-spacing: -0.012em; color: #ffffff; margin: 12px 0 0; font-size: 30px;">Check Out These Tabs</h2>

                        <div style="position: relative; margin-top: 20px; border-top: 1px solid rgba(255,255,255,.18);">
                            <div aria-hidden="true" style="position: absolute; top: 0; bottom: 0; right: -26px; width: 4px; border-radius: 999px; background: rgba(255,255,255,.13);">
                                <div data-x7-thumb style="position: absolute; left: 0; width: 4px; border-radius: 999px; background: #ff941f; height: 24%; top: 0; transition: transform .12s linear;"></div>
                            </div>

                            <div data-x7-row="0" style="border-bottom: 1px solid rgba(255,255,255,.14); overflow: hidden; transition: opacity .4s ease, max-height .6s cubic-bezier(.22,.8,.3,1);">
                                <div style="display: grid; grid-template-columns: 56px minmax(0, 1fr) 26px; align-items: baseline; gap: 0 20px; padding: 15px 0;">
                                    <div style="font: 400 13px/1.4 'Roboto Mono', monospace; letter-spacing: .08em; color: #ff941f;">01</div>
                                    <div>
                                        <div style="font: 700 22px/1.25 'Public Sans', sans-serif; letter-spacing: -0.01em; color: #ffffff;">Contracts</div>
                                        <p data-x7-sub style="font: 400 15px/1.6 'Public Sans', sans-serif; color: #c8d6e8; margin: 6px 0 0; max-width: 62ch; overflow: hidden; transition: max-height .45s ease, opacity .35s ease, margin .45s ease;">{{ $sbQueueLine }} — plus the searchable index of every technology contract.</p>
                                    </div>
                                    <a href="{{ route('research.digital-reform.contracts') }}" aria-label="Go to Contracts" style="align-self: center;">
                                        <svg viewBox="0 0 24 24" style="width: 22px; height: 22px;" aria-hidden="true">
                                            <path d="M4 12 H19 M13 6 L19 12 L13 18" fill="none" stroke="#7f9dc2" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>
                                        </svg>
                                    </a>
                                </div>
                                <div data-x7-panel style="max-height: 0; opacity: 0; transition: max-height .6s cubic-bezier(.22,.8,.3,1), opacity .45s ease;">
                                    <div style="display: grid; grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr); gap: 40px; padding: 2px 0 22px 76px; align-items: start;">
                                        <div>
                                            <p style="font: 400 15px/1.65 'Public Sans', sans-serif; color: #dce7f4; margin: 0;">Start here when you want to know what is coming up. A contract that ends is a contract someone has to decide about, and the queue is sorted by when that decision arrives.</p>
                                            <p style="font: 400 15px/1.65 'Public Sans', sans-serif; color: #a9c0dc; margin: 14px 0 0;">Flags mark the rows worth a second look. They are prompts to investigate, not determinations, and each one says why it was raised.</p>
                                        </div>
                                        <div style="border: 1px solid rgba(255,255,255,.16); border-radius: 8px; overflow: hidden;">
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) minmax(84px, 108px) minmax(70px, 92px); gap: 12px; padding: 9px 16px; background: rgba(255,255,255,.06); font: 700 12px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #a9c0dc;">
                                                <div>Contract</div><div>Ends</div><div>Flag</div>
                                            </div>
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) minmax(84px, 108px) minmax(70px, 92px); gap: 12px; padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); font: 400 14px/1.35 'Public Sans', sans-serif; color: #ffffff; align-items: center;">
                                                <div>Enterprise mapping licences</div><div style="font-family: 'Roboto Mono', monospace; color: #ffb056;">2027-06-30</div><div><span style="font: 700 11px/1 'Public Sans', sans-serif; letter-spacing: .04em; color: #ffd8a8; border: 1px solid rgba(255,148,31,.5); border-radius: 999px; padding: 4px 8px;">Alternative</span></div>
                                            </div>
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) minmax(84px, 108px) minmax(70px, 92px); gap: 12px; padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); font: 400 14px/1.35 'Public Sans', sans-serif; color: #ffffff; align-items: center;">
                                                <div>Network equipment maintenance</div><div style="font-family: 'Roboto Mono', monospace; color: #ffb056;">2028-01-14</div><div style="color: #7f9dc2;">—</div>
                                            </div>
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) minmax(84px, 108px) minmax(70px, 92px); gap: 12px; padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); font: 400 14px/1.35 'Public Sans', sans-serif; color: #ffffff; align-items: center;">
                                                <div>Case management system</div><div style="font-family: 'Roboto Mono', monospace; color: #ffb056;">2029-09-30</div><div><span style="font: 700 11px/1 'Public Sans', sans-serif; letter-spacing: .04em; color: #ffd8a8; border: 1px solid rgba(255,148,31,.5); border-radius: 999px; padding: 4px 8px;">Sole source</span></div>
                                            </div>
                                            <div style="padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); font: 400 13px/1.5 'Public Sans', sans-serif; color: #a9c0dc; background: rgba(255,255,255,.04);">Illustrative rows. Sorted by end date — the nearest decision is first.</div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div data-x7-row="1" style="border-bottom: 1px solid rgba(255,255,255,.14); overflow: hidden; transition: opacity .4s ease, max-height .6s cubic-bezier(.22,.8,.3,1);">
                                <div style="display: grid; grid-template-columns: 56px minmax(0, 1fr) 26px; align-items: baseline; gap: 0 20px; padding: 15px 0;">
                                    <div style="font: 400 13px/1.4 'Roboto Mono', monospace; letter-spacing: .08em; color: #ff941f;">02</div>
                                    <div>
                                        <div style="font: 700 22px/1.25 'Public Sans', sans-serif; letter-spacing: -0.01em; color: #ffffff;">Products</div>
                                        <p data-x7-sub style="font: 400 15px/1.6 'Public Sans', sans-serif; color: #c8d6e8; margin: 6px 0 0; max-width: 62ch; overflow: hidden; transition: max-height .45s ease, opacity .35s ease, margin .45s ease;">238 of those expiring contracts are licences, analysed product family by product family.</p>
                                    </div>
                                    <a href="{{ route('research.digital-reform.products') }}" aria-label="Go to Products" style="align-self: center;">
                                        <svg viewBox="0 0 24 24" style="width: 22px; height: 22px;" aria-hidden="true">
                                            <path d="M4 12 H19 M13 6 L19 12 L13 18" fill="none" stroke="#7f9dc2" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>
                                        </svg>
                                    </a>
                                </div>
                                <div data-x7-panel style="max-height: 0; opacity: 0; transition: max-height .6s cubic-bezier(.22,.8,.3,1), opacity .45s ease;">
                                    <div style="display: grid; grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr); gap: 40px; padding: 2px 0 22px 76px; align-items: start;">
                                        <div>
                                            <p style="font: 400 15px/1.65 'Public Sans', sans-serif; color: #dce7f4; margin: 0;">Contracts name vendors, not products. This page reads what each licence contract actually buys and groups the separate purchases of the same thing into one product family.</p>
                                            <p style="font: 400 15px/1.65 'Public Sans', sans-serif; color: #a9c0dc; margin: 14px 0 0;">Once the purchases are grouped, an alternative can be attached to the family rather than argued contract by contract.</p>
                                        </div>
                                        <div style="display: grid; gap: 12px;">
                                            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                                                <span style="font: 400 13px/1 'Public Sans', sans-serif; color: #a9c0dc; border: 1px dashed rgba(255,255,255,.28); border-radius: 6px; padding: 8px 10px;">DCP contract</span>
                                                <span style="font: 400 13px/1 'Public Sans', sans-serif; color: #a9c0dc; border: 1px dashed rgba(255,255,255,.28); border-radius: 6px; padding: 8px 10px;">DOT contract</span>
                                                <span style="font: 400 13px/1 'Public Sans', sans-serif; color: #a9c0dc; border: 1px dashed rgba(255,255,255,.28); border-radius: 6px; padding: 8px 10px;">DEP contract</span>
                                                <span style="font: 400 13px/1 'Public Sans', sans-serif; color: #a9c0dc; border: 1px dashed rgba(255,255,255,.28); border-radius: 6px; padding: 8px 10px;">+21 more</span>
                                            </div>
                                            <svg viewBox="0 0 300 26" style="width: 100%; height: 26px;" aria-hidden="true">
                                                <path d="M150 2 V22 M142 15 L150 22 L158 15" fill="none" stroke="#ff941f" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"></path>
                                            </svg>
                                            <div style="border: 1px solid rgba(255,148,31,.45); border-radius: 8px; padding: 14px 18px; background: rgba(255,148,31,.07);">
                                                <div style="font: 700 12px/1 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #ffb056;">Product family</div>
                                                <div style="font: 700 20px/1.3 'Public Sans', sans-serif; color: #ffffff; margin-top: 8px;">Desktop GIS — ArcGIS</div>
                                                <div style="font: 400 14px/1.6 'Public Sans', sans-serif; color: #c8d6e8; margin-top: 6px;">{{ $sbArcLine }}</div>
                                                <div style="display: flex; align-items: center; gap: 10px; margin-top: 14px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,.14); font: 400 14px/1.5 'Public Sans', sans-serif; color: #c8d6e8;">
                                                    <span style="font: 700 11px/1 'Public Sans', sans-serif; letter-spacing: .04em; color: #b8e8c4; border: 1px solid rgba(46,133,64,.6); border-radius: 999px; padding: 4px 8px;">Alternative</span>
                                                    QGIS · 69 government adopters · GPL-2.0
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div data-x7-row="2" style="border-bottom: 1px solid rgba(255,255,255,.14); overflow: hidden; transition: opacity .4s ease, max-height .6s cubic-bezier(.22,.8,.3,1);">
                                <div style="display: grid; grid-template-columns: 56px minmax(0, 1fr) 26px; align-items: baseline; gap: 0 20px; padding: 15px 0;">
                                    <div style="font: 400 13px/1.4 'Roboto Mono', monospace; letter-spacing: .08em; color: #ff941f;">03</div>
                                    <div>
                                        <div style="font: 700 22px/1.25 'Public Sans', sans-serif; letter-spacing: -0.01em; color: #ffffff;">Agreements</div>
                                        <p data-x7-sub style="font: 400 15px/1.6 'Public Sans', sans-serif; color: #c8d6e8; margin: 6px 0 0; max-width: 62ch; overflow: hidden; transition: max-height .45s ease, opacity .35s ease, margin .45s ease;">The instruments agencies buy against. Their figures are ceilings, not spend.</p>
                                    </div>
                                    <a href="{{ route('research.digital-reform.agreements') }}" aria-label="Go to Agreements" style="align-self: center;">
                                        <svg viewBox="0 0 24 24" style="width: 22px; height: 22px;" aria-hidden="true">
                                            <path d="M4 12 H19 M13 6 L19 12 L13 18" fill="none" stroke="#7f9dc2" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>
                                        </svg>
                                    </a>
                                </div>
                                <div data-x7-panel style="max-height: 0; opacity: 0; transition: max-height .6s cubic-bezier(.22,.8,.3,1), opacity .45s ease;">
                                    <div style="display: grid; grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr); gap: 40px; padding: 2px 0 22px 76px; align-items: start;">
                                        <div>
                                            <p style="font: 400 15px/1.65 'Public Sans', sans-serif; color: #dce7f4; margin: 0;">A master agreement is headroom, not a purchase. It sets the most that may be spent, and any agency may buy against it.</p>
                                            <svg viewBox="0 0 320 132" style="width: 100%; max-width: 250px; height: auto; margin-top: 10px;" aria-hidden="true">
                                                <rect x="2" y="10" width="316" height="34" rx="6" fill="rgba(255,148,31,.10)" stroke="#ff941f" stroke-width="1.4"></rect>
                                                <text x="14" y="31" fill="#ffb056" style="font: 700 12px 'Public Sans', sans-serif; letter-spacing: .06em;">CEILING $480M</text>
                                                <path d="M60 44 V70 M160 44 V70 M260 44 V70" stroke="#7f9dc2" stroke-width="1.3" stroke-dasharray="3 4"></path>
                                                <rect x="20" y="72" width="80" height="30" rx="5" fill="rgba(255,255,255,.07)" stroke="rgba(255,255,255,.28)" stroke-width="1"></rect>
                                                <text x="34" y="91" fill="#dce7f4" style="font: 400 11px 'Public Sans', sans-serif;">Order id A</text>
                                                <rect x="120" y="72" width="80" height="30" rx="5" fill="rgba(255,255,255,.07)" stroke="rgba(255,255,255,.28)" stroke-width="1"></rect>
                                                <text x="134" y="91" fill="#dce7f4" style="font: 400 11px 'Public Sans', sans-serif;">Order id B</text>
                                                <rect x="220" y="72" width="80" height="30" rx="5" fill="rgba(255,255,255,.07)" stroke="rgba(255,255,255,.28)" stroke-width="1"></rect>
                                                <text x="234" y="91" fill="#dce7f4" style="font: 400 11px 'Public Sans', sans-serif;">Order id C</text>
                                                <text x="20" y="122" fill="#a9c0dc" style="font: 400 11px 'Public Sans', sans-serif;">Payments are filed here, under their own ids</text>
                                            </svg>
                                        </div>
                                        <div style="border: 1px solid rgba(255,255,255,.16); border-radius: 8px; overflow: hidden;">
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) minmax(72px, 104px) minmax(84px, 128px); gap: 12px; padding: 9px 16px; background: rgba(255,255,255,.06); font: 700 12px/1.3 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #a9c0dc;">
                                                <div>Agreement</div><div style="color: #ffb056;">Ceiling</div><div>Paid under this id</div>
                                            </div>
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) minmax(72px, 104px) minmax(84px, 128px); gap: 12px; padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); font: 400 14px/1.35 'Public Sans', sans-serif; color: #ffffff; align-items: center;">
                                                <div>Citywide software reseller</div><div style="font-family: 'Roboto Mono', monospace; color: #ffb056; background: rgba(255,148,31,.14); border-radius: 4px; padding: 3px 6px;">$480M</div><div style="color: #7f9dc2;">—</div>
                                            </div>
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) minmax(72px, 104px) minmax(84px, 128px); gap: 12px; padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); font: 400 14px/1.35 'Public Sans', sans-serif; color: #ffffff; align-items: center;">
                                                <div>Hardware supply, multi-agency</div><div style="font-family: 'Roboto Mono', monospace; color: #ffb056; background: rgba(255,148,31,.14); border-radius: 4px; padding: 3px 6px;">$215M</div><div style="color: #7f9dc2;">—</div>
                                            </div>
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) minmax(72px, 104px) minmax(84px, 128px); gap: 12px; padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); font: 400 14px/1.35 'Public Sans', sans-serif; color: #ffffff; align-items: center;">
                                                <div>Single-agency support renewal</div><div style="font-family: 'Roboto Mono', monospace; color: #7f9dc2;">—</div><div style="font-family: 'Roboto Mono', monospace;">$4.2M</div>
                                            </div>
                                            <div style="padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); background: rgba(255,148,31,.08); font: 400 13px/1.6 'Public Sans', sans-serif; color: #dce7f4;">Illustrative rows. Only the third is an ordinary contract, so only it shows a payment. The first two are masters: the money spent against them is filed under separate order ids, which is why a $480M agreement can read zero.</div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div data-x7-row="3" style="border-bottom: 1px solid rgba(255,255,255,.14); overflow: hidden; transition: opacity .4s ease, max-height .6s cubic-bezier(.22,.8,.3,1);">
                                <div style="display: grid; grid-template-columns: 56px minmax(0, 1fr) 26px; align-items: baseline; gap: 0 20px; padding: 15px 0;">
                                    <div style="font: 400 13px/1.4 'Roboto Mono', monospace; letter-spacing: .08em; color: #ff941f;">04</div>
                                    <div>
                                        <div style="font: 700 22px/1.25 'Public Sans', sans-serif; letter-spacing: -0.01em; color: #ffffff;">Vendors</div>
                                        <p data-x7-sub style="font: 400 15px/1.6 'Public Sans', sans-serif; color: #c8d6e8; margin: 6px 0 0; max-width: 62ch; overflow: hidden; transition: max-height .45s ease, opacity .35s ease, margin .45s ease;">{{ number_format($sbVendors) }} vendors hold at least one confirmed technology contract.</p>
                                    </div>
                                    <a href="{{ route('research.digital-reform.vendors') }}" aria-label="Go to Vendors" style="align-self: center;">
                                        <svg viewBox="0 0 24 24" style="width: 22px; height: 22px;" aria-hidden="true">
                                            <path d="M4 12 H19 M13 6 L19 12 L13 18" fill="none" stroke="#7f9dc2" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>
                                        </svg>
                                    </a>
                                </div>
                                <div data-x7-panel style="max-height: 0; opacity: 0; transition: max-height .6s cubic-bezier(.22,.8,.3,1), opacity .45s ease;">
                                    <div style="display: grid; grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr); gap: 40px; padding: 2px 0 22px 76px; align-items: start;">
                                        <div>
                                            <p style="font: 400 15px/1.65 'Public Sans', sans-serif; color: #dce7f4; margin: 0;">Counts here cover only the contracts the classification confirmed are technology — not a vendor's whole book of City business.</p>
                                            <p style="font: 400 15px/1.65 'Public Sans', sans-serif; color: #a9c0dc; margin: 14px 0 0;">Where a vendor resells other companies' software, the product families it sells are listed. That column is what separates a reseller from a maker.</p>
                                        </div>
                                        <div style="border: 1px solid rgba(255,255,255,.16); border-radius: 8px; overflow: hidden;">
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) 84px minmax(104px, 1.05fr); gap: 12px; padding: 9px 16px; background: rgba(255,255,255,.06); font: 700 12px/1.3 'Public Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #a9c0dc;">
                                                <div>Vendor</div><div>Contracts</div><div style="color: #ffb056;">Sells</div>
                                            </div>
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) 84px minmax(104px, 1.05fr); gap: 12px; padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); font: 400 14px/1.35 'Public Sans', sans-serif; color: #ffffff; align-items: center;">
                                                <div>A reseller</div><div style="font-family: 'Roboto Mono', monospace;">37</div><div style="font-size: 13px; color: #ffd8a8;">9 product families</div>
                                            </div>
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) 84px minmax(104px, 1.05fr); gap: 12px; padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); font: 400 14px/1.35 'Public Sans', sans-serif; color: #ffffff; align-items: center;">
                                                <div>A maker</div><div style="font-family: 'Roboto Mono', monospace;">12</div><div style="font-size: 13px; color: #ffd8a8;">1 product family</div>
                                            </div>
                                            <div style="display: grid; grid-template-columns: minmax(110px, 1fr) 84px minmax(104px, 1.05fr); gap: 12px; padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); font: 400 14px/1.35 'Public Sans', sans-serif; color: #ffffff; align-items: center;">
                                                <div>A services firm</div><div style="font-family: 'Roboto Mono', monospace;">21</div><div style="font-size: 13px; color: #7f9dc2;">No licensed products</div>
                                            </div>
                                            <div style="padding: 10px 16px; border-top: 1px solid rgba(255,255,255,.1); font: 400 13px/1.5 'Public Sans', sans-serif; color: #a9c0dc; background: rgba(255,255,255,.04);">Illustrative rows. Same spend, three different kinds of company.</div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                        </div>
                    </div>
                </div>
            </div>
        </section>

    </div>
</div>
