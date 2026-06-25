# MLP Dogma Discovery Engine

A formal-methods experiment that asks a sharp question about computer
architecture:

> **Is more Memory-Level Parallelism (MLP) always better?**

Conventional wisdom says yes — wider outstanding-miss windows (more MSHRs) hide
memory latency and speed things up. This engine uses the **Z3 SMT solver** to
*search for a counterexample*: a memory-access workload on which a high-MLP core
is **slower** than a low-MLP core. Whether one exists within the bounds is left
to Z3; the engine makes no claim about the answer in advance.

## How it works

`mlp.cpp` is a single-file Bounded Model Checking (BMC) engine. It unrolls a
sequence of `N` memory requests and evaluates that one sequence on **two
mathematical CPU models** simultaneously:

| Machine          | MSHR window `W` |
|------------------|-----------------|
| `System_HighMLP` | 6               |
| `System_LowMLP`  | 2               |

Both machines run the **same workload** under the **same axioms**. The only
difference is the MSHR window `W`.

Crucially, the workload is **not hand-written**. Z3 synthesizes it from scratch
— the data-dependency graph, the per-request stream assignment, and the arrival
times — subject to physical pipeline constraints. We then ask Z3 a single
question with a standard solver (no optimizer):

> Does there exist a legal workload such that `T_HighMLP > T_LowMLP`?

If the answer is **SAT**, Z3 hands back a workload — and the engine then keeps
searching for the workload that **maximizes** the deviation (see *Finding the
worst case* below). If the answer is **UNSAT**, no such workload exists within
the bounds. We report whichever Z3 returns and analyze the witness; we do not
assume an outcome.

### What Z3 gets to choose (the symbolic workload)
- `A[i]` — program-order arrival time of each request.
- `K[i]` — which stream / hardware thread each request belongs to.
- `RW[i]` — whether each request is a read (`0`) or a write (`1`), which drives
  the bus turnaround bubbles.
- `Dep[i][j]` — a boolean matrix: does request `j` consume request `i`'s result?

### The physical pipeline bounds (keep the search realistic)
- **Strictly upper-triangular** dependencies — a request can only depend on an
  earlier one.
- **ROB horizon** — dependencies cannot span more than `ROB_SIZE` slots.
- **Stream matching** — a true dependency requires matching stream ids.
- **LSQ capacity** (`MAX_STREAM_MLP`) — a single stream can have at most
  `MAX_STREAM_MLP` concurrently-independent requests in flight.

### The hardware axioms (applied identically to both machines)
1. **Causality** — a dependent request waits for its producer to retire;
   otherwise it respects program order.
2. **MSHR gating** — a request cannot present to the channel until an
   outstanding-miss slot frees up: `A'[j] = max(Aeff[j], E[j-W])`.
3. **Pipelined channel + convex queueing + read/write turnaround** — the channel
   admits a new request every `G` cycles (`G < B`, so requests **overlap in
   flight** — this is the latency hiding MLP exists to exploit), plus a `TT`-cycle
   turnaround bubble whenever the service direction switches read↔write:
   `St[j] = max(A'[j], St[j-1] + G + TT*switch[j])`. The service cost then grows
   with how many earlier requests are still in flight when `j` starts —
   `inflight[j] = #{ i<j : E[i] > St[j] }`, measured in **time** and across **all
   streams** — under a **convex** curve: the first `C` overlaps are free
   (bank-level parallelism / bus pipelining), past `C` each costs `PEN_LO`, past
   the steeper knee `C2` each costs `PEN_HI` more:
   `E[j] = St[j] + B + PEN_LO*max(0, inflight-C) + PEN_HI*max(0, inflight-C2)`.
4. **Timeline** — total cycles `T = max(E)`.

## What makes the search non-trivial

A purely serial, work-conserving channel is **monotone in `W`** — a larger
window lets requests present no later, so completion times can only fall, and the
discovery query is vacuously UNSAT. Axiom 3 breaks that monotonicity with the
genuine physics of a shared, pipelined channel:

- **Pipelining gives MLP a real benefit.** Because admission is every `G < B`
  cycles, a wider window packs requests tighter against the bandwidth bound and
  finishes the baseline work earlier — latency hiding.
- **Convex queueing gives MLP a real cost.** The same packing drives more
  requests *concurrently in flight* (`inflight`), climbing the convex penalty
  curve. Crucially `inflight` is derived from the **schedule** (`St`/`E`) and
  counts across **all streams**, so the cost (a) is not a `W`-indexed constant —
  the backfire must *emerge* from timing, not be injected — and (b) captures
  **cross-thread interference**: an aggressive stream floods the channel and
  delays another stream's critical request.
- **Read/write turnaround** adds a `TT`-cycle bubble on each direction switch; a
  tightly-packed wide window eats more of them than a throttled one.

