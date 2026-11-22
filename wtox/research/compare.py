"""Cross-issuer comparison (docs/decisions.md, 2026-11-22, registered before running).

Question: among comparable warrants (same day, call/put, |delta| bucket, DTE bucket = "peer group"), does
buying the one that looked cheapest on the previous trading day (IV premium, spread premium vs the peer
median) lower the retail buyer's later holding cost? And which issuer is cheapest for retail, compared with
same-day same-type warrants? A cost-reduction question, not a profit strategy. Exploratory.

"Cheap" uses only day d-1 information (each warrant's notional-weighted median at-trade IV and spread
on d-1). Outcomes are retail buys: ES at the trade, the intraday 5m trader net (phase 1), and the
multi-day structural cost hold_resid_k (phase 2, corrected definition). Comparisons are within peer
group x day (fixed effects by demeaning), notional-weighted; day-clustered SE for intraday outcomes and
Newey-West with lag k trading days for k-day holds.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox.research import config, retail, toxicity
from wtox.research.coverage import dte_bucket

PEER = ["day", "kind", "peer_delta", "peer_dte"]          # peer labels come from day d-1 (known before d opens)
OUTCOMES = {"ES": 0, "trader_5m": 0, "hold_resid_1": 1, "hold_resid_5": 5}   # outcome -> NW lag (0 = day cluster)
RANKS = ("iv_prem", "spread_prem")


# --- previous-day warrant statistics ------------------------------------------------------------

def wmedian(x, w):
    x, w = np.asarray(x, float), np.asarray(w, float)
    ok = ~np.isnan(x) & ~np.isnan(w) & (w > 0)
    if not ok.any():
        return np.nan
    x, w = x[ok], w[ok]
    o = np.argsort(x, kind="mergesort")
    c = np.cumsum(w[o])
    return float(x[o][np.searchsorted(c, 0.5 * c[-1])])


def day_stats(panel):
    """Per warrant on one day: notional-weighted median at-trade IV, % spread, |delta| and days to expiry over
    trades with an at-trade quote, and the peer labels (kind, |delta| bucket, DTE bucket) they imply."""
    p = panel[panel["pre_mid"].notna() & panel["iv"].notna() & (panel["notional"] > 0)]
    cols = ["warrant_id", "kind", "prev_iv", "prev_spread", "peer_delta", "peer_dte"]
    if p.empty:
        return pd.DataFrame(columns=cols)
    rows = [(w, g["kind"].iloc[0], wmedian(g["iv"], g["notional"]), wmedian(g["pre_spread_pct"], g["notional"]),
             wmedian(g["delta"].abs(), g["notional"]), wmedian(g["T"], g["notional"]) * config.DAYS_PER_YEAR)
            for w, g in p.groupby("warrant_id", sort=True)]
    s = pd.DataFrame(rows, columns=["warrant_id", "kind", "prev_iv", "prev_spread", "abs_delta", "dte"])
    s["peer_delta"] = pd.cut(s["abs_delta"], list(config.DELTA_BUCKET_EDGES), labels=list(config.DELTA_BUCKET_LABELS)).astype(str)
    s["peer_dte"] = dte_bucket(s["dte"]).astype(str)
    return s[cols]


def rank_prev(prev):
    """Premiums and terciles among ALL warrants with d-1 data in each d-1 peer group (>= CMP_MIN_PEERS):
    the whole benchmark is known before day d opens."""
    w = prev.dropna(subset=["prev_iv", "prev_spread"]).copy()
    key = ["kind", "peer_delta", "peer_dte"]
    w = w[(w["peer_delta"] != "nan") & (w["peer_dte"] != "nan")]
    w["n_peer"] = w.groupby(key)["warrant_id"].transform("size")
    w = w[w["n_peer"] >= config.CMP_MIN_PEERS].copy()
    g = w.groupby(key)
    for r, src in zip(RANKS, ("prev_iv", "prev_spread")):
        w[r] = w[src] - g[src].transform("median")
        sd = g[r].transform("std")
        w[f"{r}_z"] = (w[r] / sd).where(sd > 0)
        pct = g[r].rank(pct=True, method="average")
        w[f"{r}_tercile"] = np.select([pct <= 1 / 3, pct > 2 / 3], ["cheap", "expensive"], "middle")
    w["spread_tie"] = w["spread_prem"] == 0
    return w.drop(columns=["prev_iv", "prev_spread"])


def premiums(d, prev):
    """d: one day's buys. prev: day_stats of the previous trading day. Adds the d-1 peer labels, premiums,
    z-scores and terciles by warrant (trades of warrants without d-1 data stay unranked)."""
    r = rank_prev(prev).drop(columns=["kind"])
    return d.merge(r, on="warrant_id", how="left", validate="many_to_one")


# --- estimation ---------------------------------------------------------------------------------

def fe_wls(y, X, w, fe, day, lag, all_days=None):
    """WLS of y on X with fixed effects ``fe`` (absorbed by weighted demeaning). SE: day scores, Bartlett
    over ``lag`` trading days (0 = clustered by day); ``all_days`` fills days without observations."""
    df = pd.DataFrame(X).astype(float)
    cols = list(df.columns)
    df["y"], df["w"], df["fe"], df["day"] = np.asarray(y, float), np.asarray(w, float), np.asarray(fe), np.asarray(day)
    df = df.dropna()
    df = df[df["w"] > 0]
    if df.empty:
        return pd.DataFrame(columns=["coef", "se", "n", "n_days"])
    vv = cols + ["y"]
    wsum = df.groupby("fe")["w"].transform("sum")
    for c in vv:
        df[c] = df[c] - (df[c] * df["w"]).groupby(df["fe"]).transform("sum") / wsum
    Xm, ym, wv = df[cols].to_numpy(), df["y"].to_numpy(), df["w"].to_numpy()
    A = Xm.T @ (Xm * wv[:, None])
    keep = np.abs(np.diag(A)) > 1e-12
    Xm, A, cols = Xm[:, keep], A[np.ix_(keep, keep)], [c for c, k in zip(cols, keep) if k]
    Ai = np.linalg.pinv(A)                                   # pinv: no crash on a collinear control
    beta = Ai @ (Xm.T @ (wv * ym))
    e = ym - Xm @ beta
    S = pd.DataFrame(Xm * (wv * e)[:, None]).groupby(df["day"].to_numpy()).sum().sort_index()
    G = len(S)
    if all_days is not None:
        S = S.reindex(all_days, fill_value=0.0)
    S = S.to_numpy()
    V = S.T @ S
    for l in range(1, min(lag, len(S) - 1) + 1):
        Gl = S[l:].T @ S[:-l]
        V += (1 - l / (lag + 1)) * (Gl + Gl.T)
    cov = Ai @ V @ Ai * (G / (G - 1) if G > 1 else np.nan)
    return pd.DataFrame({"coef": beta, "se": np.sqrt(np.diag(cov)), "n": len(df), "n_days": G}, index=cols), cov


def _p(t, G):
    from scipy import stats
    return 2 * stats.t.sf(abs(t), max(G - 1, 1)) if np.isfinite(t) else np.nan


def tercile_tests(d, all_days):
    """Cheap - expensive per ranking and outcome: base (peer x day FE) and with |delta|, moneyness controls;
    plus the joint regression on both z-scored premiums."""
    rows = []
    fe = d.groupby(PEER, dropna=False, observed=True).ngroup().to_numpy()
    day = d["day"].to_numpy()
    for y, lag in OUTCOMES.items():
        for r in RANKS:
            t = d[f"{r}_tercile"]
            base = {"cheap": (t == "cheap").astype(float), "expensive": (t == "expensive").astype(float)}
            ok = t.notna().to_numpy()
            for spec, X in [("base", base), ("controls", {**base, "abs_delta": d["delta"].abs(), "moneyness": d["moneyness"]})]:
                X = {k: np.where(ok, v, np.nan) for k, v in X.items()}
                res = fe_wls(d[y], X, d["weight"], fe, day, lag, all_days)
                if not isinstance(res, tuple):
                    continue
                tab, cov = res
                if not {"cheap", "expensive"} <= set(tab.index):
                    continue
                i, j = list(tab.index).index("cheap"), list(tab.index).index("expensive")
                diff = tab.loc["cheap", "coef"] - tab.loc["expensive", "coef"]
                se = np.sqrt(cov[i, i] + cov[j, j] - 2 * cov[i, j])
                rows.append({"outcome": y, "ranking": r, "spec": spec, "cheap_minus_expensive_bps": diff * 1e4,
                             "se_bps": se * 1e4, "t": diff / se, "p": _p(diff / se, tab["n_days"].iloc[0]),
                             "n": int(tab["n"].iloc[0]), "n_days": int(tab["n_days"].iloc[0])})
        X = {"iv_prem_z": d["iv_prem_z"], "spread_prem_z": d["spread_prem_z"]}
        res = fe_wls(d[y], X, d["weight"], fe, day, lag, all_days)
        if isinstance(res, tuple):
            tab, _ = res
            for c in tab.index:
                tt = tab.loc[c, "coef"] / tab.loc[c, "se"]
                rows.append({"outcome": y, "ranking": c, "spec": "joint_per_1sd", "cheap_minus_expensive_bps": tab.loc[c, "coef"] * 1e4,
                             "se_bps": tab.loc[c, "se"] * 1e4, "t": tt, "p": _p(tt, tab.loc[c, "n_days"]),
                             "n": int(tab.loc[c, "n"]), "n_days": int(tab.loc[c, "n_days"])})
    out = pd.DataFrame(rows)
    out["p_bh"] = np.nan
    for _, idx in out.groupby("outcome").groups.items():
        out.loc[idx, "p_bh"] = toxicity.bh_fdr(out.loc[idx, "p"])
    return out


def premium_correlation(d):
    w = d.dropna(subset=["iv_prem_z", "spread_prem_z"]).drop_duplicates(PEER + ["warrant_id"])
    return pd.DataFrame([{"spearman_iv_vs_spread_prem": w["iv_prem_z"].corr(w["spread_prem_z"], method="spearman"),
                          "n_warrant_peer_days": len(w)}])


def issuer_table(d, issuers, all_days):
    """Issuer effects vs the notional-weighted average issuer, within peer group x day (fixed effects),
    on the ranked sample (peer groups with >= CMP_MIN_PEERS warrants): WLS of the outcome on issuer dummies
    (first issuer omitted) with peer x day FE; each effect is then re-expressed as a deviation from the
    share-weighted average of all issuers (a linear contrast, SE from the full covariance). ``issuers``:
    the 2025 list; others pooled as "其他"."""
    d = d[d["n_peer"].notna()].copy()
    lab = d["issuer"].where(d["issuer"].isin(issuers), "其他")
    names = list(issuers) + (["其他"] if (lab == "其他").any() else [])
    fe = d.groupby(PEER, observed=True).ngroup().to_numpy()
    rows = []
    for y, lag in OUTCOMES.items():
        ok = d[y].notna() & (d["weight"] > 0)
        share = np.array([d.loc[ok & (lab == n), "weight"].sum() for n in names]) / d.loc[ok, "weight"].sum()
        X = {n: (lab == n).astype(float).to_numpy() for n in names[1:]}
        res = fe_wls(d[y], X, d["weight"], fe, d["day"].to_numpy(), lag, all_days)
        if not isinstance(res, tuple):
            continue
        tab, cov = res
        b = np.array([0.0] + [tab.loc[n, "coef"] if n in tab.index else np.nan for n in names[1:]])
        idx = {n: i for i, n in enumerate(tab.index)}
        for i, n in enumerate(names):
            L = -share.copy()
            L[i] += 1.0                                                  # effect_i - sum_j share_j effect_j
            Lr = np.zeros(len(tab))
            for j, m in enumerate(names[1:], start=1):
                if m in idx:
                    Lr[idx[m]] = L[j]
            est = float(L @ np.nan_to_num(b))
            se = float(np.sqrt(Lr @ cov @ Lr))
            t = est / se if se > 0 else np.nan
            rows.append({"outcome": y, "issuer": n, "vs_avg_bps": est * 1e4, "se_bps": se * 1e4, "t": t,
                         "p": _p(t, tab["n_days"].iloc[0]), "share_notional": float(share[i]),
                         "n": int(tab["n"].iloc[0]), "n_days": int(tab["n_days"].iloc[0])})
    out = pd.DataFrame(rows)
    out["p_bh"] = np.nan
    for _, ix in out.groupby("outcome").groups.items():
        out.loc[ix, "p_bh"] = toxicity.bh_fdr(out.loc[ix, "p"])
    prem = d.assign(issuer=lab).dropna(subset=["iv_prem"]).groupby("issuer").apply(
        lambda g: pd.Series({"mean_iv_prem_pts": np.average(g["iv_prem"], weights=g["weight"]) * 100,
                             "mean_spread_prem_bps": np.average(g["spread_prem"], weights=g["weight"]) * 1e4}),
        include_groups=False).reset_index()
    return out.merge(prem, on="issuer", how="left")


def issuer_same_side_iv(data_dir, days, issuers):
    """Descriptive: mean same-side IV change between consecutive same-side trades (stage 2 file), by issuer
    and side, day-clustered."""
    f = Path(data_dir) / "results" / "validation" / "same_side_iv.parquet"
    if not f.exists():
        return pd.DataFrame()
    s = pd.read_parquet(f, columns=["issuer", "side", "d_iv", "day"])
    s = s[s["day"].astype(str).isin(days)].copy()
    s["issuer"] = s["issuer"].where(s["issuer"].isin(issuers), "其他")
    rows = []
    for (iss, side), g in s.groupby(["issuer", "side"]):
        m, se, n, G = retail.nw_mean(g["d_iv"], np.ones(len(g)), g["day"], 0)
        rows.append({"issuer": iss, "side": int(side), "mean_d_iv_pts": m * 100, "se_pts": se * 100, "n": n, "n_days": G})
    return pd.DataFrame(rows)


# --- driver ---------------------------------------------------------------------------------------

def frame(days, all_days, data_dir):
    """Retail buys with outcomes and previous-day premiums. ``all_days``: every in-sample day (for d-1)."""
    data_dir = Path(data_dir)
    d, _ = toxicity.build(days, data_dir)
    keep = ["trade_id", "warrant_id", "datetime", "side", "kind", "kind_sign", "issuer", "iv", "moneyness", "delta",
            "delta_bucket", "dte_bucket", "weight", "strike", "ratio", "S_mid", "close", "pre_mid", "pre_spread_pct",
            "ES", "trunc_5m"] + [f"{p}_{h}" for p in ("RS", "RS_dt") for h in config.RETAIL_HORIZONS] + \
           [f"cost_{k}" for k in config.HEDGE_SCENARIOS]
    d = retail.metrics(d[keep].copy())
    ex = pd.concat([pd.read_parquet(data_dir / "labels" / "exit_quotes" / f"{x}.parquet") for x in days], ignore_index=True)
    if not {"S_bid_1", "gap_1"} <= set(ex.columns):
        raise RuntimeError("exit_quotes predate the spot-at-bid / gap correction: run python -m wtox.research.markout")
    d = d.merge(ex, on=["trade_id", "datetime", "warrant_id"], how="left", validate="one_to_one")
    d = retail.multiday_metrics(d, 0.0)                     # buys; hold_resid_k does not depend on the drift
    d["day"] = d["datetime"].dt.strftime("%Y-%m-%d")
    out = []
    for day, g in d.groupby("day", sort=True):
        i = all_days.index(day)
        if i == 0:
            continue
        pp = data_dir / "panel" / "tsmc_warrant_trades" / f"{all_days[i - 1]}.parquet"
        prev = day_stats(pd.read_parquet(pp, columns=["warrant_id", "kind", "pre_mid", "iv", "notional", "pre_spread_pct",
                                                      "delta", "T"]))
        out.append(premiums(g, prev))
    return pd.concat(out, ignore_index=True)


def run(data_dir, out_dir=None):
    data_dir = Path(data_dir)
    out_dir = Path(out_dir or data_dir / "results" / "extension")
    out_dir.mkdir(parents=True, exist_ok=True)
    all_days = sorted(p.stem for p in (data_dir / "panel" / "tsmc_warrant_trades").glob("*.parquet") if config.in_sample(p.stem))
    issuers = None
    for label, ds in [("2025", [x for x in all_days if x <= config.TRAIN_END]), ("2026", [x for x in all_days if x >= config.TEST_START])]:
        if not ds:
            continue
        d = frame(ds, all_days, data_dir)
        if issuers is None:                                    # 2026 reuses the 2025 issuer list
            share = d.groupby("issuer")["weight"].sum() / d["weight"].sum()
            issuers = sorted(share[share >= config.CMP_MIN_ISSUER_SHARE].index, key=lambda x: -share[x])
        days_idx = np.array(sorted(d["day"].unique()))
        cover = d.groupby(d["iv_prem_tercile"].notna())["weight"].sum() / d["weight"].sum()
        wp = d.dropna(subset=["n_peer"]).drop_duplicates(["day", "warrant_id"])
        tercile_tests(d, days_idx).assign(ranked_share=float(cover.get(True, 0.0)),
                                          spread_tie_share=float(wp["spread_tie"].mean())) \
            .to_parquet(out_dir / f"compare_terciles_{label}.parquet", index=False)
        premium_correlation(d).to_parquet(out_dir / f"compare_premium_corr_{label}.parquet", index=False)
        issuer_table(d, issuers, days_idx).to_parquet(out_dir / f"compare_issuers_{label}.parquet", index=False)
        issuer_same_side_iv(data_dir, ds, issuers).to_parquet(out_dir / f"compare_issuer_iv_change_{label}.parquet", index=False)
        del d


def main(argv=None):
    p = argparse.ArgumentParser(description="Cross-issuer comparison: does picking yesterday's cheapest peer lower holding cost?")
    p.add_argument("--data", default="../data")
    a = p.parse_args(argv)
    run(a.data)


if __name__ == "__main__":
    main()
