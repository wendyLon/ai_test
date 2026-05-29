import importlib
import os
from typing import List

class PluginLoader:
    def __init__(self, plugins_dir='platform/agent_plugins'):
        self.plugins_dir = plugins_dir

    def discover_plugins(self) -> List[str]:
        names = []
        if not os.path.exists(self.plugins_dir):
            return names
        for entry in os.listdir(self.plugins_dir):
            p = os.path.join(self.plugins_dir, entry)
            if os.path.isdir(p) and os.path.exists(os.path.join(p, '__init__.py')):
                names.append(entry)
        return names

    def load_plugin(self, name: str):
        module_path = self.plugins_dir.replace('/', '.') + '.' + name
        try:
            return importlib.import_module(module_path)
        except Exception:
            return None
