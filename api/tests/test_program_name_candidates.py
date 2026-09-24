"""Guards for the program-name candidate extractor + its LLM judging pass.

⚠⚠ THE PROPERTY THAT MATTERS MOST IS THAT NOTHING HERE CAN REACH A PAGE.
`program_name_candidates` is an AUTO tier by construction: a name becomes a
program only when a human copies it into `api/seed/program_curated.csv`, which is
the only source `build_program_groups.py` reads for the `curated` tier. This is
#146's rule — an unreviewed candidate must not be able to render BY OMISSION —
made structural for the fourth time here.

⚠ MOST are AST/source guards, for two reasons this codebase has already paid
for: `conftest.py` replaces the whole `modules` package with a MagicMock (so an
import-based assertion can pass against a mock that satisfies anything), and the
module imports `google.genai`, which is absent under test.

⚠ The RECALL guards at the bottom are behavioural, and the split is deliberate.
A source scan cannot see what a tokeniser produces, and the ACCESS HRA defect
lived in code that read perfectly: the bigram it needed was never formed. Those
tests load the module BY PATH and assert the load succeeded, because a mock
would satisfy every one of them.
"""
import ast
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'build_program_name_candidates.py')
GROUPS = os.path.join(ROOT, 'build_program_groups.py')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _strip_docstrings(src):
    """Source with every module/class/function docstring removed.

    ⚠ Docstrings ONLY — other string literals stay, because that is where SQL
    lives and a guard that dropped them would stop seeing real queries.
    """
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            b = node.body
            if (b and isinstance(b[0], ast.Expr)
                    and isinstance(b[0].value, ast.Constant)
                    and isinstance(b[0].value.value, str)):
                node.body = b[1:]
    return ast.unparse(tree)


def _tree():
    return ast.parse(_read(SRC))


def _fn(name):
    for n in ast.walk(_tree()):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    raise AssertionError(f'{name} is gone')


def _module_code():
    """Every executable line of the module, with ALL docstrings removed."""
    tree = _tree()
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:]
    return ast.unparse(tree)


def _code(node):
    """Source of a function WITHOUT its docstring.

    ⚠ `ast.unparse` INCLUDES the docstring, and every scanner in this repo that
    forgot that fired on the prose explaining the very rule it enforces — ten
    times by the last count. Strip it.
    """
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return '\n'.join(ast.unparse(b) for b in body)


# --------------------------------------------------------------------------
# The safety property: candidates are not renderable.
# --------------------------------------------------------------------------

