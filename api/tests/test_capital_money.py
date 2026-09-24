"""Guards on how the six capital money measures are presented.

⚠⚠ THE DEFECT THIS PREVENTS. CPDB publishes six money columns that read like
successive stages of one pot. They are not, and drawing them as a funnel — which
docs/CAPITAL-SECTION-PLAN.md §5.3 originally proposed — shows money vanishing
between stages that are not stages. Measured 2026-09-05: adopted funding is more
than twice planned commitments, committed is a third of spent, and each column is
published for a different subset of projects. DDC alone reads $27.4B planned
against $152.2B adopted.

⚑ F, decided 2026-09-05: separate measures, each with its own population and an
info note, plus one note saying why they do not sum or nest.

⚠ The measured baselines live in `capitalmoney.MEASURES` and nowhere else. This
docstring used to restate them, the module's docstring restated them too, and two
of the module's six totals had already drifted from the values a few lines below
them. `test_the_baselines_are_not_restated_in_prose` is what stops that
recurring; do not paste the table back into either file.

⚠ The definitions are the PUBLISHER'S, quoted. Writing our own account of what
"allocated" means in NYC capital budgeting would invent authority we do not
have, so these guards check that attribution survives.
"""
import importlib.util
import os
import re

MODULES = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', 'modules'))
ROUTER = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', 'routers', 'capital.py'))


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(MODULES, name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


money = _load('capitalmoney')


def test_all_six_measures_are_present():
    keys = [m['key'] for m in money.MEASURES]
    assert keys == ['planned_usd', 'adopt_usd', 'allocate_usd',
                    'committed_usd', 'spent_usd', 'checkbook_usd'], (
        'all six published measures must appear — dropping one because it is '
        'small or awkward is the funnel by omission')


def test_every_measure_carries_a_definition_and_its_publisher():
    for m in money.MEASURES:
        assert m['definition'].strip(), f"{m['key']} has no definition"
        assert m['source'].strip(), f"{m['key']} does not say whose definition it is"
        assert len(m['definition']) > 40, (
            f"{m['key']}'s definition is too thin to serve as an info note")


def test_checkbook_is_attributed_to_the_comptroller_not_dcp():
    """⚠ Two publishers. DCP documents the plan; the Comptroller publishes the
    payments. Blending them would misattribute a claim."""
    cb = money.measure('checkbook_usd')
    assert 'Comptroller' in cb['source'] and 'Checkbook' in cb['source']
    for key in ('planned_usd', 'adopt_usd', 'allocate_usd', 'committed_usd', 'spent_usd'):
        assert 'City Planning' in money.measure(key)['source']


def test_the_not_a_funnel_note_exists_and_says_why():
    note = money.NOT_A_FUNNEL_NOTE
    assert 'not stages' in note or 'not sum' in note
    for must in ('window', 'cumulative', 'nest'):
        assert must in note.lower(), (
            f"the note must explain the mechanism, not just assert it; missing '{must}'")
    assert 'Subtracting' in note, (
        'the note must tell a reader not to subtract one measure from another — '
        'that is the specific wrong conclusion it exists to prevent')


def test_the_publisher_caveat_is_quoted_and_attributed():
    assert 'not a project or financial management system' in money.PUBLISHER_CAVEAT
    assert money.PUBLISHER_CAVEAT_SOURCE.strip()


def test_our_own_measurement_is_marked_as_ours():
    """⚠ The definitions are the publisher's; the arithmetic is ours. A reader
    must be able to tell which is which."""
    assert 'Databook' in money.BASIS


def test_the_payload_keeps_a_measure_with_no_value():
    """An absent figure is 'not published for this project', which is
    information. Dropping it makes the set look smaller than it is."""
    p = money.payload({'planned_usd': 1.0}, {'planned_usd': 5})
    assert len(p['measures']) == 6
    absent = [m for m in p['measures'] if m['key'] == 'committed_usd'][0]
    assert absent['value'] is None and absent['population'] is None
    assert absent['definition']


def test_the_payload_always_carries_the_note():
    for args in ((), ({}, {}), ({'planned_usd': 1.0}, {'planned_usd': 5})):
        p = money.payload(*args)
        assert p['note'] == money.NOT_A_FUNNEL_NOTE, (
            'the note must accompany the measures every time — a payload that '
            'can omit it will be rendered without it')


def test_every_measure_records_its_measured_baseline():
    """⚠ One home for each figure. These are documentation, never served."""
    for m in money.MEASURES:
        assert isinstance(m['baseline_population'], int) and m['baseline_population'] > 0
        assert isinstance(m['baseline_total_usd'], float) and m['baseline_total_usd'] > 0


def test_the_baselines_are_not_restated_in_prose():
    """⚠⚠ THE DEFECT THIS EXISTS FOR, WHICH ALREADY HAPPENED ONCE.

    `capitalmoney`'s docstring carried a hand-typed table of the same totals
    that sit in `MEASURES`, and two of its six had drifted — $201.8B against a
    measured $201.6B, $309.1B against $309.0B. A figure typed beside the
    machine-readable one it was copied from cannot be kept in step by care; the
    prose may describe the RELATIONSHIPS ("more than twice", "a third of") and
    the code owns the numbers.
    """
    for src_path in (os.path.join(MODULES, 'capitalmoney.py'), __file__):
        with open(src_path, encoding='utf-8') as fh:
            text = fh.read()
        doc = re.match(r'\s*"""(.*?)"""', text, re.S)
        assert doc, f'{src_path} has no module docstring'
        # ⚠ Scoped to the DOCSTRING, not the file: `MEASURES` legitimately holds
        # these values and a whole-file scan would fire on the one place they
        # belong.
        #
        # ⚠ And it fires on PROXIMITY TO A BASELINE, not on any dollar figure. An
        # allowlist of permitted literals is the brittle version — it would need
        # editing every time a legitimate per-scope illustration is added, and a
        # guard that has to be widened to keep working is one that eventually
        # gets widened past the defect. A per-agency figure (DDC's $27.4B against
        # $152.2B) is nowhere near a programme baseline; a restatement is, by
        # construction, within rounding of one. Both drifted values that occurred
        # were inside 0.1%.
        baselines = [m['baseline_total_usd'] / 1e9 for m in money.MEASURES]
        offenders = []
        for lit, num in re.findall(r'(\$(\d[\d,]*(?:\.\d+)?)\s*(?:B\b|billion))',
                                   doc.group(1)):
            val = float(num.replace(',', ''))
            if any(abs(val - b) <= 0.01 * b for b in baselines):
                offenders.append(lit)
        assert not offenders, (
            f'{os.path.basename(src_path)} restates a programme baseline in '
            f'prose: {sorted(set(offenders))} — MEASURES owns those figures')


def test_a_baseline_never_leaks_into_a_served_payload():
    """⚠ A scope with no data must serve None, never the citywide baseline.

    Defaulting an absent value to the documented total would render one scope's
    page carrying the whole programme's money, and it would look plausible.
    """
    p = money.payload()
    baselines = {m['baseline_total_usd'] for m in money.MEASURES}
    baselines |= {float(m['baseline_population']) for m in money.MEASURES}
    for served in p['measures']:
        assert served['value'] is None and served['population'] is None
        assert 'baseline_total_usd' not in served
        assert 'baseline_population' not in served
    partial = money.payload({'planned_usd': 12.5}, {'planned_usd': 3})
    for served in partial['measures']:
        for field in ('value', 'population'):
            v = served[field]
            assert v is None or float(v) not in baselines, (
                f"{served['key']}.{field} is a documented baseline, not a measurement")



# ── the endpoint ─────────────────────────────────────────────────────────────

def _router_src():
    with open(ROUTER, encoding='utf-8') as fh:
        return fh.read()


def test_the_endpoint_serves_populations_beside_the_values():
    src = _router_src()
    assert '_MONEY_COLUMNS' in src
    m = re.search(r'_MONEY_COLUMNS = \{(.*?)\}', src, re.S)
    assert m, '_MONEY_COLUMNS not found'
    for key in ('planned_usd', 'adopt_usd', 'allocate_usd',
                'committed_usd', 'spent_usd', 'checkbook_usd'):
        assert key in m.group(1), f'{key} must be served with its population'
    assert '_n"' in m.group(1), 'each value must be paired with a count column'


def test_the_endpoint_uses_the_shared_copy_rather_than_its_own():
    """One origin for the wording, or the page and the API will drift."""
    src = _router_src()
    assert 'capitalmoney.payload(' in src
    assert 'not stages of one pot' not in src, (
        'the note belongs in modules/capitalmoney, not inlined in the router')


def test_every_payload_carries_its_vintage():
    """⚠ A figure without its plan version and reporting period is the exact
    failure this section is being rebuilt to end."""
    src = _router_src()
    assert 'def _sources(' in src
    for fn in ('capital_overview', 'capital_scope_stats'):
        m = re.search(r'async def ' + fn + r'\(.*?\n(?=\n@router|\Z)', src, re.S)
        assert m, f'{fn} not found'
        assert '_sources(' in m.group(0), f'{fn} must serve its sources'


def test_coverage_is_stated_not_implied():
    """An absent schedule is 'NYC publishes none', not 'there is none'."""
    src = _router_src()
    assert 'without_published_schedule' in src
    assert 'without_published_location' in src
