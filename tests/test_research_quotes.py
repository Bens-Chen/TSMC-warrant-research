"""At-trade quotes: missing reasons, other-side agreement, reaction test, sweep invariants.

The panel is built from raw ticks through trades.build_day, so the real order grouping is exercised."""

import numpy as np
import pandas as pd
import pytest

from wtox.research import quotes
from wtox.research.trades import build_day

DAY = "2026-09-01"
# (warrant, time, price, volume, post bid, post ask, tick_type)
TICKS = [
    ("A", "09:01:00.000", 1.01, 1, 1.00, 1.01, 1),   # first of day, post bid valid -> ok (post)
    ("A", "09:01:00.500", 1.01, 2, 1.00, 1.01, 1),   # prev in force, post == prev; reaction-test candidate
    ("A", "09:03:00.000", 1.01, 3, 0.00, 0.00, 1),   # buy sweep 1.01 -> 1.02
    ("A", "09:03:00.000", 1.02, 4, 1.00, 1.03, 1),
    ("B", "09:04:00.000", 0.50, 10, 0.49, 0.00, 2),  # first of day, post ask invalid -> first_of_day
    ("A", "09:05:00.000", 1.00, 5, 0.99, 1.03, 2),   # sell, prev bid 1.00 == P1 in force, post ask 1.03 -> ok
    ("A", "09:06:00.000", 1.01, 1, 0.99, 1.01, 0),   # unflagged -> no_side
    ("A", "09:07:00.000", 1.03, 1, 0.00, 1.04, 1),   # prev ask 1.01 != 1.03, post bid 0 -> prev_stale
    ("A", "09:08:00.000", 1.04, 1, 0.00, 1.05, 1),   # prev ask 1.04 in force but prev bid 0 -> other_side_invalid
    ("A", "09:09:00.000", 1.03, 2, 0.00, 0.00, 2),   # sell sweep 1.03 -> 1.02, post ask 1.06 -> ok
    ("A", "09:09:00.000", 1.02, 2, 1.01, 1.06, 2),
    ("A", "09:10:00.000", 1.06, 1, 0.00, 0.00, 1),   # same timestamp, conflicting flags -> mixed, no_side
    ("A", "09:10:00.000", 1.01, 1, 1.00, 1.06, 2),
]


def _panel(tmp_path, ticks=TICKS):
    t = pd.DataFrame(ticks, columns=["warrant_id", "time", "close", "volume", "bid_price", "ask_price", "tick_type"])
    t["datetime"] = pd.to_datetime(DAY + " " + t["time"])
    t["bid_volume"], t["ask_volume"] = 50, 50
    d = tmp_path / "shioaji" / "ticks" / DAY
    d.mkdir(parents=True, exist_ok=True)
    for w, g in t.drop(columns="time").groupby("warrant_id"):
        g.to_parquet(d / f"{w}.parquet", index=False)
    s = tmp_path / "shioaji" / "underlying_ticks" / "stock" / "2330"
    s.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"datetime": pd.to_datetime([f"{DAY} 09:00:01"]), "close": [2000.0], "bid_price": [1995.0],
                  "ask_price": [2005.0]}).to_parquet(s / f"{DAY}.parquet")
    terms = pd.DataFrame({"warrant_id": ["A", "B"], "event_date": [pd.NaT] * 2, "event_seq": [0, 0], "kind": ["call"] * 2,
                          "strike": [2100.0] * 2, "ratio": [0.01] * 2,
                          "expiry_date": [pd.Timestamp(DAY) + pd.Timedelta(days=100)] * 2, "issuer": ["x"] * 2,
                          "tej_id": ["A", "B"], "listing_date": [pd.Timestamp(DAY) - pd.Timedelta(days=30)] * 2,
                          "terms_source": ["twse"] * 2, "expiry_conflict": [False] * 2})
    return build_day(DAY, tmp_path, terms)


def _at(p, time, w="A"):
    return p[(p["datetime"] == pd.Timestamp(f"{DAY} {time}")) & (p["warrant_id"] == w)]


def test_reasons(tmp_path):
    c = quotes.classify(_panel(tmp_path))
    r = lambda t, w="A": _at(c, t, w)["missing_reason"].astype(str).unique().tolist()
    assert r("09:01:00") == ["ok"] and r("09:01:00.5") == ["ok"] and r("09:03:00") == ["ok"]
    assert r("09:04:00", "B") == ["first_of_day"] and r("09:05:00") == ["ok"] and r("09:09:00") == ["ok"]
    assert r("09:06:00") == ["no_side"] and r("09:10:00") == ["no_side"]
    assert r("09:07:00") == ["prev_stale"] and r("09:08:00") == ["other_side_invalid"]
    assert _at(c, "09:10:00")["mixed_tick_type"].all()
    s = quotes.summary(c).set_index("missing_reason")
    assert s.loc["ok", "share_n"] == pytest.approx(7 / 13)


def test_sweeps_use_the_first_fill_and_the_last_fills_book(tmp_path):
    p = _panel(tmp_path)
    buy = _at(p, "09:03:00")
    assert buy["pre_ask"].tolist() == [1.01, 1.01] and buy["pre_bid"].tolist() == [1.00, 1.00]
    sell = _at(p, "09:09:00")
    assert sell["pre_bid"].tolist() == [1.03, 1.03] and sell["pre_ask"].tolist() == [1.06, 1.06]
    assert (sell["side"] == -1).all()
    assert _at(p, "09:05:00")["prev_in_force"].all()                 # sell met the standing bid 1.00
    assert not _at(p, "09:07:00")["prev_in_force"].any()


def test_other_side_agreement(tmp_path):
    a = quotes.other_side_agreement(_panel(tmp_path))
    assert a["n"] == 3 and a["share_equal"] == 1                     # 09:01:00.5, buy sweep, 09:05 sell


def test_reaction_test_flags_direction(tmp_path):
    r = quotes.reaction_test(_panel(tmp_path))
    assert len(r) == 1 and not r["moved"].iloc[0]
    ticks = list(TICKS)
    ticks[1] = ("A", "09:01:00.500", 1.01, 2, 1.005, 1.01, 1)        # bid steps up right after a buy
    r = quotes.reaction_summary(quotes.reaction_test(_panel(tmp_path, ticks))).set_index("side")
    assert r.loc["buy", "moved"] == 1 and r.loc["buy", "toward"] == 1 and r.loc["buy", "against"] == 0


def test_sweep_check_invariants(tmp_path):
    p = _panel(tmp_path)
    c = quotes.sweep_check(p)
    assert c["n_below_quoted"] == 0 and c["n_worse_not_above"] == 0 and c["n_quoted_nonpositive"] == 0
    assert c["n_worse_price"] == 2                                   # second level of each sweep
    bad = p.copy()
    rows = bad["datetime"] == pd.Timestamp(f"{DAY} 09:03:00")
    bad.loc[rows, "pre_mid"] = 1.015                                 # the old bug: post-sweep ask 1.03 used
    assert quotes.sweep_check(bad)["n_quoted_nonpositive"] == 2      # mid above the 1.01 ask the order met
