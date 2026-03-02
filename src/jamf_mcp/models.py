# Copyright 2026, Jamf Software LLC
"""Pydantic models for Jamf Pro API data validation.

These models are used for validating input data to MCP tools and
structuring responses from the Jamf Pro API.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Computer Models
# =============================================================================


class ComputerGeneralUpdate(BaseModel):
    """Model for updating computer general information."""

    name: Optional[str] = Field(None, description="Computer name")
    asset_tag: Optional[str] = Field(None, description="Asset tag")
    barcode_1: Optional[str] = Field(None, description="Barcode 1")
    barcode_2: Optional[str] = Field(None, description="Barcode 2")
    po_number: Optional[str] = Field(None, description="Purchase order number")
    po_date: Optional[str] = Field(None, description="Purchase order date (YYYY-MM-DD)")
    vendor: Optional[str] = Field(None, description="Vendor name")
    lease_expiration: Optional[str] = Field(None, description="Lease expiration date")
    warranty_expiration: Optional[str] = Field(None, description="Warranty expiration date")


class ComputerLocationUpdate(BaseModel):
    """Model for updating computer location/user assignment."""

    username: Optional[str] = Field(None, description="Assigned username")
    realname: Optional[str] = Field(None, description="User's real name")
    email: Optional[str] = Field(None, description="User's email address")
    position: Optional[str] = Field(None, description="User's position/title")
    phone: Optional[str] = Field(None, description="Phone number")
    phone_number: Optional[str] = Field(None, description="Alternative phone number")
    department: Optional[str] = Field(None, description="Department name")
    building: Optional[str] = Field(None, description="Building name")
    room: Optional[str] = Field(None, description="Room number")


class ComputerExtensionAttributeUpdate(BaseModel):
    """Model for updating a computer extension attribute."""

    id: int = Field(..., description="Extension attribute definition ID")
    value: str = Field(..., description="Value to set for the extension attribute")


class ComputerUpdate(BaseModel):
    """Model for updating computer information."""

    general: Optional[ComputerGeneralUpdate] = Field(None, description="General computer info")
    location: Optional[ComputerLocationUpdate] = Field(None, description="Location and user info")
    extension_attributes: Optional[list[ComputerExtensionAttributeUpdate]] = Field(
        None, description="Extension attribute values"
    )


# =============================================================================
# Mobile Device Models
# =============================================================================


class MobileDeviceGeneralUpdate(BaseModel):
    """Model for updating mobile device general information."""

    name: Optional[str] = Field(None, description="Device name")
    asset_tag: Optional[str] = Field(None, description="Asset tag")
    po_number: Optional[str] = Field(None, description="Purchase order number")
    po_date: Optional[str] = Field(None, description="Purchase order date")
    vendor: Optional[str] = Field(None, description="Vendor name")
    lease_expiration: Optional[str] = Field(None, description="Lease expiration date")
    warranty_expiration: Optional[str] = Field(None, description="Warranty expiration date")
    airplay_password: Optional[str] = Field(None, description="AirPlay password")


class MobileDeviceLocationUpdate(BaseModel):
    """Model for updating mobile device location."""

    username: Optional[str] = Field(None, description="Assigned username")
    realname: Optional[str] = Field(None, description="User's real name")
    email: Optional[str] = Field(None, description="User's email address")
    position: Optional[str] = Field(None, description="User's position")
    phone: Optional[str] = Field(None, description="Phone number")
    department: Optional[str] = Field(None, description="Department name")
    building: Optional[str] = Field(None, description="Building name")
    room: Optional[str] = Field(None, description="Room number")


class MobileDeviceUpdate(BaseModel):
    """Model for updating mobile device information."""

    general: Optional[MobileDeviceGeneralUpdate] = Field(None, description="General device info")
    location: Optional[MobileDeviceLocationUpdate] = Field(None, description="Location info")


# =============================================================================
# User Models
# =============================================================================


class UserUpdate(BaseModel):
    """Model for updating user information."""

    name: Optional[str] = Field(None, description="Username")
    full_name: Optional[str] = Field(None, description="Full name")
    email: Optional[str] = Field(None, description="Email address")
    email_address: Optional[str] = Field(None, description="Email address (alternate)")
    phone_number: Optional[str] = Field(None, description="Phone number")
    position: Optional[str] = Field(None, description="Position/title")
    enable_custom_photo_url: Optional[bool] = Field(None, description="Enable custom photo URL")
    custom_photo_url: Optional[str] = Field(None, description="Custom photo URL")
    ldap_server_id: Optional[int] = Field(None, description="LDAP server ID")
    sites: Optional[list[dict]] = Field(None, description="Site assignments")


# =============================================================================
# Group Models
# =============================================================================


class SmartGroupCriterion(BaseModel):
    """Model for a smart group criterion."""

    name: str = Field(..., description="Criterion name (e.g., 'Computer Name', 'Department')")
    priority: int = Field(0, description="Criterion priority (order)")
    and_or: str = Field("and", description="Logical operator: 'and' or 'or'")
    search_type: str = Field(
        ...,
        description="Search type: 'is', 'is not', 'like', 'not like', 'has', 'does not have', etc.",
    )
    value: str = Field(..., description="Value to match")
    opening_paren: bool = Field(False, description="Opening parenthesis before criterion")
    closing_paren: bool = Field(False, description="Closing parenthesis after criterion")


class SmartGroupCreate(BaseModel):
    """Model for creating a smart group."""

    name: str = Field(..., description="Smart group name")
    site_id: Optional[int] = Field(None, description="Site ID (-1 for none)")
    criteria: list[SmartGroupCriterion] = Field(..., description="List of criteria")


class StaticGroupCreate(BaseModel):
    """Model for creating a static group."""

    name: str = Field(..., description="Static group name")
    site_id: Optional[int] = Field(None, description="Site ID (-1 for none)")
    device_ids: list[int] = Field(default_factory=list, description="List of device IDs to include")


# =============================================================================
# Extension Attribute Models
# =============================================================================


class ExtensionAttributeCreate(BaseModel):
    """Model for creating an extension attribute."""

    name: str = Field(..., description="Extension attribute name")
    description: Optional[str] = Field(None, description="Description")
    data_type: str = Field(
        "String", description="Data type: 'String', 'Integer', 'Date'"
    )
    input_type: str = Field(
        "Text Field",
        description="Input type: 'Text Field', 'Pop-up Menu', 'Script', 'LDAP Attribute Mapping'",
    )
    popup_choices: Optional[list[str]] = Field(
        None, description="Choices for Pop-up Menu input type"
    )
    script: Optional[str] = Field(None, description="Script contents for Script input type")
    inventory_display: str = Field(
        "Extension Attributes",
        description="Inventory display section: 'General', 'Hardware', 'Operating System', etc.",
    )
    enabled: bool = Field(True, description="Whether the extension attribute is enabled")


# =============================================================================
# Category Models
# =============================================================================


class CategoryCreate(BaseModel):
    """Model for creating a category."""

    name: str = Field(..., description="Category name")
    priority: int = Field(9, description="Category priority (1-20, lower is higher priority)")


# =============================================================================
# Pagination Models
# =============================================================================


class PaginationParams(BaseModel):
    """Model for pagination parameters."""

    page: int = Field(0, ge=0, description="Page number (0-indexed)")
    page_size: int = Field(100, ge=1, le=2000, description="Number of items per page")
    sort: Optional[str] = Field(None, description="Sort field and direction (e.g., 'name:asc')")
    filter: Optional[str] = Field(None, description="Filter expression")


# =============================================================================
# Response Models
# =============================================================================


class ToolResponse(BaseModel):
    """Standard response model for tool operations."""

    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    data: Optional[Any] = Field(None, description="Response data if applicable")
