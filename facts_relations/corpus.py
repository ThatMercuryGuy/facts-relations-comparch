"""
Corpus of 30 cache replacement facts and relations.

Organized into thematic groups:
  A. Unconditional Facts (5)
  B. LRU Stack Properties (4, includes existing R3/R4)
  C. Policy Comparison (6)
  D. Working Set / Capacity (4)
  E. Thrashing & Pathological (3)
  F. Associativity Effects (2)
  G. Belady's Anomaly / Non-Stack (2, expected_violable)
  H. Temporal / Interval Relations (2, existing R1/R2)
"""

from core import (
    entity, metric, lit, eps, constraint, conj, relation,
    add, sub, mul, div,
    MetricKind as M, CmpOp,
)


# =============================================================================
# REUSABLE ENTITIES
# =============================================================================

# Policies (kind="policy") — first-class entities bound to caches via `bindings`
p_lru = entity("LRU", kind="policy")
p_fifo = entity("FIFO", kind="policy")
p_random = entity("RANDOM", kind="policy")
p_opt = entity("OPT", kind="policy")
p_adaptive = entity("ADAPTIVE", kind="policy")
p_plru = entity("PLRU", kind="policy")

# Block size constant (bytes) used across many relations
BLOCK_SIZE = lit(64)


# =============================================================================
# GROUP A: UNCONDITIONAL FACTS (5)
# =============================================================================

# --- F1: MissRate + HitRate == 1.0 ---
#
#   MissRate[C] + HitRate[C] == 1.0
#
# Definitional identity. Holds for any cache, any policy, any workload.

C_f1 = entity("C", kind="cache")

F1_miss_rate_hit_rate_complement = relation(
    name="miss_rate_hit_rate_complement",
    premises=[],
    consequent=constraint(
        add(metric(M.MISS_RATE, C_f1), metric(M.HIT_RATE, C_f1)),
        CmpOp.EQ,
        lit(1.0)
    ),
    entities=[C_f1],
    source="definition",
    domain="any cache, any policy, any workload",
)


# --- F2: Compulsory misses are policy-independent ---
#
#   CompulsoryMisses[C_a] == CompulsoryMisses[C_b]
#
# Given same workload and same cache size, compulsory misses depend only
# on the trace's unique blocks, not on how eviction decisions are made.

C_a_f2 = entity("C_a", kind="cache")
C_b_f2 = entity("C_b", kind="cache")
p_any_a = entity("P_a", kind="policy")
p_any_b = entity("P_b", kind="policy")

F2_compulsory_misses_policy_independent = relation(
    name="compulsory_misses_policy_independent",
    premises=[
        conj(
            constraint(metric(M.SIZE, C_a_f2), CmpOp.EQ, metric(M.SIZE, C_b_f2)),
            constraint(metric(M.ASSOCIATIVITY, C_a_f2), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_b_f2)),
        )
    ],
    consequent=constraint(
        metric(M.COMPULSORY_MISSES, C_a_f2),
        CmpOp.EQ,
        metric(M.COMPULSORY_MISSES, C_b_f2)
    ),
    entities=[C_a_f2, C_b_f2, p_any_a, p_any_b],
    bindings=[(C_a_f2, p_any_a), (C_b_f2, p_any_b)],
    source="3C miss model (Hill & Smith 1989)",
    domain="same workload, same cache geometry, any two policies",
)


# --- F3: Replacement only affects capacity + conflict misses ---
#
#   MissCount[a] - MissCount[b] == (CapMisses[a] + ConflMisses[a])
#                                 - (CapMisses[b] + ConflMisses[b])
#
# Corollary of F2: since compulsory misses cancel, the difference in
# total misses equals the difference in non-compulsory misses.

C_a_f3 = entity("C_a", kind="cache")
C_b_f3 = entity("C_b", kind="cache")

F3_replacement_affects_only_capacity_conflict = relation(
    name="replacement_affects_only_capacity_conflict",
    premises=[
        conj(
            constraint(metric(M.SIZE, C_a_f3), CmpOp.EQ, metric(M.SIZE, C_b_f3)),
            constraint(metric(M.ASSOCIATIVITY, C_a_f3), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_b_f3)),
        )
    ],
    consequent=constraint(
        sub(metric(M.MISS_COUNT, C_a_f3), metric(M.MISS_COUNT, C_b_f3)),
        CmpOp.EQ,
        sub(
            add(metric(M.CAPACITY_MISSES, C_a_f3), metric(M.CONFLICT_MISSES, C_a_f3)),
            add(metric(M.CAPACITY_MISSES, C_b_f3), metric(M.CONFLICT_MISSES, C_b_f3)),
        )
    ),
    entities=[C_a_f3, C_b_f3],
    source="corollary of 3C model and F2",
    domain="same workload, same cache geometry, any two policies",
)


# --- F4: Full associativity eliminates conflict misses ---
#
#   Assoc[C] == Size[C] / 64 => ConflictMisses[C] == 0
#
# By definition: conflict misses are those that wouldn't occur in a
# fully-associative cache of the same size.

C_f4 = entity("C", kind="cache")

F4_full_associativity_zero_conflict_misses = relation(
    name="full_associativity_zero_conflict_misses",
    premises=[
        constraint(
            metric(M.ASSOCIATIVITY, C_f4),
            CmpOp.EQ,
            div(metric(M.SIZE, C_f4), BLOCK_SIZE)
        )
    ],
    consequent=constraint(
        metric(M.CONFLICT_MISSES, C_f4),
        CmpOp.EQ,
        lit(0)
    ),
    entities=[C_f4],
    source="definition (3C model)",
    domain="any policy, any workload",
)


