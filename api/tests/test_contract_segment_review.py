"""Guards for the contract-grain review gate, once it can be scoped to a segment.

⚠⚠ THE DEFECT THIS EXISTS FOR IS A REVIEW GATE THAT CANNOT SEE ITS OWN SUBJECT.
`build_contract_review_worksheet.py` selects the top N non-licence tech contracts
BY VALUE across the whole universe. Measured 2026-09-15: that draws 0 rows from
8 of the 14 composition segments. Data/analytics — the segment the builder's own
preamble is written about — is one of them, because correcting its top two rows
took it $2,137M -> $209.0M and therefore out of the global top 30. The gate
worked so well on that segment that the segment fell out of the gate, and the
residue inside it (three clinical-service contracts and a $16.0M sibling of a
contract the same gate had already reclassified) became unreachable by it.

⚠ AND THE FIX'S OWN HAZARD IS THE FILE NAME, not the query. `read_existing`
carries forward only the decisions for contracts that are IN the sheet being
written, so a segment run pointed at the global path would silently drop the 30
decisions it does not contain — the worksheet's own "re-running never discards a
decision" rule, broken without touching the code that enforces it.
"""
import ast
import asyncio
import csv
import fnmatch
import importlib.util
import io
import os
import re
import sys
import types

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
BUILDER = os.path.join(ROOT, 'build_contract_review_worksheet.py')
SEED = os.path.join(ROOT, 'seed', 'contract_enrichment_curated.csv')


def _load_builder():
    """The builder, with ONLY its database dependencies stubbed.

    ⚠⚠ `conftest.py` REPLACES THE WHOLE `modules` PACKAGE WITH A MagicMock, so a
    naive import would hand `techsegments.slug` a Mock returning a Mock and every
    assertion below would pass while measuring nothing — the documented trap that
    already made one behavioural guard test a mock. The REAL techsegments is
    injected by path and the load is asserted.
    """
    real = os.path.join(ROOT, 'modules', 'techsegments.py')
    spec = importlib.util.spec_from_file_location('_real_techsegments', real)
    ts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ts)
    # It really is the module, not a mock: a Mock has no such literal.
    assert ts.slug('Data/analytics') == 'data-analytics', 'techsegments did not load'

    saved = {k: sys.modules.get(k) for k in
             ('modules', 'modules.techsegments', 'postgrex',
              'classify_digital_contracts', 'modules.autoload')}
    pkg = types.ModuleType('modules'); pkg.__path__ = []
    pkg.techsegments = ts
    sys.modules['modules'] = pkg
    sys.modules['modules.techsegments'] = ts
    sys.modules['modules.autoload'] = types.ModuleType('modules.autoload')

    pg = types.ModuleType('postgrex')

    class _PG:
        rows = []
        calls = []

        @classmethod
        async def select_safe(cls, sql, params=None):
            cls.calls.append((sql, params))
            return cls.rows
    pg.PostgresModelAsync = _PG
    sys.modules['postgrex'] = pg

    clf = types.ModuleType('classify_digital_contracts')
    clf.CONTRACT_SELECT = 'SELECT 1 {where}'
    clf._dedup = lambda rows: rows

    async def _an(rows):
        return rows
    clf.attach_notices = _an
    sys.modules['classify_digital_contracts'] = clf

    try:
        spec2 = importlib.util.spec_from_file_location('_builder', BUILDER)
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return mod, _PG


def _code(src):
    """Source with docstrings and comments blanked.

    ⚠ Own-prose guard, avoided in advance: this file's subject is explained in
    the builder's own docstring, which NAMES the segments and the helper the
    scans below look for.
    """
    tree = ast.parse(src)
    drop = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d:
                first = node.body[0]
                drop.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    out = []
    for i, line in enumerate(src.split('\n'), 1):
        if i in drop:
            continue
        out.append('' if line.lstrip().startswith('#') else line)
    return '\n'.join(out)


