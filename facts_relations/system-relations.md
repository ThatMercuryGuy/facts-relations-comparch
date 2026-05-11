# System-Latent Relations (Coupled Epsilons)

These are relations whose epsilons cannot be solved independently — they share latent variables or form transitive chains where tightening one bound constrains another.

---

## 1. The Miss Cost Chain (Size → Hit Rate → Stalls → IPC)

A transitive chain where each link has its own epsilon, but the end-to-end bound requires solving them jointly.

**Link 1 (R3):** Larger cache improves hit rate.

$$\text{Size}[C_a] \geq \text{Size}[C_b] \implies \text{HitRate}[C_a] \geq \text{HitRate}[C_b] + \varepsilon_3$$

**Link 2 (R1):** Higher hit rate reduces stalls.

$$\text{HitRate}[t_a] \geq \text{HitRate}[t_b] \implies \text{Stalls}[t_a] \leq \text{Stalls}[t_b] + \varepsilon_1$$

**Link 3 (derived):** Fewer stalls improve IPC.

$$\text{Stalls}[t_a] \leq \text{Stalls}[t_b] + \varepsilon_1 \implies \text{IPC}[t_a] \geq \text{IPC}[t_b] - \varepsilon_{\text{ipc}}$$

**System constraint (end-to-end):** Bigger cache → better IPC.

$$\text{Size}[C_a] \geq \text{Size}[C_b] \implies \text{IPC}[t_a] \geq \text{IPC}[t_b] - f(\varepsilon_3, \varepsilon_1, \varepsilon_{\text{ipc}})$$

The combined slack $f(\varepsilon_3, \varepsilon_1, \varepsilon_{\text{ipc}})$ depends on all three jointly. Tightening $\varepsilon_3$ (bigger cache helps hit rate more) allows a tighter end-to-end bound even if $\varepsilon_1$ is loose. Memory-level parallelism determines how $\varepsilon_1$ and $\varepsilon_{\text{ipc}}$ interact — a core that can hide latency has loose $\varepsilon_1$ (hit rate doesn't predict stalls well) but that same hiding means $\varepsilon_{\text{ipc}}$ is also loose (stalls don't predict IPC well either).

---

## 2. Prefetch Pollution Coupling

Prefetch coverage helps demand hit rate, but demand hit rate's relationship to stalls depends on whether the prefetcher also pollutes the cache.

**Relation A (R28):** Better prefetch coverage improves demand hit rate.

$$\text{PrefetchCoverage}[C_a] \geq \text{PrefetchCoverage}[C_b] \implies \text{DemandHitRate}[C_a] \geq \text{DemandHitRate}[C_b] - \varepsilon_{28}$$

**Relation B (R1 applied to demand):** Higher demand hit rate reduces stalls.

$$\text{DemandHitRate}[t_a] \geq \text{DemandHitRate}[t_b] \implies \text{Stalls}[t_a] \leq \text{Stalls}[t_b] + \varepsilon_1'$$

**Coupling mechanism:** A prefetcher that achieves high coverage by aggressively filling the cache may evict demand-critical lines, inflating $\varepsilon_1'$ (the remaining misses become more critical-path because the easy ones were prefetched but the hard ones now also miss due to pollution). Formally:

$$\varepsilon_1' = g(\varepsilon_{28}, \text{PrefetchAccuracy})$$

When accuracy is low, pollution is high, and the stalls-per-miss-rate relationship degrades. You cannot tighten $\varepsilon_{28}$ (claim coverage helps a lot) without also accounting for how pollution worsens $\varepsilon_1'$.

---

## 3. Coherence–Capacity Interaction

Coherence invalidations effectively shrink usable cache capacity, shifting the system closer to the capacity cliff.

**Relation A (R36):** More invalidations → more coherence misses.

$$\text{Invalidations}[C_a] \geq \text{Invalidations}[C_b] \implies \text{CoherenceMisses}[C_a] \geq \text{CoherenceMisses}[C_b] - \varepsilon_{36}$$

**Relation B (R15):** Working set crossing capacity boundary → miss rate cliff.

$$\text{WSS}[W] > \frac{\text{Size}[C]}{B} \implies \text{MissRate}[C] \geq 2 \cdot \text{MissRate}[C_{\text{under}}] - \varepsilon_{15}$$

**Coupling mechanism:** Invalidations destroy valid lines that would otherwise serve future demand hits. This reduces the *effective* capacity of the cache:

