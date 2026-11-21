"""Stage 5: out-of-sample evaluation (CLAUDE.md §5.4, §5.5; pre-registered in §10, 2026-11-21).

Everything is fitted on the training days and applied once to the test days:

1. toxicity score: notional-weighted linear model of M_dt_<h> on trade-time features; test trades are
   sorted into quintiles by the training cut points (monotonicity, Q5 - Q1, out-of-sample R²).
2. break-even spread and pricing gap per |delta| x DTE x notional cell; the cell list is fixed by the
   training sample; sign agreement and the pooled result of the training-negative cells.
3. H4 trading: residual flow (training projection), static training 5% / 95% thresholds, a 1/5
   position per trigger held h, costs per side (2330 half spread or one tick, futures tax, fee).
4. replication of the stage 3 main estimates: same sign and p < 0.05 in the test period (for items
   significant in training), and parameter stability |Δθ| / sqrt(SE1² + SE2²) < 1.96.

The real run needs config.TEST_UNLOCKED (config.check_unlocked raises otherwise) and a clean git tree;
``--dry-run`` splits 2025 at config.DRY_RUN_SPLIT instead and never touches 2026.

    python -m wtox.research.oos --data ../data --dry-run
    python -m wtox.research.oos --data ../data            # once, after commit and unlocking
"""

import argparse
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from wtox.research import config, flow, robustness, toxicity

H = config.MAIN_HORIZON
TARGET = config.SCORE_TARGET
KEY_COLS = ["trade_id", "datetime", "warrant_id"]


# --- days ------------------------------------------------------------------------------------

def split_days(data_dir, dry_run):
    days = sorted(p.stem for p in (Path(data_dir) / "panel" / "tsmc_warrant_trades").glob("*.parquet")
                  if config.in_sample(p.stem))
    if dry_run:
        train = [d for d in days if d <= config.DRY_RUN_SPLIT]
        test = [d for d in days if config.DRY_RUN_SPLIT < d <= config.TRAIN_END]
    else:
        train = [d for d in days if d <= config.TRAIN_END]
        test = [d for d in days if d >= config.TEST_START]
    return train, test


# --- 1. toxicity score -----------------------------------------------------------------------

def fit_stats(train, drifts):
    """Everything the feature map learns from the training sample."""
    mom_drift = {w: float(drifts[w].mean()) for w in config.PAST_RETURN_WINDOWS}
    raw = _raw_features(train, mom_drift)
    lo, hi = config.SCORE_WINSOR_Q
    clip = {c: (raw[c].quantile(lo), raw[c].quantile(hi)) for c in ["half_spread", "mom_1m", "mom_5m"]}
    levels = {c: sorted(train[c].dropna().astype(str).unique()) for c in ["cell", "tod", "issuer"]}
    return {"mom_drift": mom_drift, "clip": clip, "levels": levels}


def _raw_features(d, mom_drift):
    sign = d["side"] * d["kind_sign"] * d["leverage"]
    age = d["prev_quote_age_s"]
    return pd.DataFrame({
        "log_size": np.log(d["order_volume"].astype(float)),
        "spot_fav": (d[f"spot_{config.SPOT_MOVE_WINDOW}"] == "favourable").astype(float),
        "spot_adv": (d[f"spot_{config.SPOT_MOVE_WINDOW}"] == "adverse").astype(float),
        "spot_ticked": (d["S_age_s"] <= config.STALE_SPOT_MAX_AGE_S).astype(float),
        **{f"mom_{w}": sign * (d[f"S_ret_{w}"] - mom_drift[w]) * 1e4 for w in config.PAST_RETURN_WINDOWS},
        "buy": (d["side"] > 0).astype(float), "put": (d["kind"] == "put").astype(float),
        "half_spread": d["pre_spread_pct"] / 2 * 1e4,
        "prev_in_force": d["prev_in_force"].astype(float),
        "log_age": np.log1p(age.clip(0, config.SCORE_AGE_CLIP_S)).fillna(0.0),
        "no_prev": age.isna().astype(float),
    }, index=d.index)


