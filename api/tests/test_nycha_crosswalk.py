"""Unit tests for the NYCHA->PASSPort crosswalk matching logic (pure functions;
no DB/DuckDB needed)."""
import importlib

xw = importlib.import_module("build_nycha_vendor_crosswalk")


def test_norm_strips_suffix_and_punct():
    assert xw.norm("Fine Touch Constructions, Inc.") == "FINE TOUCH CONSTRUCTIONS"
    assert xw.norm("A&M Fire-Out, LLC") == "A M FIRE OUT"


def test_norm_strips_apostrophes():
    # ADAM'S -> ADAMS (dropped, not spaced) so it exact-matches NYCHA "ADAMS".
    assert xw.norm("ADAM'S EUROPEAN CONTRACTING INC") == "ADAMS EUROPEAN CONTRACTING"
    assert xw.norm("ADAMS EUROPEAN CONTRACTING INC.") == xw.norm("ADAM'S EUROPEAN CONTRACTING INC")
    assert xw.norm("O'Brien & Sons") == "OBRIEN SONS"


def test_fuzzy_high_accepts_clear_variants():
    pv = [("ACTION CARTING ENVIRONMENTAL SERVICES", "1", "Action Carting Environmental Services Inc")]
    high, review = xw._fuzzy_matches(["ACTION CARTING ENVIRONMENTAL SERVICE INC."], pv)
    assert [h[0] for h in high] == ["ACTION CARTING ENVIRONMENTAL SERVICE INC."]
    assert high[0][1] == "1" and high[0][3] >= xw.FUZZY_HIGH


def test_fuzzy_rejects_identity_token_swap():
    """BERNARDO'S vs GERARD'S (same generic tokens, different identity) must NOT
    auto-link — a false positive that motivated the conservative threshold."""
    pv = [("GERARDS PLUMBING HEATING", "2", "Gerards Plumbing Heating Corp")]
    high, review = xw._fuzzy_matches(["BERNARDOS PLUMBING & HEATING CORP"], pv)
    assert [h[0] for h in high] == []  # not in the auto-link tier


def test_fuzzy_rejects_generic_token_collapse():
    """Different firms whose names collapse to a shared generic token (GROUP/CORP
    stripped, short identity dropped) must NOT auto-link — the magnet-cluster bug
    (e.g. "B2 CONSTRUCTION" vs "J & N Construction Group Corp")."""
    pv = [(xw.norm("J & N Construction Group Corp"), "9", "J & N Construction Group Corp")]
    high, review = xw._fuzzy_matches(["B2 CONSTRUCTION CORP"], pv)
    assert [h[0] for h in high] == []


def test_load_curated_absent(monkeypatch, tmp_path):
    """⚠ UPDATED 2026-08-28: with no env var the loader now finds the
    VERSION-CONTROLLED seed, which is the fix — so "absent" has to be simulated
    by pointing the env at a path that does not exist."""
    monkeypatch.setenv("NYCHA_CURATED_XWALK_CSV", str(tmp_path / "nope.csv"))
    assert xw._load_curated() == []


def test_load_curated_parses_confirms_and_rejections(tmp_path, monkeypatch):
    """Curated CSV: a real id = confirmed link; a '-' marker = reviewed rejection
    (id None) so the pair neither auto-links nor returns to the review queue."""
    # Names are QUOTED — 47 of the 212 reviewed NYCHA names contain a comma
    # ("C.D.E. AIR CONDITIONING CO, INC."), so the file must be real CSV.
    p = tmp_path / "curated.csv"
    p.write_text(
        "nycha_vendor_name,passport_supplier_id,note\n"
        '"W.B. MASON CO., INC.",1623399,confirmed same vendor\n'
        "DF CONTRACTING INC,-,NOT MDF CONTRACTING CORP\n"
        '"SAM\'S TECHNICAL SERVICES INC.",none,NOT SLAM Technical Services\n',
        encoding="utf-8")
    monkeypatch.setenv("NYCHA_CURATED_XWALK_CSV", str(p))
    rows = xw._load_curated()
    assert len(rows) == 3
    by = {r[0]: r[1] for r in rows}
    assert by["W.B. MASON CO., INC."] == "1623399"          # confirmed
    assert by["DF CONTRACTING INC"] is None                  # '-' -> rejection
    assert by["SAM'S TECHNICAL SERVICES INC."] is None       # 'none' -> rejection


