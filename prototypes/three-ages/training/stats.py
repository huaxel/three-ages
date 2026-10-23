"""Small statistics helpers for honest reporting of proportions."""
from __future__ import annotations
import math


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval; behaves sanely at 0 and 1."""
    if total <= 0:
        raise ValueError('total must be positive')
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, centre - spread), min(1.0, centre + spread)


def counts(rate: float, total: int) -> int:
    """Recover an integer count from a rate and denominator."""
    return int(round(rate * total))
