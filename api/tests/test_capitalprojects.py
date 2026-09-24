"""Capital-project core endpoint: list-only fallback (the /p/ 404 fix)."""
import asyncpg
import pytest


@pytest.mark.asyncio
async def test_core_falls_back_to_list_when_no_dollarscomp(client, mock_select):
    """When the commitment-plan dollars table has no matching row, core returns
    the capitalprojectslist row tagged _source='list' (→ reduced page)."""
    def fake(sql, params=None):
        if 'capitalprojectsdollarscomp' in sql:
            return {'rows': []}
        if 'capitalprojectslist' in sql:
            assert "'list' AS _source" in sql
            return {'rows': [{'maprojid': '858DOIT5MYSM', 'description': 'X', '_source': 'list'}]}
        return {'rows': []}
    mock_select.side_effect = fake
    r = await client.get('/get/capitalprojects/core/858DOIT5MYSM')
    assert r.status_code == 200
    assert r.json()['rows'][0]['_source'] == 'list'


@pytest.mark.asyncio
async def test_core_prefers_dollarscomp_when_present(client, mock_select):
    """A real commitment-plan project is returned untagged (→ full page)."""
    def fake(sql, params=None):
        if 'capitalprojectsdollarscomp' in sql:
            return {'rows': [{'PROJECT_ID': 'DOIT5MYSM', 'PROJECT_DESCR': 'X'}]}
        raise AssertionError('should not reach list fallback')
    mock_select.side_effect = fake
    r = await client.get('/get/capitalprojects/core/DOIT5MYSM')
    assert r.status_code == 200
    assert r.json()['rows'][0].get('_source') is None


@pytest.mark.asyncio
async def test_commitments_matches_either_id_form(client, mock_select):
    """Commitments lookup must match maprojid OR projectid (callers pass either)."""
    captured = {}
    def fake(sql, params=None):
        captured['sql'] = sql
        return {'rows': []}
    mock_select.side_effect = fake
    await client.get('/get/capitalprojects/commitments/858DOIT5MYSM')
    assert '"projectid" = $1 OR "maprojid" = $1' in captured['sql']


@pytest.mark.asyncio
async def test_district_capitalprojects_missing_crosswalk_is_empty_not_500(client, mock_select):
    """nta has no capitalprojects_nta_idx crosswalk (2010↔2020 NTAs don't map).
    The endpoint must return empty rows, not 500 — was flooding Sentry."""
    mock_select.side_effect = asyncpg.exceptions.UndefinedTableError(
        'relation "capitalprojects_nta_idx" does not exist')
    r = await client.get('/get/districts/nta/MN0101/capitalprojects')
    assert r.status_code == 200
    assert r.json() == {"rows": []}


@pytest.mark.asyncio
async def test_district_capitalprojects_rejects_unsafe_type(client, mock_select):
    """`type` is interpolated into the table name — an unsafe value must be
    rejected before any query runs (injection guard)."""
    r = await client.get('/get/districts/cd;DROP/101/capitalprojects')
    assert r.status_code == 200
    assert r.json() == {"rows": []}
    mock_select.assert_not_called()


@pytest.mark.asyncio
async def test_district_capitalprojects_valid_type_uses_crosswalk(client, mock_select):
    """A valid type (cd) joins the matching crosswalk table."""
    captured = {}
    def fake(sql, params=None):
        captured['sql'] = sql
        return {'rows': [{'PROJECT_ID': 'X', 'DIST': '101'}]}
    mock_select.side_effect = fake
    r = await client.get('/get/districts/cd/101/capitalprojects')
    assert r.status_code == 200
    assert 'capitalprojects_cd_idx' in captured['sql']


# ---- the eight district stat tiles: RETIRED WITH THEIR ENDPOINTS -----------
# ⚠⚠ 24 PARAMETRISED GUARDS STOOD HERE AND ARE DELETED (2026-09-10), BECAUSE THE
# ENDPOINTS THEY TESTED ARE. `/get/districts/pstats-{measure}/{type}/{id}/{pubdate}`
# — eight measures over `capitalprojectsdollarscomp`, the series NYC retired
# 2023-10-26 — had no caller left once the district capital tab moved to the
# spine, and one of the eight computed `over_budg_am`, the `Amount Over Budget`
# label this section reproduces nowhere. Keeping guards that require a dead
# endpoint to exist would have forbidden the deletion, which is the same mistake
# as the family-row guard that had to be retired once family pages existed:
# RETIRING A GUARD WHEN ITS CONDITION ENDS IS NOT WEAKENING IT.
#
# ⭐ WHAT THEY PROTECTED IS NOT LOST, and that is the test of whether a
# retirement is honest:
#   * the two HAZARDS — an unsafe `type` interpolated into a table name, and a
#     missing `capitalprojects_nta_idx` raising instead of degrading — are still
#     guarded on the LIST endpoint, by `test_district_capitalprojects_*` directly
#     above, which uses the same crosswalk through the same helper;
#   * that the routes stay deleted, that the orphaned `_pstats_select` helper
#     stays deleted, and that no frontend file builds one of those URLs, are
#     guarded by `test_retired_pstats_routes_are_gone.py`;
#   * and the one-helper rule below is re-expressed rather than dropped.
# The original defect is worth remembering either way: one nta district page
# raised EIGHT `UndefinedTableError`s in one second (Sentry DATABOOK-API-P),
# because all eight tiles loaded per page view.


def test_no_handler_interpolates_the_crosswalk_without_the_guard():
    """The crosswalk table name may only be built inside a guarding helper.

    Checks the direction that catches the handler nobody has written yet: a new
    stat endpoint that does `.format(type)` itself and calls bare `select()` is
    exactly how these eight drifted away from the list endpoint's guard. Written
    against the literal `capitalprojects_{}_idx` template — prose refers to it as
    `capitalprojects_<type>_idx` so this cannot fire on its own explanation.
    """
    import os
    main_py = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'main.py')
    with open(main_py) as fh:
        lines = fh.read().splitlines()

    interpolations = [
        ln for ln in lines
        if 'capitalprojects_{}_idx' in ln and not ln.strip().startswith('#')
    ]
    # Assert the scan looked: a guard that matches nothing passes vacuously.
    # ⚠ The floor was 9 — the list endpoint plus the eight stat tiles — and it
    # became wrong when the eight were deleted (2026-09-10). It is 1 now, which
    # is the list endpoint, and that is the whole population: a floor that
    # counts endpoints has to move when endpoints go, but a floor of ZERO would
    # make this the zero-files scanner.
    assert len(interpolations) >= 1, (
        f'expected the list endpoint at least, found {len(interpolations)}')
    for ln in interpolations:
        # ⚠ `_pstats_select` left this list because it was DELETED with its
        # eight callers, not because interpolating outside it became safe. It is
        # named here so a future reader does not re-add the helper believing a
        # guard still expects it.
        assert '_district_select(' in ln, (
            f'crosswalk interpolated outside a guarding helper: {ln.strip()}')
