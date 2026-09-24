<?php
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Http;
use Illuminate\Http\Request;
use App\Http\Controllers\Organizations;
use App\Http\Controllers\Districts;
use App\Http\Controllers\Projects;
use App\Http\Controllers\Titles;
use App\Http\Controllers\Notices;
use App\Http\Controllers\Auctions;
use App\Http\Controllers\People;
use App\Http\Controllers\ProcurementController;
use App\Http\Controllers\BudgetRevenueController;
use App\Http\Controllers\NychaController;
use App\Custom\DatabookAPI;
use App\Custom\DistDatasets;

// Local API proxy for bypassing CORS in development
Route::get('/api/{path}', function ($path) {
    if (env('APP_ENV') === 'local') {
        $url = env('FAPI_ENTRY') . "/{$path}?" . http_build_query(request()->query());
        $apiKey = env('FAPI_KEY');
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            "Authorization: Bearer {$apiKey}"
        ]);
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

        if ($httpCode >= 200 && $httpCode < 300) {
            return response($response)->header('Content-Type', 'application/json');
        }
    }
    return abort(404);
})->where('path', '.*')->name('apiProxy');

Route::get('/', [Organizations::class, 'root'])->name('root');
Route::get('/new-home', [Organizations::class, 'root'])->name('newHome');

Route::get('/about', function () { return view('about.project'); })->name('about');
Route::get('/about/data', [\App\Http\Controllers\Admin::class, 'dataHealth'])->name('about.data');
Route::get('/about/tables', [\App\Http\Controllers\Admin::class, 'dataTables'])->name('about.tables');
Route::get('/about/log', [\App\Http\Controllers\Admin::class, 'ingestionLog'])->name('about.log');

// ── the org register's editing UI (Phase 5) ─────────────────────────────────
// ⚠ GATED BY NGINX BASIC AUTH on /admin/ at the ORIGIN, not by Laravel: this app
// has no user system to hang a role on, and a Cloudflare-layer policy would be
// bypassable (task dda13bf3 — the origin answers direct connections). See
// scripts/org-admin-auth-setup.sh. Removing that gate turns these into an
// unauthenticated write surface onto the register.
Route::get('/admin/orgs', [\App\Http\Controllers\OrgAdmin::class, 'index'])->name('admin.orgs');
// ⚠ {id} is constrained to digits, or this route would swallow every literal
// path under /admin/orgs/ — `/admin/orgs/vocabulary` would arrive as id
// "vocabulary", cast to 0, and 404 from the API for a confusing reason.
Route::get('/admin/orgs/{id}', [\App\Http\Controllers\OrgAdmin::class, 'edit'])
    ->where('id', '[0-9]+')->name('admin.orgs.edit');
Route::post('/admin/orgs', [\App\Http\Controllers\OrgAdmin::class, 'create'])->name('admin.orgs.create');
Route::patch('/admin/orgs/{id}', [\App\Http\Controllers\OrgAdmin::class, 'save'])
    ->where('id', '[0-9]+')->name('admin.orgs.save');
Route::post('/admin/orgs/{id}/retire', [\App\Http\Controllers\OrgAdmin::class, 'retire'])
    ->where('id', '[0-9]+')->name('admin.orgs.retire');
Route::post('/admin/orgs/{id}/unretire', [\App\Http\Controllers\OrgAdmin::class, 'unretire'])
    ->where('id', '[0-9]+')->name('admin.orgs.unretire');

// The curation review app — Phase 1 of docs/REVIEW-APP-SCOPE.md.
//
// ⚠ Gated by nginx basic auth on /review/, exactly as /admin/ is: these pages
// show UNREVIEWED model output naming City programs and assigning them money,
// and #146's rule is that such rows never render publicly. The origin gate is
// what makes serving them safe; api/tests/test_review_ui.py pins the block.
//
// ⚠ The item route is declared with a constrained {item} rather than a bare
// wildcard so a future /review/{queue}/export cannot arrive as an item id —
// the same trap /admin/orgs/vocabulary already documents above.
Route::get('/review', [\App\Http\Controllers\Review::class, 'index'])->name('review');
// ⚠ Declared BEFORE the {queue} route or /review/glossary arrives as a queue
// name — the same trap /admin/orgs/vocabulary already documents.
Route::get('/review/glossary', [\App\Http\Controllers\Review::class, 'glossary'])->name('review.glossary');
Route::get('/review/{queue}', [\App\Http\Controllers\Review::class, 'queue'])
	->where('queue', '[a-z0-9\-]+')->name('review.queue');
