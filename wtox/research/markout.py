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

Placebo labels (``build_placebo_labels``, labels/tsmc_placebo/<day>.parquet, stage 4): a random time
in the same session per trade and the 2330 mid there and h later.

IV path labels (``build_iv_path``, labels/iv_path/<day>.parquet, extension E): per warrant and grid
point τ, the at-trade mid IV of the warrant's last quoted trade at or before τ (NaN before the first;
IVs at the solver bounds are dropped). Built from the panel only; it is a label because E reads it at
grid points after each trade.

Close quotes (``build_close_quotes``, labels/close_quotes/<day>.parquet, who-wins phase 2): per warrant
the last valid bid / ask shown before 13:25 that day (backward within the day). Exit labels
(``build_exit_labels``, labels/exit_quotes/<day>.parquet): for each trade and k in
config.RETAIL_HOLD_DAYS, the close quotes of the k-th in-sample trading day after the trade, the 2330 close
that day, whether the warrant expired by then, and the 2330 close used to settle it.

Build every day:  python -m wtox.research.markout --data ../data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

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


def build_placebo_labels(panel, stock, day, horizon=None, seed=None):
    """Stage 4 placebo: for every panel trade, a random time u in the same day's continuous session
    (fixed seed per day) and the 2330 mid at u and u + h. The trade's side / warrant are kept."""
    horizon = config.MAIN_HORIZON if horizon is None else horizon
    seed = config.PLACEBO_SEED if seed is None else seed
    out = panel[KEY].copy()
    s = _stock_mids(stock)
    if out.empty or s.empty:
        return pd.DataFrame()
    d = pd.Timestamp(day)
    rng = np.random.default_rng([seed, int(d.strftime("%Y%m%d"))])
    span = (config.CONTINUOUS_END - config.SESSION_OPEN).total_seconds()
    u = (d + config.SESSION_OPEN + pd.to_timedelta(rng.uniform(0, span, len(out)), unit="s")).astype("datetime64[ns]")
    out["rand_time"] = u
    last = s["obs_time"].iloc[-1]
    h = config.HORIZONS[horizon]
    for col, target in [("S_mid_rand", pd.Series(u, index=out.index)),
                        (f"S_mid_rand_{horizon}", pd.Series(u, index=out.index) + h if h is not None else pd.Series(last, index=out.index))]:
        q = pd.DataFrame({"target": target.clip(upper=last).to_numpy(), "row": np.arange(len(out))}).sort_values("target", kind="mergesort")
        m = pd.merge_asof(q, s, left_on="target", right_on="obs_time", direction="backward").sort_values("row")
        out[col] = m["mid"].to_numpy()
    if h is not None:
        out[f"trunc_rand_{horizon}"] = (out["rand_time"] + h) > last
    out[f"hold_rand_{horizon}"] = ((out["rand_time"] + h).clip(upper=last) - out["rand_time"]).dt.total_seconds() \
        if h is not None else (last - out["rand_time"]).dt.total_seconds()
    return out.reset_index(drop=True)


def build_iv_path(panel, day, grid=None):
    grid = config.H4_GRID if grid is None else grid
    lo, hi = config.EXT_PROXY_IV_BOUNDS
    ok = (panel["pre_mid"].notna() & panel["iv"].notna() & panel["delta"].notna()
          & panel["order_tick_type"].isin([1, 2]) & (panel["T"] > 0) & (panel["iv"] > lo) & (panel["iv"] < hi))
    src = panel.loc[ok, ["warrant_id", "datetime", "iv"]].sort_values("datetime", kind="mergesort")
    src["datetime"] = src["datetime"].astype("datetime64[ns]")
    if src.empty:
        return pd.DataFrame(columns=["warrant_id", "tau", "iv_tau"])
    d = pd.Timestamp(day)
    tau = pd.date_range(d + config.SESSION_OPEN, d + config.CONTINUOUS_END, freq=grid, inclusive="left").astype("datetime64[ns]")
    q = pd.MultiIndex.from_product([src["warrant_id"].unique(), tau], names=["warrant_id", "tau"]).to_frame(index=False)
    q = q.sort_values("tau", kind="mergesort")
    m = pd.merge_asof(q, src, left_on="tau", right_on="datetime", by="warrant_id", direction="backward")
    return m[["warrant_id", "tau"]].assign(iv_tau=m["iv"].to_numpy()).sort_values(["warrant_id", "tau"]).reset_index(drop=True)


def build_close_quotes(warrants):
    w = _session(warrants).sort_values("datetime", kind="mergesort")
    out = []
    for side in ("bid", "ask"):
        v = w[w[f"{side}_price"] > 0].groupby("warrant_id").last()
        out.append(v[[f"{side}_price", "datetime"]].rename(columns={f"{side}_price": side, "datetime": f"{side}_time"}))
    if not out[0].index.size and not out[1].index.size:
        return pd.DataFrame(columns=["warrant_id", "bid", "bid_time", "ask", "ask_time"])
    return pd.concat(out, axis=1).rename_axis("warrant_id").reset_index()


