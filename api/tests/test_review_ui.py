"""Guards for the review UI — the Laravel half of Phase 1.

⚠ Source guards. The app is PHP and cannot be exercised from pytest, so these
pin the properties that are cheap to break and expensive to notice: the origin
gate, the forwarded actor, and the queue's own verbs.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
CTRL = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Review.php')
VIEWS = os.path.join(ROOT, 'app', 'resources', 'views', 'review')
NGINX = os.path.join(ROOT, 'nginx', 'conf.d')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _block(conf_text, location):
    """The body of one `location <path> { ... }` block."""
    i = conf_text.find('location ' + location)
    if i < 0:
        return None
    depth, out, started = 0, [], False
    for ch in conf_text[i:]:
        out.append(ch)
        if ch == '{':
            depth += 1
            started = True
        elif ch == '}':
            depth -= 1
            if started and depth == 0:
                break
    return ''.join(out)


def test_review_is_behind_basic_auth_on_BOTH_ports():
    """⚠⚠ THE GATE IS WHAT MAKES SERVING CANDIDATES SAFE AT ALL, and it must be
    on every server that serves the app.

    Found while placing it: `/admin/` is gated in ssl.conf and NOT in app.conf,
    which serves the same Laravel app on port 80. That is a pre-existing gap,
    reported separately rather than silently widened — this asserts the review
    app does not repeat it.
    """
    for conf in ('ssl.conf', 'app.conf'):
        text = _read(os.path.join(NGINX, conf))
        block = _block(text, '/review/')
        assert block, f'/review/ has no location block in {conf}'
        assert 'auth_basic' in block, f'/review/ is not behind basic auth in {conf}'
        assert 'auth_basic_user_file' in block, f'no htpasswd for /review/ in {conf}'
        assert 'limit_req' in block, f'/review/ has no rate limit in {conf}'


def test_the_controller_sends_the_actor_it_does_not_only_display_it():
    """⚠⚠ THE ONE LINE THAT MAKES ATTRIBUTION TRUE RATHER THAN ASPIRATIONAL.

    The app calls the API server-to-server with ONE service token, so without
    forwarding, `require_editor` resolves to that token's user and two reviewers
    are recorded as the same string — permanently. `/admin/orgs` accepts exactly
    that and says so in its own comment ("only the label on screen"); this must
    not.
    """
    src = _read(CTRL)
    decide = src[src.index('function decide'):src.index('private function nextUndecided')]
    assert "'actor'" in decide and 'actor($request)' in decide, (
        'the decide handler no longer forwards the reviewer; decisions would be '
        "attributed to the API token's user instead of the person")


def test_the_actor_never_comes_from_the_browser():
    """⚠ It must come from the server var nginx sets from the VERIFIED
    credential. A form field would let one reviewer claim to be the other."""
    src = _read(CTRL)
    actor = src[src.index('private function actor'):]
    assert 'PHP_AUTH_USER' in actor, 'the actor is no longer read from the auth gate'
    for forgeable in ("input('actor')", 'input("actor")', "request->get('actor')"):
        assert forgeable not in src, (
            f'the actor is read from browser input ({forgeable}) — attribution '
            'would be forgeable and the audit trail decorative')


def test_the_item_view_offers_only_the_verbs_the_queue_accepts():
    """⚠ `dismiss` exists for untrusted public submissions and must never appear
    on a generator queue. The view must gate every button on the served list,
    never hardcode the set."""
    src = _read(os.path.join(VIEWS, 'item.blade.php'))
    for verb in ('accept', 'amend', 'reject', 'dismiss'):
        assert f"'{verb}', $verbs" in src or f'$canAmend' in src, \
            f'the {verb} button is not gated on the queue\'s verbs'
    assert "in_array('dismiss', $verbs, true)" in src, (
        'the dismiss button is not gated on the queue verbs — it would appear '
        'on generator queues, where spam is not a thing that can happen')


def test_the_views_distinguish_a_seed_decision_from_a_pending_one():
    """⚠⚠ Two different settled states. "The project published this" and "I
    answered this a minute ago" must not look the same to a reviewer."""
    for name in ('queue.blade.php', 'item.blade.php'):
        src = _read(os.path.join(VIEWS, name))
        assert 'in_seed' in src, f'{name} ignores in_seed'
        assert "decision" in src, f'{name} ignores a pending decision'


