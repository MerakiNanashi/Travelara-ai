import math
from collections import defaultdict
from app.schemas import ScoredPOI

# ---------------------------------------------------------------------------
# Haversine distance utilities
# ---------------------------------------------------------------------------

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_m(lat1, lon1, lat2, lon2) / 1000.0

# ---------------------------------------------------------------------------
# Normalization helper
# ---------------------------------------------------------------------------

def normalize(values: dict[str, float]) -> dict[str, float]:
    """Min-max normalize a dict of floats to [0, 1]."""
    if not values:
        return {}
    vmin = min(values.values())
    vmax = max(values.values())
    if vmax == vmin:
        return {k: 1.0 for k in values}
    return {k: (v - vmin) / (vmax - vmin) for k, v in values.items()}


# ---------------------------------------------------------------------------
# Cluster scoring and percentile pruning
# ---------------------------------------------------------------------------

def shannon_diversity(members: list[ScoredPOI]) -> float:
    """
    Normalized Shannon entropy of category distribution within a cluster,
    scaled to [0, 1]. 0 = single category, 1 = maximally spread across
    categories present. Used to keep mixed-category clusters competitive
    against large single-category clusters during pruning.
    """
    if len(members) <= 1:
        return 0.0

    counts: dict[str, int] = defaultdict(int)
    for p in members:
        counts[p.category] += 1

    n = len(members)
    k = len(counts)  # distinct categories present in this cluster

    if k <= 1:
        return 0.0

    entropy = -sum((c / n) * math.log(c / n) for c in counts.values())
    max_entropy = math.log(k)  # entropy if categories were evenly distributed

    return entropy / max_entropy if max_entropy > 0 else 0.0
