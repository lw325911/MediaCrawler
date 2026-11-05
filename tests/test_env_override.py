# -*- coding: utf-8 -*-
import pytest

from config.env_override import apply_env_overrides


def test_types_are_converted():
    ns = {"HEADLESS": False, "MAX": 1, "KEYWORDS": "a", "IDS": [], "RATE": 1.0, "lower": "x"}
    env = {"MC_HEADLESS": "true", "MC_MAX": "5", "MC_KEYWORDS": "b,c",
           "MC_IDS": '["1","2"]', "MC_RATE": "0.5", "MC_lower": "y", "MC_UNKNOWN": "1", "OTHER": "1"}
    applied = apply_env_overrides(ns, env)
    assert ns == {"HEADLESS": True, "MAX": 5, "KEYWORDS": "b,c", "IDS": ["1", "2"], "RATE": 0.5, "lower": "x"}
    assert set(applied) == {"HEADLESS", "MAX", "KEYWORDS", "IDS", "RATE"}


def test_bad_value_raises():
    with pytest.raises(ValueError):
        apply_env_overrides({"HEADLESS": False}, {"MC_HEADLESS": "maybe"})
