"""Extension analyses B-D (docs/decisions.md, 2026-11-21; pre-registered before any result).

B  trades without an at-trade quote (mostly short-dated): feature comparison, a proxy markout with a
   lagged IV, validated on quoted trades, then a combined estimate. Both groups use one definition:
   NTD markout m = s delta ratio (S(t+5m) - S(t)(1 + day 5m drift)) x shares, aggregated as
   sum m / sum (P x shares), so cheap warrants carry no side-dependent denominator bias.
C  issuer hedging impact vs information. C1: size of warrant delta flow vs 2330 volume, and the 2330
   impact coefficient λ (return on same-window signed volume) next to the H4 flow coefficient β.
   C2: does M revert from 5m to 30m / close (trades before 12:55 only), and the same for the H4
   coefficient (τ <= 12:55), as paired differences with day-clustered SEs.
D  H4 backtest with netted positions: same triggers and 1/5 tranches held 5 minutes, but costs only on
   the change of the net position each minute.

    python -m wtox.research.extension --data ../data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from wtox import bs_greeks
from wtox.research import config, flow, oos, toxicity
from wtox.research.coverage import dte_bucket
from wtox.research.markout import KEY

MAIN = config.MAIN_HORIZON


def _ci(m, se, level):
    z = stats.norm.ppf(0.5 + level / 2)
    return m - z * se, m + z * se


def _cm(x, w, day):
    m, se, n, G = toxicity.cluster_mean(x, w, day)
    return {"mean_bps": m * 1e4, "se_bps": se * 1e4, "n": n, "n_days": G}


# --- B: trades without an at-trade quote -----------------------------------------------------

def _valid_iv(iv):
    lo, hi = config.EXT_PROXY_IV_BOUNDS
    return iv.where((iv > lo) & (iv < hi))


def proxy_iv(p, carry):
    """Per trade: the mid IV of the same warrant's last quoted trade strictly before t (that day), else
    the previous day's last one (``carry``: warrant -> (time, iv)). Backward-looking only."""
    src = p[toxicity.eligible(p)].assign(iv_ok=lambda x: _valid_iv(x["iv"])).dropna(subset=["iv_ok"])
    src = src[["warrant_id", "datetime", "iv_ok"]].rename(columns={"datetime": "iv_time", "iv_ok": "iv_proxy"})
    src = src.sort_values("iv_time", kind="mergesort")
    q = p[["warrant_id", "datetime"]].reset_index().sort_values("datetime", kind="mergesort")
    m = pd.merge_asof(q, src, left_on="datetime", right_on="iv_time", by="warrant_id",
                      direction="backward", allow_exact_matches=False).set_index("index").reindex(p.index)
    # previous trading day only; the same exchange code can be another warrant, so strike, kind and
    # expiry date (day + T) must match
    if carry:
        prev = pd.DataFrame.from_dict(carry, orient="index", columns=["iv_time", "iv_proxy", "strike", "kind", "expiry"])
        miss = m["iv_proxy"].isna() & p["warrant_id"].isin(prev.index)
        if miss.any():
            c = prev.loc[p.loc[miss, "warrant_id"]].set_index(p.index[miss])
            same = ((c["strike"] - p.loc[miss, "strike"]).abs() < 1e-9) & (c["kind"] == p.loc[miss, "kind"]) \
                & ((c["expiry"] - _expiry(p.loc[miss])).abs() <= pd.Timedelta(days=2))
            idx = same[same].index
            m.loc[idx, "iv_proxy"] = c.loc[idx, "iv_proxy"]
            m.loc[idx, "iv_time"] = c.loc[idx, "iv_time"]
    last = p.loc[src.index].assign(iv_time=src["iv_time"], iv_proxy=src["iv_proxy"]).sort_values("iv_time", kind="mergesort")
    last = last.groupby("warrant_id").last()
    new_carry = {w: (r["iv_time"], r["iv_proxy"], r["strike"], r["kind"], _expiry(r)) for w, r in last.iterrows()}
    return m["iv_proxy"], m["iv_time"], new_carry


def _expiry(x):
    """Expiry date = trade date + round(T x 365) days, for a frame or a single row."""
    days = np.round(x["T"] * config.DAYS_PER_YEAR)
    if isinstance(x, pd.DataFrame):
        return x["datetime"].dt.normalize() + pd.to_timedelta(days, unit="D")
    return x["datetime"].normalize() + pd.Timedelta(days=float(days))


