#!/usr/bin/env python3
"""
Does /schools actually work in a browser? Headless, geometry-based.

WHY THIS EXISTS
---------------
On 2026-09-09 /schools threw THREE uncaught JS errors on every single load,
and had done for a long time:

    Cannot read properties of undefined (reading 'schools_no')
    Cannot read properties of undefined (reading 'setData')
    Bloodhound is not defined

None of them 500s the page, none reaches Sentry (they are client-side), and
prod-smoke only asserts HTTP 200 — so the page looked healthy from every angle
we had while its map was permanently empty and its address search dead. An
uncaught error also aborts the rest of the handler it fires in, so each one
silently took whatever followed it down too.

⚠⚠ READ GEOMETRY, NEVER PIXELS, AND ASSERT BOTH HALVES.
`map.queryRenderedFeatures` alone is NOT enough: mapbox falls back to a 400px
canvas when its container element has no size, so a map collapsed to 0px wide
still returns every feature and the check stays green on an invisible map.
Measured here: with `#map_container` forced to width 0, `rendered` was still
40. So the container's bounding box is asserted separately, at >= 200x200.
Screenshots settle nothing either — the in-app browser cannot composite
Mapbox, so the map reads as "broken" there with no cause.

⚠ THE RACE IS FORCED, NOT HOPED FOR. `projectsMapInit()` adds the `route`
source inside mapbox's `load` event, while the DataTable's `draw` handler
calls `projectsMapDrawFeatures`, which does `map.getSource('route').setData`.
Whichever lands first wins, so waiting to see what happens naturally makes the
run non-deterministic. `--style-delay` holds the style response back, which
puts the data first every time — the order that fails.

USAGE
-----
    python3 scripts/headless/verify_schools_page.py                  # against PROD
    python3 scripts/headless/verify_schools_page.py --url http://localhost:8580/schools
    python3 scripts/headless/verify_schools_page.py --style-delay 3000   # force the race

⚠⚠ IT DEFAULTS TO PROD (`https://databook.nyc/schools`), UNLIKE EVERY SIBLING IN
THIS DIRECTORY, WHICH DEFAULT TO localhost. Running it with no `--url` while
working on a local tree measures the DEPLOYED site, not your change — that has
already produced one false "the fix is broken" reading. Pass `--url` when you
mean local. The default is kept because this verifier's whole subject is a
network race, which prod's real latency exercises and a local stack does not.

⚠ AND THE INVERSE TRAP: run it `--url http://localhost:8580/schools` and it FAILS
on `queryRenderedFeatures(markers) > 0 (got 0)` — not because anything is broken,
but because `/get/schools/geojson` serves `{"rows":[]}` on a local stack. Measured
2026-09-14: byte-identical PASS/FAIL lines on an unchanged tree and a changed one,
and the same script against prod is `RESULT: PASS` with **2,184** rendered
features. Locally, read the other six assertions and ignore that one.

⚠ `--offline-assets DIR` exists for sandboxes whose egress policy denies the
CDNs this page loads (jquery, DataTables, bootstrap, mapbox-gl, typeahead).
It serves each library from `DIR/node_modules` at the version the page pins
and stubs the mapbox style, so the page, its libraries and script.js are the
real ones and only the transport is local:

    npm --prefix DIR install jquery@3.5.1 mapbox-gl@2.4.1 \
        datatables.net@1.10.23 datatables.net-buttons@1.6.5 \
        bootstrap@5.3.3 corejs-typeahead@1.3.4

⚠ Needs `pip install playwright`. Point --chrome at an existing chromium if
the pip playwright and the installed browser build disagree.
"""
import argparse, asyncio, json, pathlib, sys

DEFAULT_URL = "https://databook.nyc/schools"

# CDN url fragment -> (path under node_modules, content type). Versions match
# what layout.blade.php and schools.blade.php pin; a mismatch here would test a
# different page from the one that ships.
ASSETS = {
    "mapbox-gl-js/v2.4.1/mapbox-gl.js": ("mapbox-gl/dist/mapbox-gl.js", "application/javascript"),
    "mapbox-gl-js/v2.4.1/mapbox-gl.css": ("mapbox-gl/dist/mapbox-gl.css", "text/css"),
    "jquery-3.5.1.js": ("jquery/dist/jquery.js", "application/javascript"),
    "datatables.min.js": ("datatables.net/js/jquery.dataTables.js", "application/javascript"),
    "jquery.dataTables.min.js": ("datatables.net/js/jquery.dataTables.js", "application/javascript"),
    "dataTables.buttons.min.js": ("datatables.net-buttons/js/dataTables.buttons.js", "application/javascript"),
    "buttons.colVis.min.js": ("datatables.net-buttons/js/buttons.colVis.js", "application/javascript"),
    "bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js": ("bootstrap/dist/js/bootstrap.bundle.min.js", "application/javascript"),
    "bootstrap@5.3.3/dist/css/bootstrap.min.css": ("bootstrap/dist/css/bootstrap.min.css", "text/css"),
    "typeahead.bundle.js": ("corejs-typeahead/dist/typeahead.bundle.js", "application/javascript"),
}
# No remote dependencies, so `load` fires without reaching api.mapbox.com. It
# still fires only once parsed, which is the event the source hangs off.
STUB_STYLE = {"version": 8, "name": "stub", "sources": {},
              "layers": [{"id": "bg", "type": "background",
                          "paint": {"background-color": "#e8e8e8"}}]}