def design(d, st):
    """Design matrix: numeric features (clipped with training bounds) + baseline-coded dummies."""
    x = _raw_features(d, st["mom_drift"])
    for c, (lo, hi) in st["clip"].items():
        x[c] = x[c].clip(lo, hi)
    x = x.fillna(0.0)
    parts = [pd.Series(1.0, index=d.index, name="const"), x]
    for c, lv in st["levels"].items():
        v = d[c].astype(str)
        cat = pd.Categorical(v.where(v.isin(lv)), categories=lv)          # unseen level -> all dummies 0
        parts.append(pd.get_dummies(cat, prefix=c, dtype=float).iloc[:, 1:].set_index(d.index))
    return pd.concat(parts, axis=1)


def add_cell(d):
    return d.assign(cell=d["delta_bucket"].astype(str) + "|" + d["dte_bucket"].astype(str))


def fit_score(train, st):
    X = design(train, st)
    sw = np.sqrt(train["weight"].to_numpy(float))
    beta = np.linalg.lstsq(X.to_numpy(float) * sw[:, None], train[TARGET].to_numpy(float) * 1e4 * sw, rcond=None)[0]
    return pd.Series(beta, index=X.columns)


def predict(d, st, beta):
    return design(d, st).to_numpy(float) @ beta.to_numpy()


def score_eval(train, test, st, beta):
    ptr, pte = predict(train, st, beta), predict(test, st, beta)
    cuts = np.quantile(ptr, np.linspace(0, 1, config.SCORE_QUANTILES + 1))
    cuts[0], cuts[-1] = -np.inf, np.inf
    out = {}
    for name, d, p in [("train", train, ptr), ("test", test, pte)]:
        d = d.assign(score=p, quintile=pd.cut(p, cuts, labels=[f"Q{i}" for i in range(1, config.SCORE_QUANTILES + 1)]))
        out[f"quintiles_{name}"] = toxicity.table(d, [TARGET], ["quintile"]).assign(sample=name)
        q = d[d["quintile"].isin(["Q1", f"Q{config.SCORE_QUANTILES}"])]
        X = pd.DataFrame({"const": 1.0, "top": (q["quintile"] == f"Q{config.SCORE_QUANTILES}").astype(float)}, index=q.index)
        out[f"q5_minus_q1_{name}"] = robustness.wls_cluster(q[TARGET] * 1e4, X, q["weight"], q["datetime"].dt.normalize()) \
            .query("term == 'top'").assign(sample=name)
    w, y = test["weight"].to_numpy(float), test[TARGET].to_numpy(float) * 1e4
    ybar_train = np.average(train[TARGET].to_numpy(float) * 1e4, weights=train["weight"])
    r2 = 1 - (w * (y - pte) ** 2).sum() / (w * (y - ybar_train) ** 2).sum()
    out["r2"] = pd.DataFrame([{"r2_oos": r2, "n_test": len(test), "n_train": len(train)}])
    out["coefficients"] = beta.rename("coef").reset_index().rename(columns={"index": "term"})
    return out


# --- 2. break-even spread and pricing gap ----------------------------------------------------

def heat_cells(d):
    # bucket by the ORDER's notional (all fills of one order together), consistent with H2's order_volume
    order_notional = d.groupby([d["datetime"], d["warrant_id"]])["notional"].transform("sum") if "warrant_id" in d else d["notional"]
    nb = pd.cut(order_notional, list(config.HEATMAP_NOTIONAL_EDGES), labels=list(config.HEATMAP_NOTIONAL_LABELS), right=False)
    d = d.assign(notional_bucket=nb)
    for k in config.HEDGE_SCENARIOS:
        d[f"gap_{k}"] = d["ES"] - d[TARGET] - d[f"cost_{k}"]
    return d


CELL = ["delta_bucket", "dte_bucket", "notional_bucket"]


