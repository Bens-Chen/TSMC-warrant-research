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
    monkeypatch.setattr(pipeline.flow, "run", lambda d: calls.append(("flow", d)))
    monkeypatch.setattr(pipeline.toxicity, "run", lambda d: calls.append(("toxicity", d)))
    monkeypatch.setattr(pipeline.flow, "run_h4", lambda d: calls.append(("h4", d)))
    monkeypatch.setattr(pipeline.robustness, "run", lambda d: calls.append(("robustness", d)))
    monkeypatch.setattr(pipeline.extension, "run", lambda d: calls.append(("extension", d)))
    monkeypatch.setattr(pipeline.hedging, "run", lambda d: calls.append(("hedging", d)))
    pipeline.run(tmp_path, rebuild=True)
    assert [c[0] for c in calls] == list(pipeline.STEPS)
    assert "--rebuild" in calls[0][1] and calls[3][1] == tmp_path / "panel" / "tsmc_warrant_trades"
    assert calls[4][1] == ()                                    # no dividend file yet
    with pytest.raises(ValueError):
        pipeline.run(tmp_path, steps=["nope"])


def test_test_period_is_locked(monkeypatch):
    from wtox.research import config
    monkeypatch.setattr(config, "TEST_UNLOCKED", False)
    config.check_unlocked("2025-12-31")
    with pytest.raises(PermissionError):
        config.check_unlocked("2026-01-02")
    monkeypatch.setattr(config, "TEST_UNLOCKED", True)
    config.check_unlocked("2026-01-02")
