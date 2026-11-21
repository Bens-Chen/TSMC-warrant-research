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


def main(argv=None):
    p = argparse.ArgumentParser(description="Who wins / who loses: market maker vs trader map (intraday)")
    p.add_argument("--data", default="../data")
    p.add_argument("--out", default=None, help="default: <data>/results/extension")
    a = p.parse_args(argv)
    run(a.data, a.out)


if __name__ == "__main__":
    main()
