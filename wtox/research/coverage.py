"""Coverage of the tick data against TEJ daily volume (CLAUDE.md §2 處理規則 2, §5.1).

For every warrant-day TEJ reports as traded (volume > 0), compare:

* ``tick_volume``  whole-day Shioaji tick volume (all sessions, so it is comparable with TEJ), and
* ``panel_volume`` the panel's volume (continuous session 09:00-13:25 with terms found; optional),

then aggregate by month x days-to-expiry bucket (config.DTE_BUCKET_*). ``coverage_count`` is the
share of TEJ-traded warrant-days with any ticks (volume is concentrated in a few warrants, so high
volume coverage can still hide many small missing warrants). Volume coverage is
Σ min(tick, TEJ) / Σ TEJ, so one warrant with extra prints cannot hide another one's gap; the
uncapped ratio is reported next to it. TEJ is joined on (exchange code, date), never on tej_id.

The pass/fail standard (config.COVERAGE_MIN_*) must be written into CLAUDE.md §10 before the
table is looked at; ``passes`` refuses to run while it is unset.

    python -m wtox.research.coverage --data ../data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox.data.backfill import TEJ_DAILY_FILES, exchange_code
from wtox.research import config

KEY = ["date", "warrant_id"]


def load_tej(data_dir, underlying=config.UNDERLYING, start=config.SAMPLE_START, end=config.SAMPLE_END):
    """TEJ warrant-days with volume > 0 in the sample: date, warrant_id (exchange code), tej_id, kind, DTE."""
    data_dir = Path(data_dir)
    cols = ["date", "warrant_id", "underlying_id", "volume", "days_to_expiry", "name"]
    flt = [("underlying_id", "==", underlying), ("date", ">=", pd.Timestamp(start)), ("date", "<=", pd.Timestamp(end))]
    paths = [data_dir / "tej" / "daily" / f for f in TEJ_DAILY_FILES if (data_dir / "tej" / "daily" / f).exists()]
    d = pd.concat([pd.read_parquet(p, columns=cols, filters=flt) for p in paths], ignore_index=True)
    d = d[(d["volume"] > 0) & d["date"].dt.strftime("%Y-%m-%d").map(config.in_sample)]
    d = _dedupe_by_code(d)
    return pd.DataFrame({
        "date": d["date"].dt.normalize(), "warrant_id": d["warrant_id"].map(exchange_code), "tej_id": d["warrant_id"],
        "kind": np.where(d["name"].str.contains("售"), "put", "call"),
        "days_to_expiry": d["days_to_expiry"], "tej_volume": d["volume"].astype("int64"),
    }).reset_index(drop=True)


def _dedupe_by_code(d):
    """One row per (date, exchange code). TEJ can list a warrant-day twice: across export files, or
    under both spellings of a split id (041993T / 041993). Keep the row with the larger volume."""
    d = d.assign(_code=d["warrant_id"].map(exchange_code), date=d["date"].dt.normalize())
    d = d.sort_values("volume", ascending=False, kind="mergesort").drop_duplicates(["date", "_code"])
    return d.drop(columns="_code").sort_values(["date", "warrant_id"], kind="mergesort")


def _day_volumes(day_dir):
    rows = []
    for p in Path(day_dir).glob("*.parquet"):
        v = pd.read_parquet(p, columns=["volume"])["volume"].sum()
        rows.append((p.stem, int(v)))
    return rows


def load_tick_volume(data_dir, days):
    """Whole-day tick volume per (date, warrant_id) for the given YYYY-MM-DD days."""
    ticks = Path(data_dir) / "shioaji" / "ticks"
    rows = [(pd.Timestamp(day), code, v) for day in days for code, v in _day_volumes(ticks / day)]
    return pd.DataFrame(rows, columns=["date", "warrant_id", "tick_volume"])


def load_panel_volume(panel_dir, days):
    out = []
    for day in days:
        p = Path(panel_dir) / f"{day}.parquet"
        if p.exists():
            v = pd.read_parquet(p, columns=["warrant_id", "volume"]).groupby("warrant_id")["volume"].sum()
            out.append(pd.DataFrame({"date": pd.Timestamp(day), "warrant_id": v.index, "panel_volume": v.to_numpy()}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["date", "warrant_id", "panel_volume"])


def dte_bucket(days_to_expiry):
    return pd.cut(days_to_expiry, bins=list(config.DTE_BUCKET_EDGES), labels=list(config.DTE_BUCKET_LABELS),
                  right=True)


def warrant_days(tej, ticks, panel=None):
    """One row per TEJ-traded warrant-day with tick (and panel) volume; missing = 0."""
    d = tej.merge(ticks, on=KEY, how="left")
    d["tick_volume"] = d["tick_volume"].fillna(0).astype("int64")
    if panel is not None:
        d = d.merge(panel, on=KEY, how="left")
        d["panel_volume"] = d["panel_volume"].fillna(0).astype("int64")
    d["month"] = d["date"].dt.to_period("M")
    d["dte_bucket"] = dte_bucket(d["days_to_expiry"])
    return d


def _agg(d, by):
    cols = ["tick_volume"] + (["panel_volume"] if "panel_volume" in d else [])
    x = d.assign(**{f"{c}_capped": np.minimum(d[c], d["tej_volume"]) for c in cols})
    g = x.groupby(by, observed=True)
    out = pd.DataFrame({"n_warrant_days": g.size(), "n_missing": g["tick_volume"].agg(lambda s: int((s == 0).sum())),
                        "tej_volume": g["tej_volume"].sum()})
    out["coverage_count"] = 1 - out["n_missing"] / out["n_warrant_days"]     # share of warrant-days with any ticks
    for c in cols:
        out[f"{c}"] = g[c].sum()
        out[f"coverage_{c.split('_')[0]}"] = g[f"{c}_capped"].sum() / out["tej_volume"]
        out[f"ratio_{c.split('_')[0]}"] = out[c] / out["tej_volume"]
    return out.reset_index()


def coverage_tables(d, buckets=None):
    """(cells, months): month x DTE bucket and month totals. ``buckets`` keeps only those DTE buckets
    (the consistent pool, config.CONSISTENT_POOL_DTE_BUCKETS)."""
    if buckets is not None:
        d = d[d["dte_bucket"].isin(list(buckets))]
    if d["dte_bucket"].isna().any():
        raise ValueError(f"{int(d['dte_bucket'].isna().sum())} warrant-days without days_to_expiry")
    cells, months = _agg(d, ["month", "dte_bucket"]), _agg(d, ["month"])
    assert cells["tej_volume"].sum() == months["tej_volume"].sum()      # cells add up to the months
    return cells, months


def passes(cells, months, min_cell=None, min_month=None):
    """Apply the pre-registered standard. Returns (cells, months) with a boolean ``ok`` column."""
    min_cell = config.COVERAGE_MIN_CELL if min_cell is None else min_cell
    min_month = config.COVERAGE_MIN_MONTH if min_month is None else min_month
    if min_cell is None or min_month is None:
        raise RuntimeError("coverage standard not set: write it into CLAUDE.md §10 and config.COVERAGE_MIN_* first")
    return (cells.assign(ok=cells["coverage_tick"] >= min_cell),
            months.assign(ok=months["coverage_tick"] >= min_month))


def run(data_dir, out_dir, panel_dir=None):
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    tej = load_tej(data_dir)
    days = sorted(tej["date"].dt.strftime("%Y-%m-%d").unique())
    ticks = load_tick_volume(data_dir, days)
    panel = load_panel_volume(panel_dir, days) if panel_dir else None
    d = warrant_days(tej, ticks, panel)
    cells, months = coverage_tables(d)
    out_dir.mkdir(parents=True, exist_ok=True)
    d.to_parquet(out_dir / "coverage_warrant_days.parquet", index=False)
    cells.assign(month=cells["month"].astype(str)).to_parquet(out_dir / "coverage_cells.parquet", index=False)
    months.assign(month=months["month"].astype(str)).to_parquet(out_dir / "coverage_months.parquet", index=False)
    return d, cells, months


def main(argv=None):
    p = argparse.ArgumentParser(description="Tick coverage vs TEJ, by month x days-to-expiry")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default=None, help="default: <data>/results/validation")
    p.add_argument("--panel", default=None, help="default: <data>/panel/tsmc_warrant_trades")
    a = p.parse_args(argv)
    data = Path(a.data)
    run(data, a.out or data / "results" / "validation", a.panel or data / "panel" / "tsmc_warrant_trades")
    print("written; apply coverage.passes() only after the standard is in CLAUDE.md §10")


if __name__ == "__main__":
    main()
