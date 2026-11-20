"""At-trade quotes (CLAUDE.md §2 已知缺口「成交前報價缺失」, §10 rule A'', stage 2).

The panel's ``pre_bid`` / ``pre_ask`` follow rule A'' (wtox.research.trades): touched side = the
order's first fill price, other side from the post-trade book or the previous quote. This module
reports how often that quote exists and checks the rule:

1. ``classify`` / ``summary``: why a trade has no at-trade quote (no_side / first_of_day /
   prev_stale / other_side_invalid), by liquidity, DTE, month, side;
2. ``other_side_agreement``: where both the post-trade and the still-valid previous quote give
   the other side, how often they agree;
3. ``reaction_test``: single-fill orders with a previous quote <= 1 s old whose touched level is
   unchanged before and after. If the issuer reacted to the trade within the same print, the
   post-trade other side would move, and in the trade's direction;
4. ``sweep_check``: invariants (by construction the first fill pays exactly the quoted half spread,
   so this catches fill-ordering errors only; also: under A'' a wrong exchange flag can no longer
   show up as a negative effective spread). Every fill's half-spread paid s*(P_i - pre_mid) is >= the quoted
   half spread s*(P1 - pre_mid); a strict > holds only for fills at a worse price than P1 (one
   order can take several resting orders at the same price, so "multi-fill" alone does not imply >).

post_* columns are diagnostics only and must not become features (config.POST_TRADE_COLUMNS).

    python -m wtox.research.quotes --data ../data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox.research import config
from wtox.research.coverage import dte_bucket

REASONS = ("ok", "no_side", "first_of_day", "prev_stale", "other_side_invalid")
LIQUIDITY_EDGES = (0, 1, 5, 20, np.inf)
LIQUIDITY_LABELS = ("1", "2–5", "6–20", ">20")


def classify(panel):
    """Panel plus ``missing_reason``, ``orders_that_day`` and grouping columns."""
    p = panel.copy()
    reason = np.select(
        [p["pre_mid"].notna(), ~p["order_tick_type"].isin([1, 2]), p["prev_quote_age_s"].isna(), ~p["prev_in_force"]],
        ["ok", "no_side", "first_of_day", "prev_stale"], "other_side_invalid")
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


def _orders(panel):
    """One row per order: first-fill columns plus the last fill's post-trade quote."""
    first = panel[panel["fill_seq"] == 0].drop(columns=["post_bid", "post_ask"])
    last = panel.loc[panel["fill_seq"] == panel["n_fills"] - 1, ["datetime", "warrant_id", "post_bid", "post_ask"]]
    return first.merge(last, on=["datetime", "warrant_id"], how="left")


def other_side_agreement(panel):
    """Orders where both sources give the other side: share where post-trade == previous quote."""
    o = _orders(panel)
    buy, p1 = o["order_tick_type"] == 1, o["first_fill_price"]
    post_o, prev_o = np.where(buy, o["post_bid"], o["post_ask"]), np.where(buy, o["prev_bid"], o["prev_ask"])
    prev_t = np.where(buy, o["prev_ask"], o["prev_bid"])
    with np.errstate(invalid="ignore"):
        inside = lambda x: np.where(buy, (x > 0) & (x < p1), (x > 0) & (x > p1))
        both = o["order_tick_type"].isin([1, 2]) & inside(post_o) & inside(prev_o) & np.isclose(prev_t, p1)
    return pd.Series({"n": int(both.sum()), "share_equal": float(np.isclose(post_o[both], prev_o[both]).mean())
                      if both.any() else np.nan})


