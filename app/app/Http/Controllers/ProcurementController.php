<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\DatabookAPI;

use App\Custom\Breadcrumbs;

class ProcurementController extends Controller
{
    /* ─────────────────────────────────────────────────────────────────────────
       The Digital Services section's table standard: 10 rows a page, sortable.
       Owned HERE rather than left to the API's own defaults, because it is a
       PRESENTATION decision and the controller is what renders the presentation
       — and because naming it once stops the three server-paginated tables
       drifting apart again (they were 25/25/25 with no constant anywhere).

       ⚠ THE ALL-TECHNOLOGY INDEX IS DELIBERATELY NOT 10, and the reason is not
       taste. It pages over 4,393 contracts, so 10 a page turns 176 crawlable
       URLs into 440 — on the exact path that 504'd the whole site for four days
       in August (a distributed crawler holding every php-fpm worker) and that
       still carries a 1r/s nginx cap. The shared cache made each page cheap, so
       this is a margin rather than a fix; 25 keeps the margin. Owner decision
       2026-09-15.
       ───────────────────────────────────────────────────────────────────────── */
    private const SECTION_PAGE = 10;
    // ⚠ 10 since 2026-09-23, like every other table in the section (owner). It
    // was held at 25 because a smaller page multiplies the URLs a crawler can walk
    // on the path that 504'd the site; the nginx referer bounce (#427) now sends
    // referer-less query URLs on this page to the bare page before PHP runs.
    private const ALL_CONTRACTS_PAGE = 10;
    // Rows-per-page choices the Renewal Review Queue offers. ⚠ A closed list,
    // never a free integer: every value is a distinct cache key, and a free
    // parameter is a crawler-minted cache entry per number.
    private const QUEUE_PAGE_SIZES = [10, 25, 50, 100];
    // The export fetches the whole filtered queue in one request; the API caps
    // a page at this size, which comfortably exceeds the ~650-row window.
    private const QUEUE_EXPORT_LIMIT = 1000;

    // ⚠ ONE vocabulary for the review flags, read by the Contracts page's flag
    // mix AND the Renewal Review Queue. Two copies of this list is how a flag
    // gets renamed on one page and not the other.
    private const QUEUE_FLAGS = [
        'build_your_own'       => ['label' => 'Build-your-own candidate',               'cls' => 'db-badge-info',    'icon' => 'bi-robot'],
        // The lever a non-software-licence purchase actually has: asking "could we
        // build this?" of hosting or a support tier answers "no" and hides the money.
        'class_lever'          => ['label' => 'Different lever (price, tier, content)', 'cls' => 'db-badge-info',    'icon' => 'bi-tags'],
        'underused'            => ['label' => 'Underused (shelfware)',                  'cls' => 'db-badge-danger',  'icon' => 'bi-box-seam'],
        // Sole source or negotiated acquisition only (owner, 2026-09-24) — see
        // NONCOMPETITIVE_REVIEW_METHODS in routers/oce.py. The key is unchanged so
        // shared `expiring_flag=non_competitive` links keep working.
        'non_competitive'      => ['label' => 'Sole source or negotiated',              'cls' => 'db-badge-warning', 'icon' => 'bi-shield-exclamation'],
        'renewal_chain'        => ['label' => 'Renewal chain',                          'cls' => 'db-badge-warning', 'icon' => 'bi-arrow-repeat'],
        'scope_growth'         => ['label' => 'Scope grew over award',                  'cls' => 'db-badge-neutral', 'icon' => 'bi-graph-up-arrow'],
        'high_value_near_term' => ['label' => 'High value, near-term',                  'cls' => 'db-badge-danger',  'icon' => 'bi-cash-stack'],
        'vendor_lock_in'       => ['label' => 'Vendor lock-in',                         'cls' => 'db-badge-neutral', 'icon' => 'bi-link-45deg'],
    ];

    // Every query parameter that belongs to the queue. A Contracts-page URL
    // carrying one of these is an old queue link and is sent to the queue.
    private const QUEUE_PARAMS = ['expiring_flag', 'expiring_year', 'expiring_agency', 'expiring_method',
        'expiring_min', 'expiring_sort', 'expiring_order', 'expiring_page', 'expiring_category',
        'expiring_license', 'expiring_buildbuy', 'expiring_shownontech', 'expiring_product',
        'expiring_limit'];

    public function index(Request $request)
    {
        // OCE Parquet queries can take 30-90s; nginx fastcgi_read_timeout must be >= this
        $stats = DatabookAPI::reqOCE('/oce/dashboard/stats', 90);
        
        // Graceful fallback if API times out or fails
        if (!$stats || !is_array($stats)) {
            $stats = [
                'contracts' => 0, 'vendors' => 0, 'solicitations' => 0,
                'agencies' => 0, 'spending' => 0, 'awarded' => 0,
                'charts' => ['time' => ['labels' => [], 'values' => []],
                             'agencies' => ['labels' => [], 'values' => []],
                             'vendors' => ['labels' => [], 'values' => []],
                             'industries' => ['labels' => [], 'values' => []],
                             'methods' => ['labels' => [], 'values' => []]],
            ];
        }
        
        // Capital mini-dashboard aggregates — precomputed homepage stats (NYC
        // Capital Projects Database), the same source /projects/capital uses. Fast
        // (cached); falls back to the bundled globStats.json if the API is down.
        $globStats = DatabookAPI::reqOCE('/pipeline/globstats', 15);
        if (!$globStats || !is_array($globStats)) {
            $fallback = public_path('data/globStats.json');
            $globStats = file_exists($fallback) ? (json_decode(file_get_contents($fallback), true) ?: []) : [];
        }

        // Actual capital spending (Checkbook 'Capital Contracts' payments) by fiscal
        // year — last 10 complete FYs — for the capital spending chart. Cached +
        // pre-warmed on the API side; empty-safe if unavailable.

        return view('procurement.index', [
            'pagetitle' => "Procurement Dashboard - Databook",
            'stats' => $stats,
            'globStats' => $globStats,
            // ⚠⚠ EVERY KEY THE VIEW READS MUST BE NAMED HERE — this controller
            // passes an explicit array, so a payload the API serves and the
            // Blade reads still arrives as null unless it is listed, and
            // `?? []` makes that silent. That is #247.
        ]);
    }

    public function vendors(Request $request)
    {
        $page = $this->_page($request, 'page');
        $q = $request->input('q', '');
        // Default to highest total-awarded first so the landing surfaces real
        // contracting vendors, not the many $0 registered suppliers.
        $sort = $request->input('sort', 'amount');
        $order = $request->input('order', 'desc');
        $category = $request->input('category', '');
        $mwbe = $request->input('mwbe', '');
        
        // Pass empty strings to clear filters if not set
        $data = DatabookAPI::reqOCE("/oce/vendors?page={$page}&q=" . urlencode($q) . "&sort={$sort}&order={$order}&category=" . urlencode($category) . "&mwbe=" . urlencode($mwbe), 30);
        $data = $data ?: ['data' => [], 'total' => 0, 'page' => 1, 'pages' => 1, 'categories' => [], 'mwbe_options' => []];
        
        return view('procurement.vendors', [
            'pagetitle' => "Vendors - Procurement",
            'data' => $data,
            'q' => $q,
            'sort' => $sort,
            'order' => $order,
            'category' => $category,
            'mwbe' => $mwbe,
        ]);
    }

    public function vendorProfile($id)
    {
        $data = DatabookAPI::reqOCE("/oce/vendor/{$id}", 30);
        
        if (!$data || !isset($data['vendor'])) {
            abort(404, 'Vendor not found');
        }
        
        return view('procurement.vendor_profile', [
            'pagetitle' => ($data['vendor']['name'] ?? 'Vendor') . " - Procurement",
            'vendor' => $data['vendor'],
            'contracts' => $data['contracts'] ?? [],
            'spend' => $data['spend'] ?? null,   // Checkbook actuals across this vendor's contracts
            'sbs' => $data['sbs'] ?? null,       // SBS certified-business profile (null when unmatched)
            'passport' => $data['passport'] ?? null, // PASSPort sub-tables: ownership, MOCS ratings, entity record
            'doingBusiness' => $data['doing_business'] ?? null, // MOCS Doing Business Database (LL34)
            'dos' => $data['dos'] ?? null,        // NY DOS legal-entity record (null when unmatched)
            'relatedNotices' => $data['related_notices'] ?? [],
            'nycha' => $data['nycha'] ?? null,
            // Track B: orgs in the civic register that ARE this vendor. A list,
            // because several register rows can legitimately share one vendor —
            // United Federation of Teachers is the union plus two bargaining units.
            'civicOrgs' => $data['civic_orgs'] ?? [],
            // License product families this vendor supplies.
            'software' => $data['software'] ?? [],
            'breadcrumbs' => Breadcrumbs::procurementVendor($id, $data['vendor']['name'] ?? 'Vendor')
        ]);
    }

