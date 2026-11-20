"""Rebuild everything in order (CLAUDE.md §4): python -m wtox.research.pipeline --data ../data

Steps: panel -> labels -> stage 2 validation (coverage, missing pre-trade quotes, IV checks, clock)
-> stage 3 (flow features, toxicity tables, H4 in-sample regressions; training period only).
Dividends are downloaded separately (network): python -m wtox.research.dividends --data ../data.
Validation outputs go to <data>/results/validation; the coverage pass/fail gate (coverage.passes)
is applied by hand only after the standard is written into CLAUDE.md §10.
"""

import argparse
from pathlib import Path

from wtox.research import clock, config, coverage, dividends, flow, ivcheck, markout, quotes, toxicity, trades

STEPS = ("panel", "labels", "coverage", "quotes", "ivcheck", "clock", "flow", "toxicity", "h4")


def run(data, steps=STEPS, rebuild=False):
    data = Path(data)
    panel_dir = data / "panel" / "tsmc_warrant_trades"
    val = data / "results" / "validation"
    flag = ["--rebuild"] if rebuild else []
    for step in steps:
        print(f"== {step}")
        if step not in ("panel", "clock"):
            trades.check_schema(panel_dir)
        if step == "panel":
            trades.main(["--data", str(data), "--out", str(panel_dir), *flag])
        elif step == "labels":
            markout.main(["--data", str(data), "--panel", str(panel_dir), *flag])
        elif step == "coverage":
            coverage.run(data, val, panel_dir)
        elif step == "quotes":
            quotes.run(data, val, panel_dir)
        elif step == "ivcheck":
            has_div = (data / config.DIVIDEND_FILE).exists()
            if not has_div:
                print("   no dividend file: ex-date tags left empty")
            ivcheck.run(data, val, panel_dir, dividends.ex_dates(dividends.load(data)) if has_div else ())
        elif step == "clock":
            days = sorted(p.stem for p in panel_dir.glob("*.parquet") if config.in_sample(p.stem))
            clock.run(data, val, days)
        elif step == "flow":
            flow.run(data)
        elif step == "toxicity":
            toxicity.run(data)
        elif step == "h4":
            flow.run_h4(data)
        else:
            raise ValueError(f"unknown step {step!r}; choose from {STEPS}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Rebuild panel, labels and validation outputs")
    p.add_argument("--data", default="../data")
    p.add_argument("--steps", nargs="+", default=list(STEPS), choices=STEPS)
    p.add_argument("--rebuild", action="store_true", help="rebuild panel/labels files that already exist")
    a = p.parse_args(argv)
    run(a.data, a.steps, a.rebuild)


if __name__ == "__main__":
    main()
