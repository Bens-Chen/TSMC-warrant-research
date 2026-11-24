"""Magnitude table: contributions sum to the overall weighted mean; shares sum to one per group set."""

import numpy as np
import pandas as pd
import pytest

from wtox.research import magnitude


def test_contributions_sum_to_overall():
    rng = np.random.default_rng(0)
    n = 1000
    d = pd.DataFrame({"weight": rng.uniform(1, 10, n), "net_neutral": rng.normal(0, 0.01, n),
                      "M_dt_5m": rng.normal(0, 0.003, n), "ES": rng.uniform(0, 0.02, n),
                      "delta_bucket": rng.choice(["<0.2", ">0.6"], n), "dte_bucket": rng.choice(["1–30", ">180"], n),
                      "spot_1s": rng.choice(["favourable", "none"], n), "spot_print": rng.choice(["just_ticked", "quiet"], n),
                      "tod": rng.choice(["a", "b", "c"], n)})
    m = magnitude.magnitude(d)
    overall = (d["weight"] * d["net_neutral"]).sum() / d["weight"].sum() * 1e4
    for _, g in m.groupby("group_set"):
        assert g["contribution_bps"].sum() == pytest.approx(overall)
        assert g["share_notional"].sum() == pytest.approx(1.0)
    assert m["net_ntd"].groupby(m["group_set"]).sum().iloc[0] == pytest.approx((d["weight"] * d["net_neutral"]).sum())
