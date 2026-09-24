"""Guards on the capital geometry and district crosswalks.

⚠⚠ THE LIVE DEFECT THIS CLOSES. `capitalprojects_cc_idx` and
`capitalprojects_sd_idx` hold **0 rows** on prod, and nothing in the repo creates
any of the three crosswalks. So `/d/cc-…/projects` and `/d/sd-…/projects` have
served nothing for every council and school district — indistinguishable, to the
endpoint, from those districts having no capital work. After this build:
cc 5,810 links, sd 5,530, and the endpoints return 2,187 / 4,449 projects where
they returned 0.

⚠⚠ AND GEOMETRY ALONE WOULD HAVE BEEN A REGRESSION — caught only by comparing
against the crosswalk already on prod. Geometry covers 4,524 community-district
projects against the hand-loaded table's 6,894, losing 4,091 of which only 19
have geometry at all. The union with the published community-board TEXT is what
closes that.

⚠⚠ THE UNION'S COVERAGE FIGURES IN THIS DOCSTRING WERE 9,158 PROJECTS / 15,203
ROWS UNTIL 2026-09-10, and they counted rows the text half should never have
written. Now **7,631 projects / 9,735 `cd` rows**, and the difference is fully
accounted for: of the 2,248 projects that lost their only `cd` link, EVERY ONE
had carried nothing but `x00`/`x99` — a borough with no district. Two separate
defects were behind the old number, both in `build_cd_from_text`:

  * the retired series numbers boroughs differently from DCP and its tokens were
    taken verbatim, so **2,947 projects sat in the wrong borough's community
    district** — see the guards at the end of this file;
  * `x00` and `x99` were written as districts at all.

⭐ The `99` sentinel was already documented here as "correctly excluded"; it was
excluded by a regex that only rejected two-digit tokens, and `299` walked
straight past it. The gate is the published boundary set now, so the exclusion
is structural rather than a happy accident of the token's length.
"""
import importlib.util
import os
import re

API = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
BUILDER = os.path.join(API, 'build_capital_geography.py')


def _src():
    with open(BUILDER, encoding='utf-8') as fh:
        return fh.read()


def _code():
    """The builder's source with COMMENTS AND DOCSTRINGS STRIPPED.

    ⚠⚠ This repo has paid for the alternative ten times: a scanner that reads
    prose reports problems that are not there. The builder's own comment
    explains why `ST_Within` is wrong, and the first draft of the guard below
    fired on that explanation.
    """
    import ast
    tree = ast.parse(_src())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Module)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(tree))


