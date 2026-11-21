"""Who wins, who loses (phase 1, intraday) — docs/decisions.md, 2026-11-22 (exploratory, pre-registered).

Same trades seen from both sides, bps of pre_mid notional, notional-weighted, day-clustered:

* market maker (issuer): stage 3 net = RS_dt(h) - hedge cost (neutral main; pessimistic / optimistic range)
* trader, retail buys (opening): hold to h, exit at the issuer's bid
      net(h) = -RS(h) - quoted half spread - warrant tax - 2 x brokerage fee
  classified with de-trended RS (RS_dt), the raw version is the realised P&L; retail sells get the
  "timing value of selling" -RS(h) (exit costs are paid either way)
* leakage = neutral hedge cost + the trader's taxes and fees (paid by one side, received by neither)

Groups: |delta| x DTE map (16 cells); conditions IV vs 2330 realised vol, spot just moved (1 s), chasing
vs contrarian (2330 past 5 min), TAIEX futures past 5 min, time of day — each alone and x DTE.

    python -m wtox.research.retail --data ../data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox.research import config, toxicity

COST_RT = config.RETAIL_ROUND_TRIP_TAX + 2 * config.RETAIL_FEE
CONDITIONS = ("iv_level", "spot_1s", "chase", "tx_dir", "tod")


# --- conditions (all backward-looking) -------------------------------------------------------

def realised_vol(closes):
    """closes: Series of daily 13:25 mids indexed by day (sorted). RV for day d uses the previous
    RETAIL_RV_DAYS close-to-close log returns ending at d-1, annualised with 252 trading days."""
    r = np.log(closes).diff()
    return r.rolling(config.RETAIL_RV_DAYS, min_periods=config.RETAIL_RV_DAYS).std().shift(1) * np.sqrt(252)


def _direction(ret_bps, side, kind_sign):
    x = ret_bps * side * kind_sign
    lab = np.select([x > config.RETAIL_FLAT_BPS, x < -config.RETAIL_FLAT_BPS], ["with", "against"], "flat")
    return pd.Series(np.where(np.isnan(x), "na", lab), index=ret_bps.index)


def tx_past_return(t, bars):
    """TAIEX futures return over the 5 minutes before each trade time t (bps). A bar stamped ts is used
    from ts + 1 min; both ends must be the same contract. bars: ts, contract, close_none (day session)."""
    b = bars.sort_values("ts", kind="mergesort")
    avail = (b["ts"] + config.RETAIL_TX_BAR).to_numpy("datetime64[ns]")
    tt = t.to_numpy("datetime64[ns]")
    i_now = np.searchsorted(avail, tt, side="right") - 1
    i_past = np.searchsorted(avail, tt - np.timedelta64(5, "m"), side="right") - 1
    ok = (i_now >= 0) & (i_past >= 0)
    gap = np.timedelta64(int(config.RETAIL_TX_MAX_STALE.total_seconds()), "s")
    a_now, a_past = avail[np.clip(i_now, 0, None)], avail[np.clip(i_past, 0, None)]
    day = t.dt.normalize().to_numpy("datetime64[ns]")
    ok &= (tt - a_now <= gap) & ((tt - np.timedelta64(5, "m")) - a_past <= gap) & (a_past >= day)   # fresh, same day
    c, k = b["close_none"].to_numpy(float), b["contract"].astype(str).to_numpy()
    cn, cp = c[np.clip(i_now, 0, None)], c[np.clip(i_past, 0, None)]
    same = k[np.clip(i_now, 0, None)] == k[np.clip(i_past, 0, None)]
    return pd.Series(np.where(ok & same, (cn / cp - 1) * 1e4, np.nan), index=t.index)


def load_tx(data_dir):
    x = pd.read_parquet(Path(data_dir) / config.RETAIL_TX_FILE, columns=["ts", "trade_date", "session", "contract", "close_none"])
    return x[x["session"] == "position"]


def daily_closes(data_dir):
    days = sorted(p.stem for p in (Path(data_dir) / "labels" / "tsmc_grid").glob("*.parquet") if config.in_sample(p.stem))
    days = [x for x in days if config.TEST_UNLOCKED or x < config.TEST_START]
    return pd.Series({d: pd.read_parquet(Path(data_dir) / "labels" / "tsmc_grid" / f"{d}.parquet", columns=["S_mid_close"])
                      ["S_mid_close"].iloc[0] for d in days}).sort_index()


def add_conditions(d, rv, tx, iv_cuts):
    """rv: Series day -> realised vol; tx: day-session TAIEX futures bars; iv_cuts: two tercile cut points.
    Modifies d in place (the caller passes a column subset)."""
    day = d["datetime"].dt.strftime("%Y-%m-%d")
    d["iv_gap"] = d["iv"] - day.map(rv)
    lab = pd.cut(d["iv_gap"], [-np.inf, iv_cuts[0], iv_cuts[1], np.inf], labels=["low", "mid", "high"])
    d["iv_level"] = lab.astype(str).where(lab.notna(), "na")
    d["chase"] = _direction(d["S_ret_5m"] * 1e4, d["side"], d["kind_sign"])
    d["tx_ret_bps"] = tx_past_return(d["datetime"], tx)
    d["tx_dir"] = _direction(d["tx_ret_bps"], d["side"], d["kind_sign"])
    d["spot_1s"] = d["spot_1s"].astype(str)
    d["tod"] = d["tod"].astype(str)
    d["cell"] = d["delta_bucket"].astype(str) + "|" + d["dte_bucket"].astype(str)
    d["dte"] = d["dte_bucket"].astype(str)
    return d


# --- metrics ---------------------------------------------------------------------------------

def metrics(d):
    """Per trade (decimal), in place. 5m metrics are NaN for trades truncated at the end of the session."""
    half = d["pre_spread_pct"] / 2
    for h in config.RETAIL_HORIZONS:
        keep = ~d[f"trunc_{h}"].astype(bool) if f"trunc_{h}" in d else pd.Series(True, index=d.index)
        for k in config.HEDGE_SCENARIOS:
            d[f"mm_{k}_{h}"] = (d[f"RS_dt_{h}"] - d[f"cost_{k}"]).where(keep)
        d[f"trader_{h}"] = (-d[f"RS_dt_{h}"] - half - COST_RT).where(keep)          # buys: round trip
        d[f"trader_raw_{h}"] = (-d[f"RS_{h}"] - half - COST_RT).where(keep)
        d[f"timing_{h}"] = (-d[f"RS_dt_{h}"]).where(keep)                           # sells
        d[f"timing_raw_{h}"] = (-d[f"RS_{h}"]).where(keep)
    d["leakage"] = d["cost_neutral"] + COST_RT
    return d


SAMPLES = {
    "buys": ["trader_5m", "trader_close", "trader_raw_5m", "trader_raw_close", "mm_neutral_5m", "mm_pessimistic_5m",
             "mm_optimistic_5m", "mm_neutral_close", "leakage"],
    "all": ["mm_neutral_5m", "mm_pessimistic_5m", "mm_optimistic_5m", "mm_neutral_close"],
    "sells": ["timing_5m", "timing_close", "timing_raw_5m", "timing_raw_close", "mm_neutral_5m"],
}


def group_sets():
    out = [("cell", ["cell"])]
    for c in CONDITIONS:
        out += [(c, [c]), (f"{c}×dte", [c, "dte"])]
    return out


def build_map(d):
    rows = []
    for sample, vals in SAMPLES.items():
        x = d if sample == "all" else d[d["side"] > 0] if sample == "buys" else d[d["side"] < 0]
        rows.append(toxicity.table(x, vals).assign(sample=sample, group_set="all", group="all"))
        for name, by in group_sets():
            t = toxicity.table(x, vals, by)
            t["group"] = t[by].astype(str).agg("|".join, axis=1)
            rows.append(t.drop(columns=by).assign(sample=sample, group_set=name))
    return pd.concat(rows, ignore_index=True)


def finalise(m, include=None):
    """Cell inclusion (training counts), BH-FDR per (sample, value) over included groups. Groups with a
    missing condition value ("na") stay in the map but are flagged and left out of BH and quadrants."""
    m = m.copy()
    m["missing_label"] = m["group"].str.split("|").apply(lambda parts: any(x in ("na", "nan") for x in parts))
    if include is None:
        cnt = m[m["value"] == m.groupby("sample")["value"].transform("first")]
        ok = (cnt["n"] >= config.HEATMAP_MIN_TRADES) & (cnt["n_days"] >= config.HEATMAP_MIN_DAYS)
        include = set(map(tuple, cnt.loc[ok, ["sample", "group_set", "group"]].to_numpy()))
    key = list(zip(m["sample"], m["group_set"], m["group"]))
    m["include"] = np.array([k in include for k in key]) & ~m["missing_label"].to_numpy(bool)
    m["p_bh"] = np.nan
    for (s, v), idx in m[m["include"] & (m["group_set"] != "all")].groupby(["sample", "value"]).groups.items():
        m.loc[idx, "p_bh"] = toxicity.bh_fdr(m.loc[idx, "p"])
    return m, include


def quadrants(m, alpha=0.05):
    b = m[(m["sample"] == "buys") & m["include"] & (m["group_set"] != "all")]
    if b.empty:
        return pd.DataFrame(columns=["group_set", "group", "quadrant"])
    p = b.pivot_table(index=["group_set", "group"], columns="value", values=["mean_bps", "p_bh"])
    out = pd.DataFrame({"mm_bps": p[("mean_bps", "mm_neutral_5m")], "mm_p_bh": p[("p_bh", "mm_neutral_5m")],
                        "trader_bps": p[("mean_bps", "trader_5m")], "trader_p_bh": p[("p_bh", "trader_5m")],
                        "trader_close_bps": p[("mean_bps", "trader_close")],
                        "leakage_bps": p[("mean_bps", "leakage")]})

    def side(bps, pb, win, lose):
        return np.where(pb < alpha, np.where(bps > 0, win, lose), "不確定")

    out["market_maker"] = side(out["mm_bps"], out["mm_p_bh"], "賺", "虧")
    out["trader"] = side(out["trader_bps"], out["trader_p_bh"], "賺", "虧")
    out["quadrant"] = "造市商" + out["market_maker"] + "／交易者" + out["trader"]
    return out.reset_index()


# --- phase 2: multi-day holding (trader side) -------------------------------------------------

def nw_mean(x, w, day, lag, all_days=None):
    """Weighted mean and a Newey-West SE over the entry-day score series (Bartlett, ``lag`` trading days).
    ``all_days``: every trading day of the period, so days with no trade in the group count as zero scores
    and the lag is in trading days, not observed days. Degrees of freedom use the observed days."""
    x, w, day = np.asarray(x, float), np.asarray(w, float), np.asarray(day)
    ok = ~np.isnan(x) & ~np.isnan(w)
    x, w, day = x[ok], w[ok], day[ok]
    if len(x) == 0 or w.sum() == 0:
        return np.nan, np.nan, 0, 0
    W = w.sum()
    m = (w * x).sum() / W
    g = pd.Series(w * (x - m)).groupby(day).sum().sort_index()
    G = len(g)
    if all_days is not None:
        g = g.reindex(all_days, fill_value=0.0)
    g = g.to_numpy()
    V = (g ** 2).sum()
    for l in range(1, min(lag, G - 1) + 1):
        V += 2 * (1 - l / (lag + 1)) * (g[l:] * g[:-l]).sum()
    return m, np.sqrt(max(V, 0.0)) / W if G > 1 else np.nan, int(len(x)), G


def nw_table(d, values, lag, by=(), all_days=None):
    from scipy import stats
    rows = []
    groups = d.groupby(list(by), observed=True) if by else [((), d)]
    for key, g in groups:
        key = key if isinstance(key, tuple) else (key,)
        day = g["datetime"].dt.normalize().to_numpy()
        for v in values:
            m, se, n, G = nw_mean(g[v], g["weight"], day, lag, all_days)
            t = m / se if se and se > 0 else np.nan
            rows.append({**dict(zip(by, key)), "value": v, "mean_bps": m * 1e4, "se_bps": se * 1e4, "t": t,
                         "p": 2 * stats.t.sf(abs(t), max(G - 1, 1)) if not np.isnan(t) else np.nan, "n": n, "n_days": G,
                         "obs_share": float(g.loc[g[v].notna(), "weight"].sum() / g["weight"].sum())})
    return pd.DataFrame(rows)


def intrinsic(S, K, ratio, kind):
    return np.where(kind == "put", np.maximum(K - S, 0.0), np.maximum(S - K, 0.0)) * ratio


def multiday_metrics(d, mu):
    """Buys only. d has exit labels joined (bid_k, S_close_k, expired_k, S_settle_k). mu: the period's mean
    daily 2330 return (de-trending, statistical tests only)."""
    d = d[d["side"] > 0].copy()
    for k in config.RETAIL_HOLD_DAYS:
        exp = d[f"expired_{k}"].astype("boolean").fillna(False).to_numpy(bool)
        S_exit = np.where(exp, d[f"S_settle_{k}"], d[f"S_close_{k}"])
        val = np.where(exp, intrinsic(d[f"S_settle_{k}"].to_numpy(float), d["strike"].to_numpy(float),
                                      d["ratio"].to_numpy(float), d["kind"].to_numpy()), d[f"bid_{k}"])
        val = np.where(exp | (d[f"bid_{k}"] > 0), val, np.nan)
        raw = (val - d["close"]) / d["pre_mid"] - COST_RT
        expo = d["side"] * d["delta"] * d["ratio"] / d["pre_mid"]
        d[f"hold_raw_{k}"] = raw
        d[f"hold_dt_{k}"] = raw - expo * d["S_mid"] * mu * k
        d[f"hold_dir_{k}"] = (expo * (S_exit - d["S_mid"])).where(raw.notna())
        d[f"hold_resid_{k}"] = raw - d[f"hold_dir_{k}"]
        # unobserved exits close to expiry (likely after the last trading day, before expiry: no quote)
        near = (pd.to_datetime(d[f"expiry_{k}"]) - pd.to_datetime(d[f"exit_day_{k}"])).dt.days.between(0, 14)
        d[f"unobs_near_expiry_{k}"] = (raw.isna() & near & ~exp).astype(float)
        d[f"expired_share_{k}"] = exp.astype(float)
    return d


def multiday_summary(d):
    """Per k: exit coverage, expiry settlement, unobserved exits near expiry, exit-bid age."""
    rows = []
    for k in config.RETAIL_HOLD_DAYS:
        w = d["weight"]
        obs = d[f"hold_raw_{k}"].notna()
        for scope, m in [("all", pd.Series(True, index=d.index)), ("dte_1-30", d["dte_bucket"].astype(str) == "1–30")]:
            ww = w[m]
            rows.append({"hold": k, "scope": scope, "obs_share": float(ww[obs[m]].sum() / ww.sum()),
                         "expired_share": float((d.loc[m, f"expired_share_{k}"] * ww).sum() / ww.sum()),
                         "unobs_near_expiry_share": float((d.loc[m, f"unobs_near_expiry_{k}"] * ww).sum() / ww.sum()),
                         "bid_age_median_s": float(d.loc[m & obs, f"bid_age_s_{k}"].median())})
    return pd.DataFrame(rows)


def multiday_map(d):
    by_cols = sorted({c for _, by in group_sets() for c in by})
    d = d[["datetime", "weight"] + by_cols + [c for c in d if c.startswith("hold_")]]
    all_days = np.sort(d["datetime"].dt.normalize().unique())
    rows = []
    for k in config.RETAIL_HOLD_DAYS:
        vals = [f"hold_{x}_{k}" for x in ("raw", "dt", "dir", "resid")]
        rows.append(nw_table(d, vals, k, all_days=all_days).assign(hold=k, group_set="all", group="all"))
        for name, by in group_sets():
            t = nw_table(d, vals, k, by, all_days)
            t["group"] = t[by].astype(str).agg("|".join, axis=1)
            rows.append(t.drop(columns=by).assign(hold=k, group_set=name))
    return pd.concat(rows, ignore_index=True)


def multiday_finalise(m, phase1_include, k_include=None):
    m = m.copy()
    m["missing_label"] = m["group"].str.split("|").apply(lambda parts: any(x in ("na", "nan") for x in parts))
    if k_include is None:
        ok = (m["n"] >= config.HEATMAP_MIN_TRADES) & (m["n_days"] >= config.HEATMAP_MIN_DAYS) & m["value"].str.startswith("hold_dt_")
        k_include = set(map(tuple, m.loc[ok, ["hold", "group_set", "group"]].to_numpy()))
    base = np.array([("buys", gs, g) in phase1_include for gs, g in zip(m["group_set"], m["group"])])
    kin = np.array([(h, gs, g) in k_include for h, gs, g in zip(m["hold"], m["group_set"], m["group"])])
    m["include"] = base & kin & ~m["missing_label"].to_numpy(bool)
    m["p_bh"] = np.nan
    for _, idx in m[m["include"] & (m["group_set"] != "all")].groupby(["hold", "value"]).groups.items():
        m.loc[idx, "p_bh"] = toxicity.bh_fdr(m.loc[idx, "p"])
    return m, k_include


def multiday_quadrants(md, p1, alpha=0.05):
    k = config.RETAIL_MAIN_HOLD
    t = md[(md["hold"] == k) & (md["value"] == f"hold_dt_{k}") & md["include"] & (md["group_set"] != "all")]
    mm = p1[(p1["sample"] == "buys") & (p1["value"] == "mm_neutral_5m")][["group_set", "group", "mean_bps", "p_bh"]]
    q = t[["group_set", "group", "mean_bps", "p_bh", "obs_share"]].rename(columns={"mean_bps": "trader_bps", "p_bh": "trader_p_bh"}) \
        .merge(mm.rename(columns={"mean_bps": "mm_bps", "p_bh": "mm_p_bh"}), on=["group_set", "group"], how="left")
    side = lambda bps, pb: np.where(pb < alpha, np.where(bps > 0, "賺", "虧"), "不確定")
    q["market_maker"] = side(q["mm_bps"], q["mm_p_bh"])
    q["trader"] = side(q["trader_bps"], q["trader_p_bh"])
    q["quadrant"] = "造市商" + q["market_maker"] + "／交易者" + q["trader"]
    return q


def multiday_frame(days, data_dir, rv, tx, iv_cuts):
    data_dir = Path(data_dir)
    d, _ = toxicity.build(days, data_dir)
    keep = ["trade_id", "warrant_id", "datetime", "side", "kind", "kind_sign", "iv", "S_ret_5m", "spot_1s", "tod",
            "delta_bucket", "dte_bucket", "weight", "strike", "ratio", "delta", "S_mid", "close", "pre_mid"]
    d = d[keep].copy()
    ex = pd.concat([pd.read_parquet(data_dir / "labels" / "exit_quotes" / f"{x}.parquet") for x in days], ignore_index=True)
    d = d.merge(ex, on=["trade_id", "datetime", "warrant_id"], how="left", validate="one_to_one")
    closes = daily_closes(data_dir).loc[lambda s: s.index.isin(days)]
    mu = float(closes.pct_change().mean())
    return multiday_metrics(add_conditions(d, rv, tx, iv_cuts), mu), mu


# --- driver ----------------------------------------------------------------------------------

def period_frame(days, data_dir, rv, tx, iv_cuts=None):
    d, _ = toxicity.build(days, data_dir)
    keep = ["datetime", "side", "kind_sign", "iv", "S_ret_5m", "spot_1s", "tod", "delta_bucket", "dte_bucket", "weight",
            "pre_spread_pct", "trunc_5m"] + [f"{p}_{h}" for p in ("RS", "RS_dt") for h in config.RETAIL_HORIZONS] + \
           [f"cost_{k}" for k in config.HEDGE_SCENARIOS]
    d = d[keep].copy()                                   # small frame: the full stage 3 frame is ~1 GB a year
    if iv_cuts is None:                                   # training (2025) tercile cut points
        day = d["datetime"].dt.strftime("%Y-%m-%d")
        gap = (d["iv"] - day.map(rv)).dropna()
        iv_cuts = tuple(np.quantile(gap, [1 / 3, 2 / 3]))
    return metrics(add_conditions(d, rv, tx, iv_cuts)), iv_cuts


def run(data_dir, out_dir=None):
    data_dir = Path(data_dir)
    out_dir = Path(out_dir or data_dir / "results" / "extension")
    out_dir.mkdir(parents=True, exist_ok=True)
    days = sorted(p.stem for p in (data_dir / "panel" / "tsmc_warrant_trades").glob("*.parquet") if config.in_sample(p.stem))
    rv, tx = realised_vol(daily_closes(data_dir)), load_tx(data_dir)
    d25, cuts = period_frame([x for x in days if x <= config.TRAIN_END], data_dir, rv, tx)
    m25, include = finalise(build_map(d25))
    m25.assign(iv_cut_lo=cuts[0], iv_cut_hi=cuts[1]).to_parquet(out_dir / "retail_map_2025.parquet", index=False)
    quadrants(m25).to_parquet(out_dir / "retail_quadrants_2025.parquet", index=False)
    del d25
    test = [x for x in days if x >= config.TEST_START]
    if test:
        d26, _ = period_frame(test, data_dir, rv, tx, cuts)
        m26, _ = finalise(build_map(d26), include)
        m26.to_parquet(out_dir / "retail_map_2026.parquet", index=False)
        quadrants(m26).to_parquet(out_dir / "retail_quadrants_2026.parquet", index=False)


def run_multiday(data_dir, out_dir=None):
    data_dir = Path(data_dir)
    out_dir = Path(out_dir or data_dir / "results" / "extension")
    days = sorted(p.stem for p in (data_dir / "panel" / "tsmc_warrant_trades").glob("*.parquet") if config.in_sample(p.stem))
    rv, tx = realised_vol(daily_closes(data_dir)), load_tx(data_dir)
    p1 = pd.read_parquet(out_dir / "retail_map_2025.parquet")
    cuts = (p1["iv_cut_lo"].iloc[0], p1["iv_cut_hi"].iloc[0])
    include = set(map(tuple, p1.loc[p1["include"], ["sample", "group_set", "group"]].to_numpy()))
    k_inc = None
    for label, ds in [("2025", [x for x in days if x <= config.TRAIN_END]), ("2026", [x for x in days if x >= config.TEST_START])]:
        if not ds:
            continue
        d, mu = multiday_frame(ds, data_dir, rv, tx, cuts)
        md, k_new = multiday_finalise(multiday_map(d), include, k_inc)
        if k_inc is None:                                        # 2026 reuses the 2025 per-k inclusion
            k_inc = k_new
        multiday_summary(d).to_parquet(out_dir / f"retail_multiday_summary_{label}.parquet", index=False)
        md.assign(mu_daily=mu).to_parquet(out_dir / f"retail_multiday_map_{label}.parquet", index=False)
        p1y = pd.read_parquet(out_dir / f"retail_map_{label}.parquet")
        multiday_quadrants(md, p1y).to_parquet(out_dir / f"retail_multiday_quadrants_{label}.parquet", index=False)
        del d


def main(argv=None):
    p = argparse.ArgumentParser(description="Who wins / who loses: market maker vs trader map")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default=None, help="default: <data>/results/extension")
    p.add_argument("--multiday", action="store_true", help="phase 2: multi-day holding (needs labels/exit_quotes)")
    a = p.parse_args(argv)
    run_multiday(a.data, a.out) if a.multiday else run(a.data, a.out)


if __name__ == "__main__":
    main()
