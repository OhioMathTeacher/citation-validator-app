#!/usr/bin/env python3
"""
Citation Validator for Ohio Journal of School Mathematics
Validates citations in BibTeX files to detect hallucinated or invalid references.
"""

import re
import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from urllib.parse import quote, urlencode, urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Import enhanced validation heuristics
try:
    from citation_enhancements import EnhancedValidator
    HAS_ENHANCEMENTS = True
except ImportError:
    HAS_ENHANCEMENTS = False


class TransientNetworkError(Exception):
    """A network request could not complete due to rate limiting, timeouts,
    or transient server errors. Callers MUST treat this as 'could not
    verify' (status: warning) -- never as evidence of fabrication."""


class CitationValidator:
    """Validates academic citations against CrossRef, OpenAlex, and Semantic Scholar APIs."""
    
    def __init__(self, verbose=False, use_ai=False, groq_api_key=None):
        self.verbose = verbose
        self.use_ai = use_ai
        self.groq_api_key = groq_api_key or os.environ.get('GROQ_API_KEY')
        self.crossref_api = "https://api.crossref.org/works/"
        self.openalex_api = "https://api.openalex.org/works"
        self.groq_api = "https://api.groq.com/openai/v1/chat/completions"
        self.rate_limit_delay = 0.25  # Polite delay before AI calls

        # --- Request throttling, to stay under free-API rate limits ---
        # Minimum seconds between successive requests to the same host.
        # arXiv is strictest (it asks for ~1 request every 3 seconds).
        self._min_interval = {
            'export.arxiv.org': 3.0,
            'api.crossref.org': 0.5,
            'api.openalex.org': 0.2,
            'api.semanticscholar.org': 1.1,
            'doi.org': 0.5,
        }
        self._last_request = {}      # host -> timestamp of last request
        self._max_attempts = 4       # request attempts before giving up
        # Identify the client politely: CrossRef and OpenAlex grant a
        # better rate-limit pool to requests that carry a mailto.
        self.user_agent = ('OJSM-CitationValidator/2.0 '
                           '(mailto:editor@ohiomathjournal.org)')
        
        if self.use_ai and not self.groq_api_key:
            print("Warning: AI analysis requested but no GROQ_API_KEY found")
            print("Set GROQ_API_KEY environment variable or pass --groq-key")
            self.use_ai = False
        
    def _throttle(self, host: str) -> None:
        """Sleep as needed so requests to `host` stay under its rate limit."""
        min_interval = self._min_interval.get(host, 0.5)
        elapsed = time.time() - self._last_request.get(host, 0.0)
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request[host] = time.time()

    def _http_get(self, url: str, headers: Optional[Dict] = None,
                  timeout: int = 15) -> bytes:
        """Fetch `url` with per-host throttling and exponential-backoff retry.

        Returns the response body on success.
        Raises HTTPError for a *definitive* failure (e.g. 404 -- the
        resource genuinely does not exist).
        Raises TransientNetworkError if the request cannot complete after
        every retry (rate limits, timeouts, 5xx). Callers MUST treat that
        as 'could not verify' -- never as 'invalid'.
        """
        host = urlparse(url).netloc
        hdrs = {'User-Agent': self.user_agent}
        if headers:
            hdrs.update(headers)
        last_error = None
        for attempt in range(self._max_attempts):
            self._throttle(host)
            try:
                req = Request(url, headers=hdrs)
                with urlopen(req, timeout=timeout) as response:
                    return response.read()
            except HTTPError as e:
                if e.code in (429, 500, 502, 503, 504):
                    last_error = e          # transient -- back off and retry
                else:
                    raise                   # definitive (404 etc.) -- propagate
            except (URLError, TimeoutError, OSError) as e:
                last_error = e              # network / timeout -- transient
            if attempt < self._max_attempts - 1:
                time.sleep(2 ** attempt)    # exponential backoff: 1, 2, 4 s
        raise TransientNetworkError(
            f"{host}: request failed after {self._max_attempts} attempts "
            f"({last_error})")

    def parse_bibtex(self, filepath: Path) -> List[Dict]:
        """Parse a BibTeX file and extract citation entries."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return self._parse_bibtex_string(content)

    def _parse_bibtex_string(self, content: str) -> List[Dict]:
        """Parse a BibTeX string using brace-depth tracking (matches JS parser)."""
        entries = []
        i = 0

        while i < len(content):
            # Find next @
            at_idx = content.find('@', i)
            if at_idx == -1:
                break

            # Find opening brace
            open_brace = content.find('{', at_idx)
            if open_brace == -1:
                break

            # Extract entry type
            entry_type = content[at_idx + 1:open_brace].strip()
            if not entry_type or not entry_type.isalpha():
                i = at_idx + 1
                continue

            # Walk forward tracking brace depth to find matching close
            depth = 0
            end_idx = -1
            for j in range(open_brace, len(content)):
                if content[j] == '{':
                    depth += 1
                elif content[j] == '}':
                    depth -= 1
                    if depth == 0:
                        end_idx = j
                        break

            if end_idx == -1:
                break

            # Interior is everything between the outer braces
            interior = content[open_brace + 1:end_idx]

            # Split cite key from fields at first comma
            comma_idx = interior.find(',')
            if comma_idx == -1:
                i = end_idx + 1
                continue

            cite_key = interior[:comma_idx].strip()
            fields_str = interior[comma_idx + 1:]

            # Parse fields using brace-depth-aware parser
            fields = self._parse_bibtex_fields(fields_str)

            entries.append({
                'type': entry_type,
                'key': cite_key,
                'fields': fields
            })

            i = end_idx + 1

        return entries

    @staticmethod
    def _parse_bibtex_fields(fields_str: str) -> Dict:
        """Parse BibTeX fields with proper brace-depth tracking."""
        fields = {}
        i = 0

        def skip_delimiters():
            nonlocal i
            while i < len(fields_str) and fields_str[i] in ' \t\n\r,':
                i += 1

        while i < len(fields_str):
            skip_delimiters()
            if i >= len(fields_str):
                break

            # Match field name = ...
            m = re.match(r'([a-zA-Z][\w-]*)\s*=', fields_str[i:])
            if not m:
                i += 1
                continue

            field_name = m.group(1).lower()
            i += m.end()

            # Skip whitespace after =
            while i < len(fields_str) and fields_str[i] in ' \t\n\r':
                i += 1
            if i >= len(fields_str):
                break

            value = ''

            if fields_str[i] == '{':
                # Brace-delimited value — track depth
                i += 1
                depth = 1
                start = i
                while i < len(fields_str) and depth > 0:
                    if fields_str[i] == '{':
                        depth += 1
                    elif fields_str[i] == '}':
                        depth -= 1
                    i += 1
                value = fields_str[start:i - 1].strip()

            elif fields_str[i] == '"':
                # Quote-delimited value
                i += 1
                start = i
                while i < len(fields_str):
                    if fields_str[i] == '"' and fields_str[i - 1:i] != '\\':
                        break
                    i += 1
                value = fields_str[start:i].strip()
                i += 1  # skip closing quote

            else:
                # Bare value (number or string constant)
                start = i
                while i < len(fields_str) and fields_str[i] not in ',\n}':
                    i += 1
                value = fields_str[start:i].strip()

            fields[field_name] = value

        return fields
    
    def validate_doi(self, doi: str) -> Tuple[bool, Dict]:
        """Validate a DOI via CrossRef, falling back to the doi.org resolver.

        Returns (is_valid, data). On a transient failure (rate limit,
        timeout) the returned data carries 'transient': True -- callers
        MUST treat that as 'could not verify' (warning), not 'invalid'.
        """
        if not doi:
            return False, {'error': 'No DOI provided'}

        # Clean DOI
        doi = doi.strip().replace('https://doi.org/', '').replace('http://dx.doi.org/', '')

        # arXiv DOIs use DataCite, not CrossRef -- query the arXiv API directly
        arxiv_match = re.match(r'10\.48550/arXiv\.(\d+\.\d+)', doi)
        if arxiv_match:
            return self._validate_arxiv(arxiv_match.group(1))

        url = f"{self.crossref_api}{quote(doi)}"
        try:
            data = json.loads(self._http_get(url).decode('utf-8'))
            if data.get('status') == 'ok':
                return True, data.get('message', {})
            # CrossRef responded but had no record -- fall through to resolver
        except HTTPError as e:
            if e.code != 404 and self.verbose:
                print(f"  CrossRef HTTP {e.code} for {doi}; trying resolver")
            # 404 or other HTTP error -- the resolver may still settle it
        except TransientNetworkError as e:
            if self.verbose:
                print(f"  CrossRef unreachable for {doi} ({e}); trying resolver")
        except (json.JSONDecodeError, ValueError):
            pass  # malformed response -- fall through to resolver

        # CrossRef did not confirm the DOI. The resolver catches DataCite
        # DOIs (Zenodo, Figshare, etc.) and reports a definitive 'not
        # registered' separately from a transient failure.
        return self._validate_doi_resolver(doi)
    
    def _validate_arxiv(self, arxiv_id: str) -> Tuple[bool, Dict]:
        """Validate an arXiv paper via the arXiv API.

        A transient failure returns (False, {'transient': True}); a clean
        response with no matching paper returns a definitive (False, ...).
        """
        url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
        try:
            data = self._http_get(url).decode('utf-8')
        except HTTPError as e:
            return False, {'error': f'arXiv API HTTP {e.code}', 'transient': True}
        except TransientNetworkError as e:
            return False, {'error': f'arXiv API unreachable ({e})', 'transient': True}
        except Exception as e:
            return False, {'error': f'arXiv API error: {e}', 'transient': True}

        # arXiv returns Atom XML; a genuine entry has a <title> that is not "Error"
        if '<title>' in data and 'Error' not in data.split('<title>')[1].split('</title>')[0]:
            titles = re.findall(r'<title[^>]*>(.*?)</title>', data, re.DOTALL)
            title = titles[-1].strip() if len(titles) > 1 else titles[0].strip()
            authors = re.findall(r'<name>(.*?)</name>', data)
            return True, {
                'title': [title],
                'author': [{'given': a.split()[-1], 'family': ' '.join(a.split()[:-1])} for a in authors] if authors else [],
                'source': 'arxiv',
                'arxiv_id': arxiv_id
            }
        # arXiv answered cleanly and the paper is genuinely absent
        return False, {'error': f'arXiv paper {arxiv_id} not found'}
    
    def _validate_doi_resolver(self, doi: str) -> Tuple[bool, Dict]:
        """Fallback: check whether a DOI resolves via doi.org's handle API.

        Catches DataCite DOIs (Zenodo, Figshare, Dryad, etc.). Distinguishes
        a definitive 'not registered' from a transient failure.
        """
        url = f"https://doi.org/api/handles/{doi}"
        try:
            data = json.loads(self._http_get(url, timeout=10).decode('utf-8'))
            # The handle API returns responseCode 1 for a registered DOI.
            if data.get('responseCode') == 1:
                metadata = self._fetch_doi_metadata(doi)
                metadata['source'] = 'doi_resolver'
                metadata['doi'] = doi
                return True, metadata
            # responseCode 100 etc. -- the handle is definitively not registered
            return False, {'error': 'DOI not registered in CrossRef or doi.org'}
        except HTTPError as e:
            if e.code == 404:
                # handle API 404 -- DOI genuinely not registered
                return False, {'error': 'DOI not registered in CrossRef or doi.org'}
            return False, {'error': f'DOI resolver HTTP {e.code}', 'transient': True}
        except TransientNetworkError as e:
            return False, {'error': f'DOI resolver unreachable ({e})', 'transient': True}
        except (json.JSONDecodeError, ValueError):
            return False, {'error': 'DOI resolver returned malformed data',
                            'transient': True}

    def _fetch_doi_metadata(self, doi: str) -> Dict:
        """Fetch structured metadata for a DOI via content negotiation (CSL-JSON).

        Best-effort only: the DOI is already confirmed to exist by the time
        this is called, so any failure simply returns an empty dict.
        """
        url = f"https://doi.org/{quote(doi)}"
        try:
            body = self._http_get(url, headers={
                'Accept': 'application/vnd.citationstyles.csl+json'}, timeout=10)
            data = json.loads(body.decode('utf-8'))
            # Normalise into the same shape check_citation expects
            result = {}
            if 'title' in data:
                result['title'] = [data['title']] if isinstance(data['title'], str) else data['title']
            if 'author' in data:
                result['author'] = data['author']  # already list-of-dicts in CSL-JSON
            if 'issued' in data:
                result['published'] = {'date-parts': data['issued'].get('date-parts', [[None]])}
            elif 'published' in data:
                result['published'] = data['published']
            return result
        except Exception:
            return {}

    @staticmethod
    def _jaccard_words(a: str, b: str) -> float:
        """Word-level Jaccard similarity using \\w+ tokenisation."""
        words_a = set(re.findall(r'\w+', a.lower()))
        words_b = set(re.findall(r'\w+', b.lower()))
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)
    
    def search_openalex(self, title: str, author: str = None) -> Tuple[bool, Dict]:
        """Search OpenAlex for a publication by title and optional author."""
        if not title:
            return False, {'error': 'No title provided'}
        
        # Build search query
        query_parts = [f'title.search:"{title}"']
        if author:
            query_parts.append(f'author.search:"{author}"')
        
        params = {
            'filter': ','.join(query_parts),
            'per_page': 1,
            'mailto': 'editor@ohiomathjournal.org'  # Polite pool
        }
        
        url = f"{self.openalex_api}?{urlencode(params)}"

        try:
            data = json.loads(self._http_get(url, timeout=10).decode('utf-8'))
            results = data.get('results', [])
            if results:
                return True, results[0]
            return False, {'error': 'No matching publication found'}
        except (HTTPError, URLError, TransientNetworkError) as e:
            return False, {'error': f'API error: {e}', 'transient': True}
        except Exception as e:
            return False, {'error': f'Unexpected error: {e}'}
    
    def search_semantic_scholar(self, title: str) -> Tuple[bool, Dict]:
        """Scholar Agent fallback: search Semantic Scholar for a publication by title."""
        if not title:
            return False, {'error': 'No title provided'}

        params = urlencode({
            'query': title,
            'fields': 'title,authors,year,venue,externalIds',
            'limit': 1
        })
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"

        try:
            data = json.loads(self._http_get(url, timeout=10).decode('utf-8'))
            papers = data.get('data', [])
            if papers:
                paper = papers[0]
                ext_ids = paper.get('externalIds', {}) or {}
                return True, {
                    'title': paper.get('title'),
                    'authors': ', '.join(a.get('name', '') for a in (paper.get('authors') or [])),
                    'venue': paper.get('venue'),
                    'year': paper.get('year'),
                    'doi': ext_ids.get('DOI'),
                    'source': 'semantic_scholar'
                }
            else:
                return False, {'error': 'No matching publication found'}

        except (URLError, HTTPError) as e:
            return False, {'error': f'API error: {str(e)}'}
        except Exception as e:
            return False, {'error': f'Unexpected error: {str(e)}'}

    def analyze_with_ai(self, entry: Dict, metadata: Dict, suspicion_reasons: List[str] = None) -> Optional[Dict]:
        """Use Groq AI to analyze if citation looks like a Frankenstein citation."""
        if not self.use_ai or not self.groq_api_key:
            return None
        
        # Build enhanced prompt with more context
        if HAS_ENHANCEMENTS and suspicion_reasons:
            prompt = EnhancedValidator.improved_ai_prompt(entry, metadata, suspicion_reasons)
        else:
            # Fallback to original prompt
            fields = entry['fields']
            prompt = f"""Analyze this academic citation for signs of being AI-hallucinated or a "Frankenstein citation" (combining fragments from multiple real papers).

