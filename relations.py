"""
Lightweight relation definitions for cache microarchitecture claims.

Each relation is a dict with:
  - 'name': identifier (e.g., 'R1')
  - 'claim': callable(data: dict) -> bool, checks if the relation holds
  - 'epsilon_name': which epsilon slack variable this uses (or None)
  - 'requires': list of stat keys / config keys the claim needs
"""

# =============================================================================
# SINGLE-ENTITY RELATIONS (Facts)
# =============================================================================

F1_miss_rate_hit_rate_complement = {
    'name': 'F1',
    'description': 'miss_rate + hit_rate = 1',
    'claim': lambda d: abs((d.get('miss_rate', 0) + d.get('hit_rate', 0)) - 1.0) < 0.001,
    'epsilon_name': None,
    'requires': ['miss_rate', 'hit_rate'],
}

F2_hit_rate_bounded = {
    'name': 'F2',
    'description': 'hit_rate <= 1',
    'claim': lambda d: d.get('hit_rate', 0) <= 1.001,
    'epsilon_name': None,
    'requires': ['hit_rate'],
}

# =============================================================================
# MULTI-ENTITY RELATIONS (ordered comparisons)
# =============================================================================
# These take data as: {'entity_a': {...}, 'entity_b': {...}}
# The claim callable receives this dict and extracts what it needs.

R1_larger_cache_higher_hr = {
    'name': 'R1',
    'description': 'size[a] >= size[b] => hit_rate[a] >= hit_rate[b] + epsilon',
    'premises': ['size_a >= size_b'],
    'claim': lambda d: d.get('hit_rate_a', 0) >= d.get('hit_rate_b', 0),
    'epsilon_name': 'eps_1',
    'requires': ['hit_rate_a', 'hit_rate_b', 'size_a', 'size_b'],
}

R2_diminishing_returns_associativity = {
    'name': 'R2',
    'description': 'diminishing returns of associativity (concave in assoc)',
    'premises': [
        'size_a == size_b == size_c',
        '2 * assoc_a == assoc_b',
        '2 * assoc_b == assoc_c',
    ],
    'claim': lambda d: (d.get('hit_rate_c', 0) - d.get('hit_rate_b', 0)) <= \
                       (d.get('hit_rate_b', 0) - d.get('hit_rate_a', 0)),
    'epsilon_name': 'eps_2',
    'requires': ['hit_rate_a', 'hit_rate_b', 'hit_rate_c', 'size_a', 'size_b', 'size_c', 'assoc_a', 'assoc_b', 'assoc_c'],
}

R3_opt_upper_bounds = {
    'name': 'R3',
    'description': 'OPT policy upper-bounds all demand-fetch policies',
    'premises': [
        'size[opt] == size[any]',
        'assoc[opt] == assoc[any]',
    ],
    'claim': lambda d: d.get('hit_rate_opt', 0) >= d.get('hit_rate_policy', 0),
    'epsilon_name': 'eps_3',
    'requires': ['hit_rate_opt', 'hit_rate_policy', 'size_opt', 'size_policy', 'assoc_opt', 'assoc_policy'],
}

R4_conflict_misses_decrease_with_assoc = {
    'name': 'R4',
    'description': 'assoc[hi] >= assoc[lo], size[hi] == size[lo] => conflict_misses[hi] <= conflict_misses[lo]',
    'premises': ['assoc_hi >= assoc_lo', 'size_hi == size_lo'],
    'claim': lambda d: d.get('conflict_misses_hi', 0) <= d.get('conflict_misses_lo', 0),
    'epsilon_name': 'eps_4',
    'requires': ['conflict_misses_hi', 'conflict_misses_lo', 'assoc_hi', 'assoc_lo', 'size_hi', 'size_lo'],
}

R5_higher_hit_rate_fewer_stalls = {
    'name': 'R5',
    'description': 'hit_rate[a] >= hit_rate[b] => stalls[a] <= stalls[b]',
    'premises': ['hit_rate_a >= hit_rate_b'],
    'claim': lambda d: d.get('stalls_a', 0) <= d.get('stalls_b', 0),
    'epsilon_name': 'eps_5',
    'requires': ['hit_rate_a', 'hit_rate_b', 'stalls_a', 'stalls_b'],
}

R6_critical_hit_rate_tighter_than_overall = {
    'name': 'R6',
    'description': 'critical_hit_rate[a] >= critical_hit_rate[b] => stalls[a] <= stalls[b] (tighter than R5)',
    'premises': ['critical_hit_rate_a >= critical_hit_rate_b'],
    'claim': lambda d: d.get('stalls_a', 0) <= d.get('stalls_b', 0),
    'epsilon_name': 'eps_6',
    'requires': ['critical_hit_rate_a', 'critical_hit_rate_b', 'stalls_a', 'stalls_b'],
}