def test_a_segment_run_never_writes_the_global_sheet():
    """The decisions already made are destroyed by a FILE NAME, not by a query."""
    mod, _ = _load_builder()
    assert mod.sheet_path('') == mod.OUT, 'the global run must keep the global path'
    seg = mod.sheet_path('Data/analytics')
    assert seg != mod.OUT, 'a segment run would overwrite the global sheet'
    assert seg.endswith('contract-review-worksheet-data-analytics.csv'), seg
    # Two different segments must not collide with each other either.
    assert mod.sheet_path('ERP/financials') != seg


def test_the_segment_predicate_comes_from_the_one_owner():
    """⚠ Re-deriving "what a segment is" here would make the worksheet measure a
    different partition from the composition bar it gates — and the two would
    drift silently, because both would still produce a plausible sheet.

    ⚠⚠ THE FIRST DRAFT OF THIS GUARD WAS THE OVER-STRICT KIND THIS REPO KEEPS
    PAYING FOR: it banned the string 'Data/analytics' anywhere in the file, and
    so fired on the `--segment` flag's own `help=` text. A name in documentation
    is a MENTION; a name in a comparison or a collection is a second vocabulary.
    Only the second is banned, so the guard measures the property, not the
    spelling.
    """
    src = io.open(BUILDER, encoding='utf-8').read()
    assert 'techsegments.sql_predicate(' in _code(src), 'the builder must ask the one owner'

    tree = ast.parse(src)
    allowed = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if ast.get_docstring(node, clean=False) and node.body:
                allowed.add(id(node.body[0].value))
    for node in ast.walk(tree):          # argparse help/description are prose
        for kw in getattr(node, 'keywords', []) or []:
            if kw.arg in ('help', 'description', 'epilog'):
                allowed.add(id(kw.value))

    # A segment name is the classifier's free text. Anywhere it is USED rather
    # than described, the builder has grown its own copy of the vocabulary.
    names = ('Data/analytics', 'ERP/financials', 'Staffing/consulting',
             'Telecom/network', 'Hardware/infrastructure')
    offenders, scanned = [], 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in allowed:
            scanned += 1
            for name in names:
                if name in node.value:
                    offenders.append((node.lineno, name))
    assert not offenders, f'segment vocabulary hardcoded in the builder: {offenders}'
    # ⚠ Non-vacuity: the scan must actually reach string literals in this file.
    assert scanned > 10, f'only {scanned} literals scanned — the scan did not run'
def test_an_unmatched_segment_writes_nothing_and_exits_non_zero():
    """⚠⚠ A MISSPELLED SEGMENT MUST NOT PRODUCE AN EMPTY SHEET. The names are the
    classifier's free text, so `Data/Analytics` binds fine and matches nothing —
    and a worksheet with no rows reads exactly like "nothing here to review",
    which is this repo's oldest defect wearing a new hat."""
    mod, pg = _load_builder()
    pg.rows = []
    argv = sys.argv
    sys.argv = ['x', '--segment', 'Data/Analytics']
    try:
        rc = asyncio.run(mod.main())
    finally:
        sys.argv = argv
    assert rc not in (0, None), f'an empty result exited {rc!r}'
    assert not os.path.exists(mod.sheet_path('Data/Analytics')), 'it wrote a sheet anyway'


def _seed_rows():
    with io.open(SEED, encoding='utf-8') as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith('#')]
    return list(csv.DictReader(lines))


def test_no_contract_is_decided_twice_in_the_seed():
    """⚠⚠ THE LOADER KEEPS THE LAST ROW AND SAYS NOTHING — the same shape as the
    duplicate dict key that once left a capital builder never running. Two
    decisions about one contract is a conflict to resolve, not a precedence rule
    to rely on."""
    ids = [r['contract_id'].strip() for r in _seed_rows() if r['contract_id'].strip()]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f'decided twice: {dupes}'
    assert len(ids) > 10, f'only {len(ids)} rows scanned — the seed did not parse'


