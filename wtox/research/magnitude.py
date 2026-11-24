"""Economic magnitude of toxicity (report, descriptive; no new test, no registration needed).

For each group g: notional share s_g, mean issuer net (neutral, 5m) n_g, and its contribution s_g x n_g to
the overall mean (the contributions sum to the overall notional-weighted mean), plus the NTD total
sum(notional x net). Answers "why do toxic groups not sink the issuer": how much flow they carry.
Groups: |delta| x DTE cells, spot moved in the trader's favour in the last 1 s, 2330 just printed
(<= 0.1 s, stage 4), time of day.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wtox.research import config, toxicity

GROUPS = {"cell": ["delta_bucket", "dte_bucket"], "spot_1s": ["spot_1s"], "spot_print": ["spot_print"], "tod": ["tod"]}


def magnitude(d):
    """d: stage 3 frame restricted to 5m-usable trades with net_neutral, M_dt_5m, ES, weight (notional)."""
    W = d["weight"].sum()
    overall = float((d["weight"] * d["net_neutral"]).sum() / W)
    rows = []
    for name, by in GROUPS.items():
        for key, g in d.groupby(by, observed=True):
            key = key if isinstance(key, tuple) else (key,)
            w = g["weight"]
            share = float(w.sum() / W)
            net = float((w * g["net_neutral"]).sum() / w.sum())
            rows.append({"group_set": name, "group": "|".join(map(str, key)), "share_notional": share,
                         "share_trades": len(g) / len(d), "ES_bps": float((w * g["ES"]).sum() / w.sum()) * 1e4,
                         "M_dt_bps": float((w * g["M_dt_5m"]).sum() / w.sum()) * 1e4, "net_neutral_bps": net * 1e4,
                         "contribution_bps": share * net * 1e4, "net_ntd": float((w * g["net_neutral"]).sum()),
                         "overall_net_bps": overall * 1e4})
    return pd.DataFrame(rows)


def frame(days, data_dir):
    d, _ = toxicity.build(days, Path(data_dir))
    d = d[~d["trunc_5m"].astype(bool)].copy()
    d["net_neutral"] = d["RS_dt_5m"] - d["cost_neutral"]
    d["spot_print"] = np.where(d["S_age_s"] <= config.STALE_SPOT_MAX_AGE_S, "just_ticked", "quiet")
    return d[["datetime", "weight", "net_neutral", "M_dt_5m", "ES", "delta_bucket", "dte_bucket", "spot_1s",
              "spot_print", "tod"]]


def run(data_dir, out_dir=None):
    data_dir = Path(data_dir)
    out_dir = Path(out_dir or data_dir / "results" / "report")
    out_dir.mkdir(parents=True, exist_ok=True)
    days = sorted(p.stem for p in (data_dir / "panel" / "tsmc_warrant_trades").glob("*.parquet") if config.in_sample(p.stem))
    for label, ds in [("2025", [x for x in days if x <= config.TRAIN_END]), ("2026", [x for x in days if x >= config.TEST_START])]:
        if ds:
            magnitude(frame(ds, data_dir)).to_parquet(out_dir / f"magnitude_{label}.parquet", index=False)


def main(argv=None):
    p = argparse.ArgumentParser(description="Economic magnitude of toxic groups (report table)")
    p.add_argument("--data", default="../data")
    run(p.parse_args(argv).data)


if __name__ == "__main__":
    main()
