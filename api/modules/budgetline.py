"""One owner for the capital BUDGET LINE, which five sources punctuate five ways.

⚠⚠ WITHOUT NORMALISATION THESE SOURCES DO NOT JOIN AT ALL. Measured 2026-09-04:

    raw       `capitalprojectscommitments` x `capitalbudget`  ->      0 matches
    normalised                                                ->  1,601 matches
    normalised x `capitalcommitmentplan`                      ->  1,900 of 1,913

Zero is the whole argument. Anyone joining these tables on the raw column gets an
empty result that reads exactly like "no budget lines in common".

The five spellings, measured across every row of each source:

    capitalbudget                 'AG 0001'   space      15,742 of 15,742
    capitalcommitmentplan         'AG0001'    plain      50,204  | 'C -0075' space 7,146
                                                                  | 'AG-0001' hyphen 1,726
    capitalprojectscommitments    'AG-0001'   hyphen     41,277 of 41,277
    Dashboard  (fb86-vt7u)        'WP-D169'   hyphen, and MULTI-VALUED
    2023 series (dollarscomp)     'WP-D169'   hyphen, and MULTI-VALUED

⚠⚠ A SINGLE BUDGET LINE CAN CONTAIN A SPACE, so whitespace is NOT a record
separator. When the agency part is one letter the source pads it: `P -I001`,
`C -0075`. Splitting a single value on whitespace would cut those in half and
invent two budget lines that do not exist.

⚠⚠ AND THE TWO MULTI-VALUED SOURCES USE DIFFERENT SEPARATORS, so there is no one
`split()` that serves both:

    Dashboard     comma        'PV-0467 , PV-0N131, PV-DN031'
    2023 series   2+ spaces    'AG-D001  AG-0001  AG-M001  HR-0025'

Hence `split()` takes the source's separator explicitly rather than guessing.
A single space never separates records in either.
"""
import re

# Everything that is punctuation in one spelling and absent in another.
_STRIP = re.compile(r'[\s\-]+')

# 2+ whitespace, the 2023 series' record separator. ⚠ Two, never one: one space
# occurs INSIDE a single line ('P -I001').
_MULTI_SPACE = re.compile(r'\s{2,}')


def norm(value):
    """Canonical budget line: punctuation removed, upper-cased.

    Unifies all five spellings onto one key.

    >>> norm('AG 0001'), norm('AG-0001'), norm('AG0001')
    ('AG0001', 'AG0001', 'AG0001')
    >>> norm('P -I001')          # the internal space is punctuation, not a split
    'PI001'
    """
    if value is None:
        return ''
    return _STRIP.sub('', str(value)).upper()


def sql_norm(col):
    """`norm` as a SQL expression, so the rule has ONE owner across two languages.

    ⚠⚠ THE ZERO IS THE ARGUMENT, AND IT IS MEASURED ON THIS EXACT JOIN. Council
    capital awards (`councilcapitalbudget`) against the spine's
    `capital_projects.budget_lines`, 2026-09-06:

        raw column = raw column          ->      0 rows
        both sides through this rule     -> 11,446 rows, over 3,725 projects

    Zero reads exactly like "this project received no Council award", which is a
    claim about the City rather than about our punctuation.

    ⚠ It must stay byte-equivalent to `norm`. A guard runs both over every budget
    line spelling observed in every source and fails on a single disagreement —
    a SQL rule that has drifted from the Python one is the suffix-list defect,
    where a check measures a different system than the code it guards.
    """
    return f"upper(regexp_replace({col}, '[\\s\\-]+', '', 'g'))"


def split(value, sep='comma'):
    """Split a possibly multi-valued field into normalised budget lines.

    `sep` names the SOURCE's separator and is required to be explicit:

      'comma'  — Dashboard  ('PV-0467 , PV-0N131')
      'spaces' — 2023 series ('AG-D001  AG-0001')
      'none'   — single-valued sources (capitalbudget, commitment plan,
                 capitalprojectscommitments); the whole value is one line.

    ⚠ Order is preserved and duplicates dropped, so a field naming the same
    line twice yields one entry rather than inflating any count built from it.

    >>> split('PV-0467 , PV-0N131', 'comma')
    ['PV0467', 'PV0N131']
    >>> split('AG-D001  AG-0001', 'spaces')
    ['AGD001', 'AG0001']
    >>> split('P -I001', 'none')
    ['PI001']
    """
    if value is None:
        return []
    v = str(value).strip()
    if not v:
        return []

    if sep == 'comma':
        parts = v.split(',')
    elif sep == 'spaces':
        parts = _MULTI_SPACE.split(v)
    elif sep == 'none':
        parts = [v]
    else:
        raise ValueError(
            "sep must be 'comma', 'spaces' or 'none' — naming the source's "
            "separator explicitly is deliberate; the two multi-valued sources "
            "disagree, so a default would be wrong for one of them")

    out = []
    seen = set()
    for p in parts:
        n = norm(p)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out
