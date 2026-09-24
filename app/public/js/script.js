/* Helper functions */

/* Toggle in-map filter panel */
function toggleMapFilterPanel() {
	var panel = document.getElementById('mapFilterPanel');
	var toggleBtn = document.getElementById('mapFilterToggle');
	if (panel) {
		var isHidden = panel.style.display === 'none';
		panel.style.display = isHidden ? 'flex' : 'none';
		if (toggleBtn) {
			toggleBtn.style.display = isHidden ? 'none' : 'block';
		}
	}
}

function unescape(t) {
	return t.replace(/""/g, '"').replace(/''/g, "'")
}

function toDashDate(d) {
	if (!d)
		return ''
	y = d.toString().substr(0, 4)
	m = d.toString().substr(4, 2)
	d = d.toString().substr(6, 2)
	return '<span class="text-nowrap">' + y + '-' + m + '-' + d + '</span>';
}

function toDashDateNowrap(d) {
	if (!d)
		return ''
	y = d.toString().substr(0, 4)
	m = d.toString().substr(4, 2)
	d = d.toString().substr(6, 2)
	return y + '-' + m + '-' + d;
}

function toUsDateNowrap(d) {
	if (!d)
		return ''
	y = d.toString().substr(0, 4)
	m = d.toString().substr(4, 2)
	dd = d.toString().substr(6, 2)
	return m + '/' + dd + '/' + y;
}

function usToDashDate(d) {
	if (!d)
		return ''
	m = d.toString().substr(0, 2)
	dd = d.toString().substr(3, 2)
	y = d.toString().substr(8, 2)
	tt = d.toString().substr(10, 20)
	return '<span class="text-nowrap">20' + y + '-' + m + '-' + dd + tt + '</span>';
}

function usToDashDateNowrap(d, shortYr = false) {
	if (!d)
		return ''
	m = d.toString().substr(0, 2)
	dd = d.toString().substr(3, 2)
	y = shortYr
		? '20' + d.toString().substr(6, 2)
		: d.toString().substr(6, 4)
	return y + '-' + m + '-' + dd;
}

function dashToUsDate(d) {
	if (!d)
		return ''
	m = d.toString().substr(5, 2)
	dd = d.toString().substr(8, 2)
	y = d.toString().substr(2, 2)
	return m + '/' + dd + '/' + y;
}

