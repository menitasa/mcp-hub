"""Setup and onboarding tools for Jamf MCP Server.

This module provides tools for checking configuration status and getting
setup instructions. These tools work without any credentials configured,
enabling a zero-credential startup experience.
"""

import json
import logging
import os
from typing import Optional

from ._common import (
    PRODUCT_CONFIG,
    _check_env_vars,
    is_pro_available,
    is_protect_available,
    is_security_available,
)
from ._registry import jamf_tool, get_registered_tools

logger = logging.getLogger(__name__)

# Detailed setup instructions for each product
SETUP_INSTRUCTIONS = {
    "jamf_pro": {
        "name": "Jamf Pro",
        "description": "Core device management for macOS, iOS/iPadOS, and tvOS devices.",
        "steps": [
            "1. Log in to your Jamf Pro instance",
            "2. Navigate to Settings > System > API Roles and Clients",
            "3. Create an API Role with the permissions you need:",
            "   - Computers: Read, Update (for device management)",
            "   - Mobile Devices: Read, Update (for iOS/iPadOS management)",
            "   - Users: Read, Update (for user management)",
            "   - Smart/Static Groups: Read, Create (for group management)",
            "   - Policies, Profiles, Scripts: Read (for configuration access)",
            "4. Create an API Client and assign the role you created",
            "5. Copy the Client ID and generate a Client Secret",
            "6. Set these environment variables:",
        ],
        "env_vars": {
            "JAMF_PRO_URL": {
                "description": "Your Jamf Pro URL",
                "example": "https://yourcompany.jamfcloud.com",
            },
            "JAMF_PRO_CLIENT_ID": {
                "description": "OAuth API client ID from step 5",
                "example": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            },
            "JAMF_PRO_CLIENT_SECRET": {
                "description": "OAuth API client secret from step 5",
                "example": "your-client-secret",
            },
        },
        "docs_url": "https://developer.jamf.com/",
        "tools_available": 37,
    },
    "jamf_protect": {
        "name": "Jamf Protect",
        "description": "Endpoint security for threat detection and response on macOS.",
        "steps": [
            "1. Log in to your Jamf Protect console",
            "2. Navigate to Administrative > API Clients",
            "3. Create a new API Client",
            "4. Copy the Client ID and Password",
            "5. Set these environment variables:",
        ],
        "env_vars": {
            "JAMF_PROTECT_URL": {
                "description": "Jamf Protect API URL (GraphQL endpoint)",
                "example": "https://yourorg.protect.jamfcloud.com/graphql",
            },
            "JAMF_PROTECT_CLIENT_ID": {
                "description": "API client ID from step 4",
                "example": "your-protect-client-id",
            },
            "JAMF_PROTECT_PASSWORD": {
                "description": "API client password from step 4",
                "example": "your-protect-password",
            },
        },
        "docs_url": "https://learn.jamf.com/en-US/bundle/jamf-protect-documentation/page/Jamf_Protect_API.html",
        "tools_available": 6,
    },
    "jamf_security_cloud": {
        "name": "Jamf Security Cloud",
        "description": "Device risk management via the RISK API (formerly Wandera).",
        "steps": [
            "1. Log in to your Jamf Security Cloud console (radar.wandera.com)",
            "2. Navigate to Settings > Integrations > API",
            "3. Create new API credentials",
            "4. Copy the App ID and App Secret",
            "5. Set these environment variables:",
        ],
        "env_vars": {
            "JAMF_SECURITY_URL": {
                "description": "Security Cloud URL",
                "example": "https://radar.wandera.com",
            },
            "JAMF_SECURITY_APP_ID": {
                "description": "API App ID from step 4",
                "example": "your-security-app-id",
            },
            "JAMF_SECURITY_APP_SECRET": {
                "description": "API App Secret from step 4",
                "example": "your-security-secret",
            },
        },
        "docs_url": "https://developer.jamf.com/jamf-security",
        "tools_available": 2,
    },
}


def _get_product_status(product_key: str) -> dict:
    """Get configuration status for a specific product.

    Args:
        product_key: Key from PRODUCT_CONFIG

    Returns:
        Dict with configuration status
    """
    _config = PRODUCT_CONFIG.get(product_key, {})
    all_set, missing = _check_env_vars(product_key)

    # Check if client is actually initialized and ready
    ready = False
    if product_key == "jamf_pro":
        ready = is_pro_available()
    elif product_key == "jamf_protect":
        ready = is_protect_available()
    elif product_key == "jamf_security_cloud":
        ready = is_security_available()

    instructions = SETUP_INSTRUCTIONS.get(product_key, {})

    return {
        "configured": all_set,
        "ready": ready,
        "missing_env_vars": missing if not all_set else [],
        "tools_available": instructions.get("tools_available", 0) if ready else 0,
    }


