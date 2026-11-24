"""Report figures from result files (aggregates only). Run: .venv/bin/python reports/make_figures.py"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ZH = "/System/Library/Fonts/STHeiti Medium.ttc"
fm.fontManager.addfont(ZH)
plt.rcParams.update({"font.family": fm.FontProperties(fname=ZH).get_name(), "axes.unicode_minus": False,
                     "font.size": 10, "figure.dpi": 150})

R = Path(__file__).resolve().parents[1].parent / "data" / "results"
OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)
H = ["1s", "5s", "10s", "30s", "1m", "5m", "30m"]


def fig_curves():
    c = pd.read_parquet(R / "stage3/curves.parquet")
    c["grp"] = c["cut"] + ":" + c["group"].fillna("all")
    groups = [("all:all", "全部", "#333333", "-"), ("spot_1s:favourable", "成交前一秒現貨有利", "#c0392b", "-"),
              ("spot_1s:none", "成交前一秒現貨未動", "#2471a3", "-")]
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    x = np.arange(len(H))
    for g, lab, col, _ in groups:
        for pre, ls, suffix in (("M_", "-", ""), ("M_dt_", "--", "（去趨勢）")):
            v = c[(c["grp"] == g) & c["value"].isin([pre + h for h in H])].set_index("horizon").reindex(H)
            if pre == "M_dt_" and g == "all:all":
                continue
            ax.plot(x, v["mean_bps"], ls, color=col, marker="o", ms=3, lw=1.4, label=lab + suffix)
    ax.set_xticks(x, H)
    ax.set_xlabel("成交後經過時間 h")
    ax.set_ylabel("M(h)（bps）")
    ax.axhline(0, color="#999999", lw=0.6)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig1_markout_curves.pdf")
    fig.savefig(OUT / "fig1_markout_curves.png")


def fig_heatmap():
    h = pd.read_parquet(R / "stage5/heatmap.parquet")
    h = h[(h["sample"] == "train") & (h["value"] == "gap_neutral")]
    deltas = ["<0.2", "0.2–0.4", "0.4–0.6", ">0.6"]
    dtes = ["1–30", "31–90", "91–180", ">180"]
    sizes = ["<1萬", "1–10萬", ">10萬"]
    rows = [(d, t) for d in deltas for t in dtes]
    m = np.full((len(rows), len(sizes)), np.nan)
    for i, (d, t) in enumerate(rows):
        for j, s in enumerate(sizes):
            v = h[(h["delta_bucket"] == d) & (h["dte_bucket"] == t) & (h["notional_bucket"] == s)]["mean_bps"]
            if len(v):
                m[i, j] = v.iloc[0]
    lim = np.nanpercentile(np.abs(m), 90)
    fig, ax = plt.subplots(figsize=(4.6, 6.4))
    im = ax.imshow(m, cmap="RdBu", vmin=-lim, vmax=lim, aspect="auto")
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            ax.text(j, i, "" if np.isnan(m[i, j]) else f"{m[i, j]:.0f}", ha="center", va="center", fontsize=7.5,
                    color="black" if np.isnan(m[i, j]) or abs(m[i, j]) < 0.6 * lim else "white")
    ax.set_xticks(range(len(sizes)), ["< 1 萬元", "1–10 萬元", "> 10 萬元"])
    ax.set_yticks(range(len(rows)), [f"|delta| {d} × {t} 天" for d, t in rows], fontsize=8)
    ax.set_xlabel("委託金額")
    cb = fig.colorbar(im, ax=ax, shrink=0.6)
    cb.set_label("定價缺口 ES − BE（bps）")
    fig.tight_layout()
    fig.savefig(OUT / "fig2_pricing_gap.pdf")
    fig.savefig(OUT / "fig2_pricing_gap.png")


if __name__ == "__main__":
    fig_curves()
    fig_heatmap()
    print(sorted(p.name for p in OUT.iterdir()))
