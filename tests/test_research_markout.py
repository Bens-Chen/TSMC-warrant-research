"""Future-mid labels: horizons, session cap, warrant matching, no mixing of warrants."""

import numpy as np
import pandas as pd
import pytest

from wtox.research.markout import build_labels

DAY = "2026-09-01"


def T(s):
    return pd.Timestamp(f"{DAY} {s}")


def _stock():
    ts = ["09:00:00.5", "09:00:01.2", "09:00:04", "09:01:30", "13:24:59", "13:30:00"]
    bid = [1000, 1005, 1010, 0, 1020, 1100]          # 09:01:30 has an invalid quote -> trade price
    return pd.DataFrame({"datetime": [T(x) for x in ts], "close": [1000, 1005, 1010, 1012, 1020, 1100],
                         "bid_price": bid, "ask_price": [b + 5 if b else 0 for b in bid]})


def _warrants():
    return pd.DataFrame({
        "warrant_id": ["A", "B", "A", "A"],
        "datetime": [T("09:00:01"), T("09:00:02"), T("09:00:03"), T("09:00:09")],
        "bid_price": [1.00, 5.00, 1.02, 0.0], "ask_price": [1.01, 5.10, 1.03, 1.05],
    })


def _panel():
    return pd.DataFrame({"trade_id": [0, 1, 2], "warrant_id": ["A", "B", "A"],
                         "datetime": [T("09:00:01"), T("09:00:02"), T("13:24:50")]})


H = {"1s": pd.Timedelta(seconds=1), "5s": pd.Timedelta(seconds=5), "2m": pd.Timedelta(minutes=2), "close": None}


def test_underlying_mid_at_each_horizon():
    lab = build_labels(_panel(), _stock(), _warrants(), H).set_index("trade_id")
    assert lab.loc[0, "S_mid_1s"] == 1007.5            # 09:00:02 sees the 09:00:01.2 tick
    assert lab.loc[0, "S_mid_5s"] == 1012.5            # 09:00:06 sees 09:00:04
    assert lab.loc[0, "S_mid_2m"] == 1012              # 09:02:01 sees 09:01:30, invalid quote -> close
    assert lab.loc[0, "S_mid_close"] == 1022.5         # last continuous tick; 13:30 auction ignored


def test_horizons_past_the_continuous_session_are_capped():
    lab = build_labels(_panel(), _stock(), _warrants(), H).set_index("trade_id")
    assert lab.loc[2, "S_mid_2m"] == lab.loc[2, "S_mid_close"] == 1022.5
    assert lab.loc[2, "trunc_2m"] and not lab.loc[0, "trunc_2m"]
    assert "trunc_close" not in lab


def test_warrant_mid_uses_only_the_same_warrant():
    lab = build_labels(_panel(), _stock(), _warrants(), H).set_index("trade_id")
    assert lab.loc[0, "W_mid_1s"] == pytest.approx(1.005)        # A at 09:00:01, not B at 09:00:02
    assert lab.loc[0, "W_age_1s"] == pytest.approx(1.0)
    assert lab.loc[0, "W_mid_5s"] == pytest.approx(1.025)        # A at 09:00:03
    assert np.isnan(lab.loc[0, "W_mid_2m"])                      # A at 09:00:09 has bid 0 -> invalid
    assert lab.loc[1, "W_mid_5s"] == pytest.approx(5.05)


def test_output_rows_follow_the_panel_order():
    p = _panel().iloc[[2, 0, 1]].reset_index(drop=True)
    lab = build_labels(p, _stock(), _warrants(), H)
    assert lab["trade_id"].tolist() == [2, 0, 1]
    assert lab.loc[1, "S_mid_1s"] == 1007.5


def test_trade_after_the_last_stock_tick_never_reads_its_pre_trade_quote():
    stock = _stock()[_stock()["datetime"] < T("13:00:00")]          # last stock tick 09:01:30
    warrants = pd.concat([_warrants(), pd.DataFrame({"warrant_id": ["A"], "datetime": [T("09:05:00")],
                                                     "bid_price": [2.0], "ask_price": [2.02]})])
    panel = pd.DataFrame({"trade_id": [0], "warrant_id": ["A"], "datetime": [T("09:05:00")]})
    lab = build_labels(panel, stock, warrants, H).iloc[0]
    assert lab["W_mid_1s"] == pytest.approx(2.01)                    # its own post-trade quote, not 09:00:09
    assert lab["trunc_1s"]


def test_stock_quote_fallback_is_flagged():
    lab = build_labels(_panel(), _stock(), _warrants(), H).set_index("trade_id")
    assert lab.loc[0, "S_is_trade_2m"] and not lab.loc[0, "S_is_trade_5s"]


def test_label_file_older_than_its_panel_is_rebuilt(tmp_path, monkeypatch):
    import os
    from wtox.research import markout
    day = "2026-09-01"
    (tmp_path / "panel").mkdir()
    (tmp_path / "labels").mkdir()
    ppath, lpath = tmp_path / "panel" / f"{day}.parquet", tmp_path / "labels" / f"{day}.parquet"
    _panel().to_parquet(ppath)
    pd.DataFrame({"stale": [1]}).to_parquet(lpath)
    os.utime(lpath, (1, 1))                                           # label older than panel
    calls = []
    monkeypatch.setattr(markout, "build_day", lambda d, *a: calls.append(d) or _panel())
    markout.main(["--data", str(tmp_path), "--panel", str(tmp_path / "panel"), "--out", str(tmp_path / "labels")])
    assert calls == [day]
    calls.clear()
    markout.main(["--data", str(tmp_path), "--panel", str(tmp_path / "panel"), "--out", str(tmp_path / "labels")])
    assert calls == []                                               # now fresh -> skipped
