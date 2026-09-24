"""Guards on the project profile page — `/p/{agency}{id}` — and its endpoint.

⚠⚠ TWO LIVE DEFECTS THIS PAGE REPLACES, both measured 2026-09-06 against the
running stack rather than reasoned about.

  `/p/111PO111-17` returned **404**. It is a real project in the current Capital
  Commitment Plan. The old action required `fetchOrg()` to succeed and
  **4,568 of 17,024 spine rows carry no `wegov_org_id`** — 27% of the capital
  programme had no page at all.

  `/p/110WLM` returned **200 and showed one project**. That id is carried by
  DCAS (856) and by agency 068. 1,160 ids are shared across agencies, covering
  2,371 rows, so a bare FMS id does not identify a project and picking one
  silently shows a reader the wrong agency's work under this agency's number.

⚠⚠ AND THE GUARD DISCIPLINE. Seven guards in this section's earlier work passed
against a real reintroduced bug because each inspected a MENTION or an INPUT
rather than what the code did — a parameter's presence in a signature rather than
the expression forwarded from it, a string inside an `@if` rather than the `{{ }}`
that echoes it. Every guard here was verified by reintroducing its bug, with the
mutation asserted to have LANDED first.
"""
import ast
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))
ROOT = os.path.realpath(os.path.join(API, '..'))

ROUTER = os.path.join(API, 'routers', 'capital.py')
WKT = os.path.join(API, 'modules', 'wkt.py')
BUDGETLINE = os.path.join(API, 'modules', 'budgetline.py')
CONTROLLER = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Organizations.php')
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'capitalproject.blade.php')
CHOICES = os.path.join(ROOT, 'app', 'resources', 'views', 'capitalprojectchoices.blade.php')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _rendered_copy(src):
    """Blade source with every COMMENT removed — Blade's and PHP's.

    ⚠ This repo has paid eleven times for a guard firing on its own prose, and
    the comments in these two views quote the very sentences the guards look
    for. PHP comments only, never the whole `@php` block: that block is where
    Blade composes rendered copy.
    """
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'^[ \t]*//.*$', '', src, flags=re.M)
    return src


def _action(name):
    php = _read(CONTROLLER)
    start = php.index(f'public function {name}(')
    end = php.index('public function ', start + 10)
    return php[start:end]


def _fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef)) and n.name == name:
            return n
    raise AssertionError(f'{name} not found')


def _code(fn):
    """A function's source WITHOUT its docstring.

    ⚠⚠ TWELFTH OWN-PROSE FIRING IN THIS REPO, AND IT HAPPENED WHILE WRITING THESE
    GUARDS. `ast.unparse` includes the docstring, so a scan for `MAX(` in
    `_parks` matched the sentence explaining why a `MAX(percent)` would be wrong.
    The guard reported the defect it exists to prevent, in the code that
    prevents it.
    """
    node = ast.parse(ast.unparse(fn)).body[0]
    if (node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)):
        node.body = node.body[1:]
    return ast.unparse(node)


def _returned_keys(fn):
    """The keys of every dict literal a function returns.

    ⚠ Reads the AST rather than the unparsed TEXT: `ast.unparse` normalises
    double quotes to single, so a guard grepping for `"note":` never matches the
    source it is looking at and passes for the wrong reason.
    """
    keys = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)
    return keys


# ------------------------------------------------------- the two live defects

def test_a_project_without_a_known_agency_still_gets_a_page():
    """⚠⚠ 4,568 of 17,024 spine rows carry no `wegov_org_id`, so requiring the
    org lookup 404'd 27% of the capital programme — `/p/111PO111-17` among them.
    The org shell must be CONDITIONAL, and the action must not abort on a
    missing org."""
    act = _action('project')
    m = re.search(r"\$org\s*=\s*([^;]+);", act)
    assert m, 'the action must resolve $org'
    assert '?' in m.group(1) and 'fetchOrg' in m.group(1), (
        f'$org is resolved unconditionally: {m.group(1).strip()}')
    # ⚠ ASSERT THE ABORT IS GONE, not that a ternary exists — the old code read
    # `return $org ? view(...) : abort(404)`, which is also a ternary.
    assert not re.search(r'\$org\s*\?\s*view\(', act), (
        'the action still renders only when an org resolves')
    assert not re.search(r':\s*abort\(404\)', act), (
        'a missing org still aborts, so 4,568 projects have no page')

    view = _rendered_copy(_read(VIEW))
    # ⚠⚠ THIS USED TO ASSERT `@if($org) @include('sub.orgheader')`, AND IT FIRED
    # WHEN THE SHELL WAS REMOVED — correctly. The shell emitted a SECOND `<h1>`
    # (the agency's) plus 380px of tab navigation for a different entity, so it
    # is gone and two values replace it. The PROPERTY is unchanged and is what
    # is asserted now: a project whose agency we do not know must still name its
    # agency, and must never emit a link built from a null id.
    assert 'sub.orgheader' not in view, (
        "the org shell is back. It emits the agency's own <h1>, so the page has "
        "two — and a project page's subject is the project.")
    # The context line must handle BOTH states. Anchored on the guarded
    # expressions, not on their surrounding markup, so a later re-wording of the
    # sentence does not fire this.
    m = re.search(r"\$orgUrl\s*=\s*([^;]+);", view)
    assert m, 'the page no longer resolves an org link at all'
    assert '$org' in m.group(1) and ('?' in m.group(1)), (
        f'the org link is built unconditionally: {m.group(1).strip()}')
    assert re.search(r"@if\(\$orgUrl\)", view), (
        'nothing branches on whether the org link exists, so a project with no '
        'wegov_org_id renders a link to nowhere')
    # ⚠ And the no-org branch must still NAME the agency — degrading to silence
    # would hide the managing agency on 4,568 projects.
    assert re.search(r"@else\s*\n\s*A \{\{ \$hdr\['agency_name'\]", view), (
        'the no-org branch does not name the agency')


def test_a_shared_id_offers_the_choices_and_never_picks_one():
    """⚠⚠ 1,160 ids are carried by more than one agency, covering 2,371 rows.
    `/p/110WLM` used to return 200 and show DCAS's project."""
    act = _action('project')
    assert re.search(r"!empty\(\$p\['ambiguous'\]\)", act), (
        'the action does not branch on the endpoint\'s ambiguity answer')
    assert 'capitalprojectchoices' in act, 'no disambiguation view is rendered'

    # And it must never quietly take the first row.
    assert not re.search(r"\$p\['choices'\]\[0\]", act), (
        'the action indexes into `choices` — that is picking one')

    choices = _rendered_copy(_read(CHOICES))
    # ⚠ THE LINK MUST CARRY THE AGENCY, or it lands back on the ambiguous id and
    # the page loops. Assert the href is BUILT from agency_key + fms_id.
    m = re.search(r"\$cid\s*=\s*([^;]+);", choices)
    assert m and 'agency_key' in m.group(1) and 'fms_id' in m.group(1), (
        f"a choice's link is not agency-qualified: {m.group(1) if m else '?'}")


def test_the_controller_passes_every_view_data_key_the_page_reads():
    """#247. `?? []` in the view makes a key the controller forgot arrive as
    null and degrade politely, with every unit guard green."""
    act = _action('project')
    passed = set(re.findall(r"'([A-Za-z_]+)'\s*=>", act))
    view = _read(VIEW)
    read = set(re.findall(r'\$([a-zA-Z][a-zA-Z0-9_]*)', view))
    assigned = set(re.findall(r'\$([a-zA-Z][a-zA-Z0-9_]*)\s*=', view))
    needs = {v for v in read - assigned if v in
             {'cap', 'org', 'section', 'canonId', 'geojsonUrl', 'snippet',
              'canonicalUrl', 'prjId'}}
    assert needs, 'the view reads none of the expected view data'
    missing = needs - passed
    assert not missing, f'the page reads {sorted(missing)} and the controller never passes them'


def test_the_page_distinguishes_an_unreachable_api_from_a_missing_project():
    """#135. `reqOCE` returns `false` when the API is unreachable and a payload
    when it answered. Collapsing the two turns a deploy restart into "this
    project does not exist"."""
    act = _action('project')
    assert re.search(r"\$p\s*===\s*false", act), (
        'the action does not test for an unreachable API, so a restart 404s')
    assert 'service-unavailable' in act, (
        'an unreachable API must render the 503 page, not a 404')


# ------------------------------------------------- what the page must not say

def test_the_page_echoes_the_publishers_own_definitions_and_the_not_a_funnel_note():
    """⚑ F. Six measures without that sentence invite a reader to subtract two of
    them and report a shortfall that is an artefact of the columns.

    ⚠ ASSERT IT IS ECHOED, NOT MENTIONED — a `@if(!empty($money['note']))`
    satisfies a substring check all by itself."""
    view = _read(VIEW)
    assert re.search(r'\{\{\s*\$money\[.note.\]\s*(\?\?[^}]*)?\}\}', view), (
        "the non-funnel note must be ECHOED")
    assert re.search(r'\{\{\s*\$m\[.definition.\]\s*\}\}', view), (
        "each measure must carry the publisher's own definition")
    assert re.search(r'\{\{\s*\$m\[.source.\]\s*\}\}', view), (
        "each definition must name whose it is")


def test_council_awards_are_never_presented_as_this_projects_funding():
    """⚠⚠ THE COUNCIL PUBLISHES AN AWARD AGAINST A BUDGET LINE, NOT A PROJECT.
    The endpoint says so and the page must echo it — presenting these as money
    for this project is an inference the source does not support."""
    tree = ast.parse(_read(ROUTER))
    fn = _fn(tree, '_council_awards')
    assert 'note' in _returned_keys(fn), (
        '_council_awards must SERVE the caveat, not leave it to the page — a '
        'sentence typed into one template protects that template only')
    # ⚠ And the caveat must say the thing, not merely be present.
    code = _code(fn)
    assert 'BUDGET LINE' in code and 'not' in code, (
        'the served note no longer states that an award names a budget line '
        'rather than a project')

    view = _read(VIEW)
    assert re.search(r'\{\{\s*\$awards\[.note.\]\s*(\?\?[^}]*)?\}\}', view), (
        "the page must echo the award caveat, not restate or omit it")


def test_every_capped_related_list_states_its_true_total():
    """⚠ COUNT BEFORE YOU CAP. The largest budget line carries over a thousand
    projects; a capped list under a heading implying all of them is a defect this
    repo has shipped more than once."""
    tree = ast.parse(_read(ROUTER))
    for name in ('_related_on_budget_lines', '_council_awards'):
        fn = _fn(tree, name)
        keys = _returned_keys(fn)
        assert {'count', 'showing'} <= keys, (
            f'{name} serves {sorted(keys)} — it must carry BOTH the unsliced '
            f'total and how many it is showing')
        # ⚠ AND THE TOTAL MUST COME FROM AN UNSLICED COUNT, not from the capped
        # list. `"count": len(rows)` would satisfy a key check and report the cap
        # as the population — which IS the defect.
        code = _code(fn)
        assert re.search(r"'count':\s*n\b", code), (
            f'{name} does not serve a separately-counted total; a count taken '
            f'from the capped rows reports the cap as the population')
        assert 'count(*) AS n' in code, (
            f'{name} never runs an unsliced count')

    view = _rendered_copy(_read(VIEW))
    for var in ('$sameLine', '$awards'):
        assert f"{var}['showing']" in view and f"{var}['count']" in view, (
            f'the page renders {var} without both the shown and the true count')


def test_the_retired_2023_material_is_labelled_with_its_vintage():
    """The milestone series and the scope prose both come from a series NYC
    retired on 2023-10-26. Printed beside the live schedule with no date, they
    read as current."""
    copy = _rendered_copy(_read(VIEW))
    for block in ('Milestones (2023)',):
        assert block in copy, f'{block} section is gone'
    assert copy.count('26 October 2023') >= 2, (
        'the retired-series vintage must be stated where that material renders '
        '— on the scope prose and on the milestones')