def test_every_seed_row_carries_a_decision_and_its_reason():
    """⚠ A row correcting nothing is a no-op that reads as a review having
    happened, and a correction with no note cannot be re-judged later."""
    for r in _seed_rows():
        cid = r['contract_id'].strip()
        if not cid:
            continue
        decided = (r.get('tech_relevant') or '').strip() or (r.get('function_category') or '').strip()
        assert decided, f'{cid} corrects nothing'
        assert len((r.get('note') or '').strip()) > 40, f'{cid} has no reason recorded'


def test_every_review_worksheet_is_excluded_from_the_public_sync():
    """⚠⚠ DERIVED FROM THE TREE, because a filename list cannot cover a file that
    does not exist yet — and the gate now writes ONE SHEET PER SEGMENT, so the
    set grows on its own. `sync-public.sh` listed
    `docs/contract-review-worksheet.csv` exactly, and its exclusion loop matched
    exact paths only, so the first segment sheet would have been published: an
    unreviewed-judgement document in a category the list already claimed to
    cover. That is the same near-miss this repo records for
    `scripts/rotate-fastapi-key.sh`, one category over.

    The worksheets hold verdicts on NAMED VENDORS, several of them recorded as
    `unsure`. Only `tier='curated'` ever renders; publishing the sheets would
    route around that guarantee through a second channel.
    """
    sync = io.open(os.path.join(ROOT, '..', 'scripts', 'sync-public.sh'),
                   encoding='utf-8').read()
    # Real entries only: the comments in that file quote paths while explaining
    # this very trap, so a raw scan would pass for the wrong reason.
    entries = []
    block = sync.split('EXCLUDE=(', 1)[1].split('\n)', 1)[0]
    for line in block.split('\n'):
        if line.lstrip().startswith('#'):
            continue
        entries += re.findall(r'"([^"]+)"', line)

    docs = os.path.join(ROOT, '..', 'docs')
    sheets = [f'docs/{n}' for n in sorted(os.listdir(docs))
              if 'review-worksheet' in n]
    offenders = [s for s in sheets
                 if not any(fnmatch.fnmatch(s, e) for e in entries)]
    assert not offenders, f'review worksheets that would be published: {offenders}'
    # Non-vacuity, twice: sheets must exist, and the match must be doing work.
    assert len(sheets) >= 2, f'only {len(sheets)} worksheets found — the scan did not run'
    assert any('*' in e for e in entries), \
        'no glob in EXCLUDE — a per-segment sheet cannot be covered by exact paths'


def test_the_sync_exclusion_loop_can_expand_a_glob():
    """⚠ A GLOB IN THE LIST IS INERT IF THE LOOP QUOTES IT. `[ -e "$TREE/$p" ]`
    tests one literal path, so `docs/contract-review-worksheet*.csv` would match
    nothing and silently exclude nothing — the entry would read as protection
    while providing none. The property is that `$p` reaches a glob context."""
    sync = io.open(os.path.join(ROOT, '..', 'scripts', 'sync-public.sh'),
                   encoding='utf-8').read()
    body = '\n'.join(l for l in sync.split('\n') if not l.lstrip().startswith('#'))
    loop = body.split('for p in "${EXCLUDE[@]}"; do', 1)
    assert len(loop) == 2, 'the exclusion loop is gone or was renamed'
    loop = loop[1].split('\ndone', 1)[0]
    assert '"$TREE"/$p' in loop, \
        'the exclusion path is quoted, so a glob entry can never expand'
    assert '[ -e "$TREE/$p" ]' not in loop, 'the old exact-path test is still there'


# ---------------------------------------------------------------------------
# The ceiling split on the Overview's headline tiles.
# ---------------------------------------------------------------------------

OCE = os.path.join(ROOT, 'routers', 'oce.py')
OVERVIEW = os.path.join(ROOT, '..', 'app', 'resources', 'views',
                        'procurement', 'digital-reform.blade.php')


