"""Stage 5: score model recovers effects, training-only levels and bounds, OOS R², heatmap cells, replication."""

import numpy as np
import pandas as pd
import pytest

from wtox.research import config, oos

H = config.MAIN_HORIZON


def _d(n=4000, seed=0, start="2025-03-03", issuers=("A", "B")):
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({
        "datetime": pd.Timestamp(start) + config.SESSION_OPEN + pd.to_timedelta(rng.integers(0, 60, n), unit="D")
                    + pd.to_timedelta(rng.integers(0, 3600, n), unit="s"),
        "side": rng.choice([1.0, -1.0], n), "kind": rng.choice(["call", "put"], n), "leverage": rng.uniform(2, 8, n),
        "order_volume": rng.integers(1, 200, n), "S_age_s": rng.uniform(0, 2, n),
        "S_ret_1m": rng.normal(0, 1e-3, n), "S_ret_5m": rng.normal(0, 2e-3, n),
        "pre_spread_pct": rng.uniform(0.005, 0.05, n), "prev_in_force": rng.random(n) < 0.5,
        "prev_quote_age_s": np.where(rng.random(n) < 0.1, np.nan, rng.exponential(300, n)),
        "issuer": rng.choice(list(issuers), n), "tod": rng.choice(list(config.TOD_LABELS), n),
        "delta_bucket": rng.choice(list(config.DELTA_BUCKET_LABELS), n), "dte_bucket": rng.choice(["1–30", ">180"], n),
        "spot_1s": rng.choice(["favourable", "none", "adverse"], n, p=[0.1, 0.85, 0.05]),
        "weight": rng.uniform(1, 3, n), "close": rng.uniform(0.5, 3, n),
    })
    d["kind_sign"] = np.where(d["kind"] == "put", -1.0, 1.0)
    d["notional"] = d["close"] * d["order_volume"] * 1000
    d = oos.add_cell(d)
    d[f"M_dt_{H}"] = (10 + 30 * (d["spot_1s"] == "favourable") + rng.normal(0, 5, n)) / 1e4
    d["ES"] = 0.015
    for k in config.HEDGE_SCENARIOS:
        d[f"cost_{k}"] = 0.005
    return d


def _drifts():
    return pd.DataFrame({"1m": [1e-4, 3e-4], "5m": [0.0, 0.0]}, index=["2025-03-03", "2025-03-04"])


def test_score_recovers_effect_and_uses_training_levels():
    tr, te = _d(), _d(seed=1, start="2025-07-01", issuers=("A", "C"))     # issuer C never seen in training
    st = oos.fit_stats(tr, _drifts())
    assert st["mom_drift"]["1m"] == pytest.approx(2e-4)                  # training mean drift, not the test day's
    beta = oos.fit_score(tr, st)
    assert beta["spot_fav"] == pytest.approx(30, abs=1.5)
    X = oos.design(te, st)
    assert list(X.columns) == list(oos.design(tr, st).columns)
    assert (X.filter(like="issuer_").sum(axis=1)[te["issuer"] == "C"] == 0).all()
    lo, hi = st["clip"]["half_spread"]
    assert X["half_spread"].between(lo, hi).all()


def test_score_eval_quintiles_and_oos_r2_baseline():
    tr, te = _d(), _d(seed=1, start="2025-07-01")
    st = oos.fit_stats(tr, _drifts())
    res = oos.score_eval(tr, te, st, oos.fit_score(tr, st))
    q = res["quintiles_test"].set_index("quintile")["mean_bps"]
    assert q["Q5"] > q["Q1"]
    assert res["q5_minus_q1_test"]["coef"].iloc[0] > 10
    # R² with the TRAINING mean as baseline: shift the test target and the R² must fall
    te2 = te.assign(**{f"M_dt_{H}": te[f"M_dt_{H}"] + 0.002})
    r2b = oos.score_eval(tr, te2, st, oos.fit_score(tr, st))["r2"]["r2_oos"].iloc[0]
    assert r2b < res["r2"]["r2_oos"].iloc[0]


def test_heatmap_cells_fixed_by_training():
    tr, te = _d(n=40000), _d(n=40000, seed=1, start="2025-07-01")
    te = te[te["delta_bucket"] != "<0.2"]                                # a cell family missing in test
    full, summ = oos.heatmap(tr, te)
    a = full[(full["sample"] == "train") & (full["value"] == "gap_neutral")]
    b = full[(full["sample"] == "test") & (full["value"] == "gap_neutral")]
    assert len(a) == len(b) == summ["n_cells"].iloc[0]                  # same cell list in both samples
    assert summ["n_cells"].iloc[0] > 0
    exp = (tr["ES"] - tr[f"M_dt_{H}"] - tr["cost_neutral"]).mul(tr["weight"]).sum() / tr["weight"].sum() * 1e4
    assert np.average(a["mean_bps"], weights=a["n"]) == pytest.approx(exp, abs=1.0)   # gap = ES - M - cost
    assert b["mean_bps"].isna().sum() > 0                                  # missing test cells stay in the list
    assert summ["n_cells_with_test"].iloc[0] < summ["n_cells"].iloc[0]


