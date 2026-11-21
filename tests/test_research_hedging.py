"""Extension E: exact decomposition, delta-hedged P&L under GBM, latency, band hedging and allocation."""

import numpy as np
import pandas as pd
import pytest

from wtox import bs_greeks, warrant_price
from wtox.research import config, hedging

R, Q = config.RISK_FREE, config.DIVIDEND_YIELD
T0 = pd.Timestamp("2025-03-03 09:00")


def _pos(n, iv=0.4, T=0.25, K=100.0, N=-1000.0):
    return pd.DataFrame({"N": N, "strike": K, "ratio": 1.0, "kind": "call", "T": T, "t0": T0, "iv": iv,
                         "pre_mid": 1.0, "ES": 0.0}, index=np.arange(n))


def _gbm_points(n_paths, n_steps, dt_s, sig_real, seed=0, S0=100.0):
    rng = np.random.default_rng(seed)
    dt = dt_s / hedging.YEAR_S
    z = rng.standard_normal((n_paths, n_steps))
    logS = np.log(S0) + np.cumsum((-0.5 * sig_real ** 2) * dt + sig_real * np.sqrt(dt) * z, axis=1)
    S = np.c_[np.full(n_paths, S0), np.exp(logS)]
    t = T0 + pd.to_timedelta(np.arange(n_steps + 1) * dt_s, unit="s")
    return pd.DataFrame({"pos": np.repeat(np.arange(n_paths), n_steps + 1), "time": np.tile(t, n_paths),
                         "S": S.ravel(), "rate": 0.0})


def _run(pts, pos, every=1):
    # r = 0: the hedge is not financed in the simulation (intraday carry is negligible), so the GBM
    # identity is checked without the rate term
    x = hedging.option_pieces(pts.assign(sigma=pos.loc[pts["pos"], "iv"].to_numpy()), pos, r=0.0)
    k = x.groupby("pos").cumcount()
    x = x.assign(hedge=(k % every == 0) & ~x["last"])
    return hedging.trade_hedge(x)


def test_decomposition_is_exact():
    pos = _pos(3)
    pts = _gbm_points(3, 50, 600, 0.5, seed=3)
    sig = 0.4 + 0.05 * np.sin(np.arange(len(pts)))              # moving IV: vega non-zero
    x = hedging.option_pieces(pts.assign(sigma=sig), pos)
    x = hedging.trade_hedge(x.assign(hedge=~x["last"]))
    for p, g in x.groupby("pos"):
        T = g["T"].to_numpy()
        W = warrant_price(g["S"].to_numpy(), 100.0, R, Q, g["sigma"].to_numpy(), T, 1.0, "call")
        direct = -1000.0 * (W[-1] - W[0]) + (g["h"] * g["dS"]).sum()
        assert (g["theta"] + g["gamma"] + g["vega"]).sum() == pytest.approx(direct, rel=1e-9, abs=1e-9)


def test_delta_hedged_pnl_matches_variance_gap():
    pos = _pos(400, iv=0.3, T=0.5)
    pts = _gbm_points(400, 240, 3600, 0.3, seed=1)              # 10 calendar days, hourly hedging
    same = _run(pts, pos).groupby("pos")[["theta", "gamma"]].sum().sum(axis=1)
    assert abs(same.mean()) < 3 * same.std() / np.sqrt(len(same))   # sigma_real = sigma_implied: ~ 0
    pts2 = _gbm_points(400, 240, 3600, 0.45, seed=1)
    x = _run(pts2, pos)
    pnl = x.groupby("pos")[["theta", "gamma"]].sum().sum(axis=1)
    g = bs_greeks(x["S"].to_numpy(), 100.0, 0.0, Q, 0.3, x["T"].to_numpy(), "call")["gamma"]
    dt = 3600 / hedging.YEAR_S
    exp = (-1000.0 * 0.5 * g * x["S"] ** 2 * (0.45 ** 2 - 0.3 ** 2) * dt * ~x["last"]).groupby(x["pos"]).sum()
    assert pnl.mean() == pytest.approx(exp.mean(), rel=0.15)    # short gamma loses 1/2 Γ S² (σr² - σi²) τ


def test_more_frequent_hedging_reduces_error():
    pos = _pos(300, iv=0.3)
    pts = _gbm_points(300, 240, 600, 0.3, seed=2)
    v = lambda every: _run(pts, pos, every).groupby("pos")[["theta", "gamma"]].sum().sum(axis=1).std()
    assert v(1) < v(12) < v(240)


def test_latency_segment_is_unhedged():
    pos = _pos(1)
    pts = pd.DataFrame({"pos": 0, "time": [T0, T0 + pd.Timedelta("1s"), T0 + pd.Timedelta("5min")],
                        "S": [100.0, 102.0, 102.0], "rate": [np.nan, 0.001, np.nan]})
    x = hedging.option_pieces(pts.assign(sigma=0.4), pos)
    x = hedging.trade_hedge(x.assign(hedge=[False, True, False]))
    assert x["h"].iloc[0] == 0 and x["h"].iloc[1] > 0          # hedge only from the fill
    assert x["gamma"].iloc[0] < 0                                # the jump before the fill is lost
    assert x["cost"].iloc[1] == pytest.approx(x["h"].iloc[1] * 102.0 * 0.001)
    assert x["cost"].sum() == pytest.approx(x["cost"].iloc[1])   # no NaN cost on non-hedge rows


