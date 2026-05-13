#!/usr/bin/env python3
"""Benchmark wiki_dream.py against the planted ground truth.

For each fixture domain under tests/dreaming_fixtures/<domain>/:

1. (Re)build the fixture so log.md and pages reflect the spec.
2. Run wiki_dream.py with the fixture's `fixture_today` and `watermark`.
3. Compare the candidate set against expected.json.
4. Compute precision (TP / promoted), recall (TP / should_repromote).
5. Compute reason_quality: each TP's reasons must include the
   tokens listed in expected.json (loose substring match).
6. With --gate, exit nonzero if precision or recall < threshold.

Usage:
    run_dreaming_eval.py --fixture market_research [--gate]
        [--precision-min 0.7] [--recall-min 0.5]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugin" / "scripts"
FIXTURES = ROOT / "tests" / "dreaming_fixtures"
BUILDERS = {
    "market_research": ROOT / "tests" / "build_dreaming_fixture.py",
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fixture", required=True)
    p.add_argument("--precision-min", type=float, default=0.7)
    p.add_argument("--recall-min", type=float, default=0.5)
    p.add_argument("--gate", action="store_true",
                   help="Exit 1 if precision or recall is below threshold")
    p.add_argument("--rebuild", action="store_true", default=True,
                   help="Rebuild fixture before evaluating (default true)")
    args = p.parse_args()

    fixture_dir = FIXTURES / args.fixture
    expected_path = fixture_dir / "expected.json"
    if not expected_path.exists():
        print(f"FAIL: {expected_path} not found", file=sys.stderr)
        return 2

    builder = BUILDERS.get(args.fixture)
    if args.rebuild and builder and builder.exists():
        subprocess.run([sys.executable, str(builder)],
                       check=True, capture_output=True, cwd=str(ROOT))

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    fixture_today = expected["fixture_today"]
    watermark = expected["watermark"]

    out_path = ROOT / f"_tmp_dream_{args.fixture}.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "wiki_dream.py"),
         "--wiki", str(fixture_dir),
         "--today", fixture_today,
         "--since", watermark,
         "--out", str(out_path)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if proc.returncode != 0:
        print(f"FAIL: wiki_dream exited {proc.returncode}", file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        return 3

    dream = json.loads(out_path.read_text(encoding="utf-8"))
    promoted = {c["page"]: c for c in dream["candidates"]}

    expected_pages = {x["page"]: x for x in expected["should_repromote"]}
    should_stay = set(expected["should_stay_frozen"])

    tp = set(promoted) & set(expected_pages)
    fp = set(promoted) & should_stay
    fp_other = set(promoted) - set(expected_pages) - should_stay
    fn = set(expected_pages) - set(promoted)

    precision = len(tp) / len(promoted) if promoted else 0.0
    recall = len(tp) / len(expected_pages) if expected_pages else 0.0

    # Reason quality: each TP's reasons must include the required substrings
    reason_failures = []
    for page in tp:
        spec = expected_pages[page]
        cand = promoted[page]
        reasons_blob = " ".join(cand.get("reasons", [])).lower()
        for required in spec.get("reason_must_include", []):
            if required.lower() not in reasons_blob:
                reason_failures.append(
                    f"{page}: missing reason token {required!r} "
                    f"(reasons: {cand.get('reasons', [])})")

    # min_score check
    score_failures = []
    for page in tp:
        spec = expected_pages[page]
        cand = promoted[page]
        if cand["score"] < spec.get("min_score", 0):
            score_failures.append(
                f"{page}: score {cand['score']} < min_score {spec['min_score']}")

    summary = {
        "fixture": args.fixture,
        "fixture_today": fixture_today,
        "watermark": watermark,
        "totals": {
            "promoted": len(promoted),
            "expected_repromote": len(expected_pages),
            "expected_stay_frozen": len(should_stay),
        },
        "true_positives": sorted(tp),
        "false_positives_against_should_stay": sorted(fp),
        "false_positives_other": sorted(fp_other),
        "false_negatives": sorted(fn),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "reason_failures": reason_failures,
        "score_failures": score_failures,
        "thresholds": {
            "precision_min": args.precision_min,
            "recall_min": args.recall_min,
        },
    }

    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.gate:
        if precision < args.precision_min:
            print(f"\nGATE FAILED: precision {precision:.3f} < "
                  f"{args.precision_min}", file=sys.stderr)
            return 1
        if recall < args.recall_min:
            print(f"\nGATE FAILED: recall {recall:.3f} < "
                  f"{args.recall_min}", file=sys.stderr)
            return 1
        if reason_failures:
            print(f"\nGATE FAILED: {len(reason_failures)} reason-quality "
                  f"failures", file=sys.stderr)
            return 1
        if score_failures:
            print(f"\nGATE FAILED: {len(score_failures)} min-score "
                  f"failures", file=sys.stderr)
            return 1
        print(f"\nGATE PASSED: precision {precision:.3f}, recall {recall:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