def heatmap(train, test):
    tr, te = heat_cells(train), heat_cells(test)
    vals = ["ES", TARGET] + [f"cost_{k}" for k in config.HEDGE_SCENARIOS] + [f"gap_{k}" for k in config.HEDGE_SCENARIOS]
    a = toxicity.table(tr, vals, CELL).assign(sample="train")
    keep = a[a["value"] == "ES"]
    keep = keep[(keep["n"] >= config.HEATMAP_MIN_TRADES) & (keep["n_days"] >= config.HEATMAP_MIN_DAYS)][CELL]
    b = toxicity.table(te, vals, CELL).assign(sample="test")
    grid = keep.merge(pd.DataFrame({"value": vals}), how="cross")         # every kept cell x value, even if absent in test
    a = grid.merge(a, on=CELL + ["value"], how="left")
    b = grid.merge(b, on=CELL + ["value"], how="left").assign(sample="test")
    price = lambda d: d.groupby(CELL, observed=True).apply(lambda g: np.average(g["close"], weights=g["weight"]))
    for t, src in [(a, tr), (b, te)]:
        t["gap_twd_per_lot"] = np.where(t["value"].str.startswith("gap_"),
                                        t["mean_bps"] * 1e-4 * t.set_index(CELL).index.map(price(src)).to_numpy() * config.UNITS_PER_LOT,
                                        np.nan)
    # out of sample: 2026 effective spread against the 2025 break-even (the spread advice), per trade
    be = a[a["value"].isin([TARGET, "cost_neutral"])].groupby(CELL, observed=True)["mean_bps"].sum() / 1e4
    te = te.join(be.rename("be_train"), on=CELL)
    te["gap_vs_train_be"] = te["ES"] - te["be_train"]
    adv = toxicity.table(te[te["be_train"].notna()], ["gap_vs_train_be"], CELL).assign(sample="test")
    note = te.groupby(CELL, observed=True)["notional"].sum().rename("test_notional").reset_index()
    b = b.merge(note, on=CELL, how="left")
    b = pd.concat([b, grid[CELL].drop_duplicates().merge(adv, on=CELL, how="left").assign(value="gap_vs_train_be", sample="test")],
                  ignore_index=True)
    ga = a[a["value"] == "gap_neutral"].set_index(CELL)["mean_bps"]
    gb = b[b["value"] == "gap_neutral"].set_index(CELL)["mean_bps"]
    both = pd.concat([ga.rename("train"), gb.rename("test")], axis=1).dropna()
    neg = ga[ga < 0].index
    te_neg = te.set_index(CELL).loc[lambda x: x.index.isin(neg)].reset_index()
    day = te_neg["datetime"].dt.normalize()
    m_real, se_real, _, _ = toxicity.cluster_mean(te_neg["gap_neutral"], te_neg["weight"], day) if len(te_neg) else (np.nan,) * 4
    m_adv, se_adv, _, _ = toxicity.cluster_mean(te_neg["gap_vs_train_be"], te_neg["weight"], day) if len(te_neg) else (np.nan,) * 4
    pooled = pd.DataFrame([{
        "pooled_gap_se_bps_test": se_real * 1e4, "pooled_gap_vs_train_be_bps": m_adv * 1e4,
        "pooled_gap_vs_train_be_se_bps": se_adv * 1e4,
        "n_cells": len(keep), "n_cells_with_test": len(both),
        "share_sign_agree": float((np.sign(both["train"]) == np.sign(both["test"])).mean()) if len(both) else np.nan,
        "n_negative_cells_train": len(neg),
        "pooled_gap_bps_test": float(np.average(te_neg["gap_neutral"], weights=te_neg["weight"]) * 1e4) if len(te_neg) else np.nan,
        "pooled_gap_twd_test": float((te_neg["gap_neutral"] * te_neg["notional"]).sum()) if len(te_neg) else np.nan,
    }])
    return pd.concat([a, b], ignore_index=True), pooled


# --- 3. H4 trading ---------------------------------------------------------------------------

def _controls(d):
    return pd.concat([pd.Series(1.0, index=d.index, name="const"), (d["ret_past"] * 1e4).rename("ret_past_bps"),
                      d["signed_norm"], pd.get_dummies(pd.Categorical(d["tod"], categories=sorted(d["tod"].unique())),
                                                       prefix="tod", dtype=float).iloc[:, 1:].set_index(d.index)], axis=1)


def tick(price):
    out = np.full(len(price), np.nan)
    for floor, t in config.FUTURES_TICKS[::-1]:
        out = np.where(np.asarray(price) >= floor, t, out)
    return out


COSTS = ("futures_spread", "futures_tick", "stock_daytrade")


