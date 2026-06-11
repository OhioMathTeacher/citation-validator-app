"""Tests for the confusion matrix / accuracy calculations in run_benchmark.py.

Verifies that the standard detection convention is used:
  TP = fake citation correctly flagged (detector fires, correct)
  FP = real citation incorrectly flagged (detector fires, wrong)
  TN = real citation correctly NOT flagged (detector silent, correct)
  FN = fake citation that slips through (detector silent, wrong)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from run_benchmark import compute_accuracy


def _make_detail(key, status):
    return {"key": key, "status": status}


# ── Perfect detection on all-fake dataset ──────────────────────────────────

def test_all_fakes_detected():
    """100 fakes all flagged → TP=100, FN=0."""
    details = [_make_detail(f"fake{i}", "invalid") for i in range(100)]
    gt = {"__dataset_level__": "invalid"}
    acc = compute_accuracy(details, gt)

    assert acc["tp"] == 100   # All fakes correctly flagged
    assert acc["fn"] == 0
    assert acc["fp"] == 0
    assert acc["tn"] == 0
    assert acc["accuracy"] == 1.0
    assert acc["recall"] == 1.0


def test_all_fakes_missed():
    """100 fakes all marked valid → FN=100."""
    details = [_make_detail(f"fake{i}", "valid") for i in range(100)]
    gt = {"__dataset_level__": "invalid"}
    acc = compute_accuracy(details, gt)

    assert acc["tp"] == 0
    assert acc["fn"] == 100
    assert acc["recall"] == 0.0


# ── Perfect detection on all-real dataset ──────────────────────────────────

def test_all_real_not_flagged():
    """100 real citations all valid → TN=100, FP=0."""
    details = [_make_detail(f"real{i}", "valid") for i in range(100)]
    gt = {"__dataset_level__": "valid"}
    acc = compute_accuracy(details, gt)

    assert acc["tn"] == 100   # All real citations correctly not flagged
    assert acc["fp"] == 0
    assert acc["accuracy"] == 1.0


def test_all_real_wrongly_flagged():
    """100 real citations all flagged → FP=100."""
    details = [_make_detail(f"real{i}", "suspicious") for i in range(100)]
    gt = {"__dataset_level__": "valid"}
    acc = compute_accuracy(details, gt)

    assert acc["fp"] == 100
    assert acc["tn"] == 0
    assert acc["fpr"] == 1.0


# ── Mixed dataset ─────────────────────────────────────────────────────────

def test_mixed_dataset():
    """50 real (45 valid, 5 flagged) + 50 fake (48 flagged, 2 missed)."""
    details = (
        [_make_detail(f"real{i}", "valid") for i in range(45)]
        + [_make_detail(f"real_fp{i}", "suspicious") for i in range(5)]
        + [_make_detail(f"fake{i}", "invalid") for i in range(48)]
        + [_make_detail(f"fake_fn{i}", "valid") for i in range(2)]
    )
    gt = {}
    for d in details:
        if d["key"].startswith("real"):
            gt[d["key"]] = "valid"
        else:
            gt[d["key"]] = "invalid"

    acc = compute_accuracy(details, gt)

    assert acc["tp"] == 48    # Fakes correctly flagged
    assert acc["fp"] == 5     # Real citations wrongly flagged
    assert acc["tn"] == 45    # Real citations correctly not flagged
    assert acc["fn"] == 2     # Fakes that slipped through

    # Precision: of all flagged, how many are actually fake?
    assert abs(acc["precision"] - 48 / (48 + 5)) < 0.001
    # Recall: of all fakes, how many did we catch?
    assert abs(acc["recall"] - 48 / (48 + 2)) < 0.001
    # FPR: of all real, how many did we wrongly flag?
    assert abs(acc["fpr"] - 5 / (5 + 45)) < 0.001
    # FNR: of all fakes, how many did we miss?
    assert abs(acc["fnr"] - 2 / (2 + 48)) < 0.001

    assert len(acc["false_negatives"]) == 2
    assert len(acc["false_positives"]) == 5


def test_warning_status_not_flagged():
    """'warning' status should NOT count as flagged (only suspicious/invalid)."""
    details = [_make_detail("real1", "warning")]
    gt = {"real1": "valid"}
    acc = compute_accuracy(details, gt)

    assert acc["tn"] == 1  # Warning on a real citation = correctly not flagged
    assert acc["fp"] == 0


def test_empty_details():
    acc = compute_accuracy([], {})
    assert acc is None