# --- F5: Stack policy inclusion property (exact) ---
#
#   Size[large] >= Size[small] ∧ both LRU => MissCount[large] <= MissCount[small]
#
# For stack algorithms, every block in the smaller cache is also in the
# larger cache at all times. This is the inclusion property stated as
# an exact inequality on miss counts.

C_large_f5 = entity("C_large", kind="cache")
C_small_f5 = entity("C_small", kind="cache")

F5_stack_policy_inclusion = relation(
    name="stack_policy_inclusion",
    premises=[
        constraint(metric(M.SIZE, C_large_f5), CmpOp.GE, metric(M.SIZE, C_small_f5))
    ],
    consequent=constraint(
        metric(M.MISS_COUNT, C_large_f5),
        CmpOp.LE,
        metric(M.MISS_COUNT, C_small_f5)
    ),
    entities=[C_large_f5, C_small_f5, p_lru],
    bindings=[(C_large_f5, p_lru), (C_small_f5, p_lru)],
    source="Mattson et al. 1970 (stack algorithms)",
    domain="LRU (or any stack algorithm), same workload, same associativity",
)


# --- F6: Hit rate is bounded in [0, 1] ---
#
#   0 <= HitRate[C] <= 1
#
# A rate by definition. This seems trivial but matters for Z3:
# without this bound, the solver can propose negative hit rates
# or rates > 1 as "counterexamples." Grounding fact.

C_f6 = entity("C", kind="cache")

F6_hit_rate_bounded = relation(
    name="hit_rate_bounded",
    premises=[],
    consequent=constraint(
        metric(M.HIT_RATE, C_f6),
        CmpOp.LE,
        lit(1.0)
    ),
    entities=[C_f6],
    source="definition (rate)",
    domain="any cache, any policy, any workload",
)


# =============================================================================
# GROUP B: CACHE SIZE & ASSOCIATIVITY PROPERTIES (4)
# =============================================================================

# --- R3: Larger cache implies higher hit rate ---
#
#   Size[LLC_a] >= Size[LLC_b] => HitRate[LLC_a] >= HitRate[LLC_b] + ε_3

llc_a = entity("LLC_a", kind="cache")
llc_b = entity("LLC_b", kind="cache")
p_r3 = entity("P", kind="policy")
e3 = eps("3")

R3_larger_cache_higher_hr = relation(
    name="larger_cache_implies_higher_hit_rate",
    premises=[
        constraint(metric(M.SIZE, llc_a), CmpOp.GE, metric(M.SIZE, llc_b))
    ],
    consequent=constraint(
        metric(M.HIT_RATE, llc_a), CmpOp.GE, add(metric(M.HIT_RATE, llc_b), e3)
    ),
    entities=[llc_a, llc_b, p_r3],
    bindings=[(llc_a, p_r3), (llc_b, p_r3)],
    free_epsilons=[e3],
    source="inclusion property (exact for stack algorithms)",
    domain="any policy; same workload and assoc",
)


# --- R4: Diminishing returns of associativity ---
#
#   Assoc[a] = A/2 ∧ Assoc[b] = A ∧ Assoc[c] = 2A ∧ Size equal
#     => (HR[c] - HR[b]) <= (HR[b] - HR[a]) + ε_12

llc_a_r4 = entity("LLC_a", kind="cache")
llc_b_r4 = entity("LLC_b", kind="cache")
llc_c_r4 = entity("LLC_c", kind="cache")
p_r4 = entity("P", kind="policy")
e12 = eps("12")

R4_diminishing_assoc_returns = relation(
    name="diminishing_returns_of_associativity",
    premises=[
        conj(
            constraint(metric(M.SIZE, llc_a_r4), CmpOp.EQ, metric(M.SIZE, llc_b_r4)),
            constraint(metric(M.SIZE, llc_b_r4), CmpOp.EQ, metric(M.SIZE, llc_c_r4)),
            constraint(
                mul(lit(2), metric(M.ASSOCIATIVITY, llc_a_r4)),
                CmpOp.EQ,
                metric(M.ASSOCIATIVITY, llc_b_r4)
            ),
            constraint(
                mul(lit(2), metric(M.ASSOCIATIVITY, llc_b_r4)),
                CmpOp.EQ,
                metric(M.ASSOCIATIVITY, llc_c_r4)
            ),
        )
    ],
    consequent=constraint(
        sub(metric(M.HIT_RATE, llc_c_r4), metric(M.HIT_RATE, llc_b_r4)),
        CmpOp.LE,
        add(sub(metric(M.HIT_RATE, llc_b_r4), metric(M.HIT_RATE, llc_a_r4)), e12)
    ),
    entities=[llc_a_r4, llc_b_r4, llc_c_r4, p_r4],
    bindings=[(llc_a_r4, p_r4), (llc_b_r4, p_r4), (llc_c_r4, p_r4)],
    free_epsilons=[e12],
    source="diminishing returns / concavity of miss-rate curve",
    domain="any policy, fixed size, single workload",
)


# --- R6: Working set fits => all hits ---
#
#   WorkingSetSize[W] <= Size[C] / 64 ∧ LRU => HitRate[C] >= 1.0 - ε
#
# If the working set fits in the cache, LRU keeps it all resident
# after warmup. Epsilon accounts for compulsory misses during warmup.

C_r6 = entity("C", kind="cache")
W_r6 = entity("W", kind="workload")
p_r6 = entity("P", kind="policy")
e6 = eps("6")

