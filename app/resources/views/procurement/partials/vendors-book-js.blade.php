{{-- The Vendors book's pie (see vendors-book). Include inside a
     DOMContentLoaded handler, AFTER slice-pies-js (it uses sliceColor). --}}
    // ⚠ The wedge is a VENDOR COUNT, so its tooltip must say so — every other
    // pie on this page is money, and an unlabelled number here would be read as
    // dollars. `ovPie` formats with DBChart.money, which is right for the other
    // five and wrong for this one, so this chart is built separately.
    ovVendorMethodPie(@json($vmSlices ?? null));

    // ⚠ A COUNT, NOT MONEY. Same legend contract as `ovPie` — canvas legend off,
    // the HTML list beside it is the legend — but its own value formatter, and
    // its tooltip carries the money the wedge is NOT, so a reader cannot take
    // the slice for a dollar figure.
    function ovVendorMethodPie(block) {
        const el = document.getElementById('ovVendorMethodChart');
        if (!el || !block || !(block.values || []).length) { return; }
        const vm = @json($vm ?? []);
        const byLabel = {};
        (vm.items || []).forEach(function (i) { byLabel[i.method] = i.value; });
        const total = (block.values || []).reduce((a, b) => a + (+b || 0), 0);
        const card = el.closest('.db-chart-card');
        const titleEl = card && card.querySelector('.db-chart-title');
        new Chart(el, {
            type: 'doughnut',
            data: { labels: block.labels || [],
                    datasets: [{ data: block.values || [],
                                 backgroundColor: (block.colors || []).map(sliceColor),
                                 borderColor: '#ffffff', borderWidth: 2 }] },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '58%',
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: {
                        title: () => titleEl ? titleEl.textContent.trim() : '',
                        label: (c) => {
                            const n = +c.parsed || 0;
                            const pct = total > 0 ? ' (' + (100 * n / total).toFixed(1) + '%)' : '';
                            const v = byLabel[c.label];
                            const money = (v === undefined) ? '' : ', holding ' + DBChart.money(v);
                            return c.label + ': ' + n.toLocaleString() + ' vendors' + pct + money;
                        }
                    } }
                }
            }
        });
    }
