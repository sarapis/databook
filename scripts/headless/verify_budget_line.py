"""`/projects/budget-lines/{code}`, verified on the RENDERED page AND the map's
SOURCE DATA.

⚠⚠ A 200 SAYS THE PAGE DID NOT CRASH. What this page did, measured 2026-09-10
before the migration, is return 200 with a clean console while publishing

    Showing 1 to 1 of 1 entries (filtered from 34 total entries)

under a tile reading **60 projects** — and drawing **0** map features. Three
stacked causes, none visible to a status code or a row count:

  * `capitalprojectsdollarscomp` holds 34 rows for **9** distinct projects on
    that line, one per publication vintage (`UTIUTIL` 14 times);
  * a publication-date control indexed on COLUMN 1 auto-selected the last of 15
    dates and cut those 34 to 1;
  * the map was built from `r['GEO_JSON']` on those rows — 7 features for 3
    projects before the date filter, 0 after — where the spine's own geometry
    covers **20 of the 60**.

⚠⚠ SO `recordsTotal` IS NOT ENOUGH. The 34 rows WERE loaded; one was shown. This
asserts `recordsDisplay` too, which is the number a reader sees.

⚠⚠ AND THE MAP IS READ FROM `map.getSource('route')._data`, NEVER FROM PIXELS.
Third organ in this repo to need that rule, after the map on /projects and the
Chart.js legend drawn into a canvas. The container's own bounding box is
asserted as well, because at zero width `queryRenderedFeatures` still returns
features — mapbox falls back to a 400px canvas.
"""
from playwright.sync_api import sync_playwright
import sys, json, urllib.request

CASES = [("EP 0007", 60), ("P I001", 1135), ("AG-D001", None)]
ok = True
with sync_playwright() as p:
    b = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--use-gl=swiftshader"])
    for code, want in CASES:
        q = urllib.parse.quote(code)
        with urllib.request.urlopen(
                "http://localhost:8581/get/capital/projects/by-budget-line/" + q) as f:
            served = json.load(f)
        with urllib.request.urlopen(
                "http://localhost:8581/get/capital/stats/budget_line/" + q) as f:
            stats = json.load(f)
        with urllib.request.urlopen(
                "http://localhost:8581/get/capital/geojson?budget_line="
                + urllib.parse.quote(code)) as f:
            geo = json.load(f)

        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8580/projects/budget-lines/" + q,
                wait_until="load", timeout=90000)
        pg.wait_for_timeout(5000)
        before = pg.evaluate("""() => {
          const api = jQuery.fn.dataTable.isDataTable('#myTable')
            ? jQuery('#myTable').DataTable() : null;
          const info = document.querySelector('#myTable_info');
          return {
            total: api ? api.page.info().recordsTotal : null,
            display: api ? api.page.info().recordsDisplay : null,
            info: info ? info.innerText.trim() : null,
            // ⚠ A control indexed on a column POSITION is what filtered this
            // table to 1 of 34. Assert none exists rather than trusting the gate.
            pubDateLabel: document.body.innerText.includes('Project Publication Date'),
            selects: [...document.querySelectorAll('select.filter')].map(
                       s => s.id + '=' + s.value),
            tiles: [...document.querySelectorAll('.db-stat')].map(
                     e => e.innerText.replace(/\\n/g, ' | ')),
          };
        }""")
        pg.evaluate("() => toggleMap()")
        pg.wait_for_timeout(9000)
        after = pg.evaluate("""() => {
          let feats = null;
          try {
            const s = map.getSource('route');
            feats = s && s._data ? (s._data.features || []).length : 'no source';
          } catch (e) { feats = 'threw ' + e.message; }
          const c = document.getElementById('map_container');
          const bb = c ? c.getBoundingClientRect() : null;
          return {feats, coverage: (document.getElementById('mapCoverageNote')||{}).innerText,
                  box: bb ? [Math.round(bb.width), Math.round(bb.height)] : null,
                  located: document.querySelectorAll('#myTable tbody tr.have_coords').length,
                  visibleRows: document.querySelectorAll('#myTable tbody tr').length,
                  hscroll: document.documentElement.scrollWidth > window.innerWidth};
        }""")
        print(f"\n  /projects/budget-lines/{code}")
        print(f"    endpoint {served['count']} | stats tile {stats.get('projects')} "
              f"| table total {before['total']} | displayed {before['display']}")
        print(f"    info line: {before['info']}")
        print(f"    map source features {after['feats']} | geojson mapped "
              f"{geo['coverage']['mapped']} of {geo['coverage']['matching_filters']}")
        print(f"    container {after['box']} | rows marked located {after['located']}")
        print(f"    coverage note: {(after['coverage'] or '')[:110]}")
        print(f"    selects: {before['selects']}  pubDateLabel: {before['pubDateLabel']}")
        print(f"    horizontal scroll: {after['hscroll']}  uncaught JS: {errs[:2]}")

        # --- the assertions ---
        if before['total'] != served['count']:
            print(f"    FAIL table total {before['total']} != endpoint {served['count']}"); ok = False
        # ⚠⚠ THE ONE THAT WOULD HAVE CAUGHT THE SHIPPED DEFECT: 34 rows were
        # loaded and 1 was shown. A recordsTotal check alone passes on that.
        if before['display'] != served['count']:
            print(f"    FAIL only {before['display']} of {served['count']} rows displayed "
                  f"— a filter is cutting the table"); ok = False
        if served['count'] != stats.get('projects'):
            print(f"    FAIL list {served['count']} != tiles {stats.get('projects')}"); ok = False
        if geo['coverage']['matching_filters'] != served['count']:
            print(f"    FAIL map denominator {geo['coverage']['matching_filters']} "
                  f"!= list {served['count']}"); ok = False
        if after['feats'] != geo['coverage']['mapped']:
            print(f"    FAIL map drew {after['feats']}, geojson has "
                  f"{geo['coverage']['mapped']}"); ok = False
        if after['located'] != min(after['visibleRows'], geo['coverage']['mapped']) and \
           after['located'] > geo['coverage']['mapped']:
            print(f"    FAIL {after['located']} rows marked located, only "
                  f"{geo['coverage']['mapped']} have a location"); ok = False
        if before['pubDateLabel']:
            print("    FAIL the publication-date label still renders"); ok = False
        if not (after['coverage'] or '').strip():
            print("    FAIL the map has no coverage sentence"); ok = False
        if after['box'] and (after['box'][0] < 200 or after['box'][1] < 200):
            print(f"    FAIL map container {after['box']} — the 0px-wide defect"); ok = False
        if after['hscroll']:
            print("    FAIL the page scrolls sideways"); ok = False
        if errs:
            print(f"    FAIL uncaught JS {errs[:2]}"); ok = False
        # the unit trap: spine is USD, the retired series was THOUSANDS
        for t in before['tiles']:
            if 'B' in t and '$' in t:
                pass
        if any('Amount Over Budget' in t for t in before['tiles']):
            print("    FAIL `Amount Over Budget` is back"); ok = False
        pg.close()
    b.close()
print("\nBUDGET LINE OK" if ok else "\nBUDGET LINE FAILED")
sys.exit(0 if ok else 1)