Route::get('/review/{queue}/{item}', [\App\Http\Controllers\Review::class, 'item'])
	->where(['queue' => '[a-z0-9\-]+', 'item' => '[^/]+'])->name('review.item');
Route::post('/review/{queue}/{item}', [\App\Http\Controllers\Review::class, 'decide'])
	->where(['queue' => '[a-z0-9\-]+', 'item' => '[^/]+'])->name('review.decide');
Route::post('/review/{queue}/{item}/links', [\App\Http\Controllers\Review::class, 'addLink'])
	->where(['queue' => '[a-z0-9\-]+', 'item' => '[^/]+'])->name('review.link');
Route::post('/review/{queue}/{item}/links/{link}/delete', [\App\Http\Controllers\Review::class, 'deleteLink'])
	->where(['queue' => '[a-z0-9\-]+', 'item' => '[^/]+', 'link' => '[0-9]+'])->name('review.unlink');
Route::post('/review/{queue}/{item}/links/{link}/source', [\App\Http\Controllers\Review::class, 'flagLink'])
	->where(['queue' => '[a-z0-9\-]+', 'item' => '[^/]+', 'link' => '[0-9]+'])->name('review.linksource');

Route::get('/styleguide', function () {
    return view('styleguide', ['pagetitle' => 'Styleguide - Databook.nyc']);
});
Route::get('/styleguide/components', function () {
    return view('components-demo', ['pagetitle' => 'Blade components - Databook.nyc']);
});
Route::get('/mcp', function () {
    return view('mcp', ['pagetitle' => 'MCP Server - Databook.nyc']);
})->name('mcp');

Route::get('/blog', [\App\Http\Controllers\Articles::class, 'index'])->name('blog');
Route::get('/articles/{slug}', [\App\Http\Controllers\Articles::class, 'show'])->name('article');
Route::get('/organizations', function (\Illuminate\Http\Request $r) {
    $qs = $r->getQueryString();
    return redirect('/organizations/agencies' . ($qs ? '?'.$qs : ''));
})->name('orgs');
Route::get('/organizations/agencies', [Organizations::class, 'orgsAgencies'])->name('orgsAgencies');
Route::get('/organizations/directory', function () { return redirect(route('orgs')); });
Route::get('/organizations/chart', [Organizations::class, 'orgsChart'])->name('orgsChart');
Route::get('/organizations/chart/{id}', [Organizations::class, 'orgsChart'])->name('orgsChartFocus');
Route::get('/organizations/all', [Organizations::class, 'orgsAll'])->name('orgsAll');
Route::get('/organizations/all/{req}', [Organizations::class, 'orgsAll'])->name('orgsAllReq');

Route::get('/organization/{id}', [Organizations::class, 'orgAbout'])->name('orgProfileDepr');
Route::get('/o/{id}-{orgslug}', [Organizations::class, 'orgAbout'])->name('orgProfile');
Route::get('/o/{id}-{orgslug}/projects', [Organizations::class, 'orgProjectSection'])->name('orgProjectSection');
Route::get('/organizations/{id}/events.ics', [Organizations::class, 'ical'])->name('orgIcalEvents');
Route::get('/organizations/{id}/news.rss', [Organizations::class, 'rss'])->name('orgRSSNews');
Route::get('/o/{id}-{orgslug}/notices/{subsection}', function ($id, $orgslug, $subsection) {
    return redirect(route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => $subsection]));
})->name('orgNoticeSection');
Route::get('/o/{id}-{orgslug}/{section}', [Organizations::class, 'orgSection'])->name('orgSection');
Route::get('/o/{id}-{orgslug}/p/{prjId}-{prjslug}', function ($id, $prjId, $prjslug) {
    return redirect(route('project', ['prjId' => $prjId, 'prjslug' => $prjslug]));
})->name('orgProject');
Route::get('/p/{prjId}_{prjslug}', [Organizations::class, 'project'])->name('project');
// Support ID-only URLs without slug (e.g., /p/PW193ELV)
Route::get('/p/{prjId}', [Organizations::class, 'project'])->name('project-id-only')
    ->where('prjId', '[A-Za-z0-9\-]+');
