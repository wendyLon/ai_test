# Plugin System

Plugins live under `platform/agent_plugins/<provider>/`.
Each plugin is a Python package that may override hooks for specific agents.

Interface:
- `before_task(task)`
- `after_task(task, result)`
- `on_error(task, exc)`

Loader: `platform/agent_plugins/plugin_loader.py` discovers and imports plugins.

Use cases:
- provider-specific DOM normalization
- custom date parsers
- alternative PDF endpoints

Example structure:
```
platform/agent_plugins/hongchi/__init__.py
platform/agent_plugins/hongchi/hooks.py
```
