<?php
namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Str;
use App\Custom\CapitalSlug;
use App\Custom\OrgsDatasets;
use App\Custom\ProjectsDatasets;
use App\Custom\Breadcrumbs;
use App\Custom\DatabookAPI;


class Projects extends Controller
{
    /** The endpoint's own sort vocabulary — `sort` values it recognises. */
    const CAPITAL_SORTS = ['planned', 'adopted', 'committed', 'spent', 'agency', 'id'];
    const CAPITAL_PER_PAGE = 50;

    /**
     * Show capital projects main page.
     *
     * @return \Illuminate\View\View
     */
    public function main()
    {
		$ds = new ProjectsDatasets();
		$dates = DatabookAPI::req('/get/capitalprojects/dates');
		$date = ($dates && isset($dates[0]['PUB_DATE'])) ? $dates[0]['PUB_DATE'] : '2024-01-01';
        return view('capital', [
					'breadcrumbs' => Breadcrumbs::capital_a(),
					'datasets' => $ds->stats_data_sources(DatabookAPI::req('/get/datasets/all'),
							null,
							ProjectsDatasets::rowCounts()
						),
					// ⚠ NO `tblStatsUrl` AND NO `finStatUrls`. `capital.blade.php` renders
					// its sources through `<x-db.data-provenance mode="page">`, which
					// takes its counts from the registry with the page, and it renders no
					// `prj_stat` tile at all — so both were config for consumers this
					// view does not have. The commented-out `finStatUrls` block that stood
					// here named `#over_budg_am` and multiplied by 1000; it survived only
					// because Blade never compiles a `{{-- --}}` block, which is exactly
					// the state that makes a later reader think the tiles are still
					// hydrated from `pstats-*`.
					'globStats' => DatabookAPI::reqOCE('/pipeline/globstats') ?: json_decode(file_get_contents(public_path('data/globStats.json')), true),
					// ⚠⚠ EVERY KEY THE OVERVIEW READS MUST BE NAMED HERE. This
					// controller passes an explicit array, so a payload the API
					// serves and the Blade reads still arrives as null unless it
					// is listed — and `?? []` in the view makes that SILENT.
					// That is #247: the composition bar and pipeline block
					// shipped absent from a page whose every unit guard passed.
					'capital' => DatabookAPI::reqOCE('/get/capital/overview') ?: null,
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					'map' => true,
				]);
    }		


