"""IV checks: delta signs, TEJ comparison on (code, date), same-side IV pairs only."""

import numpy as np
import pandas as pd
import pytest

from wtox import bs_greeks, warrant_price
from wtox.research import config, ivcheck

DAY = pd.Timestamp("2026-09-01")
S, K, RATIO, T = 1000.0, 1100.0, 0.02, 60 / 365


def _orders(ivs, sides, minutes):
    kind = "call"
    px = [warrant_price(S, K, config.RISK_FREE, 0, v, T, RATIO, kind) for v in ivs]
    n = len(ivs)
    return pd.DataFrame({
        "datetime": [DAY + pd.Timedelta(hours=9, minutes=m) for m in minutes], "warrant_id": "030001",
        "kind": kind, "issuer": "元大", "strike": K, "ratio": RATIO, "T": T, "S_mid": S, "moneyness": np.log(S / K),
        "close": px, "side": sides, "fill_seq": 0, "order_volume": 10,
    })


def test_same_side_pairs_never_mix_buys_and_sells():
    # ask IV 0.50 -> 0.48 on buys; bids at 0.45 in between must not be paired with buys
    o = _orders([0.50, 0.45, 0.48, 0.44], [1, -1, 1, -1], [0, 1, 2, 3])
    pairs = ivcheck.same_side_iv_changes(o).set_index("side")
    assert len(pairs) == 2
    assert pairs.loc[1, "d_iv"] == pytest.approx(-0.02, abs=1e-4)
    assert pairs.loc[-1, "d_iv"] == pytest.approx(-0.01, abs=1e-4)
    assert pairs.loc[1, "gap_s"] == 120


def test_pairs_farther_apart_than_the_cap_are_dropped():
    o = _orders([0.50, 0.40], [1, 1], [0, 45])
    assert ivcheck.same_side_iv_changes(o, max_gap=pd.Timedelta(minutes=30)).empty


def test_delta_sign_and_tej_join():
    d = bs_greeks(S, K, 0.015, 0, 0.5, T, "call")["delta"]
    panel = pd.DataFrame({
        "datetime": [DAY + pd.Timedelta(hours=9), DAY + pd.Timedelta(hours=10), DAY + pd.Timedelta(hours=10)],
        "warrant_id": ["030001", "030001", "03962T"], "kind": ["call", "call", "put"], "ratio": RATIO,
        "iv": [0.52, 0.50, 0.40], "delta": [d, d, 0.1],          # the put's positive delta is a violation
    })
    s = ivcheck.delta_sign(panel).set_index("kind")
    assert s.loc["call", "n_bad"] == 0 and s.loc["put", "n_bad"] == 1
    tej = pd.DataFrame({"date": [DAY, DAY], "warrant_id": ["030001", "03962T"], "tej_iv": [0.49, 0.41],
                        "tej_delta": [d * RATIO, -0.01], "days_to_expiry": [60, 90]})
    out = ivcheck.iv_vs_tej(panel, tej, ex_dates=[DAY - pd.Timedelta(days=2), DAY + pd.Timedelta(days=30)])
    out = out.set_index("warrant_id")
    assert out.loc["030001", "iv_last"] == 0.50 and out.loc["030001", "iv_median"] == pytest.approx(0.51)
    assert out.loc["030001", "iv_diff"] == pytest.approx(0.01)
    assert out.loc["030001", "delta_diff"] == pytest.approx(0)       # ours scaled by ratio like TEJ's
    assert out.loc["030001", "days_from_ex"] == 2