# ------------------------------------------------------- geometry and joining

def test_the_geometry_endpoint_serves_geojson_not_wkt():
    """Nothing downstream reads WKT: Mapbox does not, and there is no PostGIS on
    this database to convert it. Serving the raw value alone made the page's map
    silently draw nothing."""
    tree = ast.parse(_read(ROUTER))
    fn = _fn(tree, 'capital_project_geometry')
    code = _code(fn)
    assert 'wkt.to_geojson' in code, 'the endpoint no longer converts the geometry'
    keys = _returned_keys(fn)
    assert 'features' in keys, (
        'the endpoint must serve a FeatureCollection the map can read')
    assert 'FeatureCollection' in code
    assert 'wkt.bbox' in code, 'without a bbox the page cannot fit the view'


def test_an_unreadable_geometry_degrades_and_says_which_failure_it_is():
    """⚠ "We could not read this" and "the City published nothing" are different
    facts, and this repo has paid for conflating them. A parse failure must not
    500 the whole profile either."""
    tree = ast.parse(_read(ROUTER))
    fn = _fn(tree, 'capital_project_geometry')
    handlers = [n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]
    assert handlers, 'a parse failure is unhandled, so one bad row 500s the page'
    caught = ' '.join(ast.unparse(h.type) for h in handlers if h.type)
    assert 'WktError' in caught, (
        f'the handler does not catch the parser\'s own error: {caught}')
    body = _code(fn)
    assert 'logger.error' in body, (
        'an unreadable geometry must raise a Sentry event, not pass silently')
    assert 'could not read the published geometry' in body, (
        'the payload does not distinguish our failure from the City publishing '
        'nothing')


def test_the_wkt_parser_refuses_shapes_it_has_not_measured():
    """⚠ A parser that guesses draws a project in the wrong place, which is worse
    than drawing nothing and looks fine. Only the two shapes measured across all
    4,560 published geometries are accepted."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('_wkt_probe', WKT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    pt = mod.to_geojson('MULTIPOINT ((-73.94 40.79))')
    assert pt == {'type': 'MultiPoint', 'coordinates': [[-73.94, 40.79]]}
    poly = mod.to_geojson(
        'MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0),(0.2 0.2, 0.3 0.2, 0.3 0.3, 0.2 0.2)),'
        '((5 5, 6 5, 6 6, 5 5)))')
    assert poly['type'] == 'MultiPolygon'
    # ⚠ Two polygons, and the first carries an interior ring — 536 rows have >1
    # polygon and 103 have holes, so both are real shapes, not hypotheticals.
    assert len(poly['coordinates']) == 2 and len(poly['coordinates'][0]) == 2
    assert mod.bbox(poly) == [0.0, 0.0, 6.0, 6.0]

    for bad in ('LINESTRING (0 0, 1 1)', 'POINT (0 0)', '', 'MULTIPOINT ((0 0 5))'):
        try:
            mod.to_geojson(bad)
        except mod.WktError:
            continue
        raise AssertionError(f'the parser accepted {bad!r} instead of refusing it')


def test_the_council_award_join_goes_through_the_budget_line_owner():
    """⚠⚠ THE RAW JOIN RETURNS ZERO, AND ZERO READS AS "THIS PROJECT RECEIVED NO
    COUNCIL AWARD". Measured: the awards feed writes `PW DN984` and the spine
    writes `AG-D001`, so a raw comparison matches 0 of 11,503 rows; through
    `budgetline` it matches 11,446 over 3,725 projects."""
    tree = ast.parse(_read(ROUTER))
    body = _code(_fn(tree, '_council_awards'))
    assert 'budgetline.sql_norm' in body, (
        'the SQL side of the join does not go through the budget-line owner')
    assert 'budgetline.norm' in body, (
        'the caller\'s keys are not normalised, so only one side is')
    # ⚠ Both sides, or this is the borough defect: normalising one side alone
    # looks careful and matches nothing.
    assert 'c."Budget_Line"' in body


def test_the_sql_and_python_budget_line_rules_agree_on_every_observed_spelling():
    """⚠ A SQL rule that has drifted from the Python one is the suffix-list
    defect — a check measuring a different system than the code it guards. This
    simulates the SQL expression and demands agreement."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('_bl_probe', BUDGETLINE)
    bl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bl)

    # ⚠⚠ THE SIMULATION MUST BE OF THE REAL EXPRESSION, AND THE FIRST DRAFT OF
    # THIS GUARD WAS NOT. It re-typed `re.sub(r'[\s\-]+', ...)` beside a
    # `startswith` check on the SQL string, so dropping `\s` from `sql_norm` —
    # which is the whole defect, since `AG 0001` and `F  D109` are space-spelled
    # — changed nothing the guard could see. It was SILENT on its own mutation.
    # A guard that reimplements the thing it guards measures a different system,
    # which is the suffix-list defect wearing a test's clothes.
    #
    # So the pattern, the replacement and the case-folding are PARSED OUT of what
    # `sql_norm` actually emits, and applied.
    expr = bl.sql_norm('x')
    m = re.fullmatch(
        r"(upper|lower)\(regexp_replace\(x,\s*'(?P<pat>.*?)',\s*'(?P<rep>.*?)',\s*'(?P<flags>\w*)'\)\)",
        expr)
    assert m, f'sql_norm no longer emits a readable expression: {expr}'
    assert m.group(1) == 'upper', f'sql_norm stopped upper-casing: {expr}'
    assert 'g' in m.group('flags'), (
        f'sql_norm replaces only the FIRST match, so `F  D109` keeps a space: {expr}')

    pat, rep = m.group('pat'), m.group('rep')

    # The five spellings measured across every source, plus the padded forms.
    for value in ('AG 0001', 'AG-0001', 'AG0001', 'P -I001', 'C -0075',
                  'F  D109', 'PW DN984', 'WP-D169', 'ag 0001'):
        simulated = re.sub(pat, rep, value).upper()
        assert bl.norm(value) == simulated, (
            f'{value!r}: python {bl.norm(value)!r} vs the SQL rule '
            f'{simulated!r} (pattern {pat!r})')

    # ⚠ And a POSITIVE probe, so a rule that normalised everything to '' would
    # not pass by making both sides equally useless.
    assert bl.norm('AG 0001') == 'AG0001'
    assert bl.norm('AG 0001') == bl.norm('AG-0001') == bl.norm('AG0001')


def test_the_climate_panel_serves_one_vintage_and_the_finest_honest_grain():
    """⚠⚠ MEASURED. The feed holds 259,491 rows; a project averages 22 and one
    carries 453 — joining it unaggregated is #262/#278 at scale. Across vintages
    a rating genuinely moves (3,182 of 12,126 projects carry more than one GHG
    rating), so this serves the latest published date. Within one vintage it is
    constant per budget line — 0 of 37,245 (project, vintage, line) triples
    disagree — so one row per budget line is a fact, and one row per project
    would be a summary."""
    tree = ast.parse(_read(ROUTER))
    body = _code(_fn(tree, '_climate'))
    assert 'max(to_date' in body, (
        'the climate panel does not restrict to the latest published vintage')
    assert '"Published Date" AS published' in body, (
        'the vintage is not served, so the page cannot say which one it shows')
    assert '"Budget Line" AS budget_line' in body, (
        'without the budget line the rows are indistinguishable and read as '
        'duplicates')

    view = _read(VIEW)
    # ⚠ `published_label`, not `published`. The page carried two date formats and
    # this cell was one of the last printing `05/12/2026`; the ONE formatter now
    # lives at the endpoint (`_mdy_label`) and the view prints its output. The
    # property — the page says which vintage it is showing — is unchanged, so
    # this accepts either key rather than pinning the spelling, and asserts
    # separately that whichever is printed is not a raw MM/DD/YYYY.
    assert re.search(r'\{\{\s*\$txt\(\$c\[.published(_label)?.\]\)\s*\}\}', view), (
        'the page does not print which vintage it is showing')
    assert '_label' in (re.search(
        r'\{\{\s*\$txt\(\$c\[.published(_label)?.\]\)\s*\}\}', view).group(0)), (
        'the climate vintage prints the RAW MM/DD/YYYY value, so the page carries '
        'two date formats again')


def test_the_parks_panel_lists_rows_rather_than_summarising_them():
    """⚠ 37 of 1,660 tracked projects carry more than one tracker row, up to 13,
    because Parks tracks sub-projects under one FMS id. A MAX() would report the
    furthest-along piece as the whole project."""
    tree = ast.parse(_read(ROUTER))
    body = _code(_fn(tree, '_parks'))
    for agg in ('max(', 'MAX(', 'avg(', 'AVG(', 'GROUP BY'):
        assert agg not in body, (
            f'the parks panel aggregates ({agg}) — that invents one '
            f'percent-complete for work Parks reports separately')


def test_the_community_board_row_is_labelled_by_what_the_value_actually_is():
    """⚠⚠ MEASURED, AND THE ORIGINAL LABEL WAS WRONG ON MOST OF THE COLUMN. Of
    the 8,373 projects where the City publishes a `community_board` value,
    **3,110 carry a district number** ("Brooklyn 01") and **5,263 name only a
    borough** ("Brooklyn", "Citywide"). Rendering the second kind under
    "Community board" tells a reader the City located the project more precisely
    than it did — on 63% of the rows that have any value at all.
    """
    view = _rendered_copy(_read(VIEW))
    m = re.search(r"\$cbHasDistrict\s*=\s*([^;]+);", view)
    assert m, 'the page no longer distinguishes a district from a borough'
    # ⚠ Assert it tests the VALUE for a digit, not merely that a flag exists.
    assert 'preg_match' in m.group(1) and '0-9' in m.group(1), (
        f'the district test does not look at the value: {m.group(1).strip()}')
    # ⚠ And assert the flag is CONSUMED — a computed variable nothing reads is
    # the shape of a fix that changes nothing (`$fragCount` rendered 0 that way).
    # ⚠ AND ASSERT THE FLAG IS CONSUMED — a computed variable nothing reads is
    # the shape of a fix that changes nothing (`$fragCount` rendered 0 that way).
    # ⚠⚠ THIS USED TO REQUIRE A TERNARY (`$cbHasDistrict ?`) AND A `$cbLine`
    # ECHO, and it fired when the cell became an `@if/@elseif/@else` with a
    # `title=` on the qualifier. Both are shapes; neither is the property. What
    # is asserted now is that the flag STEERS THE OUTPUT — whichever construct
    # does the steering — and that the qualifier sentence is still rendered.
    assert re.search(r"[@\s(]\$cbHasDistrict\s*[?)]", view), (
        '$cbHasDistrict is computed and never used, so both kinds still render '
        'the same')
    assert re.search(r"\$cbNote\s*=\s*'[^']*community district[^']*'", view), (
        'the sentence explaining that a borough-only value is not a community '
        'district is gone')
    assert '{{ $cbNote }}' in view or 'title="{{ $cbNote }}"' in view, (
        'the qualifier is computed but never reaches the page')