R6_working_set_fits_means_all_hits = relation(
    name="working_set_fits_means_all_hits",
    premises=[
        constraint(
            metric(M.WORKING_SET_SIZE, W_r6),
            CmpOp.LE,
            div(metric(M.SIZE, C_r6), BLOCK_SIZE)
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_r6),
        CmpOp.GE,
        sub(lit(1.0), e6)
    ),
    entities=[C_r6, W_r6, p_r6],
    bindings=[(C_r6, p_r6)],
    free_epsilons=[e6],
    source="Denning's working set model",
    domain="any demand-fetch policy, fully-associative or high-assoc, after warmup",
)


# --- R7: Miss rate monotone in reuse distance (under LRU) ---
#
#   ReuseDistance[W_a] <= ReuseDistance[W_b]
#     => MissRate[C_with_Wa] <= MissRate[C_with_Wb] + ε
#
# Lower average reuse distance means more accesses fall within cache
# capacity under LRU. Approximate because average reuse distance is
# not a sufficient statistic for the full distribution.

C_wa = entity("C_wa", kind="cache")
C_wb = entity("C_wb", kind="cache")
W_a_r7 = entity("W_a", kind="workload")
W_b_r7 = entity("W_b", kind="workload")
p_r7 = entity("P", kind="policy")
e7 = eps("7")

R7_miss_rate_monotone_in_reuse_distance = relation(
    name="miss_rate_monotone_in_reuse_distance",
    premises=[
        conj(
            constraint(metric(M.REUSE_DISTANCE, W_a_r7), CmpOp.LE,
                       metric(M.REUSE_DISTANCE, W_b_r7)),
            constraint(metric(M.SIZE, C_wa), CmpOp.EQ, metric(M.SIZE, C_wb)),
            constraint(metric(M.ASSOCIATIVITY, C_wa), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_wb)),
        )
    ],
    consequent=constraint(
        metric(M.MISS_RATE, C_wa),
        CmpOp.LE,
        add(metric(M.MISS_RATE, C_wb), e7)
    ),
    entities=[C_wa, C_wb, W_a_r7, W_b_r7, p_r7],
    bindings=[(C_wa, p_r7), (C_wb, p_r7)],
    free_epsilons=[e7],
    source="lower reuse distance = easier locality for any policy",
    domain="any policy, same cache geometry",
)


# --- R8: LRU set decomposition ---
#
#   HitRate[C_setassoc] ≈ HitRate[C_perset_avg] + ε
#
# For LRU, a set-associative cache's overall hit rate equals the average
# of per-set hit rates (each set is an independent LRU stack). Epsilon
# captures non-uniformity in access distribution across sets.

C_setassoc = entity("C_setassoc", kind="cache")
C_perset = entity("C_perset_avg", kind="cache")
e8 = eps("8")

R8_lru_set_decomposition = relation(
    name="lru_set_decomposition",
    premises=[
        constraint(
            metric(M.STACK_DEPTH, C_setassoc),
            CmpOp.EQ,
            metric(M.ASSOCIATIVITY, C_setassoc)
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_setassoc),
        CmpOp.GE,
        sub(metric(M.HIT_RATE, C_perset), e8)
    ),
    entities=[C_setassoc, C_perset, p_lru],
    bindings=[(C_setassoc, p_lru), (C_perset, p_lru)],
    free_epsilons=[e8],
    source="Mattson et al. decomposition",
    domain="LRU, uniform set indexing (no skewed/randomized)",
)


# =============================================================================
# GROUP C: POLICY COMPARISON (6)
# =============================================================================

# --- R9: OPT upper-bounds all policies ---
#
#   HitRate[C_opt] >= HitRate[C_any]
#
# Belady's OPT achieves the highest possible hit rate for any
# demand-fetch replacement policy on the same trace.

C_opt = entity("C_opt", kind="cache")
C_any = entity("C_any", kind="cache")
p_any_r9 = entity("P_any", kind="policy")
e9 = eps("9")

R9_opt_upper_bounds_all_policies = relation(
    name="opt_upper_bounds_all_policies",
    premises=[
        conj(
            constraint(metric(M.SIZE, C_opt), CmpOp.EQ, metric(M.SIZE, C_any)),
            constraint(metric(M.ASSOCIATIVITY, C_opt), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_any)),
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_opt),
        CmpOp.GE,
        sub(metric(M.HIT_RATE, C_any), e9)
    ),
    entities=[C_opt, C_any, p_opt, p_any_r9],
    bindings=[(C_opt, p_opt), (C_any, p_any_r9)],
    free_epsilons=[e9],
    source="Belady 1966",
    domain="same cache geometry, same workload, demand-fetch only",
)


# --- R10: Recency-aware beats recency-blind under temporal locality ---
#
#   ReuseDistance[W] <= Size[C] / (2 * 64) ∧ same geometry
#     => HitRate[C_recency_aware] >= HitRate[C_recency_blind] + ε
#
# When reuse distances are well within cache capacity, policies that
# track/exploit recency outperform those that don't.

C_aware_r10 = entity("C_recency_aware", kind="cache")
C_blind_r10 = entity("C_recency_blind", kind="cache")
W_r10 = entity("W", kind="workload")
p_aware = entity("P_recency_aware", kind="policy")
p_blind = entity("P_recency_blind", kind="policy")
e10 = eps("10")

