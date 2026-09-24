@extends('layout')

@section('head')
{{-- Published with its parent page 2026-08-11. ⚠ A family page is only as reviewed
     as the family it describes: the curated families were reviewed, the tail was
     not. What carries that caveat today is the Analysis BANNER (the badge this
     line used to name was dropped in the header simplification; the banner
     replaced it below, and it says more), the
     "AI-derived and unreviewed / two models agreed 92%" note, the `class_tier`
     marker on the purchase class, and the `summary_curated` marker on the
     summary. Do not remove them.
     ⚠ This comment used to name "the top 20 (88.0% of value)". That figure was
     stale where it was rendered on the index page and is stale here too --
     reviewed coverage is now COMPUTED from the class seed and served as
     `summary.reviewed`. Do not reintroduce a typed percentage, in copy or in a
     comment; the next reader believes both.
     ⚠⚠ AND THAT RULE WAS BEING BROKEN TWENTY LINES BELOW THIS COMMENT UNTIL
     2026-09-18. The sentence "Only the largest 20 product families — 88.0% of
     the value in this analysis — have been reviewed by hand so far" was typed
     into the class-tier block and rendered on every family whose class was not
     curated. `_reviewed()` in the API was written to remove exactly that
     sentence, was applied to the INDEX, and was never swept here. Measured when
     it was found: the top 20 are 76.0% of value, and the curated seed covers 99
     families carrying 90.6%. It is served as `reviewed` now.

     ⚠⚠ SECTION ORDER IS DELIBERATE AND IS THE POINT OF THE 2026-09-18 rebuild.
     A reader arriving here wants, in order: what this is, what else does the
     job, what our records say, and only then how we classified it. The page
     used to open with FOUR analyst boxes (summary, purchase class + mix table,
     build-vs-buy, merged spellings) plus the open-source table, so the first
     figure about City spend sat ~1,850px down at 1440. The interpretation layer
     now sits BELOW the data it interprets, under "How we classified it".
     ⚠ Moving it must not hide it: every caveat that was visible is still
     visible and none of them moved behind a click. --}}
