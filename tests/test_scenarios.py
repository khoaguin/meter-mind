from edgesim.scenarios import make_scenario


def test_flatline_is_zero():
    s = make_scenario("flatline", seed=0)
    assert all(s(t).delta == 0.0 for t in range(10))


def test_leak_spikes_after_threshold():
    s = make_scenario("leak", seed=0)
    early = sum(s(t).delta for t in range(5))
    spike = s(6).delta
    assert spike > early  # one post-threshold tick dwarfs 5 normal ticks


def test_lowconf_rolls_often():
    s = make_scenario("lowconf", seed=0)
    rolls = sum(s(t).rolling for t in range(20))
    assert rolls >= 10


def test_normal_drifts_positive():
    s = make_scenario("normal", seed=0)
    assert sum(s(t).delta for t in range(20)) > 0
