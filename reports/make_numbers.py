"""Every number cited in reports/report_draft.md, regenerated from the result files (aggregates only).

Run: .venv/bin/python reports/make_numbers.py  ->  reports/numbers.md
Each section names its source file; the report cites only numbers that appear here.
"""

from pathlib import Path

import numpy as np
import pandas as pd

R = Path(__file__).resolve().parents[1].parent / "data" / "results"
OUT = Path(__file__).resolve().parent / "numbers.md"
lines = []


def rd(p):
    return pd.read_parquet(R / p)


def sec(title, src):
    lines.append(f"\n## {title}\n\n來源：`{src}`\n")


def tab(df, digits=1):
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]) and (c in ("p", "p_bh", "spearman_p", "spearman_rho", "p_one_sided", "p_train", "p_test")
                                                    or "share" in c or c.startswith("corr")):
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else (f"{v:.3g}" if abs(v) < 0.001 and v != 0 else f"{v:.4f}"))
        elif pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else (f"{v:.3g}" if abs(v) < 0.01 and v != 0 else f"{v:,.{digits}f}"))
    df = df.astype(str).replace({"nan": "", "None": "", "<NA>": ""})
    lines.append("| " + " | ".join(map(str, df.columns)) + " |")
    lines.append("|" + "---|" * len(df.columns))
    lines.extend("| " + " | ".join("" if pd.isna(x) else str(x) for x in r) + " |" for r in df.to_numpy(dtype=object).tolist())
    lines.append("")


def pick(df, cols):
    return df[[c for c in cols if c in df.columns]]


S = ["mean_bps", "se_bps", "t", "p", "n", "n_days"]

# --- data ---------------------------------------------------------------------------------------
sec("資料：覆蓋率（每月）", "validation/coverage_months.parquet")
cm = rd("validation/coverage_months.parquet")
tab(pd.DataFrame([{"months": len(cm), "min_month_coverage_tick": cm["coverage_tick"].min(),
                   "min_month": cm.loc[cm["coverage_tick"].idxmin(), "month"], "missing_warrant_days": cm["n_missing"].sum()}]), 4)
cc = rd("validation/coverage_cells.parquet")
tab(pd.DataFrame([{"min_cell_coverage_tick": cc["coverage_tick"].min(),
                   "min_cell": f'{cc.loc[cc["coverage_tick"].idxmin(), "month"]} {cc.loc[cc["coverage_tick"].idxmin(), "dte_bucket"]}'}]), 4)
sec("資料：成交當下報價缺失原因（全樣本）", "validation/premid_missing_all.parquet")
tab(rd("validation/premid_missing_all.parquet"), 4)
sec("附錄 A：規則 A'' 驗證（2025）", "validation/train2025/premid_*.parquet")
for f in ("premid_missing_all", "premid_other_side_agreement", "premid_reaction_test", "premid_sweep_check"):
    lines.append(f"**{f}**\n")
    tab(rd(f"validation/train2025/{f}.parquet"), 4)
sec("資料：可用樣本（2025）", "stage3/exclusions.parquet")
tab(rd("stage3/exclusions.parquet"), 3)
sec("資料：delta 正負號", "validation/delta_sign.parquet")
ds = rd("validation/delta_sign.parquet")
tab(ds.groupby("kind")[["n", "n_bad"]].sum().reset_index(), 0)
sec("資料：時鐘領先落後（合併相關峰值，100 ms 與 10 ms 格點）", "validation/clock_lead_lag*.parquet")
for f in ("clock_lead_lag", "clock_lead_lag_fine"):
    c = rd(f"validation/{f}.parquet")
    pooled = c.groupby("lag_s")["corr"].mean()
    cc_ = c.dropna(subset=["corr"]); daily = cc_.loc[cc_.groupby("day")["corr"].idxmax()]
    tab(pd.DataFrame([{"file": f, "pooled_peak_lag_s": pooled.idxmax(), "daily_peak_median_s": daily["lag_s"].median(),
                       "days_peak_negative": int((daily["lag_s"] < 0).sum()), "n_days": daily["day"].nunique()}]), 3)