// Support dash-separated URLs (redirect to underscore version)
Route::get('/p/{prjId}-{prjslug}', function ($prjId, $prjslug) {
    return redirect(route('project', ['prjId' => $prjId, 'prjslug' => $prjslug]), 301);
});
// Legacy capital-archive project URLs → redirect to /p/
Route::get('/capital-archive/p/{prjId}_{prjslug}', function ($prjId, $prjslug) {
    return redirect(route('project', ['prjId' => $prjId, 'prjslug' => $prjslug]), 301);
});

#Route::get('/sitemap.xml', [Organizations::class, 'sitemap'])->name('sitemap');

Route::get('/orgChartsXHR/{id}/{section}', [Organizations::class, 'orgChartsXHR'])->name('orgChartsXHR');



Route::get('/districts', [Districts::class, 'main'])->name('districts');
Route::get('/districts/{type}', [Districts::class, 'main'])->where('type', '^(cd|cc|nta|sd)$')->name('districtsPresetType');
// Landing section comes from DistDatasets, never a literal here: 'projects'
// does not exist for sd, so hardcoding it 404'd every school-district URL that
// named no section. See DistDatasets::defaultSection().
// ⚠⚠ THE ID/SLUG SEPARATOR IS `_`, NOT `-`, AND THAT IS NOT COSMETIC.
// `{id}` compiles to a LAZY match, so on `/d/nta-Tribeca-Civic Center-district`
// it stopped at the first hyphen and the controller received `Tribeca`. **103 of
// the 255 NTA names carry a hyphen** — Tribeca-Civic Center,
// Downtown Brooklyn-DUMBO-Boerum Hill — so 40% of neighbourhood districts
// resolved to a name that does not exist and rendered an empty page.
// ⚠ This is the same fix `/p/{prjId}_{prjslug}` already uses, for the same
// reason: project ids contain hyphens too (`HED-545`). An underscore cannot
// appear in an NTA name or a slug, so the split is unambiguous by construction
// rather than by luck about the data.
// ⚠ Every link is generated through `route('districtsPreset', …)`, so they all
// move together; the legacy hyphen routes below keep old links working.
Route::get('/d/{type}-{id}_{dslug}', function ($type, $id, $dslug) {
    return redirect(route('districtsPreset', ['type' => $type, 'id' => $id, 'dslug' => $dslug, 'section' => (new DistDatasets())->defaultSection($type)]));
})->where('type', '^(cd|cc|nta|sd)$')->name('district');
Route::get('/d/{type}-{id}_{dslug}/{section}', [Districts::class, 'main'])->where('type', '^(cd|cc|nta|sd)$')->name('districtsPreset');

// ⚠ LEGACY hyphen shape, kept so existing links and bookmarks still resolve.
// Constrained to NUMERIC ids: cd/cc/sd are numbers and were never ambiguous,
// while an nta name is exactly the case the lazy match got wrong. Leaving nta on
// this pattern would keep silently truncating it.
Route::get('/d/{type}-{id}-{dslug}', function ($type, $id, $dslug) {
    return redirect(route('district', ['type' => $type, 'id' => $id, 'dslug' => $dslug]));
})->where(['type' => '^(cd|cc|nta|sd)$', 'id' => '[0-9]+'])->name('districtLegacy');
Route::get('/d/{type}-{id}-{dslug}/{section}', [Districts::class, 'main'])
    ->where(['type' => '^(cd|cc|nta|sd)$', 'id' => '[0-9]+'])->name('districtsPresetLegacy');
Route::get('/districtXHR/{type}/{id}/projects', [Districts::class, 'projectSectionXHR'])->name('distProjectSection');
Route::get('/districtXHR/{type}/{id}/{section}', [Districts::class, 'sectionXHR'])->name('distSection');


Route::get('/schools', [Districts::class, 'schools'])->name('schools');
Route::get('/s/{code}-{slug}', function ($code, $slug) {
    return redirect(route('schoolSection', ['code' => $code, 'slug' => $slug, 'section' => 'enrollment']));
})->name('school');
Route::get('/s/{code}-{slug}/{section}', [Districts::class, 'schoolSection'])->name('schoolSection');
Route::get('/schoolsXHR/geojson', [Districts::class, 'schoolsGeoJson'])->name('schoolsGeoJson');



