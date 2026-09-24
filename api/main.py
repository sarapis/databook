import json
from types import SimpleNamespace
import logging
import os
import secrets

# Logging is configured FIRST, before the routers are imported, so that nothing
# can log before there is a handler to receive it. uvicorn configures only its
# own three loggers and leaves root at WARNING with an empty handler list, which
# dropped every `logger.info` in this codebase (including the readiness signal
# `digital spend map ready`) and left warnings printing as bare, level-less
# lines via `logging.lastResort`. See modules/applog.py — it carries the
# measurements and the reason this is one owner rather than a call per module.
from modules import applog
# ⚠ The ONE owner of the capital budget-line spelling rule. Five sources
# punctuate the same line five ways and a raw comparison joins nothing.
from modules import budgetline
# ⚠ The ONE owner of the capital slug rule, and of which source table can be
# counted for which scope dimension (and HOW). Both exist because every source
# spells these dimensions differently — five punctuations of a budget line, and
# 124 of 138 category names differing from the spine's by case alone.
from modules import capitalslug
from modules import capitalsources
applog.configure()

from modules import autoload
import uvicorn
from fastapi import Depends, FastAPI, Security, Query, Request, Path, HTTPException, Header
import asyncpg
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Set
from fastapi_login import LoginManager
from fastapi_login.exceptions import InvalidCredentialsException
from fastapi.security import OAuth2PasswordRequestForm
import datetime
from config import Config
from user import User
from postgrex import CsvDataset
#from reqs import select
#from pydantic import BaseModel
from postgrex import PostgresModelAsync
from modules import duckpool
from modules import orgcore
from modules import searchindexes
from modules import orgfilter
from modules import sourcedupes
# Credential resolution lives in one place — see modules/dbcreds.py.
from modules import dbcreds
# The shared machine-to-machine key check — see modules/apikey.py.
from modules import apikey
from subprocess import Popen
from routers.oce import router as oce_router
from routers.budget_revenue import router as budget_revenue_router
from routers.payroll import router as payroll_router
from routers.nycha import router as nycha_router
from routers.capital import router as capital_router
# ⚠ THE SAME FORMATTER THE PROFILE USES, imported rather than re-written. A
# second spelling of a date format is precisely how this section came to publish
# two — `_mdy_label`'s own docstring says so. It is underscore-private, which is
# a smell; the alternative was a fourth implementation, which is worse.
from routers.capital import _mdy_label as _capital_mdy_label
from routers.data_pipeline import router as pipeline_router
from routers.public_v1 import router as public_v1_router
from routers.search import router as search_router
from routers.org_admin import router as org_admin_router
from routers.review import router as review_router
from routers.licenses import router as licenses_router
from modules.errfmt import exc_str

# Error tracking: enabled only when SENTRY_DSN is set in the environment,
# so local dev and tests run without a Sentry account configured.
if os.getenv('SENTRY_DSN'):
    import sentry_sdk

    sentry_sdk.init(
        dsn=os.getenv('SENTRY_DSN'),
        environment=os.getenv('SENTRY_ENVIRONMENT', 'production'),
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
    )

app = FastAPI(
    title = 'WeGovNYC Databook API',
    description = 'Access all normalized Databook data using our API documented below.',
    version="0.0.1",
    contact={
        'name': 'WeGovNYC Databook',
        'url': 'https://databook.wegov.nyc/',
        'email': 'dp@databook.wegov.nyc',
    },
)
'''license_info={
    'name': 'Apache 2.0',
    'url': 'https://www.apache.org/licenses/LICENSE-2.0.html',
},'''

origins = [
    'http://localhost:8000',
    'http://localhost:5539',
    'http://localhost:8580',       # Local dev (docker-compose.local.yml)
    'http://localhost:8080',       # Alternative local dev
    'http://18.191.137.137:5539',
    'http://devinbalkind',
    'http://52.14.103.188',
    'http://databook.wegov.nyc',
    'https://databook.wegov.nyc',
    'http://databook.nyc',
    'https://databook.nyc',
    'http://www.databook.nyc',
    'https://www.databook.nyc',
    'http://staging.databook.nyc',
    'https://staging.databook.nyc',
]

