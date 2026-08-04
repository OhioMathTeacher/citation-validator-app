#!/usr/bin/env python3
"""
Citation Validator Web Application
Simple Flask app for detecting hallucinated citations via web interface
"""

import os
import json
import tempfile
import requests
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_file, abort
from flask_cors import CORS
from citation_validator import CitationValidator, __version__ as APP_VERSION

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

REPO_ROOT = Path(__file__).resolve().parent.parent

# Minimal fallback — the real UI lives in citation-validator.html (repo root).
HTML_FALLBACK = '''<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:40px auto">
<h1>Citation Validator</h1>
<p>Could not find <code>citation-validator.html</code> in the repository root.</p>
<p>Make sure you are running from the repo directory:</p>
<pre>cd Ohio-Journal-of-School-Mathematics &amp;&amp; python scripts/webapp.py</pre>
</body></html>'''



@app.route('/')
def index():
    """Serve the main page."""
    page_path = REPO_ROOT / 'web' / 'citation-validator.html'
    if page_path.exists():
        return send_file(page_path)
    return Response(HTML_FALLBACK, mimetype='text/html'), 404


@app.route('/version')
def version():
    """Version of the running code, so a saved report can be traced back to it."""
    return jsonify({'version': APP_VERSION})


def _serve_repo_file(relative_path: str):
    """Serve a file from the repository while preventing path traversal."""
    target = (REPO_ROOT / relative_path).resolve()
    if not (target == REPO_ROOT or REPO_ROOT in target.parents):
        abort(404)
    if not target.exists() or not target.is_file():
        abort(404)
    return send_file(target)


@app.route('/datasets/<path:subpath>')
def serve_dataset_file(subpath):
    return _serve_repo_file(f'datasets/{subpath}')


@app.route('/test_citations/<path:subpath>')
def serve_test_citation_file(subpath):
    return _serve_repo_file(f'test_citations/{subpath}')

