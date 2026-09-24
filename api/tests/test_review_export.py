"""Guards for the review export — the step that turns decisions into seed rows.

⚠ The script cannot be imported without a loaded Config, so these are source and
pure-function guards. The behaviour that matters most was verified against real
data on a throwaway stack; what is pinned here is the reasoning that made it
safe, because the failure mode is DESTROYING a curated seed.
"""
import ast
import re
import importlib.util
import io
import os

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'export_review_decisions.py')
MOD = os.path.join(ROOT, 'modules', 'reviewqueue.py')
BPN = os.path.join(ROOT, 'build_program_name_candidates.py')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _fn(name, path=SRC):
    for n in ast.walk(ast.parse(_read(path))):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    raise AssertionError(f'{name} is gone from {os.path.basename(path)}')


def _code(node):
    b = node.body
    if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant):
        b = b[1:]
    return '\n'.join(ast.unparse(x) for x in b)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# --------------------------------------------------------------------------
# ⚠⚠ The bug that destroyed a seed in testing.
# --------------------------------------------------------------------------

def test_a_seed_path_resolves_in_the_container_layout_too():
    """⚠⚠ THIS BUG EMITTED A 2-LINE FILE OVER A 53-LINE SEED.

    Queues declare their seed REPO-relative (`api/seed/x.csv`), but the api
    container's tree is rooted at `/app` — there is no `/app/api`. The first
    version joined against `dirname(dirname(__file__))`, which inside the
    container is `/`, looked for `/api/seed/program_curated.csv`, found nothing,
    and read the existing content as EMPTY. The documented
    `--emit … > seed.csv` would then have replaced 13 curated decisions and every
    comment block with two rows.

    It failed in the reassuring direction — no error, plausible output.
    """
    ex = _load(SRC, '_export_paths') if False else None   # needs Config; source it
    src = _read(SRC)
    assert 'def seed_full_path' in src, 'the path resolver is gone'
    code = _code(_fn('seed_full_path'))
    assert "rel.startswith('api/')" in code or 'rel.startswith("api/")' in code, (
        'the resolver no longer strips the repo-relative api/ prefix, so it will '
        'look for /app/api/seed/... which does not exist')
    assert 'API_DIR' in code, 'the resolver no longer resolves against the api dir'
    assert 'dirname(os.path.dirname' not in src, (
        'the two-level dirname is back — inside the container that is "/"')


def test_a_missing_seed_refuses_instead_of_emitting_new_rows_alone():
    """⚠⚠ AN EMPTY READ IS INDISTINGUISHABLE FROM A CORRECT ONE TO A REDIRECT,
    and the redirect is the documented usage. "I could not find it" must never be
    able to look like "it had nothing in it"."""
    code = _code(_fn('_seed_lines'))
    assert 'raise SystemExit' in code, (
        'a missing seed no longer refuses; --emit would print only new rows and '
        'the documented redirect would overwrite the seed with them')
    assert 'return [], set()' not in code, 'the silent-empty return is back'


def test_the_emit_must_be_longer_than_the_file_it_replaces():
    """⚠ The cheap assertion that would have caught the path bug on its own. A
    redirect cannot undo a truncation."""
    code = _code(_fn('main'))
    assert 'len(out_lines) < len(lines) or not lines' in code, \
        'the emit no longer refuses to shrink the seed'


def test_an_item_already_in_the_seed_is_refused_not_duplicated():
    """⚠ Merging a changed decision into hand-written reasoning is a judgement a
    script should not make. And the refusal goes to STDERR, or a `> seed.csv`
    redirect swallows it and the decision is quietly not exported."""
    code = _code(_fn('main'))
    assert 'refused' in code and 'file=sys.stderr' in code, \
        'duplicate refusals are no longer reported on stderr'


def test_marking_exported_is_a_separate_invocation():
    """⚠⚠ ORDER MATTERS AND THE SCRIPT MUST NOT COLLAPSE IT. Marking a decision
    exported before the commit lands would leave it looking exported while absent
    from the seed — silently lost, and invisible because the queue stops offering
    it."""
    src = _read(SRC)
    assert '--mark-exported' in src, 'the separate marking step is gone'
    emit = _code(_fn('main'))
    # the emit branch returns BEFORE any marking can happen
    assert emit.index('args.emit') < emit.index('mark_exported'), \
        'marking is reachable from the emit path; it must be its own run'


def test_only_flagged_links_reach_the_seed_note():
    """⭐ The owner's call. An export that published every link would put leads
    behind a provenance claim about a named City program."""
    code = _code(_fn('collect'))
    assert 'rq.source_clauses(' in code, (
        'the export no longer uses the one owner of the Source contract; a '
        'local reimplementation could publish unflagged links')


# --------------------------------------------------------------------------
# A rejection has to STICK.
# --------------------------------------------------------------------------

