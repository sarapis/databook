""""What data does the City buy?" — the section plan's §5c Phase A lens.

⚠⚠ THE PROPERTY WORTH GUARDING HERE IS SEMANTIC AND INVISIBLE TO EVERY
STRUCTURAL CHECK. The page's two halves OVERLAP: measured on prod 2026-09-14,
Cyclomedia ($20.00M) and Sanborn Maps ($3.12M) are content subscriptions filed
under *Geospatial / GIS*, so **$23.1M of the $38.5M GIS figure — 60% — is
imagery the City BUYS, not a tool it licenses to analyse data**. Adding the two
halves counts that money twice, and the result is a plausible-looking number
with a status code of 200 and the right row counts behind it.

So: the endpoint must serve no key equal to the sum, every tool row's two
columns must close on the figure the Products page already publishes, and the
membership of the lens must come from the seed rather than a tuple in the
router — because the obvious derivation (catalogue_category = 'data-analytics')
silently drops the largest member.

⚠ Every guard here was mutation-verified with the two assertions in order: the
mutation LANDED (the mutated text is present / the mutated behaviour is real),
then the guard FIRED. See the session record.
"""
import ast
import csv
import importlib.util
import io
import re
import os

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
API = os.path.join(ROOT, 'api')
VOCAB = os.path.join(API, 'seed', 'license_capability_vocab.csv')


def _read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
        return fh.read()


def _expanded(rel):
    """A view with every @include expanded IN PLACE (bladeview.py). The Data
    band lives in `partials/data-book` since 2026-09-23, shared by the Overview
    and the Data page, so a file-only read would measure less than renders."""
    spec = importlib.util.spec_from_file_location(
        'bladeview', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bladeview.py'))
    bv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bv)
    return bv.expand(os.path.join(ROOT, rel))


def _vocab():
    with io.open(VOCAB, newline='', encoding='utf-8') as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith('#')]
    return list(csv.DictReader(lines))


