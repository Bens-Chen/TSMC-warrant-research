"""Trade-level panel of warrant ticks aligned with the underlying stock.

One row per warrant trade during the continuous session (09:00 <= t < 13:30), with:

* side: +1 investor buy (trade at the ask, exchange flag 外盤), -1 investor sell (內盤), 0 unknown.
  Shioaji's tick_type is used first; ticks without a flag fall back to price vs the pre-trade mid.
* pre-trade quote: Shioaji's bid/ask on a tick is the quote *after* that trade, so the quote in
  force before a trade is the previous tick's bid/ask (NaN for a warrant's first trade of the day).
* underlying: last 2330 trade and post-trade bid/ask at or before the warrant trade (as-of join).
* terms valid that day (strike, ratio, kind, expiry, issuer) from the TWSE terms table.
* iv from the pre-trade warrant mid, delta from that iv, and the delta-weighted exposure in
  underlying shares: share_equiv = side * volume * 1000 * ratio * delta (1 lot = 1,000 warrants).

Build every day:  python -m wtox.research.trades --data ../data --out ../data/panel/tsmc_warrant_trades
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox import bs_greeks, warrant_iv
from wtox.data.tej import terms_as_of

OPEN, CLOSE = pd.Timedelta(hours=9), pd.Timedelta(hours=13, minutes=30)
UNITS_PER_LOT = 1000


def continuous_session(df, col="datetime"):
    t = df[col] - df[col].dt.normalize()
    return df[(t >= OPEN) & (t < CLOSE)]


def trade_side(tick_type, price, pre_mid):
    side = np.select([tick_type == 1, tick_type == 2], [1, -1], 0)
    fallback = np.sign(price - pre_mid)
    return np.where(side != 0, side, np.nan_to_num(fallback)).astype(int)


def load_warrant_ticks(day_dir):
    frames = [pd.read_parquet(p) for p in sorted(Path(day_dir).glob("*.parquet"))]
    frames = [f for f in frames if len(f)]
    if not frames:
        return pd.DataFrame()
    w = pd.concat(frames, ignore_index=True).sort_values(["warrant_id", "datetime"], kind="mergesort")
    # quote before each trade = previous tick's (post-trade) quote, within the same warrant
    g = w.groupby("warrant_id", sort=False)
    w["pre_bid"] = g["bid_price"].shift(1)
    w["pre_ask"] = g["ask_price"].shift(1)
    return continuous_session(w)


def build_day(day, data_dir, terms, r=0.015, q=0.0):
    data_dir = Path(data_dir)
    w = load_warrant_ticks(data_dir / "shioaji" / "ticks" / day)
    s_path = data_dir / "shioaji" / "underlying_ticks" / "stock" / "2330" / f"{day}.parquet"
    if w.empty or not s_path.exists():
        return pd.DataFrame()
    s = pd.read_parquet(s_path)[["datetime", "close", "bid_price", "ask_price"]]
    s = s.rename(columns={"close": "S", "bid_price": "S_bid", "ask_price": "S_ask"}).sort_values("datetime")

    w = w.sort_values("datetime", kind="mergesort")
    w = pd.merge_asof(w, s, on="datetime", direction="backward")

    cur = terms_as_of(terms, day)[["warrant_id", "kind", "strike", "ratio", "expiry_date", "issuer"]]
    w = w.merge(cur, on="warrant_id", how="inner")
    w["T"] = (w["expiry_date"] - pd.Timestamp(day)).dt.days / 365.0

    valid_quote = (w["pre_bid"] > 0) & (w["pre_ask"] > 0) & (w["pre_ask"] >= w["pre_bid"])
    w["pre_mid"] = ((w["pre_bid"] + w["pre_ask"]) / 2).where(valid_quote)
    w["pre_spread_pct"] = ((w["pre_ask"] - w["pre_bid"]) / w["pre_mid"]).where(valid_quote)
    w["side"] = trade_side(w["tick_type"].to_numpy(), w["close"].to_numpy(), w["pre_mid"].to_numpy())

    S_mid = ((w["S_bid"] + w["S_ask"]) / 2).where((w["S_bid"] > 0) & (w["S_ask"] > 0), w["S"])
    w["S_mid"] = S_mid
    ok = w["pre_mid"].notna() & (w["T"] > 0) & S_mid.notna()
    iv = np.full(len(w), np.nan)
    if ok.any():
        sub = w[ok]
        iv[ok.to_numpy()] = warrant_iv(sub["pre_mid"].to_numpy(), sub["S_mid"].to_numpy(), sub["strike"].to_numpy(),
                                       r, q, sub["T"].to_numpy(), sub["ratio"].to_numpy(), sub["kind"].to_numpy())
    w["iv"] = iv
    has_iv = ~np.isnan(iv)
    delta = np.full(len(w), np.nan)
    if has_iv.any():
        sub = w[has_iv]
        delta[has_iv] = bs_greeks(sub["S_mid"].to_numpy(), sub["strike"].to_numpy(), r, q, sub["iv"].to_numpy(),
                                  sub["T"].to_numpy(), sub["kind"].to_numpy())["delta"]
    w["delta"] = delta
    w["moneyness"] = np.log(w["S_mid"] / w["strike"])
    w["signed_volume"] = w["side"] * w["volume"]
    w["share_equiv"] = w["signed_volume"] * UNITS_PER_LOT * w["ratio"] * w["delta"]
    w["notional"] = w["close"] * w["volume"] * UNITS_PER_LOT

    cols = ["datetime", "warrant_id", "issuer", "kind", "strike", "ratio", "T", "close", "volume", "tick_type", "side",
            "pre_bid", "pre_ask", "pre_mid", "pre_spread_pct", "bid_price", "ask_price", "S", "S_mid", "moneyness",
            "iv", "delta", "signed_volume", "share_equiv", "notional"]
    return w[cols].sort_values(["datetime", "warrant_id"]).reset_index(drop=True)


def main(argv=None):
    p = argparse.ArgumentParser(description="Build the TSMC warrant trade panel, one Parquet per day")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default="../data/panel/tsmc_warrant_trades")
    p.add_argument("--rebuild", action="store_true")
    a = p.parse_args(argv)
    data, out = Path(a.data), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    terms = pd.read_parquet(data / "twse" / "terms_2330.parquet")
    days = sorted(d.name for d in (data / "shioaji" / "ticks").iterdir() if d.is_dir())
    for day in days:
        path = out / f"{day}.parquet"
        if path.exists() and not a.rebuild:
            continue
        panel = build_day(day, data, terms)
        if len(panel):
            panel.to_parquet(path, index=False)
        print(day, len(panel), "trades", f"iv ok {panel['iv'].notna().mean():.0%}" if len(panel) else "")


if __name__ == "__main__":
    main()
