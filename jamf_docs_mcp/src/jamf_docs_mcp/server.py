"""
Jamf Developer Documentation MCP Server

This MCP server acts as a client to the Jamf Developer Documentation MCP server
at https://developer.jamf.com/mcp, providing tools to search and retrieve
API endpoint documentation for Jamf Pro.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Optional
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("jamf-docs-mcp")

# Jamf Developer Documentation MCP Server URL
JAMF_DOCS_MCP_URL = "https://developer.jamf.com/mcp"

# Cache for tools from the upstream server
_upstream_tools_cache: list[dict] | None = None


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Lifespan context manager for the server."""
    logger.info("Starting Jamf Documentation MCP Server")
    logger.info(f"Upstream server: {JAMF_DOCS_MCP_URL}")
    yield
    logger.info("Server shutdown complete")


# Create MCP server instance
mcp = FastMCP(
    "jamf-docs-mcp",
    instructions="""Jamf Developer Documentation MCP Server

This server provides tools to look up Jamf Pro API documentation directly from
the official Jamf developer documentation at https://developer.jamf.com/mcp.

Use these tools to:
- Find the correct API endpoint for a specific operation
- Get the correct HTTP method (GET, POST, PUT, DELETE)
- Determine the correct API version (v1, v2, or Classic API)
- Get request/response schemas and parameter details

Available API specs:
- "Jamf Pro API" - The modern REST API (v1/v2 endpoints)
- "Classic API" - Legacy XML/JSON API (/JSSResource endpoints)
- "Jamf Inventory API" - Inventory data across Jamf products
- "Device Inventory API" - Device inventory management
- "Device Groups API" - Device group management
- "Device Management Actions API" - Management tasks
- "Blueprints API" - Declarative device management
- "Jamf Compliance Benchmarks API" - Compliance management
- And more...

Available tools:
- list_available_specs: List all available API specs
- search_jamf_api: Search for API endpoints by pattern
- list_api_endpoints: List all endpoints for a specific API spec
- get_endpoint_details: Get detailed docs for a specific endpoint
- get_request_body_schema: Get request body schema for an endpoint
- get_response_schema: Get response schema for an endpoint
- call_jamf_docs_tool: Call any upstream tool directly
- refresh_jamf_docs_cache: Refresh the cached tool list""",
    lifespan=lifespan,
)


async def get_upstream_tools() -> list[dict]:
    """
    Connect to the Jamf docs MCP server and list available tools.
    Results are cached to avoid repeated connections.
    """
    global _upstream_tools_cache

    if _upstream_tools_cache is not None:
        return _upstream_tools_cache

    try:
        async with streamablehttp_client(JAMF_DOCS_MCP_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                _upstream_tools_cache = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                    }
                    for tool in tools_result.tools
                ]
                logger.info(f"Cached {len(_upstream_tools_cache)} tools from Jamf docs MCP server")
                return _upstream_tools_cache
    except Exception as e:
        logger.error(f"Failed to connect to Jamf docs MCP server: {e}")
        raise


