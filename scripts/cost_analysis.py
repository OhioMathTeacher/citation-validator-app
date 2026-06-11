#!/usr/bin/env python3
"""
Cost Analysis for Citation Validator AI Usage

Analyzes token usage from experiment logs and estimates costs for different
AI providers and dataset scales.

Usage:
    python scripts/cost_analysis.py
    python scripts/cost_analysis.py --provider gemini --citations 1000
    python scripts/cost_analysis.py --analyze-logs
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Provider Pricing (as of April 2026) ─────────────────────────────────────
# Prices are per 1M tokens unless otherwise noted

PRICING = {
    "gemini": {
        "name": "Google Gemini 2.5 Flash",
        "input_per_1m": 0.00,  # FREE tier: 1M tokens/day, 1500 req/day
        "output_per_1m": 0.00,
        "free_tier": {
            "tokens_per_day": 1_000_000,
            "requests_per_day": 1_500,
            "requests_per_minute": 15,
        },
        "paid_tier": {
            "input_per_1m": 0.075,  # $0.075 per 1M input tokens
            "output_per_1m": 0.30,  # $0.30 per 1M output tokens
        }
    },
    "groq": {
        "name": "Groq Llama 3.3 70B",
        "input_per_1m": 0.59,
        "output_per_1m": 0.79,
        "free_tier": {
            "tokens_per_day": 14_400,  # Very limited free tier
            "requests_per_minute": 30,
        }
    },
    "openai": {
        "name": "OpenAI GPT-4o",
        "input_per_1m": 2.50,
        "output_per_1m": 10.00,
        "free_tier": None,
    },
    "anthropic": {
        "name": "Anthropic Claude Sonnet 4",
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
        "free_tier": None,
    },
}


def estimate_cost(provider, citation_count, avg_input_tokens=400, avg_output_tokens=250):
    """
    Estimate cost for analyzing a dataset.
    
    Default token estimates based on April 2026 benchmark runs:
    - Input: ~400 tokens (BibTeX fields + database results + prompt)
    - Output: ~250 tokens (JSON response with reasoning)
    - Total: ~650 tokens per citation
    """
    if provider not in PRICING:
        print(f"ERROR: Unknown provider '{provider}'")
        print(f"Available: {', '.join(PRICING.keys())}")
        return None
    
    config = PRICING[provider]
    total_input = citation_count * avg_input_tokens
    total_output = citation_count * avg_output_tokens
    total_tokens = total_input + total_output
    
    # Calculate costs
    input_cost = (total_input / 1_000_000) * config["input_per_1m"]
    output_cost = (total_output / 1_000_000) * config["output_per_1m"]
    total_cost = input_cost + output_cost
    
    result = {
        "provider": provider,
        "provider_name": config["name"],
        "citation_count": citation_count,
        "tokens": {
            "input_per_citation": avg_input_tokens,
            "output_per_citation": avg_output_tokens,
            "total_per_citation": avg_input_tokens + avg_output_tokens,
            "total_input": total_input,
            "total_output": total_output,
            "total": total_tokens,
        },
        "cost": {
            "input": round(input_cost, 4),
            "output": round(output_cost, 4),
            "total": round(total_cost, 4),
        },
    }
    
    # Check free tier limits
    if config.get("free_tier"):
        free = config["free_tier"]
        if "tokens_per_day" in free:
            days_needed = total_tokens / free["tokens_per_day"]
            result["free_tier"] = {
                "tokens_per_day": free["tokens_per_day"],
                "days_needed": round(days_needed, 2),
                "within_daily_limit": total_tokens <= free["tokens_per_day"],
            }
            if "requests_per_day" in free:
                result["free_tier"]["requests_per_day"] = free["requests_per_day"]
                result["free_tier"]["within_request_limit"] = citation_count <= free["requests_per_day"]
    
    return result


def analyze_experiment_logs():
    """Analyze token usage from experiment_log.jsonl."""
    log_path = REPO_ROOT / "results" / "experiments" / "experiment_log.jsonl"
    
    if not log_path.exists():
        print(f"No experiment log found at {log_path}")
        return
    
    runs = []
    with open(log_path) as f:
        for line in f:
            runs.append(json.loads(line))
    
    # Filter to AI-enabled runs
    ai_runs = [r for r in runs if r.get("ai_enabled")]
    
    if not ai_runs:
        print("No AI-enabled runs found in experiment log.")
        return
    
    print(f"\n{'='*70}")
    print(f"  EXPERIMENT LOG ANALYSIS")
    print(f"{'='*70}\n")
    print(f"Total runs: {len(runs)} ({len(ai_runs)} with AI)")
    print()
    
    # Group by provider
    by_provider = {}
    for run in ai_runs:
        provider = run.get("ai_provider", "unknown")
        if provider not in by_provider:
            by_provider[provider] = []
        by_provider[provider].append(run)
    
    for provider, provider_runs in sorted(by_provider.items()):
        print(f"Provider: {provider}")
        print(f"  Runs: {len(provider_runs)}")
        
        total_citations = sum(r.get("ai_calls", 0) for r in provider_runs)
        total_tokens = sum(r.get("tokens", {}).get("total_tokens", 0) for r in provider_runs)
        total_input = sum(r.get("tokens", {}).get("input_tokens", 0) for r in provider_runs)
        total_output = sum(r.get("tokens", {}).get("output_tokens", 0) for r in provider_runs)
        
        if total_citations > 0:
            avg_tokens = total_tokens / total_citations
            avg_input = total_input / total_citations
            avg_output = total_output / total_citations
            
            print(f"  Total citations analyzed: {total_citations}")
            print(f"  Total tokens: {total_tokens:,}")
            print(f"  Avg per citation: {avg_tokens:.0f} tokens ({avg_input:.0f} in, {avg_output:.0f} out)")
            
            # Calculate cost
            if provider in PRICING:
                config = PRICING[provider]
                input_cost = (total_input / 1_000_000) * config["input_per_1m"]
                output_cost = (total_output / 1_000_000) * config["output_per_1m"]
                total_cost = input_cost + output_cost
                
                if total_cost > 0:
                    print(f"  Estimated cost: ${total_cost:.4f}")
                else:
                    print(f"  Estimated cost: FREE (within free tier)")
                
                # Show what percentage of daily limit was used
                if config.get("free_tier") and "tokens_per_day" in config["free_tier"]:
                    daily_limit = config["free_tier"]["tokens_per_day"]
                    pct = (total_tokens / daily_limit) * 100
                    print(f"  Daily free limit usage: {pct:.1f}%")
        
        print()


def print_cost_table(citation_counts, providers=None):
    """Print a comparison table of costs across providers and scales."""
    if providers is None:
        providers = list(PRICING.keys())
    
    print(f"\n{'='*70}")
    print(f"  COST ESTIMATES BY PROVIDER & SCALE")
    print(f"{'='*70}\n")
    print("Assumptions: ~400 input tokens, ~250 output tokens per citation")
    print()
    
    # Header
    print(f"{'Citations':<12}", end="")
    for p in providers:
        print(f"{PRICING[p]['name']:<25}", end="")
    print()
    print(f"{'-'*12}", end="")
    for _ in providers:
        print(f"{'-'*25}", end="")
    print()
    
    # Rows
    for count in citation_counts:
        print(f"{count:>10}  ", end="")
        for provider in providers:
            est = estimate_cost(provider, count)
            cost = est["cost"]["total"]
            
            if cost == 0:
                # Check if within free tier
                free = PRICING[provider].get("free_tier")
                if free and "tokens_per_day" in free:
                    total_tokens = est["tokens"]["total"]
                    days = total_tokens / free["tokens_per_day"]
                    if days <= 1:
                        print(f"{'FREE (1 day)':<25}", end="")
                    else:
                        print(f"{'FREE (' + f'{days:.1f}' + ' days)':<25}", end="")
                else:
                    print(f"{'FREE':<25}", end="")
            elif cost < 0.01:
                print(f"${cost:.4f}{'':<18}", end="")
            elif cost < 1:
                print(f"${cost:.3f}{'':<19}", end="")
            else:
                print(f"${cost:.2f}{'':<20}", end="")
        print()
    
    print()


def main():
    parser = argparse.ArgumentParser(description="Analyze AI costs for citation validation")
    parser.add_argument("--provider", choices=list(PRICING.keys()), 
                       help="Estimate cost for specific provider")
    parser.add_argument("--citations", type=int, 
                       help="Number of citations to estimate")
    parser.add_argument("--input-tokens", type=int, default=400,
                       help="Average input tokens per citation (default: 400)")
    parser.add_argument("--output-tokens", type=int, default=250,
                       help="Average output tokens per citation (default: 250)")
    parser.add_argument("--analyze-logs", action="store_true",
                       help="Analyze token usage from experiment logs")
    parser.add_argument("--table", action="store_true",
                       help="Show cost comparison table")
    
    args = parser.parse_args()
    
    if args.analyze_logs:
        analyze_experiment_logs()
    
    if args.provider and args.citations:
        est = estimate_cost(args.provider, args.citations, 
                          args.input_tokens, args.output_tokens)
        
        print(f"\n{'='*70}")
        print(f"  COST ESTIMATE: {est['provider_name']}")
        print(f"{'='*70}\n")
        print(f"Citations: {est['citation_count']:,}")
        print(f"\nTokens:")
        print(f"  Input:  {est['tokens']['total_input']:>10,} ({est['tokens']['input_per_citation']} per citation)")
        print(f"  Output: {est['tokens']['total_output']:>10,} ({est['tokens']['output_per_citation']} per citation)")
        print(f"  Total:  {est['tokens']['total']:>10,} ({est['tokens']['total_per_citation']} per citation)")
        
        if est["cost"]["total"] > 0:
            print(f"\nCost:")
            print(f"  Input:  ${est['cost']['input']:>8.4f}")
            print(f"  Output: ${est['cost']['output']:>8.4f}")
            print(f"  Total:  ${est['cost']['total']:>8.4f}")
        else:
            print(f"\nCost: FREE")
        
        if "free_tier" in est:
            free = est["free_tier"]
            print(f"\nFree Tier:")
            print(f"  Daily limit: {free['tokens_per_day']:,} tokens")
            print(f"  Days needed: {free['days_needed']}")
            print(f"  Within daily token limit: {free['within_daily_limit']}")
            if "within_request_limit" in free:
                print(f"  Within daily request limit: {free['within_request_limit']}")
        
        print()
    
    if args.table or (not args.provider and not args.analyze_logs):
        # Default: show cost table
        citation_counts = [10, 50, 100, 500, 1000, 5000, 10000]
        print_cost_table(citation_counts)
        
        print("\nNOTE: Gemini 2.5 Flash free tier allows 1M tokens/day, 1500 requests/day.")
        print("      This is sufficient for ~1500 citations per day at no cost.")
        print("      For larger datasets, run over multiple days or upgrade to paid tier.")
        print()


if __name__ == "__main__":
    main()