# --- stage 3 --------------------------------------------------------------------------------------
dec = rd("stage3/decomposition.parquet")
sec("H1：價差拆解與淨收益（2025，全部）", "stage3/decomposition.parquet")
tab(pick(dec[dec["cut"] == "all"], ["value"] + S))
sec("H1：按方向與四象限（中性淨收益、ES、M_dt）", "stage3/decomposition.parquet")
tab(pick(dec[dec["cut"].isin(["direction", "quadrant"]) & dec["value"].isin(["ES", "M_dt_5m", "net_neutral"])], ["cut", "group", "value"] + S))
sec("H1：等權重", "stage3/decomposition_equal.parquet")
de = rd("stage3/decomposition_equal.parquet")
tab(pick(de[(de["cut"] == "all") & de["value"].isin(["ES", "M_dt_5m", "net_neutral"])], ["value"] + S))
sec("H1：鎖死日敏感度", "extension/locked_sensitivity_2025.parquet")
tab(pick(rd("extension/locked_sensitivity_2025.parquet"), ["sample", "value"] + S))
sec("H2：主要切法 M_dt(5m)", "stage3/decomposition.parquet")
tab(pick(dec[(dec["cut"] != "all") & (dec["value"] == "M_dt_5m")], ["cut", "group"] + S))
sec("H2：|delta| × 到期天數（M_dt 與中性淨收益）", "stage3/delta_dte.parquet")
tab(pick(rd("stage3/delta_dte.parquet"), ["delta_bucket", "dte_bucket", "value", "mean_bps", "se_bps", "p", "p_bh", "n", "pre_specified"]))
sec("H2：markout 曲線（未去趨勢與去趨勢）", "stage3/curves.parquet")
cu = rd("stage3/curves.parquet")
cu["grp"] = cu["cut"] + ":" + cu["group"].fillna("all")
keep = ["all:all", "spot_1s:favourable", "spot_1s:none", "dte_bucket:1–30", "dte_bucket:>180"]
for pre in ("M_", "M_dt_"):
    c = cu[cu["grp"].isin(keep) & cu["value"].str.match(pre + r"(1s|5s|10s|30s|1m|5m|30m|close)$")]
    tab(c.pivot_table(index="grp", columns="horizon", values="mean_bps")[["1s", "5s", "10s", "30s", "1m", "5m", "30m", "close"]].reset_index())
sec("H3：發行商（組成控制後）", "stage4/h3_issuers.parquet")
tab(rd("stage4/h3_issuers.parquet"))
sec("H4：迴歸（2025）", "stage3/h4_regressions.parquet")
h4 = rd("stage3/h4_regressions.parquet")
tab(pick(h4[h4["term"].str.startswith("F_")], ["horizon", "spec", "term", "main", "coef", "se", "p", "p_bh", "n", "n_days"]), 2)
fl = pd.concat([pd.read_parquet(f, columns=["F_norm"]) for f in sorted((R.parent / "flow").glob("2025-*.parquet"))])
tab(pd.DataFrame([{"F_norm_sd_2025_all_grid": fl["F_norm"].std(), "n": fl["F_norm"].notna().sum()}]), 4)
tab(pick(h4[h4["main"] & (h4["term"] != "F_norm") & ~h4["term"].str.startswith("tod")], ["term", "coef", "se", "t", "p"]), 3)
sec("H4：流量相關", "stage3/h4_flow_correlations.parquet")
tab(rd("stage3/h4_flow_correlations.parquet"), 3)
sec("散戶延遲套利上限（現貨剛有利）", "stage3/retail_latency.parquet")
tab(pick(rd("stage3/retail_latency.parquet"), ["direction", "value", "horizon", "mean_bps", "se_bps", "n"]))