def _real_licenseclass():
    """⚠⚠ LOADED BY PATH AND THEN ASSERTED, because conftest.py replaces the whole
    `modules` package with a MagicMock — `from modules import licenseclass` inside
    the router yields a mock whose resolve() returns a MagicMock, so every class
    comparison silently fails and a behavioural test measures nothing. This repo
    has shipped a guard that "passed" against exactly that mock."""
    spec = importlib.util.spec_from_file_location(
        '_real_licenseclass', os.path.join(API, 'modules', 'licenseclass.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert isinstance(mod.CLASSES, tuple) and 'content-subscription' in mod.CLASSES, \
        'the real licenseclass did not load — this test would measure a mock'
    assert mod.resolve('x', 'y', {}, {})['class'] == '', 'resolve() is not the real one'
    return mod


def _fn_src(name):
    """The source of one function in routers/licenses.py, docstring stripped.

    ⚠ Docstring-stripped because this file's own prose quotes the strings the
    scans below look for — the own-prose guard failure this repo has recorded
    more than a dozen times."""
    src = _read('api/routers/licenses.py')
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            body = list(node.body)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:]
            return '\n'.join(ast.unparse(n) for n in body)
    raise AssertionError(f'{name}() not found in routers/licenses.py')


# --------------------------------------------------------------------------
# the vocabulary seed
# --------------------------------------------------------------------------

def test_the_data_lens_column_is_well_formed():
    rows = _vocab()
    assert len(rows) > 40, f'the vocabulary parsed as only {len(rows)} rows'
    marked = {r['capability'].strip() for r in rows
              if (r.get('data_lens') or '').strip()}
    assert marked, 'no capability is marked for the data lens — the page would be empty'
    for r in rows:
        v = (r.get('data_lens') or '').strip()
        assert v in ('', 'analyse'), \
            f"{r['capability']}: data_lens={v!r}; the only value is 'analyse'"


def test_the_lens_is_not_the_catalogue_category_and_that_is_the_point():
    """⚠⚠ THE GUARD THAT RECORDS WHY THIS IS A LOOKUP. The tempting derivation is
    `catalogue_category == 'data-analytics'`. It DROPS `geospatial-gis`, whose
    catalogue home is `geospatial` and which is the LARGEST member of the lens
    ($38.5M against BI's $21.0M on prod). A rule that silently omits the biggest
    row is the "regex doing a semantic job" defect this repo keeps paying for.

    If someone ever "simplifies" the seed back to the category, this fails — and
    it fails with the reason attached rather than as a mystery."""
    rows = _vocab()
    marked = {r['capability'].strip() for r in rows
              if (r.get('data_lens') or '').strip() == 'analyse'}
    derived = {r['capability'].strip() for r in rows
               if (r.get('catalogue_category') or '').strip() == 'data-analytics'}
    assert 'geospatial-gis' in marked, \
        'geospatial-gis left the lens — it is its largest member and the whole ' \
        'reason membership is stated rather than derived'
    assert 'geospatial-gis' not in derived, \
        'geospatial-gis moved into the data-analytics catalogue category; if that ' \
        'is deliberate, the derivation is now safe and this guard should be redone'
    assert marked - derived, \
        'the lens is now exactly the catalogue category, so it could have been ' \
        'derived — which would drop whichever member sits outside it next time'


# --------------------------------------------------------------------------
# the router reads the seed, and resolves the class through the one owner
# --------------------------------------------------------------------------

def test_the_router_reads_the_lens_from_the_seed_and_carries_no_tuple_of_its_own():
    body = _fn_src('data_lens')
    assert '_data_lens_caps()' in body, \
        'data_lens() no longer calls _data_lens_caps() — the membership has moved ' \
        'into the router, where the seed can no longer change it'
    marked = {r['capability'].strip() for r in _vocab()
              if (r.get('data_lens') or '').strip() == 'analyse'}
    # ⚠ Reads the AST's STRING LITERALS, never the raw text: the function's own
    # prose names these tags, and a text scan would fire on the explanation.
    lits = {n.value for n in ast.walk(ast.parse(body))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    leaked = marked & lits
    assert not leaked, \
        f'data_lens() names {sorted(leaked)} directly; membership belongs to the seed'


def test_the_purchase_class_goes_through_the_one_resolver():
    """⚠ Re-deriving the class here is how a lens comes to disagree with the table
    it was reached from — the defect modules/licenseclass exists to prevent."""
    body = _fn_src('data_lens')
    assert 'licenseclass.resolve' in body, \
        'data_lens() no longer resolves the class through modules/licenseclass'
    assert 'product_classes' in body and 'classes' in body, \
        'the resolver is being called without both class layers, so product-grain ' \
        'overrides would be ignored here and honoured on the Products page'


# --------------------------------------------------------------------------
# behaviour, against the REAL endpoint and the REAL resolver
# --------------------------------------------------------------------------

def _rows():
    """A fixture with the shape the real defect has: one capability holding both
    a tool licence and a content subscription."""
    def row(cid, fam, prod, agency, val, slug=''):
        return {"contract_id": cid, "family": fam, "product": prod, "agency": agency,
                "vendor_name": f"V{cid}", "value": float(val), "slug": slug,
                "expiring": False, "competitive": True, "no_competition": False, "is_generic": False,
                "fam_curated": True, "start_date": "", "end_date": "",
                "vendor_id": None, "current_amount": float(val), "award_amount": 0.0}
    return [
        row("c1", "Cyclo", "Cyclo", "DOITT", 20_000_000),       # content, in the lens
        row("c2", "ArcThing", "ArcThing", "DOITT", 5_000_000),  # tool, in the lens
        row("c3", "Dash", "Dash", "DSS", 1_000_000),            # tool, in the lens
        row("c4", "LawBooks", "LawBooks", "LAW", 3_000_000),    # content, NOT in the lens
        row("c5", "Courses", "Courses", "DCAS", 100_000),       # content, training
        row("c6", "Firewall", "Firewall", "NYPD", 700_000),     # neither
    ]


def _classes():
    return {
        "Cyclo":    {"class": "content-subscription", "capability": "geospatial-gis", "tier": "curated"},
        "ArcThing": {"class": "software-licence",     "capability": "geospatial-gis", "tier": "curated"},
        "Dash":     {"class": "software-licence",     "capability": "bi-dashboards",  "tier": "auto"},
        "LawBooks": {"class": "content-subscription", "capability": "other",          "tier": "curated"},
        "Courses":  {"class": "content-subscription", "capability": "training-content", "tier": "auto"},
        "Firewall": {"class": "software-licence",     "capability": "network-security", "tier": "auto"},
    }


def _stub_agencyalias():
    """The REAL agencyalias, with only its database lookups stubbed.

    ⚠⚠ `conftest.py` replaces the whole `modules` package with a MagicMock, so
    `from modules import agencyalias` binds a mock whose `resolve_many` is NOT
    awaitable — `TypeError: object MagicMock can't be used in 'await'`. Same
    trap `_real_licenseclass` above exists for, one module over.

    ⚠⚠ AND IT IS THE REAL MODULE, NOT A HAND-WRITTEN STAND-IN. A stub whose
    `group_by_org` passed rows straight through would make every closure test
    below measure a DIFFERENT system from production — the harness rule this
    repo has paid for more than once. Loading the real file keeps the merge, the
    label rule and the set-union under test; only the two DB calls are replaced.

    ⚠ They answer "nothing resolves" ON PURPOSE. These tests are about the lens's
    own arithmetic — the class split, the overlap, the reviewed share — and an
    org id is an enrichment layered on top. It also proves the lens still answers
    correctly when NOTHING resolves, which is the honest-degradation case a real
    map would hide."""
    spec = importlib.util.spec_from_file_location(
        '_real_agencyalias', os.path.join(API, 'modules', 'agencyalias.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(getattr(mod, 'group_by_org', None)), \
        'the real agencyalias did not load — this test would measure a stub'

    async def _resolve_many(pg, names, logger=None):
        return {}

    async def _org_names(pg, ids, logger=None):
        return {}

    mod.resolve_many = _resolve_many
    mod.org_names = _org_names
    return mod


async def _payload():
    import routers.licenses as L
    L.licenseclass = _real_licenseclass()
    L.agencyalias = _stub_agencyalias()

    async def fake_load():
        return {"available": True, "rows": _rows(), "classes": _classes(),
                "product_classes": {}, "descriptions": {}}

    real_load = L._load
    L._load = fake_load
    try:
        return await L.data_lens()
    finally:
        L._load = real_load


@pytest.mark.asyncio
async def test_no_key_in_the_payload_adds_the_two_halves():
    """⚠⚠ THE GUARD FOR THE DEFECT. The sum counts imagery bought as data
    alongside the licence to read it, and nothing about the result looks wrong."""
    d = await _payload()
    banned = d["content"]["value"] + d["tools"]["tool_value"]
    # Non-vacuity: both halves must be real, or "no key equals the sum" is
    # satisfied by a payload that computed nothing.
    assert d["content"]["value"] > 0 and d["tools"]["tool_value"] > 0, d
    assert d["overlap"]["contracts"] > 0, 'the fixture no longer exercises an overlap'

    found = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            if abs(float(node) - banned) < 0.01:
                found.append(path)

    walk(d, "payload")
    assert not found, \
        f'{found} equals content.value + tools.tool_value ({banned:,.0f}) — the two ' \
        f'halves overlap and their sum is not a quantity anybody can act on'


@pytest.mark.asyncio
async def test_every_tool_row_splits_into_exactly_its_own_total():
    """The two columns close on the row, and the row closes on what the Products
    page's function table publishes for the same tag — so this page cannot
    disagree with the table it links to."""
    import routers.licenses as L
    d = await _payload()
    rollup = {a["key"]: a for a in L._capability_rollup(_rows(), _classes())}
    assert d["tools"]["rows"], 'no tool rows — the fixture or the lens is empty'
    for r in d["tools"]["rows"]:
        assert abs(r["content_value"] + r["tool_value"] - r["value"]) < 0.01, r
        assert r["content_contracts"] + r["tool_contracts"] == r["contracts"], r
        ref = rollup.get(r["key"])
        assert ref is not None, f'{r["key"]} is not in the function rollup at all'
        assert abs(ref["value"] - r["value"]) < 0.01 and ref["contracts"] == r["contracts"], \
            f'{r["key"]}: {r["value"]}/{r["contracts"]} here vs ' \
            f'{ref["value"]}/{ref["contracts"]} on the Products page'
    # ⚠⚠ AND THE SPLIT ITSELF, because the three assertions above are ALL
    # preserved by sending every row to one side: content + tool still equals the
    # total, the counts still add up, and the row still matches the rollup.
    # Mutation-verified — `side = "tool"` for everything passed this test until
    # these two lines existed. A closure check is not a correctness check.
    rows = {r["key"]: r for r in d["tools"]["rows"]}
    assert abs(rows["geospatial-gis"]["content_value"] - 20_000_000) < 0.01, \
        'the content subscription inside a lens capability was counted as a tool'
    assert abs(rows["geospatial-gis"]["tool_value"] - 5_000_000) < 0.01, \
        'the tool licence inside a lens capability was counted as content'
    assert rows["bi-dashboards"]["content_value"] == 0, \
        'a capability with no content subscription reports one'


@pytest.mark.asyncio
async def test_the_overlap_is_reported_rather_than_netted_off():
    d = await _payload()
    fams = {r["family"] for r in d["overlap"]["rows"]}
    assert "Cyclo" in fams, \
        'the content row inside a lens capability is missing from the overlap — ' \
        'netting it off is what hides the finding'
    assert abs(d["overlap"]["value"] - 20_000_000) < 0.01, d["overlap"]


@pytest.mark.asyncio
async def test_unclassified_and_unclassifiable_are_kept_apart():
    """⚠ "classified, function not identifiable" and "never classified" are
    different claims; folding them together reports an unanswered question as an
    answered one. Invariant 20's shape at a new surface."""
    import routers.licenses as L
    d = await _payload()
    keys = [k["key"] for k in d["content"]["by_kind"]]
    assert L._OTHER_CAPABILITY in keys, 'the abstention bucket vanished from by_kind'
    # ...and both sort last, whatever their size.
    tail = keys[-2:] if '' in keys else keys[-1:]
    assert L._OTHER_CAPABILITY in tail, \
        f'the abstention bucket is not sorted last: {keys}'


@pytest.mark.asyncio
async def test_by_kind_closes_on_the_class_total():
    """A breakdown that silently drops rows reads as the whole class."""
    d = await _payload()
    c = d["content"]
    assert sum(k["contracts"] for k in c["by_kind"]) == c["contracts"]
    assert abs(sum(k["value"] for k in c["by_kind"]) - c["value"]) < 0.01


@pytest.mark.asyncio
async def test_the_overlap_says_whether_a_human_classified_it():
    """⚠⚠ THE OVERLAP IS THIS PAGE'S STRONGEST CLAIM, so it must say who made the
    judgement it rests on. Measured on prod 2026-09-14 through the shipped code:
    99.8% of the $23.17M overlap is `curated` — Cyclomedia $20.00M and Sanborn
    Maps $3.12M by hand, Lightcast $0.05M automatic. "The section files $23.1M of
    purchased imagery under GIS" is a finding when a human classified those two
    and a suggestion otherwise, and the page carries an Analysis banner saying it
    is the second by default.

    ⚠ SERVED, never typed, and never re-derived from the family table: the tier
    comes back from licenseclass.resolve() alongside the class, so the row's
    label and the row's class cannot come from different judgements."""
    d = await _payload()
    rows = {r["family"]: r for r in d["overlap"]["rows"]}
    assert rows, 'the overlap no longer reports rows'
    for r in rows.values():
        assert r.get("tier") in ("curated", "auto", "mixed", ""), r
    assert rows["Cyclo"]["tier"] == "curated", \
        'a hand-classified overlap row is not reported as one'
    cv = d["overlap"]["curated_value"]
    assert 0 < cv <= d["overlap"]["value"] + 0.01, (cv, d["overlap"]["value"])
    assert abs(cv - 20_000_000) < 0.01, cv


@pytest.mark.asyncio
async def test_a_row_classified_at_two_tiers_reports_mixed():
    """⚠⚠ ITS OWN FIXTURE, BECAUSE THE SHARED ONE CANNOT REACH THIS STATE — and
    that is exactly why the first version of the tier guards was SILENT when
    `mixed` was collapsed to whichever tier happened to come out of the set. A
    guard for a case nothing exercises asserts nothing; assert something
    SURVIVES before asserting something does not.

    A family is `auto` and one of its two products carries a CURATED override, so
    its two contracts resolve at two tiers. Claiming `curated` for that row is the
    harmful direction — it would tell a reader a human checked a judgement nobody
    checked."""
    import routers.licenses as L
    L.licenseclass = _real_licenseclass()
    L.agencyalias = _stub_agencyalias()

    def row(cid, prod, val):
        return {"contract_id": cid, "family": "Imagery", "product": prod,
                "agency": "DOITT", "vendor_name": "V", "value": float(val),
                "slug": "", "expiring": False, "competitive": True, "no_competition": False,
                "is_generic": False, "fam_curated": False, "start_date": "",
                "end_date": "", "vendor_id": None, "current_amount": float(val),
                "award_amount": 0.0}

    async def fake_load():
        return {"available": True,
                "rows": [row("m1", "Aerial", 1_000), row("m2", "Oblique", 2_000)],
                "classes": {"Imagery": {"class": "content-subscription",
                                        "capability": "geospatial-gis", "tier": "auto"}},
                # ⚠ PRODUCT-grain, which is what makes the two contracts differ.
                "product_classes": {"AERIAL": {"class": "content-subscription",
                                               "tier": "curated"}},
                "descriptions": {}}

    real = L._load
    L._load = fake_load
    try:
        d = await L.data_lens()
    finally:
        L._load = real

    rows = d["overlap"]["rows"]
    assert len(rows) == 1, rows
    assert rows[0]["tier"] == "mixed", \
        f'a row holding a curated and an auto classification reports ' \
        f'{rows[0]["tier"]!r} — claiming one of them is the harmful direction'
    # ...and the curated total must not swallow the whole row.
    assert d["overlap"]["curated_value"] == 0, d["overlap"]


def test_the_overlap_table_renders_three_states_not_two():
    """⚠ Reviewed / automatic / MIXED. Collapsing mixed into either claims
    something the data does not support, and claiming review is the harmful
    direction — the rule licenseclass.mix() already applies one layer down."""
    v = _read('app/resources/views/procurement/digital-reform-data.blade.php')
    j = v.index('<h2 class="mb-2">Counted by both halves</h2>')
    block = v[j:]
    for needle in ("'curated'", "'mixed'", "@else"):
        assert needle in block, f'the overlap table no longer distinguishes {needle}'
    assert "$ovSentence" in v and "curated_value" in v, \
        'the page no longer states how much of the overlap a human classified'
    # ⚠ The column was ADDED, so every colspan under it must have moved with it —
    # an empty-state row spanning the old width renders a ragged table.
    assert 'colspan="4"' not in block, \
        'an empty-state colspan still names the pre-column width'


@pytest.mark.asyncio
async def test_the_reviewed_share_is_computed_and_rendered():
    """⚠⚠ THE SECTION PLAN'S §5c SAID "every row already tier-curated" AND PROD
    SAYS 11 OF 100 FAMILIES ARE — carrying 87.5% of the value. Both are true and
    neither implies the other: by money this view is reviewed, by product count
    89% of it is the classifier's own judgement. A page that publishes a
    class-based finding without saying which rows a human looked at is the
    unreviewed-AI-as-fact hazard this section already carries a banner for.

    ⚠ Through the page's OWN _reviewed(), so this figure and the Products page's
    are one definition rather than two that can drift — the defect that produced
    "88.0%" as literal template text beside a computed 87.7%."""
    import routers.licenses as L
    d = await _payload()
    rev = d["content"].get("reviewed")
    assert rev, 'the content half no longer reports its reviewed share'
    ref = L._reviewed([{"key": k, "value": v} for k, v in
                       [(r["key"], r["value"]) for r in d["content"]["rows"]]],
                      _classes(), d["content"]["value"])
    assert rev == ref, f'{rev} disagrees with the page-wide helper {ref}'
    # Non-vacuity: the fixture must actually hold both a curated and an auto row,
    # or "the share matches" is satisfied by everything being one tier.
    tiers = {c["tier"] for c in _classes().values()}
    assert {"curated", "auto"} <= tiers, 'the fixture no longer exercises a mix'
    assert 0 < rev["share"] < 100, rev


def test_the_page_states_the_reviewed_share_in_both_populations():
    v = _read('app/resources/views/procurement/digital-reform-data.blade.php')
    assert "$content['reviewed']" in v, 'the view no longer reads the reviewed share'
    i = v.index("$revSentence = ")
    sent = v[i:v.index("';", v.index("unreviewed", i))]
    # ⚠ BOTH POPULATIONS. A share of VALUE alone reads as "this is reviewed"
    # while 89% of the products are not; a count alone reads as the opposite.
    assert "$rev['families']" in sent and "$rev['share']" in sent, \
        'the sentence states only one of the two populations'
    assert "$content['families']" in sent, \
        'the reviewed count has no denominator, so it is not a share of anything'


# --------------------------------------------------------------------------
# the page
# --------------------------------------------------------------------------

def test_the_page_is_wired_end_to_end():
    routes = _read('app/routes/web.php')
    assert "'/research/digital-reform/data'" in routes, 'the data page has no route'
    i = routes.index("'/research/digital-reform/data'")
    window = routes[i:i + 220]
    # ⚠ Invariant 6: the array form. The string form resolves against
    # RouteServiceProvider::$namespace, which Laravel 8 removed.
    assert 'ProcurementController::class' in window and "'digitalReformData'" in window, window
    assert "research.digital-reform.data" in window

    ctrl = _read('app/app/Http/Controllers/ProcurementController.php')
    assert 'function digitalReformData' in ctrl
    assert "'/oce/licenses/data'" in ctrl, \
        'the controller no longer reads the data endpoint'

    nav = _read('app/resources/views/sub/menubar.blade.php')
    assert "route('research.digital-reform.data')" in nav, \
        'the Data page is not in the section nav, so it is reachable only by URL — ' \
        'the unlisted-but-publicly-linked state this section already regretted once'


def test_the_view_renders_both_columns_and_never_one_combined_total():
    """⚠ A source check, because the RENDERED check lives in
    scripts/headless/verify_data_lens.py, which derives the forbidden figure from
    the payload and looks for it on the page. This half pins that the split
    exists at all."""
    v = _read('app/resources/views/procurement/digital-reform-data.blade.php')
    for needle in ("tool_value", "content_value"):
        assert needle in v, f'the view no longer renders {needle!r}'
    # ⚠ ANCHORED ON THE COLUMN HEADERS, not on the phrases. "Bought as data" also
    # occurs in the tile label "Bought as data or content", so a bare substring
    # scan survived renaming the actual <th> and passed for the wrong reason.
    # Mutation-verified both ways.
    for th in ('<th class="db-num dl-split-a">Bought as a tool</th>',
               '<th class="db-num">Bought as data</th>'):
        assert th in v, f'the two-column split lost its header: {th!r}'
    # The two halves must never be added in the template either.
    for bad in ("tool_value'] + ", "content_value'] + ", "+ $tools['tool_value']"):
        assert bad not in v, f'the view adds the two halves: {bad!r}'


def test_the_overview_card_reads_the_lens_and_degrades_to_a_clause():
    """⚠⚠ #247's SEAM. ProcurementController NAMES every view-data key, so a
    payload key the Overview reads and the controller never passes renders
    nothing while the page still returns 200 — that defect shipped once and was
    found only by fetching the page. Caught here the moment the card was added:
    the first render was `Undefined variable: dataLens`.

    ⚠ And the honest-degradation half: with the lens unavailable the card must
    ask its question, never leave a gap where a figure was. Verified by renaming
    digital_contract_enrichment out from under it — the card rendered the
    sentence, and the page stayed 200."""
    ctrl = _read('app/app/Http/Controllers/ProcurementController.php')
    i = ctrl.index("function digitalReform(")
    body = ctrl[i:ctrl.index("function digitalReformSearch(")]
    assert "'/oce/licenses/data'" in body, \
        'the Overview no longer reads the data lens for its card'
    assert "'dataBlocks' => $dataBlocks" in body, \
        'the lens figures are computed and never passed to the view — #247 exactly'
    # ⚠ Its own cache key. These entries hold different SHAPES, and a warm entry
    # under a shared key would hand this code a float where it expects a map.
    # ⚠⚠ RE-EXPRESSED 2026-09-16: the single-figure CARD became a full band, so
    # `$dataLens` / `digital_reform_data_lens_v1` were superseded by the richer
    # `$dataBlocks` and REMOVED rather than left as a dead key. The property is
    # the same one and is now checked more generally, below.
    assert "'digital_reform_ov_data_v1'" in body
    # ⚠ GENERALISED from a count of one named key: every cache key in this action
    # must be used exactly once, which is the actual rule those comments state
    # and which a per-key assertion could only ever check for keys it names.
    keys = re.findall(r"Cache::remember\('([a-z0-9_]+)'", body)
    assert keys and len(keys) == len(set(keys)), \
        f'a cache key is reused across shapes in digitalReform(): {keys}'

    view = _expanded('app/resources/views/procurement/digital-reform.blade.php')
    # ⚠ SLICED TO THE SECTION'S END, never a fixed window. A 3000-char slice
    # stopped short of this band's `@else` and reported a correct page as
    # missing its degradation branch — the same fixed-width-window trap that
    # once made a family page look like it had lost rows.
    j = view.index('id="s-data"')
    band = view[j:view.index('</section>', j)]
    assert "@if($db)" in band, \
        'the band no longer branches on whether the lens answered'
    # ⚠⚠ THE BRANCH MUST SAY SOMETHING. Asserting `"@else" in band` is blind to an
    # EMPTY else, which renders the exact defect this is here to prevent — a gap
    # where a figure was. Mutation-verified: deleting the sentence and leaving the
    # @else passed the first version of this guard.
    assert "@else" in band, 'the band has no unavailable branch'
    # ⚠ THE OUTER PAIR, via rindex. The band gained a nested `@if` for the
    # abstention share, so `index("@endif")` found the INNER one — before the
    # outer `@else` — and the slice ran backwards to '', reporting a correct
    # band as having an empty fallback. The available branch always precedes
    # the unavailable one, so the outer pair is the last of each.
    fallback = band[band.rindex("@else") + 5:band.rindex("@endif")]
    assert len(fallback.strip()) >= 20, \
        f'the unavailable branch is empty ({fallback.strip()!r}) — a failed lens ' \
        f'would render a blank band rather than saying so'
    assert 'not available right now' in fallback, \
        'an unavailable lens must say so, never leave a gap where a figure was'
    assert "route('research.digital-reform.data')" in band, \
        'the band no longer links to the page it summarises'


def test_the_nav_order_of_the_existing_pages_is_unchanged():
    """Adding a page must not reorder the five that were there — Vendors last is
    an owner decision, and Products/Data sit together because Data reads the same
    curated layers."""
    nav = _read('app/resources/views/sub/menubar.blade.php')
    order = ['research.digital-reform.contracts', 'research.digital-reform.products',
             'research.digital-reform.data', 'research.digital-reform.agreements',
             'research.digital-reform.vendors']
    idx = [nav.index(f"route('{r}')") for r in order]
    assert idx == sorted(idx), f'the submenu order changed: {order}'


def test_the_overview_never_charts_a_breakdown_the_data_page_cannot_show():
    """⚠⚠ THE SEAM THE BANDS EXIST TO CLOSE. The Overview's Data band charts
    `content.by_agency`; if this page did not also show it, the summary would be
    publishing a breakdown a reader could not follow through to — which is the
    whole reason the Overview computes nothing of its own.

    ⚠ Asserted in BOTH directions, because either half alone is a different
    (and wrong) rule: the endpoint must serve it, and the page must render it.
    """
    router = _read('api/routers/licenses.py')
    assert '"by_agency": by_agency' in router, \
        'the data lens no longer serves an agency breakdown'

    page = _read('app/resources/views/procurement/digital-reform-data.blade.php')
    assert "$content['by_agency']" in page, 'the Data page no longer reads by_agency'
    assert 'id="content-agencies"' in page, 'the agency table is gone from the Data page'

    overview = _expanded('app/resources/views/procurement/digital-reform.blade.php')
    # ⚠⚠ EXACT ANCHORS, CLOSING QUOTE INCLUDED. A bare substring check on
    # "ovDataAgencyChart" is satisfied by "ovDataAgencyChartX", so renaming the
    # canvas passed the first version of this guard — measured by mutation.
    assert 'id="ovDataAgencyChart"' in overview, \
        'the Overview no longer has the agency canvas'
    assert "ovPie('ovDataAgencyChart'" in overview, \
        'the Overview no longer draws the agency chart'


def test_the_agency_breakdown_is_the_content_half_and_is_not_capped():
    """⚠⚠ THE CONTENT HALF ONLY. This lens's two halves OVERLAP by design, so an
    agency breakdown spanning both would be the one sum the page exists to
    refuse — and it would close against nothing.

    ⚠ And UNCAPPED at the endpoint: a truncated list under a heading implying
    the whole is the `by_vendor` defect (25 of 408 under a heading meaning all
    of them). A CONSUMER may fold it, but it must fold a complete list.
    """
    router = _read('api/routers/licenses.py')
    i = router.index('    ag = {}')
    build = router[i:router.index('by_agency = sorted', i)]
    assert 'for r in crows' in build, \
        'by_agency is no longer built from the content rows — it may span both halves'
    assert '[:' not in build.replace('r[:', ''), 'the agency list is capped at the endpoint'


def test_the_data_page_leads_with_the_overviews_data_band():
    """2026-09-23: the Data page leads with the Overview's Data band, as Contracts
    and Products lead with theirs. ONE partial, so the summary and its target
    page cannot show the same three views two ways."""
    for rel in ('app/resources/views/procurement/digital-reform.blade.php',
                'app/resources/views/procurement/digital-reform-data.blade.php'):
        src = _read(rel)
        assert "@include('procurement.partials.data-book')" in src, f'{rel} lost the Data book'
        assert "@include('procurement.partials.data-book-js')" in src, f'{rel} no longer draws it'
    page = _read('app/resources/views/procurement/digital-reform-data.blade.php')
    assert page.index("@include('procurement.partials.data-book')") < page.index('db-stat-grid'), \
        'the band no longer leads the Data page'
    ctrl = _read('app/app/Http/Controllers/ProcurementController.php')
    # One builder for both pages' blocks.
    assert ctrl.count('self::_dataBookBlocks(') == 2, 'the Data book blocks are built two ways'
    i = ctrl.index('public function digitalReformData(')
    body = ctrl[i:ctrl.index('public function', i + 10)]
    assert "'dataBlocks' => self::_dataBookBlocks($d)" in body
    assert "'toolSplit'  => self::_dataToolSplit($d)" in body


def test_the_tools_chart_stacks_within_a_function_and_derives_nothing():
    """⚠⚠ The chart stacks bought-as-a-tool on bought-as-data WITHIN one function:
    each bar is that function's row total, the figure the Products function table
    publishes. Nothing adds across functions or across halves, and the series
    are built in the controller so the script cannot re-derive the split."""
    ctrl = _read('app/app/Http/Controllers/ProcurementController.php')
    i = ctrl.index('private static function _dataToolSplit(')
    fn = ctrl[i:ctrl.index('private static function', i + 10)]
    assert "'tool_value'" in fn and "'content_value'" in fn
    assert 'array_sum' not in fn, 'the tool split sums rows into a total'
    page = _read('app/resources/views/procurement/digital-reform-data.blade.php')
    js = page[page.index("@section('scripts')"):]
    assert "@json($toolSplit ?? null)" in js
    assert js.count("stack: 'row'") == 2, 'the two halves are no longer one stack per function'
    for bad in ('reduce(', '.map(', '+ ts.'):
        assert bad not in js.split('const ts =')[1].split('new Chart(')[0], \
            f'the chart script derives from the series ({bad!r})'


def test_agencies_are_a_linked_bar_list_with_the_full_table_one_click_away():
    """The top 10 as bars; ALL agencies in a sortable table behind a disclosure,
    still uncapped (the verifier closes it to the class total)."""
    page = _read('app/resources/views/procurement/digital-reform-data.blade.php')
    box = page[page.index('id="content-agencies"'):page.index('id="content-products"')]
    assert "array_slice($cAgencies, 0, 10)" in box and 'ds-bar-row' in box
    assert '<details' in box and '@forelse($cAgencies as $a)' in box, \
        'the full agency table is gone or capped'
