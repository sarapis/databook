#!/usr/bin/env python3
"""The Products index, verified on the RENDERED page.

⚠⚠ WHY: the 2026-09-18 reframe made the Product families table the page's spine
and every other section a lens on it. Order, width and the fold are LAYOUT
properties -- a unit test pins the markup order and would not notice the table
outgrowing its card (it did, by 70px, and the open-source column scrolled off) or
the card head growing until the first row sat 500px under its heading.

Checks:
  1. section ORDER as rendered: families, then the four lenses, then the
     software-licences section, then method;
  2. THE TABLE FITS ITS CARD at 1440 -- every column inside the wrap, no
     sideways scroll inside the card;
  3. the families card starts above the fold at 1440x900;
  4. the Sellers count on row 1 equals the payload's merged reseller total for
     that family -- one owner, cross-checked against the API;
  5. the Kind, Function and Sellers columns are present, with the header and
     every row the same width;
  6. 0 uncaught JS, no sideways scroll at 1440 or 390.
"""
import argparse, json, sys, urllib.request
from playwright.sync_api import sync_playwright

ORDER = ["families", "classes", "functions", "routes", "agencies", "licenses",
         "spending", "open-source", "pipeline", "calendar", "method"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8580")
    ap.add_argument("--api", default="http://localhost:8581")
    a = ap.parse_args()
    with urllib.request.urlopen(a.api + "/oce/licenses", timeout=90) as r:
        payload = json.load(r)
    fams = payload.get("families") or []
    problems = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, h in ((1440, 900), (390, 844)):
            pg = b.new_page(viewport={"width": w, "height": h}); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(a.base + "/research/digital-reform/products", wait_until="networkidle", timeout=90000)
            if errs: problems.append(f"@{w}: uncaught JS {errs}")
            if pg.evaluate("document.documentElement.scrollWidth > window.innerWidth"):
                problems.append(f"@{w}: the page scrolls sideways")
            if w == 1440:
                tops = pg.evaluate("(ids) => ids.map(id => { const e = document.getElementById(id); "
                                   "return e ? Math.round(e.getBoundingClientRect().top + scrollY) : -1; })", ORDER)
                for i, (id_, y) in enumerate(zip(ORDER, tops)):
                    if y < 0: problems.append(f"#{id_} is missing")
                    elif i and y < tops[i-1]: problems.append(f"#{id_} ({y}) renders above #{ORDER[i-1]} ({tops[i-1]})")
                fold = pg.evaluate("window.innerHeight")
                if tops[0] > fold:
                    problems.append(f"the families card starts at {tops[0]}, below the {fold}px fold")
                fit = pg.evaluate("""() => { const t = document.getElementById('licFamilyTable');
                    const wrap = t.closest('.db-table-wrap'); return [t.scrollWidth, wrap.clientWidth]; }""")
                if fit[0] > fit[1] + 1:
                    problems.append(f"the family table is {fit[0]}px wide in a {fit[1]}px card -- the "
                                    f"open-source column scrolls off")
                cols = pg.evaluate("[...document.querySelectorAll('#licFamilyTable thead th')].map(e => e.innerText.trim().toLowerCase())")
                for need in ("kind", "function", "sellers"):
                    if need not in cols: problems.append(f"the family table lost its {need} column")
                widths = pg.evaluate("""() => [document.querySelectorAll('#licFamilyTable thead th').length,
                    ...[...document.querySelectorAll('#licFamilyTable tbody tr')].map(r => r.querySelectorAll('td').length)]""")
                if len(set(widths)) != 1:
                    problems.append(f"header/row cell counts differ: {sorted(set(widths))}")
                row1 = pg.evaluate("""() => { const r = document.querySelector('#licFamilyTable tbody tr');
                    const name = r.querySelector('td a').innerText.trim();
                    const idx = [...document.querySelectorAll('#licFamilyTable thead th')].findIndex(e => /sellers/i.test(e.innerText));
                    return [name, parseInt(r.querySelectorAll('td')[idx].innerText.replace(/,/g, ''), 10)]; }""")
                served = next((f.get("resellers", {}).get("total") for f in fams if f.get("key") == row1[0]), None)
                if served != row1[1]:
                    problems.append(f"row 1 ({row1[0]}) shows {row1[1]} sellers; the payload's merged total is {served}")
                print(f"  1440: families@{tops[0]} classes@{tops[1]} licenses@{tops[5]} method@{tops[10]}  "
                      f"table {fit[0]}/{fit[1]}  row1 sellers {row1[1]}=={served}")
            else:
                print(f"  390: height {pg.evaluate('document.documentElement.scrollHeight')}")
            pg.close()
        b.close()
    if problems:
        print("\nPROBLEMS:"); [print("  -", x) for x in problems]; return 1
    print("\nPRODUCTS INDEX OK"); return 0

if __name__ == "__main__":
    sys.exit(main())