sec("2330 股價與現股價差（所有 panel 成交的簡單中位數）", "panel/tsmc_warrant_trades（S_mid、S_spread_bps）")
rows = []
for y in ("2025", "2026"):
    fs = sorted((R.parent / "panel" / "tsmc_warrant_trades").glob(f"{y}-*.parquet"))
    import pyarrow.parquet as pq
    fs = [f for f in fs if {"S_mid", "S_spread_bps"} <= set(pq.read_schema(f).names) and "2025-01-02" <= f.stem <= "2026-11-18"
          and f.stem != "2026-01-09"]
    pdx = pd.concat([pd.read_parquet(f, columns=["S_mid", "S_spread_bps"]) for f in fs], ignore_index=True)
    rows.append({"year": y, "n_files": len(fs), "median_S_mid": pdx["S_mid"].median(), "median_S_spread_bps": pdx["S_spread_bps"].median()})
tab(pd.DataFrame(rows))

sec("表 1：敘述統計（panel 全部成交；|delta| 只計有 delta 的成交）", "panel/tsmc_warrant_trades")
import pyarrow.parquet as pq
t1 = []
for y in ("2025", "2026"):
    fs = sorted((R.parent / "panel" / "tsmc_warrant_trades").glob(f"{y}-*.parquet"))
    cols = ["warrant_id", "kind", "notional", "T", "delta", "side", "issuer"]
    fs = [f for f in fs if set(cols) <= set(pq.read_schema(f).names) and "2025-01-02" <= f.stem <= "2026-11-18"
          and f.stem != "2026-01-09"]
    d = pd.concat([pd.read_parquet(f, columns=cols) for f in fs], ignore_index=True)
    W = d["notional"].sum()
    dte = pd.cut(d["T"] * 365, [0, 30, 90, 180, np.inf], labels=["1–30", "31–90", "91–180", ">180"])
    dl = pd.cut(d["delta"].abs(), [0, 0.2, 0.4, 0.6, np.inf], labels=["<0.2", "0.2–0.4", "0.4–0.6", ">0.6"])
    row = {"year": y, "days": len(fs), "trades": len(d), "notional_billion_twd": W / 1e9,
           "warrants": d["warrant_id"].nunique(), "issuers": d["issuer"].nunique(),
           "call_share_notional": d.loc[d["kind"] == "call", "notional"].sum() / W,
           "buy_share_notional": d.loc[d["side"] > 0, "notional"].sum() / W}
    for k, v in d.groupby(dte, observed=True)["notional"].sum().items():
        row[f"dte_{k}_share"] = v / W
    Wd = d.loc[d["delta"].notna(), "notional"].sum()
    for k, v in d.groupby(dl, observed=True)["notional"].sum().items():
        row[f"delta_{k}_share"] = v / Wd
    t1.append(row)
tab(pd.DataFrame(t1).set_index("year").T.reset_index().rename(columns={"index": "item"}), 3)

# --- stage 4 --------------------------------------------------------------------------------------
sec("安慰劑：同日置換", "stage4/placebo_permutation.parquet")
tab(rd("stage4/placebo_permutation.parquet"), 3)
sec("安慰劑：隨機時點", "stage4/placebo_random_time.parquet")
tab(rd("stage4/placebo_random_time.parquet"), 3)
sec("現貨剛成交（S_age ≤ 0.1 秒）", "stage4/staleness.parquet")
tab(pick(rd("stage4/staleness.parquet"), ["spot_print", "direction", "value"] + S))
sec("動能", "stage4/momentum.parquet")
tab(rd("stage4/momentum.parquet"), 3)
sec("穩健性變體", "stage4/variants.parquet")
tab(pick(rd("stage4/variants.parquet"), ["variant", "value", "delta_bucket", "mean_bps", "se_bps", "p", "base_bps", "robust"]))
sec("H4 穩健性", "stage4/h4_checks.parquet, h4_tails.parquet")
hc = rd("stage4/h4_checks.parquet")
tab(pick(hc[hc["term"].str.startswith("F")], ["check", "term", "coef", "se", "p"]), 2)
tab(rd("stage4/h4_tails.parquet"), 2)