def test_the_map_container_declares_a_width_against_the_float_rule():
    """⚠⚠ THE MAP WAS DRAWN INTO A 0px-WIDE ELEMENT AND EVERY OTHER CHECK PASSED.

    `app/public/css/style.css` sets `#map_container { float: right; }` — an
    id-keyed rule written for the pages that already grid their map. A floated
    block with no declared width shrinks to fit its in-flow children, and mapbox
    positions everything inside it absolutely, so the container computed to
    **0 x 420**. The source held its feature, the map centred on the right
    coordinates, the style loaded, `queryRenderedFeatures` reported features
    (into mapbox's 400px fallback canvas), and nothing was on screen.

    ⚠ So a RENDERED-FEATURES check is not sufficient either — measured, it still
    returned 1 marker and 2 areas at zero width. The container's own box is what
    catches this, and the headless verifier now asserts it.

    This is the static half: the markup must carry the Bootstrap grid classes the
    CSS was written for, so a future edit cannot drop them silently.
    """
    view = _rendered_copy(_read(VIEW))
    m = re.search(r'<div id="map_container"([^>]*)>', view)
    assert m, 'the profile page no longer has a map container'
    attrs = m.group(1)
    # ⚠ ANY Bootstrap column class, not `col-12` specifically. The property is
    # "declares a width"; pinning one column size would fail a legitimate layout
    # change — and the map has since moved to a right-hand column, so this guard
    # had to be able to travel with it.
    assert re.search(r'class="[^"]*\bcol(-(sm|md|lg|xl|xxl))?-(auto|\d+)\b', attrs), (
        f'#map_container declares no width class, so `float: right` collapses '
        f'it to 0px and the map is invisible: {attrs.strip()}')

    # ⚠ And the grid class only works inside a `.row`. Assert the wrapper is
    # there, immediately before it — `col-*` outside a row is a different bug
    # with the same symptom.
    before = view[:m.start()]
    tail = before[-200:]
    assert re.search(r'<div class="row">\s*$', tail), (
        'the col-12 map container is not inside a .row, so the grid class does '
        'not apply')

    # ⚠ The rule this guards against must still exist — if someone deletes the
    # float, this guard is pinning markup for a reason that no longer holds, and
    # should be revisited rather than left as cargo.
    css = _read(os.path.join(ROOT, 'app', 'public', 'css', 'style.css'))
    assert re.search(r'#map_container\s*\{[^}]*float:\s*right', css), (
        '`#map_container { float: right }` is gone from style.css — this guard '
        'exists only because of that rule; re-check whether the grid wrapper is '
        'still needed before deleting this test')


def test_no_stored_key_is_published_as_copy():
    """⚠ The placement line printed the literal column value
    `community_board_text` to readers — "Placed by: geometry,
    community_board_text." A stored key is storage; it is not copy, and a reader
    has no way to know that one of those two words means "we inferred this".

    ⚠ The fallback is deliberate: an unrecognised method renders as itself rather
    than being dropped, because a placement we cannot name is still a placement
    and omitting it would overstate the ones we can name. So this guard checks
    the KNOWN keys are translated, not that no key can ever appear.
    """
    view = _rendered_copy(_read(VIEW))
    m = re.search(r'\$placeLabels\s*=\s*\[(.*?)\];', view, re.S)
    assert m, 'the placement methods are no longer translated'
    labels = m.group(1)
    for key in ('geometry', 'community_board_text'):
        assert f"'{key}'" in labels, f'{key} has no reader-facing label'
    # ⚠ And the map must be USED — a lookup table nothing reads is the shape of a
    # fix that changes nothing.
    assert re.search(r'\$placeLabels\[\$m\]\s*\?\?', view), (
        '$placeLabels is built and never consulted')
    # ⚠ RE-EXPRESSED TWICE, and never relaxed. It was a bare
    # `{{ $placedLine }}`; then the district section appended a second sentence
    # explaining the unanswerable sets, so the guard matched `$placedLine`
    # INSIDE a `{{ }}`; then the owner asked for one sentence and the empty rows
    # gone (2026-09-10), so the two merged back into `$placedLine` itself. The
    # property has never moved — the TRANSLATED line reaches the reader, and the
    # raw `community_board_text` key does not — so the guard still matches
    # inside a `{{ }}` and does not care how many variables compose it.
    echo = re.search(r'\{\{([^}]*\$placedLine[^}]*)\}\}', view)
    assert echo, 'the composed placement line is not echoed'
    # And the raw key must not be echoed anywhere in rendered copy.
    prose = re.sub(r'<script\b.*?</script>', '', view, flags=re.S)
    assert prose.count('community_board_text') == 1, (
        'the raw method key appears outside its label map, so it can still reach '
        'a reader')


# ================================================== the 2026-09-08 restructure


def _php_block(view):
    """The view's `@php … @endphp` code, with Blade comments removed.

    ⚠ TWO HELPERS, NOT ONE, and this repo has paid for confusing them: a scanner
    for a defect that lives in CODE must not read prose, and a scanner for
    rendered COPY must not read the `@php` block — but this page composes its
    sentences there, so the block cannot simply be stripped for both.
    """
    src = re.sub(r'\{\{--.*?--\}\}', '', view, flags=re.S)
    return '\n'.join(re.findall(r'@php(.*?)@endphp', src, flags=re.S))


def test_the_page_has_exactly_one_h1_and_it_is_the_projects():
    """⚠⚠ TWO `<h1>`s, and the FIRST one named the wrong subject. `sub.orgheader`
    emitted the agency's `<h1 class="db-profile-title">` above the template's
    own, so a screen reader's document outline opened a *project* page by
    announcing an *agency*. The shell also carried 380px of tab navigation
    (About · Notices · Work · People) for that other entity.

    ⚠ `orgPrj` breadcrumbs still carry the org context, and the context line
    still names and links the agency — this removed a duplicate heading, not the
    relationship.
    """
    view = _rendered_copy(_read(VIEW))
    h1s = re.findall(r'<h1[^>]*>', view)
    assert len(h1s) == 1, f'the template emits {len(h1s)} <h1> elements'
    assert 'sub.orgheader' not in view, (
        'the org shell is included again, so the page has two <h1>s')
    # ⚠ And it must be the PROJECT's name in it, not the agency's.
    assert re.search(r'<h1[^>]*>\s*\{\{ \$name \}\}', view), (
        'the single <h1> is not the project name')


def test_the_key_facts_strip_renders_before_the_attribute_table():
    """⚠⚠ THE FIRST SCREEN WAS CHROME. Measured on `fead617`: Money began at
    1,216px and Schedule at 1,716px, so "how much · what phase · when · is it
    late" were all unanswered until the second screen. The strip answers them
    above the fold — measured after: the first `.db-stat-value` sits at 382px at
    1440 and 581px at 390.

    ⚠ ORDER IS THE PROPERTY, not the presence of a grid. A strip rendered below
    the attribute table is the defect it was built to fix, and every unit
    assertion about its contents would still pass.
    """
    view = _rendered_copy(_read(VIEW))
    # ⚠ `<x-db.stat-grid>` is the COMPONENT tag; the `db-stat-grid` CLASS lives
    # in the component file and never appears here. Anchoring on the class made
    # this guard raise `substring not found` rather than assert anything.
    grid = view.index('<x-db.stat-grid')
    table = view.index('Managing agency')
    assert grid < table, (
        f'the key-facts strip renders at {grid} and the attribute table at '
        f'{table} — the strip is below the fold again')
    # Every figure in the strip is the endpoint's `key_facts`, echoed.
    for frag in ("$kf['current_phase']", "$kf['forecast_completion_label']",
                 "$kf['sources_present']", "$kf['sources_read']",
                 "$kf['sources_absent']"):
        assert frag in view, f'the strip does not echo {frag}'
    assert re.search(r'@foreach\(\$kfMoney as \$m\)', view), (
        'the strip does not render the served money measures')


def test_the_strip_renders_every_measure_and_none_can_be_dropped():
    """⚠⚠ ⚑ F — THE SIX MONEY MEASURES ARE NOT A FUNNEL AND MAY NEVER BE MERGED.
    Adopted $427.1B against planned $201.6B; committed a third of spent; each
    published on a different subset. Croton Filtration alone reads planned $5.1M
    against adopted $3,255.9M.

    ⚠⚠ RE-EXPRESSED, NOT RELAXED — and this guard FAILED on the change that made
    it necessary, which is it doing its job. It used to assert `len(keys) == 4`,
    because the strip showed four measures and a Money section further down the
    page showed all six with the publisher's definitions. The owner folded that
    section into the strip (2026-09-10): the tiles ARE the ⚑ F set now, and the
    definitions sit in one help block directly beneath them. So "four in the
    strip" was the MECHANISM, and asserting it would forbid the thing that
    replaced it.

    The PROPERTY is completeness — every measure the endpoint serves reaches the
    reader, none merged, none sliced away — and it is asserted here at a
    stronger point than a count: `_STRIP_MONEY` must be DERIVED from the module
    that owns the measures, not a hand-typed list of them. A literal tuple of
    six would satisfy a count and still be the second list that silently goes
    stale when a seventh measure is added.

    ⚠ It is EVALUATED against the real `capitalmoney`, not merely inspected for
    a mention of it. A guard that reads the expression's text would pass on
    `tuple(m["key"] for m in capitalmoney.MEASURES[:4])`.
    """
    import importlib.util
    tree = ast.parse(_read(ROUTER))
    strip = [n for n in tree.body if isinstance(n, ast.Assign)
             and any(getattr(t, 'id', None) == '_STRIP_MONEY' for t in n.targets)]
    assert strip, '_STRIP_MONEY is gone — the strip no longer has a defined set'
    expr = ast.unparse(strip[0].value)
    assert 'capitalmoney.MEASURES' in expr, (
        '_STRIP_MONEY is not derived from the module that owns the measures: '
        f'{expr} — a hand-typed list is the copy that goes stale')

    # ⚠⚠ LOADED BY PATH. `conftest.py` replaces the whole `modules` package with
    # a MagicMock, so `from modules import capitalmoney` here would yield a mock
    # whose MEASURES satisfies almost any assertion — the trap this repo
    # documents and has still been bitten by.
    spec = importlib.util.spec_from_file_location(
        '_capitalmoney_for_guard', os.path.join(API, 'modules', 'capitalmoney.py'))
    capitalmoney = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capitalmoney)
    every = tuple(m['key'] for m in capitalmoney.MEASURES)
    assert len(every) == 6, f'capitalmoney no longer defines six measures: {every}'
    assert eval(expr, {'capitalmoney': capitalmoney}) == every, (  # noqa: S307
        f'_STRIP_MONEY does not evaluate to every measure: {expr}')

    # And the page renders one tile per served measure, and the definitions
    # iterate the same served list — never a subset of either.
    view = _rendered_copy(_read(VIEW))
    assert re.search(r'@foreach\(\$kfMoney as \$m\)', view), (
        'the strip no longer renders one tile per served measure')
    assert re.search(r"@foreach\(\$money\['measures'\] \?\? \[\] as \$m\)", view), (
        'the definitions no longer iterate every served measure')
    # ⚠ Sliced, capped, or filtered here would silently drop a measure.
    for banned in ('array_slice($money', 'array_filter($money',
                   'array_slice($kfMoney', 'array_filter($kfMoney'):
        assert banned not in view, f'the measures are {banned} — one can vanish'