def b_day(day, data_dir, carry, r=config.RISK_FREE, q=config.DIVIDEND_YIELD):
    config.check_unlocked(day)
    data_dir = Path(data_dir)
    p = pd.read_parquet(data_dir / "panel" / "tsmc_warrant_trades" / f"{day}.parquet")
    lab = pd.read_parquet(data_dir / "labels" / "tsmc_warrant_trades" / f"{day}.parquet",
                          columns=KEY + [f"S_mid_{MAIN}", f"trunc_{MAIN}"])
    drift = toxicity.day_drift(pd.read_parquet(data_dir / "labels" / "tsmc_grid" / f"{day}.parquet"))[MAIN]
    p = p.merge(lab, on=KEY, how="left", validate="one_to_one")
    iv_p, iv_t, carry = proxy_iv(p, carry)
    p["iv_proxy"], p["iv_age_s"] = iv_p, (p["datetime"] - pd.to_datetime(iv_t)).dt.total_seconds()
    keep = (p["order_tick_type"].isin([1, 2]) & ~p[f"trunc_{MAIN}"].fillna(True).astype(bool)
            & p[f"S_mid_{MAIN}"].notna() & p["S_mid"].notna() & (p["T"] > 0))
    p = p[keep].copy()
    p["has_quote"] = toxicity.eligible(p)
    ok = p["iv_proxy"].notna()
    p["delta_proxy"] = np.nan
    if ok.any():
        g = p[ok]
        p.loc[ok, "delta_proxy"] = bs_greeks(g["S_mid"].to_numpy(float), g["strike"].to_numpy(float), r, q,
                                             g["iv_proxy"].to_numpy(float), g["T"].to_numpy(float), g["kind"].to_numpy())["delta"]
    shares = p["volume"] * config.UNITS_PER_LOT
    move = p[f"S_mid_{MAIN}"] - p["S_mid"] * (1 + drift)
    p["notional_P"] = p["close"] * shares
    for name, dcol in [("true", "delta"), ("proxy", "delta_proxy")]:
        p[f"x_{name}"] = p["side"] * p[dcol] * p["ratio"] * move * shares / p["notional_P"]
    return p, carry


def b_frame(days, data_dir, seed_day=None):
    """``seed_day``: the trading day before days[0] (its last IVs seed the first day's carry)."""
    frames, carry = [], {}
    if seed_day:
        _, carry = b_day(seed_day, data_dir, {})
    for day in days:
        d, carry = b_day(day, data_dir, carry)
        frames.append(d)
    return b_features(pd.concat(frames, ignore_index=True))


def b_features(d):
    d = d.copy()
    d["day"] = d["datetime"].dt.normalize()
    d["dte_bucket"] = dte_bucket(d["T"] * config.DAYS_PER_YEAR)
    expiry = (d["day"] + pd.to_timedelta(np.round(d["T"] * config.DAYS_PER_YEAR), unit="D")).to_numpy("datetime64[D]")
    td = np.busday_count(d["day"].to_numpy("datetime64[D]"), expiry)
    d["trading_days"] = pd.cut(td, list(config.EXT_TRADING_DAY_EDGES), labels=list(config.EXT_TRADING_DAY_LABELS))
    d["direction"] = np.where(d["side"] > 0, "buy", "sell")
    d["size_bucket"] = pd.cut(d["order_volume"], list(config.SIZE_BUCKET_EDGES), labels=list(config.SIZE_BUCKET_LABELS))
    adelta = d["delta"].where(d["has_quote"], d["delta_proxy"]).abs()
    d["delta_bucket"] = pd.cut(adelta, list(config.DELTA_BUCKET_EDGES), labels=list(config.DELTA_BUCKET_LABELS))
    tod = d["datetime"] - d["day"]
    d["tod"] = pd.cut(tod, list(config.TOD_EDGES), labels=list(config.TOD_LABELS), right=False)
    kind_sign = np.where(d["kind"] == "put", -1.0, 1.0)
    fav = np.sign(d["S_chg_1s"]) * kind_sign * d["side"]
    d["spot_1s"] = np.where(d["S_chg_1s"].isna(), "na", np.select([fav > 0, fav < 0], ["favourable", "adverse"], "none"))
    d["price_bucket"] = pd.cut(d["close"], list(config.EXT_PRICE_EDGES), labels=list(config.EXT_PRICE_LABELS))
    d["multi_fill"] = d["n_fills"] > 1
    d["prev_state"] = np.select([d["prev_in_force"].fillna(False).astype(bool), d["prev_bid"].notna()],
                                ["in_force", "stale"], "none")
    d["iv_age"] = pd.cut(d["iv_age_s"], list(config.EXT_IV_AGE_EDGES), labels=list(config.EXT_IV_AGE_LABELS))
    return d


