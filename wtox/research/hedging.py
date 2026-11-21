"""Extension E: issuer dynamic hedging with IV re-marking (A) (docs/decisions.md, 2026-11-21).

The issuer takes the other side of each usable trade: N = -s x lots x 1000 warrants. The warrant is
valued at pre_mid + [model(S, T, σ) - model(S_t, T_t, σ_t)] (as in stage 3); the initial delta hedge
h = -N x delta x ratio fills at S_mid(t + L) (t to t + L is unhedged). Over each segment k -> k+1 of
the path, in this order (no residual):

    Theta = N [W(S_k, T_k+1, σ_k) - W(S_k, T_k, σ_k)]
    Gamma = N [W(S_k+1, T_k+1, σ_k) - W(S_k, T_k+1, σ_k)] + h_k (S_k+1 - S_k)    (incl. discrete / delayed hedging)
    Vega  = N [W(S_k+1, T_k+1, σ_k+1) - W(S_k+1, T_k+1, σ_k)]
    cost  = |shares traded| x S x (tax + fee + 2330 half spread)

net = ES + Theta + Gamma + Vega - cost, in bps of N x pre_mid. T counts calendar time (as the IV
inversion), so intraday horizons charge only part of a day's theta: a lower bound for the issuer.

Ladder: (1) fixed at-trade IV, initial hedge only; (2) + re-hedging; (3) + IV path (labels/iv_path).
Levels: trade (every position hedged alone on a fixed schedule) and issuer book (close only: the
issuer's day positions netted, re-hedged when |sum of targets - hedge| > band, checked at every trade's
t + L and every grid minute; band error and costs allocated back to positions).

hedging.py only reads labels (spot grid, IV path, S_mid_<L>/<h>); it differences along those paths.

    python -m wtox.research.hedging --data ../data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox import bs_greeks, warrant_price
from wtox.research import config, toxicity

YEAR_S = config.DAYS_PER_YEAR * 86400.0
COMPONENTS = ["ES", "theta", "gamma", "vega", "cost", "net"]


# --- core: option pieces along each position's path -----------------------------------------

def _by_kind(f, is_call, *arrays):
    """Evaluate f(..., kind) separately for calls and puts (avoids per-element string handling)."""
    out = np.empty(len(is_call))
    for flag, kind in ((True, "call"), (False, "put")):
        m = is_call == flag
        if m.any():
            out[m] = f(*(a[m] if np.ndim(a) else a for a in arrays), kind)
    return out


def option_pieces(pts, pos, r=config.RISK_FREE, q=config.DIVIDEND_YIELD):
    """pts: long table sorted by (pos, time) with pos, time, S, sigma. pos: per-position frame indexed by
    pos id with N, strike, ratio, kind, T, t0. Adds T, target (own delta hedge, shares), and the segment
    pieces theta / gamma_opt / vega on each row (the segment that starts at the row; 0 on a last row)."""
    p = pos.loc[pts["pos"].to_numpy()]
    K, ratio, kind, N = (p[c].to_numpy() for c in ("strike", "ratio", "kind", "N"))
    T = np.maximum(p["T"].to_numpy(float) - (pts["time"] - p["t0"].to_numpy()).dt.total_seconds().to_numpy() / YEAR_S, 1e-9)
    S, sig = pts["S"].to_numpy(float), pts["sigma"].to_numpy(float)
    last = np.r_[pts["pos"].to_numpy()[1:] != pts["pos"].to_numpy()[:-1], True]
    nxt = lambda a: np.where(last, a, np.r_[a[1:], a[-1:]])
    S1, T1, sig1 = nxt(S), nxt(T), nxt(sig)
    is_call = kind == "call"
    price = lambda s_, k_, t_, v_, rt_, kd: warrant_price(s_, k_, r, q, v_, t_, rt_, kd)
    W = lambda s, t, v: _by_kind(price, is_call, s, K.astype(float), t, v, ratio.astype(float))
    a, b, c, e = W(S, T, sig), W(S, T1, sig), W(S1, T1, sig), W(S1, T1, sig1)
    out = pts.copy()
    out["T"] = T
    out["dS"] = np.where(last, 0.0, S1 - S)
    out["theta"] = np.where(last, 0.0, N * (b - a))
    out["gamma_opt"] = np.where(last, 0.0, N * (c - b))
    out["vega"] = np.where(last, 0.0, N * (e - c))
    dl = lambda s_, k_, v_, t_, kd: bs_greeks(s_, k_, r, q, v_, t_, kd)["delta"]
    out["target"] = -N * _by_kind(dl, is_call, S, K.astype(float), sig, T) * ratio
    out["last"] = last
    return out


def trade_hedge(x):
    """Trade level: hedge reset to the own target on rows flagged ``hedge`` (the first is the t + L fill),
    held until the next flagged row; 0 before the first. Adds h, traded and cost (needs ``rate``)."""
    h = pd.Series(np.where(x["hedge"], x["target"], np.nan), index=x.index)
    first = x["hedge"].groupby(x["pos"]).cumsum() > 0
    h = h.groupby(x["pos"]).ffill().where(first, 0.0).fillna(0.0)
    prev = h.groupby(x["pos"]).shift(1).fillna(0.0)
    x = x.assign(h=h.to_numpy())
    x["traded"] = (h - prev).abs().to_numpy()
    x["cost"] = np.where(x["traded"] > 0, x["traded"] * x["S"] * x["rate"], 0.0)
    x["gamma"] = x["gamma_opt"] + x["h"] * x["dS"]
    return x


def book_hedge(x, band, fixed_target=False):
    """Issuer book: rows are (pos, event) with ``ev`` = shared event index (-1 for a position's entry
    row, which is never hedged). Own target from the t + L fill on (fixed at that value if
    ``fixed_target``); the book hedge H moves to the sum of targets when they differ by more than
    ``band`` shares. Band error (H - sum of targets) x dS is allocated by |own target|, execution costs
    by |own target change since the last execution|."""
    x = x.copy()
    live = x["hedge"].groupby(x["pos"]).cumsum() > 0
    tgt = x["target"].where(live, 0.0)
    if fixed_target:
        at_fill = x["target"].where(x["hedge"] & (x["hedge"].groupby(x["pos"]).cumsum() == 1))
        tgt = at_fill.groupby(x["pos"]).ffill().where(live, 0.0).fillna(0.0)
    x["h"] = tgt.to_numpy()
    x["gamma"] = x["gamma_opt"] + x["h"] * x["dS"]
    x["cost"], x["band_err"] = 0.0, 0.0
    ev = x[x["ev"] >= 0]
    E = int(ev["ev"].max()) + 1 if len(ev) else 0
    pos_ids = np.unique(ev["pos"])
    P = len(pos_ids)
    pi = np.searchsorted(pos_ids, ev["pos"].to_numpy())
    M = np.zeros((P, E))                                   # own targets, 0 where not live
    M[pi, ev["ev"].to_numpy()] = ev["h"].to_numpy()
    present = np.zeros((P, E), bool)
    present[pi, ev["ev"].to_numpy()] = True
    S_ev = np.full(E, np.nan)
    S_ev[ev["ev"].to_numpy()] = ev["S"].to_numpy()
    rate_ev = np.full(E, np.nan)
    rate_ev[ev["ev"].to_numpy()] = ev["rate"].to_numpy()
    cost = np.zeros((P, E))
    err = np.zeros((P, E))
    H, last_exec = 0.0, np.zeros(P)
    for e in range(E):
        D = M[:, e].sum()
        if e + 1 < E and abs(D - H) > band:          # no trade at the final valuation point
            chg = np.abs(M[:, e] - last_exec)
            total = abs(D - H) * S_ev[e] * rate_ev[e]
            cost[:, e] = total * chg / chg.sum() if chg.sum() > 0 else total / max(present[:, e].sum(), 1) * present[:, e]
            H, last_exec = D, M[:, e].copy()
        if e + 1 < E:
            dS = S_ev[e + 1] - S_ev[e]
            gap = (H - D) * dS
            wts = np.abs(M[:, e])
            if wts.sum() > 0:
                err[:, e] = gap * wts / wts.sum()
            elif present[:, e].any():
                err[:, e] = gap * present[:, e] / present[:, e].sum()
    idx = ev.index
    x.loc[idx, "cost"] = cost[pi, ev["ev"].to_numpy()]
    x.loc[idx, "band_err"] = err[pi, ev["ev"].to_numpy()]
    x["gamma"] = x["gamma"] + x["band_err"]
    return x


def summarise(x, pos):
    """Per position, bps of N x pre_mid: theta, gamma, vega, cost, ES and net."""
    g = x.groupby("pos")[["theta", "gamma", "vega", "cost"]].sum()
    scale = (pos["N"].abs() * pos["pre_mid"]).reindex(g.index)
    out = g.div(scale, axis=0)
    out["ES"] = pos["ES"].reindex(g.index)
    out["net"] = out["ES"] + out["theta"] + out["gamma"] + out["vega"] - out["cost"]
    return out


# --- path construction -----------------------------------------------------------------------

def _sigma_at(times, pos_ids, pos, ivp, mode):
    """σ at each point: the at-trade IV, or (mode "path") the warrant's grid IV at the last grid minute
    at or before the point when that minute is after the trade (else the at-trade IV)."""
    sig0 = pos.loc[pos_ids, "iv"].to_numpy(float)
    if mode == "fixed" or ivp is None or ivp.empty:
        return sig0
    last_grid = times.dt.normalize() + config.CONTINUOUS_END - config.H4_GRID     # 13:24: the 13:25 close reads it
    g = times.dt.floor(config.H4_GRID).where(lambda x: x <= last_grid, last_grid)
    key = pd.DataFrame({"warrant_id": pos.loc[pos_ids, "warrant_id"].to_numpy(), "tau": g.to_numpy()})
    v = key.merge(ivp, on=["warrant_id", "tau"], how="left")["iv_tau"].to_numpy(float)
    after = (g > pos.loc[pos_ids, "t0"].to_numpy()).to_numpy()
    return np.where(after & ~np.isnan(v), v, sig0)


def trade_points(pos, grid, horizon, latency, every, rate_grid):
    """Long table for the trade level: entry t, fill t + L, grid minutes in between (flagged for
    re-hedging every ``every`` minutes; 0 = never), and the horizon end."""
    day = pos["t0"].iloc[0].normalize()
    close_t = day + config.CONTINUOUS_END
    end = pos["t0"] + config.HORIZONS[horizon] if horizon != "close" else pd.Series(close_t, index=pos.index)
    fill = pos["t0"] + config.HORIZONS[latency]
    ok = fill < end
    rows = [pd.DataFrame({"pos": pos.index, "time": pos["t0"], "S": pos["S_mid"], "hedge": False, "rate": np.nan}),
            pd.DataFrame({"pos": pos.index, "time": fill, "S": pos[f"S_mid_{latency}"], "hedge": True, "rate": pos["rate_fill"]}),
            pd.DataFrame({"pos": pos.index, "time": end, "S": pos[f"S_mid_{horizon}"], "hedge": False, "rate": np.nan})]
    gx = pos[["t0"]].assign(fill=fill, end=end).reset_index().rename(columns={"index": "pos"}).merge(
        grid[["tau", "S_mid_tau"]], how="cross")
    gx = gx[(gx["tau"] > gx["fill"]) & (gx["tau"] < gx["end"])]
    minute = ((gx["tau"] - day - config.SESSION_OPEN) // config.H4_GRID).astype(int)
    gx = gx[(minute % every == 0)] if every else gx.iloc[:0]     # path points = re-hedging minutes only
    rows.append(pd.DataFrame({"pos": gx["pos"], "time": gx["tau"], "S": gx["S_mid_tau"], "hedge": True,
                              "rate": gx["tau"].map(rate_grid)}))
    pts = pd.concat(rows, ignore_index=True)
    pts = pts[pts["pos"].isin(pos.index[ok])]
    return pts.sort_values(["pos", "time"], kind="mergesort").reset_index(drop=True)


def book_points(pos, grid, latency, rate_grid):
    """Long table for one issuer book (close): per position its entry row (ev = -1), then every shared
    event after its entry: all positions' t + L fills and all grid minutes, and the close."""
    day = pos["t0"].iloc[0].normalize()
    close_t = day + config.CONTINUOUS_END
    fill = pos["t0"] + config.HORIZONS[latency]
    pos = pos[fill < close_t]
    fill = fill.loc[pos.index]
    ev = pd.concat([pd.DataFrame({"time": fill, "S": pos[f"S_mid_{latency}"], "rate": pos["rate_fill"], "owner": pos.index}),
                    pd.DataFrame({"time": grid["tau"], "S": grid["S_mid_tau"], "rate": grid["tau"].map(rate_grid), "owner": -1}),
                    pd.DataFrame({"time": [close_t], "S": [pos["S_mid_close"].iloc[0]], "rate": [np.nan], "owner": [-1]})],
                   ignore_index=True)
    ev = ev[ev["time"] <= close_t].sort_values(["time", "owner"], kind="mergesort").reset_index(drop=True)
    ev["ev"] = np.arange(len(ev))
    cross = pos[["t0"]].reset_index().rename(columns={"index": "pos"}).merge(ev, how="cross")
    cross = cross[cross["time"] > cross["t0"]]
    cross["hedge"] = (cross["owner"] == cross["pos"]) | (cross["time"] > cross["pos"].map(fill))
    entry = pd.DataFrame({"pos": pos.index, "time": pos["t0"], "S": pos["S_mid"], "rate": np.nan, "ev": -1, "hedge": False})
    pts = pd.concat([entry, cross[["pos", "time", "S", "rate", "ev", "hedge"]]], ignore_index=True)
    return pts.sort_values(["pos", "time", "ev"], kind="mergesort").reset_index(drop=True), pos


