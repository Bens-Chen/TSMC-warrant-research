"""Missing pre-trade quotes (CLAUDE.md §2 已知缺口「成交前報價缺失」, stage 2).

A trade has no ``pre_mid`` when it is the warrant's first trade of the day or the previous tick's
quote was not two-sided. Dropping those trades would select on liquidity, so this module

1. ``classify``: labels each trade's reason (ok / first_of_day / one_sided / empty / crossed);
2. ``summary``: counts and volume shares by reason within groups (liquidity, DTE, side, ...);
3. ``post_as_pre``: tests whether the quote right after an order can stand in for the quote before
   it. Issuers post large size, so a retail order usually leaves the touched level in place
   (``level_survived``: for a buy the post-trade ask still equals the fill price, for a sell the
   post-trade bid). On trades that HAVE both quotes, compare post vs pre mid, split by
   level_survived and by whether the order was at least the displayed size (``ate_level``). The
   same level_survived flag is observable on trades WITHOUT a pre quote, which is what makes a
   rule usable there.

Uses the order's last fill for the post quote (intermediate fills of a multi-level order carry 0/0).
post_* columns are diagnostics only and must not become features (config.POST_TRADE_COLUMNS).
The substitution rule itself is decided after these numbers and written into CLAUDE.md §10.

    python -m wtox.research.quotes --data ../data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox.research import config
from wtox.research.coverage import dte_bucket
from wtox.research.trades import quote_mid

REASONS = ("ok", "first_of_day", "one_sided", "empty", "crossed")
LIQUIDITY_EDGES = (0, 1, 5, 20, np.inf)
LIQUIDITY_LABELS = ("1", "2–5", "6–20", ">20")


def classify(panel):
    """Panel plus ``missing_reason``, ``first_order``, ``trades_that_day`` and grouping columns."""
    p = panel.copy()
    bid, ask = p["pre_bid"].fillna(0), p["pre_ask"].fillna(0)
    no_prev = p["pre_quote_age_s"].isna()
    reason = np.select(
        [p["pre_mid"].notna(), no_prev, (bid > 0) ^ (ask > 0), (bid <= 0) & (ask <= 0)],
        ["ok", "first_of_day", "one_sided", "empty"], "crossed")
    p["missing_reason"] = pd.Categorical(reason, categories=REASONS)
    orders = p[p["fill_seq"] == 0].groupby("warrant_id").size()
    p["orders_that_day"] = p["warrant_id"].map(orders).fillna(0).astype("int64")
    p["liquidity"] = pd.cut(p["orders_that_day"], list(LIQUIDITY_EDGES), labels=list(LIQUIDITY_LABELS))
    p["dte_bucket"] = dte_bucket(p["T"] * config.DAYS_PER_YEAR)
    return p


def summary(classified, by=()):
    """Share of trades and of volume per missing_reason, within each `by` group."""
    by = list(by)
    g = classified.groupby(by + ["missing_reason"], observed=False)
    out = pd.DataFrame({"n": g.size(), "volume": g["volume"].sum()}).reset_index()
    tot = out.groupby(by)[["n", "volume"]].transform("sum") if by else out[["n", "volume"]].sum()
    out["share_n"] = out["n"] / tot["n"]
    out["share_volume"] = out["volume"] / tot["volume"]
    return out


def post_as_pre(panel):
    """One row per order (its last fill): pre and post mids, level_survived, ate_level, diff in bps."""
    last = panel[panel["fill_seq"] == panel["n_fills"] - 1].copy()
    last["post_mid"] = quote_mid(last["post_bid"], last["post_ask"])
    buy, sell = last["side"] == 1, last["side"] == -1
    last["level_survived"] = (buy & np.isclose(last["post_ask"], last["close"])) | \
                             (sell & np.isclose(last["post_bid"], last["close"]))
    depth = np.where(buy, last["pre_ask_volume"], np.where(sell, last["pre_bid_volume"], np.nan))
    last["ate_level"] = pd.Series(last["order_volume"].to_numpy() >= depth, index=last.index).where(~np.isnan(depth))
    last["mid_diff_bps"] = (last["post_mid"] - last["pre_mid"]) / last["pre_mid"] * 1e4
    return last[["datetime", "warrant_id", "side", "close", "order_volume", "pre_mid", "post_mid",
                 "level_survived", "ate_level", "mid_diff_bps"]].reset_index(drop=True)


def post_as_pre_summary(orders):
    """On orders with both mids: how often post == pre, by level_survived x ate_level."""
    both = orders[orders["pre_mid"].notna() & orders["post_mid"].notna() & (orders["side"] != 0)]
    g = both.groupby(["level_survived", both["ate_level"].astype("boolean")], dropna=False)
    return pd.DataFrame({
        "n": g.size(),
        "share_equal": g["mid_diff_bps"].agg(lambda s: float(np.mean(np.abs(s) < 1e-6))),
        "median_abs_bps": g["mid_diff_bps"].agg(lambda s: float(np.median(np.abs(s)))),
        "p95_abs_bps": g["mid_diff_bps"].agg(lambda s: float(np.quantile(np.abs(s), 0.95))),
    }).reset_index()


def run(data_dir, out_dir, panel_dir=None):
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    panel_dir = Path(panel_dir or data_dir / "panel" / "tsmc_warrant_trades")
    cls, orders = [], []
    for path in sorted(panel_dir.glob("*.parquet")):
        if not config.in_sample(path.stem):
            continue
        p = pd.read_parquet(path)
        c = classify(p)
        cls.append(c[["datetime", "warrant_id", "volume", "side", "missing_reason", "liquidity", "dte_bucket",
                      "kind"]].assign(day=path.stem))
        o = post_as_pre(p).merge(c.loc[c["fill_seq"] == c["n_fills"] - 1, ["datetime", "warrant_id", "missing_reason"]]
                                 .drop_duplicates(["datetime", "warrant_id"]), on=["datetime", "warrant_id"], how="left")
        orders.append(o.assign(day=path.stem))
    out_dir.mkdir(parents=True, exist_ok=True)
    cls = pd.concat(cls, ignore_index=True)
    orders = pd.concat(orders, ignore_index=True)
    cls["month"] = cls["datetime"].dt.to_period("M").astype(str)
    tables = {by: summary(cls, by) for by in [(), ("month",), ("liquidity",), ("dte_bucket",), ("side",), ("kind",)]}
    for by, t in tables.items():
        t.to_parquet(out_dir / f"premid_missing_{'_'.join(by) or 'all'}.parquet", index=False)
    post_as_pre_summary(orders).to_parquet(out_dir / "premid_post_as_pre.parquet", index=False)
    miss = orders[(orders["missing_reason"] != "ok") & (orders["side"] != 0)]   # side 0 can never "survive"
    miss.groupby("missing_reason", observed=True)["level_survived"].mean().rename("share_level_survived") \
        .reset_index().to_parquet(out_dir / "premid_missing_level_survived.parquet", index=False)
    return tables, orders


def main(argv=None):
    p = argparse.ArgumentParser(description="Missing pre-trade quotes: rates and the post-trade substitute test")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default=None, help="default: <data>/results/validation")
    a = p.parse_args(argv)
    data = Path(a.data)
    run(data, a.out or data / "results" / "validation")


if __name__ == "__main__":
    main()