async def call_upstream_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """
    Call a tool on the upstream Jamf docs MCP server.
    """
    try:
        async with streamablehttp_client(JAMF_DOCS_MCP_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result
    except Exception as e:
        logger.error(f"Failed to call upstream tool {tool_name}: {e}")
        raise


def extract_content(result: Any) -> str:
    """Extract text content from an MCP tool result."""
    if hasattr(result, 'content'):
        content_parts = []
        for content_item in result.content:
            if hasattr(content_item, 'text'):
                content_parts.append(content_item.text)
        return "\n".join(content_parts) if content_parts else str(result)
    return str(result)


@mcp.tool()
async def list_jamf_api_tools() -> str:
    """List all available tools from the Jamf Developer Documentation MCP server.

    This returns a list of tools that can be used to search and retrieve
    Jamf Pro API documentation. Use this to discover what documentation
    tools are available from the upstream server.

    Returns:
        A JSON string containing the list of available tools with their
        names, descriptions, and input schemas.
    """
    try:
        tools = await get_upstream_tools()
        return json.dumps(tools, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def list_available_specs() -> str:
    """List all available Jamf API specifications.

    Returns the list of OpenAPI specs available for querying. Use the 'title'
    from this list when calling other tools that require a spec title.

    Common specs:
    - "Jamf Pro API" - Modern REST API with v1/v2 endpoints
    - "Classic API" - Legacy /JSSResource endpoints

    Returns:
        JSON array of available API specs with titles and descriptions.
    """
    try:
        result = await call_upstream_tool("list-specs", {})
        return extract_content(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def search_jamf_api(pattern: str) -> str:
    """Search the Jamf Pro API documentation for endpoints matching a pattern.

    Use this to find API endpoints related to specific functionality like
    "computers", "mobile", "scripts", "policies", "prestage", etc.

    This searches across ALL available API specs (Jamf Pro API, Classic API, etc.)
    and returns matching paths, operations, and schemas.

    Args:
        pattern: Case-insensitive search pattern.
                 Examples: "computers", "mobile", "prestage", "policies",
                 "scripts", "extension", "configuration", "profile"

    Returns:
        Search results containing matching endpoint paths, operations,
        and schema definitions from all available API specs.
    """
    try:
        result = await call_upstream_tool("search-specs", {"pattern": pattern})
        return extract_content(result)
    except Exception as e:
        return json.dumps({"error": str(e), "pattern": pattern})


@mcp.tool()
async def list_api_endpoints(
    spec_title: str = "Jamf Pro API"
) -> str:
    """List all API endpoints for a specific Jamf API spec.

    Returns all available paths and their HTTP methods for the specified API.

    Args:
        spec_title: Title of the OpenAPI spec to query. Common values:
                   - "Jamf Pro API" (default) - Modern v1/v2 endpoints
                   - "Classic API" - Legacy /JSSResource endpoints
                   - "Device Inventory API"
                   - "Device Groups API"
                   Use list_available_specs() to see all options.

    Returns:
        List of all endpoint paths with their HTTP methods and summaries.
    """
    try:
        result = await call_upstream_tool("list-endpoints", {"title": spec_title})
        return extract_content(result)
    except Exception as e:
        return json.dumps({"error": str(e), "spec_title": spec_title})


@mcp.tool()
async def get_endpoint_details(
    path: str,
    method: str,
    spec_title: str = "Jamf Pro API"
) -> str:
    """Get detailed documentation for a specific Jamf Pro API endpoint.

    Use this to get full details about an endpoint including:
    - Operation summary and description
    - Required and optional parameters
    - Security requirements
    - Tags and operation ID

    Args:
        path: The API endpoint path.
              Examples: "/api/v1/computers-inventory",
              "/JSSResource/policies", "/api/v2/mobile-devices"
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        spec_title: Title of the OpenAPI spec. Use:
                   - "Jamf Pro API" for /api/v1 and /api/v2 endpoints
                   - "Classic API" for /JSSResource endpoints

    Returns:
        Detailed documentation for the specified endpoint.
    """
    try:
        result = await call_upstream_tool("get-endpoint", {
            "path": path,
            "method": method.upper(),
            "title": spec_title
        })
        return extract_content(result)
    except Exception as e:
        return json.dumps({"error": str(e), "path": path, "method": method})


@mcp.tool()
async def get_request_body_schema(
    path: str,
    method: str,
    spec_title: str = "Jamf Pro API"
) -> str:
    """Get the request body schema for a specific endpoint.

    Use this for POST, PUT, and PATCH endpoints to understand
    what data to send in the request body.

    Args:
        path: The API endpoint path.
        method: HTTP method (typically POST, PUT, or PATCH)
        spec_title: Title of the OpenAPI spec.

    Returns:
        JSON schema definition for the request body.
    """
    try:
        result = await call_upstream_tool("get-request-body", {
            "path": path,
            "method": method.upper(),
            "title": spec_title
        })
        return extract_content(result)
    except Exception as e:
        return json.dumps({"error": str(e), "path": path, "method": method})


@mcp.tool()
async def get_response_schema(
    path: str,
    method: str,
    spec_title: str = "Jamf Pro API",
    status_code: str = "200"
) -> str:
    """Get the response schema for a specific endpoint.

    Use this to understand what data structure to expect from an API response.

    Args:
        path: The API endpoint path.
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        spec_title: Title of the OpenAPI spec.
        status_code: HTTP status code to get schema for (default: "200")

    Returns:
        JSON schema definition for the response body.
    """
    try:
        result = await call_upstream_tool("get-response-schema", {
            "path": path,
            "method": method.upper(),
            "title": spec_title,
            "statusCode": status_code
        })
        return extract_content(result)
    except Exception as e:
        return json.dumps({"error": str(e), "path": path, "method": method})


@mcp.tool()
async def call_jamf_docs_tool(tool_name: str, arguments: str = "{}") -> str:
    """Call any tool on the Jamf Developer Documentation MCP server directly.

    Use list_jamf_api_tools() first to see available tools and their schemas,
    then use this to call a specific tool with custom arguments.

    Available upstream tools:
    - list-specs: List all API specs
    - list-endpoints: List endpoints for a spec (requires: title)
    - get-endpoint: Get endpoint details (requires: path, method, title)
    - get-request-body: Get request schema (requires: path, method, title)
    - get-response-schema: Get response schema (requires: path, method, title)
    - search-specs: Search across specs (requires: pattern)
    - list-security-schemes: List auth methods (requires: title)
    - get-server-variables: Get server config (requires: title)
    - get-code-snippet: Generate code (requires: path, method, codingLanguage, serverVariables, title)
    - execute-request: Execute API call (requires: harRequest, title)

    Args:
        tool_name: The name of the tool to call on the Jamf docs server.
        arguments: JSON string of arguments to pass to the tool.

    Returns:
        The result from the upstream tool call.
    """
    try:
        args = json.loads(arguments)
        result = await call_upstream_tool(tool_name, args)
        return extract_content(result)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON arguments: {e}"})
    except Exception as e:
        return json.dumps({"error": str(e), "tool_name": tool_name})


@mcp.tool()
async def refresh_jamf_docs_cache() -> str:
    """Refresh the cached list of tools from the Jamf docs MCP server.

    Call this if tools seem outdated or if you're getting unexpected errors.

    Returns:
        Status message indicating success or failure of cache refresh.
    """
    global _upstream_tools_cache
    _upstream_tools_cache = None

    try:
        tools = await get_upstream_tools()
        return json.dumps({
            "status": "success",
            "message": f"Cache refreshed. Found {len(tools)} tools.",
            "tools": [t.get("name") for t in tools]
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def main():
    """Main entry point."""
    logger.info("Initializing Jamf Documentation MCP Server")
    mcp.run()


if __name__ == "__main__":
    main()