    public function agencies(Request $request)
    {
        $page = $this->_page($request, 'page');
        $q = $request->input('q', '');
        $sort = $request->input('sort', 'amount');
        $order = $request->input('order', 'desc');
        
        $data = DatabookAPI::reqOCE("/oce/agencies?page={$page}&q=" . urlencode($q) . "&sort={$sort}&order={$order}&limit=50", 30);
        $data = $data ?: ['data' => [], 'total' => 0, 'page' => 1, 'pages' => 1];
        
        return view('procurement.agencies', [
            'pagetitle' => "Agencies - Procurement",
            'data' => $data ?? [],
            'q' => $q,
            'sort' => $sort,
            'order' => $order,
        ]);
    }

    public function contracts(Request $request)
    {
        [$sort, $order] = array_pad(explode('-', $request->input('sort', 'amount-desc'), 2), 2, 'desc');
        if (!in_array($sort, ['amount', 'date', 'vendor', 'agency'], true)) { $sort = 'amount'; }
        $order = $order === 'asc' ? 'asc' : 'desc';

        $filters = [
            'q'                => trim($request->input('q', '')),
            'agency'           => $request->input('agency', ''),
            'status'           => $request->input('status', ''),
            'method'           => $request->input('method', ''),
            'industry'         => $request->input('industry', ''),
            'expense_category' => $request->input('expense_category', ''),
            'min_amount'       => $request->input('min_amount', ''),
            'max_amount'       => $request->input('max_amount', ''),
        ];
        $active = array_filter($filters, fn($v) => $v !== '' && $v !== null);

        $query = http_build_query($active + [
            'page' => (int) $request->input('page', 1), 'sort' => $sort, 'order' => $order,
        ]);
        $data = DatabookAPI::reqOCE("/oce/contracts?{$query}", 30)
            ?: ['data' => [], 'total' => 0, 'page' => 1, 'pages' => 1];
        $filterOptions = DatabookAPI::reqOCE("/oce/filter-options", 10);

        $apiBase = rtrim(config('apis.fapi_public_entry', 'https://api.databook.nyc'), '/');
        $exportUrl = $apiBase . "/oce/contracts/export?" . http_build_query($active + ['sort' => $sort, 'order' => $order]);

        return view('procurement.contracts', [
            'pagetitle'     => "Contracts - Procurement",
            'data'          => $data,
            'filters'       => $filters,
            'sortKey'       => "{$sort}-{$order}",
            'filterOptions' => $filterOptions['contracts'] ?? [],
            'exportUrl'     => $exportUrl,
        ]);
    }

    public function solicitations(Request $request)
    {
        $page = $this->_page($request, 'page');
        $q = $request->input('q', '');
        $status = $request->input('status', '');
        $method = $request->input('method', '');
        $industry = $request->input('industry', '');
        
        $queryParams = http_build_query([
            'page' => $page,
            'q' => $q,
            'status' => $status,
            'method' => $method,
            'industry' => $industry
        ]);
        
        $data = DatabookAPI::reqOCE("/oce/solicitations?{$queryParams}", 30);
        $data = $data ?: ['data' => [], 'total' => 0, 'page' => 1, 'pages' => 1];
        $filterOptions = DatabookAPI::reqOCE("/oce/filter-options", 10);
        
        return view('procurement.solicitations', [
            'pagetitle' => "Solicitations - Procurement",
            'data' => $data,
            'q' => $q,
            'status' => $status,
            'method' => $method,
            'industry' => $industry,
            'filterOptions' => $filterOptions['solicitations'] ?? [],
        ]);
    }

    public function contractProfile($id)
    {
        $data = DatabookAPI::reqOCE("/oce/contract/{$id}", 30);
        
        if (!$data || !isset($data['contract'])) {
            abort(404, 'Contract not found');
        }
        
        return view('procurement.contract_profile', [
            'pagetitle' => ($data['contract']['contract_id'] ?? 'Contract') . " - Procurement",
            'contract' => $data['contract'],
            'vendor' => $data['vendor'] ?? null,
            'solicitation' => $data['solicitation'] ?? null,
            'relatedNotices' => $data['related_notices'] ?? [],
            'spendTimeline' => $data['spend_timeline'] ?? ['labels' => [], 'values' => []],
            'spendVendors' => $data['spend_vendors'] ?? [],
            'evaluations' => $data['evaluations'] ?? [],           // MOCS agency ratings for this contract
            'evaluationsAsOf' => $data['evaluations_as_of'] ?? '',
            // ⚠ This array NAMES each key, so a new payload key does not reach the
            // view unless it is added here. That is the #247 defect exactly: the
            // Overview served `composition` and `pipeline`, the Blade read them,
            // every unit guard passed, and the page rendered without them because
            // the controller never passed them through.
            'relatedContracts' => $data['related_contracts'] ?? [],
            // The curated program this contract belongs to, or null. Named
            // here for the same #247 reason as the line above.
            'program' => $data['program'] ?? null,
            'breadcrumbs' => Breadcrumbs::procurementContract($id, $data['contract']['contract_id'] ?? 'Contract')
        ]);
    }

    public function solicitationProfile($epin)
    {
        $data = DatabookAPI::reqOCE("/oce/solicitation/{$epin}", 30);
        
        if (!$data || !isset($data['solicitation'])) {
            abort(404, 'Solicitation not found');
        }
        
        return view('procurement.solicitation_profile', [
            'pagetitle' => ($data['solicitation']['epin'] ?? 'Solicitation') . " - Procurement",
            'solicitation' => $data['solicitation'],
            'contracts' => $data['contracts'] ?? [],
            'relatedNotices' => $data['related_notices'] ?? [],
            'stats' => $data['stats'] ?? [],
            'breadcrumbs' => Breadcrumbs::procurementSolicitation($epin, $data['solicitation']['procurement_name'] ?? 'Solicitation')
        ]);
    }

    /**
     * A pagination parameter, floored at 1.
     *
     * ⚠ Returns an int, not a string: the value reaches the forwarded query
     * string AND the cache key, so `'1'` and `1` and `'01'` would otherwise mint
     * three cache entries for one page.
     */
    private function _page(Request $request, string $key): int
    {
        return max(1, (int) $request->input($key, 1));
    }

