"""Pipeline: steps run in the given order with the right paths; unknown steps fail."""

import pytest

from wtox.research import pipeline


def test_steps_run_in_order(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(pipeline.trades, "main", lambda argv: calls.append(("panel", argv)))
    monkeypatch.setattr(pipeline.markout, "main", lambda argv: calls.append(("labels", argv)))
    monkeypatch.setattr(pipeline.coverage, "run", lambda d, v, p: calls.append(("coverage", p)))
    monkeypatch.setattr(pipeline.quotes, "run", lambda d, v, p: calls.append(("quotes", p)))
    monkeypatch.setattr(pipeline.ivcheck, "run", lambda d, v, p, ex: calls.append(("ivcheck", ex)))
    monkeypatch.setattr(pipeline.clock, "run", lambda d, v, days: calls.append(("clock", days)))
    pipeline.run(tmp_path, rebuild=True)
    assert [c[0] for c in calls] == list(pipeline.STEPS)
    assert "--rebuild" in calls[0][1] and calls[3][1] == tmp_path / "panel" / "tsmc_warrant_trades"
    assert calls[4][1] == ()                                    # no dividend file yet
    with pytest.raises(ValueError):
        pipeline.run(tmp_path, steps=["nope"])
