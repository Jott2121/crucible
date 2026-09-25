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
    # 0 mutants is not 0% and it is not 100% -- it is "no answer".
    #
    # ANCHORED on purpose. pytest.raises(match=...) does a regex SEARCH, not a
    # full match, so an unanchored pattern still passes when the message has been
    # corrupted at either end. Mutation testing proved it: the mutant that turned
    # this message into "XXno mutants generated; nothing to scoreXX" SURVIVED an
    # unanchored match=, because the garbage still contains the expected text.
    with pytest.raises(EmptyMutantSet, match=r"^no mutants generated; nothing to score$"):
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
    # pinned in full: this string is the product. A partial assertion lets any
    # unchecked word rot -- and mutation testing proved exactly that, by
    # surviving a mutant in the half of the sentence the old test never read.
    assert shock_line(counts(46, 25)) == (
        "25 of 71 injected defects SURVIVED this suite "
        "(46 killed, mutation score 65%)."
    )


def test_shock_line_pairs_coverage_against_the_score_when_given():
    assert shock_line(counts(46, 25), coverage=97.0) == (
        "97% line coverage, but 25 of 71 injected defects SURVIVED this suite "
        "(46 killed, mutation score 65%)."
    )


def test_shock_line_rounds_the_score_rather_than_truncating_it():
    # 2/3 = 66.67 -> "67%", not "66%"
    assert "mutation score 67%" in shock_line(counts(2, 1))


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


# --- "survived" means undetected: survived plus never-executed (no tests) -----------
#
# mutmut reports a mutant nothing executes as "no tests", separately from
# "survived". Both walked through the suite undetected, and the survivor LIST has
# always named both (oracle_gate.survivors.undetected). The headline counted only
# "survived", so a module with an untested function printed "0 of 3 injected
# defects SURVIVED" above a list of 2 survivors -- flattering the suite in exactly
# the case it is weakest.

def test_undetected_count_includes_mutants_no_test_ever_executed():
    from crucible.score import undetected_count

    assert undetected_count({"killed": 1, "survived": 0, "no_tests": 2, "total": 3}) == 2
    assert undetected_count({"killed": 46, "survived": 20, "no_tests": 5, "total": 71}) == 25


def test_undetected_count_tolerates_counts_without_a_no_tests_field():
    from crucible.score import undetected_count

    assert undetected_count(counts(46, 25)) == 25


def test_shock_line_counts_never_executed_mutants_as_survivors():
    # the live repro: one tested function, one untested function
    assert shock_line({"killed": 1, "survived": 0, "no_tests": 2, "total": 3}) == (
        "2 of 3 injected defects SURVIVED this suite "
        "(1 killed, mutation score 33%). "
        "2 of them were never executed by any test."
    )


def test_shock_line_says_which_survivors_no_test_ever_executed():
    assert shock_line({"killed": 46, "survived": 20, "no_tests": 5, "total": 71}) == (
        "25 of 71 injected defects SURVIVED this suite "
        "(46 killed, mutation score 65%). "
        "5 of them were never executed by any test."
    )


def test_shock_line_uses_the_singular_for_one_never_executed_mutant():
    assert shock_line({"killed": 8, "survived": 1, "no_tests": 1, "total": 10}) == (
        "2 of 10 injected defects SURVIVED this suite "
        "(8 killed, mutation score 80%). "
        "1 of them was never executed by any test."
    )


def test_shock_line_accounts_for_timeouts_instead_of_losing_them():
    # killed + survived + timed out must add up to the total the line quotes
    assert shock_line({"killed": 44, "survived": 25, "timeout": 2, "total": 71}) == (
        "25 of 71 injected defects SURVIVED this suite "
        "(44 killed, 2 timed out, mutation score 62%)."
    )


def test_shock_line_names_a_single_timeout():
    # the boundary: one timed-out mutant must be named, not dropped
    assert shock_line({"killed": 9, "survived": 0, "timeout": 1, "total": 10}) == (
        "0 of 10 injected defects SURVIVED this suite "
        "(9 killed, 1 timed out, mutation score 90%)."
    )
