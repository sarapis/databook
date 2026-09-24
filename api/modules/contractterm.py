"""Contract term arithmetic — how long a contract runs, and whether it runs now.

⚠⚠ THE ONLY DIVISION THIS SECTION ALLOWS ON CONTRACT MONEY IS BY TIME. There is
no seat, site or unit count anywhere in the contract data, so a per-seat cost
cannot be computed and must never be; cost per contract-YEAR is derivable from
the term dates and is the one honest rate. `routers/licenses.py` has enforced
that since 2026-08-11 and a test there fails the build on `per_seat`/`per_site`.

⚠ This module exists because a SECOND consumer appeared (the call-center lens's
per-programme annual run-rate) and the rule was a private helper in one router.
Two copies of "how long is this contract" is how two pages come to disagree
about the same contract.
"""


def years(start, end):
    """Contract length in years from the MM/DD/YYYY term dates, or None.

    ⚠ Returns None rather than guessing when either date is unusable. A default
    of 1 would silently turn a 5-year contract into a 5x-inflated annual cost —
    a fabricated number that looks like a measurement.
    """
    try:
        sm, sd, sy = str(start).strip().split("/")
        em, ed, ey = str(end).strip().split("/")
        n = (int(ey) - int(sy)) + (int(em) - int(sm)) / 12.0
        return round(n, 2) if 0.25 <= n <= 40 else None
    except (ValueError, AttributeError, TypeError):
        return None


def annual(value, start, end):
    """Cost per year of the term, or None when the term is unusable.

    ⚠ None, never 0 — "we cannot compute a rate" and "this costs nothing a year"
    are different claims, and a rendered $0.00 is one the City did not make.
    """
    n = years(start, end)
    if not n:
        return None
    try:
        return float(value) / n
    except (TypeError, ValueError):
        return None


def _iso(d):
    """MM/DD/YYYY -> YYYY-MM-DD, or None."""
    try:
        mm, dd, yy = str(d).strip().split("/")
    except (ValueError, AttributeError):
        return None
    if len(yy) != 4:
        return None
    return f"{yy}-{mm}-{dd}"


def is_active(start, end, today):
    """Is the term running on `today` (an ISO date string)?

    ⚠ Compares ISO STRINGS rather than dates, the same choice licensewindow makes
    and for the same reason: the source columns are text, and a parse step here
    would be a second place for a timezone to creep in.
    ⚠ An unusable date answers False rather than True — a contract we cannot
    place in time must not be counted into a CURRENT run-rate, because that rate
    is the figure a reader will read as "what this costs now".
    """
    s, e = _iso(start), _iso(end)
    if not s or not e:
        return False
    return s <= today <= e


def sql_date(col):
    """A term-date TEXT column as a SQL date, for ORDER BY; NULL when unusable.

    ⚠⚠ `start_date`/`end_date` are MM/DD/YYYY TEXT, so ordering the raw column
    sorts by MONTH first: 01/31/2031 lands before 12/01/2019. The All technology
    contracts table shipped exactly that on both date columns.
    ⚠ The format test keeps `TO_DATE` off malformed values, which raise or invent
    a date; an unusable value becomes NULL and sorts last under `NULLS LAST`.
    """
    return (f"CASE WHEN {col} ~ '^[0-9]{{2}}/[0-9]{{2}}/[0-9]{{4}}$' "
            f"THEN TO_DATE({col}, 'MM/DD/YYYY') END")