$$\text{EffectiveCapacity}[C] \approx \text{Size}[C] - \text{Invalidations}[C] \cdot B \cdot \varepsilon_{\text{refill}}$$

where $\varepsilon_{\text{refill}}$ captures how quickly invalidated lines get refilled with useful data. The capacity cliff (R15) fires relative to effective capacity, not physical capacity. So:

$$\varepsilon_{15} = h(\varepsilon_{36}, \text{InvalidationRate})$$

High invalidation rates (small $\varepsilon_{36}$, meaning invalidations reliably cause coherence misses) push the effective capacity down, making $\varepsilon_{15}$ smaller (the cliff is steeper because you're deeper past the effective boundary).

---

## 4. Diminishing Returns ↔ Conflict Miss Reduction

Two relations measuring the same physical phenomenon from different abstraction levels.

**Relation A (R4):** Hit rate gain from doubling associativity is concave.

$$(\text{HitRate}[C_c] - \text{HitRate}[C_b]) \leq (\text{HitRate}[C_b] - \text{HitRate}[C_a]) + \varepsilon_{12}$$

where $2\,\text{Assoc}[C_a] = \text{Assoc}[C_b]$ and $2\,\text{Assoc}[C_b] = \text{Assoc}[C_c]$.

**Relation B (R22):** Conflict misses decrease with associativity.

$$\text{Assoc}[C_{\text{hi}}] \geq \text{Assoc}[C_{\text{lo}}] \implies \text{ConflictMisses}[C_{\text{hi}}] \leq \text{ConflictMisses}[C_{\text{lo}}] + \varepsilon_{22}$$

**Coupling mechanism:** The *reason* hit rate gains diminish (R4) is that conflict misses decrease concavely (R22). Hit rate improvement from higher associativity comes almost entirely from eliminating conflict misses. Therefore:

$$\varepsilon_{12} \approx \varepsilon_{22} \cdot \frac{\text{ConflictMisses}}{\text{Accesses}}$$

If you measure $\varepsilon_{22}$ (how much conflict misses drop), you can derive $\varepsilon_{12}$ (how much hit rate improves) by scaling by the conflict fraction. Solving them as a system lets you verify internal consistency: if the measured $\varepsilon_{12}$ is tighter than what $\varepsilon_{22}$ would predict, something else (beyond conflict elimination) is contributing to hit rate improvement at higher associativity.

---

## 5. Critical Hit Rate as a Tighter Stall Predictor

The original hypothesis from the corpus: $\varepsilon_2 < \varepsilon_1$.

**Relation A (R1):** Overall hit rate predicts stalls.

$$\text{HitRate}[t_a] \geq \text{HitRate}[t_b] \implies \text{Stalls}[t_a] \leq \text{Stalls}[t_b] + \varepsilon_1$$

**Relation B (R2):** Critical hit rate predicts stalls (tighter).

$$\text{CriticalHitRate}[t_a] \geq \text{CriticalHitRate}[t_b] \implies \text{Stalls}[t_a] \leq \text{Stalls}[t_b] + \varepsilon_2$$

**System constraint:**

$$\varepsilon_2 \leq \varepsilon_1$$

This is a **meta-relation** — a claim about the relative tightness of two bounds. You cannot verify it by evaluating R1 and R2 independently on separate data; you must evaluate *both* on the *same* intervals and compare their slacks. The coupled question is: "given a set of interval pairs, is the empirical $\varepsilon_2$ distribution stochastically dominated by the $\varepsilon_1$ distribution?"

---

## Summary

| System | Relations Involved | Shared/Coupled Latent | Nature |
|--------|-------------------|----------------------|--------|
| Miss cost chain | R3 → R1 → IPC | $\varepsilon_3, \varepsilon_1, \varepsilon_{\text{ipc}}$ | Transitive chain |
| Prefetch pollution | R28 → R1' | $\varepsilon_{28}, \varepsilon_1'$ | Interference coupling |
| Coherence–capacity | R36 ↔ R15 | $\varepsilon_{36}, \varepsilon_{15}$ | Effective capacity reduction |
| Assoc dual view | R4 ↔ R22 | $\varepsilon_{12}, \varepsilon_{22}$ | Same phenomenon, different level |
| Critical tightness | R1 vs R2 | $\varepsilon_1, \varepsilon_2$ | Meta-relation (bound ordering) |
