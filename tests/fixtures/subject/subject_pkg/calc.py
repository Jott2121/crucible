"""Tiny HR-ish math module: the mutation target for crucible's own e2e test."""


def clamp(value, lo, hi):
    """Return value bounded to [lo, hi]."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def acceptance_rate(offers, accepts):
    """accepts/offers as a fraction; 0.0 when no offers (never divide by zero)."""
    if offers <= 0:
        return 0.0
    return accepts / offers