def test_no_blade_directive_is_glued_to_a_word_character():
    """⚠ This repo's documented Blade trap: `chart@if (...)` is NOT compiled and
    only its @endif is, which 500s the page while `php -l` passes. Every
    conditional phrase must be precomputed in @php."""
    bad = []
    for name in os.listdir(VIEWS):
        if not name.endswith('.blade.php'):
            continue
        for m in re.finditer(r'\w@(if|else|endif|foreach|endforeach|php)\b',
                             _read(os.path.join(VIEWS, name))):
            bad.append(f'{name}: {m.group(0)!r}')
    assert not bad, f'Blade directives glued to a word character: {bad}'


def test_the_kind_vocabulary_is_served_never_typed_into_the_view():
    """⚠⚠ I TYPED IT INTO THE TEMPLATE AND GOT IT WRONG. The classifier's enum
    has NINE kinds; the hardcoded list had six, omitting `labor_code` (22 real
    candidates), `agency` (15) and `unclear` — so a reviewer could not amend a
    candidate to two kinds that genuinely occur.

    That is the licence-capability defect precisely: a label map copied into a
    view, stale there, with nobody looking. The vocabulary now has ONE owner
    (`build_program_name_candidates.KINDS`), which the JSON enum, the model's
    prompt and this view all read from.
    """
    src = _read(os.path.join(VIEWS, 'item.blade.php'))
    assert '@foreach ($kinds as $k)' in src, \
        'the kind list is no longer the served one'
    for typed in ("'program', 'system'", '"program", "system"'):
        assert typed not in src, (
            f'a kind vocabulary is typed into the view again ({typed}) — it will '
            'go stale the moment the classifier gains a kind')


def test_matched_titles_link_to_the_contract_and_ambiguity_stays_unlinked():
    """⚠ `contracts` is one row per AMENDMENT, each with its own ctr_id, so a
    repeated title has several. Linking an arbitrary one sends the reviewer to a
    contract the evidence did not mean — the DOS-crosswalk rule, where an
    ambiguous name stays unlinked rather than resolving to a guess."""
    src = _read(os.path.join(VIEWS, 'item.blade.php'))
    assert '/procurement/contract/' not in src, (
        'the contract URL is built in the view; it must come from the API, '
        'which is what knows whether the title resolved unambiguously')
    # ⚠ Anchored on the PROPERTY, not the markup: this guard first pinned the
    # old list layout and broke the moment the same property moved into a table.
    assert "!empty($r['href'])" in src, \
        'the link is no longer conditional on the title having resolved'
    assert '@else' in src, \
        'a title without a resolved link no longer falls back to plain text'

    # ⚠ Whitespace-normalised. Two earlier versions of this guard broke on SQL
    # realignment rather than on a real change — an anchor that brittle reports
    # a defect that is not there, which is the mirror of one that misses.
    mod = ' '.join(_read(
        os.path.join(ROOT, 'api', 'modules', 'reviewqueue.py')).split())
    assert 'count(DISTINCT ctr_id) AS n' in mod, (
        'the resolver no longer counts distinct contracts per title — an '
        'ambiguous title would link to an arbitrary amendment')
    assert 'if r["n"] != 1: continue' in mod, (
        'the resolver no longer SKIPS an ambiguous title')
    assert 'contract_title = ANY($1::text[])' in mod, (
        'title resolution is no longer one batched query; per-item lookups '
        'would be 132 round trips on the list page')