def _stats_fn(src):
    """The body of `_stats`, which is a closure inside the /all handler."""
    i = src.index('async def _stats():')
    j = src.index('async def _award_by_start_year():', i)
    return src[i:j]


def test_the_headline_tiles_split_ceiling_from_committed_money():
    """⚠⚠ A CEILING IS NOT SPEND — #261/#294 at the top of the page.

    Measured 2026-09-15: $3,337.4M across 186 master agreements is HEADROOM,
    31.6% of the headline total, and 47.6% of the Staffing/consulting segment
    (whose largest cluster is DoITT's SI panel — thirteen contracts at exactly
    $50.00M apiece, every one a per-vendor cap).

    ⭐ The page already CONTRADICTED itself: the by-start-year chart below states
    that ceilings are "headroom ... not money committed, so it is not in these
    bars", while this tile summed that same money into "Total value".
    """
    body = _stats_fn(io.open(OCE, encoding='utf-8').read())
    assert 'contractkind.sql_is_master' in body, \
        '_stats no longer splits masters through the one owner'
    # ⚠⚠ ASSERTED AT BOTH ENDS, because the first draft checked only that the
    # WORD appeared somewhere in the function — and renaming the SQL alias left
    # the key in the RETURN dict, so the guard passed while the query stopped
    # producing it. A name in a function body is not a value being computed.
    for key in ('ceiling_total', 'committed_total', 'master_count',
                'committed_ended_total'):
        assert f'as {key}' in body, f'the query no longer emits {key}'
        assert f'"{key}"' in body, f'_stats no longer returns {key}'
    # ⚠ Derived by SUBTRACTION from the same query, never a second predicate.
    assert '"committed_active_total"' in body, '_stats no longer returns the active split'


def test_the_master_test_goes_through_contractkind_never_a_local_substring():
    """⚠⚠ AND IT MUST BE THE ONE OWNER'S EXPRESSION, because the
    `coalesce(..., false)` inside it is load-bearing: `NULL IN ('MA','MMA')` is
    NULL, and in a FILTER split BOTH `FILTER (WHERE NOT x)` and
    `FILTER (WHERE x)` then exclude the row — it falls out of committed AND
    ceiling while COUNT(*) still counts it. That is how $2,500,000 once vanished
    from the by-year series while its contract count closed perfectly."""
    body = _stats_fn(io.open(OCE, encoding='utf-8').read())
    code = '\n'.join(l for l in body.split('\n') if not l.lstrip().startswith('#'))
    assert "substring(" not in code, \
        '_stats re-derives the master test instead of calling contractkind'
    assert "'MA'" not in code and "'MMA'" not in code, \
        '_stats carries its own copy of the master id vocabulary'


