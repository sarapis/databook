"""Guards for `modules.fmsid` and `modules.budgetline`.

Every case below is a shape MEASURED in the live sources on 2026-09-04, not an
invented example. The counts quoted in the assertions are what make a
regression legible: "this rule would corrupt 814 real projects", not "this
string changed".
"""
import importlib.util
import os

import pytest

MODULES = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', 'modules'))


def _load(name):
    """Load a dependency-free module BY PATH.

    ⚠ `conftest.py` replaces the whole `modules` package with a MagicMock, so
    `from modules import fmsid` inside a test yields a mock that satisfies
    almost any assertion — this repo has shipped that mistake before. Loading by
    path gets the real code.
    """
    spec = importlib.util.spec_from_file_location(name, os.path.join(MODULES, name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fmsid = _load('fmsid')
budgetline = _load('budgetline')


# ── fmsid ────────────────────────────────────────────────────────────────────

# Bare ids that BEGIN WITH DIGITS. 814 of 12,929 CPDB projectids and 361 of
# 5,608 Dashboard FMS IDs look like this; a "strip three leading digits" rule
# silently rewrites every one of them into an id that does not exist.
DIGIT_LEADING_BARE = ['02200901', '9605RENEW', '26-STAB13', '8THSTREET']

# The two external feeds, which are universally 'NNN<space>id'
# (Climate 9,146/9,146; Parks 1,962/1,962).
PREFIXED = [
    ('846 P-405VITO', 'P-405VITO', '846'),
    ('846 P-3PHILSQ', 'P-3PHILSQ', '846'),
    ('850 LNCA13HAM', 'LNCA13HAM', '850'),
    ('071 HH112LFER', 'HH112LFER', '071'),
    ('801 SEEDVANST', 'SEEDVANST', '801'),
]


@pytest.mark.parametrize('raw', DIGIT_LEADING_BARE)
def test_a_bare_id_that_starts_with_digits_is_never_stripped(raw):
    """The 814-project defect. `norm` must return these unchanged."""
    assert fmsid.norm(raw) == raw.upper(), (
        f'{raw!r} is a real bare project id. Stripping its leading digits '
        'invents an id that does not exist and every join on it misses.')


@pytest.mark.parametrize('raw,expected,code', PREFIXED)
def test_a_space_separated_prefix_is_stripped(raw, expected, code):
    """Splitting these lifts the Climate join 0 -> 9,119 and Parks 0 -> 1,409."""
    assert fmsid.norm(raw) == expected.upper()
    assert fmsid.agency_code(raw) == code


def test_agency_code_is_not_invented_for_a_bare_id():
    """A bare id yields no code even when it opens with three digits."""
    for raw in DIGIT_LEADING_BARE:
        assert fmsid.agency_code(raw) == '', (
            f'{raw!r} carries no separator, so its leading digits are part of '
            'the id, not an agency code')


def test_candidates_offers_the_exact_value_first():
    """⚠ Order is the safety property for an unknown form (e.g. a URL segment).

    The exact value must come first so a real digit-leading id resolves as
    itself. The concatenated split is a fallback, never the single answer.
    """
    got = fmsid.candidates('858DOIT5MYSM')
    assert got[0] == '858DOIT5MYSM'
    assert 'DOIT5MYSM' in got

    # A numeric-continuation id offers no split at all: '02200901' must not
    # suggest '00901'.
    assert fmsid.candidates('02200901') == ['02200901']


def test_candidates_deduplicates_and_drops_empties():
    assert fmsid.candidates('') == []
    assert fmsid.candidates(None) == []
    assert len(fmsid.candidates('846 P-405VITO')) == len(set(fmsid.candidates('846 P-405VITO')))


def test_maprojid_zero_pads_the_agency():
    """⚠ `magency` is 2-3 chars. Plain concatenation reproduces maprojid on only
    11,024 of 12,929 CPDB rows; zero-padded reproduces all 12,929."""
    assert fmsid.maprojid('57', 'FD175DRS4') == '057FD175DRS4'
    assert fmsid.maprojid('846', 'P-405VITO') == '846P-405VITO'
    assert fmsid.maprojid('', 'X') == ''


def test_the_prefix_rule_requires_a_separator():
    """Pins the mechanism, so a future 'simplification' to `^\\d{3}` fails here.

    Without the separator requirement this pattern matches every one of the
    digit-leading bare ids above.
    """
    assert fmsid._PREFIXED.match('846 P-405VITO')
    for raw in DIGIT_LEADING_BARE:
        assert not fmsid._PREFIXED.match(raw), (
            f'the prefix pattern must not match {raw!r} — it has no separator')


# ── budgetline ───────────────────────────────────────────────────────────────

# One budget line as each of the five sources spells it. Raw, these produce
# ZERO matches between sources; normalised, 1,601 commitment lines match
# capitalbudget and 1,900 of 1,913 match the commitment plan.
SPELLINGS = ['AG 0001', 'AG-0001', 'AG0001', 'ag-0001', ' AG 0001 ']


def test_every_spelling_normalises_to_one_key():
    keys = {budgetline.norm(s) for s in SPELLINGS}
    assert keys == {'AG0001'}, (
        f'the five source spellings must collapse to one key; got {keys}. '
        'Raw, these sources join 0 rows.')


def test_an_internal_space_is_punctuation_not_a_separator():
    """⚠ When the agency part is one letter the source pads it: 'P -I001',
    'C -0075'. Treating that space as a record separator invents two budget
    lines that do not exist."""
    assert budgetline.norm('P -I001') == 'PI001'
    assert budgetline.norm('C -0075') == 'C0075'
    assert budgetline.split('P -I001', 'none') == ['PI001']


def test_the_two_multivalued_sources_use_different_separators():
    """⚠ Dashboard is comma-separated, the 2023 series is 2+ spaces. There is no
    single split that serves both, which is why `sep` is explicit."""
    assert budgetline.split('PV-0467 , PV-0N131, PV-DN031', 'comma') == \
        ['PV0467', 'PV0N131', 'PVDN031']
    assert budgetline.split('AG-D001  AG-0001  AG-M001  HR-0025', 'spaces') == \
        ['AGD001', 'AG0001', 'AGM001', 'HR0025']
    # A single space must NOT split, in either mode.
    assert budgetline.split('P -I001', 'spaces') == ['PI001']


def test_split_requires_an_explicit_separator():
    """A default would be wrong for one of the two multi-valued sources."""
    with pytest.raises(ValueError):
        budgetline.split('AG-0001', 'whitespace')


def test_split_dedupes_preserving_order():
    assert budgetline.split('AG-0001 , AG 0001 , BR-0231', 'comma') == ['AG0001', 'BR0231']
    assert budgetline.split('', 'comma') == []
    assert budgetline.split(None, 'comma') == []
