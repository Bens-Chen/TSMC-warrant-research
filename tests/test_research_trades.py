"""Trade panel: side labelling, pre-trade quotes, underlying as-of join, delta exposure."""

import numpy as np
import pandas as pd
import pytest

from wtox import bs_price
from wtox.research import config
from wtox.research.trades import at_trade_quote, build_day, load_warrant_ticks, trade_side


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
                          "issuer": ["永豐"], "tej_id": ["030156"], "listing_date": [pd.Timestamp(day) - pd.Timedelta(days=30)],
                          "terms_source": ["twse"], "expiry_conflict": [False]})

    panel = build_day(day, tmp_path, terms)
    assert len(panel) == 2  # 08:59:59 and 13:31 are outside the continuous session
    first, second = panel.iloc[0], panel.iloc[1]
    assert first["side"] == 1 and second["side"] == -1
    # 09:31 sell at `fair`: the previous quote (bid fair-0.01) was stale, so rule A'' takes the touched
    # bid from the fill and the ask from the post-trade book
    assert second["prev_bid"] == pytest.approx(fair - 0.01)
    assert second["pre_bid"] == pytest.approx(fair) and second["pre_ask"] == pytest.approx(fair + 0.01)
    assert second["pre_quote_source"] == "post"
    assert first["pre_bid"] == pytest.approx(fair - 0.01) and first["pre_ask"] == pytest.approx(fair)
    assert first["S_mid"] == S and second["S_mid"] == S + 50  # as-of: 09:31 sees the 09:30:30 quote
    assert first["iv"] == pytest.approx(0.45, abs=0.02)
    assert first["share_equiv"] == pytest.approx(10 * 1000 * ratio * first["delta"])
    assert second["share_equiv"] < 0
    assert panel["trade_id"].tolist() == [0, 1]
    assert first["leverage"] == pytest.approx(abs(first["delta"]) * ratio * S / first["pre_mid"])
    assert not first["terms_stale"] and first["terms_source"] == "twse"
    # the post-trade quote is renamed so it cannot be mistaken for a pre-trade feature
    assert second["post_bid"] == pytest.approx(0.10)
    assert "bid_price" not in panel and "ask_price" not in panel


def test_fills_of_one_order_share_the_quote_before_the_first_fill(tmp_path):
    # one order walks two levels at 09:10:00.5; Shioaji writes 0/0 on the intermediate fill
    day_dir = tmp_path / "d"
    day_dir.mkdir()
    ts = pd.to_datetime(["2026-03-10 09:05:00.000", "2026-03-10 09:10:00.500", "2026-03-10 09:10:00.500",
                         "2026-03-10 09:20:00.000"])
    pd.DataFrame({"warrant_id": "056552", "datetime": ts, "close": [0.82, 0.85, 0.86, 0.84],
                  "volume": [3, 12, 52, 1], "bid_price": [0.80, 0.0, 0.84, 0.83],
                  "ask_price": [0.85, 0.0, 0.87, 0.85], "tick_type": [1, 1, 1, 2],
                  "bid_volume": [50, 0, 49, 48], "ask_volume": [80, 0, 70, 69]}).to_parquet(day_dir / "w.parquet")
    w = load_warrant_ticks(day_dir).reset_index(drop=True)
    assert w["prev_bid"].tolist()[1:3] == [0.80, 0.80] and w["prev_ask"].tolist()[1:3] == [0.85, 0.85]
    assert w["first_fill_price"].tolist()[1:3] == [0.85, 0.85]
    assert w["order_post_bid"].tolist()[1:3] == [0.84, 0.84]           # book after the order's last match
    assert w["fill_seq"].tolist() == [0, 0, 1, 0]
    assert w["order_volume"].tolist()[1:3] == [64, 64] and w["n_fills"].tolist()[1:3] == [2, 2]
    assert w["prev_quote_age_s"].tolist()[1:3] == [300.5, 300.5]
    assert w["prev_ask_volume"].tolist()[1:3] == [80, 80]    # displayed size before the first fill
    assert w.loc[3, "prev_bid"] == 0.84                      # next order sees the last fill's quote
    assert np.isnan(w.loc[0, "prev_bid"])                    # first trade of the day


