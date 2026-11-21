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


# --- phase 2 ---------------------------------------------------------------------------------

def test_close_quotes_last_valid_before_1325():
    from wtox.research import markout
    day = "2025-03-03"
    w = pd.DataFrame({"warrant_id": "A", "datetime": pd.to_datetime([f"{day} 10:00", f"{day} 13:00", f"{day} 13:26"]),
                      "bid_price": [1.0, 0.0, 2.0], "ask_price": [1.1, 1.2, 2.1]})
    q = markout.build_close_quotes(w).set_index("warrant_id")
    assert q.loc["A", "bid"] == 1.0 and q.loc["A", "ask"] == 1.2      # 13:00 bid 0 skipped; 13:26 is after 13:25


def test_exit_labels_days_expiry_and_end():
    from wtox.research import markout
    days = ["2025-03-03", "2025-03-04", "2025-03-05", "2025-03-06", "2025-03-07", "2025-03-10"]
    closes = pd.Series([100.0, 101, 102, 103, 104, 105], index=days)
    q = {d: pd.DataFrame({"warrant_id": ["A", "B"], "bid": [1.0 + i, 0.5], "ask": [1.1 + i, 0.6],
                         "bid_time": pd.Timestamp(d) + pd.Timedelta("13h")}) for i, d in enumerate(days)}
    panel = pd.DataFrame({"trade_id": [0, 1], "datetime": pd.Timestamp("2025-03-03 10:00"), "warrant_id": ["A", "B"],
                          "T": [100 / 365, 2 / 365]})
    e = markout.build_exit_labels(panel, "2025-03-03", days, q.get, closes)
    assert e.loc[0, "exit_day_1"] == "2025-03-04" and e.loc[0, "bid_1"] == 2.0 and e.loc[0, "exit_day_5"] == "2025-03-10"
    assert not e.loc[0, "expired_5"] and e.loc[1, "expired_3"] and not e.loc[1, "expired_1"]
    assert e.loc[1, "S_settle_3"] == 102.0                              # expiry 03-05: close of 03-05
    late = markout.build_exit_labels(panel, "2025-03-07", days, q.get, closes)
    assert late.loc[0, "exit_day_1"] == "2025-03-10" and np.isnan(late.loc[0, "bid_3"])   # beyond the sample


def test_newey_west_widens_with_autocorrelation():
    rng = np.random.default_rng(0)
    days = np.repeat(np.arange(400), 5)
    shock = np.repeat(np.convolve(rng.normal(size=404), np.ones(5), "valid")[:400], 5)   # overlapping 5-day sums
    x = shock + rng.normal(0, 0.1, len(days))
    m0, se0, _, _ = retail.nw_mean(x, np.ones(len(x)), days, 0)
    m5, se5, _, _ = retail.nw_mean(x, np.ones(len(x)), days, 5)
    assert m0 == pytest.approx(m5) and se5 > 1.8 * se0


def test_multiday_metrics_settlement_and_decomposition():
    d = pd.DataFrame({"side": [1.0, 1.0, 1.0, -1.0], "kind": ["call", "put", "call", "call"], "strike": 100.0, "ratio": 0.1,
                      "delta": [0.5, -0.4, 0.5, 0.5], "S_mid": 100.0, "close": [1.0, 1.0, 1.0, 1.0], "pre_mid": 0.98})
    for k in config.RETAIL_HOLD_DAYS:
        d[f"bid_{k}"] = [1.2, 0.0, np.nan, 1.0]
        d[f"S_close_{k}"] = 104.0
        d[f"expired_{k}"] = [False, True, False, False]
        d[f"S_settle_{k}"] = [np.nan, 90.0, np.nan, np.nan]
        d[f"exit_day_{k}"] = "2025-03-10"
        d[f"expiry_{k}"] = pd.Timestamp("2025-06-30")
    m = retail.multiday_metrics(d, mu=0.001)
    assert len(m) == 3                                                   # sells dropped
    assert m["hold_raw_1"].iloc[0] == pytest.approx((1.2 - 1.0) / 0.98 - retail.COST_RT)
    assert m["hold_raw_1"].iloc[1] == pytest.approx((1.0 - 1.0) / 0.98 - retail.COST_RT)   # put settles (100-90)*0.1 = 1.0
    assert np.isnan(m["hold_raw_1"].iloc[2])                             # no exit bid: unobserved
    r = m.iloc[0]
    assert r["hold_dir_1"] + r["hold_resid_1"] == pytest.approx(r["hold_raw_1"])
    assert r["hold_dt_5"] == pytest.approx(r["hold_raw_5"] - 0.5 * 0.1 / 0.98 * 100 * 0.001 * 5)


def test_newey_west_counts_missing_days_as_zero_scores():
    days = np.array([0, 0, 2, 2, 4, 4])
    x = np.array([1.0, 1.0, 1.0, 1.0, -2.0, -2.0])
    _, se_obs, _, G = retail.nw_mean(x, np.ones(6), days, 1)
    _, se_all, _, _ = retail.nw_mean(x, np.ones(6), days, 1, all_days=np.arange(5))
    assert G == 3 and se_all != se_obs             # lag 1 now pairs day 0 with day 1 (a zero), not with day 2


def test_multiday_finalise_reuses_training_inclusion():
    def frame(n):
        return pd.DataFrame({"hold": 5, "group_set": "cell", "group": ["a", "b"], "value": "hold_dt_5",
                             "mean_bps": 1.0, "p": 0.01, "n": n, "n_days": 100})
    phase1 = {("buys", "cell", "a"), ("buys", "cell", "b")}
    m25, inc = retail.multiday_finalise(frame([1000, 10]), phase1)
    assert m25.set_index("group")["include"].tolist() == [True, False]
    m26, _ = retail.multiday_finalise(frame([10, 1000]), phase1, inc)
    assert m26.set_index("group")["include"].tolist() == [True, False]      # 2025 decides, not 2026 counts


def test_exit_bid_age():
    from wtox.research import markout
    days = ["2025-03-03", "2025-03-04"]
    q = {d: pd.DataFrame({"warrant_id": ["A"], "bid": [1.0], "ask": [1.1], "bid_time": [pd.Timestamp(d) + pd.Timedelta("13h")]})
         for d in days}
    panel = pd.DataFrame({"trade_id": [0], "datetime": pd.Timestamp("2025-03-03 10:00"), "warrant_id": ["A"], "T": [1.0]})
    e = markout.build_exit_labels(panel, "2025-03-03", days, q.get, pd.Series([1.0, 1.0], index=days))
    assert e.loc[0, "bid_age_s_1"] == 25 * 60                     # 13:00 quote at the 13:25 close
