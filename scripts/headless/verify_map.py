"""Headless verification of /projects — the map is READ AS GEOMETRY, never pixels.

⚠ The in-app browser pane does not composite, so Mapbox's `load` never fires
there and a working map reads as broken. This drives real headless Chromium with
software WebGL and asks the map object what it holds.
"""
import json, sys, urllib.request
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PWTimeout

BASE = "http://localhost:8580"
API = "http://localhost:8581"

CASES = [
    ("", None),
    ("?agency=DDC", None),
    ("?has_location=0", None),
    ("?borough=RICHMOND", None),
]

def served(qs):
    with urllib.request.urlopen(API + "/get/capital/geojson" + qs) as r:
        return json.load(r)

fails = []
with sync_playwright() as p:
    browser = p.chromium.launch(args=[
        "--enable-unsafe-swiftshader", "--use-gl=swiftshader",
        "--ignore-gpu-blocklist", "--enable-webgl",
    ])
    for qs, _ in CASES:
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []      # UNCAUGHT JS — a real fault in this page
        net404 = []      # failed sub-requests — reported, not conflated
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("response", lambda r: net404.append(r.url) if r.status >= 400 else None)
        page.goto(BASE + "/projects" + qs, wait_until="load", timeout=60000)

        # Wait for OUR callback to have run (set in `complete:`), not for pixels.
        page.wait_for_function("window.CAP_MAP_DONE === true", timeout=60000)
        # And for mapbox to have finished loading its style, so the source exists.
        #
        # ⚠⚠ `isStyleLoaded()` IS A TRANSIENT RUNTIME FLAG, NOT A PROPERTY, AND
        # ASSERTING A LATER SAMPLE OF IT MADE THIS VERIFIER FLAKY. Measured
        # 2026-09-11: a battery run reported `style loaded False` on `/projects`
        # and FAILED, while that same run's own output showed 4,560 features in
        # the mapbox source and **4,555 markers RENDERED** — so the map was
        # perfect and the probe was not. Three immediate re-runs were clean.
        # Changing the wait to `isStyleLoaded()` did NOT fix it (1 of 3 still
        # failed): mapbox returns to a not-fully-loaded state while it fetches
        # tiles and sprites, so the flag flips back to false AFTER the wait
        # succeeds.
        #
        # ⭐ So "did the style ever load" is answered by the WAIT — which raises
        # on timeout and is recorded below — and never by a second sample taken
        # at an arbitrary later instant. This is not a relaxation: a style that
        # genuinely never loads now fails DETERMINISTICALLY here, where before it
        # could pass whenever the sample happened to land on a `true`.
        style_reached_loaded = True
        try:
            page.wait_for_function(
                "typeof map !== 'undefined' && map.loaded && map.loaded() "
                "&& map.isStyleLoaded && map.isStyleLoaded()", timeout=60000)
        except PWTimeout:
            style_reached_loaded = False

        want = served(qs)
        want_mapped = want["coverage"]["mapped"]
        want_note = want["coverage"]["note"]

        got_features = page.evaluate("window.CAP_MAP_FEATURES")
        src = page.evaluate(
            "(() => { const s = map.getSource('route'); "
            "return s && s._data ? (s._data.features || []).length : null; })()")
        note = (page.inner_text("#mapCoverageNote") or "").strip()
        # ⚠⚠ RENDERED, not handed to the map. See verify_profile.py — a
        # collapsed container passes every source-level assertion.
        box = page.evaluate("(()=>{const r=document.getElementById('map_container')"
                            ".getBoundingClientRect();return [Math.round(r.width),Math.round(r.height)];})()")
        drawn = page.evaluate("map.queryRenderedFeatures({layers:['markers']}).length")
        legend_visible = page.evaluate(
            "!!document.querySelector('#mapLegend') && "
            "getComputedStyle(document.querySelector('#mapLegend')).display !== 'none'")
        style_loaded = page.evaluate("map.isStyleLoaded()")
        # Read one pin's colour off the paint expression the layer actually uses.
        colours = page.evaluate(
            "(() => { const s = map.getSource('route'); "
            "const f = (s && s._data && s._data.features) || []; "
            "return [...new Set(f.slice(0, 400).map(x => x.properties.custom_color))]; })()")

        tag = qs or "<none>"
        print(f"\n=== /projects{tag}")
        # ⚠ The second value is a TRANSIENT SAMPLE and is printed for information
        # only — see the note above. `False` beside 4,555 rendered markers means
        # mapbox was fetching tiles, not that anything is wrong.
        print(f"  style reached loaded  {style_reached_loaded} "
              f"(sample now: {style_loaded})")
        print(f"  served mapped ....... {want_mapped}")
        print(f"  page CAP_MAP_FEATURES {got_features}")
        print(f"  mapbox source count . {src}")
        print(f"  legend visible ...... {legend_visible}")
        print(f"  colours in sample ... {colours}")
        print(f"  container ........... {box[0]}x{box[1]}  RENDERED markers={drawn}")
        print(f"  note ................ {note[:120]}")
        if errors:
            print(f"  UNCAUGHT JS ......... {errors[:4]}")
        if net404:
            # ⚠ Reported, never failed on: these are the six
            # `/get/pstats-records_no/*` lookups in the datasets accordion, which
            # read the RETIRED series and 404 on every page carrying that
            # accordion. Pre-existing and shared; conflating them with a fault in
            # this page is how a real error would get lost in known noise.
            print(f"  sub-request >=400 ... {len(net404)} (pre-existing pstats 404s: "
                  f"{sum('pstats' in u for u in net404)})")

        if got_features != want_mapped:
            fails.append(f"{tag}: page drew {got_features}, endpoint served {want_mapped}")
        if src != want_mapped:
            fails.append(f"{tag}: mapbox source holds {src}, endpoint served {want_mapped}")
        if note != want_note.strip():
            fails.append(f"{tag}: rendered note is not the served note")
        if not style_reached_loaded:
            fails.append(f"{tag}: mapbox style never reached loaded within 60s")
        if box[0] < 200 or box[1] < 200:
            fails.append(f"{tag}: map container is {box[0]}x{box[1]} — collapsed, so "
                         f"the map is invisible however correct its data")
        if want_mapped and drawn < 1:
            fails.append(f"{tag}: source holds {src} features and the map renders NONE")
        if errors:
            fails.append(f"{tag}: uncaught JS {errors[:2]}")
        non_pstats = [u for u in net404 if 'pstats' not in u]
        if non_pstats:
            fails.append(f"{tag}: unexpected failed request {non_pstats[:2]}")
        page.close()
    browser.close()

print("\n" + ("FAIL\n" + "\n".join(fails) if fails else "ALL HEADLESS CHECKS PASSED"))
sys.exit(1 if fails else 0)
