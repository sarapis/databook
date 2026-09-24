# Headless verifiers — the capital section

These were written across 2026-09-06..09 and lived in a **session scratchpad**,
which is discarded when the session ends. They are here so they survive.

## ⚠⚠ Why these exist at all, and not just the pytest suite

The pytest guards read SOURCE. Every one of these reads the **rendered page**,
and each was written because something passed the suite while being visibly
wrong:

| verifier | the defect no unit guard could see |
|---|---|
| `verify_profile.py` | the map drawn into a **0px-wide** element — the source held its feature, the map centred correctly, and `queryRenderedFeatures` still returned markers, because mapbox falls back to a 400px canvas. **Assert the container's own bounding box.** |
| `verify_overflow.py` | a **clipped** stat tile (`Construction Procurement` → "Constructio / Procuremer", `$105.7M` cut by 4px). The element existed, was the right size, held the right text. Overflow is invisible to every DOM assertion. |
| `verify_migration.py` | rows RENDERED and then **deleted** by a callback that treated a count of 0 as failure. A row count taken too early passes. |
| `verify_chart.py` | Chart.js animates from zero via rAF; in a pane that never ticks rAF every bar reads 0 for ever. **Disable the animation and `update('none')` first.** |
| `verify_category.py` | the table populated from the **retired series** while the page returned 200 with a correct heading. |
| `verify_profile_links.py` | every link the profile emits, followed. Five budget-line links were serving **500** under a page that looked fine. |
| `verify_toc.py` | a TOC entry pointing at a section the page hides. |
| `verify_v3.py` | page height, heading levels, `<th scope>`, date formats, touch targets, horizontal scroll. |
| `verify_provenance.py` | both provenance modes, and that folding a table into an accordion did not take a load-bearing caveat behind a click. |
| `verify_stat_sitewide.py` | a change to a SHARED component, checked on its OTHER consumers. |
| `verify_type.py` / `verify_family.py` / `verify_bl_index.py` | the facet pages' rows, units and gated links. |
| `verify_retired_sweep.py` | every live capital URL at once, for a retired-series figure: the `Amount Over Budget` label in the page TEXT **and in every Chart.js SERIES LABEL**, plus blank `prj_stat` tiles and uncaught JS. ⚠⚠ **The text scan alone missed a surface** — Chart.js draws its legend into the canvas, so the org profile plotted `Amount Over Budget` over 14 publication dates while `document.body.innerText` read clean. A blank tile is the other half: eight of them sat under real labels on the org capital tab because the loop that filled them had lost its only caller. |
| `verify_home_capital.py` | the front page's capital card after the Phase 4 repoint: the figures are the spine's and not the retired series' (5,128 and 12,929 are both plausible in a 3-slot card), the **thousands multiplier** is gone (it would render $201.6B as $201.6T), **nothing is clipped**, and — the one it exists for — the OTHER cards still hydrate, since the three removed tiles' `finStatUrls` entries went with them and one `loadTableStat` throw blanks every remaining tile. |
| `verify_schools_page.py` | the `/schools` map's **style-vs-data race**, forced rather than waited for: `--style-delay` holds the style response back so the data always lands first — the order that fails. Waiting to see what happens naturally makes the run non-deterministic, which is how a race passes CI and breaks for a reader. ⚠⚠ **This one defaults to PROD**, unlike every other script here; pass `--url` or you measure the deployed site instead of your change. ⚠ And run locally it FAILS on `queryRenderedFeatures > 0` for a DATA reason — `/get/schools/geojson` is empty on a local stack (prod: 2,184 features). Read the other six assertions there. |

## Running them

The local stack must be up (`app` on :8580, `api` on :8581) and **`app` rebuilt
with the local override**, or `FAPI_PUBLIC_ENTRY` is unset and every page asks
`api.staging.databook.nyc` — a host retired in July:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build app
docker compose exec -T app php artisan config:clear && docker compose exec -T app php artisan view:clear
python3 scripts/headless/verify_v3.py          # any of them; each exits non-zero on failure
```

⚠ Chromium needs `--enable-unsafe-swiftshader --use-gl=swiftshader` for Mapbox;
each script already passes them.

⚠ `verify_migration.py` keeps a `KNOWN` tuple for naming PRE-EXISTING errors it
must not fail on, so a NEW one still fails. **It is currently EMPTY, and that is
the finished state** — the three `/schools` errors it used to carry were fixed
and retired from it on 2026-09-12, and `/schools` now throws zero uncaught
errors.
⚠⚠ The line this replaced cited **task `be26fcdf`**, and **that id does not
exist** — verified with `get_task` on 2026-09-14. `CONTINUE-CAPITAL.md` already
records it as one of three ids cited by earlier handoffs that resolve to
nothing, with the rule *"check a task id resolves before repeating it"*. ⚠ My
own first draft of THIS correction carried the dead id forward, because I copied
the citation while fixing the sentence around it — which is the same defect one
layer down, and the reason the id is now simply gone rather than re-cited. The empty tuple is kept rather than the mechanism deleted:
the next pre-existing error wants NAMING here, with its reason, which is exactly
what let this one be retired instead of forgotten.
⚠ Read the comment above `KNOWN` before adding to it — the ORDER mattered once.
Emptying it while the fix and the mute still lived on different branches would
have un-muted errors that were genuinely real on one of them.

⚠ These are ad-hoc scripts, not a test suite: they hardcode localhost and a
handful of representative ids. Treat them as instruments, not as CI.