@app.route('/validate', methods=['POST'])
def validate():
    """Validate citations endpoint - NO AI analysis (done client-side)."""
    try:
        data = request.json
        bibtex = data.get('bibtex', '')
        
        if not bibtex:
            return jsonify({'error': 'No BibTeX content provided'}), 400
        
        # Save to unique temporary file (safe for concurrent requests)
        fd, tmp_path = tempfile.mkstemp(suffix='.bib', prefix='cv_')
        temp_file = Path(tmp_path)
        try:
            temp_file.write_text(bibtex)
            os.close(fd)

            # Validate WITHOUT AI (AI happens client-side for privacy)
            validator = CitationValidator(
                verbose=False,
                use_ai=False,  # Never use AI server-side
                groq_api_key=None
            )

            results = validator.validate_file(temp_file)
        finally:
            temp_file.unlink(missing_ok=True)
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze', methods=['POST', 'OPTIONS'])
def analyze():
    """Proxy AI analysis requests to bypass CORS restrictions."""
    import re, sys, traceback
    
    # Handle preflight requests
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.json
        provider = data.get('provider')
        api_key = data.get('apiKey')
        prompt = data.get('prompt')
        
        print(f"[ANALYZE] Provider: {provider}, Key length: {len(api_key) if api_key else 0}", flush=True)
        
        if not all([provider, api_key, prompt]):
            return jsonify({'error': 'Missing required fields: provider, apiKey, prompt'}), 400
        
        # Route to appropriate AI provider
        if provider == 'anthropic':
            print("[ANALYZE] Calling Anthropic API...", flush=True)
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01'
                },
                json={
                    'model': 'claude-sonnet-4-20250514',
                    'max_tokens': 300,
                    'messages': [{'role': 'user', 'content': prompt}]
                },
                timeout=30
            )
            print(f"[ANALYZE] Claude status: {response.status_code}", flush=True)
            
            if not response.ok:
                print(f"[ANALYZE] Claude error: {response.text[:500]}", flush=True)
                return jsonify({'error': f'Anthropic API error: {response.text}'}), response.status_code
            
            result = response.json()
            content = ''.join(block.get('text', '') for block in result.get('content', []))
            print(f"[ANALYZE] Claude content: {content[:500]}", flush=True)
            
            # Extract token usage
            usage = result.get('usage', {})
            tokens = {
                'input_tokens': usage.get('input_tokens', 0),
                'output_tokens': usage.get('output_tokens', 0),
                'total_tokens': usage.get('input_tokens', 0) + usage.get('output_tokens', 0),
            }
            stop_reason = result.get('stop_reason', 'unknown')
            
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                parsed['_metadata'] = {
                    'provider': 'anthropic',
                    'model': 'claude-sonnet-4-20250514',
                    'finish_reason': stop_reason,
                    'tokens': tokens
                }
                return jsonify(parsed)
            return jsonify({'error': 'No JSON in Claude response', 'raw': content}), 500
        
        elif provider == 'gemini':
            url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}'
            response = requests.post(
                url,
                headers={'Content-Type': 'application/json'},
                json={
                    'contents': [{'parts': [{'text': prompt}]}],
                    'generationConfig': {
                        'maxOutputTokens': 2048,
                        'temperature': 0.1,
                        'responseMimeType': 'application/json',
                        'thinkingConfig': {'thinkingBudget': 0}
                    }
                },
                timeout=60
            )
            print(f"[ANALYZE] Gemini status: {response.status_code}", flush=True)
            
            if not response.ok:
                print(f"[ANALYZE] Gemini error: {response.text[:500]}", flush=True)
                return jsonify({'error': f'Gemini API error: {response.text}'}), response.status_code
            
            result = response.json()
            candidates = result.get('candidates', [])
            finish_reason = candidates[0].get('finishReason', 'unknown') if candidates else 'none'
            content = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '') if candidates else ''
            print(f"[ANALYZE] Gemini finishReason: {finish_reason}", flush=True)
            print(f"[ANALYZE] Gemini content: {content[:500]}", flush=True)
            
            # Extract token usage
            usage_meta = result.get('usageMetadata', {})
            tokens = {
                'input_tokens': usage_meta.get('promptTokenCount', 0),
                'output_tokens': usage_meta.get('candidatesTokenCount', 0),
                'total_tokens': usage_meta.get('totalTokenCount', 0),
            }
            print(f"[ANALYZE] Gemini tokens: {tokens}", flush=True)
            
            # Strip markdown code fences if present (```json ... ```)
            content = re.sub(r'^```(?:json)?\s*', '', content.strip())
            content = re.sub(r'\s*```$', '', content.strip())
            
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                parsed['_metadata'] = {
                    'provider': 'gemini',
                    'model': 'gemini-2.5-flash',
                    'finish_reason': finish_reason,
                    'tokens': tokens
                }
                return jsonify(parsed)
            return jsonify({'error': 'No JSON found in Gemini response', 'raw': content[:300]}), 500
        
        elif provider == 'groq':
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'llama-3.3-70b-versatile',
                    'messages': [
                        {'role': 'system', 'content': 'You are an expert at detecting fabricated academic citations. Respond only with valid JSON.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.1,
                    'max_tokens': 300
                },
                timeout=30
            )
            if not response.ok:
                return jsonify({'error': f'Groq API error: {response.text}'}), response.status_code
            
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            finish_reason = result.get('choices', [{}])[0].get('finish_reason', 'unknown')
            usage = result.get('usage', {})
            tokens = {
                'input_tokens': usage.get('prompt_tokens', 0),
                'output_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0),
            }
            
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                parsed['_metadata'] = {
                    'provider': 'groq',
                    'model': 'llama-3.3-70b-versatile',
                    'finish_reason': finish_reason,
                    'tokens': tokens
                }
                return jsonify(parsed)
            return jsonify({'error': 'No JSON found in response'}), 500
        
        elif provider == 'openai':
            # Routed through OpenRouter (OpenAI-compatible API).
            # OPENAI_API_KEY holds an OpenRouter key (sk-or-...).
            response = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'openai/gpt-4o',
                    'messages': [
                        {'role': 'system', 'content': 'You are an expert at detecting fabricated academic citations. Respond only with valid JSON.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.1,
                    'max_tokens': 300
                },
                timeout=30
            )
            if not response.ok:
                return jsonify({'error': f'OpenRouter API error: {response.text}'}), response.status_code
            
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            finish_reason = result.get('choices', [{}])[0].get('finish_reason', 'unknown')
            usage = result.get('usage', {})
            tokens = {
                'input_tokens': usage.get('prompt_tokens', 0),
                'output_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0),
            }
            
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                parsed['_metadata'] = {
                    'provider': 'openai',
                    'model': 'openai/gpt-4o',
                    'finish_reason': finish_reason,
                    'tokens': tokens
                }
                return jsonify(parsed)
            return jsonify({'error': 'No JSON found in response'}), 500
        
        else:
            return jsonify({'error': f'Unsupported provider: {provider}'}), 400
    
    except requests.exceptions.Timeout:
        return jsonify({'error': 'AI API request timed out'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()

    print("\n" + "="*70)
    print("Citation Validator Web App")
    print("="*70)
    print(f"\n  Open in your browser: http://localhost:{args.port}")
    print("\n  Press Ctrl+C to stop the server")
    print("="*70 + "\n")

    app.run(debug=True, host='0.0.0.0', port=args.port)
