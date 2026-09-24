<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\OrgsDatasets;
use App\Custom\ProjectsDatasets;
use App\Custom\UnDatasets;
use App\Custom\Breadcrumbs;
use App\Custom\CapProjectsBuilder;
use App\Custom\CapProjectsBuilder2024;
use App\Custom\DatabookAPI;
use App\Custom\Schema;
use App\Custom\OrgChart;
use Illuminate\Support\Str;


class Organizations extends Controller
{
	/**
	 * Show organizations list.
	 *
	 * @return \Illuminate\View\View
	 */
	public function root()
	{
		try {
			$dates = DatabookAPI::req('/get/capitalprojects/dates');
			$date = ($dates && isset($dates[0]['PUB_DATE'])) ? $dates[0]['PUB_DATE'] : '2024-01-01';
		} catch (\Exception $e) {
			// If API call fails, use default date
			$date = '2024-01-01';
		}
		return view('root', [
			'breadcrumbs' => Breadcrumbs::root(),
			// >> THE HOME CAPITAL CARD IS OFF THE RETIRED SERIES (Phase 4).
			// `projects_no`/`orig_cost`/`curr_cost` came from `cached_stats`
			// over `capitalprojectsdollarscomp`, which NYC retired 2023-10-26:
			// the card published 5,128 projects against the spine's 17,024
			// tracked / 12,929 in the current plan. Their three hydration URLs
			// are removed with the tiles - leaving a URL for an id the page no
			// longer renders is how `loadTableStat` throws on every load.
			'capital' => DatabookAPI::reqOCE('/get/capital/overview'),
			// ⚠⚠ THE OTHER FIVE `pstats-*` URLs AND `tblStatsUrl` ARE GONE TOO, and
			// they were the same defect one step further along: the home page
			// renders NONE of `over_budg_am`, `long_no`, `over_budg_no`,
			// `late_start_no`, `late_end_no`, and never reads `tblStatsUrl` at all.
			// Measured on the rendered page 2026-09-10 — **0 pstats requests, 24 of
			// 24 tiles hydrated, 0 uncaught JS** — because the loop consuming them
			// sits inside a `/* */` block. So it was inert, not broken. Deleting it
			// is still right: this is the section that keeps having to re-establish
			// which surfaces read the retired series, and dead config naming
			// `#over_budg_am` on the front page is the most expensive place to
			// leave that question open.
			'globStats' => DatabookAPI::reqOCE('/pipeline/globstats') ?: json_decode(file_get_contents(public_path('data/globStats.json')), true),
			####### seo ########
			'pagetitle' => "NYC DataBook - Open Data Application for New York City Government Transparency",
			'articles' => (new \App\Services\PayloadService())->getLatestArticles(3, 'Databook'),
		]);
	}


	/**
	 * Show organizations list.
	 *
	 * @return \Illuminate\View\View
	 */
	public function about()
	{
		$ds = new OrgsDatasets();
		return view('about', [
			#'breadcrumbs' => Breadcrumbs::about(),
			####### seo ########
			'pagetitle' => "About NYC Databook - Award-Winning Open Data NYC Government Transparency App",
			'datasets' => $ds->all_data_sources(DatabookAPI::req('/get/datasets/all')),
			'slist' => $ds->list,
			'allDS' => $ds->dd,
		]);
	}


	/**
	 * Show organizations list.
	 *
	 * @return \Illuminate\View\View
	 */
	public function orgsChart($id = null)
	{
		// Built live from /get/orgs/chart in two views — see App\Custom\OrgChart
		// for why this is no longer a static file (it was 5 months stale, and
		// written to a container path nginx never served).
		$view = ($_GET['view'] ?? '') === 'nyc' ? 'nyc' : 'databook';
		$orgs = DatabookAPI::req('/get/orgs/chart');
		$chart = $orgs ? OrgChart::build($orgs, $view) : null;
		$counts = $orgs ? [
			'databook' => OrgChart::countNodes(OrgChart::build($orgs, 'databook')),
			'nyc' => OrgChart::countNodes(OrgChart::build($orgs, 'nyc')),
		] : ['databook' => 0, 'nyc' => 0];

		// Fall back to the last generated file only if the API is unreachable,
		// so a deploy restart shows a stale chart rather than none.
		if (!$chart)
		{
			$chartPath = public_path('data/orgChart.json');
			$chart = is_file($chartPath)
				? json_decode(file_get_contents($chartPath), true) : null;
		}
		return view('orgsChart', [
			'breadcrumbs' => Breadcrumbs::orgsChart(),
			'chart' => $chart,
			'chartView' => $view,
			'chartCounts' => $counts,
			'defType' => $_GET['type'] ?? 'City Agency',
			'defTag' => $_GET['tag'] ?? null,
			'defSearch' => $_GET['search'] ?? null,
			'defId' => $id,
			####### seo ########
			'pagetitle' => "City Agency & Organizations - Open Data Driven Profiles by NYC Databook",
		]);
	}


	/**
	 * Show organizations list.
	 *
	 * @return \Illuminate\View\View
	 */
	public function orgsDirectory()
	{
		return view('orgsDirectory', [
			'url' => DatabookAPI::url('/get/orgs/directory'),
			'breadcrumbs' => Breadcrumbs::orgs(),
			'defType' => $_GET['type'] ?? 'City Agency',
			'defTag' => $_GET['tag'] ?? null,
			'defSearch' => $_GET['search'] ?? null,
			'globStats' => DatabookAPI::reqOCE('/pipeline/globstats') ?: json_decode(file_get_contents(public_path('data/globStats.json')), true),
			####### seo ########
			'pagetitle' => "City Agency & Organizations - Open Data Driven Profiles by NYC Databook",
		]);
	}