def reaction_test(panel, max_age_s=1.0):
    """Single-fill orders, previous quote <= max_age_s old, touched level equal before/after the fill,
    and 2330's mid unchanged since the previous order in the warrant (so a re-quote on a stock move
    is not read as a reaction to the print). One row per order: did the other side move, toward /
    against the trade's direction."""
    o = _orders(panel).sort_values(["warrant_id", "datetime"], kind="mergesort")
    o["prev_S_mid"] = o.groupby("warrant_id")["S_mid"].shift(1)
    o = o[(o["n_fills"] == 1) & (o["prev_quote_age_s"] <= max_age_s) & o["order_tick_type"].isin([1, 2])
          & np.isclose(o["S_mid"], o["prev_S_mid"])]
    buy = o["order_tick_type"] == 1
    p1 = o["first_fill_price"]
    keep = np.where(buy, np.isclose(o["prev_ask"], p1) & np.isclose(o["post_ask"], p1),
                    np.isclose(o["prev_bid"], p1) & np.isclose(o["post_bid"], p1))
    other_ok = np.where(buy, (o["prev_bid"] > 0) & (o["post_bid"] > 0), (o["prev_ask"] > 0) & (o["post_ask"] > 0))
    o, buy = o[keep & other_ok], buy[keep & other_ok]
    move = np.where(buy, o["post_bid"] - o["prev_bid"], o["prev_ask"] - o["post_ask"])  # > 0: toward the trade
    moved = ~np.isclose(move, 0)
    return pd.DataFrame({"side": np.where(buy, "buy", "sell"), "moved": moved, "toward": moved & (move > 0),
                         "against": moved & (move < 0)})


def reaction_summary(flags):
    g = flags.groupby("side")
    return pd.concat([g.size().rename("n"), g[["moved", "toward", "against"]].mean()], axis=1).reset_index()


def sweep_check(panel, tol=1e-9):
    """Invariant counts on fills with an at-trade quote: paid half-spread vs quoted half-spread."""
    p = panel[panel["pre_mid"].notna() & panel["order_tick_type"].isin([1, 2])]
    s = np.where(p["order_tick_type"] == 1, 1, -1)
    paid = s * (p["close"] - p["pre_mid"])
    quoted = s * (p["first_fill_price"] - p["pre_mid"])
    worse = s * (p["close"] - p["first_fill_price"]) > tol
    return pd.Series({"n_fills": len(p), "n_below_quoted": int((paid < quoted - tol).sum()),
                      "n_worse_price": int(worse.sum()), "n_worse_not_above": int((worse & (paid <= quoted + tol)).sum()),
                      "n_quoted_nonpositive": int((quoted <= tol).sum())})


def run(data_dir, out_dir, panel_dir=None, days=None):
    """``days`` limits the run (the substitution rule was decided on training days only)."""
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    panel_dir = Path(panel_dir or data_dir / "panel" / "tsmc_warrant_trades")
    cls, agree, react, sweep = [], [], [], []
    for path in sorted(panel_dir.glob("*.parquet")):
        if not config.in_sample(path.stem) or (days is not None and path.stem not in days):
            continue
        p = pd.read_parquet(path)
        c = classify(p)
        cls.append(c[["datetime", "warrant_id", "volume", "order_volume", "side", "missing_reason", "liquidity",
                      "dte_bucket", "kind", "pre_quote_source"]].assign(day=path.stem))
        agree.append(other_side_agreement(p).rename(path.stem))
        react.append(reaction_test(p))
        sweep.append(sweep_check(p).rename(path.stem))
    out_dir.mkdir(parents=True, exist_ok=True)
    cls = pd.concat(cls, ignore_index=True)
    cls["month"] = cls["datetime"].dt.to_period("M").astype(str)
    cls["size"] = pd.cut(cls["order_volume"], [0, 10, 50, 100, 500, np.inf], labels=["1–10", "11–50", "51–100",
                                                                                     "101–500", ">500"])
    tables = {by: summary(cls, by) for by in [(), ("month",), ("liquidity",), ("dte_bucket",), ("side",), ("kind",),
                                              ("size",)]}
    for by, t in tables.items():
        t.to_parquet(out_dir / f"premid_missing_{'_'.join(by) or 'all'}.parquet", index=False)
    a = pd.DataFrame(agree)
    checks = {
        "other_side_agreement": pd.DataFrame({"n": [a["n"].sum()],
                                              "share_equal": [(a["n"] * a["share_equal"].fillna(0)).sum() / a["n"].sum()]}),
        "reaction_test": reaction_summary(pd.concat(react, ignore_index=True)),
        "sweep_check": pd.DataFrame(sweep).sum().to_frame().T,
    }
    for k, v in checks.items():
        v.to_parquet(out_dir / f"premid_{k}.parquet", index=False)
    return tables, checks


def main(argv=None):
    p = argparse.ArgumentParser(description="At-trade quote coverage and rule checks")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default=None, help="default: <data>/results/validation")
    a = p.parse_args(argv)
    data = Path(a.data)
    run(data, a.out or data / "results" / "validation")


if __name__ == "__main__":
    main()