# --- stage 5 --------------------------------------------------------------------------------------
sec("樣本外：執行紀錄", "stage5/meta.parquet")
tab(rd("stage5/meta.parquet"))
sec("樣本外：毒性分數五分位", "stage5/quintiles_*.parquet, q5_minus_q1_*.parquet, r2.parquet")
for f in ("quintiles_train", "quintiles_test", "wf_quintiles"):
    q = rd(f"stage5/{f}.parquet")
    tab(pick(q, ["quintile", "mean_bps", "se_bps", "n"]).assign(file=f))
for f in ("q5_minus_q1_train", "q5_minus_q1_test", "wf_q5_minus_q1"):
    tab(pick(rd(f"stage5/{f}.parquet"), ["coef", "se", "t", "p", "n", "n_days"]).assign(file=f), 2)
tab(rd("stage5/r2.parquet"), 4)
co = rd("stage5/coefficients.parquet")
lines.append(f"coefficients 欄位：{list(co.columns)}\n")
tab(co.head(60), 2)
sec("樣本外：熱力圖彙總", "stage5/heatmap_summary.parquet")
tab(rd("stage5/heatmap_summary.parquet"), 3)
hm = rd("stage5/heatmap.parquet")
lines.append(f"heatmap 欄位：{list(hm.columns)}\n")
wfc = rd("stage5/wf_heatmap_cells.parquet")
tab(pd.DataFrame([{"wf_sign_agree_share": wfc["sign_agree"].mean(), "n_cells": len(wfc)}]), 3)
sec("樣本外：H4 交易", "stage5/h4_trading.parquet, wf_h4_trading.parquet")
tab(rd("stage5/h4_trading.parquet"), 2)
tab(rd("stage5/wf_h4_trading.parquet"), 2)
sec("樣本外：2026 價差拆解（全部）", "stage5/test_decomposition.parquet")
td = rd("stage5/test_decomposition.parquet")
tab(pick(td[td["cut"] == "all"], ["value"] + S))
sec("樣本外：重現", "stage5/replication.parquet")
rp = rd("stage5/replication.parquet")
sig = rp["p_train"] < 0.05
tab(pd.DataFrame([{"n_items": len(rp), "sig_2025": int(sig.sum()), "reproduced": int(rp.loc[sig, "sign_and_significance"].sum()),
                   "stable_all": rp["stable"].mean(), "stable_among_sig": rp.loc[sig, "stable"].mean()}]), 3)
tab(pick(rp[rp["cut"] == "all"], ["value", "mean_bps_train", "se_bps_train", "mean_bps_test", "se_bps_test", "z_diff", "stable"]))
tab(pick(rp[rp["cut"].isin(["dte_bucket", "high_gamma", "h4"])], ["cut", "group", "value", "mean_bps_train", "mean_bps_test", "z_diff", "stable", "sign_and_significance"]))
lines.append("**2025 顯著但未重現的項目**\n")
tab(pick(rp[sig & (rp["sign_and_significance"] != 1)], ["cut", "group", "value", "mean_bps_train", "mean_bps_test", "p_test"]))

# --- extensions -----------------------------------------------------------------------------------
for y in ("2025", "2026"):
    sec(f"經濟規模（{y}）", f"report/magnitude_{y}.parquet")
    tab(rd(f"report/magnitude_{y}.parquet"), 3)
for y in ("2025", "2026"):
    sec(f"B 短天期缺報價（{y}）", f"extension/b_estimate_{y}.parquet, b_validation_{y}.parquet")
    tab(rd(f"extension/b_estimate_{y}.parquet"), 2)
    tab(pick(rd(f"extension/b_validation_{y}.parquet"), ["group_set", "group", "mean_bps", "ci_lo_bps", "ci_hi_bps", "within_margin", "criterion"]), 2)
    sec(f"C1（{y}）", f"extension/c1_*_{y}.parquet")
    tab(rd(f"extension/c1_coefficients_{y}.parquet"), 2)
    tab(rd(f"extension/c1_size_{y}.parquet"), 4)
    sec(f"C2（{y}）", f"extension/c2_*_{y}.parquet")
    tab(rd(f"extension/c2_markout_{y}.parquet"))
    tab(rd(f"extension/c2_h4_{y}.parquet"))
