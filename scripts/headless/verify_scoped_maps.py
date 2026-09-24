"""Every spine-backed capital map, verified from the SOURCE'S DATA.

⚠⚠ FOUR SURFACES DREW NOTHING, AND NOT ONE OF THEM LOOKED BROKEN. Each had its
project TABLE migrated onto the capital spine while its map went on building
features from `r['GEO_JSON']` off that table — a column the spine does not
serve. Measured on the rendered pages 2026-09-10, reading
`map.getSource('route')._data.features.length`:

    /o/{id}/projects  (org capital tab)          table 2,798   map 0
    /projects/categories/neighborhood-parks-...  table 1,036   map 0
    /projects/categories/routine-reconstruction  table   447   map 0
    /projects/budget-lines/EP 0007               table    60   map 0

Container sized, style loaded, console empty, table correct. A status code, a
row count and a JS-error check all pass on that state, which is why this reads
the source rather than any of them. Third organ in this repo to need the rule,
after the map on /projects and the Chart.js legend drawn into a canvas.

⚠⚠ AND THE SAME SWEEP FOUND THE CATEGORY PAGES FILTERED TO ONE AGENCY. An
ungated `columns([1])` plus an `option:last-child` auto-select — invariant 10,
the org capital tab's defect — meant a PARKS category page rendered *"Showing 1
to 1 of 1 (filtered from 367)"* and the one project was the Police
Department's. So `recordsDisplay` is asserted against `recordsTotal` here: a
`recordsTotal` check alone passes while 366 of 367 rows are hidden.
"""
from playwright.sync_api import sync_playwright
import json
import sys
import urllib.parse
import urllib.request

# (page path, the geojson query the page's scope should produce)
CASES = [
    ("/projects/budget-lines/" + urllib.parse.quote("EP 0007"),
     "budget_line=" + urllib.parse.quote("EP 0007")),
    ("/projects/categories/routine-reconstruction",
     "ten_year_category=routine-reconstruction"),
    ("/projects/categories/neighborhood-parks-playgrounds-and-ballfields",
     "ten_year_category=neighborhood-parks-playgrounds-and-ballfields"),
    # ⚠ A category whose name carries a COMMA — 12 of 138 do, and the old slug
    # rule could not match its own URL for those.
    ("/projects/categories/large-major-and-regional-park-reconstruction",
     "ten_year_category=large-major-and-regional-park-reconstruction"),
    ("/o/170010846-x/projects", "org=170010846"),
    # ⚠ An org with NO spine projects. Zero is a real answer and must not be a
    # blank, an error, or a leftover pin from the map's own initialisation —
    # this case read **1 feature** on an empty table before the fix.
    ("/o/170010998-x/projects", "org=170010998"),
]

ok = True
with sync_playwright() as p:
    b = p.chromium.launch(args=["--enable-unsafe-swiftshader",
                                "--use-gl=swiftshader"])
    for path, query in CASES:
        with urllib.request.urlopen(
                "http://localhost:8581/get/capital/geojson?" + query) as f:
            geo = json.load(f)
        cov = geo["coverage"]

        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8580" + path, wait_until="load", timeout=90000)
        pg.wait_for_timeout(5000)
        before = pg.evaluate("""() => {
          const api = jQuery.fn.dataTable.isDataTable('#myTable')
            ? jQuery('#myTable').DataTable() : null;
          const i = api ? api.page.info() : {};
          return {total: i.recordsTotal, display: i.recordsDisplay,
                  info: (document.querySelector('#myTable_info')||{}).innerText,
                  colSearch: api ? api.columns().search().toArray()
                     .map((s,k)=>s?k+':'+s:null).filter(Boolean) : null,
                  pubDateLabel: document.body.innerText
                     .includes('Project Publication Date')};
        }""")
        pg.evaluate("() => toggleMap()")
        pg.wait_for_timeout(9000)
        after = pg.evaluate("""() => {
          let feats = null;
          try { const s = map.getSource('route');
                feats = s && s._data ? (s._data.features||[]).length : 'no source'; }
          catch (e) { feats = 'threw ' + e.message; }
          const c = document.getElementById('map_container');
          const bb = c ? c.getBoundingClientRect() : null;
          return {feats,
                  note: ((document.getElementById('mapCoverageNote')||{}).innerText||'').trim(),
                  box: bb ? [Math.round(bb.width), Math.round(bb.height)] : null,
                  located: document.querySelectorAll('#myTable tbody tr.have_coords').length,
                  visible: document.querySelectorAll('#myTable tbody tr').length};
        }""")
        print(f"\n  {path}")
        print(f"    table {before['total']} total / {before['display']} shown"
              f"   |   map {after['feats']}   geojson mapped {cov['mapped']}"
              f" of {cov['matching_filters']}")
        print(f"    {before['info']}")
        print(f"    container {after['box']}  located rows {after['located']}"
              f"/{after['visible']}  note {'yes' if after['note'] else 'MISSING'}")

        # ⚠⚠ The one that catches the shipped defect. `recordsTotal` was right
        # on every page while the table showed 3 rows of 1,036.
        if before['total'] != before['display']:
            print(f"    FAIL {before['display']} of {before['total']} rows shown — "
                  f"a filter is cutting the table: {before['colSearch']}")
            ok = False
        # The map's own denominator must be the list's count.
        if cov['matching_filters'] != before['total']:
            print(f"    FAIL map denominator {cov['matching_filters']} != table "
                  f"{before['total']} — the two are scoped differently")
            ok = False
        if after['feats'] != cov['mapped']:
            print(f"    FAIL map drew {after['feats']}, geojson serves "
                  f"{cov['mapped']}")
            ok = False
        # ⚠ Geometry proves the element is THERE; `queryRenderedFeatures` still
        # returns features at zero width because mapbox falls back to a 400px
        # canvas, so the container's own box is the assertion that catches the
        # `float: right` defect.
        if after['box'] and (after['box'][0] < 200 or after['box'][1] < 200):
            print(f"    FAIL map container {after['box']} — the 0px-wide defect")
            ok = False
        if cov['mapped'] and not after['note']:
            print("    FAIL the map draws pins with no coverage sentence — a map "
                  "without its denominator reads as the whole programme")
            ok = False
        if after['located'] > cov['mapped']:
            print(f"    FAIL {after['located']} rows marked as located, only "
                  f"{cov['mapped']} have a published location")
            ok = False
        if before['pubDateLabel']:
            print("    FAIL a publication-date label renders on a spine contract")
            ok = False
        if errs:
            print(f"    FAIL uncaught JS {errs[:2]}")
            ok = False
        pg.close()
    b.close()
print("\nSCOPED MAPS OK" if ok else "\nSCOPED MAPS FAILED")
sys.exit(0 if ok else 1)