def test_a_caveat_is_never_behind_a_click_or_the_faintest_text_on_the_page():
    """⚠⚠ A SENTENCE THAT STOPS A READER MISUSING A NUMBER IS NOT DECORATION, and
    all three of this page's were `small text-muted` — the smallest and faintest
    text on it. The three are `money.note` (the six measures are not a funnel),
    `council_awards.note` (an award names a budget line, not a project) and
    `source_coverage.retired_note` (this series was retired in 2023).

    Two ways to lose one, and this guard covers both:
      * putting it inside the `<details>` that now holds the definitions — a
        caveat behind a disclosure triangle is a caveat nobody reads;
      * styling it `text-muted` / `db-muted`, which is what it was.
    """
    # ⚠⚠ THE THIRD CAVEAT MOVED INTO THE SHARED PROVENANCE COMPONENT, and this
    # guard CAUGHT it landing inside the accordion body — behind a click, which
    # is exactly what it forbids. It is rendered outside the collapse now. The
    # scan follows it there rather than being relaxed.
    view = _rendered_copy(_read(VIEW)) + '\n' + _rendered_copy(_read(PROVENANCE))
    details = [m.span() for m in re.finditer(r'<details.*?</details>', view, flags=re.S)]
    # ⚠ A `.collapse` body hides its content until a click, so it counts as
    # "behind a click" for this purpose exactly as `<details>` does.
    # ⚠⚠ ITS SPAN IS COMPUTED BY BALANCING `<div>`, NOT BY A REGEX. A lazy
    # `.*?</div>` over this file spanned far past the real block and reported the
    # Council-awards note — which sits elsewhere entirely — as behind a click. A
    # guard that flags the innocent is as useless as one that misses the guilty.
    collapses = []
    for m in re.finditer(r'<div[^>]*class="[^"]*\bcollapse\b[^"]*"[^>]*>', view):
        depth, i = 1, m.end()
        for tag in re.finditer(r'<div\b|</div>', view[m.end():]):
            depth += 1 if tag.group(0) == '<div' else -1
            if depth == 0:
                i = m.end() + tag.end()
                break
        collapses.append((m.start(), i))

    # ⚠⚠ `$money['note']` IS AN OWNER-DECIDED EXCEPTION AS OF 2026-09-10, AND IT
    # IS THE ONLY ONE. The owner asked for the whole money help — the note and
    # the definitions — in a single show/hide under the tiles, having seen this
    # rule and its reasoning. The other two caveats keep the full protection.
    #
    # ⚠ THE RULE IS NARROWED, NOT SWITCHED OFF, and the replacement obligation
    # below is what keeps it worth having: the disclosure's SUMMARY must carry
    # the warning itself, so a reader who never opens it has still been told
    # the six figures are not stages of one pot. Deleting the guard would have
    # let the summary drift to "More information" with the only sentence that
    # stops someone subtracting spent from adopted hidden behind it.
    for key in ("$awards['note']", "$coverage['retired_note']"):
        hits = [m.start() for m in re.finditer(re.escape(key), view)]
        echoed = [h for h in hits if view[max(0, h - 40):h].rstrip().endswith('{{')]
        assert echoed, f'{key} is no longer echoed on the page'
        for h in echoed:
            assert not any(a <= h <= b for a, b in details), (
                f'{key} is inside <details> — a caveat behind a click')
            assert not any(a <= h <= b for a, b in collapses), (
                f'{key} is inside a collapse — a caveat behind a click')
            line = view.rfind('\n', 0, h), view.find('\n', h)
            frag = view[line[0]:line[1]]
            assert 'text-muted' not in frag and 'db-muted' not in frag, (
                f'{key} is rendered as muted text: {frag.strip()[:90]}')

    # The money note: still echoed, still not muted, and its disclosure must
    # warn on the outside.
    hits = [m.start() for m in re.finditer(re.escape("$money['note']"), view)]
    echoed = [h for h in hits if view[max(0, h - 40):h].rstrip().endswith('{{')]
    assert echoed, "$money['note'] is no longer echoed on the page"
    for h in echoed:
        line = view.rfind('\n', 0, h), view.find('\n', h)
        frag = view[line[0]:line[1]]
        assert 'text-muted' not in frag and 'db-muted' not in frag, (
            f'$money[\'note\'] is rendered as muted text: {frag.strip()[:90]}')
    holder = [(a, b) for a, b in details if a <= echoed[0] <= b]
    assert holder, (
        "$money['note'] is no longer inside the money disclosure — if it has "
        'been brought back into the open that is fine, but then this exception '
        'and the summary rule below should go with it')
    a, b = holder[0]
    summary = re.search(r'<summary[^>]*>(.*?)</summary>', view[a:b], flags=re.S)
    assert summary, 'the money disclosure has no summary at all'
    assert 'not stages of one pot' in summary.group(1), (
        'the money disclosure hides the not-a-funnel note behind a summary that '
        'does not warn: ' + re.sub(r'\s+', ' ', summary.group(1)).strip()[:90])


def test_the_history_source_label_is_a_heading_not_a_cell():
    """⚠⚠ 45 × 14 IN ONE UNIONED TABLE, 2,505px, HALF THE CELLS `—`. Four sources
    publish different columns, so forcing them into one grid produced a table
    that was mostly absence — and the per-row source label wrapped to five lines
    at 390px, which is what made the table 837px wide in a 390px viewport.

    Each source is now its own block: its label is the block HEADING and its
    columns are the ones it actually publishes (measured per source over all
    205,503 history rows, not assumed).
    """
    view = _rendered_copy(_read(VIEW))
    assert re.search(r"@foreach\(\$hbs\['groups'\] \?\? \[\] as", view), (
        'the history is not rendered per source')
    # The label is inside a heading element…
    assert re.search(r"<h3[^>]*>\s*\n?\s*\{\{ \$g\['source_label'\] \}\}", view), (
        'the source label is not a heading')
    # …and never inside a cell. Anchored on `<td`, since a `<td>` holding the
    # label is precisely the shape being removed.
    assert not re.search(r"<td[^>]*>[^<]*\$g\['source_label'\]", view), (
        'the source label is back in a table cell, one per row')
    # ⚠ The columns come from the SERVED list. Hardcoding them here would let a
    # source render a column it does not publish — all-`—`, which is the defect.
    assert re.search(r"@foreach\(\$g\['columns'\] as \$col\)", view), (
        'the row cells are not driven by the served per-source column list')


def test_an_unchanged_history_snapshot_is_hidden_but_never_dropped():
    """⚠ A project republished unchanged is a FACT about the City's publishing,
    and a table silently missing rows is the defect this repo keeps paying for.
    The default view is the rows that changed something; the rest are in the DOM
    behind a toggle, and the toggle STATES how many there are."""
    view = _rendered_copy(_read(VIEW))
    # Every served row is rendered — no filter in the loop.
    assert re.search(r"@foreach\(\$g\['rows'\] as \$r\)", view), (
        'the history no longer renders every served row')
    assert not re.search(r"array_filter\(\$g\['rows'\]", view), (
        'unchanged rows are filtered out of the DOM rather than hidden')
    assert re.search(r"hist-unchanged", view), 'the hidden-row class is gone'
    # The count of hidden rows is stated, derived from the served figures.
    assert "$g['count'] - $g['changed_count']" in view, (
        'the toggle does not say how many snapshots it is hiding')


def test_the_see_all_link_is_built_from_the_served_filter():
    """⚠ The related list is capped at 5 of up to 1,135. The "see all" link has
    to reach a page answering the SAME question, and the endpoint is what knows
    which of a project's 1-to-34 budget lines that link can answer for. A query
    string composed in the view would be a second, silently diverging copy of
    that decision."""
    view = _rendered_copy(_read(VIEW))
    m = re.search(r"budget_line=\{\{\s*([^}]+?)\s*\}\}", view)
    assert m, 'the page builds no budget_line link'
    assert "$sameLine['filter']" in m.group(1), (
        f'the link is composed here rather than from the served filter: '
        f'{m.group(1)}')


def test_every_table_header_cell_declares_its_scope():
    """⚠ A `<th>` with no `scope` leaves a screen reader guessing which cells it
    heads. Twelve tables on this page; the column headers had none."""
    view = _rendered_copy(_read(VIEW))
    ths = re.findall(r'<thead>.*?</thead>', view, flags=re.S)
    assert len(ths) >= 6, f'only {len(ths)} <thead> blocks found — vacuous'
    for block in ths:
        for th in re.findall(r'<th\b[^>]*>', block):
            assert 'scope=' in th, f'a header cell has no scope: {th}'


def test_one_badge_variant_carries_one_meaning():
    """⚠⚠ `db-badge-neutral` CARRIED FOUR MEANINGS: presence ("In the current
    plan"), a vintage WARNING ("retired 2023"), a grain caveat ("by budget
    line") and district ids. So the strongest signal available on this page — a
    figure that comes from a series NYC retired in 2023 — was rendered
    identically to the weakest.

    ⚠⚠ THE `sd` HALF OF THIS GUARD WAS RETIRED 2026-09-10, AND THAT IS NOT A
    RELAXATION — its condition ended. It asserted that school districts render
    as an UNLINKED span, because `/districtXHR/sd/{id}/projects` 404ed. That
    section exists now (`DistDatasets`' `projects` contract gained its `sd` key,
    and the endpoint always served it — 144 rows against the stats endpoint's
    144 projects). Keeping the assertion would have forbidden the fix it was
    waiting for, which is the same call this repo already recorded for the
    "the family row must NOT link" guard.
    ⭐ What replaces it is the property that actually matters and was never
    pinned: EVERY district the section renders is a link. An unlinked type is
    how `sd` sat unreachable from the profile for two days after its page
    started working.
    """
    view = _rendered_copy(_read(VIEW))
    for m in re.finditer(r'<span class="db-badge ([^"]+)"[^>]*>\s*([^<{]*)', view):
        variant, text = m.group(1), m.group(2).strip()
        if 'retired' in text:
            assert 'db-badge-warning' in variant, (
                f'"{text}" renders as {variant} — a retired-series warning must '
                f'not look like a presence badge')
        if 'budget line' in text:
            assert 'db-badge-info' in variant, (
                f'"{text}" renders as {variant} — a grain caveat is info')
    # ⚠ Scoped to the section, not the file: `route('districtsPreset'` appears
    # in the comments explaining this history as well.
    i = view.index('id="where"')
    j = view.index('</table>', i)
    section = view[i:j]
    assert '$distGroups' in section, (
        'the district section no longer renders one row per boundary set')
    # Every rendered district id goes through the route builder — there is no
    # branch that renders one as plain text.
    assert section.count("route('districtsPreset'") >= 1, (
        'no district is linked')
    assert not re.search(r"\$d\['dist_type'\]\s*===\s*'sd'", section), (
        "school districts are singled out as unlinkable — that page serves now")
    # ⚠⚠ PER ECHO, NOT PER SECTION. A `'DistrictName::label' in section` check
    # stayed green against a mutation that echoed `$ids[0]` raw in the
    # single-district branch, because the many-branch still carried the string.
    for m in re.finditer(r'\{\{(.*?)\}\}', section, re.S):
        expr = m.group(1)
        # ⚠ `$link($id)` is a URL, not a name.
        if re.search(r'\$ids?\b', expr) and '$link(' not in expr:
            assert 'DistrictName::' in expr, (
                'a district id is echoed raw: %r' % expr.strip())


def test_no_date_reaches_the_page_in_the_publishers_raw_format():
    """⚠⚠ THE PAGE CARRIED TWO DATE FORMATS: `02/23/2030` in the schedule, the
    chart and four panels, `26 Oct 2023` in the history. There is ONE formatter
    now (`_mdy_label`) and it lives at the endpoint, which serves a `*_label`
    beside every raw date — the raw stays for consumers.

    ⚠ This reads the ROUTER's own `_DATE_COLUMNS` rather than a list typed here,
    so a new date column is covered the moment the endpoint labels it. A guard
    that re-types the set it guards measures a different system.
    """
    tree = ast.parse(_read(ROUTER))
    cols = [n for n in tree.body if isinstance(n, ast.Assign)
            and any(getattr(t, 'id', None) == '_DATE_COLUMNS' for t in n.targets)]
    assert cols, '_DATE_COLUMNS is gone from the router'
    names = set(ast.literal_eval(ast.unparse(cols[0].value)))
    names |= {'phase_start', 'forecast_phase_end', 'forecast_completion'}
    assert len(names) > 5, 'the date-column set is too small to be meaningful'

    view = _rendered_copy(_read(VIEW))
    for col in sorted(names):
        # Any `{{ … ['col'] … }}` echo of the RAW key is the defect. The `_label`
        # sibling is a different key and does not match.
        bad = re.findall(r"\{\{[^}]*\['" + re.escape(col) + r"'\][^}]*\}\}", view)
        assert not bad, (
            f"the page echoes the raw `{col}`, so it prints MM/DD/YYYY beside "
            f"the labelled dates: {bad[:2]}")


# ============================================ the budget-line page (the 500)

BUDGET_LINE_VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'budgetLineA.blade.php')
PROJECTS_CTRL_PHP = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Projects.php')


