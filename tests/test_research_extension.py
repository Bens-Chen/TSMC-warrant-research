"""Extension B-D: proxy IV is backward-only, proxy bias check, combined estimate, C readings, netting."""

import numpy as np
import pandas as pd
import pytest

from wtox.research import config, extension as ext


def _panel(rows):
    base = {"pre_mid": 1.0, "delta": 0.5, "order_tick_type": 1, "T": 0.1, "strike": 100.0, "kind": "call"}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_proxy_iv_strictly_earlier_and_carry():
    t = pd.Timestamp("2025-03-03 09:10")
    p = _panel([
        {"warrant_id": "A", "datetime": t, "iv": 0.40, "strike": 100.0, "kind": "call"},
        {"warrant_id": "A", "datetime": t + pd.Timedelta("1min"), "iv": 0.50},
        {"warrant_id": "A", "datetime": t + pd.Timedelta("1min"), "iv": np.nan, "pre_mid": np.nan},   # same order
        {"warrant_id": "A", "datetime": t + pd.Timedelta("2min"), "iv": 4.99},                       # solver bound
        {"warrant_id": "A", "datetime": t + pd.Timedelta("3min"), "iv": np.nan, "pre_mid": np.nan},
        {"warrant_id": "B", "datetime": t, "iv": np.nan, "pre_mid": np.nan},
    ])
    exp = pd.Timestamp("2025-03-03") + pd.Timedelta(days=round(0.1 * 365))
    carry = {"B": (pd.Timestamp("2025-02-28 13:00"), 0.33, 100.0, "call", exp + pd.Timedelta(days=1))}
    iv, when, new = ext.proxy_iv(p, carry)
    assert np.isnan(iv[0])                           # nothing earlier that day, no carry for A
    assert iv[1] == pytest.approx(0.40) and iv[2] == pytest.approx(0.40)   # own timestamp excluded
    assert iv[4] == pytest.approx(0.50)              # the bound-hitting 4.99 is skipped
    assert iv[5] == pytest.approx(0.33)              # previous day's last value
    assert new["A"][1] == pytest.approx(0.50) and "B" not in new          # carry = previous day only


def _bframe(n=4000, seed=0, bias=0.0):
    rng = np.random.default_rng(seed)
    day = pd.Timestamp("2025-03-03") + pd.to_timedelta(rng.integers(0, 40, n), unit="D")
    d = pd.DataFrame({"day": day, "datetime": day + pd.Timedelta("10h"), "has_quote": rng.random(n) < 0.7,
                      "notional_P": rng.uniform(1e3, 1e5, n), "delta": rng.uniform(0.05, 0.6, n),
                      "dte_bucket": rng.choice(["1–30", ">180"], n), "close": rng.uniform(0.02, 2, n),
                      "direction": rng.choice(["buy", "sell"], n),
                      "iv_age": rng.choice(list(config.EXT_IV_AGE_LABELS), n)})
    d["x_true"] = (20 + rng.normal(0, 30, n)) / 1e4
    d["x_proxy"] = d["x_true"] + bias / 1e4 + rng.normal(0, 1, n) / 1e4
    d.loc[~d["has_quote"], "x_true"] = np.nan
    return d


def test_validation_detects_bias():
    ok = ext.b_validation(_bframe(bias=0.0))
    bad = ext.b_validation(_bframe(bias=8.0))
    crit = lambda v: v[v["criterion"]].iloc[0]
    assert crit(ok)["within_margin"] and not crit(bad)["within_margin"]
    assert crit(bad)["mean_bps"] == pytest.approx(8.0, abs=0.3)


def test_combined_estimate_weights_by_notional():
    d = _bframe()
    est = ext.b_estimate(d, True).set_index(["scope", "estimate"])
    a = est.loc[("all", "quoted_only")]
    b = est.loc[("all", "missing_proxy")]
    c = est.loc[("all", "combined")]
    exp = (a["mean_bps"] * a["share_notional"] + b["mean_bps"] * b["share_notional"]) / (a["share_notional"] + b["share_notional"])
    assert c["mean_bps"] == pytest.approx(exp, rel=1e-9)


def test_reading_rules():
    assert ext._reading(-10, -2, 20) == "reversion"
    assert ext._reading(-5, 10, 20) == "no marked reversion"       # lower bound above -50% of 20
    assert ext._reading(-15, 3, 20) == "inconclusive"


