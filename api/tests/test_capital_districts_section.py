"""Guards on "What districts it's in" — the project profile's district section,
its api payload, and the one owner of how a district is NAMED.

⚠⚠ WHAT THIS SECTION LOOKED LIKE BEFORE, measured 2026-09-10 on the rendered
page rather than read off the payload: `/p/826HED-545` printed a flat run of
badges —

    CD 107   CD 108   CD 207   CD 208

— with no grouping, no indication that three of the four boundary sets had not
been answered at all, and `sd` rendered as an unlinked span because its district
page 404ed. `CD` was the stored key.

⚠⚠ AND THE DISTINCTION THESE GUARDS EXIST FOR: a count of ZERO and a count that
CANNOT BE ASKED are different claims, and both are real. Measured over all 9,880
placed projects:

    no published geometry   5,333 projects   cc/sd/nta are zero on EVERY one,
                                             because geometry is the only method
                                             that can place those three
    published geometry      4,547 projects   cc 20 / sd 19 / nta 21 / cd 1 are
                                             zero — a genuine spatial miss

So "No districts identified" on a project with no location would assert the City
placed it in no school district. It is in one; nothing we hold says which. That
is invariant 20 arriving on the project profile.

⚠ Every guard here was mutation-verified, with the mutation asserted to have
LANDED — the mutated text present, never "the original is absent" — before its
firing was read.
"""
import ast
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))
ROOT = os.path.realpath(os.path.join(API, '..'))

ROUTER = os.path.join(API, 'routers', 'capital.py')
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'capitalproject.blade.php')
NAME = os.path.join(ROOT, 'app', 'app', 'Custom', 'DistrictName.php')
DS = os.path.join(ROOT, 'app', 'app', 'Custom', 'DistDatasets.php')
SCHEMA = os.path.join(ROOT, 'app', 'app', 'Custom', 'Schema.php')
DISTCTL = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Districts.php')
APP = os.path.join(ROOT, 'app', 'app')
VIEWS = os.path.join(ROOT, 'app', 'resources', 'views')

TYPES = ('cd', 'cc', 'sd', 'nta')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _no_comments(src):
    """Blade, PHP and JS comments gone; quoted strings kept.

    ⚠ This repo's own-prose guard firings stand at 24, and the most recent fired
    on a CORRECT file — the comment explaining sd's menu order names
    `defaultSection['sd']`. Every scanner below reads code, so every scanner
    below strips prose first.
    ⚠ `//` is honoured only OUTSIDE a string, because a dataset description
    legitimately contains `http://labs.council.nyc/...` and a naive strip eats
    the rest of that line.
    """
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    out, i, n, quote = [], 0, len(src), None
    while i < n:
        c = src[i]
        if quote:
            if c == '\\' and i + 1 < n:
                out.append(src[i:i + 2]); i += 2; continue
            if c == quote:
                quote = None
            out.append(c); i += 1; continue
        if c in "'\"":
            quote = c; out.append(c); i += 1; continue
        if c == '/' and src.startswith('//', i):
            j = src.find('\n', i)
            i = n if j < 0 else j
            continue
        out.append(c); i += 1
    return ''.join(out)