# --- per day ---------------------------------------------------------------------------------

def _rates(d, grid, flows, scenario):
    sc = config.HEDGE_SCENARIOS[scenario]
    fixed = sc["tax"] + sc["fee"]
    med = d["S_spread_bps"].median()
    if not np.isfinite(med) and flows is not None:
        med = flows["S_spread_bps_now"].median()
    if not np.isfinite(med):                                   # no 2330 quote at all that day: one tick
        med = 5.0 / d["S_mid"].median() * 1e4
    fill = fixed + d["S_spread_bps"].fillna(med) / 2e4
    gs = grid["tau"].map(flows.set_index("tau")["S_spread_bps_now"]) if flows is not None else pd.Series(np.nan, index=grid.index)
    rate_grid = pd.Series((fixed + gs.fillna(med) / 2e4).to_numpy(), index=grid["tau"])
    return fill, rate_grid


def positions(d):
    pos = pd.DataFrame({"N": -d["side"] * d["volume"] * config.UNITS_PER_LOT, "strike": d["strike"], "ratio": d["ratio"],
                        "kind": d["kind"], "T": d["T"], "t0": d["datetime"], "iv": d["iv"], "warrant_id": d["warrant_id"],
                        "pre_mid": d["pre_mid"], "ES": d["ES"], "S_mid": d["S_mid"], "issuer": d["issuer"]})
    for c in ["S_mid_1s", "S_mid_10s", "S_mid_1m", "S_mid_5m", "S_mid_close"]:
        pos[c] = d[c]
    return pos


