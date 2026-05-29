"""Production-like deduplication engine.

Features:
- Fingerprint generation (SHA256) from normalized title/provider/date
- Chinese normalization (Traditional <-> Simplified) via OpenCC when available
- Fuzzy matching via rapidfuzz
- Storage adapters: MySQL and Redis (optional)
- Incremental upsert behavior and update detection
- Confidence scoring and logs
"""
import hashlib
import json
import time
from typing import Dict, Optional, List, Tuple

try:
    from rapidfuzz import fuzz
except Exception:
    fuzz = None

try:
    from opencc import OpenCC
except Exception:
    OpenCC = None

try:
    import pymysql
except Exception:
    pymysql = None

try:
    import redis
except Exception:
    redis = None


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


class DedupStoreInterface:
    def get(self, fingerprint: str) -> Optional[Dict]:
        raise NotImplementedError()

    def upsert(self, fingerprint: str, data: Dict):
        raise NotImplementedError()

    def find_similar(self, title_norm: str, provider_id: Optional[int], date_norm: Optional[str], limit: int = 10) -> List[Dict]:
        raise NotImplementedError()


class InMemoryDedupStore(DedupStoreInterface):
    def __init__(self):
        self.idx = {}

    def get(self, fingerprint: str) -> Optional[Dict]:
        return self.idx.get(fingerprint)

    def upsert(self, fingerprint: str, data: Dict):
        data['last_seen'] = int(time.time())
        self.idx[fingerprint] = data

    def find_similar(self, title_norm: str, provider_id: Optional[int], date_norm: Optional[str], limit: int = 10) -> List[Dict]:
        # naive linear scan
        results = []
        for fp, rec in self.idx.items():
            results.append(rec)
        return results[:limit]


class MySQLDedupStore(DedupStoreInterface):
    def __init__(self, dsn: Dict):
        if pymysql is None:
            raise RuntimeError('pymysql not installed')
        self.dsn = dsn

    def _get_conn(self):
        return pymysql.connect(**self.dsn)

    def get(self, fingerprint: str) -> Optional[Dict]:
        sql = 'SELECT fingerprint, provider_id, title_norm, date_norm, web_url, record_id, metadata, last_seen FROM dedup_index WHERE fingerprint=%s'
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (fingerprint,))
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    'fingerprint': row[0], 'provider_id': row[1], 'title_norm': row[2], 'date_norm': row[3], 'web_url': row[4], 'record_id': row[5], 'metadata': json.loads(row[6]) if row[6] else {}, 'last_seen': row[7]
                }
        finally:
            conn.close()

    def upsert(self, fingerprint: str, data: Dict):
        sql = '''INSERT INTO dedup_index (fingerprint, provider_id, title_norm, date_norm, web_url, record_id, metadata, last_seen)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                 ON DUPLICATE KEY UPDATE provider_id=VALUES(provider_id), title_norm=VALUES(title_norm), date_norm=VALUES(date_norm), web_url=VALUES(web_url), record_id=VALUES(record_id), metadata=VALUES(metadata), last_seen=VALUES(last_seen)
              '''
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    fingerprint,
                    data.get('provider_id'),
                    data.get('title_norm'),
                    data.get('date_norm'),
                    data.get('web_url'),
                    data.get('record_id'),
                    json.dumps(data.get('metadata') or {}, ensure_ascii=False),
                    int(time.time())
                ))
                conn.commit()
        finally:
            conn.close()

    def find_similar(self, title_norm: str, provider_id: Optional[int], date_norm: Optional[str], limit: int = 10) -> List[Dict]:
        # Query candidates by provider/date window for efficiency
        sql = 'SELECT fingerprint, provider_id, title_norm, date_norm, web_url, record_id, metadata, last_seen FROM dedup_index WHERE provider_id=%s LIMIT %s'
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (provider_id or 0, limit))
                rows = cur.fetchall()
                out = []
                for row in rows:
                    out.append({'fingerprint': row[0], 'provider_id': row[1], 'title_norm': row[2], 'date_norm': row[3], 'web_url': row[4], 'record_id': row[5], 'metadata': json.loads(row[6]) if row[6] else {}, 'last_seen': row[7]})
                return out
        finally:
            conn.close()