// Legacy capital-archive URLs → redirect to /projects/ equivalents
Route::get('/capital-archive', function () { return redirect(route('capital'), 301); });
Route::get('/capital-archive/projects', function () { return redirect(route('projects'), 301); });
Route::get('/capital-archive/project-types/{tslug?}', function ($tslug = null) { return $tslug ? redirect(route('prjType', ['tslug' => $tslug]), 301) : redirect(route('prjTypes'), 301); });
Route::get('/capital-archive/categories/{cslug?}', function ($cslug = null) { return $cslug ? redirect(route('prjStratCategory', ['cslug' => $cslug]), 301) : redirect(route('prjCategories'), 301); });
Route::get('/capital-archive/budget-lines/{blcode?}', function ($blcode = null) { return $blcode ? redirect(route('budgetLine', ['blcode' => $blcode]), 301) : redirect(route('budgetLines'), 301); });
Route::get('/capital-archive/commitments', function () { return redirect(route('prjCommitments'), 301); });

Route::get('/capital/minor-projects', [Projects::class, 'mProjects'])->name('mProjects');
Route::get('/capital/minor-projects/{maprojid}', [Projects::class, 'mProject'])->name('mProject');


Route::get('/projects', [Projects::class, 'projects'])->name('projects');
// ⚠ Renamed /projects/capital -> /projects/about (owner request). The ROUTE
// NAME stays `capital` deliberately: eleven call sites and several guards
// resolve it by name, and churning the name would touch all of them to no
// visible end. The old URL 302s so existing links and bookmarks still land —
// the same convention the Digital Services reorg used.
Route::get('/projects/about', [Projects::class, 'main'])->name('capital');
Route::get('/projects/capital', function () {
    return redirect()->route('capital', request()->query(), 302);
});
Route::get('/projects/types', [Projects::class, 'prjTypes_a'])->name('prjTypes');
Route::get('/projects/types/{tslug}', [Projects::class, 'prjType_a'])->name('prjType');
Route::get('/projects/categories', [Projects::class, 'categories_a'])->name('prjCategories');
Route::get('/projects/categories/{cslug?}', [Projects::class, 'category_a'])->name('prjStratCategory');
Route::get('/projects/budget-lines', [Projects::class, 'budgetLines_a'])->name('budgetLines');
// ⚠⚠ DECLARED BEFORE `{blcode}`, and the order is load-bearing — the same trap
// the digital-services section already pins: a specific path declared AFTER a
// single-segment wildcard is swallowed by it. `/projects/budget-lines/families`
// would arrive as `blcode = "families"`.
Route::get('/projects/budget-lines/families/{fslug}', [Projects::class, 'budgetLineFamily_a'])->name('budgetLineFamily');
Route::get('/projects/budget-lines/{blcode}', [Projects::class, 'budgetLine_a'])->name('budgetLine');
Route::get('/projects/commitments', [Projects::class, 'commitments_a'])->name('prjCommitments');

// Backward compatibility redirects
Route::get('/capital', function () { return redirect(route('capital')); });
Route::get('/capital/projects', function () { return redirect(route('projects')); });
Route::get('/capital/project-types/{tslug?}', function ($tslug = null) { return $tslug ? redirect(route('prjType', ['tslug' => $tslug])) : redirect(route('prjTypes')); });
Route::get('/capital/categories/{cslug?}', function ($cslug = null) { return $cslug ? redirect(route('prjStratCategory', ['cslug' => $cslug])) : redirect(route('prjCategories')); });
Route::get('/capital/budget-lines/{blcode?}', function ($blcode = null) { return $blcode ? redirect(route('budgetLine', ['blcode' => $blcode])) : redirect(route('budgetLines')); });
Route::get('/capital/commitments', function () { return redirect(route('prjCommitments')); });



Route::get('/jobs-exams', function () {
    return view('jobs_exams', [
        'pagetitle' => 'Civil Service Exams - Databook.nyc',
        'breadcrumbs' => [[route('titles'), 'Titles'], [null, 'Exams']],
    ]);
})->name('jobsExams');

Route::get('/jobs', function () {
    return view('jobs', [
        'pagetitle' => 'NYC Jobs - Databook.nyc',
        'breadcrumbs' => [[null, 'NYC Jobs']],
        'jobsUrl' => \App\Custom\DatabookAPI::url('/get/jobs/all'),
    ]);
})->name('jobs');


