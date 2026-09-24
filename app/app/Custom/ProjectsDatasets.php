<?php
Namespace App\Custom;

class ProjectsDatasets
{
	public $dd = [
		// ⚠⚠ THE SPINE-BACKED CONTRACT, BESIDE `main` RATHER THAN REPLACING IT.
		// `main` is written against `capitalprojectsdollarscomp`, the series NYC
		// RETIRED on 2023-10-26 — 8,740 distinct project ids against the spine's
		// 17,024 — and the Ten-Year category page listed projects from it.
		// Measured on one real category: `UTILITY RELOCATION FOR SE AND WM
		// PROJECTS` returned **2 projects** from the retired series and **268**
		// from the spine.
		//
		// ⚠⚠ THE MULTIPLIER IS 1, NOT 1000, AND THAT IS THE TRAP IN THIS SWAP.
		// `main`'s money fields call `toFin(r["BUDG_CURR"], 1000)` because the
		// retired series publishes THOUSANDS. The spine publishes **USD**. Reusing
		// `main`'s field list against spine rows would render every figure a
		// thousand times too large, and it would look entirely plausible — a
		// $123.5M project reading $123.5B. Hence a separate entry, not a repoint.
		//
		// ⚠⚠ `main` AND `main-a` ARE GONE (2026-09-10), AND THIS IS THE WHOLE
		// ARRAY NOW. Both were written against `capitalprojectsdollarscomp` —
		// the series NYC retired 2023-10-26 — and each carried **eleven
		// `, 1000` money multipliers**, the thing that renders a spine figure a
		// thousand times too large. Neither had a consumer left:
		//   `main-a`  served only the unrouted `projectsA` view, deleted with it
		//   `main`    served only `Projects::projects()`, which assigned it to a
		//             `$details` its rebuilt view references ZERO times, and used
		//             its `fullname` for a `dataset` lookup that returns
		//             `{"rows":[]}` and that the view also never reads
		// So three view-data keys were being built and none read — measured, not
		// assumed, before removal.
		// ⚠ THE POINT IS NOT TIDINESS. A dead contract carrying `, 1000` and the
		// retired table name is a loaded template: the next page written from it
		// republishes both defects, and this section has already paid for that
		// once on the org tab. Dead code that cannot be reached is harmless;
		// dead code carrying a retired defect is not.
		// ⚠ The comment that stood here said `main` had to stay because
		// `budgetLineA` used it — true until that page moved to `spine`, then
		// corrected to name `projects()`, and now moot.
		'spine' => [
			'name' => 'Capital Projects',
			'fullname' => 'Capital Project Detail Data - Dollars',
			'description' => 'The derived capital projects spine: every project NYC publishes in the Capital Commitment Plan, the Capital Projects Dashboard, or the retired 2023 detail series, resolved to one row per (agency, FMS id).',
			'table' => 'capital_projects',
			'hdrs' => ['Project ID', 'Agency', 'Name', 'Asset category', 'Borough', 'Phase', 'Planned commitments', 'Spent', 'In current plan'],
			'visible' => [true, true, true, true, true, true, true, true, true],
			'hide_on_map_open' => '3, 4, 7, 8',
			'flds' => [
					// ⚠ THE CANONICAL, AGENCY-CONCATENATED ID. 1,160 bare FMS ids are
					// carried by more than one agency across 2,371 rows, so a link built
					// from `fms_id` alone can land on a different agency's project — the
					// defect `/p/110WLM` shipped.
					'function (r) { return `<a href="/p/${r.id}_${slug(r.description)}">${r.id}</a>` }',
					// ⚠ 4,568 spine rows carry no `wegov_org_id`, so the agency is NOT
					// always a link. Rendering one anyway produced `/o/-` .
					'function (r) { return r["wegov_org_id"] ? `<a href="/o/${r["wegov_org_id"]}-${slug(r["agency_name"])}/projects">${r["agency_name"]}</a>` : (r["agency_name"] || r["agency_acro"] || "") }',
					// ⚠⚠ EVERY CELL RETURNS A STRING, NEVER null. Measured on the spine:
					// **4,095 rows carry no description or agency name, 5,152 no borough,
					// 5,193 no asset category** — all legitimate ("NYC publishes none"),
					// and a bare `'"description"'` hands DataTables a null it then tries
					// to sort and search, which threw `n.slice is not a function` and
					// `Cannot read properties of undefined (reading 'replace')` on every
					// category page. ⭐ The rows still RENDERED, so a status-code check
					// and a row count both passed while the table's sort was broken.
					// ⚠ Empty string, not a dash: `—` in a sortable/searchable column
					// sorts and matches as content. The dash belongs in a profile table,
					// not here.
					'function (r) { return r["description"] || "" }',
					'function (r) { return r["type_category"] || "" }',
					'function (r) { return r["borough"] || "" }',
					// ⚠ A blank phase means NYC publishes no schedule for this project,
					// which is not the same as "no phase".
					'function (r) { return r["current_phase"] || "Not published" }',
					// ⚠ `data-content` is the SORT KEY (`$fmtM`-style columns are not
					// monotonic in their visible text — `$100K` sorts above `$79.8M`).
					// `toFin`/`toFinShortK` already return '' for null, so an unpublished
					// figure sorts as empty rather than as zero — which is the same rule
					// the profile follows: a measure NYC does not publish is not $0.
					'function (r) { return `<span data-content="${toFin(r["planned_total_usd"], 1)}">${toFinShortK(r["planned_total_usd"], 1)}</span>` }',
					'function (r) { return `<span data-content="${toFin(r["spent_total_usd"], 1)}">${toFinShortK(r["spent_total_usd"], 1)}</span>` }',
					'function (r) { return r["in_current_plan"] ? "Yes" : "No" }'
				],
			// ⚠ No `details` key, so `get()` computes `detFlag = 0` and the table
			// renders no expander column. Declaring `detFlag` here would be
			// ignored — `get()` overwrites it from `details`.
			'filters' => [1 => null, 3 => null, 4 => null, 5 => null],
			// ⚠ Column 6 is `Planned commitments`, so the largest projects lead.
			// ⚠⚠ AND `order` IS NOT OPTIONAL: `categoryA` reads `$details['order']`
			// inside an `@if`, and an undefined index is an ErrorException in
			// Laravel — the `@if` does not guard it. A dataset contract missing
			// this key 500s the page it is used on.
			'order' => [[6, 'desc']],
		],

	];
	
