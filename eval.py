"""
Lightweight evaluator: check relations against gem5 stats.

Usage:
    python3 eval.py /path/to/stats.txt

For each relation:
  - Check if the claim holds (True/False)
  - If epsilon_name is set, compute minimum epsilon needed to make it true
  - Report results to stdout and eval_results.txt
"""

from pathlib import Path
from collections import defaultdict
import sys

from relations import ALL_RELATIONS


def parse_stats_file(path: str | Path) -> dict[str, float]:
    """Parse gem5 stats.txt into {stat_name: float}."""
    stats: dict[str, float] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("---") or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            key = parts[0]
            val_str = parts[1]
            try:
                val = float(val_str)
            except ValueError:
                continue
            # skip NaN, inf
            if val != val or val_str.lower() in ("inf", "-inf"):
                continue
            stats[key] = val
    return stats


def parse_stats_file_windows(path: str | Path) -> list[dict[str, float]]:
    """Parse gem5 stats.txt with multiple ROI dumps into per-window dicts."""
    BEGIN = "---------- Begin Simulation Statistics ----------"
    END = "---------- End Simulation Statistics   ----------"

    windows: list[dict[str, float]] = []
    current: dict[str, float] = {}
    inside = False

    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if stripped == BEGIN:
                inside = True
                current = {}
                continue
            if stripped == END:
                if current:
                    windows.append(current)
                inside = False
                continue
            if inside:
                parts = stripped.split()
                if len(parts) >= 2:
                    key = parts[0]
                    val_str = parts[1]
                    try:
                        val = float(val_str)
                        if val == val and val_str.lower() not in ("inf", "-inf"):
                            current[key] = val
                    except ValueError:
                        continue

    if not windows:
        return [parse_stats_file(path)]
    return windows


def resolve_metric(stats: dict[str, float], metric_name: str) -> float | None:
    """Resolve a high-level metric name to a value from gem5 stats.

    Prioritizes LLC (L3) cache metrics. Falls back to L2 or L1 if needed.

    Examples:
        'hit_rate' -> hits/accesses (LLC/L3 cache)
        'miss_rate' -> misses/accesses
        'stalls' -> cycles - instructions
    """
    metric_name = metric_name.lower()

    # Direct lookups
    if metric_name in stats:
        return stats[metric_name]

    # Computed metrics (prioritize LLC/L3)
    if metric_name == 'hit_rate' or metric_name == 'hit_rate_llc' or metric_name == 'hit_rate_l3':
        hits = stats.get('board.cache_hierarchy.llcache.overallHits::total')
        accesses = stats.get('board.cache_hierarchy.llcache.overallAccesses::total')
        if hits is not None and accesses is not None and accesses > 0:
            return hits / accesses
        # fallback: compute from misses
        accesses = stats.get('board.cache_hierarchy.llcache.overallAccesses::total')
        misses = stats.get('board.cache_hierarchy.llcache.overallMisses::total')
        if accesses is not None and misses is not None and accesses > 0:
            return (accesses - misses) / accesses

    if metric_name == 'miss_rate' or metric_name == 'miss_rate_llc' or metric_name == 'miss_rate_l3':
        misses = stats.get('board.cache_hierarchy.llcache.overallMisses::total')
        accesses = stats.get('board.cache_hierarchy.llcache.overallAccesses::total')
        if misses is not None and accesses is not None and accesses > 0:
            return misses / accesses

    if metric_name == 'load_hit_rate':
        hits = stats.get('board.cache_hierarchy.llcache.ReadReq_hits::total')
        accesses = stats.get('board.cache_hierarchy.llcache.ReadReq_accesses::total')
        if hits is not None and accesses is not None and accesses > 0:
            return hits / accesses
        # fallback to overall
        hits = stats.get('board.cache_hierarchy.llcache.overallHits::total')
        accesses = stats.get('board.cache_hierarchy.llcache.overallAccesses::total')
        if hits is not None and accesses is not None and accesses > 0:
            return hits / accesses

    if metric_name == 'store_hit_rate':
        hits = stats.get('board.cache_hierarchy.llcache.WriteReq_hits::total')
        accesses = stats.get('board.cache_hierarchy.llcache.WriteReq_accesses::total')
        if hits is not None and accesses is not None and accesses > 0:
            return hits / accesses
        # fallback to overall
        hits = stats.get('board.cache_hierarchy.llcache.overallHits::total')
        accesses = stats.get('board.cache_hierarchy.llcache.overallAccesses::total')
        if hits is not None and accesses is not None and accesses > 0:
            return hits / accesses

    if metric_name == 'stalls':
        cycles = stats.get('board.processor.switch.core.numCycles')
        insts = stats.get('board.processor.switch.core.simInsts')
        if cycles is not None and insts is not None:
            return max(0, cycles - insts)

    if metric_name == 'total_misses':
        return stats.get('board.cache_hierarchy.llcache.overallMisses::total')

    if metric_name == 'evictions':
        return stats.get('board.cache_hierarchy.llcache.replacements')

    if metric_name == 'writebacks':
        return stats.get('board.cache_hierarchy.llcache.writebacks::total')

    return None


