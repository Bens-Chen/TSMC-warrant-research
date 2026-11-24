"""Stage 4: placebo tests and robustness checks (CLAUDE.md §5.2, §6; pre-registered in §10, 2026-11-21).

Training period only. Main metrics: M_dt_<MAIN_HORIZON> (de-trended markout) and net_neutral
(RS_dt - neutral hedge cost), notional-weighted, standard errors clustered by day. A variant is
"robust" when it has the main result's sign and lies inside the main result's 95% interval.

A  placebo: within-day shuffles of side (exact expectation: day equal-weighted mean side x day
   notional-weighted mean return at the trade times), and random-time pseudo trades.
B  sources of M > 0 on both sides: 2330 quote staleness (S_age_s), momentum (past 2330 returns).
C  robustness variants (§6).
D  H4: extreme days, residual-flow tails, short- vs long-dated flow.
E  H3: issuer effects with |delta| x DTE fixed effects.

    python -m wtox.research.robustness --data ../data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from wtox import bs_greeks, warrant_iv
from wtox.research import config, dividends, flow, toxicity
from wtox.research.markout import KEY

MAIN = config.MAIN_HORIZON
METRICS = (f"M_dt_{MAIN}", "net_neutral")


def _main_rows(d):
    """Trades usable at the main horizon, with net_neutral."""
    d = d[~d[f"trunc_{MAIN}"]].copy()
    d["net_neutral"] = d[f"RS_dt_{MAIN}"] - d["cost_neutral"]
    return d


def summary(d, label, by=(), weight="weight"):
    return toxicity.table(_main_rows(d), list(METRICS), by, weight).assign(variant=label)


def robust_flags(rows, base, keys=("value",)):
    """Same sign as the baseline estimate (matched on ``keys``) and inside its 95% interval."""
    keys = list(keys)
    b = base[keys + ["mean_bps", "se_bps"]].rename(columns={"mean_bps": "base_bps", "se_bps": "base_se"})
    x = rows.drop(columns=["base_bps", "base_se"], errors="ignore").merge(b, on=keys, how="left")
    inside = (x["mean_bps"] - x["base_bps"]).abs() <= 1.96 * x["base_se"]
    return x.assign(robust=(np.sign(x["mean_bps"]) == np.sign(x["base_bps"])) & inside)


# --- A: placebo ------------------------------------------------------------------------------

def permutation_placebo(d, B=None, seed=None):
    """Within-day shuffles of side. Returns the actual M, its exact permutation expectation, and the
    permutation distribution summary (one-sided p = share of shuffles >= actual)."""
    B = config.PLACEBO_PERMUTATIONS if B is None else B
    rng = np.random.default_rng(config.PLACEBO_SEED if seed is None else seed)
    dm = _main_rows(d).dropna(subset=[f"M_dt_{MAIN}", "weight"])
    s = dm["side"].to_numpy(float)
    y = dm[f"M_dt_{MAIN}"].to_numpy(float) * s          # side-free return: M = s * y
    w = dm["weight"].to_numpy(float)
    day = pd.factorize(dm["datetime"].dt.normalize())[0]
    W = w.sum()
    actual = (w * s * y).sum() / W
    sbar = pd.Series(s).groupby(day).transform("mean").to_numpy()      # equal-weighted day mean side
    expected = (w * sbar * y).sum() / W
    base = np.argsort(day, kind="stable")
    draws = np.empty(B)
    for b in range(B):
        order = np.lexsort((rng.random(len(s)), day))                    # random order within each day
        sp = np.empty_like(s)
        sp[base] = s[order]
        draws[b] = (w * sp * y).sum() / W
    return pd.DataFrame([{"actual_bps": actual * 1e4, "expected_bps": expected * 1e4,
                          "perm_mean_bps": draws.mean() * 1e4, "perm_p95_bps": np.quantile(draws, 0.95) * 1e4,
                          "p_one_sided": float((1 + (draws >= actual).sum()) / (1 + B)), "B": B}])


def random_time_placebo(d, data_dir, drifts):
    """Pseudo trades at random times (same side, warrant, delta, ratio, pre_mid): M should be ~0."""
    days = d["datetime"].dt.strftime("%Y-%m-%d").unique()
    pl = pd.concat([pd.read_parquet(Path(data_dir) / "labels" / "tsmc_placebo" / f"{x}.parquet") for x in days],
                   ignore_index=True)
    x = d.merge(pl, on=KEY, how="inner", validate="one_to_one")
    x = x[~x[f"trunc_rand_{MAIN}"] & x["S_mid_rand"].notna() & x[f"S_mid_rand_{MAIN}"].notna()].copy()
    dr = x["datetime"].dt.strftime("%Y-%m-%d").map(drifts[MAIN])
    conv = x["side"] * x["delta"] * x["ratio"] / x["pre_mid"]
    x["M_rand"] = conv * (x[f"S_mid_rand_{MAIN}"] - x["S_mid_rand"] - x["S_mid_rand"] * dr)
    return toxicity.table(x, ["M_rand"]).assign(variant="random_time")


# --- B: why M > 0 on both sides --------------------------------------------------------------

def staleness(d):
    # "just_ticked": 2330 printed <= 0.1 s before the trade, so S_mid(t) is current (the warrant quote is
    # then the stale side); "quiet": S_mid(t) may be stale because quotes between prints are unseen
    dm = d.assign(spot_print=np.where(d["S_age_s"] <= config.STALE_SPOT_MAX_AGE_S, "just_ticked", "quiet"))
    return summary(dm, "spot_quote_age", ["spot_print", "direction"])


def wls_cluster(y, X, w, cluster):
    """Weighted least squares with day-clustered SEs (rows scaled by sqrt(w))."""
    sw = np.sqrt(np.asarray(w, float))
    return flow.ols_cluster(np.asarray(y, float) * sw, X.mul(sw, axis=0), cluster)


def momentum(d, drifts=None):
    """M (bps) on the trade's own-direction past 2330 returns; the intercept is M net of momentum.

    Regressor = side x call/put sign x leverage G x (past return - the day's mean return over windows
    of that length), in bps: M scales with G, and the drift is removed as it is from M_dt."""
    dm = _main_rows(d).dropna(subset=[f"S_ret_{w}" for w in config.PAST_RETURN_WINDOWS] + ["leverage"])
    sign = dm["side"] * dm["kind_sign"] * dm["leverage"]  # +: the trade bets on 2330 continuing its move
    day = dm["datetime"].dt.strftime("%Y-%m-%d")
    drift = {w: (day.map(drifts[w]) if drifts is not None and w in drifts else 0.0) for w in config.PAST_RETURN_WINDOWS}
    X = pd.DataFrame({"const": 1.0, **{f"own_ret_{w}_bps": sign * (dm[f"S_ret_{w}"] - drift[w]) * 1e4
                                       for w in config.PAST_RETURN_WINDOWS}}, index=dm.index)
    out = []
    for grp, g in [("all", dm), ("buy", dm[dm["side"] > 0]), ("sell", dm[dm["side"] < 0])]:
        out.append(wls_cluster(g[f"M_dt_{MAIN}"] * 1e4, X.loc[g.index], g["weight"], g["datetime"].dt.normalize())
                   .assign(group=grp))
    return pd.concat(out, ignore_index=True)


# --- C: robustness variants ------------------------------------------------------------------

def recompute(d, drifts, r=config.RISK_FREE, q=0.0):
    """Re-derive IV, delta, leverage, share_equiv and all metrics under other r / q (q may be an array)."""
    x = d.copy()
    qa = np.broadcast_to(np.asarray(q, float), (len(x),)).copy()
    x["iv"] = warrant_iv(x["pre_mid"].to_numpy(), x["S_mid"].to_numpy(), x["strike"].to_numpy(), r, qa,
                         x["T"].to_numpy(), x["ratio"].to_numpy(), x["kind"].to_numpy())
    ok = x["iv"].notna().to_numpy()
    x, qa = x[ok], qa[ok]
    x["delta"] = bs_greeks(x["S_mid"].to_numpy(), x["strike"].to_numpy(), r, qa, x["iv"].to_numpy(),
                           x["T"].to_numpy(), x["kind"].to_numpy())["delta"]
    x["leverage"] = x["delta"].abs() * x["ratio"] * x["S_mid"] / x["pre_mid"]
    x["share_equiv"] = x["side"] * x["volume"] * config.UNITS_PER_LOT * x["ratio"] * x["delta"]
    x = toxicity.trade_metrics(x, r=r, q=qa)
    parts = [toxicity.detrend(g, drifts.loc[day]) for day, g in x.groupby(x["datetime"].dt.strftime("%Y-%m-%d"))]
    return toxicity.add_cuts(toxicity.hedge_costs(pd.concat(parts)))


def unprotected_q(d, divs):
    q = np.zeros(len(d))
    for day, idx in d.groupby(d["datetime"].dt.normalize()).indices.items():
        g = d.iloc[idx]
        q[idx] = dividends.effective_q(day, g["S_mid"].to_numpy(), g["T"].to_numpy(), divs)
    return q


def day_coverage(data_dir):
    w = pd.read_parquet(Path(data_dir) / "results" / "validation" / "coverage_warrant_days.parquet")
    w = w.assign(capped=np.minimum(w["tick_volume"], w["tej_volume"]))
    g = w.groupby(w["date"].dt.strftime("%Y-%m-%d"))
    return g["capped"].sum() / g["tej_volume"].sum()


def variants(d, data_dir, drifts):
    rows = []
    tod = d["datetime"] - d["datetime"].dt.normalize()
    excl = np.zeros(len(d), bool)
    for lo, hi in config.ROBUST_EXCLUDE_TOD:
        excl |= ((tod >= lo) & (tod < hi)).to_numpy()
    rows.append(summary(d[~excl], "exclude_open_close"))
    for r in config.ROBUST_RISK_FREE:
        rows.append(summary(recompute(d, drifts, r=r), f"risk_free_{r:.3f}"))
    rows.append(summary(recompute(d, drifts, q=unprotected_q(d, dividends.load(data_dir))), "q_unprotected"))
    rows.append(summary(d[~d["S_mid_is_trade"] & ~d[f"S_is_trade_{MAIN}"].astype(bool)], "spot_quote_only"))
    tax_hi = {k: (dict(v, tax=config.ROBUST_STOCK_HEDGE_TAX / 2) if v["instrument"] == "stock" else v)
              for k, v in config.HEDGE_SCENARIOS.items()}
    rows.append(summary(toxicity.hedge_costs(d.copy(), tax_hi), f"stock_hedge_tax_{config.ROBUST_STOCK_HEDGE_TAX:.3f}"))
    for x in config.ROBUST_LARGE_ORDER:
        rows.append(summary(d.assign(large=np.where(d["order_volume"] >= x, f">={x}", f"<{x}")), f"large_{x}", ["large"]))
    rows.append(summary(d, "spot_move_5s", ["spot_5s"]).assign(base_variant="spot_move_1s"))
    size = np.where(d["side"] > 0, d["prev_ask_volume"], d["prev_bid_volume"])
    issuer_like = d["prev_in_force"] & (size > 0) & (np.mod(size, config.ISSUER_LIKE_SIZE_MULTIPLE) == 0)
    rows.append(summary(d[issuer_like], "counterparty_issuer_like"))
    med = d.groupby([d["datetime"].dt.normalize(), "warrant_id"])["pre_spread_pct"].transform("median")
    retail_like = (d["order_volume"] <= config.RETAIL_LIKE_MAX_LOTS) & (d["pre_spread_pct"] < config.RETAIL_LIKE_SPREAD_RATIO * med)
    rows.append(summary(d[~retail_like], "counterparty_drop_retail_like"))
    rows.append(summary(d.assign(w1=1.0), "equal_weight", ["delta_bucket"], weight="w1").assign(base_variant="delta_bucket"))
    cov = day_coverage(data_dir)
    good = cov[cov >= config.ROBUST_MIN_DAY_COVERAGE].index
    rows.append(summary(d[d["datetime"].dt.strftime("%Y-%m-%d").isin(good)], "coverage_days"))
    out = pd.concat(rows, ignore_index=True)
    out["p_bh"] = np.nan
    for v in METRICS:
        m = out["value"] == v
        out.loc[m, "p_bh"] = toxicity.bh_fdr(out.loc[m, "p"])
    return out


def flag_variants(out, d):
    """Robust flags against the matching baseline: pooled main for subsets; the same cut of the main
    analysis for split variants (5s vs the 1s cut, equal vs notional weight by |delta| bucket). The
    large-order thresholds are alternative cuts with no main counterpart: flag left empty."""
    main = summary(d, "main")
    if "base_variant" not in out:
        out["base_variant"] = np.nan
    parts = [robust_flags(out[out["base_variant"].isna() & out["large"].isna()] if "large" in out
                          else out[out["base_variant"].isna()], main)]
    s1 = summary(d, "spot_move_1s", ["spot_1s"]).rename(columns={"spot_1s": "spot_5s"})
    parts.append(robust_flags(out[out["base_variant"] == "spot_move_1s"], s1, ("value", "spot_5s")))
    nb = summary(d, "delta_bucket", ["delta_bucket"])
    parts.append(robust_flags(out[out["base_variant"] == "delta_bucket"], nb, ("value", "delta_bucket")))
    if "large" in out:
        parts.append(out[out["large"].notna()].assign(robust=np.nan))
    return pd.concat(parts, ignore_index=True)


# --- D: H4 -----------------------------------------------------------------------------------

def h4_checks(data_dir):
    data_dir = Path(data_dir)
    days = sorted(p.stem for p in (data_dir / "flow").glob("*.parquet") if p.stem <= config.TRAIN_END)
    d = flow.h4_frame(days, data_dir, config.H4_MAIN_HORIZON)
    out = [flow.regress(d).assign(check="main")]
    # day return: close-to-close of the 13:25 mid (needs the previous day); day flow: |net delta flow|
    # summed over non-overlapping k-windows, over the 2330 shares traded in them
    close = pd.Series({x: pd.read_parquet(data_dir / "labels" / "tsmc_grid" / f"{x}.parquet", columns=["S_mid_close"])
                       ["S_mid_close"].iloc[0] for x in days})
    day_ret = (close / close.shift(1) - 1).abs().reindex(d["day"].unique()).dropna()
    step = int(config.H4_FLOW_WINDOW / config.H4_GRID)
    nonover = d[((d["tau"] - d["tau"].dt.normalize() - config.H4_FIRST_TAU) // config.H4_GRID) % step == 0]
    g = nonover.groupby("day")
    day_flow = (g["F"].sum().abs() / g["stock_shares"].sum()).dropna()
    for name, series in [("drop_extreme_return_days", day_ret), ("drop_extreme_flow_days", day_flow)]:
        keep = series[series <= series.quantile(config.H4_EXTREME_DAY_QUANTILE)].index
        out.append(flow.regress(d[d["day"].isin(keep)]).assign(check=name))
    d = d.assign(F_short_norm=d["F_short"] / d["denom"], F_long_norm=d["F_long"] / d["denom"])
    out.append(flow.regress(d, ("F_short_norm", "F_long_norm")).assign(check="short_vs_long"))
    reg = pd.concat(out, ignore_index=True)
    # tails of the residual flow (flow net of its projection on the controls, training fit)
    X = pd.concat([pd.Series(1.0, index=d.index, name="const"), (d["ret_past"] * 1e4).rename("ret_past_bps"),
                   d["signed_norm"], pd.get_dummies(d["tod"], prefix="tod", drop_first=True, dtype=float)], axis=1)
    beta = np.linalg.lstsq(X.to_numpy(float), d["F_norm"].to_numpy(float), rcond=None)[0]
    d["F_resid"] = d["F_norm"] - X.to_numpy(float) @ beta
    edges = d["F_resid"].quantile(list(config.H4_TAIL_EDGES)).to_numpy().copy()
    edges[0], edges[-1] = -np.inf, np.inf
    q = list(config.H4_TAIL_EDGES)
    d["tail"] = pd.cut(d["F_resid"], edges, labels=[f"{a:.0%}–{b:.0%}" for a, b in zip(q[:-1], q[1:])])
    tails = []
    for grp, x in d.groupby("tail", observed=True):
        m, se, n, G = toxicity.cluster_mean(x["y_bps"] / 1e4, np.ones(len(x)), x["day"])
        tails.append({"tail": str(grp), "mean_y_bps": m * 1e4, "se_bps": se * 1e4, "n": n, "n_days": G})
    return reg, pd.DataFrame(tails)


# --- E: H3 -----------------------------------------------------------------------------------

def h3_issuers(d):
    dm = _main_rows(d).dropna(subset=["delta_bucket", "dte_bucket"])
    cell = dm["delta_bucket"].astype(str) + "|" + dm["dte_bucket"].astype(str)
    base = dm["issuer"].value_counts().index[0]
    X = pd.concat([pd.Series(1.0, index=dm.index, name="const"),
                   pd.get_dummies(dm["issuer"], prefix="iss", dtype=float).drop(columns=f"iss_{base}"),
                   pd.get_dummies(cell, prefix="cell", drop_first=True, dtype=float)], axis=1)
    r = wls_cluster(dm[f"M_dt_{MAIN}"] * 1e4, X, dm["weight"], dm["datetime"].dt.normalize())
    iss = r[r["term"].str.startswith("iss_")].assign(issuer=lambda x: x["term"].str[4:])
    iss = pd.concat([iss, pd.DataFrame([{"issuer": base, "coef": 0.0, "term": "base"}])], ignore_index=True)
    half = dm.groupby("issuer").apply(lambda g: np.average(g["pre_spread_pct"] / 2, weights=g["weight"]) * 1e4)
    iss["half_spread_bps"] = iss["issuer"].map(half)
    iss["n"] = iss["issuer"].map(dm["issuer"].value_counts())
    rho, p = stats.spearmanr(iss["coef"], iss["half_spread_bps"])
    return iss.assign(spearman_rho=rho, spearman_p=p, base_issuer=base)


# --- driver ----------------------------------------------------------------------------------

def load_drifts(days, data_dir):
    for x in days:
        config.check_unlocked(x)
    return pd.DataFrame({x: toxicity.day_drift(pd.read_parquet(Path(data_dir) / "labels" / "tsmc_grid" / f"{x}.parquet"))
                         for x in days}).T


def run(data_dir, out_dir=None):
    data_dir = Path(data_dir)
    out_dir = Path(out_dir or data_dir / "results" / "stage4")
    days = toxicity.stage3_days(data_dir / "panel" / "tsmc_warrant_trades")
    d, _ = toxicity.build(days, data_dir)
    drifts = load_drifts(days, data_dir)
    main = summary(d, "main")
    res = {"main": main, "placebo_permutation": permutation_placebo(d),
           "placebo_random_time": random_time_placebo(d, data_dir, drifts),
           "staleness": staleness(d), "momentum": momentum(d, drifts),
           "variants": flag_variants(variants(d, data_dir, drifts), d), "h3_issuers": h3_issuers(d)}
    res["h4_checks"], res["h4_tails"] = h4_checks(data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for k, v in res.items():
        v.to_parquet(out_dir / f"{k}.parquet", index=False)
    return res


def main(argv=None):
    p = argparse.ArgumentParser(description="Stage 4 placebo and robustness (training period)")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default=None, help="default: <data>/results/stage4")
    a = p.parse_args(argv)
    run(a.data, a.out)


if __name__ == "__main__":
    main()