def _fn(src, name):
    """One python function's source, by name."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError('%s is gone from the router' % name)


def _code(node):
    """`ast.unparse` minus the docstring.

    ⚠ Twelfth own-prose firing in this repo was a scan for `MAX(` matching the
    docstring that explains why a `MAX()` would be wrong.
    """
    body = list(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return '\n'.join(ast.unparse(b) for b in body)


def _strings(node):
    """Every string literal in a node.

    ⚠⚠ READ THE LITERALS, NEVER `ast.unparse`. Unparse ESCAPES quotes inside a
    string, so a scan for SQL punctuation over unparsed source silently matches
    nothing and the guard stays green against a landed mutation.
    """
    return [n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


# ============================================ the api: what the payload claims

def _groups_fn():
    """The REAL `_district_groups`, executed with the router's own constants.

    ⚠ The two module-level tuples are read out of the router too, never retyped:
    a harness that re-declares the thing it guards measures a different system,
    which is the defect this repo recorded for the org-crosswalk suffix list.
    """
    src = _read(ROUTER)
    tree = ast.parse(src)
    consts = [n for n in tree.body
              if isinstance(n, ast.Assign)
              and any(getattr(t, 'id', '').startswith(('DISTRICT_TYPES',
                                                       '_GEOMETRY_ONLY_TYPES'))
                      for t in n.targets)]
    assert len(consts) == 2, (
        'the router no longer declares both DISTRICT_TYPES and '
        '_GEOMETRY_ONLY_TYPES, so this harness would exec against defaults')
    mod = ast.Module(body=consts + [_fn(src, '_district_groups')], type_ignores=[])
    ns = {}
    exec(compile(mod, '<groups>', 'exec'), ns)
    return ns['_district_groups']


def test_the_district_sort_is_numeric_aware():
    """⚠⚠ `dist` IS TEXT, SO A PLAIN `ORDER BY` IS LEXICOGRAPHIC.

    Measured on the project carrying the most council districts (850HWCRCDB, 45
    of them): the section rendered `1, 10, 11, 12, 14, … 2, 20, 21`. `cd` hid it
    because every code is three digits, and `nta` is genuinely text.

    The guard reads the STRING LITERAL the query is built from, because that is
    where the ordering lives.
    """
    sql = ' '.join(_strings(_fn(_read(ROUTER), '_districts')))
    assert 'capital_project_districts' in sql, 'this is no longer the district query'
    assert 'ORDER BY' in sql, 'the district query no longer orders its rows'
    order = sql[sql.index('ORDER BY'):]
    assert 'lpad' in order.lower(), (
        'the district order is lexicographic again — council and school district '
        'ids are text, so 10 sorts before 2')
    assert re.search(r"\[0-9\]\+", order), (
        'nothing distinguishes a numeric district id from an NTA name, so either '
        'the names are being padded or the numbers are not')


def test_every_boundary_set_is_answered_even_when_it_has_nothing():
    """⚠ ALL FOUR TYPES, ALWAYS. An omitted row and an empty one are
    indistinguishable to a reader, and here the absence is often the finding.

    Behavioural: the real function is called, not inspected.
    """
    groups = _groups_fn()

    got = groups([{'dist_type': 'cd', 'dist': '107', 'method': 'community_board_text'}],
                 has_geometry=False)
    assert [g['dist_type'] for g in got] == list(TYPES), (
        'the payload no longer carries one entry per boundary set, in a fixed '
        'order: %r' % [g['dist_type'] for g in got])


def test_a_count_that_cannot_be_asked_is_null_and_a_real_zero_is_zero():
    """⚠⚠ INVARIANT 20 ON THIS SURFACE, AND BOTH STATES ARE REAL.

    `cc`/`sd`/`nta` can only be placed by geometry. With no geometry the honest
    answer is "we cannot say", and rendering `0` would tell a reader the City
    placed this project in no school district. With geometry, `0` is a finding —
    20 / 19 / 21 projects really do fall outside a boundary set.

    ⚠ `cd` always answers a number, because the community-board text fallback
    places it without geometry.
    """
    groups = _groups_fn()
    rows = [{'dist_type': 'cd', 'dist': '107', 'method': 'community_board_text'}]

    no_geom = {g['dist_type']: g['count'] for g in groups(rows, has_geometry=False)}
    assert no_geom['cd'] == 1, 'the community district was not counted'
    for t in ('cc', 'sd', 'nta'):
        assert no_geom[t] is None, (
            '%s reads %r with no published geometry — a 0 there claims the City '
            'placed this project in no %s district, which it never said'
            % (t, no_geom[t], t))

    with_geom = {g['dist_type']: g['count'] for g in groups(rows, has_geometry=True)}
    for t in ('cc', 'sd', 'nta'):
        assert with_geom[t] == 0, (
            '%s reads %r on a project WITH geometry — the spatial join ran and '
            'found nothing, which is a finding and must not read as unknown'
            % (t, with_geom[t]))


def test_the_geometry_only_types_are_the_measured_ones():
    """⚠ The three types that need geometry are declared, not guessed.

    Measured over the whole crosswalk 2026-09-10: `cc` 5,810 rows, `sd` 5,530,
    `nta` 6,815 — 100% `method = 'geometry'`. `cd` is 9,842 text + 5,837
    geometry. If a future builder gives one of these three a second method, this
    set is what has to move with it.
    """
    src = _read(ROUTER)
    tree = ast.parse(src)
    got = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, 'id', None) == '_GEOMETRY_ONLY_TYPES' for t in node.targets):
            got = set(ast.literal_eval(ast.unparse(node.value)))
    assert got == {'cc', 'sd', 'nta'}, (
        '_GEOMETRY_ONLY_TYPES is %r — `cd` has a text fallback and must never be '
        'in it, or a project with a published community board would report its '
        'community district as unknown' % (got,))


# ================================================= the view: what a reader sees

def _section(view):
    """The district section's markup, between its heading and its table close."""
    i = view.index('id="where"')
    j = view.index('</table>', i)
    return view[i:j]