def _load():
    spec = importlib.util.spec_from_file_location('build_capital_geography', BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


builder = _load()


def test_all_four_district_types_are_built():
    """cc and sd are the two that are empty on prod — they must be here."""
    assert set(builder.BOUNDARIES) == {'cd', 'cc', 'sd', 'nta'}, (
        f'expected all four district types, got {sorted(builder.BOUNDARIES)}')
    for kind, url in builder.BOUNDARIES.items():
        assert url.startswith('https://map.databook.nyc/data/'), (
            f'{kind} must read the boundary set the map already serves')


def test_the_spatial_join_uses_intersects_not_within():
    """⚠ A polygon project can straddle a boundary and belongs to both districts.

    ST_Within silently drops every project that crosses a line — and a park or a
    road frequently does. One real project spans 15 council districts.
    """
    code = _code()
    assert 'ST_Intersects' in code, 'the spatial join must use ST_Intersects'
    assert 'ST_Within' not in code, (
        'ST_Within drops any project straddling a boundary; use ST_Intersects')


def test_community_district_links_include_the_text_fallback():
    """⚠⚠ Without this the crosswalk loses 4,091 projects against prod."""
    src = _src()
    assert 'def build_cd_from_text' in src, (
        'the community-board text fallback is required — geometry alone covers '
        '4,524 community-district projects against the 6,894 already on prod')
    m = re.search(r'def build_districts\(db\):(.*?)(?=\nasync def |\ndef |\Z)', src, re.S)
    assert m, 'build_districts not found'
    assert 'build_cd_from_text(' in m.group(1), (
        'build_districts must call build_cd_from_text')


def test_the_text_fallback_only_fills_community_districts():
    """⚠ A community board is NOT a council district.

    Inferring cc/sd/nta from a community board would be inventing data, so the
    fallback must insert with dist_type 'cd' and nothing else.
    """
    src = _src()
    m = re.search(r'def build_cd_from_text\(db\):(.*?)(?=\ndef )', src, re.S)
    assert m, 'build_cd_from_text not found'
    body = m.group(1)
    inserts = re.findall(r"'(cd|cc|sd|nta)'", body)
    assert set(inserts) <= {'cd'}, (
        f'the text fallback may only produce community districts; found {set(inserts)}')


def test_a_community_district_id_must_be_three_digits_starting_1_to_5():
    """⚠ Rejects the '99' sentinel, which is not a district.

    The boundary set has 71 community districts and none is 99; the old
    hand-loaded crosswalk placed 24 projects in it.
    """
    # ⚠ THE QUERY IS AN f-STRING NOW, so a literal `{2}` is written `{{2}}` in
    # source and only becomes `{2}` when the string is formatted. A guard
    # reading raw source therefore has to undo the doubling, or it reports a
    # missing filter on a file that has one — which is what happened.
    src = _src().replace('{{', '{').replace('}}', '}')
    assert re.search(r"\^\[1-5\]\[0-9\]\{2\}\$", src), (
        "the community-board token filter must require a 3-digit id starting "
        "1-5, so sentinels like '99' are rejected rather than becoming a "
        "district that does not exist")


def test_borough_only_values_are_not_guessed_into_a_district():
    """The Dashboard writes 'Brooklyn' with no number for borough-wide work."""
    src = _src()
    assert "num_part <> ''" in src, (
        "a borough with no district number must be skipped, not mapped to an "
        "arbitrary district")
    # ⚠⚠ RICHMOND IS HERE ON PURPOSE, AND ITS ABSENCE DELETED A BOROUGH. The
    # retired series writes `RICHMOND` where the Dashboard writes `Staten
    # Island`; with only the second spelling the `CASE` returns NULL, and the
    # `dist IS NOT NULL` guard that exists to drop unmappable boroughs drops
    # every Staten Island row from that source instead. Shipped for one build:
    # the text rows for borough digit 5 fell 707 -> 205, silently.
    assert set(builder.BOROUGH_CODE) == {
        'MANHATTAN', 'BRONX', 'BROOKLYN', 'QUEENS', 'STATEN ISLAND', 'RICHMOND'}
    assert (builder.BOROUGH_CODE['RICHMOND']
            == builder.BOROUGH_CODE['STATEN ISLAND']), (
        'the two published spellings of one borough resolve to different codes')


def test_every_district_link_records_how_it_was_placed():
    """⚠ Coverage differs by method, so a consumer must be able to say which."""
    src = _src()
    assert "'geometry'" in src and "'community_board_text'" in src, (
        'each link must record its method')
    assert re.search(r'method\s+text NOT NULL', src), (
        'method must be NOT NULL — an unlabelled link cannot be explained')


def test_the_legacy_crosswalks_are_refreshed():
    """This is the half that fixes the empty cc/sd tabs today."""
    src = _src()
    assert 'capitalprojects_{kind}_idx' in src or 'capitalprojects_" + kind' in src, (
        'the legacy capitalprojects_<type>_idx tables must be refreshed until '
        'the endpoints are re-pointed at capital_project_districts')


def test_the_builder_refuses_when_nothing_is_mapped():
    """0 mapped projects means the geometry sources are missing, not that NYC
    stopped mapping — refuse rather than wipe the crosswalks."""
    assert '0 mapped projects' in _src(), (
        'the builder must refuse when no geometry is present'
    )


# ── the hook that keeps the crosswalks fresh ─────────────────────────────────

SCHEDULER = os.path.join(API, 'data_scheduler.py')


def _hooks_for(table):
    """The hook names registered for a table, read from the source.

    ⚠ Read as source rather than imported: data_scheduler pulls in the whole
    api at import time, which a hermetic test must not do.
    """
    with open(SCHEDULER, encoding='utf-8') as fh:
        src = fh.read()
    m = re.search(r'POST_INGEST_HOOKS = \{(.*?)\n\}', src, re.S)
    assert m, 'POST_INGEST_HOOKS not found'
    body = m.group(1)
    e = re.search(r'"' + re.escape(table) + r'":\s*\[([^\]]*)\]', body)
    return [h.strip() for h in e.group(1).split(',') if h.strip()] if e else []


def test_the_geography_rebuild_is_registered_on_every_input():
    """⚠⚠ REGISTERED IS NOT RUNNING, but UNregistered certainly is not.

    Verified live on 2026-09-05 by a real ingest, which printed
    `[hooks] Running 1 post-ingest hook(s) for cpdb_geometry_points` — the tell
    that distinguishes a hook that fires from one that merely exists.
    """
    for table in ('cpdb_geometry_points', 'cpdb_geometry_polygons'):
        assert 'rebuild_capital_geography_hook' in _hooks_for(table), (
            f'{table} must rebuild the crosswalks when it lands')


def test_the_dashboard_also_rebuilds_the_crosswalks():
    """⚠ The Dashboard is one of the two community-board TEXT sources, so a new
    reporting period changes which projects can be PLACED, not just their
    schedule. Registering only the geometry sets would freeze `cd` coverage."""
    assert 'rebuild_capital_geography_hook' in _hooks_for('capprojectsbudgetsandschedule'), (
        'a new Dashboard period changes community-district coverage')


# ============================ the retired series' borough numbering (2026-09-10)

def test_the_retired_series_token_is_translated_not_taken_verbatim():
    """⚠⚠ THE RETIRED SERIES DOES NOT NUMBER BOROUGHS THE WAY DCP DOES, AND
    TAKING ITS TOKEN VERBATIM PUT 2,947 PROJECTS IN THE WRONG BOROUGH'S
    COMMUNITY DISTRICT — on a public page.

    Measured over all 68,473 tokens with ZERO exceptions, from the series' own
    `BORO` column: 1 -> BRONX, 2 -> BROOKLYN, 3 -> MANHATTAN, 4 -> QUEENS,
    5 -> RICHMOND. DCP's is 1 Manhattan, 2 Bronx, 3 Brooklyn, so 1/2/3 are
    permuted and only Queens and Staten Island coincide.

    ⭐ The two methods proved it independently: of 3,145 text rows on projects
    that ALSO have geometry, **0** matched a geometry-derived code. The worked
    example is `826HED-545`, the Croton Filtration Plant — `BORO = BRONX`,
    `COMMUNITY_BOARD = 107 108` — which was listed on `/d/cd-107`, Manhattan's
    Upper West Side, beside genuine Riverside Park projects.

    ⚠ The guard reads the query that builds `cd_text`, not the file, because
    the file also contains the Dashboard query which always translated.
    """
    src = _src()
    i = src.index('CREATE OR REPLACE TABLE cd_text AS')
    q = src[i:src.index('CREATE OR REPLACE TABLE cd_text2 AS')]
    assert 'boro_part' in q, (
        "the retired-series query no longer reads the publisher's own BORO "
        "column, so its borough digit is whatever the token happened to say")
    assert '{cases}' in q, (
        'the borough CASE built from BOROUGH_CODE is not applied to the '
        'retired series, so its tokens land in DCP\'s namespace untranslated')
    assert not re.search(r'trim\(tok\)\s+AS\s+dist', q), (
        'the raw token is written straight into `dist` again — that is the '
        'defect, and it is invisible to every row count')


def test_both_text_sources_are_gated_on_the_published_boundary_set():
    """⚠ A token that translates to a code DCP does not publish is not a
    community district. `x00` (4,370 rows / 4,369 projects) is a BOROUGH with no
    district; `x99` (24 rows) is not a district either.

    ⭐ Gated on the boundary set the geometry half already joins against — 71
    codes, the 59 real districts plus 12 Joint Interest Areas — rather than on a
    hardcoded range, which would be the same answer typed out and would go stale
    the day DCP changes one.

    ⚠ Verified against the whole crosswalk: of the 2,248 projects that lost
    their only `cd` link, **every one** had carried nothing but `x00`/`x99`.
    """
    src = _src()
    assert re.search(r'CREATE OR REPLACE TABLE cd_codes AS', src), (
        'the cd boundary codes are no longer captured, so the gate below has '
        'nothing to check against')
    ins = src[src.index("SELECT agency_key, fms_id, 'cd', dist, 'community_board_text'"):]
    ins = ins[:ins.index('"""')]
    assert 'cd_codes' in ins, (
        'the text-derived links are no longer gated on the published boundary '
        'set, so a borough-wide marker becomes a district that does not exist')
    assert 'cd_text' in ins and 'cd_text2' in ins, (
        'the gate must cover BOTH text sources — one rule with an exception is '
        'not one rule')


def test_the_boundary_codes_are_captured_before_the_loop_moves_on():
    """⚠ `b` is overwritten by each boundary set and `build_cd_from_text` runs
    AFTER the loop, by which point `b` holds `nta`. Capturing the codes late
    would gate community districts against neighborhood names — which matches
    nothing, and would empty the text half entirely.
    """
    src = _src()
    cap = src.index('CREATE OR REPLACE TABLE cd_codes AS')
    assert src.index("if kind == 'cd':") < cap, (
        'the capture is not inside the cd branch of the boundary loop')
    # ⚠ ANCHORED ON THE CALL, NOT THE DEFINITION — `def build_cd_from_text(db):`
    # appears earlier in the file, so `src.index('build_cd_from_text(db)')`
    # finds the def and the comparison is meaningless. Wrong-occurrence
    # anchoring, which this repo has now paid for four times.
    call = re.search(r'(?<!def )\bbuild_cd_from_text\(db\)', src[cap:])
    assert call, 'nothing calls build_cd_from_text after the codes are captured'