PROBE = """() => {
    const out = {};
    const c = document.querySelector('#map_container');
    const r = c ? c.getBoundingClientRect() : null;
    out.container = r ? {w: Math.round(r.width), h: Math.round(r.height)} : null;
    try {
        const m = (typeof map !== 'undefined') ? map : null;
        out.map_loaded = !!m && m.loaded();
        const src = m ? m.getSource('route') : null;
        out.has_source = !!src;
        out.rendered = m ? m.queryRenderedFeatures({layers: ['markers']}).length : null;
    } catch (e) { out.map_error = String(e); }
    out.bloodhound = (typeof Bloodhound !== 'undefined');
    out.typeahead_wired = !!document.querySelector('.twitter-typeahead #addrSearch');
    out.stat_tiles = {};
    ['schools_no','students_no','prj_no','prj_budget','prj_costs',
     'pcosts_per_student'].forEach(function (id) {
        const el = document.getElementById(id);
        out.stat_tiles[id] = el ? el.textContent.trim() : null;
    });
    const note = document.getElementById('schoolStatsNote');
    out.stats_note = note ? note.textContent.trim() : null;
    out.table_rows = document.querySelectorAll('#myTable tbody tr').length;
    return out;
}"""


async def run(args, style_delay_ms):
    from playwright.async_api import async_playwright
    errors = []
    nm = pathlib.Path(args.offline_assets).resolve() / "node_modules" if args.offline_assets else None

    async with async_playwright() as pw:
        launch = {"args": ["--no-sandbox"]}
        if args.chrome:
            launch["executable_path"] = args.chrome
        browser = await pw.chromium.launch(**launch)
        page = await (await browser.new_context(
            viewport={"width": 1400, "height": 1000})).new_page()
        page.on("pageerror", lambda e: errors.append(str(e).split("\n")[0]))

        if nm or style_delay_ms:
            async def handler(route):
                url = route.request.url
                if nm:
                    for key, (rel, ctype) in ASSETS.items():
                        if key in url:
                            return await route.fulfill(status=200, content_type=ctype,
                                                       body=(nm / rel).read_bytes())
                if "api.mapbox.com/styles/" in url:
                    if style_delay_ms:
                        await asyncio.sleep(style_delay_ms / 1000.0)
                    if nm:
                        return await route.fulfill(status=200,
                                                   content_type="application/json",
                                                   body=json.dumps(STUB_STYLE))
                if nm:
                    # Tiles, fonts, analytics: not part of what is under test,
                    # and unreachable in the sandbox this mode exists for.
                    if "mapbox.com" in url or "fonts.g" in url or "googletagmanager" in url:
                        return await route.fulfill(status=204, body="")
                return await route.fallback()
            await page.route("**/*", handler)

        await page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        if args.zero_width:
            await page.add_style_tag(content="#map_container{width:0!important;}")
        await page.wait_for_timeout(args.settle + style_delay_ms)
        probe = await page.evaluate(PROBE)
        await browser.close()

    checks, ok = [], True
    def check(cond, text):
        nonlocal ok
        checks.append(("PASS" if cond else "FAIL", text))
        ok = ok and bool(cond)

    box = probe.get("container") or {}
    tiles = probe.get("stat_tiles") or {}
    # A blank tile is the failure mode this page shipped with: a broken stats
    # request is indistinguishable from a city with no schools. Populated, or
    # explained -- never silently empty.
    blank = [k for k, v in tiles.items() if not v]
    explained = bool(probe.get("stats_note"))

    check(not errors, "no uncaught page errors (got %d)" % len(errors))
    check(box.get("w", 0) >= 200 and box.get("h", 0) >= 200,
          "#map_container >= 200x200 (got %sx%s)" % (box.get("w"), box.get("h")))
    check(bool(probe.get("has_source")), "map source 'route' exists")
    check((probe.get("rendered") or 0) > 0,
          "queryRenderedFeatures(markers) > 0 (got %s)" % probe.get("rendered"))
    check(bool(probe.get("bloodhound")), "Bloodhound is defined")
    check(bool(probe.get("typeahead_wired")), "#addrSearch is typeahead-wired")
    check(not blank or explained,
          "stat tiles populated, or the note says why (blank: %s)" % (blank or "none"))

    print("\n=== %s | style delayed %dms | assets %s ===" % (
        args.url, style_delay_ms, "local" if nm else "network"))
    print(json.dumps({"page_errors": errors, **probe}, indent=2))
    for status, text in checks:
        print("  %s  %s" % (status, text))
    return ok


async def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--style-delay", type=int, default=3000, dest="style_delay",
                   help="ms to hold back the mapbox style, forcing the data to "
                        "win the race (0 runs only the natural order)")
    p.add_argument("--settle", type=int, default=9000,
                   help="ms to wait after load for the fetches to land")
    p.add_argument("--offline-assets", metavar="DIR", default=None,
                   help="serve the pinned libraries from DIR/node_modules")
    p.add_argument("--chrome", default=None, help="path to a chromium binary")
    p.add_argument("--zero-width", action="store_true",
                   help="collapse #map_container to 0px, to prove the geometry "
                        "assertion is load-bearing (features still render)")
    args = p.parse_args()

    results = [await run(args, args.style_delay)]
    if args.style_delay:
        # Both orders, because a fix that only works when the data is late is
        # not a fix.
        results.append(await run(args, 0))
    ok = all(results)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1

sys.exit(asyncio.run(main()))
