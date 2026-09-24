"""A heading tag names a LEVEL, not a font size — across the capital section.

⚠⚠ MEASURED ON THE RENDERED PAGES BEFORE ANY CHANGE, and scoped to
`.inner_container`, because the shared footer contributes five `<h6>`s to every
page and reading them as page structure is what made my first battery report
"5 headings below h2" on the very page whose redesign had removed its deep
headings. Inside the page container:

  * SEVEN pages titled themselves with `<h2>` and carried NO `<h1>` at all
  * TWO of those had an `<h1>` anyway — the word "Projects", MID-document, below
    the `<h2>` naming the page, so the outline claimed the page was called
    "Projects" while its real subject was a sub-heading of it
  * NINE headings announced a bare NUMBER (`<h2 class="prj_stat">`), so a reader
    navigating by heading hears "heading level 2: 447"

⭐ THE FIX ADOPTED CONVENTIONS THE SECTION ALREADY HAD rather than inventing
sizes: `.db-profile-title` pins `--db-text-2xl`, exactly what an `<h2>` renders
at, and `.db-stat-value` pins the same 30px bold in `--db-primary` plus
tabular-nums. Rendered heights moved by at most 29px on ten pages.

⚠⚠ AND THE CHANGE WOKE A DORMANT CSS RULE, WHICH IS RECORDED IN THE STYLESHEET
RATHER THAN HERE: `style.css`'s `.organization_data h1` matched nothing while
these pages had no `<h1>`, and five titles then rendered 32px against the
profile's 30px. It is NOT fossil — live on nine unrelated pages — so the class
was qualified instead. Qualifying it then out-specified the mobile media query
and took the profile's 390px title from 24px to 30px; both selectors now carry
equal specificity. `test_design_token_parity` and the palette ratchet are
unaffected: no token moved and no colour literal was added.
"""
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.realpath(os.path.join(HERE, '..', '..'))
VIEWS = os.path.join(ROOT, 'app', 'resources', 'views')
CSS = os.path.join(ROOT, 'app', 'public', 'css', 'databook-components.css')

# The capital pages that are their OWN page — each must carry exactly one <h1>.
# ⚠ `orgprojectsection` and `distprojectsection` are deliberately ABSENT: they
# render inside a shell whose `sub.orgheader` already emits the page's `<h1>`,
# and adding one there would reintroduce the two-`<h1>` defect the profile
# redesign removed.
# ⚠⚠ DERIVED FROM THE CONTROLLER, NOT TYPED — a hand-kept list is why
# `/projects/commitments` shipped with NO `<h1>` anywhere on the page while its
# title rendered at the same 30px as every sibling. The list had ten views and
# `prjCommitmentsA` was not one of them, so the guard passed on a page it could
# not see. Same failure as the date rule's two site-named guards, which missed
# `prjCommitmentsA` too — the same view, twice, for the same reason.
#
# ⚠ `mProject`/`mProjects` (the minor-projects pages) are EXCLUDED by name: they
# are outside the rebuilt section and were never measured by the design pass,
# and asserting over them would fail the build for a pre-existing condition.
# Named here with that reason rather than silently skipped, so a later reader
# can tell "measured and left" from "not looked at".
_NOT_IN_THE_REBUILT_SECTION = ('mProject', 'mProjects')


def _page_views():
    """Every view the capital controller renders, read out of it."""
    # ⚠ Reads the file directly rather than via `_read`, which is defined
    # BELOW this point — calling it here is a NameError at import time.
    with open(os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers',
                           'Projects.php'), encoding='utf-8') as fh:
        src = fh.read()
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'(?m)^\s*//.*$', '', src)
    names = sorted({n for n in re.findall(r"view\('([A-Za-z0-9_]+)'", src)
                    if n not in _NOT_IN_THE_REBUILT_SECTION})
    names = [n for n in names
             if os.path.exists(os.path.join(VIEWS, n + '.blade.php'))]
    assert len(names) >= 9, (
        'only %d capital page views resolved from Projects.php — the scan '
        'would be nearly vacuous' % len(names))
    assert 'prjCommitmentsA' in names, (
        'the commitments view is no longer reached from Projects.php, so the '
        'scan that caught its missing <h1> would be silently narrower')
    return tuple(names)


PAGE_VIEWS = _page_views() + ('capitalproject',)


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _blade_code(src):
    """Blade with comments stripped.

    ⚠ Every view touched here now carries a comment explaining the heading
    change, and those comments quote `<h1>`, `<h2>` and `db-profile-title` —
    which is own-prose firing territory in a brand-new organ.
    """
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'^[ \t]*//.*$', '', src, flags=re.M)


