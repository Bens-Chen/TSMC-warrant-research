"""Clock checks for the two Shioaji feeds (CLAUDE.md §5.1 時鐘對齊與解析度). Decides whether 1s / 5s stay.

(a) ``resolution``: how fine the timestamps really are. The column is datetime64[ns] with
    microsecond digits, but a feed stamped to the millisecond or the second shows zeros there.
(b) ``lead_lag``: cross-correlation of 2330 mid moves and warrant mid moves on a fixed grid
    (config.CLOCK_GRID). Each warrant mid move is signed by kind (call +1, put -1), so both series
    point the same way when issuers follow the stock. corr(stock[k], warrant[k + lag]):
    a peak at lag > 0 = warrants move after the stock (issuer re-quote latency, expected);
    a peak at lag < 0 = warrants move first, which points to a clock offset between the feeds.

Caveat: Shioaji has no quotes between trades, so a warrant mid move is seen only at the warrant's
next trade (post-trade quote). That delays warrant moves and biases the peak toward lag > 0; a
peak at lag < 0 is therefore the informative failure. Only valid two-sided quotes are used (no
trade-price fallback), so a bad quote cannot create a fake move.

    python -m wtox.research.clock --data ../data --days 2026-09-01 2026-06-10
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox.research import config
from wtox.research import terms as terms_mod
from wtox.research.trades import continuous_session, quote_mid


def resolution(ts):
    """Share of timestamps whose sub-second digits are zero at each precision, plus gap stats."""
    ts = pd.Series(pd.to_datetime(ts)).dropna()
    if ts.empty:
        return {"n": 0}
    sub_us = ts.dt.microsecond.to_numpy()          # 0..999999 within the second
    gaps = np.diff(np.sort(ts.to_numpy()).astype("int64")) / 1e3        # microseconds
    pos = gaps[gaps > 0]
    return {
        "n": len(ts),
        "share_whole_second": float(np.mean(sub_us == 0)),
        "share_whole_ms": float(np.mean(sub_us % 1000 == 0)),         # includes whole seconds
        "share_sub_ms": float(np.mean(sub_us % 1000 != 0)),
        "share_nonzero_ns": float(np.mean(ts.dt.nanosecond.to_numpy() != 0)),
        "share_repeated": float(np.mean(gaps == 0)) if len(gaps) else 0.0,
        "min_positive_gap_us": float(pos.min()) if len(pos) else np.nan,
    }


def _moves(times, mids, by=None):
    """(time, sign of mid change) at each tick where the valid mid changed (within `by` groups)."""
    df = pd.DataFrame({"t": times, "m": mids})
    if by is not None:
        df["g"] = by
    df = df[df["m"].notna()]
    d = df.groupby("g")["m"].diff() if by is not None else df["m"].diff()
    keep = d.notna() & (d != 0)
    return df.loc[keep, "t"], np.sign(d[keep]).to_numpy()


def _bin(times, values, start, grid, n):
    k = ((pd.to_datetime(times) - start) // grid).to_numpy().astype("int64")
    ok = (k >= 0) & (k < n)
    return np.bincount(k[ok], weights=np.asarray(values, float)[ok], minlength=n)


def lead_lag(stock, warrants, kind_by_warrant, grid=None, max_lag=None):
    """One day. stock / warrants: raw Shioaji ticks; kind_by_warrant: warrant_id -> 'call'/'put'.

    Returns DataFrame(lag, lag_s, corr, n_stock_moves, n_warrant_moves); lag in grid steps.
    """
    grid = config.CLOCK_GRID if grid is None else grid
    max_lag = config.CLOCK_MAX_LAG if max_lag is None else max_lag
    s = continuous_session(stock).sort_values("datetime", kind="mergesort")
    w = continuous_session(warrants)
    w = w[w["warrant_id"].isin(kind_by_warrant.index)].sort_values(["warrant_id", "datetime"], kind="mergesort")
    if s.empty or w.empty:
        return pd.DataFrame(columns=["lag", "lag_s", "corr", "n_stock_moves", "n_warrant_moves"])
    day = s["datetime"].iloc[0].normalize()
    start = day + config.SESSION_OPEN
    n = int((config.CONTINUOUS_END - config.SESSION_OPEN) / grid)
    st, ss = _moves(s["datetime"], quote_mid(s["bid_price"], s["ask_price"]))
    wt, ws = _moves(w["datetime"], quote_mid(w["bid_price"], w["ask_price"]), by=w["warrant_id"].to_numpy())
    sign = np.where(w.loc[wt.index, "warrant_id"].map(kind_by_warrant).to_numpy() == "put", -1.0, 1.0)
    x = _bin(st, ss, start, grid, n)
    y = _bin(wt, ws * sign, start, grid, n)
    rows = []
    for lag in range(-max_lag, max_lag + 1):
        a, b = (x[: n - lag], y[lag:]) if lag >= 0 else (x[-lag:], y[: n + lag])
        c = np.corrcoef(a, b)[0, 1] if a.std() > 0 and b.std() > 0 else np.nan
        rows.append((lag, lag * grid.total_seconds(), c))
    out = pd.DataFrame(rows, columns=["lag", "lag_s", "corr"])
    out["n_stock_moves"], out["n_warrant_moves"] = len(ss), len(ws)
    return out


def peak(ll):
    """Lag (seconds) with the highest correlation, or NaN."""
    ll = ll.dropna(subset=["corr"])
    return float(ll.loc[ll["corr"].idxmax(), "lag_s"]) if len(ll) else np.nan


def run(data_dir, out_dir, days):
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    terms, div_dates = terms_mod.load(data_dir, config.UNDERLYING)
    res, lls = [], []
    for day in days:
        spath = data_dir / "shioaji" / "underlying_ticks" / "stock" / config.UNDERLYING / f"{day}.parquet"
        files = sorted((data_dir / "shioaji" / "ticks" / day).glob("*.parquet"))
        if not spath.exists() or not files:
            continue
        stock = pd.read_parquet(spath)
        warrants = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        res += [{"day": day, "feed": "stock", **resolution(continuous_session(stock)["datetime"])},
                {"day": day, "feed": "warrant", **resolution(continuous_session(warrants)["datetime"])}]
        kinds = terms_mod.terms_on(terms, day, div_dates).set_index("warrant_id")["kind"]
        lls.append(lead_lag(stock, warrants, kinds).assign(day=day))
    out_dir.mkdir(parents=True, exist_ok=True)
    res = pd.DataFrame(res)
    ll = pd.concat(lls, ignore_index=True) if lls else pd.DataFrame()
    res.to_parquet(out_dir / "clock_resolution.parquet", index=False)
    ll.to_parquet(out_dir / "clock_lead_lag.parquet", index=False)
    return res, ll


def main(argv=None):
    p = argparse.ArgumentParser(description="Timestamp resolution and stock-warrant lead-lag")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default=None, help="default: <data>/results/validation")
    p.add_argument("--days", nargs="+", required=True)
    a = p.parse_args(argv)
    data = Path(a.data)
    days = [d for d in a.days if config.in_sample(d)]
    run(data, a.out or data / "results" / "validation", days)


if __name__ == "__main__":
    main()