R10_recency_aware_beats_blind = relation(
    name="recency_aware_beats_blind_temporal_locality",
    premises=[
        conj(
            constraint(
                metric(M.REUSE_DISTANCE, W_r10),
                CmpOp.LE,
                div(metric(M.SIZE, C_aware_r10), mul(lit(2), BLOCK_SIZE))
            ),
            constraint(metric(M.SIZE, C_aware_r10), CmpOp.EQ,
                       metric(M.SIZE, C_blind_r10)),
            constraint(metric(M.ASSOCIATIVITY, C_aware_r10), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_blind_r10)),
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_aware_r10),
        CmpOp.GE,
        add(metric(M.HIT_RATE, C_blind_r10), e10)
    ),
    entities=[C_aware_r10, C_blind_r10, W_r10, p_aware, p_blind],
    bindings=[(C_aware_r10, p_aware), (C_blind_r10, p_blind)],
    free_epsilons=[e10],
    source="recency-exploiting policies dominate when temporal locality is strong",
    domain="same geometry, strong temporal locality workloads",
)


# --- R11: Random replacement lower bound relative to any policy ---
#
#   HitRate[C_rand] >= (1 - 1/Assoc) * HitRate[C_P] - ε
#
# Random replacement retains useful blocks with probability (ways-1)/ways
# per eviction, giving a probabilistic lower bound relative to any reference.

C_ref_r11 = entity("C_ref", kind="cache")
C_rand_r11 = entity("C_rand", kind="cache")
p_ref_r11 = entity("P_ref", kind="policy")
e11 = eps("11")

R11_random_replacement_lower_bound = relation(
    name="random_replacement_lower_bound",
    premises=[
        conj(
            constraint(metric(M.SIZE, C_ref_r11), CmpOp.EQ, metric(M.SIZE, C_rand_r11)),
            constraint(metric(M.ASSOCIATIVITY, C_ref_r11), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_rand_r11)),
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_rand_r11),
        CmpOp.GE,
        sub(
            mul(
                sub(lit(1), div(lit(1), metric(M.ASSOCIATIVITY, C_ref_r11))),
                metric(M.HIT_RATE, C_ref_r11)
            ),
            e11
        )
    ),
    entities=[C_ref_r11, C_rand_r11, p_ref_r11, p_random],
    bindings=[(C_ref_r11, p_ref_r11), (C_rand_r11, p_random)],
    free_epsilons=[e11],
    source="Al-Zoubi et al.; probabilistic argument",
    domain="same cache geometry, same workload, any reference policy",
)


# --- R12: Adaptive policy tracks the best static component ---
#
#   HitRate[C_adaptive] >= HitRate[C_best_static] - ε
#
# Adaptive policies (DIP/DRRIP) use set-dueling to dynamically select
# the better sub-policy. They achieve within epsilon of the best static
# choice, where epsilon is the set-dueling overhead.

C_adapt_r12 = entity("C_adaptive", kind="cache")
C_best_r12 = entity("C_best_static", kind="cache")
C_other_r12 = entity("C_other_static", kind="cache")
p_best_r12 = entity("P_best", kind="policy")
p_other_r12 = entity("P_other", kind="policy")
e_adapt = eps("adapt")

R12_adaptive_tracks_best_component = relation(
    name="adaptive_tracks_best_component",
    premises=[
        conj(
            constraint(metric(M.SIZE, C_adapt_r12), CmpOp.EQ, metric(M.SIZE, C_best_r12)),
            constraint(metric(M.SIZE, C_best_r12), CmpOp.EQ, metric(M.SIZE, C_other_r12)),
            constraint(metric(M.ASSOCIATIVITY, C_adapt_r12), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_best_r12)),
            constraint(metric(M.HIT_RATE, C_best_r12), CmpOp.GE,
                       metric(M.HIT_RATE, C_other_r12)),
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_adapt_r12),
        CmpOp.GE,
        sub(metric(M.HIT_RATE, C_best_r12), e_adapt)
    ),
    entities=[C_adapt_r12, C_best_r12, C_other_r12, p_adaptive, p_best_r12, p_other_r12],
    bindings=[(C_adapt_r12, p_adaptive), (C_best_r12, p_best_r12),
              (C_other_r12, p_other_r12)],
    free_epsilons=[e_adapt],
    source="Qureshi et al. ISCA 2007 (DIP); Jaleel et al. ISCA 2010 (RRIP)",
    domain="same cache geometry, single workload, set-dueling adaptive policy",
)


# --- R13: Hardware approximation tracks ideal policy ---
#
#   HitRate[C_approx] >= HitRate[C_ideal] - ε
#
# Any hardware-feasible approximation of an ideal policy stays within
# epsilon of it. Applies to PLRU/LRU, quantized-Mockingjay/full, etc.

C_ideal_r13 = entity("C_ideal", kind="cache")
C_approx_r13 = entity("C_approx", kind="cache")
p_ideal = entity("P_ideal", kind="policy")
p_approx = entity("P_approx", kind="policy")
e13 = eps("13")

R13_approximation_tracks_ideal = relation(
    name="hw_approximation_tracks_ideal",
    premises=[
        conj(
            constraint(metric(M.SIZE, C_ideal_r13), CmpOp.EQ,
                       metric(M.SIZE, C_approx_r13)),
            constraint(metric(M.ASSOCIATIVITY, C_ideal_r13), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_approx_r13)),
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_approx_r13),
        CmpOp.GE,
        sub(metric(M.HIT_RATE, C_ideal_r13), e13)
    ),
    entities=[C_ideal_r13, C_approx_r13, p_ideal, p_approx],
    bindings=[(C_ideal_r13, p_ideal), (C_approx_r13, p_approx)],
    free_epsilons=[e13],
    source="general; e.g. Al-Zoubi et al. 2004 (PLRU/LRU)",
    domain="same geometry, same workload, P_approx is a hw-feasible version of P_ideal",
)


