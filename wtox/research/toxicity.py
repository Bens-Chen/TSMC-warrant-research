"""Stage 3 main analysis: per-trade toxicity metrics and day-clustered aggregates (CLAUDE.md §3, §10).

Per trade i (side s, at-trade quote pre_mid, |delta| from the at-trade IV, ratio):

    ES_i    = s (P_i - pre_mid) / pre_mid
    M_i(h)  = s delta ratio (S_mid(t+h) - S_mid(t)) / pre_mid
    W(t+h)  = pre_mid + [model(S_mid(t+h), T - h) - model(S_mid(t), T)]      model = fixed at-trade IV
    RS_i(h) = s (P_i - W(t+h)) / pre_mid,   PI_i(h) = s (W(t+h) - pre_mid) / pre_mid,   ES = RS + PI
    cost_i  = c x G_i x netting factor         (§3.3, config.HEDGE_SCENARIOS)

De-trending (config.DETREND_HORIZONS, statistical tests only, never features): 2330's expected return
over the holding period is removed from M and RS. Fixed h: the day's mean return over all grid
windows of that length (labels/tsmc_grid). close: the day's drift per second x seconds to 13:25.

Aggregates are weighted means (config.WEIGHT) with standard errors clustered by day (⭐ §5.3).
Only trades with an at-trade quote and a delta enter; ``exclusions`` reports what was dropped.

    python -m wtox.research.toxicity --data ../data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from wtox import warrant_price
from wtox.research import config
from wtox.research.coverage import dte_bucket
from wtox.research.markout import KEY

YEAR_S = config.DAYS_PER_YEAR * 86400.0


# --- per trade -------------------------------------------------------------------------------

def eligible(df):
    return (df["pre_mid"].notna() & df["iv"].notna() & df["delta"].notna() & df["order_tick_type"].isin([1, 2])
            & (df["T"] > 0))


def _hold_seconds(t, h):
    """Seconds actually held to horizon h (capped at the end of the continuous session)."""
    end = t.dt.normalize() + config.CONTINUOUS_END
    target = end if h is None else (t + h).where(t + h < end, end)
    return (target - t).dt.total_seconds()


def trade_metrics(df, horizons=None, r=config.RISK_FREE, q=config.DIVIDEND_YIELD):
    """df: panel joined with labels (eligible rows). Adds ES and M_/RS_/PI_<h> in decimal units."""
    horizons = config.HORIZONS if horizons is None else horizons
    d = df.copy()
    s = d["side"].to_numpy(float)
    pre = d["pre_mid"].to_numpy(float)
    args = (d["strike"].to_numpy(float), r, q, d["iv"].to_numpy(float))
    ratio, kind, T = d["ratio"].to_numpy(float), d["kind"].to_numpy(), d["T"].to_numpy(float)
    base = warrant_price(d["S_mid"].to_numpy(float), args[0], r, q, args[3], T, ratio, kind)
    d["ES"] = s * (d["close"].to_numpy(float) - pre) / pre
    d["kind_sign"] = np.where(kind == "put", -1.0, 1.0)
    for name, h in horizons.items():
        sh = d[f"S_mid_{name}"].to_numpy(float)
        hold = _hold_seconds(d["datetime"], h).to_numpy()
        d[f"hold_{name}"] = hold
        d[f"M_{name}"] = s * d["delta"].to_numpy(float) * ratio * (sh - d["S_mid"].to_numpy(float)) / pre
        model = warrant_price(sh, args[0], r, q, args[3], np.maximum(T - hold / YEAR_S, 1e-9), ratio, kind)
        w = pre + (model - base)
        d[f"RS_{name}"] = s * (d["close"].to_numpy(float) - w) / pre
        d[f"PI_{name}"] = s * (w - pre) / pre
    return d


def day_drift(grid, horizons=None):
    """Per day: mean 2330 return over grid windows for each fixed h, and the drift per second for close."""
    horizons = config.HORIZONS if horizons is None else horizons
    out = {}
    base = grid["S_mid_tau"]
    for name, h in horizons.items():
        if h is None:
            first = base.dropna()
            if first.empty:
                out["close_per_s"] = np.nan
                continue
            span = (grid["tau"].iloc[0].normalize() + config.CONTINUOUS_END - grid.loc[first.index[0], "tau"]).total_seconds()
            out["close_per_s"] = (grid[f"S_mid_{name}"].iloc[0] / first.iloc[0] - 1) / span
        else:
            ok = ~grid[f"trunc_{name}"] & base.notna()
            out[name] = float((grid.loc[ok, f"S_mid_{name}"] / base[ok] - 1).mean()) if ok.any() else np.nan
    return pd.Series(out)


def detrend(d, drift, horizons=None):
    """Adds M_dt_/RS_dt_/PI_dt_<h>: 2330's expected return over the hold removed (first order). All
    horizons are de-trended; config.DETREND_HORIZONS are the main ones, shorter ones are robustness."""
    horizons = list(config.HORIZONS) if horizons is None else horizons
    for name in horizons:
        exp_ret = drift["close_per_s"] * d[f"hold_{name}"] if name == "close" else drift[name]
        adj = d["side"] * d["delta"] * d["ratio"] * d["S_mid"] * exp_ret / d["pre_mid"]
        d[f"M_dt_{name}"] = d[f"M_{name}"] - adj
        d[f"RS_dt_{name}"] = d[f"RS_{name}"] + adj
        d[f"PI_dt_{name}"] = d[f"PI_{name}"] - adj          # ES = RS_dt + PI_dt still holds
    return d


def hedge_costs(d, scenarios=None):
    """cost_<scenario> per trade, as a fraction of warrant notional (c x G x netting factor)."""
    scenarios = config.HEDGE_SCENARIOS if scenarios is None else scenarios
    # a missing 2330 spread takes that day's median (never a later day's), then the frame median
    day_med = d["S_spread_bps"].groupby(d["datetime"].dt.normalize()).transform("median")
    half = d["S_spread_bps"].fillna(day_med).fillna(d["S_spread_bps"].median()) / 2e4
    gross = d["share_equiv"].abs()
    day = d["datetime"].dt.normalize()
    for name, sc in scenarios.items():
        c = sc["tax"] + sc["fee"] + half
        keys = {"none": None, "warrant_day": [day, d["warrant_id"]], "issuer_day": [day, d["issuer"]]}[sc["netting"]]
        if keys is None:
            factor = 1.0
        else:
            net = d["share_equiv"].groupby(keys).transform("sum").abs()
            tot = gross.groupby(keys).transform("sum")
            factor = (net / tot).where(tot > 0, 0.0)
        d[f"cost_{name}"] = c * d["leverage"] * factor
    return d


def add_cuts(d):
    """Pre-registered cuts (config stage 3 block), all known at trade time."""
    d["delta_bucket"] = pd.cut(d["delta"].abs(), list(config.DELTA_BUCKET_EDGES), labels=list(config.DELTA_BUCKET_LABELS))
    d["dte_bucket"] = dte_bucket(d["T"] * config.DAYS_PER_YEAR)
    d["size_bucket"] = pd.cut(d["order_volume"], list(config.SIZE_BUCKET_EDGES), labels=list(config.SIZE_BUCKET_LABELS))
    tod = d["datetime"] - d["datetime"].dt.normalize()
    d["tod"] = pd.cut(tod, list(config.TOD_EDGES), labels=list(config.TOD_LABELS), right=False)
    for name in config.SPOT_MOVE_WINDOWS:
        fav = np.sign(d[f"S_chg_{name}"]) * d["kind_sign"] * d["side"]       # +1: spot moved in the trader's favour
        lab = pd.Series(np.select([fav > 0, fav < 0], ["favourable", "adverse"], "none"), index=d.index)
        d[f"spot_{name}"] = pd.Categorical(lab.where(d[f"S_chg_{name}"].notna()),
                                           categories=["favourable", "none", "adverse"])
    d["direction"] = np.where(d["side"] > 0, "buy", "sell")
    d["quadrant"] = d["direction"] + "_" + d["kind"]
    d["weight"] = d["notional"] if config.WEIGHT == "notional" else 1.0
    return d


def locked_days(d):
    """Days on which 2330 had no valid quote (S_mid from trade prices for most trades): a price-limit lock."""
    share = d["S_mid_is_trade"].astype(float).groupby(d["datetime"].dt.strftime("%Y-%m-%d")).mean()
    return sorted(share[share >= config.LOCKED_DAY_TRADE_MID_SHARE].index)


# --- aggregation -----------------------------------------------------------------------------

def cluster_mean(x, w, cluster):
    """Weighted mean and its day-clustered standard error (CR1). NaNs in x are dropped."""
    x, w, cluster = np.asarray(x, float), np.asarray(w, float), np.asarray(cluster)
    ok = ~np.isnan(x) & ~np.isnan(w)
    x, w, cluster = x[ok], w[ok], cluster[ok]
    if len(x) == 0 or w.sum() == 0:
        return np.nan, np.nan, 0, 0
    m = (w * x).sum() / w.sum()
    g = pd.Series(w * (x - m)).groupby(cluster).sum().to_numpy()
    G = len(g)
    se = np.sqrt((g ** 2).sum() * G / max(G - 1, 1)) / w.sum() if G > 1 else np.nan
    return m, se, int(len(x)), G


def table(d, values, by=(), weight="weight"):
    """Long table: by-groups x value -> mean (bps), se (bps), t, p, n, n_days."""
    rows = []
    groups = d.groupby(list(by), observed=True) if by else [((), d)]
    for key, g in groups:
        key = key if isinstance(key, tuple) else (key,)
        day = g["datetime"].dt.normalize().to_numpy()
        for v in values:
            m, se, n, G = cluster_mean(g[v], g[weight], day)
            t = m / se if se and se > 0 else np.nan
            rows.append({**dict(zip(by, key)), "value": v, "mean_bps": m * 1e4, "se_bps": se * 1e4, "t": t,
                         "p": 2 * stats.t.sf(abs(t), max(G - 1, 1)) if not np.isnan(t) else np.nan, "n": n, "n_days": G})
    return pd.DataFrame(rows)


def bh_fdr(p):
    """Benjamini-Hochberg adjusted p-values (NaN kept)."""
    p = np.asarray(p, float)
    out = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    q = p[ok]
    order = np.argsort(q)
    ranked = q[order] * len(q) / (np.arange(len(q)) + 1)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    res = np.empty_like(q)
    res[order] = np.minimum(adj, 1)
    out[ok] = res
    return out


# --- driver ----------------------------------------------------------------------------------

def stage3_days(panel_dir):
    days = sorted(p.stem for p in Path(panel_dir).glob("*.parquet") if config.in_sample(p.stem))
    if config.STAGE3_DAYS == "train":
        days = [x for x in days if x <= config.TRAIN_END]
    return days


def load_day(day, data_dir):
    config.check_unlocked(day)
    data_dir = Path(data_dir)
    p = pd.read_parquet(data_dir / "panel" / "tsmc_warrant_trades" / f"{day}.parquet")
    lab = pd.read_parquet(data_dir / "labels" / "tsmc_warrant_trades" / f"{day}.parquet")
    grid = pd.read_parquet(data_dir / "labels" / "tsmc_grid" / f"{day}.parquet")
    d = p.merge(lab, on=KEY, how="left", validate="one_to_one")
    return d, grid


def build(days, data_dir):
    """Per-trade frame for the given days (eligible trades) and the exclusion counts."""
    frames, excl = [], []
    for day in days:
        d, grid = load_day(day, data_dir)
        ok = eligible(d)
        excl.append(d.assign(kept=ok)[["datetime", "T", "order_volume", "order_tick_type", "notional", "kept"]])
        d = trade_metrics(d[ok])
        d = detrend(d, day_drift(grid))
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    return add_cuts(hedge_costs(d)), exclusions(pd.concat(excl, ignore_index=True))


def exclusions(e):
    """Share of trades / notional with an at-trade quote, overall and by every cut computable without one."""
    e = e.assign(direction=np.select([e["order_tick_type"] == 1, e["order_tick_type"] == 2], ["buy", "sell"], "unflagged"),
                 dte_bucket=dte_bucket(e["T"] * config.DAYS_PER_YEAR),
                 size_bucket=pd.cut(e["order_volume"], list(config.SIZE_BUCKET_EDGES), labels=list(config.SIZE_BUCKET_LABELS)),
                 tod=pd.cut(e["datetime"] - e["datetime"].dt.normalize(), list(config.TOD_EDGES), labels=list(config.TOD_LABELS),
                            right=False), all="all")
    rows = []
    for cut in ["all", "direction", "dte_bucket", "size_bucket", "tod"]:
        for grp, g in e.groupby(cut, observed=True):
            rows.append({"cut": cut, "group": str(grp), "n": len(g), "share_kept_n": g["kept"].mean(),
                         "share_kept_notional": g.loc[g["kept"], "notional"].sum() / g["notional"].sum()})
    return pd.DataFrame(rows)


def _value_cols(h, prefix=("M", "RS", "PI")):
    return [f"{p}_{h}" for p in prefix]


def analyse(d):
    """All stage 3 tables (bps). Main horizon config.MAIN_HORIZON."""
    hz = list(config.HORIZONS)
    main = config.MAIN_HORIZON
    trunc_ok = lambda h: ~d[f"trunc_{h}"] if f"trunc_{h}" in d else pd.Series(True, index=d.index)
    cuts = ["direction", "quadrant", "delta_bucket", "dte_bucket", "size_bucket", f"spot_{config.SPOT_MOVE_WINDOW}", "tod"]
    out = {}
    # markout curves: M(h) and de-trended M for every cut (shape attribution, §3.4)
    curves = []
    for h in hz:
        dh = d[trunc_ok(h)]
        vals = [f"M_{h}"] + ([f"M_dt_{h}"] if f"M_dt_{h}" in d else [])
        curves += [table(dh, vals).assign(cut="all", horizon=h)]
        curves += [table(dh, vals, [c]).rename(columns={c: "group"}).assign(cut=c, horizon=h) for c in cuts]
    out["curves"] = pd.concat(curves, ignore_index=True)
    out["truncation"] = pd.DataFrame([{"horizon": h, "n": len(d), "share_truncated": float((~trunc_ok(h)).mean())}
                                      for h in hz])
    # spread decomposition and issuer net revenue at the main horizon (H1)
    dm = d[trunc_ok(main)].copy()
    costs = [f"cost_{k}" for k in config.HEDGE_SCENARIOS]
    for k in config.HEDGE_SCENARIOS:
        dm[f"net_{k}"] = dm[f"RS_dt_{main}"] - dm[f"cost_{k}"]
    vals = ["ES", f"RS_{main}", f"PI_{main}", f"M_{main}", f"RS_dt_{main}", f"PI_dt_{main}", f"M_dt_{main}"] + costs + \
           [f"net_{k}" for k in config.HEDGE_SCENARIOS]
    dec = [table(dm, vals).assign(cut="all")]
    dec += [table(dm, vals, [c]).rename(columns={c: "group"}).assign(cut=c) for c in cuts]
    out["decomposition"] = pd.concat(dec, ignore_index=True)
    # pre-specified high-gamma cell, and the exploratory |delta| x DTE grid with BH-FDR
    cross = table(dm, [f"M_dt_{main}", f"net_neutral"], ["delta_bucket", "dte_bucket"])
    cross["pre_specified"] = (cross["delta_bucket"] == config.HIGH_GAMMA_CELL[0]) & (cross["dte_bucket"] == config.HIGH_GAMMA_CELL[1])
    cross["p_bh"] = np.nan
    for v in cross["value"].unique():
        m = (cross["value"] == v) & ~cross["pre_specified"]
        cross.loc[m, "p_bh"] = bh_fdr(cross.loc[m, "p"])
    out["delta_dte"] = cross
    # equal-weighted robustness of the decomposition
    eq = dm.assign(w1=1.0)
    out["decomposition_equal"] = pd.concat([table(eq, vals, weight="w1").assign(cut="all")] +
                                           [table(eq, vals, [c], weight="w1").rename(columns={c: "group"}).assign(cut=c)
                                            for c in cuts], ignore_index=True)
    # issuers (H3, secondary): quoted half spread vs markout
    dm["half_spread"] = dm["pre_spread_pct"] / 2
    out["issuers"] = table(dm, ["half_spread", "ES", f"M_dt_{main}", f"RS_dt_{main}"], ["issuer"])
    # retail view (b): spot just moved in the trader's favour -> gross M(h) - ES, then net of warrant costs
    retail_cost = config.WARRANT_TAX + 2 * config.BROKERAGE_FEE_MAX
    fav = d[d[f"spot_{config.SPOT_MOVE_WINDOW}"] == "favourable"].copy()
    rb = []
    for h in hz:
        f = fav[trunc_ok(h).loc[fav.index]].copy()
        f["gross"] = f[f"M_{h}"] - f["ES"]                 # §3.6(b): entry half spread only
        f["gross_roundtrip"] = f[f"M_{h}"] - 2 * f["ES"]   # also exiting at the issuer's quote (~ one more half spread)
        f["net_roundtrip"] = f["gross_roundtrip"] - retail_cost
        rb.append(table(f, ["gross", "gross_roundtrip", "net_roundtrip"], ["direction"]).assign(horizon=h))
    rb = pd.concat(rb, ignore_index=True).assign(exploratory=True)   # ⭐ upper bound, exploratory only
    rb["p_bh"] = bh_fdr(rb["p"])
    out["retail_latency"] = rb
    return out


def run(data_dir, out_dir=None):
    data_dir = Path(data_dir)
    out_dir = Path(out_dir or data_dir / "results" / "stage3")
    days = stage3_days(data_dir / "panel" / "tsmc_warrant_trades")
    d, excl = build(days, data_dir)
    res = analyse(d)
    res["exclusions"] = excl
    out_dir.mkdir(parents=True, exist_ok=True)
    for k, v in res.items():
        v.to_parquet(out_dir / f"{k}.parquet", index=False)
    return res


def main(argv=None):
    p = argparse.ArgumentParser(description="Stage 3 toxicity tables (training period)")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default=None, help="default: <data>/results/stage3")
    a = p.parse_args(argv)
    run(a.data, a.out)


if __name__ == "__main__":
    main()