Route::get('/jobs-dashboard', function () {
    $sharedPath = '/var/shared/dashboard_data.json';
    $localPath = base_path('../dashboard_data.json');
    $jsonPath = file_exists($sharedPath) ? $sharedPath : $localPath;
    $data = file_exists($jsonPath) ? json_decode(file_get_contents($jsonPath), true) : null;
    return view('titles_overview', [
        'pagetitle' => 'NYC Jobs Dashboard - Databook.nyc',
        'breadcrumbs' => [[null, 'Jobs Dashboard']],
        'data' => $data,
        'jobsUrl' => \App\Custom\DatabookAPI::url('/get/jobs/all'),
    ]);
})->name('jobsDashboard');

Route::get('/titles-overview', function () {
    return redirect('/jobs-dashboard', 301);
})->name('titlesOverview');

Route::get('/titles', [Titles::class, 'main'])->name('titles');
Route::get('/title-stats', [Titles::class, 'stats'])->name('titleStats');

// Legacy Routes (Long URL)
Route::get('/t/{id}-{tslug}', function ($id, $tslug) {
    return redirect(route('titleSectionLong', ['id' => $id, 'tslug' => $tslug, 'section' => 'positions']));
})->name('titleLong');
Route::get('/t/{id}-{tslug}/{section}', [Titles::class, 'section'])->name('titleSectionLong');

// New Routes (Short URL)
Route::get('/t/{id}', function ($id) {
    return redirect(route('titleSection', ['id' => $id, 'section' => 'positions']));
})->name('title');
Route::get('/t/{id}/{section}', [Titles::class, 'sectionShort'])->name('titleSection');


Route::get('/notices', [Notices::class, 'main'])->name('notices');
Route::get('/notices/events.ics', [Notices::class, 'ical'])->name('noticesIcalEvents');
Route::get('/notices/news.rss', [Notices::class, 'rss'])->name('noticesRSSNews');
Route::get('/notices/{section}', [Notices::class, 'section'])->name('noticesSection');


Route::get('/auctions', [Auctions::class, 'main'])->name('auctions');

Route::get('/council', function () {
    return view('council', ['pagetitle' => 'City Council Hearings - Databook.nyc']);
})->name('council');


// Global search — server-rendered results page. Federates entity types via the
// API's /get/search (one round-trip); see api/routers/search.py.
Route::get('/search', function (\Illuminate\Http\Request $request) {
	$q = trim((string) $request->query('q', ''));
	$data = ['query' => $q, 'total' => 0, 'groups' => []];
	if (mb_strlen($q) >= 2) {
		// reqOCE returns the full decoded JSON; req() would strip to ['rows'] only.
		$res = \App\Custom\DatabookAPI::reqOCE('/get/search?q=' . rawurlencode($q), 8);
		if (is_array($res) && isset($res['groups'])) {
			$data = $res;
		}
	}
	return view('search', [
		'q' => $q,
		'data' => $data,
		'pagetitle' => ($q !== '' ? "Search: {$q}" : 'Search') . ' — NYC Databook',
		'noindex' => true,
	]);
})->name('search');

// Navbar typeahead — JSON proxy to the API's lightweight suggest endpoint.
// Proxied (not browser→API direct) so the bearer key stays server-side.
Route::get('/search/suggest', function (\Illuminate\Http\Request $request) {
	$q = trim((string) $request->query('q', ''));
	$out = ['query' => $q, 'suggestions' => []];
	if (mb_strlen($q) >= 2) {
		$res = \App\Custom\DatabookAPI::reqOCE('/get/search/suggest?q=' . rawurlencode($q), 3);
		if (is_array($res) && isset($res['suggestions'])) {
			$out = $res;
		}
	}
	return response()->json($out)
		->header('Cache-Control', 'private, max-age=30');
})->name('search.suggest');

Route::get('/people', [People::class, 'main'])->name('people');
Route::get('/people/search/{req}', function ($req) {
	return redirect(route('peopleSearchTbl', ['req' => $req, 'tbl' => 'all']));
})->name('peopleSearch');
Route::get('/people/search/{req}/{tbl}', [People::class, 'search'])->name('peopleSearchTbl');
Route::get('/people/{id}-{slug}', [People::class, 'person'])->name('peoplePerson');