def test_c2_markout_paired_difference():
    rng = np.random.default_rng(1)
    n = 6000
    day = pd.Timestamp("2025-03-03") + pd.to_timedelta(rng.integers(0, 30, n), unit="D")
    d = pd.DataFrame({"datetime": day + pd.Timedelta("10h"), "side": rng.choice([1.0, -1.0], n),
                      "weight": 1.0, "trunc_5m": False, "trunc_30m": False})
    m5 = (20 + rng.normal(0, 10, n)) / 1e4
    for pre in ("M_", "M_dt_"):
        d[f"{pre}5m"] = m5
        d[f"{pre}30m"] = m5 * 0.2 + rng.normal(0, 1, n) / 1e4    # 80% reverts
        d[f"{pre}close"] = m5 + rng.normal(0, 1, n) / 1e4        # persists
    late = d.index[:50]
    d.loc[late, "datetime"] = d.loc[late, "datetime"].dt.normalize() + pd.Timedelta("13h")   # after 12:55: dropped
    r = ext.c2_markout(d).query("group == 'all' and version == 'detrended'").set_index("horizon")
    assert r.loc["30m", "reading"] == "reversion" and r.loc["30m", "reversion_share"] == pytest.approx(0.8, abs=0.02)
    assert r.loc["close", "reading"] == "no marked reversion"
    assert r.loc["5m", "n"] == n - 50


def test_net_positions_and_turnover():
    minutes = pd.date_range("2025-03-03 09:05", "2025-03-03 09:30", freq="1min").to_numpy("datetime64[ns]")
    tau = lambda m: pd.Timestamp("2025-03-03 09:05") + pd.Timedelta(minutes=m)
    flip = pd.DataFrame({"tau": [tau(0), tau(5)], "signal": [1.0, -1.0]})
    pos = ext.net_positions(flip, minutes)
    assert pos[0] == pytest.approx(0.2) and pos[5] == pytest.approx(-0.2) and pos[10] == pytest.approx(0)
    assert np.abs(np.diff(np.r_[0, pos])).sum() == pytest.approx(0.2 + 0.4 + 0.2)   # flip trades 2/5
    every = pd.DataFrame({"tau": [tau(m) for m in range(20)], "signal": 1.0})
    traded = np.abs(np.diff(np.r_[0, ext.net_positions(every, minutes)])).sum()
    assert traded == pytest.approx(2.0)                                          # vs 2 * 20 / 5 = 8 unnetted
    assert ext.net_positions(every, minutes).max() == pytest.approx(1.0)


def test_c1_lambda_recovered():
    rng = np.random.default_rng(2)
    rows = []
    for k, day in enumerate(pd.bdate_range("2025-03-03", periods=40)):
        tau = day + config.H4_FIRST_TAU + pd.to_timedelta(np.arange(200), unit="min")
        sn = rng.normal(0, 0.05, 200)
        rows.append(pd.DataFrame({"day": day.strftime("%Y-%m-%d"), "tau": tau, "signed_norm": sn,
                                  "ret_past": (30 * sn + rng.normal(0, 1, 200)) / 1e4, "tod": np.arange(200) // 30,
                                  "F": rng.normal(0, 1e4, 200), "stock_shares": 1e6,
                                  "F_norm": rng.normal(0, 0.02, 200)}))
    f = pd.concat(rows, ignore_index=True)
    h4 = f.assign(y_bps=100 * f["F_norm"] + rng.normal(0, 1, len(f)))
    out = ext.c1_coefficients(f, h4).set_index("name")
    assert out.loc["lambda", "coef"] == pytest.approx(30, abs=1)
    assert out.loc["beta_controls", "coef"] == pytest.approx(100, abs=5)
    assert out["reading"].iloc[0] == "delayed hedging cannot fully explain H4"
    size = ext.c1_size(f)
    no = ext._non_overlapping(f)
    no = no[no["tau"] - no["tau"].dt.normalize() != config.H4_FIRST_TAU]           # opening window dropped
    assert size["pooled"].iloc[0] == pytest.approx(no["F"].abs().sum() / (1e6 * len(no)))


def test_reading_sign_aware():
    assert ext._reading(2, 10, -20) == "reversion"                   # negative baseline moving toward 0
    assert ext._reading(-10, 5, -20) == "no marked reversion"
    assert ext._reading(-1, 1, 0) == "n/a (baseline zero)"


def test_carry_rejects_reused_code():
    t = pd.Timestamp("2025-03-04 09:10")
    p = _panel([{"warrant_id": "A", "datetime": t, "iv": np.nan, "pre_mid": np.nan, "strike": 100.0, "kind": "call"},
                {"warrant_id": "B", "datetime": t, "iv": np.nan, "pre_mid": np.nan, "strike": 100.0, "kind": "call"}])
    exp = pd.Timestamp("2025-03-04") + pd.Timedelta(days=round(0.1 * 365))
    carry = {"A": (pd.Timestamp("2025-03-03 13:00"), 0.3, 100.0, "call", exp),
             "B": (pd.Timestamp("2025-03-03 13:00"), 0.3, 80.0, "call", exp)}     # B: another warrant, same code
    iv, _, _ = ext.proxy_iv(p, carry)
    assert iv[0] == pytest.approx(0.3) and np.isnan(iv[1])