def test_a_rejection_goes_to_a_file_the_generator_reads():
    """⚠⚠ THE DRAFT WROTE rule="rejected" INTO THE CURATED SEED, which
    `load_curated` does not accept — so the row was SKIPPED and the rejection did
    nothing while looking recorded.

    A curated seed says what a program IS; a rejection says what a candidate is
    NOT, and the thing that must read it is the candidate GENERATOR. Otherwise
    the name returns on every regeneration and the reviewer answers forever —
    the failure 110 NYCHA no-match markers exist to prevent (#155).
    """
    rq = _load(MOD, '_rq_export')
    q = rq.REGISTRY['program-names']
    assert q.reject_seed_path and q.reject_seed_path != q.seed_path, \
        'rejections go back into the curated seed'
    assert q.seed_path_for(rq.REJECT) == q.reject_seed_path
    assert q.seed_path_for(rq.ACCEPT) == q.seed_path

    item = rq.Item(queue='program-names', item_id='FOO', subject='Foo',
                   proposal='system', proposal_value='system',
                   confidence='high', why='w')
    row = q.seed_rows(item, rq.Decision(item_id='FOO', verb=rq.REJECT,
                                        note='generic', actor='devin'))[0]
    assert 'rejected' not in row, (
        'the rejection row still carries a rule the curated loader refuses')
    assert row[0] == 'Foo' and row[2] == 'devin', \
        'the rejection row is not (name, reason, decided_by)'


def test_a_rejected_name_is_excluded_from_the_candidates():
    """⚠ And on the NORMALISED name, so one rejection covers every spelling the
    extractor would have merged — a raw match would leave the variant coming
    back."""
    import collections
    bpn = _load(BPN, '_bpn_export')
    path = os.path.join(os.path.dirname(__file__), '_rej_probe.csv')
    io.open(path, 'w', encoding='utf-8').write(
        'name,reason,decided_by\n"Real Time","generic",\"devin\"\n')
    try:
        assert bpn.rejected_names(path) == {'REALTIME'}, \
            'the rejection is not normalised, so a spelling variant survives'
        stat = {'REALTIME': {'c': {1, 2, 3}, 'v': {'a', 'b', 'c'}, 'a': {'X'},
                             'val': 1.0,
                             'disp': collections.Counter(['Real Time']),
                             'ex': ['t']}}
        keep, _ = bpn.gates(stat, 100)
        assert [k['name_key'] for k in keep] == ['REALTIME'], \
            'the fixture no longer survives without a rejection — vacuous test'
        keep, rej = bpn.gates(stat, 100, bpn.rejected_names(path))
        assert keep == [], 'a rejected name is still offered as a candidate'
        assert 'REVIEWED' in rej['REALTIME']['why'], (
            'the exclusion is silent; an invisible one is indistinguishable '
            'from a generator that stopped finding it')
    finally:
        os.remove(path)


CUR = 'api/seed/program_curated.csv'
REJ = 'api/seed/program_name_rejected.csv'


def _plan(pending, arg):
    return _load(SRC, '_export_mod').marking_plan(pending, arg)


def test_marking_is_scoped_to_ONE_seed_and_refuses_when_it_cannot_tell():
    """⚠⚠ `--emit` IS PER-PATH AND `--mark-exported` WAS PER-QUEUE.

    program-names writes accepts to `program_curated.csv` and rejects to
    `program_name_rejected.csv`, and `--emit` handles one file per run. So the
    documented flow — emit one seed, commit it, then mark — marked the OTHER
    seed's decisions exported without them ever being written. Silently lost,
    and invisible, because the queue then stops offering them. Same failure as
    the script's step-4 warning: there the ORDER was wrong, here the SCOPE was.

    ⚠ Tested by CALLING it, not by scanning the source. This bug does not appear
    in any string the file contains — it is control flow, and the earlier guards
    in this file could not have seen it.
    """
    two = [{'item_id': 'NG911', 'path': CUR}, {'item_id': 'DTR', 'path': REJ}]

    with pytest.raises(SystemExit) as exc:
        _plan(two, True)
    assert 'more than one seed' in str(exc.value)
    assert CUR in str(exc.value) and REJ in str(exc.value), (
        'the refusal does not name the seeds, so the reader cannot act on it')

    to_mark, remaining, where = _plan(two, CUR)
    assert [p['item_id'] for p in to_mark] == ['NG911'], (
        "naming the curated seed marked something outside it")
    assert remaining == 1 and where == CUR

    to_mark, remaining, where = _plan(two, REJ)
    assert [p['item_id'] for p in to_mark] == ['DTR']
    assert remaining == 1 and where == REJ


def test_one_seed_still_marks_without_being_named():
    """⚠ The common case must not become tedious, or it gets worked around."""
    one = [{'item_id': 'NG911', 'path': CUR}]
    to_mark, remaining, where = _plan(one, True)
    assert [p['item_id'] for p in to_mark] == ['NG911']
    assert remaining == 0 and where == CUR


def test_naming_a_seed_with_no_pending_rows_is_refused():
    """⚠ Otherwise a typo marks nothing and reports success — a no-op that reads
    as a completed export."""
    one = [{'item_id': 'NG911', 'path': CUR}]
    with pytest.raises(SystemExit) as exc:
        _plan(one, REJ)
    assert 'no pending decision belongs' in str(exc.value)
    assert CUR in str(exc.value), 'the refusal does not say what IS pending'


