"""H4: warrant net delta flow and 2330's next return (CLAUDE.md §3.7, settings pre-registered in §10).

Features (``build_flow``, one file per day in <data>/flow, only information before τ):

* F(τ) = Σ share_equiv over panel trades in [τ - k, τ) (delta-equivalent 2330 shares; buying puts is
  negative), split into calls and puts. Trades without an at-trade quote have no delta and are left
  out (``flow_notional_share`` reports the covered share of warrant notional).
* denominator: mean 2330 shares traded in the same time-of-day window [τ - k, τ) over the previous
  config.H4_NORM_LOOKBACK_DAYS trading days (NaN until that many days exist).
* controls: 2330 mid return over [τ - k, τ]; 2330 buyer- minus seller-initiated shares in [τ - k, τ)
  over the same denominator; time-of-day bucket.

Targets come from the grid labels (wtox.research.markout, labels/tsmc_grid): r(τ, h) = S_mid(τ+h) /
S_mid(τ) - 1, mid to mid. ``regress`` fits OLS with day-clustered standard errors on the training days.

    python -m wtox.research.flow --data ../data            # features for every day
    python -m wtox.research.flow --data ../data --h4       # in-sample regressions (training period)
"""

import argparse
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from wtox.research import config
from wtox.research.toxicity import bh_fdr
from wtox.research.trades import continuous_session, quote_mid

FLOW_COLUMNS = ["F", "F_call", "F_put"]


def taus(day):
    d = pd.Timestamp(day)
    return pd.date_range(d + config.H4_FIRST_TAU, d + config.H4_LAST_TAU, freq=config.H4_GRID).astype("datetime64[ns]")


def _window_sum(times, values, tau, k):
    """Σ values with tau - k <= time < tau, for each tau (times sorted)."""
    c = np.r_[0.0, np.cumsum(values)]
    hi = np.searchsorted(times, tau.to_numpy(), side="left")
    lo = np.searchsorted(times, (tau - k).to_numpy(), side="left")
    return c[hi] - c[lo]


def stock_windows(stock, day):
    """Per τ: 2330 shares traded and signed shares in [τ - k, τ), mids at τ and τ - k."""
    s = continuous_session(stock).sort_values("datetime", kind="mergesort")
    tau, k = taus(day), config.H4_FLOW_WINDOW
    t = s["datetime"].to_numpy()
    shares = s["volume"].to_numpy(float) * config.UNITS_PER_LOT          # Shioaji stock volume is in lots
    sign = np.select([s["tick_type"] == 1, s["tick_type"] == 2], [1.0, -1.0], 0.0)
    if len(sign):
        sign[0] = 0.0          # the day's first print is the opening call auction: no aggressor side
    mid = quote_mid(s["bid_price"], s["ask_price"]).fillna(s["close"]).to_numpy(float)
    at = lambda x: np.searchsorted(t, x.to_numpy(), side="right") - 1    # last tick at or before x
    i_now, i_past = at(tau), at(tau - k)
    pick = lambda i: np.where(i >= 0, mid[np.clip(i, 0, None)], np.nan)
    return pd.DataFrame({"tau": tau, "stock_shares": _window_sum(t, shares, tau, k),
                         "stock_signed": _window_sum(t, shares * sign, tau, k),
                         "S_mid_now": pick(i_now), "S_mid_past": pick(i_past)})


