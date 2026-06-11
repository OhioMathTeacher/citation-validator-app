#!/usr/bin/env python3
"""
Test Runner for Citation Validator
Runs validation on all test citations and compares against ground truth
Calculates precision, recall, F1, false positive/negative rates
"""

import sys
import json
import subprocess
import time
from pathlib import Path
from collections import defaultdict
import argparse

def run_validator(bib_file, validator_script='../scripts/citation_validator.py'):
    """Run citation validator on a BibTeX file and return per-citation results."""
    # Import the validator as a library for per-citation granularity.
    # This avoids the old approach of parsing summary counts from stdout,
    # which collapsed per-file metrics and hid individual misses.
    scripts_dir = str(Path(validator_script).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    try:
        from citation_validator import CitationValidator
    except ImportError:
        # Fallback: run as subprocess if import fails
        return _run_validator_subprocess(bib_file, validator_script)

    try:
        validator = CitationValidator(verbose=False)
        results = validator.validate_file(Path(bib_file))

        # Build per-citation detail list
        citation_results = []
        for detail in results.get('details', []):
            citation_results.append({
                'key': detail['key'],
                'status': detail['status'],  # valid / warning / suspicious / invalid
            })

        return {
            'file': str(bib_file),
            'total': results['total'],
            'valid': results['valid'],
            'warnings': results['warnings'],
            'suspicious': results['suspicious'],
            'invalid': results['invalid'],
            'problematic': results['suspicious'] + results['invalid'],
            'citations': citation_results,
            'output': '',
        }

    except Exception as e:
        return {'file': str(bib_file), 'error': str(e)}


def _run_validator_subprocess(bib_file, validator_script):
    """Legacy fallback: run validator as subprocess and parse stdout."""
    try:
        result = subprocess.run(
            ['python3', validator_script, str(bib_file)],
            capture_output=True,
            text=True,
            timeout=60
        )

        output = result.stdout + result.stderr

        import re
        total_match = re.search(r'Total citations:\s*(\d+)', output)
        valid_match = re.search(r'✓ Valid:\s*(\d+)', output)
        warnings_match = re.search(r'⚠ Warnings:\s*(\d+)', output)
        suspicious_match = re.search(r'⚠⚠ Suspicious:\s*(\d+)', output)
        invalid_match = re.search(r'✗ Invalid:\s*(\d+)', output)

        total = int(total_match.group(1)) if total_match else 0
        valid = int(valid_match.group(1)) if valid_match else 0
        warnings = int(warnings_match.group(1)) if warnings_match else 0
        suspicious = int(suspicious_match.group(1)) if suspicious_match else 0
        invalid = int(invalid_match.group(1)) if invalid_match else 0

        problematic = suspicious + invalid

        return {
            'file': str(bib_file),
            'total': total,
            'valid': valid,
            'warnings': warnings,
            'suspicious': suspicious,
            'invalid': invalid,
            'problematic': problematic,
            'citations': [],  # Not available in subprocess mode
            'output': output
        }

    except subprocess.TimeoutExpired:
        return {'file': str(bib_file), 'error': 'timeout'}
    except Exception as e:
        return {'file': str(bib_file), 'error': str(e)}

def load_ground_truth(test_dirs):
    """Load ground truth labels from all test directories"""
    ground_truth = {}
    
    for test_dir in test_dirs:
        test_path = Path(test_dir)
        
        # Automatically determine expected results baseon directory structure
        if 'real_citations' in str(test_path):
            expected = 'VALID'
        elif 'false_negative' in str(test_path):
            expected = 'INVALID'
        elif 'false_positive' in str(test_path):
            expected = 'VALID'  # Real citations that might be incorrectly flagged
        else:
            expected = 'UNKNOWN'
        
        # Find all .bib files
        if test_path.exists():
            for bib_file in test_path.rglob('*.bib'):
                ground_truth[str(bib_file)] = expected
    
    return ground_truth

def evaluate_results(results, ground_truth):
    """Calculate precision, recall, F1, etc.

    Uses PER-CITATION granularity when available (library mode).
    Falls back to per-file evaluation for legacy subprocess results.
    """

    # Confusion matrix
    tp = 0  # True positive: Correctly identified as VALID
    tn = 0  # True negative: Correctly identified as INVALID
    fp = 0  # False positive: Real citation flagged as INVALID
    fn = 0  # False negative: Fake citation marked as VALID

    per_citation_count = 0  # Track how many citations we evaluated individually
    per_file_count = 0

    for result in results:
        file_path = result['file']
        expected = ground_truth.get(file_path, 'UNKNOWN')

        if expected == 'UNKNOWN':
            continue

        citations = result.get('citations', [])

        if citations:
            # Per-citation evaluation — the accurate path
            for cit in citations:
                status = cit['status']
                # 'suspicious' and 'invalid' are flagged; 'valid' and 'warning' are not
                is_flagged = status in ('suspicious', 'invalid')

                if expected == 'VALID':
                    if not is_flagged:
                        tp += 1
                    else:
                        fp += 1
                elif expected == 'INVALID':
                    if is_flagged:
                        tn += 1
                    else:
                        fn += 1

                per_citation_count += 1
        else:
            # Fallback: per-file evaluation (subprocess mode)
            has_issues = result.get('problematic', 0) > 0
            total_in_file = result.get('total', 1) or 1

            if expected == 'VALID':
                # Approximate: distribute valid/flagged across citations
                flagged = result.get('suspicious', 0) + result.get('invalid', 0)
                tp += total_in_file - flagged
                fp += flagged
            elif expected == 'INVALID':
                flagged = result.get('suspicious', 0) + result.get('invalid', 0)
                tn += flagged
                fn += total_in_file - flagged

            per_file_count += 1

    # Calculate metrics
    total = tp + tn + fp + fn

    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0  # False positive rate
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0  # False negative rate

    return {
        'confusion_matrix': {
            'true_positive': tp,
            'true_negative': tn,
            'false_positive': fp,
            'false_negative': fn,
            'total': total,
            'evaluated_per_citation': per_citation_count,
            'evaluated_per_file_fallback': per_file_count,
        },
        'metrics': {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'false_positive_rate': fpr,
            'false_negative_rate': fnr
        }
    }

def print_report(evaluation, results):
    """Print human-readable test report"""
    
    cm = evaluation['confusion_matrix']
    metrics = evaluation['metrics']
    
    print("\n" + "="*70)
    print("CITATION VALIDATOR TEST RESULTS")
    print("="*70)
    
    per_cit = cm.get('evaluated_per_citation', 0)
    per_file = cm.get('evaluated_per_file_fallback', 0)
    print(f"\nEvaluation granularity: {per_cit} citations evaluated individually"
          + (f", {per_file} files via fallback" if per_file else ""))

    print("\nConfusion Matrix:")
    print(f"  True Positives (TP):   {cm['true_positive']:4d}  (Real citations correctly validated)")
    print(f"  True Negatives (TN):   {cm['true_negative']:4d}  (Fake citations correctly caught)")
    print(f"  False Positives (FP):  {cm['false_positive']:4d}  (Real citations incorrectly flagged) ⚠️")
    print(f"  False Negatives (FN):  {cm['false_negative']:4d}  (Fake citations that slipped through) ⚠️")
    print(f"  Total:                 {cm['total']:4d}")
    
    print("\nPerformance Metrics:")
    print(f"  Accuracy:              {metrics['accuracy']:.2%}")
    print(f"  Precision:             {metrics['precision']:.2%}  (When we say it's real, how often are we right?)")
    print(f"  Recall:                {metrics['recall']:.2%}  (Of all real citations, how many did we validate?)")
    print(f"  F1 Score:              {metrics['f1_score']:.2%}  (Harmonic mean of precision and recall)")
    print(f"  False Positive Rate:   {metrics['false_positive_rate']:.2%}  (Real citations incorrectly flagged)")
    print(f"  False Negative Rate:   {metrics['false_negative_rate']:.2%}  (Fake citations that slipped through)")
    
    print("\n" + "="*70)
    
    # Interpretation
    print("\nInterpretation:")
    if metrics['false_positive_rate'] < 0.05:
        print("✓ Low false positive rate - won't annoy users with false alarms")
    else:
        print(f"⚠️ High false positive rate ({metrics['false_positive_rate']:.1%}) - may flag too many real citations")
    
    if metrics['false_negative_rate'] < 0.10:
        print("✓ Low false negative rate - catches most fake citations")
    else:
        print(f"⚠️ High false negative rate ({metrics['false_negative_rate']:.1%}) - many fakes slipping through")
    
    if metrics['f1_score'] > 0.90:
        print("✓ Excellent overall performance (F1 > 0.90)")
    elif metrics['f1_score'] > 0.80:
        print("✓ Good overall performance (F1 > 0.80)")
    else:
        print("⚠️ Performance needs improvement")
    
    print("="*70 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Run citation validator tests')
    parser.add_argument('--validator', default='../scripts/citation_validator.py',
                       help='Path to citation validator script')
    parser.add_argument('--test-dirs', nargs='+',
                       default=['real_citations/', 'false_negative_tests/', 'false_positive_tests/'],
                       help='Directories containing test citations')
    parser.add_argument('--limit', type=int, help='Limit number of files to test (for quick testing)')
    parser.add_argument('--output', default='test_results.json', help='Output file for results')
    
    args = parser.parse_args()
    
    print("Citation Validator Test Runner")
    print("=" * 70)
    print(f"Validator: {args.validator}")
    print(f"Test directories: {', '.join(args.test_dirs)}\n")
    
    # Load ground truth
    print("Loading ground truth labels...")
    ground_truth = load_ground_truth(args.test_dirs)
    print(f"✓ Loaded {len(ground_truth)} test cases\n")
    
    # Find all .bib files to test
    test_files = []
    for test_dir in args.test_dirs:
        test_path = Path(test_dir)
        if test_path.exists():
            test_files.extend(test_path.rglob('*.bib'))
    
    if args.limit:
        test_files = test_files[:args.limit]
    
    print(f"Testing {len(test_files)} files...\n")
    
    # Run validator on each file
    results = []
    start_time = time.time()
    
    for i, bib_file in enumerate(test_files, 1):
        print(f"[{i}/{len(test_files)}] Testing {bib_file.name}... ", end='', flush=True)
        
        result = run_validator(bib_file, args.validator)
        results.append(result)
        
        if 'error' in result:
            print(f"✗ {result['error']}")
        else:
            prob = result.get('problematic', 0)
            total = result.get('total', 0)
            warn = result.get('warnings', 0)
            susp = result.get('suspicious', 0)
            inv = result.get('invalid', 0)
            print(f"✓ ({prob} issues: {warn}W {susp}S {inv}I / {total} total)")
    
    elapsed = time.time() - start_time
    print(f"\n✓ Completed {len(results)} tests in {elapsed:.1f} seconds")
    print(f"  Average: {elapsed/len(results):.2f} seconds per file\n")
    
    # Evaluate results
    print("Evaluating results against ground truth...")
    evaluation = evaluate_results(results, ground_truth)
    
    # Print report
    print_report(evaluation, results)
    
    # Save detailed results
    output_data = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'validator': args.validator,
        'test_dirs': args.test_dirs,
        'total_files': len(test_files),
        'elapsed_seconds': elapsed,
        'evaluation': evaluation,
        'results': results
    }
    
    with open(args.output, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"✓ Detailed results saved to {args.output}")

if __name__ == '__main__':
    main()