    public function digitalReform(Request $request)
    {
        // ⚠ These are the SAME dollar figures highlighted (is-accent) on the
        // Master Agreements and Products pages — not part of
        // digitalReformViewData()'s shared payload, since each of those pages
        // calls its own endpoint. Pulled here, cached like the shared payload,
        // so the card can never show a number that disagrees with the page it
        // links to (docs/DIGITAL-REFORM-REORG-PLAN.md).
        $maCeiling = \Illuminate\Support\Facades\Cache::remember('digital_reform_ma_ceiling', 86400, function () {
            $ma = DatabookAPI::reqOCE('/oce/digital-reform/masters', 15);
            return is_array($ma) ? (float) ($ma['total_ceiling'] ?? 0) : null;
        });
        // ⚠⚠ THE SINGLE-FIGURE LENS CARD AND THE LICENCE-TOTAL SCALAR WERE
        // REMOVED WITH THE CARDS THEY FED (2026-09-16). `$dataLens` and
        // `$licTotalValue` each held one number for one numbered lens card; the
        // bands that replaced those cards read `$dataBlocks` and `$prodBlocks`,
        // which are supersets. Leaving the old keys would have left two cache
        // entries nothing reads — the "built and wired into nothing" defect this
        // repo has now found three times. Verified dead in BOTH directions
        // first: 0 references in the Overview AND 0 in the storyboard, which is
        // the check that matters because `$licStory`, `$maStory` and
        // `$maCeiling` ARE read there and look equally orphaned from the
        // Overview alone.

        // ⚠⚠ THE STORYBOARD USED TO TYPE THESE, AND THEY HAD DRIFTED. Its beat 05
        // read "$1.37B across 948 contracts covering 431 different products. Ten
        // products account for 79% of the money" — the figures from BEFORE #239's
        // full-population reclassification. Measured against the live endpoint
        // 2026-09-14: $1.77B, 1,601 contracts, 814 families, top-10 63.4%. Every
        // one understated, the product count by 47%.
        // ⚠ A NEW CACHE KEY, not the one beside it: `digital_reform_licenses_total_value`
        // stores a FLOAT, and reusing it for an array would let a warm cache hand
        // this code a number where it expects a map. A stale entry must not be
        // readable as the new shape.
        $licStory = \Illuminate\Support\Facades\Cache::remember('digital_reform_licenses_story_v1', 86400, function () {
            $lic = DatabookAPI::reqOCE('/oce/licenses', 15);
            if (!is_array($lic)) { return null; }
            $sum  = $lic['summary'] ?? [];
            $fams = $lic['families'] ?? [];
            $total = (float) ($sum['total_value'] ?? 0);
            $families = (int) ($sum['families'] ?? 0);
            // ⚠ The top-10 share is only computable when the served list is the
            // WHOLE list. If the payload ever starts capping `families`, a "top 10
            // of what we were sent" share is a different claim wearing the same
            // words — so it returns null and the page says nothing rather than
            // something plausible.
            $share = null;
            if ($total > 0 && $families > 0 && count($fams) === $families) {
                $vals = array_map(function ($f) { return (float) ($f['value'] ?? 0); }, $fams);
                rsort($vals);
                $share = 100.0 * array_sum(array_slice($vals, 0, 10)) / $total;
            }
            // ⚠ The storyboard names Esri ArcGIS as its worked consolidation
            // example, and its figures were typed: "24 contracts" against a
            // measured 23 on 2026-09-14. The family is looked up from the SAME
            // cached pull rather than re-fetched, and by KEY rather than by rank
            // — it is the example the copy names, not "the largest family"
            // (that is Microsoft), so a rank-based lookup would quietly swap the
            // subject of the sentence.
            $arc = null;
            foreach ($fams as $f) {
                if (($f['key'] ?? '') === 'Esri ArcGIS') { $arc = $f; break; }
            }
            return [
                'contracts'   => (int) ($sum['contracts'] ?? 0),
                'families'    => $families,
                'total_value' => $total,
                'top10_share' => $share,
                'arcgis'      => $arc ? [
                    'value'     => (float) ($arc['value'] ?? 0),
                    'contracts' => (int) ($arc['contracts'] ?? 0),
                    'agencies'  => (int) ($arc['agencies'] ?? 0),
                ] : null,
            ];
        });

        // ⚠⚠ THE STORYBOARD SAID "Only 22 of the City's 186 master agreements show
        // any payment under their own id at all". 22 is the number carrying a
        // Checkbook spend RECORD; the number showing an actual payment is 8.
        // Measured on the live endpoint 2026-09-14, and CLAUDE.md records the same
        // split. The sentence understated its own finding by conflating the two,
        // so both are served and the copy names each for what it is.
        // ⚠ Own cache key, not the float one beside it, for the reason given above.
        $maStory = \Illuminate\Support\Facades\Cache::remember('digital_reform_masters_story_v1', 86400, function () {
            $ma = DatabookAPI::reqOCE('/oce/digital-reform/masters', 15);
            if (!is_array($ma)) { return null; }
            $rows = $ma['rows'] ?? [];
            $withRecord = 0; $withPayment = 0;
            foreach ($rows as $r) {
                if (array_key_exists('spent', $r) && $r['spent'] !== null) {
                    $withRecord++;
                    if ((float) $r['spent'] > 0) { $withPayment++; }
                }
            }
            return [
                'count'         => (int) ($ma['count'] ?? 0),
                'ceiling'       => (float) ($ma['total_ceiling'] ?? 0),
                'with_record'   => $withRecord,
                'with_payment'  => $withPayment,
            ];
        });

        // ⚠⚠ THE SECTION BLOCKS. Each one is built from the endpoint of the page
        // it links to, never recomputed here — the Overview owns no figure of
        // its own, which is what stops a block and its page disagreeing
        // (docs/DIGITAL-REFORM-REORG-PLAN.md). The only thing done here is the
        // presentational FOLD to five slices plus a disclosed remainder.
        // ⚠ Its own cache key per shape, never shared with the narrow scalar
        // entries above: a warm cache handing this code a float where it
        // expects a map is the trap those comments already name.
        $prodBlocks = \Illuminate\Support\Facades\Cache::remember('digital_reform_ov_products_v1', 86400, function () {
            $lic = DatabookAPI::reqOCE('/oce/licenses', 15);
            if (!is_array($lic)) { return null; }
            // ⚠ ONE fold, shared with the Products page, which leads with these
            // same three views (2026-09-23).
            return self::_productsBookBlocks($lic);
        });

        $dataBlocks = \Illuminate\Support\Facades\Cache::remember('digital_reform_ov_data_v1', 86400, function () {
            $d = DatabookAPI::reqOCE('/oce/licenses/data', 15);
            return self::_dataBookBlocks(is_array($d) ? $d : []);
        });

        // ⚠ KEY BUMPED TO _v2 WITH THE SHAPE. A 24h `Cache::remember` under the
        // old key would serve the old shape to the new markup for a day — the
        // band would read "not available" on a working stack, which is the most
        // confusing possible way to ship a redesign.
        $agrBlocks = \Illuminate\Support\Facades\Cache::remember('digital_reform_ov_agreements_v2', 86400, function () {
            $ma = DatabookAPI::reqOCE('/oce/digital-reform/masters', 15);
            return self::_agreementsBookBlocks(is_array($ma) ? $ma : []);
        });

        // The two Contracts-band pies, folded from keys the shared payload
        // already carries — so they need no extra request and cannot disagree
        // with the composition figures the Contracts page publishes.
        $shared = $this->digitalReformViewData($request);

        return view('procurement.digital-reform', array_merge(
            ['pagetitle' => "Digital Services - NYC Databook"],
            $shared,
            self::_vendorsBookBlocks($shared),
            ['maCeiling' => $maCeiling, 'licStory' => $licStory,
             'maStory' => $maStory,
             'prodBlocks' => $prodBlocks, 'dataBlocks' => $dataBlocks, 'agrBlocks' => $agrBlocks],
            // ⚠ The Contracts band's pies come from the SAME helper the Contracts
            // page calls. The band is a preview of that page, so ONE owner: two
            // folds of one list is how a band and its page came to disagree.
            self::_contractsBookSlices($shared)
        ));
    }


    /**
     * The Vendors book — vendors by the route carrying most of their value, and
     * the largest by awarded value. ONE builder for the Overview's Vendors band
     * AND the Vendors page, which leads with it (2026-09-23).
     *
     * ⚠ `$shared` must be the DEFAULT view (sorted by value, unfiltered, page 1):
     * the list is headed "Largest", and a reader's own sort or search on the
     * Vendors page would otherwise put arbitrary vendors under that heading.
     */
    private static function _vendorsBookBlocks(array $shared): array
    {
        return [
            // ⚠⚠ THE WEDGE IS `vendors`, NOT `value` — the owner's call, and the two
            // give different charts: by count the head is small-purchase (242
            // vendors), by money it is Renewal ($2.7B) with small-purchase sixth.
            // `_slices` is told which measure to fold on, so the chart and its
            // legend cannot disagree about what a slice means.
            // ⚠ "Not recorded" is greyed as an ABSTENTION. It is not a procurement
            // route, and colouring it as one would put a hue on "we do not know".
            'vm'       => $shared['vendor_methods'] ?? [],
            'vmSlices' => self::_slices($shared['vendor_methods']['items'] ?? [],
                                        'method', 'vendors', ['Not recorded']),
            // ⚠ RANKED BY AWARDED, not by payments: a master-heavy vendor files
            // its drawdowns under other contract ids.
            'vendTop'   => array_slice($shared['vendors']['vendors'] ?? [], 0, 8),
            'vendTotal' => (int) ($shared['vendors']['total'] ?? 0),
        ];
    }

    /** Bubble points for the Products page's fragmentation map. */
    private static function _fragPoints(array $caps): array
    {
        $caps = array_values(array_filter($caps, function ($r) { return ($r['key'] ?? '') !== 'other'; }));
        $maxV = 1.0;
        foreach ($caps as $r) { $maxV = max($maxV, (float) ($r['value'] ?? 0)); }
        $out = ['many' => [], 'other' => []];
        foreach ($caps as $r) {
            $pt = ['x' => (int) ($r['products'] ?? 0), 'y' => (int) ($r['agencies'] ?? 0),
                   // Area, not radius, carries value: r grows with the square root.
                   'r' => round(4 + 22 * sqrt(((float) ($r['value'] ?? 0)) / $maxV), 2),
                   'row' => ['key' => $r['key'] ?? '', 'label' => $r['label'] ?? ($r['key'] ?? ''),
                             'products' => (int) ($r['products'] ?? 0), 'agencies' => (int) ($r['agencies'] ?? 0),
                             'contracts' => (int) ($r['contracts'] ?? 0), 'value' => (float) ($r['value'] ?? 0)]];
            $out[!empty($r['fragmented']) ? 'many' : 'other'][] = $pt;
        }
        return $out;
    }

    /**
     * The Products "book": value by function, the largest families, value by
     * procurement route. ONE fold for the Overview's Products band AND the
     * Products page, which leads with the same three views — so the band can
     * never preview something the page does not show.
     */
    /**
     * The Agreements book — vendors holding the most running headroom, the
     * agreements running out soonest, ceiling running in each year. ONE builder
     * for the Overview's Agreements band AND the Agreements page, which leads
     * with it (2026-09-23). Null when the endpoint did not answer.
     */
    private static function _agreementsBookBlocks(array $ma): ?array
    {
        if (!($ma['available'] ?? false)) { return null; }
        // ⚠⚠ EVERY FIGURE HERE IS SERVED, NOT COMPUTED. "The Overview
        // computes nothing" — the active split, the vendor ranking, the
        // soonest list and the year series all come from the endpoint the
        // Agreements page reads, so the two cannot disagree.
        $dd = $ma['drawdown'] ?? [];
        return [
            'vendors_active' => array_slice($ma['by_vendor_active'] ?? [], 0, 6),
            'vendors_active_n' => count($ma['by_vendor_active'] ?? []),
            'soonest'  => array_slice($ma['soonest'] ?? [], 0, 6),
            'by_year'  => $ma['ceiling_by_year'] ?? [],
            'active'   => $ma['active'] ?? ['count' => 0, 'ceiling' => 0],
            'count'    => (int) ($ma['count'] ?? 0),
            'ceiling'  => (float) ($ma['total_ceiling'] ?? 0),
            'vendors'  => (int) ($ma['vendors'] ?? 0),
            'agencies' => (int) ($ma['agencies'] ?? 0),
            // The mechanism, so the page can state why there is no spend series.
            'tracked'  => (int) ($dd['tracked'] ?? 0),
            'drawn'    => (int) ($dd['drawn'] ?? 0),
            'drawn_value' => (float) ($dd['drawn_value'] ?? 0),
        ];
    }

