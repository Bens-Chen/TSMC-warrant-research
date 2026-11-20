"""IV and delta sanity checks, and same-side IV changes (CLAUDE.md §5.1).

* ``delta_sign``: calls must have delta > 0, puts delta < 0.
* ``iv_vs_tej``: per warrant-day, our IV (last valid trade of the day and the day's median) next
  to TEJ's daily IV and delta. TEJ's delta is per warrant (option delta x ratio), so ours is
  scaled the same way; that scale is not documented, so the per-share difference is reported too. TEJ uses closing prices, we use the pre-trade mid, so
  differences reflect timing as well as model inputs; a systematic gap points to terms or r/q.
  ``days_from_ex`` tags warrant-days near an ex-dividend date for the separate check in §5.1.
* ``same_side_iv_changes``: implied vol from each order's fill price (first fill = the touched
  quote), paired with the previous order on the SAME side in the same warrant within
  config.IV_PAIR_MAX_GAP. Buy-vs-buy (ask IV) and sell-vs-sell (bid IV) only: mixing sides would
  read the normal bid-ask IV spread as a vol cut (⭐ §5.1). A falling ask IV after retail buys is
  the issuer marking vol down, which the fixed-IV W_mid cannot see.

    python -m wtox.research.ivcheck --data ../data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox import warrant_iv
from wtox.data.backfill import TEJ_DAILY_FILES, exchange_code
from wtox.research import config, coverage


def delta_sign(panel):
    """Counts of delta sign violations by kind (rows with a delta only)."""
    p = panel[panel["delta"].notna()]
    bad = ((p["kind"] == "call") & (p["delta"] <= 0)) | ((p["kind"] == "put") & (p["delta"] >= 0))
    return pd.DataFrame({"n": p.groupby("kind").size(), "n_bad": bad.groupby(p["kind"]).sum()}).reset_index()


def load_tej_greeks(data_dir, underlying=config.UNDERLYING, start=config.SAMPLE_START, end=config.SAMPLE_END):
    data_dir = Path(data_dir)
    cols = ["date", "warrant_id", "underlying_id", "tej_iv", "tej_delta", "close", "underlying_price",
            "days_to_expiry", "volume"]
    flt = [("underlying_id", "==", underlying), ("date", ">=", pd.Timestamp(start)), ("date", "<=", pd.Timestamp(end))]
    paths = [data_dir / "tej" / "daily" / f for f in TEJ_DAILY_FILES if (data_dir / "tej" / "daily" / f).exists()]
    d = pd.concat([pd.read_parquet(p, columns=cols, filters=flt) for p in paths], ignore_index=True)
    if d["tej_iv"].median() > 3:      # guard: the comparison assumes decimals (0.45), not percent (45)
        raise ValueError("tej_iv looks like percent; normalise it in wtox.data.tej first")
    d = coverage._dedupe_by_code(d)
    return d.assign(tej_id=d["warrant_id"], warrant_id=d["warrant_id"].map(exchange_code),
                    date=d["date"].dt.normalize()).rename(columns={"close": "tej_close", "volume": "tej_volume"})


def iv_vs_tej(panel, tej, ex_dates=()):
    """Per warrant-day: our last / median IV and per-warrant delta vs TEJ's. Join on (code, date)."""
    p = panel[panel["iv"].notna()].sort_values("datetime", kind="mergesort")
    p = p.assign(date=p["datetime"].dt.normalize(), share_delta=p["delta"], warrant_delta=p["delta"] * p["ratio"])
    g = p.groupby(["date", "warrant_id"])
    ours = pd.DataFrame({"kind": g["kind"].last(), "iv_last": g["iv"].last(), "iv_median": g["iv"].median(),
                         "delta_last": g["warrant_delta"].last(), "share_delta_last": g["share_delta"].last(),
                         "n_trades": g.size()}).reset_index()
    out = ours.merge(tej[["date", "warrant_id", "tej_iv", "tej_delta", "days_to_expiry"]],
                     on=["date", "warrant_id"], how="left")
    out["iv_diff"] = out["iv_last"] - out["tej_iv"]
    # TEJ's delta scale is not documented in the export: report both, the closer one decides
    out["delta_diff"] = out["delta_last"] - out["tej_delta"]                 # per warrant (x ratio)
    out["delta_diff_per_share"] = out["share_delta_last"] - out["tej_delta"]  # per share
    ex = pd.to_datetime(sorted(ex_dates))
    if len(ex) and len(out):
        dd = (out["date"].to_numpy()[:, None] - ex.to_numpy()[None, :]) / np.timedelta64(1, "D")
        out["days_from_ex"] = dd[np.arange(len(out)), np.abs(dd).argmin(axis=1)]
    else:
        out["days_from_ex"] = np.nan
    return out


