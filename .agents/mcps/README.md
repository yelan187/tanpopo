# Agent-Written MCPs

This directory is for MCP servers authored at runtime by Tanpopo.

Recommended layout:

```text
.agents/mcps/
  my_tool/
    server.py
    README.md
```

Register a Python MCP server with the plugin-manager MCP:

```json
{
  "name": "my_tool",
  "command": "",
  "args": [".agents/mcps/my_tool/server.py"],
  "enabled": true,
  "transport": "stdio",
  "cwd": "."
}
```

`command: ""` means Tanpopo will run the script with the current Python. MCP
subprocesses receive `PYTHONPATH` pointing at the project root, so scripts may
import installed packages and project modules when needed.

Keep generated MCPs small, focused, and restartable. Put scratch data in
`agent_workspace/` or `tmp/`; keep reusable plugin code here.
