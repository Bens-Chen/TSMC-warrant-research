"""H4 flow: window sums use only [τ - k, τ), denominators use only earlier days, OLS recovers betas."""

import numpy as np
import pandas as pd
import pytest

from wtox.research import config, flow

DAY = "2025-03-03"


def _stock():
    t = pd.Timestamp(DAY) + config.SESSION_OPEN + pd.to_timedelta([10, 70, 290, 299, 301], unit="s")
    return pd.DataFrame({"datetime": t, "close": [1000.0, 1005, 1010, 1010, 1015], "volume": [1, 2, 3, 4, 5],
                         "bid_price": [995.0, 1000, 1005, 1005, 1010], "ask_price": [1005.0, 1010, 1015, 1015, 1020],
                         "tick_type": [1, 1, 2, 1, 1]})


def _panel():
    t = pd.Timestamp(DAY) + config.SESSION_OPEN + pd.to_timedelta([5, 200, 300, 301], unit="s")
    return pd.DataFrame({"datetime": t, "share_equiv": [100.0, -40.0, 7.0, np.nan], "order_tick_type": [1, 2, 1, 1],
                         "kind": ["call", "put", "call", "call"], "notional": [10.0, 10, 10, 10],
                         "T": [30 / 365, 200 / 365, 30 / 365, 30 / 365]})


def test_window_excludes_tau_itself_and_older_than_k():
    f = flow.build_flow(_panel(), _stock(), DAY, np.full(len(flow.taus(DAY)), 2000.0))
    first = f.iloc[0]                                    # τ = 09:05: window [09:00, 09:05)
    assert first["tau"] == pd.Timestamp(DAY) + config.H4_FIRST_TAU
    assert first["F"] == 60 and first["F_call"] == 100 and first["F_put"] == -40      # 09:05:00 trade excluded
    assert first["F_short"] == 100 and first["F_long"] == -40
    assert first["stock_shares"] == 10 * 1000 and first["stock_signed"] == (2 - 3 + 4) * 1000   # first print = opening auction, unsigned
    assert first["F_norm"] == pytest.approx(60 / 2000) and first["S_mid_now"] == 1010
    assert np.isnan(first["ret_past"])                   # no 2330 tick at or before 09:00 -> unknown, not guessed
    second = f.iloc[1]                                   # τ = 09:06: mid at 09:06 (1015) vs at 09:01 (1000)
    assert second["ret_past"] == pytest.approx(1015 / 1000 - 1)
    assert f.attrs["flow_notional_share"] == pytest.approx(0.75)


def test_denominator_uses_only_earlier_days(tmp_path):
    days = ["2025-03-03", "2025-03-04", "2025-03-05"]
    for i, day in enumerate(days):
        (tmp_path / "panel" / "tsmc_warrant_trades").mkdir(parents=True, exist_ok=True)
        p = _panel().assign(datetime=lambda d: d["datetime"] + pd.Timedelta(days=i))
        p.to_parquet(tmp_path / "panel" / "tsmc_warrant_trades" / f"{day}.parquet")
        sd = tmp_path / "shioaji" / "underlying_ticks" / "stock" / "2330"
        sd.mkdir(parents=True, exist_ok=True)
        _stock().assign(datetime=lambda d: d["datetime"] + pd.Timedelta(days=i), volume=lambda d: d["volume"] * (i + 1)) \
            .to_parquet(sd / f"{day}.parquet")
    import wtox.research.flow as fl
    old = config.H4_NORM_LOOKBACK_DAYS
    try:
        config.H4_NORM_LOOKBACK_DAYS = 2
        fl.run(tmp_path)
    finally:
        config.H4_NORM_LOOKBACK_DAYS = old
    out = [pd.read_parquet(tmp_path / "flow" / f"{d}.parquet") for d in days]
    assert out[0]["denom"].isna().all() and out[1]["denom"].isna().all()
    assert out[2]["denom"].iloc[0] == pytest.approx((10 + 20) / 2 * 1000)    # days 1 and 2 only, not day 3 (30)


def test_ols_cluster_recovers_betas():
    rng = np.random.default_rng(1)
    n = 4000
    day = np.repeat(np.arange(40), 100)
    x = rng.normal(size=n)
    y = 2.0 + 3.0 * x + rng.normal(size=40)[day] + rng.normal(size=n)
    X = pd.DataFrame({"const": 1.0, "x": x})
    r = flow.ols_cluster(y, X, day).set_index("term")
    assert r.loc["x", "coef"] == pytest.approx(3.0, abs=0.05)
    # the intercept's clustered SE reflects the day effect (~1/sqrt(40)), far above the iid SE
    assert r.loc["const", "se"] > 0.1 and r.loc["x", "n_days"] == 40