    /**
     * The Agreements page's own two pies: ceiling by HOLDING agency, and ceiling
     * still running against ceiling on agreements that have ended.
     *
     * ⚠ Grouped on the RESOLVED org id where there is one, so an organisation
     * published under two spellings (DCAS, MOCJ) is one wedge, as on
     * /procurement/agencies; an unresolved name stands alone and never merges.
     * ⚠ Ceilings, never spend, and a pie of ceilings is part-to-whole of the
     * ceiling on the books — the only total these figures have.
     */
    private static function _agreementsSlices(array $ma): array
    {
        $by = [];
        foreach (($ma['rows'] ?? []) as $r) {
            $k = !empty($r['org_id']) ? 'org:' . $r['org_id'] : 'name:' . ($r['agency'] ?? '');
            if (!isset($by[$k])) {
                $by[$k] = ['label' => (string) ($r['agency'] ?? ''), 'value' => 0.0, 'top' => 0.0,
                           'slug' => (string) ($r['org_id'] ?? '')];
            }
            $c = (float) ($r['ceiling'] ?? 0);
            $by[$k]['value'] += $c;
            // The label is the spelling carrying the most ceiling.
            if ($c > $by[$k]['top']) { $by[$k]['top'] = $c; $by[$k]['label'] = (string) ($r['agency'] ?? ''); }
        }
        $total  = (float) ($ma['total_ceiling'] ?? 0);
        $active = (float) ($ma['active']['ceiling'] ?? 0);
        // The largest holder and its share, for the chart note: one agency holds
        // nearly all of it, and a pie alone leaves the reader to estimate how much.
        $topAg = null;
        foreach ($by as $g) { if ($topAg === null || $g['value'] > $topAg['value']) { $topAg = $g; } }
        return [
            'top_agency' => $topAg ? $topAg['label'] : '',
            'top_share'  => ($topAg && $total > 0) ? round(100 * $topAg['value'] / $total) : null,
            'agency' => self::_slices(array_values($by), 'label', 'value', [], 'slug'),
            // Ended is derived by SUBTRACTION from the served total, never a second
            // predicate, so the two wedges close on the ceiling tile by construction.
            'status' => self::_slices([
                ['label' => 'Still running', 'value' => $active],
                ['label' => 'Ended', 'value' => max(0.0, $total - $active)],
            ], 'label', 'value'),
            'active_n' => (int) ($ma['active']['count'] ?? 0),
        ];
    }

    /**
     * The Data book — value by kind, the largest data products, data spend by
     * agency. ONE builder for the Overview's Data band AND the Data page, which
     * leads with it (2026-09-23). Null when the lens did not answer.
     *
     * ⚠ The CONTENT half only, like every figure in the band: the lens's two
     * halves overlap by design and a block spanning both would be the one sum
     * the Data page exists to refuse.
     */
    private static function _dataBookBlocks(array $d): ?array
    {
        if (!($d['available'] ?? false)) { return null; }
        $c = $d['content'] ?? [];
        return [
            // ⚠ BOTH abstentions take the neutral, and they stay APART:
            // "classified, function not identifiable" and "never classified"
            // are different claims, which is why the endpoint keeps two keys.
            // ⚠ Same capability vocabulary as Products, so the same route —
            // but the NEVER-TAGGED rows carry an empty key and have no page,
            // so they must not produce a link. `_slices` emits '' there and
            // the view skips it.
            'kind'     => self::_slices($c['by_kind'] ?? [], 'label', 'value',
                                       ['Function not identified', 'Not yet tagged'], 'key'),
            'agency'   => self::_slices($c['by_agency'] ?? [], 'key', 'value',
                                        ['Agency not recorded'], 'org_id'),
            'products' => array_slice($c['rows'] ?? [], 0, 8),
            'value'    => (float) ($c['value'] ?? 0),
            'contracts'=> (int) ($c['contracts'] ?? 0),
            'families' => (int) ($c['families'] ?? 0),
        ];
    }

    /**
     * The tools half as a chart: per data-work function, the value bought as a
     * tool and the value bought as data, as two stacked series. Built HERE so
     * the chart script derives nothing.
     *
     * ⚠ Stacking is a WITHIN-ROW sum — each bar is the row total the Products
     * function table publishes. Nothing here adds ACROSS rows or across halves.
     */
    private static function _dataToolSplit(array $d): array
    {
        $rows = array_values(array_filter($d['tools']['rows'] ?? [], function ($r) {
            return ((float) ($r['value'] ?? 0)) > 0;
        }));
        return [
            'labels'  => array_map(function ($r) { return (string) ($r['label'] ?? ''); }, $rows),
            'keys'    => array_map(function ($r) { return (string) ($r['key'] ?? ''); }, $rows),
            'tool'    => array_map(function ($r) { return (float) ($r['tool_value'] ?? 0); }, $rows),
            'content' => array_map(function ($r) { return (float) ($r['content_value'] ?? 0); }, $rows),
        ];
    }

    private static function _productsBookBlocks(array $lic): array
    {
        $fams = $lic['families'] ?? [];
        return [
            // "Function not identified" is the classifier's abstention, so it
            // takes the neutral wherever it ranks — it is not a function.
            // ⚠ `key` carries the slug for both of these — the capability
            // route is `[a-z0-9-]+` and by_capability keys already match it.
            // Verified 2026-09-16 that every head key resolves 200; a link
            // landing on a 404 is worse than plain text, and this repo has
            // shipped that three times.
            'functions' => self::_slices($lic['by_capability'] ?? [], 'label', 'value',
                                         ['Function not identified'], 'key'),
            'route'     => self::_slices($lic['by_method'] ?? [], 'key', 'value', [], 'key'),
            // ⚠⚠ THE FUNCTION VIEW DOES NOT COVER EVERYTHING, AND THE PAGE HAS
            // TO SAY SO. Measured 2026-09-16: `by_capability` carries 1,432 of
            // 1,601 contracts and $1,734.0M of $1,770.4M — 169 contracts /
            // $36.5M have NO capability row at all. That is a different
            // absence from the "Function not identified" row inside the chart
            // ($137M), which is a contract classified and found unidentifiable.
            // Never-classified and classified-as-unidentifiable are different
            // claims; folding them together reports an unanswered question as
            // an answered one. Served, never typed, so it moves with the data.
            'fn_value'  => array_sum(array_map(function ($r) { return (float) ($r['value'] ?? 0); },
                                               $lic['by_capability'] ?? [])),
            'fn_contracts' => array_sum(array_map(function ($r) { return (int) ($r['contracts'] ?? 0); },
                                                  $lic['by_capability'] ?? [])),
            // A LIST, not a pie: 814 families is far past the point where a
            // part-to-whole reads, and the top one alone is 36% of the money.
            'families'  => array_slice($fams, 0, 8),
            // Value by KIND of purchase (the class lens), for the Products page's
            // middle chart. Labels from the one owner; "Not yet classified" is an
            // abstention and takes the neutral.
            'kinds'     => self::_slices(array_map(function ($r) {
                                $r['label'] = \App\Custom\PurchaseClass::label((string) ($r['key'] ?? ''));
                                return $r;
                            }, $lic['by_class'] ?? []), 'label', 'value',
                            [\App\Custom\PurchaseClass::label('(unclassified)')], 'key'),
            'summary'   => $lic['summary'] ?? [],
            'totals'    => $lic['totals'] ?? [],
        ];
    }

    /**
     * The "whole book" pies — value by agency and value by type — shared by the
     * Overview's Contracts band and the Contracts page, which leads with them.
     *
     * ⚠ Folded from keys the shared payload already carries, so neither page
     * needs an extra request and the two cannot fold one list two ways.
     */
    private static function _contractsBookSlices(array $shared): array
    {
        $agRows = [];
        $agC = $shared['charts']['agencies'] ?? [];
        foreach (($agC['labels'] ?? []) as $i => $lab) {
            // ⚠ `slug` carries the ORG ID here, not a url slug — `_slices` is
            // generic about what it forwards and the view decides the target.
            $agRows[] = ['label' => $lab, 'value' => (float) ($agC['values'][$i] ?? 0),
                         'slug'  => (string) ($agC['org_ids'][$i] ?? '')];
        }
        // ⚠ "Type" is the COMPOSITION SEGMENT — one bucket per contract, so these
        // sum to the universe. NOT function_category (46 buckets) and not
        // contract kind; this section has shipped two things under one name.
        $segRows = [];
        foreach (($shared['composition']['segments'] ?? []) as $sg) {
            $segRows[] = ['label' => $sg['segment'] ?? '', 'value' => (float) ($sg['value'] ?? 0),
                          'slug'  => $sg['slug'] ?? ''];
        }
        return [
            'ovAgencySlices' => self::_slices($agRows, 'label', 'value', [], 'slug'),
            'ovTypeSlices'   => self::_slices($segRows, 'label', 'value', [], 'slug'),
        ];
    }

