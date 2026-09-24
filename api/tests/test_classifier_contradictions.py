"""Guards for the classifier self-contradiction scan.

⚠ These CALL the functions rather than scanning the source for a word. The
per-seat guard in this repo scanned for the string `return None` and matched the
`except` clause, so it passed against a defaulting implementation for as long as
it existed — invariant 26. Every assertion here runs the real grouping over a
fixture and reads what comes back.
"""
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "scan_classifier_contradictions.py")


def _load():
    """⚠ BY PATH, and with the api root on sys.path. `conftest.py` replaces the
    whole `modules` package with a MagicMock, so a plain import can hand back a
    mock whose every attribute satisfies any assertion — this repo has shipped
    exactly that twice. Loading by path executes the real file."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    spec = importlib.util.spec_from_file_location("_scan_contradictions", SRC)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:                                  # pragma: no cover
        pytest.skip(f"scan module needs the api runtime: {exc}")
    return mod


def _row(cid, val, tech, title, vendor="ACME", agency="DOITT", curated=False):
    return {"contract_id": cid, "val": val, "tech_relevant": tech,
            "function_category": "Payments", "curated": curated,
            "contract_title": title, "vendor_name": vendor, "agency": agency}


def test_the_procurement_vehicle_is_stripped_so_one_programme_is_one_key():
    """⚠⚠ THE LARGEST CONTRADICTION IN THE CORPUS DEPENDS ON THIS. WEX BANK's
    fuel-card programme is written `Fuel Card Services Amendment #1` on one
    instrument and `FUEL CARD SERVICES - OGS Extension 1 Year` on the next. OGS
    is the STATE CONTRACT IT RIDES, not the thing being bought, so leaving it in
    splits one programme into two keys and hides $21.1M."""
    m = _load()
    assert m.norm_title("Fuel Card Services Amendment #1") == \
           m.norm_title("FUEL CARD SERVICES - OGS Extension 1 Year")
    # ...and renewal bookkeeping likewise.
    assert m.norm_title("Politico subscription.") == m.norm_title("Politico subscription")
    # ⚠ But it must NOT collapse two genuinely different programmes.
    assert m.norm_title("Fuel Card Services") != m.norm_title("Merchant Card Services")


def test_a_vendor_doing_both_kinds_of_work_is_not_a_contradiction():
    """⚠⚠ THIS IS THE CALIBRATION, AND DROPPING THE TITLE FROM THE KEY DESTROYS
    IT. Measured over the corpus: grouping on (agency, vendor) alone reports 250
    groups / $612.9M, because an IT reseller legitimately has non-tech lines too
    (COMPULINK is 65 tech rows against 4 non-tech at DoITT). Adding the title
    takes it to 18 groups / $26.4M. A firm doing two DIFFERENT things must
    produce no finding."""
    m = _load()
    found = m.contradictions([
        _row("A", 1e6, True, "Network Switch Installation"),
        _row("B", 2e6, False, "Office Furniture Delivery"),
    ])
    assert found == [], "a vendor doing two different things is not a contradiction"


def test_the_same_programme_classified_both_ways_is_reported_with_its_stake():
    m = _load()
    found = m.contradictions([
        _row("A", 21_000_000, True, "Fuel Card Services Amendment #1"),
        _row("B", 2_500_000, False, "FUEL CARD SERVICES - OGS Renewal #1"),
    ])
    assert len(found) == 1
    g = found[0]
    assert [r["contract_id"] for r in g["tech"]] == ["A"]
    assert [r["contract_id"] for r in g["non"]] == ["B"]
    # ⚠ The stake is what is still IN the universe and not already decided —
    # not the group's total, which would double-count the side being questioned.
    assert g["stake"] == pytest.approx(21_000_000)
    assert g["human_decided"] is False


def test_an_already_curated_side_is_flagged_and_leaves_the_stake():
    """A human having decided one side is the stronger signal and points at how
    the pair resolves; and a curated row must not be counted as still at stake."""
    m = _load()
    found = m.contradictions([
        _row("A", 5e6, True, "Card Program"),
        _row("B", 9e6, False, "Card Program", curated=True),
        _row("C", 4e6, True, "Card Program", curated=True),
    ])
    assert len(found) == 1
    assert found[0]["human_decided"] is True
    # A ($5M) is at stake; C is already decided even though it is on the tech side.
    assert found[0]["stake"] == pytest.approx(5e6)


def test_a_form_name_is_flagged_but_never_dropped():
    """⚠ `260 Discretionary Contract` is carried by 999 vendors — it is a FORM,
    so the group cannot claim to be one programme. It is still reported, because
    the pair may be a real inconsistency; only the 'one programme' claim goes."""
    m = _load()
    rows = [_row("A", 6e5, True, "260 Discretionary Contract", vendor="V0"),
            _row("B", 6e5, False, "260 Discretionary Contract", vendor="V0")]
    # enough other vendors on the same title to make it generic
    rows += [_row(f"X{i}", 1e3, True, "260 Discretionary Contract", vendor=f"V{i}")
             for i in range(1, m.GENERIC_TITLE_VENDORS + 3)]
    found = m.contradictions(rows)
    generic = [g for g in found if g["key"][1] == "V0"]
    assert len(generic) == 1, "a form-name group must still be reported"
    assert generic[0]["generic_title"] is True

    # ...and a title only this vendor uses is NOT flagged.
    solo = m.contradictions([_row("A", 1e6, True, "Fuel Card Services"),
                             _row("B", 1e6, False, "Fuel Card Services")])
    assert solo[0]["generic_title"] is False


def test_a_title_that_normalises_to_nothing_groups_nothing():
    """Otherwise every id-only title in the corpus collapses into one giant
    group and the scan reports a contradiction that is an artefact of the key."""
    m = _load()
    assert m.norm_title("#1 2024") == ""
    assert m.contradictions([_row("A", 1e6, True, "#1 2024"),
                             _row("B", 1e6, False, "20250001")]) == []


def test_the_scan_refuses_a_corpus_too_small_to_have_scanned_anything():
    """⚠ A ZERO MUST NOT READ AS A CLEAN BILL OF HEALTH. If the join or the
    enrichment table moves, the scan must fail loudly — the oldest defect in
    this repo is a check that reports zero because it never ran."""
    m = _load()
    assert m.MIN_CORPUS >= 5000, "the floor must exceed any plausible partial read"


def test_the_vendors_own_name_inside_its_title_does_not_split_the_key():
    """⚠⚠ THE VENDOR IS ALREADY IN THE GROUP KEY, so repeating it in the title
    adds nothing and only splits. DOF's `General Banking Services - Bank of
    America` and `General Banking Services BOA NAE` are one programme from one
    vendor at one agency, classified tech and non-tech — $6.9M invisible without
    this, including the initialism that closes `BOA`."""
    m = _load()
    v = "BANK OF AMERICA NA"
    assert m.norm_title("General Banking Services - Bank of America", v) == \
           m.norm_title("General Banking Services BOA NAE", v)
    found = m.contradictions([
        _row("A", 6.9e6, True, "General Banking Services - Bank of America", vendor=v),
        _row("B", 2.1e6, False, "General Banking Services BOA NAE", vendor=v),
    ])
    assert len(found) == 1 and found[0]["stake"] == pytest.approx(6.9e6)


def test_a_title_that_is_only_the_vendor_name_falls_back_instead_of_vanishing():
    """⚠⚠ MEASURED: stripping the vendor without this fallback gains Bank of
    America ($6.9M) and LOSES First Data ($2.0M), whose title IS its name. The
    fallback keeps both. A key of `inc` is the same failure one step on — legal
    forms are stripped from the title, so the residue cannot be junk shared by
    100 vendors."""
    m = _load()
    v = "FIRST DATA MERCHANT SERVICES LLC"
    assert m.norm_title("First Data Amendment #1", v) != ""
    found = m.contradictions([
        _row("A", 2e6, True, "First Data Amendment #1", vendor=v),
        _row("B", 9.1e6, False, "First Data Amendment #1", vendor=v),
    ])
    assert len(found) == 1, "a title that is only the vendor name must still group"
    # ...and a legal form never survives alone as the key.
    assert m.norm_title("FEDCAP REHABILITATION SERVICES, INC. Amendment #1",
                        "FEDCAP REHABILITATION SERVICES INC") not in ("inc", "llc", "")


def test_genericness_is_measured_on_the_title_not_on_the_stripped_key():
    """⚠ Asking it of the vendor-stripped residue answers a different question:
    `Politico subscription` reported as generic because 22 other vendors have the
    word `subscription` somewhere. The form-name claim is about what the TITLE
    says."""
    m = _load()
    rows = [_row("A", 1e6, True, "Politico subscription.", vendor="Politico LLC"),
            _row("B", 1e6, False, "Politico subscription", vendor="Politico LLC")]
    # many other vendors whose titles merely contain the shared residue word
    # ⚠ THE FIXTURE MUST SEPARATE THE TWO MEASUREMENTS OR THE GUARD IS SILENT —
    # it was, on first writing. Each of these strips to exactly `subscription`
    # (its own name is the only other token), so they share Politico's STRIPPED
    # key while their PLAIN titles are all different. Measuring on the stripped
    # key therefore calls Politico generic; measuring on the title does not.
    rows += [_row(f"X{i}", 1e3, True, f"Widgetco{i} subscription", vendor=f"Widgetco{i} Corp")
             for i in range(m.GENERIC_TITLE_VENDORS + 3)]
    g = [x for x in m.contradictions(rows) if x["key"][1] == "Politico LLC"]
    assert len(g) == 1
    assert g[0]["generic_title"] is False, \
        "a distinctive title must not read as a form name because its residue is common"


# --- the second axis: a decision not carried to its own siblings -------------
# ⚠⚠ THESE EXIST BECAUSE THE TITLE KEY WAS MEASURABLY BLIND. Two real rows were
# found 2026-09-16 by asking the mechanical question instead, and neither was
# reachable by `contradictions()` nor by a title-word sweep on
# `(interpret|translat)` — because one title is the vendor's brand
# (`Language Line Renewal Amendment #1`) and the other is the vendor's brand
# plus a fiscal year (`FY22 TotalCaption LLC Renewal #1`).


