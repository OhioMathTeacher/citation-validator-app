#!/bin/bash
# Quick Start: Generate 1,000 test citations in 5 minutes
# Run this to get initial test data quickly

set -e

echo "=========================================="
echo "Citation Validator - Quick Test Data Setup"
echo "=========================================="
echo ""

# Step 1: Extract citations from existing arXiv papers
echo "[1/4] Extracting citations from existing arXiv papers..."
python3 extract_citations_from_arxiv.py --all
echo "✓ Done"
echo ""

# Step 2: Download some CrossRef samples (200 citations)
echo "[2/4] Downloading 200 random citations from CrossRef..."
python3 download_crossref_sample.py 200 real_citations/crossref_random/
echo "✓ Done"
echo ""

# Step 3: Generate fake citations
echo "[3/4] Generating 400 fake citations..."
python3 generate_fake_citations.py --type all --count 400 --output false_negative_tests/
echo "✓ Done"
echo ""

# Step 4: Run tests
echo "[4/4] Running validation tests..."
python3 run_all_tests.py --limit 50
echo "✓ Done"
echo ""

echo "=========================================="
echo "Quick start complete!"
echo ""
echo "Next steps:"
echo "  - Scale up: download_crossref_sample.py 2000"
echo "  - Generate more fakes: generate_fake_citations.py --count 1000"
echo "  - Full test: run_all_tests.py (no --limit)"
echo "=========================================="