	/**
	 * Show city agencies only.
	 *
	 * @return \Illuminate\View\View
	 */
	public function orgsAgencies()
	{
		return view('orgsAgencies', [
			// /get/orgs/agencies, not /get/orgs/directory: the server owns which
			// types count as a city agency (api/modules/orgfilter.py). The page
			// used to narrow the directory itself with a JS regex on the literal
			// 'City Agency', which silently emptied when the OTI adoption
			// retyped 240 orgs onto OTI's vocabulary.
			'url' => DatabookAPI::url('/get/orgs/agencies'),
			'globStats' => DatabookAPI::reqOCE('/pipeline/globstats') ?: json_decode(file_get_contents(public_path('data/globStats.json')), true),
			'pagetitle' => "NYC City Agencies - Data Driven Profiles by NYC Databook",
		]);
	}


	/**
	 * Show organizations list.
	 *
	 * @return \Illuminate\View\View
	 */
	public function orgsAll($req=null)
	{
		return view('orgsAll', [
			'url' => DatabookAPI::url('/get/orgs/all'),
			'breadcrumbs' => Breadcrumbs::orgsAll(),
			'defType' => $_GET['type'] ?? null,
			'defTag' => $_GET['tag'] ?? null,
			'defSearch' => $req ?? $_GET['search'] ?? null,
			####### seo ########
			'pagetitle' => "City Agency & Organizations - Open Data Driven Profiles by NYC Databook",
		]);
	}


	/**
	 * Show organization profile - section about.
	 *
	 * @param  int  $id
	 * @return \Illuminate\View\View
	 */
	/**
	 * Fetch an org profile, distinguishing a transient API outage from a genuine
	 * not-found. DatabookAPI::req() returns `false` when the API is unreachable
	 * (e.g. mid-deploy restart) and `[]` when the API is up but the org doesn't
	 * exist. On a transient failure we retry once, then return a 503 (retryable,
	 * auto-refreshing) instead of a hard, cacheable 404. Returns the org row, or
	 * null when the org genuinely isn't found (caller aborts 404).
	 */
	/**
	 * The name to SHOW for an org.
	 *
	 * `display_name` carries NYC's official name from the OTI agency registry
	 * (t3jq-9nkf) wherever it differs from ours. ⚠ Display ONLY — `name` remains
	 * the join key into contracts.agency (see oce.py::_resolve_org_id and
	 * /oce/agency/summary?name=) and the source of every /o/{id}-{slug} URL, so
	 * slugs, canonical links, procurement lookups and cache keys must keep using
	 * $org['name'].
	 */
	protected static function dispName($org)
	{
		return ($org['display_name'] ?? null) ?: ($org['name'] ?? '');
	}

	protected function fetchOrg($id)
	{
		$rows = DatabookAPI::req("/get/orgs/profile/{$id}");
		if ($rows === false) {
			usleep(500000); // ride out a micro-blip before giving up
			$rows = DatabookAPI::req("/get/orgs/profile/{$id}");
		}
		if ($rows === false) {
			abort(response()->view('errors.service-unavailable', [], 503, ['Retry-After' => '5']));
		}
		$org = $rows[0] ?? null;
		if ($org)
			$org['civic_vendor'] = self::vendorActivity($id);
		return $org;
	}

	/**
	 * Track B: does this org also hold City contracts as a PASSPort vendor?
	 *
	 * Attached here rather than passed to each view because EVERY org page route
	 * already funnels through fetchOrg() (#135), so the shared header partial can
	 * read it off $org without changing a single view signature.
	 *
	 * Returns null on anything unexpected — an org profile must never fail
	 * because an additive panel could not load.
	 */
	protected static function vendorActivity($id)
	{
		$r = DatabookAPI::reqOCE("/oce/org/vendor-activity?org_id=" . (int)$id, 8);
		if (!is_array($r) || empty($r['linked']))
			return null;
		return $r;
	}

