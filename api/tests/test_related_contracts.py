"""Guards for the contract page's "Related contracts" block (task 2eba1fce (a)).

⚠⚠ THE SECOND SIGNAL IS ALMOST PURE NOISE WITHOUT ITS TWO RULES. Measured across
all 56,806 contracts on 2026-08-18:
  * 46,607 contracts co-terminate with a DIFFERENT vendor at the same agency;
  * the largest group is 4,721 contracts (DYCD, 06/30/2023), then 1,873 / 1,835 /
    1,751 — and EVERY oversized group lands on 06/30, the NYC fiscal-year
    boundary, where a shared end date carries no information at all.
Dropping either rule re-admits a "4,721 related contracts" block. With both, 3,488
groups / 12,007 contracts survive — and MOCS's PASSPort, at 2 contracts and
$61.9M all ending 04/27/2027, is among them.

⚠ This docstring said "5 contracts and $78.1M" until 2026-08-19. That figure was
the amendment double-count this file's grain guards now exist to prevent (#278):
those five ROWS are two contracts. Corrected here as well as in the code, because
a stale figure in a test reads exactly like a measured one.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
OCE = os.path.join(ROOT, 'api/routers/oce.py')
CTRL = os.path.join(ROOT, 'app/app/Http/Controllers/ProcurementController.php')
VIEW = os.path.join(ROOT, 'app/resources/views/procurement/contract_profile.blade.php')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _fn():
    s = _read(OCE)
    body = s[s.index('async def _related_contracts'):]
    return body[:body.index('\nasync def ', 5)]


def test_the_fiscal_year_boundary_is_excluded():
    """⚠ 06/30 is where hundreds of unrelated contracts expire together. Without
    this the block shows a DYCD contract 4,720 'related' ones.

    ⚠ ASSERTS THE PREDICATE, NOT THE STRING. This guard's first draft checked
    `'06/30' in code` after stripping `#` comments — and passed with the exclusion
    deleted, because the function's DOCSTRING explains the 06/30 rule and a
    docstring is not a `#` comment. Fourth time in one session that a scanner
    matched prose; assert the executable expression.
    """
    import ast
    tree = ast.parse(_read(OCE))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == '_related_contracts')
    # Ignore the docstring node entirely, then look for the real call.
    body = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                           and isinstance(fn.body[0].value, ast.Constant)) else fn.body
    calls = [n for n in ast.walk(ast.Module(body=body, type_ignores=[]))
             if isinstance(n, ast.Call)
             and getattr(n.func, 'attr', '') == 'startswith'
             and any(isinstance(a, ast.Constant) and a.value == '06/30' for a in n.args)]
    assert calls, (
        "the fiscal-year-boundary exclusion is gone from the CODE; without it a "
        "DYCD contract shows 4,720 'related' contracts")


def test_the_group_size_cap_exists_and_is_applied():
    """A program is a handful of contracts. The cap must gate the RESULT, not
    merely be defined — a constant nothing reads is not a rule."""
    src = _read(OCE)
    assert '_COTERM_MAX_GROUP' in src, "the group-size cap constant is gone"
    body = _fn()
    code = '\n'.join(l for l in body.splitlines() if not l.lstrip().startswith('#'))
    assert re.search(r'len\(peers\)\s*<=\s*_COTERM_MAX_GROUP', code), \
        "the cap is no longer applied to the peer group"


def test_the_two_kinds_are_never_merged():
    """⚠ They carry different evidential weight: same-vendor is a FACT, and
    co-termination is CIRCUMSTANTIAL. Merging them would launder the second."""
    body = _fn()
    assert '"same_vendor"' in body and '"co_terminating"' in body, \
        "the two relatedness kinds are no longer separate keys"


def test_the_page_does_not_claim_co_termination_proves_a_program():
    """⚠ THE STANDING RULE. Co-termination plus a shared agency is circumstantial;
    asserting a shared program from it is the same overreach as claiming a
    product identity from it (the Ivalua/PASSPort caution)."""
    view = _read(VIEW)
    assert 'not evidence that they are' in view, \
        "the page lost the sentence stopping it from asserting a shared program"
    assert 'fiscal-year boundary' in view, \
        "the page no longer discloses the 30 June exclusion"
    assert re.search(r'groups of \{\{ \$rcCap \}\} or fewer', view), \
        "the page no longer states the group-size cap, or hardcodes it instead of " \
        "rendering the served value"


def test_the_controller_passes_related_contracts_to_the_view():
    """⚠⚠ THE #247 DEFECT, and this controller is the shape that caused it — it
    NAMES each key rather than passing the payload wholesale, so a new key
    silently never arrives and `?? []` degrades politely. Only fetching the page
    would otherwise catch it."""
    ctrl = _read(CTRL)
    assert "'relatedContracts' => $data['related_contracts']" in ctrl, \
        "the controller does not pass related_contracts; the block renders empty"
    view = _read(VIEW)
    assert '$relatedContracts' in view, "the view no longer reads the key"


def test_the_endpoint_serves_the_key():
    src = _read(OCE)
    assert '"related_contracts": await _related_contracts(' in src, \
        "the contract endpoint no longer serves related_contracts"


# ---------------------------------------------------------------------------
# GRAIN. Added after the block shipped publishing figures that did not exist.
#
# ⚠⚠ `contracts` HOLDS ONE ROW PER AMENDMENT — 55,806 rows for 36,421 distinct
# contract_ids — and every amendment carries its OWN ctr_id. The first draft
# deduped with `DISTINCT ON (ctr_id)`, which therefore collapsed nothing, and
# measured on prod it failed in BOTH directions:
#   * standing on Ivalua's PASSPort contract, `same_vendor` listed FIVE rows,
#     every one an amendment of the contract being read — $33.67M of "other
#     contracts" that do not exist, under a heading calling the list a FACT.
#     901 (vendor, agency) groups hold ONE real contract behind >1 row, so 3,551
#     contract pages rendered a wholly phantom block;
#   * the size cap counted ROWS, so 149 genuine groups were dropped as "too big"
#     and 2,762 pages silently lost the block.
# The six guards above all passed throughout: they pin the noise rules and the
# controller seam, and NONE of them looked at the grain.
# ---------------------------------------------------------------------------

def _run_related(peers=None, same_vendor_rows=None, contract_id='CT1-002-20228801501',
                 ctr_id='4509900'):
    """Run the REAL `_related_contracts`, capturing the SQL it emits.

    ⚠ The dedup happens in Postgres, so a fake cannot execute it — which is why
    the grain is asserted against the EMITTED SQL and only the self-exclusion is
    asserted behaviourally. Same split as the partial-index guard.
    """
    import asyncio
    from routers import oce

    captured = []

    async def _fake_select_safe(sql, params=None):
        captured.append(sql)
        if 'vendor_name = $1' in sql:
            return list(same_vendor_rows or [])
        return list(peers or [])

    real = oce.PostgresModelAsync.select_safe
    oce.PostgresModelAsync.select_safe = _fake_select_safe
    try:
        out = asyncio.run(oce._related_contracts(
            ctr_id, contract_id, 'Ivalua Inc', 'OFFICE OF CONTRACT SERVICES',
            '04/27/2027'))
    finally:
        oce.PostgresModelAsync.select_safe = real
    return out, captured


def test_both_lists_dedupe_at_contract_grain_not_ctr_id():
    """⚠ ASSERTS THE EMITTED SQL, because the grain is decided by Postgres.

    `DISTINCT ON (ctr_id)` is a no-op against amendments — each has its own
    ctr_id — so it must not be what either query keys on. The key is #262's
    `coalesce(contract_id, ctid)`: keying on contract_id ALONE would collapse
    every NULL-id row into one, and 2,546 rows carry no contract_id.
    """
    _, captured = _run_related()
    assert len(captured) == 2, f'expected both queries to run, got {len(captured)}'
    for sql in captured:
        assert "DISTINCT ON (coalesce(contract_id, 'row:' || ctid::text))" in sql, (
            'a related-contracts query is not deduping at contract grain: ' + sql)
        assert 'DISTINCT ON (ctr_id)' not in sql, (
            'ctr_id cannot dedupe amendments — each amendment has its own: ' + sql)
        # the ORDER BY must lead with the same expression or Postgres rejects it,
        # and picking the largest amendment is what makes the survivor the
        # contract's own restated total (#262).
        assert "ORDER BY coalesce(contract_id, 'row:' || ctid::text), current_amount DESC" in sql


def test_a_contract_is_never_listed_as_related_to_itself():
    """⚠⚠ THE BUG THIS FILE EXISTS FOR, and it is NOT fixed by excluding ctr_id.

    A contract's own amendments share its contract_id and carry DIFFERENT
    ctr_ids, so an exclusion keyed on ctr_id leaves them in the list — which is
    how Ivalua's contract came to be listed among the contracts co-terminating
    with it, and how its five amendments became five 'other contracts this
    vendor holds'.
    """
    own_amendment = {'ctr_id': '5595171', 'contract_id': 'CT1-002-20228801501',
                     'vendor_name': 'Ivalua Inc', 'current_amount': 6_500_000.0}
    other = {'ctr_id': '5068301', 'contract_id': 'CT1-002-20248805109',
             'vendor_name': 'ACCENTURE LLP', 'current_amount': 24_010_000.0}
    self_row = {'ctr_id': '4509900', 'contract_id': 'CT1-002-20228801501',
                'vendor_name': 'Ivalua Inc', 'current_amount': 37_910_000.0}

    out, _ = _run_related(peers=[self_row, own_amendment, other],
                          same_vendor_rows=[own_amendment])

    coterm_ids = {r['contract_id'] for r in out['co_terminating']}
    assert coterm_ids == {'CT1-002-20248805109'}, (
        'the contract being read (or its amendments) leaked into '
        f'co_terminating: {coterm_ids}')
    assert out['same_vendor'] == [], (
        "an amendment of the contract being read is not another contract the "
        f"vendor holds: {out['same_vendor']}")


def test_the_size_cap_is_applied_to_the_deduped_list():
    """⚠ The cap counts CONTRACTS. Counting rows dropped 149 real groups whose
    only sin was having amendments, and 2,762 pages lost the block silently — a
    false negative is invisible in a way an inflated list is not."""
    from routers.oce import _COTERM_MAX_GROUP

    def _peer(i):
        return {'ctr_id': f'900{i}', 'contract_id': f'CT-{i}',
                'vendor_name': f'V{i}', 'current_amount': 1.0}

    at_cap, _ = _run_related(peers=[_peer(i) for i in range(_COTERM_MAX_GROUP)])
    assert at_cap['co_terminating'], 'a group exactly at the cap must still render'

    over, _ = _run_related(peers=[_peer(i) for i in range(_COTERM_MAX_GROUP + 1)])
    assert over['co_terminating'] == [], 'a group over the cap must be dropped'