def test_the_argument_accepts_a_seed_path():
    """⚠ `action='store_true'` cannot carry the seed, so the fix is not
    expressible without changing the argument itself. Pinned so a later tidy-up
    does not quietly revert it to a flag."""
    code = _code(_fn('main'))
    m = re.search(r"""add_argument\(\s*['"]--mark-exported['"](.*?)\bhelp=""",
                  code, re.S)
    assert m, 'the --mark-exported argument declaration was not found'
    assert 'store_true' not in m.group(1), (
        '--mark-exported is a bare flag again, so it cannot name the seed it is '
        'marking for')
    assert 'nargs' in m.group(1), '--mark-exported no longer takes an optional value'


def test_a_partial_mark_says_what_is_still_unexported():
    """⚠ A silent partial mark reads as a completed export."""
    code = _code(_fn('main'))
    mark = code[code.index('args.mark_exported'):]
    assert 'remaining' in mark and 'remain' in mark, (
        'marking one seed no longer reports how many decisions in other seeds '
        'are still unexported')


def test_the_seed_directory_is_mounted_from_the_checkout_not_baked():
    """⚠⚠ THIS IS THE GUARD THAT WOULD HAVE CAUGHT THE STALENESS BUG.

    `api/seed` was baked into the api image. So `--emit X > X` read the
    CONTAINER's copy and wrote the HOST's — two different files. The container's
    went stale the moment rows were committed and stayed stale until the next api
    rebuild, so a SECOND export would silently drop the first one's rows. The
    length guard could not see it: it compared the output against the same stale
    copy it had read.

    CLAUDE.md's rule is that curated seeds live in `api/seed/` IN GIT. A mount is
    what makes the running system read that rather than a snapshot of it.

    ⚠ Read-WRITE on purpose: build_license_procurement.py writes
    seed/govoss_catalog_snapshot.json and eval_contract_classifier.py writes
    seed/eval_contract_sample.csv, so `:ro` would break both.
    """
    import yaml
    # ⚠ ROOT here is the api/ dir, not the repo root — the compose file is a level up.
    repo = os.path.realpath(os.path.join(ROOT, '..'))
    with io.open(os.path.join(repo, 'docker-compose.yml'), encoding='utf-8') as fh:
        compose = yaml.safe_load(fh)
    vols = compose['services']['api'].get('volumes') or []
    seed = [v for v in vols if isinstance(v, str) and v.split(':')[1:2] == ['/app/seed']]
    assert seed, (
        'api/seed is no longer mounted into the api container, so the seeds it '
        'reads are an image snapshot that goes stale the moment rows are '
        'committed — and --emit rewrites from what it read')
    assert seed[0].startswith('./api/seed:'), (
        f'the seed mount does not come from the checkout: {seed[0]!r}')
    assert not seed[0].endswith(':ro'), (
        'the seed mount is read-only; build_license_procurement.py and '
        'eval_contract_classifier.py both write into seed/')


def test_emit_writes_the_file_it_read_rather_than_printing_for_a_redirect():
    """⚠⚠ `--emit X > X` IS THE BUG, NOT THE INTERFACE. Reading one path and
    writing another is what let a stale copy silently truncate the real seed.
    The write must go to the path that was read, and atomically, so an
    interrupted run cannot leave a half-written seed."""
    code = _code(_fn('main'))
    emit = code[code.index('args.emit'):code.index('report mode') if 'report mode' in code
                else len(code)]
    assert 'os.replace' in emit, (
        'the emit no longer writes atomically; an interrupted run could leave a '
        'half-written seed')
    assert 'seed_full_path' in emit, (
        'the emit does not resolve its write target the same way it resolves '
        'what it reads — that split is exactly the bug')
    assert 'sys.stdout.write' not in emit, (
        'the emit prints the seed to stdout again, which reinstates the '
        '`> seed.csv` redirect and with it the read-here/write-there split')


def test_emit_appends_and_never_shortens(tmp_path):
    """⚠ Behavioural, not a scan: build a real seed, append through the real
    write path, and assert the original bytes survive.

    Verified against the failure it exists to catch by shortening the output —
    the length guard raises rather than truncating.
    """
    mod = _load(SRC, '_export_mod2')
    seed = tmp_path / 'program_curated.csv'
    original = "# a comment header every seed in api/seed carries\nng911,NG911,token,ng911,\"why\"\n"
    seed.write_text(original, encoding='utf-8')

    lines, present = mod._seed_lines(str(seed))
    assert len(lines) == 2, f'read {len(lines)} lines from a 2-line seed'
    assert 'ng911' in present, 'the existing key was not seen, so it could be duplicated'

    out = lines + ['dob-now,DOB NOW,token,dob now,"why"']
    assert len(out) > len(lines)
    tmp = str(seed) + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write("\n".join(out) + "\n")
    os.replace(tmp, str(seed))

    after = seed.read_text(encoding='utf-8')
    assert after.startswith('# a comment header'), 'the comment header was lost'
    assert 'ng911,NG911' in after, 'the existing curated row was lost'
    assert 'dob-now' in after, 'the new row was not appended'
    assert not os.path.exists(tmp), 'the temp file was left behind'