def h4_triggers(tr, te):
    """Fit the residual projection and thresholds on ``tr`` (flow frames), trade ``te``: one row per trigger."""
    Xtr = _controls(tr)
    beta = np.linalg.lstsq(Xtr.to_numpy(float), tr["F_norm"].to_numpy(float), rcond=None)[0]
    Xte = _controls(te).reindex(columns=Xtr.columns, fill_value=0.0)
    tr_res = tr["F_norm"] - Xtr.to_numpy(float) @ beta
    te = te.assign(F_resid=te["F_norm"] - Xte.to_numpy(float) @ beta)
    S = te["S_mid_now"].to_numpy(float)
    tick_bps = tick(S) / S * 1e4
    half = te["S_spread_bps_now"].to_numpy(float) / 2
    half = np.where(np.isnan(half), tick_bps / 2, half)              # no valid 2330 quote at τ: half a tick
    fut_fixed = config.SINGLE_STOCK_FUTURES_TAX * 1e4 + config.FUTURES_FEE_PER_CONTRACT / (config.FUTURES_CONTRACT_SHARES * S) * 1e4
    round_trip = {                                                    # bps per round trip (entry + exit)
        "futures_spread": 2 * (half + fut_fixed),                     # main
        "futures_tick": 2 * (tick_bps + fut_fixed),                   # sensitivity
        "stock_daytrade": 2 * half + config.STOCK_DAYTRADE_TAX * 1e4 + 2 * config.BROKERAGE_FEE_MAX * 1e4,  # reference
    }
    q = config.H4_THRESHOLD_QUANTILE
    bounds = {"residual": ("F_resid", tr_res.quantile(q), tr_res.quantile(1 - q)),
              "raw": ("F_norm", tr["F_norm"].quantile(q), tr["F_norm"].quantile(1 - q))}
    trig = []
    for sig, (col, lo, hi) in bounds.items():
        signal = np.select([te[col] > hi, te[col] < lo], [1.0, -1.0], 0.0)
        on = signal != 0
        t = te.loc[on, ["day", "tau", "y_bps"]].assign(signal=signal[on], gross_bps=signal[on] * te.loc[on, "y_bps"].to_numpy(),
                                                      signal_type=sig, threshold_lo=lo, threshold_hi=hi)
        for name, rt in round_trip.items():
            t[f"cost_{name}"] = rt[on]
            t[f"net_{name}"] = t["gross_bps"] - rt[on]
        trig.append(t)
    return pd.concat(trig, ignore_index=True)


def h4_summary(trig, all_days, n_tau):
    """Per signal x cost: trade stats and the daily P&L series over ``all_days`` (1/5 position per trigger)."""
    rows = []
    for sig in ("residual", "raw"):
        t = trig[trig["signal_type"] == sig]
        for name in COSTS:
            daily = (t.groupby("day")[f"net_{name}"].sum() / 5).reindex(all_days, fill_value=0.0)
            sd = daily.std()
            rows.append({"signal": sig, "cost": name, "main": sig == config.H4_SIGNAL and name == "futures_spread",
                         "n_trades": len(t), "trigger_rate": len(t) / n_tau if n_tau else np.nan,
                         "gross_mean_bps": t["gross_bps"].mean(), "net_mean_bps": t[f"net_{name}"].mean(),
                         "cost_mean_bps": t[f"cost_{name}"].mean(),
                         "daily_mean_bps": daily.mean(), "daily_sd_bps": sd,
                         "sharpe_annual": daily.mean() / sd * np.sqrt(250) if sd > 0 else np.nan,
                         "t_daily": daily.mean() / (sd / np.sqrt(len(daily))) if sd > 0 else np.nan,
                         "n_days": len(daily)})
    return pd.DataFrame(rows)


def h4_trading(train_days, test_days, data_dir):
    tr = flow.h4_frame(train_days, data_dir, config.H4_MAIN_HORIZON)
    te = flow.h4_frame(test_days, data_dir, config.H4_MAIN_HORIZON)
    trig = h4_triggers(tr, te)
    return h4_summary(trig, sorted(te["day"].unique()), len(te)), trig


# --- 4. replication --------------------------------------------------------------------------

REPLICATE_VALUES = ["ES", f"RS_dt_{H}", f"M_dt_{H}", "net_pessimistic", "net_neutral", "net_optimistic"]
REPLICATE_CUTS = ["all", "direction", "quadrant", "delta_bucket", "dte_bucket", "size_bucket",
                  f"spot_{config.SPOT_MOVE_WINDOW}", "tod"]   # every pre-registered stage 3 cut