# --- R14: Approximation gap grows with decision space ---
#
#   Assoc[high] > Assoc[low] ∧ same size
#     => (HR_ideal - HR_approx)[high] >= (HR_ideal - HR_approx)[low] - ε
#
# More candidates to rank makes approximation harder. The gap between
# an ideal policy and its hardware approximation widens with associativity.

C_ideal_hi = entity("C_ideal_hiassoc", kind="cache")
C_approx_hi = entity("C_approx_hiassoc", kind="cache")
C_ideal_lo = entity("C_ideal_loassoc", kind="cache")
C_approx_lo = entity("C_approx_loassoc", kind="cache")
p_ideal_r14 = entity("P_ideal", kind="policy")
p_approx_r14 = entity("P_approx", kind="policy")
e14 = eps("14")

R14_approximation_gap_grows_with_associativity = relation(
    name="approximation_gap_grows_with_associativity",
    premises=[
        conj(
            constraint(metric(M.ASSOCIATIVITY, C_ideal_hi), CmpOp.GT,
                       metric(M.ASSOCIATIVITY, C_ideal_lo)),
            constraint(metric(M.SIZE, C_ideal_hi), CmpOp.EQ, metric(M.SIZE, C_ideal_lo)),
            constraint(metric(M.SIZE, C_ideal_hi), CmpOp.EQ, metric(M.SIZE, C_approx_hi)),
            constraint(metric(M.SIZE, C_ideal_lo), CmpOp.EQ, metric(M.SIZE, C_approx_lo)),
            constraint(metric(M.ASSOCIATIVITY, C_ideal_hi), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_approx_hi)),
            constraint(metric(M.ASSOCIATIVITY, C_ideal_lo), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_approx_lo)),
        )
    ],
    consequent=constraint(
        sub(metric(M.HIT_RATE, C_ideal_hi), metric(M.HIT_RATE, C_approx_hi)),
        CmpOp.GE,
        sub(
            sub(metric(M.HIT_RATE, C_ideal_lo), metric(M.HIT_RATE, C_approx_lo)),
            e14
        )
    ),
    entities=[C_ideal_hi, C_approx_hi, C_ideal_lo, C_approx_lo,
              p_ideal_r14, p_approx_r14],
    bindings=[(C_ideal_hi, p_ideal_r14), (C_approx_hi, p_approx_r14),
              (C_ideal_lo, p_ideal_r14), (C_approx_lo, p_approx_r14)],
    free_epsilons=[e14],
    source="larger decision space makes approximation harder",
    domain="same total size, same workload, P_approx is hw-feasible version of P_ideal",
)


# =============================================================================
# GROUP D: WORKING SET / CAPACITY (4)
# =============================================================================

# --- R15: Capacity cliff at working set boundary ---
#
#   WSS[W_over] > Size[C]/64 ∧ WSS[W_under] <= Size[C]/64
#     => MissRate[C_over] >= 2 * MissRate[C_under] - ε
#
# Miss rate jumps sharply (superlinearly) when the working set
# transitions from fitting to not fitting.

C_over = entity("C_over", kind="cache")
C_under = entity("C_under", kind="cache")
W_over = entity("W_over", kind="workload")
W_under = entity("W_under", kind="workload")
e15 = eps("15")

R15_cliff_at_working_set_boundary = relation(
    name="cliff_at_working_set_boundary",
    premises=[
        conj(
            constraint(metric(M.SIZE, C_over), CmpOp.EQ, metric(M.SIZE, C_under)),
            constraint(metric(M.ASSOCIATIVITY, C_over), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_under)),
            constraint(
                metric(M.WORKING_SET_SIZE, W_over),
                CmpOp.GT,
                div(metric(M.SIZE, C_over), BLOCK_SIZE)
            ),
            constraint(
                metric(M.WORKING_SET_SIZE, W_under),
                CmpOp.LE,
                div(metric(M.SIZE, C_under), BLOCK_SIZE)
            ),
        )
    ],
    consequent=constraint(
        metric(M.MISS_RATE, C_over),
        CmpOp.GE,
        sub(mul(lit(2), metric(M.MISS_RATE, C_under)), e15)
    ),
    entities=[C_over, C_under, W_over, W_under],
    free_epsilons=[e15],
    source="capacity cliff / working set model (Denning)",
    domain="any policy, looping or structured access patterns",
)


# --- R16: Capacity misses dominate beyond working set ---
#
#   WSS[W] > Size[C]/64 => CapacityMisses[C] >= MissCount[C]/2 - ε
#
# When the working set exceeds cache capacity, most misses are
# capacity misses (not conflict or compulsory).

C_r16 = entity("C", kind="cache")
W_r16 = entity("W", kind="workload")
e16 = eps("16")

R16_capacity_misses_dominate_beyond_wss = relation(
    name="capacity_misses_dominate_beyond_wss",
    premises=[
        constraint(
            metric(M.WORKING_SET_SIZE, W_r16),
            CmpOp.GT,
            div(metric(M.SIZE, C_r16), BLOCK_SIZE)
        )
    ],
    consequent=constraint(
        metric(M.CAPACITY_MISSES, C_r16),
        CmpOp.GE,
        sub(div(metric(M.MISS_COUNT, C_r16), lit(2)), e16)
    ),
    entities=[C_r16, W_r16],
    free_epsilons=[e16],
    source="3C model (Hill & Smith 1989)",
    domain="fully-associative or high-associativity (minimizes conflict misses)",
)


# --- R17: Reuse distance predicts high miss rate ---
#
#   ReuseDistance[W] * 64 >= Size[C] => MissRate[C] >= 0.5 - ε
#
# If the average reuse distance (in blocks) exceeds the cache capacity
# (in blocks), at least half of accesses miss.