def test_nothing_serves_program_name_candidates():
    """⚠⚠ THE #146 RULE. If anything serving ever selects from this table, an
    unreviewed model guess can reach a public page — and a page asserting that
    contracts are one program makes a far stronger claim than the co-termination
    block, whose own copy refuses to claim it.

    ⚠ WIDENED 2026-08-29 — it walked `api/routers/` ONLY, so a consumer in
    `main.py`, `mcp_server.py` or a Blade view was invisible to it. That is the
    orgfilter lesson exactly: a guard must cover the direction that catches the
    code nobody has written yet, not only the place the last defect happened to
    live. Verified tree-wide first: today the only references are the builder,
    the eval and this file.
    """
    roots = [ROOT,                                          # the whole api
             os.path.join(ROOT, '..', 'app', 'app'),        # Laravel controllers
             os.path.join(ROOT, '..', 'app', 'resources', 'views')]
    # ⚠⚠ `modules/reviewqueue.py` IS AN INTENDED READER, and this guard caught it
    # on its first commit — correctly, then wrongly. The #146 rule is that an
    # unreviewed candidate must never RENDER to the public; a REVIEW tool reading
    # candidates is the whole point of a review tool, and refusing it would mean
    # no interface could ever be built for the queue.
    #
    # ⚠ Allowing it opens a hole this guard is textual and cannot see: a router
    # could serve candidates through `reviewqueue` without ever naming the table.
    # `test_no_router_serves_the_review_queue_without_authenticating` below is
    # the half that closes it.
    allowed = {os.path.realpath(p) for p in
               (SRC, os.path.join(ROOT, 'eval_program_names.py'), __file__,
                os.path.join(ROOT, 'modules', 'reviewqueue.py'),
                os.path.join(ROOT, 'tests', 'test_review_contract.py'))}
    hits, scanned = [], 0
    for root in roots:
        root = os.path.realpath(root)
        if not os.path.isdir(root):
            continue
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in
                       ('vendor', 'node_modules', '__pycache__', '.git')]
            for f in files:
                if not f.endswith(('.py', '.php')):
                    continue
                p = os.path.realpath(os.path.join(d, f))
                if p in allowed:
                    continue
                scanned += 1
                body = _read(p)
                # ⚠⚠ STRIP DOCSTRINGS BEFORE SCANNING — the twelfth own-prose
                # firing in this repo, and this one was mine: routers/review.py
                # does not query the table (it goes through the queue contract),
                # but its docstring EXPLAINS that these endpoints serve
                # candidates, which is exactly the sentence a future reader
                # needs. Comments and docstrings are prose; SQL lives in other
                # string literals, so those are deliberately still scanned.
                if p.endswith('.py'):
                    try:
                        body = _strip_docstrings(body)
                    except SyntaxError:                 # not our file to parse
                        pass
                # ⚠⚠ AN IDENTIFIER BOUNDARY, NOT A BARE SUBSTRING. The table
                # name is a SUBSTRING of the module name
                # `build_program_name_candidates`, so a plain `in` fires on any
                # file that merely imports or names the builder — which is what
                # happened the moment a new test referenced it. This repo has
                # paid for the same shape before: `#[0-9a-f]{3,8}` matching
                # `#add` inside the ID selector `#addrSearch`.
                if re.search(r'(?<![A-Za-z0-9_])program_name_candidates'
                             r'(?![A-Za-z0-9_])', body):
                    hits.append(os.path.relpath(p, root))
    # ⚠ A guard that walks a tree must assert it LOOKED. A scanner that reaches
    # zero files reports zero problems and is indistinguishable from one that
    # works — this repo has paid for that twice.
    assert scanned > 200, f'the scanner only reached {scanned} files'
    assert not hits, (
        'something outside the builder/eval reads program_name_candidates; those '
        f'rows are UNREVIEWED model output and must never render: {hits}')


def test_the_curated_seed_remains_the_only_promotion_path():
    """A name becomes a program only via the version-controlled seed."""
    g = _read(GROUPS)
    assert 'program_curated.csv' in g, 'the curated seed is no longer read'
    assert 'program_name_candidates' not in g, (
        'build_program_groups reads the candidate table — promotion must stay a '
        'human edit to the seed, not an automatic join')


# --------------------------------------------------------------------------
# The extraction gates. Each exists because a measured noise class defeated the
# ranking; deleting one silently refills the list with that class.
# --------------------------------------------------------------------------

def test_a_token_from_its_own_contracts_vendor_name_is_excluded():
    """⚠ THE CORE IDEA. A vendor name clusters with one vendor, so without this
    `MOTOROLA` outranks `PASSPort`. Asserted on the executable code, not prose.

    ⚠ Anchored on `hard_drop`, which is now the one owner of the tokenise-stage
    rules — `extract` is a two-line delegate. This guard failed when that moved,
    which is a guard doing its job; it was re-pointed, never weakened.
    """
    code = _code(_fn('hard_drop'))
    assert 'k in vend' in code, \
        'the vendor-token exclusion is gone; vendor names will dominate'
    assert 'vend' in _code(_fn('tally')), 'tally no longer passes the vendor set'