def test_tick_table():
    assert oos.tick(np.array([1500.0, 999.0, 450.0])).tolist() == [5.0, 1.0, 0.5]


def test_replication_rules():
    a = pd.DataFrame({"cut": "all", "group": ["x", "y", "z"], "value": "m", "mean_bps": [25.0, 25.0, 5.0],
                      "se_bps": [2.0, 13.0, 10.0], "p": [0.0, 0.06, 0.6]})
    b = a.assign(mean_bps=[38.0, 0.2, 4.0], se_bps=[3.0, 4.0, 3.0], p=[0.0, 0.96, 0.2])
    r = oos.replicate(a, b).set_index("group")
    assert r.loc["x", "sign_and_significance"] == 1 and not r.loc["x", "stable"]   # stronger, but a structural break
    assert np.isnan(r.loc["y", "sign_and_significance"])                           # not significant in training
    assert r.loc["z", "stable"]


def _flows(days, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for day in days:
        tau = pd.Timestamp(day) + config.H4_FIRST_TAU + pd.to_timedelta(np.arange(60), unit="min")
        f = rng.normal(0, 0.02, 60)
        rows.append(pd.DataFrame({"day": day, "tau": tau, "F_norm": f, "ret_past": rng.normal(0, 1e-3, 60),
                                  "signed_norm": rng.normal(0, 0.05, 60), "tod": (np.arange(60) // 30),
                                  "y_bps": 100 * f + rng.normal(0, 1, 60), "S_mid_now": 1500.0, "S_spread_bps_now": 33.3}))
    return pd.concat(rows, ignore_index=True)


def test_walk_forward_expanding_and_no_leak():
    tr = _d(n=6000, start="2025-01-02")
    te = _d(n=3000, seed=1, start="2025-07-01")
    tr = tr[tr["datetime"] < "2025-03-01"]
    te = te[(te["datetime"] >= "2025-07-01") & (te["datetime"] < "2025-09-01")]
    allt = pd.concat([tr, te], ignore_index=True).assign(warrant_id="W", trade_id=lambda x: range(len(x)))
    days = sorted(allt["datetime"].dt.strftime("%Y-%m-%d").unique())
    base = [d for d in days if d < "2025-03-01"]
    test_days = [d for d in days if d >= "2025-07-01"]
    drifts = pd.DataFrame({"1m": 0.0, "5m": 0.0}, index=days)
    out = oos.walk_forward(allt, _flows(days), drifts, base, test_days)
    assert set(out["wf_heatmap_monthly"]["month"]) == {"2025-07", "2025-08"}
    q = out["wf_quintiles"].set_index("quintile")["mean_bps"]
    assert q["Q5"] > q["Q1"]
    trig = out["wf_h4_triggers"]
    assert set(trig["month"]) <= {"2025-07", "2025-08"}
    assert out["wf_h4_trading"].query("signal == 'residual' and cost == 'futures_spread'")["gross_mean_bps"].iloc[0] > 0


def test_walk_forward_trains_only_on_earlier_days(monkeypatch):
    tr = _d(n=6000, start="2025-01-02")
    te = _d(n=3000, seed=1, start="2025-07-01")
    allt = pd.concat([tr[tr["datetime"] < "2025-03-01"],
                      te[(te["datetime"] >= "2025-07-01") & (te["datetime"] < "2025-09-01")]], ignore_index=True).assign(warrant_id="W", trade_id=lambda x: range(len(x)))
    days = sorted(allt["datetime"].dt.strftime("%Y-%m-%d").unique())
    seen = []
    real = oos.fit_score
    monkeypatch.setattr(oos, "fit_score", lambda train, st: seen.append(train["datetime"].max()) or real(train, st))
    oos.walk_forward(allt, _flows(days), pd.DataFrame({"1m": 0.0, "5m": 0.0}, index=days),
                     [d for d in days if d < "2025-03-01"], [d for d in days if d >= "2025-07-01"])
    assert seen[0] < pd.Timestamp("2025-07-01") and seen[1] < pd.Timestamp("2025-08-01")
    assert seen[1] >= pd.Timestamp("2025-07-01")                          # August's window includes July
