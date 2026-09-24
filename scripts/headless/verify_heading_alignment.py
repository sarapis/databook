"""No heading is centred by a row it ended up alone in.

⚠⚠ THE DEFECT THIS EXISTS FOR, reported by the owner 2026-09-10. On
`/projects/budget-lines/{code}` and `/projects/categories/{slug}` the "Projects"
heading sat in a `col-md-7` (resp. `col-md-8`) paired with the publication-date
control's `col-md-5` / `col-md-4` — a balanced 12 inside a
`justify-content-center` row. Gating that control off for the spine contract
left the heading column ALONE in the row, so bootstrap centred it: the heading
rendered **327px** and **268px** from the left while every other heading on
those pages sat at 35.

⚠ Invariant 19's shape at the LAYOUT layer — gating a block can change the thing
NEXT to it, not just remove the block.

⭐ THE RULE IS STRUCTURAL, NOT "ALL HEADINGS SHARE A LEFT EDGE". That blanket
version fails on correct pages: the project profile puts its TOC beside the
content and `/projects/capital` uses a grid, so headings legitimately sit at
386 and 849. What is never right is a column narrower than the full width,
alone in a row that centres its children.
"""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8580"
URLS = [
    "/projects",
    "/projects/capital",
    "/projects/types",
    "/projects/budget-lines",
    "/projects/budget-lines/WP-0170",
    "/projects/budget-lines/EP%200007",
    "/projects/categories/routine-reconstruction",
    "/projects/budget-lines/families/parks-and-recreation",
    "/p/850GKOH15-01",
    "/p/826HED-545",
]

PROBE = """() => {
  const out = [];
  const heads = document.querySelectorAll('.inner_container h1, .inner_container h2');
  for (const h of heads) {
    const text = (h.innerText || '').trim();
    if (!text) continue;
    const row = h.closest('.row');
    if (!row) continue;
    // Only rows that centre their children can strand a column.
    const cs = getComputedStyle(row);
    const centring = row.classList.contains('justify-content-center')
                     || cs.justifyContent === 'center';
    if (!centring) continue;
    const cols = [...row.children].filter(c => /(^|\\s)col(-|\\s|$)/.test(c.className));
    if (cols.length !== 1) continue;          // a balanced row is fine
    const col = cols[0];
    // A column that fills the row cannot be centred off-axis.
    const fills = Math.round(col.getBoundingClientRect().width)
                  >= Math.round(row.getBoundingClientRect().width) - 32;
    if (fills) continue;
    out.push({text: text.slice(0, 40), cls: col.className,
              left: Math.round(h.getBoundingClientRect().left),
              rowLeft: Math.round(row.getBoundingClientRect().left)});
  }
  return out;
}"""

ok = True
checked = 0
with sync_playwright() as p:
    b = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--use-gl=swiftshader"])
    for u in URLS:
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        try:
            pg.goto(BASE + u, wait_until="load", timeout=60000)
            pg.wait_for_timeout(1800)
            bad = pg.evaluate(PROBE)
            n = pg.evaluate("()=>document.querySelectorAll('.inner_container h1,"
                            ".inner_container h2').length")
            checked += n
            print(f"  {u:<56} {n:>2} headings, {len(bad)} stranded")
            for x in bad:
                print(f"      {x['text']!r} at {x['left']} (row starts {x['rowLeft']}) "
                      f"in {x['cls']!r}")
                ok = False
        except Exception as e:
            print(f"  {u:<56} ERROR {str(e)[:60]}")
            ok = False
        pg.close()
    b.close()

# ⚠⚠ NON-VACUITY. A probe that found no headings at all would report every page
# clean — this repo's oldest defect, and the reason every sweep here says how
# much it looked at.
if checked < 15:
    print(f"FAIL: only {checked} headings seen across {len(URLS)} pages — the probe "
          f"is not finding them, so 'no stranded headings' means nothing")
    ok = False
else:
    print(f"  {checked} headings checked across {len(URLS)} pages")

print("HEADING ALIGNMENT OK" if ok else "HEADING ALIGNMENT FAILED")
sys.exit(0 if ok else 1)