def test_agency_vocabulary_is_derived_from_the_register_not_typed():
    """⚠ A typed list goes stale and cannot cover 1,200+ orgs. It must come from
    wegov_orgs, and it must respect retirement."""
    code = _code(_fn('agency_vocab'))
    assert 'wegov_orgs' in code, 'agency vocabulary is no longer derived from the register'
    assert 'retired_at IS NULL' in code, (
        'the agency query does not filter retired orgs — retirement is additive '
        'here, so an unfiltered read silently includes merged-away duplicates')


def test_the_agency_concentration_gate_survives():
    """⭐ THE DISCRIMINATOR. Measured: generics span 14-24 agencies while
    PASSPort and MyCity span 2. Without MAX_AGENCIES the list refills with
    INTEGRATION / Security / Training."""
    src = _read(SRC)
    assert 'MAX_AGENCIES' in src
    code = _code(_fn('gates'))
    assert 'na > MAX_AGENCIES' in code, 'the agency-concentration gate is not applied'




# --------------------------------------------------------------------------
# The model pass.
# --------------------------------------------------------------------------

def test_the_judged_run_cannot_exit_zero_when_every_batch_failed():
    """⚠⚠ THE DEFECT THIS REPO ALREADY SHIPPED. `classify_license_purchases.py`
    printed 'Done. 0 classified' and exited 0 when the Gemini account ran out of
    credit — and a monthly cron with a dead-man's switch would have pinged
    SUCCESS having classified nothing."""
    code = _code(_fn('main'))
    assert 'failed += 1' in code, 'batch failures are no longer counted'
    assert 'return 1 if failed else 0' in code, (
        'a run with failed batches exits 0 — indistinguishable from a clean run')


def test_no_search_tool_is_attached_to_a_lite_model():
    """⚠⚠ MEASURED TRAP: `gemini-3.1-flash-lite` returns NO grounding metadata
    when handed a search tool — it silently answers from RECALL, and an
    ungrounded right answer is indistinguishable from an ungrounded wrong one.
    This task judges supplied text, so nothing should be grounded.

    ⚠ READS CODE, NOT PROSE. The first draft asserted the tool name was absent
    from the whole FILE and fired on this module's own docstring, which explains
    why no such tool is attached. That is the ELEVENTH own-prose guard failure in
    this repo; the rule is settled — strip docstrings, or read AST literals.
    """
    code = _module_code()
    assert 'google_search' not in code, (
        'a search tool appears in the CODE of a file using a lite model; either '
        'drop it or move to a grounding model and assert sources came back')
    # and the guard must be capable of failing — prove it sees real code
    assert 'generate_content' in code, 'the scanner is not reading the API call'


def test_the_extractor_does_not_pre_filter_labor_codes_with_a_regex():
    """⚠⚠ A REGEX ATTEMPTING A SEMANTIC JUDGEMENT KILLED A REAL NAME.

    An early draft excluded staffing grades with `^[A-Z]{1,4}[0-9]{1,2}$`, which
    also matches **NYC3** — a genuine City system this very extractor had
    surfaced. The pattern failed in the direction that HIDES good answers, and it
    was caught only because a guard asserted known-good names survive.

    The judgement belongs to the model, which has a `labor_code` kind. So the
    codes are classified and stay visible in the report, rather than vanishing.
    """
    code = _module_code()
    assert 'GRADE' not in code, (
        'a grade-code regex is back; it drops NYC3 and any other name shaped '
        'letters+digit — let the model classify labor_code instead')
    src = _read(SRC)
    assert 'labor_code' in src, 'the model has no labor_code kind to route them to'


def test_the_run_reports_its_own_spend():
    """⚠ A '~$6' guess sat in these docs for six weeks and was wrong by ~2.4x.
    Thinking tokens are billed as output and dominate, so the job must measure."""
    code = _code(_fn('_report_spend'))
    assert 'thoughts_token_count' in _read(SRC), 'thinking tokens are not counted'
    assert 'do not assume cheap' in _read(SRC), (
        'the no-usage-metadata path no longer warns; silence would read as free')
    assert 'PRICES' in code