def test_a_decision_not_carried_to_its_own_sibling_is_reported():
    """The whole property. A human excluded one contract; another from the same
    vendor at the same agency is still flagged tech."""
    m = _load()
    recs = [
        _row("CT1-056-2", 4.9e6, False, "Language Line Renewal #2",
             vendor="LANGUAGE LINE SERVICES, INC.", agency="NYPD", curated=True),
        _row("CT1-056-1", 5.0e5, True, "Language Line Renewal Amendment #1",
             vendor="LANGUAGE LINE SERVICES, INC.", agency="NYPD"),
    ]
    out, n_pairs = m.unapplied_decisions(recs)
    assert n_pairs == 1, "it must report how many decided pairs it gated on"
    assert [d["row"]["contract_id"] for d in out] == ["CT1-056-1"]
    assert [p["contract_id"] for p in out[0]["peers"]] == ["CT1-056-2"], \
        "it must name the decision that was already taken, not just the stray row"


def test_the_sibling_axis_reaches_a_title_the_group_key_cannot():
    """⚠⚠ THE REASON IT EXISTS. Both rows are one service and the titles share
    no programme word, so the title key groups nothing — and must not, since
    `Language Line` normalises to the vendor's own name and falls back. The
    contradiction scan is silent on exactly the pair the sibling scan catches."""
    m = _load()
    recs = [
        _row("CT1-002-2", 99999, False, "Communication Access Real-time Translation (CART)",
             vendor="TOTALCAPTION LLC", agency="MAYORALTY", curated=True),
        _row("CT1-002-1", 99999, True, "FY22 TotalCaption LLC Renewal #1",
             vendor="TOTALCAPTION LLC", agency="OFFICE OF CRIMINAL JUSTICE (002)"),
    ]
    assert m.contradictions(recs) == [], \
        "if the title key ever DOES group these, this guard is measuring the wrong thing"
    out, _ = m.unapplied_decisions(recs)
    assert [d["row"]["contract_id"] for d in out] == ["CT1-002-1"]
    assert out[0]["cross_body"] is True, \
        "one agency CODE with two agency STRINGS must be flagged, never hidden"


