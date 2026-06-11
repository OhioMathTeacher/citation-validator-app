# Token Tracking & Cost Analysis for Citation Validator

**Added: April 10, 2026**

## What's New

We've enhanced the Citation Validator with comprehensive **token usage tracking** and **cost estimation tools** to help you run research affordably at scale.

### 1. Token Usage Tracking

**All AI providers now return token metadata:**
- Input tokens (prompt sent to AI)
- Output tokens (response from AI)
- Total tokens (sum of both)
- Finish reason (STOP, MAX_TOKENS, etc.)

This data is automatically captured and saved to experiment logs.

### 2. Enhanced Experiment Logs

**run_benchmark.py now tracks:**
- Total tokens used per run (input/output/total)
- Average tokens per citation
- AI error counts and types
- Per-citation token data in detailed JSON outputs

**Example experiment_log.jsonl entry:**
```json
{
  "timestamp": "2026-04-10T04:25:00Z",
  "dataset_id": "compound-deception-ansari",
  "citation_count": 100,
  "ai_enabled": true,
  "ai_provider": "gemini",
  "ai_model": "Gemini 2.5 Flash",
  "ai_calls": 100,
  "ai_errors": 0,
  "tokens": {
    "input_tokens": 42500,
    "output_tokens": 23000,
    "total_tokens": 65500,
    "avg_per_call": 655.0
  },
  "deterministic_seconds": 58.7,
  "ai_seconds": 125.3,
  "total_seconds": 184.0,
  "accuracy": { ... }
}
```

### 3. Cost Analysis Tool

**New script: `scripts/cost_analysis.py`**

**Show cost comparison across all providers:**
```bash
python scripts/cost_analysis.py --table
```

**Estimate cost for a specific scale:**
```bash
python scripts/cost_analysis.py --provider gemini --citations 1000
python scripts/cost_analysis.py --provider openai --citations 5000
```

**Analyze token usage from past runs:**
```bash
python scripts/cost_analysis.py --analyze-logs
```

## Why This Matters for "Research for the Rest of Us"

### Gemini 2.5 Flash is Extremely Affordable

**Free tier provides:**
- 1,000,000 tokens per day
- 1,500 requests per day
- 15 requests per minute

**At ~650 tokens per citation, you can analyze:**
- **~1,500 citations per day for FREE**
- Split larger datasets across multiple days
- Perfect for academic research budgets!

### Real Cost Examples

| Dataset Size | Gemini (Free) | Groq | OpenAI | Anthropic |
|--------------|---------------|------|--------|-----------|
| 100 citations | FREE (1 day) | $0.04 | $0.35 | $0.50 |
| 1,000 citations | FREE (1 day) | $0.43 | $3.50 | $4.95 |
| 10,000 citations | FREE (6.5 days) | $4.33 | $35.00 | $49.50 |

**For a Nature-scale analysis (1000-5000 citations):**
- Gemini: FREE (run over 1-3 days)
- Groq: $0.43-$2.17
- OpenAI: $3.50-$17.50
- Anthropic: $4.95-$24.75

## How Token Tracking Works

### 1. API Response Enrichment

Each AI provider returns usage metadata:

**Gemini:**
```json
{
  "is_suspicious": true,
  "confidence": 90,
  "reason": "...",
  "_metadata": {
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "finish_reason": "STOP",
    "tokens": {
      "input_tokens": 425,
      "output_tokens": 230,
      "total_tokens": 655
    }
  }
}
```

**Groq, OpenAI, Anthropic:**
Similar structure with provider-specific field names mapped to standard format.

### 2. Benchmark Runner Aggregation

The benchmark script:
1. Captures token metadata from each `/analyze` call
2. Accumulates totals across all citations
3. Calculates averages per citation
4. Saves to experiment logs

### 3. Cost Analysis

The `cost_analysis.py` script:
- Reads experiment logs
- Applies current provider pricing
- Calculates actual and projected costs
- Shows free tier availability

## Usage Recommendations

### For Small Tests (10-100 citations)
- Use Gemini free tier directly
- Instant results, zero cost

### For Medium Datasets (100-1000 citations)
- Use Gemini free tier
- Stay within daily limits
- One day for 1000 citations

### For Large Datasets (1000-10000+ citations)
- **Option 1:** Gemini free tier split across multiple days
  - 1500 citations/day max
  - 10,000 citations = 7 days
  - Total cost: $0
- **Option 2:** Paid Gemini tier for speed
  - 10,000 citations ≈ $0.65
  - Much cheaper than other providers
- **Option 3:** Compare providers
  - Run small sample on each
  - Measure accuracy vs cost trade-offs

## Data for Nature Paper

The enhanced tracking gives you publication-quality data:

✅ **Token usage per citation** (supports reproducibility claims)  
✅ **Cost per citation** (demonstrates accessibility)  
✅ **Error rates** (shows reliability)  
✅ **Timing data** (supports scalability claims)  
✅ **Accuracy metrics** (proves effectiveness)  

### Example Analysis for Paper

```python
# Load from experiment logs
import json
from pathlib import Path

log_path = Path("Test Results/experiments/experiment_log.jsonl")
runs = [json.loads(line) for line in log_path.read_text().splitlines()]

# Filter to Gemini runs
gemini_runs = [r for r in runs if r.get("ai_provider") == "gemini"]

# Calculate aggregate stats
total_citations = sum(r["ai_calls"] for r in gemini_runs)
total_tokens = sum(r.get("tokens", {}).get("total_tokens", 0) for r in gemini_runs)
avg_accuracy = sum(r.get("accuracy", {}).get("accuracy", 0) for r in gemini_runs) / len(gemini_runs)

print(f"Analyzed {total_citations} citations")
print(f"Used {total_tokens:,} tokens ({total_tokens/total_citations:.0f} avg)")
print(f"Accuracy: {avg_accuracy*100:.1f}%")
print(f"Cost: FREE (Gemini free tier)")
```

## Next Steps

1. **Run full Ansari100 benchmark with Gemini:**
   ```bash
   export GEMINI_API_KEY=your_key_here
   python scripts/run_benchmark.py --dataset ansari100 --provider gemini
   ```

2. **Analyze results:**
   ```bash
   python scripts/cost_analysis.py --analyze-logs
   ```

3. **Test on real citations dataset:**
   - Measure false positive rate
   - Validate precision/recall trade-offs

4. **Scale up:**
   - Run multiple datasets
   - Track token usage trends
   - Document for paper

## Cost-Effective Research FTW! 🎉

You can now run a **rigorous, publication-quality study** on AI hallucination detection **for basically zero dollars** using Gemini's generous free tier!

That's research "for the rest of us"! ✊