def test_the_model_is_told_to_judge_only_from_supplied_evidence():
    """⚠ Otherwise the model asserts a program exists from outside knowledge, and
    a confident hallucination is exactly what a curated tier cannot filter,
    because a human reviewing 40 plausible names trusts the rationale."""
    src = _read(SRC)
    assert 'JUDGE ONLY FROM THE EVIDENCE SUPPLIED' in src
    assert 'unclear' in src, 'there is no abstention option'


def test_is_program_is_restricted_to_program_and_system():
    """A vehicle, commodity or labor code must not be promotable."""
    src = _read(SRC)
    assert 'Set is_program_name = true ONLY for `program` and `system`' in src, \
        'the instruction no longer restricts which kinds count as a program'


def test_a_labor_code_cannot_be_promoted_even_if_the_model_says_it_is_a_program():
    """⚠⚠ MEASURED ON THE FIRST FULL RUN: the model returned `PM3` and `SP2` with
    kind=`labor_code` AND is_program_name=true, at HIGH confidence — contradicting
    the instruction that the flag is true only for `program`/`system`.

    This repo already documents the shape: a classifier's rationale can refute
    the flag beside it, so read both. An instruction is a request; a gate is a
    guarantee. Enforced in code, and applied to the stored column as well as the
    printed report so the table cannot disagree with what a human reviewed.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location('_pnc', SRC)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:                                   # google.genai absent
        import re as _re
        code = _read(SRC)
        assert 'def _is_program' in code and 'PROGRAM_KINDS' in code
        assert _re.search(r'return bool\(j\.get\("is_program_name"\)\)\s*and\s*'
                          r'j\.get\("kind"\) in PROGRAM_KINDS', code), \
            'the consistency gate no longer requires BOTH the flag and the kind'
        return
    assert mod._is_program({"is_program_name": True, "kind": "labor_code"}) is False
    assert mod._is_program({"is_program_name": True, "kind": "vehicle"}) is False
    assert mod._is_program({"is_program_name": True, "kind": "system"}) is True
    assert mod._is_program({"is_program_name": False, "kind": "system"}) is False


def test_the_stored_column_uses_the_same_gate_as_the_report():
    """⚠ If the table stored the raw flag while the report applied the gate, a
    reviewer would see one set and a consumer another — the two-owners defect."""
    code = _read(SRC)
    assert 'c["examples"], j.get("kind"), _is_program(j),' in code, \
        'the INSERT stores the raw model flag instead of the gated value'


# --------------------------------------------------------------------------
# Recall: the tokeniser must be able to FORM a multi-word name.
#
# ⚠⚠ These are BEHAVIOURAL, unlike the rest of this file, and the difference is
# deliberate. The properties below are about what the tokeniser produces from
# real-shaped input, and a source scan cannot see that — the ACCESS HRA defect
# was invisible in code that read perfectly. `tally`/`gates`/`hard_drop` are
# pure functions with no external dependency, so they can be exercised directly;
# the module is loaded BY PATH and the load is ASSERTED, because `conftest.py`
# replaces the whole `modules` package with a MagicMock that would otherwise
# satisfy almost any assertion.
# --------------------------------------------------------------------------

def _mod():
    """The real module, or skip. Never a mock — a mock passes everything."""
    import importlib.util
    import pytest
    spec = importlib.util.spec_from_file_location('_pnc_behav', SRC)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:                            # pragma: no cover
        pytest.skip(f'cannot load the real module: {exc}')
    assert callable(getattr(mod, 'tally', None)), 'loaded something that is not the module'
    assert callable(getattr(mod, 'gates', None))
    return mod


def _rows(*specs):
    """specs: (contract_id, title, vendor, agency, value), padded with filler.

    ⚠⚠ THE PADDING IS LOAD-BEARING AND THE FIRST DRAFT WITHOUT IT WAS VACUOUS.
    `DF_CEILING` is a share of the corpus, not a count: on a 4-row fixture the
    ceiling is 0.2 contracts, so EVERY token exceeds it and `gates` returns an
    empty list. The 'ACCESS HRA survives' assertion failed for that reason
    rather than a real one — and, worse, the two 'X must be absent' assertions
    were passing against that same empty set, proving nothing at all.

    So every fixture is padded to a corpus where the real gates can bite, and
    each test asserts something SURVIVES before asserting something does not.
    """
    rows = [{'contract_id': c, 't': t, 'v': v, 'a': a, 'val': val}
            for c, t, v, a, val in specs]
    rows += [{'contract_id': f'FILL{i}', 't': f'Padding {i} widget procurement',
              'v': f'FILLER VENDOR {i}', 'a': 'FILL', 'val': 1.0}
             for i in range(120)]
    return rows


ACCESS_HRA_ROWS = _rows(
    ('C1', 'Renewal of ACCESS HRA services', 'RCI TECHNOLOGIES INC', 'DSS', 1.0),
    ('C2', 'QED_ACCESS HRA Releases', 'QED INC', 'DSS', 1.0),
    ('C3', 'IT Consulting ACCESS HRA Releases', 'PRUTECH SOLUTIONS', 'DSS', 1.0),
    ('C4', 'IT Services for Access HRA Releases', 'ManpowerGroup', 'HRA', 1.0),
)


def test_a_multi_word_name_whose_half_is_agency_vocabulary_survives():
    """⭐⭐ THE ACCESS HRA CASE — a real City platform, 5 contracts / 5 vendors /
    2 agencies, comfortably past every gate, and invisible for a whole session.

    `HRA` alone is the Human Resources Administration and must stay excluded.
    `ACCESS HRA` is the benefits platform. A bigram pass that applied the
    unigram agency test to both halves would keep hiding it — measured, that
    policy yields 67 bigrams and STILL misses this name.
    """
    mod = _mod()
    agencies = {'HRA', 'DSS'}
    keep, rejected = mod.gates(mod.tally(ACCESS_HRA_ROWS, agencies),
                               len(ACCESS_HRA_ROWS))
    keys = {c['name_key'] for c in keep}
    assert 'ACCESSHRA' in keys, (
        'ACCESS HRA is not a candidate — the bigram pass is gone, or it is '
        'testing bigram halves for agency vocabulary again')
    assert 'HRA' not in keys and 'HRA' not in rejected, (
        'the bare agency acronym became a candidate; agency_token must still '
        'exclude a UNIGRAM even though a bigram half may be one')


def test_a_bigram_containing_a_stop_word_is_still_noise():
    """⚠ The loosest policy (drop only if BOTH halves drop) leaks 'Voice and'
    and 'III Renewal'. hard_drop applies to EVERY half, which is what keeps the
    bigram pass from becoming a phrase dump: measured +127 candidates, not +282.
    """
    mod = _mod()
    rows = _rows(
        ('C1', 'Citywide Voice and Data', 'ALPHA CORP', 'DoITT', 1.0),
        ('C2', 'Citywide Voice and Data', 'BETA LLC', 'DoITT', 1.0),
        ('C3', 'Citywide Voice and Data', 'GAMMA INC', 'DoITT', 1.0),
    )
    keep, _ = mod.gates(mod.tally(rows, set()), len(rows))
    keys = {c['name_key'] for c in keep}
    # ⚠ LIVENESS FIRST. Every assertion below is an absence, and an absence is
    # satisfied by an empty result — which is exactly how the first draft of
    # this file passed while `gates` was returning nothing.
    # (`Citywide` and `Data` are themselves stop words, so `VOICE` is the one
    # token here that should survive — which is the anchor proving the fixture
    # produces candidates at all.)
    assert 'VOICE' in keys, \
        'nothing survived; this fixture cannot falsify anything'
    assert 'VOICEAND' not in keys and 'ANDDATA' not in keys, \
        'a stop word is being admitted as half of a bigram'
    assert 'VOICEDATA' not in keys, 'bigrams must be ADJACENT tokens, not a cross product'


def test_a_gate_that_removes_a_name_says_which_gate_and_by_how_much():
    """⚠⚠ THE POINT OF THIS SESSION. A filter that hides a good answer is
    invisible; one that admits a bad answer is loud. `SYEP` is a real City
    program with 3 contracts and 2 distinct vendors, removed by MIN_VENDORS=3 —
    and reported for a whole session as a bare 'MISSED', indistinguishable from
    a name the tokeniser could not form. Those need OPPOSITE fixes.

    So a rejection must name its gate and carry the value that failed it.
    """
    mod = _mod()
    rows = _rows(
        ('C1', 'SYEP Work Readiness Curriculum', 'HATS AND LADDERS', 'DYCD', 1.0),
        ('C2', 'SYEP Work Readiness Curriculum Amendment', 'HATS AND LADDERS', 'DYCD', 1.0),
        ('C3', 'SYEP Online Platform', 'YOUTHFUL LLC', 'DYCD', 1.0),
    )
    keep, rejected = mod.gates(mod.tally(rows, {'DYCD'}), len(rows))
    assert 'SYEP' not in {c['name_key'] for c in keep}, \
        'SYEP now passes — MIN_VENDORS changed; re-measure before accepting this'
    assert 'SYEP' in rejected, 'the rejection was not recorded at all'
    why = rejected['SYEP']['why']
    # ⚠ Pinned to MIN_VENDORS ALONE. On an unpadded fixture SYEP is also caught
    # by DF_CEILING, so `'MIN_VENDORS' in why` would pass for the wrong reason —
    # a test that is accidentally right stops being a test the moment the gate
    # it names is the one that changes.
    assert why.startswith('MIN_VENDORS') and 'DF_CEILING' not in why, \
        f'SYEP is being removed by a gate other than MIN_VENDORS: {why!r}'
    assert '(has 2)' in why, f'the reason does not carry the failing value: {why!r}'
    assert rejected['SYEP']['n_contracts'] == 3


def test_the_recall_eval_reports_why_each_miss_was_removed():
    """⚠ The eval is the only thing measuring recall, and 'MISSED' with no cause
    sends the next reader to re-derive it. It must distinguish a gate threshold
    (a precision judgement) from a name the tokeniser cannot form (a bug).
    """
    ev = os.path.join(ROOT, 'eval_program_names.py')
    code = _read(ev)
    assert 'diagnose(' in code, 'the eval no longer asks what was thrown away'
    assert 'never tokenised' in code and 'gate:' in code, \
        'the eval no longer distinguishes a gated miss from an unformable one'


def test_every_known_program_name_carries_a_source():
    """⚠ A name nobody can verify is not ground truth, it is a guess with a
    citation slot. Recall is computed from this file, so an unsourced row
    silently moves a published number."""
    import csv
    import io as _io
    seed = os.path.join(ROOT, 'seed', 'program_names_known.csv')
    with _io.open(seed, encoding='utf-8') as fh:
        rows = [r for r in csv.reader(fh)
                if r and r[0].strip() and not r[0].lstrip().startswith('#')
                and r[0].strip().lower() != 'name']
    assert len(rows) >= 13, f'the seed shrank to {len(rows)} names'
    for r in rows:
        assert len(r) >= 3 and r[2].strip().startswith('http'), \
            f'{r[0]!r} has no source URL'
        assert r[1].strip() in ('yes', 'absent', 'unknown'), \
            f'{r[0]!r} has an unrecognised expect value {r[1]!r}'


def test_every_gate_is_named_so_a_silent_one_can_still_be_reported():
    """⚠⚠ A GATE THAT REMOVED NOTHING AND A GATE THAT DOES NOT EXIST look
    identical in a list of what was removed — this repo's oldest defect, and
    DF_CEILING is a live instance: it currently removes 0 names, because after
    STOP the commonest surviving token is in 94 contracts against a ceiling of
    219. Inert is a fine answer; indistinguishable-from-missing is not.

    So the gate names are declared, and every declared name must actually be
    applied in `gates`. Adding a gate without listing it, or listing one that is
    never applied, both fail here.
    """
    src = _read(SRC)
    assert 'GATE_NAMES' in src, 'the gate names are no longer enumerable'
    mod = _mod()
    body = _code(_fn('gates'))
    assert len(mod.GATE_NAMES) >= 4, f'only {len(mod.GATE_NAMES)} gates declared'
    for g in mod.GATE_NAMES:
        assert g in body, f'{g} is declared in GATE_NAMES but never applied in gates()'
    # and nothing applied may be missing from the declaration
    import re as _re
    applied = set(_re.findall(r'\b(MIN_[A-Z]+|MAX_[A-Z]+|DF_[A-Z]+)\b', body))
    assert applied <= set(mod.GATE_NAMES), \
        f'gates() applies a threshold that GATE_NAMES does not list: {applied - set(mod.GATE_NAMES)}'
    assert _read(os.path.join(ROOT, 'eval_program_names.py')).count('bpn.GATE_NAMES') == 1, \
        'the eval no longer seeds its report from the declared gates, so a gate '\
        'that fires zero times will silently vanish from it again'


def test_the_eval_reports_what_the_tokeniser_could_actually_reach():
    """⚠⚠ THREE COUNTS, ALL CORRECT, FOR DIFFERENT QUESTIONS — and only one of
    them bounds recall. NG911 is 72 titles by substring, 69 by word boundary,
    and **66 reachable** as a token the extractor can form; the gap is fusion
    (`NG911FDNY`, `NG911-CAD`) that no gate change can close.

    `reachable` must be derived from the tokeniser's own output, not from a
    second regex — a regex would drift from the thing it claims to measure, and
    the word-boundary form already disagrees by 3.
    """
    ev = _read(os.path.join(ROOT, 'eval_program_names.py'))
    assert 'reachable' in ev, 'the reachable column is gone'
    assert 'reach = {c["name_key"]: c["n_contracts"] for c in cands}' in ev, (
        'reachable is no longer taken from the tokeniser output; if it is now '
        'computed by a regex it can disagree with the extractor it measures')
    assert 'ILIKE $1' in ev, (
        'corpus_hits stopped using a substring match — a word boundary here '
        'DROPS 3 real NG911 contracts written NG911CALLHANDLING-')


def test_one_name_spelled_two_ways_becomes_one_candidate():
    """⭐ AN UNANTICIPATED SECOND WIN FROM THE BIGRAM PASS, worth pinning because
    nothing about "support multi-word names" implies it.

    `norm()` strips non-alphanumerics, so the bigram `EMS CAD` and the unigram
    `EMSCAD` produce the SAME key and merge. Before the bigram pass they were
    two different names and only the one-word spelling was counted: measured on
    prod, EMSCAD went from **$22.99M / 3 contracts to $34.7M / 5** — the money
    was understated because a spelling variant was invisible.

    46 surviving candidates merge this way and every one inspected is a single
    name spelled two ways (ELASTIC SEARCH/Elasticsearch, CYBER COMMAND, SEND
    GRID, TOUGH BOOKS, NG911 NYPD/NG911-NYPD). None is a false merge of two
    unrelated phrases, which was the risk worth checking: `FOO BARBAZ` and
    `FOOBAR BAZ` would also share a key.
    """
    mod = _mod()
    rows = _rows(
        ('C1', 'EMS CAD system upgrade', 'ALPHA CORP', 'FDNY', 1.0),
        ('C2', 'EMSCAD maintenance', 'BETA LLC', 'FDNY', 1.0),
        ('C3', 'EMS CAD integration services', 'GAMMA INC', 'FDNY', 1.0),
    )
    keep, _ = mod.gates(mod.tally(rows, {'FDNY'}), len(rows))
    by_key = {c['name_key']: c for c in keep}
    assert 'EMSCAD' in by_key, 'the two spellings no longer share a key'
    assert by_key['EMSCAD']['n_contracts'] == 3, (
        'the spellings are being counted as separate names again — this is how '
        f"EMSCAD understated its own money: {by_key['EMSCAD']}")


def test_no_router_serves_the_review_queue_without_authenticating():
    """⚠⚠ THE HALF THAT CLOSES THE HOLE ABOVE.

    `modules/reviewqueue.py` is allowed to read candidate tables, so the textual
    scan can no longer see a router that serves candidates THROUGH it — such a
    router need never name `program_name_candidates` at all.

    So: a router may import the review queue, but only if it also authenticates.
    The precedent is `routers/org_admin.py`, which calls `require_editor` on every
    mutating path and is reachable only behind nginx basic auth on `/admin/`.
    Unreviewed model output naming City programs and assigning them money must
    not be one unauthenticated GET away.

    Today NO router imports it — the contract is still a proposal — so this
    asserts the safe state and becomes load-bearing the moment Phase 1 ships.
    """
    routers = os.path.join(ROOT, 'routers')
    offenders, scanned = [], 0
    for d, _, files in os.walk(routers):
        for f in files:
            if not f.endswith('.py'):
                continue
            scanned += 1
            body = _read(os.path.join(d, f))
            if 'reviewqueue' not in body:
                continue
            if 'require_editor' not in body:
                offenders.append(f)
    assert scanned > 3, f'the scanner only reached {scanned} router files'
    assert not offenders, (
        'a router imports the review queue without authenticating, so unreviewed '
        f'candidates would be servable to the public: {offenders}')


def test_the_prompt_is_built_from_KINDS_and_is_byte_identical():
    """⚠⚠ A PROMPT CHANGE IS A BEHAVIOUR CHANGE. The kind block in INSTRUCTION
    is now generated from `KINDS` so the enum and the prose cannot drift — but
    generating it must not have altered a single character of what the model is
    given, or every candidate already judged was judged against a different
    prompt than the one in the file.

    Asserted against the hand-written block verbatim.
    """
    mod = _load_bpn()
    expected = (
        "  program    a named City initiative or service people would recognise\n"
        "  system     a named IT system or platform\n"
        "  vehicle    a procurement construct, not a thing being run\n"
        "             (e.g. a \"Class 3\" citywide integration vehicle, a GSA schedule)\n"
        "  commodity  a category of goods/services (laptops, cabling, fuel, parking)\n"
        "  labor_code a staffing grade or job title (SP3, PM3, Program Manager)\n"
        "  agency     an agency, bureau or office name/abbreviation\n"
        "  vendor     a supplier's name or brand\n"
        "  generic    an ordinary procurement or English word\n"
        "  unclear    genuinely cannot tell from the evidence supplied")
    assert expected in mod.INSTRUCTION, (
        'the generated kind block no longer matches the prompt the corpus was '
        'judged with — regenerate the candidates or restore the wording')
    assert '__KIND_BLOCK__' not in mod.INSTRUCTION, 'the placeholder leaked'
    assert mod.SCHEMA['properties']['results']['items']['properties']['kind']['enum'] \
        == list(mod.KINDS), 'the JSON enum drifted from KINDS'
    assert mod.PROGRAM_KINDS == ('program', 'system'), (
        'the kinds that count as a program name changed; is_program and the '
        'gate downstream both depend on exactly these two')


def _load_bpn():
    import importlib.util
    spec = importlib.util.spec_from_file_location('_bpn_kinds', SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