def build_flow(panel, stock, day, denom):
    """One day of H4 features. ``denom``: array aligned with taus(day) (NaN when unknown)."""
    sw = stock_windows(stock, day)
    tau, k = sw["tau"], config.H4_FLOW_WINDOW
    ok = panel["share_equiv"].notna() & panel["order_tick_type"].isin([1, 2])
    p = panel[ok].sort_values("datetime", kind="mergesort")
    t = p["datetime"].to_numpy()
    out = sw.copy()
    for col, m in [("F", np.ones(len(p), bool)), ("F_call", (p["kind"] == "call").to_numpy()),
                   ("F_put", (p["kind"] == "put").to_numpy())]:
        out[col] = _window_sum(t, np.where(m, p["share_equiv"].to_numpy(float), 0.0), tau, k)
    out["n_trades"] = _window_sum(t, np.ones(len(p)), tau, k)
    out["denom"] = np.asarray(denom, float)
    for col in FLOW_COLUMNS:
        out[f"{col}_norm"] = out[col] / out["denom"]
    out["signed_norm"] = out["stock_signed"] / out["denom"]
    out["ret_past"] = out["S_mid_now"] / out["S_mid_past"] - 1
    tod = tau - tau.dt.normalize()
    out["tod"] = ((tod - config.SESSION_OPEN) // config.H4_TOD_DUMMY).astype(int)
    out.attrs["flow_notional_share"] = float(panel.loc[ok, "notional"].sum() / panel["notional"].sum()) if len(panel) else np.nan
    return out


def run(data_dir, out_dir=None):
    """Features for every in-sample day in date order; the denominator only uses earlier days."""
    data_dir = Path(data_dir)
    out_dir = Path(out_dir or data_dir / "flow")
    out_dir.mkdir(parents=True, exist_ok=True)
    panel_dir = data_dir / "panel" / "tsmc_warrant_trades"
    days = sorted(p.stem for p in panel_dir.glob("*.parquet") if config.in_sample(p.stem))
    past = deque(maxlen=config.H4_NORM_LOOKBACK_DAYS)
    cover = []
    for day in days:
        spath = data_dir / "shioaji" / "underlying_ticks" / "stock" / config.UNDERLYING / f"{day}.parquet"
        if not spath.exists():
            continue
        stock = pd.read_parquet(spath)
        denom = np.mean(past, axis=0) if len(past) == past.maxlen else np.full(len(taus(day)), np.nan)
        f = build_flow(pd.read_parquet(panel_dir / f"{day}.parquet"), stock, day, denom)
        f.to_parquet(out_dir / f"{day}.parquet", index=False)
        cover.append({"day": day, "flow_notional_share": f.attrs["flow_notional_share"]})
        past.append(f["stock_shares"].to_numpy(float))
    cover = pd.DataFrame(cover)
    res = data_dir / "results"
    res.mkdir(parents=True, exist_ok=True)
    cover.to_parquet(res / "flow_coverage.parquet", index=False)
    return cover


# --- in-sample regressions -------------------------------------------------------------------

def ols_cluster(y, X, cluster):
    """OLS coefficients with CR1 day-clustered standard errors. X: DataFrame (incl. const)."""
    Xv, yv = X.to_numpy(float), np.asarray(y, float)
    n, k = Xv.shape
    bread = np.linalg.pinv(Xv.T @ Xv)
    beta = bread @ Xv.T @ yv
    u = yv - Xv @ beta
    scores = pd.DataFrame(Xv * u[:, None]).groupby(np.asarray(cluster)).sum().to_numpy()
    G = len(scores)
    c = G / (G - 1) * (n - 1) / (n - k) if G > 1 else np.nan
    V = c * bread @ (scores.T @ scores) @ bread
    se = np.sqrt(np.diag(V))
    t = beta / se
    return pd.DataFrame({"term": X.columns, "coef": beta, "se": se, "t": t,
                         "p": 2 * stats.t.sf(np.abs(t), max(G - 1, 1)), "n": n, "n_days": G})


def h4_frame(days, data_dir, horizon):
    """Flow features joined with the τ + h target (bps), valid τ only."""
    data_dir = Path(data_dir)
    h = config.HORIZONS[horizon]
    rows = []
    for day in days:
        f = pd.read_parquet(data_dir / "flow" / f"{day}.parquet")
        g = pd.read_parquet(data_dir / "labels" / "tsmc_grid" / f"{day}.parquet", columns=["tau", "S_mid_tau", f"S_mid_{horizon}"])
        d = f.merge(g, on="tau", how="inner")
        end = pd.Timestamp(day) + config.CONTINUOUS_END
        if h is not None:
            d = d[d["tau"] + h <= end]
        d["y_bps"] = (d[f"S_mid_{horizon}"] / d["S_mid_tau"] - 1) * 1e4
        rows.append(d.assign(day=day))
    d = pd.concat(rows, ignore_index=True)
    need = ["y_bps", "F_norm", "ret_past", "signed_norm"]
    return d.dropna(subset=need)


def regress(d, flow_terms=("F_norm",)):
    X = pd.concat([pd.Series(1.0, index=d.index, name="const"), d[list(flow_terms)],
                   (d["ret_past"] * 1e4).rename("ret_past_bps"), d["signed_norm"],
                   pd.get_dummies(d["tod"], prefix="tod", drop_first=True, dtype=float)], axis=1)
    return ols_cluster(d["y_bps"], X, d["day"])


def run_h4(data_dir, out_dir=None):
    data_dir = Path(data_dir)
    out_dir = Path(out_dir or data_dir / "results" / "stage3")
    out_dir.mkdir(parents=True, exist_ok=True)
    days = sorted(p.stem for p in (data_dir / "flow").glob("*.parquet") if p.stem <= config.TRAIN_END)
    res = []
    for h in (config.H4_MAIN_HORIZON, *config.H4_EXPLORATORY_HORIZONS):
        d = h4_frame(days, data_dir, h)
        main = h == config.H4_MAIN_HORIZON
        res.append(regress(d).assign(horizon=h, spec="all", main=main))
        res.append(regress(d, ("F_call_norm", "F_put_norm")).assign(horizon=h, spec="call_put", main=False))
    res = pd.concat(res, ignore_index=True)
    flow = res["term"].str.startswith("F_")
    expl = flow & ~res["main"]
    res["p_bh"] = np.nan
    res.loc[expl, "p_bh"] = bh_fdr(res.loc[expl, "p"])
    d = h4_frame(days, data_dir, config.H4_MAIN_HORIZON)
    corr = d[["F_norm", "ret_past", "signed_norm"]].corr()       # stage 5 asks for this (§10)
    res.to_parquet(out_dir / "h4_regressions.parquet", index=False)
    corr.reset_index().to_parquet(out_dir / "h4_flow_correlations.parquet", index=False)
    return res, corr


def main(argv=None):
    p = argparse.ArgumentParser(description="H4 flow features and in-sample regressions")
    p.add_argument("--data", default="../data")
    p.add_argument("--h4", action="store_true", help="run the training-period regressions")
    a = p.parse_args(argv)
    run_h4(a.data) if a.h4 else run(a.data)


if __name__ == "__main__":
    main()
