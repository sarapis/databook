{{-- The part-to-whole pie factory — sliceColor, paintLegends, ovPie — as JS
     function declarations, included INSIDE a page's DOMContentLoaded script.
     ONE owner for every pie in the Digital Services section: the Overview's
     bands and the Contracts page both include this, so the palette and the
     legend rules cannot fork. --}}
    // ---- The section bands' part-to-whole charts -------------------------
    // ⚠⚠ ONE FACTORY FOR ALL FIVE. Five doughnuts written five times is five
    // chances for one to cycle a hue, drop its remainder, or lose its legend.
    //
    // ⚠ COLOURS COME FROM `DBChart.slice`, NOT `DBChart.palette`. Measured with
    // the dataviz validator: palette's first six FAIL three checks (three of
    // them read gray, one renders at 2.75:1), which a legend survives on a bar
    // chart and a pie does not, because its slices touch. `slice` is the same
    // brand hues re-ordered to pass; see the note in db-charts.js.
    //
    // ⚠ The server sends `colors` as an index into DBChart.slice, or 'OTHER'
    // (categories folded for space), or 'UNKNOWN' (the classifier had no
    // answer). Neither marker is ever a categorical hue — that would rank it
    // beside real categories — and the two are DIFFERENT GREYS, because one
    // grey for both made "41 others" and "Function not identified"
    // indistinguishable wedges in the same ring.
    //
    // ⚠ The 2px surface gap and the always-present legend are the SECONDARY
    // ENCODING the validator's CVD check requires; do not remove either to
    // tighten the layout.
    // ⚠⚠ ONE COLOUR OWNER for the arcs AND the legend swatches. The legend is
    // HTML now, so without a shared resolver the palette would have two homes
    // and a key could name a wedge it does not match.
    function sliceColor(c) {
        if (c === 'OTHER')   { return DBChart.sliceOther; }    // folded categories
        if (c === 'UNKNOWN') { return DBChart.sliceUnknown; }  // no answer at all
        return DBChart.slice[c] || DBChart.sliceOther;
    }

    // Paint every legend swatch from that resolver. Runs once; the entries are
    // server-rendered, so there is nothing to wait for.
    function paintLegends() {
        document.querySelectorAll('.ds-seglinks [data-c]').forEach(function (el) {
            var raw = el.getAttribute('data-c');
            var c = /^\d+$/.test(raw) ? parseInt(raw, 10) : raw;
            var sw = el.querySelector('.ds-sw');
            if (sw) { sw.style.setProperty('--sw', sliceColor(c)); }
        });
    }

    function ovPie(canvasId, block) {
        const el = document.getElementById(canvasId);
        if (!el || !block || !(block.values || []).length) { return; }
        // ⚠ THE TITLE IS READ FROM THE CARD THAT ALREADY RENDERS IT, never typed
        // here. A second copy is a second vocabulary: this section already has
        // two names for one segment because a friendlier label was typed beside
        // the payload's own.
        const card = el.closest('.db-chart-card');
        const titleEl = card && card.querySelector('.db-chart-title');
        const chartTitle = titleEl ? titleEl.textContent.trim() : '';
        const colors = (block.colors || []).map(sliceColor);
        const total = (block.values || []).reduce((a, b) => a + (+b || 0), 0);
        new Chart(el, {
            type: 'doughnut',
            data: { labels: block.labels || [],
                    datasets: [{ data: block.values || [], backgroundColor: colors,
                                 borderColor: '#ffffff', borderWidth: 2 }] },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '58%',
                plugins: {
                    // ⚠⚠ THE CANVAS LEGEND IS OFF, AND THE `.ds-seglinks` LIST IS
                    // THE LEGEND. They used to render the same five labels twice
                    // — once as dead text Chart.js drew into the canvas, once
                    // here as links — so the duplication was the defect and the
                    // canvas copy is the half that could not be clicked, focused
                    // or read by a screen reader. Every wedge still has a legend
                    // entry, including the fold, because an always-present legend
                    // is the SECONDARY ENCODING the palette's colour-vision check
                    // requires. ⚠ Do not restore `legend.display` to get the
                    // middle-ellipsis truncation back: the HTML legend wraps, so
                    // it needs no truncation and two long agency names can no
                    // longer collapse into one string.
                    legend: { display: false },
                    tooltip: { callbacks: {
                        // ⚠⚠ THE TITLE WAS THE LABEL AND SO WAS THE BODY. Chart.js
                        // defaults a doughnut's tooltip title to the slice label,
                        // and the body callback prepended it again — every hover
                        // read "Renewal / Renewal: $2.7B (27%)". The title now
                        // names the CHART, which is the one thing the hover did
                        // not say.
                        title: () => chartTitle || '',
                        label: (c) => {
                            const v = +c.parsed || 0;
                            const pct = total > 0 ? ' (' + (100 * v / total).toFixed(1) + '%)' : '';
                            return c.label + ': ' + DBChart.money(v) + pct;
                        }
                    } }
                }
            }
        });
    }