def simulate_day(d, grid, ivp, flows):
    """All variants for one day. Returns {variant: per-trade frame indexed like d}."""
    grid = grid.assign(tau=grid["tau"].astype("datetime64[ns]")).dropna(subset=["S_mid_tau"])
    if ivp is not None:
        ivp = ivp.assign(tau=ivp["tau"].astype("datetime64[ns]"))
    pos = positions(d)
    out = {}
    fill_t, grid_t = _rates(d, grid, flows, config.E_TRADE_COSTS)
    fill_b, grid_b = _rates(d, grid, flows, config.E_BOOK_COSTS)
    trade_runs = []
    for h, every in config.E_HORIZONS.items():
        trade_runs += [(h, config.E_LATENCY, every, (1, 2, 3))]
        if h == "close":
            trade_runs += [(h, config.E_LATENCY, config.E_REBALANCE_SENSITIVITY, (2, 3))]
        trade_runs += [(h, lat, every, (1, 3)) for lat in config.E_LATENCY_SENSITIVITY]
    short_ok = ~d["trunc_5m"].astype(bool).to_numpy()        # 5m drops trades truncated at 13:25; close keeps all
    for h, lat, every, ladders in trade_runs:
        pp = pos[short_ok] if h == "5m" else pos
        base = trade_points(pp.assign(rate_fill=fill_t.loc[pp.index]), grid, h, lat, every, grid_t)
        for mode in ("fixed", "path"):
            want = [k for k in ladders if (k == 3) == (mode == "path")]
            if not want:
                continue
            x = base.assign(sigma=_sigma_at(base["time"], base["pos"].to_numpy(), pos, ivp, mode))
            x = option_pieces(x, pos)
            for k in want:
                xs = x if k > 1 else x.assign(hedge=x["hedge"] & (x.groupby("pos").cumcount() == 1))
                res = summarise(trade_hedge(xs), pos)
                out[("trade", h, lat, every, k)] = res
    # issuer book, close only
    for k in (1, 2, 3):
        parts = []
        for _, g in pos.groupby("issuer"):
            pts, gp = book_points(g.assign(rate_fill=fill_b.loc[g.index]), grid, config.E_LATENCY, grid_b)
            if pts.empty:
                continue
            mode = "path" if k == 3 else "fixed"
            x = pts.assign(sigma=_sigma_at(pts["time"], pts["pos"].to_numpy(), pos, ivp, mode))
            x = option_pieces(x, pos)
            parts.append(summarise(book_hedge(x, config.E_BOOK_BAND_SHARES, fixed_target=k == 1), pos))
        if parts:
            out[("book", "close", config.E_LATENCY, 0, k)] = pd.concat(parts)
    # IV coverage: no IV update within the horizon
    # "IV at the horizon end differs from the at-trade IV" (same lookup as the path)
    for h in config.E_HORIZONS:
        pp = pos[short_ok] if h == "5m" else pos
        end = pp["t0"] + config.HORIZONS[h] if h != "close" else pd.Series(pp["t0"].iloc[0].normalize() + config.CONTINUOUS_END, index=pp.index)
        sig_end = _sigma_at(end, pp.index.to_numpy(), pos, ivp, "path")
        out[("iv_update", h)] = pd.DataFrame({"updated": np.abs(sig_end - pp["iv"].to_numpy()) > 1e-12}, index=pp.index)
    return out