    /**
     * Fold a served, value-sorted list into a part-to-whole slice set.
     *
     * ⚠⚠ THE CAP IS FIVE BECAUSE THE PALETTE IS FIVE. `DBChart.slice` carries
     * exactly five validated hues — no ordering of the ten brand hues passes
     * the CVD/contrast checks at six — so a sixth category is the REMAINDER,
     * in gray, never a generated colour.
     *
     * ⚠ THE REMAINDER IS DISCLOSED, NOT DROPPED. `other_count` is returned so
     * the caller can name how many rows it folds, and the slices always sum to
     * the list's own total — which is what lets the pie reconcile against the
     * figure the linked page publishes. A capped list presented as a whole is
     * the defect this section already paid for on `by_vendor` (25 of 408 under
     * a heading implying all of them).
     *
     * ⚠ ONE OWNER for every pie on the Overview. Five folds written five times
     * is five chances for one of them to drop its remainder silently.
     *
     * @param  array  $rows    served rows, already sorted by value descending
     * @param  string $labelK  key holding the display label
     * @param  string $valueK  key holding the value
     * @param  array  $greyKeys labels that mean "not identified" and must take
     *                          the neutral rather than a categorical hue
     */
    private static function _slices(array $rows, string $labelK, string $valueK,
                                   array $greyKeys = [], string $slugK = '')
    {
        $clean = [];
        foreach ($rows as $r) {
            $v = (float) ($r[$valueK] ?? 0);
            if ($v <= 0) { continue; }                 // a zero slice draws nothing
            $clean[] = ['label' => (string) ($r[$labelK] ?? ''), 'value' => $v,
                        'slug'  => $slugK === '' ? '' : (string) ($r[$slugK] ?? '')];
        }
        usort($clean, function ($a, $b) { return $b['value'] <=> $a['value']; });
        $total = 0.0;
        foreach ($clean as $c) { $total += $c['value']; }

        $head = array_slice($clean, 0, 5);
        $tail = array_slice($clean, 5);
        $tailValue = 0.0;
        foreach ($tail as $t) { $tailValue += $t['value']; }

        $labels = [];
        $values = [];
        $colors = [];
        // ⚠ THE DRILL-DOWN LIVES HERE, and it is a LIST of real links rendered
        // beside the chart rather than a click handler on the canvas. A canvas
        // onClick is invisible to the keyboard and to a screen reader, and this
        // is the only route from the Overview to a segment-filtered contract
        // list — `techsegments.resolve_slug` and the `contract_segment`
        // parameter have no other consumer, so losing it would leave a whole
        // filter built and wired to nothing.
        $items = [];
        foreach ($head as $i => $c) {
            $labels[] = $c['label'];
            $values[] = $c['value'];
            // A row that means "we do not know" keeps the neutral wherever it ranks.
            // ⚠ 'UNKNOWN' (an abstention) and 'OTHER' (the fold) are separate
            // markers, because they are separate claims — one grey for both put
            // two meanings on one wedge colour.
            $grey = in_array($c['label'], $greyKeys, true);
            $colors[] = $grey ? 'UNKNOWN' : $i;
            // ⚠⚠ `color` RIDES ON THE ITEM because the items ARE the legend now.
            // The canvas legend is off (it duplicated these entries as dead
            // text), so each entry paints its own swatch — from `DBChart.slice`
            // via the SAME resolver the arcs use, never a second colour list.
            $items[] = ['label' => $c['label'], 'value' => $c['value'],
                        'slug' => $c['slug'], 'grey' => $grey,
                        'color' => $grey ? 'UNKNOWN' : $i];
        }
        if ($tailValue > 0) {
            $labels[] = count($tail) . ' others';
            $values[] = $tailValue;
            $colors[] = 'OTHER';   // the fold, not an abstention
            // ⚠⚠ THE FOLD IS AN ITEM TOO, and it has to be. With the canvas
            // legend off, an arc that appears in no item is an arc with NO
            // legend entry — and the always-present legend is the SECONDARY
            // ENCODING the dataviz validator's colour-vision check requires, not
            // decoration. It carries no slug, so it renders as text: a fold is
            // not somewhere you can go.
            $items[] = ['label' => count($tail) . ' others', 'value' => $tailValue,
                        'slug' => '', 'grey' => true, 'color' => 'OTHER'];
        }
        return [
            'labels'      => $labels,
            'values'      => $values,
            'colors'      => $colors,          // int = slice index | 'OTHER' fold | 'UNKNOWN'
            'items'       => $items,          // head slices, with slugs where they exist
            'other_count' => count($tail),
            'total'       => $total,
            'shown'       => count($head),
            'rows'        => count($clean),
        ];
    }

    /**
     * Dedicated page for the Renewal Review Queue (contracts expiring before 2030).
     */
    public function digitalReformExpiring(Request $request)
    {
        // ⚠ The Renewal Review Queue moved to its own page (2026-09-23). A
        // Contracts URL carrying a queue parameter is an old queue link — shared
        // in email, linked from the Products pages — so it is sent there with
        // its query string rather than landing on a page that ignores it.
        if (count(array_intersect(array_keys($request->query()), self::QUEUE_PARAMS)) > 0) {
            return redirect()->route('research.digital-reform.review', $request->query());
        }
        $shared = $this->digitalReformViewData($request);
        return view('procurement.digital-reform-expiring', array_merge(
            ['pagetitle' => "Digital Service Contracts - NYC Databook"],
            $shared,
            // The page leads with the same "whole book" the Overview's band
            // previews, folded by the same helper.
            self::_contractsBookSlices($shared)
        ));
    }

    /**
     * The Renewal Review Queue — its own page since 2026-09-23, a working tool for
     * someone deciding whether a technology contract should be renewed as it
     * stands. Same payload as the rest of the section, so its figures are the
     * Contracts page's figures.
     */
    public function digitalReformReview(Request $request)
    {
        return view('procurement.digital-reform-review', array_merge(
            ['pagetitle' => "Renewal Review Queue - NYC Databook"],
            $this->digitalReformViewData($request)
        ));
    }

    /**
     * The filtered queue as CSV — every matching row, not the visible page.
     *
     * ⚠ Not cached here: it is one request a reviewer makes on purpose, and a
     * cached export keyed on every filter is the cache-minting shape #321 found.
     * The API caps the page at QUEUE_EXPORT_LIMIT; the count it reports is
     * compared with the rows received, and a short export says so in its last
     * line rather than passing as complete.
     */
    public function digitalReformReviewExport(Request $request)
    {
        $qs = [];
        foreach (self::QUEUE_PARAMS as $k) {
            if (!in_array($k, ['expiring_page', 'expiring_limit'], true) && $request->filled($k)) {
                $qs[$k] = (string) $request->input($k);
            }
        }
        $qs['expiring_page'] = 1;
        $qs['expiring_limit'] = self::QUEUE_EXPORT_LIMIT;
        // Keep the other blocks small: only the queue is wanted.
        $qs['vendor_limit'] = 1;
        $qs['contract_limit'] = 1;
        $all = DatabookAPI::reqOCE('/oce/digital-reform/all?' . http_build_query($qs), 60);
        $exp = is_array($all) ? ($all['expiring'] ?? null) : null;
        if (!is_array($exp)) {
            abort(503, 'The queue is unavailable right now.');
        }
        $rows = $exp['contracts'] ?? [];
        $total = (int) ($exp['total'] ?? count($rows));
        $flagLabels = array_map(function ($f) { return $f['label']; }, self::QUEUE_FLAGS);

        $cols = ['contract_id', 'vendor_name', 'agency', 'contract_title', 'start_date', 'end_date',
                 'days_to_expiry', 'award_amount', 'current_amount', 'value', 'amount_kind',
                 'procurement_method', 'function_category', 'is_license', 'license_family',
                 'purchase_class', 'build_vs_buy', 'spent', 'utilization', 'epin', 'review_flags'];
        return response()->streamDownload(function () use ($rows, $cols, $total, $flagLabels) {
            $out = fopen('php://output', 'w');
            fputcsv($out, $cols);
            foreach ($rows as $r) {
                $flags = array_map(function ($f) use ($flagLabels) {
                    return $flagLabels[$f['key'] ?? ''] ?? ($f['label'] ?? '');
                }, $r['flags'] ?? []);
                $line = [];
                foreach ($cols as $c) {
                    if ($c === 'review_flags') { $line[] = implode('; ', $flags); continue; }
                    $v = $r[$c] ?? '';
                    $line[] = is_bool($v) ? ($v ? 'yes' : 'no') : (is_array($v) ? '' : $v);
                }
                fputcsv($out, $line);
            }
            // ⚠ A truncated export must not read as complete.
            if (count($rows) < $total) {
                fputcsv($out, ['NOTE: ' . count($rows) . ' of ' . $total
                    . ' matching contracts exported; narrow the filters for the rest.']);
            }
            fclose($out);
        }, 'renewal-review-queue.csv', ['Content-Type' => 'text/csv; charset=UTF-8']);
    }