R7_hit_rate_between_load_and_store = {
    'name': 'R7',
    'description': 'hit_rate between load_hit_rate and store_hit_rate',
    'premises': ['load_hit_rate >= store_hit_rate'],
    'claim': lambda d: d.get('store_hit_rate', 0) <= d.get('hit_rate', 0) <= d.get('load_hit_rate', 0),
    'epsilon_name': None,
    'requires': ['hit_rate', 'load_hit_rate', 'store_hit_rate'],
}

R9_prefetch_coverage_reduces_demand_misses = {
    'name': 'R9',
    'description': 'prefetch_coverage[a] >= prefetch_coverage[b] => demand_hit_rate[a] >= demand_hit_rate[b]',
    'premises': ['prefetch_coverage_a >= prefetch_coverage_b', 'same_geometry'],
    'claim': lambda d: d.get('demand_hit_rate_a', 0) >= d.get('demand_hit_rate_b', 0),
    'epsilon_name': 'eps_9',
    'requires': ['demand_hit_rate_a', 'demand_hit_rate_b', 'prefetch_coverage_a', 'prefetch_coverage_b'],
}

R10_low_prefetch_accuracy_hurts = {
    'name': 'R10',
    'description': 'prefetch_accuracy <= 0.25 => demand_hit_rate[prefetch] <= demand_hit_rate[no_prefetch]',
    'premises': ['prefetch_accuracy <= 0.25'],
    'claim': lambda d: d.get('demand_hit_rate_prefetch', 0) <= d.get('demand_hit_rate_no_prefetch', 0),
    'epsilon_name': 'eps_10',
    'requires': ['demand_hit_rate_prefetch', 'demand_hit_rate_no_prefetch', 'prefetch_accuracy'],
}

R11_stores_hit_less_than_loads = {
    'name': 'R11',
    'description': 'write-allocate: store_hit_rate <= load_hit_rate',
    'premises': [],
    'claim': lambda d: d.get('store_hit_rate', 0) <= d.get('load_hit_rate', 0),
    'epsilon_name': 'eps_11',
    'requires': ['store_hit_rate', 'load_hit_rate'],
}

R12_four_c_miss_decomposition = {
    'name': 'R12',
    'description': 'total_misses >= compulsory + capacity + conflict + coherence',
    'premises': [],
    'claim': lambda d: d.get('total_misses', 0) >= (
        d.get('compulsory_misses', 0) +
        d.get('capacity_misses', 0) +
        d.get('conflict_misses', 0) +
        d.get('coherence_misses', 0)
    ),
    'epsilon_name': 'eps_12',
    'requires': ['total_misses', 'compulsory_misses', 'capacity_misses', 'conflict_misses', 'coherence_misses'],
}

R13_more_invalidations_more_coherence_misses = {
    'name': 'R13',
    'description': 'invalidations[a] >= invalidations[b] => coherence_misses[a] >= coherence_misses[b]',
    'premises': ['invalidations_a >= invalidations_b', 'same_geometry'],
    'claim': lambda d: d.get('coherence_misses_a', 0) >= d.get('coherence_misses_b', 0),
    'epsilon_name': 'eps_13',
    'requires': ['coherence_misses_a', 'coherence_misses_b', 'invalidations_a', 'invalidations_b'],
}

R14_more_dirty_lines_more_writebacks = {
    'name': 'R14',
    'description': 'store_hit_rate[a] >= store_hit_rate[b] AND evictions[a] >= evictions[b] => writebacks[a] >= writebacks[b]',
    'premises': ['store_hit_rate_a >= store_hit_rate_b', 'evictions_a >= evictions_b', 'size_a == size_b'],
    'claim': lambda d: d.get('writebacks_a', 0) >= d.get('writebacks_b', 0),
    'epsilon_name': 'eps_14',
    'requires': ['writebacks_a', 'writebacks_b', 'store_hit_rate_a', 'store_hit_rate_b', 'evictions_a', 'evictions_b', 'size_a', 'size_b'],
}

# =============================================================================
# COLLECTION
# =============================================================================

ALL_RELATIONS = [
    F1_miss_rate_hit_rate_complement,
    F2_hit_rate_bounded,
    R1_larger_cache_higher_hr,
    R2_diminishing_returns_associativity,
    R3_opt_upper_bounds,
    R4_conflict_misses_decrease_with_assoc,
    R5_higher_hit_rate_fewer_stalls,
    R6_critical_hit_rate_tighter_than_overall,
    R7_hit_rate_between_load_and_store,
    R9_prefetch_coverage_reduces_demand_misses,
    R10_low_prefetch_accuracy_hurts,
    R11_stores_hit_less_than_loads,
    R12_four_c_miss_decomposition,
    R13_more_invalidations_more_coherence_misses,
    R14_more_dirty_lines_more_writebacks,
]

assert len(ALL_RELATIONS) == 15, f"Expected 15 relations, got {len(ALL_RELATIONS)}"