def test_a_row_the_owner_KEPT_never_gates_anything():
    """⚠ A human excluding one contract does not decide the next. The owner kept
    two interpretation contracts while excluding three; a kept row carries no
    curated exclusion, so it must gate nothing — otherwise deciding to keep
    something would start flagging its siblings."""
    m = _load()
    recs = [
        _row("CT1-858-2", 1e6, True, "Tablets with video relay",
             vendor="KYNDRYL", agency="DOITT", curated=True),   # kept, and curated tech
        _row("CT1-858-1", 2e5, True, "Something else entirely",
             vendor="KYNDRYL", agency="DOITT"),
    ]
    out, n_pairs = m.unapplied_decisions(recs)
    assert n_pairs == 0 and out == []


def test_a_decision_at_one_agency_does_not_gate_the_same_vendor_elsewhere():
    m = _load()
    recs = [
        _row("CT1-858-2", 1e6, False, "Lab tests", vendor="ACME",
             agency="DOITT", curated=True),
        _row("CT1-846-1", 2e5, True, "Lab tests", vendor="ACME", agency="PARKS"),
    ]
    out, n_pairs = m.unapplied_decisions(recs)
    assert n_pairs == 1 and out == [], \
        "the vendor is the same and the agency is not; that is not an unapplied decision"


