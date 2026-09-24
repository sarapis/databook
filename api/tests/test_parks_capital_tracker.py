"""Guards on the NYC Parks Capital Project Tracker loader.

⚠⚠ WHY THE FEED AND NOT SOCRATA. `4hcv-tc5r` is the Socrata mirror of this very
feed, marked "Daily / Automation: Yes" with `rowsUpdatedAt` = today — and it
returned **0 rows** when measured 2026-09-03, every column `non_null = 0`, while
the Parks-hosted JSON had 2,244 records at the same moment. Registering the
Socrata id would have silently served an empty table under a fresh timestamp.

⚠⚠ AND THE NESTED FIELDS ARE WRAPPED, WHICH FAILS AS SUCCESS. The feed publishes

    "FundingSources": {"FundingSource": ["City Council"]}
    "Locations":      {"Location": [{"name": ..., "ParkID": ..., "Latitude": ...}]}

Iterating those dicts yields their KEYS, so the first draft of the loader wrote
the literal string "FundingSource" once per project — **2,244 rows, exactly the
project count, which is what made it look like a working load** — and produced 0
locations. After unwrapping: 3,408 funding rows across six real sources
(Mayoral 1,554, City Council 1,001, Borough President 431, Federal 155, Private
153, State 114) and 2,758 locations, every one with coordinates.

The lesson is in the numbers: a child-table count equal to the parent count is
the tell.
"""
import importlib.util
import os
import re

import pytest

API = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
LOADER = os.path.join(API, 'extractors', 'parks_capital_tracker.py')
SCHEDULER = os.path.join(API, 'data_scheduler.py')
SETUP = os.path.join(API, 'setup_data_pipeline.py')


def _src(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _load():
    spec = importlib.util.spec_from_file_location('parks_capital_tracker', LOADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


parks = _load()


def test_it_reads_the_feed_not_the_empty_socrata_mirror():
    assert 'nycgovparks.org' in parks.FEED_URL, (
        'the loader must read the Parks feed; the Socrata mirror 4hcv-tc5r '
        'served 0 rows while advertising a same-day refresh')
    setup = _src(SETUP)
    m = re.search(r'"parkscapitaltracker":\s*\{[^}]*\}', setup, re.S)
    assert m, 'parkscapitaltracker has no METADATA_CORRECTIONS entry'
    assert '4hcv-tc5r' not in m.group(0), (
        'registering the Socrata id would ingest the empty mirror')


@pytest.mark.parametrize('wrapper,inner,expected', [
    ({"FundingSource": ["City Council", "Mayoral"]}, 'FundingSource',
     ["City Council", "Mayoral"]),
    ({"Location": [{"name": "A"}]}, 'Location', [{"name": "A"}]),
    # a bare list still works, so a future feed dropping the wrapper is fine
    (["City Council"], 'FundingSource', ["City Council"]),
    # a single non-list value is wrapped rather than iterated
    ({"Borough": "Queens"}, 'Borough', ["Queens"]),
    (None, 'Location', []),
])
def test_unwrap_returns_the_inner_list_never_the_keys(wrapper, inner, expected):
    assert parks._unwrap(wrapper, inner) == expected


def test_unwrap_never_yields_a_dict_key():
    """The exact defect: iterating {"FundingSource": [...]} gives "FundingSource"."""
    got = parks._unwrap({"FundingSource": ["City Council"]}, "FundingSource")
    assert "FundingSource" not in got, (
        'unwrapping must not return the wrapper key — that is the bug that '
        'wrote one bogus funding row per project')


def test_the_loader_refuses_an_empty_feed():
    """⚠ The Socrata mirror proves an empty response is a real state. Accepting
    it silently replaces 2,244 projects with nothing and reports success."""
    src = _src(LOADER)
    assert 'refusing to replace the table' in src, (
        'a 0-record feed must be refused, not loaded')
    assert 'live * 0.5' in src, 'a >50% row drop must be refused'


def test_the_scheduler_branches_to_the_json_loader():
    """⚠ The feed is JSON; the CSV loader cannot read it. This follows the
    per-table precedent `contracts` set rather than inventing a mechanism."""
    src = _src(SCHEDULER)
    m = re.search(r'async def process_extractor_dataset.*?\n\nasync def', src, re.S)
    assert m, 'process_extractor_dataset not found'
    body = m.group(0)
    assert 'parkscapitaltracker' in body and 'import_parks_tracker' in body, (
        'the Parks feed must be branched inside process_extractor_dataset so it '
        'rides the existing daily extractor schedule')


def test_it_is_registered_as_an_extractor():
    setup = _src(SETUP)
    assert re.search(r'"parkscapitaltracker":\s*\([^)]*"extractor"', setup), (
        'parkscapitaltracker must be source_type=extractor — the Socrata path '
        'would try to CSV-parse a JSON feed')
    assert 'parkscapitaltracker' in parks.TABLE


def test_the_child_tables_are_separate():
    """A project with five sites and three funders is not five rows of project."""
    assert parks.LOCATIONS_TABLE != parks.TABLE
    assert parks.FUNDING_TABLE != parks.TABLE
    assert parks.BOROUGH_TABLE != parks.TABLE


def test_the_date_fields_match_the_feed():
    """⚠ The feed uses `DesignStart`, not `DesignStartDate` — the first draft
    invented the longer names and every start date came back NULL."""
    for f in ('DesignStart', 'ProcurementStart', 'ConstructionStart'):
        assert f in parks.FIELDS, f'{f} is the feed\'s own name'
        assert f + 'Date' not in parks.FIELDS