B_FEATURES = ("direction", "size_bucket", "delta_bucket", "trading_days", "tod", "spot_1s", "price_bucket",
              "multi_fill", "prev_state")


def _scopes(d):
    return [("dte_1-30", d[d["dte_bucket"] == "1–30"]), ("all", d)]


def b_feature_table(d):
    rows = []
    for scope, s in _scopes(d):
        for hq, g in s.groupby("has_quote"):
            for f in B_FEATURES:
                c = g.assign(**{f: g[f].astype(str)}).groupby(f).agg(n=("x_proxy", "size"), notional=("notional_P", "sum"))
                rows.append(c.reset_index().rename(columns={f: "group"}).assign(
                    scope=scope, feature=f, has_quote=bool(hq), share_n=c["n"].to_numpy() / len(g),
                    share_notional=c["notional"].to_numpy() / g["notional_P"].sum()))
    out = pd.concat(rows, ignore_index=True)
    out["group"] = out["group"].astype(str)
    return out


def b_validation(d):
    """Paired proxy - true bias on quoted trades (same trades, same NTD definition)."""
    v = d[d["has_quote"] & d["x_proxy"].notna() & d["x_true"].notna()]
    v = v.assign(diff=v["x_proxy"] - v["x_true"])
    short = v["dte_bucket"] == "1–30"
    groups = [("dte_1-30", "all", short), ("all", "all", pd.Series(True, index=v.index)),
              ("dte_1-30_delta<0.2", "all", short & (v["delta"].abs() < 0.2)),
              ("price<=0.05", "all", v["close"] <= 0.05)]
    groups += [("direction", g, v["direction"] == g) for g in ("buy", "sell")]
    groups += [("iv_age", str(g), v["iv_age"] == g) for g in config.EXT_IV_AGE_LABELS]
    groups += [("dte_1-30_iv_age", str(g), short & (v["iv_age"] == g)) for g in config.EXT_IV_AGE_LABELS]
    rows = []
    margin, level = config.EXT_PROXY_EQUIV_MARGIN_BPS, config.EXT_PROXY_CI
    for name, grp, m in groups:
        g = v[m]
        r = _cm(g["diff"], g["notional_P"], g["day"])
        lo, hi = _ci(r["mean_bps"], r["se_bps"], level)
        rows.append({"group_set": name, "group": grp, **r, "ci_lo_bps": lo, "ci_hi_bps": hi,
                     "true_bps": _cm(g["x_true"], g["notional_P"], g["day"])["mean_bps"],
                     "proxy_bps": _cm(g["x_proxy"], g["notional_P"], g["day"])["mean_bps"],
                     "within_margin": bool(lo >= -margin and hi <= margin),
                     "criterion": name == "dte_1-30"})
    return pd.DataFrame(rows)


def b_estimate(d, proxy_ok):
    rows = []
    for scope, s in _scopes(d):
        miss = s[~s["has_quote"]]
        est = miss["x_proxy"].notna()
        kept = s[s["has_quote"] & s["x_true"].notna()]
        comb = pd.concat([kept.assign(x=kept["x_true"]), miss[est].assign(x=miss.loc[est, "x_proxy"])])
        tot = s["notional_P"].sum()
        for what, g, col in [("quoted_only", kept, "x_true"), ("missing_proxy", miss[est], "x_proxy"),
                             ("combined", comb, "x")]:
            rows.append({"scope": scope, "estimate": what, **_cm(g[col], g["notional_P"], g["day"]),
                         "share_notional": g["notional_P"].sum() / tot, "proxy_validated": proxy_ok})
        rows.append({"scope": scope, "estimate": "missing_unestimable", "n": int((~est).sum()),
                     "share_notional": miss.loc[~est, "notional_P"].sum() / tot, "proxy_validated": proxy_ok})
    return pd.DataFrame(rows)


def b_run(days, data_dir, seed_day=None):
    d = b_frame(days, data_dir, seed_day)
    val = b_validation(d)
    ok = bool(val.loc[val["criterion"], "within_margin"].iloc[0]) if val["criterion"].any() else False
    return {"b_features": b_feature_table(d), "b_validation": val, "b_estimate": b_estimate(d, ok)}


# --- C: hedging impact vs information --------------------------------------------------------

