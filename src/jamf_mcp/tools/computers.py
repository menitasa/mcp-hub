# Copyright 2026, Jamf Software LLC
"""Computer management tools for Jamf Pro.

This module provides tools for retrieving and updating macOS computer
inventory information.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
from urllib.parse import quote

from ..client import JamfAPIError
from ._common import format_error, format_response, get_client_safe
from ._registry import jamf_tool

logger = logging.getLogger(__name__)


def _build_fields(field_mapping: dict[str, Any]) -> dict[str, Any]:
    """Build a dict from field mapping, excluding None values.

    Args:
        field_mapping: Dict of API field names to values

    Returns:
        Dict containing only non-None values
    """
    return {key: value for key, value in field_mapping.items() if value is not None}


def _build_extension_attributes(extension_attributes: list[dict]) -> list[dict]:
    """Format extension attributes for the Jamf API.

    Args:
        extension_attributes: List of dicts with 'id' and 'value' keys

    Returns:
        List formatted for Jamf API with 'definitionId' and 'values'
    """
    return [
        {"definitionId": str(ea["id"]), "values": [str(ea["value"])]}
        for ea in extension_attributes
    ]


def _strip_nulls(obj: Any) -> Any:
    """Recursively remove None values from dicts and lists."""
    if isinstance(obj, dict):
        return {k: _strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_nulls(i) for i in obj]
    return obj


def _build_concise_computer_result(
    computer_id: int, update_data: dict, api_result: Any
) -> dict:
    """Build a concise result dict from update response.

    Args:
        computer_id: The computer ID that was updated
        update_data: The data that was sent in the update
        api_result: The raw API response

    Returns:
        Concise result dict with key fields only
    """
    result = {
        "id": computer_id,
        "updated_fields": list(update_data.keys()),
    }
    if isinstance(api_result, dict) and "general" in api_result:
        result["name"] = api_result["general"].get("name")
        result["serialNumber"] = api_result["general"].get("serialNumber")
    return result


@jamf_tool
async def jamf_get_computer(
    computer_id: Optional[int] = None,
    serial_number: Optional[str] = None,
    name: Optional[str] = None,
    username: Optional[str] = None,
    page: int = 0,
    page_size: int = 100,
    sections: Optional[list[str]] = None,
) -> str:
    """Get computer information from Jamf Pro.

    Retrieves detailed inventory information for macOS computers managed by Jamf Pro.
    You can search by ID, serial number, name, or macOS username. If no identifier
    is provided, returns a paginated list of all computers.

    Single-device lookups (by computer_id) default to GENERAL, HARDWARE,
    USER_AND_LOCATION, and EXTENSION_ATTRIBUTES sections. List/search queries
    default to GENERAL only to keep responses small — pass sections= explicitly
    to get more detail.

    Args:
        computer_id: Jamf Pro computer ID to retrieve specific device
        serial_number: Computer serial number to search for exact match
        name: Computer name to search for (substring match, case-insensitive)
        username: macOS local username (lastLoggedInUsernameBinary) to search for
        page: Page number for pagination (0-indexed, default: 0)
        page_size: Number of results per page (default: 100, max: 2000)
        sections: Inventory sections to include. Single-device default:
            ["GENERAL", "HARDWARE", "USER_AND_LOCATION", "EXTENSION_ATTRIBUTES"].
            List/search default: ["GENERAL"].
            Available sections: GENERAL, DISK_ENCRYPTION, PURCHASING, APPLICATIONS,
            STORAGE, USER_AND_LOCATION, CONFIGURATION_PROFILES, PRINTERS, SERVICES,
            HARDWARE, LOCAL_USER_ACCOUNTS, CERTIFICATES, ATTACHMENTS, PLUGINS,
            PACKAGE_RECEIPTS, FONTS, SECURITY, OPERATING_SYSTEM, LICENSED_SOFTWARE,
            IBEACONS, SOFTWARE_UPDATES, EXTENSION_ATTRIBUTES, CONTENT_CACHING,
            GROUP_MEMBERSHIPS.

    Returns:
        JSON containing computer details or list of computers with inventory data
        including hardware, software, extension attribute values, and management
        information.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        if computer_id:
            active_sections = sections or ["GENERAL", "HARDWARE", "USER_AND_LOCATION", "EXTENSION_ATTRIBUTES"]
            result = await client.get_computer_inventory(
                computer_id=computer_id, section=active_sections
            )
            return format_response(result, f"Retrieved computer ID {computer_id}")

        active_sections = sections or ["GENERAL"]

        filters = []
        if serial_number:
            filters.append(f'hardware.serialNumber=="{serial_number}"')
        if name:
            filters.append(f'general.name=like="*{name}*"')
        if username:
            filters.append(f'general.lastLoggedInUsernameBinary=="{username}"')

        params: dict = {"page": page, "page-size": page_size, "section": active_sections}
        if filters:
            params["filter"] = " and ".join(filters)

        result = await client.v1_get("computers-inventory", params=params)
        if "results" in result:
            result = dict(result)
            result["results"] = [_strip_nulls(c) for c in result["results"]]
        count = result.get("totalCount", len(result.get("results", [])))
        return format_response(result, f"Retrieved {count} computers")

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error getting computer info")
        return format_error(e)


