"""Stage 4: permutation expectation, robust flags, momentum regression, H3 fixed effects, recompute."""

import numpy as np
import pandas as pd
import pytest

from wtox.research import config, robustness, toxicity

MAIN = config.MAIN_HORIZON


def _d(n=3000, seed=0, days=30):
    rng = np.random.default_rng(seed)
    day = pd.Timestamp("2025-03-03") + pd.to_timedelta(rng.integers(0, days, n), unit="D")
    d = pd.DataFrame({
        "datetime": day + config.SESSION_OPEN + pd.to_timedelta(rng.integers(0, 3600, n), unit="s"),
        "side": rng.choice([1, -1], n, p=[0.6, 0.4]).astype(float), "weight": rng.uniform(1, 5, n),
        "kind_sign": 1.0, f"trunc_{MAIN}": False, "cost_neutral": 0.0,
    })
    y = rng.normal(0.001, 0.002, n)
    d[f"M_dt_{MAIN}"] = d["side"] * y
    d[f"RS_dt_{MAIN}"] = 0.01
    return d


def test_permutation_expectation_matches_shuffles():
    d = _d()
    r = robustness.permutation_placebo(d, B=400, seed=1).iloc[0]
    assert r["perm_mean_bps"] == pytest.approx(r["expected_bps"], abs=0.3)
    # with side independent of y, the actual value is just one more draw
    assert 0.01 < r["p_one_sided"] < 0.99


def test_permutation_detects_timing_information():
    d = _d()
    d[f"M_dt_{MAIN}"] = np.abs(d[f"M_dt_{MAIN}"]) + 0.002              # trades always right
    r = robustness.permutation_placebo(d, B=200, seed=2).iloc[0]
    assert r["actual_bps"] > r["perm_p95_bps"] and r["p_one_sided"] == pytest.approx(1 / 201)


def test_robust_flags():
    main = pd.DataFrame({"value": ["a", "b"], "mean_bps": [10.0, -5.0], "se_bps": [2.0, 1.0]})
    rows = pd.DataFrame({"value": ["a", "a", "b"], "mean_bps": [12.0, 20.0, 1.0]})
    assert robustness.robust_flags(rows, main)["robust"].tolist() == [True, False, False]
    # split variants are matched on their group, not on the pooled estimate
    base = pd.DataFrame({"value": ["a", "a"], "g": ["x", "y"], "mean_bps": [40.0, 10.0], "se_bps": [2.0, 2.0]})
    rows = pd.DataFrame({"value": ["a", "a"], "g": ["x", "y"], "mean_bps": [40.0, 40.0]})
    assert robustness.robust_flags(rows, base, ("value", "g"))["robust"].tolist() == [True, False]


def test_momentum_intercept_and_slope():
    rng = np.random.default_rng(3)
    n = 4000
    d = pd.DataFrame({"datetime": pd.Timestamp("2025-03-03 09:30") + pd.to_timedelta(rng.integers(0, 40, n), unit="D"),
                      "side": rng.choice([1.0, -1.0], n), "kind_sign": rng.choice([1.0, -1.0], n),
                      "weight": rng.uniform(1, 3, n), f"trunc_{MAIN}": False, "cost_neutral": 0.0, f"RS_dt_{MAIN}": 0.0,
                      "S_ret_1m": rng.normal(0, 1e-3, n), "S_ret_5m": rng.normal(0, 2e-3, n),
                      "leverage": rng.uniform(2, 10, n)})
    own5 = d["side"] * d["kind_sign"] * d["leverage"] * d["S_ret_5m"] * 1e4
    d[f"M_dt_{MAIN}"] = (5.0 + 0.5 * own5 + rng.normal(0, 1, n)) / 1e4
    r = robustness.momentum(d)
    a = r[r["group"] == "all"].set_index("term")
    assert a.loc["const", "coef"] == pytest.approx(5.0, abs=0.1)
    assert a.loc["own_ret_5m_bps", "coef"] == pytest.approx(0.5, abs=0.02)
    assert abs(a.loc["own_ret_1m_bps", "coef"]) < 0.05


def test_h3_fixed_effects_undo_composition():
    """Issuer B looks more toxic only because it trades the toxic cell; with cell FE its effect is 0."""
    rng = np.random.default_rng(4)
    n = 6000
    issuer = rng.choice(["A", "B"], n, p=[0.6, 0.4])
    toxic_cell = np.where(issuer == "B", rng.random(n) < 0.8, rng.random(n) < 0.2)
    d = pd.DataFrame({"datetime": pd.Timestamp("2025-03-03 10:00") + pd.to_timedelta(rng.integers(0, 30, n), unit="D"),
                      "issuer": issuer, "weight": 1.0, f"trunc_{MAIN}": False, "cost_neutral": 0.0, f"RS_dt_{MAIN}": 0.0,
                      "delta_bucket": np.where(toxic_cell, "0.4–0.6", ">0.6"), "dte_bucket": np.where(toxic_cell, "1–30", ">180"),
                      "pre_spread_pct": np.where(issuer == "B", 0.02, 0.01)})
    d[f"M_dt_{MAIN}"] = (np.where(toxic_cell, 50.0, 10.0) + rng.normal(0, 5, n)) / 1e4
    raw = d.groupby("issuer")[f"M_dt_{MAIN}"].mean() * 1e4
    assert raw["B"] - raw["A"] > 15
    r = robustness.h3_issuers(d).set_index("issuer")
    assert r.loc["A", "coef"] == 0 and abs(r.loc["B", "coef"]) < 1.0
    assert r.loc["B", "half_spread_bps"] == pytest.approx(100)


def test_recompute_at_the_same_rate_reproduces_the_metrics():
    from tests.test_research_toxicity import _trades
    d = toxicity.add_cuts(toxicity.hedge_costs(toxicity.detrend(toxicity.trade_metrics(_trades()),
                          pd.Series({h: 0.0 for h in config.HORIZONS if h != "close"} | {"close_per_s": 0.0}))))
    drifts = pd.DataFrame({"2025-03-03": pd.Series({h: 0.0 for h in config.HORIZONS if h != "close"} | {"close_per_s": 0.0})}).T
    x = robustness.recompute(d, drifts, r=config.RISK_FREE)
    assert np.allclose(x[f"M_dt_{MAIN}"], d[f"M_dt_{MAIN}"], rtol=1e-6)
    y = robustness.recompute(d, drifts, r=0.03)
    assert not np.allclose(y["iv"], d["iv"])                            # a different rate moves the IV
