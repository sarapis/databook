"""Headless verification of /p/{id} — the map read as GEOMETRY, never pixels."""
import json, sys, urllib.request
from playwright.sync_api import sync_playwright

BASE, API = "http://localhost:8580", "http://localhost:8581"
CASES = ["850GKOH15-01", "801P-2CPIHCR", "846P-407LBSF"]   # polygon, point, point

def served(i):
    with urllib.request.urlopen(f"{API}/get/capital/project/{i}/geometry") as r:
        return json.load(r)

fails = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--use-gl=swiftshader"])
    for pid in CASES:
        pg = b.new_page(viewport={"width": 1400, "height": 1100})
        errs, bad = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("response", lambda r: bad.append(r.url) if r.status >= 400 else None)
        pg.goto(f"{BASE}/p/{pid}", wait_until="load", timeout=60000)
        pg.wait_for_function("window.PRJ_MAP_DONE === true", timeout=60000)
        pg.wait_for_function("typeof map!=='undefined' && map.loaded && map.loaded()", timeout=60000)

        want = served(pid)
        n_want = len(want.get("features") or [])
        got = pg.evaluate("window.PRJ_MAP_FEATURES")
        src = pg.evaluate("(()=>{const s=map.getSource('route');"
                          "return s&&s._data?(s._data.features||[]).length:null;})()")
        gtype = pg.evaluate("(()=>{const s=map.getSource('route');"
                            "const f=(s&&s._data&&s._data.features)||[];"
                            "return f.length?f[0].geometry.type:null;})()")
        # ⚠ Read the map's own viewport, not a screenshot: after fitBounds the
        # centre must sit inside the served bbox, or the map is drawing the
        # geometry somewhere the project is not.
        centre = pg.evaluate("[map.getCenter().lng, map.getCenter().lat]")
        # ⚠⚠ WHAT THE MAP ACTUALLY DRAWS, NOT WHAT IT WAS HANDED. Reading
        # `getSource('route')._data` is reading the INPUT — the same class of
        # mistake this repo keeps recording in its guards, here in the
        # verification itself. `#map_container` carries `float: right` from an
        # id-keyed rule in style.css, so without a grid class it computed to
        # **0px wide**: the source held its feature, the map centred on the right
        # coordinates, every assertion passed, and nothing was on screen.
        box = pg.evaluate("(()=>{const r=document.getElementById('map_container')"
                          ".getBoundingClientRect();return [Math.round(r.width),Math.round(r.height)];})()")
        drawn = pg.evaluate("({markers: map.queryRenderedFeatures({layers:['markers']}).length,"
                            "  areas: map.queryRenderedFeatures({layers:['areas']}).length})")
        note = (pg.inner_text("#mapNote") or "").strip()
        bbox_ = want.get("bbox") or [None]*4

        inside = (bbox_[0] is not None
                  and bbox_[0]-0.05 <= centre[0] <= bbox_[2]+0.05
                  and bbox_[1]-0.05 <= centre[1] <= bbox_[3]+0.05)
        print(f"\n=== /p/{pid}  ({want.get('geom_kind')})")
        print(f"  served features {n_want} | page {got} | mapbox source {src} | type {gtype}")
        print(f"  bbox {[round(x,4) for x in bbox_]}  map centre {[round(c,4) for c in centre]}  inside={inside}")
        print(f"  container {box[0]}x{box[1]}  RENDERED markers={drawn['markers']} areas={drawn['areas']}")
        print(f"  note: {note[:90]}")
        if bad: print(f"  sub-request >=400: {len(bad)} (pstats {sum('pstats' in u for u in bad)})")
        if errs: print(f"  UNCAUGHT JS: {errs[:3]}")

        if got != n_want: fails.append(f"{pid}: page drew {got}, endpoint served {n_want}")
        if src != n_want: fails.append(f"{pid}: mapbox source holds {src}")
        if gtype != want["features"][0]["geometry"]["type"]:
            fails.append(f"{pid}: drew {gtype}, served {want['features'][0]['geometry']['type']}")
        if not inside: fails.append(f"{pid}: map centre {centre} is outside the served bbox {bbox_}")
        if box[0] < 200 or box[1] < 200:
            fails.append(f"{pid}: the map container is {box[0]}x{box[1]} — the map "
                         f"is drawn into a collapsed element and is invisible")
        want_layer = 'areas' if want.get('geom_kind') == 'polygon' else 'markers'
        if drawn[want_layer] < 1:
            fails.append(f"{pid}: the map renders NOTHING on layer '{want_layer}' "
                         f"though the source holds {src} feature(s)")
        if note != (want.get("note") or "").strip():
            fails.append(f"{pid}: rendered note is not the served note")
        if errs: fails.append(f"{pid}: uncaught JS {errs[:2]}")
        np = [u for u in bad if 'pstats' not in u]
        if np: fails.append(f"{pid}: unexpected failed request {np[:2]}")
        pg.close()
    b.close()

print("\n" + ("FAIL\n  " + "\n  ".join(fails) if fails else "ALL HEADLESS CHECKS PASSED"))
sys.exit(1 if fails else 0)