# Procurement
Route::get('/procurement', [ProcurementController::class, 'index'])->name('procurement.index');
Route::get('/procurement/vendors', [ProcurementController::class, 'vendors'])->name('procurement.vendors');
Route::get('/procurement/vendor/{id}', [ProcurementController::class, 'vendorProfile'])->name('procurement.vendor');
Route::get('/procurement/agencies', [ProcurementController::class, 'agencies'])->name('procurement.agencies');
Route::get('/procurement/contracts', [ProcurementController::class, 'contracts'])->name('procurement.contracts');
Route::get('/procurement/contract/{id}', [ProcurementController::class, 'contractProfile'])->name('procurement.contract');
Route::get('/procurement/solicitations', [ProcurementController::class, 'solicitations'])->name('procurement.solicitations');
Route::get('/procurement/solicitation/{epin}', [ProcurementController::class, 'solicitationProfile'])->name('procurement.solicitation');
Route::get('/procurement/agency/{name}', [ProcurementController::class, 'orgProcurement'])->where('name', '.*')->name('agency.procurement');
Route::get('/research/digital-reform', [ProcurementController::class, 'digitalReform'])->name('research.digital-reform');
// REORGANIZED 2026-08-21 (docs/DIGITAL-REFORM-REORG-PLAN.md): the section is a
// five-page submenu -- Overview / Contracts / Products / Master Agreements /
// Vendors. /expiring and /licenses* became /contracts and /products*; the old
// paths 302 below, WITH their query strings, because family pages are linked
// from every vendor profile and the queue's filter URLs are shared in email.
Route::get('/research/digital-reform/search', [ProcurementController::class, 'digitalReformSearch'])->name('research.digital-reform.search');
Route::get('/research/digital-reform/contracts', [ProcurementController::class, 'digitalReformExpiring'])->name('research.digital-reform.contracts');
// The Renewal Review Queue's own page (2026-09-23), split out of Contracts: a
// working tool for reviewers, with its CSV export beside it. A Contracts URL
// carrying a queue parameter 302s here (see digitalReformExpiring).
Route::get('/research/digital-reform/contracts/review', [ProcurementController::class, 'digitalReformReview'])->name('research.digital-reform.review');
Route::get('/research/digital-reform/contracts/review/export', [ProcurementController::class, 'digitalReformReviewExport'])->name('research.digital-reform.review.export');
Route::get('/research/digital-reform/agreements', [ProcurementController::class, 'digitalReformMasterAgreements'])->name('research.digital-reform.agreements');
Route::get('/research/digital-reform/vendors', [ProcurementController::class, 'digitalReformVendors'])->name('research.digital-reform.vendors');
// The data lens (docs/DIGITAL-SERVICES-SECTION-PLAN.md §5c Phase A). Reads
// /oce/licenses/data, which derives entirely from layers the Products page
// already publishes -- so this page adds a QUESTION, never a second set of
// figures. ⚠ Declared before /products/{slug}, which is constrained to
// [A-Za-z0-9-]+ and would otherwise be the only candidate for a future
// /products/data; keeping it a sibling of /products rather than a child avoids
// the collision entirely.
Route::get('/research/digital-reform/data', [ProcurementController::class, 'digitalReformData'])->name('research.digital-reform.data');
Route::get('/research/digital-reform/call-centers', [ProcurementController::class, 'digitalReformCallCenters'])->name('research.digital-reform.call-centers');
// Renamed 2026-09-16 (owner): "Master Agreements" -> "Agreements" in the
// submenu and on the page, and the URL moved with the label rather than being
// left to disagree with it. Same treatment as /expiring -> /contracts and
// /licenses* -> /products* above: a 302 carrying the query string, because the
// old path is linked from the storyboard, the Products page and the queue.
Route::get('/research/digital-reform/master-agreements', function () {
    return redirect()->route('research.digital-reform.agreements', request()->query());
});
// /expiring WAS the queue, so it goes straight to the queue's own page.
Route::get('/research/digital-reform/expiring', function () {
    return redirect()->route('research.digital-reform.review', request()->query());
});
// PUBLISHED 2026-08-11. Was UNLISTED (absent from the nav + noindex) from
// 2026-08-10 while every licence judgement on it was unreviewed AI output. The
// top 20 families -- 88.0% of the $1,370.4M -- have now been reviewed and
// accepted, so it is in the Digital Services Analysis submenu and indexable.
// ⚠ The middle state it left is the one to avoid repeating: noindex and out of
// the nav, but linked from PUBLIC vendor profiles, so reachable by anyone
// browsing vendors while reading as private to us. URL obscurity was never
// access control here -- this site has a documented distributed crawler. If any
// future page must actually be private, use nginx basic auth (the /admin/
// pattern), not absence from the nav.
// ⚠ The ~410-family tail below the top 20 is still auto-classified. What makes
// publishing defensible is that the page says so; guard tests pin those caveats.
Route::get('/research/digital-reform/products', [ProcurementController::class, 'digitalReformLicenses'])->name('research.digital-reform.products');
Route::get('/research/digital-reform/licenses', function () {
    return redirect()->route('research.digital-reform.products', request()->query());
});
// Per-family profile at a stable URL. The slug is assigned at build time in
// license_family, so it survives rebuilds; constrained here so it cannot
// swallow a future sibling route.
// ⚠ Declared BEFORE the {slug} family route, or "function/network-security" is
// swallowed by it. Laravel matches in declaration order.
// ⚠ Declared BEFORE the {slug} family route too, or "open-source" arrives as a
// family slug and 404s.
Route::get('/research/digital-reform/products/open-source', [ProcurementController::class, 'digitalReformOpenSource'])->name('research.digital-reform.open-source');
Route::get('/research/digital-reform/products/function/{cap}', [ProcurementController::class, 'digitalReformLicenseCapability'])
    ->where('cap', '[a-z0-9-]+')->name('research.digital-reform.product-capability');