def test_the_overview_discloses_the_ceiling_outside_the_stat_grid():
    """⚠ #400's lesson: a <p> inside `.db-stat-grid` becomes a GRID ITEM —
    measured 186x110px against 1376x21 for the same sentence outside it. The
    disclosure must sit after the grid closes, and must render figures from the
    payload rather than typing them."""
    raw = io.open(OVERVIEW, encoding='utf-8').read()
    # ⚠⚠ OWN-PROSE GUARD, HIT WHILE WRITING THIS ONE. The Blade comment above the
    # note EXPLAINS that it sits outside `.db-stat-grid`, so it contains the exact
    # string the scan below looks for and the first draft failed on a CORRECT
    # file. Markup scans read the markup; comments are prose.
    view = re.sub(r'\{\{--.*?--\}\}', '', raw, flags=re.S)
    assert 'id="ceilingNote"' in view, 'the ceiling disclosure is gone'
    grid = view.index('db-stat-grid')
    note = view.index('id="ceilingNote"')
    # ⚠ Anchor on MARKUP, not on a comment: 'THE COMPOSITION' lives only inside a
    # Blade comment, so it vanishes with the strip above and the first fix raised
    # ValueError on a correct file — the same trap one layer down.
    # ⚠⚠ RE-EXPRESSED 2026-09-16, NOT RELAXED. The downstream anchor used to be
    # `id="composition"` — the stacked bar — which the band redesign folded into
    # the Contracts pie. The property this guards is unchanged: the disclosure
    # sits AFTER the stat grid and OUTSIDE it. Only the thing that follows it
    # moved, so the anchor moves with it.
    after = view.index('id="s-contracts"')
    assert grid < note < after, 'the note moved out of its place after the grid'
    # It must be OUTSIDE the grid: the grid cannot still be open at the note.
    # ⚠⚠ ASSERT THE SLICE EXISTS BEFORE ASSERTING WHAT IS NOT IN IT. Found by
    # mutation 2026-09-16: put a note ABOVE the `Vendors` tile and this slice
    # runs backwards, yields '', and both `not in` checks pass on a note sitting
    # inside the grid — the guard reporting clean because it looked at nothing.
    # "Assert something survives before asserting something does not."
    between = view[view.index('Vendors', grid):note]
    assert len(between) > 100, \
        'the outside-the-grid check has nothing to look at — it would pass vacuously'
    assert 'db-stat-grid' not in between and 'db-stat"' not in between, \
        'the note is inside the stat grid'
    # ⚠ Figures come from the payload. A typed one cannot move when the data does.
    for var in ('$stCeil', '$stComm', '$stMast'):
        assert var in view, f'{var} is no longer rendered'


def test_the_ceiling_is_never_added_to_committed_money_on_the_overview():
    """⚠⚠ THE WHOLE POINT, and the #294 defect it prevents. The two figures are
    REPORTED side by side and never summed — a page that adds them counts
    agreements nobody has drawn against as spend."""
    view = io.open(OVERVIEW, encoding='utf-8').read()
    php = re.sub(r'\{\{--.*?--\}\}', '', view, flags=re.S)   # Blade comments are prose
    for bad in ('$stCeil + $stComm', '$stComm + $stCeil',
                "$stats['ceiling_total'] + ", "+ $stats['ceiling_total']"):
        assert bad not in php, f'the Overview adds ceiling to committed money: {bad}'


def test_the_worksheet_says_when_a_contract_is_already_decided():
    """⚠⚠ A SEGMENT SHEET DOES NOT INHERIT THE GLOBAL SHEET'S VERDICTS, so without
    this a settled row reappears blank and a reviewer can re-decide or CONTRADICT
    it. Measured 2026-09-15: the $998.5M and $537.6M camera-enforcement pair were
    settled in August and showed up undecided in the Hardware sheet.

    ⚠ The seed stays the ONE home for a decision — this column only reports that
    one exists, which is why it is `already_curated` and not a second verdict.
    """
    src = io.open(BUILDER, encoding='utf-8').read()
    code = _code(src)
    assert 'already_curated' in FIELDS_OF(src), 'the column is gone from FIELDS'
    # It must be READ FROM THE DATABASE, not inferred from the sheet or guessed.
    assert 'e.curated' in code, 'the builder no longer selects the curated flag'
    assert "m.get(\"curated\")" in code or "m.get('curated')" in code, \
        'the column is emitted without reading the row it describes'


