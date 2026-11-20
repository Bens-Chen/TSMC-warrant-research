"""Trade-level panel of warrant ticks aligned with the underlying stock.

One row per warrant trade during the continuous session (09:00 <= t < 13:25; 13:25-13:30 is the
closing call auction and is excluded), with:

* side: +1 investor buy (trade at the ask, exchange flag 外盤), -1 investor sell (內盤), 0 unknown.
  The order's exchange flag (``order_tick_type``; fills with conflicting flags -> ``mixed_tick_type``,
  treated as unflagged) is used first; unflagged orders fall back to price vs the previous mid.
* orders: one aggressive order that walks several price levels prints several ticks with the same
  timestamp (intermediate ones carry bid/ask 0/0). ``fill_seq`` numbers the fills, ``order_volume`` /
  ``n_fills`` describe the order, ``first_fill_price`` is the price of its first fill.
* previous quote ``prev_bid`` / ``prev_ask`` (+ ``_volume``, ``prev_quote_age_s``): Shioaji's bid/ask on
  a tick is the quote *after* that trade, so the previous order's last tick gives the last quote seen
  before this order (NaN for a warrant's first order of the day). It is often stale: the issuer
  re-quotes between trades without a print.
* at-trade quote ``pre_bid`` / ``pre_ask`` / ``pre_mid`` (rule A'', CLAUDE.md §10), the quote the order
  met, which every fill of the order shares:
  1. touched side = ``first_fill_price``: an exchange 外盤 (tick_type 1) fill is at the resting ask by
     definition, 內盤 (2) at the resting bid. Rows without the flag get no at-trade quote.
  2. other side = the post-trade quote's other side on the order's last fill (the exchange shows the
     book after the order's last match), if valid and strictly on the right side of the first fill
     price (buy: 0 < post_bid < P1). An unfilled remainder of the order rests at its limit, which is
     at or through P1, so this test also rejects the order's own residual.
  3. else the previous quote's other side, if the previous quote was still in force (its touched side
     equals P1) and valid on the right side.
  4. else NaN. ``pre_quote_source`` is "post", "prev" or "". ``prev_in_force`` marks orders whose
     previous quote was still standing (only then is ``prev_*_volume`` the size the order met).
  Step 2 reads post-trade *prices* only where they were already resting before the order; post-trade
  volumes stay diagnostics (config.POST_TRADE_COLUMNS).
* underlying: last 2330 trade and post-trade bid/ask at or before the warrant trade (as-of join).
  ``S_mid_is_trade`` marks rows where the quote was invalid and the last trade price was used.
* terms valid that day (strike, ratio, kind, expiry, issuer), point-in-time, from TWSE + TEJ so
  delisted warrants are kept (see wtox.research.terms).
* iv from the pre-trade warrant mid, delta from that iv, and the delta-weighted exposure in
  underlying shares: share_equiv = side * volume * 1000 * ratio * delta (1 lot = 1,000 warrants).
* effective leverage G = |delta| * ratio * S_mid / pre_mid (known at trade time, a feature).
* trade_id: row number within the day, the join key for labels (wtox.research.markout).
* post_bid / post_ask (+ _volume): the quote right *after* this trade. It already reflects this trade's impact,
  so it is kept for diagnostics only and must never be a model feature (config.POST_TRADE_COLUMNS).

Everything here is known at trade time. Future information belongs in labels only (CLAUDE.md §4).

Build every day:  python -m wtox.research.trades --data ../data --out ../data/panel/tsmc_warrant_trades
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox import bs_greeks, warrant_iv
from wtox.research import config
from wtox.research import terms as terms_mod

OPEN, CLOSE = config.SESSION_OPEN, config.CONTINUOUS_END
SCHEMA_MARKER = "pre_quote_source"      # panels built before rule A'' lack it and must be rebuilt


def check_schema(panel_dir):
    """Raise if any in-sample panel file predates rule A'' (run the panel step with --rebuild)."""
    import pyarrow.parquet as pq
    old = [p.name for p in Path(panel_dir).glob("*.parquet")
           if config.in_sample(p.stem) and SCHEMA_MARKER not in pq.read_schema(p).names]
    if old:
        raise RuntimeError(f"{len(old)} panel files predate rule A'' (e.g. {sorted(old)[0]}): rebuild with --rebuild")
UNITS_PER_LOT = config.UNITS_PER_LOT


def continuous_session(df, col="datetime"):
    t = df[col] - df[col].dt.normalize()
    return df[(t >= OPEN) & (t < CLOSE)]


def quote_mid(bid, ask):
    """Mid of a valid two-sided quote, else NaN. Shared with markout.py so S_mid(t) and S_mid(t+h) match."""
    ok = (bid > 0) & (ask > 0) & (ask >= bid)
    return ((bid + ask) / 2).where(ok)


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
    # quote before each trade = previous tick's (post-trade) quote, within the same warrant;
    # all fills sharing a timestamp take the quote before the first of them
    g = w.groupby("warrant_id", sort=False)
    prev = pd.DataFrame({"prev_bid": g["bid_price"].shift(1), "prev_ask": g["ask_price"].shift(1),
                         "prev_bid_volume": g["bid_volume"].shift(1), "prev_ask_volume": g["ask_volume"].shift(1),
                         "prev_time": g["datetime"].shift(1)})
    order = w.groupby(["warrant_id", "datetime"], sort=False)
    w["fill_seq"] = order.cumcount()
    first = w["fill_seq"] == 0
    order_no = first.cumsum()          # rows of one order are contiguous after the sort above
    for c in prev:                     # broadcast the first fill's value; a NaN there stays NaN
        w[c] = prev[c].where(first).groupby(order_no).ffill()
    w["prev_quote_age_s"] = (w["datetime"] - w["prev_time"]).dt.total_seconds()
    w["order_volume"] = order["volume"].transform("sum")
    w["n_fills"] = order["volume"].transform("size")
    w["first_fill_price"] = order["close"].transform("first")
    # one exchange flag per order; fills that disagree (or are all unflagged) leave the order unflagged
    flags = w["tick_type"].where(w["tick_type"].isin([1, 2]))
    w["mixed_tick_type"] = flags.groupby([w["warrant_id"], w["datetime"]]).transform("nunique") > 1
    w["order_tick_type"] = flags.groupby([w["warrant_id"], w["datetime"]]).transform("first").fillna(0).astype(int)
    w.loc[w["mixed_tick_type"], "order_tick_type"] = 0
    w["order_post_bid"] = order["bid_price"].transform("last")      # book shown after the order's last match
    w["order_post_ask"] = order["ask_price"].transform("last")
    return continuous_session(w)


def at_trade_quote(tick_type, p1, post_bid, post_ask, prev_bid, prev_ask):
    """Rule A'' (module docstring): (bid, ask, source) of the quote an order met. Arrays in, arrays out."""
    tick_type, p1 = np.asarray(tick_type), np.asarray(p1, float)
    post_bid, post_ask, prev_bid, prev_ask = (np.asarray(x, float) for x in (post_bid, post_ask, prev_bid, prev_ask))
    buy, sell = tick_type == 1, tick_type == 2

    def inside(other):     # valid and strictly on the untouched side of P1 (NaN compares False)
        with np.errstate(invalid="ignore"):
            return np.where(buy, (other > 0) & (other < p1), sell & (other > 0) & (other > p1))

    post_other = np.where(buy, post_bid, post_ask)
    prev_other = np.where(buy, prev_bid, prev_ask)
    prev_touched = np.where(buy, prev_ask, prev_bid)
    use_post = inside(post_other)
    use_prev = ~use_post & np.isclose(prev_touched, p1) & inside(prev_other)
    other = np.where(use_post, post_other, np.where(use_prev, prev_other, np.nan))
    ok = use_post | use_prev
    bid = np.where(ok, np.where(buy, other, p1), np.nan)
    ask = np.where(ok, np.where(buy, p1, other), np.nan)
    return bid, ask, np.where(use_post, "post", np.where(use_prev, "prev", ""))


def build_day(day, data_dir, terms, div_dates=(), r=config.RISK_FREE, q=config.DIVIDEND_YIELD):
    data_dir = Path(data_dir)
    w = load_warrant_ticks(data_dir / "shioaji" / "ticks" / day)
    s_path = data_dir / "shioaji" / "underlying_ticks" / "stock" / config.UNDERLYING / f"{day}.parquet"
    if w.empty or not s_path.exists():
        return pd.DataFrame()
    s = pd.read_parquet(s_path)[["datetime", "close", "bid_price", "ask_price"]]
    s = s.rename(columns={"close": "S", "bid_price": "S_bid", "ask_price": "S_ask"}).sort_values("datetime", kind="mergesort")

    w = w.sort_values("datetime", kind="mergesort")
    w = pd.merge_asof(w, s, on="datetime", direction="backward")

    cur = terms_mod.terms_on(terms, day, div_dates)[
        ["warrant_id", "tej_id", "kind", "strike", "ratio", "expiry_date", "issuer", "terms_source", "terms_stale",
         "expiry_conflict"]]
    no_terms = sorted(set(w["warrant_id"]) - set(cur["warrant_id"]))
    w = w.merge(cur, on="warrant_id", how="inner")
    w["T"] = (w["expiry_date"] - pd.Timestamp(day)).dt.days / config.DAYS_PER_YEAR

    bid, ask, src = at_trade_quote(w["order_tick_type"], w["first_fill_price"], w["order_post_bid"],
                                   w["order_post_ask"], w["prev_bid"], w["prev_ask"])
    w["pre_bid"], w["pre_ask"], w["pre_quote_source"] = bid, ask, src
    # the previous quote was still in force when the order arrived (its touched side == P1); only then
    # is prev_*_volume the size the order met (§6 counterparty sensitivity)
    w["prev_in_force"] = np.isclose(np.where(w["order_tick_type"] == 1, w["prev_ask"], w["prev_bid"]),
                                    w["first_fill_price"]) & w["order_tick_type"].isin([1, 2])
    w["pre_mid"] = quote_mid(w["pre_bid"], w["pre_ask"])
    w["pre_spread_pct"] = (w["pre_ask"] - w["pre_bid"]) / w["pre_mid"]
    # unflagged ticks fall back to price vs the previous mid; they never get an at-trade quote
    w["side"] = trade_side(w["order_tick_type"].to_numpy(), w["close"].to_numpy(),
                           quote_mid(w["prev_bid"], w["prev_ask"]).to_numpy())

    S_mid = quote_mid(w["S_bid"], w["S_ask"])
    w["S_mid_is_trade"] = S_mid.isna() & w["S"].notna()
    S_mid = S_mid.fillna(w["S"])
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
    w["post_bid"], w["post_ask"] = w["bid_price"], w["ask_price"]
    w["post_bid_volume"], w["post_ask_volume"] = w["bid_volume"], w["ask_volume"]
    w["leverage"] = w["delta"].abs() * w["ratio"] * w["S_mid"] / w["pre_mid"]

    cols = ["datetime", "warrant_id", "tej_id", "issuer", "kind", "strike", "ratio", "T", "close", "volume",
            "fill_seq", "n_fills", "order_volume", "first_fill_price", "tick_type", "order_tick_type", "mixed_tick_type", "side",
            "pre_bid", "pre_ask", "pre_mid", "pre_spread_pct", "pre_quote_source",
            "prev_bid", "prev_ask", "prev_bid_volume", "prev_ask_volume", "prev_quote_age_s", "prev_in_force",
            "post_bid", "post_ask", "post_bid_volume", "post_ask_volume",
            "S", "S_mid", "S_mid_is_trade", "moneyness", "iv", "delta", "leverage", "signed_volume", "share_equiv",
            "notional", "terms_source", "terms_stale", "expiry_conflict"]
    w = w[cols].sort_values(["datetime", "warrant_id"], kind="mergesort").reset_index(drop=True)
    w.insert(0, "trade_id", np.arange(len(w), dtype="int64"))
    w.attrs["no_terms"] = no_terms
    return w


def main(argv=None):
    p = argparse.ArgumentParser(description="Build the TSMC warrant trade panel, one Parquet per day")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default="../data/panel/tsmc_warrant_trades")
    p.add_argument("--rebuild", action="store_true")
    a = p.parse_args(argv)
    data, out = Path(a.data), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    terms, div_dates = terms_mod.load(data, config.UNDERLYING)
    days = sorted(d.name for d in (data / "shioaji" / "ticks").iterdir() if d.is_dir() and config.in_sample(d.name))
    for day in days:
        path = out / f"{day}.parquet"
        if path.exists() and not a.rebuild:
            continue
        panel = build_day(day, data, terms, div_dates)
        if len(panel):
            panel.to_parquet(path, index=False)
        print(day, len(panel), "trades", f"iv ok {panel['iv'].notna().mean():.0%}" if len(panel) else "",
              f"no terms: {len(panel.attrs.get('no_terms', []))} warrants" if len(panel) else "")


if __name__ == "__main__":
    main()
