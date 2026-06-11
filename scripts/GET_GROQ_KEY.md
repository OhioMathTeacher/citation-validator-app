# How to Get Your Groq API Key

## Quick Setup (2 minutes)

1. **Go to:** https://console.groq.com/
2. **Sign up/Log in** (free account, no credit card needed)
3. **Navigate to:** API Keys section
4. **Click:** "Create API Key"
5. **Copy the key** (starts with `gsk_...`)

## Set Your API Key

### Option 1: Environment Variable (Recommended)
```bash
export GROQ_API_KEY="gsk_your_key_here"
```

### Option 2: In your shell profile (Persistent)
```bash
echo 'export GROQ_API_KEY="gsk_your_key_here"' >> ~/.bashrc
source ~/.bashrc
```

### Option 3: Command-line argument
```bash
python3 citation_validator.py --ai --groq-key "gsk_your_key_here" file.bib
```

## Test It Works
```bash
python3 scripts/citation_validator.py --ai test_citations/2604.05875/custom.bib
```

You should see AI analysis in the output!

---
**Free Tier Limits:**
- 30 requests/minute
- 7,000 requests/day
- Plenty for our use case!