    /**
     * Show capital projects archive page.
     *
     * @return \Illuminate\View\View
     */
    public function projects(Request $request)
    {
        $ds = new ProjectsDatasets();
        // ⚠⚠ NO `$details` HERE ANY MORE, AND THE WHOLE CHAIN WAS DEAD. This
        // read `$ds->get('main')` — a contract written against
        // `capitalprojectsdollarscomp` with eleven `, 1000` money multipliers —
        // and passed `details` plus a `dataset` looked up from its `fullname`.
        // Measured 2026-09-10: `projects.blade.php` references `$details` ZERO
        // times and `$dataset` ZERO times, and the lookup itself returns
        // `{"rows":[]}` for that name, so `dataset` was already `null`. Three
        // keys, none read.
        // ⚠ `$ds` stays: `stats_data_sources` below is what this page actually
        // needs from it.

        // ⚠⚠ FLOOR AND CAST, BOTH HALVES (#321). A crawler followed a live href
        // on a disabled pagination control down through page=0, -1, -2 with no
        // floor, and the raw value reached a cache key so '1', 1 and '01' minted
        // three entries for one page. `(int)` is not decoration.
        $page = max(1, (int) $request->input('page', 1));

        // ⚠ `CAPITAL_SORTS` IS A SECOND COPY of the endpoint's vocabulary, and
        // saying so is the point: the whitelist has to run before any API call,
        // so it cannot be read from the served `sorts` list. A guard
        // (`test_capital_projects_page.py`) pins it byte-equal to the router's
        // `_SORTS`, because an unknown sort silently becomes the default there —
        // so a drifted copy would offer the reader an option that does nothing
        // and looks like it worked.
        $sort = in_array($request->input('sort'), self::CAPITAL_SORTS, true)
            ? $request->input('sort') : 'planned';
        $direction = $request->input('direction') === 'asc' ? 'asc' : 'desc';

        // Tri-state flags: absent means "don't filter", which is NOT the same as
        // false. `has_location=0` is a real question ("what has the City not
        // located?") and must survive as `false`, not collapse into unset.
        $flag = function ($key) use ($request) {
            $v = $request->input($key);
            if ($v === null || $v === '') return null;
            return in_array((string) $v, ['1', 'true', 'on', 'yes'], true) ? 'true' : 'false';
        };

        $capFilters = array_filter([
            'agency'       => trim((string) $request->input('agency', '')),
            'category'     => trim((string) $request->input('category', '')),
            'phase'        => trim((string) $request->input('phase', '')),
            'borough'      => trim((string) $request->input('borough', '')),
            'q'            => trim((string) $request->input('q', '')),
            // ⚠⚠ THE ENDPOINT'S `budget_line` FILTER HAD NO CONSUMER. It was built,
            // normalised on both sides through `modules/budgetline`, and verified
            // across twelve list/map combinations — and `budget_line` appeared
            // NOWHERE in `app/`, so no page could ask for it and the budget-line
            // page had nowhere to send a reader. "Check a new module has a
            // CONSUMER, not just a test."
            // ⚠ Deliberately NOT a new form control: there are 1,913 budget lines.
            // It is a URL parameter that the list, the map, the pager and the
            // filter form all carry, which is what a link into this page needs.
            'budget_line'  => trim((string) $request->input('budget_line', '')),
            'in_plan'      => $flag('in_plan'),
            'has_schedule' => $flag('has_schedule'),
            'has_location' => $flag('has_location'),
            'has_borough'  => $flag('has_borough'),
        ], function ($v) { return $v !== '' && $v !== null; });

        $listQuery = array_merge($capFilters, [
            'page' => $page, 'per_page' => self::CAPITAL_PER_PAGE,
            'sort' => $sort, 'direction' => $direction,
        ]);

        return view('projects', [
            'breadcrumbs' => Breadcrumbs::projects(),
            // ⚠ The programme tiles and the Checkbook capital-spend chart moved
            // here from /procurement (owner request). They were added there on
            // 2026-07-13 when no rebuilt capital section existed and CheckbookNYC
            // published no capital feed; with /projects and /projects/about built,
            // keeping them on a procurement page is the duplication that produced
            // the 5,128-vs-12,929 disagreement.
            // ⚠⚠ EVERY KEY THE VIEW READS MUST BE NAMED HERE — the #247 seam.
            'capital' => DatabookAPI::reqOCE('/get/capital/overview') ?: null,
            'capitalSpend' => (function () {
                    $cs = DatabookAPI::reqOCE('/oce/spending/capital-by-year', 30);
                    return (!$cs || !is_array($cs)) ? ['labels' => [], 'values' => []] : $cs;
                })(),

            // ⚠⚠ EVERY KEY THE VIEW READS MUST BE NAMED HERE. This controller
            // passes an explicit array, so a payload the API serves and the
            // Blade reads still arrives as null unless it is listed — and
            // `?? []` in the view makes that SILENT (#247).
            'capList' => DatabookAPI::reqOCE('/get/capital/projects?' . http_build_query($listQuery), 15) ?: null,
            'capOptions' => DatabookAPI::reqOCE('/get/capital/projects/filters', 15) ?: null,

            // ⚠ THE MAP'S URL IS BUILT FROM `$capFilters`, THE SAME ARRAY THE
            // LIST REQUEST USED — never from a second read of the request. The
            // map is fetched by the browser because it is 1.68 MB of centroids
            // at its widest and the page must render before it arrives; the
            // FILTERS it carries are decided here, once.
            'capGeojsonUrl' => DatabookAPI::url('/get/capital/geojson?' . http_build_query($capFilters)),

            'capFilters' => $capFilters,
            'capPage' => $page,
            'capSort' => $sort,
            'capDirection' => $direction,

            // ⚠ `globStats` IS GONE FROM THIS PAGE, and that is the point of the
            // rewrite. It served four tiles — Number of Projects / Original Cost
            // / Current Cost / Amount Over Budget — computed by
            // `rebuild_glob_stats` over `capitalprojectsdollarscomp`, the OMB
            // series NYC RETIRED on 2023-10-26. The count it published was 5,128
            // against the spine's 17,024. "Amount Over Budget" is deliberately
            // not repointed: it is the label this section documents as carrying
            // two definitions, so the rebuild drops it rather than preserving the
            // defect under new data.
            // ⚠ Counts come from the registry SERVER-SIDE. The per-row AJAX this
            // replaces called `/get/pstats-records_no/{table}`, a route that has
            // never existed — it 404d, and the caller then DELETED the row, so
            // the accordion rendered six real datasets and emptied itself.
            'datasets' => $ds->stats_data_sources(
                    DatabookAPI::req('/get/datasets/all'),
                    ['capitalprojectslist', 'capitalprojectscommitments', 'capprojectsbudgetsandschedule', 'capprojectsbudgetandspend', 'capprojectsbudgetspendhistory', 'capprojectsschedulehistory'],
                    ProjectsDatasets::rowCounts()
                ),
           ####### seo ########
            'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
            'map' => true,
        ]);
    }


