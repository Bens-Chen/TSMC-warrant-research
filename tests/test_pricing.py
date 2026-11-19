"""Pricing core checks against closed-form values and internal consistency."""

import numpy as np
import pytest

from wtox import bs_greeks, bs_price, crr_price, implied_vol, warrant_greeks, warrant_iv, warrant_price

S, K, R, Q, SIGMA, T = 100.0, 100.0, 0.05, 0.0, 0.2, 1.0


def test_bs_textbook_values():
    # Hull's standard example: S=K=100, r=5%, sigma=20%, T=1
    assert bs_price(S, K, R, Q, SIGMA, T, "call") == pytest.approx(10.4506, abs=1e-4)
    assert bs_price(S, K, R, Q, SIGMA, T, "put") == pytest.approx(5.5735, abs=1e-4)


def test_put_call_parity_vectorised():
    k = np.array([80.0, 100.0, 120.0])
    c = bs_price(S, k, R, 0.02, SIGMA, T, "call")
    p = bs_price(S, k, R, 0.02, SIGMA, T, "put")
    assert np.allclose(c - p, S * np.exp(-0.02 * T) - k * np.exp(-R * T))


def test_expired_option_is_intrinsic():
    assert bs_price(110.0, K, R, Q, SIGMA, 0.0, "call") == pytest.approx(10.0)
    assert bs_price(110.0, K, R, Q, SIGMA, 0.0, "put") == pytest.approx(0.0)


def test_european_crr_converges_to_bs():
    crr = crr_price(S, K, R, Q, SIGMA, T, "call", style="european", steps=2000)
    assert crr == pytest.approx(bs_price(S, K, R, Q, SIGMA, T, "call"), abs=5e-3)


def test_american_put_at_least_european():
    assert crr_price(S, K, R, Q, SIGMA, T, "put", style="american") >= bs_price(S, K, R, Q, SIGMA, T, "put") - 1e-9


def test_greeks_signs_and_delta_relation():
    g_call = bs_greeks(S, K, R, Q, SIGMA, T, "call")
    g_put = bs_greeks(S, K, R, Q, SIGMA, T, "put")
    assert 0 < g_call["delta"] < 1 and -1 < g_put["delta"] < 0
    assert g_call["delta"] - g_put["delta"] == pytest.approx(1.0)
    h = 1e-4
    fd = (bs_price(S + h, K, R, Q, SIGMA, T, "call") - bs_price(S - h, K, R, Q, SIGMA, T, "call")) / (2 * h)
    assert g_call["delta"] == pytest.approx(fd, abs=1e-6)


def test_implied_vol_round_trip():
    sig = np.array([0.15, 0.3, 0.6])
    prices = bs_price(S, K, R, Q, sig, T, "call")
    assert np.allclose(implied_vol(prices, S, K, R, Q, T, "call"), sig, atol=1e-6)


def test_warrant_scales_by_ratio():
    ratio = 0.05
    w = warrant_price(S, K, R, Q, SIGMA, T, ratio, "call")
    assert w == pytest.approx(ratio * bs_price(S, K, R, Q, SIGMA, T, "call"))
    assert warrant_iv(w, S, K, R, Q, T, ratio, "call") == pytest.approx(SIGMA, abs=1e-6)
    assert warrant_greeks(S, K, R, Q, SIGMA, T, ratio, "call")["delta"] == pytest.approx(
        ratio * bs_greeks(S, K, R, Q, SIGMA, T, "call")["delta"])
