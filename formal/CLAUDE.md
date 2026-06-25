# CLAUDE.md

Guidance for working in this directory (`formal/`).

## What this is

A single-file Z3 (C++ API) Bounded Model Checking engine, `mlp.cpp`, that tests
the architectural dogma *"more Memory-Level Parallelism is always better."* It
unrolls `N` memory requests over two state machines (`System_HighMLP`,
`System_LowMLP`) that share one synthesized workload and differ only in their
MSHR / outstanding-miss window `W`. A standard `z3::solver` (NOT `z3::optimize`)
searches for a workload where `T_HighMLP > T_LowMLP`.

## Build & run

```
g++ -std=c++23 mlp.cpp -lz3 -o mlp -Ofast -march=native
./mlp           # default 60s solver timeout
./mlp 120       # optional first arg = solver timeout in SECONDS (0 = unlimited)
```

Z3 4.x with `z3++.h` is installed system-wide (`/usr/include`, `libz3.so`).
g++ 15.2 (full C++23). There is no test harness or build script — compile and
run directly. The model is deterministic; the same config yields the same model.

The optional first CLI argument sets the solver timeout in seconds (default 60,
`0` = no timeout). It applies to both the discovery `check()` and every
maximization probe, so a larger value lets the worst-case search climb further.

## Where to change things

All knobs are in `namespace cfg` at the top of `mlp.cpp`:
- `N`, `S`, `B` — unroll depth, streams (threads), per-request bank latency.
- `ROB_SIZE`, `MAX_STREAM_MLP` — dependency-matrix pipeline bounds.
- `G` — channel inter-admission gap (`1/bandwidth`, `< B`): the channel admits a
  new request every `G` cycles, so requests overlap in flight (latency hiding).
- `TT` — read/write bus turnaround bubble added on each direction switch.
- `C`, `C2`, `PEN_LO`, `PEN_HI` — the **convex** queueing-delay curve (see
  critical note below): the first `C` concurrently-in-flight requests are free,
  past `C` each costs `PEN_LO`, past the steeper knee `C2` each costs `PEN_HI`
  more.
- `W_HIGH`, `W_LOW` — the MSHR windows of the two machines (the only knob that
  differs between them). Currently `6` vs `2`.

Changing the comparison (e.g. "6 vs 2 MSHRs") means editing `W_HIGH` / `W_LOW`
only — nothing else.

## Critical modeling fact — do not regress this

A purely serial, work-conserving channel is **monotone in `W`**: with a shared
workload, a larger window lets requests present no later, so completion times can
only fall, and `T_HighMLP > T_LowMLP` is vacuously **UNSAT**. The model breaks
that monotonicity with the genuine physics of a shared, **pipelined** channel
(Axiom 3), folded in as **identical physics for both machines** — only `W`
differs:

- **Pipelined finite bandwidth (the MLP *benefit*).** The channel admits a new
  request every `G` cycles (`G < B`):
  `St[j] = max(A'[j], St[j-1] + G + TT*switch[j])`, where `switch[j]` is 1 when
  the read/write direction changes from `j-1`. Because admission is faster than
  service, requests **overlap in flight** — a wider window packs them tighter
  against the `G` bound and finishes baseline work earlier. This is the latency
  hiding MLP exists to exploit.
- **Convex queueing delay (the MLP *cost*), measured in TIME.** `inflight[j] =
  #{ i<j : E[i] > St[j] }` — how many earlier requests are still in service when
  `j` starts. Service cost is **convex** in it: the first `C` overlaps are free
  (bank-level parallelism), past `C` each costs `PEN_LO`, past `C2` each costs
  `PEN_HI` more:
  `E[j] = St[j] + B + PEN_LO*max(0,inflight-C) + PEN_HI*max(0,inflight-C2)`.