sec("D 合併部位", "extension/d_netting.parquet")
tab(rd("extension/d_netting.parquet"), 2)
for y in ("2025", "2026"):
    sec(f"E 動態避險（{y}，全部成交）", f"extension/e_main_{y}.parquet")
    e = rd(f"extension/e_main_{y}.parquet")
    e = e[(e["cut"] == "all")]
    tab(e.pivot_table(index=["sample", "level", "horizon", "latency", "rebalance", "ladder"], columns="value", values="mean_bps").reset_index())
    eh = rd(f"extension/e_main_{y}.parquet")
    eh = eh[(eh["cut"].isin(["high_gamma", "direction"])) & (eh["sample"] == "all") & (eh["latency"] == "1s")]
    tab(eh.pivot_table(index=["cut", "group", "level", "horizon", "rebalance", "ladder"], columns="value", values="mean_bps").reset_index())
for y in ("2025", "2026"):
    sec(f"誰賺誰虧：當日（{y}，整體與 16 格）", f"extension/retail_map_{y}.parquet")
    m = rd(f"extension/retail_map_{y}.parquet")
    m = m[(m["sample"] == "buys") & m["group_set"].isin(["all", "cell", "spot_1s", "iv", "tx", "tod", "chase"])]
    tab(m.pivot_table(index=["group_set", "group"], columns="value", values="mean_bps")[
        [c for c in ["trader_5m", "trader_raw_5m", "trader_close", "mm_neutral_5m", "leakage"] if c in m["value"].unique()]].reset_index())
    q = rd(f"extension/retail_quadrants_{y}.parquet")
    tab(q["quadrant"].value_counts().rename_axis("quadrant").reset_index(), 0)
for y in ("2025", "2026"):
    sec(f"誰賺誰虧：跨日（{y}）", f"extension/retail_multiday_*_{y}.parquet")
    md = rd(f"extension/retail_multiday_map_{y}.parquet")
    a = md[md["group_set"] == "all"]
    tab(a.pivot_table(index="hold", columns="value", values="mean_bps").reset_index())
    c = md[(md["group_set"] == "cell") & (md["hold"] == 5) & md["value"].isin(["hold_resid_5", "hold_dt_5"])]
    tab(c.pivot_table(index="group", columns="value", values="mean_bps").reset_index())
    sigp = md[md["include"] & (md["group_set"] != "all") & md["value"].str.startswith("hold_dt_")]
    tab(pd.DataFrame([{"sig_pos": int(((sigp["p_bh"] < .05) & (sigp["mean_bps"] > 0)).sum()),
                       "sig_neg": int(((sigp["p_bh"] < .05) & (sigp["mean_bps"] < 0)).sum())}]), 0)
    tab(rd(f"extension/retail_multiday_summary_{y}.parquet"), 3)
    tab(rd(f"extension/retail_multiday_quadrants_{y}.parquet")["quadrant"].value_counts().rename_axis("quadrant").reset_index(), 0)
for y in ("2025", "2026"):
    sec(f"跨發行商比價（{y}）", f"extension/compare_*_{y}.parquet")
    tab(rd(f"extension/compare_terciles_{y}.parquet"))
    tab(rd(f"extension/compare_premium_corr_{y}.parquet"), 3)
    ci = rd(f"extension/compare_issuers_{y}.parquet")
    tab(ci.pivot_table(index="issuer", columns="outcome", values="vs_avg_bps").join(
        ci.groupby("issuer")[["share_notional", "mean_iv_prem_pts", "mean_spread_prem_bps"]].first()).reset_index())
    tab(ci.pivot_table(index="issuer", columns="outcome", values="p_bh").reset_index(), 3)

OUT.write_text("# 報告數字表（由 reports/make_numbers.py 自動產生，勿手改）\n" + "\n".join(lines), encoding="utf-8")
print(OUT, len(lines))