def test_first_order_of_the_day_does_not_borrow_its_own_fill_quote(tmp_path):
    day_dir = tmp_path / "d"
    day_dir.mkdir()
    ts = pd.to_datetime(["2026-03-10 09:10:00", "2026-03-10 09:10:00"])
    pd.DataFrame({"warrant_id": "A", "datetime": ts, "close": [1.0, 1.01], "volume": [1, 1],
                  "bid_price": [0.99, 1.0], "ask_price": [1.01, 1.02], "tick_type": [1, 1],
                  "bid_volume": 5, "ask_volume": 5}).to_parquet(day_dir / "w.parquet")
    w = load_warrant_ticks(day_dir)
    assert w["prev_bid"].isna().all()


def test_sample_window_excludes_days_outside_and_listed_exclusions():
    assert config.in_sample("2025-01-02") and config.in_sample("2026-11-18")
    assert not config.in_sample("2026-11-19") and not config.in_sample("2024-12-31")
    assert not config.in_sample("2026-01-09")


def test_at_trade_quote_rule():
    nan = np.nan
    # rows: buy post ok | buy residual rests at P1, prev still valid | buy residual, prev stale |
    #       sell post ok | sell, post ask invalid, prev valid | unflagged | buy, first order of the day
    tt = np.array([1, 1, 1, 2, 2, 0, 1])
    p1 = np.array([1.00, 1.00, 1.00, 0.50, 0.50, 1.00, 1.00])
    post_bid = np.array([0.99, 1.00, 1.01, 0.49, 0.48, 0.99, 0.0])
    post_ask = np.array([1.00, 1.02, 1.02, 0.51, 0.0, 1.00, 1.01])
    prev_bid = np.array([0.98, 0.98, 0.98, nan, 0.50, 0.99, nan])
    prev_ask = np.array([1.00, 1.00, 1.01, nan, 0.52, 1.00, nan])
    bid, ask, src = at_trade_quote(tt, p1, post_bid, post_ask, prev_bid, prev_ask)
    assert src.tolist() == ["post", "prev", "", "post", "prev", "", ""]
    assert bid[:2].tolist() == [0.99, 0.98] and ask[:2].tolist() == [1.00, 1.00]
    assert bid[3] == 0.50 and ask[3] == 0.51 and bid[4] == 0.50 and ask[4] == 0.52
    assert np.isnan(bid[[2, 5, 6]]).all() and np.isnan(ask[[2, 5, 6]]).all()


def test_sweep_fills_share_the_quote_met_by_the_first_fill(tmp_path):
    """Sweep buy 1.00 -> 1.01; the post-trade ask 1.01 must not become the at-trade ask."""
    day, S, K, ratio = "2026-03-10", 2000.0, 2100.0, 0.01
    wdir = tmp_path / "shioaji" / "ticks" / day
    wdir.mkdir(parents=True)
    ts = pd.to_datetime([f"{day} 09:05:00", f"{day} 09:10:00", f"{day} 09:10:00"])
    pd.DataFrame({"warrant_id": "A", "datetime": ts, "close": [0.99, 1.00, 1.01], "volume": [1, 10, 20],
                  "bid_price": [0.98, 0.0, 0.99], "ask_price": [1.00, 0.0, 1.01], "tick_type": [2, 1, 1],
                  "bid_volume": 5, "ask_volume": 5}).to_parquet(wdir / "A.parquet")
    sdir = tmp_path / "shioaji" / "underlying_ticks" / "stock" / "2330"
    sdir.mkdir(parents=True)
    pd.DataFrame({"datetime": pd.to_datetime([f"{day} 09:00:01"]), "close": [S], "bid_price": [S - 5],
                  "ask_price": [S + 5]}).to_parquet(sdir / f"{day}.parquet")
    terms = pd.DataFrame({"warrant_id": ["A"], "event_date": [pd.NaT], "event_seq": [0], "kind": ["call"],
                          "strike": [K], "ratio": [ratio], "expiry_date": [pd.Timestamp(day) + pd.Timedelta(days=100)],
                          "issuer": ["x"], "tej_id": ["A"], "listing_date": [pd.Timestamp(day) - pd.Timedelta(days=30)],
                          "terms_source": ["twse"], "expiry_conflict": [False]})
    p = build_day(day, tmp_path, terms)
    sweep = p[p["n_fills"] == 2]
    assert sweep["pre_ask"].tolist() == [1.00, 1.00] and sweep["pre_bid"].tolist() == [0.99, 0.99]
    paid = sweep["close"] - sweep["pre_mid"]
    assert paid.iloc[1] > paid.iloc[0] == pytest.approx(0.005)        # slippage shows on the second level


