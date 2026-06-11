# Citation Validator AI Example

This example shows how to use AI-powered Frankenstein citation detection.

## Setup

1. Get a free Groq API key from https://console.groq.com/
2. Set it as an environment variable:

```bash
export GROQ_API_KEY='your-groq-api-key-here'
```

## Usage

### Basic validation (CrossRef + OpenAlex only):
```bash
python3 scripts/citation_validator.py bibliography.bib
```

### With AI analysis for suspicious citations:
```bash
python3 scripts/citation_validator.py bibliography.bib --ai --verbose
```

### Or pass API key directly:
```bash
python3 scripts/citation_validator.py bibliography.bib --ai --groq-key 'your-key'
```

## What the AI Does

The AI (Llama 3.1 via Groq) analyzes suspicious citations to detect:
- **Frankenstein citations** - Assembled from fragments of multiple papers
- **Metadata inconsistencies** - Title/author/journal combinations that don't make sense
- **Hallucination patterns** - Common patterns in AI-generated fake citations

## Example Output

```
[INVALID] Bettayeb2024
  ✗ Invalid DOI: API error: HTTP Error 404: Not Found
  🤖 AI Analysis: LIKELY HALLUCINATED (85% confidence)
     Reason: DOI format is valid but returns 404. Title and author 
     combination appears plausible but cannot be verified in any 
     database. Common pattern in LLM-generated citations.
```

## Performance

- **Without AI**: Fast (~0.1s per citation)
- **With AI**: Slower (~0.5s per suspicious citation)
- **Cost**: Free on Groq's tier (Llama 3.1-8B-Instant)

## Tips

- Run without `--ai` first to identify suspicious citations
- Use `--ai` only when you find suspicious/invalid citations
- AI is most useful for edge cases where metadata is plausible but wrong
- Always manually verify AI flagged citations

## Model Details

- **Model**: Llama 3.1 8B Instant (via Groq)
- **Why this model**: Fast, free tier, good at pattern analysis
- **Temperature**: 0.1 (low randomness for consistent analysis)
- **Max tokens**: 200 (concise analysis)
