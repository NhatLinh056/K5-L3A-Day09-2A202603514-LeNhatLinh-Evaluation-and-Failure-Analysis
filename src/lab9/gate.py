"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    import math

    problems: list[str] = []

    # 1. Any metric value in pr["metrics"] that is NaN or inf
    for m, v in pr.get("metrics", {}).items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            problems.append(f"metric {m} is {v}")

    # 2. Check row count vs manifest
    manifest = pr.get("manifest", {})
    expected_rows = manifest.get("items", 0) * len(manifest.get("seeds", []))
    if expected_rows > 0 and len(pr.get("rows", [])) != expected_rows:
        problems.append(f"row count {len(pr.get('rows', []))} != {expected_rows}")

    # 3. Check duplicate (item_id, seed) rows
    pairs = [(r.get("item_id"), r.get("seed")) for r in pr.get("rows", [])]
    if len(pairs) != len(set(pairs)):
        problems.append("duplicate (item_id, seed) rows in PR")

    # 4. Check (item_id, seed) set vs baseline
    pr_pairs = set(pairs)
    base_pairs = {(r.get("item_id"), r.get("seed")) for r in base.get("rows", [])}
    if base_pairs and pr_pairs != base_pairs:
        problems.append(f"PR (item_id, seed) set differs from baseline (PR: {len(pr_pairs)}, base: {len(base_pairs)})")

    # 5. Check evaluator_failures or None values for graded spec metrics in rows
    if pr.get("evaluator_failures"):
        problems.append(f"evaluator_failures non-empty ({len(pr['evaluator_failures'])})")
    graded_mids = [m["id"] for m in spec.get("metrics", [])]
    for r in pr.get("rows", []):
        for mid in graded_mids:
            if mid in r and r[mid] is None:
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} has None for metric {mid}")
                break
        else:
            continue
        break

    # 6. Check slice tags of each item vs baseline
    base_slices: dict[str, set[str]] = {}
    for r in base.get("rows", []):
        iid = r.get("item_id")
        if iid and iid not in base_slices:
            base_slices[iid] = set(r.get("slices") or [])
    for r in pr.get("rows", []):
        iid = r.get("item_id")
        if iid in base_slices and set(r.get("slices") or []) != base_slices[iid]:
            problems.append(f"item {iid} slice tags in PR differ from baseline")
            break

    # 7. Ratchet check when base_spec is provided (for same eval-set version)
    if base_spec is not None and base_spec.get("eval_set_version") == spec.get("eval_set_version"):
        spec_metrics = {m["id"]: m for m in spec.get("metrics", [])}
        for bm in base_spec.get("metrics", []):
            mid = bm["id"]
            if mid not in spec_metrics:
                problems.append(f"metric {mid} was removed from spec")
                continue
            sm = spec_metrics[mid]
            if bm.get("blocking") and not sm.get("blocking"):
                problems.append(f"metric {mid} changed from blocking to non-blocking")

            b_th = bm.get("threshold", {})
            s_th = sm.get("threshold", {})
            if "min" in b_th:
                if "min" not in s_th or s_th["min"] < b_th["min"]:
                    problems.append(f"metric {mid} min threshold loosened ({b_th.get('min')} -> {s_th.get('min')})")
            if "max" in b_th:
                if "max" not in s_th or s_th["max"] > b_th["max"]:
                    problems.append(f"metric {mid} max threshold loosened ({b_th.get('max')} -> {s_th.get('max')})")
            if "max_increase" in b_th:
                if "max_increase" not in s_th or s_th["max_increase"] > b_th["max_increase"]:
                    problems.append(f"metric {mid} max_increase loosened")
            if b_th.get("no_significant_drop") and not s_th.get("no_significant_drop"):
                problems.append(f"metric {mid} dropped no_significant_drop")

        spec_slices = {sl["name"]: sl for sl in spec.get("slices", [])}
        for b_sl in base_spec.get("slices", []):
            sname = b_sl["name"]
            if sname not in spec_slices:
                problems.append(f"slice {sname} was removed from spec")
                continue
            s_sl = spec_slices[sname]
            if b_sl.get("blocking") and not s_sl.get("blocking"):
                problems.append(f"slice {sname} changed from blocking to non-blocking")
            if "min" in b_sl:
                if "min" not in s_sl or s_sl["min"] < b_sl["min"]:
                    problems.append(f"slice {sname} min threshold loosened")
            if b_sl.get("no_significant_drop") and not s_sl.get("no_significant_drop"):
                problems.append(f"slice {sname} dropped no_significant_drop")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices", []):
        name = sl["name"]
        metric = sl["metric"]
        sid = f"slice:{name}/{metric}"
        min_th = sl.get("min")
        no_drop = sl.get("no_significant_drop", False)
        is_blocking = sl.get("blocking", False)

        pr_items = per_item(pr, metric, slice_name=name)
        val = sum(pr_items.values()) / len(pr_items) if pr_items else 0.0

        verdict, note = "ok", ""
        if min_th is not None and val < min_th:
            verdict = "fail"

        if no_drop and pr_items:
            base_items = per_item(base, metric, slice_name=name)
            keys = sorted(set(pr_items) & set(base_items))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [pr_items[k] for k in keys],
                    [base_items[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"

        if verdict != "ok" and is_blocking:
            blocked.append(sid)

        label = "ok" if verdict == "ok" else ("BLOCK" if is_blocking else "warn")
        th_info = {k: v for k, v in sl.items() if k not in ("name", "metric")}
        lines.append(f"  {sid:<28} {val!s:<8} {json.dumps(th_info):<34} {note:<28} {label}")

    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