def _flows(days, data_dir):
    out = []
    for day in days:
        config.check_unlocked(day)
        out.append(pd.read_parquet(Path(data_dir) / "flow" / f"{day}.parquet").assign(day=day))
    return pd.concat(out, ignore_index=True)


def _non_overlapping(f):
    step = int(config.H4_FLOW_WINDOW / config.H4_GRID)
    k = (f["tau"] - f["tau"].dt.normalize() - config.H4_FIRST_TAU) // config.H4_GRID
    return f[k % step == 0]


def c1_size(f):
    x = _non_overlapping(f)
    first = x["tau"] - x["tau"].dt.normalize() == config.H4_FIRST_TAU     # window includes the opening auction
    x = x[(x["stock_shares"] > 0) & x["F"].notna() & ~first]
    share = x["F"].abs() / x["stock_shares"]
    qs = share.quantile([0.5, 0.9, 0.99])
    return pd.DataFrame([{"n_windows": len(x), "median": qs.loc[0.5], "p90": qs.loc[0.9], "p99": qs.loc[0.99],
                          "pooled": x["F"].abs().sum() / x["stock_shares"].sum()}])


def c1_coefficients(f, h4):
    """λ: 2330 return over [τ-k, τ] on the same window's signed 2330 volume (same denominator as F_norm),
    with time-of-day dummies; β: H4 flow coefficient with and without controls. All in bps per unit."""
    x = f.dropna(subset=["ret_past", "signed_norm"])
    X = pd.concat([pd.Series(1.0, index=x.index, name="const"), x["signed_norm"],
                   pd.get_dummies(x["tod"], prefix="tod", drop_first=True, dtype=float)], axis=1)
    lam = flow.ols_cluster(x["ret_past"] * 1e4, X, x["day"]).query("term == 'signed_norm'").assign(name="lambda")
    main = flow.regress(h4).query("term == 'F_norm'").assign(name="beta_controls")
    Xn = pd.concat([pd.Series(1.0, index=h4.index, name="const"), h4["F_norm"]], axis=1)
    bare = flow.ols_cluster(h4["y_bps"], Xn, h4["day"]).query("term == 'F_norm'").assign(name="beta_no_controls")
    out = pd.concat([lam, main, bare], ignore_index=True)
    out["ci_lo"], out["ci_hi"] = out["coef"] - 1.96 * out["se"], out["coef"] + 1.96 * out["se"]
    lam_hi = out.loc[out["name"] == "lambda", "ci_hi"].iloc[0]
    b_lo = out.loc[out["name"] == "beta_controls", "ci_lo"].iloc[0]
    reading = "delayed hedging cannot fully explain H4" if b_lo > lam_hi else "inconclusive (intervals overlap)"
    return out.assign(reading=reading)


def _reading(lo, hi, base):
    """Reversion = the effect shrinks toward 0 from its 5m level (sign-aware; longer horizons only)."""
    if not np.isfinite(base) or base == 0:
        return "n/a (baseline zero)"
    if base < 0:
        lo, hi, base = -hi, -lo, -base
    if hi < 0:
        return "reversion"
    if lo > -config.EXT_REVERSION_SHARE * base:
        return "no marked reversion"
    return "inconclusive"


def c2_markout(d):
    """d: stage 3 trades. Paired M(h) - M(5m) on trades before 12:55, raw and de-trended."""
    tod = d["datetime"] - d["datetime"].dt.normalize()
    s = d[(tod < config.EXT_C2_LAST_TRADE) & ~d["trunc_5m"] & ~d["trunc_30m"]]
    day = s["datetime"].dt.normalize()
    rows = []
    for grp, g in [("all", s), ("buy", s[s["side"] > 0]), ("sell", s[s["side"] < 0])]:
        gd = day.loc[g.index]
        for kind, pre in [("detrended", "M_dt_"), ("raw", "M_")]:
            base = _cm(g[f"{pre}{MAIN}"], g["weight"], gd)
            rows.append({"group": grp, "version": kind, "horizon": MAIN, **base, "diff_bps": np.nan})
            for h in config.EXT_C2_HORIZONS:
                lvl = _cm(g[f"{pre}{h}"], g["weight"], gd)
                dif = _cm(g[f"{pre}{h}"] - g[f"{pre}{MAIN}"], g["weight"], gd)
                lo, hi = dif["mean_bps"] - 1.96 * dif["se_bps"], dif["mean_bps"] + 1.96 * dif["se_bps"]
                rows.append({"group": grp, "version": kind, "horizon": h, **lvl, "diff_bps": dif["mean_bps"],
                             "diff_se_bps": dif["se_bps"], "diff_ci_lo": lo, "diff_ci_hi": hi,
                             "reversion_share": -dif["mean_bps"] / base["mean_bps"] if base["mean_bps"] else np.nan,
                             "reading": _reading(lo, hi, base["mean_bps"])})
    return pd.DataFrame(rows)


