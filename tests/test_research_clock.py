"""Clock checks: timestamp resolution and recovering a known lead-lag."""

import numpy as np
import pandas as pd
import pytest

from wtox.research import clock

DAY = pd.Timestamp("2026-09-01")


def test_resolution_tells_seconds_from_milliseconds():
    sec = pd.Series(DAY + pd.to_timedelta([9 * 3600, 9 * 3600 + 1, 9 * 3600 + 1], unit="s"))
    r = clock.resolution(sec)
    assert r["share_whole_second"] == 1 and r["share_repeated"] == pytest.approx(0.5)
    ms = pd.Series(DAY + pd.to_timedelta([0, 1, 2.25], unit="ms"))
    r = clock.resolution(ms)
    assert r["share_whole_ms"] == pytest.approx(2 / 3) and r["share_sub_ms"] == pytest.approx(1 / 3)
    assert r["min_positive_gap_us"] == pytest.approx(1000)


def _feeds(delay_ms, n=400, seed=0):
    rng = np.random.default_rng(seed)
    t = np.sort(rng.choice(np.arange(10, 15000), n, replace=False)) * 1000      # ms after 09:00, >= 1 s apart
    steps = rng.choice([-1, 1], n)
    mid = 1000 + np.cumsum(steps)
    stock = pd.DataFrame({"datetime": DAY + pd.Timedelta(hours=9) + pd.to_timedelta(t, unit="ms"),
                          "bid_price": mid - 0.5, "ask_price": mid + 0.5, "close": mid})
    wt = DAY + pd.Timedelta(hours=9) + pd.to_timedelta(t + delay_ms, unit="ms")
    call = pd.DataFrame({"warrant_id": "C", "datetime": wt, "bid_price": 1 + mid / 100, "ask_price": 1.01 + mid / 100})
    put = pd.DataFrame({"warrant_id": "P", "datetime": wt, "bid_price": 30 - mid / 100, "ask_price": 30.01 - mid / 100})
    junk = pd.DataFrame({"warrant_id": "X", "datetime": wt, "bid_price": 0.0, "ask_price": 1.0})   # invalid quotes
    return stock, pd.concat([call, put, junk], ignore_index=True), pd.Series({"C": "call", "P": "put", "X": "call"})


@pytest.mark.parametrize("delay_ms", [300, -500, 0])
def test_lead_lag_recovers_the_offset(delay_ms):
    stock, warrants, kinds = _feeds(delay_ms)
    ll = clock.lead_lag(stock, warrants, kinds, grid=pd.Timedelta(milliseconds=100), max_lag=20)
    assert clock.peak(ll) == pytest.approx(delay_ms / 1000)
    assert ll["corr"].max() > 0.9                      # put moves are sign-flipped, not cancelling
    assert ll["n_warrant_moves"].iloc[0] == 2 * (len(stock) - 1) - (stock["close"].diff() == 0).sum() * 2