def _main_table(d):
    res = toxicity.analyse(d)
    dec = res["decomposition"]
    dec = dec[dec["cut"].isin(REPLICATE_CUTS) & dec["value"].isin(REPLICATE_VALUES)]
    cell = res["delta_dte"][res["delta_dte"]["pre_specified"]].assign(cut="high_gamma", group="cell")
    cols = ["cut", "group", "value", "mean_bps", "se_bps", "p", "n", "n_days"]
    return pd.concat([dec[cols], cell[cols]], ignore_index=True)


def replicate(a, b):
    """a: training estimates, b: test estimates (same rows)."""
    keys = ["cut", "group", "value"]
    m = a.merge(b, on=keys, suffixes=("_train", "_test"), how="left")
    sig = m["p_train"] < config.REPLICATION_ALPHA
    m["sign_and_significance"] = np.where(sig, (np.sign(m["mean_bps_train"]) == np.sign(m["mean_bps_test"]))
                                          & (m["p_test"] < config.REPLICATION_ALPHA), np.nan)
    m["z_diff"] = (m["mean_bps_test"] - m["mean_bps_train"]) / np.sqrt(m["se_bps_train"] ** 2 + m["se_bps_test"] ** 2)
    m["stable"] = (m["z_diff"].abs() < 1.96).where(m["z_diff"].notna())
    return m


def h4_replicate(train_days, test_days, data_dir):
    a = flow.regress(flow.h4_frame(train_days, data_dir, config.H4_MAIN_HORIZON)).assign(sample="train")
    b = flow.regress(flow.h4_frame(test_days, data_dir, config.H4_MAIN_HORIZON)).assign(sample="test")
    f = lambda x: x[x["term"] == "F_norm"].rename(columns={"coef": "mean_bps", "se": "se_bps"})[["mean_bps", "se_bps", "p", "n", "n_days"]] \
        .assign(cut="h4", group="all", value="F_norm")
    return replicate(f(a), f(b))


# --- walk-forward (secondary) ----------------------------------------------------------------

def _wmean(x, w):
    x, w = np.asarray(x, float), np.asarray(w, float)
    ok = ~np.isnan(x)
    return float((x[ok] * w[ok]).sum() / w[ok].sum()) if ok.any() and w[ok].sum() > 0 else np.nan


