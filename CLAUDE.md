# Jamf MCP Server

MCP server for Jamf Pro, Protect, and Security Cloud. Stack: Python + FastMCP + `uv`.

## Key Commands

```bash
uv run jamf-mcp          # run server locally
./run_tests.sh            # run full test suite (generates remediation_report.json on failure)
python3 verify_test_coverage.py  # confirm all tools have tests
```

## Architecture

```
Claude → FastMCP (server.py) → @jamf_tool modules (tools/*.py) → Client → Jamf API
```

API versions: Classic `/JSSResource` (XML write, JSON read) · v1 `/api/v1` · v2 `/api/v2` · v3 `/api/v3`

## Adding a Tool

1. Implement in `src/jamf_mcp/tools/<module>.py` using `@jamf_tool` decorator
2. Export in `src/jamf_mcp/tools/__init__.py`
3. Add test to `test_agent.py` and map in `verify_test_coverage.py`
4. Update README.md tools list and `docs/INSTALLATION.md` privileges

Use the `jamf-api-lookup` agent to verify correct endpoints and schemas before implementing.
API docs: `https://developer.jamf.com/` — also queryable via `jamf_docs_mcp/` tools.

## Agents (active in this folder)

| Agent | When to use |
|---|---|
| `jamf-api-lookup` | Verify endpoints and schemas before implementing a tool |
| `mcp-server-builder` | Add or extend tools following project patterns |
| `code-standards-reviewer` | Review code changes for quality |
| `test-and-lint-validator` | Validate before committing |
