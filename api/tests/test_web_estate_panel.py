"""The "Observed running on the public web" panel on licence family pages.

⚠⚠ THIS PANEL PUBLISHES A THIRD PARTY'S INFERENCE ON A PAGE WHOSE ENTIRE CLAIM ON
A READER IS THAT IT MEASURES. Every guard here is about keeping that distinction
visible, because the failure mode is not a crash — it is a sentence that reads as
a procurement fact.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SERVICE = os.path.join(ROOT, 'app/app/Services/WebEstateService.php')
PANEL = os.path.join(ROOT, 'app/resources/views/procurement/partials/web-estate-panel.blade.php')
FAMILY = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php')
CTRL = os.path.join(ROOT, 'app/app/Http/Controllers/ProcurementController.php')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _prose(src):
    """Rendered copy only — Blade comments and @php blocks stripped.

    ⚠ Eleven guards in this repo have fired on their own explanation. The
    comments here quote the very words the wording rules ban, so a prose scan
    must not see them.
    """
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
    return re.sub(r'@php.*?@endphp', '', src, flags=re.S)


def _php_code(src):
    """PHP source with docblocks and comments removed, for the same reason
    `_prose` exists: the comments here quote the identifiers the rules ban."""
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'//[^\n]*', '', src)


def test_the_feed_is_fetched_server_side_never_from_the_browser():
    """⚠ A browser fetch would need the page CSP widened, put the reader on a
    third origin, and turn an outage at their end into a console error on a
    public page. It is read in PHP and cached."""
    svc = _read(SERVICE)
    assert 'file_get_contents' in svc, 'the feed is no longer fetched server-side'
    assert 'Cache::remember' in svc, 'the feed is no longer cached'
    assert '3600' in svc, "the TTL no longer matches the feed's own max-age"
    for f in (PANEL, FAMILY):
        body = _read(f)
        assert 'nyc-web-estate.pages.dev/observed.json' not in body, (
            'the view fetches the feed directly; it must come from the service')


def test_every_failure_path_returns_null_and_never_an_empty_result():
    """⚠⚠ "THEIR JSON IS BROKEN" AND "NOTHING WAS OBSERVED" MUST NOT BE THE SAME
    VALUE. Returning [] on a parse failure would render the not-observed card —
    publishing "no evidence of it running" on the strength of a network blip.
    That is this codebase's oldest defect: a count of zero that cannot be
    distinguished from a check that never ran."""
    svc = _read(SERVICE)
    body = svc[svc.index('public function feed'):svc.index('public function forSlug')]
    assert body.count('return null;') >= 3, (
        'a failure path no longer returns null — check unreachable, unparseable '
        'and thrown')
    assert 'return [];' not in body, (
        'a failure path returns an empty array, which the view cannot tell from '
        '"nothing observed"')
    assert 'Log::warning' in body, 'failures are no longer logged'


def test_the_panel_says_observed_and_never_claims_use():
    """⚠⚠ "Observed", NEVER "uses" or "runs on". A response header means the
    server named itself; a tag means a resource was referenced. Both are strong
    evidence and neither is "this agency uses this product"."""
    copy = _prose(_read(PANEL))
    assert 'Observed running on the public web' in copy, 'the heading changed'
    for banned in (' uses this', ' runs on ', 'is using', 'confirmed in use'):
        # "not confirmed in use" is the disclaimer and is allowed; the bare claim is not
        if banned == 'confirmed in use':
            assert 'not confirmed in use' in copy or banned not in copy, (
                'the panel claims confirmed use')
            continue
        assert banned not in copy.lower(), (
            'the panel claims use rather than observation: %r' % banned)


def test_absence_from_the_scan_is_stated_not_implied():
    """⚠⚠ A SHORT LIST READS AS A FINDING ABOUT THE CITY RATHER THAN ABOUT THE
    SCAN. 49 of the 243 hosts do not answer a public request at all and 33 refuse
    automated ones, so absence is not evidence of non-use — and the page has to
    say so, in the same panel, not in a methodology note elsewhere."""
    copy = _prose(_read(PANEL))
    assert 'not evidence' in copy, 'the panel no longer says absence is not evidence'
    assert '243' in copy, 'the panel no longer states the scan population'
    assert 'independent' in copy, 'the panel no longer names this as an outside audit'


def test_components_are_named_because_family_grain_is_coarser():
    """⚠⚠ FOUR MICROSOFT COMPONENTS MAP TO OUR ONE `microsoft` FAMILY (Azure,
    Entra, IIS, Power BI — 62 observations). That family carries every Microsoft
    product the City buys, $643.6M, so a panel that shows only the family name
    reads as "Microsoft's $643.6M is observed on these 62 hosts". Naming each
    component is what keeps the grain visible."""
    panel = _read(PANEL)
    assert "$c['name']" in panel, 'the panel no longer names each component'
    svc = _read(SERVICE)
    assert "'name'  => $name" in svc, 'the service no longer carries component names'


def test_the_finding_class_is_never_rendered():
    """⚠ `finding_class` is THEIR taxonomy, and class B means "no purchase record
    found" — a judgement about OUR data that this very page is the evidence for.
    The page can speak for itself."""
    # ⚠ TWELFTH OWN-PROSE GUARD FAILURE IN THIS REPO, caught on first run: both
    # files carry a comment saying finding_class is deliberately NOT rendered, so
    # a raw scan finds the string in the explanation of why it must be absent.
    assert 'finding_class' not in _prose(_read(PANEL)), (
        "the panel renders finding_class, which is a claim about our own data")
    assert 'finding_class' not in _php_code(_read(SERVICE)), (
        "the service carries finding_class into the view")


def test_the_observation_list_counts_before_it_caps():
    """⚠ Microsoft IIS alone carries 54 observations. A capped list presented as
    complete is a defect this repo has shipped more than once."""
    svc = _read(SERVICE)
    assert "'total' => count($obs)" in svc, 'the true total is no longer computed'
    assert 'array_slice' in svc, 'the list is no longer capped'
    panel = _read(PANEL)
    assert "$c['total'] > count($c['observations'])" in panel, (
        'the cap disclosure is not gated on actually capping')


def test_the_controller_passes_the_panel_and_the_view_includes_it():
    """⚠ The API having a value proves nothing about the page receiving it — the
    Overview rebuild shipped a whole missing section that way, because the
    controller names each view-data key."""
    assert "'webEstate'" in _read(CTRL), 'the controller no longer passes webEstate'
    assert "@include('procurement.partials.web-estate-panel')" in _read(FAMILY), (
        'the family page no longer includes the panel')
