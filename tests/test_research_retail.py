"""Who wins / who loses: trader and market-maker formulas, backward-only conditions, quadrants."""

import numpy as np
import pandas as pd
import pytest

from wtox.research import config, retail


def test_realised_vol_uses_only_previous_days():
    c = pd.Series(100 * np.exp(np.cumsum(np.r_[0, np.full(30, 0.01)])), index=[f"d{i:02d}" for i in range(31)])
    c.iloc[25] = c.iloc[24] * 1.5                      # a jump on day 25
    rv = retail.realised_vol(c)
    assert np.isnan(rv.iloc[20]) and rv.iloc[21] == pytest.approx(0.0, abs=1e-12)
    assert rv.iloc[25] == pytest.approx(0.0, abs=1e-12)  # the jump is not visible on its own day
    assert rv.iloc[26] > 0.5


def test_tx_return_uses_completed_bars_only():
    t0 = pd.Timestamp("2025-03-03 09:00")
    bars = pd.DataFrame({"ts": t0 + pd.to_timedelta(np.arange(-15, 10), unit="min"), "contract": "202503",
                         "close_none": 20000.0})
    bars.loc[bars["ts"] == t0, "close_none"] = 21000.0                     # bar stamped 09:00
    t = pd.Series([t0 + pd.Timedelta("30s"), t0 + pd.Timedelta("1min")])
    r = retail.tx_past_return(t, bars)
    assert r.iloc[0] == pytest.approx(0.0)            # 09:00 bar not usable before 09:01
    assert r.iloc[1] == pytest.approx(500.0)          # usable from 09:01
    bars2 = bars.assign(contract=np.where(bars["ts"] < t0 - pd.Timedelta("2min"), "202502", "202503"))
    assert np.isnan(retail.tx_past_return(t, bars2).iloc[1])   # roll inside the window


def test_direction_labels():
    s = pd.Series([5.0, -5.0, 0.5, np.nan])
    lab = retail._direction(s, pd.Series([1.0, 1.0, 1.0, 1.0]), pd.Series([-1.0, -1.0, 1.0, 1.0]))
    assert lab.tolist() == ["against", "with", "flat", "na"]   # puts flip the sign


def test_trader_and_market_maker_formulas():
    d = pd.DataFrame({"RS_dt_5m": [0.012], "RS_5m": [0.010], "RS_dt_close": [0.02], "RS_close": [0.02],
                      "trunc_5m": [False], "pre_spread_pct": [0.02],
                      **{f"cost_{k}": [0.005] for k in config.HEDGE_SCENARIOS}})
    m = retail.metrics(d)
    assert m["trader_5m"].iloc[0] == pytest.approx(-0.012 - 0.01 - retail.COST_RT)
    assert m["trader_raw_5m"].iloc[0] == pytest.approx(-0.010 - 0.01 - retail.COST_RT)
    assert m["mm_neutral_5m"].iloc[0] == pytest.approx(0.007)
    assert m["timing_5m"].iloc[0] == pytest.approx(-0.012)
    assert m["leakage"].iloc[0] == pytest.approx(0.005 + retail.COST_RT)
    t = retail.metrics(d.assign(trunc_5m=True))
    assert np.isnan(t["trader_5m"].iloc[0]) and not np.isnan(t["trader_close"].iloc[0])


def test_quadrants_and_inclusion():
    rows = []
    for g, mm, tr, n in [("a", 50.0, -100.0, 1000), ("b", -30.0, 40.0, 1000), ("c", -30.0, 40.0, 10)]:
        for v, x in [("mm_neutral_5m", mm), ("trader_5m", tr), ("trader_close", tr), ("leakage", 20.0)]:
            rows.append({"sample": "buys", "group_set": "cell", "group": g, "value": v, "mean_bps": x, "se_bps": 1.0,
                         "p": 1e-6, "n": n, "n_days": 100})
    m, inc = retail.finalise(pd.DataFrame(rows))
    assert ("buys", "cell", "c") not in inc                     # too few trades
    q = retail.quadrants(m).set_index("group")
    assert q.loc["a", "quadrant"] == "造市商賺／交易者虧" and q.loc["b", "quadrant"] == "造市商虧／交易者賺"
    assert "c" not in q.index
    m2, _ = retail.finalise(pd.DataFrame(rows).assign(p=0.5), inc)
    assert (retail.quadrants(m2)["quadrant"] == "造市商不確定／交易者不確定").all()


def test_tx_return_stale_or_previous_day_is_missing():
    t0 = pd.Timestamp("2025-03-03 10:00")
    bars = pd.DataFrame({"ts": [t0 - pd.Timedelta("20min"), t0 - pd.Timedelta("19min")], "contract": "x", "close_none": 1.0})
    assert np.isnan(retail.tx_past_return(pd.Series([t0]), bars).iloc[0])          # last bar 18 min old
    prev = pd.DataFrame({"ts": pd.Timestamp("2025-02-27 13:44") + pd.to_timedelta([0], unit="min"), "contract": "x",
                         "close_none": 1.0})
    early = pd.DataFrame({"ts": [pd.Timestamp("2025-03-03 08:45")], "contract": "x", "close_none": 1.0})
    t = pd.Series([pd.Timestamp("2025-03-03 08:47")])
    assert np.isnan(retail.tx_past_return(t, pd.concat([prev, early])).iloc[0])     # 5 min back is the previous day


def test_missing_labels_left_out_of_bh_and_quadrants():
    rows = []
    for g in ("with|1–30", "na|1–30"):
        for v in ("mm_neutral_5m", "trader_5m", "trader_close", "leakage"):
            rows.append({"sample": "buys", "group_set": "chase×dte", "group": g, "value": v, "mean_bps": 10.0,
                         "se_bps": 1.0, "p": 1e-6, "n": 1000, "n_days": 100})
    m, _ = retail.finalise(pd.DataFrame(rows))
    assert m.loc[m["group"] == "na|1–30", "p_bh"].isna().all() and m.loc[m["group"] == "na|1–30", "missing_label"].all()
    assert retail.quadrants(m)["group"].tolist() == ["with|1–30"]
