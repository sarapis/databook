{{-- Section-wide layout glue for the Digital Services pages that share the
     band / pie / ranked-list components (the Overview and the Contracts page).
     ⚠ Emitted from @section('head'), i.e. BEFORE the stylesheet links, so every
     selector here must be a name databook-components.css does not carry. --}}
<style>
    /* A band = one submenu page, on its own horizontal strip. The rule doing the
       work is the top border: it separates the bands without adding a box around
       each, which would read as five cards rather than one page. */
    .ds-band { padding: var(--db-space-5) 0 var(--db-space-4); border-top: 1px solid var(--db-border); }
    .ds-band:first-of-type { border-top: 0; }
    .ds-band-head { display: flex; align-items: flex-start; justify-content: space-between;
                    gap: var(--db-space-3); flex-wrap: wrap; margin-bottom: var(--db-space-3); }
    .ds-band-title { margin: 0 0 var(--db-space-1); }
    .ds-band-lead { margin: 0; max-width: 62ch; color: var(--db-text-muted); }
    /* ⚠ The CTA must not stretch on a narrow screen: `flex-wrap` drops it onto its
       own line, and a 100%-wide button there reads as a form submit. */
    .ds-band-cta { flex: 0 0 auto; white-space: nowrap; }

    /* A ranked list where a pie would need more than five slices. Deliberately
       NOT a chart: 814 product families is far past the point where part-to-whole
       reads, and the largest is a third of the money on its own. */
    .ds-rank { display: flex; flex-direction: column; }
    .ds-rank-row { display: flex; align-items: baseline; justify-content: space-between;
                   gap: var(--db-space-2); padding: 7px var(--db-space-2);
                   border-top: 1px solid var(--db-border); color: inherit; text-decoration: none;
                   font-size: var(--db-text-sm); }
    .ds-rank-row:first-child { border-top: 0; }
    .ds-rank-row:hover { background: var(--db-navy-050, #f4f7fb); }
    .ds-rank-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    /* ⚠ The value is tabular so the column reads as a column, and it must not
       shrink -- a truncated money figure is a WRONG money figure, which this
       repo has already shipped once on a clipped stat tile. */
    .ds-rank-val { flex: 0 0 auto; font-variant-numeric: tabular-nums;
                   font-weight: var(--db-weight-semibold); }

    /* THE PIE'S LEGEND. Not a caption beside one: the canvas legend is off, so
       this list is the only legend each pie has, and it is also the drill-down.
       That is the whole point — the two used to render the same five labels
       twice, once as dead text in the canvas and once here as links. */
    .ds-seglinks { display: flex; flex-wrap: wrap; gap: 4px var(--db-space-3);
                   padding: var(--db-space-2) var(--db-space-2) 0;
                   font-size: var(--db-text-2xs); }
    .ds-seglinks span { color: var(--db-text-muted); }
    .ds-seglinks a, .ds-seglinks span { display: inline-flex; align-items: center; gap: 6px; }
    /* ⚠ The swatch is painted by JS from `DBChart.slice` — the SAME array the
       arcs read — so a legend key cannot drift from the wedge it names. A CSS
       colour list here would be a second owner of the palette. */
    .ds-sw { width: 10px; height: 10px; border-radius: 2px; flex: none;
             background: var(--sw, var(--db-gray-400)); }

    .ds-chart-note { margin: var(--db-space-2) 0 0; padding: 0 var(--db-space-2) var(--db-space-1);
                     font-size: var(--db-text-2xs); color: var(--db-text-muted); }
    /* Top-10 bar lists (agencies, vendors): every row a link, the full table one
       click away. HTML rather than canvas so each bar is focusable. */
    .ds-bar-row { display: grid; grid-template-columns: 1fr auto; gap: 2px var(--db-space-2);
                  padding: 6px var(--db-space-1); border-top: 1px solid var(--db-border);
                  color: inherit; text-decoration: none; font-size: var(--db-text-sm); }
    .ds-bar-row:first-child { border-top: 0; }
    .ds-bar-row:hover { background: var(--db-navy-050); }
    /* Wraps rather than ellipsing: an agency name cut to "DEPARTMENT OF INFORMATION TECHNOLO..."
       is a name the reader cannot use. */
    .ds-bar-name { overflow-wrap: anywhere; }
    .ds-bar-val { font-variant-numeric: tabular-nums; font-weight: var(--db-weight-semibold); }
    .ds-bar-track { grid-column: 1 / -1; height: 6px; background: var(--db-navy-050); border-radius: 3px; }
    .ds-bar-track i { display: block; height: 100%; background: var(--db-primary); border-radius: 3px; }
    /* Secondary notes, one click away: the first sentence of each section stays
       visible, the qualifications live here. */
    .lic-more { margin-top: var(--db-space-1); font-size: var(--db-text-sm); }
    .lic-more > summary { cursor: pointer; color: var(--db-text-muted); font-size: var(--db-text-2xs); }
</style>