Route::get('/research/digital-reform/products/{slug}', [ProcurementController::class, 'digitalReformLicenseFamily'])
    ->where('slug', '[A-Za-z0-9-]+')->name('research.digital-reform.product-family');
// Old /licenses/* deep links 302 to their /products/* twins, slug intact.
// ⚠ function/{cap} declared before {slug} here too, or the redirect for
// "licenses/function/x" is swallowed by the slug redirect.
Route::get('/research/digital-reform/licenses/function/{cap}', function ($cap) {
    return redirect()->route('research.digital-reform.product-capability',
        array_merge(['cap' => $cap], request()->query()));
})->where('cap', '[a-z0-9-]+');
Route::get('/research/digital-reform/licenses/{slug}', function ($slug) {
    return redirect()->route('research.digital-reform.product-family',
        array_merge(['slug' => $slug], request()->query()));
})->where('slug', '[A-Za-z0-9-]+');
Route::get('/procurement/transactions', [ProcurementController::class, 'transactions'])->name('procurement.transactions');
Route::get('/procurement/transactions/search', [ProcurementController::class, 'transactionsSearch'])->name('procurement.transactions.search');
Route::get('/procurement/budget', [BudgetRevenueController::class, 'budget'])->name('procurement.budget');
Route::get('/procurement/revenue', [BudgetRevenueController::class, 'revenue'])->name('procurement.revenue');
Route::get('/procurement/payroll', [BudgetRevenueController::class, 'payroll'])->name('procurement.payroll');
Route::get('/procurement/nycha', [NychaController::class, 'index'])->name('procurement.nycha');
Route::get('/procurement/nycha/budget', [NychaController::class, 'budget'])->name('procurement.nycha.budget');
Route::get('/procurement/nycha/revenue', [NychaController::class, 'revenue'])->name('procurement.nycha.revenue');
Route::get('/procurement/nycha/contracts', [NychaController::class, 'contracts'])->name('procurement.nycha.contracts');
Route::get('/procurement/nycha/spending', [NychaController::class, 'spending'])->name('procurement.nycha.spending');
Route::get('/procurement/data-sources', [ProcurementController::class, 'dataSources'])->name('procurement.datasources');

# Legacy OCE blog redirects
Route::get('/blog/the-missing-pieces-bridging-nyc-procurement-data-with-ocds', fn() =>
    redirect('/articles/the-missing-pieces-bridging-nyc-procurement-data-with-ocds', 301));
Route::get('/blog/all-in-a-days-work-building-the-open-contracting-explorer', fn() =>
    redirect('/articles/all-in-a-days-work-building-the-open-contracting-explorer', 301));