# --- driver ----------------------------------------------------------------------------------

def day_frame(day, data_dir):
    d, grid = toxicity.load_day(day, data_dir)
    d = d[toxicity.eligible(d)]
    d = toxicity.trade_metrics(d, {"5m": config.HORIZONS["5m"], "close": None})
    d = toxicity.detrend(d, toxicity.day_drift(grid, {"5m": config.HORIZONS["5m"], "close": None}), ["5m", "close"])
    d = toxicity.add_cuts(toxicity.hedge_costs(d))
    return d.reset_index(drop=True), grid


def run_period(days, data_dir):
    data_dir = Path(data_dir)
    res, trades = {}, []
    for day in days:
        d, grid = day_frame(day, data_dir)
        if d.empty:
            continue
        ivp_path = data_dir / "labels" / "iv_path" / f"{day}.parquet"
        fpath = data_dir / "flow" / f"{day}.parquet"
        ivp = pd.read_parquet(ivp_path) if ivp_path.exists() else None
        flows = pd.read_parquet(fpath) if fpath.exists() else None
        sim = simulate_day(d, grid, ivp, flows)
        keep = ["datetime", "weight", "direction", "delta_bucket", "dte_bucket", "issuer"]
        for k in config.HEDGE_SCENARIOS:
            d[f"stage3_net_{k}"] = (d["RS_dt_5m"] - d[f"cost_{k}"]).where(~d["trunc_5m"].astype(bool))
            d[f"stage3_close_net_{k}"] = d["RS_dt_close"] - d[f"cost_{k}"]
        trades.append(d[keep + [c for c in d if c.startswith("stage3_")]].assign(day=day, pos=d.index))
        for key, frame in sim.items():
            res.setdefault(key, []).append(frame.rename_axis("pos").reset_index().assign(day=day))
    t = pd.concat(trades, ignore_index=True)
    return t, {k: pd.concat(v) for k, v in res.items()}


