"""Missing pre-trade quotes: reasons, shares, and the post-as-pre diagnostic."""

import numpy as np
import pandas as pd
import pytest

from wtox.research import quotes


def _panel():
    t = pd.to_datetime(["2026-09-01 09:01", "2026-09-01 09:02", "2026-09-01 09:03", "2026-09-01 09:03",
                        "2026-09-01 09:04", "2026-09-01 09:05"])
    p = pd.DataFrame({
        "datetime": t, "warrant_id": ["A", "A", "A", "A", "B", "A"], "volume": [1, 2, 3, 4, 10, 5],
        "fill_seq": [0, 0, 0, 1, 0, 0], "n_fills": [1, 1, 2, 2, 1, 1], "order_volume": [1, 2, 7, 7, 10, 5],
        "side": [1, 1, 1, 1, -1, -1], "close": [1.01, 1.01, 1.01, 1.02, 0.50, 1.00],
        "pre_bid": [np.nan, 0.0, 1.00, 1.00, np.nan, 1.00], "pre_ask": [np.nan, 1.01, 1.01, 1.01, np.nan, 1.02],
        "pre_bid_volume": [np.nan, 0, 50, 50, np.nan, 3], "pre_ask_volume": [np.nan, 100, 5, 5, np.nan, 100],
        "pre_quote_age_s": [np.nan, 60, 60, 60, np.nan, 120],
        "post_bid": [0.0, 1.00, 0.0, 1.01, 0.49, 0.99], "post_ask": [1.01, 1.01, 0.0, 1.03, 0.51, 1.02],
        "post_bid_volume": 0, "post_ask_volume": 0, "T": [20 / 365] * 6, "kind": "call",
    })
    from wtox.research.trades import quote_mid
    p["pre_mid"] = quote_mid(p["pre_bid"], p["pre_ask"])
    return p


def test_reasons_and_shares():
    c = quotes.classify(_panel())
    assert c["missing_reason"].tolist() == ["first_of_day", "one_sided", "ok", "ok", "first_of_day", "ok"]
    assert c["orders_that_day"].tolist() == [4, 4, 4, 4, 1, 4]       # A has 4 orders (the 2-fill order counts once)
    s = quotes.summary(c).set_index("missing_reason")
    assert s.loc["first_of_day", "share_n"] == pytest.approx(2 / 6)
    assert s.loc["first_of_day", "share_volume"] == pytest.approx(11 / 25)
    by = quotes.summary(c, ["liquidity"]).set_index(["liquidity", "missing_reason"])
    assert by.loc[("1", "first_of_day"), "share_n"] == 1


def test_post_as_pre_uses_the_last_fill_and_flags_surviving_levels():
    o = quotes.post_as_pre(_panel()).set_index("datetime")
    assert len(o) == 5                                                # one row per order
    walked = o.loc[pd.Timestamp("2026-09-01 09:03")]                 # 2 fills: post quote of the last one
    assert walked["post_mid"] == pytest.approx(1.02) and not walked["level_survived"] and walked["ate_level"]
    kept = o.loc[pd.Timestamp("2026-09-01 09:02")]                   # buy at 1.01, post ask still 1.01
    assert kept["level_survived"] and not kept["ate_level"]
    sell = o.loc[pd.Timestamp("2026-09-01 09:05")]                   # sell at 1.00, post bid 0.99: level gone
    assert not sell["level_survived"] and sell["ate_level"]          # 5 lots >= 3 displayed
    assert sell["mid_diff_bps"] == pytest.approx((1.005 - 1.01) / 1.01 * 1e4)
    first = o.loc[pd.Timestamp("2026-09-01 09:01")]                   # no pre quote, post ask == fill: usable
    assert first["level_survived"] and np.isnan(first["pre_mid"])


def test_post_as_pre_summary_only_uses_orders_with_both_mids():
    s = quotes.post_as_pre_summary(quotes.post_as_pre(_panel()))
    assert s["n"].sum() == 2                                          # the 09:03 and 09:05 orders