def c2_h4(days, data_dir):
    """H4 flow coefficient at each horizon minus the 5m one, same τ <= 12:55 sample (paired targets)."""
    last = config.EXT_C2_LAST_TRADE
    frames = {h: flow.h4_frame(days, data_dir, h) for h in (MAIN, *config.EXT_C2_H4_HORIZONS)}
    sel = lambda x: x[(x["tau"] - x["tau"].dt.normalize()) <= last].set_index(["day", "tau"])
    base = sel(frames[MAIN])
    b = flow.regress(base.reset_index()).query("term == 'F_norm'").iloc[0]
    rows = [{"horizon": MAIN, "coef": b["coef"], "se": b["se"], "n": b["n"]}]
    for h in config.EXT_C2_H4_HORIZONS:
        x = sel(frames[h])
        common = base.index.intersection(x.index)
        lvl = flow.regress(x.loc[common].reset_index()).query("term == 'F_norm'").iloc[0]
        dd = base.loc[common].assign(y_bps=x.loc[common, "y_bps"] - base.loc[common, "y_bps"]).reset_index()
        dif = flow.regress(dd).query("term == 'F_norm'").iloc[0]
        lo, hi = dif["coef"] - 1.96 * dif["se"], dif["coef"] + 1.96 * dif["se"]
        rows.append({"horizon": h, "coef": lvl["coef"], "se": lvl["se"], "n": lvl["n"], "diff": dif["coef"],
                     "diff_se": dif["se"], "diff_ci_lo": lo, "diff_ci_hi": hi,
                     "reading": _reading(lo, hi, b["coef"]) if h != "1m" else "n/a (shorter than 5m)"})
    return pd.DataFrame(rows)


def c_run(days, data_dir, trades):
    f = _flows(days, data_dir)
    h4 = flow.h4_frame(days, data_dir, config.H4_MAIN_HORIZON)
    return {"c1_size": c1_size(f), "c1_coefficients": c1_coefficients(f, h4),
            "c2_markout": c2_markout(trades), "c2_h4": c2_h4(days, data_dir)}


# --- D: netted H4 backtest -------------------------------------------------------------------

def _side_costs(f):
    """Per (day, tau): one-side cost (bps of position) for each cost scenario, missing values filled
    with the day's median spread / price (then half a tick, as in stage 5)."""
    f = f.copy()
    g = f.groupby("day")
    S = f["S_mid_now"].fillna(g["S_mid_now"].transform("median"))
    spread = f["S_spread_bps_now"].fillna(g["S_spread_bps_now"].transform("median"))
    tick_bps = oos.tick(S.to_numpy(float)) / S * 1e4
    half = (spread / 2).where(spread.notna(), tick_bps / 2)
    fixed = config.SINGLE_STOCK_FUTURES_TAX * 1e4 + config.FUTURES_FEE_PER_CONTRACT / (config.FUTURES_CONTRACT_SHARES * S) * 1e4
    return pd.DataFrame({"day": f["day"].astype(str), "tau": f["tau"],
                         "futures_spread": half + fixed, "futures_tick": tick_bps + fixed,
                         "stock_daytrade": half + (config.STOCK_DAYTRADE_TAX / 2 + config.BROKERAGE_FEE_MAX) * 1e4})


def net_positions(trig, minutes):
    """Net position (units of one full position) at each minute: each trigger adds signal / 5 over
    [τ, τ + k). ``minutes``: sorted grid of the day including the last exit time."""
    step = int(config.H4_FLOW_WINDOW / config.H4_GRID)
    idx = np.searchsorted(minutes, trig["tau"].to_numpy())
    add = np.zeros(len(minutes) + step + 1)
    np.add.at(add, idx, trig["signal"].to_numpy(float) / step)
    np.add.at(add, idx + step, -trig["signal"].to_numpy(float) / step)
    return np.cumsum(add)[:len(minutes)]


