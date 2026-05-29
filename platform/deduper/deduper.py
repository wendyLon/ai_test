import hashlib
from typing import Dict

class Deduper:
    def fingerprint(self, record: Dict) -> str:
        # Primary fingerprint: web_url
        u = record.get('web_url','')
        if u:
            return hashlib.sha256(u.encode('utf-8')).hexdigest()
        # fallback: title+schedule
        key = (record.get('title_zh_cn','') + '||' + record.get('schedule_time','')).strip()
        return hashlib.sha256(key.encode('utf-8')).hexdigest()

    def is_duplicate(self, fingerprint: str, index_set: set) -> bool:
        # index_set is an in-memory or persistent set of known fingerprints
        return fingerprint in index_set