@jamf_tool
async def jamf_update_computer(
    computer_id: int,
    name: Optional[str] = None,
    asset_tag: Optional[str] = None,
    username: Optional[str] = None,
    realname: Optional[str] = None,
    email: Optional[str] = None,
    department_id: Optional[Union[str, int]] = None,
    building_id: Optional[Union[str, int]] = None,
    room: Optional[str] = None,
    position: Optional[str] = None,
    phone: Optional[str] = None,
    extension_attributes: Optional[list[dict]] = None,
) -> str:
    """Update computer information in Jamf Pro.

    Updates inventory fields for a specific computer. Only provided fields will be
    updated; omitted fields remain unchanged. Useful for updating asset information,
    user assignments, and custom extension attribute values.

    Args:
        computer_id: Jamf Pro computer ID to update (required)
        name: New computer name
        asset_tag: Asset tag value for inventory tracking
        username: Assigned user's username
        realname: Assigned user's full/display name
        email: Assigned user's email address
        department_id: Department ID (use jamf_get_departments to find valid IDs).
            Accepts integer or string, e.g., 1 or "1"
        building_id: Building ID (use jamf_get_buildings to find valid IDs).
            Accepts integer or string, e.g., 28 or "28"
        room: Room number or name (free-form text, no validation)
        position: User's job position or title (free-form text)
        phone: Contact phone number (free-form text)
        extension_attributes: List of extension attribute updates, each with:
            - id: Extension attribute definition ID (integer)
            - value: New value to set (string)

    Returns:
        JSON with update confirmation and the updated computer record.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        update_data = {}

        general = _build_fields({"name": name, "assetTag": asset_tag})
        if general:
            update_data["general"] = general

        user_and_location = _build_fields({
            "username": username,
            "realname": realname,
            "email": email,
            "departmentId": str(department_id) if department_id is not None else None,
            "buildingId": str(building_id) if building_id is not None else None,
            "room": room,
            "position": position,
            "phone": phone,
        })
        if user_and_location:
            update_data["userAndLocation"] = user_and_location

        if extension_attributes:
            update_data["extensionAttributes"] = _build_extension_attributes(
                extension_attributes
            )

        if not update_data:
            return format_error(ValueError("No update fields provided"))

        result = await client.v1_patch(
            f"computers-inventory-detail/{computer_id}", update_data
        )
        concise_result = _build_concise_computer_result(computer_id, update_data, result)
        return format_response(concise_result, f"Updated computer ID {computer_id}")

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error updating computer info")
        return format_error(e)


@jamf_tool
async def jamf_get_computers_not_checked_in(
    days: int = 30,
    page: int = 0,
    page_size: int = 100,
) -> str:
    """Find computers that haven't checked in with Jamf for N or more days.

    Identifies stale, lost, or offline Macs by querying computers whose last
    contact time is older than the specified number of days. Results are sorted
    oldest-first so the most stale devices appear at the top.

    Use this to identify computers that may need attention: retired devices still
    in Jamf, Macs that have been offline for an extended period, or devices that
    have lost MDM connectivity.

    Args:
        days: Number of days of inactivity threshold (default: 30). Computers
            that last contacted Jamf more than this many days ago are returned.
        page: Page number for pagination (0-indexed, default: 0)
        page_size: Number of results per page (default: 100, max: 2000)

    Returns:
        JSON with list of inactive computers including name, serial number, model,
        last contact time, and days since last contact. Also includes total count
        and the cutoff date used for the query.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

        params: dict = {
            "page": page,
            "page-size": page_size,
            "section": ["GENERAL", "HARDWARE"],
            "filter": f'general.lastContactTime=lt="{cutoff_str}"',
            "sort": "general.lastContactTime:asc",
        }
        result = await client.v1_get("computers-inventory", params=params)

        computers = result.get("results", [])
        now = datetime.now(timezone.utc)
        enriched = []
        for c in computers:
            general = c.get("general") or {}
            hardware = c.get("hardware") or {}
            last_contact = general.get("lastContactTime")
            days_since = None
            if last_contact:
                try:
                    contact_dt = datetime.fromisoformat(last_contact.replace("Z", "+00:00"))
                    days_since = (now - contact_dt).days
                except (ValueError, AttributeError):
                    pass
            enriched.append({
                "id": c.get("id"),
                "name": general.get("name"),
                "serialNumber": hardware.get("serialNumber"),
                "model": hardware.get("model"),
                "lastContactTime": last_contact,
                "daysSinceContact": days_since,
            })

        total = result.get("totalCount", len(enriched))
        summary = {
            "totalNotCheckedIn": total,
            "thresholdDays": days,
            "cutoffDate": cutoff_str,
            "page": page,
            "pageSize": page_size,
            "computers": enriched,
        }
        return format_response(summary, f"{total} computer(s) haven't checked in for {days}+ days")

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error getting inactive computers")
        return format_error(e)