def test_every_capital_page_title_is_the_same_size_as_its_siblings():
    """An `<h1>` with no class is a font size, and it was 36px on one page.

    ⚠ The sibling guard counts `<h1>` elements and says nothing about how one
    RENDERS, which is exactly the gap `/projects/about` sat in: it declared one
    correct `<h1>` and, carrying no class, took the browser default **36px at
    BOTH 1440 and 390** — the only capital page that never shrinks on a phone,
    beside nine siblings at 30px/24px. Measured on the rendered pages, then
    fixed by giving it `.db-profile-title` (owner decision 2026-09-12).

    ⭐ The class is what pins BOTH sizes: `h1.db-profile-title` is 30px and the
    media query takes it to 24px. So asserting the class is asserting the pair,
    and it cannot drift the way a typed pixel value would.
    """
    checked = 0
    for view in PAGE_VIEWS:
        src = _blade_code(_read(os.path.join(VIEWS, view + '.blade.php')))
        tag = re.search(r'<h1[^>]*>', src)
        assert tag, '%s declares no <h1>' % view
        checked += 1
        assert 'db-profile-title' in tag.group(0), (
            '%s titles itself %s — with no `db-profile-title` it renders the '
            'browser default 36px at every width, against 30px/24px on every '
            'sibling. That is the state /projects/about shipped in.'
            % (view, tag.group(0)))
    assert checked >= 10, 'only %d capital page titles checked' % checked


def test_every_capital_page_declares_exactly_one_h1():
    checked = 0
    for view in PAGE_VIEWS:
        path = os.path.join(VIEWS, view + '.blade.php')
        assert os.path.exists(path), 'a named capital page view is gone: %s' % view
        src = _blade_code(_read(path))
        n = len(re.findall(r'<h1[\s>]', src))
        checked += 1
        assert n == 1, (
            '%s declares %d <h1> elements; a page has exactly one, and it is '
            'the page\'s own name — two of these views used to spend theirs on '
            'the word "Projects" mid-document' % (view, n))
    assert checked == len(PAGE_VIEWS), 'the scan did not read every page view'


def test_the_h1_is_the_first_heading_in_each_capital_page():
    """⚠ THE HALF THAT CATCHES THE REAL DEFECT. Counting one `<h1>` is not
    enough: `categoryA` and `budgetLineA` each had exactly one, and it sat
    BELOW the `<h2>` that named the page. The outline is about ORDER."""
    for view in PAGE_VIEWS:
        src = _blade_code(_read(os.path.join(VIEWS, view + '.blade.php')))
        heads = [(m.start(), m.group(1)) for m in re.finditer(r'<(h[1-6])[\s>]', src)]
        if not heads:
            continue
        first = heads[0][1]
        assert first == 'h1', (
            "%s opens its headings with <%s>; the page's own name must come "
            'first, or a reader navigating by heading is told the page is '
            'called whatever the first heading says' % (view, first))


def test_no_capital_stat_value_is_a_heading():
    """A number is not a heading. ⚠ And the `prj_stat` DATA HOOK is preserved —
    `loadFinStat` writes into it, so the class and every id stay; only the tag
    changed, to the `.db-stat-value` the section's own `<x-db.stat>` uses."""
    # ⚠ WALKED, not `listdir`. The top level holds 56 views and the rest live in
    # subdirectories (`sub/`, `components/db/`, `procurement/partials/`) — a
    # `prj_stat` heading in a PARTIAL is exactly the one a flat scan would miss,
    # and my floor of 80 fired on the flat version rather than hiding it.
    bad, scanned = [], 0
    for dirpath, _dirs, files in os.walk(VIEWS):
        for name in sorted(files):
            if not name.endswith('.blade.php'):
                continue
            src = _blade_code(_read(os.path.join(dirpath, name)))
            scanned += 1
            rel = os.path.relpath(os.path.join(dirpath, name), VIEWS)
            for m in re.finditer(r'<(h[1-6])[^>]*\bclass="[^"]*prj_stat', src):
                bad.append('%s: <%s class="… prj_stat">' % (rel, m.group(1)))
    assert scanned > 80, (
        'this guard scanned only %d views, so it is the zero-files scanner '
        'again' % scanned)
    # ⚠⚠ SCOPED TO THE CAPITAL SECTION, AND THE EXCLUSION IS A MEASUREMENT, NOT
    # A CONVENIENCE. Walking every view finds the same pattern on exactly ONE
    # page outside this section — `schools.blade.php`, 6 instances — and nothing
    # else. Fixing it would restyle a page this work never measured, on a
    # section nobody asked about; asserting over it would fail the build for a
    # pre-existing condition. So it is named here with its count, which is how a
    # later reader can tell "measured and left" from "not looked at".
    OUT_OF_SCOPE = {'schools.blade.php': 6}
    residual = {}
    inside = []
    for entry in bad:
        rel = entry.split(':')[0]
        if rel in OUT_OF_SCOPE:
            residual[rel] = residual.get(rel, 0) + 1
        else:
            inside.append(entry)
    assert not inside, (
        'a capital stat tile announces its number as a heading: %s' % inside[:5])
    for rel, n in OUT_OF_SCOPE.items():
        assert residual.get(rel, 0) == n, (
            '%s now has %d number-as-heading tiles, not the %d measured when '
            'this was scoped out — either it was fixed (drop the entry) or it '
            'grew (the pattern is spreading)' % (rel, residual.get(rel, 0), n))