    /**
     * Show capital projectcts archive view.
     *
     * @return \Illuminate\View\View
     */
    public function prjTypes_a()
    {
		$dd = DatabookAPI::req('/get/capitalprojects/taxonomy/all');
		$ds = new ProjectsDatasets();
		if (!$dd || !is_array($dd)) {
			$dd = [];
		}
		// ⚠⚠ THE SET OF TYPES THAT HAVE A PAGE, so the index links only those.
		// Measured 2026-09-10 across all 202 published names: 194 resolve and
		// **8 return 404** — their only rows live in the two defective
		// `capitalstrategy` vintages, which the money guard drops, so the 404 is
		// CORRECT and the link to it is not. Same shape as the budget-lines
		// index's family gate, and the fifth time this section has paid for
		// "a link that lands on a 404 is worse than text".
		// ⚠ The served set is computed with the PAGE'S OWN predicate, so the
		// gate cannot drift from what it gates.
		$tsl = DatabookAPI::reqOCE('/get/capitalprojects/type-slugs', 8);
		$typeSlugs = is_array($tsl) ? array_flip($tsl['slugs'] ?? []) : [];
		foreach ($dd as $i=>$d)
	{
		if (!$d['ptype_name'])
			unset($dd[$i]);
		else {
			$tslug = CapitalSlug::make($d['ptype_name']);
			// ⚠ An EMPTY served set means the lookup failed, not that nothing
			// resolves. Degrading to "link nothing" would silently strip every
			// link on the page — so with no answer, behave as before.
			$ok = empty($typeSlugs) || isset($typeSlugs[$tslug]);
			$dd[$i] = array_merge($d, [
				'link' => $ok ? route('prjType', ['tslug' => $tslug]) : null,
			]);
		}
	}
    return view('prjTypesA', [
					'breadcrumbs' => Breadcrumbs::prjTypes_a(),
					'data' => $dd,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Ten-Year Capital Strategy'))[0] ?? null,
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							['capitalprojectsdollarscomp', 'capitalbudget', 'capitalcommitmentplan', 'capitalstrategy'],
							ProjectsDatasets::rowCounts()
						),
					'tblStatsUrl' => DatabookAPI::url('/get/pstats-records_no/tblname'),
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					#'map' => true,
				]);
    }		


    /**
     * Show project type page main view.
     *
     * @return \Illuminate\View\View
     */
    public function prjType_a($tslug)
    {
		$ds = new ProjectsDatasets();
		$data = DatabookAPI::req('/get/pstats-categories_by_type/' . $tslug);
		if (!$data || !is_array($data) || empty($data)) {
			return abort(404);
		}
		foreach ($data as $i=>$d)
			$data[$i]['category-slug'] = CapitalSlug::make($d['category']);
        return view('prjTypeA', [
					'breadcrumbs' => Breadcrumbs::prjType_a($data[0]['prjtypename']),
					'data' => $data,
					'budg_lines_url' => DatabookAPI::url('/get/budglines_by_prjtype/' . $tslug),
					'prj_commitments_url' => DatabookAPI::url('/get/commitments_by_prjtype/' . $tslug),
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							['capitalstrategy', 'capitalbudget', 'capitalcommitmentplan'],
							ProjectsDatasets::rowCounts()
						),
					'tblStatsUrl' => DatabookAPI::url("/get/pstats-records_no-by_prjtype/tblname/{$tslug}"),
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
				]);
    }		


    /**
     * Show project categories directory main view.
     *
     * @return \Illuminate\View\View
     */
    public function categories_a()
    {
		$data = DatabookAPI::req("/get/pstats-categories/all");
		if (isset($data['rows'])) {
			$data = $data['rows'];
		}

		if (!$data || !is_array($data)) {
			$data = [];
		}
		foreach ($data as $i=>$d)
			$data[$i]['category-slug'] = CapitalSlug::make($d['category']);
        return view('categoriesA', [
					'breadcrumbs' => Breadcrumbs::categories_a(),
					'data' => $data,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Ten-Year Capital Strategy'))[0] ?? null,
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					#'map' => true,
				]);
    }		


    /**
     * Show project strategy category page main view.
     *
     * @return \Illuminate\View\View
     */
    public function category_a($cslug)
    {
		// ⚠⚠ THE STRATEGY IS NO LONGER WHAT DECIDES THE PAGE EXISTS. It used to
		// `abort(404)` whenever `capitalstrategy` had no row — and the strategy is
		// a PROGRAMME-level plan table (267 rows for a whole city, no project
		// key), so a category can be entirely absent from it while the spine holds
		// hundreds of real projects in it. Measured:
		// `neighborhood-parks-playgrounds-and-ballfields` has **0 strategy rows
		// and 1,036 spine projects**, and 404'd.
		// ⚠ The page 404s only when BOTH are empty — which is the honest test of
		// whether the category exists at all.
		$data = DatabookAPI::req("/get/capitalprojects/stratcategory/{$cslug}");
		$spine = DatabookAPI::reqOCE("/get/capital/projects/by-category/{$cslug}", 12);
		$spineRows = is_array($spine) ? ($spine['rows'] ?? []) : [];
		if (!$data && !$spineRows)
			return abort(404);
		// ⚠ The breadcrumb and heading need a name; take the strategy's spelling
		// when it has one, else the spine's, else the slug. Never a raw `$data[0]`
		// subscript — that is what 500s a page whose one source is empty.
		$catName = $data[0]['Ten-Year Plan Category']
			?? ($spineRows[0]['ten_year_category'] ?? Str::title(str_replace('-', ' ', $cslug)));
		$ds = new ProjectsDatasets();
		// ⚠⚠ THE SPINE CONTRACT, NOT `main`. `main` is written against
		// `capitalprojectsdollarscomp` — retired 2023-10-26 — and its money fields
		// multiply by 1000 because that series publishes thousands. See the note
		// on `spine` in ProjectsDatasets.
		$details = $ds->get('spine');
		$prjTypes = [];
		foreach ($data as $d)
			if ($d['Project Type Description'])
				$prjTypes[$d['Project Type Description']] = route('prjType', ['tslug'=> CapitalSlug::make($d['Project Type Description'])]);
        return view('categoryA', [
					'breadcrumbs' => Breadcrumbs::category_a($catName),
					// ⚠⚠ THE PROJECT LIST NOW COMES FROM THE SPINE. The old endpoint was
					// `SELECT * FROM capitalprojectsdollarscomp` — measured on one real
					// category, `UTILITY RELOCATION FOR SE AND WM PROJECTS` returned **2
					// projects** where the spine has **268**.
					// ⚠ And its slug rule was `replace(' ', '-')`, which is NOT how
					// Laravel builds the slug in the URL: **12 of 138 categories** carry a
					// comma, so `large, major and regional park reconstruction` never
					// matched and fell through to a loose `ILIKE '%…%'`. The new endpoint
					// slugs BOTH SIDES the same way, so it is exact or nothing.
					'prjsUrl' => DatabookAPI::url("/get/capital/projects/by-category/{$cslug}"),
					// ⚠⚠ THE MAP'S OWN SOURCE, SCOPED THE SAME WAY. This page's table was
					// repointed at the spine and its map was left reading `GEO_JSON` off
					// that table — a column the spine does not serve — so it drew **0
					// features** with a clean container, a loaded style and an empty
					// console. Measured 2026-09-10 on `routine-reconstruction` (447
					// projects in the table, 0 pins) and
					// `neighborhood-parks-playgrounds-and-ballfields` (1,036, 0).
					// ⚠ `ten_year_category`, NOT `category`: the geojson endpoint's
					// `category` is CPDB's coarse 3-value ASSET class, and two things
					// called `category` is the ambiguity this repo retired on the stats
					// endpoint. The slug is compared through the one `_SLUG_SQL` rule, so
					// the 12 categories carrying a comma resolve here exactly as they do
					// in the list.
					'capGeojsonUrl' => DatabookAPI::url('/get/capital/geojson?' . http_build_query(['ten_year_category' => $cslug])),
					#'dates_req_url' => DatabookAPI::url('/get/capitalprojects/dates'),
					'data' => $data,
					'catName' => $catName,
					'details' => $details,
					'prjTypes' => $prjTypes,
					// ⚠ The spine tiles. `#over_budg_am` (Amount Over Budget) is GONE, not
					// renamed — see the note in categoryA's loadFinStat.
					'finStatSelectors' => ['#projects_no', '#in_plan_no', '#planned_cost', '#spent_cost', '#sched_no'],
					// ⚠⚠ NOW WIDENED — the blocker was the WRONG ZERO, and it is fixed.
					// This panel is `mode="scoped"`: every row's cell is a PER-SCOPE count
					// from `/get/pstats-records_no-by_category/{table}/{slug}`. That
					// endpoint used to return **0** for any table it had no rule for, and
					// the component's own rule reads 0 as "this dataset holds nothing for
					// this scope — a finding". So adding these three published a
					// confident, plausible, wrong zero about datasets this page's own
					// table draws 447 spine projects from, and the omission was the lesser
					// defect.
					// ⭐ `modules/capitalsources` now answers for them, by counting each
					// source's rows through the PROJECT they belong to via the spine —
					// measured on `routine-reconstruction`: capitalprojectslist **413**,
					// capitalprojectscommitments **953**,
					// capprojectsbudgetsandschedule **3,465**, against 447 spine projects.
					// A table that genuinely cannot be scoped now answers `null`, which
					// renders `—`, never 0.
					// ⚠ `capitalprojectslist`'s 413 is cross-checked, not just plausible:
					// that table IS the current plan, so its count must equal the spine's
					// in-plan count for the category — and across all 138 category slugs,
					// 0 disagree.
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							['capitalstrategy', 'capitalprojectsdollarscomp',
							 'capitalprojectslist', 'capitalprojectscommitments',
							 'capprojectsbudgetsandschedule'],
							ProjectsDatasets::rowCounts()
						),
					'tblStatsUrl' => DatabookAPI::url("/get/pstats-records_no-by_category/tblname/{$cslug}"),
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					'map' => true,
					'cslug' => $cslug,
				]);
    }		


    /**
     * Show project categories directory main view.
     *
     * @return \Illuminate\View\View
     */
    public function budgetLines_a()
    {
		$data = DatabookAPI::req('/get/pstats-categories/recent');
		if (!$data || !is_array($data)) {
			$data = [];
		}
		foreach ($data as $i=>$d)
			$data[$i]['category-slug'] = CapitalSlug::make($d['category']);
        // ⚠⚠ THE SET OF FAMILIES THAT HAVE A PAGE, so the index links only those.
        // The index groups by `capitalbudget."Project Type Name"` (41 values) and
        // the spine's families are 39; **only 25 slugs match** — the other 16 are
        // the same programmes spelled differently (`PARKS` vs `Parks and
        // Recreation`, `FIRE` vs `Fire Department`). Linking every header would
        // 404 on 39% of them, and a link that lands on a 404 is worse than text.
        $fams = DatabookAPI::reqOCE('/get/capital/families', 8);
        $famSlugs = is_array($fams) ? ($fams['slugs'] ?? []) : [];

        return view('budgetLinesA', [
					'breadcrumbs' => Breadcrumbs::budgetLines_a(),
					'data' => $data,
					'famSlugs' => $famSlugs,
					'dataUrl' => DatabookAPI::url('/get/capitalbudget/bydate/recent'),
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Capital Budget'))[0] ?? null,
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					#'map' => true,
				]);
    }		


    /**
     * Show project budget line page main view.
     *
     * @return \Illuminate\View\View
     */
    /**
     * One BUDGET-LINE FAMILY: the projects funded through it.
     *
     * ⚠⚠ THIS IS NOT `/projects/types/{slug}`, AND CONFLATING THE TWO IS THE
     * DEFECT THIS PAGE EXISTS TO END. Measured 2026-09-08: the spine's
     * `project_types` is **39** values (the deduplicated budget-line families a
     * project is funded through — `P`→Parks and Recreation, `HW`→Highways);
     * `capitalstrategy."Project Type Description"`, which `/projects/types/`
     * is keyed on, is **236** values of Ten-Year Strategy WORK TYPE. They share
     * **5 names, every one a coincidence**.
     *
     * ⚠ The family dimension is project-level (12,929 projects, exactly the
     * current plan) where the strategy's has no project key at all — which is
     * why this page can list projects and that one cannot.
     */
    public function budgetLineFamily_a($fslug)
    {
        $d = DatabookAPI::reqOCE('/get/capital/projects/by-family/' . rawurlencode($fslug), 15);
        if ($d === false || !is_array($d))
            return response()->view('errors.service-unavailable', [], 503);
        $rows = $d['rows'] ?? [];
        if (!$rows)
            return abort(404);

        $ds = new ProjectsDatasets();
        return view('budgetLineFamilyA', [
                    'breadcrumbs' => Breadcrumbs::budgetLines_a(),
                    'family' => $d['family'] ?? $fslug,
                    'fam' => $d,
                    // ⚠ The SPINE contract — `main` multiplies money by 1000 for
                    // the retired series' thousands. See ProjectsDatasets.
                    'details' => $ds->get('spine'),
                    'prjsUrl' => DatabookAPI::url('/get/capital/projects/by-family/' . rawurlencode($fslug)),
                    'datasets' => $ds->stats_data_sources(
                            DatabookAPI::req('/get/datasets/all'),
                            ['capitalprojectslist', 'capitalprojectscommitments'],
                            ProjectsDatasets::rowCounts()
                        ),
                   ####### seo ########
                    'pagetitle' => ($d['family'] ?? $fslug) . ' | Budget-line family | NYC Databook',
                    'snippet' => 'Capital projects funded through the ' . ($d['family'] ?? $fslug) . ' budget-line family.',
                ]);
    }


    public function budgetLine_a($blcode, $blslug=null)
    {
		$enc = rawurlencode($blcode);
		$data = DatabookAPI::req("/get/capitalbudget/{$enc}");
		if (!$data)
			return abort(404);
		// ⚠⚠ THIS FALLBACK NAMED A COLUMN THAT DOES NOT EXIST, AND EVERY BUDGET
		// LINE 500'd FOR IT. `/get/capitalbudget/{code}` serves **`Project Type
		// Name`**; the fallback looked for `Project Type Description` (which is
		// `capitalstrategy`'s column, a different table), so it never fired and
		// `budgetLineA.blade.php:731` hit `Undefined index: wegov-prjtype-name`.
		// Measured 2026-09-08: all five budget lines on a real project profile
		// returned 500, and `capitalbudget` carries `Project Type Name` on
		// **16,491 of 16,491 rows, 0 blank** — so the fallback now always fires.
		//
		// ⚠ BOTH SPELLINGS ARE TRIED, in order, because the two feeds really do
		// differ and a future one may use either. The `??=` chain degrades to
		// null rather than raising: a missing DISPLAY LABEL must never take the
		// page down, which is the disproportion this defect was made of.
		foreach ($data as &$row) {
			if (!isset($row['wegov-prjtype-name']))
				$row['wegov-prjtype-name'] = $row['Project Type Name']
					?? $row['Project Type Description'] ?? null;
		}
		unset($row);
		$ds = new ProjectsDatasets();
		// ⚠⚠ THE SPINE CONTRACT, NOT `main`. `main` is written against
		// `capitalprojectsdollarscomp` (retired 2023-10-26) and its money fields
		// multiply by 1000 because that series publishes THOUSANDS; the spine is
		// USD, so reusing `main` here would render every figure a thousand times
		// too large and look entirely plausible (invariant 2). See the note on
		// `spine` in ProjectsDatasets.
		// ⚠ `spine` declares NO `pubdate_filter`, which is what removes the
		// column-1 publication-date control from this page — see the view.
		$details = $ds->get('spine');
        return view('budgetLineA', [
					'breadcrumbs' => Breadcrumbs::budgetLine_a($data[0]['Budget Line'], $data[0]['Budget Line Title']),
					// ⚠⚠ THE PROJECT TABLE NOW COMES FROM THE SPINE. The old endpoint was
					// `SELECT * FROM capitalprojectsdollarscomp` — measured on `EP 0007`
					// (2026-09-10) it served **34 rows for 9 distinct projects**, one per
					// publication vintage, against the spine's **60 projects**; and the
					// page's own publication-date control then cut those 34 to **1**, so
					// the rendered table read *"Showing 1 to 1 of 1 entries (filtered from
					// 34 total entries)"* directly under a tile saying 60.
					// ⚠ `$enc` is the code as `capitalbudget` publishes it — with a SPACE
					// (`EP 0007`) on all 15,742 rows, where the spine stores `EP-0007`. The
					// endpoint normalises through `modules/budgetline`, so this passes the
					// code as it came rather than minting a second spelling of that rule
					// in PHP (invariant 14).
					'prjsUrl' => DatabookAPI::url("/get/capital/projects/by-budget-line/{$enc}"),
					// ⚠⚠ THE MAP READS THE SAME SCOPE, SERVED — it does not scrape the
					// table's rows for a `GEO_JSON` column the spine does not have. The old
					// page built its features from `r['GEO_JSON']` on the retired series'
					// rows, which drew **7 features for 3 distinct projects** (the same
					// project plotted once per vintage); this scope has **20** projects with
					// a published location out of 60. `budget_line` is the only filter, so
					// the map and the table cannot answer different questions.
					'capGeojsonUrl' => DatabookAPI::url('/get/capital/geojson?' . http_build_query(['budget_line' => $blcode])),
					'capCommUrl' => DatabookAPI::url("/get/capitalcommitments/stats_by_budgetline/{$enc}"),
					'commUrl' => DatabookAPI::url("/get/commitments/by_budgetline/{$enc}"),
					'data' => $data,
					'details' => $details,
					// ⚠⚠ THE EIGHT `finStatSelectors` TILES ARE GONE. They were summed in
					// the browser from the retired series' rows currently shown in the
					// table, times 1000, and they contradicted each other: EP-0007 read
					// `Projects 1`, `Original Cost $502M`, `Current Cost $474M` and
					// `Amount Over Budget $297M` — $28M under budget beside a claim of
					// $297M over — while the spine has **60** projects on that line.
					// ⚠ Server-rendered from the spine's own budget-line scope now, the
					// same shape the district and org capital tabs use.
					// ⚠ `$enc` is the code as published by `capitalbudget`, which spells
					// it with a SPACE (`EP 0007`) on all 15,742 rows while the spine
					// spells it `EP-0007`. The endpoint normalises through
					// `modules/budgetline`, so this passes the code as it comes rather
					// than minting a second spelling of that rule in PHP.
					'capital' => DatabookAPI::reqOCE("/get/capital/stats/budget_line/{$enc}") ?: null,
					// The code itself, for the link to the spine's own list of this
					// line's projects. Taken from the served row, never re-derived.
					'blCode' => $data[0]['Budget Line'] ?? $blcode,
					// ⚠⚠ NOW WIDENED — the blocker was the WRONG ZERO, and it is fixed.
					// This panel is `mode="scoped"`, so every cell is a PER-SCOPE count
					// from `/get/pstats-records_no-by_budgetline/{table}/{code}`. That
					// endpoint returned **0** for any table it had no rule for, and the
					// component reads 0 as "this dataset holds nothing for this scope — a
					// finding". It also 500'd on FOUR of its eight declared tables,
					// naming `"BUDGET_LINE"` where the column is `Budget Line` or absent.
					// ⭐ Measured on `EP 0007` now: capitalbudget 30 · commitment plan 32 ·
					// capitalprojectscommitments 82 · the 2023 series 34 ·
					// capprojectsbudgetsandschedule 33 · capitalprojectslist **60**, which
					// equals the spine's own project count for the line.
					// ⚠⚠ AND THE TWO COUNTING METHODS ARE NOT INTERCHANGEABLE HERE. A
					// project is funded through SEVERAL budget lines, so counting a
					// source's rows through the project would give 568 commitment rows
					// where 82 actually name this line. `modules/capitalsources` therefore
					// prefers each table's OWN budget-line column and uses the project
					// crosswalk only where there is none — and the endpoint SERVES which
					// method it used, so the two are distinguishable rather than mixed.
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							['capitalbudget', 'capitalcommitmentplan', 'capitalprojectscommitments',
							 'capitalprojectsdollarscomp', 'capitalprojectslist',
							 'capprojectsbudgetsandschedule'],
							ProjectsDatasets::rowCounts()
						),
					'tblStatsUrl' => DatabookAPI::url("/get/pstats-records_no-by_budgetline/tblname/{$enc}"),
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					'map' => true,				
				]);
    }		


    /**
     * Show projects commitments directory main view.
     *
     * @return \Illuminate\View\View
     */
    	public function commitments_a()
	{
		$data = DatabookAPI::req('/get/capitalcommitmentplan/all');
        return view('prjCommitmentsA', [
					'breadcrumbs' => Breadcrumbs::prjCommitments_a(),
					'data' => $data,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Capital Commitment Plan'))[0] ?? null,
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					#'map' => true,
				]);
    }		




    /**
     * Show minor capital projects main view.
     *
     * @return \Illuminate\View\View
     */
    public function mProjects()
    {
        $data = DatabookAPI::req('/get/mcapitalprojects/all');
        if (!is_array($data) || isset($data['detail'])) {
            $data = [];
        }
        // ⚠⚠ `datasets` WAS NEVER PASSED, AND `main` ONLY GOT AWAY WITH IT
        // BECAUSE ITS SOLE CONSUMER WAS DEAD CODE. The old view's
        // `@foreach($datasets ...)` sat inside a Blade comment (lines 190-212),
        // so the variable was never evaluated and the page returned 200 with a
        // latent missing key. Migrating this page to <x-db.data-provenance>
        // gave it a LIVE consumer and the page began 500ing with
        // `Undefined variable: datasets` — the #247 controller seam again, and
        // caught by #383's page-family sweep on its first real use.
        $ds = new ProjectsDatasets();
        return view('mProjects', [
					'breadcrumbs' => Breadcrumbs::mProjects(),
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Capital Projects Database (CPDB) - Projects'))[0] ?? null,
					// ⚠ Scoped to the COMMITMENTS datasets, which is what this
					// page is about in its own words: projects that received
					// financial commitments but are not documented in the main
					// CPDB project datasets. Passing the full capital set would
					// claim sources this page does not draw on.
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							['capitalprojectscommitments', 'capitalcommitmentplan'],
							ProjectsDatasets::rowCounts()
						),
					'data' => $data,
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					'map' => false,
				]);
    }		

	
    /**
     * Show minor capital project.
     *
     * @param  string  	$prjId
     * @return \Illuminate\View\View
     */
    public function mProject($maprojid)
    {
		$section = 'projects';
		$prj = DatabookAPI::req("/get/capitalprojects/mcore/{$maprojid}");
		if (!$prj || !isset($prj[0])) {
			return abort(404);
		}
		//print_r($prj);
		//die();
		$org = DatabookAPI::req("/get/orgs/profile/{$prj[0]['wegov-org-id']}")[0] ?? null;
		$ds = new OrgsDatasets();
		$details = $ds->get($section);
		return $prj
			? view('mProject', [
					'id' => $prj[0]['wegov-org-id'],
					'prjId' => $maprojid,
					'pagetitle' => "{$prj[0]['description']} | {$maprojid}",
					'org' => $org,
					'section' => $section,
					'slist' => $ds->list,
					'menu' => $ds->menu,
					'activeDropDown' => $ds->menuActiveDD($section),
					'icons' => $ds->socicons,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Capital Projects Database (CPDB) - Projects'))[0] ?? null,
					//'url' => DatabookAPI::url("/get/capitalprojects/mcore/{$maprojid}"),
					'prj' => $prj[0],
					'commUrl' => DatabookAPI::url("/get/capitalprojects/commitments/{$prj[0]['projectid']}"),
					'breadcrumbs' => Breadcrumbs::mProject($maprojid, $prj[0]['description']),
					'map' => true,
				   ####### seo ########
					#'schema' => Schema::project($prj[0], $org),
					'pagetitle' => "{$prj[0]['description']} | WeGovNYC Databook Capital Projects",
					'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', "{$maprojid}"),
					'canonicalUrl' => route('mProject', ['maprojid' => $maprojid]),
				])
			: abort(404);
    }


}