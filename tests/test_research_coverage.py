"""Coverage: join on exchange code + date, capped coverage, DTE buckets, standard gate."""

import pandas as pd
import pytest

from wtox.research import coverage


def _tej():
    return pd.DataFrame({
        "date": pd.to_datetime(["2025-03-03"] * 3 + ["2025-04-01"]),
        "warrant_id": ["030001", "030002", "03962T", "030001"], "tej_id": ["030001", "030002", "03962TZ", "030001"],
        "kind": ["call", "call", "put", "call"], "days_to_expiry": [10, 200, 30, 31],
        "tej_volume": [100, 50, 40, 10],
    })


def _ticks():
    # 030001 has extra prints (120 > 100), 030002 is missing, the put is half covered
    return pd.DataFrame({"date": pd.to_datetime(["2025-03-03", "2025-03-03", "2025-04-01", "2025-03-03"]),
                         "warrant_id": ["030001", "03962T", "030001", "099999"], "tick_volume": [120, 20, 10, 7]})


def test_capped_coverage_by_month_and_bucket():
    d = coverage.warrant_days(_tej(), _ticks())
    assert len(d) == 4                                  # ticks of warrants TEJ did not trade are ignored
    cells, months = coverage.coverage_tables(d)
    c = cells.set_index(["month", "dte_bucket"])["coverage_tick"]
    mar = pd.Period("2025-03", "M")
    assert c[(mar, "1–30")] == pytest.approx((100 + 20) / (100 + 40))    # extra prints capped at TEJ volume
    assert c[(mar, ">180")] == 0
    assert c[(pd.Period("2025-04", "M"), "31–90")] == 1                 # DTE 31 falls in 31–90
    m = months.set_index("month")
    assert m.loc[mar, "coverage_tick"] == pytest.approx(120 / 190)
    assert m.loc[mar, "ratio_tick"] == pytest.approx(140 / 190)
    assert m.loc[mar, "n_missing"] == 1
    assert m.loc[mar, "coverage_count"] == pytest.approx(2 / 3)


def test_consistent_pool_filter_and_panel_column():
    panel = pd.DataFrame({"date": pd.to_datetime(["2025-03-03"]), "warrant_id": ["030001"], "panel_volume": [90]})
    d = coverage.warrant_days(_tej(), _ticks(), panel)
    cells, months = coverage.coverage_tables(d, buckets=[">180"])
    assert months["n_warrant_days"].sum() == 1                       # only the 200-day warrant
    _, months = coverage.coverage_tables(d)
    assert months.set_index("month").loc[pd.Period("2025-03", "M"), "coverage_panel"] == pytest.approx(90 / 190)


def test_standard_must_be_set_before_use(monkeypatch):
    cells, months = coverage.coverage_tables(coverage.warrant_days(_tej(), _ticks()))
    monkeypatch.setattr(coverage.config, "COVERAGE_MIN_CELL", None)
    monkeypatch.setattr(coverage.config, "COVERAGE_MIN_MONTH", None)
    with pytest.raises(RuntimeError):
        coverage.passes(cells, months)
    cells, months = coverage.passes(cells, months, min_cell=0.95, min_month=0.98)
    assert months["ok"].tolist() == [False, True]


def test_tick_volume_reads_whole_day(tmp_path):
    day = tmp_path / "shioaji" / "ticks" / "2025-03-03"
    day.mkdir(parents=True)
    pd.DataFrame({"volume": [3, 4]}).to_parquet(day / "030001.parquet")
    t = coverage.load_tick_volume(tmp_path, ["2025-03-03", "2025-03-04"])
    assert t.to_dict("records") == [{"date": pd.Timestamp("2025-03-03"), "warrant_id": "030001", "tick_volume": 7}]


def test_split_tej_ids_count_once_and_expiry_day_is_kept():
    raw = pd.DataFrame({"date": pd.to_datetime(["2025-03-03", "2025-03-03", "2025-03-04"]),
                        "warrant_id": ["041993T", "041993", "041993"], "volume": [30, 30, 5]})
    d = coverage._dedupe_by_code(raw)
    assert len(d) == 2
    tej = _tej().assign(days_to_expiry=[0, 200, 30, 31])           # an expiry-day row
    cells, months = coverage.coverage_tables(coverage.warrant_days(tej, _ticks()))
    assert "≤0" in set(cells["dte_bucket"]) and cells["tej_volume"].sum() == months["tej_volume"].sum()
