"""Combined TWSE + TEJ point-in-time terms."""

import pandas as pd

from wtox.research.terms import combine, dividend_dates, terms_on

D = pd.Timestamp


def _twse():
    # 032388 is listed today; TWSE has its 2026 dividend adjustment
    return pd.DataFrame({
        "warrant_id": ["032388", "032388"], "kind": "call", "issuer": "元大",
        "expiry_date": D("2026-11-17"), "event_date": [pd.NaT, D("2026-06-11")], "event_seq": [0, 1],
        "event": ["發行", "除權息調整"], "strike": [1800.0, 1776.32], "ratio": [0.02, 0.02],
        "snapshot_date": D("2026-11-12"),
    })


def _tej():
    rows = [
        # same warrant as TWSE, but TEJ is stale and its `strike` column is the latest value
        ("032388", D("2025-08-14"), 1, 1800.0, 0.02, D("2025-08-18"), D("2026-11-17"), 1786.87),
        # delisted, reused code 086717 -> TEJ id 086717U; strike reset on 2025-06-12
        ("086717U", D("2025-01-10"), 1, 1000.0, 0.05, D("2025-01-14"), D("2025-09-30"), 990.0),
        ("086717U", D("2025-06-12"), 1, 990.0, 0.051, D("2025-01-14"), D("2025-09-30"), 990.0),
        # a later warrant re-using exchange code 086717
        ("086717", D("2026-01-05"), 1, 1500.0, 0.03, D("2026-01-07"), D("2026-08-30"), 1500.0),
    ]
    t = pd.DataFrame(rows, columns=["warrant_id", "event_date", "event_seq", "strike_event", "ratio_event",
                                    "listing_date", "expiry_date", "strike"])
    return t.assign(underlying_id="2330", kind="call", issuer="凱基", ratio=t["ratio_event"],
                    last_trade_date=t["expiry_date"] - pd.Timedelta(days=2))


def test_twse_wins_when_it_knows_the_warrant():
    t = combine(_twse(), _tej())
    w = terms_on(t, "2026-09-01").set_index("warrant_id")
    assert w.loc["032388", "strike"] == 1776.32 and w.loc["032388", "terms_source"] == "twse"
    assert w.loc["032388", "tej_id"] == "032388"


def test_delisted_warrant_uses_point_in_time_tej_event_not_latest_strike():
    t = combine(_twse(), _tej())
    before = terms_on(t, "2025-03-03").set_index("warrant_id").loc["086717"]
    after = terms_on(t, "2025-07-01").set_index("warrant_id").loc["086717"]
    assert (before["strike"], before["tej_id"]) == (1000.0, "086717U")
    assert (after["strike"], after["ratio"]) == (990.0, 0.051)


def test_reused_code_maps_to_the_warrant_alive_that_day():
    t = combine(_twse(), _tej())
    assert terms_on(t, "2026-03-02").set_index("warrant_id").loc["086717", "tej_id"] == "086717"
    assert "086717" not in set(terms_on(t, "2025-12-01")["warrant_id"])   # gap between the two
    assert "086717" not in set(terms_on(t, "2025-01-13")["warrant_id"])   # before listing


def test_stale_tej_terms_are_flagged_after_a_missed_dividend_date():
    tej = _tej()
    t = combine(_twse().iloc[:0], tej)   # pretend TWSE no longer lists 032388
    w = terms_on(t, "2026-09-01", div_dates=[D("2026-06-11")]).set_index("warrant_id")
    assert bool(w.loc["032388", "terms_stale"])
    assert not terms_on(t, "2026-06-01", div_dates=[D("2026-06-11")]).set_index("warrant_id").loc["032388", "terms_stale"]


def test_dividend_dates_take_the_quarterly_mode():
    tw = pd.DataFrame({"event": ["除權息調整"] * 12 + ["履約價重設"],
                       "event_date": [D("2026-06-11")] * 11 + [D("2026-06-12"), D("2026-05-02")]})
    assert dividend_dates(tw) == [D("2026-06-11")]


def test_twse_warrant_with_no_tej_record_never_displaces_a_dated_warrant():
    # TWSE lists a new 036619 with no TEJ record (no listing date); TEJ has the old 036619V
    tw = pd.DataFrame({"warrant_id": ["036619"], "kind": "call", "issuer": "元大", "expiry_date": D("2027-06-01"),
                       "event_date": [pd.NaT], "event_seq": [0], "event": ["發行"], "strike": [2750.0], "ratio": [0.01],
                       "snapshot_date": D("2026-11-12")})
    tj = _tej().iloc[:1].assign(warrant_id="036619V", strike_event=545.0, listing_date=D("2023-01-05"),
                               expiry_date=D("2023-12-29"), event_date=D("2023-01-03"))
    w = terms_on(combine(tw, tj), "2023-06-20").set_index("warrant_id")
    assert w.loc["036619", "strike"] == 545.0 and w.loc["036619", "tej_id"] == "036619V"


def test_expiry_disagreement_is_matched_on_code_and_issue_strike():
    tw = _twse().assign(expiry_date=D("2027-01-21"))                 # TEJ says 2026-11-17
    w = terms_on(combine(tw, _tej()), "2026-09-01").set_index("warrant_id")
    assert w.loc["032388", "tej_id"] == "032388" and bool(w.loc["032388", "expiry_conflict"])
    assert w.loc["032388", "terms_source"] == "twse" and w.loc["032388", "expiry_date"] == D("2027-01-21")


def test_stale_flag_survives_a_later_genuine_reset():
    tej = pd.concat([_tej(), _tej().iloc[[0]].assign(event_date=D("2026-08-01"), event_seq=1, strike_event=1700.0)])
    t = combine(_twse().iloc[:0], tej)
    w = terms_on(t, "2026-09-01", div_dates=[D("2026-06-11")]).set_index("warrant_id")
    assert w.loc["032388", "strike"] == 1700.0 and bool(w.loc["032388", "terms_stale"])


def test_fallback_never_matches_an_old_warrant_that_reused_the_code():
    # new TWSE 086717 (issue strike 1000, not yet in TEJ); the delisted 086717U also issued at 1000
    tw = _twse().iloc[:1].assign(warrant_id="086717", strike=1000.0, expiry_date=D("2027-05-01"))
    t = combine(tw, _tej())
    old = terms_on(t, "2025-03-03").set_index("warrant_id").loc["086717"]
    assert old["tej_id"] == "086717U" and old["terms_source"] == "tej"      # old warrant keeps its own terms
    new = t[(t["terms_source"] == "twse") & (t["warrant_id"] == "086717")]
    assert new["tej_id"].isna().all() and not new["expiry_conflict"].any()


def test_split_tej_ids_get_one_id_and_twse_rows_are_not_duplicated():
    tej = pd.concat([_tej(), _tej().iloc[[0]].assign(warrant_id="032388T", event_date=D("2025-09-01"),
                                                     listing_date=D("2025-08-18"))])
    t = combine(_twse(), tej)
    assert (t["warrant_id"] == "032388").sum() == len(_twse())
    tj_only = combine(_twse().iloc[:0], tej)
    assert tj_only.loc[tj_only["warrant_id"] == "032388", "tej_id"].nunique() == 1
