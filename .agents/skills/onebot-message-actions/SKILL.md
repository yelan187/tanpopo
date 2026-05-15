---
name: onebot-message-actions
description: Use this when replying to normalized OneBot QQ messages with Tanpopo's QQ MCP tools.
triggers:
  - onebot
  - qq_send_text
  - qq
  - group_id
  - message_type
  - runtime_capabilities
  - add_skill
  - add_mcp
---

# OneBot Message Actions

Use `qq_send_text` for normal QQ text replies.

For group messages:

- Set `message_type` to `metadata.message_type`.
- Set `group_id` to `metadata.group_id`.
- Do not pass `metadata.user_id` as `user_id`; it is the sender, not the group target.
- To mention the sender, pass `at_user_id=metadata.user_id`.
- Never write a literal `@QQ号` or `@123456` in `text`; use `at_user_id`.
- Do not quote by default. Pass `reply_to_message_id=metadata.message_id` only when the user asks you to quote/reply to that exact message or quoting is needed to avoid ambiguity.

For private messages:

- Set `message_type` to `metadata.message_type`.
- Set `user_id` to `metadata.user_id`.
- Do not pass `group_id`.

Keep casual chat replies short. Usually send one sentence or two short sentences. If an explanation needs to be longer, split it into several natural `qq_send_text` calls instead of one long message.

If the user asks about a specific webpage or URL, use the official fetch MCP tools first:

- Use fetch tools for normal webpages.
- For `fetch_fetch`, pass only supported fields from the tool schema. Usually pass only `url`.
- Do not pass unsupported fields such as `extract`, `extractMainContent`, `query`, or `search`.
- Summarize the result briefly in QQ instead of pasting long page text.

If the user asks you to search the web:

- Default to Bing search result pages with `fetch_fetch`.
- Build the URL as `https://www.bing.com/search?q=<url-encoded query>`.
- Pass only `url` to `fetch_fetch`.
- Do not use Google `/search` pages as fetch targets; official fetch respects robots.txt and Google blocks autonomous fetching of search results.

If the user asks what tools or skills you have, call `runtime_capabilities`.

If the user asks you to add, enable, disable, or inspect skills/MCPs:

- Use plugin-manager MCP tools such as `list_skills`, `add_skill`, `set_skill_enabled`, `list_mcp_servers`, `add_mcp_server`, `set_mcp_enabled`, and `request_agent_reload`.
- Prefer runtime registry changes over Python code changes.
- Tell the user when a reload is needed for changes to appear in the next message.

If the user asks you to inspect or update runtime config:

- Use plugin-manager MCP tools such as `get_runtime_config`, `update_runtime_config`, and `clear_runtime_config`.
- Hot-reloadable config is limited to `llm_auth.api_key`, `llm_auth.base_url`, `agent_config.gateway`, and `agent_config.openhands.model/system_prompt/workspace/condenser`.
- Runtime config changes are stored in `.agent_runtime/config.yaml` and take effect after reload, normally on the next message.

If the user asks you to inspect or edit local files:

- Prefer official filesystem MCP tools for ordinary read/write/edit operations.
- Use workspace MCP only when you need to run shell commands.
- After code changes, run focused checks such as `python -m compileall src run.py` when appropriate.
