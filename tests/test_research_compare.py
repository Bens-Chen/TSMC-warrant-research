"""Cross-issuer comparison: weighted median, previous-day premiums and terciles, FE regression recovers a
planted cheap - expensive gap, issuer table is relative to the peer average."""

import numpy as np
import pandas as pd
import pytest

from wtox.research import compare


def test_wmedian():
    assert compare.wmedian([1, 2, 3], [1, 1, 10]) == 3
    assert compare.wmedian([1, 2, 3], [1, 1, 1]) == 2
    assert np.isnan(compare.wmedian([np.nan], [1]))


def test_day_stats_uses_quoted_trades_and_sets_peer():
    p = pd.DataFrame({"warrant_id": ["A", "A", "A"], "kind": "call", "pre_mid": [1.0, 1.0, np.nan], "iv": [0.3, 0.5, 0.9],
                      "notional": [100.0, 300.0, 1e6], "pre_spread_pct": [0.01, 0.02, 0.5], "delta": [0.3, 0.35, 0.9],
                      "T": [60 / 365] * 3})
    s = compare.day_stats(p).set_index("warrant_id")
    assert s.loc["A", "prev_iv"] == 0.5 and s.loc["A", "prev_spread"] == 0.02   # unquoted trade ignored
    assert s.loc["A", "peer_delta"] == "0.2–0.4" and s.loc["A", "peer_dte"] == "31–90"


def _prev(ivs=(0.30, 0.32, 0.34, 0.36, 0.38), spreads=(0.05, 0.04, 0.03, 0.02, 0.01)):
    n = len(ivs)
    return pd.DataFrame({"warrant_id": list("ABCDE")[:n], "kind": "call", "prev_iv": ivs, "prev_spread": spreads,
                         "peer_delta": "0.2–0.4", "peer_dte": "31–90"})


def test_premiums_terciles_from_previous_day_only():
    d = pd.DataFrame({"day": "2025-03-04", "warrant_id": ["A", "A", "E", "F"], "x": 1.0})
    out = compare.premiums(d, _prev())
    assert len(out) == 4                                                   # trade rows preserved
    o = out.set_index(["warrant_id", "x"]).groupby(level=0).first()
    assert o.loc["A", "iv_prem"] == pytest.approx(-0.04) and o.loc["A", "iv_prem_tercile"] == "cheap"
    assert o.loc["E", "iv_prem_tercile"] == "expensive" and o.loc["E", "spread_prem_tercile"] == "cheap"
    assert pd.isna(o.loc["F", "iv_prem_tercile"])                          # no d-1 data
    # the benchmark uses every d-1 warrant, not only those bought on d: dropping B..D from d changes nothing
    assert compare.premiums(d[d["warrant_id"] == "A"], _prev())["iv_prem"].iloc[0] == pytest.approx(-0.04)
    assert compare.premiums(d, _prev(ivs=(0.3, 0.32), spreads=(0.05, 0.04)))["iv_prem_tercile"].isna().all()   # < 3 peers


def _synthetic(n_days=60, gap=-0.01, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for k, day in enumerate(pd.bdate_range("2025-03-03", periods=n_days).strftime("%Y-%m-%d")):
        for peer in ("0.2–0.4", "0.4–0.6"):
            level = rng.normal(0, 0.05)                                       # peer-day level: absorbed by FE
            for t in ("cheap", "middle", "expensive"):
                for _ in range(10):
                    y = level + {"cheap": gap / 2, "middle": 0.0, "expensive": -gap / 2}[t] + rng.normal(0, 0.002)
                    rows.append({"day": day, "kind": "call", "peer_delta": peer, "peer_dte": "31–90", "n_peer": 30,
                                 "iv_prem_tercile": t, "spread_prem_tercile": t, "weight": rng.uniform(1, 2),
                                 "iv_prem_z": {"cheap": -1.0, "middle": 0.0, "expensive": 1.0}[t] + rng.normal(0, .1),
                                 "spread_prem_z": rng.normal(0, 1), "delta": 0.3, "moneyness": rng.normal(0, .1),
                                 "issuer": {"cheap": "甲", "middle": "乙", "expensive": "丙"}[t],
                                 "iv_prem": 0.0, "spread_prem": 0.0,
                                 **{o: y for o in compare.OUTCOMES}})
    return pd.DataFrame(rows)


def test_tercile_gap_recovered_with_fixed_effects():
    d = _synthetic()
    out = compare.tercile_tests(d, np.array(sorted(d["day"].unique())))
    r = out.query("outcome == 'hold_resid_5' and ranking == 'iv_prem' and spec == 'base'").iloc[0]
    assert r["cheap_minus_expensive_bps"] == pytest.approx(-100, abs=3)
    assert r["p"] < 1e-6
    j = out.query("outcome == 'ES' and spec == 'joint_per_1sd'").set_index("ranking")
    assert j.loc["iv_prem_z", "cheap_minus_expensive_bps"] == pytest.approx(50, abs=5)   # -(gap/2) per +1 sd
    assert abs(j.loc["spread_prem_z", "cheap_minus_expensive_bps"]) < 5


def test_issuer_table_relative_to_peer():
    d = _synthetic()
    t = compare.issuer_table(d, ["甲", "丙"], np.array(sorted(d["day"].unique())))
    t = t[t["outcome"] == "ES"].set_index("issuer")
    assert t.loc["甲", "vs_avg_bps"] == pytest.approx(-50, abs=3) and t.loc["丙", "vs_avg_bps"] == pytest.approx(50, abs=3)
    assert t.loc["其他", "vs_avg_bps"] == pytest.approx(0, abs=3)
    assert (t["share_notional"] * t["vs_avg_bps"]).sum() == pytest.approx(0, abs=1e-6)   # deviations from the weighted average
    assert (t["se_bps"] > 0).all()


def test_fe_wls_nw_lag_widens():
    rng = np.random.default_rng(1)
    days = np.repeat(np.arange(300), 4)
    x = rng.normal(size=len(days))
    shock = np.repeat(np.convolve(rng.normal(size=304), np.ones(5), "valid")[:300], 4)
    y = 0.5 * x + shock * x
    t0, _ = compare.fe_wls(y, {"x": x}, np.ones(len(y)), np.zeros(len(y)), days, 0)
    t5, _ = compare.fe_wls(y, {"x": x}, np.ones(len(y)), np.zeros(len(y)), days, 5)
    assert t0.loc["x", "coef"] == pytest.approx(t5.loc["x", "coef"])
    assert t5.loc["x", "se"] > 1.5 * t0.loc["x", "se"]                     # overlapping shocks: Bartlett lag widens SE