def tables(t, res):
    """Notional-weighted, day-clustered means (bps) for every variant, overall and by the main cuts."""
    t = t.copy()
    t["high_gamma"] = np.where((t["delta_bucket"] == config.HIGH_GAMMA_CELL[0]) & (t["dte_bucket"] == config.HIGH_GAMMA_CELL[1]),
                               "cell", "other")
    key = ["day", "pos"]
    cuts = ["direction", "dte_bucket", "delta_bucket", "high_gamma"]
    rows = []
    for k, v in res.items():
        if k[0] == "iv_update":
            continue
        x = t.merge(v, on=key, how="inner", validate="one_to_one")
        lab = dict(zip(["level", "horizon", "latency", "rebalance", "ladder"], k))
        rows.append(toxicity.table(x, COMPONENTS).assign(cut="all", group="all", **lab))
        for c in cuts:
            rows.append(toxicity.table(x, COMPONENTS, [c]).rename(columns={c: "group"}).assign(cut=c, **lab))
    main = pd.concat(rows, ignore_index=True)
    main["group"] = main["group"].astype(str)
    ref = pd.concat([toxicity.table(t, [c for c in t if c.startswith("stage3_")]).assign(cut="all", group="all")] +
                    [toxicity.table(t, [c for c in t if c.startswith("stage3_")], [c]).rename(columns={c: "group"}).assign(cut=c)
                     for c in cuts], ignore_index=True)
    ref["group"] = ref["group"].astype(str)
    cov = []
    for k, v in res.items():
        if k[0] != "iv_update":
            continue
        x = t.merge(v, on=key, how="inner", validate="one_to_one")
        cov.append({"horizon": k[1], "share_no_update_n": float((~x["updated"]).mean()),
                    "share_no_update_notional": float(x.loc[~x["updated"], "weight"].sum() / x["weight"].sum())})
    return {"e_main": main, "e_stage3_reference": ref, "e_iv_coverage": pd.DataFrame(cov)}


def run(data_dir, out_dir=None, periods=("2025", "2026")):
    data_dir = Path(data_dir)
    out_dir = Path(out_dir or data_dir / "results" / "extension")
    out_dir.mkdir(parents=True, exist_ok=True)
    days = sorted(p.stem for p in (data_dir / "panel" / "tsmc_warrant_trades").glob("*.parquet") if config.in_sample(p.stem))
    for label, ds in [("2025", [x for x in days if x <= config.TRAIN_END]), ("2026", [x for x in days if x >= config.TEST_START])]:
        if not ds or label not in periods:
            continue
        t, res = run_period(ds, data_dir)
        for name, frame in tables(t, res).items():
            frame.to_parquet(out_dir / f"{name}_{label}.parquet", index=False)


def main(argv=None):
    p = argparse.ArgumentParser(description="Extension E: issuer dynamic hedging simulation")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default=None, help="default: <data>/results/extension")
    p.add_argument("--period", nargs="+", default=["2025", "2026"], choices=["2025", "2026"])
    a = p.parse_args(argv)
    run(a.data, a.out, a.period)


if __name__ == "__main__":
    main()
