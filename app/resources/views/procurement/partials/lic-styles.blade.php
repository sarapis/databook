{{-- The Products page's style glue, shared with the open-source alternatives
     page (moved off Products 2026-09-23). --}}
<style>
    /* Software Licenses (Renewal/license analysis) - page glue. */
    .db-page-lead { max-width: none; }
    .lic-note { background: var(--db-gray-050, #f8f9fb); border-left: 3px solid var(--db-brand, #d9730d);
                padding: var(--db-space-3); margin-bottom: var(--db-space-4); font-size: var(--db-text-sm); }
    .lic-bar-wrap { display: flex; align-items: center; gap: 8px; min-width: 120px; }
    .lic-bar { height: 8px; border-radius: 4px; background: var(--db-navy-500, #162E51); flex: 0 0 auto; }
    .lic-bar.is-accent { background: var(--db-brand, #d9730d); }
    .lic-num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
    .lic-sub { font-size: var(--db-text-2xs); color: var(--db-text-muted); }
    /* Notice-derived reseller marker (the "Bought through" column). The dagger
       lives HERE as an escaped code point: not in a PHP-block string (those are
       guarded entity-free in this view -- the mdash regression), and not as a
       raw non-ASCII char (these pages are ASCII-safe, #66). Writing the
       directive name itself in this comment compiles it -- Blade reads style
       blocks too. */
    .lic-notice-only::after { content: "\2020"; }
    .lic-prod { font-size: var(--db-text-2xs); color: var(--db-text-muted); display: block;
                max-width: 340px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .lic-section-head { display: flex; align-items: baseline; justify-content: space-between;
                        gap: var(--db-space-3); flex-wrap: wrap; margin-bottom: var(--db-space-2); }
    .lic-tag { font-size: var(--db-text-2xs); text-transform: uppercase; letter-spacing: var(--db-tracking-wide);
               color: var(--db-text-muted); }
    .lic-generic { color: var(--db-text-muted); font-style: italic; }
    /* One class per heading instead of ten copies of the same inline style. */
    .lic-h2 { font-size: var(--db-text-lg); margin: 0; }
    /* One line per family description (owner, 2026-09-18); the full text is the title and the family page. */
    .lic-clamp { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 260px; }
    .lic-caveat { font-size: var(--db-text-2xs); color: var(--db-text-muted); border-left: 2px solid var(--db-border);
                  padding-left: var(--db-space-2); margin: var(--db-space-1) 0 var(--db-space-2); }
    .lic-rule { margin-top: var(--db-space-2); padding-top: var(--db-space-2); border-top: 1px solid var(--db-border); }
    /* Jump navigation. ~10 sections over 15,000px had no way to move between
       them except scrolling. */
    .lic-jump { display: flex; flex-wrap: wrap; gap: var(--db-space-1);
                margin: var(--db-space-3) 0 var(--db-space-4); }
    /* The one visual anchor on an all-tables page: the class mix as a single bar. */
    .lic-mix { display: flex; width: 100%; height: 26px; border-radius: 4px; overflow: hidden;
               margin-bottom: var(--db-space-2); }
    .lic-mix-seg { height: 100%; min-width: 2px; }
    .lic-mix-key { display: flex; flex-wrap: wrap; gap: var(--db-space-3); font-size: var(--db-text-2xs); }
    .lic-mix-key span { display: inline-flex; align-items: center; gap: 5px; }
    .lic-swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
    .lic-legacy { font-size: var(--db-text-2xs); }
    /* Awarded beside paid. Two columns on desktop, stacked below 992px — the
       comparison is the point, so they must not end up one above the fold and one
       below it on a normal screen. */
    .lic-two-charts { display: grid; grid-template-columns: 1fr 1fr;
                      gap: var(--db-space-4); padding: var(--db-space-3); }
    @media (max-width: 991px) { .lic-two-charts { grid-template-columns: 1fr; } }
    /* ⚠ The component default is `overflow: hidden`, and it only becomes
       scrollable under the 768px breakpoint -- so a wide table is CLIPPED on a
       desktop, not scrolled. These run to 8 columns, so they opt into scrolling
       at every width; the page itself then never scrolls sideways. */
    .db-table-wrap { overflow-x: auto; }
    @media (max-width: 575px) {
        .lic-prod { max-width: 200px; }
        .lic-jump .db-btn { font-size: var(--db-text-2xs); }
    }
</style>