C_r17 = entity("C", kind="cache")
W_r17 = entity("W", kind="workload")
e17 = eps("17")

R17_reuse_distance_predicts_high_miss_rate = relation(
    name="reuse_distance_predicts_high_miss_rate",
    premises=[
        constraint(
            mul(metric(M.REUSE_DISTANCE, W_r17), BLOCK_SIZE),
            CmpOp.GE,
            metric(M.SIZE, C_r17)
        )
    ],
    consequent=constraint(
        metric(M.MISS_RATE, C_r17),
        CmpOp.GE,
        sub(lit(0.5), e17)
    ),
    entities=[C_r17, W_r17],
    free_epsilons=[e17],
    source="Mattson et al. 1970; information-theoretic argument",
    domain="any policy, fully-associative",
)


# --- R18: Temporal locality decay increases misses ---
#
#   ReuseDistance[t_later] >= ReuseDistance[t_earlier]
#     => MissRate[t_later] >= MissRate[t_earlier] - ε
#
# If a workload's reuse distance increases over time, later intervals
# have higher miss rates. Epsilon accounts for warm cache state
# carrying over between intervals.

t_earlier = entity("t_earlier", kind="interval")
t_later = entity("t_later", kind="interval")
e18 = eps("18")

R18_locality_decay_increases_misses = relation(
    name="locality_decay_increases_misses",
    premises=[
        constraint(
            metric(M.REUSE_DISTANCE, t_later),
            CmpOp.GE,
            metric(M.REUSE_DISTANCE, t_earlier)
        )
    ],
    consequent=constraint(
        metric(M.MISS_RATE, t_later),
        CmpOp.GE,
        sub(metric(M.MISS_RATE, t_earlier), e18)
    ),
    entities=[t_earlier, t_later],
    free_epsilons=[e18],
    source="intuitive; larger reuse distance => more evictions between reuses",
    domain="same cache, same policy, sequential intervals",
)


# =============================================================================
# GROUP E: THRASHING & PATHOLOGICAL (3)
# =============================================================================

# --- R19: LRU thrashing on cyclic pattern ---
#
#   UniqueBlocks[W] == Size[C]/64 + 1 ∧ LRU ∧ cyclic => HitRate[C] <= ε
#
# A cyclic access pattern of N+1 distinct blocks on an LRU cache of
# capacity N blocks produces 0% hit rate — every access evicts the
# next needed block.

C_r19 = entity("C", kind="cache")
W_r19 = entity("W_cyclic", kind="workload")
e19 = eps("19")

R19_lru_thrashing_cyclic = relation(
    name="lru_thrashing_cyclic",
    premises=[
        constraint(
            metric(M.UNIQUE_BLOCKS, W_r19),
            CmpOp.EQ,
            add(div(metric(M.SIZE, C_r19), BLOCK_SIZE), lit(1))
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_r19),
        CmpOp.LE,
        e19
    ),
    entities=[C_r19, W_r19, p_lru],
    bindings=[(C_r19, p_lru)],
    free_epsilons=[e19],
    source="classic LRU thrashing (Hennessy & Patterson)",
    domain="LRU, purely cyclic/looping access pattern",
)


# --- R20: BIP mitigates thrashing ---
#
#   Same thrashing workload ∧ ADAPTIVE => HitRate[C] >= ε
#
# Bimodal insertion policy (BIP) inserts at LRU position with high
# probability, preventing the cascade eviction that causes thrashing.
# Under the same cyclic workload that kills LRU, BIP achieves
# significantly positive hit rate.

C_r20 = entity("C", kind="cache")
W_r20 = entity("W_cyclic", kind="workload")
e20 = eps("20")

R20_bip_mitigates_thrashing = relation(
    name="bip_mitigates_thrashing",
    premises=[
        constraint(
            metric(M.UNIQUE_BLOCKS, W_r20),
            CmpOp.EQ,
            add(div(metric(M.SIZE, C_r20), BLOCK_SIZE), lit(1))
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_r20),
        CmpOp.GE,
        e20
    ),
    entities=[C_r20, W_r20, p_adaptive],
    bindings=[(C_r20, p_adaptive)],
    free_epsilons=[e20],
    source="Qureshi et al. ISCA 2007 (DIP/BIP)",
    domain="cyclic thrashing workload, BIP or DIP adaptive policy",
)


# --- R21: Random replacement avoids deterministic thrashing ---
#
#   RANDOM ∧ cyclic => HitRate[C] >= 1/Assoc - ε
#
# Random replacement never hits 0% because it retains useful blocks
# with nonzero probability. The expected hit rate has a floor related
# to the survival probability per eviction.

C_r21 = entity("C", kind="cache")
W_r21 = entity("W_cyclic", kind="workload")
e21 = eps("21")

R21_random_avoids_deterministic_thrashing = relation(
    name="random_avoids_deterministic_thrashing",
    premises=[
        constraint(
            metric(M.UNIQUE_BLOCKS, W_r21),
            CmpOp.EQ,
            add(div(metric(M.SIZE, C_r21), BLOCK_SIZE), lit(1))
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_r21),
        CmpOp.GE,
        sub(div(lit(1), metric(M.ASSOCIATIVITY, C_r21)), e21)
    ),
    entities=[C_r21, W_r21, p_random],
    bindings=[(C_r21, p_random)],
    free_epsilons=[e21],
    source="probabilistic argument; survival probability (ways-1)/ways",
    domain="cyclic/repeating workload, random replacement",
)


# =============================================================================
# GROUP F: ASSOCIATIVITY EFFECTS (2)
# =============================================================================