    /**
     * Section search (reorg Phase 6) — JSON for the Overview's search box.
     *
     * ⚠ A thin proxy on purpose: the browser must not call the API host directly
     * (that is a different origin and the app's FAPI credential never reaches the
     * client), and the scoped endpoint is cheap enough to hit per keystroke-batch.
     */
    public function digitalReformSearch(Request $request)
    {
        $q = trim((string) $request->input('q', ''));
        if ($q === '' || mb_strlen($q) < 2) {
            return response()->json(['query' => $q, 'groups' => [], 'total' => 0]);
        }
        $res = DatabookAPI::reqOCE('/oce/digital-reform/search?q=' . urlencode($q), 8);
        if (!is_array($res)) {
            // ⚠ 200 with an explicit flag, never a 500: a search box that errors
            // out is worse than one that says it is unavailable.
            return response()->json(['query' => $q, 'groups' => [], 'total' => 0,
                                     'unavailable' => true]);
        }
        return response()->json($res);
    }

    /**
     * Vendors of the technology universe (reorg Phase 1). The table moved here
     * from the Overview's tabs; it reads the same shared payload, so the figures
     * cannot diverge from the Overview's tiles.
     */
    public function digitalReformVendors(Request $request)
    {
        $shared = $this->digitalReformViewData($request);
        // The band always shows the DEFAULT ranking, whatever the table below is
        // sorted or searched by. With no vendor parameters that is this same
        // payload; otherwise it is the bare page's, which is the same cache entry
        // a visit with no query string uses.
        $default = true;
        foreach (['vendor_q', 'vendor_page', 'vendor_sort', 'vendor_order'] as $k) {
            if ($request->filled($k)) { $default = false; }
        }
        $bandShared = $default ? $shared : $this->digitalReformViewData(Request::create($request->url()));
        return view('procurement.digital-reform-vendors', array_merge(
            ['pagetitle' => "Digital Service Vendors - NYC Databook"],
            $shared,
            self::_vendorsBookBlocks($bandShared)
        ));
    }

    /**
     * "What data does the City buy?" — the section plan's §5c Phase A lens.
     *
     * Its own small endpoint, like Master Agreements, because the Products
     * payload carries nothing at this grain. ⚠ The page shows TWO halves that
     * OVERLAP by $23.2M — imagery filed under GIS is both data the City buys and
     * a row in the GIS total — so the view must never add them, and the API
     * deliberately serves no key that does.
     */
    public function digitalReformData(Request $request)
    {
        $d = DatabookAPI::reqOCE('/oce/licenses/data', 15);
        if (!is_array($d)) {
            $d = ['available' => false];
        }
        return view('procurement.digital-reform-data', [
            'pagetitle' => 'What data does the City buy? - NYC Databook',
            'd'         => $d,
            // The same three views the Overview's Data band previews.
            'dataBlocks' => self::_dataBookBlocks($d),
            'toolSplit'  => self::_dataToolSplit($d),
        ]);
    }

    /**
     * The call-center lens: what the City buys when it buys a phone line, and
     * where this section's own technology boundary falls across it.
     *
     * ⚠⚠ THE OUTSIDE HALF IS NOT TECHNOLOGY SPENDING and must never be added to
     * any figure on the rest of the section. It is money the classification has
     * deliberately excluded; the lens shows it so the boundary is legible, not
     * so it can be counted back in.
     */
    public function digitalReformCallCenters(Request $request)
    {
        $d = DatabookAPI::reqOCE('/oce/digital-reform/call-centers', 15);
        if (!is_array($d)) {
            $d = ['available' => false];
        }
        return view('procurement.digital-reform-call-centers', [
            'pagetitle' => 'What the City buys when it buys a phone line - NYC Databook',
            'd'         => $d,
        ]);
    }

    /**
     * Master Agreements: registered MA/MMA instruments in the technology
     * universe. Reads its own small endpoint (cached API-side) — deliberately
     * NOT digitalReformViewData, whose payload carries nothing at master grain.
     * ⚠ Every figure on this page is a CEILING; the view must never present one
     * as spend (modules/contractkind is the API-side owner of that split).
     */
    public function digitalReformMasterAgreements(Request $request)
    {
        $ma = DatabookAPI::reqOCE('/oce/digital-reform/masters', 15);
        if (!is_array($ma)) {
            $ma = ['available' => false];
        }
        // ⚠ AGREEMENTS IN THE PIPELINE moved here from the Contracts page
        // (2026-09-23): agreements PASSPort has not registered yet. Read from the
        // section's shared payload, never a second query — `pipelinevehicles` is
        // the one owner of that figure. With no query string this is the same
        // cache entry the bare Contracts page uses.
        $pipe = $this->digitalReformViewData($request)['pipeline'] ?? [];

        // For each pending agreement, the REGISTERED masters held by the same
        // vendor at the same agency. ⚠ A FACT, not a succession claim: the page
        // says "registered with the same vendor and agency", because nothing in
        // PASSPort links a pending agreement to the one it may replace (measured:
        // 0 of 2,427 unregistered EPINs match a registered master's EPIN).
        $regBy = [];
        foreach (($ma['rows'] ?? []) as $r) {
            $regBy[($r['vendor_name'] ?? '') . '|' . ($r['agency'] ?? '')][] = $r;
        }
        // ⚠ A pending agreement whose START DATE passed more than TWO YEARS ago is
        // flagged, not hidden: T-Mobile's $244.2M telecom agreement has read
        // "In Progress" since 01/01/2017. The threshold is stated on the page.
        // ⚠⚠ Two years, not one, and measured: registering after the start date is
        // routine in NYC, and at one year 35 of the 58 rows shown carried the
        // badge — a flag on 60% of rows marks nothing.
        $staleBefore = \Carbon\Carbon::today()->subYears(2);
        $rows = [];
        foreach (($pipe['rows'] ?? []) as $p) {
            $reg = $regBy[($p['vendor_name'] ?? '') . '|' . ($p['agency'] ?? '')] ?? [];
            usort($reg, function ($a, $b) {
                return strcmp(self::_mdyKey($b['end_date'] ?? ''), self::_mdyKey($a['end_date'] ?? ''));
            });
            $start = \DateTime::createFromFormat('m/d/Y', (string) ($p['start_date'] ?? ''));
            $p['registered'] = array_slice($reg, 0, 3);
            $p['registered_n'] = count($reg);
            $p['stale'] = $start !== false && $start < $staleBefore;
            $rows[] = $p;
        }
        $pipe['rows'] = $rows;
        $pipe['stale_n'] = count(array_filter($rows, function ($r) { return $r['stale']; }));
        $pipe['matched_n'] = count(array_filter($rows, function ($r) { return $r['registered_n'] > 0; }));

        return view('procurement.digital-reform-agreements', [
            'pagetitle' => 'Agreements - NYC Databook',
            'ma'        => $ma,
            'pipe'      => $pipe,
            // The same three views the Overview's Agreements band previews.
            'agrBlocks' => self::_agreementsBookBlocks($ma),
            'agrSlices' => self::_agreementsSlices($ma),
        ]);
    }

    /** MM/DD/YYYY -> YYYYMMDD for ordering; '' when unparseable. */
    private static function _mdyKey(string $d): string
    {
        return preg_match('#^(\d{2})/(\d{2})/(\d{4})$#', $d, $m) ? $m[3] . $m[1] . $m[2] : '';
    }

    /**
     * Software Licenses (UNLISTED — not in the nav, noindex).
     *
     * ⚠ Everything on this page is AI-derived: is_license agreed only 92%
     * between two models on a 40-contract sample and no row is human-curated,
     * which is why it ships behind the Analysis identity and unpublished.
     *
     * Longer timeout than the 5s default because the payload aggregates ~950
     * contracts; the API caches it 6h, so only the first call after a restart
     * is slow. A failure degrades to the unavailable state rather than 500ing.
     */
    public function digitalReformLicenses(Request $request)
    {
        $family = trim((string) $request->input('family', ''));
        $agency = trim((string) $request->input('agency', ''));
        // ⚠ The purchase class is the page's headline lens and was the one table
        // with no drill-down: families and functions both clicked through while
        // classes dead-ended. Resolved server-side by the API through
        // modules/licenseclass, never re-derived here.
        $class  = trim((string) $request->input('class', ''));

        $lic = DatabookAPI::reqOCE('/oce/licenses', 15);
        if (!is_array($lic)) {
            $lic = ['available' => false, 'reason' => 'the API could not be reached'];
        }

        $drill = null;
        if ($family !== '' || $agency !== '' || $class !== '') {
            $q = '/oce/licenses/contracts?limit=300&family=' . urlencode($family)
               . '&agency=' . urlencode($agency)
               . '&class=' . urlencode($class);
            $drill = DatabookAPI::reqOCE($q, 15);
            if (!is_array($drill)) {
                $drill = null;
            }
        }

        return view('procurement.digital-reform-licenses', [
            'pagetitle' => 'Software Products - NYC Databook',
            'lic'       => $lic,
            // The fragmentation map's points: distinct products (x) against buying
            // agencies (y), area by value. Built HERE so the chart script derives
            // nothing. ⚠ `other` is the classifier's abstention, not a function.
            'fragPoints' => self::_fragPoints($lic['by_capability'] ?? []),
            // The same three views the Overview's Products band previews.
            'prodBlocks' => ($lic['available'] ?? true) !== false && isset($lic['families'])
                ? self::_productsBookBlocks($lic) : null,
            // Owner, 2026-09-23: on THIS page the book's middle chart is value by
            // kind; the Overview's band keeps the largest-families list.
            'prodMiddle' => 'kind',
            'family'    => $family,
            'agencySel' => $agency,
            'classSel'  => $class,
            'drill'     => $drill,
        ]);
    }

