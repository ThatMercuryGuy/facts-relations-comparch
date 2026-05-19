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

## 2. The Coherence Stall Chain (Invalidations → Coherence Misses → Hit Rate → Stalls → IPC)

The multicore analog of the Miss Cost Chain. In a shared-memory system, coherence protocol traffic introduces a category of misses invisible to single-core analysis. This chain traces how inter-core communication degrades IPC through the cache miss path.

**Link 1 (R13):** More invalidations cause more coherence misses.

$$\text{Invalidations}[C_a] \geq \text{Invalidations}[C_b] \implies \text{CoherenceMisses}[C_a] \geq \text{CoherenceMisses}[C_b] - \varepsilon_{13}$$

**Link 2 (R12):** Coherence misses contribute to total miss count.

$$\text{MissCount}[C] \geq \text{CompulsoryMisses}[C] + \text{CapacityMisses}[C] + \text{ConflictMisses}[C] + \text{CoherenceMisses}[C] + \varepsilon_{12}$$

**Link 3 (F1):** Total misses determine hit rate.

$$\text{MissRate}[C] + \text{HitRate}[C] = 1$$

**Link 4 (R5):** Lower hit rate causes more stalls.

$$\text{HitRate}[t_a] \geq \text{HitRate}[t_b] \implies \text{Stalls}[t_a] \leq \text{Stalls}[t_b] + \varepsilon_5$$

**System constraint (end-to-end):** More invalidations → worse IPC.

$$\text{Invalidations}[C_a] \geq \text{Invalidations}[C_b] \implies \text{IPC}[t_a] \leq \text{IPC}[t_b] + g(\varepsilon_{13}, \varepsilon_{12}, \varepsilon_5)$$

The combined slack $g(\varepsilon_{13}, \varepsilon_{12}, \varepsilon_5)$ cannot be decomposed into independent per-link contributions. $\varepsilon_{13}$ is loose when invalidations hit lines that were about to be evicted anyway — the coherence miss overlaps with what would have been a capacity miss, so the re-fetch is not an additional cost. $\varepsilon_5$ is loose when out-of-order execution hides miss latency via memory-level parallelism. These interact in a non-trivial way: bursty invalidations (tight $\varepsilon_{13}$ within each burst) create bursty stall patterns that the reorder buffer can absorb (loosening $\varepsilon_5$). Conversely, a steady drip of invalidations (loose $\varepsilon_{13}$ per individual event) produces a sustained throughput drag with predictable stall patterns (tightening $\varepsilon_5$). Tightening one epsilon can loosen another — they cannot be solved independently.

---

## 3. Writeback–Bandwidth Interference (R14 coupled to R5)

Unlike the transitive chains in Systems 1 and 2, this is an *interference coupling* — R14 modulates the tightness of $\varepsilon_5$ rather than feeding into it sequentially. It explains why two configurations with identical hit rates can produce very different stall counts.

**The modulator (R14):** More store hits and more evictions produce more writebacks.

$$\text{StoreHitRate}[C_a] \geq \text{StoreHitRate}[C_b] \;\wedge\; \text{Evictions}[C_a] \geq \text{Evictions}[C_b]$$
$$\implies \text{Writebacks}[C_a] \geq \text{Writebacks}[C_b] - \varepsilon_{14}$$

**The target (R5):** Hit rate predicts stalls.

$$\text{HitRate}[t_a] \geq \text{HitRate}[t_b] \implies \text{Stalls}[t_a] \leq \text{Stalls}[t_b] + \varepsilon_5$$

**The coupling mechanism:** $\varepsilon_5$ is not a constant — it is a function of writeback pressure.

R5 relates hit rate to stalls, but stalls depend on miss *latency*, not just miss *count*. Writebacks consume bus/interconnect bandwidth without delivering useful data to the requesting core. When writeback traffic is high, demand misses queue behind writebacks in the bus arbitration, inflating the effective miss penalty. This means the same hit rate produces more stalls under heavy writeback pressure.

$$\varepsilon_5 = h(\text{Writebacks}, \text{BusBandwidth})$$

**Microarchitectural mechanism:** Write-back buffers are finite (typically 8–16 entries in modern designs). When full, evictions stall the pipeline directly — a structural hazard independent of the cache miss path. Additionally, demand misses contend with writebacks for bus cycles, increasing their service time. Both effects inflate $\varepsilon_5$.

**System constraint:** The Miss Cost Chain (System 1) and the Coherence Stall Chain (System 2) both terminate at R5. Their end-to-end bounds inherit this hidden dependency: the combined slack functions $f(\varepsilon_3, \varepsilon_1, \varepsilon_{\text{ipc}})$ and $g(\varepsilon_{13}, \varepsilon_{12}, \varepsilon_5)$ are both modulated by R14's writeback pressure. A store-heavy workload with high eviction rates will loosen both chains' end-to-end predictions, even if the hit-rate links are tight.

---

## 4. Associativity Saturation in Multicore (R4 + R12 + R13 + R5)

This system identifies a *saturation point* — a regime transition where increasing associativity stops improving IPC because the dominant miss category is insensitive to geometry.

**The diminishing component (R4):** More associativity reduces conflict misses.

$$\text{Assoc}[C_{\text{hi}}] \geq \text{Assoc}[C_{\text{lo}}] \;\wedge\; \text{Size}[C_{\text{hi}}] = \text{Size}[C_{\text{lo}}]$$
$$\implies \text{ConflictMisses}[C_{\text{hi}}] \leq \text{ConflictMisses}[C_{\text{lo}}] + \varepsilon_4$$

**The invariant component (R13):** Coherence misses depend on sharing patterns, not geometry.

$$\text{Invalidations}[C_a] \geq \text{Invalidations}[C_b] \implies \text{CoherenceMisses}[C_a] \geq \text{CoherenceMisses}[C_b] - \varepsilon_{13}$$

**The budget (R12):** Total misses are at least the sum of all four categories.

$$\text{MissCount}[C] \geq \text{Compulsory} + \text{Capacity} + \text{Conflict} + \text{Coherence} + \varepsilon_{12}$$

**The payoff (R5):** Fewer misses → fewer stalls → better IPC.

**System constraint:** The IPC benefit of associativity is bounded by the fraction of misses that are conflicts.

$$\Delta\text{IPC}_{\text{from assoc}} \leq \frac{\text{ConflictMisses}}{\text{MissCount}} \cdot f(\varepsilon_4, \varepsilon_5)$$

Even if $\varepsilon_4 \to 0$ (associativity perfectly eliminates all conflicts), the IPC gain is capped by how much of the total miss budget was conflicts in the first place. Once coherence misses dominate total misses — as happens on high-sharing workloads with many cores — the numerator shrinks toward zero and increasing associativity yields no IPC improvement.

**Saturation crossover:** The transition occurs at approximately $\text{ConflictMisses} \approx \text{CoherenceMisses}$. Below this point, geometry tuning (more ways) is the efficient lever. Above it, protocol optimization (reducing invalidations) is the only path to IPC gains. The crossover itself is workload- and core-count-dependent: more cores and more sharing push the system toward coherence-dominated regimes where $\varepsilon_4$'s contribution to end-to-end IPC vanishes regardless of its tightness.

**Architectural relevance:** This is the tradeoff architects face when sizing shared LLC associativity in chip multiprocessors. The system predicts that beyond a measurable sharing intensity, silicon spent on extra ways would be better spent on coherence filtering, directory bandwidth, or snoop reduction.