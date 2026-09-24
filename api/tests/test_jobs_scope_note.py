"""`nycjobs` is ONE hiring portal — every surface that presents it must say so.

⚠⚠ THE DEFECT THIS PREVENTS. `nycjobs` (Socrata kpav-sd4t) is the City's central
careers portal and a CURRENT snapshot, not a history. Employers that run their own
hiring systems are absent from it entirely — measured 2026-09-02, by payroll rows:

    3,509,622  Department of Education   -> teachnyc.net
      424,455  Board of Elections        -> vote.nyc
      268,005  City University of New York -> cuny.edu/employment
       12,500  City Council              -> council.nyc.gov/jobs
       10,606  District Attorney - Queens -> queensda.org/careers
        ~3,300  the four Borough Presidents -> their own careers pages

So a bare count off this table looks like "City job postings" and excludes the
City's LARGEST employer and every independently elected office. That is the
complete-looking-but-partial shape this repo has paid for repeatedly (the renewal
calendar's silently dropped rows, `by_vendor` showing 25 of 88) — except here it
is baked into the SOURCE, so no query fix can close it. Only disclosure can.

⚠ I TESTED THE OBVIOUS EXPLANATION AND IT FAILED: "they are not in the DCAS civil
service system" is wrong — 18 of the 19 absent agencies ARE on the `civillist`
roster, DOE included (150,606 rows). Do not reach for that reasoning.

⚠ Payroll is UNAFFECTED and must not gain this note: `payrolldata` does cover
those employers. Only the jobs surfaces are partial.
"""
import ast
import os

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
VIEWS = os.path.join(ROOT, 'app/resources/views')

# The phrase every jobs surface must carry. Kept short and specific so the guard
# checks the CLAIM, not an exact wording nobody may reword.
_MARKER = 'central careers portal'

# How a view is recognised as presenting nycjobs data.
_JOBS_DATA = ('jobsUrl', 'jobTable', '/get/jobs/')

# ⚠⚠ AN EXPLICIT INVENTORY, BECAUSE AUTO-DETECTION MISSED ONE AND SHIPPED.
# The detector above looks for jobs-SPECIFIC markers, which a GENERIC view does
# not carry: `/o/{id}/jobs` renders `orgsection.blade.php`, a template that
# renders whatever section it is handed and mentions jobs nowhere. It passed the
# detector by not being seen at all, and the note was missing from the rendered
# page while every unit test was green — caught only by fetching the URL.
# So: name the surfaces. A detector finds NEW ones; the inventory pins the KNOWN
# ones, the same split as ALLOWED_NAME_JOINS in test_vendor_identity.py.
_KNOWN_SURFACES = {
    'jobs.blade.php':            '/jobs',
    'titles_overview.blade.php': '/jobs-dashboard',
    'organization.blade.php':    'the org profile overview',
    'orgsection.blade.php':      '/o/{id}/jobs — GENERIC view, invisible to the detector',
}


def _views_presenting_jobs():
    out = []
    for dirpath, _dirnames, filenames in os.walk(VIEWS):
        for fn in filenames:
            if not fn.endswith('.blade.php'):
                continue
            path = os.path.join(dirpath, fn)
            src = open(path, encoding='utf-8', errors='replace').read()
            if any(t in src for t in _JOBS_DATA):
                out.append((os.path.relpath(path, ROOT), src))
    return out


def test_every_known_jobs_surface_carries_the_scope_note():
    """The inventory. Auto-detection is not enough — see _KNOWN_SURFACES."""
    for fn, where in _KNOWN_SURFACES.items():
        path = os.path.join(VIEWS, fn)
        assert os.path.exists(path), f"{fn} is gone — did {where} move?"
        src = open(path, encoding='utf-8').read()
        assert _MARKER in src, f"{fn} ({where}) lost the scope note"


def test_every_view_presenting_jobs_carries_the_scope_note():
    views = _views_presenting_jobs()
    # ⚠ A guard that finds zero surfaces passes. This repo's oldest defect.
    assert len(views) >= 3, (
        f"only {len(views)} jobs surfaces found — the detector is not looking. "
        f"Expected at least /jobs, the jobs dashboard and the org profile tab.")
    missing = [rel for rel, src in views if _MARKER not in src]
    assert not missing, (
        "these present nycjobs data without the scope note, so a reader sees a "
        f"count that silently excludes DOE, CUNY, BoE, the Council, the DAs and "
        f"the Borough Presidents: {missing}")


def test_the_note_names_the_large_exclusions_rather_than_hedging_vaguely():
    """⚠ "may not be complete" is not a disclosure — it tells a reader nothing
    they can act on. The note must NAME the big absentees, the way the renewal
    calendar discloses its three buckets rather than saying "some rows omitted"."""
    for rel, src in _views_presenting_jobs():
        if _MARKER not in src:
            continue
        for who in ('Department of Education', 'CUNY', 'Board of Elections'):
            assert who in src, f"{rel}: the scope note does not name {who}"


def test_the_hero_no_longer_claims_to_cover_all_agencies():
    """⚠ THE HEADLINE WAS ITSELF THE OVER-CLAIM. /jobs read "current openings
    across NYC government agencies", which states the very thing that is false.
    A note underneath does not undo a false sentence above it."""
    src = open(os.path.join(VIEWS, 'jobs.blade.php'), encoding='utf-8').read()
    assert 'across NYC government agencies' not in src, (
        "the /jobs hero claims to cover NYC government agencies; it covers one portal")


def test_the_mcp_jobs_tool_declares_its_scope_but_the_payroll_tools_do_not():
    """An AI consumer needs this more than a human reader: it will happily report
    a total as "City job postings". ⚠ And payroll must NOT carry it — payrolldata
    DOES cover those employers, so the same note there would be simply false."""
    src = open(os.path.join(ROOT, 'api/mcp_server.py'), encoding='utf-8').read()
    tree = ast.parse(src)
    docs = {n.name: (ast.get_docstring(n) or '')
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert 'search_jobs' in docs, "search_jobs is gone"
    d = docs['search_jobs']
    assert 'SCOPE' in d and 'Department of Education' in d, (
        "search_jobs no longer declares that it covers one portal only")
    for payroll_tool in ('get_salary_stats', 'get_top_salaries'):
        assert 'central careers portal' not in docs.get(payroll_tool, ''), (
            f"{payroll_tool} carries the jobs scope note, but payrolldata DOES "
            f"cover DOE/CUNY/BoE — the note would be false there")