def test_the_section_renders_one_row_per_boundary_set():
    view = _no_comments(_read(VIEW))
    sec = _section(view)
    assert '$distGroups' in sec, (
        'the section no longer iterates the payload groups, so a boundary set '
        'with nothing can be omitted again')
    assert 'DistrictName::PLURAL' in sec, (
        'the row label is not the one naming owner')


def test_only_the_sets_the_project_is_in_are_rendered():
    """⚑ OWNER DECISION, 2026-09-10 — and this guard is RE-EXPRESSED, not relaxed.

    It used to assert the opposite: that a number, `0` and "we cannot say"
    render as three different things, with the `null` branch tested BEFORE the
    `0` branch because PHP says `null == 0`. The owner saw the result — three
    rows reading "Not determinable" above one row carrying data — and asked for
    the empty sets to be dropped.

    ⚠ THE REASONING THAT MADE THE OLD RULE RIGHT HAS NOT GONE AWAY, IT HAS
    MOVED. An omitted row and an empty one are indistinguishable, so the fact
    the empty rows carried is now carried by the sentence below the table, which
    states there is no published location and therefore only one kind of
    placement. `test_the_placement_sentence_says_why_the_other_sets_are_absent`
    is what stops that sentence being dropped too.

    ⚠ And the PAYLOAD still answers for all four including the null/zero
    distinction — `test_a_count_that_cannot_be_asked_is_null_and_a_real_zero_is_zero`
    is untouched. This is a rendering choice; nothing measured was lost.
    """
    view = _no_comments(_read(VIEW))
    assert re.search(r'\$distGroups\s*=\s*array_values\(array_filter\(', view), (
        'the view no longer filters the groups, so a set the project is in no '
        'district of renders a row again')
    sec = _section(view)
    # ⚠ The dead branches must be DELETED, not gated. `$n` is always >= 1 after
    # the filter, so a `$n === 0` arm is unreachable — and dead code that reads
    # as a live claim is worse than no code, which is the call this repo already
    # made for the three unrouted `*A` orphans.
    assert not re.search(r'\$n\s*===\s*(?:0|null)', sec), (
        'an unreachable zero/null branch is still in the section')
    assert 'Not determinable' not in sec and 'No districts identified' not in sec, (
        'the empty-state copy is still rendered from a branch that cannot fire')


def test_a_single_district_shows_its_name_and_many_show_a_count():
    """⚠⚠ THE SINGLE-DISTRICT ROW IS THE DEFAULT, NOT THE FALLBACK — measured:
    cc 4,001 of 4,527 · nta 3,786 of 4,526 · sd 4,067 of 4,528 projects are in
    exactly one. Only `cd` is mostly many (3,611 of 9,879).
    """
    sec = _section(_no_comments(_read(VIEW)))
    assert re.search(r'\$n\s*===\s*1', sec), 'the single-district case is gone'
    assert 'DistrictName::unit' in sec, (
        'the many case no longer renders a counted unit, so the reader is told '
        'a bare number with no noun')
    assert '<details>' in sec and '<summary' in sec, (
        'the many case is no longer openable in place')


def test_every_district_the_section_renders_is_a_link():
    """⚠ Invariant 4 from the other side: an unlinked district is how `sd` sat
    unreachable from this page for as long as its own page 404ed.
    """
    sec = _section(_no_comments(_read(VIEW)))
    assert "route('districtsPreset'" in sec, 'no district is linked'
    assert not re.search(r"dist_type'\]\s*===\s*'sd'", sec), (
        'school districts are singled out — that page serves now')
    # ⚠⚠ PER ECHO, NOT PER SECTION — the first draft asserted
    # `'DistrictName::label' in section`, which stayed GREEN when the
    # single-district branch was mutated to echo `$ids[0]` raw, because the
    # many-branch still contained the string. A word in the section is not the
    # branch that renders it.
    for m in re.finditer(r'\{\{(.*?)\}\}', sec, re.S):
        expr = m.group(1)
        # ⚠ `$link($id)` is a URL, not a name — it is the one echo that may
        # carry a raw id, and excluding it is what keeps this guard falsifiable
        # instead of red on correct code.
        if re.search(r'\$ids?\b', expr) and '$link(' not in expr:
            assert 'DistrictName::' in expr, (
                'a district id is echoed raw: %r — it must go through the one '
                'naming owner, or the reader is shown a stored key' % expr.strip())