def FIELDS_OF(src):
    """The FIELDS list as the builder declares it."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, 'id', None) == 'FIELDS' for t in node.targets):
            return [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
    return []


def test_the_headline_tile_publishes_committed_money_not_the_blended_total():
    """⚠⚠ OWNER DECISION 2026-09-15. The tile read "Total value, all time" over
    `total`, which sums master-agreement CEILINGS into money the City has agreed
    to pay — while the by-start-year chart below says in its own copy that
    ceilings are "not money committed, so it is not in these bars". One sum, two
    claims, one page.

    ⚠ AND THE SUB-LINE MUST BE COMMITTED-SCOPED TOO. A headline over one
    population with a running/ended split over another is /procurement's "no two
    of the four tiles shared a denominator", on three numbers that touch.
    """
    raw = io.open(OVERVIEW, encoding='utf-8').read()
    view = re.sub(r'\{\{--.*?--\}\}', '', raw, flags=re.S)
    i = view.index('Committed value, all time')
    tile = view[i:i + 700]
    assert "$stats['committed_total']" in tile, 'the headline is not committed money'
    assert "$stats['committed_active_total']" in tile and \
           "$stats['committed_ended_total']" in tile, \
        'the running/ended split is not committed-scoped'
    # ⚠ The blended total must not be what the tile publishes.
    assert "$stats['total']" not in tile, 'the tile still publishes the blended total'
    assert "$stats['active_total']" not in tile, 'the sub-line is over all contracts'
    # ⚠ The CONTRACT COUNT keeps masters — #261: masters stay, only the summing stops.
    assert "$stats['count']" in view, 'the contract count is gone'


# ---------------------------------------------------------------------------
# The call-center lens.
# ---------------------------------------------------------------------------

CC_SEED = os.path.join(ROOT, 'seed', 'phone_service_contracts.csv')
CC_VIEW = os.path.join(ROOT, '..', 'app', 'resources', 'views', 'procurement',
                       'digital-reform-call-centers.blade.php')


def _cc_endpoint(src):
    i = src.index('async def digital_reform_call_centers():')
    j = src.index('\n@router.get(', i)
    return src[i:j]


def test_call_center_membership_is_a_curated_lookup_not_a_pattern():
    """⚠⚠ THE PATTERNS FAILED, THREE TIMES IN ONE SITTING, and each failure read
    exactly like a measurement: `311` matched a geotechnical contract number
    (PW311S20A), `988` matched a shelter's street address ("988 Myrtle Ave"),
    and `crisis` matched crisis SHELTERS and DYCD's Crisis Management System.
    The first total they produced was $369.3M against a measured $247.8M.

    So membership is a reviewed list. A title regex reappearing in this endpoint
    would silently re-import that error.
    """
    body = _cc_endpoint(io.open(OCE, encoding='utf-8').read())
    code = '\n'.join(l for l in body.split('\n') if not l.lstrip().startswith('#'))
    assert '_call_center_seed()' in code, 'the endpoint no longer reads the curated seed'
    for banned in ('ILIKE', '~*', 'contract_title ~', 'hotline', 'call cent'):
        assert banned not in code, f'the endpoint matches on text again: {banned}'


def test_inside_and_outside_are_read_live_and_never_stored_in_the_seed():
    """⚠ The lens must REPORT the classification, not assert it. Storing the
    in/out answer beside the membership lets the two drift, and the drift would
    be invisible — the seed would keep claiming a boundary the classifier had
    moved."""
    seed = io.open(CC_SEED, encoding='utf-8').read()
    rows = [r for r in csv.DictReader(
        [l for l in seed.split('\n') if not l.lstrip().startswith('#')])]
    assert len(rows) > 15, f'only {len(rows)} seed rows parsed'
    cols = {c.strip() for c in (rows[0].keys() if rows else [])}
    for banned in ('tech_relevant', 'inside', 'counted'):
        assert banned not in cols, f'the seed stores the in/out answer ({banned})'
    body = _cc_endpoint(io.open(OCE, encoding='utf-8').read())
    assert 'e.tech_relevant' in body, 'in/out is no longer read from the classification'


def test_the_lens_never_presents_excluded_money_as_technology_spending():
    """⚠⚠ THE HAZARD HERE IS THE OPPOSITE OF THE DATA LENS'S. Those two columns
    OVERLAP and must never be summed; these two halves are DISJOINT, so the lens
    total is real. What must never happen is `outside` being added to the
    section's own figures — it is money the classification deliberately excluded,
    and folding it back in would silently readmit it.
    """
    raw = io.open(CC_VIEW, encoding='utf-8').read()
    view = re.sub(r'\{\{--.*?--\}\}', '', raw, flags=re.S)
    # The page must say, in rendered copy, that the excluded half is not ours.
    assert 'not technology spending' in view, \
        'the page no longer disclaims the excluded half'
    # And it must never add the two halves into a single "technology" figure.
    for bad in ("$ins['value'] + $out['value']", "$out['value'] + $ins['value']"):
        assert bad not in view, f'the page adds the halves: {bad}'


def test_the_lens_page_computes_its_figures_from_the_payload():
    """⚠ No typed figures — the section's standing rule. A figure that cannot
    move when the data does is a claim about a moment, not a measurement."""
    raw = io.open(CC_VIEW, encoding='utf-8').read()
    view = re.sub(r'\{\{--.*?--\}\}', '', raw, flags=re.S)
    for var in ("$all['value']", "$ins['value']", "$out['value']"):
        assert var in view, f'{var} is no longer rendered'
    # ⚠ The measured totals must not be typed into the copy.
    for typed in ('247.78', '91.48', '156.30', '$247.8M'):
        assert typed not in view, f'a measured figure is typed into the page: {typed}'


def test_the_lens_serves_program_and_vendor_rollups():
    """⚠ A programme is the unit a reader asks about, and grouping by it is what
    found the missing NYC Well successor: its title says nothing about a phone
    line, so no pattern could propose it and a list curated FROM a pattern
    inherited that blind spot. $105.55M -> $210.89M for that programme, and
    $247.78M -> $353.12M for the lens."""
    body = _cc_endpoint(io.open(OCE, encoding='utf-8').read())
    for key in ('"programs"', '"vendors"'):
        assert key in body, f'the lens no longer serves {key}'
    assert '_agg(' in body, 'the rollups are no longer computed'
    seed = io.open(CC_SEED, encoding='utf-8').read()
    rows = [r for r in csv.DictReader(
        [l for l in seed.split('\n') if not l.lstrip().startswith('#')])]
    assert all((r.get('program') or '').strip() for r in rows), \
        'a seed row has no programme'


def test_the_vendor_table_is_scoped_to_the_lens_and_says_so():
    """⚠⚠ A VENDOR IS NOT A PROGRAMME. Safe Horizon holds 107 contracts worth
    $441.3M and The Mental Health Association 34 worth $315.1M — almost none of
    them phone lines. A vendor table on this page that read as the vendor's whole
    City book would attribute an entire business to one programme, which is the
    error the `program` column exists to prevent."""
    raw = io.open(CC_VIEW, encoding='utf-8').read()
    view = re.sub(r'\{\{--.*?--\}\}', '', raw, flags=re.S)
    assert 'not each vendor' in view, \
        'the vendor table no longer says it is scoped to this lens'
    assert 'ccVendors' in view and 'ccPrograms' in view, 'a rollup table is gone'


def test_the_straddling_sentence_reads_the_program_shape():
    """⚠ `straddling` is a list of PROGRAM rows. It was vendor rows, and leaving
    this sentence on the old keys 500'd the page with `Undefined index: vendor` —
    the #247 seam, found by rendering and by nothing else."""
    raw = io.open(CC_VIEW, encoding='utf-8').read()
    view = re.sub(r'\{\{--.*?--\}\}', '', raw, flags=re.S)
    i = view.index('$stradSentence =')
    block = view[i:i + 420]
    assert "$s0['program']" in block, 'the sentence no longer reads the programme'
    for stale in ("$s0['vendor']", "$s0['inside']", "$s0['outside']"):
        assert stale not in block, f'the sentence still reads the old shape: {stale}'