def test_spot_change_before_the_trade_looks_back_only(tmp_path):
    day, S, K, ratio = "2026-03-10", 2000.0, 2100.0, 0.01
    wdir = tmp_path / "shioaji" / "ticks" / day
    wdir.mkdir(parents=True)
    pd.DataFrame({"warrant_id": "A", "datetime": pd.to_datetime([f"{day} 09:10:00", f"{day} 09:10:10"]),
                  "close": [1.00, 1.00], "volume": [1, 1], "bid_price": [0.99, 0.99], "ask_price": [1.00, 1.00],
                  "tick_type": [1, 1], "bid_volume": 5, "ask_volume": 5}).to_parquet(wdir / "A.parquet")
    sdir = tmp_path / "shioaji" / "underlying_ticks" / "stock" / "2330"
    sdir.mkdir(parents=True)
    st = pd.to_datetime([f"{day} 09:00:01.000", f"{day} 09:10:09.500", f"{day} 09:10:10.500"])
    pd.DataFrame({"datetime": st, "close": [S, S + 5, S + 10], "bid_price": [S - 5, S, S + 5],
                  "ask_price": [S + 5, S + 10, S + 15]}).to_parquet(sdir / f"{day}.parquet")
    terms = pd.DataFrame({"warrant_id": ["A"], "event_date": [pd.NaT], "event_seq": [0], "kind": ["call"],
                          "strike": [K], "ratio": [ratio], "expiry_date": [pd.Timestamp(day) + pd.Timedelta(days=100)],
                          "issuer": ["x"], "tej_id": ["A"], "listing_date": [pd.Timestamp(day) - pd.Timedelta(days=30)],
                          "terms_source": ["twse"], "expiry_conflict": [False]})
    p = build_day(day, tmp_path, terms)
    assert p["S_chg_1s"].tolist() == [0.0, 5.0]          # 09:10:10 sees the 09:10:09.5 move, not the later tick
    assert p["S_chg_5s"].tolist() == [0.0, 5.0]
    assert p["S_spread_bps"].iloc[1] == pytest.approx(10 / (S + 5) * 1e4)


def test_past_return_and_spot_quote_age(tmp_path):
    day, S, K, ratio = "2026-03-10", 2000.0, 2100.0, 0.01
    wdir = tmp_path / "shioaji" / "ticks" / day
    wdir.mkdir(parents=True)
    pd.DataFrame({"warrant_id": "A", "datetime": pd.to_datetime([f"{day} 09:10:00.000"]), "close": [1.00], "volume": [1],
                  "bid_price": [0.99], "ask_price": [1.00], "tick_type": [1], "bid_volume": 5,
                  "ask_volume": 5}).to_parquet(wdir / "A.parquet")
    sdir = tmp_path / "shioaji" / "underlying_ticks" / "stock" / "2330"
    sdir.mkdir(parents=True)
    st = pd.to_datetime([f"{day} 09:04:00.000", f"{day} 09:08:30.000", f"{day} 09:09:59.750", f"{day} 09:10:00.500"])
    pd.DataFrame({"datetime": st, "close": [S, S, S + 10, S + 50], "bid_price": [S - 5, S + 5, S + 5, S + 45],
                  "ask_price": [S + 5, S + 15, S + 15, S + 55]}).to_parquet(sdir / f"{day}.parquet")
    terms = pd.DataFrame({"warrant_id": ["A"], "event_date": [pd.NaT], "event_seq": [0], "kind": ["call"],
                          "strike": [K], "ratio": [ratio], "expiry_date": [pd.Timestamp(day) + pd.Timedelta(days=100)],
                          "issuer": ["x"], "tej_id": ["A"], "listing_date": [pd.Timestamp(day) - pd.Timedelta(days=30)],
                          "terms_source": ["twse"], "expiry_conflict": [False]})
    r = build_day(day, tmp_path, terms).iloc[0]
    assert r["S_age_s"] == pytest.approx(0.25)
    assert r["S_ret_1m"] == pytest.approx((S + 10) / (S + 10) - 1)       # 09:09:00 sees the 09:08:30 quote, mid S+10
    assert r["S_ret_5m"] == pytest.approx((S + 10) / S - 1)              # 09:05:00 sees the 09:04 quote, mid S