# --- R22: Conflict misses decrease with associativity ---
#
#   Assoc[C_high] >= Assoc[C_low] ∧ Size equal
#     => ConflictMisses[C_high] <= ConflictMisses[C_low] + ε
#
# More ways per set means fewer collisions within sets.

C_hi_r22 = entity("C_hiassoc", kind="cache")
C_lo_r22 = entity("C_loassoc", kind="cache")
e22 = eps("22")

R22_conflict_misses_decrease_with_associativity = relation(
    name="conflict_misses_decrease_with_associativity",
    premises=[
        conj(
            constraint(metric(M.ASSOCIATIVITY, C_hi_r22), CmpOp.GE,
                       metric(M.ASSOCIATIVITY, C_lo_r22)),
            constraint(metric(M.SIZE, C_hi_r22), CmpOp.EQ, metric(M.SIZE, C_lo_r22)),
        )
    ],
    consequent=constraint(
        metric(M.CONFLICT_MISSES, C_hi_r22),
        CmpOp.LE,
        add(metric(M.CONFLICT_MISSES, C_lo_r22), e22)
    ),
    entities=[C_hi_r22, C_lo_r22],
    free_epsilons=[e22],
    source="Hill & Smith 1989 (3C model)",
    domain="any policy (same for both), same workload",
)


# --- R23: Scan-aware policy beats scan-naive on mixed workloads ---
#
#   Scanning component has high reuse distance ∧ recurrent component
#   fits in cache ∧ scan-aware vs scan-naive => HR[aware] >= HR[naive] + ε
#
# Scan-naive policies pollute the cache with streaming data; scan-aware
# policies (RRIP, ARC, LIRS, Mockingjay) protect the recurrent working set.

C_naive_r23 = entity("C_scan_naive", kind="cache")
C_aware_r23 = entity("C_scan_aware", kind="cache")
W_scan = entity("W_scan_component", kind="workload")
W_recur = entity("W_recurrent", kind="workload")
p_naive = entity("P_scan_naive", kind="policy")
p_scan_aware = entity("P_scan_aware", kind="policy")
e23 = eps("23")

R23_scan_resistance = relation(
    name="scan_aware_beats_scan_naive",
    premises=[
        conj(
            constraint(metric(M.SIZE, C_naive_r23), CmpOp.EQ,
                       metric(M.SIZE, C_aware_r23)),
            constraint(metric(M.ASSOCIATIVITY, C_naive_r23), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_aware_r23)),
            constraint(
                metric(M.REUSE_DISTANCE, W_scan),
                CmpOp.GT,
                div(metric(M.SIZE, C_naive_r23), BLOCK_SIZE)
            ),
            constraint(
                metric(M.WORKING_SET_SIZE, W_recur),
                CmpOp.LT,
                div(metric(M.SIZE, C_naive_r23), BLOCK_SIZE)
            ),
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_aware_r23),
        CmpOp.GE,
        add(metric(M.HIT_RATE, C_naive_r23), e23)
    ),
    entities=[C_naive_r23, C_aware_r23, W_scan, W_recur, p_naive, p_scan_aware],
    bindings=[(C_naive_r23, p_naive), (C_aware_r23, p_scan_aware)],
    free_epsilons=[e23],
    source="Megiddo & Modha 2003 (ARC); Jiang & Zhang 2002 (LIRS)",
    domain="mixed scan+recurrent workload",
)


# =============================================================================
# GROUP G: BELADY'S ANOMALY / NON-STACK (2)
# =============================================================================

# --- R24: Belady's anomaly for FIFO ---
#
#   FIFO ∧ Size[large] > Size[small]
#     => MissRate[large] <= MissRate[small] + ε
#
# For FIFO, increasing cache size can INCREASE the miss rate.
# We state the "expected" monotonicity and mark it expected_violable.
# A negative epsilon IS the anomaly manifesting.

C_large_r24 = entity("C_large", kind="cache")
C_small_r24 = entity("C_small", kind="cache")
e24 = eps("24")

R24_beladys_anomaly_fifo = relation(
    name="beladys_anomaly_fifo",
    premises=[
        conj(
            constraint(metric(M.SIZE, C_large_r24), CmpOp.GT,
                       metric(M.SIZE, C_small_r24)),
            constraint(metric(M.ASSOCIATIVITY, C_large_r24), CmpOp.EQ,
                       metric(M.ASSOCIATIVITY, C_small_r24)),
        )
    ],
    consequent=constraint(
        metric(M.MISS_RATE, C_large_r24),
        CmpOp.LE,
        add(metric(M.MISS_RATE, C_small_r24), e24)
    ),
    entities=[C_large_r24, C_small_r24, p_fifo],
    bindings=[(C_large_r24, p_fifo), (C_small_r24, p_fifo)],
    free_epsilons=[e24],
    source="Belady et al. 1969",
    domain="FIFO policy specifically",
    expected_violable=True,
)


# --- R25: Non-stack non-monotone associativity ---
#
#   FIFO ∧ Assoc[high] > Assoc[low] ∧ same size
#     => HitRate[high] >= HitRate[low] - ε
#
# For non-stack policies, increasing associativity while keeping size
# fixed does NOT guarantee a hit rate increase. Negative epsilon means
# violation.

C_hi_r25 = entity("C_hiassoc", kind="cache")
C_lo_r25 = entity("C_loassoc", kind="cache")
e25 = eps("25")