def test_the_profile_title_class_outranks_the_legacy_descendant_rule():
    """⚠⚠ BOTH SELECTORS MUST BE QUALIFIED, AND THE MOBILE ONE IS THE ONE THAT
    BREAKS SILENTLY. `style.css`'s `.organization_data h1` is (0,1,1); a bare
    `.db-profile-title` is (0,1,0) and loses despite loading later. Qualifying
    only the base rule then out-specifies the mobile media query, which took the
    profile's 390px title from 24px to 30px with nothing failing — measured by
    reverting the one line, not reasoned about.
    """
    css = re.sub(r'/\*.*?\*/', '', _read(CSS), flags=re.S)
    # ⚠ The mobile rule sits INSIDE a media query, so a flat
    # `selector { … }` pattern cannot see it and this guard reported one rule
    # where there are two. Find each SIZE declaration for the class and read the
    # selector text immediately before it instead.
    title_rules = []
    for m in re.finditer(r'([^{};]*db-profile-title[^{};]*)\{([^}]*)\}', css):
        if '--db-text-' in m.group(2):
            title_rules.append(m.group(1))
    assert len(title_rules) >= 2, (
        'expected a base and a mobile rule for the profile title, found %d'
        % len(title_rules))
    for rule in title_rules:
        assert 'h1.db-profile-title' in rule, (
            'a `.db-profile-title` size rule is not qualified with `h1.`, so it '
            'either loses to `.organization_data h1` or out-specifies its own '
            'mobile override: %s' % ' '.join(rule.split())[:80])


# ============ a heading stranded in a centred row it ended up alone in (2026-09-10)

def test_the_projects_heading_column_follows_whether_its_sibling_renders():
    """⚠⚠ GATING A BLOCK CAN MOVE THE THING NEXT TO IT, not just remove it.

    Reported by the owner: on `/projects/budget-lines/{code}` and
    `/projects/categories/{slug}` the "Projects" heading rendered **327px** and
    **268px** from the left while every other heading on those pages sat at 35.

    It was a fixed `col-md-7` / `col-md-8` paired with the publication-date
    control's `col-md-5` / `col-md-4` — a balanced 12 in a
    `justify-content-center` row. Gating that control off for the spine contract
    (invariant 10; it is a retired-series artifact) left the heading column
    ALONE in a row that centres its children, so bootstrap centred it. Nothing
    about the heading changed, and nothing failed.

    ⚠ `pubdate_filter` is set only by `OrgsDatasets`, so on these two pages the
    control never renders today and a bare `col-md-12` would be correct. The
    width stays CONDITIONAL so the pair cannot silently unbalance again if a
    contract ever sets it — and this guard pins that, not the literal 12.

    ⭐ The rendered half is `scripts/headless/verify_heading_alignment.py`, which
    finds any heading in a column narrower than its row, alone in a row that
    centres. A blanket "every heading shares a left edge" rule would fail on
    correct pages — the project profile puts its TOC beside the content.
    """
    for name in ('budgetLineA.blade.php', 'categoryA.blade.php'):
        view = _read(os.path.join(VIEWS, name))
        view = re.sub(r'\{\{--.*?--\}\}', '', view, flags=re.S)
        i = view.index('<h2>Projects</h2>')
        # the column this heading sits in
        open_tag = view.rindex('<div class="', 0, i)
        cls = view[open_tag:view.index('>', open_tag)]
        assert 'organization_data' in cls, (
            '%s: the Projects heading is no longer in the column this guards' % name)
        assert 'pubdate_filter' in cls, (
            "%s: the heading column's width is fixed again, so gating the "
            "publication-date control beside it leaves it alone in a centred "
            "row and the heading drifts off the page's left edge: %r"
            % (name, cls))
        assert "'12'" in cls or '"12"' in cls, (
            '%s: the no-sibling case is not full width, so the heading is still '
            'centred when the control is absent: %r' % (name, cls))
