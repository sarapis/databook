{{-- The Agreements book's ceiling-by-year chart (see agreements-book). Include
     inside a DOMContentLoaded handler, with DBChart applied. --}}
    // The Agreements band's ceiling-by-year bars.
    // ⚠⚠ ONE SERIES, and the note beside it says these do not add up: an
    // agreement counts in EVERY year of its term. There is deliberately no spend
    // series — none of the 182 agreements carries a payment under its own
    // contract id, so a second bar would have to be invented.
    (function () {
        const el = document.getElementById('ovAgrYearChart');
        const rows = @json($agrBlocks['by_year'] ?? []);
        if (!el || !rows.length) { return; }
        new Chart(el, {
            type: 'bar',
            data: {
                labels: rows.map(r => String(r.year)),
                datasets: [{ label: 'Ceiling running in that year',
                             data: rows.map(r => +r.ceiling || 0),
                             backgroundColor: DBChart.slice[0], borderRadius: 4 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: {
                        title: (c) => c[0].label,
                        label: (c) => {
                            const r = rows[c.dataIndex] || {};
                            return DBChart.money(+c.parsed.y || 0) + ' across '
                                 + (r.agreements || 0) + ' agreements';
                        }
                    } }
                },
                scales: { y: { beginAtZero: true,
                               ticks: { callback: (v) => DBChart.money(v) } } }
            }
        });
    })();