def test_the_records_table_columns_come_from_the_queue():
    """⚠ The view renders a table it does not define. A column list typed into
    the template is the licence-label defect at table scale — a second queue
    with different records would silently land its values under the wrong
    headings, or need a view change nobody would think to make."""
    src = _read(os.path.join(VIEWS, 'item.blade.php'))
    assert '@foreach ($cols as $c)' in src, 'the columns are no longer served'
    for typed in ('>Agency<', '>Amount<', '>Ends<'):
        assert typed not in src, (
            f'a column heading is typed into the view ({typed}); it must come '
            'from the queue')


def test_a_master_agreement_amount_is_labelled_a_ceiling():
    """⚠⚠ A CEILING IS NOT SPEND — #261/#294/#301, the same defect found three
    times. A master's figure is headroom agencies buy against, drawn down under
    other contract ids. In a column of amounts an unlabelled $45M ceiling reads
    as money spent, which is precisely how a vendor got flagged for
    'concentrated dependency' on money the City had never paid.

    Measured on the live preview: of ACCESS HRA's five matched contracts exactly
    one is a master, and only it carries the badge.
    """
    src = _read(os.path.join(VIEWS, 'item.blade.php'))
    assert 'is_ceiling' in src and 'ceiling' in src, \
        'the view no longer distinguishes a ceiling from spend'

    mod = _read(os.path.join(ROOT, 'api', 'modules', 'reviewqueue.py'))
    assert 'contractkind.is_master(' in mod, (
        'the ceiling test no longer uses contractkind — the leading-alpha-run '
        'rule lives there and a local reimplementation would misread MMA ids')
    assert 'import contractkind' in mod, 'contractkind is used but not imported'


def test_the_links_section_is_not_called_citations():
    """⚠ Owner's call, and the reason is substantive: most links a reviewer wants
    here are leads or context, so a heading asserting they are all citations
    misdescribes the section — and a store named `review_citation` holding
    non-citations would misdescribe its own contents. Renamed while unmerged;
    doing it after data accumulates is the #235 key-rename defect."""
    src = _read(os.path.join(VIEWS, 'item.blade.php'))
    assert 'Related links' in src, 'the section heading changed again'
    heading = src[src.index('db-eyebrow mb-1'):][:200]
    assert 'Citations' not in heading, 'the heading says Citations again'
    mod = _read(os.path.join(ROOT, 'api', 'modules', 'reviewqueue.py'))
    assert 'CREATE TABLE IF NOT EXISTS review_link' in mod, \
        'the table is no longer review_link'
    # ⚠ Scoped to the DDL, not the file: the module's own comment explains why
    # it is not called review_citation, and a whole-file scan fires on that
    # prose. Thirteenth own-prose firing in this repo; the rule is settled.
    assert 'CREATE TABLE IF NOT EXISTS review_citation' not in mod, \
        'the old citation table is back'


def test_a_link_can_be_flagged_as_a_source_from_the_ui():
    """⭐ The reviewer picks which links become Source clauses. Without a control
    the flag is unreachable and every link would have to be one, or none."""
    src = _read(os.path.join(VIEWS, 'item.blade.php'))
    assert "route('review.linksource'" in src, 'no control flags a link as a source'
    assert 'Use as source' in src and 'Unflag' in src, \
        'the flag is one-way — a reviewer could not undo it'
    assert 'source_clauses' not in src, (
        'the view computes the export itself; that contract belongs to the '
        'module so the export and the preview cannot disagree')


def _locations(conf_text):
    """Every `location` directive in one server block, as (kind, path).

    kind is 'exact' for `location = /x`, 'prefix' for `location /x`, and
    'regex' for `location ~ ...` / `~* ...`, which this does not try to model.
    """
    out = []
    for m in re.finditer(r'^\s*location\s+(=\s+|\^~\s+|~\*?\s+)?(\S+)\s*\{',
                         conf_text, re.M):
        mod, path = (m.group(1) or '').strip(), m.group(2)
        kind = 'exact' if mod == '=' else ('regex' if mod.startswith('~') else 'prefix')
        out.append((kind, path, m.start()))
    return out