    /**
     * Open-source alternatives (owner, 2026-09-23): the three review bands and
     * the catalogue gaps, moved off the Products page. Same payload as Products,
     * which the API caches 6h, so this page adds no computation.
     */
    public function digitalReformOpenSource(Request $request)
    {
        $lic = DatabookAPI::reqOCE('/oce/licenses', 15);
        if (!is_array($lic)) {
            $lic = ['available' => false, 'reason' => 'the API could not be reached'];
        }
        return view('procurement.digital-reform-open-source', [
            'pagetitle' => 'Open-Source Alternatives - NYC Databook',
            'lic'       => $lic,
        ]);
    }

    /**
     * One software FUNCTION: which products do this job, in which agencies.
     *
     * The click the consolidation view was missing - naming a function as
     * fragmented and then dead-ending is worse than not naming it.
     */
    public function digitalReformLicenseCapability(Request $request, $cap)
    {
        $data = DatabookAPI::reqOCE('/oce/licenses/capability/' . urlencode($cap), 15);
        if (!is_array($data) || !($data['available'] ?? false)) {
            abort(404, 'Software function not found');
        }

        return view('procurement.digital-reform-license-capability', [
            'pagetitle' => 'Software by function - NYC Databook',
            'cap'       => $data,
        ]);
    }

    /**
     * One license product family, at its own URL.
     *
     * 404s on an unknown slug rather than rendering an empty shell, so a stale
     * or mistyped link is unambiguous.
     */
    public function digitalReformLicenseFamily(Request $request, $slug)
    {
        $fam = DatabookAPI::reqOCE('/oce/licenses/family/' . urlencode($slug), 15);
        if (!is_array($fam) || !($fam['available'] ?? false)) {
            abort(404, 'License family not found');
        }

        // ⚠⚠ THE COMPANY FACTS ARE HYDRATED, NOT RETYPED INTO THE SEED. Where the
        // maker is a registered City vendor we already hold its address, revenue
        // band, ticker and LL34 principal officers on its vendor profile, so the
        // card reads them from there and cannot drift from the page it links to.
        // The seed carries only what PASSPort does not know: who the maker IS,
        // its parent, what it used to be called, and why that matters.
        // ⚠ Fails soft to null -- a company card must never take the page down,
        // and `reqOCE` returns false on a timeout.
        $makerVendor = null;
        $mvId = $fam['maker']['maker_vendor_id'] ?? '';
        if ($mvId !== '') {
            $v = DatabookAPI::reqOCE('/oce/vendor/' . urlencode($mvId), 10);
            $makerVendor = is_array($v) ? $v : null;
        }

        return view('procurement.digital-reform-license-family', [
            'pagetitle' => ($fam['family'] ?? 'License family') . ' licenses - NYC Databook',
            'fam'       => $fam,
            // ⚠ NAMED HERE OR IT NEVER ARRIVES. This controller lists every
            // view-data key explicitly, so a key the Blade reads and this array
            // omits degrades silently to nothing (#247).
            'makerVendor' => $makerVendor,
            // ⚠ An independent audit's observations, fetched server-side and
            // failing soft to null. Most families get null, correctly.
            'webEstate' => (new \App\Services\WebEstateService())
                ->forSlug($fam['slug'] ?? $slug),
        ]);
    }

    /**
     * Shared loader for both Digital Services pages: reads all filter params,
     * calls the combined API (cached 24h), and returns the full view-data array.
     * The two pages each render the slice they need.
     */
    private function digitalReformViewData(Request $request)
    {
        // ⚠⚠ CLAMPED, AND THE REASON IS A CRAWLER TRAP WE GENERATE OURSELVES.
        // These were raw `$request->input(...)`, so `contract_page=-42` flowed
        // straight through — into the forwarded query string, into the API, and
        // into `$cacheKey = 'digital_reform_' . md5($qs)` with a 24h TTL.
        //
        // The negative values are NOT external fuzzing. The pagination markup put
        // `disabled` on the <li> while leaving a real href on the <a> inside, so
        // "Previous" from page 1 linked to page 0, from 0 to -1, and so on with no
        // floor. A crawler following links walks infinitely downward, and every
        // step mints a distinct 24-hour cache entry holding a full API payload.
        //
        // Measured on prod 2026-08-29, over ONE 10-minute window:
        //     955 requests to this page from 265 distinct IPs
        //     453 of them carrying a negative page number
        //     Laravel file cache: 1.2 GB across 10,851 entries
        //
        // `_page` clamps the floor at 1. The ceiling cannot be clamped here — the
        // page count is only known after the API call — but a page beyond the end
        // returns an empty list, which is bounded; a page below 1 was not.
        $vendorPage = $this->_page($request, 'vendor_page');
        $vendorSort = $request->input('vendor_sort', 'amount');
        $vendorOrder = $request->input('vendor_order', 'desc');
        $vendorQ = trim((string) $request->input('vendor_q', ''));

        $contractPage = $this->_page($request, 'contract_page');
        $contractSort = $request->input('contract_sort', 'date');
        $contractOrder = $request->input('contract_order', 'desc');
        $contractQ = trim((string) $request->input('contract_q', ''));
        $contractMethod = trim((string) $request->input('contract_method', ''));
        $contractAgency = trim((string) $request->input('contract_agency', ''));

        $expiringPage = $this->_page($request, 'expiring_page');
        $expiringLimit = (int) $request->input('expiring_limit', self::SECTION_PAGE);
        if (!in_array($expiringLimit, self::QUEUE_PAGE_SIZES, true)) {
            $expiringLimit = self::SECTION_PAGE;
        }
        $expiringSort = $request->input('expiring_sort', 'date');
        $expiringOrder = $request->input('expiring_order', 'asc');
        $expiringYear = trim((string) $request->input('expiring_year', ''));
        $expiringAgency = trim((string) $request->input('expiring_agency', ''));
        $expiringMethod = trim((string) $request->input('expiring_method', ''));
        $expiringMin = (float) $request->input('expiring_min', 0);
        $expiringFlag = trim((string) $request->input('expiring_flag', ''));
        $expiringCategory = trim((string) $request->input('expiring_category', ''));
        $expiringLicense = trim((string) $request->input('expiring_license', ''));
        $expiringBuildbuy = trim((string) $request->input('expiring_buildbuy', ''));
        $expiringShowNonTech = trim((string) $request->input('expiring_shownontech', ''));
        // Deep-link target from the (unlisted) Licenses page: a product FAMILY name.
        $expiringProduct = trim((string) $request->input('expiring_product', ''));
        // Which composition segment the contracts table is drilled into (a slug from
        // modules/techsegments; the API resolves it and returns the resolved name).
        $contractSegment = trim((string) $request->input('contract_segment', ''));

        // Single combined API call with Laravel file cache (24h). Cache key + the
        // forwarded query string both include every filter so results stay correct.
        $qs = http_build_query([
            'vendor_page' => $vendorPage, 'vendor_sort' => $vendorSort, 'vendor_order' => $vendorOrder,
            'vendor_q' => $vendorQ, 'vendor_limit' => self::SECTION_PAGE,
            'contract_page' => $contractPage, 'contract_sort' => $contractSort, 'contract_order' => $contractOrder,
            'contract_q' => $contractQ, 'contract_method' => $contractMethod,
            'contract_agency' => $contractAgency,
            'contract_limit' => self::ALL_CONTRACTS_PAGE,
            'expiring_page' => $expiringPage, 'expiring_sort' => $expiringSort, 'expiring_order' => $expiringOrder,
            'expiring_limit' => $expiringLimit,
            'expiring_year' => $expiringYear, 'expiring_agency' => $expiringAgency,
            'expiring_method' => $expiringMethod, 'expiring_min' => $expiringMin, 'expiring_flag' => $expiringFlag,
            'expiring_category' => $expiringCategory, 'expiring_license' => $expiringLicense,
            'expiring_buildbuy' => $expiringBuildbuy, 'expiring_shownontech' => $expiringShowNonTech,
            'expiring_product' => $expiringProduct,
            // The composition bar's drill-down. ⚠ Part of the cache key too, or every
            // segment would serve whichever segment was requested first.
            'contract_segment' => $contractSegment,
        ]);
        $cacheKey = 'digital_reform_' . md5($qs);
        $allData = \Illuminate\Support\Facades\Cache::remember($cacheKey, 86400, function () use ($qs) {
            return DatabookAPI::reqOCE("/oce/digital-reform/all?{$qs}", 30);
        });

        $stats = $allData['stats'] ?? [];
        $charts = $allData['charts'] ?? [];
        $vendors = $allData['vendors'] ?? [];
        $contracts = $allData['contracts'] ?? [];
        $expiring = $allData['expiring'] ?? [];
        $contractOptions = $allData['contract_options'] ?? ['methods' => [], 'agencies' => []];

        return [
            'expiringProduct' => $expiringProduct,
            'stats' => $stats,
            'charts' => $charts,
            'vendors' => $vendors,
            'contracts' => $contracts,
            'expiring' => $expiring,
            'contractOptions' => $contractOptions,
            // ⚠⚠ THE CONTROLLER IS THE SEAM, AND FORGETTING IT IS SILENT. The API
            // served `composition`, `pipeline` and `scope`; this array did not pass
            // them, so the Overview rendered with no composition bar and no pipeline
            // block and threw no error — `$composition ?? []` degrades politely.
            // Every guard passed, because they scan the template and the API, not the
            // wiring between them. Only rendering the page found it.
            // Same lesson as the org chart: selecting a value proves nothing about
            // surfacing it.
            'composition' => $allData['composition'] ?? [],
            'pipeline' => $allData['pipeline'] ?? [],
            // Phase 2: the renewal calendar over the whole universe. ⚠ Named in
            // this array or the Contracts page reads it as empty and renders the
            // section as nothing, silently — the #247 seam.
            'calendar' => $allData['calendar'] ?? [],
            // Committed money by start year, with master ceilings kept separate.
            // ⚠ Named here or the Overview's chart renders as nothing, silently —
            // the #247 seam again, and the per-view guard checks this array.
            'awardByStartYear' => $allData['award_by_start_year'] ?? [],
            // Vendors by the procurement route carrying most of their value.
            // ⚠⚠ THE #247 SEAM CAUGHT ME THREE LINES BELOW ITS OWN WARNING. The
            // api served `vendor_methods`, the controller read
            // `$shared['vendor_methods']`, and this array did not name it — so
            // `_slices` folded an empty list, the band's `@if` was false and the
            // pie simply was not there. No error, no failing test: the guard
            // reads the VIEW's keys, and this one is consumed in the controller.
            'vendor_methods' => $allData['vendor_methods'] ?? [],
            'scope' => $allData['scope'] ?? [],
            'contractSegment' => $contractSegment,
            'vendorPage' => $vendorPage,
            'vendorSort' => $vendorSort,
            'vendorOrder' => $vendorOrder,
            'vendorQ' => $vendorQ,
            'contractPage' => $contractPage,
            'contractSort' => $contractSort,
            'contractOrder' => $contractOrder,
            'contractQ' => $contractQ,
            'contractMethod' => $contractMethod,
            'contractAgency' => $contractAgency,
            'expiringPage' => $expiringPage,
            'expiringSort' => $expiringSort,
            'expiringOrder' => $expiringOrder,
            'expiringYear' => $expiringYear,
            'expiringAgency' => $expiringAgency,
            'expiringMethod' => $expiringMethod,
            'expiringMin' => $expiringMin,
            'expiringFlag' => $expiringFlag,
            'expiringCategory' => $expiringCategory,
            'expiringLicense' => $expiringLicense,
            'expiringBuildbuy' => $expiringBuildbuy,
            'expiringShowNonTech' => $expiringShowNonTech,
            'expiringLimit' => $expiringLimit,
            'queuePageSizes' => self::QUEUE_PAGE_SIZES,
            'queueFlags' => self::QUEUE_FLAGS,
        ];
    }