def _count_available_tools() -> int:
    """Count total number of registered tools."""
    return len(get_registered_tools())


@jamf_tool
async def jamf_get_setup_status() -> str:
    """Get the configuration status for all Jamf products.

    Shows which products are configured and ready, which environment variables
    are missing, and how many tools are available for each product. Use this
    tool to understand what's configured and what needs setup.

    This tool always works, even when no credentials are configured.

    Returns:
        JSON containing configuration status for each product:
        - jamf_pro: Core device management status
        - jamf_protect: Endpoint security status
        - jamf_security_cloud: Risk management status
        - summary: Overall counts and status
    """
    status = {
        "jamf_pro": _get_product_status("jamf_pro"),
        "jamf_protect": _get_product_status("jamf_protect"),
        "jamf_security_cloud": _get_product_status("jamf_security_cloud"),
    }

    # Calculate summary
    products_configured = sum(1 for p in status.values() if p["configured"])
    products_ready = sum(1 for p in status.values() if p["ready"])
    total_tools_available = sum(p["tools_available"] for p in status.values())

    # Add setup tools that are always available
    setup_tools = 2  # jamf_get_setup_status and jamf_configure_help
    total_tools_available += setup_tools

    status["summary"] = {
        "products_configured": products_configured,
        "products_ready": products_ready,
        "total_products": 3,
        "tools_available": total_tools_available,
        "total_tools": _count_available_tools(),
    }

    if products_ready == 0:
        status["summary"]["message"] = (
            "No products configured. Use jamf_configure_help() to get setup instructions."
        )
    elif products_ready < 3:
        unconfigured = [
            PRODUCT_CONFIG[k]["name"]
            for k, v in status.items()
            if isinstance(v, dict) and v.get("ready") is False
        ]
        status["summary"]["message"] = (
            f"Some products not configured: {', '.join(unconfigured)}. "
            "Use jamf_configure_help() for setup instructions. Please note, that the not all products need to be configured for a tool to function correctly. If in doubt, attempt to use the tool before asking the user to provide additional credentials or configuration."
        )
    else:
        status["summary"]["message"] = "All products configured and ready."

    return json.dumps({"success": True, "data": status}, indent=2)


@jamf_tool
async def jamf_configure_help(
    product: str = "all",
) -> str:
    """Get detailed setup instructions for Jamf products.

    Provides step-by-step instructions for configuring each Jamf product,
    including required environment variables and documentation links.

    This tool always works, even when no credentials are configured.

    Args:
        product: Which product to get help for. Options:
            - "all" (default): Instructions for all products
            - "jamf_pro": Jamf Pro device management
            - "jamf_protect": Jamf Protect security
            - "jamf_security_cloud": Jamf Security Cloud risk management

    Returns:
        JSON containing setup instructions with:
        - Step-by-step setup guide
        - Required environment variables with examples
        - Documentation links
        - Current configuration status
    """
    valid_products = ["all", "jamf_pro", "jamf_protect", "jamf_security_cloud"]
    if product not in valid_products:
        return json.dumps({
            "success": False,
            "error": f"Invalid product '{product}'. Must be one of: {', '.join(valid_products)}",
        }, indent=2)

    result = {}

    if product == "all":
        products_to_show = ["jamf_pro", "jamf_protect", "jamf_security_cloud"]
    else:
        products_to_show = [product]

    for prod_key in products_to_show:
        instructions = SETUP_INSTRUCTIONS.get(prod_key, {})
        status = _get_product_status(prod_key)

        result[prod_key] = {
            "name": instructions.get("name", prod_key),
            "description": instructions.get("description", ""),
            "current_status": {
                "configured": status["configured"],
                "ready": status["ready"],
                "missing_env_vars": status["missing_env_vars"],
            },
            "setup_steps": instructions.get("steps", []),
            "environment_variables": instructions.get("env_vars", {}),
            "documentation": instructions.get("docs_url", ""),
            "tools_when_configured": instructions.get("tools_available", 0),
        }

    message = f"Setup instructions for {product}"
    if product == "all":
        message = "Setup instructions for all Jamf products"

    return json.dumps({"success": True, "message": message, "data": result}, indent=2)