@jamf_tool
async def jamf_get_os_summary() -> str:
    """Get a fleet-wide macOS version summary.

    Fetches all managed Macs and aggregates them by OS version to show the
    distribution across the fleet. Identifies the latest macOS version present
    in the fleet and shows how many devices are on it vs. older versions.

    Useful for patch compliance reporting, understanding upgrade exposure, and
    identifying devices still running outdated macOS versions.

    Returns:
        JSON with total device count, latest macOS version in the fleet, number
        of devices on the latest version vs. older versions, and a full version
        breakdown table with counts and percentages.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        all_computers: list[dict] = []
        page = 0
        total_count = None
        while True:
            result = await client.v1_get("computers-inventory", params={
                "page": page,
                "page-size": 200,
                "section": ["OPERATING_SYSTEM", "GENERAL"],
            })
            batch = result.get("results", [])
            if total_count is None:
                total_count = result.get("totalCount", 0)
            all_computers.extend(batch)
            if not batch or len(all_computers) >= (total_count or 0):
                break
            page += 1

        version_counts: dict[str, int] = {}
        for c in all_computers:
            version = (c.get("operatingSystem") or {}).get("version") or "Unknown"
            version_counts[version] = version_counts.get(version, 0) + 1

        def _version_key(v: str) -> list[int]:
            try:
                return [int(x) for x in v.split(".")]
            except (ValueError, AttributeError):
                return [0]

        known_versions = [v for v in version_counts if v != "Unknown"]
        latest = max(known_versions, key=_version_key, default="Unknown")

        total = len(all_computers)
        breakdown = sorted(
            [
                {
                    "version": v,
                    "count": cnt,
                    "percent": round(cnt / total * 100, 1) if total else 0,
                    "isLatest": v == latest,
                }
                for v, cnt in version_counts.items()
            ],
            key=lambda x: _version_key(x["version"]),
            reverse=True,
        )

        devices_on_latest = version_counts.get(latest, 0)
        summary = {
            "totalDevices": total,
            "latestVersion": latest,
            "devicesOnLatest": devices_on_latest,
            "devicesNotOnLatest": total - devices_on_latest,
            "percentOnLatest": round(devices_on_latest / total * 100, 1) if total else 0,
            "versionBreakdown": breakdown,
        }
        return format_response(summary, f"OS summary: {total} devices, latest is {latest} ({devices_on_latest} devices)")

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error getting OS summary")
        return format_error(e)


@jamf_tool
async def jamf_search_computers_by_app(
    app_name: str,
    inventory_fields: Optional[str] = None,
) -> str:
    """Find computers with a specific application installed.

    Searches Jamf inventory for all managed Macs that have a specific application
    installed. Returns the full list of computers and a breakdown by installed
    version across the fleet. Uses the Classic API's computer applications endpoint
    which provides server-side filtering.

    Requires the "Read Computer Application Usage" privilege in the Jamf Pro API
    role. If the API client lacks this privilege, the call will return a 401 error.

    Note: The app_name must match the application name as Jamf records it (e.g.,
    "Google Chrome" not "chrome"). The match is exact (not a substring search).
    If no results are returned, try checking the exact app name in Jamf inventory.

    Args:
        app_name: Application name as it appears in Jamf inventory (e.g.,
            "Google Chrome", "Microsoft Word", "Zoom", "Safari").
        inventory_fields: Optional comma-separated display fields to include per
            computer. Spaces must be percent-encoded (e.g.,
            "Operating%20System,Last%20Check-in,Username"). When provided, uses
            the extended /inventory/{fields} endpoint variant.

    Returns:
        JSON with total number of computers that have the app installed, a version
        breakdown showing how many computers run each version, and the list of
        unique computers (id, name, serial number, plus any inventory_fields).
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        encoded_name = quote(app_name, safe="")
        if inventory_fields:
            resource_path = f"computerapplications/application/{encoded_name}/inventory/{inventory_fields}"
        else:
            resource_path = f"computerapplications/application/{encoded_name}"
        result = await client.classic_get(resource_path)

        def _ensure_list(val: Any) -> list:
            if val is None:
                return []
            return val if isinstance(val, list) else [val]

        unique_raw = result.get("unique_computers") or {}
        unique_computers = _ensure_list(unique_raw.get("computer"))

        versions_raw = result.get("versions") or {}
        version_list = _ensure_list(versions_raw.get("version"))

        version_breakdown = []
        for v in version_list:
            if not isinstance(v, dict):
                continue
            computers_in_v_raw = v.get("computers") or {}
            if isinstance(computers_in_v_raw, dict):
                computers_in_v = _ensure_list(computers_in_v_raw.get("computer"))
            else:
                computers_in_v = _ensure_list(computers_in_v_raw)
            version_breakdown.append({
                "version": v.get("number", "Unknown"),
                "computerCount": len(computers_in_v),
            })

        version_breakdown.sort(key=lambda x: x["computerCount"], reverse=True)

        summary = {
            "appName": app_name,
            "totalComputers": len(unique_computers),
            "versionBreakdown": version_breakdown,
            "computers": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "serialNumber": c.get("serial_number"),
                }
                for c in unique_computers
            ],
        }
        return format_response(summary, f"Found {len(unique_computers)} computer(s) with '{app_name}' installed")

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error searching computers by app")
        return format_error(e)