	public function orgAbout($id, $orgslug = '')
	{
		$org = $this->fetchOrg($id);
		$dispName = self::dispName($org);
		if (!$org)
			return abort(404);
		if (preg_match('~Union|Bargaining Unit~si', $org['type']))
			return redirect(route('orgSection', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-'), 'section' => 'civil-service-titles']));

		$ds = new OrgsDatasets();
		#$details = $ds->getAbout('jobs');
		$details = $ds->get('jobs-about');
		$positionDetails = $ds->get('positions');
		return view('organization', [
			'id' => $id,
			'org' => $org,
			'slist' => $ds->list,
			'menu' => $ds->menu,
			'activeDropDown' => '',
			'icons' => $ds->socicons,
			'allDS' => $ds->dd,
			'details' => $details,
			'url' => ($details['fapireq'] ?? null)
				? DatabookAPI::url(sprintf($details['fapireq'], $id))
				: DatabookAPI::url("/get/orgs/section/{$id}/{$details['table']}"),
			'positionDataUrl' => DatabookAPI::url("/get/orgs/stats-civillist-aggregated/{$id}"),
			'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
			'tableStatUrls' => [
				'reg' => DatabookAPI::url("/get/orgs/stats-reg/{$id}/tablename"),
				'notices' => DatabookAPI::url("/get/orgs/stats-notices/{$id}/sectionTitle"),
				'noticesEvents' => DatabookAPI::url("/get/orgs/stats-events/{$id}"),
			],
			'finStatUrls' => [
				'headcount' => DatabookAPI::url("/get/orgs/stats-headcount/{$id}"),
				'pastheadcount' => DatabookAPI::url("/get/orgs/stats-pastheadcount/{$id}"),
				'as' => DatabookAPI::url("/get/orgs/stats-as/{$id}"),
				'ac' => DatabookAPI::url("/get/orgs/stats-ac/{$id}"),
				'prj' => DatabookAPI::url("/get/orgs/stats-prj/{$id}"),
			],
			'finStatYear' => 2025,
			'breadcrumbs' => Breadcrumbs::org($id, self::dispName($org)),
			'newsUrl' => DatabookAPI::url("/get/orgs/frontnews/{$id}"),
			'eventsUrl' => DatabookAPI::url("/get/orgs/frontevents/{$id}"),
			'procurementSummaryUrl' => DatabookAPI::url("/oce/agency/summary?name=" . rawurlencode($org['name'])),
			'procurementProfileUrl' => '/procurement/agency/' . rawurlencode($org['name']),
			'datasets' => $ds->data_sources(DatabookAPI::req('/get/datasets/all'), $id, $org['name']),

			####### seo ########
			'schema' => Schema::org($org),
			'pagetitle' => "{$dispName} | WeGovNYC Databook",
			'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', $org['description']),
			'canonicalUrl' => route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-')]),
		]);
	}


	/**
	 * Show organization profile section.
	 *
	 * @param  int  	$id
	 * @param  string  	$section
	 * @return \Illuminate\View\View
	 */
	public function orgSection($id, $orgslug = null, $section = null)
	{
		$org = $this->fetchOrg($id);
		$dispName = self::dispName($org);
		// Check if org exists before accessing its properties
		if (!$org) {
			return abort(404);
		}
		
		// Handle procurement sections specially
		if (str_starts_with($section, 'procurement-')) {
			return $this->orgProcurementSection($id, $org, $section);
		}
		
		$ds = preg_match('~Union|Bargaining Unit~si', $org['type'])
			? new UnDatasets()
			: new OrgsDatasets();
		$details = $ds->get($section);
		return $org && $details
			? view('orgsection', [
				'id' => $id,
				'org' => $org,
				'section' => $section,
				'slist' => $ds->list,
				'menu' => $ds->menu,
				'activeDropDown' => $ds->menuActiveDD($section),
				'icons' => $ds->socicons,
				'url' => ($details['fapireq'] ?? null)
					? DatabookAPI::url(sprintf($details['fapireq'], $id))
					: DatabookAPI::url("/get/orgs/section/{$id}/{$details['table']}"),
				// ⚠ THE CONTROLLER MUST NAME EVERY KEY THE VIEW READS. #247 shipped a
				// page where the API served three payload keys, the Blade read them and
				// every unit guard passed — but this array never passed them, and
				// `$x ?? []` degraded politely, so the section simply did not render.
				// Only fetching the page found it. `?? ''` here would repeat that, so
				// the key is always present and the view's fetch is a no-op when the
				// section has no table of its own.
				'coverageUrl' => isset($details['table'])
					? DatabookAPI::url("/get/orgs/section-coverage/{$details['table']}")
					: '',
				'contractWorkUrl' => DatabookAPI::url("/get/orgs/contract-work/{$id}"),
				'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
				'breadcrumbs' => Breadcrumbs::orgSect($org['id'], self::dispName($org), $section, $ds->list[$section]),
				'details' => $details,
				'map' => $details['map'] ?? null,
				####### seo ########
				#'schema' => Schema::org($org),
				'pagetitle' => "{$dispName} | WeGovNYC Databook",
				'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', $org['description']),
				'canonicalUrl' => route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-')]),


				'salaryStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-civillist_salaries_by_year"),
				'employeesStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-civillist_entries_by_year"),
				'positionsStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-positionschedule_positions_by_agency"),

			])
			: abort(404);
	}


