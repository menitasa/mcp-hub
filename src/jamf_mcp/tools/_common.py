# Copyright 2026, Jamf Software LLC
"""Common utilities for MCP tool implementations.

This module provides shared functionality used by all tool modules including
client management and response formatting.
"""

import json
import logging
import os
from typing import Any, Optional, TYPE_CHECKING, Tuple

from ..client import JamfAPIError, JamfClient
from ..protect_client import ProtectAPIError, ProtectClient

if TYPE_CHECKING:
    from ..security_client import JamfSecurityClient

logger = logging.getLogger(__name__)

# Product configuration information
PRODUCT_CONFIG = {
    "jamf_pro": {
        "name": "Jamf Pro",
        "env_vars": ["JAMF_PRO_URL", "JAMF_PRO_CLIENT_ID", "JAMF_PRO_CLIENT_SECRET"],
        "description": "Core device management for macOS, iOS/iPadOS, and tvOS",
        "docs_url": "https://developer.jamf.com/",
    },
    "jamf_protect": {
        "name": "Jamf Protect",
        "env_vars": ["JAMF_PROTECT_URL", "JAMF_PROTECT_CLIENT_ID", "JAMF_PROTECT_PASSWORD"],
        "description": "Endpoint security for threat detection and response",
        "docs_url": "https://learn.jamf.com/en-US/bundle/jamf-protect-documentation/page/Jamf_Protect_API.html",
    },
    "jamf_security_cloud": {
        "name": "Jamf Security Cloud",
        "env_vars": ["JAMF_SECURITY_URL", "JAMF_SECURITY_APP_ID", "JAMF_SECURITY_APP_SECRET"],
        "description": "Device risk management via the RISK API",
        "docs_url": "https://developer.jamf.com/jamf-security",
    },
}

# Global client instances (initialized by server)
_client: Optional[JamfClient] = None
_protect_client: Optional[ProtectClient] = None
_security_client: Optional["JamfSecurityClient"] = None


def set_client(client: JamfClient) -> None:
    """Set the global Jamf Pro client instance.

    Args:
        client: Configured JamfClient instance
    """
    global _client
    _client = client


def get_client() -> JamfClient:
    """Get the global Jamf Pro client instance.

    Returns:
        JamfClient instance

    Raises:
        RuntimeError: If client is not initialized
    """
    if _client is None:
        raise RuntimeError("Jamf client not initialized. Check server configuration.")
    return _client


def set_protect_client(client: Optional[ProtectClient]) -> None:
    """Set the global Jamf Protect client instance.

    Args:
        client: Configured ProtectClient instance, or None if not available
    """
    global _protect_client
    _protect_client = client


def get_protect_client() -> ProtectClient:
    """Get the global Jamf Protect client instance.

    Returns:
        ProtectClient instance

    Raises:
        RuntimeError: If Protect client is not configured
    """
    if _protect_client is None:
        raise RuntimeError(
            "Jamf Protect not configured. Set JAMF_PROTECT_URL, "
            "JAMF_PROTECT_CLIENT_ID, and JAMF_PROTECT_PASSWORD environment variables."
        )
    return _protect_client


def is_protect_available() -> bool:
    """Check if Jamf Protect client is configured and available.

    Returns:
        True if Protect client is available, False otherwise
    """
    return _protect_client is not None


def is_pro_available() -> bool:
    """Check if Jamf Pro client is configured and available.

    Returns:
        True if Pro client is available, False otherwise
    """
    return _client is not None


def is_security_available() -> bool:
    """Check if Jamf Security Cloud client is configured and available.

    Returns:
        True if Security client is available, False otherwise
    """
    return _security_client is not None


def _check_env_vars(product_key: str) -> Tuple[bool, list[str]]:
    """Check if environment variables are set for a product.

    Args:
        product_key: Key from PRODUCT_CONFIG

    Returns:
        Tuple of (all_set, missing_vars)
    """
    config = PRODUCT_CONFIG.get(product_key, {})
    env_vars = config.get("env_vars", [])
    missing = [var for var in env_vars if not os.environ.get(var)]
    return len(missing) == 0, missing