def _matching_block(conf_text, uri):
    """The block nginx would use for `uri`, by exact-then-longest-prefix.

    ⚠ Deliberately does NOT model regex locations; the test asserts separately
    that none of them could claim a review URI, rather than pretending to
    implement nginx's full precedence.
    """
    locs = _locations(conf_text)
    for kind, path, pos in locs:
        if kind == 'exact' and path == uri:
            return conf_text[pos:pos + len(_block(conf_text[pos:], '= ' + path) or '')]
    best = None
    for kind, path, pos in locs:
        if kind == 'prefix' and uri.startswith(path):
            if best is None or len(path) > len(best[1]):
                best = (kind, path, pos)
    if not best:
        return None
    tail = conf_text[best[2]:]
    depth, out, started = 0, [], False
    for ch in tail:
        out.append(ch)
        if ch == '{':
            depth += 1
            started = True
        elif ch == '}':
            depth -= 1
            if started and depth == 0:
                break
    return ''.join(out).strip()


# ⚠⚠ EVERY PREFIX THE APP GATES, NOT JUST THE ONE THIS FILE WAS WRITTEN FOR.
# The route guard below was scoped to `/review` and its sibling's docstring
# recorded `/admin/` as "a pre-existing gap, reported separately rather than
# silently widened". That was the right call at the time and it is also how the
# gap survived: a guard that knows about one gated prefix cannot fail on the
# other. `http://databook.nyc/admin/orgs` served the real Org register page,
# unauthenticated, until 2026-09-03.
GATED_PREFIXES = ('/review', '/admin')