# Allow additional origins via environment variable (comma-separated).
# This avoids hardcoding staging/preview domains in source code.
_extra_origins = os.getenv('CORS_EXTRA_ORIGINS', '')
if _extra_origins:
    origins.extend([o.strip() for o in _extra_origins.split(',') if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# --- Cache-Control on the read-only API ------------------------------------------
# A Cloudflare Cache Rule caches GET /oce/* and /get/* at the edge, which is what
# absorbs the distributed crawl documented in CLAUDE.md (525 distinct IPs, 82%
# making exactly one request — no per-IP rate limit can see that traffic).
#
# ⚠⚠ THE ORDER OF THIS CHANGE AND THE CLOUDFLARE RULE IS LOAD-BEARING, in both
# directions, and getting it wrong fails SILENTLY:
#   * While the rule is `override_origin`, Cloudflare IGNORES these headers, so
#     deploying this alone changes nothing at the edge. Harmless, and it is why
#     the api must ship FIRST.
#   * The moment the rule becomes `respect_origin`, an endpoint that sends NO
#     Cache-Control stops being cached at all. That is why this is a middleware
#     with a default rather than a header added per handler — a new /oce/ endpoint
#     must not silently drop out of the cache by omission.
# So: deploy the api, then flip the rule to respect_origin. Never the reverse.
CACHEABLE_API_PREFIXES = ("/oce/", "/get/")
API_EDGE_MAX_AGE = int(os.getenv("API_EDGE_MAX_AGE", "600"))


@app.middleware("http")
async def add_read_api_cache_control(request: Request, call_next):
    response = await call_next(request)
    # Only successful GETs, and never clobber a handler that set its own value —
    # that is how a handler opts out (see oce._spend_cache_headers, which sends
    # no-store while the contract spend map is still populating).
    if (
        request.method == "GET"
        and response.status_code == 200
        and request.url.path.startswith(CACHEABLE_API_PREFIXES)
        and "cache-control" not in response.headers
    ):
        response.headers["Cache-Control"] = f"public, max-age={API_EDGE_MAX_AGE}"
    return response

manager = LoginManager(Config.fastapi['key'], '/login')


# ── token scopes ─────────────────────────────────────────────────────────────
#
# ⚠ Until 2026-08-01 `/login` minted `scopes=['read']` HARDCODED and never read
# `users.scope`, so no login token could reach any write endpoint. That looked
# safe but it was vestigial, and the obvious "fix" — mint the token's scopes
# from `users.scope` — would have silently made a human login able to DROP
# tables via `/delete`, because that endpoint only required `write`.
#
# So the scopes are TIERED, and the tiers are the decision the exposure forced:
#   read   every normal query
#   write  ingest operations (`/upload`, `/log-ingestion`) — a data operator
#   admin  DESTRUCTIVE or privileged ops (`/delete`) — the owner only
# A `write` user can load data but cannot drop a table; only a `full`/`admin`
# user gets `admin`. `users.scope` on prod is a single row, `full`.
#
# ⚠⚠ NONE OF THIS MATTERS WHILE THE SIGNING SECRET IS GUESSABLE. Scopes gate a
# token the server ISSUED; they do nothing against a token an attacker FORGED,
# and the JWT is signed with `Config.fastapi['key']`. That key must be a strong
# secret (rotation: scripts/rotate-fastapi-key.sh) or a forger simply writes
# `scopes:['admin']` into their own token. The scope tiers are defence in depth
# behind that, not a substitute for it.
def scopes_for(user_scope):
    s = (user_scope or '').strip().lower()
    if s in ('full', 'admin', 'superuser'):
        return ['read', 'write', 'admin']
    if s == 'write':
        return ['read', 'write']
    return ['read']
user = User()
select = PostgresModelAsync.select

import re
_VALID_TABLE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# ⚠⚠ A table name an IMPORT may create. /upload takes it from the CSV url's last
# path segment and /import-csv from a form field; both reach DDL, a staging-table
# name and a file path (`/tmp/import_<name>.csv`, `COPY … FROM '<path>'`). Before
# 2026-09-24 neither was checked, so a credentialed caller could run arbitrary SQL
# through either. Hyphens stay legal: `nyc-agencies-and-governance-organizations`
# is a live table, and every use of the name below is double-quoted.
_IMPORT_TABLE = re.compile(r'^[a-z_][a-z0-9_-]*$')


def _import_table_ok(name: str) -> bool:
    return bool(name) and len(name) <= 63 and bool(_IMPORT_TABLE.match(name))


def _safe_table(tbl: str) -> str:
    """Reject anything that isn't a plain SQL identifier, so a table name from
    a URL path can't be used for SQL injection when interpolated into a query.
    """
    if not _VALID_TABLE.match(tbl):
        raise HTTPException(status_code=404, detail="Unknown table")
    return tbl

# Register routers
app.include_router(public_v1_router)
app.include_router(search_router)
app.include_router(oce_router)
app.include_router(budget_revenue_router)
app.include_router(payroll_router)
app.include_router(nycha_router)
app.include_router(capital_router)
app.include_router(pipeline_router)
# Phase 5 — the org register's editing surface. Every route is gated by
# routers/org_admin.require_editor; see that module for why it authorises on the
# user row's scope rather than the token's.
app.include_router(org_admin_router)
app.include_router(review_router)
app.include_router(licenses_router)


@app.on_event("startup")
async def start_data_scheduler():
    """Launch the background data scheduler if enabled via environment variable."""
    import asyncio
    if os.environ.get('DATA_SCHEDULER_ENABLED', '').strip() == '1':
        from data_scheduler import scheduler_loop
        asyncio.create_task(scheduler_loop())
        print("[startup] Data scheduler enabled — background task started.")
    else:
        print("[startup] Data scheduler disabled. Set DATA_SCHEDULER_ENABLED=1 to enable.")

@manager.user_loader()
async def query_user(user_id: str):
    """Load user from database using async connection to avoid sync connection corruption."""
    try:
        user_id_int = int(user_id)  # Cast string to int for asyncpg (id column is integer)
    except (ValueError, TypeError):
        return None
    result = await PostgresModelAsync.select(
        "SELECT id, email, pwdhash, scope FROM users WHERE id=$1", (user_id_int,)
    )
    if result.get('rows'):
        return result['rows'][0]
    return None

# JWT signing secrets that are published defaults — running with any of these
# means anyone can forge a token with `scopes:['admin']` and DROP tables. The
# scope tiers in scopes_for() are meaningless while this is true.
_WEAK_SIGNING_KEYS = {'supersecretkey', 'secret', 'changeme', 'test-secret-key'}


@app.on_event("startup")
async def warn_on_weak_signing_key():
    # ⚠ Turns "silently forgeable" into "screams on every boot until rotated".
    # A WARNING, not a refusal: a refusal that misfires would brick the api, and
    # the point is to be impossible to ignore, not to be a new outage mode.
    key = (Config.fastapi or {}).get('key', '')
    if key in _WEAK_SIGNING_KEYS:
        msg = ("[SECURITY] the JWT signing secret is a PUBLISHED DEFAULT — anyone "
               "can forge an admin token. Rotate it: scripts/rotate-fastapi-key.sh")
        print("=" * 78 + f"\n{msg}\n" + "=" * 78, flush=True)
        if os.getenv('SENTRY_DSN'):
            try:
                import sentry_sdk
                sentry_sdk.capture_message(msg, level='error')
            except Exception:
                pass


@app.on_event("startup")
async def startup():
    # Fully opens the pool (min_size == max_size) BEFORE traffic, so the request
    # path never calls getaddrinfo; see modules/postgrex/asyncmodel.py.
    await PostgresModelAsync.connect()
    print(f"[startup] Postgres pool warm: {PostgresModelAsync.pool_status()}", flush=True)
    # DuckDB gets its OWN executor so Parquet scans can never starve DNS
    # resolution for new Postgres connections; see modules/duckpool.py.
    print(f"[startup] DuckDB executor: {duckpool.pool_status()}", flush=True)
    await ensure_people_indexes()
    
    # Pre-warm heavy caches in the background so first user hits are instant.
    # IMPORTANT: run them SEQUENTIALLY in a single task, not as concurrent
    # create_task() fan-out. Each warm scans large Parquet/Postgres data; run
    # concurrently their peak allocations stacked and blew the container memory
    # limit -> OOM mid-warm -> restart -> re-warm, a perpetual crash-loop. Serial
    # keeps peak memory to one task at a time while staying off the startup
    # critical path (uvicorn is already accepting requests).
    import asyncio
    from routers.oce import refresh_dashboard_cache, refresh_digital_reform_cache, prewarm_transactions_metadata
    from routers.data_pipeline import _build_briefing

    async def _sequential_prewarm():
        warms = [
            ("dashboard", refresh_dashboard_cache),
            ("digital-reform", refresh_digital_reform_cache),
            ("transactions", prewarm_transactions_metadata),
            ("briefing", _build_briefing),
            ("projects-map", _load_projects_map_cache),
        ]
        for label, fn in warms:
            try:
                await fn()
                print(f"[startup] pre-warm done: {label}", flush=True)
            except Exception as e:
                print(f"[startup] pre-warm failed ({label}): {exc_str(e)}", flush=True)
        print("[startup] Sequential cache pre-warm complete.", flush=True)
    asyncio.create_task(_sequential_prewarm())
    print("[startup] Sequential cache pre-warm started (dashboard -> digital-reform -> transactions -> briefing -> projects-map).")

    # Briefing rebuilds every 6h thereafter (the initial build runs in the
    # sequential pre-warm above; this loop sleeps FIRST so it never collides
    # with startup warm).
    async def _briefing_rebuild_loop():
        while True:
            await asyncio.sleep(6 * 3600)  # 6 hours
            try:
                await _build_briefing()
            except Exception as e:
                print(f"[briefing] Cache rebuild failed: {exc_str(e)}", flush=True)
    asyncio.create_task(_briefing_rebuild_loop())
    print("[startup] Briefing 6h rebuild loop started.")


async def ensure_people_indexes():
    """Apply the declared indexes for the three people tables at startup.

    ⚠⚠ THIS FUNCTION USED TO BE A SECOND DECLARATION SITE, and that was the defect:
    it issued its own CREATE INDEX statements under names that differed from the ones
    in `data_scheduler.TABLE_INDEXES`, so the same column was declared twice and only
    the startup name ever existed. Worse, startup is a WEAK mechanism for a
    pipeline-loaded table — /import-csv drops the table on every ingest and restores
    only the GIN half — so `idx_civillist_titlecode` (the most-used index on that
    table, 6,528 scans, declared nowhere else) was absent from each ingest until the
    next api restart.

    Now it calls the SAME function the post-ingest hook does, so there is one owner
    for what an index is and two callers for when to apply it. Idempotent; ANALYZE on
    the three tables measures ~1.8s in total, which is noise against startup.
    """
    try:
        # Lazy import: data_scheduler pulls in the whole enrichment stack, and this
        # module is imported at startup either way — matching the scheduler_loop
        # import above rather than adding a module-level dependency.
        from data_scheduler import recreate_table_indexes
        # `recreate_table_indexes` wants something with `.execute(sql)`;
        # PostgresModelAsync.execute has exactly that shape, so a namespace is enough.
        conn = SimpleNamespace(execute=PostgresModelAsync.execute)
        for tbl in ("civillist", "payrolldata", "civillistactive"):
            await recreate_table_indexes(conn, tbl)
        print("[startup] People search + org section indexes ensured.")
    except Exception as e:
        # Non-fatal: tables may not exist yet (first boot before data import)
        print(f"[startup] Skipped people indexes: {exc_str(e)}")


@app.on_event("shutdown")
async def shutdown():
    await PostgresModelAsync.disconnect()
    duckpool.shutdown()


@app.get('/health', tags=['Operations'], summary='Health check for deployment verification')
async def health_check():
    """Validate all critical dependencies are reachable."""
    checks = {}
    # Postgres
    try:
        result = await select('SELECT 1 AS ok')
        checks['postgres'] = 'ok' if result.get('rows') else 'no_rows'
    except Exception as e:
        checks['postgres'] = f'fail: {e}'
    # Table count
    try:
        result = await select("SELECT count(*) AS cnt FROM pg_tables WHERE schemaname='public'")
        checks['tables'] = result['rows'][0]['cnt'] if result.get('rows') else 0
    except Exception as e:
        checks['tables'] = f'fail: {e}'
    # CORS origins
    checks['cors_origins'] = len(origins)
    overall = 'ok' if checks.get('postgres') == 'ok' and isinstance(checks.get('tables'), int) and checks['tables'] > 0 else 'degraded'
    return {'status': overall, 'checks': checks}


    
# ================ datasets ================

@app.get('/get/datasets/all', tags=['Datasets'], summary="Get all dataset profiles")
async def get_all_datasets_profiles():
    """Return dataset metadata from dataset_registry.

    Aliases columns to match the legacy data_sources field names
    expected by PHP consumers (stats_data_sources, About page, etc.).
    """
    return await select("""
        SELECT display_name AS "Name",
               citation_url AS "Citation URL",
               source AS "Source",
               section AS "Section",
               description AS "Descripton",
               CASE WHEN is_active THEN 'Active' ELSE 'Develop' END AS "Status",
               to_char(last_ingested_at, 'MM/DD/YYYY HH24:MI') AS "Last Updated",
               to_char(last_checked_at, 'MM/DD/YYYY HH24:MI') AS "Last Modified",
               source_url AS "Data URL",
               table_name || '.csv' AS "Output Path",
               table_name AS "Label",
               category AS "Core Dataset(s)",
               id AS "_uid"
        FROM dataset_registry
        WHERE display_name IS NOT NULL
        ORDER BY display_name
    """)


@app.get('/get/datasets/profile/{name}', tags=['Datasets'], summary="Get dataset profile by name")
async def get_dataset_profile_by_name(name:str):
    """Get dataset profile from dataset_registry.

    Aliases columns to match the legacy data_sources field names
    expected by blade template citations.
    """
    return await select("""
        SELECT display_name AS "Name",
               citation_url AS "Citation URL",
               source AS "Source",
               section AS "Section",
               description AS "Descripton",
               CASE WHEN is_active THEN 'Active' ELSE 'Develop' END AS "Status",
               to_char(last_ingested_at, 'MM/DD/YYYY HH24:MI') AS "Last Updated",
               to_char(last_checked_at, 'MM/DD/YYYY HH24:MI') AS "Last Modified",
               source_url AS "Data URL",
               table_name || '.csv' AS "Output Path",
               table_name AS "Label",
               id AS "_uid"
        FROM dataset_registry
        WHERE display_name LIKE $1
    """, (name,))


# ================ orgs ================

# Retired org rows must not be served — see modules/orgfilter.py for why this is
# a probed, cached helper rather than an inline `AND retired_at IS NULL`.
async def _orgs_live(prefix: str = 'AND') -> str:
    return await orgfilter.live_clause(select, prefix)


@app.get('/get/orgs/chart', tags=['Organizations'])
async def get_organizations_for_building_chart():
    """Candidates for the org chart, carrying BOTH on-chart opinions.

    Type selects the candidates (including the `Classification` / `Official`
    scaffolding nodes). `wegov_orgs.in_org_chart` is OUR editorial flag and is
    applied here — `IS NOT FALSE`, not `IS TRUE`, so an org we have no opinion
    about stays on the chart exactly as it did before the flag existed.

    OTI's separate opinion rides along as `oti_in_org_chart` rather than being
    applied, because the two chart views differ only in whether they honour it:

        Databook view (default)  our exclusions only
        NYC/OTI view             additionally drop oti_in_org_chart = 'false'

    Conflating the two in one column is what made the second view impossible
    the first time round.
    """
    # Every chart row carries `parent_org_id`, whichever mechanism resolved it:
    # once the FK exists `org.*` supplies it, and before then the legacy
    # child_of/airtable_id join supplies it under the same name. That keeps the
    # PHP builder (App\Custom\OrgChart) on ONE code path — a conditional there
    # is invisible to `php -l` and only a rendered page would catch it.
    par_sel, par_join = await orgfilter.parent_id_projection(select)
    base = ('SELECT org.*' + par_sel + '{enr} FROM wegov_orgs org' + par_join
            + '{join} WHERE org."type" IN ('
            + orgfilter.sql_type_list(orgfilter.CHART_TYPES) + ')'
            + (await _orgs_live()).replace('retired_at', 'org.retired_at')
            + (await orgfilter.in_chart_clause(select)).replace(
                'in_org_chart', 'org.in_org_chart')
            + ' ORDER BY org.name')
    try:
        return await select(base.format(
            enr=', enr.in_org_chart AS oti_in_org_chart',
            join=' LEFT JOIN nyc_org_enrichment enr ON enr.org_id = org.id'))
    except Exception:
        # A database without nyc_org_enrichment still gets a working chart —
        # it just cannot offer the NYC/OTI view.
        return await select(base.format(enr='', join=''))

@app.get('/get/orgs/directory', tags=['Organizations'])
async def get_organizations_directory():
    return await select('SELECT * FROM wegov_orgs WHERE "type" IN ('
                        + orgfilter.sql_type_list(orgfilter.DIRECTORY_TYPES) + ')'
                        + await _orgs_live() + ' ORDER BY name')

@app.get('/get/orgs/agencies', tags=['Organizations'])
async def get_city_agencies():
    """City-level agencies, for /organizations/agencies.

    The page used to take /get/orgs/directory and narrow it client-side with a
    DataTables regex on the literal string 'City Agency'. That broke silently
    when the OTI adoption retyped 240 orgs (167 -> 27). The type vocabulary
    belongs in exactly one place — see modules/orgfilter.py.
    """
    return await select('SELECT * FROM wegov_orgs WHERE "type" IN ('
                        + orgfilter.sql_type_list(orgfilter.CITY_AGENCY_TYPES) + ')'
                        + await _orgs_live() + ' ORDER BY name')


@app.get('/get/orgs/core', tags=['Organizations'])
async def get_orgs_core_feed(report: int = 0):
    """The normalizer's `orgs` matching dictionary, derived from the register.

    One row per NAME VARIANT ({"name", "id"}), assembled by modules/orgcore.py
    — read its docstring before changing anything here; the collision policy
    and the alias table are what keep 2,588 manual match rows resolving.

    Returns a BARE JSON list (not the {"rows": ...} wrapper): the consumer is
    the normalizer's `url:` core-dataset source (`core_datasets.py`), which
    expects a list. `?report=1` returns the assembly diagnostics instead —
    what was omitted and why.
    """
    cols = {r['column_name'] for r in await PostgresModelAsync.select_safe(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'wegov_orgs'")}
    wanted = [c for c in ('id', 'name', 'alternate_name', 'display_name',
                          'type', 'retired_at', 'merged_into') if c in cols]
    org_rows = await PostgresModelAsync.select_safe(
        'SELECT ' + ', '.join(f'"{c}"' for c in wanted) + ' FROM wegov_orgs')
    try:
        alias_rows = await PostgresModelAsync.select_safe(
            'SELECT name, org_id FROM org_core_aliases')
    except asyncpg.exceptions.UndefinedTableError:
        # A database that has not run seed_org_core_aliases.py serves the
        # register-derived feed alone. The pre-flight (--check) still gates
        # any refresh against it, so this cannot silently drop curation.
        alias_rows = []
    feed, diag = orgcore.build_core_feed(org_rows, alias_rows)
    return JSONResponse(diag if report else feed)


@app.get('/get/orgs/all', tags=['Organizations'])
async def get_organizations_full_list():
    return await select('SELECT * FROM wegov_orgs WHERE "type" NOT IN (\'Classification\', \'Official\', \'Public Figure\')' + await _orgs_live() + ' ORDER BY name')

@app.get('/get/orgs/profile/{id}', tags=['Organizations'])
async def get_organization_profile(id: int):
    # `parent_id` / `parent_name` / `parent_type` are COMPUTED aliases over the
    # joined parent row, not table columns — the table columns of those names
    # were 0% populated and are dropped in Phase 3. The alias names are load
    # bearing: sub/orgheader.blade.php renders $org['parent_name'] and links via
    # $org['parent_id'], and greys the label on a Classification/Official
    # parent using $org['parent_type'].
    _base = "SELECT org.*, p.id AS parent_id, p.name AS parent_name, p.type AS parent_type"
    _joins = " FROM wegov_orgs org" + await orgfilter.parent_join(select)
    # Greenbook-derived agency head + fallback address (see api/enrich_agency.py).
    # Guarded so environments that haven't built the enrichment tables yet fall
    # back to the plain profile instead of 500ing every org page.
    try:
        return await select(
            _base
            + ", ahe.head_name AS derived_head_name, ahe.head_title AS derived_head_title"
            + ", ahe.confidence AS derived_head_confidence"
            + ", ace.address AS derived_address, ace.address_rows AS derived_address_rows"
            + _joins
            + " LEFT JOIN agency_head_enrichment ahe ON ahe.org_id = org.id"
            + " LEFT JOIN agency_contact_enrichment ace ON ace.org_id = org.id"
            + " WHERE org.id = $1", (id,))
    except asyncpg.exceptions.UndefinedTableError:
        return await select(_base + _joins + " WHERE org.id = $1", (id,))

@app.get('/get/orgs/section/{id}/{tbl}', tags=['Organizations'])
async def get_subdataset_related_to_organization(id: str, tbl: str):
    # Cap rows: large agencies map to hundreds of thousands of civillist /
    # payrolldata rows (payrolldata is ~6.8M total). SELECT * with no LIMIT
    # materialized the whole set into a Python list of dicts (~660 MB for the
    # worst title equivalent) — concurrent hits OOM-killed the container. Twin of
    # the /get/titles/{id}/{tbl} cap. The client-side DataTable can't render that
    # many rows anyway; org stats/charts use the separate aggregated endpoints.
    _ROW_CAP = 10000
    # civillist's employee-name column is already trimmed to "EMPLOYEE NAME"
    if tbl == 'civillist':
        return await select('SELECT * FROM civillist WHERE "wegov-org-id"=$1 LIMIT {}'.format(_ROW_CAP), (id,))
    # Some tables (e.g. ll18payanddemo, civillistactive) lack the wegov-org-id
    # mapping column — return empty rather than 500 (resilient fallback).
    try:
        return await select("SELECT * FROM {} WHERE \"wegov-org-id\"=$1 LIMIT {}".format(_safe_table(tbl), _ROW_CAP), (id,))
    except (asyncpg.exceptions.UndefinedColumnError, asyncpg.exceptions.UndefinedTableError):
        return []

@app.get('/get/orgs/section-coverage/{tbl}', tags=['Organizations'])
async def get_section_org_coverage(tbl: str):
    """How many organizations a dataset covers at all.

    ⚠⚠ WHY THIS EXISTS: AN EMPTY SECTION TABLE IS AMBIGUOUS, and it resolves the
    reassuring way. The org profile offers every section to every org, so a body
    the dataset simply does not cover renders an empty table that reads as "this
    organization has no capital projects" rather than "this dataset does not list
    organizations like this one".

    The worked example is the Economic Development Corporation. Measured
    2026-09-02, `capitalprojectsdollarscomp` holds 72,437 rows across just 26
    managing agencies — the bodies with their own capital budget lines — and EDC
    is not one, because it is not a City agency: our own register types it
    "Public Benefit or Development Organization", it appears 0 times as a
    contracting agency, and its work reaches it as a VENDOR (24 contracts,
    $12.3B, all from Small Business Services). Its capital tab was empty and
    silent about why.

    ⚠ This counts DISTINCT mapped orgs, which is the dataset's own universe — not
    a hardcoded list that would go stale the moment an agency is added.
    """
    try:
        return await select(
            'SELECT count(DISTINCT "wegov-org-id") AS orgs FROM {}'.format(_safe_table(tbl)),
            ())
    except (asyncpg.exceptions.UndefinedColumnError, asyncpg.exceptions.UndefinedTableError):
        return [{"orgs": 0}]


@app.get('/get/orgs/contract-work/{id}', tags=['Organizations'])
async def get_org_contract_work(id: str):
    """City work an organization delivers as a VENDOR, not as an agency.

    ⚠⚠ WHY THE ORG PROFILE NEEDS THIS. Every agency-keyed section is empty for a
    body that is not a City agency, and that emptiness reads as "no activity"
    rather than "wrong lens". The Economic Development Corporation is the worked
    example: 0 rows in all three capital tables and 0 contracts AS AN AGENCY, but
    12 contracts worth $11.2B as a VENDOR, all from Small Business Services.
    ⚠ 12, not the 24 raw rows — see the dedup note below. I reported 24 twice
    before deduping, which is the amendment double-count this repo has shipped
    twice already.

    ⚠ DEDUPED TO CONTRACT GRAIN. `contracts` holds ONE ROW PER AMENDMENT, and the
    key is `coalesce(contract_id, ctid)` — the spelling #262/#278 established.
    Keying on contract_id alone collapses every NULL-id row into one; not deduping
    at all counts amendments as contracts, which has shipped twice here.
    Amendments RESTATE a total rather than adding to it, so the surviving row is
    the largest `current_amount`.

    ⚠ EXACT vendor_name from a curated seed, never a LIKE — `%ECONOMIC
    DEVELOPMENT CORP%` matches seven different organizations.
    """
    from modules import orgcontractvendors
    names = orgcontractvendors.vendor_names_for(id)
    if not names:
        return {"rows": [], "available": False}
    rows = await select("""
        SELECT DISTINCT ON (coalesce(c.contract_id, 'row:' || c.ctid::text))
               c.contract_id, c.ctr_id, c.agency, c.contract_title,
               c.start_date, c.end_date, c.status, c.vendor_name,
               coalesce(c.current_amount, c.award_amount) AS amount
        FROM contracts c
        WHERE upper(trim(c.vendor_name)) = ANY($1)
        ORDER BY coalesce(c.contract_id, 'row:' || c.ctid::text),
                 coalesce(c.current_amount, c.award_amount) DESC NULLS LAST
    """, ([n.upper().strip() for n in names],))
    # ⚠ `select()` already returns {"rows": [...]}, so wrapping it again produced
    # {"rows": {"rows": [...]}} and the view's `w.rows` was an object, not an
    # array — the table silently rendered nothing. Caught by reading the raw
    # response rather than trusting the shape.
    return {"rows": (rows or {}).get("rows", []), "available": True,
            "vendor_names": names}


@app.get('/get/orgs/capital-projects-via/{id}', tags=['Organizations'])
async def get_org_capital_projects_via_text(id: str):
    r"""Capital projects whose PLAN DESCRIPTION names this organization, from
    BOTH the current plan and the retired series, unioned at PROJECT grain.

    ⚠⚠ WHY THIS EXISTS. A body that is not a City agency holds no row under its
    own id — the managing agencies are the ones with their own capital budget
    lines — so its Capital Projects tab is empty even when it plainly delivers
    capital work. NYCEDC is the worked example: 0 rows under its id.

    ⚠⚠ A UNION, NEVER A SWAP, AND THE MEASUREMENT IS WHY. For NYCEDC the current
    plan names 10 projects and the retired series 15, and only **5** are in both
    — so re-pointing this query at the live table would have silently dropped 10,
    and leaving it on the retired one hides 5. The union is 20. Each row says
    which plans it appears in, because "absent from the 2026 plan" is itself
    information a reader should see rather than have quietly removed.

    ⚠⚠ TWO MONEY COLUMNS, NEVER ONE. They are different measures AND different
    units at source: `plannedcommit_total` is planned commitment in DOLLARS,
    while `BUDG_CURR` is a current budget in THOUSANDS (the retired dataset's own
    description says so, and the page's renderer multiplies by 1000 — carrying
    that unit across is exactly the 1000x defect this file already paid for).
    Both are normalised to dollars HERE, once, and the keys are suffixed `_usd`
    so a later reader cannot re-scale them. They are never added together.

    ⚠ The retired series republishes every project at each of its 14 publication
    dates — 108 rows for 15 projects — so it is deduped to the NEWEST publication
    per project. `PUB_DATE` is numeric, so DESC is chronological. Without this the
    page would count publication events as projects.

    ⚠ `PROJECT_ID` is `character` (blank-padded) while `projectid` is `text`, so
    every join and dedup key is `btrim()`ed explicitly rather than relying on
    bpchar comparison semantics to ignore trailing spaces.

    ⚠⚠ WORD BOUNDARY, NEVER A BARE SUBSTRING. `%EDC%` matches **INCLUDEDCITY**
    (INCLUDED + CITY run together in a DDC scope text) and drags in 11 unrelated
    road-reconstruction projects — 26 by substring vs 15 with `\mEDC\M`.

    ⚠ TEXT EVIDENCE, NOT AN AUTHORITATIVE LINK, and the page says so. The Plan
    publishes no contractor field.
    """
    from modules import orgprojecttokens
    token = orgprojecttokens.token_for(id)
    if not token:
        return {"rows": [], "available": False}
    # \m and \M are Postgres word boundaries. The token is validated alphanumeric
    # in the module, so it cannot carry a regex metacharacter.
    pattern = r'\m' + token + r'\M'
    rows = await select("""
        WITH cur AS (
          SELECT btrim(projectid) AS pid, btrim(description) AS name,
                 -- ⚠ `magency` is a numeric CODE, not a name: it is a bare number on
                 -- all 12,929 rows, and `magencyacro` (the acronym) is populated on
                 -- every one. Reading the plausibly-named column rendered "126" as the
                 -- agency of a $52M project. The column name is not the contract.
                 btrim(coalesce(magencyacro, '')) AS agency,
                 btrim(coalesce(typecategory, '')) AS category,
                 btrim(coalesce(ccpversion, '')) AS ccpversion,
                 btrim(coalesce("wegov-org-id", '')) AS org_id,
                 CASE WHEN btrim(coalesce(plannedcommit_total, '')) ~ '^[0-9.]+$'
                      THEN btrim(plannedcommit_total)::numeric END AS planned_commit_usd
          FROM capitalprojectslist
          WHERE description ~* $1
        ), ret AS (
          SELECT DISTINCT ON (btrim("PROJECT_ID"))
                 btrim("PROJECT_ID") AS pid, btrim("PROJECT_DESCR") AS name,
                 btrim(coalesce("MANAGING_AGCY", '')) AS agency,
                 btrim(coalesce("TYP_CATEGORY_NAME", '')) AS category,
                 btrim(coalesce("BORO", '')) AS boro,
                 "PUB_DATE" AS pub_date,
                 "wegov-org-id"::text AS org_id,
                 -- ⚠ BUDG_ORIG is `numeric` while BUDG_CURR is text-like and holds
                 -- '' and '-', so they cannot be guarded the same way: wrapping the
                 -- numeric one in coalesce(...,'') raises
                 -- `invalid input syntax for type numeric: ""`.
                 -- ⚠⚠ SCHEDULE DATES, AND ONLY FROM THIS SIDE. The 2026 plan's
                 -- mindate/maxdate are NOT the same measure: 12,408 of its 12,929
                 -- maxdate values fall on 06/01, i.e. fiscal-year plan boundaries,
                 -- where START_CURR lands on 06/01 only 16% of the time and spreads
                 -- across 12 month-days. They agree on an exact start for 51 of
                 -- 6,323 overlapping projects (0.8%), so coalescing them would put
                 -- two different measures in one column — the same defect the money
                 -- columns were split to avoid.
                 -- ⚠ 1899/1900 is a spreadsheet-epoch SENTINEL, 703 rows in one
                 -- spike, and NYCEDC's GI-EDC carries 12/01/1899. Suppressed here so
                 -- there is ONE owner for the rule. Deliberately NOT a wider cutoff:
                 -- the 1930-1939 cluster (138 rows) and the isolated 1983/86/88 dates
                 -- may well be real, and nothing here evidences otherwise.
                 CASE WHEN btrim(coalesce("START_CURR", '')) NOT IN ('', '-')
                       AND right(btrim("START_CURR"), 4) >= '1901'
                      THEN btrim("START_CURR") END AS start_date,
                 CASE WHEN btrim(coalesce("END_CURR", '')) NOT IN ('', '-')
                       AND right(btrim("END_CURR"), 4) >= '1901'
                      THEN btrim("END_CURR") END AS end_date,
                 "BUDG_ORIG" * 1000 AS orig_cost_usd,
                 -- ⚠ `-?` matches the stats endpoint's guard so the COLUMN and the
                 -- TILE cannot diverge on sign. A no-op today, verified rather than
                 -- assumed: 0 negative BUDG_CURR and 0 negative BUDG_ORIG in all
                 -- 72,437 rows.
                 CASE WHEN btrim(coalesce("BUDG_CURR", '')) ~ '^-?[0-9.]+$'
                      THEN btrim("BUDG_CURR")::numeric * 1000 END AS budget_usd
          FROM capitalprojectsdollarscomp
          WHERE "PROJECT_DESCR" ~* $1 OR "SCOPE_TEXT" ~* $1
          ORDER BY btrim("PROJECT_ID"), "PUB_DATE" DESC
        )
        SELECT coalesce(c.pid, r.pid)          AS project_id,
               coalesce(c.name, r.name)        AS name,
               -- ⚠ Retired first HERE ONLY, and only for this column: it carries the
               -- agency's full name ("DEPT OF SMALL BUSINESS SERVICES") where the
               -- current plan carries the acronym ("SBS"). Same body either way.
               -- ⚠ THE RAW STRING IS KEPT AS A FALLBACK, never dropped: it is what
               -- renders when an org id does not resolve, and losing the agency
               -- entirely would be worse than showing it unlinked. Retired-first
               -- here because that side carries the full name where the current plan
               -- carries an acronym.
               coalesce(nullif(r.agency, ''), c.agency)     AS agency,
               -- ⚠⚠ 2026-FIRST FOR THE ID, the opposite of the line above and
               -- deliberate. #366 measured that `capitalprojectslist` is the correct
               -- side: of 319 projects whose agency changed inside the retired
               -- series' own publications, 307 ended up matching the 2026 plan. The
               -- raw string is only a display fallback, but the id is a CLAIM about
               -- which agency runs the project and a LINK a reader will follow, so
               -- it takes the authoritative source.
               o.id                             AS agency_org_id,
               coalesce(o.display_name, o.name) AS agency_name,
               coalesce(nullif(c.category, ''), r.category) AS category,
               coalesce(r.boro, '')            AS boro,
               (c.pid IS NOT NULL)             AS in_current,
               (r.pid IS NOT NULL)             AS in_retired,
               c.ccpversion                    AS ccpversion,
               r.pub_date                      AS pub_date,
               c.planned_commit_usd            AS planned_commit_usd,
               r.start_date                    AS start_date,
               r.end_date                      AS end_date,
               r.orig_cost_usd                 AS orig_cost_usd,
               r.budget_usd                    AS budget_usd
        FROM cur c FULL OUTER JOIN ret r ON c.pid = r.pid
        -- ⚠ The regex guard is required, not defensive: the list table's column
        -- is TEXT, so one non-numeric value would abort the whole query on ::int.
        LEFT JOIN wegov_orgs o
          ON coalesce(nullif(c.org_id, ''), r.org_id) ~ '^[0-9]+$'
         AND o.id = coalesce(nullif(c.org_id, ''), r.org_id)::int
        -- ⚠ Ordered by what the table SHOWS. The visible money columns are the
        -- 2023 series' original and current cost, so ranking by the 2026 plan's
        -- planned commitment would order rows by a figure no column displays. It
        -- stays as the tiebreak, which is all it can be for the rows that appear
        -- only in the 2026 plan and therefore carry no cost at all.
        ORDER BY coalesce(r.budget_usd, 0) DESC, coalesce(c.planned_commit_usd, 0) DESC
        LIMIT 10000
    """, (pattern,))
    out = (rows or {}).get("rows", [])
    # ⚠ COUNT WHAT IS SHOWN. The previous version counted distinct projects across
    # all 14 publication dates (15) while the table rendered only the newest
    # publication (9), so the note's own figure disagreed with the rows beneath
    # it. The count is now len(out) by construction — one row per project.
    return {"rows": out, "available": bool(out), "token": token,
            "projects": len(out),
            "in_current": sum(1 for r in out if r.get("in_current")),
            "in_retired": sum(1 for r in out if r.get("in_retired"))}

@app.get('/get/orgs/current-capital-plan/{id}', tags=['Organizations'])
async def get_org_current_capital_plan(id: str):
    """The CURRENT Capital Commitment Plan rows for an organization.

    ⚠⚠ WHY A SECOND TABLE RATHER THAN A REPLACEMENT. The Capital Projects tab is
    built on `capitalprojectsdollarscomp`, which NYC RETIRED in October 2023 — it
    is `is_active=false`, carries no socrata_id, has never been ingested, and its
    newest PUB_DATE is 20231026. So every agency's tab has shown ~3-year-old data.
    The successor (`capitalprojectslist`, ccpversion fisa_2026, ingested
    2026-08-25) is live and larger — 12,905 projects against 8,740, 28 orgs
    against 25.

    ⚠ BUT IT IS NOT A DROP-IN, WHICH IS WHY BOTH TABLES NOW APPEAR. Measured: the
    live table has NO LAT/LNG/GEO_JSON (the tab's map depends on them), no BORO,
    no SCOPE_TEXT, no BUDG_ORIG/CURR/DIFF (the "Budget Change %" column), no
    START/END/DURATION _ORIG/_DIFF (the "Timeline Change" column) and none of the
    wegov project-type taxonomy. Swapping would have silently deleted the map and
    five columns from 25 agency pages. No other current table carries them either
    — capitalcommitmentplan, capitalcommitmentactuals and capitalstrategy were all
    checked and none has geo, scope or borough.

    ⚠ `plannedcommit_total` is the headline money column because it is the best
    populated: measured across 12,929 rows, plannedcommit_total > 0 on 9,213,
    spent_total on 7,118 and commit_total on only 5,158. A zero here is usually
    REAL rather than missing — EDC's projects are future-dated lump sums starting
    2026-2031, so they legitimately carry no commitment yet.
    """
    return await select("""
        SELECT ccpversion, projectid, magencyacro, magency, description,
               typecategory, mindate, maxdate,
               plannedcommit_total, commit_total, spent_total,
               spent_total_checkbooknyc
        FROM capitalprojectslist
        WHERE "wegov-org-id"::text = $1
        ORDER BY
          CASE WHEN plannedcommit_total ~ '^[0-9.]+$'
               THEN plannedcommit_total::numeric ELSE 0 END DESC
        LIMIT 10000
    """, (str(id),))


@app.get('/get/orgs/ccmember/{id}', tags=['Organizations'])
async def get_city_council_member_related_to_organization(id: str):
    return await select("SELECT * FROM ccmembers WHERE \"wegov-org-id\"=$1", (id,))


# ---- stats --------
@app.get('/get/orgs/stats-reg/{id}/{tbl}', tags=['Organizations'])
async def organization_subdataset_number_stats(id: str, tbl: str):
    # Tables without the wegov-org-id column → count 0 rather than 500.
    try:
        return await select("SELECT count(*) FROM {} WHERE \"wegov-org-id\"=$1".format(_safe_table(tbl)), (id,))
    except (asyncpg.exceptions.UndefinedColumnError, asyncpg.exceptions.UndefinedTableError):
        return [{"count": 0}]

@app.get('/get/orgs/stats-notices/{id}/{crolsection}', tags=['Organizations'])
async def organization_notices_number_stats(id: str, crolsection: str):
    return await select("SELECT count(*) FROM crol WHERE \"wegov-org-id\"=$1 AND \"SectionName\"=$2", (id, crolsection))

@app.get('/get/orgs/stats-events/{id}', tags=['Organizations'])
async def organization_events_number_stats(id: str):
    return await select("SELECT count(*) FROM crol WHERE \"wegov-org-id\"=$1 AND NOT \"EventDate\" = ''", (id,))

@app.get('/get/orgs/stats-headcount/{id}/{fyear}', tags=['Organizations'])
async def organization_headcount_number_stats(id: str, fyear: str):
    return await select("SELECT sum(\"HEADCOUNT\"::numeric) FROM headcountactualsfunding WHERE \"wegov-org-id\"=$1 AND \"FISCAL YEAR\"=$2", (id, fyear))

@app.get('/get/orgs/stats-as/{id}/{fyear}', tags=['Organizations'])
async def organization_actual_spending_stats(id: str, fyear: str):
    return await select("SELECT sum(\"AMOUNT\"::numeric * 1000) FROM expenseactualsfunding WHERE \"wegov-org-id\"=$1 AND \"FISCAL YEAR\"=$2", (id, fyear))

@app.get('/get/orgs/stats-ac/{id}/{fyear}', tags=['Organizations'])
async def organization_additional_cost_stats(id: str, fyear: str):
    return await select("SELECT sum(\"TOTAL AMOUNT\"::numeric * 1000) FROM additionalcostsallocation WHERE \"wegov-org-id\"=$1 AND \"FISCAL YEAR\"=$2", (id, fyear))


@app.get('/get/orgs/pstats-union/{id}', tags=['Organizations'])
async def organization_projects_union_stats(id: str):
    r"""The eight project stat tiles for an org matched by TEXT, not by org id.

    ⚠⚠ WHY THE EXISTING TILES ARE BLANK HERE. All eight `pstats-*` endpoints read
    `capitalprojectsdollarscomp WHERE "wegov-org-id" = $1 AND "PUB_DATE" = $2`.
    A body with no capital budget line of its own has ZERO rows under its id, and
    the publication-date selector those tiles read is populated from the very
    table that came back empty — so the pubdate is the empty string too. Two
    reasons for nothing, neither of them visible to a reader.

    ⚠⚠ THE DENOMINATOR IS NOT THE UNION, AND THE PAGE MUST SAY SO. Budget and
    schedule variance exist ONLY in the retired series: the current plan publishes
    no original-vs-current budget and no start/end variance at all. For NYCEDC
    that is 15 of the union's 20 projects. `budget_basis` is returned so the page
    can state the denominator rather than implying these figures cover every row
    in the table above them.

    ⚠ `projects_no` is deliberately NOT returned. The page already has that number
    — it is the length of the union list it just rendered — and computing it a
    second time here is exactly how the note came to say 15 above a table of 9.
    One number, one owner.

    ⚠ Deduped to the NEWEST publication per project, the same rows the union's
    `budget_usd` column shows, so a reader can add up the column and land on
    `curr_cost`.

    ⚠ MIXED COLUMN TYPES IN ONE TABLE: `BUDG_ORIG` is `numeric` while `BUDG_CURR`,
    `BUDG_DIFF`, `DURATION_DIFF`, `START_DIFF` and `END_DIFF` are text-like and
    hold '' and '-'. Guarding them all the same way raises
    `invalid input syntax for type numeric: ""` on the numeric one.
    """
    from modules import orgprojecttokens
    token = orgprojecttokens.token_for(id)
    if not token:
        return {"rows": [], "available": False}
    pattern = r'\m' + token + r'\M'
    return await select("""
        WITH ret AS (
          SELECT DISTINCT ON (btrim("PROJECT_ID")) *
          FROM capitalprojectsdollarscomp
          WHERE "PROJECT_DESCR" ~* $1 OR "SCOPE_TEXT" ~* $1
          ORDER BY btrim("PROJECT_ID"), "PUB_DATE" DESC
        )
        SELECT count(*)                                              AS budget_basis,
               round(sum("BUDG_ORIG") * 1000)                        AS orig_cost,
               round(sum(CASE WHEN btrim("BUDG_CURR") ~ '^-?[0-9.]+$'
                              THEN btrim("BUDG_CURR")::numeric END) * 1000) AS curr_cost,
               round(-sum(CASE WHEN btrim("BUDG_DIFF") ~ '^-?[0-9.]+$'
                               THEN btrim("BUDG_DIFF")::numeric END) * 1000) AS over_budg_am,
               count(*) FILTER (WHERE btrim("BUDG_DIFF") ~ '^-?[0-9.]+$'
                                  AND btrim("BUDG_DIFF")::numeric < 0)      AS over_budg_no,
               count(*) FILTER (WHERE btrim("DURATION_DIFF") ~ '^-?[0-9.]+$'
                                  AND btrim("DURATION_DIFF")::numeric < 0)  AS long_no,
               count(*) FILTER (WHERE btrim("START_DIFF") ~ '^-?[0-9.]+$'
                                  AND btrim("START_DIFF")::numeric < 0)     AS late_start_no,
               count(*) FILTER (WHERE btrim("END_DIFF") ~ '^-?[0-9.]+$'
                                  AND btrim("END_DIFF")::numeric < 0)       AS late_end_no
        FROM ret
    """, (pattern,))

# ⚠⚠ THE EIGHT PER-PUBLICATION-DATE `pstats-*` ENDPOINTS THAT STOOD HERE ARE
# DELETED (2026-09-10), and so are their citywide and per-district twins below —
# 24 routes over `capitalprojectsdollarscomp`, the series NYC retired
# 2023-10-26. Every one served ONE number for ONE publication date:
# projects_no · orig_cost · curr_cost · over_budg_am · long_no · over_budg_no ·
# late_start_no · late_end_no.
#
# ⭐ THEY WERE PROVED UNUSED BEFORE REMOVAL, not assumed. Their sole callers were
# the `finStatUrls` / `pstats-*` hydration arrays on the org capital tab, the
# district capital tab and `/projects`, and all three were deleted when those
# surfaces moved to the spine (`9516a75`, and the tab migrations before it). A
# tree-wide scan for each route now finds it in exactly two kinds of place: a
# COMMENT in `app/` saying the URL was removed, and a GUARD asserting it is
# absent (`test_district_capital_tab.py` bans `pstats-orig_cost` from the view).
# Neither is a consumer. Nothing in `app/`, `mcp_server.py`, `routers/`,
# `chatbot.py`, `public_v1.py` or `scripts/` builds one.
#
# ⚠ THE POINT IS NOT TIDINESS — it is `over_budg_am`. That measure is `Amount
# Over Budget`, the label this section retired for carrying two definitions, and
# these routes are the last place its arithmetic still lives. A dead endpoint
# publishing a retired label is a loaded template: the next page written from it
# republishes the defect, which is what the org capital tab already did for
# weeks. `/get/orgs/pstats-union/{id}` stays — it is LIVE, it is labelled as the
# 2023 series on the page, and it serves the whole row in one query.

# ---- time-series stats for organization profile --------

@app.get('/get/orgs/stats-headcount/{id}', tags=['Organizations'])
async def organization_headcount_timeseries(id: str):
    return await select("SELECT \"FISCAL YEAR\" as year, sum(\"HEADCOUNT\"::numeric) as v FROM headcountactualsfunding WHERE \"wegov-org-id\"=$1 GROUP BY \"FISCAL YEAR\" ORDER BY \"FISCAL YEAR\"", (id,))

@app.get('/get/orgs/stats-pastheadcount/{id}', tags=['Organizations'])
async def organization_past_headcount_timeseries(id: str):
    return await select("SELECT \"CALENDAR YEAR\" as year, count(*) as v FROM civillist WHERE \"wegov-org-id\"=$1 GROUP BY \"CALENDAR YEAR\" ORDER BY \"CALENDAR YEAR\"", (id,))

@app.get('/get/orgs/stats-as/{id}', tags=['Organizations'])
async def organization_actual_spending_timeseries(id: str):
    return await select("SELECT \"FISCAL YEAR\" as year, sum(\"AMOUNT\"::numeric * 1000) as v FROM expenseactualsfunding WHERE \"wegov-org-id\"=$1 GROUP BY \"FISCAL YEAR\" ORDER BY \"FISCAL YEAR\"", (id,))

@app.get('/get/orgs/stats-ac/{id}', tags=['Organizations'])
async def organization_additional_cost_timeseries(id: str):
    return await select("SELECT \"FISCAL YEAR\" as year, sum(\"TOTAL AMOUNT\"::numeric * 1000) as v FROM additionalcostsallocation WHERE \"wegov-org-id\"=$1 GROUP BY \"FISCAL YEAR\" ORDER BY \"FISCAL YEAR\"", (id,))

@app.get('/get/orgs/stats-prj/{id}', tags=['Organizations'])
async def organization_project_stats_timeseries(id: str):
    return await select("SELECT \"PUB_DATE\" as pub_date, sum(cast(REPLACE(\"BUDG_CURR\", ',', '.') as decimal)) as budg_curr, -sum(cast(REPLACE(\"BUDG_DIFF\", ',', '.') as decimal)) as budg_diff FROM capitalprojectsdollarscomp WHERE \"wegov-org-id\"=$1 GROUP BY \"PUB_DATE\" ORDER BY \"PUB_DATE\"", (id,))

@app.get('/get/orgs/stats-civillist-aggregated/{id}', tags=['Organizations'])
async def organization_civillist_aggregated(id: str):
    # civillist has ~3.2M rows with text SALARY RATE (e.g. "$ 81,184.00") — needs
    # regexp_replace + SUM which exceeds the 15s global statement_timeout.
    sql = 'SELECT "TITLE CODE" as title, SUM(cast(regexp_replace("SALARY RATE", \'[$,]\', \'\', \'g\') as numeric)) as sum FROM civillist WHERE "wegov-org-id"=$1 GROUP BY "TITLE CODE" ORDER BY sum DESC LIMIT 10'
    rr = await PostgresModelAsync.select_safe_with_timeout(sql, [id], timeout_seconds=60)
    return {'rows': json.loads(PostgresModelAsync.jsonsafe(rr))}

# ---- notices --------

@app.get('/get/orgs/frontnews/{id}', tags=['Organizations'])
async def organization_future_news(id: str):
    return await select("SELECT \"StartDate\", \"EndDate\", \"SectionName\", \"ShortTitle\", \"RequestID\", \"TypeOfNoticeDescription\", \"wegov-org-name\", \"wegov-org-id\" FROM crol WHERE \"wegov-org-id\" = $1 AND \"EventDate\" = '' ORDER BY \"StartDate\" DESC LIMIT 9", (id,))
            
@app.get('/get/orgs/frontevents/{id}', tags=['Organizations'])
async def organization_future_events(id: str):
    return await select("SELECT \"StartDate\", \"EndDate\", \"SectionName\", \"ShortTitle\", \"RequestID\" FROM crol WHERE \"wegov-org-id\" = $1 AND \"EventDate\" <> '' ORDER BY \"EventDate\" DESC LIMIT 9", (id,))

@app.get('/get/orgs/notices/{id}', tags=['Organizations'])
async def organization_all_notices(id: str):
    return await select("SELECT * FROM crol WHERE \"wegov-org-id\"=$1 ORDER BY date(\"StartDate\")", (id,))
            
@app.get('/get/orgs/changeofpersonnel/{id}', tags=['Organizations'])
async def organization_change_of_personnel_notices(id: str):
    return await select("SELECT * FROM crol WHERE \"wegov-org-id\"=$1 AND \"SectionName\"='Changes in Personnel' ORDER BY date(\"StartDate\")", (id,))
            
@app.get('/get/orgs/publichearings/{id}', tags=['Organizations'])
async def organization_public_hearings_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Public Hearings and Meetings\'', (id,))
            
@app.get('/get/orgs/contractawards/{id}', tags=['Organizations'])
async def organization_contract_awards_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Contract Award Hearings\'', (id,))
            
@app.get('/get/orgs/specialmaterials/{id}', tags=['Organizations'])
async def organization_special_materials_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Special Materials\'', (id,))
            
@app.get('/get/orgs/agencyrules/{id}', tags=['Organizations'])
async def organization_agency_rules_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Agency Rules\'', (id,))
            
