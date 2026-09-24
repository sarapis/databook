/* =============================================================================
   db-tables.js — the Digital Services section's table standard, in one place.

   Opt in by putting `db-dt` on a <table>. Every such table gets:
     · 10 rows a page, with pagination once there are more than 10
     · click-to-sort on every column
     · the order the SERVER chose as the initial order (`order: []`)

   ⚠⚠ WHY THE MONEY SORT IS PARSED HERE RATHER THAN KEYED IN THE MARKUP.
   The section renders money two ways, and they do not sort alike — measured in
   a live page by building tables and reading DataTables' own detected type:

       $573,752,896   -> `num-fmt`  -> sorts correctly, needs nothing
       $10.0M         -> `string`   -> sorts $1.2B, $10.0M, $357.8M, $4.1M, $900K

   The abbreviated form is not monotonic in its value, so it needs a sort key.
   16 tables in this section carry it with NO `data-order` at all, including the
   408-row vendor table and a column where `$587K` sits beside `$574.6M`.

   The obvious fix is to emit `data-order` from the formatter — except `$fmtM` is
   defined FIVE times, once per view, 41 call sites. Adding the key at source
   means changing five copies of one rule and hoping the sixth is never written.
   Parsing the RENDERED TEXT has one owner, covers every table present and
   future, and cannot drift from a formatter it never reads.

   ⚠ Where `data-order` already exists DataTables uses it and ignores the text,
   so the two coexist and the server's key still wins. Nothing here overrides a
   key that was deliberately set.
   ============================================================================= */
// ⚠ ONE OWNER FOR THE PAGE SIZE. The Product families table keeps a bespoke
// init (it owns the `licFragOnly` filter, which needs the instance), so it reads
// this rather than typing 10 again -- two copies is how 25/25/25 drifted.
//
// ⚠⚠ HALVED ON A PHONE, AND THE REASON IS MEASURED. Every row on these tables
// wraps to several lines at 390px, so ten of them is most of the page's height:
// the product family page measured 13,677px at 390 against 7,834 at 1440, and
// four paginated tables were nearly all of the difference. Five rows a page is
// the same table with a pager that costs one more tap -- and a pager is cheaper
// than a scroll a reader cannot see the end of.
// ⚠ READ ONCE, AT LOAD, not on resize: DataTables fixes pageLength at init, so a
// value that changed with the viewport would leave a rotated phone showing a
// length its pager disagrees with. A reload applies the new one.
// ⚠ 768 is Bootstrap's own md breakpoint, the same one the layout's `col-md-*`
// and `d-none d-md-block` use, so the table and the sidebar change together.
window.DB_TABLE_PAGE = (window.matchMedia && window.matchMedia('(max-width: 767.98px)').matches) ? 5 : 10;

