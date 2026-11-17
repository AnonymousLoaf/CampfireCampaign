"""A short automated playtest with the offline DM: the game's rule checks must all pass."""
from tools import playtest


def test_short_offline_playtest_finds_no_problems():
    problems = playtest.play(rounds=3, engine="offline", seed=2, timeout=20)
    assert list(problems) == []