def d_netting(trig, f, label):
    costs = _side_costs(f)
    rows = []
    for sig in ("residual", "raw"):
        t = trig[trig["signal_type"] == sig].assign(day=lambda x: x["day"].astype(str))
        days = sorted(costs["day"].unique())
        daily = {name: [] for name in oos.COSTS}
        traded, gross_day = 0.0, []
        for day in days:
            c = costs[costs["day"] == day].sort_values("tau")
            minutes = pd.date_range(c["tau"].iloc[0], c["tau"].iloc[-1] + config.H4_FLOW_WINDOW,
                                    freq=config.H4_GRID).to_numpy("datetime64[ns]")
            cc = c.set_index("tau").reindex(minutes)
            td = t[t["day"] == day]
            pos = net_positions(td, minutes) if len(td) else np.zeros(len(minutes))
            dpos = np.abs(np.diff(np.r_[0.0, pos]))
            traded += dpos.sum()
            gross_day.append(td["gross_bps"].sum() / 5)
            for name in oos.COSTS:
                cost = cc[name].fillna(cc[name].median()).to_numpy(float)
                daily[name].append(td["gross_bps"].sum() / 5 - np.nansum(dpos * cost))
        n = len(t)
        for name in oos.COSTS:
            dl = pd.Series(daily[name], index=days)
            sd = dl.std()
            cost_total = sum(gross_day) - dl.sum()
            rows.append({"period": label, "signal": sig, "cost": name, "n_trades": n,
                         "turnover_ratio": traded / (2 * n / 5) if n else np.nan,
                         "gross_mean_bps": t["gross_bps"].mean(),
                         "cost_per_trade_bps": cost_total * 5 / n if n else np.nan,
                         "net_mean_bps": t["gross_bps"].mean() - cost_total * 5 / n if n else np.nan,
                         "unnetted_cost_bps": t[f"cost_{name}"].mean(),
                         "lower_bound_cost_bps": t[f"cost_{name}"].mean() / 5,
                         "daily_mean_bps": dl.mean(), "daily_sd_bps": sd,
                         "sharpe_annual": dl.mean() / sd * np.sqrt(250) if sd > 0 else np.nan,
                         "t_daily": dl.mean() / (sd / np.sqrt(len(dl))) if sd > 0 else np.nan, "n_days": len(dl)})
    return pd.DataFrame(rows)


def d_run(data_dir, train_days, test_days):
    data_dir = Path(data_dir)
    tr = flow.h4_frame(train_days, data_dir, config.H4_MAIN_HORIZON)
    out = [d_netting(oos.h4_triggers(tr, tr), tr, "2025_in_sample")]
    res5 = data_dir / "results" / "stage5"
    if test_days:
        te = flow.h4_frame(test_days, data_dir, config.H4_MAIN_HORIZON)
        for name, file in [("2026_static", "h4_triggers.parquet"), ("2026_walk_forward", "wf_h4_triggers.parquet")]:
            if (res5 / file).exists():
                out.append(d_netting(pd.read_parquet(res5 / file), te, name))
    return {"d_netting": pd.concat(out, ignore_index=True)}


# --- driver ----------------------------------------------------------------------------------

def run(data_dir, out_dir=None):
    data_dir = Path(data_dir)
    out_dir = Path(out_dir or data_dir / "results" / "extension")
    out_dir.mkdir(parents=True, exist_ok=True)
    all_days = sorted(p.stem for p in (data_dir / "panel" / "tsmc_warrant_trades").glob("*.parquet") if config.in_sample(p.stem))
    flow_days = {p.stem for p in (data_dir / "flow").glob("*.parquet")}
    periods = {"2025": [x for x in all_days if x <= config.TRAIN_END],
               "2026": [x for x in all_days if x >= config.TEST_START]}

    def save(name, frame):
        frame.to_parquet(out_dir / f"{name}.parquet", index=False)

    for label, days in periods.items():
        if not days:
            continue
        before = [x for x in all_days if x < days[0]]
        for k, v in b_run(days, data_dir, before[-1] if before else None).items():
            save(f"{k}_{label}", v)
        trades, _ = toxicity.build(days, data_dir)
        for k, v in c_run([x for x in days if x in flow_days], data_dir, trades).items():
            save(f"{k}_{label}", v)
    fd = lambda xs: [x for x in xs if x in flow_days]
    for k, v in d_run(data_dir, fd(periods["2025"]), fd(periods["2026"])).items():
        save(k, v)


def main(argv=None):
    p = argparse.ArgumentParser(description="Extension analyses B-D")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default=None, help="default: <data>/results/extension")
    a = p.parse_args(argv)
    run(a.data, a.out)


if __name__ == "__main__":
    main()
