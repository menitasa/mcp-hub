# Copyright 2026, Jamf Software LLC
"""Extension attribute management tools for Jamf Pro.

This module provides tools for retrieving and creating extension attributes
which define custom inventory fields for computers, mobile devices, and users.

Distinction between tools:
  - jamf_get_extension_attributes  : EA *definitions* (schema, data type, script)
  - jamf_get_computer_ea_values    : EA *values* on a specific computer
  - jamf_search_computers_by_ea    : Find computers where an EA matches a value
"""

import logging
from typing import Optional

from ..client import JamfAPIError
from ._common import format_error, format_response, get_client_safe
from ._registry import jamf_tool

logger = logging.getLogger(__name__)


@jamf_tool
async def jamf_get_extension_attributes(
    ea_type: str,
    ea_id: Optional[int] = None,
    name: Optional[str] = None,
    page: int = 0,
    page_size: int = 100,
) -> str:
    """Get extension attributes from Jamf Pro.

    Retrieves extension attributes which define custom inventory fields.
    Extension attributes allow collecting additional device or user information
    beyond the standard inventory.

    Args:
        ea_type: Type of extension attribute (REQUIRED):
            - "computer" - Custom fields for macOS computers
            - "mobile_device" - Custom fields for iOS/iPadOS devices
            - "user" - Custom fields for Jamf Pro users
        ea_id: Specific extension attribute ID to retrieve full definition
        name: Filter by name (partial match)
        page: Page number for pagination (0-indexed, default: 0)
        page_size: Number of results per page (default: 100)

    Returns:
        JSON containing extension attribute list or detailed definition
        including input type, data type, and script contents (if applicable).
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        if ea_type == "computer":
            if ea_id:
                result = await client.classic_get("computerextensionattributes", ea_id)
                return format_response(
                    result.get("computer_extension_attribute", result),
                    f"Retrieved computer extension attribute ID {ea_id}"
                )

            result = await client.classic_get("computerextensionattributes")
            eas = result.get("computer_extension_attributes", [])
        elif ea_type == "mobile_device":
            if ea_id:
                result = await client.classic_get("mobiledeviceextensionattributes", ea_id)
                return format_response(
                    result.get("mobile_device_extension_attribute", result),
                    f"Retrieved mobile device extension attribute ID {ea_id}"
                )

            result = await client.classic_get("mobiledeviceextensionattributes")
            eas = result.get("mobile_device_extension_attributes", [])
        elif ea_type == "user":
            if ea_id:
                result = await client.classic_get("userextensionattributes", ea_id)
                return format_response(
                    result.get("user_extension_attribute", result),
                    f"Retrieved user extension attribute ID {ea_id}"
                )

            result = await client.classic_get("userextensionattributes")
            eas = result.get("user_extension_attributes", [])
        else:
            return format_error(
                ValueError(f"Invalid ea_type '{ea_type}'. Must be 'computer', 'mobile_device', or 'user'")
            )

        if name:
            eas = [ea for ea in eas if name.lower() in ea.get("name", "").lower()]

        start = page * page_size
        end = start + page_size
        paginated = eas[start:end]

        return format_response(
            {"extension_attributes": paginated, "totalCount": len(eas)},
            f"Retrieved {len(paginated)} {ea_type} extension attributes (total: {len(eas)})"
        )

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error getting extension attributes")
        return format_error(e)


@jamf_tool
async def jamf_create_extension_attribute(
    name: str,
    ea_type: str,
    data_type: str = "String",
    description: str = "",
    input_type: str = "Text Field",
    script_contents: Optional[str] = None,
    popup_choices: Optional[list[str]] = None,
    inventory_display: str = "Extension Attributes",
) -> str:
    """Create an extension attribute in Jamf Pro.

    Creates a new custom inventory field for computers, mobile devices, or users.
    Extension attributes extend the inventory data collected from devices.

    Args:
        name: Extension attribute name (required, must be unique)
        ea_type: Type (REQUIRED): "computer", "mobile_device", or "user"
        data_type: Data type for the value (default: "String"):
            - "String" - Text values
            - "Integer" - Numeric values
            - "Date" - Date values (YYYY-MM-DD format)
        description: Description shown in the Jamf Pro UI
        input_type: How values are collected (default: "Text Field"):
            - "Text Field" - Manual text entry
            - "Pop-up Menu" - Selection from predefined choices
            - "script" - Collected via script (computer only)
        script_contents: Script code (required if input_type is "script")
            Only valid for computer extension attributes
        popup_choices: List of choices (required if input_type is "Pop-up Menu")
        inventory_display: Display section in inventory (default: "Extension Attributes")

    Returns:
        JSON with creation result including new extension attribute ID.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        input_type_data = {"type": input_type}

        if input_type.lower() == "script" and script_contents:
            if ea_type != "computer":
                return format_error(
                    ValueError("Script input type is only valid for computer extension attributes")
                )
            input_type_data["script"] = script_contents
        elif input_type.lower() == "pop-up menu" and popup_choices:
            input_type_data["popup_choices"] = popup_choices

        if ea_type == "computer":
            resource = "computerextensionattributes"
            payload = {
                "computer_extension_attribute": {
                    "name": name,
                    "description": description,
                    "data_type": data_type,
                    "input_type": input_type_data,
                    "inventory_display": inventory_display,
                    "enabled": True,
                }
            }
        elif ea_type == "mobile_device":
            resource = "mobiledeviceextensionattributes"
            payload = {
                "mobile_device_extension_attribute": {
                    "name": name,
                    "description": description,
                    "data_type": data_type,
                    "input_type": input_type_data,
                    "inventory_display": inventory_display,
                }
            }
        elif ea_type == "user":
            resource = "userextensionattributes"
            payload = {
                "user_extension_attribute": {
                    "name": name,
                    "description": description,
                    "data_type": data_type,
                    "input_type": input_type_data,
                }
            }
        else:
            return format_error(
                ValueError(f"Invalid ea_type '{ea_type}'. Must be 'computer', 'mobile_device', or 'user'")
            )

        result = await client.classic_post(resource, payload)
        return format_response(result, f"Created {ea_type} extension attribute '{name}'")

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error creating extension attribute")
        return format_error(e)


