"""Tests for steering — detects advise-only responses, injects correction."""

from __future__ import annotations


class TestNeedsSteering:
    def test_detects_advice_response(self):
        from maggy.pipeline.steering import needs_steering
        text = "Here's what you should do:\n1. Open the file\n2. Edit it"
        assert needs_steering(text) is True

    def test_detects_recommendation(self):
        from maggy.pipeline.steering import needs_steering
        text = "I recommend updating the config file with these changes"
        assert needs_steering(text) is True

    def test_detects_steps_to_follow(self):
        from maggy.pipeline.steering import needs_steering
        text = "Here are the steps to follow:\n1. First step"
        assert needs_steering(text) is True

    def test_detects_you_can_try(self):
        from maggy.pipeline.steering import needs_steering
        text = "You can try running pytest to check"
        assert needs_steering(text) is True

    def test_detects_youll_need(self):
        from maggy.pipeline.steering import needs_steering
        text = "You'll need to update the imports first"
        assert needs_steering(text) is True

    def test_passes_action_response(self):
        from maggy.pipeline.steering import needs_steering
        text = "I've updated the file and ran the tests. All passing."
        assert needs_steering(text) is False

    def test_passes_tool_call_response(self):
        from maggy.pipeline.steering import needs_steering
        text = (
            "Reading the file.\n"
            "```tool_call\n"
            '{"name": "file_read", "params": {"path": "x.py"}}\n'
            "```\n"
        )
        assert needs_steering(text) is False

    def test_passes_short_answer(self):
        from maggy.pipeline.steering import needs_steering
        text = "The function is defined in src/main.py line 42."
        assert needs_steering(text) is False

    def test_passes_empty(self):
        from maggy.pipeline.steering import needs_steering
        assert needs_steering("") is False


class TestSteeringInjection:
    def test_returns_instruction(self):
        from maggy.pipeline.steering import steering_injection
        text = steering_injection()
        assert "execute" in text.lower() or "act" in text.lower()
        assert "do not advise" in text.lower() or "don't advise" in text.lower()