def test_the_sibling_scan_reports_zero_pairs_so_a_caller_can_refuse_a_vacuous_clean_bill():
    """⚠⚠ ITS ZERO IS MEANINGLESS UNLESS IT GATED ON SOMETHING. With no curated
    exclusion loaded the result is [] for EVERY corpus, which reads as 'every
    decision has been applied' — this repo's oldest defect. The count is the
    only thing that tells the two apart, so it is part of the return value and
    `main()` refuses below MIN_DECIDED_PAIRS."""
    m = _load()
    recs = [_row("CT1-858-1", 2e5, True, "Anything at all", vendor="ACME")]
    out, n_pairs = m.unapplied_decisions(recs)
    assert out == [] and n_pairs == 0
    assert m.MIN_DECIDED_PAIRS > 0, \
        "a floor of zero would make the refusal unreachable and the zero vacuous again"


# --- the sheet must not eat a decision ---------------------------------------


def _one_group(m):
    recs = [_row("CT1-858-1", 1e6, True, "Widget platform"),
            _row("CT1-858-2", 2e6, False, "Widget platform")]
    found = m.contradictions(recs)
    assert found, "fixture must produce a group, or the assertions below are vacuous"
    return found


def _sheet_with(tmp_path, m, **decided):
    """A real sheet on disk, written through the module's own field list."""
    p = tmp_path / "contradictions.csv"
    import csv as _csv
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write("# header comment the reader must skip\n")
        w = _csv.DictWriter(fh, fieldnames=m.CSV_FIELDS, quoting=_csv.QUOTE_ALL)
        w.writeheader()
        for cid, (verdict, note) in decided.items():
            row = {k: "" for k in m.CSV_FIELDS}
            row.update({"contract_id": cid.replace("_", "-"),
                        "verdict": verdict, "note": note})
            w.writerow(row)
    return str(p)