@app.get('/get/orgs/propertydisposition/{id}', tags=['Organizations'])
async def organization_property_disposition_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Property Disposition\'', (id,))
            
@app.get('/get/orgs/courtnotices/{id}', tags=['Organizations'])
async def organization_court_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Court Notices\'', (id,))
            
@app.get('/get/orgs/procurement/{id}', tags=['Organizations'])
async def organization_procurement_notices(id: str):
    return await select('SELECT "RequestID", "StartDate", "wegov-org-name", "TypeOfNoticeDescription", "CategoryDescription", "ShortTitle", "SelectionMethodDescription", "AdditionalDescription1", "SpecialCaseReasonDescription", "PIN", "DueDate", "EndDate", "AddressToRequest", "ContactName", "ContactPhone", "Email", "ContractAmount", "ContactFax", "OtherInfo1", "VendorName", "VendorAddress", "Printout1", "DocumentLinks", "EventBuildingName", "EventStreetAddress1" FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Procurement\'', (id,))
            
@app.get('/get/orgs/events/{id}', tags=['Organizations'])
async def organization_events_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND NOT "EventDate" = \'\' ORDER BY date("EventDate") DESC', (id,))

@app.get('/get/orgs/icalevents/{id}', tags=['Event Feeds'])
async def organization_ical_events_feed(id: str):
    return await select("SELECT * FROM crol WHERE \"wegov-org-id\"=$1 AND NOT \"EventDate\" = '' AND DATE(\"EventDate\") >= DATE(NOW() - INTERVAL '1 week') ORDER BY date(\"EventDate\") DESC", (id,))

@app.get('/get/orgs/rssnews/{id}', tags=['Event Feeds'])
async def organization_rss_news_feed(id: str):
    return await select("SELECT c.* FROM crol c WHERE \"wegov-org-id\"=$1 AND \"EventDate\" = '' AND DATE(\"StartDate\") >= DATE(NOW() - INTERVAL '1 week') ORDER BY date(\"StartDate\") DESC", (id,))



# ================ capital projects ================

@app.get('/get/capitalprojects/all/{pubdate}', tags=['Capital Projects'])
async def get_capital_projects_by_year(pubdate: str):
    return await select("SELECT * FROM capitalprojectsdollarscomp WHERE \"PUB_DATE\" = $1", (pubdate, ))

# ⚠ The eight citywide `/get/pstats-{measure}/{pubdate}` routes were deleted here
# 2026-09-10 with their org and district twins — see the note above
# `# ---- time-series stats for organization profile`. Unused, and the set
# included `over_budg_am`.

@app.get('/get/capitalprojects/milestones/{prjid}', tags=['Capital Projects'])
async def get_capital_project_milestones(prjid: str):
    return await select("SELECT * FROM capitalprojectsmilestones WHERE \"PROJECT_ID\" = $1 order by \"PUB_DATE\" DESC", (prjid, ))

@app.get('/get/capitalprojects/dates', tags=['Capital Projects'])
async def get_capital_projects_years_list():
    return await select("SELECT DISTINCT \"PUB_DATE\" FROM capitalprojectsdollarscomp ORDER BY \"PUB_DATE\" DESC")

@app.get('/get/capitalprojects/geojson', tags=['Capital Projects'])
async def get_capital_project_all_geodata():
    return await select('SELECT "GEO_JSON", "wegov-org-id" FROM capitalprojectsdollarscomp WHERE "PUB_DATE" = (SELECT DISTINCT "PUB_DATE" pd FROM capitalprojectsdollarscomp ORDER BY pd DESC LIMIT 1) AND "GEO_JSON" != \'\'')

@app.get('/get/capitalprojects/core/{prjid}', tags=['Capital Projects'])
async def get_capital_project_core(prjid: str):
    """Fetch a single capital project profile by ID.

    Why: Map popup links use maprojid format (e.g. '826WI-298-B') but the DB
    stores PROJECT_ID without the 3-digit agency prefix ('WI-298-B'). Try the
    exact ID first, then fall back to stripping the prefix.

    ⚠⚠ THE COALESCES ARE LOAD-BEARING AND MUST STAY LAST. `SELECT t1.*, t2.*`
    across a LEFT JOIN emits `wegov-org-id` and `wegov-org-name` TWICE — those
    are the only two columns the tables share — and `dict(record)` keeps the
    LAST. So for a project with no row in `capitalprojectslist` the unmatched
    side's NULL silently overwrote the real org id.

    That id is what the project page resolves its organization from, so the page
    aborted to the "Databook is briefly unavailable" view: a PERMANENT data
    condition wearing the costume of a transient outage, on a page that
    auto-retries forever. Measured before the fix: **2,433 of 8,740 project
    pages** (28%) could never load. Found from one link on the NYCEDC page.

    ⚠ Appending the coalesces relies on the same last-wins behaviour that caused
    the bug — which is exactly why it works, and why a guard runs the real
    function and asserts a non-joining project still resolves its org.

    ⚠⚠ THE COALESCE ORDER IS t2-FIRST, AND IT IS NOW MEASURED RATHER THAN MERELY
    CONSERVATIVE. The two tables disagree about which agency runs a project on
    **2,786 of 59,652 joining rows / 525 distinct projects**, and every one of
    those rows disagrees on the agency NAME too — so it was never an enrichment
    bug. `capitalprojectslist` (2026) is the CORRECT side:

      · restricted to the newest 2023 publication the disagreement is 232, not 525
      · agreement with the 2026 plan RISES as the 2023 data gets newer —
        5,792 of 6,323 at its oldest publication, 6,091 at its newest
      · of the 319 projects whose agency changed WITHIN the 2023 series' own 14
        publications, **307 (96%) ended up matching the 2026 plan and 8 moved
        away** — the retired series is converging on it

    The residual is real-world reassignment to construction-delivery bodies:
    DDC 110+, Brooklyn Navy Yard 48, Trust for Governors Island 19, and DDC's
    managed portfolio grows 1,510 -> 2,202 between the two datasets. Neither
    table has a separate sponsor column and both use DDC as a managing agency at
    scale, so this is not one table meaning "sponsor" and the other "manager" —
    it is management genuinely transferring.

    So t2-first is the RIGHT answer, not just the safe one, and t1 fills in only
    where t2 is NULL.

    ⚠ `t1."wegov-org-id"` is `numeric` and `t2."wegov-org-id"` is `text`, so the
    cast is required — an uncast coalesce raises
    `COALESCE types numeric and text cannot be matched` and 500s the endpoint.
    Casting t1 to text (rather than t2 to numeric) keeps the payload's type
    exactly what joining projects already return.

    ⚠ Blank-padding is NOT a factor here, measured rather than assumed: the join
    is `character = text`, and 6,307 projects join with or without btrim.
    """
    result = await select("SELECT t1.*, t2.*, coalesce(t2.\"wegov-org-id\", t1.\"wegov-org-id\"::text) AS \"wegov-org-id\", coalesce(t2.\"wegov-org-name\", t1.\"wegov-org-name\") AS \"wegov-org-name\" FROM capitalprojectsdollarscomp t1 LEFT JOIN capitalprojectslist t2 ON t1.\"PROJECT_ID\" = t2.\"projectid\" WHERE t1.\"PROJECT_ID\" = $1 order by t1.\"PUB_DATE\" DESC LIMIT 1", (prjid, ))
    if not result.get('rows'):
        # Try stripping 3-digit managing agency prefix (maprojid → projectid)
        stripped = prjid[3:] if len(prjid) > 3 and prjid[:3].isdigit() else prjid
        if stripped != prjid:
            result = await select("SELECT t1.*, t2.*, coalesce(t2.\"wegov-org-id\", t1.\"wegov-org-id\"::text) AS \"wegov-org-id\", coalesce(t2.\"wegov-org-name\", t1.\"wegov-org-name\") AS \"wegov-org-name\" FROM capitalprojectsdollarscomp t1 LEFT JOIN capitalprojectslist t2 ON t1.\"PROJECT_ID\" = t2.\"projectid\" WHERE t1.\"PROJECT_ID\" = $1 order by t1.\"PUB_DATE\" DESC LIMIT 1", (stripped, ))
    if not result.get('rows'):
        # Fallback: ~6.3K projects live in capitalprojectslist but have no row in
        # the capital-commitment-plan *dollars* dataset (unbudgeted / planning-stage).
        # Return the list row tagged _source='list' so the frontend renders the
        # reduced project page (no dollars/schedule time-series) instead of 404ing.
        result = await select("SELECT *, 'list' AS _source FROM capitalprojectslist WHERE \"maprojid\" = $1 OR \"projectid\" = $1 LIMIT 1", (prjid, ))
    return result

@app.get('/get/capitalprojects/commitments/{prjid}', tags=['Capital Projects'])
async def get_capital_project_commitments(prjid: str):
    # Match either id form: callers pass maprojid (e.g. 858DOIT5MYSM) or the
    # prefix-stripped projectid (DOIT5MYSM); the table carries both columns.
    return await select("SELECT * FROM capitalprojectscommitments WHERE \"projectid\" = $1 OR \"maprojid\" = $1", (prjid, ))

@app.get('/get/capitalprojects/budgetandspend/{prjid}', tags=['Capital Projects'])
async def get_capital_project_budget_and_spend(prjid: str):
    return await select("SELECT * FROM capprojectsbudgetandspend WHERE \"FMS ID\" = $1", (prjid, ))

@app.get('/get/capitalprojects/budgetspendhistory/{prjid}', tags=['Capital Projects'])
async def get_capital_project_budget_spend_history(prjid: str):
    return await select("SELECT * FROM capprojectsbudgetspendhistory WHERE \"FMS ID\" = $1", (prjid, ))

@app.get('/get/capitalprojects/budgetsandschedule/{prjid}', tags=['Capital Projects'])
async def get_capital_project_budgets_and_schedule(prjid: str):
    return await select("SELECT * FROM capprojectsbudgetsandschedule WHERE \"FMS ID\" = $1", (prjid, ))

@app.get('/get/capitalprojects/schedulehistory/{agcy_cd}', tags=['Capital Projects'])
async def get_capital_project_schedule_history(agcy_cd: str):
    return await select("SELECT * FROM capprojectsschedulehistory WHERE \"Managing Agency\" = $1", (agcy_cd, ))

_projects_map_cache: dict = None
_projects_map_cache_time: float = 0.0

_PROJECTS_MAP_SQL = '''
    SELECT
        t1."PROJECT_ID",
        t1."PROJECT_DESCR",
        t1."GEO_JSON",
        t1."LAT" AS lat,
        t1."LNG" AS lng,
        t1."BUDG_CURR" AS "PLANNEDCOST",
        t1."START_ORIG",
        t1."END_CURR",
        t1."BORO",
        t1."TYP_CATEGORY_NAME" AS "CATEGORY",
        t1."wegov-project-type-names" AS "wegov-prjtype-name",
        t1."wegov-project-category" AS "wegov-prj-color",
        t1."wegov-org-name",
        t1."wegov-org-id",
        t2.description AS "description",
        t2.projectid,
        t2.typecategory
    FROM capitalprojectsdollarscomp t1
    LEFT JOIN capitalprojectslist t2 ON t1."PROJECT_ID" = t2.projectid
    WHERE t1."PUB_DATE" = (SELECT max("PUB_DATE") FROM capitalprojectsdollarscomp)
'''

async def _load_projects_map_cache():
    """Load (or refresh) the projects map cache. Runs at startup and every 6 hours.

    Why: capitalprojectsdollarscomp has 5k rows with large GEO_JSON TOAST values
    that take >15s to read, exceeding Postgres statement_timeout. Caching at app-level
    sidesteps the timeout entirely and makes map loads instant for all users.
    """
    import time
    global _projects_map_cache, _projects_map_cache_time
    try:
        rows = await PostgresModelAsync.select_safe_with_timeout(_PROJECTS_MAP_SQL, [], timeout_seconds=120)
        _projects_map_cache = {'rows': rows}
        _projects_map_cache_time = time.time()
        print(f"[projects cache] Loaded {len(rows)} projects into map cache.")
    except Exception as e:
        print(f"[projects cache] Failed to load: {exc_str(e)}")

@app.get('/get/capitalprojects/projectsnew', tags=['Capital Projects'])
async def get_capital_projects_new():
    """Serve projects map data from in-memory cache (built at startup, refreshed every 6h).
    
    Why cached: The underlying query reads ~10MB of GEO_JSON TOAST data across 5k rows,
    which consistently exceeds the 15s Postgres statement_timeout.
    """
    import time
    if _projects_map_cache is None:
        return JSONResponse(status_code=503, content={'error': 'Cache loading, please retry in 60s'})
    # Refresh stale cache in background (don't block the response)
    if time.time() - _projects_map_cache_time > 21600:
        import asyncio
        asyncio.create_task(_load_projects_map_cache())
    return _projects_map_cache

@app.get('/get/capitalprojects/mcore/{id}', tags=['Capital Projects'])
async def get_minor_capital_project_core(id: str):
    return await select('SELECT * FROM capitalprojectslist WHERE "maprojid"=$1', (id,))

# ---- stats --------



# ================ Titles =======================

@app.get('/get/titles', tags=['Titles'])
async def get_all_civil_titles():
    return await select('SELECT * FROM nyccivilservicetitles ORDER BY "Title Code"', [])

@app.get('/get/titles/{id}', tags=['Titles'])
async def get_civil_title_profile(id: str):
    return await select("SELECT * FROM nyccivilservicetitles WHERE \"Title Code\" = $1 ORDER BY \"Assignment Level\"", (id, ))

@app.get('/get/titles/{id}/stats-civillist_salaries_by_year', tags=['Titles'])
async def get_salaries_by_year_stats_from_civillist(id: str):
    """Aggregate salary stats by year for the Employees & Salaries chart.

    Why: The titleheader.blade.php chart expects {year, salary, employees} fields.
    """
    return await select("""
        SELECT "CALENDAR YEAR" AS year,
               CAST(SUM(CAST(REGEXP_REPLACE("SALARY RATE", '[$\\s,]', '', 'g') AS REAL)) AS INT) AS salary,
               COUNT(*) AS employees
        FROM civillist
        WHERE "TITLE CODE" = $1
        GROUP BY "CALENDAR YEAR"
        ORDER BY "CALENDAR YEAR"
    """, (id,))

@app.get('/get/titles/{id}/stats-positionschedule_positions_by_agency', tags=['Titles'])
async def get_positions_by_agency_stats(id: str):
    """Aggregate position counts by agency for a given title code."""
    return await select('SELECT "AGENCY NAME" as agency, SUM(CAST("POSITIONS" AS INT)) as positions FROM positionschedule WHERE "TITLE CODE"=$1 AND "PUBLICATION DATE" = (SELECT MAX("PUBLICATION DATE") FROM positionschedule) GROUP BY "AGENCY NAME" ORDER BY positions DESC', (id,))