	public function get($section)
	{
		$dd = $this->dd[strtolower($section)] ?? null;
		if (!$dd)
			return $dd;
		$dd['detFlag'] = $inc = $dd['details'] ?? null ? 1 : 0;
		$flts = [];
		foreach ((array)$dd['filters'] as $i=>$v)
			$flts[$i + $inc] = $v;
		$dd['filters'] = $flts;
		$fltDel = [];
		foreach ((array)($dd['fltDelim'] ?? []) as $i=>$v)
			$fltDel[$i + $inc] = $v;
		$dd['fltDelim'] = $fltDel;
		
		$dd['fltsCols'] = implode(',', array_keys($dd['filters']));
		return $dd;
	}

	
	public $stats_datasets = [
		'capitalprojectsdollarscomp' => ['projects', 'Projects'],			# table => route
		'capitalprojectsmilestones' => ['projects', 'Projects'],
		'capitalprojectslist' => ['projects', 'Projects'],
		'capitalstrategy' => ['prjCategories', 'Categories'],	# 214
		'capitalbudget' => ['budgetLines', 'Capital Budget'],	# 213
		'capitalcommitmentplan' => ['prjCommitments', 'Commitments'],	# 212
		'capitalprojectscommitments' => ['budgetLines', 'Capital Budget'],
		
		'capprojectsbudgetsandschedule' => ['projects', 'Projects'],		# 244
		'capprojectsbudgetandspend' => ['projects', 'Projects'],			# 325
		'capprojectsbudgetspendhistory' => ['projects', 'Projects'],		# 326
		'capprojectsschedulehistory' => ['projects', 'Projects'],			# 327
	];
	
	
	/**
	 * Row counts per table, from the pipeline registry.
	 *
	 * ⚠⚠ THIS REPLACES SIX AJAX CALLS TO A ROUTE THAT HAS NEVER EXISTED.
	 * `loadTableStat()` fetched `/get/pstats-records_no/{table}` per dataset;
	 * `git log -S` over the whole repo history finds no commit that added or
	 * removed that route, and it 404s for every table. On a non-200 the caller
	 * ran `datasets.splice(i,1)` — so the page rendered six real dataset rows
	 * and then DELETED them, leaving "No data available in table" and two blank
	 * counters. Measured on the running site 2026-09-08.
	 *
	 * ⚠ `/pipeline/registry` already carries `estimated_rows` for 75 tables, and
	 * it matches `count(*)` EXACTLY on all six capital tables (12,929 / 41,277 /
	 * 56,525 / 288,446 / 53,495 / 22,464 — checked, not assumed). So no new
	 * endpoint is needed and the count arrives with the page instead of six
	 * round trips after it.
	 *
	 * ⚠ Returns [] when the registry cannot be reached, and the caller renders
	 * that as "not available" rather than as zero. A failed request is not an
	 * empty dataset.
	 */
	public static function rowCounts()
	{
		$reg = \App\Custom\DatabookAPI::reqOCE('/pipeline/registry', 8);
		$rows = is_array($reg) ? ($reg['rows'] ?? $reg['datasets'] ?? $reg) : [];
		$out = [];
		if (is_array($rows))
			foreach ($rows as $r) {
				if (!is_array($r) || empty($r['table_name'])) continue;
				if (isset($r['estimated_rows']) && is_numeric($r['estimated_rows']))
					$out[strtolower($r['table_name'])] = (int) $r['estimated_rows'];
			}
		return $out;
	}