function toFin(d, m = 1) {
	if (Object.is(d, null) || d === '') return '';
	let val = parseFloat(d);
	if (isNaN(val)) return '';
	return '$' + (val * m).toFixed(0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")
}

function commaThousands(d, m = 1) {
	if (Object.is(d, null) || d === '') return '';
	let val = parseFloat(d);
	if (isNaN(val)) return '';
	return (val * m).toFixed(0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")
}

function toFinShortK(d, m = 1) {
	if (Object.is(d, null) || d === '') return '';
	d = parseFloat(d) * m
	if (isNaN(d)) return '';
	if (d < 1000)
		return '$' + d.toFixed(0)
	var units = { 0: 'K', 1: 'M', 2: 'B' }
	for (let u = 0; u <= 2; u++) {
		d = d / 1000
		if (d < 1000) {
			if (d >= 100) {
				return '$' + d.toFixed(0) + units[u]
			} else if (d >= 10) {
				return '$' + d.toFixed(1) + units[u]
			} else if (d >= 1) {
				return '$' + d.toFixed(2) + units[u]
			}
		}
	}
}

function toPerc(p, a) {
	if (!parseFloat(p))
		return '-'
	return ((parseFloat(a) / parseFloat(p) - 1) * 100).toFixed(0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",") + '%'
}


function sortUsDatesList(dd, shortYr = false) {
	return dd.sort(function (a, b) {
		aa = usToDashDateNowrap(a, shortYr)
		bb = usToDashDateNowrap(b, shortYr)
		if (aa < bb)
			return -1
		if (aa > bb)
			return 1
		return 0
	})
}



function globStatView(dd) {
	for (const [sel, val] of Object.entries(dd)) {
		ee = $('#' + sel)
		if (!ee.length)
			continue;
		el = ee[0]
		if (sel == 'latest_update') {
			var d = new Date(val);
			var options = {
				year: 'numeric', month: 'numeric', day: 'numeric',
				hour: 'numeric', minute: 'numeric',
				timeZone: 'America/New_York'
			};
			$(el).text(d.toLocaleString('en-US', options));
		}
		else if ($(el).hasClass('gs_fin'))
			$(el).text(toFin(val))
		else if ($(el).hasClass('gs_finshort'))
			$(el).text(toFinShortK(val, $(el).data('multiplier') ? parseFloat($(el).data('multiplier')) : 1))
		else if ($(el).hasClass('gs_perc'))
			$(el).text(toPerc(val))
		else if ($(el).hasClass('gs_thousandscomma'))
			$(el).text(commaThousands(val))
		else
			$(el).text(val)
	}
}


window.onscroll = function () { scrollFunction() }

function scrollFunction() {
	if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
		$('#return-to-top').show()
	} else {
		$('#return-to-top').hide()
	}
}

function topFunction() {
	document.body.scrollTop = 0; // For Safari
	document.documentElement.scrollTop = 0; // For Chrome, Firefox, IE and Opera
}

function subscribe_newsletter() {
	var email = $('#newsletter-email').val()
	$.get(`/api/newsletter_subscription`, { 'key': 'as9s8d6d78as6f9sdf876', 'email': email }, function (data) {
		var jj = JSON.parse(data)
		if (jj['success']) {
			$('#newsletter-subs div.row').html('<div class="col-sm-12 col-form-label" style="color:#fff;">✓ Thank you for subscribing!</div>');
			$('#newsletter-subs small').html('Your email address');
			$('#newsletter-subs small').attr('style', 'color:white;');
		}
		else {
			$('#newsletter-subs small').html('Failed. Please try again');
			$('#newsletter-subs small').attr('style', 'color:red;');
		}
	})
}

function intWithCommas(x) {
	return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function initPopovers() {
	$('[data-content]').each(function () {
		$(this).attr('data-container', 'body')
		$(this).attr('data-toggle', 'popover')
		$(this).attr('data-placement', 'bottom')
		$(this).popover()
		$(this).on('show.bs.popover', function () {
			$('[data-content]').not(this).popover('hide')
			$('.popover').hide()
		})

	});
}


/** maps ******************************************/


var map = null
var zones = { 'cc': '#9abe0c', 'cd': '#bc2b32', 'nta': '#185892', 'ed': '#a881c2', 'pp': '#be7957', 'dsny': '#d2ac6d', 'fb': '#77aa98', 'sd': '#3e7864', 'hc': '#085732', 'nycongress': '#f3bd1c', 'sa': '#f5912f', 'ss': '#dc2118', 'bid': '#39a6a5', 'zipcode': '#7a7e5a' }
var filtFields = { 'cd': 'nameCol', 'cc': 'nameCol', 'nta': 'nameAlt', 'sd': 'nameCol' }

function newMap() {
	mapboxgl.accessToken = 'pk.REPLACE_WITH_YOUR_MAPBOX_TOKEN';

	var center = (typeof center == 'undefined') ? [-73.957, 40.727] : center;
	var zoom = (typeof zoom == 'undefined') ? 11 : zoom;

	map = new mapboxgl.Map({
		container: 'map',
		style: 'mapbox://styles/mapbox/light-v10',
		center: center,
		zoom: zoom
	});

	// Zoom stepper bottom-right (no compass) so it clears the top-right overlay controls
	map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'bottom-right');

}


/** org section map ******************************************/

function applyFilterOnClick(e) {
	var chckbox = $('#map-controls input:checked')
	//console.log(chckbox, typeof chckbox)
	if (typeof chckbox.attr('id') == 'undefined') {
		var code = $('#button-addon3 span').attr('trg')
		var col = { 'cc': 'city-council-discretionary', 'cd': 'city-council-discretionary', 'nta': 'city-council-discretionary', 'sd': 'schools' }[code]
	} else {
		var code = chckbox.attr('id').replace('-filter-switch', '')
		var col = chckbox.attr('param')
	}
	var filtField = filtFields[code]

	var bbox = [
		[e.point.x, e.point.y],
		[e.point.x, e.point.y]
	];
	var features = map.queryRenderedFeatures(bbox, {
		layers: [code + 'FHH']
	});

	var filter = features.reduce(
		function (memo, feature) {
			memo.push(feature.properties[filtField]);
			return memo;
		},
		['in', filtField]
	);

	mapAction(filter, code, col);

	map.setFilter(code + 'FH', filter);
}


function orgSectionMapInit(filters, filterType) {
	newMap();

	$('select, option').click(function (e) {
		e.stopPropagation();
	});

	var geojson = { 'type': 'FeatureCollection', 'features': [] };

	/*
	if (filterType == 'sd')
		schoolsMapInit(true);
	else
	*/
	projectsMapInit(true);

	map.on('load', function () {

		for (const [code, clr] of Object.entries(zones)) {
			setBoundary(code, clr, clr);
		}

		for (const [code, col] of Object.entries(filters)) {
			setFilter(code, col);
		}

		if (typeof filterType == 'undefined')
			window.setTimeout(function () {
				if (!$('#map-controls div:nth-child(2) input:checked').length)
					$('#map-controls div:nth-child(2) input')[0].click();
			}, 500
			)
		else
			window.setTimeout(function () {
				//	enable preset filter
				$(`#${filterType}-filter-switch`).click();
				$(`#${filterType}-button`).click();
			}, 500
			)

		map.on('click', function (e) { applyFilterOnClick(e); })

	});

}

function setBoundary(code, lineClr, symbClr) {

	map.addSource(code, {
		type: "geojson",
		data: `/data/${code}.geojson`
	});

	map.addLayer({
		"id": code + 'L',
		"type": "line",
		"source": code,
		"layout": {
			'visibility': 'none',
		},
		"paint": {
			"line-color": lineClr,
			"line-width": 1
		}
	});

	map.addLayer({
		"id": code + 'S',
		"type": "symbol",
		"source": code,
		"layout": {
			'text-field': '{nameCol}',
			'visibility': 'none',
			'text-size': {
				"base": 1,
				"stops": [
					[12, 12],
					[16, 16]
				]
			},
		},
		"paint": {
			"text-color": symbClr,
			"text-halo-color": "hsl(0, 0%, 100%)",
			"text-halo-width": 0.5,
			"text-halo-blur": 1
		}
	});

	$(`#${code}-switch`).change(function () {
		if ($(this).is(':checked')) {
			map.setLayoutProperty(code + 'L', 'visibility', 'visible');
			map.setLayoutProperty(code + 'S', 'visibility', 'visible');
		} else {
			map.setLayoutProperty(code + 'L', 'visibility', 'none');
			map.setLayoutProperty(code + 'S', 'visibility', 'none');
		}
	});

	$(`label[for="${code}-switch"] hr`).attr('style', `background-color: ${lineClr};`);
}

function setFilter(code, col) {
	var clr = zones[code]
	var filtField = filtFields[code]
	map.addLayer({
		"id": code + 'FH',
		"type": "fill",
		"source": code,
		"layout": {
			'visibility': 'none',
		},
		'paint': {
			'fill-outline-color': clr,
			'fill-color': clr,
			'fill-opacity': 0.4
		},
		'filter': ['in', filtField, '']
	},
		'settlement-label'
	);

	var filter = ['has', 'nameCol']

	if (typeof datatable != 'undefined') {
		datatable.columns([col]).every(function (c, a, i) {
			var vv = []
			this.data().each(function (d, j) {
				d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
				if (d)
					vv.push(d)
			})
			vv = [...new Set(vv)]
			filter = vv.reduce(
				function (memo, v) {
					memo.push(v);
					return memo;
				},
				['in', filtField]
			);
		});
	}

	map.addLayer({
		"id": code + 'FHH',
		"type": "fill",
		"source": code,
		"layout": {
			'visibility': 'none',
		},
		'paint': {
			'fill-color': clr,
			'fill-opacity': 0.3
		},
		'filter': filter
	},
		'settlement-label'
	);
	map.addLayer({
		"id": code + 'FL',
		"type": "line",
		"source": code,
		"layout": {
			'visibility': 'none',
		},
		"paint": {
			"line-color": clr,
			"line-width": 1
		},
		'filter': filter
	},
		'settlement-label'
	);
	map.addLayer({
		"id": code + 'FS',
		"type": "symbol",
		"source": code,
		"layout": {
			'text-field': '{nameCol}',
			'visibility': 'none',
			'text-size': {
				"base": 1,
				"stops": [
					[12, 12],
					[16, 16]
				]
			},
		},
		"paint": {
			"text-color": clr,
			"text-halo-color": "hsl(0, 0%, 100%)",
			"text-halo-width": 0.5,
			"text-halo-blur": 1
		},
		'filter': filter
	},
		'settlement-label'
	);

}
/** /org section map ******************************************/



/** projects map ******************************************/

var popup = null
function mapPopup(e) {
	var obj = e.features[0].properties;
	//console.log('mapPopup', obj);
	var description = ('SCHOOL_ID' in obj)

		? `
		<table><tbody>
			<tr><th scope="row">Name</th><td><a href="/s/${obj.SCHOOL_ID}-${slug(obj.NAME)}">${obj.NAME}</a></td></tr>
			<tr>
				<th scope="row">School District</th>
				<td><a href="/d/sd-${obj.SCHOOL_DISTRICT}-${slug('COMMUNITY SCHOOL DISTRICT ' + obj.SCHOOL_DISTRICT)}/schools">${obj.SCHOOL_DISTRICT}</a></td>
			</tr>
			<tr><th scope="row">Type</th><td>${obj.TYPE}</td></tr>
			<tr><th scope="row">Category</th><td>${obj.CATEGORY}</td></tr>
			<tr><th scope="row">Principal Name</th><td>${obj.PRINCIPAL_NAME}</td></tr>
			<tr><th scope="row">Phone</th><td>${obj.PRINCIPAL_PHONE}</td></tr>
		</tbody></table>`

		: `<table><tbody>
		<tr><th scope="row">Name</th><td><a href="/p/${obj.PRJ_ID}_${slug(obj.NAME)}">${obj.NAME}</a></td></tr>
		<tr><th scope="row">Agency</th><td>${obj.AGENCY}</td></tr>
		<tr><th scope="row">Category</th><td>${obj.CATEGORY}</td></tr>
		<tr><th scope="row" class="pr-2">Planned Cost</th><td data-content="${toFin(obj.PLANNEDCOST.replaceAll(',', ''), 1)}">${toFinShortK(obj.PLANNEDCOST.replaceAll(',', ''), 1)}</td></tr>
		<tr><th scope="row">Start</th><td>${obj.START_CURR}</td></tr>
		<tr><th scope="row">End</th><td>${obj.END_CURR}</td></tr>
	</tbody></table>`;

	map.fitBounds([
		[obj.W, obj.S],
		[obj.E, obj.N]
	], {
		padding: [50, 50],
		maxZoom: 18,
		duration: 1000,
		animate: true,
		essential: true,
	});

	if (popup)
		popup.remove();

	popup = new mapboxgl.Popup()
		.setLngLat(e.lngLat)
		.setHTML(description)
		.addTo(map);
	initPopovers();
	e.stopPropagation();
}


/**
 * Parse a GEO_JSON string served by the API.
 *
 * ⚠⚠ TRY THE VALUE AS SERVED FIRST. Callers historically did
 * `JSON.parse(s.replaceAll('""', '"'))` to undo CSV quote-doubling, but the API
 * serves clean JSON straight from Postgres — and on correctly-escaped JSON that
 * replace CORRUPTS the value. A project named  Plaza"A"  is stored with the
 * quotes escaped as  \"A\" , and the replace collapses the trailing  \""  to
 * \" , which unterminates the string.
 *
 * Measured 2026-09-04 over every capital project carrying geometry in the
 * newest publication: **all 3,082 parse as served, and exactly one fails after
 * the replace** — `P-1PELHAM`, "Pelham Parkway Malls-Plaza"A"" (Parks). The
 * per-row catch at each call site swallowed it, so that project was silently
 * absent from the map rather than erroring.
 *
 * The fallback is kept so a genuinely quote-doubled source still works: this
 * can only widen what parses, never narrow it.
 */
function parseGeoJSON(s) {
	try {
		return JSON.parse(s);
	} catch (e) {
		return JSON.parse(String(s).replaceAll('""', '"'));
	}
}


function projectsMapInit(as_addon = false) {
	if (!as_addon)
		newMap();

	map.on('load', function () {
		map.addSource('route', {
			type: "geojson",
			data: {
				"type": "FeatureCollection",
				"features": [{ "type": "Feature", "properties": { "custom_color": "#C0DDC0" }, "geometry": { "type": "Point", "coordinates": ["-73.95098200", "40.82387280"] } }]
			}
		});
		map.addLayer({
			'id': 'markers',
			'type': 'circle',
			'source': 'route',
			'paint': {
				'circle-radius': 5,
				'circle-color': ['get', 'custom_color']
			},
			'filter': ['==', '$type', 'Point']
		});

		map.addLayer({
			'id': 'streets',
			'type': 'line',
			'source': 'route',
			'layout': {
				'line-join': 'round',
				'line-cap': 'round'
			},
			'paint': {
				'line-color': ['get', 'custom_color'],
				'line-width': 5
			},
			'filter': ['==', '$type', 'LineString']
		});

		map.addLayer({
			'id': 'areas',
			'type': 'fill',
			'source': 'route',
			'paint': {
				'fill-color': ['get', 'custom_color'],
				'fill-opacity': 0.75
			},
			'filter': ['==', '$type', 'Polygon']
		});
		map.on('zoom', () => {
			var z = map.getZoom();
			const zz = { 12: 6, 11: 5, 10: 4, 9: 3, 8: 2 }
			for (const [l, r] of Object.entries(zz)) {
				if (z > l) {
					map.setPaintProperty('markers', 'circle-radius', r);
					map.setPaintProperty('streets', 'line-width', r);
				}
			}
		});

		map.on('click', 'areas', mapPopup);
		map.on('click', 'streets', mapPopup);
		map.on('click', 'markers', mapPopup);

		// Change the cursor to a pointer when the mouse is over the places layer.
		map.on('mouseenter', 'streets', function () { map.getCanvas().style.cursor = 'pointer'; });
		map.on('mouseenter', 'markers', function () { map.getCanvas().style.cursor = 'pointer'; });
		map.on('mouseenter', 'areas', function () { map.getCanvas().style.cursor = 'pointer'; });

		// Change it back to a pointer when it leaves.
		map.on('mouseleave', 'streets', function () { map.getCanvas().style.cursor = ''; });
		map.on('mouseleave', 'markers', function () { map.getCanvas().style.cursor = ''; });
		map.on('mouseleave', 'areas', function () { map.getCanvas().style.cursor = ''; });

		if (!as_addon) {
			for (const [code, clr] of Object.entries(zones)) {
				setBoundary(code, clr, clr);
			}
		}
	});
}


function schoolsMapDrawFeatures(dd, do_fitbounds = true) {
	projectsMapDrawFeatures(dd, do_fitbounds);
}


function projectsMapDrawFeatures(dd, do_fitbounds = true) {
	// ⚠⚠ WAIT FOR THE MAP, OR THE WHOLE MAP SILENTLY STAYS EMPTY. The 'route'
	// source this function writes to is added inside projectsMapInit's
	// `map.on('load')` handler, while the caller fires the moment the API
	// responds. Whichever wins is a race: when the DATA wins, `getSource`
	// returns undefined, `src.setData(...)` throws, and the page renders a
	// basemap with no features and only a console error.
	//
	// Measured 2026-09-04: against a local API (~20ms) the data wins EVERY
	// time, so /projects, the org projects tab, category and budget-line maps
	// all drew nothing. Production currently escapes it only because the
	// projects payload is ~14 MB and the map wins — i.e. it is timing, not
	// design, that keeps it working there.
	//
	// projectsMapInit() registers its load handler synchronously before any
	// fetch starts, so a missing 'route' source means load has not fired yet
	// and deferring to it is safe.
	if (!map.getSource('route')) {
		map.once('load', function () { projectsMapDrawFeatures(dd, do_fitbounds); });
		return;
	}

	var bounds = [[360, 180], [-360, -180]];
	//var colors_depr = ['#ecd078', '#d95b43', '#c02942', '#542437', '#53777a', '#f5ae33', '#99ac40', '#ff7c7c', '#78c0a8', '#7a6a53', '#6c5b7b', '#c06c84', '#d2ff0f', '#f2c45a', '#3b2d38', '#b8af03', '#d1e751', '#ff3a31', '#99b59a', '#676970', '#ecd078', '#618eff', '#7dffff', '#f07241', '#bcbcbc'];

	dd.forEach(function (el, i) {
		if (!el.properties)
			console.log('undefined props', el)
		bounds[0][0] = Math.min(bounds[0][0], el.properties.W - 0.01);
		bounds[0][1] = Math.min(bounds[0][1], el.properties.S - 0.01);
		bounds[1][0] = Math.max(bounds[1][0], el.properties.E + 0.01);
		bounds[1][1] = Math.max(bounds[1][1], el.properties.N + 0.01);
		//dd[i].properties.custom_color = colors[i % 25]
		dd[i].properties.custom_color = (dd[i].properties.custom_color ?? null) ? dd[i].properties.custom_color : '#53777a';
	});

	if (bounds[0][0] == 360)
		bounds = [[-74.05395, 40.68309], [-73.944433, 40.797808]]

	bounds[0][0] = Math.max(bounds[0][0], -74.275);
	bounds[0][1] = Math.max(bounds[0][1], 40.503);
	bounds[1][0] = Math.min(bounds[1][0], -73.690);
	bounds[1][1] = Math.min(bounds[1][1], 40.974);

	var src = map.getSource('route')
	src.setData({ "type": "FeatureCollection", "features": dd });
	if (popup)
		popup.remove();
	if (do_fitbounds)
		map.fitBounds(bounds, {
			padding: [50, 50],
			maxZoom: 18,
			duration: 1000,
			animate: true,
			essential: true,
		});
}


function fitBounds(bounds) {
	map.fitBounds(bounds);
}


/** the scoped capital map ***********************************************
 *
 * ⚠⚠ ONE OWNER, BECAUSE THERE WERE THREE BYTE-IDENTICAL COPIES AND ALL THREE
 * WERE DRAWING NOTHING. `budgetLineA`, `categoryA` and `orgprojectsection` each
 * held the same `drawProjects(pages)` reading `r['GEO_JSON']` out of their own
 * DataTable. Every one of those pages was migrated onto the capital spine, and
 * the spine carries no `GEO_JSON` column at all — so each map drew an empty
 * `route` source with a clean container, a loaded style and an empty console.
 *
 * Measured on the rendered pages, 2026-09-10, reading
 * `map.getSource('route')._data.features.length` rather than pixels:
 *
 *     /projects/categories/routine-reconstruction        table   447   map 0
 *     /projects/categories/neighborhood-parks-...        table 1,036   map 0
 *     /o/170010846-x/projects  (org capital tab)         table 2,798   map 0
 *     /projects/budget-lines/EP 0007                     table    60   map 0
 *
 * A row count, a status code and a JS-error check all pass on that. This is the
 * five-surfaces finding of 2026-09-09 arriving in a fourth organ: a tab is not
 * migrated when its TABLE is repointed.
 *
 * ⚠ THE FEATURES COME FROM `/get/capital/geojson`, SCOPED THE SAME WAY THE LIST
 * IS. Each page passes one scope (a budget line, a Ten-Year category, an org),
 * so the map and the table cannot answer one question two ways — the property
 * `/projects` had to be given by construction after `?has_location=false`
 * listed 12,464 projects while its map drew 4,560 the list had excluded.
 *
 * ⚠ The table's CLIENT-SIDE search still moves the map: the served features are
 * INTERSECTED with the ids the table is currently showing, never re-derived.
 */
var capMap = (function () {
	var url = null;
	var features = null;       // every located project in this scope
	var located = null;        // Set of ids the City publishes a location for
	var coverage = null;       // the endpoint's own denominator, served
	var mapReady = false;
	var pending = false;       // a draw was asked for before both were ready
	var fetching = false;

	function idOf(props) {
		props = props || {};
		return String((props.agency_key || '') + (props.fms_id || ''));
	}

	function init(geojsonUrl) {
		url = geojsonUrl || null;
	}

	// ⚠ Called from the view's mapbox `load` handler. `load` may already have
	// fired by the time a view binds, so each caller also checks `map.loaded()`;
	// mapbox no-ops a late `on('load')`.
	function ready() {
		mapReady = true;
		if (pending) { pending = false; draw('all'); }
	}

	function isLocated(id) {
		return !!(located && id && located.has(String(id)));
	}

	// ⚠⚠ THE OLD PAGES DID THIS IN `createdRow` FROM `data.GEO_JSON != ''`. On a
	// spine row that key is UNDEFINED and `undefined != ''` is TRUE, so every row
	// would be marked as located — including the 40 of 60 on EP 0007 the City
	// publishes no location for. It runs on the fetch AND on every draw, because
	// the two are a race.
	function markLocated() {
		if (!located || !jQuery.fn.dataTable.isDataTable('#myTable')) return;
		jQuery('#myTable').dataTable().api().rows().every(function () {
			var d = this.data();
			jQuery(this.node()).toggleClass('have_coords',
				isLocated(d && d.id));
		});
	}

	function visibleIds(pages) {
		var ids = new Set();
		if (!jQuery.fn.dataTable.isDataTable('#myTable')) return ids;
		jQuery('#myTable').dataTable().api()
			.rows('', {order: 'current', page: pages, search: 'applied'})
			.data().each(function (r) { if (r && r.id) ids.add(String(r.id)); });
		return ids;
	}

	function draw(pages) {
		// The map is hidden until the reader opens it; `toggleMap()` clears the
		// inline style, so an empty/absent style attribute means it is showing.
		if (jQuery('#map_container').attr('style')) return;
		// ⚠⚠ HOLD WHATEVER ARRIVES FIRST AND DRAW WHEN BOTH ARE READY. The `route`
		// source is added inside mapbox's `load` handler while the fetch fires
		// independently; when the DATA wins, `map.getSource('route')` is undefined,
		// `setData` throws inside the AJAX success handler and the map stays empty
		// for ever. Measured against a local API the data wins every time — the old
		// pages escaped it only on payload size, and papered over it with a
		// `setTimeout(..., 3000)`, which is a guess about the style load rather
		// than a synchronisation with it.
		if (features === null || !mapReady) {
			pending = true;
			fetch();
			return;
		}
		var ids = visibleIds(pages);
		var shown = features.filter(function (ft) {
			return ids.has(idOf(ft.properties));
		});
		projectsMapDrawFeatures(shown);
		window.CAP_MAP_FEATURES = shown.length;
	}

	// ⚠ Zoom to one project, looked up in the SERVED features by the same
	// agency-concatenated id the table renders — the spine row has no geometry on
	// it. A project with no published location zooms nowhere, which is the honest
	// answer rather than a jump to wherever the last click left the view.
	function zoomTo(id) {
		if (!features || !id) return;
		var want = String(id);
		for (var i = 0; i < features.length; i++) {
			if (idOf(features[i].properties) === want) {
				var pr = features[i].properties;
				fitBounds([[pr.W, pr.S], [pr.E, pr.N]]);
				return;
			}
		}
	}

	function fetch() {
		if (url === null || features !== null || fetching) return;
		fetching = true;
		jQuery.ajax({
			url: url,
			dataType: 'json',
			success: function (fc) {
				var ff = (fc && fc.features) ? fc.features : [];
				ff.forEach(function (ft) {
					var c = ft.geometry && ft.geometry.coordinates;
					if (!ft.properties) ft.properties = {};
					// `projectsMapDrawFeatures` fits the view from W/S/E/N; a
					// centroid is its own bounding box.
					if (c && c.length === 2) {
						ft.properties.W = ft.properties.E = parseFloat(c[0]);
						ft.properties.S = ft.properties.N = parseFloat(c[1]);
					}
				});
				features = ff;
				located = new Set(ff.map(function (ft) { return idOf(ft.properties); }));
				// ⚠ The note is the SERVED sentence, printed as it came: it carries
				// the denominator for the scope actually applied. A map with no
				// denominator reads as the whole capital programme when it is a
				// quarter of it, and the gap is not evenly spread — several agencies
				// publish no location at all.
				coverage = (fc && fc.coverage) ? fc.coverage : null;
				jQuery('#mapCoverageNote').text(coverage && coverage.note
					? coverage.note
					: 'Location coverage is not available right now.');
				window.CAP_MAP_COVERAGE = coverage;
				markLocated();
				if (pending) { pending = false; draw('all'); }
			},
			error: function () {
				// ⚠⚠ A FAILED REQUEST IS NOT AN EMPTY MAP. Saying nothing here draws
				// zero pins and reads as "no project in this scope has a location",
				// which is a claim about the City rather than about this page.
				features = [];
				located = new Set();
				jQuery('#mapCoverageNote').text('Project locations could not be '
					+ 'loaded. This is a problem with this page, not a statement '
					+ 'about the capital programme.');
				window.CAP_MAP_FEATURES = null;
			},
			complete: function () {
				fetching = false;
				window.CAP_MAP_DONE = true;
			}
		});
	}

	return {init: init, ready: ready, draw: draw, markLocated: markLocated,
			isLocated: isLocated, zoomTo: zoomTo,
			coverage: function () { return coverage; }};
})();


/** /projects map ******************************************/


/** share button ******************************************/

function copyLinkM(a, sel = "details-permalink") {
	var el = document.getElementById(sel);
	el.select();
	el.setSelectionRange(0, 99999);
	document.execCommand("copy");
	$(a).find('.share_icon_container').popover('show')
	setTimeout(function () {
		$(a).find('.share_icon_container').popover('hide')
	}, 3000);
	event.stopPropagation()
}

function copyLink() {
	var el = document.getElementById("details-permalink");
	el.select();
	el.setSelectionRange(0, 99999);
	document.execCommand("copy");
	$('.share_icon_container').popover('show')
	setTimeout(function () {
		$('.share_icon_container').popover('hide')
	}, 3000);
}

/** /share button ******************************************/

/** fapi requests ******************************************/
function fapireq(url, cb) {
	$.ajax({
		url: url,
		// ⚠⚠ THE API SERVES TWO PAYLOAD SHAPES AND THIS HANDLED ONE, so on the
		// other it called back a BARE ARRAY — where `resp.data` is `undefined`.
		// DataTables' own ajax callback then read `.length` off that undefined
		// and threw `Cannot read properties of undefined (reading 'length')`.
		// Measured 2026-09-10: **1 uncaught error on 5 of 5 org profiles**
		// tested, from `/get/orgs/section/{id}/nycjobs`, which returns a bare
		// `[]`. And it is not an edge case there — of that page's ~44 payloads,
		// 14 carry a `rows` key and ~30 are bare lists
		// (`/get/orgs/stats-reg/{id}/{tbl}` returns `[{"count":0}]`).
		//
		// ⚠⚠ AND THE ERROR BRANCH BELOW WAS ALREADY FIXED, with a comment
		// explaining that a failed request is not an empty result. So one branch
		// returned `{data: …}` and the other returned an array: the
		// fixed-one-branch pattern this repo records for `_cached` in
		// `nycha.py`, where two sibling routers had the same defect and one had
		// been treated.
		//
		// ⚠ A bare list is always DATA, never an error: FastAPI's own error
		// payload is `{"detail": …}`, a dict. And a non-JSON body arrives as a
		// string, which is neither shape and falls to `unexpected` below.
		//
		// ⚠ THREE STATES ARE KEPT, because they are three different claims —
		// the rule `schoolStatTiles` already relies on:
		//     {data: rows}              the request answered, with or without rows
		//     {data: [], unexpected}    it answered in a shape we do not read
		//     {data: [], error, status} we could not ask
		// Collapsing `unexpected` into a plain empty result would make "the
		// endpoint returned something we cannot read" indistinguishable from
		// "the query matched nothing", which is this repo's oldest defect.
		success: function (data) {
			if (data && data['rows'])
				cb({ 'data': data['rows'] })
			else if (Array.isArray(data))
				cb({ 'data': data })
			else
				cb({ 'data': [], 'unexpected': true })
		},
		error: function (jqXHR, textStatus, errorThrown) {
			// A FAILED REQUEST IS NOT AN EMPTY RESULT. Callers used to see only
			// an empty `data` and treat it as "this dataset has no records" --
			// the same defect as a search group that returns [] because its
			// query is broken. `status` is carried so a caller can tell a 429
			// (we throttled our own page) from a 500 from a genuine empty set.
			cb({ 'data': [], 'error': errorThrown || textStatus || 'request failed',
			     'status': jqXHR.status })
		}
	})
}
/** /fapi requests ******************************************/


/** school stat tiles ******************************************/

/**
 * Fill the six school stat tiles from a `/get/schools/sdstats/...` payload.
 *
 * ⚠⚠ `fapireq` HANDS BACK THREE DIFFERENT SHAPES AND ONLY ONE CARRIES A ROW.
 * On success it calls back `{data: rows}`; on a transport or HTTP failure
 * `{data: [], error, status}`; and on a payload it cannot read,
 * `{data: [], unexpected: true}`. Both callers used to read
 * `resp.data[0].schools_no` straight off, so two of those three shapes threw
 * `Cannot read properties of undefined (reading 'schools_no')` and took the
 * rest of the ready handler down with them. The endpoint returns exactly one
 * row when it succeeds (api/main.py `get_schools_global_stats`), so no row
 * means the request did not succeed -- never "this district has no schools".
 *
 * ⚠ CORRECTED 2026-09-10: the third shape used to be a BARE ARRAY, and this
 * comment described it as such. That was the source of an uncaught TypeError on
 * every org profile, because DataTables' own callback reads `.data.length`.
 * `fapireq` now always calls back an OBJECT, and it reads a bare list as data —
 * which is what `/get/orgs/*` actually serves for ~30 of an org profile's ~44
 * payloads. This function needed no change; it was already defensive.
 *
 * ⚠ A FAILED REQUEST IS NOT AN EMPTY DISTRICT. Six blank tiles are
 * indistinguishable from a district with nothing in it, which is this repo's
 * oldest defect. The tiles get an em dash and `noteId`, when the page
 * provides it, says which of the two happened -- `error`/`status` are set by
 * fapireq's error branch alone, so their presence is what separates "we could
 * not ask" from "it answered with nothing".
 *
 * Returns true when real figures were rendered.
 */
function schoolStatTiles(resp, noteId, tiles) {
	// ⚠⚠ THE TILE LISTS ARE A PARAMETER BECAUSE THE THIRD CONSUMER DOES NOT HAVE
	// THE SAME TILES, and hardcoding them is what made this function un-adoptable.
	// /schools and /d/{sd} share one set; the SCHOOL PROFILE (/s/{code}) has no
	// `schools_no` — it is one school — and does have `povetry_perc`, which is
	// neither a count nor money and takes no formatter at all.
	//
	// ⚠ The default reproduces the original two callers EXACTLY, so they did not
	// change. Forking this function for the third page is precisely how
	// distsection came to hold /schools' unguarded `resp.data[0]` read verbatim,
	// and then had to be fixed twice.
	//
	// ⚠ `povetry_perc` is passed through RAW on purpose: the endpoint serves
	// either a percentage or the literal string 'N/A' when no demographics row
	// exists (api/main.py `get_school_stats`), and 'N/A' is the publisher's own
	// answer — running it through a number formatter would turn a real answer
	// into NaN.
	var TILES = tiles || { count: ['schools_no', 'students_no', 'prj_no'],
	                       money: ['prj_budget', 'prj_costs', 'pcosts_per_student'] };
	var COUNT_TILES = TILES.count || [];
	var MONEY_TILES = TILES.money || [];
	var PLAIN_TILES = TILES.plain || [];
	var rows = (resp && resp.data) ? resp.data : null;
	var row = (rows && rows.length) ? rows[0] : null;
	var note = noteId ? document.getElementById(noteId) : null;

	if (!row) {
		COUNT_TILES.concat(MONEY_TILES).concat(PLAIN_TILES).forEach(function (id) {
			$('#' + id).text('\u2014');
		});
		if (note) {
			note.textContent = (resp && resp.error)
				? 'These figures could not be loaded (' +
				  (resp.status ? 'HTTP ' + resp.status : resp.error) +
				  '). That is a problem with this page, not a statement about the schools.'
				: 'These figures are not available right now.';
			note.style.display = '';
		}
		return false;
	}

	if (note) {
		note.textContent = '';
		note.style.display = 'none';
	}
	COUNT_TILES.forEach(function (id) { $('#' + id).text(commaThousands(row[id])); });
	MONEY_TILES.forEach(function (id) { $('#' + id).text(toFinShortK(row[id])); });
	PLAIN_TILES.forEach(function (id) {
		$('#' + id).text(row[id] != null ? row[id] : '\u2014');
	});
	return true;
}
/** /school stat tiles ******************************************/


/** slugged urls ******************************************/
function slug(n) {
	return n ? n.toString().toLowerCase().replace(/\s+/g, '-').replace(/[^-\w]/g, '') : ''
}
/** /fapi requests ******************************************/