def format_not_configured_error(product_key: str) -> str:
    """Format a helpful error response when a product is not configured.

    Args:
        product_key: Key from PRODUCT_CONFIG (jamf_pro, jamf_protect, jamf_security_cloud)

    Returns:
        JSON formatted error response with setup instructions
    """
    config = PRODUCT_CONFIG.get(product_key, {})
    name = config.get("name", product_key)
    env_vars = config.get("env_vars", [])
    docs_url = config.get("docs_url", "")

    _, missing = _check_env_vars(product_key)

    error_data = {
        "success": False,
        "error": f"{name} is not configured",
        "product": product_key,
        "setup": {
            "required_env_vars": env_vars,
            "missing_env_vars": missing,
            "docs_url": docs_url,
            "hint": f"Use jamf_configure_help(product='{product_key}') for detailed setup instructions",
        },
    }
    return json.dumps(error_data, indent=2)


def get_client_safe() -> Tuple[Optional[JamfClient], Optional[str]]:
    """Get the global Jamf Pro client instance safely.

    Returns a tuple of (client, error_response) where error_response is a
    formatted JSON string if the client is not available.

    Returns:
        Tuple of (JamfClient or None, error response string or None)
    """
    if _client is None:
        return None, format_not_configured_error("jamf_pro")
    return _client, None


def get_protect_client_safe() -> Tuple[Optional[ProtectClient], Optional[str]]:
    """Get the global Jamf Protect client instance safely.

    Returns a tuple of (client, error_response) where error_response is a
    formatted JSON string if the client is not available.

    Returns:
        Tuple of (ProtectClient or None, error response string or None)
    """
    if _protect_client is None:
        return None, format_not_configured_error("jamf_protect")
    return _protect_client, None


def get_security_client_safe() -> Tuple[Optional["JamfSecurityClient"], Optional[str]]:
    """Get the global Jamf Security Cloud client instance safely.

    Returns a tuple of (client, error_response) where error_response is a
    formatted JSON string if the client is not available.

    Returns:
        Tuple of (JamfSecurityClient or None, error response string or None)
    """
    if _security_client is None:
        return None, format_not_configured_error("jamf_security_cloud")
    return _security_client, None


def set_security_client(client: "JamfSecurityClient") -> None:
    """Set the global Jamf Security Cloud client instance.

    Args:
        client: Configured JamfSecurityClient instance
    """
    global _security_client
    _security_client = client


def get_security_client() -> "JamfSecurityClient":
    """Get the global Jamf Security Cloud client instance.

    Returns:
        JamfSecurityClient instance

    Raises:
        RuntimeError: If security client is not initialized
    """
    if _security_client is None:
        raise RuntimeError(
            "Jamf Security Cloud client not initialized. "
            "Set JAMF_SECURITY_URL, JAMF_SECURITY_APP_ID, and JAMF_SECURITY_APP_SECRET."
        )
    return _security_client


def format_response(data: Any, message: str = "Success", max_size: int = 100000) -> str:
    """Format a successful response as JSON string.

    Args:
        data: Response data
        message: Success message
        max_size: Maximum response size in characters (default 100KB)

    Returns:
        JSON formatted response string, truncated if necessary
    """
    response = json.dumps({"success": True, "message": message, "data": data}, indent=2, default=str)
    if len(response) > max_size:
        truncated_response = {
            "success": True,
            "message": message,
            "data": {"_truncated": True, "_original_size": len(response)},
            "_note": "Response truncated due to size. Use more specific queries or pagination."
        }
        return json.dumps(truncated_response, indent=2)
    return response


def format_error(error: Exception, max_detail_size: int = 2000) -> str:
    """Format an error response as JSON string.

    Args:
        error: Exception that occurred
        max_detail_size: Maximum size for error details (default 2KB)

    Returns:
        JSON formatted error response string
    """
    error_data = {"success": False, "error": str(error)}
    if isinstance(error, JamfAPIError):
        error_data["status_code"] = error.status_code
        if error.response_body:
            try:
                parsed = json.loads(error.response_body)
                details_str = json.dumps(parsed)
                if len(details_str) > max_detail_size:
                    error_data["details"] = {"_truncated": True, "_original_size": len(details_str)}
                else:
                    error_data["details"] = parsed
            except json.JSONDecodeError:
                error_data["details"] = error.response_body[:max_detail_size]
    elif isinstance(error, ProtectAPIError):
        error_data["status_code"] = error.status_code
        if error.graphql_errors:
            error_data["graphql_errors"] = error.graphql_errors
    return json.dumps(error_data, indent=2)
