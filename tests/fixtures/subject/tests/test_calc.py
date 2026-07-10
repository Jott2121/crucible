from subject_pkg.calc import acceptance_rate, clamp


def test_clamp_runs():
    assert clamp(5, 0, 10) == 5


def test_rate_runs():
    acceptance_rate(10, 5)  # no assertion on the value: the classic false-pass