@app.get('/get/titles/{id}/{tbl}', tags=['Titles'])
async def get_subdataset_related_to_civil_title(id: str, tbl: str):
    # Map table names to their title ID column
    col_map = {
        'positionschedule': 'TITLE CODE',
        'civillist': 'TITLE CODE',
        'nycjobs': 'wegov-service-title-id',
        'civillistactive': 'wegov-service-title-id',
    }
    # ⚠⚠ `tbl` is interpolated as the FROM relation, so it must be one of these.
    # Unguarded, `tbl=users WHERE $1<>'' --` read the api's credential table
    # (found 2026-09-24; tests/test_sql_injection.py). These four are every
    # table the frontend's TitlesDatasets asks for.
    if tbl not in col_map:
        raise HTTPException(status_code=404, detail="Unknown table")
    col = col_map[tbl]
    # positionschedule and civillistactive don't have wegov-org-id
    order_map = {
        'positionschedule': '"AGENCY NAME"',
        'nycjobs': '"wegov-org-id"',
        'civillist': '"wegov-org-id"',
        'civillistactive': '1',
    }
    order_col = order_map.get(tbl, '1')
    # Cap rows. A few title codes map to hundreds of thousands of civillist rows
    # (e.g. 70210 ≈ 262k). SELECT * with no LIMIT materialized the entire set into
    # a Python list of dicts — ~660 MB for a single call, so a few concurrent
    # requests OOM-killed the container (this was THE api crash-loop driver). It
    # also swamps the client-side DataTable. Cap to a browsable window; the title
    # charts use the separate aggregated /stats-* endpoints, so totals are
    # unaffected by this cap.
    _ROW_CAP = 10000
    if tbl == 'civillist':
        return await select(
            'SELECT * FROM civillist WHERE "TITLE CODE"=$1 ORDER BY "wegov-org-id" LIMIT {}'.format(_ROW_CAP),
            (id,))
    return await select('SELECT * FROM {} WHERE "{}"=$1 ORDER BY {} LIMIT {}'.format(tbl, col, order_col, _ROW_CAP), (id,))


# ================ Jobs =======================

_jobs_cache = {"data": None, "ts": 0}

@app.get('/get/jobs/all', tags=['Jobs'], summary="Get all current NYC job postings")
async def get_all_nyc_jobs():
    """Return job postings with only the columns needed for the Jobs page cards.

    Why: SELECT * returns 35+ columns including multi-KB text fields (Job Description,
    Minimum Qual Requirements, Preferred Skills) which bloats the response from ~15MB
    to ~1.6MB and slows client-side parsing. Only card-relevant fields are selected.

    Caching: 15-minute in-memory cache since nycjobs updates daily.
    """
    import time
    now = time.time()
    if _jobs_cache["data"] and (now - _jobs_cache["ts"]) < 900:  # 15 min
        from starlette.responses import JSONResponse
        return JSONResponse(
            content=_jobs_cache["data"],
            headers={"Cache-Control": "public, max-age=300"}
        )

    # Try full query with org enrichment columns first; fall back to base columns
    # if wegov-org-name / wegov-org-id haven't been added to nycjobs yet (e.g. staging).
    try:
        result = await select("""
            SELECT "Job ID", "Business Title", "Civil Service Title", "Agency",
                   "wegov-org-name", "wegov-org-id", "Salary Range From", "Salary Range To",
                   "Salary Frequency", "Posting Type", "Career Level", "Title Code No",
                   "Posting Date", "Post Until", "Full-Time/Part-Time indicator",
                   "Job Category", "Title Classification", "Work Location",
                   "# Of Positions", "Level"
            FROM nycjobs ORDER BY "Posting Date" DESC
        """, [])
    except Exception:
        # Org-enrichment columns missing — return base columns with NULL stubs
        result = await select("""
            SELECT "Job ID", "Business Title", "Civil Service Title", "Agency",
                   NULL AS "wegov-org-name", NULL AS "wegov-org-id",
                   "Salary Range From", "Salary Range To",
                   "Salary Frequency", "Posting Type", "Career Level", "Title Code No",
                   "Posting Date", "Post Until", "Full-Time/Part-Time indicator",
                   "Job Category", "Title Classification", "Work Location",
                   "# Of Positions", "Level"
            FROM nycjobs ORDER BY "Posting Date" DESC
        """, [])

    _jobs_cache["data"] = result
    _jobs_cache["ts"] = now

    from starlette.responses import JSONResponse
    return JSONResponse(
        content=result,
        headers={"Cache-Control": "public, max-age=300"}
    )




# ================ Districts =======================


@app.get('/get/orgs/bycd/{cd}', tags=['Organizations'])
async def get_organization_profile_associated_to_community_district(cd: str):
    #return await select('SELECT "id", "url" FROM wegov_orgs WHERE "communityDistrictId" LIKE $1', (cd,))
    return await select('SELECT * FROM wegov_orgs WHERE "communityDistrictId" = $1' + await _orgs_live(), ('["{}"]'.format(cd),))

@app.get('/get/orgs/bycc/{cc}', tags=['Organizations'])
async def get_organization_profile_associated_to_city_council_district(cc: str):
    #return await select('SELECT "id", "url" FROM wegov_orgs WHERE "cityCouncilDistrictId" LIKE $1', (cc,))
    return await select('SELECT * FROM wegov_orgs WHERE "cityCouncilDistrictId" = $1' + await _orgs_live(), ('["{}"]'.format(cc),))

# ---- fire battalions (spatial) --------
# These MUST be declared before the generic /{type}/{id}/{tbl} route below,
# otherwise FastAPI matches the wildcard first.

@app.get('/get/districts/fb/{id}/fire_causes', tags=['Districts'])
async def get_fire_causes_by_battalion(id: str, limit: int=Query(None, ge=1, le=10000), offset: int=Query(0, ge=0)):
    page_clause = f" LIMIT {int(limit)}" if limit else ""
    page_clause += f" OFFSET {int(offset)}" if offset else ""
    return await select(f'SELECT * FROM fire_causes WHERE "battalion_id" = $1{page_clause}', (id,))

@app.get('/get/districts/fb/{id}/fire_inspections', tags=['Districts'])
async def get_fire_inspections_by_battalion(id: str, limit: int=Query(None, ge=1, le=10000), offset: int=Query(0, ge=0)):
    page_clause = f" LIMIT {int(limit)}" if limit else ""
    page_clause += f" OFFSET {int(offset)}" if offset else ""
    return await select(f'SELECT * FROM fdny_inspections WHERE "battalion_id" = $1{page_clause}', (id,))

@app.get('/get/districts/fb/{id}/fire_violations', tags=['Districts'])
async def get_fire_violations_by_battalion(id: str, limit: int=Query(None, ge=1, le=10000), offset: int=Query(0, ge=0)):
    page_clause = f" LIMIT {int(limit)}" if limit else ""
    page_clause += f" OFFSET {int(offset)}" if offset else ""
    return await select(f'SELECT * FROM fdny_violations WHERE "battalion_id" = $1{page_clause}', (id,))

@app.get('/get/districts/fb/{id}/fire_dispatch', tags=['Districts'])
async def get_fire_dispatch_by_battalion(id: str, limit: int=Query(200, ge=1, le=10000), offset: int=Query(0, ge=0)):
    """Query dispatch records by battalion using array containment.

    Why: battalion_ids is a TEXT[] array because one Police Precinct can
    overlap with multiple Fire Battalions (many-to-many crosswalk).
    Default limit=200 to prevent full-table scans (~35s) on this 600k+ row table.
    """
    page_clause = f" LIMIT {int(limit)}"
    page_clause += f" OFFSET {int(offset)}" if offset else ""
    try:
        return await select(f'SELECT * FROM fire_incident_dispatch WHERE $1 = ANY("battalion_ids"){page_clause}', (id,))
    except Exception:
        return {"rows": [], "note": "fire_incident_dispatch not yet ingested"}


@app.get('/get/districts/{type}/{id}/capitalprojects', tags=['Districts'])
async def get_capital_projects_by_administrative_district(type: str, id: str):
    # `type` is interpolated into the crosswalk table name (capitalprojects_<type>_idx),
    # so guard it to a safe charset to keep the interpolation injection-proof. Crosswalk
    # tables exist for cd/cc/sd; nta has none (2010↔2020 NTA boundaries don't crosswalk —
    # the frontend hides capital projects for nta districts), so a missing table must
    # return empty rather than 500. _district_select tolerates the missing relation.
    if not re.fullmatch(r"[a-z]{2,4}", type):
        return {"rows": []}
    return await _district_select("SELECT pp.*, i.\"DIST\" FROM capitalprojectsdollarscomp pp INNER JOIN capitalprojects_{}_idx i ON pp.\"PROJECT_ID\"=i.\"PROJECT_ID\" WHERE i.\"DIST\" = $1".format(type), (id,))

# Column mapping: which column stores the district identifier for each table + district type.
# Used by the generic district subdataset endpoint to filter rows by district.
# Keys are district types (cd, cc, nta); values map table names to their filter column.
# Lists are used when column names differ between environments (e.g. staging vs production).
DISTRICT_COLUMNS = {
    "cd": {
        "councilstatcases": ["Community Board", "COMMUNITY_BOARD"],
        "nyccouncildiscretionaryfunding": ["Community Board"],
        "budgetrequestsregister": ["Community Board"],
        "facilitydb": ["cd"],
    },
    "cc": {
        "councilstatcases": ["Council District", "COUNCIL_DIST"],
        "nyccouncildiscretionaryfunding": ["Council District"],
        "budgetrequestsregister": ["Council District"],
        "facilitydb": ["council"],
    },
    "sd": {
        # District-grain graduation outcomes (docs/GRADUATION-INGEST-PLAN.md ⚑ B).
        # ⚠ Declared here rather than left to the view's `f=` fallback, which is
        # a CLIENT-supplied column name; the map is consulted first.
        "graduationoutcomes": ["Geographic Subdivision"],
    },
    "nta": {
        # nyccouncildiscretionaryfunding intentionally absent: its NTA column is
        # 2010-vintage (stores 2010 NTA *names*), incompatible with the 2020 NTAs
        # the district pages use. 2010 and 2020 NTAs differ in actual boundaries,
        # not just naming, so there is no valid crosswalk — the section is hidden
        # for the nta district type (see app DistDatasets). Don't re-add without a
        # genuine 2020-vintage NTA column on this table.
        "budgetrequestsregister": ["Neighborhood Tabulation Area (NTA) (2020)"],
        "facilitydb": ["nta2020"],
        # councilstatcases has no NTA column
    },
}

# Borough digit to name mapping for parsing cd IDs (e.g. 101 = Manhattan district 01)
_CD_BOROUGH_NAMES = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}

# Tables where 'Community Board' stores "01 Manhattan" format instead of "101"
_CD_BOROUGH_FORMAT_TABLES = {"councilstatcases"}

# Tables where 'Community Board' stores just the board number ("01" or "1")
_CD_BOARD_ONLY_TABLES = {"budgetrequestsregister"}

# Tables where 'Council District' stores "NYCC001" prefix format
_CC_NYCC_PREFIX_TABLES = {"councilstatcases"}

# Cache resolved column names to avoid repeated schema queries
_resolved_columns: dict = {}

async def _resolve_district_column(tbl: str, candidates: list) -> str:
    """Find the actual column name from a list of candidates by checking the DB schema.

    Why: Column names differ between environments (e.g. 'Community Board' vs 'COMMUNITY_BOARD').
    Caches results so the schema is queried only once per table+candidates combination.
    """
    cache_key = f"{tbl}:{','.join(candidates)}"
    if cache_key in _resolved_columns:
        return _resolved_columns[cache_key]

    if len(candidates) == 1:
        _resolved_columns[cache_key] = candidates[0]
        return candidates[0]

    # Query the DB schema to find which candidate column actually exists
    try:
        result = await select(
            "SELECT column_name FROM information_schema.columns WHERE table_name = $1 AND column_name = ANY($2) LIMIT 1",
            (tbl, candidates))
        if result and "rows" in result and result["rows"]:
            col = result["rows"][0]["column_name"]
            _resolved_columns[cache_key] = col
            return col
    except Exception:
        pass

    # Fallback to first candidate
    _resolved_columns[cache_key] = candidates[0]
    return candidates[0]

async def _district_select(query: str, params: tuple = ()):
    """select() that tolerates the brief window during a table re-import (the
    scheduler's staging-swap drops/renames the table), returning empty instead
    of a 500 if the table/column momentarily isn't there."""
    try:
        return await select(query, params)
    except (asyncpg.exceptions.UndefinedColumnError, asyncpg.exceptions.UndefinedTableError):
        return {"rows": []}

# ⚠⚠ A SECOND, FIXED PREDICATE FOR TABLES THAT STACK SEVERAL GRAINS IN ONE
# TABLE UNDER ONE KEY COLUMN. `graduationoutcomes` holds School / District /
# Borough / Charter School / Citywide / Transfer School rows all keyed on
# `Geographic Subdivision`, and `get_school_section` already carries the
# equivalent map for the School half.
#
# ⚠ Measured 2026-09-21: at District grain the key is a BARE NUMBER (1-32) while
# every other grain is a DBN, a borough name or "Citywide", so today no district
# id collides and `Geographic Subdivision='2'` returns 686 rows either way. That
# is a property of the DATA, not of the schema — the School half DOES collide
# (54 of 497 DBNs also appear as Transfer School). Filtering explicitly makes the
# grain a guarantee rather than a coincidence a later publication could remove.
#
# ⚠ Values are CONSTANTS declared here, never anything the caller supplies.
_DISTRICT_FIXED_FILTERS = {
    'graduationoutcomes': ('Report Category', 'District'),
}

# ⚠⚠ `tbl` is interpolated as the FROM relation and `f`/`sort` as quoted
# identifiers, all straight from the URL. Unguarded, `tbl=pg_user WHERE $1<>'' --`
# read any relation the api role can see, and an embedded `"` in `sort` broke out
# of its identifier (found 2026-09-24; tests/test_sql_injection.py). The allowlist
# is every table the frontend's DistDatasets serves plus every mapped table;
# a test keeps it in step with DistDatasets.php.
_DISTRICT_TABLES = frozenset({
    'budgetrequestsregister', 'capital_projects', 'councilstatcases', 'demographics',
    'facilitydb', 'graduationoutcomes', 'nyccouncildiscretionaryfunding',
    'scacapitalprojectschedules', 'scademostats', 'schoollocations',
}) | frozenset(t for m in DISTRICT_COLUMNS.values() for t in m)


def _ident_body(name: str) -> str:
    """`name` made safe to sit between double quotes: an embedded `"` is doubled,
    which is how Postgres escapes one inside a quoted identifier."""
    return name.replace('"', '""')


@app.get('/get/districts/{type}/{id}/{tbl}', tags=['Districts'])
async def get_subdataset_by_administrative_district(type: str, tbl: str, id: str, sort: str=Query(None), f: str=Query(None), limit: int=Query(None, ge=1, le=10000), offset: int=Query(0, ge=0)):
    """Get rows from a table filtered by district type and id.

    Why: The filter column varies per table. DISTRICT_COLUMNS provides the
    mapping; the `f` query param is a legacy fallback for tables not in the map.
    Value formats also differ: facilitydb stores cd as '101', councilstatcases
    stores '01 Manhattan', budgetrequestsregister stores '01'.
    """
    if tbl not in _DISTRICT_TABLES:
        raise HTTPException(status_code=404, detail="Unknown table")
    # Determine which column to filter on
    candidates = DISTRICT_COLUMNS.get(type, {}).get(tbl)
    if not candidates:
        if not f:
            return {"rows": [], "error": f"No column mapping for table '{tbl}' with district type '{type}'"}
        col = _ident_body(f)
    else:
        col = await _resolve_district_column(tbl, candidates)

    # Build ORDER BY clause (optional)
    order_clause = ""
    if sort and ',' in sort:
        s1, s2 = sort.split(',', 1)
        order_clause = ' ORDER BY "{}", "{}"'.format(
            _ident_body(s1.strip().strip('"')), _ident_body(s2.strip().strip('"')))

    # Build pagination clause
    page_clause = ""
    if limit is not None:
        page_clause = f" LIMIT {int(limit)}"
    if offset:
        page_clause += f" OFFSET {int(offset)}"

    # Handle cd value format differences
    if type == "cd" and len(id) == 3 and tbl in _CD_BOROUGH_FORMAT_TABLES:
        # Convert 101 → "01 Manhattan" (LIKE match for leading-zero/no-leading-zero variants)
        boro_digit = id[0]
        district_num = id[1:]  # "01"
        boro_name = _CD_BOROUGH_NAMES.get(boro_digit, "")
        # Match both "01 Manhattan" and "1 Manhattan" variants
        district_int = str(int(district_num))  # strip leading zero: "01" → "1"
        like_pattern = f"%{boro_name}"
        return await _district_select(
            'SELECT * FROM {} WHERE "{}" LIKE $1 AND (SPLIT_PART("{}", \' \', 1) = $2 OR SPLIT_PART("{}", \' \', 1) = $3){}{}'.format(
                sourcedupes.relation(tbl), col, col, col, order_clause, page_clause),
            (like_pattern, district_num, district_int))

    if type == "cd" and len(id) == 3 and tbl in _CD_BOARD_ONLY_TABLES:
        # Convert 101 → match "01" or "1" (board number only, no borough)
        district_num = id[1:]  # "01"
        district_int = str(int(district_num))  # "1"
        return await _district_select(
            'SELECT * FROM {} WHERE "{}" = $1 OR "{}" = $2{}{}'.format(sourcedupes.relation(tbl), col, col, order_clause, page_clause),
            (district_num, district_int))

    # Handle cc value format differences
    if type == "cc" and tbl in _CC_NYCC_PREFIX_TABLES:
        # councilstatcases stores council district as "NYCC001", "NYCC01", "NYCC1"
        # Try all zero-padded variants: NYCC001, NYCC01, NYCC1
        padded3 = id.zfill(3)   # "001"
        padded2 = id.zfill(2)   # "01"
        raw = str(int(id)) if id.isdigit() else id  # "1"
        return await _district_select(
            'SELECT * FROM {} WHERE "{}" IN ($1, $2, $3){}{}'.format(sourcedupes.relation(tbl), col, order_clause, page_clause),
            (f"NYCC{padded3}", f"NYCC{padded2}", f"NYCC{raw}"))

    fixed = _DISTRICT_FIXED_FILTERS.get(tbl)
    if fixed:
        fcol, fval = fixed
        return await _district_select(
            'SELECT * FROM {} WHERE "{}"=$1 AND "{}"=$2{}{}'.format(
                sourcedupes.relation(tbl), col, fcol, order_clause, page_clause),
            (id, fval))

    return await _district_select('SELECT * FROM {} WHERE "{}"=$1{}{}'.format(sourcedupes.relation(tbl), col, order_clause, page_clause), (id,))


# ⚠ The eight `/get/districts/pstats-{measure}/{type}/{id}/{pubdate}` routes and
# their `_pstats_select` helper were deleted here 2026-09-10 — the helper had no
# other caller, and leaving a helper whose every caller is gone is how a future
# reader concludes the endpoints must still exist somewhere.
# ⚠ `_district_select` is NOT that: it still serves the live district tables.

# ================ notices =======================

@app.get('/get/notices/frontnews', tags=['Notices'])
async def get_all_future_news():
    return await select("SELECT \"StartDate\", \"EndDate\", \"SectionName\", \"ShortTitle\", \"RequestID\" , \"TypeOfNoticeDescription\", \"wegov-org-name\", \"wegov-org-id\" FROM crol WHERE \"EventDate\" = '' AND start_date_parsed::date >= current_date - INTERVAL '7 days' order by start_date_parsed DESC LIMIT 9", [])

@app.get('/get/notices/frontevents', tags=['Notices'])
async def get_all_future_events():
    return await select("""SELECT "StartDate", "EndDate", "SectionName", "ShortTitle", "RequestID", "EventDate", "TypeOfNoticeDescription", "wegov-org-name", "wegov-org-id" FROM crol WHERE event_date_parsed IS NOT NULL AND event_date_parsed >= current_date ORDER BY event_date_parsed LIMIT 9""", [])

@app.get('/get/notices/last30daysstats', tags=['Notices'])
async def get_last30days_stats():
    return await select("""
        SELECT "SectionName", start_date_parsed as "StartDate", COUNT(*) as count FROM crol 
        WHERE "EventDate" = '' AND start_date_parsed::date >= current_date - INTERVAL '30 days'
        GROUP BY "SectionName", start_date_parsed
        ORDER BY start_date_parsed
    """, [])

@app.get('/get/notices/years', tags=['Notices'])
async def get_list_of_notices_year():
    return await select('SELECT DISTINCT(SUBSTRING(\"StartDate\" from 7 for 4)) yy FROM crol ORDER BY yy DESC', [])
            

@app.get('/get/notices/all/{year}', tags=['Notices'])
async def get_all_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "EventDate" = \'\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/changeofpersonnel/{year}', tags=['Notices'])
async def get_change_of_personnel_notices_by_year(year: int):
    return await select('SELECT "AdditionalDescription1", "StartDate", "wegov-org-id", "wegov-org-name" FROM crol WHERE "SectionName" = \'Changes in Personnel\' AND NOT "AdditionalDescription1" = \'\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/publichearings/{year}', tags=['Notices'])
async def get_public_hearings_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Public Hearings and Meetings\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])

@app.get('/get/notices/meetings/{year}', tags=['Notices'])
async def get_meetings_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Public Hearings and Meetings\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/contractawards/{year}', tags=['Notices'])
async def get_contract_awards_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Contract Award Hearings\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/specialmaterials/{year}', tags=['Notices'])
async def get_special_materials_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Special Materials\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/agencyrules/{year}', tags=['Notices'])
async def get_agency_rules_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Agency Rules\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/propertydisposition/{year}', tags=['Notices'])
async def get_property_disposition_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Property Disposition\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/courtnotices/{year}', tags=['Notices'])
async def get_court_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Court Notices\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/procurement/{year}', tags=['Notices'])
async def get_procurement_notices_by_year(year: int):
    # resolved_ctr_id / resolved_epin: forward links from procurement notices to the
    # awarded contract (PIN = contracts.epin, exact) or the solicitation (PIN[:10] = EPIN).
    return await select('SELECT "RequestID", "StartDate", "wegov-org-name", "wegov-org-id", "TypeOfNoticeDescription", "CategoryDescription", "ShortTitle", "SelectionMethodDescription", "AdditionalDescription1", "SpecialCaseReasonDescription", "PIN", "DueDate", "EndDate", "AddressToRequest", "ContactName", "ContactPhone", "Email", "ContractAmount", "ContactFax", "OtherInfo1", "VendorName", "VendorAddress", "Printout1", "DocumentLinks", "EventBuildingName", "EventStreetAddress1", ct.ctr_id AS resolved_ctr_id, s."EPIN" AS resolved_epin FROM crol c LEFT JOIN LATERAL (SELECT ctr_id FROM contracts WHERE epin = trim(c."PIN") LIMIT 1) ct ON true LEFT JOIN LATERAL (SELECT "EPIN" FROM solicitations WHERE "EPIN" = left(trim(c."PIN"),10) LIMIT 1) s ON true WHERE "SectionName" = \'Procurement\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/events/{year}', tags=['Notices'])
async def get_event_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE NOT "EventDate" = \'\' AND SUBSTRING("EventDate" from 7 for 4) = \'{}\''.format(year), [])