def test_the_placement_sentence_says_why_the_other_sets_are_absent():
    """⚠⚠ THIS IS WHAT THE DROPPED ROWS LEFT BEHIND, so it is the load-bearing
    half of the owner's change. With the empty sets no longer rendered, the only
    thing telling a reader why a project shows one boundary set and not four is
    this sentence — and the fact it must carry is that the City publishes no
    location, which is also why there is no pin on the map.

    ⚠ Invariant 6: it is outside every disclosure. It used to be two sentences
    in two columns (the map's "The City publishes no location for this project"
    and a separate reason line); the owner asked for one, so the guard follows
    the property rather than the wording.
    """
    view = _no_comments(_read(VIEW))
    m = re.search(r'\$placedLine\s*=\s*!\$methods(.*?);\n', view, re.S)
    assert m, 'the placement sentence is no longer composed'
    expr = m.group(1)
    assert '$hasGeom' in expr, (
        'the sentence no longer varies on whether the City published a location, '
        'so a project with none is not told why it shows one boundary set')
    assert 'no location' in expr, (
        'the sentence stopped saying the City publishes no location — the fact '
        'the dropped rows used to carry')
    echo = [x for x in re.finditer(r'\{\{([^}]*\$placedLine[^}]*)\}\}', view)]
    assert echo, 'the placement sentence is never echoed'
    for d in re.finditer(r'<details\b.*?</details>', view, re.S):
        assert not (d.start() < echo[0].start() < d.end()), (
            'the placement sentence is behind a click')


def test_the_map_note_renders_only_when_something_will_replace_it():
    """⚠⚠ A SPINNER THAT NEVER RESOLVES — reported by the owner, 2026-09-10.

    `#mapNote` ships the text "Loading the published outline…" and the AJAX that
    replaces it sits inside the geometry branch. The element was rendered
    whenever there was a MAP, and a project with no published location still has
    one (its districts are highlighted), so that page said "Loading…" for ever,
    on a page that had finished loading.

    ⚠ Invariant 7's fourth thing: it is not a number, not a zero and not an em
    dash — it says nothing at all while looking like it is about to say
    something.
    """
    view = _no_comments(_read(VIEW))
    i = view.index('id="mapNote"')
    before = view[:i]
    # The nearest enclosing Blade conditional must test geometry.
    opens = [m for m in re.finditer(r'@if\((.*?)\)', before)]
    assert opens, 'the map note is no longer inside any conditional'
    assert '$hasGeom' in opens[-1].group(1), (
        'the map note is not gated on geometry, so a project with no published '
        'location renders a loading line nothing will ever replace: gated on %r'
        % opens[-1].group(1))


# ========================================== one owner for how a district is named

def test_the_district_name_prefix_has_exactly_one_owner():
    """⚠⚠ IT HAD THREE, AND THEY DISAGREED — Schema::districtFromFile(),
    Organizations::sitemap() (which carried NO `sd` key) and districts.blade.php's
    JS. Nothing was visibly broken, because the sitemap never asks for `sd`:
    correct by luck in the one place the copies differed.

    The scan looks for the VALUE, not for a variable name, because a fourth copy
    would be spelled differently and mean the same thing.
    """
    owner = os.path.realpath(NAME)
    offenders = []
    for base in (APP, VIEWS):
        for root, _, files in os.walk(base):
            for fn in files:
                if not fn.endswith('.php'):
                    continue
                path = os.path.realpath(os.path.join(root, fn))
                if path == owner:
                    continue
                body = _no_comments(_read(path))
                if re.search(r"'City Council District\s", body):
                    offenders.append(os.path.relpath(path, ROOT))
    assert not offenders, (
        'these files spell the district name prefix themselves instead of '
        'reading App\\Custom\\DistrictName: %r' % offenders)
    # Non-vacuity: the scan must have been able to see the owner's own copy.
    assert re.search(r"'City Council District\s", _no_comments(_read(NAME))), (
        'the scanner cannot match the owner itself, so it would report a clean '
        'tree whatever the other files contain')


