"""Toxicity metrics: injected markout is recovered, ES = RS + PI, de-trending, netting, clustered SE."""

import numpy as np
import pandas as pd
import pytest

from wtox import warrant_price
from wtox.research import config, toxicity

DAY = pd.Timestamp("2025-03-03")


def _trades(n=4, side=(1, -1, 1, -1), dS=10.0):
    S, K, ratio, iv, T = 1000.0, 1050.0, 0.01, 0.4, 60 / 365
    pre = float(warrant_price(S, K, config.RISK_FREE, 0.0, iv, T, ratio, "call"))
    d = pd.DataFrame({
        "datetime": DAY + pd.to_timedelta([10 * 60 + i for i in range(n)], unit="s") + config.SESSION_OPEN,
        "warrant_id": "A", "issuer": "x", "kind": "call", "strike": K, "ratio": ratio, "T": T, "iv": iv,
        "S_mid": S, "pre_mid": pre, "side": list(side)[:n], "order_tick_type": [1 if s > 0 else 2 for s in side][:n],
        "volume": 10, "order_volume": 10, "S_spread_bps": 5.0, "S_chg_1s": 0.0, "S_chg_5s": 0.0,
    })
    d["close"] = d["pre_mid"] + d["side"] * 0.005                           # pay half a 0.01 spread
    from wtox import bs_greeks
    d["delta"] = bs_greeks(S, K, config.RISK_FREE, 0.0, iv, T, "call")["delta"]
    d["leverage"] = d["delta"].abs() * ratio * S / pre
    d["share_equiv"] = d["side"] * d["volume"] * 1000 * ratio * d["delta"]
    d["notional"] = d["close"] * d["volume"] * 1000
    for name in config.HORIZONS:
        d[f"S_mid_{name}"] = S + dS
        if config.HORIZONS[name] is not None:
            d[f"trunc_{name}"] = False
    return d


def test_injected_markout_is_recovered_and_es_decomposes():
    d = toxicity.trade_metrics(_trades())
    exp = d["side"] * d["delta"] * d["ratio"] * 10.0 / d["pre_mid"]
    assert np.allclose(d["M_5m"], exp)
    for h in config.HORIZONS:
        assert np.allclose(d["ES"], d[f"RS_{h}"] + d[f"PI_{h}"])
    assert np.allclose(d["ES"], 0.005 / d["pre_mid"])                       # half spread, both sides
    # with no time decay PI tracks M to first order; buyers (side +1) gain when S rises
    assert (d.loc[d["side"] > 0, "PI_1s"] > 0).all() and (d.loc[d["side"] < 0, "PI_1s"] < 0).all()


def test_detrend_removes_a_known_drift():
    d = toxicity.trade_metrics(_trades())
    drift = pd.Series({"5m": 10.0 / 1000, "30m": 10.0 / 1000, "close_per_s": 0.0})
    d = toxicity.detrend(d, drift, horizons=("5m", "30m"))
    assert np.allclose(d["M_dt_5m"], 0) and np.allclose(d["RS_dt_5m"] + d["PI_5m"] - d["ES"], d["RS_dt_5m"] - d["RS_5m"])


def test_day_drift_from_grid():
    tau = pd.date_range(DAY + config.SESSION_OPEN, periods=4, freq="1min")
    g = pd.DataFrame({"tau": tau, "S_mid_tau": [100.0, 101, 102, 103], "S_mid_5m": [101.0, 102, 103, 104],
                      "trunc_5m": [False, False, False, True], "S_mid_close": 110.0})
    dr = toxicity.day_drift(g, {"5m": pd.Timedelta(minutes=5), "close": None})
    assert dr["5m"] == pytest.approx(np.mean([1 / 100, 1 / 101, 1 / 102]))
    span = (config.CONTINUOUS_END - config.SESSION_OPEN).total_seconds()
    assert dr["close_per_s"] == pytest.approx(0.10 / span)


def test_hedge_cost_netting():
    d = toxicity.hedge_costs(toxicity.trade_metrics(_trades()))
    c = config.HEDGE_SCENARIOS
    assert np.allclose(d["cost_pessimistic"], (c["pessimistic"]["tax"] + c["pessimistic"]["fee"] + 2.5e-4) * d["leverage"])
    assert np.allclose(d["cost_neutral"], 0)                               # two buys, two sells of one warrant net out
    one = toxicity.hedge_costs(toxicity.trade_metrics(_trades(side=(1, 1, 1, -1))))
    assert np.allclose(one["cost_optimistic"], (c["optimistic"]["tax"] + 2.5e-4) * one["leverage"] * 0.5)


def test_cluster_mean_matches_day_level_reasoning():
    x = np.array([1.0, 3.0, 2.0, 2.0, 5.0, 7.0])
    w = np.ones(6)
    day = np.array([1, 1, 2, 2, 3, 3])
    m, se, n, G = toxicity.cluster_mean(x, w, day)
    assert m == pytest.approx(10 / 3) and n == 6 and G == 3
    resid_sums = np.array([4 - 2 * m, 4 - 2 * m, 12 - 2 * m])
    assert se == pytest.approx(np.sqrt((resid_sums ** 2).sum() * 3 / 2) / 6)


def test_placebo_shuffled_sides_give_zero_markout():
    rng = np.random.default_rng(0)
    side = rng.choice([1, -1], 2000)
    d = toxicity.trade_metrics(_trades(n=2000, side=side))
    d["side"] = rng.permutation(np.r_[np.ones(1000), -np.ones(1000)])  # balanced shuffle
    d = toxicity.trade_metrics(d)
    assert abs(d["M_5m"].mean()) < 1e-12


def test_bh_fdr():
    p = np.array([0.01, 0.04, 0.03, np.nan, 0.5])
    adj = toxicity.bh_fdr(p)
    # m = 4: ranked 0.01, 0.03, 0.04, 0.5 -> 0.04, 0.06, 0.0533, 0.5 -> step-up minimum
    assert adj[0] == pytest.approx(0.04) and adj[1] == pytest.approx(0.04 * 4 / 3) and adj[2] == pytest.approx(0.04 * 4 / 3)
    assert np.isnan(adj[3]) and adj[4] == pytest.approx(0.5)


def test_cuts_spot_move_direction():
    d = toxicity.trade_metrics(_trades())
    d["S_chg_1s"] = [5.0, 5.0, -5.0, 0.0]                                 # call: up favours buyers
    d = toxicity.add_cuts(d)
    assert d["spot_1s"].astype(str).tolist() == ["favourable", "adverse", "adverse", "none"]
    assert d["quadrant"].tolist() == ["buy_call", "sell_call", "buy_call", "sell_call"]
