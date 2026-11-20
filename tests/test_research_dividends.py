"""Dividends: FinMind parsing, ex-date comparison, PV-equivalent q."""

import numpy as np
import pandas as pd
import pytest

from wtox.research import dividends


def _raw():
    return pd.DataFrame({
        "CashExDividendTradingDate": ["2025-03-18", "2025-06-12", "", "2025-06-12"],
        "CashEarningsDistribution": [4.5, 5.0, 0, 0.0], "CashStatutorySurplus": [0, 0, 0, 0.5],
        "CashDividendPaymentDate": ["2025-04-10", "2025-07-10", "", "2025-07-10"],
    })


def test_parse_sums_cash_parts_per_ex_date():
    d = dividends.parse(_raw())
    assert d["ex_date"].tolist() == [pd.Timestamp("2025-03-18"), pd.Timestamp("2025-06-12")]
    assert d["cash"].tolist() == [4.5, 5.5]
    with pytest.raises(ValueError):
        dividends.parse(pd.DataFrame({"date": ["2025-01-01"]}))


def test_compare_ex_dates_lists_both_sides():
    d = dividends.parse(_raw())
    c = dividends.compare_ex_dates(d, [pd.Timestamp("2025-03-18"), pd.Timestamp("2025-09-16")])
    assert c[["finmind", "twse_adjustment"]].values.tolist() == [[True, True], [True, False], [False, True]]


def test_effective_q_matches_dividend_pv():
    d = dividends.parse(_raw())
    day, S, r = pd.Timestamp("2025-03-18"), 1000.0, 0.015   # the 03-18 dividend is already ex on its own date
    q = dividends.effective_q(day, [S, S], [0.1, 0.5], d, r)
    assert q[0] == 0                                         # 06-12 is beyond 0.1 years
    t = (pd.Timestamp("2025-06-12") - day).days / 365
    pv = 5.5 * np.exp(-r * t)
    assert S * np.exp(-q[1] * 0.5) == pytest.approx(S - pv)  # same forward-price drop as the cash dividend
