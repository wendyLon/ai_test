"""LLM client abstraction supporting OpenAI, Claude and local models.

This module provides `LLMClient` with a minimal implementation that tries to
use OpenAI (if `OPENAI_API_KEY` is configured) and falls back to a local
mock that uses heuristic extraction when no real model is available.

Implementors can subclass `LLMClient` to add real Claude or local model integrations.
"""
import os
import json
from typing import Dict

try:
    import openai
except Exception:
    openai = None


class LLMClient:
    def __init__(self, provider: str = 'auto'):
        self.provider = provider
        self._has_openai = (openai is not None) and bool(os.environ.get('OPENAI_API_KEY'))
        if self._has_openai:
            openai.api_key = os.environ.get('OPENAI_API_KEY')

    def extract_structured(self, prompt: str) -> Dict:
        """Return structured JSON like {'fields': {...}, 'confidence': {field:score}}.

        If a real LLM isn't available, return a lightweight heuristic mapping.
        """
        # Use OpenAI if available
        if self._has_openai:
            try:
                resp = openai.ChatCompletion.create(
                    model=os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
                    messages=[{'role':'user','content':prompt}],
                    temperature=0.0,
                    max_tokens=800
                )
                txt = resp['choices'][0]['message']['content']
                # Expect model to return JSON — try to parse
                try:
                    data = json.loads(txt)
                    return data
                except Exception:
                    # fallback: wrap text
                    return {'fields': {'llm_text': txt}, 'confidence': {'llm_text': 0.4}}
            except Exception as e:
                return {'fields': {}, 'confidence': {}, 'error': str(e)}

        # Fallback mock extractor: attempt to parse 'title' and first sentence
        # Not a replacement for LLM — just keeps pipeline runnable.
        return self._mock_extract(prompt)

    def classify(self, text: str, task: str = 'sen_relevance') -> Dict:
        """Return classification scores or tags. Fallback heuristic implemented."""
        if self._has_openai:
            # For brevity, use the same ChatCompletion call with a classification prompt
            try:
                prompt = f"Classify the following text for task={task}. Return JSON.\nText:\n{text[:4000]}"
                resp = openai.ChatCompletion.create(
                    model=os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
                    messages=[{'role':'user','content':prompt}],
                    temperature=0.0,
                    max_tokens=300
                )
                txt = resp['choices'][0]['message']['content']
                try:
                    return json.loads(txt)
                except Exception:
                    return {'raw': txt}
            except Exception as e:
                return {'error': str(e)}

        return self._mock_classify(text)

    # ----------------- Mock helpers -----------------
    def _mock_extract(self, prompt: str) -> Dict:
        # crude heuristics: extract first line as title, look for http links
        fields = {}
        conf = {}
        # title guess
        first_line = prompt.split('\n')[0][:200]
        fields['title_zh_cn'] = first_line
        conf['title_zh_cn'] = 0.3
        # links
        import re
        m = re.search(r'(https?://[^\s]+)', prompt)
        if m:
            fields['signup_url'] = m.group(1)
            conf['signup_url'] = 0.4
        return {'fields': fields, 'confidence': conf}

    def _mock_classify(self, text: str) -> Dict:
        lower = text.lower()
        score = 0.0
        for kw in ['autism','adhd','dyslexia','特殊需要','自閉症','讀寫']:
            if kw in lower:
                score += 1.0
        return {'sen_related_score': min(1.0, score/3.0)}


__all__ = ['LLMClient']