	public function stats_data_sources($dd, $dslist=null, $counts=null)
	{
		$rr = $ii = [];
		if ($dd)
			foreach ($dd as $d)
				$ii[strtolower(str_replace('.csv', '', $d['Output Path']))] = $d;
		foreach ($dslist ?? array_keys($this->stats_datasets) as $tbl)
		{
			$route = $this->stats_datasets[$tbl];
			// Check if dataset info exists before accessing it
			if (isset($ii[$tbl])) {
				// ⚠⚠ A BLANK CELL IS NOT A CLAIM, and two of these columns are
				// blank for real rows. Measured 2026-09-10 against
				// `/get/datasets/all`: `capitalprojectslist` publishes no
				// description, and `capitalprojectsdollarscomp` publishes neither
				// a description NOR a Last Updated — so the RETIRED 2023 series
				// rendered with an empty date column, which is precisely where a
				// reader needs to see that it stops in October 2023.
				// ⚠ An em dash says "our registry does not carry this"; an empty
				// cell says nothing at all, which is invariant 7's fourth thing
				// (a number, 0, — and a blank are four different claims). The
				// `else` branch below already used "N/A" for a missing registry
				// ENTRY, so a present entry with a blank FIELD was the only one
				// of the three states with no spelling.
				// ⚠ The gap itself is upstream in the dataset registry and is not
				// fixed here — this stops it reading as an assertion.
				$dash = function ($v) {
					return (trim((string) $v) === '') ? '<span class="db-muted">&mdash;</span>' : $v;
				};
				$rr[$tbl] = [
					"<a href=\"{$ii[$tbl]['Citation URL']}\" target=\"_blank\" rel=\"nofollow\">{$ii[$tbl]['Name']}</a>",
					'<a href="' . route($route[0]) . "\">{$route[1]}</a>",
					$dash($ii[$tbl]['Descripton'] ?? ''),
					// ⚠ ONE DATE FORMAT. This cell published `09/05/2026 22:10`
					// while the profile publishes `23 Feb 2030`, and on the
					// budget-line page it sat on the SAME page as a commitments
					// table of raw dates. `CapitalDate` is in this namespace.
					$dash(CapitalDate::label($ii[$tbl]['Last Updated'] ?? '')),
					$this->countCell($tbl, $counts),
				];
			} else {
				// Provide fallback data when dataset info is missing
				$rr[$tbl] = [
					"Dataset: " . ucwords(str_replace('_', ' ', $tbl)),
					'<a href="' . route($route[0]) . "\">{$route[1]}</a>",
					"No description available",
					"N/A",
					$this->countCell($tbl, $counts),
				];
			}
		}
		return $rr;
	}


	/**
	 * The record-count cell.
	 *
	 * ⚠ Three states, and they are different facts: a known count, a table the
	 * registry does not track, and "we could not ask". The old markup had one —
	 * an empty span — so all three read as zero.
	 *
	 * ⚠ The `stats_<table>` id is KEPT so the pages still running the filtered
	 * `-by_*` lookups can overwrite this cell with their narrower count. Those
	 * three variants work; only the unfiltered form was missing.
	 */
	/**
	 * The dataset-row-count cell.
	 *
	 * ⚠⚠ PUBLIC AND STATIC BECAUSE THREE CLASSES RENDER THIS CELL —
	 * `ProjectsDatasets`, `DistDatasets` and `SchoolDatasets` — and all three used
	 * to emit a bare `<span id="stats_{tbl}"></span>` for JS that never arrived.
	 * Three copies of one rule is how the same defect ends up needing three fixes.
	 *
	 * ⚠ THREE STATES, and they are different claims:
	 *   null counts    → an empty span, for a caller that fills it by fetch
	 *   absent key     → "not tracked", i.e. we do not read that table's registry
	 *   a number       → the count
	 * A missing key must never render as 0.
	 */
	public static function countCell($tbl, $counts)
	{
		$id = 'stats_' . $tbl;
		if ($counts === null)
			return '<span id="' . $id . '"></span>';
		if (!array_key_exists($tbl, $counts))
			return '<span id="' . $id . '" class="text-muted">not tracked</span>';
		return '<span id="' . $id . '">' . number_format($counts[$tbl]) . '</span>';
	}
	
	
}