def build_exit_labels(panel, day, days, close_quotes, closes):
    """panel: one day (KEY + T). days: sorted in-sample days. close_quotes: day -> frame (or None).
    closes: Series day -> 2330 13:25 mid (in-sample days)."""
    out = panel[KEY].copy()
    i = days.index(day)
    expiry = (pd.Timestamp(day) + pd.to_timedelta(np.round(panel["T"].to_numpy(float) * config.DAYS_PER_YEAR), unit="D"))
    cdays = pd.to_datetime(pd.Index(closes.index))
    for k in config.RETAIL_HOLD_DAYS:
        if i + k >= len(days):
            for c in ("exit_day", "bid", "ask", "bid_age_s", "S_close", "expired", "S_settle"):
                out[f"{c}_{k}"] = np.nan
            continue
        ex = days[i + k]
        q = close_quotes(ex)
        m = out[["warrant_id"]].merge(q[["warrant_id", "bid", "ask", "bid_time"]], on="warrant_id", how="left") if q is not None \
            else pd.DataFrame({"bid": np.nan, "ask": np.nan, "bid_time": pd.NaT}, index=range(len(out)))
        out[f"exit_day_{k}"] = ex
        out[f"bid_{k}"] = m["bid"].to_numpy()
        out[f"ask_{k}"] = m["ask"].to_numpy()
        close_t = pd.Timestamp(ex) + config.CONTINUOUS_END
        out[f"bid_age_s_{k}"] = (close_t - pd.to_datetime(m["bid_time"])).dt.total_seconds().to_numpy()
        out[f"expiry_{k}"] = expiry
        out[f"S_close_{k}"] = closes.get(ex, np.nan)
        exp = expiry <= pd.Timestamp(ex)
        out[f"expired_{k}"] = np.asarray(exp)
        pos = cdays.searchsorted(expiry, side="right") - 1          # last in-sample close on or before expiry
        settle = np.where(pos >= 0, closes.to_numpy()[np.clip(pos, 0, None)], np.nan)
        out[f"S_settle_{k}"] = np.where(exp, settle, np.nan)
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
    plc_out = out.parent / "tsmc_placebo"
    plc_out.mkdir(parents=True, exist_ok=True)
    iv_out = out.parent / "iv_path"
    iv_out.mkdir(parents=True, exist_ok=True)
    cq_out = out.parent / "close_quotes"
    cq_out.mkdir(parents=True, exist_ok=True)
    ex_out = out.parent / "exit_quotes"
    ex_out.mkdir(parents=True, exist_ok=True)
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
        ppl = plc_out / f"{day}.parquet"
        if spath.exists() and (a.rebuild or not ppl.exists() or ppl.stat().st_mtime <= ppath.stat().st_mtime):
            pl = build_placebo_labels(pd.read_parquet(ppath, columns=KEY), pd.read_parquet(spath), day)
            if len(pl):
                pl.to_parquet(ppl, index=False)
        ivp = iv_out / f"{day}.parquet"
        iv_cols = ["warrant_id", "datetime", "pre_mid", "iv", "delta", "order_tick_type", "T"]
        if (a.rebuild or not ivp.exists() or ivp.stat().st_mtime <= ppath.stat().st_mtime) \
                and set(iv_cols) <= set(pq.read_schema(ppath).names):
            build_iv_path(pd.read_parquet(ppath, columns=iv_cols), day).to_parquet(ivp, index=False)
        cqp = cq_out / f"{day}.parquet"
        files = sorted((data / "shioaji" / "ticks" / day).glob("*.parquet"))
        if (a.rebuild or not cqp.exists()) and files:
            cols = ["warrant_id", "datetime", "bid_price", "ask_price"]
            build_close_quotes(pd.concat([pd.read_parquet(f, columns=cols) for f in files], ignore_index=True)).to_parquet(cqp, index=False)
        path = out / f"{day}.parquet"
        fresh = path.exists() and path.stat().st_mtime > ppath.stat().st_mtime   # equal mtime -> rebuild
        if fresh and not a.rebuild:
            continue
        labels = build_day(day, data, panel_dir)
        if len(labels):
            labels.to_parquet(path, index=False)
        print(day, len(labels), "labels")
    build_all_exit_labels(data, panel_dir, ex_out, cq_out, out.parent / "tsmc_grid", a.rebuild)


def build_all_exit_labels(data, panel_dir, ex_out, cq_out, grid_dir, rebuild=False):
    """Second pass (needs every day's close quotes): forward-looking exit labels per trade."""
    days = sorted(p.stem for p in Path(panel_dir).glob("*.parquet") if config.in_sample(p.stem))
    closes = pd.Series({d: pd.read_parquet(Path(grid_dir) / f"{d}.parquet", columns=["S_mid_close"])["S_mid_close"].iloc[0]
                        for d in days if (Path(grid_dir) / f"{d}.parquet").exists()})
    cache = {}

    def cq(d):
        if d not in cache:
            f = Path(cq_out) / f"{d}.parquet"
            cache[d] = pd.read_parquet(f) if f.exists() else None
        return cache[d]

    for day in days:
        f = Path(ex_out) / f"{day}.parquet"
        pp = Path(panel_dir) / f"{day}.parquet"
        if f.exists() and not rebuild and f.stat().st_mtime > pp.stat().st_mtime:
            continue
        if "T" not in pq.read_schema(pp).names:
            continue
        panel = pd.read_parquet(pp, columns=KEY + ["T"])
        build_exit_labels(panel, day, days, cq, closes).to_parquet(f, index=False)


if __name__ == "__main__":
    main()