@app.get('/get/notices/icalevents', tags=['Notices'])
async def get_events_ical_feed():
    return await select('SELECT * FROM crol WHERE event_date_parsed IS NOT NULL AND event_date_parsed >= current_date - INTERVAL \'1 week\' ORDER BY event_date_parsed DESC', [])

@app.get('/get/notices/rssnews', tags=['Notices'])
async def get_news_rss_feed():
    return await select('SELECT c.* FROM crol c WHERE event_date_parsed IS NULL AND start_date_parsed IS NOT NULL AND start_date_parsed >= current_date - INTERVAL \'1 week\' ORDER BY start_date_parsed DESC', [])

@app.get('/get/notices/lastupdated', tags=['Notices'])
async def get_crol_last_updated():
    """Get the date when CROL data was last ingested into our database."""
    # Try ingestion_log first (most accurate)
    result = await select(
        "SELECT ingested_at FROM ingestion_log WHERE table_name = 'crol' AND status = 'success' ORDER BY ingested_at DESC LIMIT 1"
    )
    if result.get('rows') and result['rows'][0].get('ingested_at'):
        return {'rows': [{'last_updated': result['rows'][0]['ingested_at']}]}
    
    # Fallback: use most recent StartDate from crol table
    result = await select("SELECT MAX(start_date_parsed) as last_updated FROM crol")
    return result


# ---- stats --------
            
@app.get('/get/notices/stats/publichearings/{days}', tags=['Notices'])
async def get_public_hearings_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Public Hearings and Meetings\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/contractawards/{days}', tags=['Notices'])
async def get_contract_awards_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Contract Award Hearings\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/specialmaterials/{days}', tags=['Notices'])
async def get_special_materials_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Special Materials\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/agencyrules/{days}', tags=['Notices'])
async def get_agency_rules_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Agency Rules\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/propertydisposition/{days}', tags=['Notices'])
async def get_property_disposition_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Property Disposition\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/courtnotices/{days}', tags=['Notices'])
async def get_court_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Court Notices\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/procurement/{days}', tags=['Notices'])
async def get_procurement_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Procurement\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/changeofpersonnel/{days}', tags=['Notices'])
async def get_change_of_personnel_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Changes in Personnel\' AND NOT "AdditionalDescription1" = \'\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])



# ================ auctions =======================

@app.get('/get/auctions', tags=['Auctions'])
async def get_all_auctions():
    return await select('SELECT * FROM auctions WHERE date("Auction Ends") >= date(now()) ORDER BY "Auction Ends"', [])

@app.get('/get/frontauctions', tags=['Auctions'])
async def get_future_auctions():
    return await select('SELECT * FROM auctions WHERE date("Auction Ends") > date(now()) ORDER BY "Auction Ends" LIMIT 3', [])




# ================ srv routes ================

@app.post('/login', tags=['Auth'], summary="Authentication entry point", 
        responses={200: {
            'description': 'Access token',
            'content': {'application/json': {'example': {'access_token': 'xxxxxxxxxxxxxxxxxxxxxx', 'token_type': 'bearer'}}}
        }})
def auth(data: OAuth2PasswordRequestForm = Depends()):
    """
    Get authentication token
    """
    email = data.username
    password = data.password

    #user = query_user(email)
    usr = user.get_user(email=email)
    if not usr:
        raise InvalidCredentialsException
    elif User.pwd_hash(password) != usr['pwdhash']:
        raise InvalidCredentialsException

    access_token = manager.create_access_token(
        data={'sub': usr['id']}
        ,expires=datetime.timedelta(hours=24)
        ,scopes=scopes_for(usr.get('scope'))
    )
    return {'access_token': access_token, 'token_type': 'bearer'}


    
def _api_key_ok(header_key: str, query_key: str) -> bool:
    """Config-aware wrapper over the shared resolver.

    The logic — header first, query parameter deprecated-but-accepted with a
    warning, constant-time comparison, fail closed — lives in
    `modules/apikey.py`, because `routers/org_admin.py` needs exactly the same
    check and cannot import from `main` at module scope. There were THREE
    independent comparisons against this secret and they had already drifted:
    org_admin read the query parameter FIRST and compared with `==`.
    """
    return apikey.ok(header_key, query_key, Config.fastapi.get('key', '') or '')


@app.post('/upload', tags=['Datasets'], summary="Upload CSV dataset",
        responses={200: {'description': 'Success', 'content': {'application/json': {'example': {'result': 'OK'}}}},
                   503: {'description': 'Failed', 'content': {'application/json': {'example': {'result': 'Fail'}}}}}
         )
async def upload_csv_dataset(
    url: str = '',
    idxs: str = '',
    api_key: str = None,
    x_api_key: str = Header(None, alias="X-API-Key"),
    request: Request = None,
    user=Security(manager, scopes=['write'], use_cache=False)
):
    """
    Upload CSV dataset basically hosted at AWS S3:

    - **url**: CSV file url
    - **idxs**: comma separated fields list for adding database indexes
    - **X-API-Key**: header carrying the API key for machine-to-machine auth
    - **api_key**: DEPRECATED query-parameter form — it lands in the access log
      in plaintext. Send the `X-API-Key` header instead.
    """
    # Allow API key auth for internal automation
    if not _api_key_ok(x_api_key, api_key):
        if not user:
            return JSONResponse(
                status_code=401,
                content={'error': 'Invalid credentials - provide X-API-Key or Bearer token'}
            )
    if not url:
        return {'error': 'malformed request'}
    
    tbl = CsvDataset.url2fn(url)
    if not _import_table_ok(tbl):
        return JSONResponse(status_code=400, content={'result': 'Fail', 'error': 'invalid table name'})

    # Route CROL to async import (too large for sync driver)
    if tbl == 'crol':
        return await import_crol_async(url)
    
    ds = CsvDataset()
    
    if not ds.download(url):
        # Log failed download
        await log_ingestion(tbl, url, 'fail', error_message='Download failed')
        return {'result': 'fail'}
    
    extraidxs = {
        'crol': '',
        'wegov_orgs': 'type,communityDistrictId,cityCouncilDistrictId',
        '': '',

    }.get(tbl, '')
    req = ds.import_csv(tbl, tbl, ','.join(set([el for el in idxs.split(',') + extraidxs.split(',') if el])))
    
    if not req:
        await log_ingestion(tbl, url, 'fail', error_message='Import failed')
        return JSONResponse(status_code=503, content={'result': 'Fail'})
    
    # Get row count and log success
    try:
        row_count_result = await select(f'SELECT COUNT(*) as cnt FROM "{tbl}"')
        row_count = row_count_result['rows'][0]['cnt'] if row_count_result.get('rows') else None
    except:
        row_count = None
    
    await log_ingestion(tbl, url, 'success', row_count=row_count)
    
    return {'result': 'OK', 'table': tbl, 'rows': row_count}


def _staging_name(table_name: str) -> str:
    """`_staging_<table>`, refusing a name Postgres would silently truncate.

    ⚠ Identifiers are capped at 63 bytes and Postgres TRUNCATES rather than
    erroring, so a long table name would yield a staging name that could collide
    with another table's — and the collision would surface as one import
    clobbering another's staging data, which is close to unfindable. Measured
    2026-09-02: the longest active table name is 30 chars, so this has plenty of
    headroom and exists only so a future long name fails loudly here instead.
    """
    staging = f"_staging_{table_name}"
    if len(staging.encode()) > 63:
        raise ValueError(
            f"staging name for {table_name!r} exceeds Postgres' 63-byte identifier "
            f"limit and would be silently truncated")
    return staging


async def _swap_staging_into_place(db, table_name: str, staging: str,
                                   total: int, build_started: float):
    """ANALYZE the staging table, then swap it over the live one atomically.

    ⚠⚠ ONE SPELLING FOR BOTH IMPORTERS. `import_crol_async` and
    `import_csv_async` both used to DROP the live table and rebuild it in place,
    leaving every consumer to see `relation "X" does not exist` or — worse,
    because it does not raise — a PARTIALLY POPULATED table. Two copies of the
    swap would be two chances to get it subtly different; this is the one owner.

    ⚠ ANALYZE BEFORE THE SWAP, and it is load-bearing rather than tidy: measured
    on prod against throwaway tables, a staging table's reltuples and pg_stats
    rows are IDENTICAL after the rename, because pg_statistic is keyed on the
    relation OID and RENAME preserves it. So the table is never
    live-without-statistics — the #199 defect, where a hook reports success while
    every lookup still seq-scans.

    ⚠ BOTH STATEMENTS IN ONE TRANSACTION. DDL is transactional in Postgres —
    measured: a rolled-back swap leaves the original table intact with all its
    rows — so no reader can observe the moment between them. They see the old
    table or the new one, never neither. That is the entire point.

    ⚠ Indexes are deliberately NOT built here. Their names are schema-unique and
    declared in data_scheduler.TABLE_INDEXES / modules.searchindexes, so creating
    them on the staging table would COLLIDE with the live table's; reproducing the
    naming at the call site would add another declaration site, which #252 exists
    to prevent. Callers rebuild them after this returns, which is also what the
    old code did — so the residual "complete but briefly unindexed" window is no
    worse than before, and strictly better than "missing or partial".
    """
    import time
    await db.execute(f'ANALYZE "{staging}"')
    swap_started = time.time()
    async with db.transaction():
        await db.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        await db.execute(f'ALTER TABLE "{staging}" RENAME TO "{table_name}"')
    # ⚠ print, NOT logger: main.py defines no logger and `main` is not in
    # applog.APP_LOGGER_ROOTS, so a logger call here would be a NameError and even
    # with one its INFO would be dropped (#249). Every progress line in this file
    # is a bracketed print for the same reason. The duration is recorded because
    # the log had no start marker, so the size of this window was never known.
    print(f"[{table_name}] swapped {total} rows into place in "
          f"{time.time() - swap_started:.3f}s "
          f"(build took {swap_started - build_started:.1f}s)", flush=True)