R25_non_stack_non_monotone_associativity = relation(
    name="non_stack_non_monotone_associativity",
    premises=[
        conj(
            constraint(metric(M.ASSOCIATIVITY, C_hi_r25), CmpOp.GT,
                       metric(M.ASSOCIATIVITY, C_lo_r25)),
            constraint(metric(M.SIZE, C_hi_r25), CmpOp.EQ, metric(M.SIZE, C_lo_r25)),
        )
    ],
    consequent=constraint(
        metric(M.HIT_RATE, C_hi_r25),
        CmpOp.GE,
        sub(metric(M.HIT_RATE, C_lo_r25), e25)
    ),
    entities=[C_hi_r25, C_lo_r25, p_fifo],
    bindings=[(C_hi_r25, p_fifo), (C_lo_r25, p_fifo)],
    free_epsilons=[e25],
    source="consequence of Belady's anomaly in associativity dimension",
    domain="FIFO or non-stack policy",
    expected_violable=True,
)


# =============================================================================
# GROUP H: TEMPORAL / INTERVAL RELATIONS (2)
# =============================================================================

# --- R1 (existing): Higher hit rate implies fewer stalls ---
#
#   HitRate[t_a] >= HitRate[t_b] => Stalls[t_a] <= Stalls[t_b] + ε_1

t_a = entity("t_a", kind="interval")
t_b = entity("t_b", kind="interval")
e1 = eps("1")

R1_hit_rate_implies_fewer_stalls = relation(
    name="hit_rate_implies_fewer_stalls",
    premises=[
        constraint(metric(M.HIT_RATE, t_a), CmpOp.GE, metric(M.HIT_RATE, t_b))
    ],
    consequent=constraint(
        metric(M.STALLS, t_a), CmpOp.LE, add(metric(M.STALLS, t_b), e1)
    ),
    entities=[t_a, t_b],
    free_epsilons=[e1],
    source="folklore / intuition",
    domain="single-core, same cache geometry, intervals large enough for metric stability",
)


# --- R2 (existing): Critical hit rate is a tighter predictor ---
#
#   CriticalHitRate[t_a] >= CHR[t_b] => Stalls[t_a] <= Stalls[t_b] + ε_2

e2 = eps("2")

R2_critical_hit_rate_implies_fewer_stalls = relation(
    name="critical_hit_rate_implies_fewer_stalls",
    premises=[
        constraint(metric(M.CRITICAL_HIT_RATE, t_a), CmpOp.GE,
                   metric(M.CRITICAL_HIT_RATE, t_b))
    ],
    consequent=constraint(
        metric(M.STALLS, t_a), CmpOp.LE, add(metric(M.STALLS, t_b), e2)
    ),
    entities=[t_a, t_b],
    free_epsilons=[e2],
    source="folklore / Qureshi ISCA'06 insight",
    domain="single-core, same cache geometry, intervals large enough for metric stability",
)


# =============================================================================
# CORPUS COLLECTION
# =============================================================================

ALL_RELATIONS = [
    # Group A: Unconditional Facts
    F1_miss_rate_hit_rate_complement,
    F6_hit_rate_bounded,
    F2_compulsory_misses_policy_independent,
    F3_replacement_affects_only_capacity_conflict,
    F4_full_associativity_zero_conflict_misses,
    F5_stack_policy_inclusion,
    # Group B: LRU Stack Properties
    R3_larger_cache_higher_hr,
    R4_diminishing_assoc_returns,
    R6_working_set_fits_means_all_hits,
    R7_miss_rate_monotone_in_reuse_distance,
    R8_lru_set_decomposition,
    # Group C: Policy Comparison
    R9_opt_upper_bounds_all_policies,
    R10_recency_aware_beats_blind,
    R11_random_replacement_lower_bound,
    R12_adaptive_tracks_best_component,
    R13_approximation_tracks_ideal,
    R14_approximation_gap_grows_with_associativity,
    # Group D: Working Set / Capacity
    R15_cliff_at_working_set_boundary,
    R16_capacity_misses_dominate_beyond_wss,
    R17_reuse_distance_predicts_high_miss_rate,
    R18_locality_decay_increases_misses,
    # Group E: Thrashing & Pathological
    R19_lru_thrashing_cyclic,
    R20_bip_mitigates_thrashing,
    R21_random_avoids_deterministic_thrashing,
    # Group F: Associativity Effects
    R22_conflict_misses_decrease_with_associativity,
    R23_scan_resistance,
    # Group G: Belady's Anomaly / Non-Stack
    R24_beladys_anomaly_fifo,
    R25_non_stack_non_monotone_associativity,
    # Group H: Temporal / Interval
    R1_hit_rate_implies_fewer_stalls,
    R2_critical_hit_rate_implies_fewer_stalls,
]

assert len(ALL_RELATIONS) == 30, f"Expected 30, got {len(ALL_RELATIONS)}"


if __name__ == "__main__":
    print(f"=== Cache Replacement Corpus: {len(ALL_RELATIONS)} relations ===\n")

    facts = [r for r in ALL_RELATIONS if not r.premises]
    conditionals = [r for r in ALL_RELATIONS if r.premises and not r.expected_violable]
    violable = [r for r in ALL_RELATIONS if r.expected_violable]

    print(f"  Unconditional facts: {len(facts)}")
    print(f"  Conditional relations: {len(conditionals)}")
    print(f"  Expected-violable: {len(violable)}")
    print()

    for i, r in enumerate(ALL_RELATIONS, 1):
        tag = ""
        if not r.premises:
            tag = " [FACT]"
        elif r.expected_violable:
            tag = " [VIOLABLE]"
        print(f"{i:2d}. {r}{tag}")
        if r.bindings:
            binds = ", ".join(f"{c} uses {p}" for c, p in r.bindings)
            print(f"      bindings: {binds}")
        print()
