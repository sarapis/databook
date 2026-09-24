/* ============================================================================
   Charts that are derived from a DataTable's CURRENTLY FILTERED rows.

   ⚠⚠ WHY THE ROWS AND NOT THE PAYLOAD. Every page using this serves several
   PUBLICATION VINTAGES in one payload and filters to one — `/projects/types`
   carries 531 rows across 8 vintages for 37 types, `/projects/categories`
   1,617 across 8. Charting the payload would sum every vintage at once, which
   is not a number about anything. Two of those vintages are also the ones this
   repo documents as ingested wrong, so the error would not even be uniform.

   ⭐ Deriving from `rows({search:'applied'})` makes the chart and the table
   answer the same question BY CONSTRUCTION rather than by two computations
   agreeing — the property this repo relies on for the list-vs-map check, and
   the defect it has paid for when two figures were computed twice.

   ⚠ It redraws on `draw`, so changing a filter moves the charts with the table.
   ========================================================================== */
window.DBTableCharts = (function () {
  'use strict';

  function num(v) {
    // ⚠⚠ EVERY MONEY FIELD IN THESE PAYLOADS IS A STRING (`'129000'`), so `+`
    // concatenates. That defect shipped on two pages in this section and
    // rendered a y-axis of `$7E141` and legends reading `undefined (NaN %)`.
    // `Number(v) || 0` also absorbs '' and null, which `?? 0` never did.
    return Number(v) || 0;
  }

  function aggregate(rows, spec) {
    var acc = {};
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      // ⚠ `expand` is for a row that contributes to SEVERAL buckets — a
      // commitment row carries five fiscal years, and one (label, value) per
      // row cannot express that without charting four of the five.
      var pairs = spec.expand ? spec.expand(r) : [[spec.label(r), spec.value(r)]];
      for (var j = 0; j < pairs.length; j++) {
        var k = pairs[j][0];
        if (k === null || k === undefined || k === '') continue;
        acc[k] = (acc[k] || 0) + num(pairs[j][1]);
      }
    }
    var pairs = Object.keys(acc).map(function (k) { return [k, acc[k]]; });
    if (spec.order === 'label') {
      pairs.sort(function (a, b) { return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0; });
    } else {
      pairs.sort(function (a, b) { return b[1] - a[1]; });
    }
    // ⚠ A CAPPED LIST MUST STILL ACCOUNT FOR WHAT IT CAPPED. This repo has
    // shipped "top 25 of 88" presented as the whole set more than once, so the
    // remainder is folded into one labelled slice rather than dropped.
    if (spec.top && pairs.length > spec.top) {
      var rest = pairs.slice(spec.top).reduce(function (s, p) { return s + p[1]; }, 0);
      pairs = pairs.slice(0, spec.top);
      if (rest > 0) pairs.push([spec.restLabel || ('All other (' + (spec.top ? '…' : '') + ')'), rest]);
    }
    return pairs;
  }

  // ⚠⚠ A TRUNCATION THAT MAKES TWO DIFFERENT LABELS IDENTICAL IS WORSE THAN A
  // LONG ONE. Cutting at 23 characters rendered "Department of Environmental
  // Protection" and "Department of Environmental Remediation" as the SAME
  // string, so the chart showed two bars with one name and no way to tell which
  // was which. Keeping the END is what distinguishes them, and it is where the
  // distinguishing word lives in every one of these vocabularies.
  function shorten(v) {
    var s = String(this.getLabelForValue(v));
    if (s.length <= 30) return s;
    return s.slice(0, 12) + '…' + s.slice(-16);
  }

  function build(canvas, spec, pairs) {
    var isPie = spec.type === 'pie' || spec.type === 'doughnut';
    var money = spec.money !== false;
    var fmt = function (v) { return money ? window.DBChart.money(v) : String(v); };
    var cfg = {
      type: spec.type || 'bar',
      data: {
        labels: pairs.map(function (p) { return p[0]; }),
        datasets: [{
          label: spec.seriesLabel || '',
          data: pairs.map(function (p) { return p[1]; }),
          backgroundColor: isPie
            ? pairs.map(function (_, i) { return window.DBChart.palette[i % window.DBChart.palette.length]; })
            : window.DBChart.navy,
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: spec.horizontal ? 'y' : 'x',
        plugins: {
          legend: {display: !!isPie, position: 'right'},
          datalabels: {display: false},
          tooltip: {callbacks: {label: function (c) {
            var v = c.parsed;
            if (typeof v === 'object' && v !== null) v = spec.horizontal ? v.x : v.y;
            return ' ' + c.label + ': ' + fmt(v);
          }}},
        },
        scales: isPie ? {} : {
          x: {grid: {display: false},
              // ⚠⚠ `maxRotation: 0` IS ON BOTH BRANCHES ON PURPOSE, and it was
              // missing here. On a horizontal bar the x axis is the VALUE axis,
              // and Chart.js's default `maxRotation: 50` rotates its labels
              // whenever the tick count it picks does not fit the width — so at
              // the ~408px three charts leave, `$0 $10.0B $20.0B …` rendered on
              // a ~30° slant. Measured: which chart slants MOVES with the
              // viewport (1440 tyByTen + caByTen at 29.8°, 1024 tyByTen +
              // caByYr1 at 27.3° while caByTen straightens), because it depends
              // on the ticks Chart.js happens to choose. Capping rotation makes
              // it DROP a tick instead, which is right for a value axis — the
              // gridlines stay and the tooltip carries the exact figure —
              // whereas on the CATEGORY axis below skipping would hide a
              // category, which is why that branch also sets `autoSkip: false`.
              ticks: spec.horizontal ? {callback: fmt, maxRotation: 0} : {autoSkip: false, maxRotation: 0,
                     callback: function (v) {
                       var s = this.getLabelForValue(v);
                       return s.length > 16 ? s.slice(0, 15) + '…' : s;
                     }}},
          y: {grid: {color: window.DBChart.grid}, beginAtZero: true,
              ticks: spec.horizontal ? {autoSkip: false, callback: shorten} : {callback: fmt}},
        },
      },
    };
    return new window.Chart(canvas, cfg);
  }

  return {
    bind: function (table, specs) {
      if (!window.Chart || !window.DBChart) return;
      window.DBChart.apply(window.Chart);
      var charts = {};
      function redraw() {
        var rows = table.rows({search: 'applied'}).data().toArray();
        specs.forEach(function (spec) {
          var el = document.getElementById(spec.canvas);
          if (!el) return;
          var pairs = aggregate(rows, spec);
          if (charts[spec.canvas]) {
            charts[spec.canvas].data.labels = pairs.map(function (p) { return p[0]; });
            charts[spec.canvas].data.datasets[0].data = pairs.map(function (p) { return p[1]; });
            if (spec.type === 'pie' || spec.type === 'doughnut') {
              charts[spec.canvas].data.datasets[0].backgroundColor = pairs.map(function (_, i) {
                return window.DBChart.palette[i % window.DBChart.palette.length];
              });
            }
            charts[spec.canvas].update();
          } else {
            charts[spec.canvas] = build(el, spec, pairs);
          }
        });
      }
      table.on('draw', redraw);
      redraw();
      return charts;
    },
    _aggregate: aggregate,
  };
})();