def test_the_borough_is_a_lookup_and_never_a_parse_of_the_id():
    """⚠⚠ 27 OF THE 86 `cd` CODES IN THE CROSSWALK ARE NOT COMMUNITY DISTRICTS.

    `100/200/300/400/500` (4,370 rows) are a borough with no district;
    `164 226 227 228 355 356 480-484 595` are DCP Joint Interest Areas; the
    retired series also publishes `213`-`218`, and the Bronx has twelve
    community districts. A positional parse renders `213` as "Bronx Community
    District 13" — confidently, and wrongly.

    So the borough comes from `DistDatasets::$cdAltName`, a curated map of the
    59 real ones, and a code it does not carry gets no borough at all.
    """
    body = _no_comments(_read(NAME))
    m = re.search(r'function borough\([^)]*\)\s*\{(.*?)\n    \}', body, re.S)
    assert m, 'DistrictName::borough is gone'
    fn = m.group(1)
    assert 'cdAltName' in fn, (
        'the borough no longer comes from the curated community-district map')
    assert not re.search(r'\$id\s*\[\s*0\s*\]|substr\(\s*\$id', fn), (
        'the borough is being parsed out of the id — that renders 213 as a Bronx '
        'community district, and there is no such thing')


def test_only_cd_gets_a_borough():
    """⚠ `cc` and `sd` deliberately get none: this repo already measures council
    district 8 as Manhattan 67% / Bronx 32% (East Harlem + Mott Haven), so a
    single borough on a council district would be false.
    """
    body = _no_comments(_read(NAME))
    m = re.search(r'function borough\([^)]*\)\s*\{(.*?)\n    \}', body, re.S)
    fn = m.group(1)
    assert re.search(r"!==\s*'cd'", fn), (
        'borough() no longer restricts itself to community districts')


# ================================================= school districts have a section

def test_school_districts_have_a_capital_projects_section():
    """⚠⚠ THE 404 WAS ONE MAP KEY WIDE. Measured 2026-09-10 before the fix:

        /districtXHR/sd/4/projects              404
        /get/capital/projects/by-district/sd/4  200 — 144 rows
        /get/capital/stats/sd/4                 200 — 144 projects

    `get('projects', $type)` returns null for a type the contract's `map` omits,
    and `projectSectionXHR` abort(404)s on null. Everything else was already
    sd-ready.
    """
    ds = _no_comments(_read(DS))
    i = ds.index("'projects' => [")
    seg = ds[i:ds.index("'map' =>", i) + 400]
    m = re.search(r"'map' => \[(.*?)\]", seg, re.S)
    assert m, "the projects contract has no map"
    keys = set(re.findall(r"'([a-z]{2,3})' =>", m.group(1)))
    assert keys == set(TYPES), (
        "the projects contract's map covers %r — a type missing from it has no "
        "capital section, whatever the endpoint serves" % sorted(keys))
    menu = ds[ds.index('public $menu'):]
    sd = menu[menu.index("'sd' => ["):]
    sd = sd[:sd.index('];')]
    assert "'projects'" in sd, "sd's menu no longer offers its capital section"


def test_the_two_project_sections_do_not_share_a_label():
    """⚠⚠ GIVING `sd` A CAPITAL SECTION PUT TWO MENU ITEMS BOTH READING
    "Projects" IN ONE MENU. `projects` is the capital spine;
    `school-projects` is the SCA's `scacapitalprojectschedules` — school
    CONSTRUCTION. `$list` is flat, so the label cannot vary by district type.
    """
    ds = _no_comments(_read(DS))
    block = ds[ds.index('public $list'):]
    block = block[:block.index('];')]
    labels = dict(re.findall(r"'([a-z0-9-]+)' => '([^']+)'", block))
    assert labels.get('projects') and labels.get('school-projects'), (
        'one of the two project sections has lost its label')
    assert labels['projects'] != labels['school-projects'], (
        'both project sections render as %r, so a school district shows two '
        'identical menu items' % labels['projects'])


def test_the_projects_section_never_reaches_the_generic_table_endpoint():
    """⚠ The `projects` contract's `map` VALUES are a presence marker, not
    columns — the contract was repointed at the spine and builds its own URL in
    `projectSectionXHR`. Only `sectionXHR` interpolates `map[$type]` into a `f=`
    parameter, so if `projects` ever routed there it would send the crosswalk's
    table name as a column name.
    """
    ctl = _no_comments(_read(DISTCTL))
    assert re.search(r"\(\s*\$section\s*==\s*'projects'\s*\)\s*\?\s*\$this->projectSectionXHR",
                     ctl, re.S), (
        "`projects` no longer routes to projectSectionXHR — sectionXHR would "
        "interpolate the contract's map value as a column name")
