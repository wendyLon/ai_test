import re
from typing import Dict
from dateutil import parser as dateparser

class Normalizer:
    def normalize_fee(self, fee_text: str) -> Dict:
        # crude fee normalization
        if not fee_text:
            return {'fee_type': 'unknown', 'fee': None, 'fee_amount': None, 'currency': 'HKD'}
        t = fee_text.lower()
        if 'free' in t or '免費' in t:
            return {'fee_type':'free', 'fee': fee_text, 'fee_amount': 0.0, 'currency':'HKD'}
        m = re.search(r"(\d+[\.,]?\d*)", fee_text)
        if m:
            amt = float(m.group(1).replace(',', ''))
            return {'fee_type':'paid', 'fee': fee_text, 'fee_amount': amt, 'currency':'HKD'}
        return {'fee_type':'unknown', 'fee': fee_text, 'fee_amount': None, 'currency':'HKD'}

    def normalize_date(self, date_text: str):
        try:
            return dateparser.parse(date_text)
        except Exception:
            return None