def test_the_vendor_table_names_the_program_and_joins_from_a_list():
    """⚠ Measured 2026-09-15: every vendor in this lens serves exactly ONE
    programme (0 of 14 serve more than one) — so a bare string would render
    correctly TODAY and silently show only one of two the first time a vendor
    picked up a second. The payload serves a list and the view joins it.

    ⚠ The mirror is real and is why the programme table gained a Vendors column:
    two programmes DO span several vendors (NYC 311 has 2, the NYC Benefits
    access line 3), so the many-to-one runs one way only.
    """
    body = _cc_endpoint(io.open(OCE, encoding='utf-8').read())
    assert 'a["programs"] = sorted(a["programs"])' in body, \
        'the rollup no longer serves programmes as a sorted list'
    raw = io.open(CC_VIEW, encoding='utf-8').read()
    view = re.sub(r'\{\{--.*?--\}\}', '', raw, flags=re.S)
    i = view.index('ccVendors')
    block = view[i:i + 1800]
    assert "implode(', ', $v['programs']" in block, \
        'the vendor table prints a bare value instead of joining the list'
    assert "$v['program']" not in block, \
        'the vendor table reads a singular key that the payload does not serve'
    j = view.index('ccPrograms')
    assert "$p['vendor_count']" in view[j:j + 1800], \
        'the programme table no longer shows how many vendors serve it'


