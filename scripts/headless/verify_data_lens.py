"""The data lens page renders readably, and never shows a combined total.

⚠⚠ THE DEFECT CLASS THIS EXISTS FOR IS SEMANTIC, NOT STRUCTURAL. The two halves
of this page OVERLAP — measured on prod, $23.2M of imagery is both data the City
buys and a row inside the GIS function total — so any figure that adds them is
wrong in a way a status code, a row count and a DOM check all pass. The API
serves no summed key (pinned in api/tests/test_data_lens.py); this asserts the
PAGE does not compute one either, by deriving the forbidden figure from the
served payload and looking for its rendered spellings.

⚠ Plus the three rules this repo has already paid for on a page of this shape:
a <p> inside .db-stat-grid becomes a GRID ITEM (186x110px instead of full width,
#400); a clipped element passes every geometry and DOM check (the Phase tile);
and one uncaught JS error per load is indistinguishable from noise unless
something asserts zero.
"""
import json
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8580"
API = "http://localhost:8581"
PATH = "/research/digital-reform/data"


def _money(v):
    """Every spelling this page could render a dollar figure in."""
    return {f"${v/1e6:,.1f}M", f"${v:,.0f}", f"${round(v):,}"}


def main():
    with urllib.request.urlopen(f"{API}/oce/licenses/data", timeout=60) as fh:
        d = json.load(fh)
    if not d.get("available"):
        print("FAIL: the endpoint is unavailable, so nothing below was tested")
        return 1
    content, tools = d["content"], d["tools"]
    # ⚠ THE FORBIDDEN FIGURE. Not a number anybody can act on: it counts imagery
    # bought as data alongside the licence to read it.
    banned = _money(content["value"] + tools["tool_value"])
    # ...and the same for the two halves' contract counts.
    banned_ctr = content["contracts"] + tools["tool_contracts"]

    ok = True
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--use-gl=swiftshader"])
        for w, h in ((1440, 900), (390, 844)):
            pg = b.new_page(viewport={"width": w, "height": h})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(BASE + PATH, wait_until="load", timeout=60000)
            pg.wait_for_timeout(1200)

            # ⚠⚠ LOWERCASED, because `innerText` returns text AS RENDERED and
            # `.db-stat-label` / `.db-table th` are `text-transform: uppercase`
            # site-wide. The first draft of this file scanned case-sensitively
            # and reported three of its own non-vacuity strings missing from a
            # page that plainly renders them. Same hole was live in
            # verify_retired_sweep.py's text arm; fixed there in the same change.
            body = pg.evaluate("document.body.innerText").lower()
            hit = sorted(s for s in banned if s.lower() in body)
            if hit:
                print(f"FAIL {w}px: the page renders the two halves ADDED: {hit}")
                ok = False
            if f"{banned_ctr:,} contracts" in body:
                print(f"FAIL {w}px: the page renders the summed contract count "
                      f"{banned_ctr:,}")
                ok = False

            if errs:
                print(f"FAIL {w}px: {len(errs)} uncaught JS: {errs[:2]}")
                ok = False

            sw = pg.evaluate("document.documentElement.scrollWidth")
            iw = pg.evaluate("window.innerWidth")
            if sw > iw:
                print(f"FAIL {w}px: page scrolls sideways, {sw} > {iw}")
                ok = False

            # ⚠ #400: a note or paragraph inside the stat grid becomes a grid item.
            strays = pg.evaluate("""() => {
                const out = [];
                document.querySelectorAll('.db-stat-grid').forEach(g => {
                    [...g.children].forEach(c => {
                        if (!c.classList.contains('db-stat')) {
                            const r = c.getBoundingClientRect();
                            out.push(c.tagName + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
                        }
                    });
                });
                return out; }""")
            if strays:
                print(f"FAIL {w}px: non-tile children inside .db-stat-grid: {strays}")
                ok = False

            # ⚠ Geometry proves an element is THERE; only this proves it is READABLE.
            # ⚠⚠ PER AXIS. The first version tested `overflowX + overflowY` as one
            # string, so a box that scrolls horizontally (overflow-x: auto) but
            # hides vertically still matched /hidden/ and was reported clipped —
            # flagging five CORRECTLY SCROLLING tables. A table wider than its
            # scroll box is not a defect; that is what the box is for. What IS a
            # defect is content overflowing an axis that is itself hidden, with
            # no way to reach it.
            clipped = pg.evaluate("""() => {
                const out = [];
                document.querySelectorAll('.inner_container *').forEach(el => {
                    const st = getComputedStyle(el);
                    const bad = [];
                    if (/hidden|clip/.test(st.overflowX) && el.scrollWidth > el.clientWidth + 1) {
                        bad.push('x ' + el.scrollWidth + '/' + el.clientWidth);
                    }
                    if (/hidden|clip/.test(st.overflowY) && el.scrollHeight > el.clientHeight + 1) {
                        bad.push('y ' + el.scrollHeight + '/' + el.clientHeight);
                    }
                    if (bad.length) {
                        out.push(el.tagName + '.' + String(el.className).split(' ')[0] +
                                 ' ' + bad.join(' '));
                    }
                });
                return out.slice(0, 5); }""")
            if clipped:
                print(f"FAIL {w}px: clipped elements: {clipped}")
                ok = False

            # Non-vacuity: a page that rendered nothing passes every check above.
            for needle in ("bought as a tool", "bought as data", "counted by both"):
                if needle not in body:
                    print(f"FAIL {w}px: the page does not render {needle!r} — "
                          f"it may have degraded to the unavailable state")
                    ok = False
            # ---- the agency table closes to the class total --------------------
            # ⚠⚠ READ FROM THE RENDERED TABLE, not from the payload. The payload
            # closing proves the ENDPOINT is right; only the rendered rows prove
            # the PAGE is. This table exists because the Overview's Data band
            # charted an agency breakdown this page could not show, and a table
            # that quietly dropped its tail would restore that seam invisibly.
            # ⚠⚠ READ THE DATATABLE, NOT THE DOM. These tables carry `db-dt`, so
            # the section's table standard pages them at 10 and the DOM holds ten
            # <tr> however many rows exist. My first version read the DOM and
            # reported a complete 29-row table as "truncated to 10" — a probe
            # measuring the pager, not the data.
            ag = pg.evaluate("""() => {
                const box = document.getElementById('content-agencies');
                if (!box) { return null; }
                const el = box.querySelector('table');
                const api = (window.jQuery && jQuery.fn.dataTable
                             && jQuery.fn.dataTable.isDataTable(el))
                    ? jQuery(el).DataTable() : null;
                const cells = api
                    ? api.column(3, {search: 'none'}).nodes().toArray()
                    : [...box.querySelectorAll('tbody tr td[data-order]')];
                return {
                    rows: cells.length,
                    paged: !!api,
                    sum: cells.reduce((a, td) => a + Number(td.getAttribute('data-order') || 0), 0)
                }; }""")
            served_rows = len(d["content"].get("by_agency") or [])
            served_val = float(d["content"].get("value") or 0)
            if not ag or not ag["rows"]:
                print(f"FAIL {w}px: the agency table is missing or empty")
                ok = False
            elif ag["rows"] != served_rows:
                print(f"FAIL {w}px: agency table shows {ag['rows']} rows, endpoint "
                      f"serves {served_rows} — the list is truncated")
                ok = False
            else:
                # ⚠ Per-row `(int)` truncates cents, so the tolerance is one dollar
                # per ROW — not a blanket epsilon that would hide a dropped agency.
                gap = abs(served_val - ag["sum"])
                if gap > ag["rows"]:
                    print(f"FAIL {w}px: agency table sums to {_money(ag['sum'])} "
                          f"against a class value of {_money(served_val)}")
                    ok = False
                else:
                    print(f"  {w}px: agency table {ag['rows']} rows, "
                          f"{_money(ag['sum'])} vs class {_money(served_val)} "
                          f"(gap ${gap:.2f}, within $1/row)")

            print(f"  {w}px: {len(body)} chars, 0 uncaught JS, scrollWidth {sw}")
        b.close()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
