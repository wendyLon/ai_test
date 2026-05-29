# OpenClaw Integration

Design choices for OpenClaw compatibility:

- JSON-only message passing compatible with tool-calling
- Agents expose capability descriptors via registry
- Agents implemented as isolated processes or tasks that accept messages
- `platform/agents/message.py` provides serialization helpers

Future work:
- Implement OpenClaw adapters to submit tasks as actions to the MCP server
- Provide authentication and tool manifests