def walk_forward(trades, flows, drifts, base_days, test_days):
    """Expanding window, monthly refit (CLAUDE.md §10). ``trades``: usable trades of all days (train and
    test, with cells); ``flows``: H4 frames of all days; ``drifts``: day drift table of all days."""
    tday = trades["datetime"].dt.strftime("%Y-%m-%d")
    months = sorted({d[:7] for d in test_days})
    tr_base = heat_cells(trades[tday.isin(base_days)])
    cnt = tr_base.groupby(CELL, observed=True).agg(n=("ES", "size"), days=("datetime", lambda x: x.dt.normalize().nunique()))
    keep = cnt[(cnt["n"] >= config.HEATMAP_MIN_TRADES) & (cnt["days"] >= config.HEATMAP_MIN_DAYS)].index
    scored, heat_rows, heat_trades, trig = [], [], [], []
    for m in months:
        start = f"{m}-01"
        train_m = trades[tday < start]
        test_m = trades[tday.str[:7] == m]
        assert train_m["datetime"].max() < pd.Timestamp(start), "walk-forward leak: training data reaches the test month"
        if test_m.empty:
            continue
        train_days_m = sorted(tday[tday < start].unique())
        st = fit_stats(train_m, drifts.loc[train_days_m])
        beta = fit_score(train_m, st)
        cuts = np.quantile(predict(train_m, st, beta), np.linspace(0, 1, config.SCORE_QUANTILES + 1))
        cuts[0], cuts[-1] = -np.inf, np.inf
        p = predict(test_m, st, beta)
        scored.append(test_m.assign(score=p, month=m, quintile=pd.cut(p, cuts, labels=[f"Q{i}" for i in range(1, config.SCORE_QUANTILES + 1)])))
        # heatmap: break-even from the expanding window, on the training-fixed cell list
        h_tr, h_te = heat_cells(train_m), heat_cells(test_m)
        g = h_tr.groupby(CELL, observed=True)
        be = (g.apply(lambda x: _wmean(x[TARGET], x["weight"])) + g.apply(lambda x: _wmean(x["cost_neutral"], x["weight"])))
        pred = g.apply(lambda x: _wmean(x["gap_neutral"], x["weight"]))      # same definition as the static heatmap
        cells = pd.DataFrame({"be": be, "pred_gap": pred}).loc[lambda x: x.index.isin(keep)]
        h_te = h_te.join(cells, on=CELL, how="inner")
        h_te["gap_vs_be"] = h_te["ES"] - h_te["be"]
        neg = h_te[h_te["pred_gap"] < 0]
        heat_rows.append({"month": m, "n_negative_cells": int((cells["pred_gap"] < 0).sum()), "n_trades_negative": len(neg),
                          "realized_gap_bps": _wmean(neg["gap_neutral"], neg["weight"]) * 1e4,
                          "gap_vs_be_bps": _wmean(neg["gap_vs_be"], neg["weight"]) * 1e4,
                          "realized_gap_twd": float((neg["gap_neutral"] * neg["notional"]).sum()) if len(neg) else np.nan,
                          "notional_negative": float(neg["notional"].sum()),
                          "n_days": int(neg["datetime"].dt.normalize().nunique())})
        heat_trades.append(h_te[KEY_COLS + CELL + ["weight", "be", "pred_gap", "gap_neutral", "gap_vs_be", "notional"]].assign(month=m))
        # H4: projection and thresholds from the expanding window
        fd = flows["day"].astype(str)
        assert fd[fd < start].max() < start
        trig.append(h4_triggers(flows[fd < start], flows[fd.str[:7] == m]).assign(month=m))
    out = {}
    sc = pd.concat(scored, ignore_index=True)
    out["wf_quintiles"] = toxicity.table(sc, [TARGET], ["quintile"])
    q = sc[sc["quintile"].isin(["Q1", f"Q{config.SCORE_QUANTILES}"])]
    X = pd.DataFrame({"const": 1.0, "top": (q["quintile"] == f"Q{config.SCORE_QUANTILES}").astype(float)}, index=q.index)
    out["wf_q5_minus_q1"] = robustness.wls_cluster(q[TARGET] * 1e4, X, q["weight"], q["datetime"].dt.normalize()).query("term == 'top'")
    out["wf_q5_minus_q1_monthly"] = toxicity.table(sc, [TARGET], ["month", "quintile"]).query("quintile in ['Q1', 'Q5']")
    out["wf_heatmap_monthly"] = pd.DataFrame(heat_rows)
    ht = pd.concat(heat_trades, ignore_index=True)
    per = ht.groupby(CELL, observed=True).apply(lambda x: pd.Series({"pred": _wmean(x["pred_gap"], x["weight"]),
                                                                   "real": _wmean(x["gap_neutral"], x["weight"]),
                                                                   "n": len(x), "notional": x["notional"].sum()}))
    out["wf_heatmap_cells"] = per.reset_index().assign(sign_agree=lambda x: np.sign(x["pred"]) == np.sign(x["real"]))
    trig = pd.concat(trig, ignore_index=True)
    fd = flows["day"].astype(str)
    te_flows = flows[fd.isin(test_days)]
    out["wf_h4_trading"] = h4_summary(trig, sorted(te_flows["day"].unique()), len(te_flows))
    out["wf_h4_monthly"] = trig.groupby(["signal_type", "month"]).agg(n=("gross_bps", "size"), gross_bps=("gross_bps", "mean"),
                                                                        net_futures_spread_bps=("net_futures_spread", "mean")).reset_index()
    out["wf_h4_triggers"] = trig
    out["wf_predictions"] = sc[KEY_COLS + ["month", "score"]].assign(quintile=sc["quintile"].astype(str), target_bps=sc[TARGET] * 1e4)
    out["wf_heat_trades"] = ht.assign(**{c: ht[c].astype(str) for c in CELL})
    return out


# --- driver ----------------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[2]


