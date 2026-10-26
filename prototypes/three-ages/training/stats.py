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


def classification_by_class(confusion, classes) -> dict:
    """Descriptive image-level support/precision/recall, not an uncertainty CI.

    Confusion rows are true classes, columns predictions. Undefined precision
    or recall stays None rather than pretending unsupported classes scored zero.
    """
    names = list(classes)
    matrix = [list(row) for row in confusion]
    if (not names or len(set(names)) != len(names) or len(matrix) != len(names)
            or any(len(row) != len(names) for row in matrix)
            or any(type(value) is not int or value < 0 for row in matrix for value in row)):
        raise ValueError('square nonnegative integer confusion matrix and unique classes required')
    result = {}
    for i, name in enumerate(names):
        support = sum(matrix[i])
        predicted = sum(row[i] for row in matrix)
        true_positive = matrix[i][i]
        result[name] = {'support': support, 'predicted_support': predicted,
                        'true_positive': true_positive,
                        'precision': true_positive / predicted if predicted else None,
                        'recall': true_positive / support if support else None}
    return result


def counts(rate: float, total: int) -> int:
    """Recover an integer count from a rate and denominator."""
    return int(round(rate * total))


def _group_scores(building_ids, *score_vectors):
    """Validate aligned finite per-image scores and preserve group membership."""
    ids = list(building_ids)
    vectors = [list(scores) for scores in score_vectors]
    if not ids or any(len(scores) != len(ids) for scores in vectors):
        raise ValueError('nonempty aligned building IDs and scores required')
    groups = {}
    for i, bid in enumerate(ids):
        if not isinstance(bid, str) or not bid.strip():
            raise ValueError('nonempty string building IDs required')
        values = tuple(float(scores[i]) for scores in vectors)
        if not all(math.isfinite(value) for value in values):
            raise ValueError('scores must be finite')
        groups.setdefault(bid, []).append(values)
    return groups


def building_macro_mean(building_ids, scores) -> float:
    """Mean per-image score within each building, then equal-weight buildings."""
    groups = _group_scores(building_ids, scores)
    return sum(sum(row[0] for row in rows) / len(rows)
               for rows in groups.values()) / len(groups)


def paired_grouped_bootstrap(building_ids, scores_a, scores_b, *,
                             n_resamples: int = 2000, seed: int = 42,
                             confidence: float = 0.95,
                             weighting: str = 'building_macro') -> dict:
    """Percentile CI for A minus B, resampling whole buildings with replacement.

    Inputs are ALIGNED per-image metric contributions (e.g. correctness), not
    predictions or aggregate F1. Both models use the same sampled buildings;
    all images and duplicate draws remain together. ``image_micro`` preserves
    image weighting, whereas the default weights buildings equally. A single
    building yields a degenerate CI, not independent image-level uncertainty.
    No model fitting, threshold choice, or test-set selection is performed.
    """
    import random

    if isinstance(n_resamples, bool) or not isinstance(n_resamples, int) or n_resamples < 1:
        raise ValueError('n_resamples must be a positive integer')
    if not 0 < confidence < 1:
        raise ValueError('confidence must lie between zero and one')
    if weighting not in {'building_macro', 'image_micro'}:
        raise ValueError('unknown weighting')
    groups = _group_scores(building_ids, scores_a, scores_b)
    # Canonical ordering makes seeded results independent of input row order.
    totals = []
    for bid in sorted(groups):
        rows = groups[bid]
        delta = math.fsum(sorted(a - b for a, b in rows))
        totals.append((delta, len(rows)))

    def statistic(sample):
        if weighting == 'building_macro':
            return math.fsum(delta / n for delta, n in sample) / len(sample)
        return math.fsum(delta for delta, _ in sample) / sum(n for _, n in sample)

    rng = random.Random(seed)
    draws = sorted(statistic([totals[rng.randrange(len(totals))]
                              for _ in totals]) for _ in range(n_resamples))

    def quantile(p):
        index = (len(draws) - 1) * p
        lo = math.floor(index)
        hi = math.ceil(index)
        return draws[lo] + (draws[hi] - draws[lo]) * (index - lo)

    alpha = (1 - confidence) / 2
    return {'difference': statistic(totals),
            'ci': [quantile(alpha), quantile(1 - alpha)],
            'confidence': confidence, 'n_buildings': len(totals),
            'n_images': sum(n for _, n in totals), 'n_resamples': n_resamples,
            'seed': seed, 'weighting': weighting}
