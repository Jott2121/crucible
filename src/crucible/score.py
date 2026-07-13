"""The $0 diagnose: what fraction of injected defects does a suite actually kill?

No model is called here. `crucible score` is plain mutation testing plus the
arithmetic, which is the whole point -- the number that embarrasses a coverage
badge is free to compute, and nobody should need an API key to be told the
truth about their own suite.

Everything below is a plain module-level function over dicts. That is deliberate:
mutmut cannot mutate dataclass methods (see docs/MUTATION.md, the lean.py
delegate refactor), so logic that lives in a method is logic the mutation gate
is blind to. Rendering the badge and grading the suite are exactly the places
where a silent off-by-one would be most embarrassing, so they stay mutable.
"""

# Cutoffs are a judgment call, not a measurement. They are set where a reader's
# reaction should change: >=90 is a genuinely hardened suite; <40 means the
# suite is decorative. The "green at 75" line sits deliberately BELOW typical
# coverage numbers, because a 75% mutation score is a far better suite than a
# 95% coverage number -- and the badge should not punish honesty.
_COLOR_BANDS = (
    (90.0, "brightgreen"),
    (75.0, "green"),
    (60.0, "yellow"),
    (40.0, "orange"),
)
_COLOR_FLOOR = "red"


def stale_artifacts(subject) -> list:
    """mutmut working state that must be cleared before a score can be trusted.

    Found the hard way: mutmut 3.x copies the source AND tests into `mutants/`.
    If that directory survives from an earlier run, a later `crucible score` can
    grade the OLD copy of the tests and report its number as if it were today's.
    On a repo that had been hardened once, this reported 70/71 killed for a
    suite that actually kills 46 -- a 34-point lie, silently, in the flattering
    direction. A stale cache is exactly the failure this tool exists to catch,
    so it is cleared rather than trusted.
    """
    from pathlib import Path

    subject = Path(subject)
    return [p for p in (subject / "mutants", subject / ".mutmut-cache") if p.exists()]


class EmptyMutantSet(ValueError):
    """No mutants were generated, so there is no score to report.

    This is a refusal, not a zero. A scope that produces no mutants tells you
    nothing about the suite, and reporting it as 0% (or 100%) would be a lie in
    whichever direction flattered the reader.
    """


def mutation_score(counts: dict) -> float:
    """Percent of injected defects the suite killed: killed / total.

    Uses the FULL denominator (every mutant generated), not just the ones a test
    happened to reach. Dropping unreached mutants is the flattering variant and
    it is how a bad suite scores well -- see docs/MUTATION.md.
    """
    total = counts["total"]
    if total == 0:
        raise EmptyMutantSet("no mutants generated; nothing to score")
    return 100.0 * counts["killed"] / total


def badge_color(score: float) -> str:
    """shields.io color for a mutation score."""
    for floor, color in _COLOR_BANDS:
        if score >= floor:
            return color
    return _COLOR_FLOOR


def badge_payload(counts: dict, label: str = "mutation") -> dict:
    """A shields.io *endpoint* payload.

    Deliberately serverless: the caller writes this JSON into their own repo and
    points shields.io at the raw URL. No badge service to run, no uptime to owe
    anyone, nothing of mine in the middle of their CI.
    """
    score = mutation_score(counts)
    return {
        "schemaVersion": 1,
        "label": label,
        "message": f"{score:.0f}%",
        "color": badge_color(score),
    }


def shock_line(counts: dict, coverage: float | None = None) -> str:
    """The one-line result, written to be pasted into a PR or a tweet.

    Leads with the survivors rather than the score, because "25 bugs survived"
    is a fact about the reader's code and "65%" is a fact about my tool.
    """
    survived = counts["survived"]
    total = counts["total"]
    killed = counts["killed"]
    score = mutation_score(counts)
    cov = f"{coverage:.0f}% line coverage, but " if coverage is not None else ""
    return (
        f"{cov}{survived} of {total} injected defects SURVIVED this suite "
        f"({killed} killed, mutation score {score:.0f}%)."
    )


def below_threshold(score: float, fail_under: float | None) -> bool:
    """True when a --fail-under gate should red the build.

    `None` means no gate was asked for, which is not the same as a gate of 0 --
    conflating them is how a threshold silently stops protecting anyone.
    """
    if fail_under is None:
        return False
    return score < fail_under