def test_a_recorded_verdict_survives_a_rerun(tmp_path):
    """⚠⚠ MEASURED 2026-09-16: it did not. A verdict written into the sheet came
    back blank on the next `--csv`, and a verdict of `ok` produces NO seed row —
    so the worksheet is the ONLY record that a row was looked at and found
    right. Destroying it destroys the only evidence the review happened.

    ⚠ Goes through a REAL FILE, because the first fix took the decisions as an
    argument and the call site could still pass `{}` — the defect reproduced
    past every guard. `csv_rows` reads the sheet itself now, so this exercises
    the whole path."""
    m = _load()
    sheet = _sheet_with(tmp_path, m, CT1_858_1=("KEEP", "looked, it is fine"))
    rows = m.csv_rows(_one_group(m), sheet)
    keep = [r for r in rows if r["contract_id"] == "CT1-858-1"]
    assert keep and keep[0]["verdict"] == "KEEP" and keep[0]["note"] == "looked, it is fine"
    other = [r for r in rows if r["contract_id"] == "CT1-858-2"]
    assert other and other[0]["verdict"] == "" and other[0]["note"] == "", \
        "a contract with no recorded decision must stay blank, not inherit one"


def test_the_carry_forward_rule_has_one_owner():
    """⚠ The segment worksheets already own 'a re-run never discards a
    decision'. A second copy here is how two sheets come to disagree about what
    has been decided — so this asserts the SAME function object, not merely that
    something with the same name exists."""
    m = _load()
    import build_contract_review_worksheet as seg
    assert m._read_existing is seg.read_existing


def test_a_sheet_that_does_not_exist_yet_is_not_an_error(tmp_path):
    """The first run has nothing to carry forward, and must still produce rows."""
    m = _load()
    rows = m.csv_rows(_one_group(m), str(tmp_path / "not-created-yet.csv"))
    assert rows and all(r["verdict"] == "" for r in rows)


def test_the_sheet_carries_the_columns_a_reviewer_writes_in(tmp_path):
    m = _load()
    assert m.CSV_FIELDS[-2:] == ["verdict", "note"]
    rows = m.csv_rows(_one_group(m), str(tmp_path / "none.csv"))
    assert set(rows[0]) == set(m.CSV_FIELDS), \
        "a field written but not declared (or vice versa) silently drops a column"


def test_writing_the_sheet_twice_keeps_the_decision_end_to_end(tmp_path):
    """⚠⚠ THE END-TO-END PROPERTY, and the only form with no hole in it. Two
    earlier shapes of this fix each passed their own guards while a mutation
    walked through the CALL SITE — decisions injected as an argument, then the
    path injected as an argument. `write_sheet` reads and writes ONE path, so
    there is nothing left for a caller to supply wrongly. Round-trips through a
    real file rather than asserting on a return value."""
    m = _load()
    import csv as _csv
    sheet = str(tmp_path / "sub" / "contradictions.csv")

    def _read():
        with open(sheet, encoding="utf-8") as fh:
            body = [ln for ln in fh if not ln.lstrip().startswith("#")]
        return {r["contract_id"]: r for r in _csv.DictReader(body)}

    m.write_sheet(_one_group(m), sheet)                       # first run: blank
    rows = _read()
    assert rows["CT1-858-1"]["verdict"] == ""

    rows["CT1-858-1"].update(verdict="KEEP", note="a human looked")
    with open(sheet, "w", newline="", encoding="utf-8") as fh:
        fh.write("# a header comment the reader must skip\n")
        w = _csv.DictWriter(fh, fieldnames=m.CSV_FIELDS, quoting=_csv.QUOTE_ALL)
        w.writeheader()
        for r in rows.values():
            w.writerow(r)
    assert _read()["CT1-858-1"]["verdict"] == "KEEP", \
        "the verdict must actually be IN the file, or the re-run below proves nothing"

    m.write_sheet(_one_group(m), sheet)                       # re-run
    back = _read()
    assert back["CT1-858-1"]["verdict"] == "KEEP"
    assert back["CT1-858-1"]["note"] == "a human looked"
    assert back["CT1-858-2"]["verdict"] == "", "an undecided row must not inherit one"