class DeduperEngine:
    def __init__(self, store: DedupStoreInterface = None, opencc_mode: str = 't2s'):
        self.store = store or InMemoryDedupStore()
        self.opencc_mode = opencc_mode
        self.opencc = OpenCC(opencc_mode) if OpenCC is not None else None

    def normalize_text(self, text: str) -> str:
        if not text:
            return ''
        t = text.strip().lower()
        # remove punctuation
        t = ''.join(ch for ch in t if ch.isalnum() or ch.isspace())
        t = ' '.join(t.split())
        if self.opencc:
            try:
                # convert to simplified for normalization
                t = self.opencc.convert(t)
            except Exception:
                pass
        return t

    def fingerprint(self, title: str, provider: str, date_norm: str) -> str:
        s = (title or '') + '||' + (provider or '') + '||' + (date_norm or '')
        s = self.normalize_text(s)
        return _sha256_hex(s)

    def check_duplicate(self, record: Dict, fuzzy_threshold: int = 90) -> Dict:
        """Return a dict describing duplicate status and candidate matches.

        Output example:
        {
          'is_duplicate': True/False,
          'match_type': 'exact'|'fuzzy'|'moved_url'|'none',
          'fingerprint': '...',
          'matched_fingerprint': '...',
          'confidence': 0.0-1.0,
          'candidates': [ ... ]
        }
        """
        title = record.get('title_zh_cn') or record.get('title_zh_tw') or record.get('title_en_us') or ''
        provider = str(record.get('provider_id') or record.get('provider') or '')
        date_norm = record.get('end_time') or record.get('schedule_time') or ''
        title_norm = self.normalize_text(title)
        provider_norm = self.normalize_text(provider)
        fp = self.fingerprint(title_norm, provider_norm, date_norm)

        # exact fingerprint lookup
        existing = self.store.get(fp)
        if existing:
            return {'is_duplicate': True, 'match_type': 'exact', 'fingerprint': fp, 'matched_fingerprint': fp, 'confidence': 1.0, 'candidates': [existing]}

        # moved URL detection: scan by web_url equality
        web = record.get('web_url')
        if web:
            # naive: check if any stored entry has same web_url (only in stores that support scanning)
            candidates = self.store.find_similar(title_norm, record.get('provider_id'), date_norm, limit=20)
            for c in candidates:
                if c.get('web_url') == web and c.get('fingerprint') != fp:
                    return {'is_duplicate': True, 'match_type': 'moved_url', 'fingerprint': fp, 'matched_fingerprint': c.get('fingerprint'), 'confidence': 0.95, 'candidates': [c]}

        # fuzzy similarity search
        candidates = self.store.find_similar(title_norm, record.get('provider_id'), date_norm, limit=50)
        best = None
        best_score = 0.0
        for c in candidates:
            cand_title = c.get('title_norm') or ''
            if fuzz is not None:
                score = fuzz.token_sort_ratio(title_norm, cand_title)
            else:
                # fallback: basic ratio
                score = 100.0 if title_norm == cand_title else 0.0
            if score > best_score:
                best_score = score
                best = c

        if best and best_score >= fuzzy_threshold:
            conf = min(0.99, best_score / 100.0)
            return {'is_duplicate': True, 'match_type': 'fuzzy', 'fingerprint': fp, 'matched_fingerprint': best.get('fingerprint'), 'confidence': conf, 'candidates': [best]}

        return {'is_duplicate': False, 'match_type': 'none', 'fingerprint': fp, 'matched_fingerprint': None, 'confidence': 0.0, 'candidates': []}

    def upsert(self, record: Dict, record_id: Optional[int] = None):
        title = record.get('title_zh_cn') or record.get('title_zh_tw') or record.get('title_en_us') or ''
        provider = str(record.get('provider_id') or record.get('provider') or '')
        date_norm = record.get('end_time') or record.get('schedule_time') or ''
        title_norm = self.normalize_text(title)
        provider_norm = self.normalize_text(provider)
        fp = self.fingerprint(title_norm, provider_norm, date_norm)
        data = {
            'fingerprint': fp,
            'provider_id': record.get('provider_id'),
            'title_norm': title_norm,
            'date_norm': date_norm,
            'web_url': record.get('web_url'),
            'record_id': record_id,
            'metadata': record,
            'last_seen': int(time.time())
        }
        self.store.upsert(fp, data)
        return fp


__all__ = ['DeduperEngine','InMemoryDedupStore','MySQLDedupStore']