BibTeX Entry:
- Type: {entry['type']}
- Title: {fields.get('title', 'N/A')}
- Author(s): {fields.get('author', 'N/A')}
- Year: {fields.get('year', 'N/A')}
- Journal: {fields.get('journal', 'N/A')}
- DOI: {fields.get('doi', 'N/A')}

Verified Metadata (if found):
{json.dumps(metadata, indent=2) if metadata else 'None found'}

Does this citation show signs of being fabricated or assembled from fragments? Consider:
1. Are the components (title, author, journal, year) internally consistent?
2. Do they match any verified publication data?
3. Are there unusual patterns (generic titles, mismatched metadata)?

Respond with JSON: {{"is_suspicious": true/false, "confidence": 0-100, "reason": "brief explanation"}}"""

        payload = {
            "model": "llama-3.3-70b-versatile",  # Match webapp.py model
            "messages": [
                {"role": "system", "content": "You are an expert at detecting fabricated academic citations. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 200
        }
        
        try:
            time.sleep(self.rate_limit_delay)
            req = Request(
                self.groq_api,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Authorization': f'Bearer {self.groq_api_key}',
                    'Content-Type': 'application/json'
                }
            )
            response = urlopen(req, timeout=30)
            data = json.loads(response.read().decode('utf-8'))
            
            # Extract AI response
            content = data['choices'][0]['message']['content']
            # Try to parse JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return None
                
        except Exception as e:
            if self.verbose:
                print(f"  AI analysis failed: {str(e)}")
            return None
    
    def check_citation(self, entry: Dict) -> Dict:
        """Check a single citation entry for issues."""
        result = {
            'key': entry['key'],
            'type': entry['type'],
            'fields': entry['fields'],
            'status': 'valid',
            'issues': [],
            'warnings': [],
            'ai_analysis': None,
            'suspicion_reasons': []
        }
        
        fields = entry['fields']
        doi = fields.get('doi', '')
        verified_metadata = None
        is_arxiv_doi = doi.lower().startswith('10.48550/arxiv.') if doi else False
        
        # ENHANCEMENT: Check for suspicious patterns first
        if HAS_ENHANCEMENTS:
            suspicion_warnings = EnhancedValidator.check_suspicious_patterns(entry)
            result['suspicion_reasons'].extend(suspicion_warnings)
            if suspicion_warnings:
                result['warnings'].extend(suspicion_warnings)
                if result['status'] == 'valid':
                    result['status'] = 'warning'
        
        # Try DOI validation first
        if doi:
            is_valid, doi_data = self.validate_doi(doi)
            
            if not is_valid:
                if doi_data.get('transient'):
                    # Transient API failure (rate limit / timeout): the DOI
                    # could not be VERIFIED -- 'unverifiable', not
                    # 'fabricated'. Record a warning, never an invalid flag.
                    result['warnings'].append(
                        f"DOI could not be verified: {doi_data.get('error', 'transient API failure')}")
                    if result['status'] == 'valid':
                        result['status'] = 'warning'
                    if self.use_ai:
                        result['ai_analysis'] = self.analyze_with_ai(
                            entry, None, result['suspicion_reasons'])
                    return result
                # Definitive: the DOI is not registered in any registry.
                result['status'] = 'invalid'
                result['issues'].append(f"Invalid DOI: {doi_data.get('error', 'Unknown error')}")
                result['suspicion_reasons'].append("DOI validation failed")
                
                # AI analysis for invalid DOI
                if self.use_ai:
                    result['ai_analysis'] = self.analyze_with_ai(entry, None, result['suspicion_reasons'])
                
                return result
            
            verified_metadata = doi_data

            # Compare metadata using Jaccard similarity
            if 'title' in fields and 'title' in doi_data:
                bib_title = fields['title']
                doi_title = ' '.join(doi_data['title']) if isinstance(doi_data['title'], list) else doi_data['title']

                sim = self._jaccard_words(bib_title, doi_title)
                if sim < 0.4:
                    result['warnings'].append(f"Title mismatch (similarity {sim:.2f}): BibTeX='{fields['title'][:50]}...' vs DOI='{doi_title[:50]}...'")
                    result['status'] = 'suspicious'
                    result['suspicion_reasons'].append(f"DOI title similarity only {sim:.2f}")
            
            # Check year
            if 'year' in fields and 'published' in doi_data:
                bib_year = fields['year']
                doi_year = str(doi_data['published'].get('date-parts', [[None]])[0][0])
                
                if bib_year != doi_year:
                    result['warnings'].append(f"Year mismatch: BibTeX={bib_year} vs DOI={doi_year}")
                    if result['status'] == 'valid':
                        result['status'] = 'warning'
        
        else:
            # No DOI - try OpenAlex search
            title = fields.get('title', '')
            author = fields.get('author', '')
            
            if title:
                found, openalex_data = self.search_openalex(title, author)

                if found:
                    oa_title = openalex_data.get('title', '')
                    sim = self._jaccard_words(title, oa_title) if oa_title else 0.0

                    if sim >= 0.5:
                        # Strong title match — treat as genuine validation
                        verified_metadata = openalex_data
                        if result['status'] in ('invalid', 'warning'):
                            result['status'] = 'warning'
                        # keep 'valid' as-is
                    elif sim >= 0.3:
                        # Weak match — not enough to validate, just note it
                        verified_metadata = openalex_data
                        result['warnings'].append(f"Weak OpenAlex title match (similarity {sim:.2f})")
                        if result['status'] == 'valid':
                            result['status'] = 'warning'
                    else:
                        # OpenAlex returned something unrelated
                        result['warnings'].append(f"OpenAlex top result doesn't match (similarity {sim:.2f})")
                        result['status'] = 'warning'
                else:
                    result['warnings'].append('No DOI found and not in OpenAlex')
                    # Stay at 'warning' — absence from databases is not evidence
                    # of fabrication.  Many real papers (preprints, old papers,
                    # non-English, grey literature) aren't indexed.
                    # Escalation to 'suspicious' happens later only if additional
                    # heuristic red flags accumulate.
                    if result['status'] == 'valid':
                        result['status'] = 'warning'
            else:
                # Only warn if metadata is too sparse to perform any meaningful lookup.
                has_author_or_venue = bool(fields.get('author') or fields.get('journal') or fields.get('booktitle'))
                if not has_author_or_venue:
                    result['warnings'].append('Insufficient metadata to validate (missing DOI/title/author/venue)')
                    result['status'] = 'warning'
        
        # Scholar Agent fallback: try Semantic Scholar if still unresolved
        # (We only reach here when DOI path didn't return early, so DOI is unconfirmed)
        if not verified_metadata or result['status'] not in ('valid',):
            title = fields.get('title', '')
            if title:
                ss_found, ss_data = self.search_semantic_scholar(title)
                if ss_found and ss_data.get('title'):
                    sim = self._jaccard_words(title, ss_data['title'])
                    if sim >= 0.5:
                        if not verified_metadata:
                            verified_metadata = ss_data
                        
                        # Check author/year cross-validation before promoting to valid
                        author_match = False
                        year_match = False
                        
                        if fields.get('author') and ss_data.get('authors'):
                            # BibTeX: "Last, First and Last2, First2" → extract last names
                            bib_lastnames = re.findall(r'([A-Z][a-z]+)', fields['author'])
                            # Semantic Scholar: "Full Name, Full Name" comma-separated string
                            ss_authors = [a.strip() for a in ss_data['authors'].split(',')]
                            
                            # Check if any last name overlaps
                            for bib_ln in bib_lastnames:
                                for ss_auth in ss_authors:
                                    if bib_ln.lower() in ss_auth.lower():
                                        author_match = True
                                        break
                                if author_match:
                                    break
                        
                        if fields.get('year') and ss_data.get('year'):
                            year_match = str(fields['year']) == str(ss_data['year'])
                        
                        # Only promote to valid if we have author OR year confirmation
                        if result['status'] in ('warning', 'suspicious', 'invalid'):
                            if author_match or year_match:
                                result['status'] = 'valid'
                            else:
                                result['warnings'].append('Semantic Scholar title match but no author/year confirmation')
                                # Keep existing suspicious/warning status
                    
                    elif sim >= 0.3 and not verified_metadata:
                        verified_metadata = ss_data
                        result['warnings'].append(f"Weak Semantic Scholar match (similarity {sim:.2f})")

        # ENHANCEMENT: Calculate similarity score if we have verified metadata
        if HAS_ENHANCEMENTS and verified_metadata:
            has_rich_metadata = bool(fields.get('title')) and bool(fields.get('author'))
            title_word_count = len(re.findall(r'\w+', fields.get('title', '')))
            if has_rich_metadata and not is_arxiv_doi and title_word_count >= 4:
                similarity = EnhancedValidator.calculate_metadata_similarity(fields, verified_metadata)
                if similarity < 0.30:  # More conservative threshold to reduce false positives.
                    result['warnings'].append(f"Low metadata similarity score: {similarity:.2f}")
                    result['suspicion_reasons'].append(f"Metadata similarity only {similarity:.2f}")
                    if result['status'] == 'valid':
                        result['status'] = 'warning'
        
        # AI analysis for suspicious/invalid citations
        if self.use_ai and result['status'] in ['suspicious', 'invalid', 'warning']:
            ai_result = self.analyze_with_ai(entry, verified_metadata, result['suspicion_reasons'])
            result['ai_analysis'] = ai_result
            
            # Allow AI to escalate status if high confidence
            if ai_result and isinstance(ai_result, dict):
                is_suspicious = ai_result.get('is_suspicious', False)
                confidence = ai_result.get('confidence', 0)
                
                if is_suspicious and confidence >= 70:
                    if result['status'] == 'warning':
                        result['status'] = 'suspicious'
                        result['suspicion_reasons'].append(f"AI flagged as suspicious (confidence: {confidence}%)")
                    elif result['status'] == 'suspicious' and confidence >= 85:
                        result['status'] = 'invalid'
                        result['issues'].append(f"AI high-confidence fabrication detection (confidence: {confidence}%)")
        
        return result
    
    def validate_file(self, filepath: Path) -> Dict:
        """Validate all citations in a BibTeX file."""
        print(f"\nValidating citations in: {filepath}")
        print("=" * 70)
        
        entries = self.parse_bibtex(filepath)
        print(f"Found {len(entries)} citations to check\n")
        
        results = {
            'file': str(filepath),
            'total': len(entries),
            'valid': 0,
            'warnings': 0,
            'suspicious': 0,
            'invalid': 0,
            'details': []
        }
        
        for i, entry in enumerate(entries, 1):
            if self.verbose:
                print(f"Checking [{i}/{len(entries)}]: {entry['key']}")
            
            check_result = self.check_citation(entry)
            results['details'].append(check_result)
            
            # Update counts
            if check_result['status'] == 'valid':
                results['valid'] += 1
            elif check_result['status'] == 'warning':
                results['warnings'] += 1
            elif check_result['status'] == 'suspicious':
                results['suspicious'] += 1
            elif check_result['status'] == 'invalid':
                results['invalid'] += 1
        
        return results
    
    def print_report(self, results: Dict):
        """Print a human-readable report."""
        print("\n" + "=" * 70)
        print("CITATION VALIDATION REPORT")
        print("=" * 70)
        print(f"File: {results['file']}")
        print(f"Total citations: {results['total']}")
        print(f"  ✓ Valid: {results['valid']}")
        print(f"  ⚠ Warnings: {results['warnings']}")
        print(f"  ⚠⚠ Suspicious: {results['suspicious']}")
        print(f"  ✗ Invalid: {results['invalid']}")
        
        # Show details for problematic citations
        problematic = [d for d in results['details'] if d['status'] != 'valid']
        
        if problematic:
            print("\n" + "-" * 70)
            print("ISSUES FOUND:")
            print("-" * 70)
            
            for detail in problematic:
                print(f"\n[{detail['status'].upper()}] {detail['key']}")
                for issue in detail['issues']:
                    print(f"  ✗ {issue}")
                for warning in detail['warnings']:
                    print(f"  ⚠ {warning}")
                
                # Show enhanced suspicion reasons if available
                if detail.get('suspicion_reasons'):
                    print(f"  🔍 Suspicion flags:")
                    for reason in detail['suspicion_reasons']:
                        print(f"     - {reason}")
                
                # Show AI analysis if available
                if detail.get('ai_analysis'):
                    ai = detail['ai_analysis']
                    confidence = ai.get('confidence', 0)
                    is_suspicious = ai.get('is_suspicious', False)
                    reason = ai.get('reason', 'No reason provided')
                    hallucination_type = ai.get('hallucination_type', 'unknown')
                    red_flags = ai.get('red_flags', [])
                    
                    if is_suspicious:
                        print(f"  🤖 AI Analysis: LIKELY HALLUCINATED ({confidence}% confidence)")
                        if hallucination_type != 'none':
                            print(f"     Type: {hallucination_type}")
                    else:
                        print(f"  🤖 AI Analysis: Appears legitimate ({confidence}% confidence)")
                    print(f"     Reason: {reason}")
                    if red_flags:
                        print(f"     Red flags: {', '.join(red_flags)}")
        else:
            print("\n✓ No issues found! All citations appear valid.")
        
        print("\n" + "=" * 70)


def main():
    """Main entry point."""
    if len(sys.argv) < 2 or '--help' in sys.argv or '-h' in sys.argv:
        print("OJSM Citation Validator - Detect hallucinated academic references")
        print("\nUsage: python3 citation_validator.py <path_to_bib_file> [options]")
        print("\nOptions:")
        print("  --verbose, -v       Show detailed progress")
        print("  --ai                Enable AI-powered Frankenstein citation detection")
        print("  --groq-key KEY      Groq API key (or set GROQ_API_KEY env var)")
        print("\nExamples:")
        print("  Basic validation:")
        print("    python3 citation_validator.py bibliography.bib")
        print("\n  With OpenAlex fallback for non-DOI citations:")
        print("    python3 citation_validator.py bibliography.bib --verbose")
        print("\n  With AI analysis (requires Groq API key):")
        print("    export GROQ_API_KEY='your-key-here'")
        print("    python3 citation_validator.py bibliography.bib --ai")
        print("\nGet free Groq API key at: https://console.groq.com/")
        sys.exit(0)
    
    # Parse arguments
    bib_file = Path(sys.argv[1])
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    use_ai = '--ai' in sys.argv
    
    # Get Groq API key if provided
    groq_key = None
    for i, arg in enumerate(sys.argv):
        if arg == '--groq-key' and i + 1 < len(sys.argv):
            groq_key = sys.argv[i + 1]
            break
    
    if not bib_file.exists():
        print(f"Error: File not found: {bib_file}")
        sys.exit(1)
    
    validator = CitationValidator(verbose=verbose, use_ai=use_ai, groq_api_key=groq_key)
    results = validator.validate_file(bib_file)
    validator.print_report(results)
    
    # Exit with error code if invalid citations found
    if results['invalid'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
