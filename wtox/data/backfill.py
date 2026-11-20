"""Backfill historical warrant ticks from Shioaji, including warrants that have since been delisted.

Shioaji's contract list only holds warrants that are listed today, but its tick history still
serves delisted ones: build the contract by hand with ``sj.Stock(exchange, code)``.

The work list comes from TEJ daily data (every warrant-day with volume > 0), so coverage does not
depend on what is listed at download time. TEJ ids carry one extra trailing letter when an exchange
code has been reused (``086717U`` is exchange code ``086717``; ``03962TZ`` is ``03962T``); Shioaji
needs the exchange code. Files are written exactly like ``shioaji_source`` writes them:

    <data>/shioaji/ticks/<day>/<code>.parquet
    <data>/shioaji/underlying_ticks/stock/<underlying>/<day>.parquet

Each finished day also gets ``<data>/shioaji/backfill_log/<day>.parquet`` with ticks fetched vs
TEJ volume per warrant, for the coverage check. Re-running skips files already on disk, so a run
stopped by the budget or an error continues where it left off. Empty results are not written, so
they are retried next time.

    python -m wtox.data.backfill --data ../data --start 2025-01-02 --end 2026-11-18 \
        --env-file "<path to .env>" --max-mb 100000 --reserve-mb 100   # use the quota, keep 100 MB
"""

import argparse
import os
import re
import time
from pathlib import Path

import pandas as pd

from wtox.data.shioaji_source import TICK_COLUMNS, Budget, load_env_file, to_frame

TEJ_DAILY_FILES = ["part1_earlier_exports.parquet", "part2_delisted2026_2024_2025.parquet",
                   "part3_delisted2025_2023_2024.parquet"]
_REUSED = re.compile(r"^(\d{6}|\d{5}[A-Z])[A-Z]$")


def exchange_code(tej_id):
    """TEJ warrant id -> exchange code (drop TEJ's reuse letter on 7-character ids)."""
    m = _REUSED.match(tej_id)
    return m.group(1) if m else tej_id


def work_list(data_dir, start, end, underlying="2330"):
    """Warrant-days with TEJ volume > 0 in [start, end] whose tick file is not on disk yet."""
    data_dir = Path(data_dir)
    cols = ["date", "warrant_id", "underlying_id", "volume"]
    flt = [("underlying_id", "==", underlying), ("date", ">=", pd.Timestamp(start)), ("date", "<=", pd.Timestamp(end))]
    paths = [data_dir / "tej" / "daily" / f for f in TEJ_DAILY_FILES if (data_dir / "tej" / "daily" / f).exists()]
    d = pd.concat([pd.read_parquet(p, columns=cols, filters=flt) for p in paths], ignore_index=True)
    d = d[d["volume"] > 0].drop_duplicates(["date", "warrant_id"])
    d["day"] = d["date"].dt.strftime("%Y-%m-%d")
    d["code"] = d["warrant_id"].map(exchange_code)
    d = d.rename(columns={"warrant_id": "tej_id", "volume": "tej_volume"})
    ticks = data_dir / "shioaji" / "ticks"
    d["on_disk"] = [(ticks / day / f"{code}.parquet").exists() for day, code in zip(d["day"], d["code"])]
    return d.loc[~d["on_disk"], ["day", "code", "tej_id", "tej_volume"]].sort_values(["day", "code"]).reset_index(drop=True)


def _retry(fn, tries=3, wait=2.0):
    for i in range(tries):
        try:
            return fn()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(wait * (i + 1))