**Why this is honest and not rigged.** The old model added `PEN * overlap` where
`overlap` counted siblings in the *index* window `[j-W, j)` — a quantity
**monotone in `W` by construction**, so the wide machine *could not* pay less and
the "discovery" was essentially an arithmetic identity. The new `inflight` count
is derived from the **schedule** (`St`/`E`), not from a `W`-indexed window, and
spans **all streams** — so (a) the backfire must *emerge* from timing rather than
being injected, and (b) it captures **cross-thread interference** (an aggressive
stream floods the channel and delays another stream's critical request). The
read/write turnaround `TT` is a third emergent cost. Do **not** revert to an
index-window penalty term — that reintroduces the monotone-by-design artifact.

Key consequence — **under the realistic default config the query is UNSAT, and
that is the correct result, not a bug.** Once the channel offers a couple of
requests of free concurrency (`C=2`), the wide window's latency-hiding benefit
always covers its contention cost within the bounds. The backfire only emerges
in a starved regime (small `C`, large `G`/penalties). See Status.

## Maximizing the deviation (worst case)

After the discovery query returns SAT, the engine does **not** stop at the first
counterexample — it searches for the workload that *maximizes* the deviation
`Delta = T_HighMLP - T_LowMLP`. This is done **without `z3::optimize`** (per the
design constraint), by incremental tightening on the standard solver:

1. Keep the best model found so far (`best`).
2. `push()`, assert `Delta >= best+1`, `check()`.
3. SAT → adopt the larger witness, `pop()`, re-pin `Delta >= best` permanently,
   repeat. UNSAT → `best` is the **proved maximum**. UNKNOWN (timeout) → report
   `best` as a lower bound (not proven maximal).

Each `check()` inherits the solver timeout (60s by default, overridable via the
CLI argument — see Build & run), so the *final* probe (which is the hardest — it
tries to beat the true max) may exhaust it and the run reports "best found"
rather than a proof. The intermediate SAT steps are fast. Raising the timeout
(e.g. `./mlp 600`) gives the final probe more room to either climb higher or
prove maximality.

## Status

Pipelined-channel + convex-queueing + R/W-turnaround model, `6 vs 2` MSHRs.

**Default (realistic) config — `G=2, TT=4, C=2, C2=4, PEN_LO=3, PEN_HI=5`:**
the query is **UNSAT**. Within the bounds, more MLP is never worse — the
latency-hiding benefit of the wide window always covers its contention cost once
the channel offers `C=2` requests of free concurrency. **This is the honest
result: the dogma holds under realistic physics.**

**The backfire emerges only as the channel is starved.** Sweeping the free-
concurrency budget `C` (other defaults fixed):

| `C` | result |
|-----|--------|
| `2` (default) | **UNSAT** — dogma holds |
| `1` | SAT, proved max `Delta = 6` |
| `0` | SAT, `Delta` climbs (timeout-limited at low budget) |

**Pathological channel — `G=6, C=0, C2=1, PEN_LO=8, PEN_HI=16`:** SAT, and
maximization climbs `16 → 19 → 22 → 48 → 72` with the probe for `73` returning
UNSAT, so **delta = 72 is a proved maximum** (`T_HighMLP = 154 > T_LowMLP = 82`),
finishing inside `./mlp 30`.

### Worst-case witness (the pathological-regime proved-maximal workload)

The `delta = 72` counterexample under the starved channel:

- **HighMLP (W=6)** never gates on its MSHR file, so it packs requests against
  the channel admission bound; its `nfly` (in-flight) row climbs to **4**
  concurrent requests, each paying the steep convex penalty (here everything past
  `C2=1` costs `PEN_HI=16`), which stacks into a long tail (`E[7]=154`).
- **LowMLP (W=2)** is throttled: its `nfly` row stays pinned at **1**, so it
  almost never climbs the convex curve even though MSHR gating delays some issues
  (`E[7]=82`).

The aggressive machine's larger *temporal* in-flight count is what its extra MLP
buys, and — only in this starved regime — it is precisely what costs it the
convex contention penalty. Under the realistic default config the same mechanism
exists but the free-concurrency budget absorbs it, so the dogma holds.

The `nfly` row in the timeline dump is the variable to read to see the mechanism:
it is the temporal in-flight count that drives the convex penalty.

## Future work (deferred, not modeled)

- **FR-FCFS / reordering memory controller** — the canonical academic backfire
  mechanism; the channel here services in index order (`St` non-decreasing).
- **Explicit DRAM row-buffer / banks / `tRC`/`tFAW`.**
- **Out-of-order MSHR completion + same-line miss merging** (gating currently
  assumes in-order completion via `E[j-W]`).
- **Start-time backpressure** — queueing currently delays *completion* (`E`),
  not *admission* (`St`).