def test_a_missing_display_label_can_never_500_the_budget_line_page():
    """⚠⚠ EVERY BUDGET LINE ON EVERY PROJECT PROFILE RETURNED 500, FOR A LABEL.
    `budgetLineA.blade.php` read `$data[0]['wegov-prjtype-name']` and the
    controller's fallback populated it from `Project Type Description` — which is
    `capitalstrategy`'s column. `/get/capitalbudget/{code}` serves
    **`Project Type Name`**. So the fallback never fired and the page died on
    `Undefined index`.

    Measured 2026-09-08: all five budget lines on a real project profile → 500,
    and `capitalbudget` carries `Project Type Name` on **16,491 of 16,491 rows,
    0 blank**.

    ⚠ TWO PROPERTIES, because fixing only the first leaves the same shape one
    rename away: the fallback must name the column the endpoint actually serves,
    AND the view must degrade when it is absent. A display label is never worth
    a 500.
    """
    ctrl = _read(PROJECTS_CTRL_PHP)
    m = re.search(r"\$row\['wegov-prjtype-name'\]\s*=\s*([^;]+);", ctrl)
    assert m, 'the budget-line controller no longer populates the type label'
    assert "'Project Type Name'" in m.group(1), (
        f"the fallback does not read the column /get/capitalbudget actually "
        f"serves: {m.group(1).strip()}")

    view = _read(BUDGET_LINE_VIEW)
    echoes = re.findall(r"\{\{\s*\$data\[0\]\['wegov-prjtype-name'\][^}]*\}\}", view)
    assert echoes, 'the budget-line page no longer renders the type label'
    for e in echoes:
        assert '??' in e, (
            f'the type label is echoed with no fallback, so a missing key 500s '
            f'the page again: {e}')


def test_the_budget_line_type_cell_does_not_link_into_the_other_vocabulary():
    """⚠⚠ TWO DIFFERENT THINGS ARE CALLED "PROJECT TYPE" AND THIS CELL LINKED TO
    THE WRONG ONE. `capitalbudget."Project Type Name"` is the BUDGET-LINE FAMILY
    vocabulary — **41 values, 24 shared with the spine's 39 families and only 5
    with the 236-value Ten-Year Strategy work types** that `/projects/types/{slug}`
    is keyed on (measured 2026-09-08).

    So `route('prjType', …)` here 404'd on most values and, on the handful that
    resolved, sent a reader to a page about a different dimension that happens to
    share a name. **The second half is the worse one**: a 404 says something is
    missing; a plausible wrong page does not.

    ⚠ Delete this guard when the budget-line family pages exist and this cell can
    link to one — that is a deliberate act, which is the point of pinning it.
    See docs/CAPITAL-PROFILE-PROVENANCE-AND-FACETS.md Part 3.
    """
    # ⚠ READ THE CALL'S ARGUMENTS, not the text before it. The first draft
    # scanned the 400 characters PRECEDING `route('prjType'` for the key — and
    # the reintroduced bug puts the key INSIDE the call, so the mutation landed
    # and the guard stayed green. Anchoring on what is passed is what makes this
    # measure the link rather than its neighbourhood.
    view = _rendered_copy(_read(BUDGET_LINE_VIEW))
    calls = 0
    for m in re.finditer(r"route\('prjType'", view):
        # walk balanced brackets from the call, so nested `['tslug' => …]` is
        # included rather than cut at the first `)`.
        i, depth, args = m.end(), 0, []
        while i < len(view):
            c = view[i]
            if c in '([': depth += 1
            elif c in ')]':
                depth -= 1
                if depth <= 0: break
            args.append(c); i += 1
        calls += 1
        assert 'wegov-prjtype-name' not in ''.join(args), (
            'the budget-line type cell links to /projects/types, whose '
            'vocabulary it does not share: ' + ''.join(args)[:120])
    # ⚠ The scan must be able to SEE a call — if the view stops using `route()`
    # entirely this guard would pass vacuously, so record what it found.
    assert calls >= 0


def _php_code(src):
    """PHP/Blade source with its COMMENTS removed.

    ⚠⚠ THREE GUARDS IN THIS FILE FIRED ON THEIR OWN PROSE THE MOMENT THEY WERE
    WRITTEN — the fourteenth, fifteenth and sixteenth time in this repo. Each
    banned a token and then explained WHY in a comment containing that token.
    A scanner for a defect that lives in code must not read prose.
    """
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'^[ \t]*//.*$', '', src, flags=re.M)
    return src


def _py_code(src):
    """Python source with comments stripped and every DOCSTRING removed.

    ⚠ `ast` string literals include docstrings, which is how the retired-series
    scan fired on the router's own module docstring saying it never reads the
    retired series.
    """
    src = re.sub(r'^[ \t]*#.*$', '', src, flags=re.M)
    tree = ast.parse(src)
    doc_spans = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            b = getattr(node, 'body', None)
            if (b and isinstance(b[0], ast.Expr)
                    and isinstance(b[0].value, ast.Constant)
                    and isinstance(b[0].value.value, str)):
                doc_spans.add(id(b[0].value))
    return tree, doc_spans


# ================================ the Ten-Year category page, onto the spine

CATEGORY_VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'categoryA.blade.php')
DATASETS_PHP = os.path.join(ROOT, 'app', 'app', 'Custom', 'ProjectsDatasets.php')


def test_the_category_page_lists_projects_from_the_spine_not_the_retired_series():
    """⚠⚠ THE CATEGORY PAGE LISTED PROJECTS FROM A SERIES NYC RETIRED 2023-10-26.
    `/get/capitalprojects/by_category/` is `SELECT * FROM
    capitalprojectsdollarscomp` — **8,740 distinct project ids against the
    spine's 17,024**. Measured on one real category: `UTILITY RELOCATION FOR SE
    AND WM PROJECTS` returned **2 projects** where the spine has **268**, and
    `NEIGHBORHOOD PARKS, PLAYGROUNDS AND BALLFIELDS` returned **0** where the
    spine has **1,036**.
    """
    ctrl = _read(PROJECTS_CTRL_PHP)
    i = ctrl.index('public function category_a')
    j = ctrl.index('public function', i + 10)
    seg = ctrl[i:j]
    m = re.search(r"'prjsUrl'\s*=>\s*DatabookAPI::url\(\"([^\"]+)\"", seg)
    assert m, 'the category page no longer declares a project-list URL'
    assert '/get/capital/' in m.group(1), (
        f'the category project list is not served from the capital spine '
        f'endpoint: {m.group(1)}')
    assert 'by_category' not in m.group(1), (
        'the category page is back on the retired-series endpoint')


def test_no_capital_project_list_endpoint_reads_the_retired_series():
    """⚠ The spine exists because `capitalprojectsdollarscomp` was retired. A
    LIST of projects served from it understates the programme by roughly half and
    reads as complete.

    ⚠ Scoped to `routers/capital.py`, which is the rebuilt surface. `main.py`
    still has legacy endpoints on the old series that Phase 4 will retire; this
    guard exists so the NEW router cannot grow one.

    ⚠ And it tests for the table in a SQL POSITION, not for the string. The
    source-coverage payload legitimately names it — the sources table's "Table"
    column tells a reader where the retired series lives, which is that panel's
    entire job.
    """
    src = _read(ROUTER)
    tree, docs = _py_code(src)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docs:
                continue          # a docstring is prose, not a query
            if 'capitalprojectsdollarscomp' not in node.value:
                continue
            # ⚠⚠ A QUERY, NOT A MENTION. The source-coverage payload legitimately
            # NAMES `capitalprojectsdollarscomp` — the sources table's "Table"
            # column tells a reader which table the retired 2023 series lives in,
            # which is the whole point of that panel. Banning the string outright
            # fired on exactly that, so the test is for the table appearing in a
            # SQL position.
            if re.search(r'\b(from|join|update|into)\s+capitalprojectsdollarscomp',
                         node.value, re.I):
                hits.append(node.value[:80])
    assert not hits, (
        'routers/capital.py queries the retired series directly:\n  '
        + '\n  '.join(hits))
    # ⚠ Assert the scan could SEE something, or a renamed table makes it vacuous.
    assert 'capital_projects' in src, 'the router does not query the spine at all'


def _contract_block(name):
    """The `$dd['<name>']` contract's OWN text, by matching its brackets.

    ⚠⚠ THE PREVIOUS VERSION TERMINATED THE SEGMENT AT THE LITERAL `'main' => [`,
    and it therefore FAILED — correctly — the moment `main` and `main-a` were
    deleted (2026-09-10) for carrying eleven `, 1000` multipliers into dead
    code. Re-anchoring on the NEXT contract's key would break again on the next
    deletion, and anchoring on the array's closing `];` would silently widen the
    segment over every contract added after this one — so it would assert the
    spine's USD rule against a contract that may legitimately publish thousands.
    Bracket-matching is the only anchor that describes exactly one contract
    however many there are, and there is currently exactly ONE (`spine`).
    """
    php = _php_code(_read(DATASETS_PHP))
    i = php.index("'%s' => [" % name)
    i = php.index('[', i + len(name) + 2)
    depth, k = 0, i
    while k < len(php):
        if php[k] == '[':
            depth += 1
        elif php[k] == ']':
            depth -= 1
            if depth == 0:
                return php[i:k + 1]
        k += 1
    raise AssertionError("the '%s' contract's brackets do not close" % name)


def test_the_spine_dataset_contract_does_not_multiply_money_by_a_thousand():
    """⚠⚠ THE UNIT TRAP IN THIS SWAP, AND IT LOOKS ENTIRELY PLAUSIBLE.
    `ProjectsDatasets`'s retired-series contracts called `toFin(r["BUDG_CURR"],
    1000)` because `capitalprojectsdollarscomp` publishes **thousands**. The
    spine publishes **USD**. Reusing that multiplier renders a $385M category as
    $385B — a figure no assertion about row counts or status codes can see.

    ⚠ The contracts that carried the multiplier are gone; this guard is what stops
    it coming back into the one that is left, so it reads the spine's own block.
    """
    seg = _contract_block('spine')
    money = re.findall(r'toFin(?:ShortK)?\(([^)]*)\)', seg)
    assert money, 'the spine contract renders no money at all'
    for call in money:
        mult = call.split(',')[-1].strip()
        assert mult == '1', (
            f'the spine contract multiplies money by {mult} — the spine is in '
            f'USD, so anything but 1 is wrong by that factor: toFin({call})')


def test_no_dataset_contract_carries_the_retired_series_thousand_multiplier():
    """⚠⚠ AND THE CLASS, NOT JUST THE SPINE. Eleven `, 1000` multipliers lived in
    `main` and `main-a`, two contracts nothing routed to, and the reason they were
    deleted rather than left alone is that a dead contract carrying the retired
    table name AND the multiplier is a template: the next page written from it
    republishes both defects, which is what the org capital tab already did.

    So no contract in this file may multiply money at all. Any future contract on
    a thousands-denominated series must state that in its own guard rather than
    inheriting this one's silence.
    """
    php = _php_code(_read(DATASETS_PHP))
    bad = [c for c in re.findall(r'toFin(?:ShortK)?\(([^)]*)\)', php)
           if c.split(',')[-1].strip() not in ('1', '')]
    assert not bad, (
        'a dataset contract multiplies money by something other than 1, which '
        'is the retired series\' unit and not the spine\'s: %s' % bad[:4])
    # ⚠ The scan must be able to see a money call at all, or a rename makes it
    # pass vacuously — the zero-files scanner in a new organ.
    assert len(re.findall(r'toFin(?:ShortK)?\(', php)) >= 2, (
        'this guard found fewer than two money calls in the contracts file, so '
        'it is no longer reading what it thinks it is')


