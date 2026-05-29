class AgentPluginBase:
    """Base class for agent plugins (provider-specific overrides, hooks, etc)."""
    def before_task(self, task):
        pass
    def after_task(self, task, result):
        pass
    def on_error(self, task, exc):
        pass