def test_the_annual_figure_is_a_current_run_rate_not_a_sum_of_rates():
    """⚠⚠ MEASURING THE TERMS IS WHAT SETTLED THIS, and either naive answer is
    wrong on half the data. These programmes are mostly CONSECUTIVE renewals of
    one service — NYC Well runs 2021-2024 then 2024-2027, NYC 311 2022-2024 then
    2024-2026 — so adding their annual rates reports ~$72M/yr for a programme
    costing ~$36M/yr. But the NYC Benefits access line is three vendors running
    CONCURRENTLY (all 2024-01-01 to 2027-06-30), where the sum IS the answer.
    Annualising only the contracts running TODAY is correct in both shapes
    without special-casing either.
    """
    body = _cc_endpoint(io.open(OCE, encoding='utf-8').read())
    assert 'x["active"]' in body, 'the annual figure no longer filters to live contracts'
    assert '"current_annual"' in body, 'the rollup no longer serves a run-rate'
    # ⚠ None, never 0 — "no contract is running" is not "it costs nothing".
    assert 'if live else None' in body, \
        'an empty live set no longer yields None'


def test_the_term_rule_has_one_owner():
    """⚠ `_term_years` was private to routers/licenses.py until the lens needed
    the same rule. Two copies of "how long is this contract" is how two pages
    come to disagree about one contract."""
    lic = io.open(os.path.join(ROOT, 'routers', 'licenses.py'), encoding='utf-8').read()
    assert 'contractterm.years(' in lic, 'licenses.py no longer delegates'
    oce = io.open(OCE, encoding='utf-8').read()
    assert 'contractterm.' in oce, 'the lens no longer uses the shared owner'
    # And the rule itself must not be re-typed in either file.
    for name, src in (('licenses.py', lic), ('oce.py', oce)):
        code = '\n'.join(l for l in src.split('\n') if not l.lstrip().startswith('#'))
        assert '(int(ey) - int(sy))' not in code, \
            f'{name} carries its own copy of the term arithmetic'


def test_a_dash_in_the_annual_column_is_explained_on_the_page():
    """⚠ A dash means NO CONTRACT IS RUNNING, not "unknown" — and it is the
    majority case here (6 of 11 programmes). Left unexplained it reads as missing
    data; rendered as $0.00 it would be a claim the City never made."""
    raw = io.open(CC_VIEW, encoding='utf-8').read()
    view = re.sub(r'\{\{--.*?--\}\}', '', raw, flags=re.S)
    assert 'A dash means no contract is running today' in view, \
        'the dash is no longer explained'
    assert "$p['current_annual'] === null" in view, \
        'the null case is no longer distinguished from a zero'