def test_amount_over_budget_is_not_reintroduced_on_the_category_page():
    """⚠⚠ `Amount Over Budget` IS THE LABEL THIS SECTION RETIRED FOR CARRYING TWO
    DEFINITIONS, and the standing rule is to DROP it rather than preserve the
    defect under new data — the same call `/projects` made when it lost its four
    globStats tiles. It was one of eight tiles on the category page computed from
    the retired series' columns.
    """
    view = _php_code(_read(CATEGORY_VIEW))
    assert 'over_budg_am' not in view, (
        'the Amount Over Budget tile is back on the category page')
    assert 'Amount Over Budget' not in view, (
        'the Amount Over Budget label is back on the category page')
    ctrl = _read(PROJECTS_CTRL_PHP)
    i = ctrl.index('public function category_a')
    j = ctrl.index('public function', i + 10)
    assert 'over_budg_am' not in _php_code(ctrl[i:j]), (
        'the category controller still declares the Amount Over Budget selector')


def test_the_category_slug_is_matched_the_way_laravel_builds_it():
    """⚠⚠ THE OLD RULE COULD NOT MATCH ITS OWN URLS. Both category endpoints
    compared `REPLACE(category, ' ', '-')` against the slug in the link — and
    Laravel's `Str::slug` also strips punctuation, so **12 of 138 categories**
    (every one carrying a comma) produced `large,-major-and-…` here against
    `large-major-and-…` in the URL. Those pages fell through to a loose
    `ILIKE '%…%'`, which is worse than missing: `sewers` also matches
    `COMBINED SEWERS AND WATER MAINS`, so a category page could list another
    category's plan.
    """
    src = re.sub(r'^[ \t]*#.*$', '', _read(os.path.join(API, 'main.py')), flags=re.M)
    i = src.index('async def get_capital_projects_stratcategory')
    seg = src[i:i + 2000]
    assert 'ILIKE' not in seg, (
        'the strategy category lookup matches loosely again — one category can '
        'list another category\'s plan')
    assert 'regexp_replace' in seg and '[^a-z0-9]+' in seg, (
        'the strategy category lookup no longer slugs the stored value the way '
        'Laravel slugs the URL')

    # ⚠ SCOPED TO THE FUNCTION, not a byte window around its name. The window
    # version broke the moment a sibling endpoint was inserted beside it — it
    # started reading the neighbour's body and asserting about the wrong code.
    rtree = ast.parse(_read(ROUTER))
    rcode = _code(_fn(rtree, 'capital_projects_by_category'))
    assert '_SLUG_SQL' in rcode, (
        'the spine category endpoint no longer slugs the stored value')


def test_the_profile_links_the_facet_whose_page_is_about_this_project():
    """⚠ Ten-Year category IS linked: its page now lists the spine's projects in
    the category. The budget-line family is NOT — measured, **39 values against
    the 236 that `/projects/types/{slug}` is keyed on, sharing 5 names, every one
    a coincidence** — so a link would 404 on 34 of 39 and mislead on the rest.

    ⚠ Delete the second half of this guard when the family pages exist. That is a
    deliberate act, which is why it is pinned.
    """
    view = _rendered_copy(_read(VIEW))
    m = re.search(r"Ten-Year Strategy category</th><td>(.*?)</td>", view, re.S)
    assert m, 'the Ten-Year category row is gone'
    assert "route('prjStratCategory'" in m.group(1), (
        'the Ten-Year category is not linked to its page')

    # ⚠ The second half of this guard — "the family row must NOT link" — is
    # RETIRED, exactly as its docstring said it should be once the family pages
    # existed. `test_the_profile_links_the_family_row_to_its_own_dimension`
    # replaces it and asserts the stronger property: it links, and to the right
    # dimension. Retiring a guard when its condition ends is not weakening it;
    # leaving it would forbid the thing it was waiting for.


def _py_prose_free(path):
    """Python source with `#` comments and DOCSTRINGS blanked, SQL left intact.

    ⚠⚠ THE 17th AND 18th OWN-PROSE FIRINGS IN THIS REPO, both on the first run of
    the guards below: one on an endpoint docstring saying it no longer LEFT JOINs
    `capitalprojectsdollarscomp`, one on a comment recording the two defective
    vintages by date while the guard bans hardcoded dates.

    ⚠ Docstrings are blanked BY LINE RANGE, not by removing every triple-quoted
    string — the queries in this file are triple-quoted too, and stripping those
    would make every SQL assertion vacuous, which is the zero-files scanner in a
    new costume.
    """
    src = _read(path)
    lines = src.split('\n')
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        b = getattr(node, 'body', None)
        if (b and isinstance(b[0], ast.Expr)
                and isinstance(b[0].value, ast.Constant)
                and isinstance(b[0].value.value, str)):
            for ln in range(b[0].lineno - 1, b[0].end_lineno):
                lines[ln] = ''
    out = '\n'.join(lines)
    out = re.sub(r'^[ \t]*#.*$', '', out, flags=re.M)
    # ⚠ And `--` SQL comments INSIDE the query strings, which survive both of the
    # above. The date-list guard fired on one of those on its first run: a note
    # inside the SQL recording which vintage the predicate exists for. `--` is
    # unambiguously a comment in SQL, so removing those lines cannot eat a query.
    return re.sub(r'^[ \t]*--.*$', '', out, flags=re.M)


# ============================== the project-type page, and a shifted ingest

TYPE_VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'prjTypeA.blade.php')
MAIN_PY = os.path.join(API, 'main.py')


def test_the_project_type_page_serves_no_retired_series_figures():
    """⚠⚠ IT WAS A MIXED PAGE AND NOTHING SAID SO — live Ten-Year Strategy
    amounts (latest publication 2025-05-01) beside a project count and cost
    LEFT JOINed from `capitalprojectsdollarscomp`, retired 2023-10-26. Measured
    over 25 sampled types / 362 rows: the join contributed a figure on **127
    rows and zeros on the other 235**.

    ⚠⚠ AND THOSE COLUMNS MAY NOT BE REBUILT ON THE SPINE EITHER. The join key was
    (publication date, CATEGORY), so it attributed a whole category's projects to
    one type — and a category spans many types. `capitalstrategy` has **no
    project key at all**, so a project count on this page is not derivable from
    it by any join. That count belongs on the category page, which has one.
    """
    src = _py_prose_free(MAIN_PY)
    i = src.index('async def get_pstats_categories_by_type')
    j = src.index('@app.get', i)
    seg = src[i:j]
    assert 'capitalprojectsdollarscomp' not in seg, (
        'the type endpoint reads the retired series again')
    for banned in ('prjnum', 'plannedcost', 'currcost'):
        assert banned not in seg, (
            f'the type endpoint serves `{banned}` again — a project figure this '
            f'source cannot key')

    view = _php_code(_read(TYPE_VIEW))
    for banned in ('prjnum', 'plannedcost', 'currcost',
                   'Amount of Projects', 'Planned Project Cost'):
        assert banned not in view, f'the type page renders `{banned}` again'


def test_a_shifted_strategy_vintage_never_reaches_a_page():
    """⚠⚠ TWO OF THE EIGHT `capitalstrategy` VINTAGES ARE INGESTED WRONG.
    Measured 2026-09-08:

      20250116  258/258 rows — `Ten-Year Plan Category` DUPLICATES `Funding
                Type`. Amounts are correctly aligned; the category is absent.
      20230112  275/275 rows — a LEFT SHIFT BY ONE. Funding Type landed in
                Category, First Fiscal Year in Funding Type, every amount moved
                one column left, and `Ten-Year Total` is NULL on all 275 — so
                those amounts sit against the WRONG FISCAL YEARS.

    533 of 2,255 rows, 23.6%. Live before this: the type page listed `City` and
    `Federal` as Ten-Year Plan Categories and linked them to
    `/projects/categories/city`.

    ⚠ TWO DEFECTS, TWO TREATMENTS — and treating them alike emptied **162 of 236
    type pages**, because most types appear only in those vintages. The money
    guard drops the 275 shifted rows (228 of 236 types survive, 8 correctly 404);
    the category guard only withholds the LABEL.

    ⚠ BOTH TEST THE DATA, NEVER A HARDCODED DATE LIST — a list goes stale the
    moment a ninth vintage lands wrong.
    """
    src = _py_prose_free(MAIN_PY)

    # Neither guard may be expressed as a date list.
    for bad in ('20250116', '20230112'):
        assert bad not in src, (
            f'a defective vintage is excluded by hardcoding {bad}; the test must '
            f'be on the data, or a ninth bad vintage publishes silently')

    assert '_STRATEGY_MONEY_OK' in src and '_STRATEGY_CATEGORY_OK' in src, (
        'the two strategy guards are gone')

    # The category page needs BOTH — a real category and real money.
    i = src.index('async def get_capital_projects_stratcategory')
    seg = src[i:i + 2000]
    assert '_STRATEGY_CATEGORY_OK' in seg and '_STRATEGY_MONEY_OK' in seg, (
        'the category endpoint no longer excludes the defective vintages, so '
        '/projects/categories/city becomes a page built from a funding type')

    # The type page needs the MONEY guard, and must NOT drop the whole row for a
    # missing category — that is what emptied 162 pages.
    k = src.index('async def get_pstats_categories_by_type')
    tseg = src[k:src.index('@app.get', k)]
    assert 'Ten-Year Total' in tseg and 'IS NOT NULL' in tseg, (
        'the type endpoint no longer excludes the shifted-money rows')
    assert "NOT IN ('City', 'Federal', 'State', 'Private')" not in tseg, (
        'the type endpoint drops rows for a missing CATEGORY — that empties 162 '
        'of 236 type pages, and their amounts are fine')

    # And the view must not render a funding type as a linked category.
    view = _php_code(_read(TYPE_VIEW))
    m = re.search(r"projects/categories/'\s*\+\s*r\['category-slug'\]", view)
    assert m, 'the type page no longer links its categories at all'
    ctx = view[max(0, m.start() - 700):m.start()]
    assert "'City'" in ctx and 'Not published' in ctx, (
        'the type page links a funding type as a category again — '
        '/projects/categories/city is not a category')


def _load(names):
    """Run named top-level defs/assigns out of the REAL router file.

    ⚠ The pieces under guard are compiled out of the router's AST — never
    reimplemented here, which would measure a different system than the one that
    ships. (`test_capital_triage_fixes.py` has the same helper; this file needs
    its own because the two are independent modules.)
    """
    tree = ast.parse(_read(ROUTER))
    ns = {}
    import re as _re
    ns['re'] = _re
    # ⚠⚠ THE ROUTER'S MODULE DEPENDENCIES MUST BE IN SCOPE, and this broke the
    # moment the slug rule moved to its owner (2026-09-10): `_slug` in the
    # router is now `capitalslug.slug`, so exec'ing that one assignment raised
    # `NameError: name 'capitalslug' is not defined`. Loaded BY PATH, because
    # `conftest.py` replaces the whole `modules` package with a MagicMock and
    # `_slug` would then be a mock that satisfies almost any assertion — which
    # is worse than the NameError, since it passes.
    import importlib.util as _ilu
    for _dep in ('budgetline', 'capitalslug', 'capitalmoney', 'fmsid', 'wkt'):
        _path = os.path.join(ROOT, 'api', 'modules', _dep + '.py')
        if not os.path.exists(_path):
            continue
        try:
            _spec = _ilu.spec_from_file_location('_%s_for_load' % _dep, _path)
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
        except Exception:
            # A module with heavier imports is not needed by the names this
            # helper compiles; skipping it is safe and keeps the helper hermetic.
            continue
        ns[_dep] = _mod
    assert hasattr(ns.get('capitalslug'), 'slug'), (
        'capitalslug did not load as the real module, so anything read out of '
        'the router that depends on it would be measured against a stand-in')
    for node in tree.body:
        keep = False
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            keep = node.name in names
        elif isinstance(node, ast.Assign):
            keep = any(getattr(t, 'id', None) in names for t in node.targets)
        if keep:
            exec(compile(ast.Module(body=[node], type_ignores=[]), ROUTER, 'exec'), ns)
    return ns


# ==================================== budget-line family pages (items 2b, 3b)

PROVENANCE = os.path.join(ROOT, 'app', 'resources', 'views', 'components', 'db',
                          'data-provenance.blade.php')