def _git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=REPO)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def _git_state():
    """(commit, dirty, diff). Dirty counts tracked changes and untracked files under wtox/ or tests/."""
    head = _git("rev-parse", "HEAD").strip()
    status = _git("status", "--porcelain", "--untracked-files=all", "--", "wtox", "tests", "CLAUDE.md")
    return head, bool(status.strip()), _git("diff", "HEAD")


def run(data_dir, dry_run=True, out_dir=None):
    data_dir = Path(data_dir)
    head, dirty, diff = _git_state()
    meta = Path(out_dir or Path(data_dir) / "results" / ("stage5_dryrun" if dry_run else "stage5")) / "meta.parquet"
    if not dry_run and meta.exists():
        raise RuntimeError(f"{meta} exists: the test period was already evaluated once (CLAUDE.md §5.4). "
                           "A re-run must be justified in docs/decisions.md and the old outputs moved first.")
    if not dry_run:
        if not config.TEST_UNLOCKED:
            raise PermissionError("set config.TEST_UNLOCKED = True only for the single test run (CLAUDE.md §10)")
        if dirty:
            raise RuntimeError("commit everything first: the test run records the commit it ran on")
    out_dir = Path(out_dir or data_dir / "results" / ("stage5_dryrun" if dry_run else "stage5"))
    train_days, test_days = split_days(data_dir, dry_run)
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {}

    def save(name, frame):              # write as soon as produced: a later crash keeps earlier outputs
        res[name] = frame
        frame.to_parquet(out_dir / f"{name}.parquet", index=False)

    save("meta", pd.DataFrame([{"commit": head, "dirty_tree": dirty, "dry_run": dry_run, "unlocked": config.TEST_UNLOCKED,
                                "train_first": train_days[0], "train_last": train_days[-1],
                                "test_first": test_days[0], "test_last": test_days[-1],
                                "run_at": pd.Timestamp.now().isoformat()}]))
    (out_dir / "git_diff.txt").write_text(diff)
    train, _ = toxicity.build(train_days, data_dir)
    test, excl_test = toxicity.build(test_days, data_dir)
    save("exclusions_test", excl_test)
    train, test = add_cell(train), add_cell(test)
    drifts = robustness.load_drifts(train_days, data_dir)
    trm, tem = train[~train[f"trunc_{H}"]], test[~test[f"trunc_{H}"]]
    nan_rows = pd.DataFrame([{"sample": k, "n": len(x), "n_nan_target": int(x[TARGET].isna().sum())} for k, x in [("train", trm), ("test", tem)]])
    save("nan_targets", nan_rows)
    trm, tem = trm.dropna(subset=[TARGET]), tem.dropna(subset=[TARGET])
    st = fit_stats(trm, drifts)
    beta = fit_score(trm, st)
    for k, v in score_eval(trm, tem, st, beta).items():
        save(k, v)
    save("predictions_test", tem[KEY_COLS].assign(score=predict(tem, st, beta), target_bps=tem[TARGET] * 1e4))
    hm, hs = heatmap(trm, tem)
    save("heatmap", hm)
    save("heatmap_summary", hs)
    h4, trig = h4_trading(train_days, test_days, data_dir)
    save("h4_trading", h4)
    save("h4_triggers", trig)
    save("replication", pd.concat([replicate(_main_table(train), _main_table(test)),
                                   h4_replicate(train_days, test_days, data_dir)], ignore_index=True))
    for k, v in toxicity.analyse(test).items():          # the full stage 3 tables on the test period
        save(f"test_{k}", v)
    # walk-forward (secondary): expanding window, monthly refit
    allt = pd.concat([trm, tem], ignore_index=True)
    flows = flow.h4_frame(train_days + test_days, data_dir, config.H4_MAIN_HORIZON)
    drifts_all = robustness.load_drifts(train_days + test_days, data_dir)
    for k, v in walk_forward(allt, flows, drifts_all, train_days, test_days).items():
        save(k, v)
    return res


def main(argv=None):
    p = argparse.ArgumentParser(description="Stage 5 out-of-sample evaluation")
    p.add_argument("--data", default="../data")
    p.add_argument("--dry-run", action="store_true", help="split 2025 at config.DRY_RUN_SPLIT; never reads 2026")
    a = p.parse_args(argv)
    run(a.data, dry_run=a.dry_run)


if __name__ == "__main__":
    main()
