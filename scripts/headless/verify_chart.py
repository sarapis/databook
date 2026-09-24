"""The slippage chart, read as GEOMETRY — never pixels, never a screenshot.

⚠ Chart.js animates bars/lines up from zero via requestAnimationFrame, so in a
pane that never ticks rAF every height reads 0 forever and the data looks empty
when it is fine. Disable the animation and `update('none')` before measuring.
"""
from playwright.sync_api import sync_playwright
import sys, json, urllib.request
ok=True
with sync_playwright() as p:
    b=p.chromium.launch(args=["--enable-unsafe-swiftshader","--use-gl=swiftshader"])
    pg=b.new_page(viewport={"width":1400,"height":1000})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8580/p/850GKOH15-01", wait_until="load", timeout=60000)
    pg.wait_for_function("window.SLIP_CHART !== undefined", timeout=30000)
    r=pg.evaluate("""() => {
      const c=window.SLIP_CHART;
      c.options.animation=false; c.update('none');
      const m=c.getDatasetMeta(0);
      const body=document.querySelector('.db-chart-body').getBoundingClientRect();
      const cv=document.getElementById('slipChart').getBoundingClientRect();
      return {points:m.data.length, ys:m.data.map(e=>Math.round(e.y)),
              labels:c.data.labels, values:c.data.datasets[0].data,
              body:[Math.round(body.width),Math.round(body.height)],
              canvas:[Math.round(cv.width),Math.round(cv.height)],
              tip: c.options.plugins.tooltip.callbacks.label({dataIndex:0})};
    }""")
    with urllib.request.urlopen("http://localhost:8581/get/capital/project/850GKOH15-01") as f:
        served=json.load(f)["slippage"]
    print(f"  served points {len(served['points'])} | chart points {r['points']}")
    print(f"  values {r['values']}")
    print(f"  distinct y positions {len(set(r['ys']))} (a flat/undrawn chart collapses to 1)")
    print(f"  .db-chart-body {r['body']}  canvas {r['canvas']}")
    print(f"  tooltip[0]: {r['tip']}")
    if r['points'] != len(served['points']): print("  FAIL point count"); ok=False
    if r['values'] != [pt['months_later'] for pt in served['points']]: print("  FAIL values differ from payload"); ok=False
    if len(set(r['ys'])) < 2: print("  FAIL chart is flat/undrawn"); ok=False
    if r['canvas'][1] < 100 or r['canvas'][1] > 600: print(f"  FAIL canvas height {r['canvas'][1]} (unbounded growth = #61)"); ok=False
    # ⚠ ONE DATE FORMAT: the tooltip was the last place printing MM/DD/YYYY.
    import re
    if any(re.search(r'\d{2}/\d{2}/\d{4}', s) for s in r['tip']): print("  FAIL tooltip prints MM/DD/YYYY"); ok=False
    if errs: print(f"  FAIL uncaught JS {errs[:2]}"); ok=False
    b.close()
print("CHART OK" if ok else "CHART FAILED"); sys.exit(0 if ok else 1)
