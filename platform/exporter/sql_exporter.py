from typing import Dict, Tuple
import json

def generate_insert(table: str, record: Dict) -> Tuple[str, Dict]:
    cols = []
    vals = {}
    for k, v in record.items():
        cols.append(k)
        vals[k] = v
    cols_sql = ', '.join(f'`{c}`' for c in cols)
    vals_sql = ', '.join('%(' + c + ')s' for c in cols)
    sql = f"INSERT INTO `{table}` ({cols_sql}) VALUES ({vals_sql});"
    return sql, vals

def generate_upsert(table: str, record: Dict, unique_keys: list):
    sql, params = generate_insert(table, record)
    updates = ', '.join(f"`{k}`=VALUES(`{k}`)" for k in record.keys() if k not in unique_keys)
    upsert = sql[:-1] + f" ON DUPLICATE KEY UPDATE {updates};"
    return upsert, params
