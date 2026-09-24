/* ============================================================================
   Databook design-system — shared Chart.js factory
   Loaded globally (no Chart.js dependency at load time). On any page that
   loads Chart.js, call DBChart.apply(Chart) once to theme every chart with the
   navy/accent palette + Public Sans, then use DBChart.navy / .accent /
   .palette / .money() for per-dataset colors. Keeps chart styling consistent
   without each view re-declaring fonts, grid colors, and tooltips.
   ========================================================================== */
window.DBChart = {
  navy: '#162e51',
  accent: '#2491ff',
  navyFill: 'rgba(22, 46, 81, 0.08)',
  accentFill: 'rgba(36, 145, 255, 0.14)',
  grid: '#eef0f2',
  muted: '#757575',
  border: '#dfe1e2',
  // Categorical palette: navy → accent ramp, then harmonized state hues.
  palette: ['#162e51', '#2491ff', '#1f3a63', '#759fbc', '#2e8540', '#c2850c', '#005ea2', '#90c3c8', '#b50909', '#54278f'],

  /* ⚠⚠ SLICE ORDER FOR PART-TO-WHOLE, AND IT IS NOT `palette`. Measured with
     the dataviz validator (OKLab, light surface) rather than judged by eye:
     `palette`'s first six FAIL three checks — #162e51, #1f3a63 and #759fbc sit
     below the chroma floor and read as GRAY, #162e51/#1f3a63 fall outside the
     lightness band, and #759fbc renders at 2.75:1 against the surface. On a bar
     chart with a legend that survives; on a pie, where slices touch, three
     near-identical blues read as one wedge.

     These are the SAME brand hues, re-ordered so green separates the two blues
     and sits away from red. That order PASSES all five checks
     (lightness, chroma, CVD ΔE 16.9 worst adjacent, normal-vision ΔE 21.9,
     contrast ≥ 3:1). Re-run before changing it:
       node scripts/validate_palette.js "#2491ff,#2e8540,#005ea2,#c2850c,#b50909" --mode light

     ⚠ FIVE, not six: no ordering of the ten brand hues passes at six —
     #90c3c8 reads gray at 1.89:1 and #54278f is too dark. A sixth slice is
     therefore the fold below, never a generated hue.
     ⚠ DO NOT "simplify" this into `palette`. Every other chart on the site
     uses that array, and repainting them is not this section's call. */
  slice: ['#2491ff', '#2e8540', '#005ea2', '#c2850c', '#b50909'],

  /* TWO neutrals, because a fold and an abstention are DIFFERENT CLAIMS and
     shipping them in one grey put two meanings on one visual — "41 others" and
     "Function not identified" were indistinguishable wedges in the same ring.
     Neither is a categorical slot: giving either a hue would rank it beside
     real categories.

     ⚠ The abstention is the DARKER of the two ON PURPOSE. It is a FINDING —
     65% of the data lens's value carries no identified kind — so it has to be
     legible; 4.83:1 against the surface. The fold is housekeeping, so it
     recedes at 1.86:1, which the visible legend label relieves. They separate
     from each other at 2.60. */
  sliceOther:   '#b8bfc6',   /* "N others" — real categories, folded for space */
  sliceUnknown: '#6b7280',   /* "not identified" / "not recorded" — no answer  */

  // Compact money formatter for axis ticks ($1.2B / $340M / $12K).
  money: function (v) {
    v = +v || 0;
    var a = Math.abs(v);
    if (a >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B';
    if (a >= 1e6) return '$' + (v / 1e6).toFixed(0) + 'M';
    if (a >= 1e3) return '$' + (v / 1e3).toFixed(0) + 'K';
    return '$' + v;
  },

  // Theme Chart.js global defaults. Safe to call once Chart.js is loaded.
  apply: function (Chart) {
    if (!Chart || !Chart.defaults) return;
    Chart.defaults.font.family = "'Public Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = this.muted;
    var p = Chart.defaults.plugins || {};
    if (p.legend) {
      p.legend.labels = Object.assign({}, p.legend.labels, { usePointStyle: true, boxWidth: 10, padding: 14 });
    }
    if (p.tooltip) {
      p.tooltip.backgroundColor = this.navy;
      p.tooltip.padding = 10;
      p.tooltip.cornerRadius = 6;
      p.tooltip.titleFont = { weight: '600' };
    }
  }
};
