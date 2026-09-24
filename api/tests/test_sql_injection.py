"""Request values reach SQL as bound parameters, never as SQL text.

⚠⚠ Two of these were LIVE on prod. On 2026-09-24 a scanner sent
`/procurement/agencies?q=' ORDER BY 1000-- -` and Postgres answered "ORDER BY
position 1000 is not in select list" (Sentry DATABOOK-API-3E): the quote had
closed the LIKE literal and the rest ran as SQL. 3C/3D are the UNION probes
that followed. Nothing errors when this is broken for an innocent search, so
the only proof is what the query TEXT contains.
"""

import asyncio

import pytest

from routers import oce

PAYLOAD = "' UNION ALL SELECT NULL,NULL,NULL-- x"


class _Recorder:
    def __init__(self):
        self.calls = []

    async def select_safe(self, sql, dd=[]):
        self.calls.append((sql, list(dd)))
        return []


@pytest.fixture
def db(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(oce, "PostgresModelAsync", rec)

    async def passthrough(_db, rows, *a, **k):
        return rows
    monkeypatch.setattr(oce.agencyalias, "group_by_org", passthrough)
    return rec


def test_the_agency_search_binds_q_instead_of_splicing_it(db):
    asyncio.run(oce.list_agencies(q=PAYLOAD))
    sql, params = db.calls[0]
    assert "UNION" not in sql and "'" + "%" not in sql, \
        "the agency search puts the caller's text into the SQL again"
    assert "$1" in sql and params == [f"%{PAYLOAD.lower()}%"]


def test_the_agency_search_escapes_like_wildcards(db):
    """A search for `_` must match an underscore, not every agency."""
    asyncio.run(oce.list_agencies(q="a_b%c"))
    assert db.calls[0][1] == ["%a\\_b\\%c%"]


def test_no_search_binds_nothing(db):
    asyncio.run(oce.list_agencies())
    sql, params = db.calls[0]
    assert params == [] and "$1" not in sql


# ── /login: the credential lookup (modules/user.py) ─────────────────────────
#
# ⚠⚠ The worst of the three. `username` from the unauthenticated /login form
# went into `WHERE email='{}'`, so a UNION could return a row with a real id, a
# pwdhash the attacker chose and scope 'admin' — a full-scope token with no
# password, which unlocks /delete/{tbl} and /upload.

import importlib.util
import os
import sys

import main  # noqa: E402


def _load_user_module():
    path = os.path.join(os.path.dirname(__file__), '..', 'modules', 'user.py')
    spec = importlib.util.spec_from_file_location('_user_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _SyncModel:
    def __init__(self):
        self.calls = []

    def bselect_safe(self, sql, dd=[]):
        self.calls.append((sql, list(dd)))
        return {}

    def select(self, sql, *a, **k):          # the old, formatting path
        self.calls.append((sql, []))
        return {}


def _user_with(model):
    User = _load_user_module().User
    u = object.__new__(User)
    u._User__model = model
    return u


LOGIN_PAYLOAD = "' UNION SELECT 1,'a','h','admin'--"


def test_the_login_lookup_binds_the_username():
    m = _SyncModel()
    assert not _user_with(m).get_user(email=LOGIN_PAYLOAD)
    sql, params = m.calls[0]
    assert 'UNION' not in sql and "'" not in sql, \
        'the login lookup puts the submitted username into the SQL again'
    assert params == [LOGIN_PAYLOAD]


def test_auth_user_binds_both_values():
    m = _SyncModel()
    assert _user_with(m).auth_user(LOGIN_PAYLOAD, 'pw') is None
    sql, params = m.calls[0]
    assert 'UNION' not in sql and "'" not in sql and params[0] == LOGIN_PAYLOAD


def test_user_py_formats_no_sql():
    src = open(os.path.join(os.path.dirname(__file__), '..', 'modules', 'user.py')).read()
    code = '\n'.join(l for l in src.splitlines() if not l.lstrip().startswith('#'))
    assert "='{}'" not in code and ".q(" not in code, \
        'user.py builds SQL by string formatting again'


# ── /get/titles/{id}/{tbl} and /get/districts/{type}/{id}/{tbl} ─────────────

@pytest.fixture
def main_sql(monkeypatch):
    calls = []

    async def fake_select(sql, params=()):
        calls.append((sql, list(params)))
        return []
    monkeypatch.setattr(main, 'select', fake_select)
    return calls


def _status(exc_info):
    return exc_info.value.status_code


@pytest.mark.parametrize('tbl', ["users WHERE $1<>'' --", 'users', 'pg_user'])
def test_the_titles_route_refuses_a_table_it_does_not_serve(main_sql, tbl):
    with pytest.raises(main.HTTPException) as e:
        asyncio.run(main.get_subdataset_related_to_civil_title('1', tbl))
    assert _status(e) == 404 and main_sql == []


def test_the_titles_route_still_serves_its_tables(main_sql):
    for tbl in ('positionschedule', 'civillist', 'nycjobs', 'civillistactive'):
        asyncio.run(main.get_subdataset_related_to_civil_title('1', tbl))
    assert len(main_sql) == 4


@pytest.mark.parametrize('tbl', ["pg_user WHERE $1<>'' --", 'users'])
def test_the_district_route_refuses_a_table_it_does_not_serve(main_sql, tbl):
    with pytest.raises(main.HTTPException) as e:
        asyncio.run(main.get_subdataset_by_administrative_district(
            type='cd', tbl=tbl, id='101', sort=None, f='email', limit=None, offset=0))
    assert _status(e) == 404 and main_sql == []


def test_a_quote_in_the_district_sort_or_column_cannot_close_the_identifier(main_sql):
    evil = 'a", (SELECT pwdhash FROM users)--'
    asyncio.run(main.get_subdataset_by_administrative_district(
        type='nta', tbl='facilitydb', id='x', sort=f'"facname",{evil}', f=evil,
        limit=None, offset=0))
    sql = main_sql[0][0]
    # Every `"` the caller sent is doubled, so the payload stays inside one identifier.
    assert '"a"", (SELECT pwdhash FROM users)--"' in sql
    assert sql.replace('""', '').count('"') % 2 == 0


def test_the_frontends_own_district_urls_still_work(main_sql):
    asyncio.run(main.get_subdataset_by_administrative_district(
        type='nta', tbl='facilitydb', id='Flatbush', sort='"facname","facdomain"',
        f='wegov-nta-code', limit=None, offset=0))
    assert 'ORDER BY "facname", "facdomain"' in main_sql[0][0]


def _unmapped_table():
    t = sorted(main._DISTRICT_TABLES - set(main.DISTRICT_COLUMNS.get('cc', {})))[0]
    return t


def test_the_legacy_f_column_is_used_and_cannot_close_its_identifier(main_sql):
    evil = 'a" = $1 OR 1=1 --'
    asyncio.run(main.get_subdataset_by_administrative_district(
        type='cc', tbl=_unmapped_table(), id='x', sort=None, f=evil, limit=None, offset=0))
    sql = main_sql[0][0]
    assert '"a"" = $1 OR 1=1 --"' in sql, sql
    assert sql.replace('""', '').count('"') % 2 == 0


def test_a_plain_f_column_is_quoted_as_before(main_sql):
    asyncio.run(main.get_subdataset_by_administrative_district(
        type='cc', tbl=_unmapped_table(), id='14', sort=None, f='Council District',
        limit=None, offset=0))
    assert '"Council District"' in main_sql[0][0]


def test_the_district_allowlist_covers_every_table_the_frontend_serves():
    php = open(os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'app',
                            'Custom', 'DistDatasets.php')).read()
    import re
    served = set(re.findall(r"'table'\s*=>\s*'([^']+)'", php))
    assert served and served <= main._DISTRICT_TABLES, \
        f'DistDatasets serves tables the api now 404s: {sorted(served - main._DISTRICT_TABLES)}'


# ── /import-csv and /upload: the table name, CSV headers and index names ────
#
# Both need a credential, but both reach DDL with caller text: /upload takes the
# table from the CSV url's last path segment, /import-csv from a form field, and
# both take column names from the CSV header row. `/upload` runs through the
# sync driver's `execute`, which accepts stacked statements.

import json as _json


@pytest.mark.parametrize('name', [
    'crol', 'wegov_orgs', 'civillist', 'payrolldata',
    'nyc-agencies-and-governance-organizations',   # a live table, hyphens and all
])
def test_every_real_import_name_is_accepted(name):
    assert main._import_table_ok(name)


@pytest.mark.parametrize('name', [
    'x"; DROP TABLE users; --', "x'", 'a b', '../etc', 'a.b', 'a/b', '',
    '1abc', 'a' * 64, 'x");--',
])
def test_a_hostile_import_name_is_refused(name):
    assert not main._import_table_ok(name)


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setattr(main, '_api_key_ok', lambda *a, **k: True)


def test_import_csv_refuses_a_hostile_table_before_touching_anything(keyed, monkeypatch):
    import aiohttp
    monkeypatch.setattr(aiohttp, 'ClientSession', lambda *a, **k: pytest.fail('downloaded'))
    r = asyncio.run(main.import_csv_async(
        url='https://example.org/x.csv', table_name='x"; DROP TABLE users; --',
        api_key=None, x_api_key='k', request=None))
    assert r.status_code == 400


def test_upload_refuses_a_hostile_table_from_the_url(keyed, monkeypatch):
    monkeypatch.setattr(main, 'CsvDataset', type('CsvDataset', (), {
        'url2fn': staticmethod(lambda u: 'x";drop table users;--'),
        '__init__': lambda self: pytest.fail('reached the importer')}))
    r = asyncio.run(main.upload_csv_dataset(
        url='https://example.org/x%22;drop.csv', idxs='', api_key=None,
        x_api_key='k', request=None, user=None))
    assert r.status_code == 400


def test_import_csv_doubles_a_quote_in_a_csv_header():
    src = open(os.path.join(os.path.dirname(__file__), '..', 'main.py')).read()
    assert src.count("""col_defs = ', '.join([f'"{col}" TEXT' for col in clean_cols])""") == 0, \
        'a CSV header is spliced into CREATE TABLE unescaped again'
    assert src.count("""'"{}" TEXT'.format(col.replace('"', '""'))""") == 2, \
        'both CSV importers (generic and crol) must escape their headers'


def _load_csvdataset():
    here = os.path.dirname(__file__)
    for p in (os.path.join(here, '..', 'modules'), os.path.join(here, '..', 'modules', 'postgrex')):
        if p not in sys.path:
            sys.path.insert(0, p)
    path = os.path.join(here, '..', 'modules', 'postgrex', 'csvdataset.py')
    spec = importlib.util.spec_from_file_location('_csvdataset_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Db:
    def __init__(self, tables=()):
        self.sql, self._tables = [], list(tables)

    def q(self, sql):
        self.sql.append(sql)

    def tables(self):
        return self._tables


def _dataset(mod, db, model):
    ds = object.__new__(mod.CsvDataset)
    ds.db, ds.datadir = db, '/data'
    ds.model = lambda fn='': model
    return ds


def test_the_importer_quotes_every_caller_name():
    mod = _load_csvdataset()
    db = _Db()
    evil_col = 'a", (SELECT 1)) ; DROP TABLE users; --'
    model = {evil_col: {'postgres': 'text', 'type': 'text'}, 'ok': {'postgres': 'text', 'type': 'text'}}
    _dataset(mod, db, model).import_csv('t_1', 't_1', f'ok,{evil_col}')
    joined = '\n'.join(db.sql)
    assert '"a"", (SELECT 1)) ; DROP TABLE users; --"' in joined
    for stmt in db.sql:
        body = stmt.split(" FROM '")[0]          # the COPY path is a literal, not an identifier
        assert body.replace('""', '').count('"') % 2 == 0, stmt
    assert db.sql[0].startswith('CREATE TABLE "t_1"')


def test_the_importer_refuses_a_hostile_table():
    mod = _load_csvdataset()
    db = _Db()
    with pytest.raises(ValueError):
        _dataset(mod, db, {'a': {'postgres': 'text', 'type': 'text'}}).import_csv(
            'x; DROP TABLE users', 'x', '')
    assert db.sql == []
