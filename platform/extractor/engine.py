import json
import re
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as dateparser

from platform.normalizer.normalizer import Normalizer
from platform.extractor.pdf_ocr import PDFOCRProcessor


class AdaptiveExtractor:
    """AI-assisted adaptive extraction engine.

    Architecture:
    - DOM block segmentation via repeated-structure detection (cards, lists, tables)
    - Candidate scoring by presence of dates/fees/locations/signup links
    - Multi-stage extraction: JSON-LD/meta -> heuristics -> LLM
    - Merge results with per-field confidence
    - Output normalized JSON matching `schemas/event_schema.json`

    Extensible: pass an `llm_client` that implements `extract_structured(prompt)` and
    `classify(text, task)`.
    """

    SEN_KEYWORDS = {
        'en': ['autism', 'adhd', 'dyslexia', 'speech delay', 'intellectual disability', 'special needs', 'SEN', 'learning difficulty'],
        'zh': ['自閉症', '自閉', '過度活躍', '專注力不足', '注意力', '讀寫障礙', '語言遲緩', '特殊教育', '特殊需要']
    }

    DATE_RE = re.compile(r"(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}|\bAM\b|\bPM\b|上午|下午|[0-2]?\d[:]\d{2})", re.I)
    PRICE_RE = re.compile(r"(\$\s?\d+[\.,]?\d*|HKD|港幣|免費|免費參加|free)", re.I)

    def __init__(self, llm_client=None, normalizer: Optional[Normalizer] = None):
        self.llm = llm_client
        self.normalizer = normalizer or Normalizer()
        self.pdf_proc = PDFOCRProcessor()

    # ---------- Public pipeline ----------
    def extract_from_page(self, html: str, page_url: str, screenshot_path: Optional[str] = None) -> List[Dict]:
        """Full pipeline:

        HTML -> block segmentation -> candidate extraction -> LLM mapping -> normalization -> dedupe-ready JSON
        """
        logs: List[str] = []
        soup = BeautifulSoup(html, 'lxml')
        results: List[Dict] = []

        # 0. Try JSON-LD / metadata extraction for explicit Event objects
        jsonld_events = self._parse_json_ld(soup)
        if jsonld_events:
            logs.append(f'Found {len(jsonld_events)} JSON-LD event(s)')

        # 0.5 Detect PDF links and image flyers -> run OCR and parse
        pdf_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.lower().endswith('.pdf') or '.pdf' in href.lower():
                pdf_links.append(href)
        for pl in pdf_links:
            try:
                pdf_path = self.pdf_proc.download(pl)
                if pdf_path:
                    pdf_out = self.pdf_proc.process_pdf(pdf_path)
                    text_combined = (pdf_out.get('text','') or '') + '\n' + (pdf_out.get('ocr_text','') or '')
                    fields, confs = self.pdf_proc.parse_text_to_fields(text_combined, source_url=pl)
                    merged, confidences = self._merge_fields(fields, confs, {}, {})
                    merged['raw_html'] = ''
                    merged['screenshot_path'] = ''
                    merged['web_url'] = pl
                    merged['pdf_path'] = str(pdf_path)
                    normalized = self._normalize_record(merged)
                    results = results if 'results' in locals() else []
                    results.insert(0, {'raw': {'pdf': pdf_out}, 'merged': merged, 'normalized': normalized, 'confidence': confidences, 'logs': logs.copy()})
            except Exception as e:
                logs.append(f'PDF processing failed for {pl}: {e}')

        # Image flyers: detect large images or alt/class containing flyer/poster
        img_candidates = []
        for img in soup.find_all('img', src=True):
            alt = (img.get('alt') or '').lower()
            cls = ' '.join(img.get('class') or []).lower()
            src = img['src']
            if any(k in alt for k in ['flyer','poster','海報','傳單','宣傳']) or any(k in cls for k in ['flyer','poster']):
                img_candidates.append(src)
        for ic in img_candidates:
            try:
                ocr_text, ocr_conf = self.pdf_proc.ocr_image_from_url(ic)
                fields, confs = self.pdf_proc.parse_text_to_fields(ocr_text, source_url=ic)
                merged, confidences = self._merge_fields(fields, confs, {}, {})
                merged['web_url'] = ic
                merged['screenshot_path'] = ''
                normalized = self._normalize_record(merged)
                results = results if 'results' in locals() else []
                results.insert(0, {'raw': {'image_ocr': ocr_text}, 'merged': merged, 'normalized': normalized, 'confidence': {'ocr_conf': ocr_conf, **confidences}, 'logs': logs.copy()})
            except Exception as e:
                logs.append(f'Image OCR failed for {ic}: {e}')

        # 1. Block segmentation
        blocks = self._segment_blocks(soup)
        logs.append(f'Segmented into {len(blocks)} candidate block(s)')

        # 2. Score & filter candidates
        scored: List[Tuple[float, BeautifulSoup]] = []
        for b in blocks:
            score = self._score_block(b)
            scored.append((score, b))
        scored.sort(key=lambda x: x[0], reverse=True)

        # results already initialized above

        # 3. Extract from best candidates (limit to top N)
        for rank, (score, block) in enumerate(scored[:20]):
            block_html = str(block)
            heur_fields, heur_conf = self._heuristic_extract(block)
            llm_fields, llm_conf = {}, {}
            if self.llm:
                try:
                    prompt = self._build_prompt(block_html, page_url)
                    llm_out = self.llm.extract_structured(prompt)
                    if isinstance(llm_out, dict):
                        llm_fields = llm_out.get('fields', llm_out)
                        llm_conf = llm_out.get('confidence', {})
                except Exception as e:
                    logs.append(f'LLM extraction failed: {e}')

            merged, confidences = self._merge_fields(heur_fields, heur_conf, llm_fields, llm_conf)
            merged.setdefault('web_url', page_url)
            merged.setdefault('raw_html', block_html)
            merged.setdefault('screenshot_path', screenshot_path)

            # SEN relevance
            sen_related, sen_scores = self._classify_sen(merged)
            merged['sen_related'] = sen_related
            merged['sen_scores'] = sen_scores

            # Expiry detection
            expired, inferred_end = self._detect_expiry(merged)
            merged['expired'] = expired
            if inferred_end:
                merged['end_time'] = inferred_end

            # Normalization
            normalized = self._normalize_record(merged)

            results.append({
                'raw': {'heuristic': heur_fields, 'llm': llm_fields},
                'merged': merged,
                'normalized': normalized,
                'confidence': confidences,
                'logs': logs.copy()
            })

        # If JSON-LD events exist but no candidates, convert JSON-LD to results
        if not results and jsonld_events:
            for ev in jsonld_events:
                merged = ev
                merged.setdefault('web_url', page_url)
                normalized = self._normalize_record(merged)
                results.append({'raw': {'jsonld': ev}, 'merged': merged, 'normalized': normalized, 'confidence': {}, 'logs': logs.copy()})

        return results

    # ---------- Segmentation ----------
    def _segment_blocks(self, soup: BeautifulSoup) -> List[BeautifulSoup]:
        """Detect repeated structures (cards), tables, lists and return candidate elements."""
        blocks = []

        # Tables -> each row as candidate
        for table in soup.find_all('table'):
            for tr in table.find_all('tr'):
                blocks.append(tr)

        # Lists -> each li
        for li in soup.find_all('li'):
            blocks.append(li)

        # Repeated div/card detection by class signature
        sig_count = {}
        for div in soup.find_all(['div', 'section', 'article']):
            cls = ' '.join(sorted(div.get('class') or []))
            sig = (div.name, cls)
            sig_count.setdefault(sig, []).append(div)

        for sig, elems in sig_count.items():
            if len(elems) >= 3:
                blocks.extend(elems)

        # If nothing found, fallback to large <div> or article blocks
        if not blocks:
            for tag in soup.find_all(['article', 'div']):
                if len(tag.get_text(strip=True)) > 200:
                    blocks.append(tag)

        # Unique-ify while preserving order
        seen = set()
        uniq = []
        for b in blocks:
            key = id(b)
            if key not in seen:
                uniq.append(b)
                seen.add(key)
        return uniq

    # ---------- Scoring ----------
    def _score_block(self, block: BeautifulSoup) -> float:
        text = block.get_text(' ', strip=True)
        score = 0.0
        if self.DATE_RE.search(text):
            score += 2.0
        if self.PRICE_RE.search(text):
            score += 1.0
        # signup link
        for a in block.find_all('a', href=True):
            if re.search(r'register|signup|apply|报名|報名|sign[-_ ]?up', a['href'], re.I):
                score += 1.5
                break
        # title headings
        if block.find(['h1', 'h2', 'h3', 'h4']):
            score += 0.5
        # length
        ln = len(text)
        if 100 < ln < 5000:
            score += 0.5
        return score

    # ---------- Heuristic extraction ----------
    def _heuristic_extract(self, block: BeautifulSoup) -> Tuple[Dict, Dict]:
        text = block.get_text(' ', strip=True)
        fields: Dict = {}
        conf: Dict = {}

        # Title heuristics: heading or strong/bold or first sentence
        title = None
        for h in ['h1','h2','h3','h4']:
            el = block.find(h)
            if el and el.get_text(strip=True):
                title = el.get_text(strip=True)
                conf['title'] = 0.8
                break
        if not title:
            strong = block.find(['strong','b'])
            if strong and strong.get_text(strip=True):
                title = strong.get_text(strip=True)
                conf['title'] = 0.6
        if not title:
            title = text.split('\n')[0][:200]
            conf['title'] = 0.4
        fields['title_zh_cn'] = title

        # Dates
        dt_match = self.DATE_RE.search(text)
        if dt_match:
            try:
                parsed = dateparser.parse(dt_match.group(0), fuzzy=True)
                fields['schedule_time'] = dt_match.group(0)
                fields['end_time'] = parsed.isoformat()
                conf['schedule_time'] = 0.6
                conf['end_time'] = 0.6
            except Exception:
                fields['schedule_time'] = dt_match.group(0)
                conf['schedule_time'] = 0.4

        # Fees
        fee_match = self.PRICE_RE.search(text)
        if fee_match:
            fields['fee'] = fee_match.group(0)
            fee_norm = self.normalizer.normalize_fee(fields['fee'])
            fields.update(fee_norm)
            conf['fee'] = 0.6

        # Signup link
        signup = None
        for a in block.find_all('a', href=True):
            href = a['href']
            if re.search(r'register|signup|apply|报名|報名|sign[-_ ]?up', href, re.I):
                signup = href
                conf['signup_url'] = 0.8
                break
        fields['signup_url'] = signup

        # Location
        loc = None
        for kw in ['地點','地點：','地址','venue','location','地点']:
            if kw in text:
                # crude grab: take substring around keyword
                idx = text.find(kw)
                loc = text[idx:idx+120]
                conf['venue_name'] = 0.5
                break
        fields['venue_name'] = loc

        # Description
        fields['description_zh_cn'] = text[:5000]
        conf['description_zh_cn'] = 0.5

        return fields, conf

    # ---------- JSON-LD parser ----------
    def _parse_json_ld(self, soup: BeautifulSoup) -> List[Dict]:
        results = []
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '{}')
            except Exception:
                continue
            if isinstance(data, list):
                for item in data:
                    if item.get('@type') == 'Event' or item.get('type') == 'Event':
                        results.append(item)
            else:
                if data.get('@type') == 'Event' or data.get('type') == 'Event':
                    results.append(data)
        return results

    # ---------- LLM prompt ----------
    def _build_prompt(self, block_html: str, page_url: str) -> str:
        schema_hint = {
            'title_zh_cn': '培训/活动标题（中文）',
            'description_zh_cn': '活动完整描述（中文）',
            'summary_zh_cn': '摘要，不超过500字',
            'schedule_time': '时间文本',
            'end_time': '结束时间 ISO 格式或可解析文本',
            'fee': '费用原文',
            'fee_amount': '费用数值',
            'currency': '货币',
            'venue_name': '地点/地址',
            'signup_url': '报名链接',
            'web_url': '來源頁面 URL'
        }
        prompt = (
            "Extract event information as JSON with keys matching the following schema:\n"
            + json.dumps(schema_hint, ensure_ascii=False, indent=2)
            + "\nReturn a JSON object: { 'fields': {...}, 'confidence': {field: 0.0-1.0} }\n"
            + f"Page URL: {page_url}\n"
            + "HTML_SNIPPET_START\n"
            + (block_html[:4000])
            + "\nHTML_SNIPPET_END\n"
        )
        return prompt

    # ---------- Merge heuristic + LLM ----------
    def _merge_fields(self, heur: Dict, heur_conf: Dict, llm: Dict, llm_conf: Dict) -> Tuple[Dict, Dict]:
        merged = {}
        confidences = {}
        keys = set(list(heur.keys()) + list(llm.keys()))
        for k in keys:
            hval = heur.get(k)
            lval = llm.get(k)
            hc = heur_conf.get(k, 0.4)
            lc = llm_conf.get(k, 0.0)
            # prefer LLM when confidence higher than heuristic
            if lval is not None and lc >= hc:
                merged[k] = lval
                confidences[k] = lc
            else:
                merged[k] = hval if hval is not None else lval
                confidences[k] = max(hc, lc)
        return merged, confidences

    # ---------- SEN classification ----------
    def _classify_sen(self, record: Dict) -> Tuple[bool, Dict]:
        text = ' '.join(filter(None, [record.get('title_zh_cn',''), record.get('description_zh_cn',''), record.get('title_zh_tw',''), record.get('description_en_us','')]))
        scores = {}
        total = 0.0
        for code, kws in self.SEN_KEYWORDS.items():
            for kw in kws:
                if kw.lower() in text.lower():
                    scores[kw] = scores.get(kw, 0) + 1
                    total += 1
        # Normalize
        for k in list(scores.keys()):
            scores[k] = min(1.0, scores[k] / 3.0)
        return (len(scores) > 0), scores

    # ---------- Expiry detection ----------
    def _detect_expiry(self, record: Dict) -> Tuple[bool, Optional[str]]:
        now = datetime.utcnow()
        end_time = record.get('end_time')
        if end_time:
            try:
                dt = dateparser.parse(end_time)
                if dt and dt < now:
                    return True, dt.isoformat()
                return False, dt.isoformat() if dt else None
            except Exception:
                return False, None
        # try schedule_time
        st = record.get('schedule_time')
        if st:
            try:
                dt = dateparser.parse(st, fuzzy=True)
                if dt and dt < now:
                    return True, dt.isoformat()
                return False, dt.isoformat() if dt else None
            except Exception:
                return False, None
        return False, None

    # ---------- Normalization ----------
    def _normalize_record(self, record: Dict) -> Dict:
        out = dict(record)
        # currency / fee amount already normalized by Normalizer when possible
        # ensure language codes/json fields exist
        for j in ['sen_codes_json', 'district_codes_json', 'age_ranges_json', 'language_codes_json']:
            if j in out and out[j] is None:
                out[j] = []
        # ensure summary
        if not out.get('summary_zh_cn') and out.get('description_zh_cn'):
            out['summary_zh_cn'] = out['description_zh_cn'][:500]
        return out

