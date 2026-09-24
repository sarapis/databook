"""One owner for the FMS capital project id, which four publishers spell three ways.

⚠⚠ THE DEFECT THIS EXISTS TO PREVENT, AND IT IS NOT THE OBVIOUS ONE. The
tempting rule is "strip a leading three-digit agency code". That rule is WRONG,
and wrong in the silent direction: it corrupts ids that legitimately begin with
digits. Measured 2026-09-04 against the live plan (`capitalprojectslist`,
ccpversion fisa_2026) and the Dashboard (period 202605):

    814 of 12,929 CPDB `projectid` values START WITH 3+ DIGITS   02200901, 9605RENEW
    361 of  5,608 Dashboard `FMS ID` values likewise             (bare ids, not prefixed)

Blind stripping would rewrite `02200901` to `00901` — a project id that does not
exist — for over a thousand projects, and every join on them would then miss.

⚠⚠ THE MEASUREMENT THAT SETTLES THE DESIGN: **no source joins on the
agency-concatenated form.** Both id-bearing tables carry the BARE `projectid`:

    Dashboard `FMS ID`   5,608 ids -> 5,556 match `projectid`, **0** match `maprojid`
    2023 series `PROJECT_ID`       -> 4,865 match `projectid`, **0** match `maprojid`

So concatenation is an INTERNAL CPDB spelling (`maprojid = lpad(magency,3,'0') ||
projectid`, verified on all 12,929 rows) plus a legacy URL form, never a join
key. There is therefore nothing to infer: the only prefix this module removes is
one it can see unambiguously.

⚠ THE TWO EXTERNAL FEEDS ARE SPACE-SEPARATED AND UNIVERSALLY SO, which is what
makes them safe to split:

    Climate Budgeting `project_id`   9,146 of 9,146 match `^\\d{3} `   '850 LNCA13HAM'
    Parks tracker     `FMSID`        1,962 of 1,962 match `^\\d{3} `   '846 P-405VITO'

Normalising them lifts the join from **0 to 9,119** (Climate, of 9,134 distinct)
and **0 to 1,409** (Parks, of 1,867) against CPDB. A space cannot appear inside a
bare id, so the split is exact rather than heuristic.

⚠ For a value that may be EITHER form — a URL path segment such as
`858DOIT5MYSM` — use `candidates()`, which returns what to try in order and
leaves the resolving to the caller, who has the data. Guessing a single answer is
what breaks the 814.
"""
import re

# `NNN` + whitespace + the id. Both external feeds use exactly this, always.
# The separator is required: without it the pattern would match a bare id that
# merely starts with three digits, which is the 814-project defect above.
_PREFIXED = re.compile(r'^(\d{3})\s+(\S.*)$')

# The agency-concatenated form CPDB stores in `maprojid`: three digits followed
# immediately by the id. ⚠ Only ever applied as a FALLBACK candidate, never as
# the single answer — see the module docstring.
_CONCATENATED = re.compile(r'^(\d{3})(\D.*)$')


def norm(value):
    """Canonical bare project id for joining.

    Strips a three-digit agency code ONLY when a separator makes it
    unambiguous, upper-cases, and trims. Anything else is returned as-is,
    because a bare id that starts with digits is a real id.

    >>> norm('846 P-405VITO')
    'P-405VITO'
    >>> norm('02200901')          # NOT stripped — a real id
    '02200901'
    """
    if value is None:
        return ''
    v = str(value).strip()
    if not v:
        return ''
    m = _PREFIXED.match(v)
    if m:
        v = m.group(2).strip()
    return v.upper()


def agency_code(value):
    """The three-digit managing-agency code carried in the id, or ''.

    Only reads a code the separator makes unambiguous, for the same reason
    `norm` does. A bare id never yields one even when it starts with digits.
    """
    if value is None:
        return ''
    m = _PREFIXED.match(str(value).strip())
    return m.group(1) if m else ''


def candidates(value):
    """Ordered ids to try when the form is UNKNOWN — e.g. a URL segment.

    ⚠ THE ORDER IS THE SAFETY PROPERTY. The exact value comes first, so a real
    id that happens to begin with three digits resolves as itself and never as
    its own truncation. The concatenated split is offered only afterwards, and
    only when what follows the digits is non-numeric — `858DOIT5MYSM` splits,
    `02200901` does not.

    Returns a de-duplicated list preserving that order. The caller resolves
    against the data; this module never decides which candidate is real.

    >>> candidates('858DOIT5MYSM')
    ['858DOIT5MYSM', 'DOIT5MYSM']
    >>> candidates('02200901')
    ['02200901']
    """
    if value is None:
        return []
    v = str(value).strip()
    if not v:
        return []

    out = [v.upper()]

    m = _PREFIXED.match(v)
    if m:
        out.append(m.group(2).strip().upper())

    m = _CONCATENATED.match(v)
    if m:
        out.append(m.group(2).strip().upper())

    seen = set()
    ordered = []
    for c in out:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def maprojid(agency, projectid):
    """Rebuild CPDB's concatenated form.

    ⚠ `lpad(magency, 3, '0')`, not plain concatenation: `magency` is 2-3 chars
    in the source and `maprojid = magency || projectid` holds on only 11,024 of
    12,929 rows, while the zero-padded form holds on **all 12,929**.
    """
    a = '' if agency is None else str(agency).strip()
    p = '' if projectid is None else str(projectid).strip()
    if not a or not p:
        return ''
    return a.zfill(3) + p
