"""Backfill tests against a fake Shioaji API (no network, no credentials)."""

from types import SimpleNamespace

import pandas as pd
import pytest

from wtox.data.backfill import exchange_code, run, work_list


@pytest.mark.parametrize("tej_id, code", [
    ("070962", "070962"),    # call
    ("086717U", "086717"),   # reused call code
    ("04088P", "04088P"),    # put
    ("03962TZ", "03962T"),   # reused put code
])
def test_exchange_code_drops_tej_reuse_letter(tej_id, code):
    assert exchange_code(tej_id) == code


def _tej(tmp_path, rows):
    d = tmp_path / "tej" / "daily"
    d.mkdir(parents=True)
    pd.DataFrame(rows, columns=["date", "warrant_id", "underlying_id", "volume"]).assign(
        date=lambda x: pd.to_datetime(x["date"])).to_parquet(d / "part1_earlier_exports.parquet")


def test_work_list_maps_codes_filters_and_skips_files_on_disk(tmp_path):
    _tej(tmp_path, [
        ("2025-03-03", "086717U", "2330", 100),
        ("2025-03-03", "04088P", "2330", 5),
        ("2025-03-03", "070962", "2330", 0),       # no trade
        ("2025-03-03", "011111", "2317", 50),      # other underlying
        ("2025-03-04", "086717U", "2330", 7),
        ("2024-12-31", "086717U", "2330", 7),      # before start
    ])
    have = tmp_path / "shioaji" / "ticks" / "2025-03-04"
    have.mkdir(parents=True)
    (have / "086717.parquet").write_bytes(b"x")
    todo = work_list(tmp_path, "2025-01-02", "2025-12-31")
    assert todo[["day", "code", "tej_id"]].values.tolist() == [
        ["2025-03-03", "04088P", "04088P"], ["2025-03-03", "086717", "086717U"]]


class FakeAPI:
    def __init__(self, empty=(), fail=(), cost=1000, limit=10**9):
        self.empty, self.fail = set(empty), set(fail)
        self.bytes, self.cost, self.limit = 0, cost, limit
        self.calls = []

    def usage(self):
        return SimpleNamespace(bytes=self.bytes, remaining_bytes=self.limit - self.bytes)

    def ticks(self, contract, date):
        self.calls.append((contract.code, date))
        self.bytes += self.cost
        if contract.code in self.fail:
            raise TimeoutError("boom")
        n = 0 if contract.code in self.empty else 2
        ts = [int(pd.Timestamp(f"{date} 10:00:0{i}").value) for i in range(n)]
        return SimpleNamespace(ts=ts, close=[1.0] * n, volume=[3] * n, bid_price=[0.9] * n, bid_volume=[10] * n,
                               ask_price=[1.0] * n, ask_volume=[10] * n, tick_type=[1] * n)


def _todo():
    return pd.DataFrame([("2025-03-03", "086717", "086717U", 6), ("2025-03-03", "04088P", "04088P", 5),
                         ("2025-03-04", "086717", "086717U", 6)], columns=["day", "code", "tej_id", "tej_volume"])


def _run(api, tmp_path, todo, **kw):
    return run(api, tmp_path, todo, lambda c: SimpleNamespace(code=c), SimpleNamespace(code="2330"),
               throttle=0, log=lambda *_: None, **kw)


def test_run_writes_ticks_underlying_and_log(tmp_path):
    api = FakeAPI(empty={"04088P"})
    s = _run(api, tmp_path, _todo())
    assert (s["files"], s["empty"], s["errors"], s["days"]) == (2, 1, 0, 2)
    w = pd.read_parquet(tmp_path / "shioaji/ticks/2025-03-03/086717.parquet")
    assert list(w.columns[:2]) == ["warrant_id", "close"] and w["warrant_id"].eq("086717").all()
    assert not (tmp_path / "shioaji/ticks/2025-03-03/04088P.parquet").exists()  # empty -> retried next run
    assert (tmp_path / "shioaji/underlying_ticks/stock/2330/2025-03-04.parquet").exists()
    lg = pd.read_parquet(tmp_path / "shioaji/backfill_log/2025-03-03.parquet").set_index("code")
    assert lg.loc["086717", "tick_volume"] == 6 and lg.loc["086717", "tej_volume"] == 6
    assert lg.loc["04088P", "n_ticks"] == 0


def test_errors_are_logged_and_do_not_stop_the_run(tmp_path):
    api = FakeAPI(fail={"04088P"})
    s = _run(api, tmp_path, _todo())
    assert s["errors"] == 1 and s["files"] == 2
    lg = pd.read_parquet(tmp_path / "shioaji/backfill_log/2025-03-03.parquet").set_index("code")
    assert lg.loc["04088P", "error"] == "TimeoutError"


def test_budget_stops_and_newest_day_goes_first(tmp_path):
    api = FakeAPI(cost=300_000)
    s = _run(api, tmp_path, _todo(), max_mb=0.5)
    assert s["stopped_by_budget"] and s["days"] == 1
    assert api.calls[0][1] == "2025-03-04"  # newest first