def _app_server_block(conf_text):
    """Just the `server { ... }` block that serves the Laravel app.

    ⚠⚠ WITHOUT THIS THE GUARD CANNOT BE RIGHT IN EITHER DIRECTION. `app.conf`
    defines three servers — the app, the api, and a staging api — and the api
    ones carry `location ~ ^/(\.well-known|register|authorize|token|admin)`.
    In nginx a REGEX location beats a prefix location, so scanning the file as
    one soup reports that regex as capturing `/admin/orgs` and the guard fails on
    a correct config. Weakening the regex assertion to make it pass would have
    been worse: a regex on the APP server really would override the new
    `location /admin/` gate, silently, and that is precisely the failure worth
    catching.

    Identified by server_name rather than by order, so inserting a server block
    cannot shift which one is checked.
    """
    out = []
    for m in re.finditer(r'\bserver\s*\{', conf_text):
        i = m.end() - 1
        depth, j = 0, i
        while j < len(conf_text):
            if conf_text[j] == '{':
                depth += 1
            elif conf_text[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        body = conf_text[i:j + 1]
        names = re.search(r'server_name\s+([^;]+);', body)
        if not names:
            continue
        hosts = names.group(1).split()
        if any(h in ('databook.nyc', 'www.databook.nyc') for h in hosts):
            out.append(body)
    return '\n'.join(out)


def _gated_route_uris():
    """A concrete URI for every route Laravel declares under a gated prefix.

    Read from `routes/web.php` rather than hardcoded, so a route added later is
    covered without anyone remembering to extend this list.
    """
    web = _read(os.path.join(ROOT, 'app', 'routes', 'web.php'))
    uris = set()
    for pre in GATED_PREFIXES:
        for m in re.finditer(
                r"Route::(?:get|post|patch|put|delete)\(\s*'(" + re.escape(pre) + r"[^']*)'", web):
            # substitute any {placeholder} with something a route would accept
            uris.add(re.sub(r'\{[^}]+\}', 'x', m.group(1)))
    return sorted(uris)


def _review_route_uris():
    return [u for u in _gated_route_uris() if u.startswith('/review')]


def test_every_review_uri_laravel_serves_is_behind_the_gate():
    """⚠⚠ `location /review/` IS A PREFIX MATCH AND DOES NOT MATCH `/review`.

    Measured with a throwaway nginx before this guard existed:

        /review               -> 200   (fell through to `location /`, no auth)
        /review/              -> 401
        /review/glossary      -> 401
        /review/program-names -> 401

    And `Route::get('/review')` is a real route — the queue index, which calls
    the API with the service token and therefore renders. So the bare URI
    reached PHP unauthenticated while the gate, the guard above it, and the
    nginx comment claiming "stops an unauthenticated request reaching PHP at
    all" all read as correct.

    The property is therefore not "a `/review/` block exists" but "every URI
    Laravel routes is covered by a gated block", which is what this asserts,
    per conf and per route.
    """
    uris = _gated_route_uris()
    assert len(uris) >= 3, (
        f'only found {uris} in routes/web.php — the scanner is wrong, and a '
        'guard that checks nothing passes')
    assert '/review' in uris, 'the bare /review route vanished; re-check this guard'
    assert any(u.startswith('/admin') for u in uris), (
        'no /admin route was found — this guard covers /admin precisely because '
        'its gate was missing from app.conf while ssl.conf had it')
    for conf in ('ssl.conf', 'app.conf'):
        # ⚠ Only the server that serves the app — see _app_server_block.
        text = _app_server_block(_read(os.path.join(NGINX, conf)))
        assert text, 'no databook.nyc server block found in %s' % conf
        for kind, path, _ in _locations(text):
            if kind == 'regex':
                assert not any(re.search(path.lstrip('~ '), u) for u in uris), (
                    f'a regex location in {conf} could claim a review URI; this '
                    'guard does not model regex precedence')
        for uri in uris:
            block = _matching_block(text, uri)
            assert block, f'no location in {conf} matches {uri}'
            assert 'auth_basic_user_file' in block, (
                f'{uri} is served UNAUTHENTICATED in {conf} — it matches '
                f'{block.splitlines()[0].strip()!r}, which has no basic auth')
            assert 'limit_req' in block, f'{uri} has no rate limit in {conf}'


def _auth_file(block):
    """The htpasswd path an nginx location block authenticates against."""
    m = re.search(r'auth_basic_user_file\s+(\S+?);', block or '')
    return m.group(1) if m else None


def test_review_and_admin_authenticate_against_DIFFERENT_htpasswd_files():
    """⚠⚠ ONE FILE FOR BOTH GATES MEANT ONE PASSWORD FOR TWO POWERS.

    `/review/` and `/admin/` both named `/etc/letsencrypt/admin.htpasswd`, so
    adding a reviewer so they could judge program names ALSO handed them
    `/admin/orgs` — write access to the org register that 3,700 org match rows
    and every ingested `wegov-org-id` resolve through, including a rename of
    `wegov_orgs.name`, which is a join key.

    Measured 2026-08-31 before the split: that file held exactly ONE entry,
    `databook`, so there was no per-person attribution either — every decision
    would have been recorded as the same string, permanently, in an audit trail
    built specifically to prevent that.

    "May judge a program name" and "may rename an agency" are different
    permissions. This asserts they stay different FILES, which is the crude
    first instalment of the role model in docs/REVIEW-APP-SCOPE.md §6.6.
    """
    seen = {}
    for conf in ('ssl.conf', 'app.conf'):
        text = _read(os.path.join(NGINX, conf))
        for uri in _review_route_uris():
            f = _auth_file(_matching_block(text, uri))
            assert f, f'{uri} has no auth_basic_user_file in {conf}'
            seen[(conf, uri)] = f
        admin = _block(text, '/admin/')
        if admin:                       # app.conf has no /admin/ block (port 80)
            admin_file = _auth_file(admin)
            assert admin_file, f'/admin/ has no auth_basic_user_file in {conf}'
            for (c, uri), f in seen.items():
                if c != conf:
                    continue
                assert f != admin_file, (
                    f'{uri} and /admin/ in {conf} both authenticate against '
                    f'{f} — a reviewer credential would also open the org '
                    'register')

    files = set(seen.values())
    assert len(files) == 1, (
        f'the review URIs disagree about their htpasswd: {sorted(files)}; one '
        'gate stricter than another is a gap, not defence in depth')
    assert 'review' in next(iter(files)), (
        f'review authenticates against {next(iter(files))}, which is not a '
        'review-specific file')


def test_the_research_path_carries_a_GLOBAL_rate_limit_not_only_a_per_IP_one():
    """⚠⚠ THE WHOLE SITE WENT TO 504 BECAUSE PER-IP LIMITING CANNOT SEE THIS.

    /research/digital-reform/contracts renders in 11-17s (measured on the api
    itself, not through the app). A distributed crawler — 676 distinct IPs,
    1,164 requests in 5 minutes, ~1.7 EACH — exhausted every php-fpm worker, so
    nginx could not even connect to the upstream and EVERY page 504'd, including
    the home page. Measured: 18,947 504s in one hour, in bursts since 28 August,
    and nothing alerted because the api was healthy throughout.

    A `zone=pages` per-IP limit is invisible to 1.7 requests per address. The
    cap that works is keyed on a CONSTANT, so every client shares one bucket and
    the total number of concurrent renders is bounded regardless of how many
    addresses ask.

    ⚠ This WAS a stopgap over a cost problem, and the guard said so: the fix is
    that one page costing 11-17s. ⭐ IT HAS BEEN MADE CHEAP — re-measured on prod
    2026-09-19, past nginx, with genuinely novel parameter combinations: **0.63
    to 0.71s**, about 20x cheaper. So the cap moved 1r/s -> 5r/s on exactly the
    precondition this docstring named, not in spite of it.

    ⚠⚠ AND THE OLD CAP WAS REJECTING READERS. Measured 66,134 x 429 in 24 hours,
    1,849 in one 30-minute window across 1,855 DISTINCT IPs. One global bucket at
    1r/s means a real reader is rejected whenever the crawler took that second's
    token — reported as "frequent and sporadic 429s", which is exactly what a
    shared bucket feels like from the outside.

    ⚠ The KEY is still a constant and must stay one; only the RATE moved.
    """
    sec = _read(os.path.join(NGINX, 'security.conf'))
    m = re.search(r'limit_req_zone\s+(\S+)\s+zone=research_total:', sec)
    assert m, ('the global research zone is gone; /research/ is back to per-IP '
               'limiting only, which provably cannot see this crawler')
    rate = re.search(r'zone=research_total:\d+m\s+rate=(\d+)r/s', sec)
    assert rate, 'the research_total zone declares no rate'
    # ⚠ The arithmetic, not a taste — redone 2026-09-19 against a re-measured
    # 0.7s novel render and pm.max_children = 15:
    #      5r/s x 0.7s = 3.5 workers  (23% of the pool)
    #     10r/s x 0.7s = 7.0 workers  (47%)
    # The ceiling is 5, which leaves a LARGER relative margin than 1r/s ever had
    # at 8-12s. ⚠ Raising it again means re-measuring the page first: this
    # number is downstream of that cost, and the cost has moved twice.
    assert int(rate.group(1)) <= 5, (
        f'research_total allows {rate.group(1)}r/s; at ~0.7s per novel render '
        'and pm.max_children = 15 that is over a third of the worker pool — '
        're-measure the page before raising this')
    assert m.group(1) != '$binary_remote_addr', (
        'research_total is keyed on the client address, which makes it a '
        'per-IP limit again — the exact thing that did not work')

    for conf in ('ssl.conf', 'app.conf'):
        block = _block(_read(os.path.join(NGINX, conf)), '/research/')
        assert block, f'/research/ has no location block in {conf}'
        assert 'zone=research_total' in block, (
            f'/research/ in {conf} has no global cap, so one server block can '
            'still starve the worker pool')