def same_side_iv_changes(panel, r=config.RISK_FREE, q=config.DIVIDEND_YIELD, max_gap=None):
    """Pairs (previous same-side order, order) in one warrant: IVs from fill prices and the change.

    Built backward (each order against the one before it on the same side), so no future
    operator is needed; the pairs are the same as "order vs next same-side order".
    """
    max_gap = config.IV_PAIR_MAX_GAP if max_gap is None else max_gap
    o = panel[(panel["fill_seq"] == 0) & (panel["side"] != 0) & (panel["T"] > 0)].copy()
    if o.empty:
        return pd.DataFrame()
    o["iv_fill"] = warrant_iv(o["close"].to_numpy(), o["S_mid"].to_numpy(), o["strike"].to_numpy(), r, q,
                              o["T"].to_numpy(), o["ratio"].to_numpy(), o["kind"].to_numpy())
    o = o.sort_values(["warrant_id", "side", "datetime"], kind="mergesort")
    g = o.groupby(["warrant_id", "side"], sort=False)
    o["prev_time"] = g["datetime"].shift(1)
    o["prev_iv"] = g["iv_fill"].shift(1)
    o["prev_S_mid"] = g["S_mid"].shift(1)
    o["prev_order_volume"] = g["order_volume"].shift(1)
    o["gap_s"] = (o["datetime"] - o["prev_time"]).dt.total_seconds()
    o = o[o["prev_time"].notna() & (o["gap_s"] <= max_gap.total_seconds())]
    o["d_iv"] = o["iv_fill"] - o["prev_iv"]
    o["dS_bps"] = (o["S_mid"] - o["prev_S_mid"]) / o["prev_S_mid"] * 1e4
    return o[["prev_time", "datetime", "warrant_id", "kind", "issuer", "side", "T", "moneyness", "prev_order_volume",
              "prev_iv", "iv_fill", "d_iv", "gap_s", "dS_bps"]].reset_index(drop=True)


def run(data_dir, out_dir, panel_dir=None, ex_dates=()):
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    panel_dir = Path(panel_dir or data_dir / "panel" / "tsmc_warrant_trades")
    tej = load_tej_greeks(data_dir)
    signs, ivs, pairs = [], [], []
    for path in sorted(panel_dir.glob("*.parquet")):
        if not config.in_sample(path.stem):
            continue
        p = pd.read_parquet(path)
        signs.append(delta_sign(p).assign(day=path.stem))
        ivs.append(iv_vs_tej(p, tej[tej["date"] == pd.Timestamp(path.stem)], ex_dates))
        pairs.append(same_side_iv_changes(p).assign(day=path.stem))
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {"delta_sign": pd.concat(signs, ignore_index=True), "iv_vs_tej": pd.concat(ivs, ignore_index=True),
           "same_side_iv": pd.concat(pairs, ignore_index=True)}
    for k, v in res.items():
        v.to_parquet(out_dir / f"{k}.parquet", index=False)
    return res


def main(argv=None):
    from wtox.research import dividends
    p = argparse.ArgumentParser(description="IV vs TEJ, delta signs, same-side IV changes")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default=None, help="default: <data>/results/validation")
    a = p.parse_args(argv)
    data = Path(a.data)
    ex = dividends.ex_dates(dividends.load(data)) if (data / config.DIVIDEND_FILE).exists() else ()
    run(data, a.out or data / "results" / "validation", ex_dates=ex)


if __name__ == "__main__":
    main()