The physics in Axioms 1–4 is **identical for both machines**; only the window
`W` differs. Whether more MLP helps or hurts is now genuinely workload- and
regime-dependent — that is exactly what Z3 is asked to decide, and what we
analyze in any witness it returns. (Notably, under the realistic default config
below the answer is **UNSAT** — see *Example result*.)

## Finding the worst case

A single counterexample only shows one workload exists. Once the discovery query
is SAT, the engine searches for the workload that **maximizes** the deviation
`Delta = T_HighMLP - T_LowMLP`, so the reported figure is the largest Z3 can
exhibit within the bounds rather than an arbitrary first hit.

This is done **without `z3::optimize`** (a deliberate design constraint), by
incrementally tightening the standard solver: remember the best model, assert
`Delta >= best + 1`, and re-solve. A SAT result is a strictly worse workload (we
adopt it and raise the floor); the first UNSAT proves the previous `Delta` was
the maximum achievable within the bounds. Each solve inherits the solver timeout
(60 s by default, overridable via the CLI argument), so if the final (hardest)
probe times out, the engine reports the best `Delta` found as a lower bound
rather than a proven maximum.

## Building and running

Requirements: a C++23 compiler and Z3 (with `z3++.h` / `libz3`).

```sh
g++ -std=c++23 mlp.cpp -lz3 -o mlp -Ofast -march=native
./mlp            # default 60 s solver timeout
./mlp 120        # raise the solver timeout to 120 s
./mlp 0          # no timeout (run the maximality probe to completion)
```

The optional first argument sets the solver timeout in **seconds** (default 60,
`0` = unlimited). It bounds both the discovery query and each maximization probe,
so a larger value lets the worst-case search push `Delta` further before giving
up.

## Example result (6 vs 2 MSHRs)

Under the realistic default config (pipelined channel `G=2`, two requests of
free concurrency `C=2`, convex knee `C2=4`, `PEN_LO=3`, `PEN_HI=5`), the dogma
**holds**:

```
Query: exists workload with  T_HighMLP > T_LowMLP ?

UNSAT: no counterexample. Within these bounds, more MLP is never worse -- the dogma holds.
```

This is the honest outcome: once the channel offers a couple of requests' worth
of free concurrency (bank-level parallelism / bus pipelining), the latency-hiding
benefit of the wide window always covers its added contention within these
bounds. More MLP is never worse here.

The backfire **emerges only in a genuinely starved regime** — when the free
concurrency budget shrinks toward zero. Sweeping `C` at the default settings:

| `C` (free concurrency) | Result |
|------------------------|--------|
| `2` (default)          | **UNSAT** — dogma holds |
| `1`                    | SAT, proved max `Delta = 6` |
| `0` (no free parallelism) | SAT, `Delta` climbs further (timeout-limited) |

And under a deliberately pathological channel (`G=6`, `C=0`, `C2=1`, `PEN_LO=8`,
`PEN_HI=16`) Z3 drives the deviation to a **proved-maximal 72 cycles**
(`T_HighMLP = 154 > T_LowMLP = 82`). In that witness the printed `nfly`
(in-flight) row shows the wide machine climbing to 4 concurrent requests while
the throttled machine stays gated at 1 — so the wide core pays the steep convex
penalty on requests the narrow core never has in flight. That is the mechanism,
read directly off the timeline rather than assumed. The engine prints the full
witness (arrivals, streams, read/write tags, dependency matrix, and both
machines' `St`/`nfly`/`E` timelines) for exactly this purpose.

## Configuration

All parameters live in `namespace cfg` at the top of `mlp.cpp`:

| Knob             | Meaning                                        | Default |
|------------------|------------------------------------------------|---------|
| `N`              | unroll depth (number of requests)              | 8       |
| `S`              | streams / hardware threads                     | 2       |
| `B`              | bank access latency per request (cycles)       | 10      |
| `ROB_SIZE`       | reorder-buffer dependency horizon              | 4       |
| `MAX_STREAM_MLP` | LSQ: max independent reqs per stream           | 3       |
| `G`              | channel inter-admission gap (`1/bw`, `<B`)     | 2       |
| `TT`             | read/write bus turnaround bubble (cycles)      | 4       |
| `C`              | free concurrency (overlaps below this cost 0)  | 2       |
| `C2`             | steeper convex knee (`> C`)                    | 4       |
| `PEN_LO`         | per-overlap cost in the `[C, C2)` regime       | 3       |
| `PEN_HI`         | additional per-overlap cost beyond `C2`        | 5       |
| `W_HIGH`         | MSHRs for `System_HighMLP`                     | 6       |
| `W_LOW`          | MSHRs for `System_LowMLP`                      | 2       |

To compare different MLP budgets (e.g. 6 vs 1), edit `W_HIGH` / `W_LOW` and
rebuild.