	/**
	 * Show organization procurement section (Highlights, Contracts, Solicitations, Vendors).
	 *
	 * @param  int  	$id
	 * @param  array  	$org
	 * @param  string  	$section
	 * @return \Illuminate\View\View
	 */
	protected function orgProcurementSection($id, $org, $section)
	{
		$dispName = self::dispName($org);
		$ds = new OrgsDatasets();
		
		// Map section to subsection name
		$subsectionMap = [
			'procurement-highlights' => 'highlights',
			'procurement-contracts' => 'contracts',
			'procurement-solicitations' => 'solicitations',
			'procurement-vendors' => 'vendors',
			'procurement-transactions' => 'transactions',
		];
		
		$subsection = $subsectionMap[$section] ?? 'highlights';

		// NYCHA is a separate public authority — its procurement lives in the
		// dedicated /oce/nycha/* domains (Checkbook `_NYCHA` feeds), NOT the City
		// contracts/solicitations/spending tables that the shared agency_body reads
		// (which is why the standard tab is empty for it). Render the NYCHA hub body
		// (explanatory flag + the four domain cards) instead.
		$isNycha = (string) ($org['id'] ?? '') === '170020034'
			|| stripos($org['name'] ?? '', 'housing authority') !== false;
		if ($isNycha) {
			$orgslug = Str::slug($org['name'], '-');
			// Shared org-profile chrome for every NYCHA procurement page (org header
			// + on-page NYCHA tabs). The tabs/cards build orgSection URLs from these.
			$chrome = [
				'id' => $id,
				'org' => $org,
				'section' => $section,
				'subsection' => $subsection,
				'orgslug' => $orgslug,
				'slist' => $ds->list,
				'menu' => $ds->menu,
				'activeDropDown' => 'Procurement',
				'icons' => $ds->socicons,
				'breadcrumbs' => Breadcrumbs::orgSect($org['id'], self::dispName($org), $section, $ds->list[$section] ?? 'Procurement'),
				'canonicalUrl' => route('orgProfile', ['id' => $id, 'orgslug' => $orgslug]),
			];
			$fy = request()->input('fiscal_year');
			$q  = $fy ? "?fiscal_year={$fy}" : '';
			$qc = $fy ? "&fiscal_year={$fy}" : '';
			switch ($section) {
				case 'procurement-nycha-budget':
					$bq = trim((string) request()->input('q', ''));
					$bsort = request()->input('sort', 'modified');
					$border = request()->input('order', 'desc') === 'asc' ? 'asc' : 'desc';
					$bpage = max(1, (int) request()->input('page', 1));
					$brecUrl = '/oce/nycha/budget/records?limit=25&page=' . $bpage
						. '&sort=' . urlencode($bsort) . '&order=' . $border
						. ($fy ? '&fiscal_year=' . $fy : '') . ($bq !== '' ? '&q=' . urlencode($bq) : '');
					return view('procurement.nycha_budget', $chrome + [
						'pagetitle' => "{$dispName} — Expense Budget | WeGovNYC Databook",
						'snippet' => "NYCHA expense budget — adopted, modified, committed, and actual spending.",
						'summary' => DatabookAPI::reqOCE('/oce/nycha/budget/summary', 60) ?: ['available' => false, 'latest_year' => null, 'totals' => [], 'by_year' => [], 'by_category' => []],
						'units'   => DatabookAPI::reqOCE('/oce/nycha/budget/units' . $q, 60) ?: ['available' => false, 'data' => [], 'total' => 0],
						'records' => DatabookAPI::reqOCE($brecUrl, 60) ?: ['available' => false, 'data' => [], 'total' => 0, 'page' => 1, 'pages' => 1],
						'recFilters' => ['q' => $bq, 'fiscal_year' => $fy, 'sort' => $bsort, 'order' => $border],
					]);
				case 'procurement-nycha-revenue':
					$vq = trim((string) request()->input('q', ''));
					$vsort = request()->input('sort', 'recognized');
					$vorder = request()->input('order', 'desc') === 'asc' ? 'asc' : 'desc';
					$vpage = max(1, (int) request()->input('page', 1));
					$vrecUrl = '/oce/nycha/revenue/records?limit=25&page=' . $vpage
						. '&sort=' . urlencode($vsort) . '&order=' . $vorder
						. ($fy ? '&fiscal_year=' . $fy : '') . ($vq !== '' ? '&q=' . urlencode($vq) : '');
					return view('procurement.nycha_revenue', $chrome + [
						'pagetitle' => "{$dispName} — Revenue | WeGovNYC Databook",
						'snippet' => "NYCHA revenue — adopted, modified, and recognized by funding source.",
						'summary' => DatabookAPI::reqOCE('/oce/nycha/revenue/summary', 60) ?: ['available' => false, 'latest_year' => null, 'totals' => [], 'by_year' => [], 'by_category' => [], 'by_funding_source' => []],
						'sources' => DatabookAPI::reqOCE('/oce/nycha/revenue/sources' . $q, 60) ?: ['available' => false, 'data' => [], 'total' => 0],
						'records' => DatabookAPI::reqOCE($vrecUrl, 60) ?: ['available' => false, 'data' => [], 'total' => 0, 'page' => 1, 'pages' => 1],
						'recFilters' => ['q' => $vq, 'fiscal_year' => $fy, 'sort' => $vsort, 'order' => $vorder],
					]);
				case 'procurement-nycha-contracts':
					// Record explorer: search/filter/sort/paginate individual contracts.
					$cq    = trim((string) request()->input('q', ''));
					$csort = request()->input('sort', 'current');
					$corder = request()->input('order', 'desc') === 'asc' ? 'asc' : 'desc';
					$cpage = max(1, (int) request()->input('page', 1));
					$clim  = 25;
					$cUrl  = '/oce/nycha/contracts?limit=' . $clim
						. '&page=' . $cpage . '&sort=' . urlencode($csort) . '&order=' . $corder
						. ($cq !== '' ? '&q=' . urlencode($cq) : '') . $qc;
					return view('procurement.nycha_contracts', $chrome + [
						'pagetitle' => "{$dispName} — Contracts | WeGovNYC Databook",
						'snippet' => "NYCHA contracts — original, current, and invoiced value by vendor.",
						'summary' => DatabookAPI::reqOCE('/oce/nycha/contracts/summary', 60) ?: ['available' => false, 'totals' => [], 'by_year' => [], 'top_vendors' => []],
						'contracts' => DatabookAPI::reqOCE($cUrl, 60) ?: ['available' => false, 'data' => [], 'total' => 0, 'page' => 1, 'pages' => 1],
						'filters' => ['q' => $cq, 'fiscal_year' => $fy, 'sort' => $csort, 'order' => $corder],
					]);
				case 'procurement-nycha-spending':
					$ssum = DatabookAPI::reqOCE('/oce/nycha/spending/summary', 60) ?: ['available' => false, 'latest_year' => null, 'totals' => [], 'by_year' => [], 'by_category' => [], 'by_funding_source' => [], 'section_8' => [], 'top_vendors' => []];
					// Payment (record) explorer: FY-scoped (default latest) so each query
					// prunes to one partition instead of the full 22.56M-row lake.
					$sFy   = $fy ?: ($ssum['latest_year'] ?? null);
					$sq    = trim((string) request()->input('q', ''));
					$scat  = (string) request()->input('spending_category', '');
					$ss8   = (string) request()->input('section_8', '');
					$ssort = request()->input('sort', 'amount');
					$sorder = request()->input('order', 'desc') === 'asc' ? 'asc' : 'desc';
					$spage = max(1, (int) request()->input('page', 1));
					$recUrl = '/oce/nycha/spending/records?limit=25&page=' . $spage
						. '&sort=' . urlencode($ssort) . '&order=' . $sorder
						. ($sFy ? '&fiscal_year=' . $sFy : '')
						. ($sq !== '' ? '&q=' . urlencode($sq) : '')
						. ($scat !== '' ? '&spending_category=' . urlencode($scat) : '')
						. (in_array($ss8, ['Y', 'N'], true) ? '&section_8=' . $ss8 : '');
					return view('procurement.nycha_spending', $chrome + [
						'pagetitle' => "{$dispName} — Spending | WeGovNYC Databook",
						'snippet' => "NYCHA spending — every payment by category, funding source, and development.",
						'summary' => $ssum,
						'developments' => DatabookAPI::reqOCE('/oce/nycha/spending/by-development?sort=spending&limit=50' . ($sFy ? '&fiscal_year=' . $sFy : ''), 60) ?: ['available' => false, 'data' => [], 'total' => 0],
						'records' => DatabookAPI::reqOCE($recUrl, 60) ?: ['available' => false, 'data' => [], 'total' => 0, 'page' => 1, 'pages' => 1],
						'recFilters' => ['q' => $sq, 'fiscal_year' => $sFy, 'spending_category' => $scat, 'section_8' => $ss8, 'sort' => $ssort, 'order' => $sorder],
					]);
				case 'procurement-nycha-contract':
					// Individual NYCHA contract profile (detail + actual payments).
					$cpId = trim((string) request()->input('id', ''));
					if ($cpId === '') {
						return redirect(route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => 'procurement-nycha-contracts']));
					}
					$cp = DatabookAPI::reqOCE('/oce/nycha/contract?id=' . urlencode($cpId), 60);
					if (!$cp || empty($cp['available'])) {
						abort(404, 'NYCHA contract not found');
					}
					return view('procurement.nycha_contract_profile', $chrome + [
						'pagetitle' => "{$cpId} — NYCHA Contract | WeGovNYC Databook",
						'snippet' => "NYCHA contract {$cpId} — value, vendor, and actual payments (Checkbook NYC).",
						'cp' => $cp,
						'cid' => $cpId,
					]);
				case 'procurement-nycha-vendors':
					// Directory of every NYCHA vendor. Matched vendors link to the
					// City vendor profile; unmatched get a NYCHA-native profile.
					$nvq = trim((string) request()->input('q', ''));
					$nvsort = request()->input('sort', 'spending');
					$nvorder = request()->input('order', 'desc') === 'asc' ? 'asc' : 'desc';
					$nvpage = max(1, (int) request()->input('page', 1));
					$nvUrl = '/oce/nycha/vendors?limit=25&page=' . $nvpage
						. '&sort=' . urlencode($nvsort) . '&order=' . $nvorder
						. ($nvq !== '' ? '&q=' . urlencode($nvq) : '');
					return view('procurement.nycha_vendors', $chrome + [
						'pagetitle' => "{$dispName} — Vendors | WeGovNYC Databook",
						'snippet' => "NYCHA vendors — contract and payment activity, linked to City vendor profiles where matched.",
						'vendors' => DatabookAPI::reqOCE($nvUrl, 60) ?: ['available' => false, 'data' => [], 'total' => 0, 'page' => 1, 'pages' => 1],
						'filters' => ['q' => $nvq, 'sort' => $nvsort, 'order' => $nvorder],
					]);
				case 'procurement-nycha-vendor':
					// NYCHA-native vendor profile (for vendors with no PASSPort record).
					$vpName = trim((string) request()->input('name', ''));
					if ($vpName === '') {
						return redirect(route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => 'procurement-nycha-vendors']));
					}
					$vp = DatabookAPI::reqOCE('/oce/nycha/vendor?name=' . urlencode($vpName), 60);
					// Crosswalked vendors have a richer City profile (which now shows
					// NYCHA activity) — send them there instead of the NYCHA-native page.
					if ($vp && !empty($vp['vendor_id'])) {
						return redirect(route('procurement.vendor', ['id' => $vp['vendor_id']]));
					}
					return view('procurement.nycha_vendor_profile', $chrome + [
						'pagetitle' => "{$vpName} — NYCHA Vendor | WeGovNYC Databook",
						'snippet' => "NYCHA vendor {$vpName} — contracts and spending (Checkbook NYC).",
						'vp' => $vp ?: ['available' => false, 'contract_list' => [], 'contracts' => null, 'spending' => null],
						'vname' => $vpName,
					]);
				default: // procurement-highlights (and any other procurement-* for NYCHA) → finances overview
					$councilStat = DatabookAPI::req('/get/orgs/stats-reg/' . $id . '/nyccouncildiscretionaryfunding');
					return view('org_procurement_section', $chrome + [
						'isNycha' => true,
						'pagetitle' => "{$dispName} Finances & Procurement | WeGovNYC Databook",
						'snippet' => "NYCHA finances & procurement — budget, revenue, contracts, spending (Checkbook NYC), and Council discretionary funding.",
						'budget'    => DatabookAPI::reqOCE('/oce/nycha/budget/summary', 30)    ?: ['available' => false, 'totals' => []],
						'revenue'   => DatabookAPI::reqOCE('/oce/nycha/revenue/summary', 30)   ?: ['available' => false, 'totals' => []],
						'contracts' => DatabookAPI::reqOCE('/oce/nycha/contracts/summary', 30) ?: ['available' => false, 'totals' => []],
						'spending'  => DatabookAPI::reqOCE('/oce/nycha/spending/summary', 30)  ?: ['available' => false, 'totals' => []],
						'councilCount' => (int) ($councilStat[0]['count'] ?? 0),
					]);
			}
		}

		// Fetch procurement data from OCE API (cached 24h — data refreshes daily)
		$cacheKey = "org_procurement_" . md5($org['name']);
		$data = \Illuminate\Support\Facades\Cache::remember($cacheKey, 86400, function () use ($org) {
			return DatabookAPI::reqOCE("/oce/agency/procurement?name=" . urlencode($org['name']), 60);
		});
		
		if (!$data || !isset($data['agency'])) {
			// If no procurement data, show empty state
			$data = [
				'agency' => ['name' => $org['name']],
				'stats' => [],
				'monthly_activity' => [],
				'yearly_spending' => [],
				'contracts' => [],
				'solicitations' => [],
				'vendors' => [],
			];
		}
		
		// Transactions are loaded client-side (lazy AJAX) in the view to avoid a slow
		// blocking OCE fetch that could exceed the request timeout (504). The Checkbook
		// query for large agencies is expensive; fetching it in the browser keeps the
		// page responsive. See org_procurement_section.blade.php (transactions subsection).
		$transactions = [];
		
		return view('org_procurement_section', [
			'id' => $id,
			'org' => $org,
			'section' => $section,
			'subsection' => $subsection,
			'slist' => $ds->list,
			'menu' => $ds->menu,
			'activeDropDown' => 'Procurement',
			'icons' => $ds->socicons,
			'breadcrumbs' => Breadcrumbs::orgSect($org['id'], self::dispName($org), $section, $ds->list[$section] ?? 'Procurement'),
			
			// Procurement data
			'agency' => $data['agency'],
			'stats' => $data['stats'] ?? [],
			'monthly_activity' => $data['monthly_activity'] ?? [],
			'yearly_spending' => $data['yearly_spending'] ?? [],
			'contracts' => $data['contracts'] ?? [],
			'solicitations' => $data['solicitations'] ?? [],
			'vendors' => $data['vendors'] ?? [],
			'transactions' => $transactions,
			
			####### seo ########
			'pagetitle' => "{$dispName} Procurement | WeGovNYC Databook",
			'snippet' => "Procurement data for {$org['name']} including contracts, solicitations, and vendors.",
			'canonicalUrl' => route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-')]),
		]);
	}




	/**
	 * Show organization notice subsection.
	 *
	 * @param  int  	$id
	 * @param  string  	$subsection
	 * @return \Illuminate\View\View
	 */
	public function orgNoticesSection($id, $subsection)
	{
		return $this->orgSection($id, "notices/{$subsection}");
	}


	/**
	 * Show organization capital projects section.
	 *
	 * @param  int  	$id
	 * @return \Illuminate\View\View
	 */
	public function orgProjectSection($id, $orgslug = '')
	{
		$section = 'projects';
		$org = $this->fetchOrg($id);
		$dispName = self::dispName($org);
		$ds = new OrgsDatasets();
		$details = $ds->get($section);
		return $org && $details
			? view('orgprojectsection', [
				'id' => $id,
				'org' => $org,
				'section' => $section,
				'slist' => $ds->list,
				'menu' => $ds->menu,
				'activeDropDown' => $ds->menuActiveDD($section),
				'icons' => $ds->socicons,
				// ⚠⚠ NOT the generic `/get/orgs/section/{id}/{tbl}` any more. That
				// endpoint hardcodes the quoted `"wegov-org-id"` column and the spine's
				// is `wegov_org_id`, so it CANNOT serve `capital_projects` — which is
				// why this tab was the last surface still on the retired series.
				'url' => DatabookAPI::url("/get/capital/projects/by-org/{$id}"),
				// ⚠⚠ THE MAP'S OWN SOURCE, SCOPED THE SAME WAY AS THE TABLE. When this
				// tab was repointed at the spine (`94e6379`) its map was left reading
				// `GEO_JSON` off the table — a column the spine does not serve — so it
				// drew **0 features** while the table held 2,798 projects. Measured on
				// the rendered page 2026-09-10 from
				// `map.getSource('route')._data.features.length`, with a clean
				// container, a loaded style and an empty console: the same class as
				// this tab's eight blank tiles, found the same way, one organ over.
				'capGeojsonUrl' => DatabookAPI::url('/get/capital/geojson?' . http_build_query(['org' => $id])),
				// ⚠ The SAME two keys orgsection passes. This method renders a
				// DIFFERENT view (orgprojectsection) for the same kind of section, so
				// adding them to one and not the other is exactly how the first
				// attempt shipped a scope note that never appeared on /projects.
				'coverageUrl' => DatabookAPI::url("/get/orgs/section-coverage/{$details['table']}"),
				'contractWorkUrl' => DatabookAPI::url("/get/orgs/contract-work/{$id}"),
				// Capital projects carried on ANOTHER agency's budget that name this org.
				'altProjectsUrl' => DatabookAPI::url("/get/orgs/capital-projects-via/{$id}"),
				// The CURRENT Capital Commitment Plan. The section's own table is the
				// series NYC retired in Oct 2023; this is what is happening now.
				'currentPlanUrl' => DatabookAPI::url("/get/orgs/current-capital-plan/{$id}"),
				'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
				'breadcrumbs' => Breadcrumbs::orgSect($org['id'], self::dispName($org), $section, $ds->list[$section]),
				'details' => $details,
				'map' => true,
				// ⚠⚠ THE EIGHT `pstats-*` HYDRATION URLs ARE GONE, AND THIS TAB'S
				// TILES WERE BLANK BECAUSE OF THEM. They fetched
				// `/get/orgs/pstats-{measure}/{id}/{pubdate}` over
				// `capitalprojectsdollarscomp`, and the only thing that ever called
				// `loadFinStat()` sat inside the `@if ($details['pubDateFilter'])`
				// block — which the spine contract turns OFF, deliberately, because a
				// derived spine has no per-row publication date. So after the tab was
				// repointed at the spine the loop had no caller: **measured on the
				// rendered page 2026-09-10, all eight tiles read `&nbsp;` and ZERO
				// pstats requests were made**, on every org that has spine projects.
				// The table beside them was correct throughout — which is why a row
				// count or a status code could not see this.
				// ⚠ The tiles are SERVER-RENDERED from the spine now, exactly as the
				// district tab's are (`distprojectsection`), so there is nothing left
				// to hydrate and no unit to re-scale.
				'capital' => DatabookAPI::reqOCE("/get/capital/stats/org/{$id}") ?: null,
				// Stats for an org matched by TEXT rather than by org id. Such an org
				// holds NO spine row — so `/get/capital/stats/org/{id}` correctly
				// answers `found: false` for it, and this is the only figure it has.
				'unionStatsUrl' => DatabookAPI::url("/get/orgs/pstats-union/{$id}"),
				####### seo ########
				#'schema' => Schema::org($org),
				'pagetitle' => "{$dispName} | WeGovNYC Databook",
				'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', $org['description']),
				'canonicalUrl' => route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-')]),
			])
			: abort(404);
	}


	/**
	 * Show capital project.
	 *
	 * @param  string  	$prjId
	 * @return \Illuminate\View\View
	 */
	/**
	 * One capital project, from the spine.
	 *
	 * ⚠⚠ TWO LIVE DEFECTS THIS REPLACES, BOTH MEASURED 2026-09-06.
	 *
	 * `/p/111PO111-17` returned **404** — a real project in the current Capital
	 * Commitment Plan. The old action required `fetchOrg()` to succeed, and
	 * **4,568 of 17,024 spine rows carry no `wegov_org_id`** (27%), so a quarter
	 * of the capital programme had no page at all. The org shell is now
	 * conditional: an agency we know gets its profile chrome, and one we do not
	 * still gets a project page.
	 *
	 * `/p/110WLM` returned **200** and showed ONE project — that id is carried by
	 * DCAS (856) and agency 068. A bare FMS id does not identify a project:
	 * 1,160 ids are shared across agencies, covering 2,371 rows. The endpoint
	 * returns the CHOICES and never picks; this renders them.
	 *
	 * ⚠ The canonical id is the agency-concatenated form (`035L103RENO`), which
	 * is what CPDB, Parks and Climate Budgeting all publish and what Databook's
	 * legacy URL already used. A bare id still resolves when it is unique.
	 */
	public function project($prjId, $prjslug = '')
	{
		$section = 'projects';
		$ds = new OrgsDatasets();
		$details = $ds->get($section);

		// ⚠ The agency is a DISAMBIGUATOR, not a filter — it only ever narrows a
		// shared id to one project, and the endpoint refuses to guess without it.
		$agency = trim((string) request()->input('agency', ''));
		$q = $agency === '' ? '' : ('?agency=' . rawurlencode($agency));
		$p = DatabookAPI::reqOCE('/get/capital/project/' . rawurlencode($prjId) . $q, 15);

		// ⚠ `false` means the API could not be reached; `available` false means it
		// answered and has nothing. Collapsing the two turns a deploy restart into
		// "this project does not exist" (the #135 distinction).
		if ($p === false || !is_array($p))
			return response()->view('errors.service-unavailable', [], 503);

		if (empty($p['found'])) {
			if (!empty($p['ambiguous']))
				return view('capitalprojectchoices', [
					'breadcrumbs' => Breadcrumbs::purePrj($prjId, $prjId),
					'prjId' => $prjId,
					'cap' => $p,
					'pagetitle' => "{$prjId} — more than one project | NYC Databook",
				]);
			return abort(404);
		}

		$orgId = $p['header']['wegov_org_id'] ?? null;
		$org = $orgId ? $this->fetchOrg($orgId) : null;
		$name = $p['header']['description'] ?: ($p['id']['maprojid'] ?? $prjId);
		$canonId = ($p['id']['agency_key'] ?? '') . ($p['id']['fms_id'] ?? '');

		return view('capitalproject', [
			// ⚠⚠ EVERY KEY THE VIEW READS MUST BE NAMED HERE (#247). A payload the
			// API serves and the Blade reads still arrives as null unless it is
			// listed, and `?? []` in the view makes that silent.
			'cap' => $p,
			'prjId' => $prjId,
			'canonId' => $canonId,
			'geojsonUrl' => DatabookAPI::url('/get/capital/project/' . rawurlencode($canonId) . '/geometry'),

			// The org shell renders only when we know the agency — see the note
			// above; requiring it 404'd 4,568 projects.
			'id' => $orgId,
			'org' => $org,
			'section' => $section,
			'slist' => $ds->list,
			'menu' => $ds->menu,
			'activeDropDown' => $ds->menuActiveDD($section),
			'icons' => $ds->socicons,
			'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
			'breadcrumbs' => $org
				? Breadcrumbs::orgPrj($orgId, $org['name'], $section, $ds->list[$section], $canonId, $name)
				: Breadcrumbs::purePrj($canonId, $name),
			'map' => true,
			####### seo ########
			'pagetitle' => "{$name} | {$canonId} | NYC Databook Capital Projects",
			'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', "{$canonId} - {$name}"),
			'canonicalUrl' => route('project', ['prjId' => $canonId, 'prjslug' => Str::slug($name, '-')]),
		]);
	}


	/**
	 * Show capital project.
	 *
	 * @param  string  	$prjId
	 * @return \Illuminate\View\View
	 */
	public function orgChartsXHR($id, $section)
	{
		return view("orgCharts.{$section}", [
			'id' => $id,
			'section' => $section,

			'salaryStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-civillist_salaries_by_year"),
			'employeesStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-civillist_entries_by_year"),
			'positionsStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-positionschedule_positions_by_agency"),
		]);
	}


	/**
	 * Show events ical feed.
	 *
	 * @return \Illuminate\View\View
	 */
	public function ical($id)
	{
		$data = DatabookAPI::req("/get/orgs/icalevents/{$id}");
		if (!$data) {
			return response('BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//WeGovNYC//Databook//EN
END:VCALENDAR', 200)
				->header('Content-type', 'text/calendar');
		}
		return response()->view('icalevents', [
			'data' => $data,
			'agencyName' => $data[0]['wegov-org-name'],
			'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('City Record Online (CROL)'))[0] ?? null,
		])
			->header('Content-type', 'text/calendar');
	}


	/**
	 * Return news rss feed.
	 *
	 * @return \Illuminate\View\View
	 */
	public function rss($id)
	{
		$data = DatabookAPI::req("/get/orgs/rssnews/{$id}");
		if (!$data) {
			return response('<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
 <title>WeGovNYC Databook</title>
 <description>No news found</description>
</channel>
</rss>', 200)
				->header('Content-type', 'text/xml; charset=utf-8');
		}
		return response()->view('rss', [
			'data' => $data,
			'agencyName' => $data[0]['wegov-org-name'],
			'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('City Record Online (CROL)'))[0] ?? null,
		])
			->header('Content-type', 'text/xml; charset=utf-8');
	}


	/**
	 * Return sitemap.xml.
	 *
	 * @return \Illuminate\View\View
	 */
	public function sitemap()
	{
		$dd = [];
		#orgs
		$dd[] = [route('root'), 0.6, 'monthly'];
		$dd[] = [route('about'), 0.6, 'monthly'];
		$dd[] = [route('orgs'), 0.6, 'monthly'];
		foreach (DatabookAPI::req('/get/orgs/directory') as $org)
			$dd[] = [route('orgProfile', [$org['id'], Str::slug($org['name'], '-')]), 1, 'weekly'];
		#districts
		$dd[] = [route('districts'), 0.6, 'monthly'];
		foreach (['cc', 'cd', 'nta'] as $type) {
			$fn = public_path("data/{$type}.geojson");
			// ⚠ ONE OWNER (App\Custom\DistrictName). The literal typed here carried
			// no `sd` key at all — harmless only because this loop never asks for one.
			$title = \App\Custom\DistrictName::PREFIX[$type];
			$geojson = json_decode(file_get_contents($fn), true);
			$f = $type == 'nta' ? 'nameAlt' : 'nameCol';
			foreach ($geojson['features'] as $d) {
				$id = $d['properties'][$f];
				$name = $title . $id;
				$dd[] = [route('districtsPreset', ['type' => $type, 'id' => $id, 'dslug' => Str::slug($name, '-'), 'section' => 'projects']), 1, 'weekly'];
			}
		}
		#projects
		$dd[] = [route('projects'), 0.6, 'monthly'];
		$dates = DatabookAPI::req('/get/capitalprojects/dates');
		#print_r($dates);
		foreach (DatabookAPI::req('/get/capitalprojects/all/' . $dates[0]['PUB_DATE']) as $prj)
			if (!strstr($prj['PROJECT_ID'], '&'))
				$dd[] = [route('project', ['prjId' => $prj['PROJECT_ID'], 'prjslug' => Str::slug($prj['PROJECT_DESCR'], '-')]), 1, 'weekly'];
		#titles
		$dd[] = [route('titles'), 0.6, 'monthly'];
		#notices 
		$dd[] = [route('notices'), 0.6, 'monthly'];
		#auctions
		$dd[] = [route('auctions'), 0.6, 'monthly'];

		return response()->view('sitemap', [
			'entries' => $dd,
		])
			->header('Content-type', 'text/xml; charset=utf-8');
	}
}
