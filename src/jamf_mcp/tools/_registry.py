# Copyright 2026, Jamf Software LLC
"""Tool registry for Jamf MCP Server.

This module provides a decorator-based registration system for MCP tools.
Tools decorated with @jamf_tool are automatically collected and can be
registered with the FastMCP server using register_all().

Usage:
    # In tool modules:
    from ._registry import jamf_tool

    @jamf_tool
    async def jamf_get_something(...) -> str:
        '''Docstring becomes MCP tool description.'''
        # implementation

    # In server.py:
    from .tools import register_all_tools
    register_all_tools(mcp)
"""

from enum import Enum
from typing import Callable, Optional

class ToolType(Enum):
    API = "api"
    COMPLEX = "complex"

# Registry of all MCP tools with their type
# List of tuples: (function, tool_type)
_tools: list[tuple[Callable, ToolType]] = []


def jamf_tool(func_or_type: Optional[Callable] = None, tool_type: ToolType = ToolType.API) -> Callable:
    """Decorator to register a function as an MCP tool.

    Can be used as @jamf_tool or @jamf_tool(tool_type=ToolType.COMPLEX).

    The decorated function will be automatically registered with the
    FastMCP server when register_all() is called.

    The function's docstring becomes the MCP tool description shown to LLMs.
    """
    def _decorator(func: Callable) -> Callable:
        _tools.append((func, tool_type))
        return func

    if func_or_type is None:
        # Called as @jamf_tool(tool_type=...)
        return _decorator
    elif callable(func_or_type):
        # Called as @jamf_tool without arguments
        return _decorator(func_or_type)
    else:
        # Called with tool_type as first argument (shouldn't happen with correct usage but handle it)
        tool_type = func_or_type
        return _decorator


def get_tool_product(func: Callable) -> str:
    """Determine which product a tool belongs to based on its module.
    
    Returns:
        One of: 'jamf_pro', 'jamf_protect', 'jamf_security_cloud', 'setup'
    """
    module_name = func.__module__
    
    if "protect" in module_name:
        return "jamf_protect"
    elif "risk" in module_name or "security" in module_name:
        return "jamf_security_cloud"
    elif "setup" in module_name:
        return "setup"
    
    # default to Jamf Pro for other tools in tools package
    return "jamf_pro"


def register_all(
    mcp,
    tool_filter: Optional[str] = None,
    allowed_products: Optional[list[str]] = None,
) -> None:
    """Register all decorated tools with the FastMCP server.

    Args:
        mcp: The FastMCP server instance to register tools with.
        tool_filter: Optional filter string ('api' or 'complex').
                    If None or 'all', registers all tools.
        allowed_products: Optional list of product names to register tools for.
                         If None, registers all products.
                         Valid values: 'jamf_pro', 'jamf_protect', 'jamf_security_cloud'
                         Note: 'setup' tools are always registered.
    """
    for func, t_type in _tools:
        # Apply type filter (api/complex)
        if tool_filter and tool_filter.lower() != "all":
            if t_type.value != tool_filter.lower():
                continue
        
        # Apply product filter
        if allowed_products:
            product = get_tool_product(func)
            # unexpected values in allowed_products, usually passed from CLI, might be short names
            # Map CLI names to internal names if needed, but let's assume we handle that in caller or standardise
            
            # Use 'setup' as a special internal product that is always allowed
            if product != "setup":
                # Check if product is in allowed list
                # Use strict matching with alias support to avoid "pro" in "protect" issues
                is_allowed = False
                for p in allowed_products:
                    p_lower = p.lower()
                    if p_lower == product:
                        is_allowed = True
                    # Aliases
                    elif p_lower == "pro" and product == "jamf_pro":
                        is_allowed = True
                    elif p_lower == "protect" and product == "jamf_protect":
                        is_allowed = True
                    elif (p_lower == "security" or p_lower == "risk") and product == "jamf_security_cloud":
                        is_allowed = True
                
                if not is_allowed:
                    continue
                
        mcp.tool()(func)


def get_registered_tools() -> list[tuple[Callable, ToolType]]:
    """Get list of all registered tool functions with their types.

    Useful for introspection and testing.
    """
    return _tools.copy()
