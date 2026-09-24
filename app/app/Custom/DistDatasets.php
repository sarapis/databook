<?php
Namespace App\Custom;

class DistDatasets
{
	public $dd = [
		'requests' => [
			'fullname' => 'Register of Community Board Budget Requests API',
			'table' => 'budgetrequestsregister',
			'hdrs' => ['Publication Date', 'Borough', 'C Board', 'Priority', 'Tracking Code', 'Request', 'Council District', 'NTA', 'Agency'],
			'visible' => [true, false, false, true, true, true, false, false, true],
			'flds' => [ 
						'function (r) { return toDashDate(r["Publication"]) }', 
						'"Borough"', '"Community Board"', '"Priority"', '"Tracking  Code"', '"Request"', '"wegov-cd-id"', '"wegov-nta-code"',
						'function (r) { return `<a href="/o/${r["wegov-org-id"]}-${slug(r["wegov-org-name"])}/requests">${r["wegov-org-name"]}</a>` }',
					  ], 
			'sort' => ['"Publication"', '"Borough"',],
			'filters' => [0 => '2020-07-01', 1 => null, 2 => null, 3 => null],
			'details' => [
						'Explanation' => 'Explanation',
						'Response' => 'Response',
						'Responded By' => 'Responded By',
						#'Responsible Agency' => 'Responsible Agency',
						'Site Street' => 'Site Street',
						'Number' => 'Number',
						'Street' => 'Street',
						'Block' => 'Block',
						'Lot' => 'Lot',
						'Postcode' => 'Postcode',
						'Council District' => 'Council District',
						'BIN' => 'BIN',
						'BBL' => 'BBL',
						'NTA' => 'NTA'			
			],
			'map' => ['cd' => 'Community Board', 'cc' => 'Council District', 'nta' => 'wegov-nta-code'],
		],
		
		'facilities' => [
			'fullname' => 'NYC Facilities Database',
			'table' => 'facilitydb',
			'hdrs' => ['Name', 'Category', 'Group', 'Subgroup', 'Address', 'Borough', 'Council District', 'NTA'],
			'visible' => [true, true, true, true, true, true, false, false],
			'flds' => ['"facname"', '"facdomain"', '"facgroup"', '"facsubgrp"', '"address"', '"boro"', '"wegov-cd-id"', '"wegov-nta-code"'], 
			'sort' => ['"facname"', '"facdomain"'],
			'filters' => [1 => null, 2 => null, 3 => null, 5 => null],
			'details' => [
					'Number' => 'number',
					'Street' => 'street',
					'City' => 'city',
					'Zipcode' => 'postcode',
					'Latitude' => 'latitude',
					'Longitude' => 'longitude',
					'BIN' => 'bin',
					'BBL' => 'bbl',
					'Community Board' => 'community board',
					'Council District' => 'council district',
					'Neighborhood' => 'nta',
					'Facility Type' => 'factype',
					'Capacity' => 'capacity',
					'Capital Type' => 'captype',
					'Property Type' => 'proptype'			
			],
			'description' => 'The Facilities Database (FacDB) captures the locations and descriptions of public and private facilities ranging from the provision of social services, recreation, education, to solid waste management.',
			'map' => ['cd' => 'wegov-comd-id', 'cc' => 'wegov-cd-id', 'nta' => 'wegov-nta-code'],	
		],

		'city-council-discretionary' => [								#nyccouncildiscretionaryfunding
			'fullname' => 'New York City Council Discretionary Funding',
			'table' => 'nyccouncildiscretionaryfunding',
			'hdrs' => ['Fiscal Year', 'Source', 'Council Member', 'Legal Name of Organization', 'Status', 'Amount ($)', 'Borough', 'Council District', 'NTA'],
			'visible' => [true, true, true, true, true, true, true, true, false],
			'flds' => [
					'"Fiscal Year"', '"Source"', '"Council Member"', 
					'function (r) { return `<a href="https://projects.propublica.org/nonprofits/organizations/${r["EIN"]}" target="_blank" rel="nofollow">${r["Legal Name of Organization"]}</a>` }',
					'"Status"', '"Amount ($)"', '"Borough"', '"Council District"', '"NTA"'
				], 
			'sort' => ['"Fiscal Year"', '"Source"'],
			'filters' => [0 => null, 1 => null, 2 => null, 6 => null, 7 => null],
			'details' => [
				'EIN' => 'EIN',
				'MOCS ID' => 'MOCS ID',
				'Program Name' => 'Program Name',
				'Address' => 'Address',
				'Address 2 (optional)' => 'Address 2 (optional)',
				'City' => 'City',
				'State' => 'State',
				'Postcode' => 'Postcode',
				'Purpose of Funds' => 'Purpose of Funds',
				'Fiscal Conduit Name' => 'Fiscal Conduit Name',
				'FC EIN' => 'FC EIN',
				'Latitude' => 'Latitude',
				'Longitude' => 'Longitude',
				'Community Board' => 'Community Board',
				'Census Tract' => 'Census Tract',
				'BIN' => 'BIN',
				'BBL' => 'BBL',
				'NTA' => 'NTA',
			],
			'description' => 'The dataset reflects applications for discretionary funding to be allocated by the New York City Council.',
			// No 'nta' mapping: this dataset's NTA column is 2010-vintage (stores 2010 NTA
			// *names*), but the district pages use 2020 NTAs — and 2010↔2020 differ in actual
			// boundaries, not just labels, so there is no valid crosswalk. Omitting the key
			// hides this section from NTA pages (menu() gates on map[$type]) and 404s any
			// direct URL (get() returns null). cd/cc are unaffected — they key on Community
			// Board / Council District, which are stored correctly.
			'map' => ['cd' => 'Community Board', 'cc' => 'Council District'],
		],

		'projects' => [						#capital_projects (the spine)
			// ⚠⚠ REPOINTED OFF `capitalprojectsdollarscomp` — the last surface on
			// the series NYC retired 2023-10-26. The old contract joined that table
			// to a `capitalprojects_{type}_idx` on `PROJECT_ID`; the spine's own
			// crosswalk is `capital_project_districts`, keyed on
			// `(agency_key, fms_id)` — the grain a bare FMS id does not have.
			// ⚠ EVERY MONEY CELL DROPPED ITS `, 1000`. The retired series is
			// denominated in THOUSANDS and the spine in USD, so carrying one over
			// renders $652.6M as $652.6B (invariant 2).
			'name' => 'Capital Projects',
			'fullname' => 'Capital Project Detail Data - Dollars',
			'table' => 'capital_projects',
			'description' => 'The derived capital projects spine: every project NYC publishes in the Capital Commitment Plan, the Capital Projects Dashboard, or the retired 2023 detail series, resolved to one row per (agency, FMS id). Only projects the City attributes to this district are listed.',
			// ⚠ NO SCOPE COLUMN. The old contract carried one because the retired
			// series stored a district string per row; the spine's district link is
			// a crosswalk, and every row here is in THIS district by construction.
			'hdrs' => ['Project ID', 'Agency', 'Name', 'Asset category', 'Phase', 'Planned commitments', 'Spent', 'In current plan'],
			'visible' => [true, true, true, true, true, true, true, true],
			'hide_on_map_open' => '3, 6, 7',
			'flds' => [
					// ⚠ THE CANONICAL, AGENCY-CONCATENATED ID — 1,160 bare FMS ids are
					// carried by more than one agency across 2,371 rows.
					'function (r) { return `<a href="/p/${r.id}_${slug(r.description)}">${r.id}</a>` }',
					// ⚠ 4,568 spine rows carry no `wegov_org_id`, so the agency is not
					// always a link; rendering one anyway produced `/o/-`.
					'function (r) { return r["wegov_org_id"] ? `<a href="/o/${r["wegov_org_id"]}-${slug(r["agency_name"])}/projects">${r["agency_name"]}</a>` : (r["agency_name"] || r["agency_acro"] || "") }',
					// ⚠⚠ EVERY CELL RETURNS A STRING, NEVER null — a null hands
					// DataTables something it tries to sort and search, which threw
					// `n.slice is not a function` while the rows still RENDERED.
					'function (r) { return r["description"] || "" }',
					'function (r) { return r["type_category"] || "" }',
					// ⚠ A blank phase means NYC publishes no schedule, not "no phase".
					'function (r) { return r["current_phase"] || "Not published" }',
					// ⚠ `data-content` is the SORT KEY — money columns are not monotonic
					// in their visible text. Multiplier 1, not 1000.
					'function (r) { return `<span data-content="${toFin(r["planned_total_usd"], 1)}">${toFinShortK(r["planned_total_usd"], 1)}</span>` }',
					'function (r) { return `<span data-content="${toFin(r["spent_total_usd"], 1)}">${toFinShortK(r["spent_total_usd"], 1)}</span>` }',
					'function (r) { return r["in_current_plan"] ? "Yes" : "No" }'
				],
			'filters' => [1 => null, 3 => null, 4 => null],
			// ⚠⚠ `order` IS NOT OPTIONAL — the view reads it inside an `@if`, and an
			// undefined index is an ErrorException that the `@if` does not guard.
			'order' => [[5, 'desc']],
			// ⚠⚠ `map` IS LOAD-BEARING: DistDatasets reads it to decide which sections
			// a district TYPE offers, and `get()` returns null for a type it omits.
			// ⚠⚠ `sd` IS NOW HERE, and that was the whole of "school districts are
			// broken". Measured 2026-09-10 before changing anything:
			//
			//     /d/sd-4_district                        200
			//     /districtXHR/sd/4/projects              **404**
			//     /get/capital/stats/sd/4                 200 — 144 projects
			//     /get/capital/projects/by-district/sd/4  200 — **144 rows**
			//
			// 144 == 144, so the spine serves school districts completely; the 404
			// was this map, one key wide. `projectSectionXHR` was already sd-ready
			// (it carries an `sd` branch for `linkedAgencyUrl` and for `datasets`).
			// ⚠ THE VALUE IS A PRESENCE MARKER FOR THIS CONTRACT, NOT A COLUMN.
			// Only `sectionXHR` reads `map[$type]`'s value (as the `f=` parameter),
			// and `Districts::index` routes `projects` to `projectSectionXHR`, which
			// builds the spine URL and never reads it. The four values named columns
			// on the RETIRED series and have been dead since the repoint; they name
			// the spine's actual crosswalk now so the map cannot be read as a claim
			// about a column that no longer decides anything. A guard pins that
			// `projects` never reaches `sectionXHR`.
			'map' => ['cd' => 'capital_project_districts', 'cc' => 'capital_project_districts',
			          'nta' => 'capital_project_districts', 'sd' => 'capital_project_districts'],
		],

	// ------ shools ------------------------

		'schools' => [
			'fullname' => 'Schools',
			'table' => 'schoollocations',
			'hdrs' => ['Location Name', 'Location Code', 'Managed By', 'Category', 'Grades', 'Status', 'Address', 'Neighborhood'],
			'visible' => [true, true, true, true, true, true, true, true],
			'flds' => [
					'function (r) { return `<a href="/s/${r.location_code}-${slug(r.location_name)}">${r.location_name}</a>` }', 
					'"location_code"', '"Managed_by_name"', '"Location_Category_Description"', '"Grades_text"', '"Status_descriptions"', '"primary_address_line_1"', '"NTA_Name"'
				], 
			'hide_on_map_open' => '',
			'sort' => ['"location_code"', '"Grades_text"'],
			'filters' => [2 => null, 5 => null, ],
			'description' => '2019 - 2020 School Locations',
			'details' => [],
			'map' => ['sd' => 'Geographical_District_code'],
		],

		'school-projects' => [
			'fullname' => 'School Projects',
			'table' => 'scacapitalprojectschedules',
			'hdrs' => ['Project School Name', 'Project Type', 'Project Description', 'Project Phase Name', 'Project Status Name', 'Project Phase Actual Start Date', 'Project Phase Planned End Date', 'Project Phase Actual End Date', 'Project Budget Amount', 'Final Estimate of Actual Costs Through End of Phase Amount', 'Total Phase Actual Spending Amount'],
			'visible' => [true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true],
			'flds' => [
					'"Project School Name"', '"Project Type"', '"Project Description"', '"Project Phase Name"', '"Project Status Name"', '"Project Phase Actual Start Date"', '"Project Phase Planned End Date"', '"Project Phase Actual End Date"', '"Project Budget Amount"', '"Final Estimate of Actual Costs Through End of Phase Amount"', '"Total Phase Actual Spending Amount"'
				], 
			'sort' => ['"Project School Name"', '"Project Type"'],
			'filters' => [],
			'description' => 'Capital Project Schedules and Budgets',
			'details' => [],
			'map' => ['sd' => 'Project Geographic District'],
		],

		'graduation' => [					# mjm3-8dw8 — docs/GRADUATION-INGEST-PLAN.md
			'fullname' => 'Graduation Results, Cohorts 2012-2019',
			'sectionTitle' => 'Graduation',
			'table' => 'graduationoutcomes',
			'description' => 'Graduation, Regents and dropout outcomes for the district as a whole, by cohort. Cohorts 2012-2019 are the graduating classes of 2016-2023; a cohort is labelled by the year students entered 9th grade.',
			'hdrs' => ['Cohort Year', 'Cohort', 'Category', '# Total Cohort', '# Grads', '% Grads', '# Advanced Regents', '% Advanced Regents of Cohort', '# Dropout', '% Dropout'],
			'visible' => [true, true, true, true, true, true, true, true, true, true],
			'flds' => ['"Cohort Year"', '"Cohort"', '"Category"',
				'function (r) { return commaThousands( r["# Total Cohort"] ); }',
				'function (r) { return commaThousands( r["# Grads"] ); }',
				'"% Grads"',
				'function (r) { return commaThousands( r["# Advanced Regents"] ); }',
				'"% Advanced Regents of Cohort"',
				'function (r) { return commaThousands( r["# Dropout"] ); }',
				'"% Dropout"'],
			// ⚠ Defaulted, NOT filtered at source: the endpoint returns every cohort
			// definition and every demographic breakdown (674-688 rows per district,
			// measured), and the reader can clear these to reach them. '4 year June'
			// is NYC's headline on-time measure.
			'filters' => [1 => null, 2 => null],
			'fltPreselect' => [1 => '4 year June', 2 => 'All Students'],
			'sort' => ['"Cohort Year"', '"Category"'],
			'details' => [],
			// ⚠ A district id here is a BARE NUMBER (1-32), the same shape as
			// schoollocations.Geographical_District_code — verified, all 32 present.
			'map' => ['sd' => 'Geographic Subdivision'],
		],

		'enrollment' => [
			'fullname' => 'Current & Future Enrollment',
			'sectionTitle' => 'Future Enrollment',
			'table' => 'scademostats',
			'hdrs' => ['Data Type', 'Year', 'PK', 'K', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', 'GED', 'SE1', 'Total'],
			'visible' => [true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true],
			'flds' => [
					'"Data Type"', '"Year"', '"PK"', '"K"', '"1"', '"2"', '"3"', '"4"', '"5"', '"6"', '"7"', '"8"', '"9"', '"10"', '"11"', '"12"', '"GED"', '"SE1"', '"Total"'
				], 
			'sort' => ['"Year"', '"Data Type"'],
			'filters' => [],
			'description' => 'Demographic Projection Report - Enrollment Projections - New York City Public Schools prepared by Statistical Forecasting.',
			'details' => [],
			'map' => ['sd' => 'Borough or District'],
		],

		'enrollment-past' => [
			'fullname' => '2017-18 - 2021-22 Demographic Snapshot',
			'sectionTitle' => 'Past Enrollment',
			'table' => 'demographics',
			'hdrs' => ['Year', 'Total', '3K', 'PK', 'K', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'],
			'visible' => [true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true],
			'flds' => [
					'"Year"', 
					'function (r) { return commaThousands( r["Total Enrollment"] ); }',
					'function (r) { return commaThousands( r["Grade 3K"] ); }',
					'function (r) { return commaThousands( r["Grade PK (Half Day & Full Day)"] ); }',
					'function (r) { return commaThousands( r["Grade K"] ); }',
					'function (r) { return commaThousands( r["Grade 1"] ); }',
					'function (r) { return commaThousands( r["Grade 2"] ); }',
					'function (r) { return commaThousands( r["Grade 3"] ); }',
					'function (r) { return commaThousands( r["Grade 4"] ); }',
					'function (r) { return commaThousands( r["Grade 5"] ); }',
					'function (r) { return commaThousands( r["Grade 6"] ); }',
					'function (r) { return commaThousands( r["Grade 7"] ); }',
					'function (r) { return commaThousands( r["Grade 8"] ); }',
					'function (r) { return commaThousands( r["Grade 9"] ); }',
					'function (r) { return commaThousands( r["Grade 10"] ); }',
					'function (r) { return commaThousands( r["Grade 11"] ); }',
					'function (r) { return commaThousands( r["Grade 12"] ); }',
				], 
			'sort' => ['"Year"', '"Total Enrollment"'],
			'filters' => [],
			'description' => 'Enrollment counts are based on the October 31 Audited Register for the 2017-18 to 2019-20 school years. To account for the delay in the start of the school year, enrollment counts are based on the November 13 Audited Register for 2020-21 and the November 12 Audited Register for 2021-22.',
			'details' => [],
			'map' => ['sd' => 'wegov-sd-id'],
		],

		'city-council-stat-cases' => [
			'fullname' => 'NYC Council Constituent Services',
			'sectionTitle' => 'CouncilStat Cases',
			'table' => 'councilstatcases',
			'hdrs' => ['ID', 'Submitted By', 'Opened', 'Complaint Type', 'Description', 'Closed'],
			'visible' => [true, true, true, true, true, true],
			'flds' => ['"UNIQUE_KEY"', '"ACCOUNT"', '"OPENDATE"', '"COMPLAINT_TYPE"', '"DESCRIPTOR"', '"CLOSEDATE"'], 
			'sort' => ['"UNIQUE_KEY"', '"ACCOUNT"'],
			'filters' => [],
			'description' => 'The dataset comes from CouncilStat, which is used by many NYC Council district offices to enter and track constituent cases that can range from issues around affordable housing, to potholes and pedestrian safety. This dataset aggregates the information that individual staff have input. However, district staffs handle a wide range of complex issues. Each offices uses the program differently, and thus records cases, differently and so comparisons between accounts may be difficult. Not all offices use the program. For more info - <a href="http://labs.council.nyc/districts/data/">http://labs.council.nyc/districts/data/</a>',
			'details' => [
				'Zipcode' => 'ZIP',
				'Borough' => 'BOROUGH',
				'City' => 'CITY',
				'Council District' => 'COUNCIL_DIST',
				'Community Board' => 'COMMUNITY_BOARD',
			],
			'map' => ['cd' => 'Community Board', 'cc' => 'Council District'],
		],
	];

	public $list = [
		'city-council-discretionary' => 'City Council Discretionary Spending',
		'city-council-stat-cases' => 'City Council Stat Cases',
		// ⚠⚠ THESE TWO USED TO BOTH READ "Projects", AND GIVING `sd` A CAPITAL
		// SECTION PUT THEM IN ONE MENU. They are different datasets: `projects`
		// is the capital spine (its own contract is already named 'Capital
		// Projects'), and `school-projects` is the SCA's
		// `scacapitalprojectschedules` — school CONSTRUCTION, keyed on
		// 'Project Geographic District'. `$list` is flat, so the label cannot be
		// varied per district type; both are renamed to what they actually are.
		'projects' => 'Capital Projects',
		'requests' => 'Requests',
		'facilities' => 'Facilities',
		'enrollment' => 'Future',
		'enrollment-past' => 'Past',
		'schools' => 'Schools',
		'school-projects' => 'School Construction',
		'graduation' => 'Graduation',
	];
	
	public $menu = [
		'cd' => [
			'city-council-discretionary',
			'city-council-stat-cases',
			'projects',
			'requests',
			'facilities',
		],
		'cc' => [
			'city-council-discretionary',
			'city-council-stat-cases',
			'projects',
			'requests',
			'facilities',
		],
		'nta' => [
			// 'city-council-discretionary' intentionally omitted — its NTA data is
			// 2010-vintage and incompatible with the 2020 NTA geography (see the
			// 'city-council-discretionary' map comment above).
			'projects',
			'requests',
			'facilities',
		],
		'sd' => [
			'schools',
			// ⚠ AFTER `schools`, NOT BEFORE — `defaultSection['sd']` stays 'schools',
			// which is the canonical url already published for every school
			// district. Deriving the landing section from the first menu item is
			// exactly the thing `$defaultSection` exists to prevent, but leaving
			// the order alone means the two cannot disagree even if someone later
			// does derive it.
			'projects',
			'school-projects',
			'graduation',
			'Enrollment' => [
				'enrollment',
				'enrollment-past',
			]
		],
	];
	
	public $cdAltName = ['101' => 'MN01', '102' => 'MN02', '103' => 'MN03', '104' => 'MN04', '105' => 'MN05', '106' => 'MN06', '107' => 'MN07', '108' => 'MN08', '109' => 'MN09', '110' => 'MN10', '111' => 'MN11', '112' => 'MN12', '201' => 'BX01', '202' => 'BX02', '203' => 'BX03', '204' => 'BX04', '205' => 'BX05', '206' => 'BX06', '207' => 'BX07', '208' => 'BX08', '209' => 'BX09', '210' => 'BX10', '211' => 'BX11', '212' => 'BX12', '301' => 'BK01', '302' => 'BK02', '303' => 'BK03', '304' => 'BK04', '305' => 'BK05', '306' => 'BK06', '307' => 'BK07', '308' => 'BK08', '309' => 'BK09', '310' => 'BK10', '311' => 'BK11', '312' => 'BK12', '313' => 'BK13', '314' => 'BK14', '315' => 'BK15', '316' => 'BK16', '317' => 'BK17', '318' => 'BK18', '401' => 'QN01', '402' => 'QN02', '403' => 'QN03', '404' => 'QN04', '405' => 'QN05', '406' => 'QN06', '407' => 'QN07', '408' => 'QN08', '409' => 'QN09', '410' => 'QN10', '411' => 'QN11', '412' => 'QN12', '413' => 'QN13', '414' => 'QN14', '501' => 'SI01', '502' => 'SI02', '503' => 'SI03'];
	
	
	
	public function menu($type)
	{
		$rr = [];
		foreach ($this->menu[$type] as $h=>$vv)
			if (is_array($vv))
			{
				foreach ($vv as $i=>$v)
					if (isset($this->dd[$v]['map'][$type]))
						$rr[$h][$i] = $v;
			} elseif (isset($this->dd[$vv]['map'][$type]))
				$rr[$h] = $vv;
		return $rr;
	}
	
	public function menuActiveDD($type, $sect)
	{
		foreach ($this->menu[$type] as $h=>$items)
			if (is_array($items) && (array_search($sect, $items) !== false))
				return $h;
		return '';
	}
	
	
	// ⚠⚠ `projects` IS NOT A UNIVERSAL LANDING SECTION, and the reason has
	// CHANGED — corrected 2026-09-10. It used to be that `sd` had no capital
	// section at all (the contract's `map` carried no `sd` key, so
	// get('projects','sd') returned null and projectSectionXHR() abort(404)ed).
	// `sd` HAS one now. What is still true is that its LANDING section is
	// `schools`, because that is the canonical url already published for every
	// school district — so this map stays declared rather than derived.
	// Every sd district URL that named no section used to land
	// exactly there, because the bare /d/{type}-{id}-{dslug} redirect AND
	// Schema::district()'s canonical url both hardcoded 'projects' — so the one
	// URL shape a link would naturally use was the one guaranteed to 404, while
	// /d/sd-10-x/schools worked the whole time (which is what the districts map
	// itself links to). One owner now, so a landing section cannot be decided
	// in two places again.
	// ⚠ Declared per type rather than derived from menu()'s first item: cd, cc
	// and nta land on `projects` today and their canonical urls are published,
	// so deriving would silently move three types' canonical url to
	// city-council-discretionary. `defaultSection()` falls back to the first
	// menu item, so a new type that has a menu cannot 404 before anyone
	// declares its landing section; a guard demands the declaration anyway, so
	// the fallback is a safety net rather than the answer. It returns null for
	// a type with no menu at all, which is a state `sectionXHR` already cannot
	// serve.
	public $defaultSection = [
		'cd' => 'projects',
		'cc' => 'projects',
		'nta' => 'projects',
		'sd' => 'schools',
	];
	
	public function defaultSection($type)
	{
		if (isset($this->defaultSection[$type]))
			return $this->defaultSection[$type];
		if (isset($this->menu[$type]))
			foreach ($this->menu($type) as $vv)
				return is_array($vv) ? reset($vv) : $vv;
		return null;
	}
	
	public function get($section, $type)
	{
		$dd = $this->dd[strtolower($section)] ?? null;
		if (!$dd)
			return $dd;
		if (!isset($dd['map']) || !isset($dd['map'][$type]))
			return null;
		
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
		// ⚠⚠ PRESELECTS COME FROM AN EXPLICIT `fltPreselect`, NEVER FROM A NON-NULL
		// VALUE IN `filters`. `filters` has documented `fld no => def value` since it
		// was written and only the KEYS were ever read, so a value there is DORMANT —
		// and `requests` carries one (`0 => '2020-07-01'`, a Publication Date).
		// Deriving preselects from `filters` would therefore have silently pinned the
		// live Requests page to a single date. Opt in explicitly instead, so a dormant
		// declaration stays dormant and turning one on is a visible edit.
		$pre = [];
		foreach ((array)($dd['fltPreselect'] ?? []) as $i=>$v)
			$pre[$i + $inc] = $v;
		$dd['fltDefaults'] = (object)$pre;
		return $dd;
	}


	

	// ⚠ `$counts` is LAST and optional: this signature differs from
	// `ProjectsDatasets`' and a positional insert would have silently landed the
	// counts in `$dslist`. (It nearly did — a blind edit across both controllers.)
	public function stats_data_sources($dd, $id, $type, $dslist=null, $counts=null)
	{
		$stats_datasets = [
			
			'nyccouncildiscretionaryfunding' => [																				# table => route
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'Discretionary Funding'
			],
			// ⚠⚠ THE SPINE'S SOURCES, NOT ONE OF THEM. The district capital tab reads
			// `capital_projects`, which is built from FOUR publications — and this map
			// named only `capitalprojectsdollarscomp`, the retired one, whose row is
			// blank in the panel ("not tracked", no description, no date) because it is
			// never ingested. So the sources panel for a tab whose every figure comes
			// from the spine listed a single 2023 publication and nothing else.
			// Measured 2026-09-10: "normalized data from 5 datasets containing 227,395
			// records", the capital row contributing 0.
			// ⚠ The retired series STAYS. `build_capital_projects.py` reads it for scope
			// text, borough and the 2023 budgets, so naming it is accurate; naming it
			// ALONE is what was wrong. `/projects` already lists all four and reads
			// 475,136 records.
			'capitalprojectsdollarscomp' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'projects']),
				'Projects'
			],
			'capitalprojectslist' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'projects']),
				'Projects'
			],
			'capprojectsbudgetsandschedule' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'projects']),
				'Projects'
			],
			'capitalprojectscommitments' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'projects']),
				'Projects'
			],
			'budgetrequestsregister' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'requests']),
				'Budget Requests'
			],
			'facilitydb' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'facilities']),
				'Facilities'
			],
			'ccmembers' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'District'
			],
			'nyccommunityboards' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'District'
			],
			'nta' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'nta', 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'District'
			],
			'cd' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'cd', 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'District'
			],
			'cc' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'cc', 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'District'
			],

			'scademostats' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'sd', 'dslug'=>'-', 'section'=>'enrollment']),
				'District'
			],
			'demographics' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'sd', 'dslug'=>'-', 'section'=>'enrollment-past']),
				'District'
			],
			'schoollocations' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'sd', 'dslug'=>'-', 'section'=>'schools']),
				'District'
			],
			'scacapitalprojectschedules' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'sd', 'dslug'=>'-', 'section'=>'school-projects']),
				'District'
			],
			'sd' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'sd', 'dslug'=>'-', 'section'=>'enrollment']),
				'District'
			],
			
		];

		$rr = [];
		$ii = [
			'nta' => [
				'Citation URL' => 'https://data.cityofnewyork.us/City-Government/2020-Neighborhood-Tabulation-Areas-NTAs-Tabular/9nt8-h7nd', 
				'Name' => '2020 Neighborhood Tabulation Areas (NTAs)',
				'Descripton' => '2020 Neighborhood Tabulation Areas (NTAs) are medium-sized statistical geographies for reporting Decennial Census and American Community Survey (ACS). 2020 NTAs are created by aggregating 2020 census tracts and nest within Community District Tabulation Areas (CDTA). NTAs were delineated with the need for both geographic specificity and statistical reliability in mind. Consequently, each NTA contains enough population to mitigate sampling error associated with the ACS yet offers a unit of analysis that is smaller than a Community District.',
				'Last Updated' => '4/6/2023 11:00pm'
			],
			'cd' => [
				'Citation URL' => 'https://data.cityofnewyork.us/City-Government/Community-Districts/yfnk-k7r4', 
				'Name' => 'Community Districts',
				'Descripton' => 'GIS data: Boundaries of Community Districts.',
				'Last Updated' => '4/6/2023 11:00pm'
			],
			'cc' => [
				'Citation URL' => 'https://data.cityofnewyork.us/City-Government/City-Council-Districts/yusd-j4xi', 
				'Name' => 'City Council Districts',
				'Descripton' => 'GIS data: Boundaries of City Council Districts.',
				'Last Updated' => '4/6/2023 11:00pm'
			],
			'sd' => [
				'Citation URL' => 'https://data.cityofnewyork.us/Education/School-Districts/r8nu-ymqj', 
				'Name' => 'School Districts',
				'Descripton' => 'GIS data: Boundaries of School Districts.',
				'Last Updated' => '4/6/2023 11:00pm'
			],
		];
		foreach ($dd as $d)
			$ii[strtolower(str_replace('.csv', '', $d['Output Path']))] = $d;
		foreach ($dslist ?? array_keys($stats_datasets) as $tbl)
		{
			$route = $stats_datasets[$tbl];
			$rr[$tbl] = [
				"<a href=\"{$ii[$tbl]['Citation URL']}\" target=\"_blank\" rel=\"nofollow\">{$ii[$tbl]['Name']}</a>",
				'<a href="' . $route[0] . "\">{$route[1]}</a>",
				$ii[$tbl]['Descripton'],
				$ii[$tbl]['Last Updated'],
				\App\Custom\ProjectsDatasets::countCell($tbl, $counts),
			];
		}
		return $rr;
	}
	

}