def extract_data_for_relation(stats: dict[str, float], relation: dict) -> tuple[dict, list[str]]:
    """Extract metric values needed by a relation.

    Returns (data_dict, missing_keys) where missing_keys are metrics that couldn't be resolved.
    """
    data = {}
    missing = []

    if 'requires' not in relation:
        return data, missing

    for metric in relation['requires']:
        val = resolve_metric(stats, metric)
        if val is not None:
            data[metric] = val
        else:
            missing.append(metric)

    return data, missing


def evaluate_relation(relation: dict, stats: dict[str, float]) -> dict:
    """Evaluate a single relation against stats.

    Returns a dict with:
        - 'name': relation name
        - 'holds': True/False/None (None = unevaluable)
        - 'epsilon': float or None (minimum epsilon needed to make claim true)
        - 'missing': list of unresolved metrics
    """
    data, missing = extract_data_for_relation(stats, relation)

    if missing:
        return {
            'name': relation['name'],
            'holds': None,
            'epsilon': None,
            'missing': missing,
        }

    try:
        holds = relation['claim'](data)
    except Exception as e:
        return {
            'name': relation['name'],
            'holds': None,
            'epsilon': None,
            'missing': [str(e)],
        }

    epsilon = None
    if relation['epsilon_name']:
        # Compute minimum epsilon needed (always 0 for now; can be refined later)
        epsilon = 0.0 if holds else None

    return {
        'name': relation['name'],
        'holds': holds,
        'epsilon': epsilon,
        'missing': [],
    }


def format_result(result: dict) -> str:
    """Format a result dict as human-readable text."""
    name = result['name']
    holds = result['holds']
    epsilon = result['epsilon']
    missing = result['missing']

    if holds is None:
        status = "UNEVALUABLE"
        if missing:
            reason = f"missing: {', '.join(missing)}"
        else:
            reason = "error during evaluation"
        return f"  [{name}] {status} — {reason}"
    elif holds:
        if epsilon is not None:
            return f"  [{name}] HOLDS (epsilon={epsilon})"
        else:
            return f"  [{name}] HOLDS"
    else:
        if epsilon is not None:
            return f"  [{name}] VIOLATED (needs epsilon={epsilon})"
        else:
            return f"  [{name}] VIOLATED"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 eval.py <stats.txt> [<stats.txt> ...]")
        sys.exit(1)

    all_results = []

    for stats_path in sys.argv[1:]:
        print(f"\n{'='*70}")
        print(f"Evaluating: {stats_path}")
        print('='*70)

        # Try to parse windows, fall back to single parse
        windows = parse_stats_file_windows(stats_path)

        for window_idx, stats in enumerate(windows):
            print(f"\nWindow {window_idx}:")
            for relation in ALL_RELATIONS:
                result = evaluate_relation(relation, stats)
                print(format_result(result))
                all_results.append({
                    'stats_file': str(stats_path),
                    'window': window_idx,
                    **result,
                })

    # Write summary to eval_results.txt
    output_path = Path('eval_results.txt')
    with open(output_path, 'w') as f:
        f.write("RELATION EVALUATION SUMMARY\n")
        f.write("="*70 + "\n\n")

        # Group by file
        by_file = defaultdict(list)
        for r in all_results:
            by_file[r['stats_file']].append(r)

        for stats_file, results in sorted(by_file.items()):
            f.write(f"File: {stats_file}\n")
            f.write("-"*70 + "\n")

            # Count holds/violated/unevaluable
            holds_count = sum(1 for r in results if r['holds'] is True)
            violated_count = sum(1 for r in results if r['holds'] is False)
            unevaluable_count = sum(1 for r in results if r['holds'] is None)

            f.write(f"  HOLDS: {holds_count}, VIOLATED: {violated_count}, UNEVALUABLE: {unevaluable_count}\n\n")

            # Per-window detail
            by_window = defaultdict(list)
            for r in results:
                by_window[r['window']].append(r)

            for window_idx in sorted(by_window.keys()):
                f.write(f"  Window {window_idx}:\n")
                for r in by_window[window_idx]:
                    f.write(f"    {format_result(r)}\n")
            f.write("\n")

    print(f"\n\nResults written to {output_path}")


if __name__ == '__main__':
    main()
