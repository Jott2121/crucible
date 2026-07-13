import json

import pytest

from crucible.score import (
    EmptyMutantSet,
    badge_color,
    badge_payload,
    below_threshold,
    mutation_score,
    shock_line,
)


def counts(killed, survived, total=None):
    return {"killed": killed, "survived": survived, "total": total if total is not None else killed + survived}


def test_score_is_killed_over_the_full_denominator():
    # the reference run: 71 injected, 46 killed, 25 survived
    assert mutation_score(counts(46, 25)) == pytest.approx(64.788, abs=0.01)


def test_score_uses_total_not_killed_plus_survived():
    # a mutant that was never reached still counts against you; scoring on the
    # reached-only denominator is the flattering variant this must not do
    assert mutation_score({"killed": 5, "survived": 5, "total": 20}) == pytest.approx(25.0)


def test_perfect_and_zero_suites():
    assert mutation_score(counts(10, 0)) == 100.0
    assert mutation_score(counts(0, 10)) == 0.0


def test_empty_mutant_set_refuses_rather_than_reporting_a_number():
    # 0 mutants is not 0% and it is not 100% -- it is "no answer"
    with pytest.raises(EmptyMutantSet):
        mutation_score({"killed": 0, "survived": 0, "total": 0})


@pytest.mark.parametrize(
    "score,color",
    [
        (100.0, "brightgreen"),
        (90.0, "brightgreen"),
        (89.9, "green"),
        (75.0, "green"),
        (74.9, "yellow"),
        (60.0, "yellow"),
        (59.9, "orange"),
        (40.0, "orange"),
        (39.9, "red"),
        (0.0, "red"),
    ],
)
def test_badge_color_bands_including_their_exact_boundaries(score, color):
    assert badge_color(score) == color


def test_badge_payload_is_a_valid_shields_endpoint():
    payload = badge_payload(counts(46, 25))
    assert payload["schemaVersion"] == 1
    assert payload["label"] == "mutation"
    assert payload["message"] == "65%"       # 64.788 rounds to 65
    assert payload["color"] == "yellow"
    json.dumps(payload)                       # must survive serialization


def test_badge_label_is_overridable():
    assert badge_payload(counts(9, 1), label="mutants killed")["label"] == "mutants killed"


def test_shock_line_leads_with_the_survivors_not_the_score():
    line = shock_line(counts(46, 25))
    assert line.startswith("25 of 71 injected defects SURVIVED")
    assert "mutation score 65%" in line


def test_shock_line_pairs_coverage_against_the_score_when_given():
    line = shock_line(counts(46, 25), coverage=97.0)
    assert line.startswith("97% line coverage, but 25 of 71 injected defects SURVIVED")


def test_shock_line_omits_coverage_when_it_was_not_measured():
    assert "coverage" not in shock_line(counts(46, 25))


def test_below_threshold_gates_only_when_a_threshold_was_asked_for():
    assert below_threshold(50.0, 80.0) is True
    assert below_threshold(80.0, 80.0) is False      # at the floor is passing
    assert below_threshold(80.1, 80.0) is False


def test_no_threshold_is_not_a_threshold_of_zero():
    # conflating "no gate" with "gate of 0" is how a floor silently stops
    # protecting anyone
    assert below_threshold(0.0, None) is False
    assert below_threshold(0.0, 0.0) is False


def test_stale_artifacts_finds_the_mutmut_working_copy(tmp_path):
    from crucible.score import stale_artifacts

    assert stale_artifacts(tmp_path) == []

    (tmp_path / "mutants").mkdir()
    (tmp_path / ".mutmut-cache").write_text("")
    found = {p.name for p in stale_artifacts(tmp_path)}
    # both must be found: mutants/ holds the stale copy of the TESTS, which is
    # what silently produced a 34-point-too-high score on a real repo
    assert found == {"mutants", ".mutmut-cache"}
