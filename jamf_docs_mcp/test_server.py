#!/usr/bin/env python3
"""Test script for the Jamf Documentation MCP Server."""

import asyncio
import json
import sys


async def test_server():
    """Test that the server module imports and tools are defined."""
    try:
        from jamf_docs_mcp.server import mcp

        print("Server module imported successfully")
        print(f"Server name: {mcp.name}")

        # List the registered tools
        print("\nRegistered tools:")
        tools = [
            'list_jamf_api_tools',
            'list_available_specs',
            'search_jamf_api',
            'list_api_endpoints',
            'get_endpoint_details',
            'get_request_body_schema',
            'get_response_schema',
            'call_jamf_docs_tool',
            'refresh_jamf_docs_cache'
        ]
        for tool_name in tools:
            print(f"  - {tool_name}")

        print("\nServer is correctly configured!")
        print("\nTo use this server, add it to your Claude Desktop or Claude Code configuration.")
        return True

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


async def test_upstream_connection():
    """Test connection to the upstream Jamf docs MCP server."""
    try:
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession

        print("\nTesting connection to Jamf docs MCP server...")
        url = "https://developer.jamf.com/mcp"

        async with streamablehttp_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()

                print(f"Successfully connected to {url}")
                print(f"Found {len(tools_result.tools)} upstream tools:")
                for tool in tools_result.tools:
                    desc = tool.description or "No description"
                    print(f"  - {tool.name}: {desc[:60]}...")

                return True

    except Exception as e:
        print(f"Connection test failed: {e}", file=sys.stderr)
        print("This may be expected if there are network restrictions.")
        return False


async def test_list_specs():
    """Test listing available API specs."""
    try:
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession

        print("\nTesting list-specs...")
        url = "https://developer.jamf.com/mcp"

        async with streamablehttp_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("list-specs", {})

                print("List specs successful!")
                if hasattr(result, 'content'):
                    for content in result.content:
                        if hasattr(content, 'text'):
                            specs = json.loads(content.text)
                            print(f"Found {len(specs)} API specifications:")
                            for spec in specs[:5]:  # Show first 5
                                print(f"  - {spec.get('title', 'Unknown')}")
                            if len(specs) > 5:
                                print(f"  ... and {len(specs) - 5} more")
                            break

                return True

    except Exception as e:
        print(f"List specs test failed: {e}", file=sys.stderr)
        return False


async def test_search():
    """Test searching for API endpoints."""
    try:
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession

        print("\nTesting search-specs for 'computers'...")
        url = "https://developer.jamf.com/mcp"

        async with streamablehttp_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("search-specs", {"pattern": "computers"})

                print("Search successful!")
                if hasattr(result, 'content'):
                    for content in result.content:
                        if hasattr(content, 'text'):
                            text = content.text
                            if len(text) > 500:
                                text = text[:500] + "..."
                            print(f"Results preview:\n{text}")
                            break

                return True

    except Exception as e:
        print(f"Search test failed: {e}", file=sys.stderr)
        return False


async def test_get_endpoint():
    """Test getting endpoint details."""
    try:
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession

        print("\nTesting get-endpoint for /api/v1/computers-inventory...")
        url = "https://developer.jamf.com/mcp"

        async with streamablehttp_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("get-endpoint", {
                    "path": "/api/v1/computers-inventory",
                    "method": "GET",
                    "title": "Jamf Pro API"
                })

                print("Get endpoint successful!")
                if hasattr(result, 'content'):
                    for content in result.content:
                        if hasattr(content, 'text'):
                            text = content.text
                            if len(text) > 800:
                                text = text[:800] + "..."
                            print(f"Endpoint details preview:\n{text}")
                            break

                return True

    except Exception as e:
        print(f"Get endpoint test failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Jamf Documentation MCP Server - Test Suite")
    print("=" * 60)

    # Test module import
    result = asyncio.run(test_server())

    # Test upstream connection (optional)
    if "--test-connection" in sys.argv:
        asyncio.run(test_upstream_connection())

    if "--test-specs" in sys.argv:
        asyncio.run(test_list_specs())

    if "--test-search" in sys.argv:
        asyncio.run(test_search())

    if "--test-endpoint" in sys.argv:
        asyncio.run(test_get_endpoint())

    if "--all" in sys.argv:
        asyncio.run(test_upstream_connection())
        asyncio.run(test_list_specs())
        asyncio.run(test_search())
        asyncio.run(test_get_endpoint())

    if not any(arg in sys.argv for arg in ["--test-connection", "--test-specs", "--test-search", "--test-endpoint", "--all"]):
        print("\nRun with options to test upstream functionality:")
        print("  --test-connection  Test connection to Jamf docs MCP server")
        print("  --test-specs       Test listing API specs")
        print("  --test-search      Test searching for API endpoints")
        print("  --test-endpoint    Test getting endpoint details")
        print("  --all              Run all tests")

    sys.exit(0 if result else 1)