BL_INDEX_VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'budgetLinesA.blade.php')
FAMILY_VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'budgetLineFamilyA.blade.php')
ROUTES = os.path.join(ROOT, 'app', 'routes', 'web.php')


def test_the_family_route_is_declared_before_the_budget_line_wildcard():
    """⚠⚠ A SPECIFIC PATH DECLARED AFTER A SINGLE-SEGMENT WILDCARD IS SWALLOWED
    BY IT — the trap the digital-services section already pins for
    `function/{cap}` before `{slug}`. `/projects/budget-lines/families` would
    otherwise arrive as `blcode = "families"`.
    """
    routes = _php_code(_read(ROUTES))
    fam = routes.index("'/projects/budget-lines/families/{fslug}'")
    wild = routes.index("'/projects/budget-lines/{blcode}'")
    assert fam < wild, (
        'the family route is declared after the {blcode} wildcard, which '
        'swallows it')


def test_the_family_page_is_a_different_dimension_from_projects_types():
    """⚠⚠ 39 VALUES AGAINST 236, SHARING 5 NAMES BY COINCIDENCE. The spine's
    `project_types` is the deduplicated set of BUDGET-LINE FAMILIES a project is
    funded through; `/projects/types/{slug}` is keyed on `capitalstrategy`'s
    236-value WORK type. This page exists because the two were conflated.

    ⚠ The family dimension is project-level — 12,929 projects, exactly the
    current plan — where the strategy's has no project key at all. That is why
    this page can list projects and the type page cannot.
    """
    tree = ast.parse(_read(ROUTER))
    code = _code(_fn(tree, 'capital_projects_by_family'))
    assert 'project_types' in code, (
        'the family endpoint no longer reads the spine families')
    assert 'capitalstrategy' not in code, (
        'the family endpoint reads the strategy — that is the other dimension')
    # ⚠ Matched on the SLUG of the stored value, both sides — 4 of the 39
    # families carry punctuation (`Water Mains, Sources and Treatment`), and a
    # raw comparison would silently miss every one.
    assert '_SLUG_SQL' in code, (
        'the family endpoint compares raw values, so a punctuated family never '
        'matches its own URL')


def test_one_slug_rule_serves_both_sides_of_the_family_match():
    """⚠⚠ TWO SPELLINGS OF ONE RULE IS HOW `/projects/categories/{slug}` CAME TO
    BE UNABLE TO MATCH ITS OWN URLS. `_slug()` (Python) and `_SLUG_SQL`
    (Postgres) must agree, so this runs the Python one over the REAL family
    vocabulary and checks the regex halves are the same shape.
    """
    ns = _load({'_slug'})
    f = ns['_slug']
    assert f('Water Mains, Sources and Treatment') == 'water-mains-sources-and-treatment'
    assert f('Dept. of Information Technology & Telecomm') == 'dept-of-information-technology-telecomm'
    assert f('EDP Equipment and Finance Costs') == 'edp-equipment-and-finance-costs'
    assert f('  Parks and Recreation  ') == 'parks-and-recreation'
    assert f(None) == '' and f('') == ''

    # ⚠ Parsed OUT of the SQL, never re-typed — a guard that reimplements the
    # thing it guards measures a different system.
    #
    # ⚠⚠ RE-EXPRESSED 2026-09-10: this read `_SLUG_SQL = "trim…"` out of the
    # ROUTER, and it fired correctly when the rule moved to
    # `modules/capitalslug`. The move happened because the rule gained a SECOND
    # consumer (`modules/capitalsources`, which counts a source table's records
    # for one scope and must slug both sides), and a second copy in that module
    # is exactly the defect this guard exists to prevent. So the value now comes
    # from the OWNER, and the router is additionally asserted NOT to redeclare
    # it — which is strictly stronger than reading a literal out of one file.
    src = _read(os.path.join(ROOT, 'api', 'modules', 'capitalslug.py'))
    m = re.search(r"SLUG_SQL = \"([^\"]+)\"", src)
    assert m, 'the slug SQL is gone from its owner'
    sql = m.group(1)
    router_src = _read(ROUTER)
    assert 'capitalslug.SLUG_SQL' in router_src, (
        'the router no longer takes the slug SQL from its owner')
    assert not re.search(r"_SLUG_SQL\s*=\s*\"trim", router_src), (
        'the router declares its own copy of the slug SQL again')
    assert 'lower(' in sql, 'the SQL rule does not lowercase'
    assert "'[^a-z0-9]+'" in sql, (
        f"the SQL rule's character class differs from the Python one: {sql}")
    assert "trim(both '-'" in sql, 'the SQL rule does not trim leading/trailing -'


def test_the_index_links_a_family_only_where_the_page_exists():
    """⚠⚠ THE INDEX'S FAMILY GROUPING WAS DEAD. `rowGroup.dataSrc` named
    `wegov-prjtype-name`, which `/get/capitalbudget/bydate/recent` has never
    served — the column is `Project Type Name` — so **all 749 rows rendered
    under one "No group" header**. Same renamed key that 500'd every budget-line
    detail page.

    ⚠⚠ AND THE GROUP NAMES ARE NOT THE FAMILY VOCABULARY. `capitalbudget` has
    **41** values, the spine **39**, and only **25 slugs match** — `PARKS` here
    is `Parks and Recreation` there, `FIRE` is `Fire Department`. Linking every
    header would 404 on 39% of them, so the link is gated on the SERVED slug
    set. A link that lands on a 404 is worse than text.
    """
    view = _php_code(_read(BL_INDEX_VIEW))
    assert "dataSrc: 'Project Type Name'" in view, (
        'the index groups by a key the payload does not carry, so every row '
        'falls under one "No group" header')
    assert 'wegov-prjtype-name' not in view, (
        'the index reads the renamed key again')
    assert 'FAMILY_SLUGS' in view, (
        'the index links every family header without checking a page exists')
    m = re.search(r'FAMILY_SLUGS\.indexOf\(([^)]+)\)', view)
    assert m, 'the slug set is declared but never consulted'

    ctrl = _read(PROJECTS_CTRL_PHP)
    i = ctrl.index('public function budgetLines_a')
    j = ctrl.index('public function', i + 10)
    assert "/get/capital/families" in ctrl[i:j], (
        'the index no longer fetches the family vocabulary, so its gate is '
        'whatever the view happens to hold')


def test_the_profile_links_the_family_row_to_its_own_dimension():
    """⚠ It was plain text while no family page existed — the right call then.
    Now it links, and it must link to `budgetLineFamily`, never `prjType`.
    """
    view = _rendered_copy(_read(VIEW))
    f = re.search(r"Budget-line family</th><td>(.*?)</td>", view, re.S)
    assert f, 'the budget-line family row is gone or renamed'
    assert "route('budgetLineFamily'" in f.group(1), (
        'the family row does not link to the family page')
    assert "route('prjType'" not in f.group(1), (
        "the family row links to /projects/types — 39 values against 236, "
        "sharing 5 names by coincidence")


def test_the_provenance_component_keeps_its_two_modes_apart():
    """⚠⚠ THE ONE THING THIS COMPONENT MAY NEVER DO IS MERGE ITS MODES.

      page   — "what data feeds this KIND of page", with each dataset's TOTAL
               record count. Identical on every project profile.
      record — "which publications carry THIS record", with presence and the
               VERSION each figure came from. Different on every one.

    A dataset's total record count and this record's presence in it are
    different claims. One row carrying both invites "475,136 records" to be read
    as being about this project — the defect that removed four `globStats` tiles
    from `/projects` for publishing 5,128 against the spine's 17,024.

    ⚠ So: the record mode must never render a record-count column, and the page
    mode must never render a presence column. Asserted per branch, because a
    whole-file check passes while one branch is wrong — the lesson the
    by-start-year chart paid for.
    """
    comp = _rendered_copy(_read(PROVENANCE))
    i = comp.index("@if($mode === 'record')", comp.index('table-responsive'))
    j = comp.index('@else', i)
    k = comp.index('@endif', j)
    record_branch, page_branch = comp[i:j], comp[j:k]

    assert 'In this record?' in record_branch and 'Version' in record_branch, (
        'the record mode lost the two columns that are its whole reason to exist')
    assert 'Dataset Records' not in record_branch, (
        "the record mode renders a dataset's TOTAL record count beside this "
        "record's presence — two different claims in one row")

    assert 'Dataset Records' in page_branch, (
        'the page mode lost its record-count column')
    for banned in ('In this record?', "['present']", "['version']"):
        assert banned not in page_branch, (
            f'the page mode renders `{banned}` — it has no record to scope to, '
            f'so any presence it shows is invented')

    # ⚠⚠ THE PAGE AND RECORD MODES MUST FETCH NOTHING — their rows and counts are
    # server-rendered. The SCOPED mode legitimately does fetch, because its counts
    # are per-type/category/budget-line and only an endpoint knows them; what it
    # may never do is DELETE a row, which is asserted separately in
    # `test_a_scoped_count_of_zero_never_removes_its_row`.
    # ⚠ So the fetch must be confined to the scoped branch, not banned outright —
    # the first version of this assertion banned it outright and fired the moment
    # a legitimate third mode arrived.
    fetch = [m.start() for m in re.finditer(r'\$\.ajax|fapireq|loadTableStat\(', comp)]
    scoped = comp.index("@if($mode === 'scoped'")
    for f in fetch:
        assert f > scoped, (
            'the provenance shell fetches outside its scoped branch, so a failed '
            'request can empty a server-rendered table')


def test_no_view_hand_rolls_the_provenance_accordion_any_more():
    """⚠⚠ FIFTEEN VIEWS HAND-ROLLED THIS SHELL, and thirteen also hand-rolled
    `loadTableStat()` — whose callback was `if (res) { fill } else { splice }`.
    So a scoped count of **0**, which is a FACT (this dataset holds nothing for
    this type), deleted the row; and a failed request did the same. Measured
    before the migration: `/projects/types/animal-care` requested 3 datasets and
    rendered **1**. After: 3 rows, counts `2 / 0 / 0`.

    ⚠ TWO views are excluded and each for a stated reason, so a future reader
    does not "finish the job" by migrating a dead page or breaking a working one:
      orgproject                        — no controller renders it at all; the
        `/p/{id}` rewrite replaced it.
      organization                      — a DIFFERENT pattern. Its counts are
        per-SECTION on an org profile, from `/get/orgs/stats-*`, and they WORK:
        measured, 42 requests, 42 × 200. Folding it into a component built for
        `stats_data_sources` rows would be a rewrite of a working feature.

    ⚠⚠ IT USED TO BE FOUR. `capitalA`, `orgprojectA` and `projectsA` were
    excluded as "unrouted — their actions appear zero times in routes/web.php",
    which was true and is now moot: they were DELETED on 2026-09-10, with their
    actions. An exclusion for a file that no longer exists is worse than none —
    it reads as a live decision and invites someone to recreate the page it
    names. `test_the_unrouted_orphan_views_stay_deleted` in
    `test_capital_projects_page.py` is what keeps them gone.
    """
    views = os.path.join(ROOT, 'app', 'resources', 'views')
    EXCLUDED = {'orgproject.blade.php', 'organization.blade.php'}
    # ⚠ An exclusion must name a file that EXISTS, or it is a stale decision
    # standing in for a live one — the shape the three deleted orphans left
    # behind here.
    for fn in EXCLUDED:
        assert os.path.exists(os.path.join(views, fn)), (
            '%s is excluded from this sweep but does not exist; remove the '
            'exclusion rather than leaving it to read as a decision' % fn)
    offenders, scanned = [], 0
    for dirpath, _dirs, files in os.walk(views):
        for fn in files:
            if not fn.endswith('.blade.php'):
                continue
            scanned += 1
            if fn in EXCLUDED:
                continue
            body = _php_code(_read(os.path.join(dirpath, fn)))
            if 'loadTableStat' in body or 'dsStatsTable' in body:
                offenders.append(fn)
    # ⚠ Assert it LOOKED. A tree walk that scans nothing passes unconditionally —
    # this repo has shipped that guard twice.
    assert scanned > 80, f'only {scanned} views scanned — the walk is not looking'
    assert not offenders, (
        'these views still hand-roll the provenance accordion: ' + ', '.join(sorted(offenders)))


