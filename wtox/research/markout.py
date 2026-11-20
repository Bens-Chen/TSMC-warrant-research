"""Labels: future mids after each panel trade. The ONLY module allowed to look forward (CLAUDE.md §4).

For every panel trade (key: day + trade_id) and every horizon h in config.HORIZONS:

* ``S_mid_<h>``  underlying mid at t+h: the post-trade bid/ask of the last 2330 tick at or before
  t+h (last trade price when the quote is invalid, flagged ``S_is_trade_<h>``). Ticks exist only at
  trades, so between trades the quote is assumed unchanged. Same mid rule as the panel (quote_mid).
* ``W_mid_<h>``  the warrant's own last observed post-trade mid at or before t+h (NaN if invalid),
  with ``W_age_<h>`` = seconds between that tick and t+h. Shioaji has no quotes between trades, so
  this is stale for illiquid warrants; the model-based W_mid uses S_mid_<h> instead (toxicity.py).

t+h is capped at the last continuous-session tick (before 13:25); ``close`` is that last tick.
``trunc_<h>`` (fixed-length h only) is True when the cap bit, i.e. the trade was held less than h.
Only future prices are stored: no drift, no cross-sample statistic (de-trending is in toxicity.py).

Join labels to the panel on the full KEY (trade_id, datetime, warrant_id), never on trade_id alone:
trade_id is a row number and shifts when the panel is rebuilt. A label file older than its panel
file is rebuilt automatically.

Grid labels (``build_grid_labels``, labels/tsmc_grid/<day>.parquet): on the fixed grid τ =
09:00, 09:01, ... (config.H4_GRID) before 13:25, the 2330 mid at τ and at τ + h for every horizon
(capped and flagged like the trade labels). They are the H4 targets and the day de-trending base.

Build every day:  python -m wtox.research.markout --data ../data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox.research import config
from wtox.research.trades import quote_mid

KEY = ["trade_id", "datetime", "warrant_id"]


def _session(df):
    t = df["datetime"] - df["datetime"].dt.normalize()
    return df[(t >= config.SESSION_OPEN) & (t < config.CONTINUOUS_END)]


def build_labels(panel, stock, warrants, horizons=None):
    """panel: one day of the trade panel. stock / warrants: that day's raw Shioaji ticks."""
    horizons = config.HORIZONS if horizons is None else horizons
    out = panel[KEY].copy()
    if out.empty:
        return out
    s = _session(stock).sort_values("datetime", kind="mergesort")
    qm = quote_mid(s["bid_price"], s["ask_price"])
    s = pd.DataFrame({"obs_time": s["datetime"], "mid": qm.fillna(s["close"]), "is_trade": qm.isna()})
    w = _session(warrants).sort_values("datetime", kind="mergesort")
    w = pd.DataFrame({"obs_time": w["datetime"], "warrant_id": w["warrant_id"],
                      "wmid": quote_mid(w["bid_price"], w["ask_price"])})
    last = s["obs_time"].iloc[-1] if len(s) else out["datetime"].max()

    for name, h in horizons.items():
        if h is None:
            target = pd.Series(last, index=out.index)
        else:
            target = (out["datetime"] + h).clip(upper=last)
            out[f"trunc_{name}"] = (out["datetime"] + h) > last
        q = pd.DataFrame({"target": target, "warrant_id": out["warrant_id"], "row": np.arange(len(out))})
        q = q.sort_values("target", kind="mergesort")
        sm = pd.merge_asof(q, s, left_on="target", right_on="obs_time", direction="backward")
        # a trade after the last stock tick would otherwise read the warrant's pre-trade quote
        qw = q.assign(target=np.maximum(q["target"], out["datetime"].to_numpy()[q["row"]]))
        qw = qw.sort_values("target", kind="mergesort")
        wm = pd.merge_asof(qw, w, left_on="target", right_on="obs_time", by="warrant_id", direction="backward")
        order = sm["row"].to_numpy()
        out.loc[out.index[order], f"S_mid_{name}"] = sm["mid"].to_numpy()
        out.loc[out.index[order], f"S_is_trade_{name}"] = sm["is_trade"].fillna(False).astype(bool).to_numpy()
        wm = wm.set_index("row").loc[order]
        out.loc[out.index[order], f"W_mid_{name}"] = wm["wmid"].to_numpy()
        out.loc[out.index[order], f"W_age_{name}"] = (wm["target"] - wm["obs_time"]).dt.total_seconds().to_numpy()
    return out.reset_index(drop=True)


