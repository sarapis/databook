"""The Parks tracker has two sources, and each has been the broken one.

⚠⚠ WHY THIS EXISTS. `parkscapitaltracker` has never existed on prod, and its
absence took `/get/capital/project/{id}` to 500 for ALL 17,024 projects on
2026-09-11. The cause was that NYC Parks IP-blocks the server: measured the same
minute, `nycgovparks.org` answers **405 from prod** and **200 from a laptop**.

⚠⚠ AND THE OBVIOUS FIX — "use the Socrata mirror" — WAS ALREADY TRIED AND
REJECTED, for a reason that has since expired. `4hcv-tc5r` served **0 rows** on
2026-09-03, every column `non_null = 0`; re-measured 2026-09-11 it carries
**2,785 rows / 2,271 distinct TrackerID**, the same 2,271 projects the JSON feed
has, with 0 ids unique to either side. So both sources are wired and either may
answer — which is the property these guards protect.

⚠⚠ THE MIRROR IS FLAT, AND INGESTING IT RAW IS THE #262/#278 DEFECT. One row per
(project x location): tracker `5072` is **27 rows all reading $4,806,000**. Raw,
that repeats one project 27 times in a panel that serves a LIST and makes any
`SUM(TotalFunding)` 27x too high.

⚠⚠ AND IT FABRICATES A DAY. Every schedule date is month precision in the feed
(`08/2022`); Socrata renders `08/01/2022 12:00:00 AM`, supplying day `01` on
1,689 of 1,689. Keeping it would publish a precision NYC Parks never asserted.
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))


def _mod():
    """Load the extractor BY PATH.

    ⚠ `conftest.py` replaces the whole `modules` package with a MagicMock, and a
    mock satisfies almost any assertion — this repo has shipped guards that
    passed against one. The extractor is dependency-free apart from aiohttp, so
    loading it directly is what makes these assertions real.
    """
    path = os.path.join(API, 'extractors', 'parks_capital_tracker.py')
    spec = importlib.util.spec_from_file_location('_parks_extractor', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# A miniature of the real export: ONE project over three park locations, with
# the money repeated on every row exactly as Socrata publishes it.
CSV = (
    "TrackerID,FMSID,Title,Summary,CurrentPhase,DesignPercentComplete,"
    "ProcurementPercentComplete,ConstructionPercentComplete,DesignStart,"
    "DesignProjectedCompletion,DesignAdjustedCompletion,DesignActualCompletion,"
    "ProcurementStart,ProcurementProjectedCompletion,"
    "ProcurementAdjustedCompletion,ProcurementActualCompletion,"
    "ConstructionStart,ConstructionProjectedCompletion,"
    "ConstructionAdjustedCompletion,ConstructionActualCompletion,TotalFunding,"
    "ProjectLiaison,LastUpdated,FundingSource,name,ParkID,Latitude,Longitude,"
    "Borough\n"
    + "".join(
        f"5072,846 P-1X,A Title,A summary,construction,100,100,40,"
        f"03/01/2015 12:00:00 AM,,,,,,,,"
        f"07/01/2021 12:00:00 AM,08/01/2022 12:00:00 AM,,,"
        f"$4806000,A Liaison,09/09/2026 12:00:00 AM,"
        f"Borough PresidentMayoral,{n},X{i:03d},40.1,-73.9,\"Bronx, Queens\"\n"
        for i, n in enumerate(("Park One", "Park Two", "Park Three"), start=1))
)


def test_the_flat_export_is_renormalised_to_one_row_per_project():
    """⚠ THE DEFECT THIS PREVENTS IS A PANEL REPEATING ONE PROJECT 27 TIMES.
    `_parks` returns a LIST, so a flat ingest is visible to the reader, not just
    to a SUM."""
    m = _mod()
    recs = m._records_from_socrata_csv(CSV)
    assert len(recs) == 1, (
        'the flat export was not deduped to project grain: %d records from 3 '
        'location rows of ONE project' % len(recs))
    locs = recs[0]['Locations']['Location']
    assert len(locs) == 3, (
        'the locations were lost in the dedup: %d, expected 3' % len(locs))
    assert [l['ParkID'] for l in locs] == ['X001', 'X002', 'X003'], (
        'the per-row location is not preserved')


def test_a_fabricated_day_is_demoted_to_the_publishers_precision():
    """⚠⚠ Socrata supplies day `01` on every schedule date; the feed publishes
    none. Rendering "1 Aug 2022" for "August 2022" is precision we invented."""
    m = _mod()
    rec = m._records_from_socrata_csv(CSV)[0]
    assert rec['ConstructionProjectedCompletion'] == '08/2022', (
        'a schedule date kept its fabricated day/time: %r'
        % rec['ConstructionProjectedCompletion'])
    assert rec['DesignStart'] == '03/2015', rec['DesignStart']
    # ⚠ LastUpdated is genuinely MM/DD/YYYY in the feed — it must keep its day
    # and lose only the appended midnight. Demoting it too would DESTROY
    # precision the publisher really does give.
    assert rec['LastUpdated'] == '09/09/2026', (
        'LastUpdated lost the day the publisher actually asserts: %r'
        % rec['LastUpdated'])


def test_the_month_precision_list_excludes_last_updated():
    """⚠ The two rules are opposite, so the membership is the whole decision."""
    m = _mod()
    assert 'LastUpdated' not in m._MONTH_PRECISION_COLS
    for col in ('DesignStart', 'ConstructionProjectedCompletion',
                'ConstructionActualCompletion'):
        assert col in m._MONTH_PRECISION_COLS, col


def test_unparseable_funding_yields_no_rows_rather_than_a_guess():
    """⚠ Socrata runs funders together with NO separator, so the split is a
    longest-match against the publisher's own closed vocabulary. A value it
    cannot account for means the vocabulary moved — and a funding source we
    invented is worse than one we lack."""
    m = _mod()
    assert m._split_funding('Borough PresidentMayoral') == [
        'Borough President', 'Mayoral']
    assert m._split_funding('Borough President, City Council') == [
        'Borough President', 'City Council']
    assert m._split_funding('Some New Funder') == [], (
        'an unknown funder was parsed into something rather than refused')
    assert m._split_funding('') == []


def test_both_sources_are_wired_and_zero_records_counts_as_failure():
    """⚠⚠ EACH SOURCE HAS BEEN THE BROKEN ONE. The JSON was complete while
    Socrata was empty (2026-09-03); Socrata was reachable while the JSON was
    IP-blocked (2026-09-11). A fetch that trusted either alone would have failed
    on one of those days.

    ⚠ And an empty answer must count as a failure, not as data — that is
    literally how Socrata behaved while advertising a same-day refresh."""
    import ast
    m = _mod()
    src = open(os.path.join(API, 'extractors',
                            'parks_capital_tracker.py'), encoding='utf-8').read()
    tree = ast.parse(src)
    fetch = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.AsyncFunctionDef) and n.name == 'fetch')
    body = ast.unparse(fetch)
    assert 'FEED_URL' in body and 'SOCRATA_CSV_URL' in body, (
        'fetch no longer tries both sources')
    assert body.index('FEED_URL') < body.index('SOCRATA_CSV_URL'), (
        'Socrata is tried before the publisher\'s own feed; the JSON is '
        'lossless and must stay first')
    # the zero-record rejection, on BOTH arms
    assert body.count('if records:') == 2, (
        'a source returning 0 records is no longer treated as a failure on '
        'both arms — that is exactly how the empty Socrata mirror behaved')
    assert m.SOCRATA_ID == '4hcv-tc5r'


def test_the_socrata_mirror_is_known_to_omit_three_columns():
    """⚠ RECORDED, NOT SILENT. The mirror publishes 29 columns and omits
    `ContractID`, `ProjectUpdate` and `VitalParksUnder400K`. None is read by
    `_parks`, so the panel is unaffected — but a row sourced from Socrata has
    them empty, and the docstring must keep saying so or the next reader reads
    an empty column as "the City published nothing"."""
    src = open(os.path.join(API, 'extractors',
                            'parks_capital_tracker.py'), encoding='utf-8').read()
    head = src[:src.index('import csv')]
    for col in ('ContractID', 'ProjectUpdate', 'VitalParksUnder400K'):
        assert col in head, (
            'the docstring no longer records that Socrata omits %s' % col)
