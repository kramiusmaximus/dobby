from __future__ import annotations

import pytest
from pydantic import ValidationError

from dobby_app.config.settings import Settings


def test_model_and_reasoning_defaults():
    settings = Settings()

    assert settings.planner_model == "gpt-5.5"
    assert settings.planner_reasoning_effort == "low"
    assert settings.executioner_model == "gpt-5.4-mini"
    assert settings.executioner_reasoning_effort == "medium"


def test_reasoning_effort_rejects_unknown_values(monkeypatch):
    monkeypatch.setenv("PLANNER_REASONING_EFFORT", "deep")

    with pytest.raises(ValidationError):
        Settings()