<style>
    .db-page-lead { max-width: none; }

    /* ⚠⚠ ONE CARD TREATMENT. The page carried THREE competing ones -- a navy
       left-border block for prose (`lic-summary`), a bordered white card for
       tables (`db-table-wrap`), and an orange left-border block for the
       build-vs-buy rating (`lic-note`). Three shapes for "a box of content" made
       the page read as three pages stapled together. Everything is `lic-card`
       now: the same white surface, border and radius the table wrapper already
       used, so a prose block and a table block sit in the same family.
       ⚠ The accent is a THIN TOP RULE, not a 3px left border, because a left
       border shifts the content in and made the prose blocks hang out of line
       with the tables beside them. */
    .lic-card { background: var(--db-bg); border: 1px solid var(--db-border);
                border-radius: var(--db-radius); padding: var(--db-space-3); }
    .lic-card-head { padding: var(--db-space-3) var(--db-space-3) 0; }
    .lic-card.is-accent { border-top: 3px solid var(--db-brand); }
    /* ⚠ A NAMED VARIANT, NOT DRIFT. The two rollup cards under the tiles carry
       16px padding where every other card carries 24px, and the reason is
       measured: at 24px the header ran to 947 at 1440x900 and the fold guard
       fired. A variant with a name is a decision the next reader can see; a
       one-off inline padding is the inconsistency the audit was removing. */
    .lic-card.is-compact { padding: var(--db-space-2); }
    .lic-card.is-brandwash { background: var(--db-brand-wash); border-color: var(--db-brand); }

    .lic-h2 { font-size: var(--db-text-lg); margin: 0; }
    .lic-num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
    .lic-sub { font-size: var(--db-text-2xs); color: var(--db-text-muted); }
    .lic-prod { font-size: var(--db-text-2xs); color: var(--db-text-muted); display: block; }
    .lic-tag { font-size: var(--db-text-2xs); text-transform: uppercase;
               letter-spacing: var(--db-tracking-wide); color: var(--db-text-muted); }
    .lic-chip { display: inline-block; background: var(--db-gray-100, #eef1f5); border-radius: 12px;
                padding: 2px 10px; margin: 2px 4px 2px 0; font-size: var(--db-text-2xs); }

    /* ⚠⚠ A CAVEAT IS COMPACT, NEVER HIDDEN. The owner asked for the page's grey
       method paragraphs to collapse behind disclosures. Enumerating them first
       showed that MOST ARE CAVEATS -- "a mention is not a purchase", "a shared
       function is not proof one could replace another", "never what was bought
       or what it cost", the product table's remainder, the notice cap. Those are
       the sentences that stop a reader misusing a figure, and this codebase's
       rule is that such a sentence is never behind a click. So they are made
       SHORT and given one consistent treatment instead: a single indented line
       with a rule, which reads as an aside without disappearing. */
    .lic-caveat { font-size: var(--db-text-2xs); color: var(--db-text-muted);
                  border-left: 2px solid var(--db-border); padding-left: var(--db-space-2);
                  margin: var(--db-space-1) 0 0; }

    /* ...and only genuine METHOD/PROVENANCE text -- how a row was sourced, what a
       classifier agreed on -- goes behind this. Its summary still names what is
       inside, so a reader can tell whether it is worth opening. */
    .lic-method { font-size: var(--db-text-2xs); color: var(--db-text-muted); margin-top: var(--db-space-1); }
    .lic-method > summary { cursor: pointer; color: var(--db-link, #005ea2); list-style: none; display: inline-flex;
                            align-items: center; gap: 4px; }
    .lic-method > summary::-webkit-details-marker { display: none; }
    .lic-method > summary::before { content: "\F282"; font-family: "bootstrap-icons"; font-size: .8em; }
    .lic-method[open] > summary::before { content: "\F286"; }
    .lic-method > div { margin-top: 4px; padding-left: var(--db-space-2);
                        border-left: 2px solid var(--db-border); }

    /* ⚠ SPACING IS ON THE TOKEN GRID, NOT TYPED. The audit found 11 inline
       `margin-top: 4px` and 7 `margin-top: 6px` beside a grid whose smallest
       step is 8px -- three different gaps doing one job. `lic-gap` is the one
       small gap; `lic-rule` is the one "new sub-block" separator. */
    .lic-gap  { margin-top: var(--db-space-1); }
    .lic-rule { margin-top: var(--db-space-1); padding-top: var(--db-space-1); border-top: 1px solid var(--db-border); }
    /* ⚠ THE WEB-ESTATE PANEL'S <h3> RENDERED AT 24px -- LARGER than the 20px h2s
       above it. A component name is a sub-heading of the panel and sizes below
       its h2. */
    .lic-band h3.lic-h3 { font-size: var(--db-text-base); margin: var(--db-space-2) 0 var(--db-space-05); }
    /* The compact rollup tables under the tiles: one class, not inline cell padding. */
    .lic-mini td { padding: var(--db-space-05) 0; border: 0; line-height: 1.3; }
    /* The compact cards' own small gap: half a step, and still on the grid. */
    .lic-card.is-compact .lic-gap { margin-top: var(--db-space-05); }
    /* The header's answer chips: what kind of purchase, what job, reviewed or not.
       Each one links to, or is explained by, a block further down the page. */
    .lic-keychip { display: inline-flex; align-items: center; gap: 6px; background: var(--db-bg);
                   border: 1px solid var(--db-border); border-radius: 14px;
                   padding: var(--db-space-05) var(--db-space-15); margin: 2px 6px 2px 0; font-size: var(--db-text-sm); }
    .lic-keychip a { text-decoration: none; }
    /* Section rule: the page is long, so each h2 gets a visible top edge rather
       than relying on whitespace alone to separate the bands. */
    .lic-band { border-top: 2px solid var(--db-border, #dde1e6); padding-top: var(--db-space-4);
                margin-top: var(--db-space-5); }
    .lic-band-title { font-size: var(--db-text-xl); margin: 0 0 var(--db-space-1); }
</style>
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    // ⚠ Plain text only — these are echoed through Blade escaping.
    $sum = $fam['summary'] ?? [];
    $products = $fam['products'] ?? [];
    $agencies = $fam['agencies'] ?? [];
    $vendors  = $fam['vendors'] ?? [];
    $rows     = $fam['contracts'] ?? [];
    $years    = $fam['by_year']['years'] ?? [];
    $methods  = $fam['by_method'] ?? [];
    $notices      = $fam['notices'] ?? [];
    $noticesTotal = (int) ($fam['notices_total'] ?? 0);
    // Precomputed: a Blade directive glued to a word character is not compiled,
    // and "top N of M" must only appear when the list is actually capped.
    $noticesCapped = $noticesTotal > count($notices);
    $isGeneric = (bool) ($fam['is_generic'] ?? false);
    $curated   = (bool) ($fam['curated'] ?? false);

    $fmtM = function ($v) {
        $v = (float) $v;
        if ($v >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
        if ($v >= 1000000)    return '$' . number_format($v / 1000000, 1) . 'M';
        if ($v >= 1000)       return '$' . number_format($v / 1000, 0) . 'K';
        return '$' . number_format($v, 0);
    };
    $licRoute = route('research.digital-reform.products');
    $expLink = route('research.digital-reform.review')
        . '?expiring_license=1&expiring_product=' . urlencode($fam['family'] ?? '')
        . '#expiring-contracts';
    // Precomputed: a Blade directive glued to a word character is not compiled.
    $rep = $fam['replaceability'] ?? [];
    // Plain-English label, precomputed: a Blade directive glued to a word
    // character is not compiled, and these strings are echoed escaped.
    $repWords = [
        'high'   => 'Plausibly, with open-source and modern tooling',
        'medium' => 'Feasible, but real effort and integration',
        'low'    => 'Unlikely - specialised, regulated or deeply integrated',
    ];
    $repLabel = $repWords[$rep['top'] ?? ''] ?? 'Not rated';
    $repSpread = '';
    if (!empty($rep['ranked'])) {
        $parts = [];
        foreach ($rep['ranked'] as $r0) {
            $parts[] = $r0['rating'] . ' on ' . $r0['contracts'] . ' contract'
                     . ($r0['contracts'] == 1 ? '' : 's');
        }
        $repSpread = '(' . implode(', ', $parts) . ')';
    }
    $purposes = $fam['recorded_purposes'] ?? [];
    $pClass = $fam['purchase_class'] ?? '';
    $pLever = $fam['lever'] ?? '';
    $cands  = $fam['candidates'] ?? [];
    $catMeta = $fam['catalogue'] ?? [];
    // ⚠ Build-vs-buy is only a meaningful question for a software license.
    // For hosting, cloud, content or services it is the WRONG question, and
    // showing it there is how $6.80M of AWS ended up invisible on `low`.
    // ⚠ $pClass is now the class that DOMINATES this family by value, resolved at
    // product grain. When the family holds more than one kind of purchase the mix
    // is rendered below, so a minority lever is stated rather than absorbed.
    $showRating = ($pClass === '' || $pClass === 'software-licence');
    $classMix   = $fam['class_mix'] ?? [];
    $classMixed = (bool) ($fam['class_mixed'] ?? false);
    $famValue   = 0.0;
    foreach ($classMix as $cm) { $famValue += (float) ($cm['value'] ?? 0); }
    // ⚠ Whether this classification was REVIEWED. The summary below already shows
    // its provenance; the class did not, so on a published page a reader could not
    // tell a hand-held judgement from an automatic one. Precomputed here because a
    // Blade directive glued to a word character is not compiled.
    $classTier  = $fam['class_tier'] ?? '';
    $tierWords  = [
        'curated' => 'Reviewed: held in a version-controlled file and never reclassified automatically.',
        'auto'    => 'Classified by AI and not yet reviewed by a person.',
        'mixed'   => 'Partly reviewed: some products here were classified by hand, others automatically.',
    ];
    $tierLabel  = $tierWords[$classTier] ?? '';
    $tierIcon   = ['curated' => 'bi-clipboard-check', 'auto' => 'bi-stars',
                   'mixed' => 'bi-clipboard-minus'][$classTier] ?? '';
    // ⚠⚠ COMPUTED, NEVER TYPED. This replaces a literal "88.0% of the value in
    // this analysis" that survived here after the same sentence was removed from
    // the index. Served by _reviewed() in the API, measured on the class seed.
    $reviewed = $fam['reviewed'] ?? [];
    $reviewedLine = '';
    if (($reviewed['families'] ?? 0) > 0) {
        $reviewedLine = number_format($reviewed['families']) . ' product families - '
            . $reviewed['share'] . '% of the value in this analysis - have been reviewed by hand so far.';
    }
    $classWords = \App\Custom\PurchaseClass::LABELS;
    $leverWords = [
        'open-source-substitute'   => 'Ask: is there an open-source substitute?',
        'benchmark-then-self-host' => 'Ask: is the price right for the volume? Rate cards are public.',
        'price-and-rightsizing'    => 'Ask: is consumption right-sized, and is committed-use pricing in place?',
        'is-the-paid-tier-needed'  => 'Ask: does the commercial tier earn its price? The software itself is free.',
        'is-the-content-needed'    => 'Ask: is this content needed, and is there a cheaper source?',
        'scope-and-rate-review'    => 'Ask: is the scope and day rate right? This is people, not software.',
    ];
    $capability = $fam['capability'] ?? '';
    $rateCard = $fam['rate_card'] ?? null;
    // Unregistered purchasing vehicles naming this product. Never added to any
    // total here -- see the block that renders them.
    $pipeVehicles = $fam['pipeline_vehicles'] ?? [];
    // ⚠ NO LABEL MAP HERE. Served by the API from the capability vocabulary seed
    // -- this was the third partial copy of that mapping across three views, all
    // of them stale. See _capability_labels() in api/routers/licenses.py.
    $capLabel = $fam['capability_label'] ?? $capability;
    $classLabel = $classWords[$pClass] ?? '';
    $leverLabel = $leverWords[$pLever] ?? '';

    $mergedNote = count($products) > 1
        ? 'Merged from ' . count($products) . ' spellings in the source data'
        : '';

    // ⚠⚠ ONE SELLER LIST, SERVED. "Vendors selling it" here counted only contract
    // vendors -- Microsoft read 6 -- while the index's "Bought through" cell read
    // 32 for the same family, because that column merges the City Record
    // awarded-to names through modules/resellers. Two answers under one heading.
    // The API now runs the SAME merge for this page, so the counts cannot drift.
    $sellers = $fam['sellers'] ?? [];
    $sellerNames = $sellers['names'] ?? [];
    // Contract vendors carry figures and a profile link; a notice-only name holds
    // no contract in this set, so it has neither and is marked rather than mixed in.
    $noticeOnlyNames = [];
    foreach ($sellerNames as $sn) {
        if (!empty($sn['notice_only'])) { $noticeOnlyNames[] = $sn['name']; }
    }
    $sellerTotal = (int) ($sellers['total'] ?? count($vendors));
    $sellerNoticeOnly = (int) ($sellers['notice_only'] ?? 0);
    // Capped display, full counts -- the cap is the API's and it is stated when it bites.
    $noticeOnlyHidden = $sellerNoticeOnly - count($noticeOnlyNames);

    // ⚠⚠ THE CALENDAR IS A SENTENCE NOW, NOT A TABLE. A three-row table headed
    // "When these end" 1,400px away from the contracts it describes said nothing
    // the contracts table cannot say in its own Ends column. The sentence still
    // discloses ALL THREE buckets -- years, ended, no end date -- because a
    // calendar that silently drops rows reads as the whole inventory, which is
    // the defect that once summed 262 contracts under a tile reading 948.
    $endedCount = (int) ($fam['by_year']['ended']['contracts'] ?? 0);
    $endedValue = (float) ($fam['by_year']['ended']['value'] ?? 0);
    $noEndDate  = (int) ($fam['by_year']['no_end_date'] ?? 0);
    $futureCount = 0;
    foreach ($years as $y) { $futureCount += (int) $y['contracts']; }

    // ⚠⚠ WHO MAKES IT. CURATED ONLY -- there is no automatic tier for this claim
    // and there must not be one. Every other block on this page describes a
    // CONTRACT; this one names a COMPANY, and being wrong about a named company
    // is a different kind of wrong. An absent row renders "not yet identified",
    // which is the honest state for 794 of the 814 families.
    $maker = $fam['maker'] ?? null;
    $makerKindWords = [
        'company'          => 'Made by',
        'service-provider' => 'Sold as a service by',
        'bundle'           => 'Built on a product made by',
    ];
    $makerKind = $maker['maker_kind'] ?? 'company';
    $makerVerb = $makerKindWords[$makerKind] ?? 'Made by';
    // ⚠ HYDRATED from the maker's own vendor profile where it has one, so the
    // company facts cannot drift from the page this card links to. Everything
    // here degrades to nothing when the lookup failed or the maker is not a
    // registered City vendor -- which is itself a finding the card states.
    $mvEntity  = $makerVendor['passport']['entity'] ?? [];
    $mvDb      = $makerVendor['doing_business'] ?? [];
    // ⚠⚠ OFFICERS ARE DELIBERATELY NOT RENDERED HERE, and only looking at the
    // page found out why. The Local Law 34 filing for MICROSOFT CORPORATION
    // lists "DANA BARNES - Chief Executive Officer" and "JAMIE HARPER - Chief
    // Executive Officer" alongside two Chief Financial Officers. Those are the
    // roles as FILED by whoever registered the company for City business -- in
    // practice regional or divisional officers -- not the corporation's
    // officers. On a card headed "Who makes it" they would tell a reader that
    // Microsoft's chief executive is Dana Barnes, which is false.
    // ⭐ The vendor profile still shows them, where the LL34 framing is explicit
    // and the claim is about the City filing rather than about the company. The
    // card links there. A fact that is true in one frame and false in another
    // belongs in the frame that makes it true.
    $makerHq = $maker['hq'] ?? '';
    $sameMaker = $fam['same_maker'] ?? [];

    // ⭐ THE ABOVE-THE-FOLD ROLLUPS (owner, 2026-09-18): who sells it and which
    // agencies buy it, beside the figures, without scrolling. Both are already
    // served value-ranked, so this is a SLICE of the same list the full tables
    // below render -- never a second aggregation, which is how one page comes to
    // hold two answers for one number.
    // ⚠ COUNT BEFORE YOU CAP. Each rollup states the full total beside the three
    // it shows, and links to the table that has the rest.
    $topAgencies = array_slice($agencies, 0, 3);
    $topVendors  = array_slice($vendors, 0, 3);

    // ⭐⭐ THE PRODUCTS IN THIS FAMILY, DERIVED -- NO SEED AND NO NEW CLAIM.
    // The owner asked what individual products the City is likely buying under a
    // family name, and the answer was already in the data, filed as something
    // else: the merged contract SPELLINGS. Citrix's are `Citrix NetScaler` and
    // `Citrix ShareFile`; Broadcom's are `CA Erwin` and `CA-IDMS`; Axon's are
    // `Axon Evidence` and `Axon Body Camera System`. Those are products, named on
    // contracts, and they were rendered at the bottom of the page as evidence
    // that a merge was correct rather than as the product list they are.
    // ⚠ EVERY ROW CARRIES HOW WE KNOW IT, because the grades are not equally
    // strong. "Named on a contract" is the City's own word for what it bought;
    // "observed on a City host" is an outside audit's inference about what is
    // running, which is a different claim and is labelled as one.
    // ⚠ A spelling equal to the family name is NOT a product row -- it is the
    // family itself, and listing "Microsoft" as a product of Microsoft is noise.
    $famName = $fam['family'] ?? '';
    $prodRows = [];
    foreach ($rows as $r0) {
        $pn = trim((string) ($r0['product'] ?? ''));
        if ($pn === '' || strcasecmp($pn, $famName) === 0) { continue; }
        if (!isset($prodRows[$pn])) {
            $prodRows[$pn] = ['name' => $pn, 'contracts' => 0, 'value' => 0.0,
                              'evidence' => 'contract-name', 'purposes' => []];
        }
        $prodRows[$pn]['contracts']++;
        $prodRows[$pn]['value'] += (float) ($r0['value'] ?? 0);
        $pu = trim((string) ($r0['purpose'] ?? ''));
        if ($pu !== '' && !in_array($pu, $prodRows[$pn]['purposes'], true)) {
            $prodRows[$pn]['purposes'][] = $pu;
        }
    }
    uasort($prodRows, function ($a, $b) { return $b['value'] <=> $a['value']; });
    // ⚠⚠ DISCLOSE THE REMAINDER. This table is a subset by construction -- a
    // contract recorded under the family name alone names no product and so has
    // no row -- and a table that silently sums to less than the tile above it
    // reads as the whole inventory. Microsoft: 22 of 24 contracts carry a
    // product name ($643.3M), 2 do not ($0.3M). Same rule as the folded calendar
    // and the capped notice panel: count before you cap, and say what is missing.
    $prodNamed = 0; $prodNamedValue = 0.0;
    foreach ($prodRows as $_pr) { $prodNamed += $_pr['contracts']; $prodNamedValue += $_pr['value']; }
    $prodUnnamed = (int) ($sum['contracts'] ?? 0) - $prodNamed;
    $prodUnnamedValue = (float) ($sum['value'] ?? 0) - $prodNamedValue;
    // ⚠ The web-estate half is merged HERE and not in the API, because the audit
    // feed is fetched by the controller and the API has never seen it. A
    // component already named by a contract keeps the stronger grade -- the two
    // sources agreeing is not a second product.
    $webProducts = [];
    foreach (($webEstate['components'] ?? []) as $wc) {
        $wn = trim((string) ($wc['name'] ?? ''));
        if ($wn === '') { continue; }
        $dup = false;
        foreach ($prodRows as $k => $_v) {
            if (strcasecmp($k, $wn) === 0) { $dup = true; break; }
        }
        if (!$dup) { $webProducts[] = ['name' => $wn, 'total' => (int) ($wc['total'] ?? 0)]; }
    }
    $hasProductList = count($prodRows) || count($webProducts);

    // ⭐ WHAT ELSE THE CITY BUYS FOR THIS JOB. Derived from the function tag, so
    // it is our own data rather than a new claim -- and it was already one click
    // away behind an unlabelled "see every product the City buys to do this job".
    // ⚠ DESCRIPTIVE, never "alternatives to this". A peer can be the SAME
    // vendor's separate family (Citrix's list leads with Citrix Virtual Apps and
    // Citrix Workspace, which the merge has not joined up), and calling those an
    // alternative to Citrix would be nonsense. What the data supports is "the
    // City also buys these for this job", which is true in every case.
    $peers = $fam['peers'] ?? [];
    $peersTotal = (int) ($fam['peers_total'] ?? 0);
    $peersCapped = $peersTotal > count($peers);
    $peersValue = 0.0;
    foreach ($peers as $pr) { $peersValue += (float) ($pr['value'] ?? 0); }

    // The contents list. Built here so a band that does not render cannot leave a
    // dead anchor in the sidebar.
    $toc = [];
    $toc[] = ['section-maker', 'Who makes it'];
    if ($hasProductList) { $toc[] = ['section-products', 'Products']; }
    if (count($cands) || count($peers)) { $toc[] = ['section-alternatives', 'Alternatives']; }
    $toc[] = ['section-records', 'The City&rsquo;s records'];
    $toc[] = ['section-contracts', 'Contracts'];
    $toc[] = ['section-buyers', 'Agencies and sellers'];
    if (count($notices)) { $toc[] = ['section-notices', 'City Record notices']; }
    $toc[] = ['section-classification', 'How we classified it'];
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-2); padding-bottom: var(--db-space-5);">
        <a href="{{ $licRoute }}" class="db-btn db-btn-ghost db-btn-sm mb-1"><i class="bi bi-arrow-left"></i> Products</a>
        <h1 style="margin-bottom: var(--db-space-1);">{{ $fam['family'] }}</h1>
        {{-- ⚠ THE ANALYSIS IDENTITY. The leaf pages were once left with no marking
             at all, against a "do not remove them" comment at the top of this file,
             and the shared banner was restored here. The owner then asked for
             something more subtle on this page (2026-09-18), so it is the compact
             TAG: same sentence, but the caveat a reader must not miss -- "prompts
             to investigate, not official determinations" -- is on the tag's face
             and the full paragraph opens on hover or tap. The guard accepts either
             carrier and insists the tag's visible text keeps the caveat. --}}
        @include('sub.analysis-tag')

        @if($isGeneric)
            <div class="lic-card is-brandwash mb-3">
                <strong><i class="bi bi-question-circle"></i> Not a product.</strong>
                These are contracts the classifier flagged as licenses but could not name a product for.
                They are grouped here so the volume is visible, not because they are related to each other.
            </div>
        @endif
        {{-- ⚠ No lead sentence any more: it read "across 17 agencies and 32 sellers"
             directly above tiles that say 17 and 32. Two spellings of one figure,
             three lines apart, is how this section came to have numbers that
             disagreed. The generic-family note above stays, because it says
             something the tiles cannot. --}}

        {{-- ================= A. THE HEADER BAND =================
             ⚠⚠ ONE BAND, TWO COLUMNS (owner, 2026-09-18). "Who makes it" was its
             own section below this one, so a reader met the description, then the
             tiles, then scrolled past a rule to learn whose product it is -- three
             facts about the same thing, stacked, with the text-heavy maker card
             alone on a full-width row. They are one header now: the company on the
             left, what the software does on the right, the figures underneath.
             ⚠ The maker keeps `id="section-maker"` so every existing anchor, the
             contents link and the headless checks still resolve. --}}
        <div class="row g-3 mb-1 align-items-stretch" id="section-about">
            <div class="col-lg-5 d-flex order-lg-2" id="section-maker">
            @if($maker)
                <div class="lic-card w-100">
                    <div class="lic-tag">{{ $makerVerb }}</div>
                    <p style="font-size: var(--db-text-lg); margin: var(--db-space-05) 0 var(--db-space-1); line-height: 1.4;">
                        <strong>{{ $maker['maker'] }}</strong>
                        @if(!empty($maker['ticker']))
                            <span class="lic-sub">&middot; listed as {{ $maker['ticker'] }}</span>
                        @endif
                    </p>
                    <div>
                        @if($makerHq)
                            <span class="lic-chip"><i class="bi bi-geo-alt"></i> {{ $makerHq }}</span>
                        @endif
                        @if(!empty($maker['parent']))
                            <span class="lic-chip"><i class="bi bi-diagram-2"></i> Owned by {{ $maker['parent'] }}</span>
                        @endif
                        @if(!empty($maker['formerly']))
                            <span class="lic-chip"><i class="bi bi-arrow-repeat"></i> Formerly {{ $maker['formerly'] }}</span>
                        @endif
                        @if(!empty($maker['website']))
                            <span class="lic-chip"><i class="bi bi-link-45deg"></i>
                                <a href="{{ $maker['website'] }}" rel="noopener nofollow">{{ preg_replace('~^https?://(www\.)?~', '', $maker['website']) }}</a></span>
                        @endif
                    </div>

                    {{-- ⚠⚠ IS THE MAKER A CITY VENDOR? A BLANK ID IS A FINDING, NOT A
                         GAP. Broadcom and Octave are not registered City vendors at
                         all, so every dollar on those lines reaches the maker through
                         a reseller -- which is exactly what a reader looking at
                         "Who sells it" needs to know. --}}
                    {{-- ⚠⚠ THE ONE-LINE ANSWER STAYS VISIBLE; THE DETAIL COLLAPSES.
                         "Is the maker a City vendor?" is a FINDING either way -- Broadcom
                         and Octave are not registered at all, so every dollar on those
                         lines reaches the maker through a reseller -- so the sentence
                         that says which, and the profile link, are on the card's face.
                         The registered address, the revenue band and the Local Law 34
                         pointer are corroborating detail, and they cost the header 100px
                         it needs for the seller and agency rollups the owner asked to see
                         above the fold. --}}
                    <div class="lic-sub lic-rule">
                        @if(!empty($maker['maker_vendor_id']))
                            <i class="bi bi-person-badge"></i>
                            <strong>A registered City vendor.</strong>
                            <a href="{{ route('procurement.vendor', $maker['maker_vendor_id']) }}">See its vendor profile</a>.
                        @else
                            <i class="bi bi-person-badge"></i>
                            <strong>Not a registered City vendor.</strong>
                            The City holds no PASSPort record for {{ $maker['maker'] }}, so every dollar on
                            this product reaches it through the resellers below rather than directly.
                        @endif
                    </div>
                    @if(count($sameMaker))
                        {{-- ⭐ THE CROSS-REFERENCE. The seed already knew Casebuilder and
                             SoundThinking are one company, and that AT&T Vehicle Tracking runs
                             on the platform the City's separate Geotab contracts buy -- and
                             each page stated its own half while neither pointed at the other.
                             ⚠ A LINK, NEVER A MERGE: these families stay separate on purpose,
                             and nothing sums across this row. --}}
                        <div class="lic-sub lic-rule">
                            <i class="bi bi-arrow-left-right"></i>
                            <strong>The City buys {{ count($sameMaker) == 1 ? 'one other product' : count($sameMaker) . ' other products' }} from {{ $maker['maker'] }}</strong>,
                            on separate contracts:
                            @foreach($sameMaker as $smi => $sm)
                                @php
                                    // ⚠ PRECOMPUTED. Written inline this read
                                    // `...another vendor@endif)`, and a Blade directive glued to a
                                    // WORD CHARACTER is not compiled -- only the @endif's partner
                                    // was, and the view died on "unexpected endforeach". The
                                    // documented trap, met again; this file's convention is to
                                    // compose conditional phrases in @php for exactly this reason.
                                    $smNote = (($sm['maker_kind'] ?? '') === 'bundle')
                                        ? ', resold by another vendor' : '';
                                    $smEnd  = $smi < count($sameMaker) - 1 ? ';' : '.';
                                @endphp
                                <a href="{{ route('research.digital-reform.product-family', ['slug' => $sm['slug']]) }}">{{ $sm['family'] }}</a>
                                ({{ $fmtM($sm['value']) }}{{ $smNote }}){{ $smEnd }}
                            @endforeach
                            Counted separately everywhere on this site &mdash; nothing here adds them together.
                        </div>
                    @endif
                    {{-- ONE disclosure for everything corroborating: the editorial note,
                         the PASSPort registration detail, and the provenance.
                         ⚠⚠ A STABLE URL, NEVER A GROUNDING REDIRECT. The AI identity pass
                         cites vertexaisearch redirect links and every one now 404s
                         (measured 2026-09-18) -- a citation that dies reads as evidence and
                         is worse than none.
                         ⚠ ALL OF THIS IS CONTEXT AND PROVENANCE, NOT CAVEAT, which is why it
                         may sit behind a disclosure while the notes elsewhere on this page
                         may not. The claim a reader must not miss -- whether the maker is a
                         City vendor -- is on the card's face above. --}}
                    @if(!empty($maker['why']) || !empty($maker['source_url']) || !empty($mvEntity['address']))
                        <details class="lic-method">
                            <summary>More about this company</summary>
                            <div>
                                @if(!empty($maker['why']))
                                    <p style="margin: 0 0 var(--db-space-1);">{{ $maker['why'] }}</p>
                                @endif
                                @if(!empty($maker['maker_vendor_id']))
                                    @if(!empty($mvEntity['address']))
                                        Registered with the City at {{ $mvEntity['address'] }}.
                                    @endif
                                    @if(!empty($mvEntity['revenue']))
                                        Reported revenue band {{ $mvEntity['revenue'] }}.
                                    @endif
                                    @if(!empty($mvDb['people']))
                                        Its Local Law 34 filing names
                                        {{ count($mvDb['people']) }} {{ count($mvDb['people']) == 1 ? 'person' : 'people' }}
                                        &mdash; officers, owners and lobbyists as declared for City business.
                                        <a href="{{ route('procurement.vendor', $maker['maker_vendor_id']) }}#section-doing-business">See them on the vendor profile</a>,
                                        where the roles carry the filing's own framing.
                                    @endif
                                @endif
                                @if(!empty($maker['source_url']))
                                    <p style="margin: var(--db-space-1) 0 0;">
                                        Identified by hand from
                                        <a href="{{ $maker['source_url'] }}" rel="noopener nofollow">a published source</a>@if(!empty($maker['as_of'])), checked {{ $maker['as_of'] }}@endif.
                                        The contract facts on this page come from the City&rsquo;s own records; who
                                        owns the product does not, and is recorded separately for that reason.
                                    </p>
                                @endif
                            </div>
                        </details>
                    @endif
                </div>
            @else
                {{-- ⚠ A CARD, like the identified state -- otherwise the 794 families
                     with no maker row render a bare paragraph beside a bordered
                     description card, and the header looks broken rather than
                     honest. Same shell, different content. --}}
                <div class="lic-card w-100 lic-sub">
                    <i class="bi bi-question-circle"></i>
                    <strong>Maker not yet identified.</strong>
                    Who makes this product is researched by hand, largest families first, and this one has
                    not been done. The vendors below are who the City <em>pays</em>, which is often a
                    reseller rather than the company that makes the software.
                </div>
            @endif
            </div>
            <div class="col-lg-7 d-flex order-lg-1">
            {{-- ---------- Product summary ---------- --}}
            @if(empty($fam['summary_text']) && !$isGeneric)
            <div class="lic-card w-100">
                <div class="lic-tag">What this software does</div>
                <p style="margin: var(--db-space-05) 0 0; color: var(--db-text-muted); font-style: italic;">
                    Not described. The descriptions New York City recorded on these contracts were too
                    vague to summarise honestly, so nothing is claimed here rather than something invented.
                </p>
            </div>
            @endif
            @if(!empty($fam['summary_text']))
            <div class="lic-card w-100">
                <div class="lic-tag">What this software does</div>
                <p style="font-size: var(--db-text-lg); margin: var(--db-space-05) 0 var(--db-space-1); line-height: 1.3;">{{ $fam['summary_text'] }}</p>
                <details class="lic-method">
                    <summary>How this description was written</summary>
                    <div>
                    @if($fam['summary_curated'] ?? false)
                        {{-- ⚠ Deliberately does NOT say "written by a person". Curated means
                             held fixed and reviewable, not necessarily human-authored -- and a
                             page whose point is checkable claims must not make an unverifiable
                             one about its own provenance. --}}
                        Curated: written by hand into a version-controlled file and never
                        regenerated. Still checkable against the recorded purposes below.
                    @else
                        Summarised by AI <strong>from the descriptions New York City recorded on these
                        contracts</strong> &mdash; listed below &mdash; not from outside knowledge of the
                        product. Check it against them.
                    @endif
                    </div>
                </details>
                {{-- ⚠ THE CHIPS LIVE INSIDE THIS CARD. They sat below it, which left the
                     right column short beside the dense maker card and the header
                     reading as a box next to a gap. Inside, the two cards stretch to
                     the same height and the band reads as one pair. --}}
                @if($classLabel || $capability)
                <div style="margin-top: var(--db-space-2); padding-top: var(--db-space-2); border-top: 1px solid var(--db-border);">
                @if($classLabel)
                    <span class="lic-keychip">
                        <i class="bi bi-tag"></i>
                        <a href="#section-classification">{{ $classLabel }}</a>
                    </span>
                @endif
                @if($capability)
                    <span class="lic-keychip">
                        <i class="bi bi-diagram-3"></i>
                        <a href="{{ route('research.digital-reform.product-capability', ['cap' => $capability]) }}">{{ $capLabel }}</a>
                    </span>
                @endif
                @if($tierLabel)
                    <span class="lic-keychip" title="{{ $tierLabel }}">
                        <i class="bi {{ $tierIcon }}"></i>
                        <a href="#section-classification">{{ $classTier === 'curated' ? 'Reviewed' : ($classTier === 'mixed' ? 'Partly reviewed' : 'Not yet reviewed') }}</a>
                    </span>
                @endif
                </div>
                @endif
            </div>
            @endif
            </div>
        </div>
        {{-- ⭐ THE HEADLINE FIGURES SIT IN THE HEADER (owner, 2026-09-18): the
             product's name, what it is, and what the City has spent on it are one
             glance. `db-stat-grid` stays the anchor the order guard and the
             headless verifier measure the analyst bands against. --}}
        <div class="db-stat-grid mb-1">
            <div class="db-stat">
                <div class="db-stat-label">Contracts</div>
                <div class="db-stat-value">{{ number_format($sum['contracts'] ?? 0) }}</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Current value</div>
                <div class="db-stat-value">{{ $fmtM($sum['value'] ?? 0) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Expiring before 2030</div>
                <div class="db-stat-value">{{ number_format($sum['expiring'] ?? 0) }}</div>
                <div class="db-stat-sub">
                    @if(($sum['expiring'] ?? 0) > 0)
                        <a href="{{ $expLink }}">{{ $fmtM($sum['expiring_value'] ?? 0) }} up for renewal</a>
                    @else
                        None in the review window
                    @endif
                </div>
            </div>
            @if(!empty($sum['per_year']))
            <div class="db-stat">
                <div class="db-stat-label">Cost per year</div>
                <div class="db-stat-value">{{ $fmtM($sum['per_year']) }}</div>
                <div class="db-stat-sub">
                    Annualised over {{ $sum['per_year_basis'] }} of {{ $sum['contracts'] }}
                    contracts with a usable term
                </div>
            </div>
            @endif
            <div class="db-stat">
                <div class="db-stat-label">Agencies</div>
                <div class="db-stat-value">{{ number_format($sum['agencies'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ number_format($sellerTotal) }} sellers</div>
            </div>
        </div>

        {{-- ---------- Who sells it / who buys it, above the fold ----------
             ⚠ A SLICE, NOT A SECOND SUM: `$agencies` and `$vendors` are the same
             value-ranked lists the full tables below render, so these cannot
             disagree with them. Each side names its full total and links down. --}}
        @if(count($topAgencies) || count($topVendors))
        <div class="row g-2 mb-2">
            <div class="col-md-6">
                <div class="lic-card is-compact h-100">
                    <div class="lic-tag">Agencies buying it</div>
                    <table class="db-table lic-mini lic-gap">
                        <tbody>
                        @foreach($topAgencies as $ta)
                            <tr>
                                <td>
                                    <a href="{{ route('agency.procurement', ['name' => $ta['key']]) }}">{{ $ta['key'] }}</a>
                                </td>
                                <td class="lic-num">{{ $fmtM($ta['value']) }}</td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                    <div class="lic-sub lic-gap">
                        @if(count($agencies) > count($topAgencies))
                            The {{ count($topAgencies) }} largest of {{ number_format(count($agencies)) }}.
                        @endif
                        <a href="#section-buyers">All agencies and what each spends.</a>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="lic-card is-compact h-100">
                    <div class="lic-tag">Who sells it</div>
                    <table class="db-table lic-mini lic-gap">
                        <tbody>
                        @foreach($topVendors as $tv)
                            <tr>
                                <td>
                                    @if(!empty($tv['vendor_id']))
                                        <a href="{{ route('procurement.vendor', $tv['vendor_id']) }}">{{ $tv['key'] }}</a>
                                    @else
                                        {{ $tv['key'] }}
                                    @endif
                                </td>
                                <td class="lic-num">{{ $fmtM($tv['value']) }}</td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                    <div class="lic-sub lic-gap">
                        {{-- ⚠ The denominator is the MERGED seller count, the same figure the
                             header and the index both state -- not count($vendors), which is
                             the contract half only and is how this page once read 6 against
                             the index's 32. --}}
                        @php
                            // ⚠ PRECOMPUTED, for the third time in this file today: written
                            // inline the clause ended `...City Record notice@endif.`, and a
                            // Blade directive glued to a WORD CHARACTER is not compiled, so
                            // only the @if's partner was and the view died on "unexpected end
                            // of file". Conditional phrases are composed in @php here.
                            $sellerNoticeClause = $sellerNoticeOnly > 0
                                ? ', of which ' . number_format($sellerNoticeOnly)
                                  . ' appear only on a City Record notice'
                                : '';
                        @endphp
                        @if($sellerTotal > count($topVendors))
                            The {{ count($topVendors) }} largest of {{ number_format($sellerTotal) }}{{ $sellerNoticeClause }}.
                        @endif
                        <a href="#section-buyers">All sellers.</a>
                    </div>
                </div>
            </div>
        </div>
        @endif


        <div class="row">
            {{-- Contents sidebar. ⚠ px-0 px-md-3 on the content column: a sidebar
                 that is d-none on mobile still costs mobile width through the
                 gutter, which cost 312px on the capital profile. --}}
            <div class="col-md-2 d-none d-md-block">
                <nav class="db-toc">
                    <div class="db-toc-title">Contents</div>
                    @foreach($toc as $t)<a href="#{{ $t[0] }}">{!! $t[1] !!}</a>@endforeach
                </nav>
            </div>
            <div class="col-md-10 px-0 px-md-3">



        {{-- ================= C. PRODUCTS IN THIS FAMILY ================= --}}
        @if($hasProductList)
        <div class="lic-band" id="section-products">
            <h2 class="lic-band-title"><i class="bi bi-box-seam"></i> Products in this family</h2>
            <p class="lic-sub">
                A family is a group of contracts bought under one vendor&rsquo;s name, so what the
                City actually gets is spread across the individual products below.
                <strong>Each row says how we know it</strong> &mdash; the grades are not equally
                strong, and a product the City names on a contract is a firmer thing than one an
                outside scan observed running.
            </p>
            @if(count($prodRows))
            <div class="db-table-wrap mb-3">
                <table class="db-table db-dt">
                    <thead><tr><th>Product</th><th>How we know</th>
                        <th class="lic-num">Contracts</th><th class="lic-num">Value</th></tr></thead>
                    <tbody>
                    @foreach($prodRows as $pRow)
                        <tr>
                            <td>
                                <strong>{{ $pRow['name'] }}</strong>
                                @if(count($pRow['purposes']))
                                    <span class="lic-prod">{{ implode('; ', array_slice($pRow['purposes'], 0, 3)) }}</span>
                                @endif
                            </td>
                            <td class="lic-sub">
                                <span class="db-badge db-badge-success">named on a contract</span>
                            </td>
                            <td class="lic-num">{{ number_format($pRow['contracts']) }}</td>
                            <td class="lic-num" data-order="{{ (int) $pRow['value'] }}">{{ $fmtM($pRow['value']) }}</td>
                        </tr>
                    @endforeach
                    </tbody>
                </table>
            </div>
            @if($prodUnnamed > 0)
                <p class="lic-sub">
                    {{ number_format($prodNamed) }} of {{ number_format($sum['contracts'] ?? 0) }}
                    contracts name a product above ({{ $fmtM($prodNamedValue) }}).
                    The other {{ number_format($prodUnnamed) }}
                    ({{ $fmtM($prodUnnamedValue) }}) {{ $prodUnnamed == 1 ? 'is' : 'are' }}
                    recorded under the family name alone, so the City&rsquo;s own records do not
                    say which product {{ $prodUnnamed == 1 ? 'it covers' : 'they cover' }}.
                </p>
            @endif
            @else
                <p class="lic-sub">
                    Every contract in this family is recorded under the family name alone, so the
                    City&rsquo;s own records do not say which individual products it covers.
                </p>
            @endif

            @if(count($webProducts))
            <div class="mb-3">
                <div class="lic-tag">Also seen running on City websites</div>
                <div class="lic-gap">
                    @foreach($webProducts as $wp)
                        <span class="lic-chip">{{ $wp['name'] }}
                            <strong>{{ number_format($wp['total']) }}</strong></span>
                    @endforeach
                </div>
                <div class="lic-caveat">
                    {{-- ⚠ A DIFFERENT KIND OF CLAIM, and it keeps its own framing. This
                         is an independent audit's inference about what is running on
                         public hosts, not a record of a purchase, and it cannot be
                         priced -- which is why these carry an observation count and no
                         money. The panel further down carries the hosts and the
                         evidence grade for each one. --}}
                    Detected by an independent scan of public City websites, not recorded on any
                    contract &mdash; so these say what appears to be running, never what was bought
                    or what it cost. <a href="#section-records">The hosts and the evidence for each
                    are further down the page.</a>
                </div>
            </div>
            @endif
        </div>{{-- /section-products --}}
        @endif

        {{-- ================= D. WHAT ELSE DOES THIS JOB ================= --}}
        @if(count($cands) || count($peers))
        <div class="lic-band" id="section-alternatives">
            <h2 class="lic-band-title"><i class="bi bi-arrow-left-right"></i> Alternatives</h2>

        {{-- ---------- What the City already buys for this job ----------
             ⚠ THE STRONGEST BAND HERE, because it is the only one that is our own
             measurement rather than a suggestion: these are products the City is
             already paying for, tagged with the same function. --}}
        @if(count($peers))
            <div class="db-table-wrap mb-3">
                <div class="px-3 pt-3">
                    <h2 class="lic-h2">What else the City buys for this job</h2>
                    <p class="lic-caveat mb-0">
                        Products carrying the same function tag,
                        <strong>{{ $capLabel }}</strong>. These are purchases the City
                        already makes, not suggestions &mdash; but a shared function is not
                        proof that one could replace another, and a product here may be a
                        different part of the same vendor&rsquo;s range.
                        @if($peersCapped)
                            Showing the {{ number_format(count($peers)) }} largest of
                            {{ number_format($peersTotal) }}.
                        @endif
                        @if($capability)
                            <a href="{{ route('research.digital-reform.product-capability', ['cap' => $capability]) }}">See the whole function.</a>
                        @endif
                    </p>
                </div>
                <table class="db-table db-dt">
                    <thead><tr><th>Product</th><th class="lic-num">Value</th>
                        <th class="lic-num">Contracts</th><th class="lic-num">Agencies</th></tr></thead>
                    <tbody>
                    @foreach($peers as $pr)
                        <tr>
                            <td>
                                @if(!empty($pr['slug']))
                                    <a href="{{ route('research.digital-reform.product-family', ['slug' => $pr['slug']]) }}">{{ $pr['key'] }}</a>
                                @else
                                    {{ $pr['key'] }}
                                @endif
                            </td>
                            <td class="lic-num" data-order="{{ (int) ($pr['value'] ?? 0) }}">{{ $fmtM($pr['value'] ?? 0) }}</td>
                            <td class="lic-num">{{ number_format($pr['contracts'] ?? 0) }}</td>
                            <td class="lic-num">{{ number_format($pr['agencies'] ?? 0) }}</td>
                        </tr>
                    @endforeach
                    </tbody>
                </table>
            </div>
        @endif

        {{-- ---------- Replacement candidates ---------- --}}
        @if(count($cands))
            <div class="db-table-wrap mb-3">
                <div class="px-3 pt-3">
                    <h2 class="lic-h2">Possible open-source replacements</h2>
                    <p class="lic-sub mb-0">
                        From European public-sector open-source catalogues.
                        <strong>Suggestions, not recommendations</strong> &mdash; nothing here has been
                        checked against this agency's requirements, integrations or support needs.
                        @if(!empty($catMeta['generated_at']))
                            Catalogue data as of {{ $catMeta['generated_at'] }}.
                        @endif
                    </p>
                </div>
                <table class="db-table db-dt">
                    <thead><tr><th>Candidate</th><th>Confidence</th><th>Kind</th><th class="lic-num">Gov adopters</th><th>License</th></tr></thead>
                    <tbody>
                    @foreach($cands as $cd)
                        @php
                            $isNone = ($cd['candidate_kind'] ?? '') === 'none-found' || empty($cd['candidate']);
                            $confBadge = ['strong' => 'db-badge-success', 'partial' => 'db-badge-warning',
                                          'adjacent' => 'db-badge-neutral'][$cd['confidence'] ?? ''] ?? 'db-badge-neutral';
                        @endphp
                        <tr>
                            <td>
                                @if($isNone)
                                    <span class="lic-sub"><em>No known open-source alternative</em></span>
                                @elseif(!empty($cd['url']))
                                    <a href="{{ $cd['url'] }}" rel="noopener nofollow"><strong>{{ $cd['candidate'] }}</strong></a>
                                @else
                                    <strong>{{ $cd['candidate'] }}</strong>
                                @endif
                                @if(!empty($cd['why']))
                                    <span class="lic-prod" style="white-space: normal;">{{ $cd['why'] }}</span>
                                @endif
                            </td>
                            <td>
                                @if(!$isNone)
                                    <span class="db-badge {{ $confBadge }}">{{ $cd['confidence'] }}</span>
                                @endif
                            </td>
                            <td class="lic-sub">{{ $isNone ? 'searched, not found' : ($cd['candidate_kind'] ?? '') }}</td>
                            <td class="lic-num">{{ $cd['gov_adopters'] ?? '' }}</td>
                            {{-- ⚠ 'licence' IS A DATA KEY (the DB column on
                                 license_replacement_candidate), NOT PROSE. The US-spelling
                                 pass blind-renamed it and this cell silently rendered
                                 empty for every candidate — `?? ''` made the breakage
                                 invisible. Test-pinned now. --}}
                            <td class="lic-sub">{{ $cd['licence'] ?? '' }}</td>
                        </tr>
                    @endforeach
                    </tbody>
                </table>
            </div>
        @endif
        </div>{{-- /section-alternatives --}}
        @endif

        {{-- ================= E. THE CITY'S RECORDS ================= --}}
        <div class="lic-band" id="section-records">
            <h2 class="lic-band-title"><i class="bi bi-file-earmark-text"></i> The City&rsquo;s records</h2>

        {{-- ---------- How they are bought ----------
             ⚠ WAS A FIVE-ROW TABLE. Reported, not judged, and a table with its own
             heading for three numbers is furniture. The chips carry the same
             figures; the caveat that made the table worth reading is kept. --}}
        @if(count($methods))
        <div class="mb-3">
            <div class="lic-tag">Bought through these routes</div>
            <div class="lic-gap">
                @foreach($methods as $m)
                    <span class="lic-chip">{{ $m['key'] }}
                        <strong>{{ number_format($m['contracts']) }}</strong>
                        &middot; {{ $fmtM($m['value']) }}</span>
                @endforeach
            </div>
            <div class="lic-caveat">
                Reported, not judged. Intergovernmental GSA/OGS means riding an
                already-competed schedule; a large Sole Source is the line worth asking about.
            </div>
        </div>
        @endif

        {{-- ---------- Every contract, with its own calendar ---------- --}}
        <div class="db-table-wrap mb-3" id="section-contracts">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-list-ul"></i> All {{ number_format(count($rows)) }} contracts</h2>
                {{-- ⚠ THE CALENDAR, AS A SENTENCE. All three buckets are named --
                     ending in future years, already ended, and no end date
                     recorded -- because a calendar that silently drops rows reads
                     as the whole inventory. The per-contract dates are in the Ends
                     column beside each row, which is where a reader looks for them. --}}
                <p class="lic-sub mb-0">
                    @if($futureCount > 0)
                        {{ number_format($futureCount) }} of {{ number_format($sum['contracts'] ?? 0) }}
                        {{ $futureCount == 1 ? 'contract ends' : 'contracts end' }} in a future year.
                    @endif
                    @if($endedCount > 0)
                        {{ number_format($endedCount) }}
                        {{ $endedCount == 1 ? 'has' : 'have' }} already ended
                        ({{ $fmtM($endedValue) }}), and still count toward the figures above.
                    @endif
                    @if($noEndDate > 0)
                        {{ number_format($noEndDate) }}
                        {{ $noEndDate == 1 ? 'has' : 'have' }} no usable end date recorded.
                    @else
                        Every contract here records an end date.
                    @endif
                </p>
            </div>
            <table class="db-table db-dt">
                <thead>
                    <tr>
                        <th>Contract</th><th>Product</th><th>Agency</th><th>Vendor</th>
                        <th class="lic-num">Value</th><th>Ends</th><th>Route</th>
                    </tr>
                </thead>
                <tbody>
                @foreach($rows as $r)
                    <tr>
                        <td>
                            <a href="{{ route('procurement.contract', $r['contract_id']) }}">{{ $r['contract_id'] }}</a>
                            @if(!empty($r['contract_title']))
                                <span class="lic-prod">{{ $r['contract_title'] }}</span>
                            @endif
                        </td>
                        <td>
                            {{ $r['product'] ?? '' }}
                            @if(!empty($r['purpose']))
                                <span class="lic-prod">{{ $r['purpose'] }}</span>
                            @endif
                        </td>
                        <td>
                            @if(!empty($r['agency']))
                                <a href="{{ route('agency.procurement', ['name' => $r['agency']]) }}">{{ $r['agency'] }}</a>
                            @endif
                        </td>
                        <td>
                            @if(!empty($r['vendor_id']))
                                <a href="{{ route('procurement.vendor', $r['vendor_id']) }}">{{ $r['vendor_name'] }}</a>
                            @else
                                {{ $r['vendor_name'] ?? '' }}
                            @endif
                        </td>
                        <td class="lic-num">{{ $fmtM($r['current_amount'] ?: $r['award_amount']) }}</td>
                        {{-- ⚠⚠ ONE COLUMN, NOT TWO. The folded calendar first added an
                             `Ends` column beside the existing `Term`, which said the
                             same thing twice and cost the table the width its agency
                             and vendor names need. The end YEAR leads because that is
                             what a reader scans and what the calendar answered; the
                             full window is under it; and `data-order` sorts the column
                             by the end DATE, since the visible text is not monotonic
                             in it. ⚠ An em dash, never a year invented from a blank -- a
                             contract with no recorded end date is counted in the
                             sentence above the table. --}}
                        <td data-order="{{ $r['end_date'] ?? '' }}">
                            {{ !empty($r['end_year']) ? $r['end_year'] : '—' }}
                            @if($r['expiring'] ?? false)
                                <span class="db-badge db-badge-warning">expiring</span>
                            @endif
                            @if(!empty($r['start_date']) || !empty($r['end_date']))
                                <span class="lic-prod">{{ $r['start_date'] ?? '' }} to {{ $r['end_date'] ?? '' }}</span>
                            @endif
                        </td>
                        <td class="lic-sub">{{ $r['procurement_method'] ?? '' }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </div>

        {{-- ---------- Agencies and sellers ---------- --}}
        <div class="row mb-3" id="section-buyers">
            <div class="col-lg-6">
                <div class="db-table-wrap">
                    <div class="px-3 pt-3">
                        <h2 class="lic-h2"><i class="bi bi-building"></i> Agencies buying it</h2>
                    </div>
                    <table class="db-table db-dt">
                        <thead><tr><th>Agency</th><th class="lic-num">Contracts</th><th class="lic-num">Value</th></tr></thead>
                        <tbody>
                        @foreach($agencies as $a)
                            <tr>
                                <td><a href="{{ route('agency.procurement', ['name' => $a['key']]) }}">{{ $a['key'] }}</a></td>
                                <td class="lic-num">{{ number_format($a['contracts']) }}</td>
                                <td class="lic-num">{{ $fmtM($a['value']) }}</td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="col-lg-6">
                <div class="db-table-wrap">
                    <div class="px-3 pt-3">
                        <h2 class="lic-h2"><i class="bi bi-briefcase"></i> Who sells it</h2>
                        {{-- ⚠⚠ ONE LIST, TWO KINDS OF EVIDENCE. This heading used to
                             cover contract vendors only and read 6 for Microsoft
                             while the index cell for the same family read 32. Both
                             counts now come from the same merge. --}}
                        <p class="lic-sub mb-0">
                            A reseller often appears here rather than the software maker.
                            @if($sellerNoticeOnly > 0)
                                {{ number_format($sellerTotal) }} sellers in all:
                                {{ number_format(count($vendors)) }} hold a contract in this set and
                                {{ number_format($sellerNoticeOnly) }} appear only as the awarded
                                vendor on a City Record notice naming this product.
                            @endif
                        </p>
                    </div>
                    <table class="db-table db-dt">
                        <thead><tr><th>Vendor</th><th class="lic-num">Contracts</th><th class="lic-num">Value</th></tr></thead>
                        <tbody>
                        @foreach($vendors as $v)
                            <tr>
                                <td>
                                    @if(!empty($v['vendor_id']))
                                        <a href="{{ route('procurement.vendor', $v['vendor_id']) }}">{{ $v['key'] }}</a>
                                    @else
                                        {{ $v['key'] }}
                                        <span class="lic-sub" title="This name does not resolve to exactly one PASSPort supplier id, so it is not linked rather than linked to a guess">(no unique profile)</span>
                                    @endif
                                </td>
                                <td class="lic-num">{{ number_format($v['contracts']) }}</td>
                                <td class="lic-num">{{ $fmtM($v['value']) }}</td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                    @if(count($noticeOnlyNames))
                    <div class="px-3 pb-3">
                        <div class="lic-tag lic-gap">Named on a notice, no contract here</div>
                        <div class="lic-gap">
                            @foreach($noticeOnlyNames as $non)
                                <span class="lic-chip">{{ $non }}</span>
                            @endforeach
                        </div>
                        <div class="lic-sub lic-gap">
                            {{-- ⚠ A weaker claim than a paid relationship, and stated as one.
                                 These have no contracts or value column because they hold
                                 neither in this set; rendering a 0 would be a claim the
                                 City did not make. --}}
                            These were named as the awarded vendor on a City Record notice mentioning
                            this product, but hold no contract in this license set &mdash; so they carry
                            no figures here.
                            @if($noticeOnlyHidden > 0)
                                Showing {{ number_format(count($noticeOnlyNames)) }} of
                                {{ number_format($sellerNoticeOnly) }}.
                            @endif
                        </div>
                    </div>
                    @endif
                </div>
            </div>
        </div>

        {{-- City Record notices naming this product --}}
        @if(count($notices))
        <div class="db-table-wrap mb-3" id="section-notices">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-newspaper"></i> City Record notices mentioning it</h2>
                <p class="lic-sub mb-0">Notices whose text names this product.
                    <strong>A mention is not a purchase</strong> - a notice may
                    name a product in a hearing agenda, a background section or a
                    list of requirements, so treat these as leads to read rather
                    than as procurement activity.
                    <strong>Where an amount is shown it is the whole
                    notice&rsquo;s award, not this product&rsquo;s share</strong> -
                    the City states one figure per notice, and a notice naming
                    this product may cover much more. Only award-type notices
                    carry a vendor and an amount at all; a dash means the notice
                    does not state one.
                    @if($noticesCapped)
                        Showing {{ number_format(count($notices)) }} of
                        {{ number_format($noticesTotal) }} - those stating an
                        award amount first, largest first, then the most recent.
                    @endif
                </p>
            </div>
            <table class="db-table db-dt">
                <thead><tr>
                    <th>Notice</th><th>Type</th><th>Agency</th>
                    <th>Awarded to</th><th class="lic-num">Amount</th>
                    <th>Contract</th><th>Date</th>
                </tr></thead>
                <tbody>
                @foreach($notices as $n)
                    @php
                        // ⚠ Precomputed: a Blade directive glued to a word
                        // character is not compiled, and these are echoed escaped.
                        // ⚠ `amount` is NULL, never 0, when the source is blank —
                        // an em dash says "not stated", where "$0.00" would be a
                        // claim the City did not make. Only award-type notices
                        // carry these two fields at all.
                        $nAmt = isset($n['amount']) && $n['amount'] !== null
                              ? '$' . number_format((float) $n['amount']) : '—';
                        $nVendor = $n['vendor'] !== '' ? $n['vendor'] : '—';
                    @endphp
                    <tr>
                        <td><a href="{{ $n['url'] }}" target="_blank" rel="noopener noreferrer">{{ $n['title'] }}</a></td>
                        <td>{{ $n['type'] }}</td>
                        <td>{{ $n['agency'] }}</td>
                        <td>{{ $nVendor }}</td>
                        <td class="lic-num" data-order="{{ $n['amount'] ?? 0 }}">{{ $nAmt }}</td>
                        <td>
                            @if($n['ctr_id'] !== '')
                                <a href="/procurement/contract/{{ $n['ctr_id'] }}">{{ $n['pin'] !== '' ? $n['pin'] : 'Contract' }}</a>
                            @elseif($n['pin'] !== '')
                                {{ $n['pin'] }}
                            @else
                                —
                            @endif
                        </td>
                        <td>{{ $n['date'] }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </div>
        @endif

        @include('procurement.partials.web-estate-panel')
        </div>{{-- /section-records --}}

        {{-- ================= F. HOW WE CLASSIFIED IT =================
             ⚠ THE INTERPRETATION LAYER, BELOW THE DATA IT INTERPRETS. Everything
             in this band used to sit above the first spend figure on the page.
             Nothing here is hidden: no block moved behind a click, and every
             caveat that was visible before is visible here. --}}
        <div class="lic-band" id="section-classification">
            <h2 class="lic-band-title"><i class="bi bi-clipboard-data"></i> How we classified it</h2>

        {{-- ---------- What kind of purchase ---------- --}}
        @if($classLabel)
        <div class="lic-card mb-3">
            <div class="lic-tag">What kind of purchase is this</div>
            <p style="margin: var(--db-space-05) 0 var(--db-space-1); font-size: var(--db-text-lg);"><strong>{{ $classLabel }}</strong></p>
            @if($leverLabel)
                <p style="margin: 0 0 var(--db-space-1);">{{ $leverLabel }}</p>
            @endif
            @if($capability)
                <div class="lic-sub" style="margin-bottom: 6px;">
                    Function:
                    <a href="{{ route('research.digital-reform.product-capability', ['cap' => $capability]) }}">{{ $capLabel }}</a>
                    &mdash; see every product the City buys to do this job.
                </div>
            @endif
            @if($rateCard)
                <div class="lic-sub lic-rule">
                    <strong>Published list price:</strong>
                    ${{ $rateCard['list_price_usd'] }} {{ $rateCard['unit'] }}
                    (<a href="{{ $rateCard['source_url'] }}" rel="noopener nofollow">source</a>, as of {{ $rateCard['as_of'] }}).
                    <br>
                    <i class="bi bi-exclamation-triangle"></i>
                    Shown beside the spend, deliberately <strong>not divided into it</strong>: no seat
                    or site count exists in the contract data, so a per-unit figure would require
                    inventing the denominator.
                    @if(!empty($rateCard['note']))
                        <span>{{ $rateCard['note'] }}</span>
                    @endif
                </div>
            @endif
            @if(count($pipeVehicles))
                {{-- ⚠⚠ THE CASE THIS EXISTS FOR: Salesforce reads $3.1M in licences
                     on this page while a $75M CITYWIDE SALESFORCE PURCHASING
                     CONTRACT sits unregistered and invisible to the whole
                     analysis. Matched on the agreement TITLE and the title is
                     shown, so the reader can judge the link rather than trust it. --}}
                <div class="lic-sub lic-rule">
                    <strong><i class="bi bi-hourglass"></i> Not yet registered, and not counted above:</strong>
                    @foreach($pipeVehicles as $pv)
                        <div class="lic-gap">
                            {{ $pv['contract_title'] }} &mdash;
                            <strong>{{ $fmtM($pv['value']) }}</strong> ceiling,
                            {{ $pv['vendor_name'] }}, {{ $pv['agency'] }} ({{ $pv['status'] }}).
                        </div>
                    @endforeach
                    <div class="lic-gap">
                        <i class="bi bi-exclamation-triangle"></i>
                        Matched because the agreement's title names this product. It carries no contract
                        number yet, so it was never classified and is absent from every figure on this
                        page &mdash; and a ceiling is a spending limit, not a purchase.
                        <a href="{{ $licRoute }}#pipeline">More on pipeline agreements.</a>
                    </div>
                </div>
            @endif
            @if($tierLabel)
                {{-- ⚠ Deliberately does NOT say "written by a person". Curated means
                     held fixed and reviewable, not necessarily human-authored -- the
                     same wording discipline the summary block uses, for the same
                     reason: a page whose point is checkable claims must not make an
                     unverifiable one about its own provenance. --}}
                <div class="lic-sub lic-gap">
                    <i class="bi {{ $tierIcon }}"></i> {{ $tierLabel }}
                    {{-- ⚠⚠ COMPUTED. This sentence was a typed "the largest 20 product
                         families — 88.0% of the value" until 2026-09-18; see the
                         comment at the top of this file. --}}
                    @if($classTier !== 'curated' && $reviewedLine !== '')
                        {{ $reviewedLine }}
                    @endif
                </div>
            @endif
            @if(!empty($fam['class_why']))
                <div class="lic-sub">{{ $fam['class_why'] }}</div>
            @endif
            @if($classMixed)
                {{-- ⚠ THE POINT OF THE PRODUCT GRAIN. This family holds more than one
                     kind of purchase, so more than one lever applies. Before this
                     block existed the family's dominant class spoke for all of it,
                     and $68.9M of Microsoft support was being asked whether an
                     open-source substitute existed. --}}
                <div class="lic-sub lic-rule">
                    <strong><i class="bi bi-diagram-2"></i>
                    This family is not all one kind of purchase.</strong>
                    Each part carries its own question:
                    <table class="db-table db-dt lic-gap">
                        <thead>
                            <tr><th>Part of this family</th><th class="lic-num">Value</th>
                                <th class="lic-num">Share</th><th>The question to ask</th></tr>
                        </thead>
                        <tbody>
                        @foreach($classMix as $cm)
                            @php
                                $cmKey   = $cm['key'] ?? '';
                                $cmLabel = $classWords[$cmKey] ?? ($cmKey === '(unclassified)' ? 'Not yet classified' : $cmKey);
                                $cmLever = $leverWords[$cm['lever'] ?? ''] ?? '';
                                $cmShare = $famValue > 0 ? round(((float) $cm['value']) / $famValue * 100, 1) : 0;
                                $cmProds = $cm['products'] ?? [];
                                // Per-part provenance: within one family a curated product
                                // override can sit beside an auto family answer, so the
                                // header's tier does not speak for every row here.
                                $cmTier = $cm['tier'] ?? '';
                                $cmTierWord = ['curated' => 'reviewed', 'auto' => 'not reviewed',
                                               'mixed' => 'partly reviewed'][$cmTier] ?? '';
                            @endphp
                            <tr>
                                <td>
                                    <strong>{{ $cmLabel }}</strong>
                                    @if($cmTierWord)
                                        <span class="lic-sub">&middot; {{ $cmTierWord }}</span>
                                    @endif
                                    @if(!empty($cmProds))
                                        <div class="lic-sub">{{ implode(', ', $cmProds) }}</div>
                                    @endif
                                </td>
                                <td class="lic-num">{{ $fmtM($cm['value'] ?? 0) }}</td>
                                <td class="lic-num">{{ $cmShare }}%</td>
                                <td class="lic-sub">{{ $cmLever }}</td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                    <div class="lic-gap">
                        The rating below, where shown, applies to the
                        <strong>{{ $classLabel }}</strong> part only.
                    </div>
                </div>
            @endif
            @if(!$showRating)
                <div class="lic-sub lic-gap">
                    <i class="bi bi-info-circle"></i>
                    No build-vs-buy rating is shown for this class, because "could the City build
                    this itself?" is the wrong question here &mdash; and answering it anyway is how
                    infrastructure spend became invisible in this analysis.
                </div>
            @endif
        </div>
        @endif

        {{-- ---------- Replaceability (software licenses only) ---------- --}}
        @if(($rep['rated'] ?? 0) && $showRating)
        {{-- ⚠ THE ID IS LOAD-BEARING FOR THE HEADLESS CHECK. A text scan for this
             block's heading is satisfied by the sentence ABOVE that explains why
             the block is correctly ABSENT for a non-software class -- it quotes
             the same question. Asserting on the element is the only form that can
             tell the block from its own explanation. --}}
        <div class="lic-card is-brandwash mb-3" id="bvb-rating">
            <div class="lic-tag">Could the City build this itself?</div>
            <p style="margin: var(--db-space-05) 0 var(--db-space-1);">
                <strong style="font-size: var(--db-text-lg);">{{ $repLabel }}</strong>
                <span class="lic-sub">{{ $repSpread }}</span>
            </p>
            @if($rep['mixed'] ?? false)
                <p class="lic-sub mb-0">
                    <i class="bi bi-exclamation-triangle"></i>
                    <strong>The classifier rated this product inconsistently across its own
                    contracts.</strong> That is a reason to distrust the rating for this product
                    specifically, not just in general &mdash; 64 of 435 families show the same
                    disagreement.
                </p>
            @endif
            <p class="lic-sub mb-0 lic-gap">
                <i class="bi bi-exclamation-triangle"></i> This is the least reliable judgement on the site: two models agreed on it only
                <strong>75%</strong> of the time, against 98% for "is this a tech contract".
                Read it as a prompt to look, never as a conclusion.
            </p>
        </div>
        @endif

        {{-- ---------- The merge evidence ---------- --}}
        @if(count($products))
        <div class="mb-3">
            <div class="lic-sub" style="text-transform: uppercase; letter-spacing: var(--db-tracking-wide);">
                Bought under these names
                @if($curated)
                    <span title="Merged by the curated mapping"><i class="bi bi-link-45deg"></i> curated merge</span>
                @endif
            </div>
            @foreach($products as $p)
                <span class="lic-chip">{{ $p }}</span>
            @endforeach
            @if($mergedNote)
                <div class="lic-sub lic-gap">
                    {{ $mergedNote }}. If any of these is not the same product, the grouping is wrong
                    and belongs in the curated mapping file, not here.
                </div>
            @endif
        </div>
        @endif

        @if(count($purposes))
        <div class="mb-3">
            <div class="lic-tag">What the contracts themselves say it is for</div>
            <ul class="lic-sub" style="margin: var(--db-space-05) 0 0; padding-left: 1.1rem; columns: 2;">
                @foreach($purposes as $p)
                    <li>{{ $p }}</li>
                @endforeach
            </ul>
        </div>
        @endif

        {{-- ⚠ SHRUNK 2026-09-18: the Analysis tag in the header now carries the
             "interpretation layer / prompts to investigate" sentence this note used to
             repeat. What survives is what the tag does NOT say -- the measured
             agreement rate, which is the figure a reader weighs the page against and
             which a guard pins. --}}
        <p class="lic-caveat">
            License detection is AI-derived and unreviewed: two models agreed
            <strong>92%</strong> on a sample, so roughly 1 contract in 12 may not belong here.
            One row per contract, valued at current value where set. Vendors are linked only where
            the name resolves to exactly one PASSPort supplier record.
        </p>
        </div>{{-- /section-classification --}}

            </div>{{-- /col-md-9 --}}
        </div>{{-- /row --}}
    </div>


</div>
@endsection