def test_load_curated_defaults_to_the_version_controlled_seed(monkeypatch):
    """⚠⚠ REWRITTEN 2026-08-28 — IT PREVIOUSLY PINNED THE DEFECT.

    This asserted the loader defaults to `<DATA>/nycha_curated_xwalk.csv`, i.e. a
    file on the prod box. That is exactly why 213 reviewed decisions lived in
    exactly one place, one volume rebuild from gone. The test was doing its job:
    it failed the moment the default changed, which is how a guard should behave
    when you deliberately change the thing it guards.

    The default is now the repo seed, matching build_org_vendor_crosswalk.py.
    ⚠ The $DATA path survives as a FALLBACK so decisions made on the box before
    this shipped are still picked up rather than silently dropped.
    """
    monkeypatch.delenv("NYCHA_CURATED_XWALK_CSV", raising=False)
    rows = xw._load_curated()
    assert len(rows) >= 213, f"the seed is not being read: {len(rows)} rows"
    assert not any(n.startswith("#") for n, _i, _n2 in rows), \
        "comment lines are being parsed as vendor names"


# ---------------------------------------------------------------------------
# SAFETY BY CONSTRUCTION — added 2026-08-28, after the review-contract draft
# surfaced that this table publishes unreviewed matches.
# ---------------------------------------------------------------------------

def _src():
    import io, os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                     'build_nycha_vendor_crosswalk.py')
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def test_a_held_candidate_never_lands_in_the_live_id_column():
    """⚠⚠ THE #146 DEFECT, MEASURED LIVE ON THIS TABLE.

    `routers/oce.py`'s vendor-profile reverse lookup runs
        SELECT ... FROM nycha_vendor_crosswalk WHERE passport_supplier_id = $1
    with NO tier filter. So while a `fuzzy-review` row carried a real
    `passport_supplier_id`, an unreviewed guess would have published as NYCHA
    activity on a public vendor profile. Nothing was wrong at the time only
    because the fuzzy-review queue happened to be empty.

    `org_vendor_crosswalk` was written later and avoids this by construction —
    candidates in `candidate_supplier_id`, link column NULL, so a join CANNOT
    return one. This asserts NYCHA now matches that standard.
    """
    import re
    s = _src()
    assert "'fuzzy-review', 'fuzzy-token-ratio'" in s, \
        'the fuzzy-review insert is gone or unrecognisable'
    assert re.search(r"VALUES \(\$1, NULL, \$2", s), (
        'the fuzzy-review INSERT no longer writes NULL into passport_supplier_id '
        '— a held candidate would publish on the vendor profile')
    assert 'candidate_supplier_id' in s, 'the candidate column is gone'


def test_both_columns_move_together_on_conflict():
    """⚠ Nulling the link without recording the candidate loses the proposal;
    recording the candidate without nulling the link leaves the guess published.
    Only both together is correct."""
    s = _src()
    assert 'passport_supplier_id = NULL,' in s and \
           'candidate_supplier_id = EXCLUDED.candidate_supplier_id,' in s, \
        'the ON CONFLICT branch no longer moves both columns together'


def test_the_curated_seed_is_version_controlled():
    """⚠⚠ 213 REVIEWED DECISIONS LIVED ONLY ON THE PROD BOX until 2026-08-28,
    at $DATA/nycha_curated_xwalk.csv — one volume rebuild from gone. CLAUDE.md
    carried it as a known defect for a month. The builder must default to the
    version-controlled seed, matching build_org_vendor_crosswalk.py which was
    written later specifically to avoid repeating this."""
    import io, os
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    seed = os.path.join(root, 'seed', 'nycha_curated_xwalk.csv')
    assert os.path.exists(seed), 'the curated seed is not in the repo'
    s = _src()
    assert 'seed", "nycha_curated_xwalk.csv"' in s, \
        'the builder no longer defaults to the version-controlled seed'
    import csv
    with io.open(seed, encoding='utf-8') as fh:
        rows = [r for r in csv.reader(fh)
                if r and r[0].strip() and not r[0].lstrip().startswith('#')]
    assert len(rows) - 1 >= 213, f'decisions lost: {len(rows)-1} < 213'
    # ⚠ 47 of these names contain a comma; hand-splitting mangled them once (#155)
    assert sum(1 for r in rows if ',' in r[0]) >= 47, \
        'comma-containing names were mangled — the file must stay quoted CSV'