    public function orgProcurement(Request $request, $name = null)
    {
        $agencyName = $name ?? $request->input('name');
        if (!$agencyName) {
            abort(400, 'Agency name required');
        }
        
        $data = DatabookAPI::reqOCE("/oce/agency/procurement?name=" . urlencode($agencyName), 30);

        if (!$data || !isset($data['agency'])) {
            abort(404, 'Agency not found');
        }

        // Agency-profile unification: when this agency resolves to an org record,
        // send users to the single canonical profile (org profile's procurement
        // section) instead of this standalone page. Unmatched agencies (org_id
        // null) fall through and render the standalone page as the fallback.
        // 302 (not 301) during rollout so the crosswalk stays tunable without
        // poisoning browser caches.
        $orgId = $data['agency']['org_id'] ?? null;
        if ($orgId) {
            return redirect()->route('orgSection', [
                'id'      => $orgId,
                'orgslug' => \Illuminate\Support\Str::slug($data['agency']['name'] ?? $agencyName, '-'),
                'section' => 'procurement-highlights',
            ], 302);
        }

        return view('procurement.org_procurement', [
            'pagetitle' => ($data['agency']['name'] ?? 'Agency') . " Procurement - Databook",
            'agency' => $data['agency'],
            'stats' => $data['stats'] ?? [],
            'monthly_activity' => $data['monthly_activity'] ?? [],
            'yearly_spending' => $data['yearly_spending'] ?? [],
            'contracts' => $data['contracts'] ?? [],
            'solicitations' => $data['solicitations'] ?? [],
            'vendors' => $data['vendors'] ?? [],
            'breadcrumbs' => Breadcrumbs::procurementAgency($data['agency']['name'] ?? $agencyName)
        ]);
    }

    /**
     * Spending dashboard — stat tiles, Top-5 ranked cards, and charts.
     */
    public function transactions(Request $request)
    {
        // The dashboard's heavy widgets (totals, Top-N, charts, sub-vendor, M/WBE)
        // are lazy-loaded client-side from the API so a cold/slow Parquet scan never
        // blocks the page render. Controller just passes the fiscal year.
        $fy = (int) $request->input('fiscal_year', 2026);

        return view('procurement.transactions', [
            'pagetitle' => "Spending - Procurement",
            'fiscal_year' => $fy,
        ]);
    }

    /**
     * Transaction explorer — faceted filters, expandable results table, pagination.
     */
    public function transactionsSearch(Request $request)
    {
        // Sort select encodes column + direction as "col-dir" (e.g. "amount-desc").
        [$sort, $order] = array_pad(explode('-', $request->input('sort', 'amount-desc'), 2), 2, 'desc');
        $allowedSort = ['amount', 'date', 'agency', 'vendor'];
        if (!in_array($sort, $allowedSort, true)) { $sort = 'amount'; }
        $order = $order === 'asc' ? 'asc' : 'desc';

        $filters = [
            'q'                 => trim($request->input('q', '')),
            'fiscal_year'       => $request->input('fiscal_year', 2026),
            'agency'            => $request->input('agency', ''),
            'expense_category'  => $request->input('expense_category', ''),
            'spending_category' => $request->input('spending_category', ''),
            'industry'          => $request->input('industry', ''),
            'sub_vendor'        => $request->input('sub_vendor', ''),
            'mwbe_category'     => $request->input('mwbe_category', ''),
            'woman_owned'       => $request->input('woman_owned', ''),
            'emerging'          => $request->input('emerging', ''),
            'min_amount'        => $request->input('min_amount', ''),
            'max_amount'        => $request->input('max_amount', ''),
            'date_from'         => $request->input('date_from', ''),
            'date_to'           => $request->input('date_to', ''),
        ];
        $active = array_filter($filters, fn($v) => $v !== '' && $v !== null);

        $query = http_build_query($active + [
            'page'  => (int) $request->input('page', 1),
            'sort'  => $sort,
            'order' => $order,
        ]);
        $data = DatabookAPI::reqOCE("/oce/transactions?{$query}", 30)
            ?: ['data' => [], 'total' => 0, 'total_amount' => 0, 'page' => 1, 'pages' => 1, 'fiscal_years' => []];

        $fy = (int) $filters['fiscal_year'];
        // Contextual facets: pass every active filter so each dimension narrows to the rest.
        $facets = DatabookAPI::reqOCE("/oce/transactions/facets?" . http_build_query($active), 300)
            ?: ['agency' => [], 'expense_category' => [], 'industry' => [], 'spending_category' => []];

        // CSV export streams from the public API directly (browser download), current filters minus paging.
        $apiBase = rtrim(config('apis.fapi_public_entry', 'https://api.databook.nyc'), '/');
        $exportUrl = $apiBase . "/oce/transactions/export?" . http_build_query($active + ['sort' => $sort, 'order' => $order]);

        return view('procurement.transactions_search', [
            'pagetitle'  => "Transactions - Spending",
            'data'       => $data,
            'facets'     => $facets,
            'filters'    => $filters,
            'sortKey'    => "{$sort}-{$order}",
            'exportUrl'  => $exportUrl,
        ]);
    }

    /**
     * Display the data sources page documenting all OCE datasets.
     */
    public function dataSources()
    {
        return view('procurement.data_sources', [
            'pagetitle' => "Data Sources - Procurement",
        ]);
    }
}

