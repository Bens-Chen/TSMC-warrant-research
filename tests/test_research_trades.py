"""Trade panel: side labelling, pre-trade quotes, underlying as-of join, delta exposure."""

import numpy as np
import pandas as pd
import pytest

from wtox import bs_price
from wtox.research.trades import build_day, trade_side


def test_trade_side_uses_flag_then_price_vs_mid():
    side = trade_side(np.array([1, 2, 0, 0, 0]), np.array([1.0, 1.0, 1.1, 0.9, 1.0]), np.array([1.0, 1.0, 1.0, 1.0, np.nan]))
    assert side.tolist() == [1, -1, 1, -1, 0]


def test_build_day_aligns_quotes_and_underlying(tmp_path):
    day = "2026-11-12"
    S, K, ratio, T = 2000.0, 2100.0, 0.01, 100 / 365
    fair = ratio * bs_price(S, K, 0.015, 0, 0.45, T, "call")
    wdir = tmp_path / "shioaji" / "ticks" / day
    wdir.mkdir(parents=True)
    ts = pd.to_datetime([f"{day} 08:59:59", f"{day} 09:30:00", f"{day} 09:31:00", f"{day} 13:31:00"])
    pd.DataFrame({
        "warrant_id": "030156", "datetime": ts, "close": [fair] * 4, "volume": [1, 10, 4, 9],
        "bid_price": [fair - 0.01, fair - 0.01, 0.10, fair - 0.01], "bid_volume": 5,
        "ask_price": [fair + 0.01, fair + 0.01, fair + 0.01, fair + 0.01], "ask_volume": 5,
        "tick_type": [0, 1, 2, 1],
    }).to_parquet(wdir / "030156.parquet")
    sdir = tmp_path / "shioaji" / "underlying_ticks" / "stock" / "2330"
    sdir.mkdir(parents=True)
    pd.DataFrame({"datetime": pd.to_datetime([f"{day} 09:00:01", f"{day} 09:30:30"]), "close": [S, S + 50],
                  "bid_price": [S - 5, S + 45], "ask_price": [S + 5, S + 55]}).to_parquet(sdir / f"{day}.parquet")
    terms = pd.DataFrame({"warrant_id": ["030156"], "event_date": [pd.NaT], "event_seq": [0], "kind": ["call"],
                          "strike": [K], "ratio": [ratio], "expiry_date": [pd.Timestamp(day) + pd.Timedelta(days=100)],
                          "issuer": ["永豐"]})

    panel = build_day(day, tmp_path, terms)
    assert len(panel) == 2  # 08:59:59 and 13:31 are outside the continuous session
    first, second = panel.iloc[0], panel.iloc[1]
    assert first["side"] == 1 and second["side"] == -1
    # pre-trade quote of the 09:31 trade is the 09:30 tick's post-trade quote, not its own (bid 0.10)
    assert second["pre_bid"] == pytest.approx(fair - 0.01)
    assert first["S_mid"] == S and second["S_mid"] == S + 50  # as-of: 09:31 sees the 09:30:30 quote
    assert first["iv"] == pytest.approx(0.45, abs=0.02)
    assert first["share_equiv"] == pytest.approx(10 * 1000 * ratio * first["delta"])
    assert second["share_equiv"] < 0