def test_book_band_and_allocation():
    pos = _pos(2, N=-1000.0)
    pos.loc[1, "N"] = 1000.0                                     # offsetting positions: no net hedge needed
    t = T0 + pd.to_timedelta([0, 60, 120, 180], unit="s")
    rows = []
    for p in (0, 1):
        rows.append(pd.DataFrame({"pos": p, "time": [T0 - pd.Timedelta("1s")] + list(t), "S": [100, 100, 101, 99, 100.0],
                                  "rate": [np.nan, 0.001, 0.001, 0.001, np.nan], "ev": [-1, 0, 1, 2, 3],
                                  "hedge": [False, True, True, True, True]}))
    pts = pd.concat(rows, ignore_index=True).sort_values(["pos", "time"]).reset_index(drop=True)
    x = hedging.option_pieces(pts.assign(sigma=0.4), pos)
    y = hedging.book_hedge(x, band=10)
    assert y["cost"].sum() == 0                                  # targets cancel: never trade
    assert y["band_err"].sum() == pytest.approx(-(y["h"] * y["dS"]).sum())   # book hedge 0 => error offsets own hedges
    one = hedging.book_hedge(x[x["pos"] == 0], band=10)
    D = one.loc[one["ev"] == 0, "target"].iloc[0]
    assert one["cost"].sum() == pytest.approx(abs(D) * 100 * 0.001 + one["cost"].iloc[2:].sum())
    big = hedging.book_hedge(x[x["pos"] == 0], band=1e9)
    assert big["cost"].sum() == 0
    tot = (big["gamma_opt"] + big["h"] * big["dS"] + big["band_err"]).sum()
    assert tot == pytest.approx(big["gamma_opt"].sum())          # nothing hedged: band error cancels own hedge


def test_iv_path_backward_and_bounds():
    from wtox.research import markout
    day = "2025-03-03"
    p = pd.DataFrame({"warrant_id": "A", "datetime": pd.to_datetime([f"{day} 09:01:30", f"{day} 09:03:00", f"{day} 09:04:10"]),
                      "pre_mid": 1.0, "iv": [0.4, 4.99, 0.5], "delta": 0.5, "order_tick_type": 1, "T": 0.1})
    ivp = markout.build_iv_path(p, day).set_index("tau")["iv_tau"]
    t = lambda hm: pd.Timestamp(f"{day} {hm}")
    assert np.isnan(ivp[t("09:01")]) and ivp[t("09:02")] == 0.4
    assert ivp[t("09:03")] == 0.4                      # 4.99 hits the solver bound: previous value kept
    assert ivp[t("09:04")] == 0.4 and ivp[t("09:05")] == 0.5   # 09:04:10 not visible at 09:04
    assert ivp.index.max() == t("13:24")


def test_sigma_at_close_reads_last_grid_minute():
    day = pd.Timestamp("2025-03-03")
    pos = pd.DataFrame({"iv": [0.3], "warrant_id": ["A"], "t0": [day + pd.Timedelta("10h")]}, index=[0])
    ivp = pd.DataFrame({"warrant_id": "A", "tau": [day + pd.Timedelta("9h59min"), day + pd.Timedelta("13h24min")],
                        "iv_tau": [0.2, 0.5]})
    times = pd.Series([day + pd.Timedelta("10h"), day + pd.Timedelta("13h25min"), day + pd.Timedelta("13h24min30s")])
    sig = hedging._sigma_at(times, np.zeros(3, int), pos, ivp, "path")
    assert sig.tolist() == [0.3, 0.5, 0.5]             # before the trade: at-trade IV, never an older one


def test_trade_points_order():
    day = pd.Timestamp("2025-03-03")
    pos = pd.DataFrame({"t0": [day + pd.Timedelta("10h00min30s")], "S_mid": 100.0, "S_mid_1s": 100.1, "S_mid_5m": 100.5,
                        "S_mid_close": 101.0, "rate_fill": 0.001}, index=[7])
    grid = pd.DataFrame({"tau": day + config.SESSION_OPEN + pd.to_timedelta(np.arange(265), unit="min"), "S_mid_tau": 100.0})
    rg = pd.Series(0.001, index=grid["tau"])
    x = hedging.trade_points(pos, grid, "5m", "1s", 1, rg)
    assert x["time"].is_monotonic_increasing and x["hedge"].tolist()[:2] == [False, True]
    assert x["time"].iloc[-1] == pos["t0"].iloc[0] + pd.Timedelta("5min") and len(x) == 2 + 5 + 1      # entry, fill, 10:01-10:05, end
    c = hedging.trade_points(pos, grid, "close", "1s", 5, rg)
    assert ((c["time"].iloc[2:-1].dt.minute % 5) == 0).all() and c["time"].iloc[-1] == day + config.CONTINUOUS_END