def _write(df, path):
    """Write via a temp file + rename, so an interrupted run never leaves a half file that looks done."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def run(api, data_dir, todo, make_contract, stock_contract, underlying="2330", max_mb=400.0,
        throttle=0.12, newest_first=True, log=print, reserve_mb=20.0):
    """Download every row of `todo` (from work_list). Returns a summary dict."""
    data_dir = Path(data_dir)
    out = data_dir / "shioaji"
    budget = Budget(api, max_mb, reserve_mb)
    summary = {"days": 0, "files": 0, "ticks": 0, "empty": 0, "errors": 0, "stopped_by_budget": False}
    days = sorted(todo["day"].unique(), reverse=newest_first)
    for n, day in enumerate(days, 1):
        if budget.exhausted():
            summary["stopped_by_budget"] = True
            break
        spath = out / "underlying_ticks" / "stock" / underlying / f"{day}.parquet"
        if not spath.exists():
            s = to_frame(_retry(lambda: api.ticks(stock_contract, date=day)), TICK_COLUMNS)
            if len(s):
                _write(s, spath)
            time.sleep(throttle)
        rows = []
        for r in todo[todo["day"] == day].itertuples(index=False):
            try:
                res = _retry(lambda: api.ticks(make_contract(r.code), date=day))
            except Exception as exc:  # keep going; the file stays missing and is retried next run
                summary["errors"] += 1
                rows.append((day, r.code, r.tej_id, r.tej_volume, -1, 0, type(exc).__name__))
                continue
            df = to_frame(res, TICK_COLUMNS)
            vol = int(df["volume"].sum()) if len(df) else 0
            if len(df):
                df.insert(0, "warrant_id", r.code)
                _write(df, out / "ticks" / day / f"{r.code}.parquet")
                summary["files"] += 1
                summary["ticks"] += len(df)
            else:
                summary["empty"] += 1
            rows.append((day, r.code, r.tej_id, r.tej_volume, len(df), vol, ""))
            time.sleep(throttle)
        lpath = out / "backfill_log" / f"{day}.parquet"
        new = pd.DataFrame(rows, columns=["day", "code", "tej_id", "tej_volume", "n_ticks", "tick_volume", "error"])
        if lpath.exists():  # a resumed day: keep earlier rows, newest result per code wins
            new = pd.concat([pd.read_parquet(lpath), new]).drop_duplicates("code", keep="last")
        _write(new, lpath)
        summary["days"] += 1
        if n % 10 == 0 or n == len(days):
            log(f"  {n}/{len(days)} 天（{day}），檔案 {summary['files']}，空 {summary['empty']}，"
                f"錯誤 {summary['errors']}，本次已用 {budget.used_mb():.1f} MB")
    summary["used_mb"] = round(budget.used_mb(), 1)
    log(f"完成：{summary}")
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description="Backfill historical (incl. delisted) warrant ticks from Shioaji")
    p.add_argument("--data", default="../data")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--underlying", default="2330")
    p.add_argument("--env-file", default=os.environ.get("SHIOAJI_ENV_FILE"))
    p.add_argument("--max-mb", type=float, default=400, help="cap on this run's usage")
    p.add_argument("--reserve-mb", type=float, default=20,
                   help="stop when the account's remaining daily quota falls to this (keep some for daily jobs)")
    p.add_argument("--limit-days", type=int, default=0, help="only the newest N days (for a trial run)")
    a = p.parse_args(argv)

    todo = work_list(a.data, a.start, a.end, a.underlying)
    if a.limit_days:
        keep = sorted(todo["day"].unique())[-a.limit_days:]
        todo = todo[todo["day"].isin(keep)]
    print(f"待抓：{len(todo)} 個權證 × 日，{todo['day'].nunique()} 天")
    if todo.empty:
        return

    if a.env_file:
        load_env_file(a.env_file)
    if not os.environ.get("SJ_API_KEY") or not os.environ.get("SJ_SEC_KEY"):
        raise SystemExit("請設定 SJ_API_KEY / SJ_SEC_KEY，或用 --env-file 指定 .env 檔")
    import shioaji as sj

    api = sj.Shioaji(simulation=False)
    api.login(api_key=os.environ["SJ_API_KEY"], secret_key=os.environ["SJ_SEC_KEY"],
              fetch_contract=True, contracts_timeout=60000)
    try:
        run(api, a.data, todo, lambda code: sj.Stock(exchange="TSE", code=code, security_type="STK"),
            api.Contracts.Stocks[a.underlying], a.underlying, a.max_mb, reserve_mb=a.reserve_mb)
    finally:
        try:
            api.logout()
        except Exception as exc:  # data is already saved
            print(f"登出逾時，可忽略：{type(exc).__name__}")


if __name__ == "__main__":
    main()
