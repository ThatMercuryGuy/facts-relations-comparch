# Facts & Relations: Lightweight Cache Microarchitecture Verification

A minimal framework for stating falsifiable claims about cache replacement and verifying them against gem5 simulation data.

## What This Is

A relation is a claim: "if cache A has property X and cache B has property Y, then the outcome satisfies Z (within tolerance ε)."

For example: "If cache A has size ≥ cache B's size, then A's hit rate ≥ B's hit rate (within epsilon_1)."

## Files

- **`relations.py`** — 15 relation definitions (facts F1–F2 and relations R1–R14). Each relation is a dict with:
  - `name`: identifier (F1, R1, etc.)
  - `claim`: callable that checks if the relation holds for given data
  - `epsilon_name`: name of slack variable (or None for exact relations)
  - `requires`: list of metric names the claim needs

- **`eval.py`** — Evaluator. Loads gem5 stats.txt files, resolves metrics, checks each relation, computes minimum epsilon needed. Outputs to eval_results.txt.

- **`corpus.md`** — Human-readable LaTeX descriptions of each relation (unchanged).

- **`system-relations.md`** — Coupled epsilon systems and interactions (unchanged).

## Running

```bash
# Evaluate a single stats file
python3 eval.py /path/to/stats.txt

# Evaluate multiple stats files
python3 eval.py run1/stats.txt run2/stats.txt run3/stats.txt

# Results go to eval_results.txt
```

## Adding a New Relation

1. Add a dict to `relations.py` with `name`, `description`, `premises`, `claim`, `epsilon_name`, `requires`.
2. Add it to `ALL_RELATIONS` list.
3. Update the assert at the bottom.

Example:

```python
R_my_claim = {
    'name': 'R15',
    'description': 'my claim about cache behavior',
    'premises': ['some_metric_a >= some_metric_b'],
    'claim': lambda d: d.get('outcome_a', 0) >= d.get('outcome_b', 0),
    'epsilon_name': 'eps_15',
    'requires': ['outcome_a', 'outcome_b', 'some_metric_a', 'some_metric_b'],
}

ALL_RELATIONS.append(R_my_claim)
assert len(ALL_RELATIONS) == 16  # update count
```

## Metric Resolution

The evaluator resolves high-level metric names to gem5 stats, prioritizing LLC (L3) cache:
- `hit_rate` → `hits / accesses` (LLC/L3 cache)
- `miss_rate` → `misses / accesses`
- `load_hit_rate`, `store_hit_rate` → read/write hit rates
- `stalls` → `cycles - instructions`
- `evictions`, `writebacks`, `total_misses` → direct stat lookups

All metrics are mapped to `board.cache_hierarchy.llcache.*` stats. Add more metric resolution logic in `resolve_metric()`.

## Design Notes

- Relations are just dicts + lambdas — no heavy AST machinery.
- Each claim is a pure function: `data dict -> bool`.
- Epsilon computation is intentionally simple for now (can be refined later).
- Single-entity relations (F1, F2) check properties of one dataset.
- Multi-entity relations compare two or more datasets (pass them as separate keys in data dict).
