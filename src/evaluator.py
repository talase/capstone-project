"""Evaluate extracted profiles against expected synthetic style behavior."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from profile_store import load_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"


EXPECTED_CHECKS = {
    "teacher": [("formality", ">=", 0.65), ("politeness", ">=", 0.65)],
    "boss": [("formality", ">=", 0.60), ("verbosity", "<=", 0.65)],
    "friend": [("formality", "<=", 0.45), ("optimism", ">=", 0.55)],
    "sister": [("formality", "<=", 0.50), ("optimism", ">=", 0.55)],
    "delivery": [("verbosity", "<=", 0.45), ("formality", "<=", 0.55)],
    "mom": [("politeness", ">=", 0.65), ("optimism", ">=", 0.55)],
}


def _score(profile: dict[str, Any], trait: str) -> float:
    return float(profile.get("traits", {}).get(trait, {}).get("score", 0.5))


def _passes(value: float, operator: str, expected: float) -> bool:
    if operator == ">=":
        return value >= expected
    if operator == "<=":
        return value <= expected
    raise ValueError(f"Unsupported operator: {operator}")


def evaluate_profiles() -> dict[str, Any]:
    """Read saved profiles, print results, and write JSON/CSV summaries."""

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []

    for contact_file in sorted(DATA_DIR.glob("*.txt")):
        contact = contact_file.stem
        profile = load_profile(contact)
        checks = EXPECTED_CHECKS.get(contact, [])
        check_results = []

        for trait, operator, expected in checks:
            value = _score(profile, trait)
            passed = _passes(value, operator, expected)
            check_results.append(
                {
                    "trait": trait,
                    "rule": f"{operator} {expected}",
                    "value": round(value, 3),
                    "passed": passed,
                }
            )
            rows.append(
                {
                    "contact": contact,
                    "trait": trait,
                    "expected": f"{operator} {expected}",
                    "actual": round(value, 3),
                    "status": "PASS" if passed else "FAIL",
                }
            )

        results[contact] = {
            "profile": profile,
            "checks": check_results,
            "status": "PASS" if all(item["passed"] for item in check_results) else "FAIL",
        }

        print(f"\n=== {contact.upper()} ===")
        print(json.dumps(profile, indent=2))
        for item in check_results:
            status = "PASS" if item["passed"] else "FAIL"
            print(f"{status}: {item['trait']} {item['rule']} (actual {item['value']})")

    (RESULTS_DIR / "style_results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    with (RESULTS_DIR / "test_summary.csv").open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["contact", "trait", "expected", "actual", "status"],
        )
        writer.writeheader()
        writer.writerows(rows)

    return results


if __name__ == "__main__":
    evaluate_profiles()
