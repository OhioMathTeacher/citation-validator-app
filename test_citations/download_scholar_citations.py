#!/usr/bin/env python3
"""
Google Scholar Citation Downloader
Downloads BibTeX citations from Google Scholar for testing citation validator

Usage:
    python download_scholar_citations.py "query terms" output.bib
    python download_scholar_citations.py --file queries.txt output.bib
"""

import sys
import time
import argparse
from urllib.parse import quote_plus

def generate_scholar_urls(query, num_results=10):
    """Generate Google Scholar URLs for manual download"""
    base_url = "https://scholar.google.com/scholar"
    encoded_query = quote_plus(query)
    
    urls = []
    for start in range(0, num_results, 10):
        url = f"{base_url}?q={encoded_query}&hl=en&start={start}"
        urls.append(url)
    
    return urls

def print_instructions():
    """Print step-by-step instructions for downloading citations"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║  Google Scholar Citation Download Instructions               ║
╚═══════════════════════════════════════════════════════════════╝

AUTOMATED METHOD (Recommended - using scholarly library):
---------------------------------------------------------
1. Install dependencies:
   pip install scholarly

2. Run this script with --auto flag:
   python download_scholar_citations.py --auto "machine learning" output.bib

MANUAL METHOD (No dependencies required):
---------------------------------------------------------
1. Visit the URLs printed below
2. For each paper you want to cite:
   - Click the "Cite" button (quotation marks icon)
   - Click "BibTeX" at the bottom
   - Copy the BibTeX entry
   - Paste into your output file

3. Save all entries in a single .bib file

TIPS:
- Mix recent papers (2024-2026) with older classics (2010-2020)
- Include papers from different fields
- Get papers with and without DOIs
- Include preprints (arXiv) and journal articles
""")

def download_with_scholarly(query, max_results=20):
    """Download citations using scholarly library (requires pip install scholarly)"""
    try:
        from scholarly import scholarly
    except ImportError:
        print("ERROR: scholarly library not installed")
        print("Install with: pip install scholarly")
        sys.exit(1)
    
    print(f"Searching for: {query}")
    print(f"Max results: {max_results}\n")
    
    search_query = scholarly.search_pubs(query)
    citations = []
    
    for i, paper in enumerate(search_query):
        if i >= max_results:
            break
        
        try:
            # Get citation in BibTeX format
            bib = scholarly.bibtex(paper)
            if bib:
                citations.append(bib)
                print(f"✓ Downloaded {i+1}/{max_results}: {paper.get('bib', {}).get('title', 'Unknown')}")
            
            # Be polite to Google Scholar
            time.sleep(2)
        except Exception as e:
            print(f"✗ Failed to download paper {i+1}: {e}")
            continue
    
    return citations

def main():
    parser = argparse.ArgumentParser(description='Download BibTeX citations from Google Scholar')
    parser.add_argument('query', nargs='?', help='Search query')
    parser.add_argument('output', nargs='?', help='Output .bib file')
    parser.add_argument('--auto', action='store_true', help='Use scholarly library for automated download')
    parser.add_argument('--file', help='File with list of queries (one per line)')
    parser.add_argument('--num', type=int, default=20, help='Number of results per query (default: 20)')
    
    args = parser.parse_args()
    
    if args.auto:
        if not args.query or not args.output:
            print("Usage with --auto: python download_scholar_citations.py --auto \"query\" output.bib")
            sys.exit(1)
        
        citations = download_with_scholarly(args.query, args.num)
        
        with open(args.output, 'w') as f:
            f.write(f"% Google Scholar citations for query: {args.query}\n")
            f.write(f"% Downloaded: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("\n\n".join(citations))
        
        print(f"\n✓ Saved {len(citations)} citations to {args.output}")
    
    elif args.file:
        # Read queries from file
        with open(args.file) as f:
            queries = [line.strip() for line in f if line.strip()]
        
        print_instructions()
        print("\nGenerated URLs for your queries:\n")
        
        for query in queries:
            print(f"\nQuery: {query}")
            urls = generate_scholar_urls(query, args.num)
            for url in urls:
                print(f"  {url}")
    
    else:
        # Single query - print instructions and URL
        if not args.query:
            print("Usage: python download_scholar_citations.py \"query\" output.bib")
            print("   or: python download_scholar_citations.py --auto \"query\" output.bib")
            print("   or: python download_scholar_citations.py --file queries.txt output.bib")
            sys.exit(1)
        
        print_instructions()
        print(f"\nQuery: {args.query}\n")
        urls = generate_scholar_urls(args.query, args.num)
        for url in urls:
            print(url)

if __name__ == '__main__':
    main()
