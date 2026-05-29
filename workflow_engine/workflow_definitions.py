"""Load and validate workflow definitions (YAML/JSON)."""
import yaml
import json
from typing import Dict, Any


def load_workflow_from_yaml(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    # basic validation
    if 'workflow' not in data:
        raise ValueError('workflow key missing')
    wf = data['workflow']
    if 'name' not in wf or 'steps' not in wf:
        raise ValueError('workflow.name or workflow.steps missing')
    return wf


def workflow_to_json(wf: Dict[str, Any]) -> str:
    return json.dumps(wf, ensure_ascii=False, indent=2)