(function () {
    if (!window.jQuery || !jQuery.fn || !jQuery.fn.DataTable) { return; }
    var $ = jQuery;

    // $1.04B · $593.4M · $587K · $2,847.5M · 12.3% · 1,205 · $0 · — · (blank)
    var NUMISH = /^\s*[-+]?\$?\s*[\d,]+(?:\.\d+)?\s*(?:[KMB]|%)?\s*$/i;
    var MULT = { k: 1e3, m: 1e6, b: 1e9 };

    function parseNum(raw) {
        if (raw === null || raw === undefined) { return null; }
        var s = String(raw).replace(/<[^>]*>/g, '').trim();
        if (!s || !NUMISH.test(s)) { return null; }
        var suffix = s.slice(-1).toLowerCase();
        var mult = MULT[suffix] || 1;
        var n = parseFloat(s.replace(/[^0-9.\-+]/g, ''));
        return isNaN(n) ? null : n * mult;
    }

    // A column is ours only if EVERY non-empty cell parses AND at least one
    // carries a suffix or a currency mark — otherwise leave DataTables' own
    // `num`/`num-fmt`/`string` detection alone. ⚠ Claiming a plain-integer
    // column would change nothing but would hide which mechanism is sorting it.
    $.fn.dataTable.ext.type.detect.unshift(function (d) {
        if (d === null || d === undefined) { return null; }
        var s = String(d).trim();
        if (s === '' || s === '—' || s === '-') { return 'db-money'; }
        if (!NUMISH.test(s)) { return null; }
        return /[KMB%$]/i.test(s) ? 'db-money' : null;
    });

    // ⚠ An unparseable or empty cell sorts LAST in both directions rather than
    // as zero: "not published" is not "$0", and this repo has shipped a rendered
    // $0 that was a claim the City never made. -Infinity would put every em dash
    // at the top of an ascending sort and read as the cheapest rows.
    $.fn.dataTable.ext.type.order['db-money-pre'] = function (d) {
        var n = parseNum(d);
        return n === null ? -Infinity : n;
    };

    $(function () {
        $('table.db-dt').each(function () {
            if ($.fn.DataTable.isDataTable(this)) { return; }
            // Count real body rows: a table whose rows all fit on one page gets
            // sorting and nothing else. A pager and "Showing 1 to 6 of 6" under a
            // six-row table is furniture, not information.
            var rows = $(this).find('tbody > tr').filter(function () {
                return !$(this).hasClass('rr-dossier-row') && $(this).find('td').length > 1;
            }).length;
            var paged = rows > 10;
            // ⚠ THE HOUSE `dom`, NOT DataTables' DEFAULT. `databook-components.css`
            // has skinned DataTables since the design system landed, but only for
            // nodes it can find: `.db-table-toolbar` (a bordered strip) and
            // `.db-table-footer` (space-between, border-top). The default layout
            // puts the filter and pager loose in `.dataTables_wrapper`, so none of
            // that styling applied and the controls rendered raw. Same string as
            // titles.blade.php, which also runs pageLength 10 -- this standard
            // already existed in the app and had simply never reached this section.
            // ⚠ `l` is omitted: lengthChange is false, so it would contribute an
            // empty node and leave the pager alone against `space-between`.
            // ⚠ A table that fits on one page gets `rt` -- no chrome at all. Giving
            // it a toolbar would render an empty bordered strip above it.
            $(this).DataTable({
                dom: paged
                    ? "<'db-table-toolbar'f>rt<'db-table-footer'ip>"
                    : 'rt',
                // ⚠ `order: []` keeps the order the API chose. Several of these
                // tables are deliberately ranked (the function table by distinct
                // products, with "Function not identified" pinned last) and an
                // initial client sort would silently undo that ranking.
                order: [],
                pageLength: window.DB_TABLE_PAGE,
                paging: paged,
                info: paged,
                searching: paged,
                lengthChange: false,
                deferRender: true,
                // ⚠ "Page X of Y", NOT DataTables' default "Showing 1 to 10 of N".
                // The three server-paginated tables in this section cannot safely
                // print a row range: the page ceiling is only known after the API
                // answers, so ?page=99999 would compute a first row past the last --
                // this repo published exactly that on /projects ("Showing
                // 4,999,901-17,024"). Matching THEM here gives one wording across
                // both mechanisms and keeps the range arithmetic out of the section.
                language: {
                    search: '', searchPlaceholder: 'Filter these rows…',
                    info: 'Page _PAGE_ of _PAGES_ · _TOTAL_ entries',
                    infoEmpty: 'No rows', infoFiltered: '(of _MAX_ )',
                    paginate: { previous: 'Previous', next: 'Next' }
                }
            });
            // ⚠ Reuse the site's own search component rather than restyling the
            // generated input: add its class and its icon, and `.db-search` does the
            // rest. One owner for what a search box looks like.
            var $label = $(this).closest('.dataTables_wrapper')
                                .find('.dataTables_filter label');
            if ($label.length && !$label.hasClass('db-search')) {
                $label.addClass('db-search')
                      .prepend('<i class="bi bi-search" aria-hidden="true"></i>');
            }
        });
    });
})();
