# Jamf Developer Documentation MCP Server

An MCP (Model Context Protocol) server that acts as a client to the official Jamf Developer Documentation MCP server at `https://developer.jamf.com/mcp`. This server provides tools for Claude agents to look up correct Jamf Pro API endpoints, paths, HTTP methods, and API versions.

## Purpose

When developing integrations with the Jamf Pro API, it's critical to use the correct:

- API endpoints (v1, v2, or Classic API)
- HTTP methods (GET, POST, PUT, DELETE, PATCH)
- Request/response schemas

This MCP server connects to Jamf's official documentation server and exposes tools that allow Claude agents to query and retrieve accurate, up-to-date API documentation.

## Features

The server provides these tools:

| Tool                      | Description                                                        |
| ------------------------- | ------------------------------------------------------------------ |
| `list_jamf_api_tools`     | List all available tools from upstream server                      |
| `list_available_specs`    | List all Jamf API specifications (Jamf Pro API, Classic API, etc.) |
| `search_jamf_api`         | Search for endpoints across all specs by pattern                   |
| `list_api_endpoints`      | List all endpoints for a specific API spec                         |
| `get_endpoint_details`    | Get detailed docs for a specific endpoint                          |
| `get_request_body_schema` | Get request body schema for POST/PUT endpoints                     |
| `get_response_schema`     | Get response schema for an endpoint                                |
| `call_jamf_docs_tool`     | Call any upstream tool directly                                    |
| `refresh_jamf_docs_cache` | Refresh cached tool list                                           |

## Available API Specifications

The Jamf docs server provides multiple API specifications:

- **Jamf Pro API** - Modern REST API with `/api/v1` and `/api/v2` endpoints
- **Classic API** - Legacy `/JSSResource` XML/JSON endpoints
- **Jamf Inventory API** - Cross-product inventory data
- **Device Inventory API** - Device inventory management
- **Device Groups API** - Device group management
- **Device Management Actions API** - Management tasks
- **Blueprints API** - Declarative device management
- **Jamf Compliance Benchmarks API** - Compliance management
- And more...

## Installation

### Using uv (Recommended)

```bash
cd /Users/username/repo_name/jamf_docs_mcp
uv sync
```

### Using pip

```bash
cd /Users/username/repo_name/jamf_docs_mcp
pip install -e .
```

## Usage

### Running the Server

```bash
# Using uv
uv run jamf-docs-mcp

# Or using Python directly
python -m jamf_docs_mcp.server
```

### Claude Desktop Configuration

Add this to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "jamf-docs": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/username/repo_name/jamf_docs_mcp",
        "jamf-docs-mcp"
      ]
    }
  }
}
```

Or using Python directly:

```json
{
  "mcpServers": {
    "jamf-docs": {
      "command": "python3",
      "args": ["-m", "jamf_docs_mcp.server"],
      "cwd": "/Users/username/repo_name/jamf_docs_mcp"
    }
  }
}
```

## Example Queries

Once configured, you can ask Claude questions like:

- "What's the correct endpoint for listing computers in Jamf Pro?"
- "Search for the mobile device prestage API"
- "What API version should I use for configuration profiles?"
- "Get details for the /api/v1/scripts endpoint"
- "Show me the request body schema for creating a computer group"

## Tool Usage Examples

### List Available API Specs

```
list_available_specs()
```

Returns all API specifications available for querying.

### Search for Endpoints

```
search_jamf_api(pattern="computers")
```

Searches across all API specs for endpoints matching "computers".

### Get Endpoint Details

```
get_endpoint_details(
    path="/api/v1/computers-inventory",
    method="GET",
    spec_title="Jamf Pro API"
)
```

Returns detailed documentation including parameters, security requirements, and operation details.

### Get Request Body Schema

```
get_request_body_schema(
    path="/api/v1/computer-prestages",
    method="POST",
    spec_title="Jamf Pro API"
)
```

Returns the JSON schema for the request body.

## Testing

Verify the server works correctly:

```bash
# Basic module test
python3 test_server.py

# Full test suite (connects to upstream server)
python3 test_server.py --all

# Individual tests
python3 test_server.py --test-connection
python3 test_server.py --test-specs
python3 test_server.py --test-search
python3 test_server.py --test-endpoint
```

## Architecture

```
+-------------------+          +---------------------------+
|  Claude Agent     |          |  Jamf Docs MCP Server     |
|  (MCP Client)     |  stdio   |  (This Project)           |
+--------+----------+          +------------+--------------+
         |                                  |
         | MCP Protocol                     | Streamable HTTP
         |                                  |
         v                                  v
+--------+----------+          +------------+--------------+
|  jamf-docs-mcp    |  ------> |  developer.jamf.com/mcp   |
|  (Local Server)   |          |  (Jamf Official Server)   |
+-------------------+          +---------------------------+
```

This server acts as a bridge, translating local MCP requests (via stdio) to remote MCP requests (via Streamable HTTP) to the Jamf documentation server.

## Dependencies

- `mcp>=1.0.0` - Model Context Protocol SDK
- `httpx>=0.27.0` - HTTP client with async support
- `httpx-sse>=0.4.0` - SSE support for httpx

## Troubleshooting

### Connection Errors

If you see connection errors to `developer.jamf.com/mcp`:

1. Check your internet connection
2. Verify the Jamf docs server is accessible
3. Try refreshing the cache with `refresh_jamf_docs_cache()`

### Tool Not Found

If a tool call fails with "tool not found":

1. Call `list_jamf_api_tools()` to see available upstream tools
2. Use `call_jamf_docs_tool()` with the exact tool name and arguments

### Cache Issues

If responses seem stale, call `refresh_jamf_docs_cache()` to clear the cached tool list.

### Spec Title Errors

Many tools require a `spec_title` parameter. Common values:

- `"Jamf Pro API"` for `/api/v1` and `/api/v2` endpoints
- `"Classic API"` for `/JSSResource` endpoints

Use `list_available_specs()` to see all available options.

## References

- [Jamf MCP Documentation](https://developer.jamf.com/developer-guide/docs/mcp)
- [Jamf Developer Portal](https://developer.jamf.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