def _stock_mids(stock):
    s = _session(stock).sort_values("datetime", kind="mergesort")
    qm = quote_mid(s["bid_price"], s["ask_price"])
    return pd.DataFrame({"obs_time": s["datetime"].astype("datetime64[ns]"), "mid": qm.fillna(s["close"])})


def build_grid_labels(stock, day, horizons=None, grid=None):
    """2330 mid at each grid point τ and at τ + h (capped at the last continuous tick)."""
    horizons = config.HORIZONS if horizons is None else horizons
    grid = config.H4_GRID if grid is None else grid
    s = _stock_mids(stock)
    if s.empty:
        return pd.DataFrame()
    d = pd.Timestamp(day)
    tau = pd.date_range(d + config.SESSION_OPEN, d + config.CONTINUOUS_END, freq=grid, inclusive="left")
    out = pd.DataFrame({"tau": tau.astype("datetime64[ns]")})      # one time unit for the as-of joins
    last = s["obs_time"].iloc[-1]
    at = pd.merge_asof(out.rename(columns={"tau": "target"}), s, left_on="target", right_on="obs_time",
                       direction="backward")
    out["S_mid_tau"] = at["mid"].to_numpy()
    for name, h in horizons.items():
        target = pd.Series(last, index=out.index) if h is None else (out["tau"] + h).clip(upper=last)
        if h is not None:
            out[f"trunc_{name}"] = (out["tau"] + h) > last
        m = pd.merge_asof(pd.DataFrame({"target": target}), s, left_on="target", right_on="obs_time",
                          direction="backward")
        out[f"S_mid_{name}"] = m["mid"].to_numpy()
    return out


def build_day(day, data_dir, panel_dir):
    data_dir = Path(data_dir)
    ppath = Path(panel_dir) / f"{day}.parquet"
    spath = data_dir / "shioaji" / "underlying_ticks" / "stock" / config.UNDERLYING / f"{day}.parquet"
    if not ppath.exists() or not spath.exists():
        return pd.DataFrame()
    panel = pd.read_parquet(ppath, columns=KEY)
    files = sorted((data_dir / "shioaji" / "ticks" / day).glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    cols = ["warrant_id", "datetime", "bid_price", "ask_price"]
    warrants = pd.concat([pd.read_parquet(f, columns=cols) for f in files], ignore_index=True)
    return build_labels(panel, pd.read_parquet(spath), warrants)


def main(argv=None):
    p = argparse.ArgumentParser(description="Future-mid labels for the warrant trade panel, one Parquet per day")
    p.add_argument("--data", default="../data")
    p.add_argument("--panel", default=None, help="default: <data>/panel/tsmc_warrant_trades")
    p.add_argument("--out", default=None, help="default: <data>/labels/tsmc_warrant_trades")
    p.add_argument("--rebuild", action="store_true")
    a = p.parse_args(argv)
    data = Path(a.data)
    panel_dir = Path(a.panel or data / "panel" / "tsmc_warrant_trades")
    out = Path(a.out or data / "labels" / "tsmc_warrant_trades")
    out.mkdir(parents=True, exist_ok=True)
    grid_out = out.parent / "tsmc_grid"
    grid_out.mkdir(parents=True, exist_ok=True)
    for ppath in sorted(panel_dir.glob("*.parquet")):
        day = ppath.stem
        if not config.in_sample(day):
            continue
        gpath = grid_out / f"{day}.parquet"
        spath = data / "shioaji" / "underlying_ticks" / "stock" / config.UNDERLYING / f"{day}.parquet"
        if (a.rebuild or not gpath.exists()) and spath.exists():
            g = build_grid_labels(pd.read_parquet(spath), day)
            if len(g):
                g.to_parquet(gpath, index=False)
        path = out / f"{day}.parquet"
        fresh = path.exists() and path.stat().st_mtime > ppath.stat().st_mtime   # equal mtime -> rebuild
        if fresh and not a.rebuild:
            continue
        labels = build_day(day, data, panel_dir)
        if len(labels):
            labels.to_parquet(path, index=False)
        print(day, len(labels), "labels")


if __name__ == "__main__":
    main()
