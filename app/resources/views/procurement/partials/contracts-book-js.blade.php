{{-- The whole-book charts' JS (see contracts-book). Include inside a
     DOMContentLoaded handler, AFTER slice-pies-js, with DBChart applied. --}}
    // ---- Committed money by start year ---------------------------------
    // ⚠⚠ TWO DATASETS, BOTH COMMITTED MONEY (still running / already ended).
    // The year's master-agreement CEILING is carried in the tooltip and is
    // deliberately NOT a dataset: stacking it would draw undrawn headroom as
    // spend (#294). Do not "complete" this chart by adding it as a third bar.
    // ⚠ Read from the payload key, not a variable the markup partial computed —
    // an included view renders in its own scope, so nothing it defines comes back.
    const abyData = @json($awardByStartYear['years'] ?? []);
    const abyCurrent = @json($awardByStartYear['current_year'] ?? '');
    if (abyData.length && document.getElementById('digitalStartYearChart')) {
        const musd = (v) => '$' + (Number(v) / 1000000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'M';
        new Chart(document.getElementById('digitalStartYearChart'), {
            type: 'bar',
            data: {
                labels: abyData.map(d => d.year + (d.year === abyCurrent ? ' (partial)' : '')),
                datasets: [
                    { label: 'Committed - still running', data: abyData.map(d => d.committed_active),
                      backgroundColor: DBChart.navy, borderRadius: 4, stack: 'committed' },
                    // A muted tone for ended money: it is real money, but it is
                    // history, and the eye should land on the live book first.
                    { label: 'Committed - already ended', data: abyData.map(d => d.committed_ended),
                      backgroundColor: DBChart.palette[3] || '#9aa5b1', borderRadius: 4, stack: 'committed' }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: { x: { stacked: true }, y: { stacked: true,
                          ticks: { callback: (val) => '$' + (val / 1000000).toFixed(0) + 'M' } } },
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, padding: 10, font: { size: 11 } } },
                    tooltip: { callbacks: {
                        label: (c) => c.dataset.label + ': ' + musd(c.parsed.y),
                        // ⚠ The ceiling appears HERE, labelled as a ceiling, never
                        // added to the committed figures above it.
                        afterBody: (items) => {
                            const d = abyData[items[0].dataIndex]; if (!d) { return ''; }
                            const out = [d.contracts + ' contracts (' + d.active_contracts +
                                         ' still running, ' + d.ended_contracts + ' ended)'];
                            if (Number(d.ceiling) > 0) {
                                out.push('Master agreement ceiling, not included above: ' +
                                         musd(d.ceiling) + ' across ' + d.master_contracts +
                                         (d.master_contracts === 1 ? ' agreement' : ' agreements'));
                            }
                            return out;
                        }
                    } }
                }
            }
        });
    }
    // Contracts: value by agency. Served pre-capped by the endpoint, so it is
    // folded here only to give the remainder a neutral and a name.
    const ovAgencyBlock = @json($ovAgencySlices ?? null);
    ovPie('ovAgencyChart', ovAgencyBlock);
    ovPie('ovTypeChart',        @json($ovTypeSlices ?? null));
