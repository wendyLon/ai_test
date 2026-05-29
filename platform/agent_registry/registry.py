from typing import Dict, Callable

class AgentRegistry:
    """Registry for agent classes and plugins."""
    def __init__(self):
        self._agents: Dict[str, Callable] = {}
        self._plugins: Dict[str, Callable] = {}

    def register_agent(self, name: str, agent_cls: Callable):
        self._agents[name] = agent_cls

    def get_agent(self, name: str):
        return self._agents.get(name)

    def register_plugin(self, name: str, plugin: Callable):
        self._plugins[name] = plugin

    def get_plugin(self, name: str):
        return self._plugins.get(name)

    def list_agents(self):
        return list(self._agents.keys())

    def list_plugins(self):
        return list(self._plugins.keys())

    def capabilities(self) -> Dict[str, Dict]:
        """Return basic capability descriptors for registered agents."""
        out = {}
        for name, cls in self._agents.items():
            out[name] = {
                'class': f"{cls.__module__}.{cls.__name__}",
                'doc': getattr(cls, '__doc__', '')[:200]
            }
        return out

    def hot_reload(self, module_name: str):
        import importlib
        if module_name in self._agents:
            cls = self._agents[module_name]
            importlib.reload(importlib.import_module(cls.__module__))
            return True
        return False