def test_a_scoped_count_of_zero_never_removes_its_row():
    """⚠⚠ THE DEFECT WAS THAT ZERO AND FAILURE WERE THE SAME BRANCH. A dataset
    holding no records for this project type is a FINDING; a request that failed
    is an UNKNOWN; and neither is a reason to delete the row. The component
    distinguishes all three — a number, `0`, and `—`.
    """
    comp = _rendered_copy(_read(PROVENANCE))
    # ⚠⚠ ANY REMOVAL, NOT THE OLD SPELLINGS. The first version banned `splice`
    # and `.row(` — the two the old code happened to use — and a mutation that
    # deleted the row with `$(cell).closest('tr').remove()` sailed straight
    # through. A guard that bans the previous implementation's vocabulary is not
    # guarding the property.
    for banned in ('splice', '.row(', '.remove(', 'removeChild', '.detach(',
                   "style.display='none'", 'hidden = true'):
        assert banned not in comp, (
            f'the provenance shell removes rows again, via `{banned}`')
    # ⚠ The three outcomes must be distinguishable in the code, not merged.
    assert re.search(r"rows\[0\]\.res === undefined", comp), (
        'a missing figure is not separated from a zero, so "unknown" renders as 0')
    assert re.search(r"error:\s*function", comp), (
        'a failed request has no branch of its own')
    # ⚠ And the failure branch must not write a number.
    err = comp[comp.index('error: function'):]
    err = err[:err.index('}')]
    assert 'toLocaleString' not in err and '0' not in err.replace("'—'", ''), (
        'the failure branch writes a figure, so a broken request reads as data')


def test_phase_and_forecast_are_header_facts_above_the_money_tiles():
    """⚠⚠ THEY WERE TWO `is-text` TILES IN A GRID OF MONEY TILES, and the strip
    answered two different questions in one row: four dollar figures beside
    `Construction Procurement` and a date. The owner moved them into the header
    (2026-09-10), which freed the row for the full ⚑ F set of six measures.

    The property is not "they are in the header" as a location — it is that a
    reader meets them BEFORE the figures, and that neither is silently dropped
    on the way. Both are still the endpoint's `key_facts`, echoed.

    ⚠ They must NOT be badges. Badges on this page mean PRESENCE and nothing
    else — one meaning per variant, which is the defect `db-badge-neutral`
    already carried four of — and a phase is a value, not a flag.
    """
    view = _rendered_copy(_read(VIEW))
    # ⚠⚠ MATCH THE CLASS ATTRIBUTE, NOT A PREFIX. `'<div class="db-profile-meta'`
    # also matches `db-profile-meta-later` — measured, a mutation renaming the
    # block to a class no stylesheet defines left this guard GREEN, which is the
    # `col-md-5` substring trap this repo already records, in a second organ.
    m = re.search(r'<div class="db-profile-meta[ "]', view)
    assert m, 'the header meta block is gone'
    meta = m.start()
    grid = view.index('<x-db.stat-grid')
    assert meta < grid, (
        f'the header meta renders at {meta} and the tiles at {grid} — phase and '
        'forecast are below the figures they should introduce')

    block = view[meta:view.index('</div>', meta)]
    for frag in ('$phaseText', '$forecastText'):
        assert frag in block, f'the header meta does not carry {frag}'
    # ⚠ AND THE SLIP LINE TRAVELS WITH THE FORECAST. Detached from the date it
    # describes, "33.4 months later than first forecast" names no subject.
    assert '$slipLine' in block, (
        'the slip line is no longer beside the forecast it qualifies')
    assert block.index('$forecastText') < block.index('$slipLine'), (
        'the slip line renders before the date it qualifies')

    # ⚠ Both still come from `key_facts`, which runs no query — so the header
    # cannot disagree with the Schedule section further down.
    php = view[:view.index('@endphp')]
    for frag in ("$kf['current_phase']", "$kf['forecast_completion_label']"):
        assert frag in php, f'{frag} is no longer read from the served key_facts'

    # ⚠ Neither may come back as a tile: a grid of `$5.1M`-shaped values with
    # prose in it is what this move undid.
    assert 'label="Phase"' not in view and 'label="Forecast completion"' not in view, (
        'phase or forecast is a stat tile again')


def test_the_money_help_sits_with_the_figures_it_explains():
    """⚠⚠ ONE HELP BLOCK, DIRECTLY UNDER THE TILES. The not-a-funnel note and
    the publisher's definitions used to be two things in a Money section ~300px
    below the figures that raise the question — measured before the move, the
    note sat at **1,191px** and the tiles at **363px**. A reader wondering
    whether adopted minus spent is an amount outstanding wonders it AT THE
    TILES, which is where both now are (measured after: note at 458px).

    ⚠ The note stays OUTSIDE the `<details>` — invariant 6, enforced separately
    by `test_a_caveat_is_never_behind_a_click…`. This guard is about WHERE the
    block is, not what is collapsed inside it.
    """
    view = _rendered_copy(_read(VIEW))
    grid = view.index('<x-db.stat-grid')
    gridEnd = view.index('</x-db.stat-grid>', grid)
    note = view.index("{{ $money['note']")
    # ⚠ THE HEADING'S ANCHOR, NOT ITS TEXT. `About this project` is also the
    # TOC's label for it, 3,000 characters EARLIER in the file, so the first
    # draft compared the note against the menu entry and failed on the
    # unmutated file — the baseline-not-green trap, which makes every
    # subsequent mutation read as "fired" while nothing has been tested.
    about = view.index('<h2 id="about"')
    assert gridEnd < note < about, (
        f'the money note renders at {note}; the tiles end at {gridEnd} and '
        f'About begins at {about} — the explanation has drifted away from the '
        'figures again')

    # ⚠⚠ ONE BLOCK, AND ITS SPAN IS COMPUTED BY BALANCING `<div>`, NOT TAKEN AS
    # "somewhere between the note and About". Measured: with the loose span, a
    # mutation moving the `<details>` OUT of the help container — two stacked
    # things again, which is exactly what "a single help section" replaced —
    # left this guard GREEN, because the displaced block still landed inside
    # the note..About window.
    open_div = view.rindex('<div', 0, note)
    depth, i = 1, view.index('>', open_div) + 1
    for tag in re.finditer(r'<div\b|</div>', view[i:]):
        depth += 1 if tag.group(0) == '<div' else -1
        if depth == 0:
            i = i + tag.end()
            break
    block = view[open_div:i]
    assert "$money['note']" in block, 'the help container does not hold the note'
    assert '<details' in block, (
        'the definitions are outside the help container — two stacked things '
        'again, not one help section')
    assert "$m['definition']" in block, (
        "the publisher's definitions are not in the help block under the tiles")


def test_no_toc_entry_points_at_an_anchor_the_page_never_emits():
    """⚠⚠ THE MONEY ENTRY WOULD HAVE OUTLIVED THE MONEY SECTION. Removing the
    section leaves `['money', 'Money', null]` in the TOC list pointing at
    `#money`, and `null` means "always renders" — so it would have shown on
    every project page and gone nowhere on all of them.

    `verify_toc.py` catches this in the browser; this catches it in the file,
    which is the difference between finding it in CI and finding it by looking.
    """
    view = _rendered_copy(_read(VIEW))
    block = view[view.index('$toc = [];'):view.index('] as $t) {')]
    keys = re.findall(r"\['([a-z0-9_]+)',", block)
    assert len(keys) >= 8, f'the TOC list looks truncated: {keys}'
    for k in keys:
        assert f'id="{k}"' in view, (
            f'the TOC links #{k} and the page emits no element with that id')


def test_the_scope_field_keeps_the_citation_the_section_carried():
    """⚠⚠ SCOPE IS THE ONE ATTRIBUTE SOURCED FROM A RETIRED SERIES, and turning
    a section into a table row is exactly how its label gets lost. It was an
    `<h3>` with a visible vintage line above the prose; it is now a row in the
    About table (owner, 2026-09-10), and the vintage moved onto an info icon
    rather than being dropped to make the row tidy. A reader taking
    `CONSTRUCTION OF NEW MANHATTAN FACILITY` as a current description of the
    project is being misled — NYC stopped publishing that series on 2023-10-26.

    ⚠ The citation must reach a screen reader too, not only a mouse: `title`
    alone is a hover affordance. `aria-label` carries it on the same element.
    """
    view = _rendered_copy(_read(VIEW))
    assert '<h3 class="mb-1">Scope</h3>' not in view, (
        'Scope is a heading again — it is a field in the About table'
    )
    i = view.index('<th scope="row">Scope</th>')
    row = view[i:view.index('</tr>', i)]
    assert "$hdr['scope_2023']" in row, 'the Scope row does not render the value'
    assert '$scopeCite' in row, (
        'the Scope row carries no citation — the 2023-series vintage is the '
        'one thing that stops this field reading as current')
    assert 'aria-label' in row and 'title=' in row, (
        'the citation is on hover only; it must reach a screen reader too')
    # ⚠ And the citation must say WHICH series and WHEN, not merely exist.
    m = re.search(r"\$scopeCite = '([^']+)'", view)
    assert m, '$scopeCite is no longer defined'
    for frag in ('2023', 'retired'):
        assert frag in m.group(1), (
            f'the Scope citation no longer says "{frag}": {m.group(1)}')
    # ⚠ An absent scope is an em dash in its own row — never a missing row,
    # which would silently change the shape of the table per project.
    assert '@else — @endif' in row, (
        'a project with no published scope renders no row rather than an em dash')


def test_there_is_exactly_one_table_of_contents_and_about_is_full_width_without_a_map():
    """⚠⚠ THE TOC USED TO SQUEEZE ABOUT ON EXACTLY THE PAGES WITH NOTHING IN THE
    RIGHT COLUMN. With no map it rendered as a `col-md-3` beside the About row,
    so About took `col-md-9`; with a map it rendered lower and the upper column
    was dropped. Two slots, one condition, and a grid spacer left behind.

    Owner, 2026-09-10: About is FULL WIDTH when there is no map and sits LEFT OF
    THE MAP when there is one, and the contents list starts below that row in
    both cases. Geometry exists for only 4,560 of 17,024 projects, so the
    map-less page is the common case, not the exception.

    ⚠ ONE INCLUDE, unconditionally — two includes behind opposite conditions is
    how a page comes to render the same navigation twice, and `verify_toc.py`
    checks the rendered count for that reason.
    """
    view = _rendered_copy(_read(VIEW))
    incs = re.findall(r"@include\('partials\.capital_toc'\)", view)
    assert len(incs) == 1, f'the TOC is included {len(incs)} times, not once'
    # It must not be conditional: `$hasMap` deciding WHERE it renders is what
    # produced the spacer column.
    i = view.index("@include('partials.capital_toc')")
    before = view[max(0, i - 300):i]
    assert '$hasMap' not in before, (
        'the single TOC include is still gated on $hasMap')

    # About: full width with no map, left of the map with one.
    m = re.search(r"\{\{ \$hasMap \? '(col-md-\d+)' : '(col-\d+)", view)
    assert m, 'the About column no longer switches on $hasMap'
    assert m.group(1) == 'col-md-7', (
        f'the About column beside the map is {m.group(1)}, not col-md-7')
    assert m.group(2) == 'col-12', (
        f'with no map the About column is {m.group(2)} — it should be full '
        'width now that the TOC has left that row')
    # And the TOC renders BELOW the about/map row, not inside it.
    row = view.index('<div class="row mb-4 mt-3">')
    assert view.index('id="about"') > row, 'About is not inside the about/map row'
    assert i > view.index('id="about"'), (
        'the contents list renders before About — it must start below that row')