async def import_crol_async(url: str):
    """
    Async import for CROL dataset - streams to disk then uses psql COPY.
    Bypasses the sync driver which saturates on large datasets.
    """
    import aiohttp
    import csv
    import asyncpg
    import time
    
    try:
        # Stream download to file (avoids loading 600MB into memory)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await log_ingestion('crol', url, 'fail', error_message=f'Download failed: HTTP {response.status}')
                    return JSONResponse(status_code=400, content={'result': 'Fail', 'error': f'Download failed: HTTP {response.status}'})
                
                with open('/tmp/crol_import.csv', 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
        
        # Read header
        with open('/tmp/crol_import.csv', 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
        
        # Dedupe columns
        seen = {}
        clean_cols = []
        for col in header:
            if col in seen:
                seen[col] += 1
                clean_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                clean_cols.append(col)
        
        # Connect to database. Environment first, env.yaml only as a fallback —
        # dbcreds resolves secret file / env var / YAML in that order and reads
        # the YAML keys with .get(), so a config that no longer carries a `pwd:`
        # (the box's, since the credential moved to Docker secrets) cannot raise
        # KeyError here. See modules/dbcreds.py.
        db = await asyncpg.connect(**dbcreds.settings(Config.db))

        # ⚠⚠ BUILD INTO A STAGING TABLE AND SWAP — NEVER DROP THE LIVE ONE.
        # This used to `DROP TABLE crol` and then spend the whole import
        # rebuilding it: 1.1M rows / 789 MB of COPY, plus TWO full table
        # rewrites (the ALTER COLUMN ... TYPE DATE and the event_date_parsed
        # UPDATE below). For that entire window every consumer saw either
        # `relation "crol" does not exist` or — worse, because it does not
        # raise — a PARTIALLY POPULATED table. Sentry caught the first shape
        # three times at 04:15 on three different days (DATABOOK-API-31); the
        # second shape is invisible: a notices panel silently renders fewer
        # notices than exist and a count reads low, which is this repo's
        # empty-reads-as-data defect at ingest grain.
        #
        # Consumers affected: oce.py::_notices_for_epins and related_notices
        # (the contract page's panel), routers/search.py::_notices (global
        # search + typeahead), the notice pages, notice_product_links' builder
        # and the classifier's CROL tier.
        #
        # ⚠ THE SWAP IS THE SAME PATTERN THE EXTRACTOR PATH ALREADY USES, which
        # is why indexes are rebuilt AFTER the rename rather than before: index
        # names are schema-unique and declared explicitly in
        # data_scheduler.TABLE_INDEXES, so building them on the staging table
        # would collide with the live table's. Reproducing the naming here to
        # dodge that would give crol a fourth declaration site — the exact
        # sprawl #252 removed. So the window that remains is "complete but
        # briefly unindexed", which is strictly better than "missing or partial"
        # AND is no worse than the old code, which also only indexed at the end.
        staging = _staging_name('crol')
        build_started = time.time()
        try:
            # A previous run that died mid-import can leave one behind; it holds
            # a full copy of the table, so it is dropped rather than reused.
            await db.execute(f'DROP TABLE IF EXISTS {staging}')
            # A CSV header is caller data: an embedded `"` is doubled so it cannot
            # leave its identifier (copy_records_to_table quotes the same way).
            col_defs = ', '.join(['"{}" TEXT'.format(col.replace('"', '""')) for col in clean_cols])
            await db.execute(f'CREATE TABLE {staging} ({col_defs})')

            # Stream import in batches
            batch_size = 10000
            batch = []
            total = 0
            
            with open('/tmp/crol_import.csv', 'r') as f:
                reader = csv.reader(f)
                next(reader)  # skip header
                for row in reader:
                    batch.append(tuple(row))
                    if len(batch) >= batch_size:
                        await db.copy_records_to_table(staging, records=batch, columns=clean_cols)
                        total += len(batch)
                        batch = []
                if batch:
                    await db.copy_records_to_table(staging, records=batch, columns=clean_cols)
                    total += len(batch)
            
            # Convert date columns (only if they exist in the CSV)
            for date_col in ['start_date_parsed', 'event_date_parsed']:
                if date_col in clean_cols:
                    try:
                        await db.execute(f"""
                            ALTER TABLE {staging}
                            ALTER COLUMN {date_col} TYPE DATE USING CASE 
                                WHEN {date_col} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' THEN {date_col}::DATE 
                                ELSE NULL 
                            END
                        """)
                    except Exception:
                        pass  # Column may have unexpected values
            
            # If event_date_parsed not in CSV, create it from EventDate
            # EventDate format: "MM/DD/YYYY HH:MM:SS AM/PM"
            if 'event_date_parsed' not in clean_cols and 'EventDate' in clean_cols:
                await db.execute(f'ALTER TABLE {staging} ADD COLUMN event_date_parsed DATE')
                await db.execute(f"""
                    UPDATE {staging} SET event_date_parsed = 
                        TO_DATE(SUBSTRING("EventDate" FROM 1 FOR 10), 'MM/DD/YYYY')
                    WHERE "EventDate" != '' AND length("EventDate") >= 10
                """)

            # ⚠ The index list moved to data_scheduler.TABLE_INDEXES['crol'].
            # It lived here as a literal — and as a verbatim SECOND copy in
            # import_csv_async below — so crol had THREE declaration sites and the
            # two trim("PIN") indexes the crosswalk needs were in none of them.
            # This drops the table on every import, so the indexes must be rebuilt
            # here rather than left to the scheduler's later hook call.
            #
            # ⚠⚠ AND THERE IS NO "SCHEDULER'S LATER HOOK CALL" FOR crol — measured
            # 2026-08-18, not assumed. All four `run_post_ingest_hooks` call sites
            # live in data_scheduler and fire only for tables the SCHEDULER
            # ingests; crol arrives through this endpoint (the normalizer POSTs
            # /import-crol), so nothing here ever invoked the hooks. The proof is
            # in the log: contracts/solicitations/vendors each print
            # "[hooks] Running N post-ingest hook(s)" before their index lines and
            # crol printed its index lines with no such wrapper.
            #
            # So this calls the HOOK RUNNER rather than the index rebuild directly.
            # `POST_INGEST_HOOKS['crol'][0]` *is* recreate_table_indexes(conn,
            # 'crol'), so the indexes are still rebuilt first and nothing about the
            # old behaviour changes — but anything else registered on crol now
            # actually runs. Registering a hook that never fires is worse than
            # having no hook, because the data looks maintained.
            # ⚠ ANALYZE BEFORE THE SWAP, and it is load-bearing rather than
            # tidy: pg_statistic rows are keyed on the relation OID and RENAME
            # preserves the OID, so statistics gathered here SURVIVE the rename
            # and the table is never live-without-stats. Without it the planner
            # would treat a 1.1M-row table as empty for the window between the
            # swap and the post-ingest ANALYZE — the #199 defect, where a hook
            # reports success while every lookup still seq-scans.
            await _swap_staging_into_place(db, 'crol', staging, total, build_started)

            from data_scheduler import run_post_ingest_hooks
            await run_post_ingest_hooks('crol', db)
            
        finally:
            # ⚠ A run that died mid-build leaves a full-size copy behind (789 MB
            # at current volumes). After a SUCCESSFUL swap this is a no-op,
            # because the staging table no longer exists under that name.
            try:
                await db.execute(f'DROP TABLE IF EXISTS {staging}')
            except Exception:  # noqa: BLE001 — cleanup must never mask the real error
                pass
            await db.close()
        
        # Cleanup temp file
        import os
        os.remove('/tmp/crol_import.csv')
        
        await log_ingestion('crol', url, 'success', row_count=total)
        return {'result': 'OK', 'table': 'crol', 'rows': total}
        
    except Exception as e:
        await log_ingestion('crol', url, 'fail', error_message=str(e))
        return JSONResponse(status_code=500, content={'result': 'Fail', 'error': str(e)})


async def log_ingestion(table_name: str, s3_url: str, status: str, row_count: int = None, error_message: str = None):
    """Log dataset ingestion to ingestion_log table."""
    try:
        await PostgresModelAsync.execute("""
            INSERT INTO ingestion_log (table_name, s3_url, status, row_count, error_message)
            VALUES ($1, $2, $3, $4, $5)
        """, (table_name, s3_url, status, row_count, error_message))
    except Exception as e:
        print(f"Failed to log ingestion: {exc_str(e)}")


async def update_registry_status(table_name: str, status: str,
                                 row_count: int = None,
                                 error_message: str = None):
    """Reflect an import outcome onto the dataset_registry row.

    Why: /pipeline/dataset-counts (homepage totals + "latest update") and the
    per-row fields in /pipeline/health read last_ingested_at / estimated_rows
    / last_error straight from dataset_registry. The scheduler's socrata and
    extractor paths call update_registry(), but the normalizer→/import-csv
    path never did — so normalizer-driven datasets showed stale counts and
    lingering errors even after a successful refresh. Matches by table_name
    (already lowercased to match the registry); a no-op for tables that
    aren't registered.
    """
    try:
        if status == 'success':
            await PostgresModelAsync.execute(
                """UPDATE dataset_registry
                   SET last_ingested_at = NOW(),
                       estimated_rows = COALESCE($2, estimated_rows),
                       last_error = NULL
                   WHERE table_name = $1""",
                (table_name, row_count))
        else:
            await PostgresModelAsync.execute(
                """UPDATE dataset_registry
                   SET last_error = $2
                   WHERE table_name = $1""",
                (table_name, (error_message or '')[:500]))
    except Exception as e:
        print(f"Failed to update registry status for {table_name}: {exc_str(e)}")


@app.post('/log-ingestion', tags=['Datasets'], summary="Log dataset ingestion (for normalizers)")
async def post_log_ingestion(
    table_name: str,
    status: str = 'success',
    row_count: int = None,
    s3_url: str = None,
    error_message: str = None,
    user=Security(manager, scopes=['write'])
):
    """
    Log a dataset ingestion event. Called by normalizers after successful data import.
    
    - **table_name**: Name of the table that was ingested (e.g., 'crol')
    - **status**: 'success' or 'fail'
    - **row_count**: Number of rows ingested (optional)
    - **s3_url**: Source URL if applicable (optional)
    - **error_message**: Error details if status is 'fail' (optional)
    """
    try:
        await PostgresModelAsync.execute("""
            INSERT INTO ingestion_log (table_name, s3_url, status, row_count, error_message)
            VALUES ($1, $2, $3, $4, $5)
        """, (table_name, s3_url or '', status, row_count, error_message))
        return {'result': 'OK', 'table_name': table_name, 'status': status, 'row_count': row_count}
    except Exception as e:
        return JSONResponse(status_code=500, content={'result': 'Fail', 'error': str(e)})


# ⚠ THE DECLARATIONS MOVED to modules/searchindexes.py, and this call site is now a
# thin wrapper over it. They lived here as a literal list applied only by /import-csv,
# while `contracts` and `solicitations` are loaded by the EXTRACTOR path — which drops
# and renames their tables and never ran this. Measured 2026-08-13: 5 of the 19
# declared search indexes were missing on prod, all 5 on those two tables. The shared
# module is applied by BOTH paths (here, and data_scheduler's post-ingest hook).
async def _ensure_search_indexes(db, table_name: str):
    """Recreate the global-search GIN indexes for a freshly (re)imported table.

    /import-csv does DROP TABLE + CREATE + COPY, which drops all indexes — without
    this, search silently degrades to seq-scans. Best-effort: a failing index
    (missing column, pg_trgm absent) is logged, never fatal to the import."""
    await searchindexes.ensure(db, table_name, log=logging.warning)


@app.post('/import-csv', tags=['Datasets'], summary="Import CSV dataset (streaming)")
async def import_csv_async(
    url: str,
    table_name: str,
    api_key: str = None,
    x_api_key: str = Header(None, alias="X-API-Key"),
    request: Request = None
):
    # Allow API key auth for internal automation OR JWT auth.
    # X-API-Key header preferred; the api_key query param is deprecated because
    # it is written to the access log in plaintext. See _api_key_ok.
    if _api_key_ok(x_api_key, api_key):
        pass  # Authorized via API key
    else:
        # Try JWT auth
        try:
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not token:
                return JSONResponse(status_code=401, content={'result': 'Fail', 'error': 'Invalid credentials - provide X-API-Key or Bearer token'})
            user = await manager.get_current_user(token)
            if not user:
                return JSONResponse(status_code=401, content={'result': 'Fail', 'error': 'Invalid credentials'})
        except Exception:
            return JSONResponse(status_code=401, content={'result': 'Fail', 'error': 'Invalid credentials - provide api_key or Bearer token'})

    # Normalise to lowercase so the imported table matches the unquoted
    # names the API uses in SELECT queries (Postgres lowercases unquoted
    # identifiers, but double-quoted names are case-sensitive).
    table_name = table_name.lower()
    if not _import_table_ok(table_name):
        return JSONResponse(status_code=400, content={'result': 'Fail', 'error': 'invalid table name'})
    """
    Import a CSV file from S3 into a PostgreSQL table using streaming.
    Downloads to disk first, then batch-inserts via COPY to avoid OOM
    on large datasets (1M+ rows like Expense Budget and CROL).
    """
    import aiohttp
    import csv
    import sys
    import os
    import time
    csv.field_size_limit(sys.maxsize)
    import asyncpg
    
    tmp_path = f'/tmp/import_{table_name}.csv'
    
    try:
        # Stream download to disk (avoids loading entire CSV into memory)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f'Download failed: HTTP {response.status}'
                    await log_ingestion(table_name, url, 'fail', error_message=err)
                    await update_registry_status(table_name, 'fail', error_message=err)
                    return JSONResponse(status_code=400, content={'result': 'Fail', 'error': f'Failed to download CSV: HTTP {response.status}'})

                with open(tmp_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        f.write(chunk)

        # Check file is non-empty
        if os.path.getsize(tmp_path) == 0:
            os.remove(tmp_path)
            err = f'S3 file is empty: {url}'
            await log_ingestion(table_name, url, 'fail', error_message=err)
            await update_registry_status(table_name, 'fail', error_message=err)
            return JSONResponse(status_code=400, content={'result': 'Fail', 'error': err})
        
        # Read header and dedupe columns
        with open(tmp_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)
        
        seen = {}
        clean_cols = []
        for col in header:
            if col in seen:
                seen[col] += 1
                clean_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                clean_cols.append(col)
        
        # Connect to database. Environment first, env.yaml only as a fallback —
        # dbcreds resolves secret file / env var / YAML in that order and reads
        # the YAML keys with .get(), so a config that no longer carries a `pwd:`
        # (the box's, since the credential moved to Docker secrets) cannot raise
        # KeyError here. See modules/dbcreds.py.
        db = await asyncpg.connect(**dbcreds.settings(Config.db))

        # ⚠⚠ BUILD INTO A STAGING TABLE AND SWAP — NEVER DROP THE LIVE ONE.
        # This used to `DROP TABLE "<table>"` and then spend the whole import
        # rebuilding it, so for that window every consumer saw either
        # `relation "X" does not exist` or — worse, because it does not raise — a
        # PARTIALLY POPULATED table, reading fewer rows than exist while a count
        # came back low. Measured 2026-09-02, this path serves 52 active datasets
        # including payrolldata (1787 MB) and civillist (725 MB), both LARGER than
        # crol, and civillist backs people search, person profiles and the org
        # Employees tab — all public pages.
        #
        # Same pattern and the same ONE OWNER as the crol importer above; see
        # _swap_staging_into_place for why ANALYZE happens before the swap and why
        # indexes are still rebuilt after it.
        staging = _staging_name(table_name)
        build_started = time.time()
        try:
            # A previous run that died mid-import leaves a full-size copy behind.
            await db.execute(f'DROP TABLE IF EXISTS "{staging}"')
            # A CSV header is caller data: an embedded `"` is doubled so it cannot
            # leave its identifier (copy_records_to_table quotes the same way).
            col_defs = ', '.join(['"{}" TEXT'.format(col.replace('"', '""')) for col in clean_cols])
            await db.execute(f'CREATE TABLE "{staging}" ({col_defs})')
            
            # Stream import in batches
            batch_size = 10000
            batch = []
            total = 0
            
            with open(tmp_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader)  # skip header
                for row in reader:
                    batch.append(tuple(row))
                    if len(batch) >= batch_size:
                        await db.copy_records_to_table(
                            staging, records=batch, columns=clean_cols)
                        total += len(batch)
                        batch = []
                if batch:
                    await db.copy_records_to_table(
                        staging, records=batch, columns=clean_cols)
                    total += len(batch)
            
            # CROL-specific post-processing: date columns and indexes
            if table_name == 'crol':
                for date_col in ['start_date_parsed', 'event_date_parsed']:
                    if date_col in clean_cols:
                        try:
                            await db.execute(f"""
                                ALTER TABLE "{staging}"
                                ALTER COLUMN {date_col} TYPE DATE USING CASE 
                                    WHEN {date_col} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' THEN {date_col}::DATE 
                                    ELSE NULL 
                                END
                            """)
                        except Exception:
                            pass

                if 'event_date_parsed' not in clean_cols and 'EventDate' in clean_cols:
                    await db.execute(f'ALTER TABLE "{staging}" ADD COLUMN event_date_parsed DATE')
                    await db.execute(f"""
                        UPDATE "{staging}" SET event_date_parsed = 
                            TO_DATE(SUBSTRING("EventDate" FROM 1 FOR 10), 'MM/DD/YYYY')
                        WHERE "EventDate" != '' AND length("EventDate") >= 10
                    """)


            await _swap_staging_into_place(db, table_name, staging, total, build_started)

            # ⚠ HOOKS AND INDEXES RUN AFTER THE SWAP, on the real table name. If
            # they ran before it they would build indexes under the STAGING name,
            # and the rename would carry those names onto the live table — leaving
            # the declared names absent and a duplicate set present.
            # ⚠ THE SECOND COPY of the same block, now also delegated. See
            # data_scheduler.TABLE_INDEXES['crol'] — and the note at the other
            # site for why this calls the hook runner, not the index rebuild.
            if table_name == 'crol':
                from data_scheduler import run_post_ingest_hooks
                await run_post_ingest_hooks('crol', db)

            # Refresh planner stats so pg_class.reltuples is accurate
            # immediately. The health dashboard reads reltuples (an estimate)
            # for row counts; after a DROP+CREATE+COPY it is 0 until
            # autoanalyze runs, which briefly flags a freshly-loaded table as
            # "Empty". Running ANALYZE here makes the count correct at once.
            await db.execute(f'ANALYZE "{table_name}"')

            # Rebuild this table's global-search GIN indexes — DROP+CREATE above
            # wiped them. Without this, search degrades to seq-scans after every
            # re-import (no-op for non-searchable tables).
            await _ensure_search_indexes(db, table_name)

            # Log ingestion
            await db.execute("""
                INSERT INTO ingestion_log (table_name, s3_url, status, row_count, error_message)
                VALUES ($1, $2, $3, $4, $5)
            """, table_name, url, 'success', total, None)
            
        finally:
            # ⚠ A run that died mid-build leaves a full-size copy behind — 1787 MB
            # for payrolldata. After a successful swap this is a no-op, because the
            # staging table no longer exists under that name.
            try:
                await db.execute(f'DROP TABLE IF EXISTS "{staging}"')
            except Exception:  # noqa: BLE001 — cleanup must never mask the real error
                pass
            await db.close()
        
        # Cleanup temp file
        os.remove(tmp_path)
        
        await log_ingestion(table_name, url, 'success', row_count=total)
        await update_registry_status(table_name, 'success', row_count=total)
        return {'result': 'OK', 'table_name': table_name, 'rows': total, 's3_url': url}

    except Exception as e:
        await log_ingestion(table_name, url, 'fail', error_message=str(e))
        await update_registry_status(table_name, 'fail', error_message=str(e))
        # Cleanup on error
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return JSONResponse(status_code=500, content={'result': 'Fail', 'error': str(e)})


@app.get('/ingestion-log', tags=['Datasets'], summary="Get ingestion log")
async def get_ingestion_log(
    table_name: str = None,
    limit: int = 100,
    
):
    """Get ingestion history, optionally filtered by table name."""
    if table_name:
        return await select(
            "SELECT * FROM ingestion_log WHERE table_name = $1 ORDER BY ingested_at DESC LIMIT $2",
            (table_name, limit)
        )
    return await select(
        "SELECT * FROM ingestion_log ORDER BY ingested_at DESC LIMIT $1",
        (limit,)
    )


@app.get('/table-stats', tags=['Datasets'], summary="Get all database table statistics")
async def get_table_stats(
    
):
    """
    Get comprehensive statistics for all database tables including:
    - Row counts (estimated from pg_stat)
    - Table sizes
    - Last ingestion timestamps
    """
    # Get table sizes and estimated row counts using pg_class for better estimates
    table_info = await select("""
        SELECT 
            c.relname as table_name,
            c.reltuples::bigint as estimated_rows,
            pg_size_pretty(pg_total_relation_size(quote_ident(c.relname)::regclass)) as size,
            pg_total_relation_size(quote_ident(c.relname)::regclass) as size_bytes
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' 
          AND c.relkind = 'r'
        ORDER BY pg_total_relation_size(quote_ident(c.relname)::regclass) DESC
    """)
    
    # Get latest ingestion timestamps for each table
    ingestion_info = await select("""
        SELECT DISTINCT ON (table_name) 
            table_name,
            ingested_at,
            row_count as actual_rows,
            status,
            s3_url
        FROM ingestion_log 
        ORDER BY table_name, ingested_at DESC
    """)
    
    # Create lookup for ingestion info
    ingestion_map = {row['table_name']: row for row in ingestion_info.get('rows', [])}
    
    # Merge the data
    result = []
    for table in table_info.get('rows', []):
        table_name = table['table_name']
        ingestion = ingestion_map.get(table_name, {})
        
        # Use actual row count from ingestion if available and recent
        actual_rows = ingestion.get('actual_rows')
        estimated_rows = table.get('estimated_rows', 0)
        
        result.append({
            'table_name': table_name,
            'row_count': actual_rows if actual_rows else estimated_rows,
            'estimated_rows': estimated_rows,
            'size': table.get('size', 'Unknown'),
            'size_bytes': table.get('size_bytes', 0),
            'last_ingested': ingestion.get('ingested_at'),
            'ingestion_status': ingestion.get('status'),
            'source_url': ingestion.get('s3_url'),
        })
    
    return {'rows': result, 'total_tables': len(result)}

# ---- Schools --------

# ⚠⚠ `schoollocations` IS NOT ONE ROW PER SCHOOL AT SOURCE. The City publishes
# 2,190 rows for 2,131 schools -- 59 byte-exact repeats -- so a bare count
# over-reports and every JOIN on `location_code` doubles the joined rows for
# those buildings. District 18 read 17,803 students against a real 17,051.
# `modules/sourcedupes` owns the dedupe; these are its two spellings, and no
# query below may name the raw table instead. See that module for why the fix
# is here and not in a post-ingest hook.
_SCHOOL_LOCATIONS = sourcedupes.relation('schoollocations')
_SCHOOL_LOCATIONS_T2 = sourcedupes.relation('schoollocations', 't2')

@app.get('/get/schools/sdstats/all', tags=['Schools'])
async def get_schools_global_stats():
    schools_no = await select(f'SELECT count(*) as res FROM {_SCHOOL_LOCATIONS}')
    students_no = await select('SELECT sum(cast("Org Enroll" as decimal)) as res FROM scaenrollmentcapacity WHERE "Org Enroll" ~ \'^[0-9\\.]+\' AND "Data As Of" = (SELECT max("Data As Of") FROM scaenrollmentcapacity)')
    prj_no = await select('SELECT count(*) as res FROM scaactiveprojects')
    prj_budget = await select('SELECT sum(cast("Project Budget Amount" as decimal)) as res FROM scacapitalprojectschedules WHERE "Project Budget Amount" ~ \'^[0-9\\.]+\'')
    prj_costs = await select('SELECT sum(cast("Total Phase Actual Spending Amount" as decimal)) as res FROM scacapitalprojectschedules WHERE "Total Phase Actual Spending Amount" ~ \'^[0-9\\.]+\'')
    
    s_no = students_no['rows'][0]['res'] or 1
    p_costs = prj_costs['rows'][0]['res'] or 0
    
    return {'rows': [{
        'schools_no': schools_no['rows'][0]['res'],
        'students_no': s_no,
        'prj_no': prj_no['rows'][0]['res'],
        'prj_budget': prj_budget['rows'][0]['res'],
        'prj_costs': p_costs,
        'pcosts_per_student': p_costs / s_no
    }]}

@app.get('/get/schools/all', tags=['Schools'])
async def get_all_schools():
    return await select(f'SELECT * FROM {_SCHOOL_LOCATIONS}')

@app.get('/get/schools/sdstats/{id}', tags=['Schools'])
async def get_school_district_stats(id: str):
    schools_no = await select(f'SELECT count(*) as res FROM {_SCHOOL_LOCATIONS} WHERE "Geographical_District_code" = $1', (id,))
    students_no = await select(f'SELECT sum(cast("Org Enroll" as decimal)) as res FROM scaenrollmentcapacity t1 JOIN {_SCHOOL_LOCATIONS_T2} ON t1."Bldg ID" = t2."location_code" WHERE t2."Geographical_District_code" = $1 AND "Org Enroll" ~ \'^[0-9\\.]+\' AND "Data As Of" = (SELECT max("Data As Of") FROM scaenrollmentcapacity)', (id,))
    prj_no = await select(f'SELECT count(*) as res FROM scaactiveprojects t1 JOIN {_SCHOOL_LOCATIONS_T2} ON t1."Building ID" = t2."location_code" WHERE t2."Geographical_District_code" = $1', (id,))
    prj_budget = await select(f'SELECT sum(cast("Project Budget Amount" as decimal)) as res FROM scacapitalprojectschedules t1 JOIN {_SCHOOL_LOCATIONS_T2} ON t1."Project Building Identifier" = t2."location_code" WHERE t2."Geographical_District_code" = $1 AND "Project Budget Amount" ~ \'^[0-9\\.]+\'', (id,))
    prj_costs = await select(f'SELECT sum(cast("Total Phase Actual Spending Amount" as decimal)) as res FROM scacapitalprojectschedules t1 JOIN {_SCHOOL_LOCATIONS_T2} ON t1."Project Building Identifier" = t2."location_code" WHERE t2."Geographical_District_code" = $1 AND "Total Phase Actual Spending Amount" ~ \'^[0-9\\.]+\'', (id,))
    
    s_no = students_no['rows'][0]['res'] or 1
    p_costs = prj_costs['rows'][0]['res'] or 0
    
    return {'rows': [{
        'schools_no': schools_no['rows'][0]['res'],
        'students_no': s_no,
        'prj_no': prj_no['rows'][0]['res'],
        'prj_budget': prj_budget['rows'][0]['res'],
        'prj_costs': p_costs,
        'pcosts_per_student': p_costs / s_no
    }]}

@app.get('/get/globstats', tags=['General'])
async def get_global_stats():
    total_datasets_no = await select(
        "SELECT count(*) as res FROM dataset_registry WHERE display_name IS NOT NULL")
    total_records_no = await select(
        'SELECT sum(n_live_tup) as res FROM pg_stat_user_tables')
    latest_update = await select(
        "SELECT to_char(max(last_ingested_at), 'MM/DD/YYYY HH24:MI') as res FROM dataset_registry")
    
    return {'rows': [{
        'total_datasets_no': total_datasets_no['rows'][0]['res'],
        'total_records_no': total_records_no['rows'][0]['res'],
        'latest_update': latest_update['rows'][0]['res']
    }]}

@app.get('/get/schools/{id}', tags=['Schools'])
async def get_school_details(id: str):
    return await select(f'SELECT * FROM {_SCHOOL_LOCATIONS} WHERE "location_code" = $1', (id,))

@app.get('/get/schools/section/{id}/{tbl}', tags=['Schools'])
async def get_school_section(id: str, tbl: str):
    # Map table names to their ID columns
    col_map = {
        'demographics': 'DBN',
        'attendance': 'DBN',
        'scaenrollmentcapacity': 'Bldg ID',
        'temphousing': 'DBN',
        'guidancecounsellors': 'DBN',
        'dohmhinspections': 'BBL',
        'scaactiveprojects': 'Building ID',
        'scacapitalprojectschedules': 'Project Building Identifier',
        'scaschoolprograms': 'Building ID',
        'scacurrentplan': 'Building ID',
        'scaaddedprojects': 'Bldg ID',
        'graduationoutcomes': 'Geographic Subdivision'
    }

    # ⚠⚠ A SECOND, FIXED PREDICATE — and for graduation it is load-bearing, not
    # tidiness. `mjm3-8dw8` stacks six grains in one table, keyed on one column:
    # a School row's "Geographic Subdivision" is a DBN (02M422), but so is a
    # Transfer School row's. Measured 2026-09-21: of 497 School DBNs, **54 also
    # appear under 'Transfer School'** — so filtering on the DBN alone returns
    # both sets and double-counts 11% of high schools. (Charter School is also
    # DBN-shaped, 85 of them, but overlaps School on 0.)
    # Values are CONSTANTS declared here, never anything the caller supplies.
    fixed_filters = {
        'graduationoutcomes': ('Report Category', 'School'),
    }

    if tbl not in col_map:
        raise HTTPException(status_code=404, detail="Table not found or not authorized")

    col = col_map[tbl]
    if tbl in fixed_filters:
        fcol, fval = fixed_filters[tbl]
        return await select(
            f'SELECT * FROM {tbl} WHERE "{col}" = $1 AND "{fcol}" = $2', (id, fval))
    return await select(f'SELECT * FROM {tbl} WHERE "{col}" = $1', (id,))

@app.get('/get/schools/schoolStats/{id}', tags=['Schools'])
async def get_school_stats(id: str):
    # Get system_code for demographics
    school = await select(f'SELECT "system_code" FROM {_SCHOOL_LOCATIONS} WHERE "location_code" = $1', (id,))
    if not school['rows']:
        return {'rows': []}
    system_code = school['rows'][0]['system_code']

    students_no = await select('SELECT sum(cast("Org Enroll" as decimal)) as res FROM scaenrollmentcapacity WHERE "Bldg ID" = $1 AND "Org Enroll" ~ \'^[0-9\\.]+\' AND "Data As Of" = (SELECT max("Data As Of") FROM scaenrollmentcapacity)', (id,))
    prj_no = await select('SELECT count(*) as res FROM scacapitalprojectschedules WHERE "Project Building Identifier" = $1', (id,))
    prj_budget = await select('SELECT sum(cast("Project Budget Amount" as decimal)) as res FROM scacapitalprojectschedules WHERE "Project Building Identifier" = $1 AND "Project Budget Amount" ~ \'^[0-9\\.]+\'', (id,))
    prj_costs = await select('SELECT sum(cast("Total Phase Actual Spending Amount" as decimal)) as res FROM scacapitalprojectschedules WHERE "Project Building Identifier" = $1 AND "Total Phase Actual Spending Amount" ~ \'^[0-9\\.]+\'', (id,))
    
    # Get latest poverty percentage
    povetry_perc = await select('SELECT "% Poverty" as res FROM demographics WHERE "DBN" = $1 ORDER BY "Year" DESC LIMIT 1', (system_code,))

    s_no = students_no['rows'][0]['res'] or 0
    p_costs = prj_costs['rows'][0]['res'] or 0
    
    return {'rows': [{
        'students_no': s_no,
        'prj_no': prj_no['rows'][0]['res'],
        'prj_budget': prj_budget['rows'][0]['res'],
        'prj_costs': p_costs,
        'pcosts_per_student': p_costs / s_no if s_no > 0 else 0,
        'povetry_perc': povetry_perc['rows'][0]['res'] if povetry_perc['rows'] else 'N/A'
    }]}


# ================ Budget Lines & Capital Projects Extras ================

@app.get('/get/pstats-categories/all', tags=['Capital Projects'])
async def get_pstats_categories_all():
    """Aggregate category stats across all published dates.

    Why: categoriesA.blade.php renders a DataTable expecting pubdate,
    category, fundingsource, year1amount, year10total, prjnum,
    plannedcost, and currcost per row.  Strategy data comes from
    capitalstrategy; project counts and costs come from
    capitalprojectsdollarscomp using the LATEST PUB_DATE, joined
    by category only (STRATEGY_PUB_DATE is too sparse to match).
    """
    return await select("""
        SELECT
            s."Published Date"                          AS pubdate,
            s."Ten-Year Plan Category"                  AS category,
            s."Funding Type"                            AS fundingsource,
            SUM(NULLIF(s."Fiscal Year 1 Amount", '')::BIGINT) AS year1amount,
            SUM(NULLIF(s."Ten-Year Total", '')::BIGINT)       AS year10total,
            COALESCE(p.prjnum, 0)                       AS prjnum,
            COALESCE(p.plannedcost, 0)                  AS plannedcost,
            COALESCE(p.currcost, 0)                     AS currcost
        FROM capitalstrategy s
        LEFT JOIN (
            SELECT
                UPPER("wegov-project-category")         AS cat_upper,
                COUNT(DISTINCT "PROJECT_ID")             AS prjnum,
                COALESCE(SUM("BUDG_ORIG"), 0)::BIGINT AS plannedcost,
                SUM(CASE WHEN "BUDG_CURR" ~ '^-?[0-9.]+$' THEN "BUDG_CURR"::NUMERIC ELSE 0 END)::BIGINT AS currcost
            FROM capitalprojectsdollarscomp
            WHERE "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp WHERE "PUB_DATE" < 20260000)
            GROUP BY UPPER("wegov-project-category")
        ) p ON p.cat_upper = UPPER(s."Ten-Year Plan Category")
        GROUP BY s."Published Date",
                 s."Ten-Year Plan Category",
                 s."Funding Type",
                 p.prjnum, p.plannedcost, p.currcost
        ORDER BY s."Published Date" DESC, s."Ten-Year Plan Category"
    """)

@app.get('/get/pstats-categories/recent', tags=['Capital Projects'])
async def get_pstats_categories_recent():
    """Get pstats-categories for the most recent published date.

    Why: Avoids hardcoding dates in the frontend.
    """
    date_result = await select('SELECT MAX("Published Date") as d FROM capitalstrategy')
    if not date_result.get('rows') or not date_result['rows'][0].get('d'):
        return {'rows': []}
    date = date_result['rows'][0]['d']
    return await get_pstats_categories(date)

@app.get('/get/pstats-categories/{date}', tags=['Capital Projects'])
async def get_pstats_categories(date: str):
    """Same as /all but filtered by published date."""
    return await select("""
        SELECT
            s."Published Date"                          AS pubdate,
            s."Ten-Year Plan Category"                  AS category,
            s."Funding Type"                            AS fundingsource,
            SUM(NULLIF(s."Fiscal Year 1 Amount", '')::BIGINT) AS year1amount,
            SUM(NULLIF(s."Ten-Year Total", '')::BIGINT)       AS year10total,
            COALESCE(p.prjnum, 0)                       AS prjnum,
            COALESCE(p.plannedcost, 0)                  AS plannedcost,
            COALESCE(p.currcost, 0)                     AS currcost
        FROM capitalstrategy s
        LEFT JOIN (
            SELECT
                "STRATEGY_PUB_DATE"                     AS pub_date,
                UPPER("wegov-project-category")         AS cat_upper,
                COUNT(DISTINCT "PROJECT_ID")             AS prjnum,
                SUM("BUDG_ORIG"::BIGINT)                 AS plannedcost,
                SUM(TRIM(REPLACE(NULLIF("BUDG_CURR", ''), ',', '.'))::NUMERIC::BIGINT) AS currcost
            FROM capitalprojectsdollarscomp
            WHERE "STRATEGY_PUB_DATE" = $1
            GROUP BY "STRATEGY_PUB_DATE", UPPER("wegov-project-category")
        ) p ON p.pub_date = s."Published Date"
            AND p.cat_upper = UPPER(s."Ten-Year Plan Category")
        WHERE s."Published Date" = $1
        GROUP BY s."Published Date",
                 s."Ten-Year Plan Category",
                 s."Funding Type",
                 p.prjnum, p.plannedcost, p.currcost
        ORDER BY s."Ten-Year Plan Category"
    """, (date,))

@app.get('/get/capitalbudget/bydate/recent', tags=['Capital Projects'])
async def get_capital_budget_by_date_recent():
    """Get capitalbudget data for the most recent publication date.

    Why: Avoids hardcoding dates in the frontend. Returns all rows
    matching the latest 'Published Date' in the table.
    """
    return await select("""
        SELECT * FROM capitalbudget
        WHERE "Published Date" = (
            SELECT MAX("Published Date") FROM capitalbudget
        )
    """)

@app.get('/get/capitalbudget/bydate/{date}', tags=['Capital Projects'])
async def get_capital_budget_by_date(date: str):
    return await select('SELECT * FROM capitalbudget WHERE "Published Date" = $1', (date,))

@app.get('/get/capitalbudget/{blcode}', tags=['Capital Projects'])
async def get_capital_budget_by_code(blcode: str):
    """Get budget line detail, falling back to capitalcommitmentplan if capitalbudget is empty.

    Why: capitalbudget is a dated dataset that may lack rows for newer budget lines.
    capitalcommitmentplan has current data and similar columns.
    Budget line formats vary: 'AG 0001' (capitalbudget), 'AG-0001'
    (commitments), 'AG0001' (no separator). We normalize and try all.
    """
    import re
    # Generate all format variants from whatever input we get
    stripped = blcode.replace(' ', '').replace('-', '')  # AG0001
    # Insert space after alpha prefix: AG 0001
    spaced = re.sub(r'^([A-Za-z]+)(\w)', r'\1 \2', stripped)
    # Insert dash after alpha prefix: AG-0001
    dashed = re.sub(r'^([A-Za-z]+)(\w)', r'\1-\2', stripped)
    variants = list(dict.fromkeys([blcode, stripped, spaced, dashed]))

    # Try capitalbudget first with all variants
    for v in variants:
        result = await select(
            'SELECT * FROM capitalbudget WHERE "Budget Line" = $1', (v,))
        if result.get('rows'):
            return result

    # Fallback: capitalcommitmentplan with all variants
    for v in variants:
        result = await select("""
            SELECT DISTINCT "Budget Line",
                   "Budget Line Description" AS "Budget Line Title",
                   "Funding Type",
                   "Project Type",
                   "Project Type Description",
                   "Project Type Description" AS "wegov-prjtype-name",
                   "Published Date"
            FROM capitalcommitmentplan
            WHERE "Budget Line" = $1
            ORDER BY "Published Date" DESC
        """, (v,))
        if result.get('rows'):
            return result

    return {"rows": []}

@app.get('/get/budglines_by_prjtype/{tslug}', tags=['Capital Projects'])
async def get_budglines_by_prjtype(tslug: str):
    """Budget lines for a project type, aliased for the blTable DataTable.

    Why: capitalstrategy uses compound codes like 'BR and HB' while
    capitalbudget uses individual codes like 'HB'. We split the compound
    code and match any part.
    """
    # ⚠ THE SAME ONE OWNER as the type endpoint below. All four type
    # surfaces slugged with `REPLACE(' ', '-')` and would have kept the
    # 18 unreachable pages EMPTY had only one been fixed.
    _d = capitalslug.SLUG_SQL.format(col='s."Project Type Description"')
    _t = capitalslug.SLUG_SQL.format(col='s."Project Type"')
    return await select("""
        SELECT
            b."Published Date"       AS pubdate,
            b."Budget Line"          AS budgline,
            b."Budget Line Title"    AS budglinename,
            b."Funding Type"         AS ftype,
            b."First Fiscal Year"    AS year1,
            NULLIF(b."Fiscal Year 1 Amount", '')::BIGINT AS year1amount,
            (COALESCE(NULLIF(b."Fiscal Year 1 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(b."Fiscal Year 2 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(b."Fiscal Year 3 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(b."Fiscal Year 4 Amount",'')::BIGINT,0)) AS totalbudgetvalue
        FROM capitalbudget b
        WHERE b."Project Type" IN (
            SELECT TRIM(regexp_split_to_table(
                CASE WHEN LENGTH(s."Project Type") <= 10 THEN s."Project Type"
                     ELSE s."Project Type Description" END,
                ' and '))
            FROM capitalstrategy s
            WHERE {d} = $1
               OR {t} = $1
            GROUP BY s."Project Type", s."Project Type Description"
        )
        ORDER BY b."Published Date" DESC, b."Budget Line"
    """.format(d=_d, t=_t), (capitalslug.slug(tslug),))

@app.get('/get/commitments_by_prjtype/{tslug}', tags=['Capital Projects'])
async def get_commitments_by_prjtype(tslug: str):
    """Commitments for a project type, aliased for the commTable DataTable."""
    # ⚠ THE SAME ONE OWNER as the type endpoint below. All four type
    # surfaces slugged with `REPLACE(' ', '-')` and would have kept the
    # 18 unreachable pages EMPTY had only one been fixed.
    _d = capitalslug.SLUG_SQL.format(col='s."Project Type Description"')
    _t = capitalslug.SLUG_SQL.format(col='s."Project Type"')
    return await select("""
        SELECT
            c."Published Date"       AS pubdate,
            c."Budget Line"          AS budgline,
            c."Budget Line Description" AS budglinedesc,
            c."Funding Type"         AS ftype,
            (COALESCE(NULLIF(c."Fiscal Year 1 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(c."Fiscal Year 2 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(c."Fiscal Year 3 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(c."Fiscal Year 4 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(c."Fiscal Year 5 Amount",'')::BIGINT,0)) AS totalcommvalue,
            c."First Fiscal Year"    AS year1,
            NULLIF(c."Fiscal Year 1 Amount", '')::BIGINT AS year1amount,
            NULLIF(c."Fiscal Year 2 Amount", '')::BIGINT AS year2amount,
            NULLIF(c."Fiscal Year 3 Amount", '')::BIGINT AS year3amount,
            NULLIF(c."Fiscal Year 4 Amount", '')::BIGINT AS year4amount,
            NULLIF(c."Fiscal Year 5 Amount", '')::BIGINT AS year5amount
        FROM capitalcommitmentplan c
        WHERE c."Project Type" IN (
            SELECT TRIM(regexp_split_to_table(
                CASE WHEN LENGTH(s."Project Type") <= 10 THEN s."Project Type"
                     ELSE s."Project Type Description" END,
                ' and '))
            FROM capitalstrategy s
            WHERE {d} = $1
               OR {t} = $1
            GROUP BY s."Project Type", s."Project Type Description"
        )
        ORDER BY c."Published Date" DESC, c."Budget Line"
    """.format(d=_d, t=_t), (capitalslug.slug(tslug),))

def _unscopable(table, dimension, scope_id):
    """The answer when a table cannot be counted for this dimension at all.

    ⚠⚠ `res: None`, NEVER 0, AND THAT IS THE WHOLE POINT OF THIS SHAPE. The
    shared provenance component treats three outcomes as three different
    claims — a number, `0` ("this dataset holds nothing for this scope, a
    FINDING"), and `—` ("we could not ask") — and the code this replaces
    returned 0 for every table it had no rule for. A dataset that does not
    carry a dimension has not told us it holds nothing; it has not been asked.
    """
    return {'rows': [{'res': None}], 'table': table, 'scope_type': dimension,
            'scope_id': scope_id, 'via': None,
            'retired': capitalsources.retired(table),
            'note': ('This dataset carries no %s dimension and no key that '
                     'resolves to a capital project, so it cannot be counted '
                     'for one. That is not the same as holding no records for '
                     'it.' % dimension.replace('_', ' '))}


async def _scoped_source_count(table, dimension, scope_key):
    """Records in one source table for one scope, via `modules/capitalsources`.

    ⚠ ONE OWNER for both scoped-count endpoints, because they had two copies of
    the same table→column map and five of the eleven entries between them named
    a column that does not exist.

    ⚠ `via` is SERVED. Two rows in one panel can be counted differently — a
    table's own scope column where it has one, the project crosswalk where it
    does not — and the gap is large (82 rows against 568 on one budget line).
    Serving the method is what stops those being silently mixed.
    """
    sql, via = capitalsources.count_sql(table, dimension)
    if not sql:
        return _unscopable(table, dimension, scope_key)
    result = await select(sql, (scope_key,))
    rows = result.get('rows') or []
    # ⚠ A query that returned nothing is not a zero either — `count(*)` always
    # returns a row, so an empty result means the query itself failed to answer.
    if not rows or rows[0].get('res') is None:
        return _unscopable(table, dimension, scope_key)
    return {'rows': [{'res': rows[0]['res']}], 'table': table.lower(),
            'scope_type': dimension, 'scope_id': scope_key, 'via': via,
            # ⚠ SERVED so the panel can label a 2023-series figure. Measured
            # unlabelled on the category panel: the retired series' 2,671 sat
            # beside four current sources with a BLANK "Last Updated" and
            # nothing saying the series stops in October 2023.
            'retired': capitalsources.retired(table)}


@app.get('/get/pstats-records_no-by_prjtype/tblname/{tslug}', tags=['Capital Projects'])
async def get_pstats_records_no_by_prjtype(tslug: str):
    return {'rows': [{'res': 0}]}

@app.get('/get/pstats-records_no-by_prjtype/{tblname}/{tslug}', tags=['Capital Projects'])
async def get_pstats_records_no_by_prjtype_real(tblname: str, tslug: str):
    """Count records for a project type in a specific capital projects table.

    Why: Each table uses a different column for project type. Project type names
    are slugified, so we match by slugifying the column values.
    """
    col_map = {
        'capitalbudget': ('"Project Type Name"', 'slug'),
        'capitalcommitmentplan': ('"Project Type Description"', 'slug'),
        'capitalprojectscommitments': ('projecttype', 'slug'),
        'capitalprojectsdollarscomp': ('"wegov-project-types"', 'ilike'),
        'capitalstrategy': ('"Project Type Description"', 'slug'),
    }
    entry = col_map.get(tblname.lower())
    if not entry:
        return {'rows': [{'res': 0}]}
    col, match_type = entry
    if match_type == 'ilike':
        query = f'SELECT COUNT(*) as res FROM {tblname} WHERE {col} ILIKE $1'
        result = await select(query, (f'%{tslug}%',))
    else:
        # ⚠ THE ONE OWNER HERE TOO. This is the fourth of the four type
        # surfaces: leaving it on `REPLACE(' ', '-')` would have made the
        # provenance panel report 0 records for the 18 pages the other three
        # fixes just made reachable — a confident wrong zero beside a table
        # full of rows, which is the defect the scoped counts exist to avoid.
        query = (f'SELECT COUNT(*) as res FROM {tblname} WHERE '
                 + capitalslug.SLUG_SQL.format(col=col) + ' = $1')
        result = await select(query, (capitalslug.slug(tslug),))
    if result.get('rows') and result['rows'][0].get('res', 0) > 0:
        return result
    return {'rows': [{'res': 0}]}

# ⚠⚠ TWO OF THE EIGHT `capitalstrategy` VINTAGES ARE INGESTED WRONG, AND BOTH
# PUBLISH A FUNDING TYPE WHERE A CATEGORY BELONGS. Measured 2026-09-08:
#
#   20250116  258 of 258 rows — `Ten-Year Plan Category` DUPLICATES
#             `Funding Type`; everything else is aligned. The category is simply
#             absent.
#   20230112  275 of 275 rows — a LEFT SHIFT BY ONE: Funding Type landed in
#             Category, First Fiscal Year in Funding Type, every amount moved one
#             column left, and `Ten-Year Total` is NULL on all 275. So the money
#             on those rows is attributed to the WRONG FISCAL YEARS.
#
# 533 of 2,255 rows, 23.6%. Live consequence before this: the project-type page
# listed `City` and `Federal` as Ten-Year Plan Categories and linked them to
# `/projects/categories/city`, a category that does not exist.
#
# ⚠ THE TEST IS ON THE DATA, NOT A HARDCODED DATE LIST — a date list goes stale
# the moment a ninth vintage lands wrong, and this repo has paid for hardcoded
# ranges before. Separation is exact: **0 of 1,722 rows on the six clean
# vintages are flagged, and 533 of 533 on the two bad ones.**
#
# ⚠ EXCLUDED, NOT REPAIRED. Un-shifting 20230112 would mean asserting which
# fiscal year each amount belongs to, which is a claim about NYC's publication
# that this data cannot support. The fix belongs in the ingest; until then these
# rows are withheld rather than published wrong.
# ⚠⚠ TWO DEFECTS, TWO TREATMENTS — and treating them alike threw away 162 of
# 236 project types. The first blanket exclusion dropped every row whose category
# was a funding type, which is BOTH vintages; but only ONE of them has bad money.
#
#   `_STRATEGY_MONEY_OK`  drops the 275 LEFT-SHIFTED rows (20230112), whose
#     amounts sit one fiscal year off. Tell: `Ten-Year Total` is NULL — exact,
#     **275 of 275 on that vintage and 0 on the other seven**. The money is
#     unusable, so the row goes. 228 of 236 types survive.
#   `_STRATEGY_CATEGORY_OK`  keeps the 258 rows of 20250116 — their amounts are
#     correctly aligned — and only withholds the CATEGORY, which duplicates the
#     funding type. Exact the same way: **0 of 1,722 clean rows flagged, 533 of
#     533 on the two bad vintages.**
#
# ⚠ BOTH TEST THE DATA, NOT A DATE LIST. A hardcoded list of bad vintages goes
# stale the moment a ninth lands wrong, and this repo has paid for hardcoded
# ranges before.
# ⚠ NEITHER REPAIRS ANYTHING. Un-shifting 20230112 would mean asserting which
# fiscal year each amount belongs to — a claim about NYC's publication this data
# cannot support. The fix belongs in the ingest.
_STRATEGY_MONEY_OK = "\"Ten-Year Total\" IS NOT NULL AND \"Ten-Year Total\" <> ''"
_STRATEGY_CATEGORY_OK = (
    "\"Ten-Year Plan Category\" NOT IN ('City', 'Federal', 'State', 'Private')")


@app.get('/get/capitalprojects/stratcategory/{cslug}', tags=['Capital Projects'])
async def get_capital_projects_stratcategory(cslug: str):
    """Get capital strategy data filtered by category slug."""
    # ⚠⚠ SLUG BOTH SIDES THE SAME WAY. This matched on
    # `REPLACE(category, ' ', '-')`, which is NOT how Laravel builds the slug in
    # the URL: **12 of 138 categories carry a comma**, so
    # `large, major and regional park reconstruction` produced
    # `large,-major-and-...` here against `large-major-and-...` in the link, and
    # the page 404'd on its own URL.
    # ⚠ The `ILIKE '%…%'` fallback that used to rescue some of them is GONE, and
    # deliberately: it also matched `sewers` inside `COMBINED SEWERS AND WATER
    # MAINS`, so a category page could list another category's plan. An exact
    # slug comparison is either right or empty; a loose one is quietly wrong.
    return await select(
        'SELECT * FROM capitalstrategy '
        "WHERE trim(both '-' from regexp_replace(lower(\"Ten-Year Plan Category\"), "
        "'[^a-z0-9]+', '-', 'g')) = $1 "
        # ⚠ BOTH guards here: a category page needs a real category (or
        # `/projects/categories/city` becomes a page built from a funding type)
        # AND real money (or its plan chart is a fiscal year out).
        "  AND " + _STRATEGY_CATEGORY_OK + " AND " + _STRATEGY_MONEY_OK,
        (cslug.lower(),)
    )

@app.get('/get/capitalprojects/by_category/{cslug}', tags=['Capital Projects'])
async def get_capital_projects_by_category(cslug: str):
    """Get projects for a category from capitalprojectsdollarscomp.

    Why: The category pages need to show all projects in a category,
    not just 10. Matches by the slugified category column.
    """
    return await select(
        'SELECT * FROM capitalprojectsdollarscomp '
        'WHERE LOWER(REPLACE("wegov-project-category", \' \', \'-\')) = $1',
        (cslug.lower(),)
    )

@app.get('/get/pstats-records_no-by_category/tblname/{cslug}', tags=['Capital Projects'])
async def get_pstats_records_no_by_category(cslug: str):
    """The un-substituted template route. ⚠ `res: None`, not 0 — see below."""
    return _unscopable('(no table)', 'ten_year_category', cslug)


@app.get('/get/pstats-records_no-by_category/{tblname}/{cslug}', tags=['Capital Projects'])
async def get_pstats_records_no_by_category_real(tblname: str, cslug: str):
    """Records in one source table for one Ten-Year category.

    ⚠⚠ THE COLUMN MAP THIS REPLACES RETURNED **0** FOR EVERY TABLE IT HAD NO
    RULE FOR, and the shared provenance component reads 0 as "this dataset holds
    nothing for this scope — a finding". So widening this panel to the spine's
    three current sources published a confident, plausible, wrong zero about
    datasets the page's own table draws hundreds of projects from. That is why
    the panel was left narrow, and it is what `modules/capitalsources` ends.

    ⚠⚠ AND ITS `capitalbudget` ENTRY NAMED `"Ten-Year Plan Category"`, A COLUMN
    THAT TABLE DOES NOT HAVE — a live 500 (measured 2026-09-10), one of five
    such entries across the two scoped-count endpoints. `capitalbudget` carries
    no category dimension at all, so the honest answer is "cannot be scoped",
    which is `None` and renders `—`.

    ⚠ Slugged on BOTH sides through `modules/capitalslug`. Comparing resolved
    NAMES was tried and is wrong: `capitalstrategy` spells only 5 of the spine's
    138 category names identically and 124 match only after case-folding, so a
    name comparison read 0 on that source for 124 of 138 pages.
    """
    return await _scoped_source_count(tblname, 'ten_year_category',
                                      capitalslug.slug(cslug))

@app.get('/get/capitalcommitments/stats_by_budgetline/{blcode}', tags=['Capital Projects'])
async def get_capital_commitments_stats_by_budgetline(blcode: str):
    """Aggregate commitment plan data by Published Date + Funding Type for the OMB chart.

    Why: The budgetLineA template expects grouped stats with comm_no (count) and
    yr1amount-yr5amount (sums). Budget line formats vary across tables (spaces, dashes,
    none), so we try all variants.
    """
    # ⚠⚠ ONE NORMALISED QUERY, NOT A LIST OF GUESSED SPELLINGS — and the loop this
    # replaces returned a PARTIAL answer for most budget lines. It tried
    # `blcode`, a stripped form, and forms with a space or a hyphen inserted
    # after the leading alpha run, and RETURNED THE FIRST that yielded any rows.
    # `capitalcommitmentplan` genuinely spells one line several ways across
    # vintages, so "the first spelling with rows" silently drops the others.
    #
    # Measured 2026-09-10 over every row of that table:
    #
    #   1,817 of 2,724 distinct budget lines carry MORE THAN ONE spelling,
    #   covering 51,623 of 59,076 rows (87%), and each of those 1,817 lines
    #   loses exactly ONE publication vintage — 1,817 vintages absent from the
    #   chart's own date dropdown.
    #
    # `C 0075` holds 30 vintages (2016-04-26 → 2026-05-12) and `C -0075` holds
    # one (2018-10-10); the loop served whichever it reached first and the other
    # vintage did not exist as far as the page was concerned.
    #
    # ⚠ THE UNION IS PURELY ADDITIVE, MEASURED RATHER THAN ASSUMED: **0** group
    # keys `(normalised line, Published Date, Funding Type)` span two spellings,
    # so no group can merge and no figure can double-count. That check is what
    # makes this safe to change on a published chart.
    #
    # ⚠ `modules/budgetline` is the ONE owner of this rule, in both languages.
    # The hand-rolled variants here were a second spelling of it and could not
    # generate the padded single-letter form the sources use (`P -I001`,
    # `C -0075`) at all.
    norm = budgetline.norm(blcode)
    query = """
        SELECT "Published Date", "Funding Type",
               COUNT(*) as comm_no,
               MIN("First Fiscal Year") as "First Fiscal Year",
               SUM(CAST(COALESCE(NULLIF("Fiscal Year 1 Amount", ''), '0') AS NUMERIC)) as yr1amount,
               SUM(CAST(COALESCE(NULLIF("Fiscal Year 2 Amount", ''), '0') AS NUMERIC)) as yr2amount,
               SUM(CAST(COALESCE(NULLIF("Fiscal Year 3 Amount", ''), '0') AS NUMERIC)) as yr3amount,
               SUM(CAST(COALESCE(NULLIF("Fiscal Year 4 Amount", ''), '0') AS NUMERIC)) as yr4amount,
               SUM(CAST(COALESCE(NULLIF("Fiscal Year 5 Amount", ''), '0') AS NUMERIC)) as yr5amount
        FROM capitalcommitmentplan
        WHERE """ + budgetline.sql_norm('"Budget Line"') + """ = $1
        GROUP BY "Published Date", "Funding Type"
        ORDER BY "Published Date" DESC, "Funding Type"
    """
    result = await select(query, (norm,))
    if result.get('rows'):
        return result
    return {"rows": []}

@app.get('/get/commitments/by_budgetline/{blcode}', tags=['Capital Projects'])
async def get_commitments_by_budgetline(blcode: str):
    """Get commitments for a budget line from capitalprojectscommitments.

    Why: The commDatatable in budgetLineA.blade.php expects columns from
    capitalprojectscommitments (maprojid, projectdescription, plancommdate,
    typcname, wegov-org-id, etc.). Adds SQL aliases for normalizer columns
    that the DataTable expects but don't exist in the raw table.
    """
    import re
    query = """SELECT *, typcname AS "wegov-prjtype-name"
               FROM capitalprojectscommitments WHERE budgetline = $1"""
    # Generate all format variants
    stripped = blcode.replace(' ', '').replace('-', '')
    spaced = re.sub(r'^([A-Za-z]+)(\w)', r'\1 \2', stripped)
    dashed = re.sub(r'^([A-Za-z]+)(\w)', r'\1-\2', stripped)
    for v in dict.fromkeys([blcode, stripped, spaced, dashed]):
        result = await select(query, (v,))
        if result.get('rows'):
            # ⚠ ONE DATE FORMAT, AND IT BELONGS AT THE ENDPOINT. `plancommdate`
            # is already in `_DATE_COLUMNS`, but that labelling runs in
            # `routers/capital.py` and this endpoint never called it — so the
            # budget-line page rendered 10 raw `06/01/2026` cells beside a
            # sources table and a profile that both say `1 Jun 2026`. Served
            # BESIDE the raw value, never instead of it: `MM/DD/YYYY` is what
            # the City published and what a consumer joins on.
            for r in result['rows']:
                if 'plancommdate' in r:
                    r['plancommdate_label'] = _capital_mdy_label(r['plancommdate'])
            return result
    return {"rows": []}

@app.get('/get/pstats-records_no-by_budgetline/tblname/{blcode}', tags=['Capital Projects'])
async def get_pstats_records_no_by_budgetline(blcode: str):
    """The un-substituted template route. ⚠ `res: None`, not 0 — see below."""
    return _unscopable('(no table)', 'budget_line', blcode)


@app.get('/get/pstats-records_no-by_budgetline/{tblname}/{blcode}', tags=['Capital Projects'])
async def get_pstats_records_no_by_budgetline_real(tblname: str, blcode: str):
    """Records in one source table for one budget line.

    ⚠⚠ FOUR OF THIS ENDPOINT'S EIGHT COLUMN MAPPINGS NAMED A COLUMN THAT DOES
    NOT EXIST — every one a live 500, measured 2026-09-10 against
    `information_schema`:

        capprojectsbudgetsandschedule  "BUDGET_LINE"  -> it is "Budget Line"
        capprojectsbudgetandspend      "BUDGET_LINE"  -> no such column
        capprojectsbudgetspendhistory  "BUDGET_LINE"  -> no such column
        capprojectsschedulehistory     "BUDGET_LINE"  -> no such column

    The last three carry no budget-line dimension at all, so they now answer
    "cannot be scoped" (`None`, rendered `—`) rather than 500ing — and the first
    answers with real rows.

    ⚠⚠ AND THE TRY-EACH-SPELLING LOOP IS GONE. It returned the FIRST spelling
    with any rows, which on `capitalcommitmentplan` silently dropped a
    publication vintage for 1,817 of 2,724 budget lines — the same defect fixed
    in `/get/capitalcommitments/stats_by_budgetline` this session.
    `modules/budgetline` normalises both sides once.

    ⚠ An unmapped table returned **0**, which the provenance component reads as
    "this dataset holds nothing for this budget line — a finding". `None` is the
    honest answer and is a different claim.
    """
    return await _scoped_source_count(tblname, 'budget_line',
                                      budgetline.norm(blcode))

@app.get('/get/capitalcommitmentplan/all', tags=['Capital Projects'])
async def get_capital_commitment_plan_all():
    """Return commitment plan records for the 3 most recent publication dates.

    Why: prjCommitmentsA.blade.php DataTable expects a dataset with
    client-side filtering by Published Date and First Fiscal Year.
    Returning all 57K rows times out, so limit to 3 most recent dates.
    """
    return await select("""
        SELECT * FROM capitalcommitmentplan
        WHERE TRIM("Published Date") IN (
            SELECT DISTINCT TRIM("Published Date")
            FROM capitalcommitmentplan
            ORDER BY TRIM("Published Date") DESC
            LIMIT 3
        )
        ORDER BY "Published Date" DESC, "Budget Line"
    """)

@app.get('/get/capitalcommitmentplan/bydate/recent', tags=['Capital Projects'])
async def get_capital_commitment_plan_recent():
    return await select('SELECT DISTINCT "Published Date" FROM capitalcommitmentplan ORDER BY "Published Date" DESC LIMIT 5')

@app.get('/get/capitalcommitmentplan/bydate/{date}', tags=['Capital Projects'])
async def get_capital_commitment_plan_by_date(date: str):
    return await select('SELECT * FROM capitalcommitmentplan WHERE TRIM("Published Date") = $1', (date,))

@app.get('/get/capitalprojects/taxonomy/all', tags=['Capital Projects'])
async def get_capital_projects_taxonomy_all():
    """Aggregate project types from the Ten-Year Capital Strategy.

    Why: prjTypesA.blade.php DataTable expects pubdate, ptype_name, catnum,
    yr10_total, yr1_amt, plus budget/project columns (blnum, bl_yr4_total,
    cnum, pnum, budg_cost, curr_cost). Strategy data is the primary value;
    budget crossovers are zeroed until a proper ETL join is built.
    """
    return await select("""
        SELECT
            s."Published Date" as pubdate,
            CASE WHEN LENGTH(s."Project Type Description") > LENGTH(s."Project Type")
                 THEN s."Project Type Description"
                 ELSE s."Project Type" END as ptype_name,
            COUNT(DISTINCT s."Ten-Year Plan Category") as catnum,
            CAST(SUM(CAST(NULLIF(s."Ten-Year Total", '') AS NUMERIC)) AS NUMERIC) as yr10_total,
            CAST(SUM(CAST(NULLIF(s."Fiscal Year 1 Amount", '') AS NUMERIC)) AS NUMERIC) as yr1_amt,
            COALESCE(MAX(bl.blnum), 0) as blnum,
            COALESCE(MAX(bl.bl_yr4_total), 0) as bl_yr4_total,
            COALESCE(MAX(cm.cnum), 0) as cnum,
            COALESCE(MAX(p.prjnum), 0) as pnum,
            COALESCE(MAX(p.plannedcost), 0) as budg_cost,
            COALESCE(MAX(p.currcost), 0) as curr_cost
        FROM capitalstrategy s
        LEFT JOIN (
            SELECT
                UNNEST(STRING_TO_ARRAY("wegov-project-type-names", '; ')) AS ptype_name,
                COUNT(DISTINCT "PROJECT_ID") AS prjnum,
                SUM("BUDG_ORIG") AS plannedcost,
                SUM(TRIM(REPLACE(NULLIF("BUDG_CURR", ''), ',', '.'))::NUMERIC) AS currcost
            FROM capitalprojectsdollarscomp
            WHERE "PUB_DATE" = (
                SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp
                WHERE "STRATEGY_PUB_DATE" IS NOT NULL AND "STRATEGY_PUB_DATE" != ''
            )
            GROUP BY ptype_name
        ) p ON p.ptype_name = CASE WHEN LENGTH(s."Project Type Description") > LENGTH(s."Project Type")
                                    THEN s."Project Type Description"
                                    ELSE s."Project Type" END
        LEFT JOIN (
            SELECT
                "Project Type" AS ptype_code,
                COUNT(DISTINCT "Budget Line") AS blnum,
                SUM(
                    COALESCE(NULLIF("Fiscal Year 1 Amount", '')::NUMERIC, 0) +
                    COALESCE(NULLIF("Fiscal Year 2 Amount", '')::NUMERIC, 0) +
                    COALESCE(NULLIF("Fiscal Year 3 Amount", '')::NUMERIC, 0) +
                    COALESCE(NULLIF("Fiscal Year 4 Amount", '')::NUMERIC, 0)
                ) AS bl_yr4_total
            FROM capitalbudget
            WHERE "Published Date" = (SELECT MAX("Published Date") FROM capitalbudget)
            GROUP BY "Project Type"
        ) bl ON bl.ptype_code = CASE WHEN LENGTH(s."Project Type Description") < LENGTH(s."Project Type")
                                     THEN s."Project Type Description"
                                     ELSE s."Project Type" END
        LEFT JOIN (
            SELECT
                "Project Type" AS ptype_code,
                COUNT(*) AS cnum
            FROM capitalcommitmentplan
            WHERE "Published Date" = (SELECT MAX("Published Date") FROM capitalcommitmentplan)
            GROUP BY "Project Type"
        ) cm ON cm.ptype_code = CASE WHEN LENGTH(s."Project Type Description") < LENGTH(s."Project Type")
                                     THEN s."Project Type Description"
                                     ELSE s."Project Type" END
        GROUP BY s."Published Date",
                 CASE WHEN LENGTH(s."Project Type Description") > LENGTH(s."Project Type")
                      THEN s."Project Type Description"
                      ELSE s."Project Type" END
        ORDER BY s."Published Date" DESC, ptype_name
    """)

@app.get('/get/capitalprojects/taxonomy/{date}', tags=['Capital Projects'])
async def get_capital_projects_taxonomy(date: str):
    return await select('SELECT DISTINCT "Project Type" as type, count(*) as count FROM capitalprojectsdollarscomp WHERE "PUB_DATE" = $1 GROUP BY "Project Type" ORDER BY "Project Type"', (date,))

@app.get('/get/capitalprojects/type-slugs', tags=['Capital Projects'])
async def get_capital_project_type_slugs():
    """The set of project-type slugs that HAVE a page, so a caller can gate a link.

    ⚠⚠ THE TYPES INDEX LINKED EVERY ROW, AND 8 OF THEM CANNOT RESOLVE. Measured
    2026-09-10 by sweeping all 202 published names: 194 resolve and **8 return
    404** — `Day Care Facilities`, `Energy Conservation Projects`, `Ferry
    Maintenance Facility Construction`, `Low to Moderate Income Public Housing
    Construction`, `Miscellaneous Transit Improvement Projects`, `Rehabilitation
    of Court Buildings`, `Replacement of Electrical Distribution Systems`,
    `Vehicle Purchase or Retrofit`. None carries punctuation, so none is a slug
    casualty: their only rows live in the two defective `capitalstrategy`
    vintages, which the money guard drops. That is CORRECT behaviour — and a
    link to it is not. This section's standing rule is that a link landing on a
    404 is worse than text, and this is the fifth instance.

    ⭐ THE PREDICATE IS THE PAGE'S OWN. `/get/pstats-categories_by_type/{tslug}`
    returns rows exactly when `"Ten-Year Total"` is present, and the controller
    404s on an empty result — so resolvability is that condition and nothing
    else. Re-deriving it here with a second rule is the suffix-list defect: a
    gate that measures a different system than the thing it gates.

    ⚠ And the slug comes from `modules/capitalslug`, the one owner, so the
    caller never re-derives it — which is exactly how `/projects/types/{slug}`
    came to be unable to match its own URLs.
    """
    d = capitalslug.SLUG_SQL.format(col='s."Project Type Description"')
    t = capitalslug.SLUG_SQL.format(col='s."Project Type"')
    res = await select("""
        SELECT DISTINCT {d} AS d_slug, {t} AS t_slug
        FROM capitalstrategy s
        WHERE s."Ten-Year Total" IS NOT NULL AND s."Ten-Year Total" <> ''
    """.format(d=d, t=t))
    slugs = set()
    for r in res.get('rows', []):
        for key in ('d_slug', 't_slug'):
            v = (r.get(key) or '').strip()
            if v:
                slugs.add(v)
    return {"slugs": sorted(slugs), "count": len(slugs)}


@app.get('/get/pstats-categories_by_type/{tslug}', tags=['Capital Projects'])
async def get_pstats_categories_by_type(tslug: str):
    """The Ten-Year Capital Strategy's amounts for one project type.

    ⚠⚠ THIS WAS A MIXED PAGE AND NOTHING SAID SO. It LEFT JOINed
    `capitalprojectsdollarscomp` — the series NYC retired 2023-10-26 — for
    `prjnum`, `plannedcost` and `currcost`, and served them beside LIVE strategy
    amounts (`capitalstrategy`'s latest publication is 2025-05-01). Measured over
    25 sampled types / 362 rows: the join contributed a figure on **127 rows and
    zeros on the other 235**, so two thirds of the table read "0 projects,
    $0 planned" for real programmes. Those three columns are gone.

    ⚠⚠ AND THEY CANNOT BE REPLACED WITH SPINE FIGURES, WHICH IS THE WHOLE POINT.
    `capitalstrategy` has **no project key** — its columns are (Published Date,
    Project Type, Project Type Description, Ten-Year Plan Category, Funding Type,
    Fiscal Year 1-10 Amount, Ten-Year Total), 267 rows for a whole city. The join
    it used was on (publication date, CATEGORY), so it attributed a whole
    category's projects to one type; a category spans many types, and doing the
    same thing against the spine would be the identical error with fresher
    numbers. **A project count belongs on the category page, which has one.**

    ⚠ The category cell links there, which is the honest connection: same
    vocabulary, and that page now lists the spine's projects.

    ⚠⚠ AND ITS SLUG WAS A THIRD SPELLING, WHICH MADE 18 REAL TYPE PAGES
    UNREACHABLE — measured 2026-09-10, and it is the category endpoints' own
    defect surviving in the one place that was never migrated. The WHERE
    compared `LOWER(REGEXP_REPLACE(REPLACE(name, ' ', '-'), '-+', '-', 'g'))`,
    which replaces SPACES only: an apostrophe, an ampersand, a comma or a slash
    survives into a slug no URL can ever carry.

        Department of Parks & Recreation        -> department-of-parks-&-recreation
        Children's Services                     -> children's-services
        DEP - Water Mains, Sources and Treatment -> …water-mains,-sources-and-treatment

    Of 236 distinct type descriptions, **18 slug differently from
    `modules/capitalslug`, every one of them carries usable rows, and 212 usable
    rows were stranded** behind a URL that could not be typed. `Department of
    Parks & Recreation` alone holds 76.

    ⭐ IT RECONCILES, which is why the diagnosis is trustworthy: a sweep of the
    rendered index found **26** published type names returning 404, and
    18 slug-defect + 8 genuinely-empty = 26 — the 8 matching the "228 types
    survive, 8 correctly 404" figure measured independently on 2026-09-08.

    ⚠ I first attributed all of these to the two defective `capitalstrategy`
    vintages and recorded that in a handoff. **That was wrong**, and the tell was
    that `Department of Parks & Recreation` is not a marginal programme. Checking
    the row counts rather than reasoning from a known nearby defect is what
    separated the 18 from the 8.
    """
    # ⚠ BUILT FROM THE ONE OWNER, never re-typed here. `SLUG_SQL` is a format
    # string taking `{col}`, so the two comparisons cannot drift from each other
    # or from `capitalslug.slug()` — which is the property a guard asserts by
    # parsing the character class back out of the emitted SQL.
    _d = capitalslug.SLUG_SQL.format(col='s."Project Type Description"')
    _t = capitalslug.SLUG_SQL.format(col='s."Project Type"')
    return await select("""
        SELECT
            CASE WHEN LENGTH(s."Project Type") <= 10 THEN s."Project Type"
                 ELSE s."Project Type Description" END AS prjtype,
            CASE WHEN LENGTH(s."Project Type Description") > 10 THEN s."Project Type Description"
                 ELSE s."Project Type" END               AS prjtypename,
            s."Published Date"                          AS pubdate,
            s."Ten-Year Plan Category"                  AS category,
            s."Funding Type"                            AS fundingsource,
            SUM(NULLIF(s."Fiscal Year 1 Amount", '')::BIGINT) AS year1amount,
            SUM(NULLIF(s."Ten-Year Total", '')::BIGINT)       AS year10total
        FROM capitalstrategy s
        WHERE ({d} = $1
            OR {t} = $1)
          -- ⚠ MONEY GUARD ONLY. Excluding the funding-type-as-category rows too
          -- emptied **162 of 236 type pages**, because most types appear only in
          -- the two defective vintages. Their AMOUNTS are fine on 20250116; it is
          -- the category label that is missing, and the view says so per row
          -- rather than the endpoint discarding the money.
          AND s."Ten-Year Total" IS NOT NULL AND s."Ten-Year Total" <> ''
        GROUP BY s."Project Type",
                 s."Project Type Description",
                 s."Published Date",
                 s."Ten-Year Plan Category",
                 s."Funding Type"
        ORDER BY s."Published Date" DESC, s."Ten-Year Plan Category"
    """.format(d=_d, t=_t), (capitalslug.slug(tslug),))


@app.get('/delete/{tbl}', tags=['Datasets'], summary="Delete dataset", 
        responses={200: {'description': 'Success', 'content': {'application/json': {'example': {'result': 'OK'}}}},
                   404: {'description': 'Failed', 'content': {'application/json': {'example': {'result': 'Not found'}}}}}
         )
def delete_dataset_in_database(tbl:str, user=Security(manager, scopes=['admin'])):
    """
    Delete dataset table in database:

    - **tbl**: Table name same as dataset name to delete

    ⚠ Requires the `admin` scope, NOT merely `write` — this DROPs a table. A data
    operator (`write`) must not reach it, and the app's own service token is
    `write`, so it cannot either. The name is validated against a plain-identifier
    pattern AND actual existence in `CsvDataset.delete` before any DROP (it used
    to be interpolated raw). No caller in the app or pipeline references this.
    """
    ds = CsvDataset()
    if ds.delete(tbl):
        return {'result': 'OK'}
    else:
        return JSONResponse(status_code=404, content={'result': 'Not found'})

# ================ People Search ================

@app.get('/search/people/{req}/{tbl}', tags=['People'])
async def search_people(req: str, tbl: str):
    """Search for people across multiple datasets.

    Why: The Laravel peoplesearchresults blade expects rows with fullname,
    date, wegov-org-id, wegov-org-name, tbl, and perm-id fields.
    The perm-id must use table prefix + numeric hash (e.g. cl12345)
    because the person controller parses the prefix to determine the table.
    Perm-id is computed in Python to avoid slow SQL MD5 on every row.
    """
    import hashlib
    import re as _re

    search_term = _re.sub(r'\s+', ' ', req.replace('+', ' ')).strip()
    pattern = f'%{search_term}%'

    queries = {
        'civillist': """
            SELECT
                TRIM("EMPLOYEE NAME") AS fullname,
                "CALENDAR YEAR" AS date,
                COALESCE("wegov-org-id", '') AS "wegov-org-id",
                COALESCE("wegov-org-name", '') AS "wegov-org-name",
                'civillist' AS tbl
            FROM civillist
            WHERE "EMPLOYEE NAME" ILIKE $1
            LIMIT 200
        """,
        'civillistactive': """
            SELECT
                TRIM("First Name" || ' ' || "Last Name") AS fullname,
                "Published Date" AS date,
                COALESCE("List Agency Code", '') AS "wegov-org-id",
                COALESCE("List Agency Desc", '') AS "wegov-org-name",
                'civillistactive' AS tbl
            FROM civillistactive
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 200
        """,
        'nycgreenbook': """
            SELECT
                TRIM("First Name" || ' ' || "Last Name") AS fullname,
                '' AS date,
                COALESCE("wegov-org-id", '') AS "wegov-org-id",
                COALESCE("wegov-org-name", '') AS "wegov-org-name",
                'nycgreenbook' AS tbl
            FROM nycgreenbook
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 200
        """,
        'payrolldata': """
            SELECT
                TRIM("First Name" || ' ' || "Last Name") AS fullname,
                COALESCE("Agency Start Date", '') AS date,
                COALESCE("wegov-org-id", '') AS "wegov-org-id",
                COALESCE("wegov-org-name", '') AS "wegov-org-name",
                'payrolldata' AS tbl
            FROM payrolldata
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 200
        """,
    }

    prefixes = {'civillist': 'cl', 'civillistactive': 'cla',
                'nycgreenbook': 'gb', 'payrolldata': 'pr'}

    if tbl == 'all':
        parts = list(queries.values())
    elif tbl in queries:
        parts = [queries[tbl]]
    else:
        return {'rows': []}

    full_query = ' UNION ALL '.join(f'({q})' for q in parts)
    result = await select(full_query, (pattern,))
    rows = result.get('rows', result) if isinstance(result, dict) else result

    # Add perm-id in Python (fast) instead of SQL (slow)
    for row in rows:
        key = f"{row['fullname']}|{row['date']}|{row['wegov-org-name']}|{row['tbl']}"
        h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
        row['perm-id'] = prefixes.get(row['tbl'], 'xx') + str(h)

    return {'rows': rows}


@app.get('/get/people/{pid}', tags=['People'])
async def get_person(pid: str, name: str = ''):
    """Look up a person by their perm-id (prefix + numeric hash).

    Why: The person controller parses the prefix (cl, cla, gb, pr) to
    determine the source table. We use an optional name query param to
    narrow the search, then match the hash for the exact record.
    If no name param, we fall back to scanning more broadly.
    """
    import re
    import hashlib
    m = re.match(r'^(cla|cl|gb|pr)(\d+)$', pid)
    if not m:
        return []
    prefix, uid = m.group(1), m.group(2)

    table_map = {'cl': 'civillist', 'cla': 'civillistactive',
                 'gb': 'nycgreenbook', 'pr': 'payrolldata'}
    tbl = table_map[prefix]

    # Search by name within the specific table (fast ILIKE)
    # If no name provided, we try to extract from referrer or scan broadly
    if name:
        search_name = name.replace('-', ' ').replace('+', ' ').strip()
        pattern = f'%{search_name}%'
    else:
        pattern = '%'  # fallback: broad scan (limited)

    name_queries = {
        'cl': """
            SELECT *
            FROM civillist
            WHERE "EMPLOYEE NAME" ILIKE $1
            LIMIT 500
        """,
        'cla': """
            SELECT *, '' AS "wegov-org-id", "List Agency Desc" AS "wegov-org-name"
            FROM civillistactive
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 500
        """,
        'gb': """
            SELECT * FROM nycgreenbook
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 500
        """,
        'pr': """
            SELECT * FROM payrolldata
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 500
        """,
    }

    result = await select(name_queries[prefix], (pattern,))
    rows = result.get('rows', result) if isinstance(result, dict) else result

    for row in rows:
        if tbl == 'civillist':
            rname = (row.get('EMPLOYEE NAME   ', row.get('EMPLOYEE NAME', ''))).strip()
            key = f"{rname}|{row.get('CALENDAR YEAR', '')}||{tbl}"
        elif tbl == 'civillistactive':
            rname = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
            key = f"{rname}|{row.get('Published Date', '')}|{row.get('List Agency Desc', '')}|{tbl}"
        elif tbl == 'nycgreenbook':
            rname = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
            key = f"{rname}||{row.get('wegov-org-name', '')}|{tbl}"
        else:  # payrolldata
            rname = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
            key = f"{rname}|{row.get('Agency Start Date', '')}|{row.get('wegov-org-name', '')}|{tbl}"

        h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
        if str(h) == uid:
            if tbl == 'civillist':
                row['EMPLOYEE NAME'] = rname
            return {'rows': [row]}

    # Fallback: return first match if hash not found
    if rows:
        row = rows[0]
        if tbl == 'civillist':
            row['EMPLOYEE NAME'] = (row.get('EMPLOYEE NAME   ', row.get('EMPLOYEE NAME', ''))).strip()
        return {'rows': [row]}

    return {'rows': []}


# ================ Chatbot ================

from pydantic import BaseModel
from typing import List, Dict

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

@app.post('/api/chat', tags=['Chatbot'], summary="Chat with AI assistant")
async def chat_with_assistant(request: ChatRequest):
    """
    Chat with the Databook AI assistant.
    The assistant can search organizations, capital projects, contracts, and more.
    
    - **message**: User's message
    - **history**: Optional conversation history
    """
    try:
        from chatbot import chat
        
        # Convert history to the format expected by chatbot
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]
        
        # Call the async chat function
        response = await chat(request.message, history)
        
        return {"response": response}
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"Chat error: {error_msg}")
        traceback.print_exc()
        
        # Check for rate limit errors and return friendly message
        if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
            return {"response": "I'm temporarily unavailable due to high usage. Try again later or connect the DatabookNYC MCP server to your own AI assistant by following instructions at <a href='https://databook.nyc/mcp' target='_blank'>databook.nyc/mcp</a>."}
        elif "INVALID_ARGUMENT" in error_msg:
            return {"response": "I had trouble processing that request. Please try rephrasing your question."}
        else:
            return {"response": "I encountered an error. Please try again."}


# ================ Newsletter Admin ================

@app.get('/admin/newsletter/preview', tags=['Newsletter'], summary="Preview newsletter HTML")
async def preview_newsletter():
    """
    Generate and preview the weekly newsletter.
    Returns the full HTML that would be sent to subscribers.
    """
    from fastapi.responses import HTMLResponse
    try:
        from newsletter_generator import generate_newsletter
        html = await generate_newsletter()
        return HTMLResponse(content=html)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@app.post('/admin/newsletter/send', tags=['Newsletter'], summary="Send newsletter")
async def send_newsletter_now(
    test_email: Optional[str] = None,
    user=Security(manager, scopes=['write'])
):
    """
    Send the weekly newsletter.
    
    - **test_email**: If provided, send only to this email (test mode)
    - Without test_email, sends to all subscribers from AirTable
    
    Requires write scope (admin access).
    """
    try:
        from newsletter_generator import generate_newsletter
        from newsletter_sender import send_newsletter
        
        html = await generate_newsletter()
        
        if test_email:
            result = await send_newsletter(html, test_only=True, test_email=test_email)
        else:
            result = await send_newsletter(html)
        
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@app.get('/admin/newsletter/validate', tags=['Newsletter'], summary="Validate newsletter links")
async def validate_newsletter_links_endpoint():
    """
    Generate the newsletter and test all links.
    Returns an HTML report showing link status.
    """
    from fastapi.responses import HTMLResponse
    try:
        from newsletter_generator import generate_newsletter
        from newsletter_link_validator import validate_newsletter_links
        
        # Generate newsletter
        html = await generate_newsletter()
        
        # Validate all links
        result = await validate_newsletter_links(html)
        
        return HTMLResponse(content=result["report_html"])
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


if __name__ == '__main__':
    Popen(['python', '-m', 'https_redirect'])
    uvicorn.run(
        'main:app', port=443, host='0.0.0.0',
        reload=True, workers=4,
        ssl_keyfile='/etc/letsencrypt/live/databook-api.wegov.nyc/privkey.pem',
        ssl_certfile='/etc/letsencrypt/live/databook-api.wegov.nyc/fullchain.pem')