@jamf_tool
async def jamf_get_computer_ea_values(
    computer_id: int,
    ea_name: Optional[str] = None,
) -> str:
    """Get extension attribute values for a specific computer.

    Returns the actual EA values collected from a computer's last inventory
    check — not the EA definitions. Each entry shows the EA name, definition
    ID, and the current value reported by the device.

    Use jamf_get_extension_attributes to inspect EA definitions (data type,
    script contents, input type). Use this tool to read what a device
    actually reported.

    Args:
        computer_id: Jamf Pro computer ID (required)
        ea_name: Optional filter — return only EAs whose name contains this
            string (case-insensitive). Omit to return all EA values.

    Returns:
        JSON list of extension attribute values with name, definitionId, and
        current value for the specified computer.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        result = await client.get_computer_inventory(
            computer_id=computer_id,
            section=["GENERAL", "EXTENSION_ATTRIBUTES"],
        )

        computer_name = result.get("general", {}).get("name", f"ID {computer_id}")
        raw_eas = result.get("extensionAttributes", [])

        if ea_name:
            raw_eas = [
                ea for ea in raw_eas
                if ea_name.lower() in ea.get("name", "").lower()
            ]

        ea_values = [
            {
                "name": ea.get("name"),
                "definitionId": ea.get("definitionId"),
                "value": ea.get("values", [None])[0] if ea.get("values") else None,
            }
            for ea in raw_eas
        ]

        return format_response(
            {"computer": computer_name, "computerId": computer_id, "extensionAttributes": ea_values},
            f"Retrieved {len(ea_values)} EA values for {computer_name}",
        )

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error getting computer EA values")
        return format_error(e)


@jamf_tool
async def jamf_search_computers_by_ea(
    ea_name: str,
    ea_value: str,
    page: int = 0,
    page_size: int = 100,
) -> str:
    """Find computers where a specific extension attribute matches a value.

    Fetches computers with extension attribute data and filters for devices
    where the named EA contains the specified value (case-insensitive partial
    match). Returns computer name, ID, serial number, and the matched EA value.

    Useful for investigations — e.g., find all Macs where "FileVault Status"
    is "Off", or where a custom compliance EA equals "Non-Compliant".

    Args:
        ea_name: Extension attribute name to match against (case-insensitive,
            partial match supported). Example: "FileVault Status"
        ea_value: Value to search for (case-insensitive, partial match).
            Example: "Off" or "Non-Compliant"
        page: Page number for pagination (0-indexed, default: 0)
        page_size: Number of computers to fetch per page (default: 100, max: 2000)

    Returns:
        JSON with list of matching computers, total match count, and the
        matched EA name/value for each result.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        params: dict = {
            "page": page,
            "page-size": page_size,
            "section": ["GENERAL", "HARDWARE", "EXTENSION_ATTRIBUTES"],
        }
        result = await client.v1_get("computers-inventory", params=params)
        computers = result.get("results", [])
        total_fetched = result.get("totalCount", len(computers))

        matches = []
        for computer in computers:
            general = computer.get("general", {})
            hardware = computer.get("hardware", {})
            for ea in computer.get("extensionAttributes", []):
                if ea_name.lower() not in ea.get("name", "").lower():
                    continue
                value = ea.get("values", [None])[0] if ea.get("values") else None
                if value is not None and ea_value.lower() in str(value).lower():
                    matches.append({
                        "id": computer.get("id"),
                        "name": general.get("name"),
                        "serialNumber": hardware.get("serialNumber"),
                        "matchedEa": {
                            "name": ea.get("name"),
                            "definitionId": ea.get("definitionId"),
                            "value": value,
                        },
                    })
                    break  # one match per computer is enough

        return format_response(
            {
                "matches": matches,
                "matchCount": len(matches),
                "totalComputersScanned": len(computers),
                "totalComputersInJamf": total_fetched,
                "searchCriteria": {"ea_name": ea_name, "ea_value": ea_value, "page": page},
                "_note": (
                    "Filtered from the fetched page only. "
                    "Increment 'page' to search additional computers."
                ) if total_fetched > len(computers) else None,
            },
            f"Found {len(matches)} computers where '{ea_name}' matches '{ea_value}'",
        )

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error searching computers by EA value")
        return format_error(e)
